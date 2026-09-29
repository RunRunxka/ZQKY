'use client';
import { memo, useRef, useState, type ReactNode } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import 'katex/dist/katex.min.css';
import { normalizeMathDelimiters } from './model/markdown-math';

function CodeBlock({ children }: { children?: ReactNode }) {
  const ref = useRef<HTMLPreElement>(null),
    [status, setStatus] = useState('复制代码');
  return (
    <div className="answer-code">
      <button
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(ref.current?.textContent ?? '');
            setStatus('已复制');
          } catch {
            setStatus('复制失败');
          }
        }}
      >
        {status}
      </button>
      <pre ref={ref}>{children}</pre>
    </div>
  );
}

/**
 * 正文 Markdown 渲染。
 *
 * - `omitImages`（RAG 专用「省略图片」策略，PLAN §4.2）：`img` 不渲染、**不发起任何图片请求**；
 *   普通聊天保持默认 `false`，仍显示既有的文字占位（行为不变）；
 * - `inline`：知识点标题/说明内的公式同行渲染，不产生块级段落（`[n]` 引用编号可紧跟其后）。
 */
const MarkdownBody = memo(function MarkdownBody({
  text,
  omitImages = false,
  inline = false,
}: {
  text: string;
  omitImages?: boolean;
  inline?: boolean;
}) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[
        [rehypeKatex, { trust: false, strict: 'ignore', throwOnError: false, maxExpand: 1000 }],
        rehypeHighlight,
      ]}
      skipHtml
      components={{
        pre: CodeBlock,
        a: ({ children, href }) => (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ),
        img: ({ alt }) =>
          omitImages ? null : <span className="chat-status-text">[图片：{alt || '图片内容未加载'}]</span>,
        table: ({ children }) => (
          <div className="answer-table" tabIndex={0}>
            <table>{children}</table>
          </div>
        ),
        ...(inline
          ? { p: ({ children }: { children?: ReactNode }) => <span className="chat-answer-line">{children}</span> }
          : {}),
      }}
    >
      {normalizeMathDelimiters(text)}
    </Markdown>
  );
});

export const AnswerMarkdown = memo(function AnswerMarkdown({
  text,
  omitImages = false,
  inline = false,
}: {
  text: string;
  omitImages?: boolean;
  inline?: boolean;
}) {
  if (inline)
    return (
      <span className="answer-markdown answer-markdown-inline">
        <MarkdownBody text={text} omitImages={omitImages} inline />
      </span>
    );
  return (
    <div className="answer-markdown">
      <MarkdownBody text={text} omitImages={omitImages} />
    </div>
  );
});
