import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import '@/styles/globals.css';
import '@/styles/motion.css';
import { MotionPreference } from '@/components/layout/MotionPreference';
export const metadata: Metadata = {
  title: '智启课源 · 教案工作台',
  description: '中文学习与备课工作台',
};
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <MotionPreference />
        {children}
      </body>
    </html>
  );
}
