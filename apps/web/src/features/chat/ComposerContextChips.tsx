'use client';
import { useEffect, useRef } from 'react';
import type { ContextWindowView } from '@/contracts/model-settings';

/** 上下文容量环形进度：随已占用上下文顺时针逐渐填充；超 80% 转橙、超 95% 转红。 */
function ContextRing({ ratio }: { ratio: number | null }) {
  const size = 16;
  const stroke = 2;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const circumference = 2 * Math.PI * r;
  const clamped = ratio === null ? 0 : Math.min(1, Math.max(0, ratio));
  // 从顶部（-90°）起顺时针填充
  const dashOffset = circumference * (1 - clamped);
  const tone =
    ratio === null ? 'var(--muted)' : clamped >= 0.95 ? 'var(--danger)' : clamped >= 0.8 ? '#e08a2e' : 'var(--blue)';
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="var(--line)" strokeWidth={stroke} />
      <circle
        cx={cx}
        cy={cx}
        r={r}
        fill="none"
        stroke={tone}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        transform={`rotate(-90 ${cx} ${cx})`}
        style={{ transition: 'stroke-dashoffset 0.3s var(--ease-standard), stroke 0.3s var(--ease-standard)' }}
      />
    </svg>
  );
}

/** 参考工具栏中的上下文胶囊；角色选择走可直达的空间菜单，这里只保留上下文估算。 */
export function ComposerContextChips({
  contextTokens,
  contextSource,
  contentChars,
}: {
  contextTokens?: number | null;
  /** 上限来源（profile=档案手填；model-table=按模型族推断；unknown/缺失=不标注来源） */
  contextSource?: ContextWindowView['source'] | null;
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
  const ratio = contextTokens ? tokens / contextTokens : null;
  const percent = ratio === null ? null : Math.ceil(ratio * 100);
  // 上限来源：档案手填给精确值；按模型族推断的上限标注约值与可覆盖位置；未知不猜造数值。
  const limitNote = !contextTokens
    ? '，模型上下文上限未知'
    : contextSource === 'model-table'
      ? `，模型上下文上限约 ${contextTokens.toLocaleString()}（按模型族推断，可在设置→模型档案中手填覆盖）`
      : `，模型上下文上限 ${contextTokens.toLocaleString()}`;
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
        <summary aria-label={`上下文估算${percent === null ? '' : ` ${percent}%`}`}>
          <ContextRing ratio={ratio} />
          <span>{percent === null ? '—' : `${percent}%`}</span>
        </summary>
        <div className="chat-chip-popover">
          <strong>上下文估算</strong>
          <p>
            当前消息与输入约 {tokens.toLocaleString()} tokens
            {limitNote}。
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
