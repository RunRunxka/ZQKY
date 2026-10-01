'use client';

/**
 * 表格导入：上传（.xlsx/.csv，multipart + subjectId）→ 批次列表 → 选中批次进入校对。
 *
 * 列表读取失败显示错误码与重试（**不当空目录**）；AI 候选批次用独立 chip 与说明
 * 与人工表格导入区分（候选未入库）。
 */

import { useState } from 'react';
import { RefreshCw, Upload } from 'lucide-react';
import type { KnowledgeImportSummary } from '@/contracts/knowledge';
import { Modal } from '@/components/ui/Modal';
import { createKnowledgeImport, listKnowledgeImports } from '@/services/knowledge-points-api';
import { asApiError, useAsyncResource } from './hooks';
import {
  formatDateTime,
  importSourceLabel,
  importStateChipClass,
  importStateLabel,
} from './labels';
import { ImportReviewPanel } from './ImportReviewPanel';

const ACCEPT = '.xlsx,.csv,.txt';

export function ImportPanel({
  subjects,
  taxonomyReady,
  defaultSubjectId,
  selectedImportId,
  onSelectImport,
  refreshToken,
  onConfirmed,
}: {
  subjects: { id: string; label: string }[];
  taxonomyReady: boolean;
  defaultSubjectId: string;
  selectedImportId: string | null;
  onSelectImport: (importId: string | null) => void;
  refreshToken: number;
  onConfirmed?: () => void;
}) {
  const [listTick, setListTick] = useState(0);
  const imports = useAsyncResource(
    (signal) => listKnowledgeImports({ limit: 100 }, signal),
    `kp-imports|${refreshToken}|${listTick}`,
  );
  const [uploadOpen, setUploadOpen] = useState(false);

  const items: KnowledgeImportSummary[] =
    imports.state.phase === 'ready' ? imports.state.data.items : [];

  return (
    <section className="kp-imports" aria-label="表格导入与校对">
      <div className="space-toolbar">
        <button className="space-button primary" onClick={() => setUploadOpen(true)}>
          <Upload size={14} aria-hidden />
          上传表格
        </button>
        <button className="space-button" onClick={imports.reload}>
          <RefreshCw size={14} aria-hidden />
          刷新批次
        </button>
        <span className="kp-hint">
          支持 .xlsx / .csv（.txt 按 CSV
          文本解析）；上传只生成待校对预览，确认后才写入正式知识点表。
        </span>
      </div>

      <div className="space-bank-layout kp-import-layout">
        <nav className="kp-import-rail" aria-label="导入批次列表">
          {imports.state.phase === 'loading' && (
            <div
              className="space-skeleton"
              style={{ height: 64 }}
              aria-busy="true"
              aria-label="正在读取导入批次"
            />
          )}

          {imports.state.phase === 'failed' && (
            <div className="space-banner error" role="alert">
              <span>
                批次读取失败（{imports.state.error.code}）：{imports.state.error.message}
              </span>
              <button className="space-button" onClick={imports.reload}>
                重试
              </button>
            </div>
          )}

          {imports.state.phase === 'ready' && items.length === 0 && (
            <div className="space-empty">
              <strong>还没有导入批次</strong>
              <span>上传 .xlsx / .csv 表格后会先在这里生成待校对预览。</span>
            </div>
          )}

          {items.map((item) => (
            <button
              key={item.importId}
              data-testid={`kp-import-card-${item.importId}`}
              className={
                item.importId === selectedImportId ? 'kp-import-card current' : 'kp-import-card'
              }
              aria-current={item.importId === selectedImportId}
              onClick={() => onSelectImport(item.importId)}
            >
              <span className="kp-import-name">
                {item.source === 'ai' ? 'AI 候选批次' : '表格批次'} · {item.importId.slice(0, 8)}
              </span>
              <span className="space-meta-row">
                <span className={item.source === 'ai' ? 'space-chip amber' : 'space-chip'}>
                  {importSourceLabel(item.source)}
                </span>
                <span className={importStateChipClass(item.state)}>
                  {importStateLabel(item.state)}
                </span>
                <span className="space-chip">行 {item.rowCount}</span>
                {item.blockingIssueCount > 0 && (
                  <span className="space-chip amber">阻断 {item.blockingIssueCount}</span>
                )}
              </span>
              <span className="kp-hint">{formatDateTime(item.updatedAt)}</span>
            </button>
          ))}
        </nav>

        <div className="space-bank-main">
          {selectedImportId ? (
            <ImportReviewPanel
              key={selectedImportId}
              importId={selectedImportId}
              onChanged={() => setListTick((value) => value + 1)}
              onConfirmed={() => {
                setListTick((value) => value + 1);
                onConfirmed?.();
              }}
            />
          ) : (
            <div className="space-empty">
              <strong>未选择批次</strong>
              <span>从左侧选择一个批次进行预览校对，或上传新表格。</span>
            </div>
          )}
        </div>
      </div>

      {uploadOpen && (
        <UploadDialog
          subjects={subjects}
          taxonomyReady={taxonomyReady}
          defaultSubjectId={defaultSubjectId}
          onClose={() => setUploadOpen(false)}
          onUploaded={(importId) => {
            setUploadOpen(false);
            setListTick((value) => value + 1);
            onSelectImport(importId);
          }}
        />
      )}
    </section>
  );
}

