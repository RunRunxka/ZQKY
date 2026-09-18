'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import type { ReactNode } from 'react';
import '@/features/space/styles/space.css';

/**
 * S5-A 学习空间 hub-and-spoke 壳（对照参考 SpaceMain）：
 * /space 是唯一导航器，子页只提供"返回学习空间"链接，不复制持久侧栏；
 * 仪表盘本身不渲染返回链接（对照参考 isDashboard 分支）。
 */
export function SpaceMain({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname() ?? '';
  const isDashboard = pathname === '/space';
  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          {!isDashboard && (
            <Link className="space-back" href="/space">
              <ArrowLeft size={16} />
              返回学习空间
            </Link>
          )}
          {actions}
        </div>
        <h1>{title}</h1>
        {description && <p className="space-description">{description}</p>}
      </header>
      <main className="space-content">{children}</main>
    </div>
  );
}
