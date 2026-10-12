'use client';

/**
 * 确认入库面板：只收集 `reviewed` 草稿，`submissionId` 由父级生成并在失败重试时复用。
 * 服务端语义：HTTP 200 + `failures` 非空 = 整体不确认、逐条给原因（未登记提交，可重试）。
 *
 * 界面纪律（F10-QB）：
 * - `failures` 非空时只显示「**整批未确认**」与逐条清单，**不显示成功徽标**、不出现
 *   「已入库 N 道」；确认按钮保持可用（修正后复用同一提交标识重试）；
 * - AI 候选草稿（`extractionMethod=ai`）逐条显式标识来源，说明仍需人工确认后才入库；
 * - ID 降级：草稿标识用「#序号 题型」（完整 `draftId` 走 `title`），不把 uuid 当主标识。
 */

import type { ConfirmResult, DraftView, DuplicateResolution } from '@/contracts/question-bank';
import { ApiError } from '@/services/api-client';
import { confirmBlockers } from './draft-form';
import {
  AI_CANDIDATE_CHIP,
  CONFIRM_UNCONFIRMED_TITLE,
  EXTRACTION_METHOD_LABEL,
  draftLabel,
  reviewStateLabel,
} from './labels';

export type ConfirmState =
  | { phase: 'idle' }
  | { phase: 'failed'; error: ApiError }
  | { phase: 'done'; result: ConfirmResult };

