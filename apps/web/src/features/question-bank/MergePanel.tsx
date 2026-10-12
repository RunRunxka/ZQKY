'use client';

/** 合并草稿：多选（≥2）后按各自的期望修订提交 `POST /question-imports/{id}/merge`。 */

import type { DraftView } from '@/contracts/question-bank';
import { reviewStateLabel } from './labels';

export function MergePanel({
  drafts,
  selected,
  busy,
  error,
  notice,
  onToggle,
  onMerge,
}: {
  drafts: DraftView[];
  selected: string[];
  busy: boolean;
  error: string | null;
  notice: string | null;
  onToggle: (draftId: string) => void;
  onMerge: () => void;
}) {
  return (
    <section className="qb-subpanel" aria-label="合并草稿">
      <h2>合并草稿</h2>
      <p className="qb-hint">
        勾选至少两道草稿后台并：内容按原文顺序拼接，选中的旧草稿会被排除，合并结果需要重新校对。
      </p>
      <ul className="qb-merge-list">
        {drafts.map((draft) => (
          <li key={draft.draftId}>
            <label className="qb-check">
              <input
                type="checkbox"
                checked={selected.includes(draft.draftId)}
                disabled={busy || draft.reviewState === 'excluded'}
                onChange={() => onToggle(draft.draftId)}
              />
              <span className="qb-merge-label">
                <span className="space-chip">{reviewStateLabel(draft.reviewState)}</span>
                <span>修订 r{draft.revision}</span>
                <span className="qb-merge-stem">
                  {draft.content.stemMarkdown.slice(0, 48)}
                  {draft.content.stemMarkdown.length > 48 ? '…' : ''}
                </span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      {error && (
        <p className="space-banner error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="space-banner info" role="status">
          {notice}
        </p>
      )}
      <div className="qb-actions">
        <button className="space-button" disabled={busy || selected.length < 2} onClick={onMerge}>
          {busy ? '合并中…' : `合并所选草稿（${selected.length}）`}
        </button>
      </div>
    </section>
  );
}
