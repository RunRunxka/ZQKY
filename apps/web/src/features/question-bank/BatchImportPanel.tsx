'use client';

/**
 * 「批量导入」面板（R4-FE 2026-10-11）。
 *
 * 参考图只保留顶部两个按钮，导入相关动作全部收进本面板：
 * 1. **从教材课后习题提取**（`POST /question-imports/from-textbook`）：教材未入库 / 未索引时
 *    服务端原因原样展示（503 教材目录未装配、422 没有可提取的课后习题、413 超上限），
 *    成功只生成**待校对草稿**并刷新下方批次列表，绝不宣称已入库；
 * 2. 上传试题文件（.md/.pdf/.docx，≤ 上限）：成功后进入校对页；
 * 3. 导入批次列表（放弃 / 彻底删除与 409 引用守卫都在 `ImportBatchList` 内）。
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { FileUp, RefreshCw, Upload } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { createQuestionImport, importQuestionsFromTextbook } from '@/services/question-bank-api';
import { ImportBatchList } from './ImportBatchList';
import { asApiError, errorText } from './hooks';
import {
  QUESTION_IMPORT_ACCEPT,
  QUESTION_IMPORT_MAX_MIB,
  QUESTION_IMPORT_SUFFIX_HINT,
  questionImportFileError,
} from './question-file';
import type { TaxonomyIndex } from './taxonomy';

export function BatchImportPanel({
  taxonomy,
  onClose,
}: {
  taxonomy: TaxonomyIndex;
  onClose: () => void;
}) {
  const router = useRouter();
  const [batchToken, setBatchToken] = useState(0);

  const [extractSubjectId, setExtractSubjectId] = useState(
    taxonomy.subjects[0]?.id ?? '',
  );
  const [extracting, setExtracting] = useState(false);
  const [extractNotice, setExtractNotice] = useState<
    { kind: 'info' | 'error'; text: string; importId?: string } | null
  >(null);

  const [file, setFile] = useState<File | null>(null);
  const [subjectId, setSubjectId] = useState('');
  const [gradeId, setGradeId] = useState('');
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function extractFromTextbook() {
    if (extracting) return;
    if (!extractSubjectId.trim()) {
      setExtractNotice({ kind: 'error', text: '请先选择学科：教材习题按学科提取。' });
      return;
    }
    setExtracting(true);
    setExtractNotice(null);
    try {
      const detail = await importQuestionsFromTextbook({ subjectId: extractSubjectId.trim() });
      setBatchToken((value) => value + 1);
      setExtractNotice({
        kind: 'info',
        importId: detail.importId,
        text: `已从教材课后习题提取为导入草稿（草稿 ${detail.draftCount} 道，需人工校对）：可在下方批次列表或校对页打开。`,
      });
    } catch (cause) {
      const apiError = asApiError(cause);
      // 服务端原因原样展示（教材未就绪、没有习题区域、超上限等都在这里）
      setExtractNotice({
        kind: 'error',
        text: `提取失败（${apiError.code}）：${errorText(cause)}`,
      });
    } finally {
      setExtracting(false);
    }
  }

  function pick(next: File | null) {
    setFile(next);
    setFileError(next ? questionImportFileError(next) : null);
  }

  async function submitFile() {
    if (!file) {
      setFileError('请先选择试题文件。');
      return;
    }
    const invalid = questionImportFileError(file);
    if (invalid) {
      setFileError(invalid);
      return;
    }
    setUploading(true);
    setFileError(null);
    try {
      const detail = await createQuestionImport(file, { subjectId, gradeId });
      setBatchToken((value) => value + 1);
      router.push(`/question-bank/imports/${encodeURIComponent(detail.importId)}`);
    } catch (cause) {
      const apiError = asApiError(cause);
      setFileError(
        `上传失败（${apiError.code}）：${errorText(cause)} 已选择的文件与分类保留，可直接重试。`,
      );
    } finally {
      setUploading(false);
    }
  }

  return (
    <Modal title="批量导入" onClose={onClose}>
      <div className="qb-panel">
        <p className="qb-hint">
          题目来自服务端对文件的本地解析与规则拆题；教材提取与 AI 结果都只生成「待校对草稿」，
          必须人工校对确认后才入库。
        </p>

        <section className="qb-import-section" aria-label="从教材课后习题提取">
          <h3>从教材课后习题提取</h3>
          <p className="qb-hint">
            从已入库教材的课后习题区域（exercise 区）提取为导入草稿；教材未入库、未完成索引或没有
            习题区域时按服务端原因原样提示，不伪造成功。
          </p>
          <div className="qb-extract-row">
            <TaxonomyField
              id="qb-extract-subject"
              label="学科"
              value={extractSubjectId}
              options={taxonomy.subjects}
              ready={taxonomy.ready}
              disabled={extracting}
              onChange={setExtractSubjectId}
            />
            <button
              className="space-button primary"
              type="button"
              disabled={extracting}
              onClick={() => void extractFromTextbook()}
            >
              <FileUp size={14} aria-hidden />
              {extracting ? '提取中…' : '从教材课后习题提取'}
            </button>
          </div>
          {extractNotice && (
            <p
              className={extractNotice.kind === 'error' ? 'space-banner error' : 'space-banner info'}
              role={extractNotice.kind === 'error' ? 'alert' : 'status'}
            >
              {extractNotice.text}
              {extractNotice.importId && (
                <button
                  className="space-button"
                  type="button"
                  onClick={() =>
                    router.push(`/question-bank/imports/${encodeURIComponent(extractNotice.importId as string)}`)
                  }
                >
                  打开校对页
                </button>
              )}
            </p>
          )}
        </section>

        <section className="qb-import-section" aria-label="上传试题文件">
          <h3>上传试题文件</h3>
          <p className="qb-hint">
            支持 {QUESTION_IMPORT_SUFFIX_HINT}，单文件不超过 {QUESTION_IMPORT_MAX_MIB} MiB。
          </p>
          <label className="qb-field" htmlFor="qb-import-file">
            试题文件
            <input
              id="qb-import-file"
              type="file"
              accept={QUESTION_IMPORT_ACCEPT}
              disabled={uploading}
              onChange={(event) => pick(event.target.files?.[0] ?? null)}
            />
          </label>
          {file && (
            <p className="qb-file-line">
              已选择：{file.name}（{Math.max(1, Math.round(file.size / 1024))} KiB）
            </p>
          )}
          <div className="qb-form-grid">
            <TaxonomyField
              id="qb-import-subject"
              label="学科（可选）"
              value={subjectId}
              options={taxonomy.subjects}
              ready={taxonomy.ready}
              disabled={uploading}
              onChange={setSubjectId}
            />
            <TaxonomyField
              id="qb-import-grade"
              label="年级（可选）"
              value={gradeId}
              options={taxonomy.grades}
              ready={taxonomy.ready}
              disabled={uploading}
              onChange={setGradeId}
            />
          </div>
          {!taxonomy.ready && (
            <p className="qb-hint">分类字典未读取成功：可先留空导入，稍后在校对页补齐分类。</p>
          )}
          {fileError && (
            <p className="space-banner error" role="alert">
              {fileError}
            </p>
          )}
          <div className="qb-actions">
            <button
              className="space-button primary"
              type="button"
              disabled={uploading}
              onClick={() => void submitFile()}
            >
              <Upload size={14} aria-hidden />
              {uploading ? '上传中…' : '上传并解析'}
            </button>
          </div>
        </section>

        <section className="qb-import-section" aria-label="导入批次">
          <div className="qb-card-head">
            <h3>导入批次</h3>
            <button
              className="space-button"
              type="button"
              onClick={() => setBatchToken((value) => value + 1)}
            >
              <RefreshCw size={14} aria-hidden />
              刷新列表
            </button>
          </div>
          <ImportBatchList refreshToken={batchToken} />
        </section>
      </div>
    </Modal>
  );
}

function TaxonomyField({
  id,
  label,
  value,
  options,
  ready,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: { id: string; label: string }[];
  ready: boolean;
  disabled: boolean;
  onChange: (next: string) => void;
}) {
  return (
    <label className="qb-field" htmlFor={id}>
      {label}
      {ready ? (
        <select
          id={id}
          className="space-select"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">未设置</option>
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          value={value}
          disabled={disabled}
          placeholder="分类 id"
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}
