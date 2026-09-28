'use client';

/**
 * 「导入试题」面板：选文件（.md/.pdf/.docx，≤100 MiB 前端先校验）→ 上传 →
 * 成功后由父级跳到校对页。上传失败时保留已选文件与已填分类，可直接重试。
 */

import { useState } from 'react';
import { Upload } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { createQuestionImport } from '@/services/question-bank-api';
import { asApiError, errorText } from './hooks';
import {
  QUESTION_IMPORT_ACCEPT,
  QUESTION_IMPORT_MAX_MIB,
  QUESTION_IMPORT_SUFFIX_HINT,
  questionImportFileError,
} from './question-file';
import type { TaxonomyIndex } from './taxonomy';

export function ImportQuestionPanel({
  taxonomy,
  onClose,
  onImported,
}: {
  taxonomy: TaxonomyIndex;
  onClose: () => void;
  onImported: (importId: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [subjectId, setSubjectId] = useState('');
  const [gradeId, setGradeId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function pick(next: File | null) {
    setFile(next);
    setError(next ? questionImportFileError(next) : null);
  }

  async function submit() {
    if (!file) {
      setError('请先选择试题文件。');
      return;
    }
    const invalid = questionImportFileError(file);
    if (invalid) {
      setError(invalid);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const detail = await createQuestionImport(file, { subjectId, gradeId });
      onImported(detail.importId);
    } catch (cause) {
      const apiError = asApiError(cause);
      setError(
        `上传失败（${apiError.code}）：${errorText(cause)} 已选择的文件与分类保留，可直接重试。`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="导入试题" onClose={onClose}>
      <div className="qb-panel">
        <p className="qb-hint">
          支持 {QUESTION_IMPORT_SUFFIX_HINT}，单文件不超过 {QUESTION_IMPORT_MAX_MIB} MiB。
          题目来自服务端对文件的本地解析与规则拆题，导入后需要人工校对才能入库。
        </p>

        <label className="qb-field" htmlFor="qb-import-file">
          试题文件
          <input
            id="qb-import-file"
            type="file"
            accept={QUESTION_IMPORT_ACCEPT}
            disabled={busy}
            onChange={(event) => pick(event.target.files?.[0] ?? null)}
          />
        </label>
        {file && (
          <p className="qb-file-line">
            已选择：{file.name}（{Math.max(1, Math.round(file.size / 1024))} KiB）
          </p>
        )}

        <div className="qb-form-grid">
          <TaxonomyInput
            id="qb-import-subject"
            label="学科（可选）"
            value={subjectId}
            options={taxonomy.subjects}
            ready={taxonomy.ready}
            disabled={busy}
            onChange={setSubjectId}
          />
          <TaxonomyInput
            id="qb-import-grade"
            label="年级（可选）"
            value={gradeId}
            options={taxonomy.grades}
            ready={taxonomy.ready}
            disabled={busy}
            onChange={setGradeId}
          />
        </div>
        {!taxonomy.ready && (
          <p className="qb-hint">分类字典未读取成功：可先留空导入，稍后在校对页补齐分类。</p>
        )}

        {error && (
          <p className="space-banner error" role="alert">
            {error}
          </p>
        )}

        <div className="qb-actions">
          <button className="space-button primary" onClick={() => void submit()} disabled={busy}>
            <Upload size={14} aria-hidden />
            {busy ? '上传中…' : '上传并解析'}
          </button>
          <button className="space-button" onClick={onClose} disabled={busy}>
            取消
          </button>
        </div>
      </div>
    </Modal>
  );
}

function TaxonomyInput({
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
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}