function UploadDialog({
  subjects,
  taxonomyReady,
  defaultSubjectId,
  onClose,
  onUploaded,
}: {
  subjects: { id: string; label: string }[];
  taxonomyReady: boolean;
  defaultSubjectId: string;
  onClose: () => void;
  onUploaded: (importId: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [subjectId, setSubjectId] = useState(defaultSubjectId);
  const [sheetName, setSheetName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!file) {
      setError('请先选择表格文件。');
      return;
    }
    if (!subjectId.trim()) {
      setError('请选择或填写批次学科（后端必填 subjectId）。');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createKnowledgeImport(file, {
        subjectId: subjectId.trim(),
        sheetName: sheetName.trim() || null,
      });
      onUploaded(created.importId);
    } catch (cause) {
      const apiError = asApiError(cause);
      setError(
        `上传失败（${apiError.code}）：${apiError.message} 已选文件与学科保留，可直接重试。`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="上传知识点表格" onClose={onClose}>
      <div className="kp-form">
        <p className="kp-hint">
          表头可用「学科/编码/名称/说明/父级/别名」等中文同义词自动映射；上传后先预览校对，确认才入库。
        </p>
        <label className="kp-field">
          <span className="kp-field-label">表格文件（.xlsx / .csv）</span>
          <input
            type="file"
            accept={ACCEPT}
            aria-label="表格文件"
            disabled={busy}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        {file && (
          <p className="kp-hint">
            已选择：{file.name}（{Math.max(1, Math.round(file.size / 1024))} KiB）
          </p>
        )}
        <label className="kp-field">
          <span className="kp-field-label">批次学科（必填）</span>
          {taxonomyReady ? (
            <select
              className="space-select"
              value={subjectId}
              aria-label="批次学科"
              disabled={busy}
              onChange={(event) => setSubjectId(event.target.value)}
            >
              <option value="">请选择学科</option>
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={subjectId}
              aria-label="批次学科"
              placeholder="学科 id（如 math）"
              disabled={busy}
              onChange={(event) => setSubjectId(event.target.value)}
            />
          )}
        </label>
        <label className="kp-field">
          <span className="kp-field-label">工作表名（可选，多表 XLSX 用）</span>
          <input
            value={sheetName}
            aria-label="工作表名"
            disabled={busy}
            onChange={(event) => setSheetName(event.target.value)}
          />
        </label>
        {error && (
          <p className="space-banner error" role="alert">
            {error}
          </p>
        )}
        <div className="kp-actions">
          <button className="space-button primary" disabled={busy} onClick={() => void submit()}>
            <Upload size={14} aria-hidden />
            {busy ? '上传中…' : '上传并解析'}
          </button>
          <button className="space-button" disabled={busy} onClick={onClose}>
            取消
          </button>
        </div>
      </div>
    </Modal>
  );
}
