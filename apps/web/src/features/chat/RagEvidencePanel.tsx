'use client';
import { useEffect, useId, useRef, useState } from 'react';
import { BookMarked, ChevronRight, Copy, FileText, History } from 'lucide-react';
import type { ChatMessage } from '@/contracts/chat';
import { AnswerMarkdown } from './AnswerMarkdown';
import { buildCompactSources, type CompactSource, type RagMessageView } from './model/message-projection';

/**
 * 教材依据（来源）面板（RAG-QUALITY v1.1 · PLAN §4.1 / §4.2）。
 *
 * 边界（本卡 Q1 的核心修复）：
 * - **只负责来源**，不再渲染知识点（知识点由 `RagAnswer` 渲染一次）；
 * - 两级展开：面板默认折叠 → 「查看教材依据（N 条）」展开来源列表 → 单条「展开摘录」
 *   才显示清洗后的完整摘录；预览最多 160 字，在完整句或结构边界结束，不截半个公式；
 * - 展示/预览/复制摘录一律用 **清洗文本**（新结果 = `readable.text`；旧消息缺 `readable`
 *   时降级为 `text` 并**明确标注未清洗历史原文**，本地隐藏图片语法只影响展示、不改库）；
 * - 回传引用与校验只用 `evidenceId` + 坐标字段（不在本组件里做任何回传）；
 * - `isSuperseded` 的历史修订提示保留在对应来源上；图片清洗造成信息缺失时在展开区提示**一次**；
 * - **不发起任何图片网络请求**（摘录/预览用「省略图片」策略渲染）；
 * - 后端没给证据就不渲染来源条目（不猜造引用）；旧 v1 形状原样只读。
 */
