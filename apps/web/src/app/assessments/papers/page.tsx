import type { Metadata } from 'next';
import { PapersWorkspacePage } from '@/features/assessments/PapersWorkspacePage';

export const metadata: Metadata = { title: '智启课源 · 试卷管理' };

/**
 * 试卷管理（`/assessments/papers`，需求 6）：导入试卷（DOCX / PDF 文本层）→ 校对拆题与
 * AI 知识点分类建议 → 确认入库；表格下方按知识点给出占比环状图。
 *
 * 壳与滚动容器由 layout 的 ModuleWorkspaceShell 统一提供（`assessments` 需登记为业务根），
 * 页面只渲染业务组件；标题取自导航登记表，业务状态全部来自 FastAPI。
 * 本页**不包 WorkspaceShell**（避免与公共壳重复）。
 */
export default function AssessmentsPapersPage() {
  return <PapersWorkspacePage />;
}
