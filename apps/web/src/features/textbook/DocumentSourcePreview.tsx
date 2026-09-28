'use client';

/**
 * 来源预览：调用 `GET /textbook-revisions/{revisionId}/source` 读取不可变修订的规范化文本与定位。
 * 读取失败如实报错（含 code 与重试），不显示占位原文、不缓存伪结果。
 */

import { useState } from 'react';
import type { LocatorView, SourceSpanView } from '@/contracts/textbook';
import { getDocumentSource } from '@/services/textbook-api';
import { errorText } from './hooks';

function locatorText(locator: LocatorView): string {
  const parts: string[] = [`类型 ${locator.kind}`];
  if (locator.lineStart !== null) {
    parts.push(`行 ${locator.lineStart}${locator.lineEnd !== null ? `–${locator.lineEnd}` : ''}`);
  }
  if (locator.pageStart !== null) {
    parts.push(`页 ${locator.pageStart}${locator.pageEnd !== null ? `–${locator.pageEnd}` : ''}`);
  }
  if (locator.blockStart !== null) {
    parts.push(
      `段 ${locator.blockStart}${locator.blockEnd !== null ? `–${locator.blockEnd}` : ''}`,
    );
  }
  return parts.join(' · ');
}

export function DocumentSourcePreview({
  revisionId,
  charCount,
}: {
  revisionId: string;
  charCount: number;
}) {
  const [charStart, setCharStart] = useState(0);
  const [charEnd, setCharEnd] = useState(Math.min(1200, Math.max(1, charCount)));
  const [span, setSpan] = useState<SourceSpanView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const next = await getDocumentSource(revisionId, charStart, charEnd);
      setSpan(next);
    } catch (cause) {
      setSpan(null);
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="textbook-source">
      <div className="space-meta-row">
        <span className="space-chip">修订 {revisionId}</span>
        <span className="space-chip">总字符 {charCount}</span>
      </div>
      <div className="textbook-source-controls">
        <label className="textbook-field" htmlFor={`source-start-${revisionId}`}>
          <span>起始字符</span>
          <input
            id={`source-start-${revisionId}`}
            type="number"
            min={0}
            max={charCount}
            value={charStart}
            onChange={(event) => setCharStart(Number(event.target.value))}
          />
        </label>
        <label className="textbook-field" htmlFor={`source-end-${revisionId}`}>
          <span>结束字符</span>
          <input
            id={`source-end-${revisionId}`}
            type="number"
            min={1}
            max={charCount}
            value={charEnd}
            onChange={(event) => setCharEnd(Number(event.target.value))}
          />
        </label>
        <button className="space-button" onClick={() => void load()} disabled={busy}>
          {busy ? '读取中…' : '读取原文'}
        </button>
      </div>

      {error && (
        <div className="space-banner error" role="alert">
          原文读取失败：{error}
          <div className="textbook-panel-actions">
            <button className="space-button" onClick={() => void load()}>
              重试
            </button>
          </div>
        </div>
      )}

      {span && (
        <>
          <div className="space-meta-row">
            <span className="space-chip">{locatorText(span.locator)}</span>
            <span className="space-chip">
              字符 {span.charStart}–{span.charEnd}
            </span>
            <span className="space-chip">文本指纹 {span.normalizedTextSha256.slice(0, 12)}…</span>
          </div>
          {span.text ? (
            <pre className="textbook-source-text">{span.text}</pre>
          ) : (
            <p className="textbook-hint" role="status">
              区间内没有文本（服务端返回空片段）。
            </p>
          )}
        </>
      )}
    </div>
  );
}