export function RagEvidencePanel({
  message,
  view = null,
  scopeLabel = null,
  focusRequest = null,
}: {
  message: ChatMessage;
  /** 结构化紧凑视图（有 `ragResult` 时由 Message 传入；null = 旧 v1 或只有孤立证据） */
  view?: RagMessageView | null;
  /** 本轮范围文案（回答头已有范围时不再重复） */
  scopeLabel?: string | null;
  /** 点击正文 `[n]` 的定位请求：展开面板并把焦点移到对应条目 */
  focusRequest?: { evidenceId: string; token: number } | null;
}) {
  const result = message.ragResult;
  const sources: CompactSource[] = view?.sources ?? buildCompactSources(message.ragEvidence ?? []);
  const selection = result?.scopeSnapshot?.selection ?? message.ragScope?.selection ?? null;
  const [expanded, setExpanded] = useState(false);
  const [excerptFor, setExcerptFor] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copyFailedId, setCopyFailedId] = useState<string | null>(null);
  const entryRefs = useRef(new Map<string, HTMLButtonElement>());
  const listId = useId();

  // 点击消息里的 [n]：展开面板并移动焦点到对应条目（不请求模型、不改动数据）
  useEffect(() => {
    if (!focusRequest) return;
    setExpanded(true);
  }, [focusRequest]);
  useEffect(() => {
    if (!focusRequest || !expanded) return;
    const entry = entryRefs.current.get(focusRequest.evidenceId);
    entry?.focus();
    entry?.scrollIntoView?.({ block: 'nearest' });
  }, [focusRequest, expanded]);

  const hasEvidence = sources.length > 0;
  // 回答头（RagAnswer）已显示本轮范围时不重复；旧 v1 / 孤立证据才由面板承担
  const showScope = !view && !!scopeLabel && !!selection;
  // 结果、证据、范围三者都没有时整块不渲染（旧数据不猜造引用）
  if (!result && !hasEvidence && !showScope) return null;
  const imagesRemoved = sources.some((item) => item.removedImageCount > 0);

  async function copyExcerpt(source: CompactSource) {
    try {
      await navigator.clipboard.writeText(source.readableText);
      setCopiedId(source.evidenceId);
      setCopyFailedId(null);
    } catch {
      setCopyFailedId(source.evidenceId);
      setCopiedId(null);
    }
  }

  return (
    <section className="chat-rag-evidence" aria-label="教材依据">
      <button
        type="button"
        className="chat-rag-toggle"
        aria-expanded={expanded}
        aria-controls={listId}
        onClick={() => setExpanded((open) => !open)}
      >
        <BookMarked size={13} aria-hidden="true" />
        <span>{hasEvidence ? `查看教材依据（${sources.length} 条）` : '查看教材依据'}</span>
        <ChevronRight size={13} className={expanded ? 'open' : undefined} aria-hidden="true" />
      </button>
      {showScope && <span className="chat-rag-scope">本轮范围：{scopeLabel}</span>}
      {/* 结果原因由 RagAnswer 统一展示一次；面板只负责来源，不再重复状态与说明 */}
      {!view && result?.status === 'no_evidence' && (
        <p className="chat-rag-hint" role="status">
          当前范围内没有找到足够依据，回答未包含教材外推内容。可补充题干条件、教材章节或具体步骤后重新定位。
        </p>
      )}
      {expanded && (
        <div className="chat-rag-body" id={listId}>
          {imagesRemoved && (
            <p className="chat-rag-image-note" role="status">
              已省略图片，未识别图中内容。
            </p>
          )}
          {hasEvidence && (
            <ol className="chat-rag-list">
              {sources.map((source) => {
                const location = [
                  source.editionLabel,
                  source.subjectLabel,
                  source.chapterPath.join(' → '),
                  source.locator,
                ]
                  .filter(Boolean)
                  .join(' · ');
                const open = excerptFor === source.evidenceId;
                return (
                  <li
                    key={source.evidenceId}
                    className={source.isSuperseded ? 'superseded' : undefined}
                    data-evidence-id={source.evidenceId}
                  >
                    <p className="chat-rag-cite">
                      <FileText size={12} aria-hidden="true" />
                      <span className="chat-rag-index">[{source.index}]</span>
                      <strong>{source.title}</strong>
                      {location && <small>{location}</small>}
                    </p>
                    {source.isSuperseded && (
                      <p className="chat-rag-superseded" role="status">
                        <History size={12} aria-hidden="true" />
                        教材已更新，此引用为历史修订（不再代表当前有效教材内容）。
                      </p>
                    )}
                    {source.preview && (
                      <span className="chat-rag-preview">
                        <AnswerMarkdown text={source.preview} inline omitImages />
                      </span>
                    )}
                    <div className="chat-rag-source-actions">
                      <button
                        type="button"
                        data-evidence-entry
                        ref={(node) => {
                          if (node) entryRefs.current.set(source.evidenceId, node);
                          else entryRefs.current.delete(source.evidenceId);
                        }}
                        aria-expanded={open}
                        onClick={() => setExcerptFor(open ? null : source.evidenceId)}
                      >
                        {open ? '收起摘录' : '展开摘录'}
                      </button>
                      <button
                        type="button"
                        aria-label={`复制摘录 [${source.index}]`}
                        onClick={() => void copyExcerpt(source)}
                      >
                        <Copy size={12} aria-hidden="true" />
                        {copiedId === source.evidenceId ? '已复制摘录' : copyFailedId === source.evidenceId ? '复制失败' : '复制摘录'}
                      </button>
                    </div>
                    {open && (
                      <div className="chat-rag-excerpt">
                        {source.legacyRaw && (
                          <p className="chat-rag-legacy-note" role="status">
                            未清洗历史原文（该条缺少服务端清洗版本）：已本地隐藏图片语法，未识别图中内容。
                          </p>
                        )}
                        {source.readableText.trim() ? (
                          <AnswerMarkdown text={source.readableText} omitImages />
                        ) : (
                          <p className="chat-rag-hint">该条清洗后没有可显示的正文（可能只有图片）。</p>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      )}
    </section>
  );
}
