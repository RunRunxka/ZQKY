'use client';

import { useRef, type HTMLAttributes } from 'react';
import { useSlidingIndicator } from '@/components/motion/useSlidingIndicator';

/**
 * 带滑动指示器的分段组（页签 / 分段筛选）。渲染与原来完全相同的 `<div>`（role、aria、类名
 * 原样透传），只多一个 `data-sliding-indicator`（`pill` 滑块 / `underline` 下划线），当前项由子按钮自身的 `.current` /
 * `aria-selected` 决定；`activeKey` 仅用于在切换后重新测量。
 */
export function SlidingGroup({
  activeKey,
  variant = 'pill',
  ...props
}: HTMLAttributes<HTMLDivElement> & { activeKey: unknown; variant?: 'pill' | 'underline' }) {
  const ref = useRef<HTMLDivElement>(null);
  useSlidingIndicator(ref, activeKey);
  return <div ref={ref} data-sliding-indicator={variant === 'underline' ? 'underline' : ''} {...props} />;
}
