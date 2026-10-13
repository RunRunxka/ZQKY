'use client';

/**
 * 选择入库面板（2026-10-13「多选即确认」）：教师勾选要入库的草稿，不再要求逐题校对。
 *
 * - 勾选驱动：`selection` 由父级持有，默认全选（教师可取消勾选或再次全选）；
 * - 知识点**只读**展示：每题列出 AI 绑定的知识点名称（不可在此修改，编辑器也不提供编辑）；
 * - 缺答案照常可入库：以 `answerState=not_provided` 落库，这里明确标注而不是阻断；
 * - 已排除的草稿不参与入库（拆分/合并/并入已有题的结果），单独列出并说明；
 * - 服务端语义：HTTP 200 + `failures` 非空 = 整体不确认、逐条给原因（未登记提交，可重试）。
 */

import type { ConfirmResult, DraftView, DuplicateResolution } from '@/contracts/question-bank';
import { ApiError } from '@/services/api-client';
import { answerHasContent, confirmBlockers } from './draft-form';
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
  selection,
  onToggle,
  onSelectAll,
  onClearSelection,
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
  /** 勾选的草稿 id（顺序无关；提交时按批次内顺序生成 items）。 */
  selection: readonly string[];
  onToggle: (draftId: string) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  submissionId: string | null;
  state: ConfirmState;
  busy: boolean;
  resolutions: Record<string, DuplicateResolution>;
  onResolutionChange: (draftId: string, action: DuplicateResolution['action']) => void;
  onConfirm: () => void;
  onOpenLibrary: () => void;
  onReload: () => void;
}) {
  const selectable = drafts.filter((draft) => draft.reviewState !== 'excluded');
  const excluded = drafts.filter((draft) => draft.reviewState === 'excluded');
  const selected = selectable.filter((draft) => selection.includes(draft.draftId));
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
    <section className="qb-confirm" aria-label="选择入库">
      <header className="qb-source-head">
        <h2>选择入库</h2>
        <span className="space-chip blue" data-testid="qb-confirm-selected-count">
          已选 {selected.length} 道
        </span>
        {selected.some((draft) => draft.extractionMethod === 'ai') && (
          <span className="space-chip amber" data-testid="qb-confirm-ai-count">
            含 AI 候选 {selected.filter((draft) => draft.extractionMethod === 'ai').length} 道
          </span>
        )}
      </header>

      {selectable.length === 0 ? (
        <p className="qb-hint" role="status">
          该批次没有可入库的草稿（全部已排除）；请返回题库列表重新导入或换一批解析结果。
        </p>
      ) : (
        <>
          <div className="qb-actions">
            <button
              className="space-button"
              type="button"
              onClick={onSelectAll}
              disabled={busy || completed || selected.length === selectable.length}
              data-testid="qb-confirm-select-all"
            >
              全选（{selectable.length} 道）
            </button>
            <button
              className="space-button"
              type="button"
              onClick={onClearSelection}
              disabled={busy || selected.length === 0}
              data-testid="qb-confirm-clear-selection"
            >
              清空选择
            </button>
          </div>

          <ul className="qb-confirm-list">
            {selectable.map((draft) => {
              const blockers = confirmBlockers(draft.content, draft.reviewState);
              const links = draft.knowledgeLinks ?? [];
              const missingAnswer = !answerHasContent(draft.content.answer);
              return (
                <li key={draft.draftId} className="qb-confirm-item">
                  <label className="qb-check" htmlFor={`qb-confirm-pick-${draft.draftId}`}>
                    <input
                      id={`qb-confirm-pick-${draft.draftId}`}
                      type="checkbox"
                      checked={selection.includes(draft.draftId)}
                      disabled={busy || completed}
                      onChange={() => onToggle(draft.draftId)}
                      data-testid={`qb-confirm-pick-${draft.draftId}`}
                    />
                    <span className="space-chip" title={draft.draftId}>
                      {labelOf(draft)}
                    </span>
                  </label>
                  <div className="space-meta-row">
                    <span className="space-chip">修订 r{draft.revision}</span>
                    <span className="space-chip">{reviewStateLabel(draft.reviewState)}</span>
                    <span className="space-chip">
                      {EXTRACTION_METHOD_LABEL[draft.extractionMethod]}
                    </span>
                    {draft.extractionMethod === 'ai' && (
                      <span
                        className="space-chip amber"
                        data-testid={`qb-confirm-ai-source-${draft.draftId}`}
                      >
                        {AI_CANDIDATE_CHIP}
                      </span>
                    )}
                    {missingAnswer && (
                      <span
                        className="space-chip amber"
                        data-testid={`qb-confirm-missing-answer-${draft.draftId}`}
                      >
                        原文未提供答案（按缺答案入库）
                      </span>
                    )}
                  </div>
                  <p className="qb-block-text">{draft.content.stemMarkdown.slice(0, 80)}</p>
                  <p className="qb-hint" data-testid={`qb-confirm-links-${draft.draftId}`}>
                    知识点（AI 绑定，只读）：
                    {links.length > 0
                      ? links.map((link) => link.knowledgeNameSnapshot || '（名称未提供）').join('、')
                      : '无绑定'}
                  </p>
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
        </>
      )}

      {excluded.length > 0 && (
        <p className="qb-hint" role="status" data-testid="qb-confirm-excluded">
          已排除 {excluded.length} 道（拆分/合并或并入已有题的结果），不参与本次入库。
        </p>
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
              {busy ? '提交中…' : `修正后重新提交（${selected.length} 道）`}
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
          disabled={busy || completed || (!unknown && selected.length === 0)}
          onClick={onConfirm}
          data-testid="qb-confirm-submit"
        >
          {busy ? '提交中…' : unknown ? '重试原确认（结果未知）' : `入库（${selected.length} 道）`}
        </button>
        <span className="qb-hint">
          入库使用乐观锁与幂等提交：任一条校验失败则整体不确认，失败原因逐条列出。
        </span>
      </div>
    </section>
  );
}
