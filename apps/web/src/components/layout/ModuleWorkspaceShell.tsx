'use client';
import type { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { navigation } from '@/services/navigation';
import { WorkspaceShell } from './WorkspaceShell';
import { ShellScope } from './ShellScope';

// 这些独立模块此前没有全局导航；已有壳的聊天、教案、设置和规划页不重复嵌套。
// 注：协同写作/沉浸阅读/学习空间/笔记本/Whisper 已移除实现并走 [planned] 规划页
// （规划页自带壳），不再登记为独立模块根，避免双重壳。
const independentRoots = new Set([
  '/knowledge-bases',
  '/knowledge-points',
  '/books',
  '/courses',
  '/question-bank',
  '/assessments',
  '/learning-analysis',
  '/practices',
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
