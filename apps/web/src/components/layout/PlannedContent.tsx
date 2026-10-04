'use client';

import { useRef, type ReactNode } from 'react';
import { useEntrance } from '@/components/motion/useEntrance';

/** 服务端保留导航登记与 metadata；这里只负责已渲染内容的入场。 */
export function PlannedContent({ children, className }: { children: ReactNode; className: string }) {
  const entranceRef = useRef<HTMLElement>(null);
  useEntrance(entranceRef, { preset: 'page' });
  return <main className={className} ref={entranceRef}>{children}</main>;
}
