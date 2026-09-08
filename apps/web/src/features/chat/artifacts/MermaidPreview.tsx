'use client';
import { useEffect, useRef, useState } from 'react';
import type { ChatArtifact } from '@/contracts/chat';

/**
 * Mermaid 预览：本地 mermaid@11 渲染（对照参考 web/components/visualization 中的
 * Mermaid 组件）。渲染失败时回退展示源码原文，不吞错误。SVG 输出经 mermaid
 * 自身安全处理（securityLevel: 'strict'），不执行图内脚本。
 */
export function MermaidPreview({ artifact }: { artifact: ChatArtifact }) {
  const source =
    (artifact.data && typeof artifact.data === 'object' && 'source' in artifact.data
      ? String((artifact.data as { source?: unknown }).source ?? '')
      : '') || artifact.content;
  const holder = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });
        const { svg } = await mermaid.render(`mermaid-${artifact.id}`, source);
        if (!cancelled && holder.current) {
          holder.current.innerHTML = svg;
          setFailed(false);
        }
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [artifact.id, source]);

  return (
    <div className="chat-mermaid-preview">
      <div ref={holder} className="chat-mermaid-holder" />
      {failed && (
        <div className="chat-mermaid-fallback">
          <p>Mermaid 渲染失败，以下为源码原文：</p>
          <pre>{source}</pre>
        </div>
      )}
    </div>
  );
}