export function ConfirmPanel({
  drafts,
  submissionId,
  state,
  busy,
  resolutions,
  onResolutionChange,
  onConfirm,
  onOpenLibrary,
  onReload,
}: {
  drafts: DraftView[];
  submissionId: string | null;
  state: ConfirmState;
  busy: boolean;
  resolutions: Record<string, DuplicateResolution>;
  onResolutionChange: (draftId: string, action: DuplicateResolution['action']) => void;
  onConfirm: () => void;
  onOpenLibrary: () => void;
  onReload: () => void;
}) {
  const reviewed = drafts.filter((draft) => draft.reviewState === 'reviewed');
  const completed = state.phase === 'done' && state.result.failures.length === 0;
  const unknown = state.phase === 'failed' && state.error.status === 0;
  /** 草稿在本批次里的序号 → 「#N 题型」；序号未知时退回题型（不显示 uuid 当主文案）。 */
  const positionOf = (draftId: string) => {
    const index = drafts.findIndex((draft) => draft.draftId === draftId);
    return index >= 0 ? index + 1 : null;
  };
  const labelOf = (draft: DraftView) =>
    draftLabel(positionOf(draft.draftId), draft.content.type);

  return (
    <section className="qb-confirm" aria-label="确认入库">
      <header className="qb-source-head">
        <h2>确认入库</h2>
        <span className="space-chip blue">已校对 {reviewed.length} 道</span>
        {reviewed.some((draft) => draft.extractionMethod === 'ai') && (
          <span className="space-chip amber" data-testid="qb-confirm-ai-count">
            含 AI 候选 {reviewed.filter((draft) => draft.extractionMethod === 'ai').length} 道（需人工确认）
          </span>
        )}
      </header>

      {reviewed.length === 0 ? (
        <p className="qb-hint" role="status">
          还没有已校对的草稿：在右侧编辑区点「标记已校对」后才会进入本次入库。
        </p>
      ) : (
        <ul className="qb-confirm-list">
          {reviewed.map((draft) => {
            const blockers = confirmBlockers(draft.content, draft.missingAnswerAcknowledged);
            return (
              <li key={draft.draftId} className="qb-confirm-item">
                <div className="space-meta-row">
                  <span className="space-chip" title={draft.draftId}>
                    {labelOf(draft)}
                  </span>
                  <span className="space-chip">修订 r{draft.revision}</span>
                  <span className="space-chip green">{reviewStateLabel(draft.reviewState)}</span>
                  <span className="space-chip">{EXTRACTION_METHOD_LABEL[draft.extractionMethod]}</span>
                  {draft.extractionMethod === 'ai' && (
                    <span
                      className="space-chip amber"
                      data-testid={`qb-confirm-ai-source-${draft.draftId}`}
                    >
                      {AI_CANDIDATE_CHIP}
                    </span>
                  )}
                </div>
                <p className="qb-block-text">{draft.content.stemMarkdown.slice(0, 80)}</p>
                {blockers.map((blocker) => (
                  <p key={blocker} className="qb-warn-text" role="alert">
                    {blocker}
                  </p>
                ))}
                {draft.duplicateOfQuestionId && (
                  <label className="qb-field" htmlFor={`qb-dup-${draft.draftId}`}>
                    与已有题目 {draft.duplicateOfQuestionId} 重复，本次处理方式
                    <select
                      id={`qb-dup-${draft.draftId}`}
                      className="space-select"
                      value={resolutions[draft.draftId]?.action ?? 'none'}
                      disabled={busy || completed || unknown}
                      onChange={(event) =>
                        onResolutionChange(
                          draft.draftId,
                          event.target.value as DuplicateResolution['action'],
                        )
                      }
                    >
                      <option value="none">默认（按服务端规则跳过重复）</option>
                      <option value="skip">跳过（不改动已有题目）</option>
                      <option value="link_existing">并入已有题目（新增来源记录）</option>
                      <option value="edit_as_new">作为新题入库（内容需确实不同）</option>
                    </select>
                  </label>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {submissionId && (
        <p className="qb-hint">
          提交标识 {submissionId}（失败重试复用同一标识，服务端据此保证幂等）。
        </p>
      )}

      {state.phase === 'failed' && (
        <p className="space-banner error" role="alert">
          {unknown ? '确认结果未知' : '确认请求失败'}（{state.error.code}）：{state.error.message}{' '}
          {unknown
            ? '未收到服务端回执，本次可能已经入库。原提交标识与完整载荷已冻结，请直接重试以读取原结果，或重新读取批次核对。'
            : '服务端明确拒绝本次确认；草稿与提交标识保留，修正后可直接重试。'}
        </p>
      )}
      {unknown && (
        <button className="space-button" onClick={onReload} disabled={busy}>
          重新读取批次（保留冻结确认）
        </button>
      )}

      {state.phase === 'done' && state.result.failures.length > 0 && (
        <div
          className="space-banner error"
          role="alert"
          data-testid="qb-confirm-unconfirmed"
        >
          <strong>{CONFIRM_UNCONFIRMED_TITLE}</strong>
          ：服务端逐条校验未通过（HTTP 200 + {state.result.failures.length} 条 failures），
          <strong>没有任何题目被入库</strong>
          ，也不会显示部分成功徽标；本次提交未登记，修正后可复用同一提交标识重试。
          <ul className="qb-failure-list">
            {state.result.failures.map((failure) => {
              const failed = drafts.find((draft) => draft.draftId === failure.draftId);
              return (
                <li key={`${failure.draftId}-${failure.code}`}>
                  <span title={failure.draftId}>
                    {failed ? labelOf(failed) : `草稿 ${failure.draftId}`}
                  </span>{' '}
                  · {failure.code}：{failure.message}
                </li>
              );
            })}
          </ul>
          <div className="qb-actions">
            <button className="space-button primary" onClick={onConfirm} disabled={busy}>
              {busy ? '提交中…' : `修正后重新提交（${reviewed.length} 道）`}
            </button>
            <button className="space-button" onClick={onReload} disabled={busy}>
              重新读取批次
            </button>
          </div>
        </div>
      )}

      {completed && (
        <div className="space-banner info" role="status">
          <strong>本次已入库 {state.result.confirmedQuestionIds.length} 道题</strong>
          {state.result.confirmedQuestionIds.length > 0 && (
            <span>：{state.result.confirmedQuestionIds.join('、')}</span>
          )}
          {state.result.linkedQuestionIds.length > 0 && (
            <span>；并入已有题目 {state.result.linkedQuestionIds.join('、')}</span>
          )}
          {state.result.skippedDraftIds.length > 0 && (
            <span>；跳过重复草稿 {state.result.skippedDraftIds.length} 道</span>
          )}
          <div className="qb-actions">
            <button className="space-button" onClick={onOpenLibrary}>
              查看已入库题目
            </button>
            <button className="space-button" onClick={onReload} disabled={busy}>
              刷新批次
            </button>
          </div>
        </div>
      )}

      <div className="qb-actions">
        <button
          className="space-button primary"
          disabled={busy || completed || (!unknown && reviewed.length === 0)}
          onClick={onConfirm}
        >
          {busy ? '提交中…' : unknown ? '重试原确认（结果未知）' : `确认入库（${reviewed.length} 道）`}
        </button>
        <span className="qb-hint">
          入库使用乐观锁与幂等提交：任一条校验失败则整体不确认，失败原因逐条列出。
        </span>
      </div>
    </section>
  );
}
