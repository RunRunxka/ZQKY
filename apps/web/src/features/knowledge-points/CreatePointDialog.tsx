'use client';

/**
 * 新建知识点（人工建立）。
 *
 * - 学科来自 `GET /api/v1/textbook-taxonomy` 的 `subjects[]`（不存在 /subjects 接口）；
 * - `code` 是学科内身份键：同 `(subjectId, code)` 冲突由服务端返回 409
 *   `KNOWLEDGE_CODE_CONFLICT`，这里原样显示并保留输入；
 * - 父级用 `parentCode`（可在后续详情页改挂/清空）。
 */

import { useState } from 'react';
import { Plus } from 'lucide-react';
import type { ErrorIssue } from '@/contracts/api';
import type { KnowledgePointView } from '@/contracts/knowledge';
import { Modal } from '@/components/ui/Modal';
import { createKnowledgePoint } from '@/services/knowledge-points-api';
import { asApiError } from './hooks';
import { planPointCreate, type PointCreateValues } from './point-form';

const EMPTY: PointCreateValues = {
  subjectId: '',
  code: '',
  name: '',
  description: '',
  parentCode: '',
  sortOrder: '',
  aliasesText: '',
};

export function CreatePointDialog({
  subjects,
  taxonomyReady,
  defaultSubjectId,
  onClose,
  onCreated,
}: {
  subjects: { id: string; label: string }[];
  taxonomyReady: boolean;
  defaultSubjectId: string;
  onClose: () => void;
  onCreated: (point: KnowledgePointView) => void;
}) {
  const [values, setValues] = useState<PointCreateValues>({
    ...EMPTY,
    subjectId: defaultSubjectId,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issues, setIssues] = useState<ErrorIssue[]>([]);

  const plan = planPointCreate(values);

  async function submit() {
    if (!plan.request) {
      setError('请先修正表单问题再建立。');
      return;
    }
    setBusy(true);
    setError(null);
    setIssues([]);
    try {
      const created = await createKnowledgePoint(plan.request);
      onCreated(created);
    } catch (cause) {
      const apiError = asApiError(cause);
      if (apiError.status === 409) {
        setError(
          `建立失败（${apiError.code}）：${apiError.message} 该学科内编码已存在，请改用「更新」既有知识点或换一个编码。`,
        );
      } else if (apiError.status === 422) {
        setIssues(apiError.details?.issues ?? []);
        setError(`建立失败（${apiError.code}）：${apiError.message}`);
      } else {
        setError(`建立失败（${apiError.code}）：${apiError.message} 已填内容保留，可直接重试。`);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="新建知识点" onClose={onClose}>
      <div className="kp-form">
        <label className="kp-field">
          <span className="kp-field-label">学科（必填）</span>
          {taxonomyReady ? (
            <select
              className="space-select"
              value={values.subjectId}
              aria-label="学科"
              disabled={busy}
              onChange={(event) => setValues({ ...values, subjectId: event.target.value })}
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
              value={values.subjectId}
              aria-label="学科"
              placeholder="学科 id（如 math）"
              disabled={busy}
              onChange={(event) => setValues({ ...values, subjectId: event.target.value })}
            />
          )}
        </label>
        <label className="kp-field">
          <span className="kp-field-label">编码（学科内唯一）</span>
          <input
            value={values.code}
            aria-label="编码"
            disabled={busy}
            onChange={(event) => setValues({ ...values, code: event.target.value })}
          />
        </label>
        <label className="kp-field">
          <span className="kp-field-label">名称</span>
          <input
            value={values.name}
            aria-label="名称"
            disabled={busy}
            onChange={(event) => setValues({ ...values, name: event.target.value })}
          />
        </label>
        <label className="kp-field">
          <span className="kp-field-label">说明（可选）</span>
          <textarea
            value={values.description}
            aria-label="说明"
            rows={3}
            disabled={busy}
            onChange={(event) => setValues({ ...values, description: event.target.value })}
          />
        </label>
        <div className="kp-form-row">
          <label className="kp-field">
            <span className="kp-field-label">父级编码（可选）</span>
            <input
              value={values.parentCode}
              aria-label="父级编码"
              disabled={busy}
              onChange={(event) => setValues({ ...values, parentCode: event.target.value })}
            />
          </label>
          <label className="kp-field kp-field-narrow">
            <span className="kp-field-label">排序（可选）</span>
            <input
              type="number"
              min={0}
              value={values.sortOrder}
              aria-label="排序"
              disabled={busy}
              onChange={(event) => setValues({ ...values, sortOrder: event.target.value })}
            />
          </label>
        </div>
        <label className="kp-field">
          <span className="kp-field-label">别名（可选，用「、」「,」「;」或换行分隔）</span>
          <textarea
            value={values.aliasesText}
            aria-label="别名"
            rows={2}
            disabled={busy}
            onChange={(event) => setValues({ ...values, aliasesText: event.target.value })}
          />
        </label>

        {plan.errors.length > 0 && (
          <ul className="kp-issue-list" aria-label="表单问题">
            {plan.errors.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        {error && (
          <p className="space-banner error" role="alert">
            {error}
          </p>
        )}
        {issues.length > 0 && (
          <ul className="kp-issue-list">
            {issues.map((issue, index) => (
              <li key={`${issue.code}-${index}`}>
                {issue.field ? `字段 ${issue.field}：` : ''}
                {issue.code}：{issue.message}
              </li>
            ))}
          </ul>
        )}

        <div className="kp-actions">
          <button
            className="space-button primary"
            disabled={busy || plan.request === null}
            onClick={() => void submit()}
          >
            <Plus size={14} aria-hidden />
            {busy ? '建立中…' : '建立知识点'}
          </button>
          <button className="space-button" disabled={busy} onClick={onClose}>
            取消
          </button>
        </div>
      </div>
    </Modal>
  );
}
