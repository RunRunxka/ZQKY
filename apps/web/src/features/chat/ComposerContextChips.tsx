'use client';
import { useEffect, useRef } from 'react';
import type { ContextWindowView } from '@/contracts/model-settings';
import { formatTokenCount, type ContextUsage } from './context-usage';

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

/** 参考工具栏中的上下文胶囊；角色选择走可直达的空间菜单，这里只保留上下文占用。 */
export function ComposerContextChips({
  contextTokens,
  contextSource,
  usage,
  canRefresh = false,
  refreshing = false,
  notice = null,
  onRefresh,
}: {
  contextTokens?: number | null;
  /** 上限来源（profile=档案；model=精确模型 ID；upstream=上游读取；model-table=族暂估；unknown=未知） */
  contextSource?: ContextWindowView['source'] | null;
  /** 真实用量优先、草稿估算补齐的上下文占用 */
  usage: ContextUsage;
  /** 当前上限是否来自估算/未知，可请求上游读取 */
  canRefresh?: boolean;
  refreshing?: boolean;
  notice?: string | null;
  onRefresh?: () => void;
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
  const tokens = usage.usedTokens;
  const ratio = contextTokens ? tokens / contextTokens : null;
  const percent = ratio === null ? null : Math.ceil(ratio * 100);
  // 上限来源：档案/精确模型 ID/上游读取给明确值；模型族暂估标注约值与覆盖路径；未知不猜造数值。
  const limitNote = !contextTokens
    ? '，模型上下文上限未知'
    : contextSource === 'model-table'
      ? `，模型上下文上限约 ${contextTokens.toLocaleString()}（按模型族暂估，可点下方“读取模型信息”或在模型档案手填覆盖）`
      : contextSource === 'model'
        ? `，模型上下文上限 ${contextTokens.toLocaleString()}（按模型 ID 已知值）`
        : contextSource === 'upstream'
          ? `，模型上下文上限 ${contextTokens.toLocaleString()}（来自上游模型信息）`
          : contextSource === 'profile'
            ? `，模型上下文上限 ${contextTokens.toLocaleString()}（来自模型档案）`
            : `，模型上下文上限 ${contextTokens.toLocaleString()}`;
  const sourceText =
    usage.source === 'provider'
      ? `基准是最近一轮供应商返回的输入 ${formatTokenCount(usage.baselineTokens)} tokens（含系统提示、历史与工具结果）；其后新增约 ${formatTokenCount(usage.tailTokens)} tokens、输入框约 ${formatTokenCount(usage.draftTokens)} tokens 为本地估算`
      : `尚无可用的真实用量，按可见消息与输入框约 ${formatTokenCount(usage.usedTokens)} tokens 估算（不含系统提示与工具结果）`;
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
        <summary
          aria-label={`上下文占用${percent === null ? '' : ` ${percent}%`}`}
          title={usage.source === 'provider' ? '上下文占用（真实用量）' : '上下文占用（本地估算）'}
        >
          <ContextRing ratio={ratio} />
          <span>{percent === null ? '—' : `${percent}%`}</span>
        </summary>
        <div className="chat-chip-popover">
          <strong>上下文占用</strong>
          <p>
            当前约 {formatTokenCount(tokens)} tokens
            {limitNote}。
          </p>
          <p>{sourceText}。</p>
          {usage.outputTokens !== null && (
            <p>基准轮输出累计 {formatTokenCount(usage.outputTokens)} tokens。</p>
          )}
          {usage.cachedInputTokens !== null && usage.cachedInputTokens > 0 && (
            <p>其中缓存命中输入 {formatTokenCount(usage.cachedInputTokens)} tokens。</p>
          )}
          {notice && <p role="status">{notice}</p>}
          {canRefresh && onRefresh && (
            <button type="button" disabled={refreshing} onClick={onRefresh}>
              {refreshing ? '正在读取…' : '读取模型信息'}
            </button>
          )}
        </div>
      </details>
    </div>
  );
}
