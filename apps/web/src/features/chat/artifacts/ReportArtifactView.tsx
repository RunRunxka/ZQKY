'use client';
import { useMemo } from 'react';
import type { ChatArtifact } from '@/contracts/chat';
import type { ReportArtifactData } from '../model/capability-demo';
import { AnswerMarkdown } from '../AnswerMarkdown';

/**
 * S4 研究报告产物视图：报告正文（markdown）+ 引用定位列表
 * （CIT-x-x 对照参考 citation 格式；引用为本地演示资料，如实标识）。
 * 「保存到笔记」能力已随学习空间一并移除，报告仅在当前消息内展示。
 */
export function ReportArtifactView({
  artifact,
}: {
  artifact: ChatArtifact;
  messageId?: string;
  /** 产物所属会话 id（R-10） */
  sessionId?: string | null;
}) {
  const data = useMemo<ReportArtifactData | null>(() => {
    if (!artifact.data || typeof artifact.data !== 'object') return null;
    const raw = artifact.data as Partial<ReportArtifactData>;
    return {
      mode: typeof raw.mode === 'string' ? raw.mode : '',
      depth: typeof raw.depth === 'string' ? raw.depth : '',
      subtopics: Array.isArray(raw.subtopics) ? raw.subtopics : [],
      citations: Array.isArray(raw.citations) ? raw.citations : [],
    };
  }, [artifact.data]);

  return (
    <div className="chat-report-view">
      <div className="chat-report-body">
        <AnswerMarkdown text={artifact.content} />
      </div>
      {data && data.citations.length > 0 && (
        <details className="chat-report-citations">
          <summary>引用与资料定位（{data.citations.length}）</summary>
          <ul>
            {data.citations.map((c) => (
              <li key={c.citation_id}>
                <strong>{c.citation_id}</strong> {c.title}
                <p>{c.snippet}</p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
