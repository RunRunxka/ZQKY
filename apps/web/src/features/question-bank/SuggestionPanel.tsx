'use client';

/**
 * AI 整理结果与建议列表。
 *
 * 语义边界（界面必须显式说明）：AI 结果只是**待校对的建议**，不会直接覆盖人工草稿；
 * 「应用」走 `POST /question-suggestions/{id}/apply`（带 `expectedDraftRevision`），
 * 「忽略」以 `accept:false` 复用同一通道；应用后草稿回到待校对。
 *
 * 后端当前只在任务视图里返回建议**计数**；响应若带 `suggestions` 明细则逐条展示，
 * 未带时如实说明缺少明细通道，不用假数据补齐。
 */

import type { DraftView, OrganizeJobView, SuggestionView } from '@/contracts/question-bank';
import {
  difficultyLabel,
  organizeStateLabel,
  questionTypeLabel,
  SUGGESTION_STATE_LABEL,
} from './labels';
import { QuestionPreview } from './QuestionPreview';

/** 整理失败错误码 → 用户可读原因（本机模型链路；未知码按「本机模型服务不可用」提示）。 */
export const ORGANIZER_ERROR_HINT: Record<string, string> = {
  ORGANIZER_MODEL_MISSING:
    '本机没有该整理模型：请在本机 Ollama 拉取并运行默认模型（如 qwen2.5:7b），或在本机模型状态里确认模型名。',
  ORGANIZER_UNAVAILABLE: '本机模型服务不可达：请确认本机 Ollama 正在运行。',
  ORGANIZER_TIMEOUT: '本机模型响应超时：可稍后重试，或换更小的本机模型。',
  ORGANIZE_TARGET_EMPTY: '没有可整理的草稿：请先选择或新增草稿。',
};

export function organizerFailureReason(code: string | null): string {
  if (!code) return '本机模型服务不可用或未返回原因。';
  return ORGANIZER_ERROR_HINT[code] ?? `本机模型整理失败（${code}）。`;
}

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
      <p className="qb-hint">
        AI 只给出待校对建议，永不直接覆盖人工草稿；应用建议同样不会自动入库，需要重新标记已校对。
      </p>
      <div className="space-meta-row">
        <span className="space-chip">建议 {job.suggestionCount} 条</span>
        <span className="space-chip">失败批次 {job.failedBatches}</span>
        {job.errorCode && <span className="space-chip amber">错误码 {job.errorCode}</span>}
        {job.jobId && <span className="space-chip">任务 {job.jobId}</span>}
      </div>

      {job.state === 'failed' && (
        <p className="space-banner error" role="alert">
          本次 AI 整理失败{job.errorCode ? `（${job.errorCode}）` : ''}：
          {organizerFailureReason(job.errorCode)} 草稿未被修改，可修正本机模型后重试。
        </p>
      )}

      {job.suggestionCount > 0 && suggestions.length === 0 && (
        <p className="space-banner info" role="status">
          服务端报告生成 {job.suggestionCount}{' '}
          条建议，但本次响应没有返回建议明细（当前后端未提供建议列表接口），
          因此无法逐条应用或忽略。草稿未被修改；请刷新页面或等待接口补齐后重新整理。
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
                    该建议基于的草稿修订已过期（草案 r{suggestion.baseDraftRevision}
                    {target ? ` → 当前 r${target.revision}` : ' → 草稿已不在批次中'}）。
                    应用会被服务端拒绝；请重新整理或先处理该草稿。
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

      {job.suggestionCount === 0 && job.state !== 'failed' && (
        <p className="qb-hint">本次整理没有产生建议：现有草稿结构与原文已经一致。</p>
      )}
    </section>
  );
}
