'use client';
import { createContext, useContext, type ReactNode } from 'react';
import { WorkspaceShell } from './WorkspaceShell';

/**
 * 公共壳的提供状态（R-06）。
 *
 * `ModuleWorkspaceShell` 位于根布局，是“是否已有一层公共壳”的唯一判断点：
 * 已加壳时向下提供 `provided: true`；返回裸 children 时提供 `provided: false`。
 * 404/错误页据此决定要不要自己补一层壳，从而**任何路径都恰好一层壳**，
 * 既不会在独立模块内重复嵌套导航，也不会在未知路径上缺壳。
 */
const ShellProvidedContext = createContext<boolean>(false);

export function ShellScope({ provided, children }: { provided: boolean; children: ReactNode }) {
  return <ShellProvidedContext.Provider value={provided}>{children}</ShellProvidedContext.Provider>;
}

/**
 * 状态页（404/错误）专用外壳：已有公共壳时只渲染内容，否则补一层公共壳。
 * 标题、品牌按钮与可访问名称都来自同一条主页/登记定义，不硬编码。
 */
export function StatusShell({ pageTitle, children }: { pageTitle: string; children: ReactNode }) {
  const provided = useContext(ShellProvidedContext);
  const content = <main className="status-page">{children}</main>;
  if (provided) return content;
  return <WorkspaceShell pageTitle={pageTitle}>{content}</WorkspaceShell>;
}
