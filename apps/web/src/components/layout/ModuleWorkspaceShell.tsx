'use client';
import type { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { navigation } from '@/services/navigation';
import { WorkspaceShell } from './WorkspaceShell';

// 这些独立模块此前没有全局导航；已有壳的聊天、教案、设置和规划页不重复嵌套。
const independentRoots = new Set([
  '/co-writer',
  '/reading',
  '/space',
  '/knowledge-bases',
  '/books',
  '/courses',
  '/notebooks',
  '/whisper',
]);
export function ModuleWorkspaceShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const root = `/${pathname.split('/')[1]}`;
  if (!independentRoots.has(root)) return children;
  const title = navigation.find((item) => item.path === root)?.label ?? '智启课源';
  return (
    <WorkspaceShell pageTitle={title} className="module-workspace-shell">
      <div className="module-workspace-content">{children}</div>
    </WorkspaceShell>
  );
}
