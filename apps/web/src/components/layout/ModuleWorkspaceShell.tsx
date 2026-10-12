'use client';
import type { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { navigation } from '@/services/navigation';
import { WorkspaceShell } from './WorkspaceShell';
import { ShellScope } from './ShellScope';

// 业务模块根：由本壳统一提供 WorkspaceShell 与可滚动内容容器（.module-workspace-content），
// 页面本身裸渲染、不再自包壳。聊天、设置、教案（未来）为独立形态，不在此登记。
const independentRoots = new Set<string>([
  'textbooks',
  'knowledge-points',
  'question-bank',
  'learning-analysis',
  'assessments',
  'lesson-plans',
  'practices',
]);
export function ModuleWorkspaceShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  // 注册表条目是**无前导斜杠**的业务根首段（textbooks / lesson-plans …）；
  // 标题按 navigation 登记表用带斜杠路径反查。
  const root = pathname.split('/')[1] ?? '';
  if (!independentRoots.has(root)) {
    // 未加壳：向下声明“尚无公共壳”，让 404/错误页自行补一层（R-06）。
    return <ShellScope provided={false}>{children}</ShellScope>;
  }
  const title = navigation.find((item) => item.path === `/${root}`)?.label ?? '智启课源';
  return (
    <ShellScope provided>
      <WorkspaceShell pageTitle={title} className="module-workspace-shell">
        <div className="module-workspace-content">{children}</div>
      </WorkspaceShell>
    </ShellScope>
  );
}
