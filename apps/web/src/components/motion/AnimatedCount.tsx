'use client';
import NumberFlow from '@number-flow/react';
import { useMotionPreference } from '@/components/layout/MotionPreference';

/**
 * 数字翻转计数（NumberFlow）：数值变化时逐位滚动，替代瞬间跳变。
 * 未取到数值显示「—」（与 countText 同口径）；应用内「减少动画」或系统偏好开启时直接显示静态文本。
 */
export function AnimatedCount({ value }: { value: number | undefined }) {
  const { reduced } = useMotionPreference();
  if (value === undefined) return <>—</>;
  if (reduced) return <>{value}</>;
  return <NumberFlow value={value} />;
}
