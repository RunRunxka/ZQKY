import type { Metadata } from 'next';
import { RosterWorkspacePage } from '@/features/assessments/RosterWorkspacePage';

export const metadata: Metadata = { title: '智启课源 · 班级管理' };

/**
 * 班级管理（`/assessments/roster`，需求 6）：班级选择 + 学生名单（一键导入 xlsx/csv、
 * 逐个添加/编辑、删除可恢复）。
 *
 * 壳与滚动容器由 layout 的 ModuleWorkspaceShell 统一提供（`assessments` 需登记为业务根），
 * 页面只渲染业务组件；标题取自导航登记表，业务状态全部来自 FastAPI。
 * 本页**不包 WorkspaceShell**（避免与公共壳重复）。
 */
export default function AssessmentsRosterPage() {
  return <RosterWorkspacePage />;
}
