'use client';
import { BookMarked, FileText, History } from 'lucide-react';
import type { ChatMessage } from '@/contracts/chat';
import type { TextbookSelection } from '@/contracts/textbook';
import {
  RAG_RESULT_STATUS_LABEL,
  locatorLabel,
  type TextbookEvidence,
} from './model/rag-v2';

/**
 * 教材证据与范围展示（RAG-REBUILD v1.0 §6/§7）。
 *
 * 边界：
 * - 只渲染后端已给出的结构化证据（`rag.result` 落库的 `ragResult/ragEvidence`），
 *   不在前端伪造定位、章节或引用；**后端未给证据就不显示证据区**；
 * - `isSuperseded=true` 明确标注「教材已更新，此引用为历史修订」，不隐藏也不冒充有效；
 * - 旧消息缺这些字段时整块不渲染（不猜造引用）；旧 v1 `rag` 形状仍按原样只读展示。
 */
export function RagEvidencePanel({
  message,
  scopeLabelFor,
}: {
  message: ChatMessage;
  scopeLabelFor?: (selection: TextbookSelection) => string | null;
}) {
  const result = message.ragResult;
  const evidence: TextbookEvidence[] = message.ragEvidence ?? result?.evidence ?? [];
  const selection = result?.scopeSnapshot?.selection ?? message.ragScope?.selection ?? null;
  const scopeLabel = selection && scopeLabelFor ? scopeLabelFor(selection) : null;
  const status = result?.status;
  // 结果、证据、范围三者都没有时整块不渲染（旧数据不猜造引用）
  if (!result && !evidence.length && !scopeLabel) return null;
  return (
    <section className="chat-rag-evidence" aria-label="教材依据">
      <header className="chat-rag-head">
        <BookMarked size={13} aria-hidden="true" />
        <strong>教材依据</strong>
        {status && (
          <span className={`chat-rag-status ${status}`}>{RAG_RESULT_STATUS_LABEL[status]}</span>
        )}
        {scopeLabel && <span className="chat-rag-scope">本轮范围：{scopeLabel}</span>}
      </header>
      {result?.reason && <p className="chat-rag-reason">{result.reason}</p>}
      {status === 'no_evidence' && (
        <p className="chat-rag-hint" role="status">
          当前范围内没有找到足够依据，回答未包含教材外推内容。可补充题干条件、教材章节或具体步骤后重新定位。
        </p>
      )}
      {!!result?.points.length && (
        <ul className="chat-rag-points">
          {result.points.map((point) => (
            <li key={point.pointId}>
              <strong>{point.title}</strong>
              <p>{point.summary}</p>
              {!!point.evidenceIds.length && (
                <small>依据：{point.evidenceIds.join('、')}</small>
              )}
            </li>
          ))}
        </ul>
      )}
      {!!evidence.length && (
        <ol className="chat-rag-list">
          {evidence.map((item) => {
            const locator = locatorLabel(item.locator);
            return (
              <li key={item.evidenceId} className={item.isSuperseded ? 'superseded' : undefined}>
                <p className="chat-rag-cite">
                  <FileText size={12} aria-hidden="true" />
                  <strong>{item.title}</strong>
                  <small>
                    {[item.editionLabel, item.subjectLabel, item.chapterPath.join(' → '), locator]
                      .filter(Boolean)
                      .join(' · ')}
                  </small>
                  <span className="chat-rag-eid">[{item.evidenceId}]</span>
                </p>
                {item.isSuperseded && (
                  <p className="chat-rag-superseded" role="status">
                    <History size={12} aria-hidden="true" />
                    教材已更新，此引用为历史修订（不再代表当前有效教材内容）。
                  </p>
                )}
                <blockquote className="chat-rag-text">{item.text}</blockquote>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
