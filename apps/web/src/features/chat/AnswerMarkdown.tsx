'use client';
import { memo, useRef, useState, type ReactNode } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import 'katex/dist/katex.min.css';

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
export const AnswerMarkdown = memo(function AnswerMarkdown({ text }: { text: string }) {
  return (
    <div className="answer-markdown">
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
          img: ({ alt }) => (
            <span className="chat-status-text">[图片：{alt || '图片内容未加载'}]</span>
          ),
          table: ({ children }) => (
            <div className="answer-table" tabIndex={0}>
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {text}
      </Markdown>
    </div>
  );
});
