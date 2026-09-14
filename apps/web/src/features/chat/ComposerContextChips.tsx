'use client';
import { useEffect, useRef } from 'react';
import { Circle } from 'lucide-react';

/** 参考工具栏中的上下文胶囊；角色选择走可直达的空间菜单，这里只保留上下文估算。 */
export function ComposerContextChips({
  contextTokens,
  contentChars,
}: {
  contextTokens?: number | null;
  contentChars: number;
}) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) {
        root.current
          ?.querySelectorAll('details[open]')
          .forEach((node) => node.removeAttribute('open'));
      }
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, []);
  const tokens = Math.ceil(contentChars / 2);
  const percent = contextTokens ? Math.ceil((tokens / contextTokens) * 100) : null;
  return (
    <div
      className="chat-context-chips"
      ref={root}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          const details = (event.target as HTMLElement).closest('details');
          if (details) {
            event.stopPropagation();
            details.open = false;
            details.querySelector('summary')?.focus();
          }
        }
      }}
    >
      <details className="chat-context-chip chat-budget-chip">
        <summary aria-label="查看上下文估算">
          <Circle size={13} strokeWidth={1.65} />
          <span>{percent === null ? '—' : `${percent}%`}</span>
        </summary>
        <div className="chat-chip-popover">
          <strong>上下文估算</strong>
          <p>
            当前消息与输入约 {tokens.toLocaleString()} tokens
            {contextTokens
              ? `，模型上下文上限 ${contextTokens.toLocaleString()}`
              : '，模型上下文上限未知'}
            。
          </p>
          <p>
            按约 2 字符 / token
            估算，不含系统提示或附件；实际请求沿用原有历史截断与输出预留规则，以供应商返回用量为准。
          </p>
        </div>
      </details>
    </div>
  );
}
