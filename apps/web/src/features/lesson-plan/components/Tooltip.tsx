'use client';
/**
 * Radix Tooltip 的轻封装：dock / 图标按钮的悬浮说明。
 *
 * 样式走模块 CSS（`.lw-tooltip`），不引入 Tailwind。
 */
import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import type { ReactElement, ReactNode } from 'react';

export function TooltipProvider({ children }: { children: ReactNode }) {
  return (
    <TooltipPrimitive.Provider delayDuration={220} skipDelayDuration={320}>
      {children}
    </TooltipPrimitive.Provider>
  );
}

export function Tip({
  label,
  side = 'left',
  children,
}: {
  label: ReactNode;
  side?: 'top' | 'right' | 'bottom' | 'left';
  children: ReactElement;
}) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content className="lw-tooltip" side={side} sideOffset={10} collisionPadding={8}>
          {label}
          <TooltipPrimitive.Arrow className="lw-tooltip-arrow" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
