'use client';
import type { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { navigation } from '@/services/navigation';
import { WorkspaceShell } from './WorkspaceShell';
import { ShellScope } from './ShellScope';

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
  if (!independentRoots.has(root)) {
    // 未加壳：向下声明“尚无公共壳”，让 404/错误页自行补一层（R-06）。
    return <ShellScope provided={false}>{children}</ShellScope>;
  }
  const title = navigation.find((item) => item.path === root)?.label ?? '智启课源';
  return (
    <ShellScope provided>
      <WorkspaceShell pageTitle={title} className="module-workspace-shell">
        <div className="module-workspace-content">{children}</div>
      </WorkspaceShell>
    </ShellScope>
  );
}
