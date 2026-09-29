'use client';

/**
 * AI 整理结果与建议列表。
 *
 * 语义边界（界面必须显式说明）：AI 结果只是**待校对的建议**，不会直接覆盖人工草稿；
 * 「应用」走 `POST /question-suggestions/{id}/apply`（带 `expectedDraftRevision`），
 * 「忽略」以 `accept:false` 复用同一通道；应用后草稿回到待校对。
 *
 * 错误说明只来自 `organizer-notice`（v1.1 唯一一份）：
 * 认证/限流/网络/配置失败指向**模型服务**，批级失败说明「该批未生成可应用建议，原文与草稿未被修改」；
 * 前端不自己编造错误码，也不把上游故障说成题目内容有问题。
 */

import type { DraftView, OrganizeJobView, SuggestionView } from '@/contracts/question-bank';
import {
  difficultyLabel,
  organizeStateLabel,
  questionTypeLabel,
  SUGGESTION_STATE_LABEL,
} from './labels';
import {
  ORGANIZER_CANCELLED_NOTICE,
  ORGANIZER_SUGGESTION_SEMANTICS,
  organizerFailureText,
  organizerStaleSuggestionText,
} from './organizer-notice';
import { QuestionPreview } from './QuestionPreview';

export function SuggestionPanel({
  job,
  suggestions,
  drafts,
  busySuggestionId,
  onApply,
  onIgnore,
}: {
  job: OrganizeJobView | null;
  suggestions: SuggestionView[];
  drafts: DraftView[];
  busySuggestionId: string | null;
  onApply: (suggestion: SuggestionView) => void;
  onIgnore: (suggestion: SuggestionView) => void;
}) {
  if (!job) return null;
  const draftById = new Map(drafts.map((draft) => [draft.draftId, draft]));

  return (
    <section className="qb-organize" aria-label="AI 整理建议">
      <header className="qb-source-head">
        <h2>AI 整理建议</h2>
        <span className="space-chip">{organizeStateLabel(job.state)}</span>
      </header>
      <p className="qb-hint">{ORGANIZER_SUGGESTION_SEMANTICS}</p>
      <div className="space-meta-row">
        <span className="space-chip">建议 {job.suggestionCount} 条</span>
        <span className="space-chip">失败批次 {job.failedBatches}</span>
        {job.errorCode && <span className="space-chip amber">错误码 {job.errorCode}</span>}
        {job.jobId && <span className="space-chip">任务 {job.jobId}</span>}
      </div>

      {job.state === 'failed' && (
        <p className="space-banner error" role="alert">
          本次 AI 整理失败{job.errorCode ? `（${job.errorCode}）` : ''}：
          {organizerFailureText(job.errorCode)}
          {job.failures.length > 0
            ? ' 失败批次的建议没有落库，原文与草稿未被修改；其余批次照常。'
            : ' 原文与草稿未被修改。'}
        </p>
      )}

      {job.state === 'cancelled' && (
        <p className="space-banner info" role="status">
          {ORGANIZER_CANCELLED_NOTICE}
        </p>
      )}

      {job.failures.length > 0 && (
        <ul className="qb-failure-list">
          {job.failures.map((failure) => (
            <li key={`${failure.batchIndex}-${failure.code}`}>
              批次 {failure.batchIndex + 1}（{failure.code}）：
              {failure.message.trim() || organizerFailureText(failure.code)}
            </li>
          ))}
        </ul>
      )}

      {job.suggestionCount > 0 && suggestions.length === 0 && (
        <p className="space-banner info" role="status">
          服务端报告生成 {job.suggestionCount}{' '}
          条建议，但本次响应没有返回可处理的建议明细（可能已被应用或忽略），
          因此无法逐条应用或忽略。草稿未被修改；请重新整理或刷新页面后再看。
        </p>
      )}

      {suggestions.length > 0 && (
        <ul className="qb-suggestion-list">
          {suggestions.map((suggestion) => {
            const target = draftById.get(suggestion.targetDraftId);
            const stale =
              suggestion.state === 'pending' &&
              (target ? target.revision !== suggestion.baseDraftRevision : true);
            const busy = busySuggestionId === suggestion.suggestionId;
            return (
              <li key={suggestion.suggestionId} className="qb-suggestion">
                <div className="space-meta-row">
                  <span className="space-chip blue">
                    {questionTypeLabel(suggestion.proposedContent.type)}
                  </span>
                  <span className="space-chip">{SUGGESTION_STATE_LABEL[suggestion.state]}</span>
                  <span className="space-chip">目标草稿 {suggestion.targetDraftId}</span>
                  <span className="space-chip">基准修订 r{suggestion.baseDraftRevision}</span>
                  {target && <span className="space-chip">当前修订 r{target.revision}</span>}
                  <span className="space-chip">
                    难度：{difficultyLabel(suggestion.proposedMetadata.difficulty)}
                  </span>
                </div>
                {stale && (
                  <p className="space-banner error" role="alert">
                    {organizerStaleSuggestionText(
                      suggestion.baseDraftRevision,
                      target ? target.revision : null,
                    )}
                  </p>
                )}
                {suggestion.note && <p className="qb-hint">{suggestion.note}</p>}
                <QuestionPreview content={suggestion.proposedContent} compact />
                <div className="qb-actions">
                  <button
                    className="space-button primary"
                    disabled={busy || suggestion.state !== 'pending'}
                    onClick={() => onApply(suggestion)}
                  >
                    应用建议
                  </button>
                  <button
                    className="space-button"
                    disabled={busy || suggestion.state !== 'pending'}
                    onClick={() => onIgnore(suggestion)}
                  >
                    忽略
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {job.suggestionCount === 0 && job.state === 'succeeded' && (
        <p className="qb-hint">本次整理没有产生建议：现有草稿结构与原文已经一致。</p>
      )}
    </section>
  );
}
