'use client';
import { useMemo, useState } from 'react';
import { BookMarked } from 'lucide-react';
import type { ChatArtifact } from '@/contracts/chat';
import { saveNotebookEntry } from '@/services/space-store';
import type { ReportArtifactData } from '../model/capability-demo';
import { AnswerMarkdown } from '../AnswerMarkdown';

/**
 * S4 研究报告产物视图：报告正文（markdown）+ 引用定位列表
 * （CIT-x-x 对照参考 citation 格式；引用为本地演示资料，如实标识）。
 * "保存到笔记"写入 space-store，与业务页（S5 /notebooks）同一仓储，同 id 幂等。
 */
export function ReportArtifactView({
  artifact,
  messageId,
}: {
  artifact: ChatArtifact;
  messageId: string;
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
  const [saved, setSaved] = useState<'idle' | 'added' | 'exists'>('idle');

  const save = () => {
    const result = saveNotebookEntry({
      id: `${messageId}:${artifact.id}`,
      messageId,
      artifactId: artifact.id,
      title: artifact.title,
      kind: 'research_report',
      content: artifact.content,
    });
    setSaved(result);
  };

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
      <div className="chat-report-actions">
        <button type="button" className="chat-report-save" onClick={save}>
          <BookMarked size={13} />
          {saved === 'added'
            ? '已保存到笔记'
            : saved === 'exists'
              ? '笔记中已存在（同源不重复）'
              : '保存到笔记（本地仓储）'}
        </button>
      </div>
    </div>
  );
}
