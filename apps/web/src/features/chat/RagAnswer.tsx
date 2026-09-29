'use client';
import { AnswerMarkdown } from './AnswerMarkdown';
import { RAG_RESULT_STATUS_LABEL } from './model/rag-v2';
import { splitCitationMarkers, type CompactPoint, type RagMessageView } from './model/message-projection';

/**
 * 紧凑首答（RAG-QUALITY v1.1 · PLAN §2.1 / §4.1）。
 *
 * - 只渲染**知识点**（编号 + 标题 + 说明 + `[n]`）；教材原文一律在「教材依据」面板按需展开
 *   —— 同一条消息里知识点只出现一次，原文正文默认不出现在消息流里；
 * - `[n]` 编号 = 证据在 `result.evidence` 中的序号；点击只展开来源并定位，**不请求模型**；
 * - 公式走现有 KaTeX；RAG 文本使用「省略图片」策略（不渲染、不请求任何图片）；
 * - `partial` / `uncertain` / `no_evidence` 如实显示状态与原因，不把部分结果说成成功；
 *   旧版首答里装不下预算的知识点放在「展开旧答」中，**不伪造新摘要**。
 */
export function RagAnswer({
  view,
  scopeLabel,
  onCitation,
}: {
  view: RagMessageView;
  scopeLabel?: string | null;
  onCitation: (evidenceId: string) => void;
}) {
  const evidenceIdFor = (index: number) => view.sources.find((item) => item.index === index)?.evidenceId;
  const allowed = new Set(view.sources.map((item) => item.index));
  const renderCitation = (point: CompactPoint) =>
    point.citations.map((index) => {
      const evidenceId = evidenceIdFor(index);
      if (!evidenceId)
        return (
          <span key={`unknown-${index}`} className="chat-rag-cite-plain">
            [{index}]
          </span>
        );
      return (
        <button
          key={index}
          type="button"
          className="chat-rag-cite-chip"
          title={`查看教材依据 [${index}]`}
          aria-label={`查看教材依据 ${index}`}
          onClick={() => onCitation(evidenceId)}
        >
          [{index}]
        </button>
      );
    });
  return (
    <section className="chat-rag-answer" aria-label="教材知识点">
      <header className="chat-rag-answer-head">
        <strong>教材知识点</strong>
        <span className={`chat-rag-status ${view.status}`}>{RAG_RESULT_STATUS_LABEL[view.status]}</span>
        {scopeLabel && <span className="chat-rag-scope">本轮范围：{scopeLabel}</span>}
      </header>
      {view.userNotice && (
        <p className={`chat-rag-hint ${view.status}`} role="status">
          {view.userNotice}
        </p>
      )}
      {view.officialReason && view.officialReason !== view.userNotice && (
        <p className="chat-rag-reason">{view.officialReason}</p>
      )}
      {view.points.length > 0 && (
        <ol className="chat-rag-answer-points">
          {view.points.map((point) => (
            <li key={point.pointId}>
              <span className="chat-rag-point-title">
                <AnswerMarkdown text={point.title} inline omitImages />
              </span>
              {point.summary && (
                <span className="chat-rag-point-summary">
                  {splitCitationMarkers(point.summary, allowed).map((part, position) =>
                    part.kind === 'text' ? (
                      <AnswerMarkdown key={position} text={part.text} inline omitImages />
                    ) : (
                      <span key={position}>{renderCitation({ ...point, citations: [part.index!] })}</span>
                    ),
                  )}
                </span>
              )}
              {!point.summary && point.overflowSummary && (
                <details className="chat-rag-legacy-answer">
                  <summary>展开旧答</summary>
                  <AnswerMarkdown text={point.overflowSummary} omitImages />
                  {point.citations.length > 0 && (
                    <p className="chat-rag-legacy-refs">{renderCitation(point)}</p>
                  )}
                </details>
              )}
            </li>
          ))}
        </ol>
      )}
      {view.points.some((point) => point.overflowSummary) && (
        <p className="chat-rag-answer-foot">
          旧版首答：未装入预算的知识点保留在「展开旧答」中（不截断、不改写）。
        </p>
      )}
    </section>
  );
}
