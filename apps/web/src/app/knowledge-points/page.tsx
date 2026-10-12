import { KnowledgePointsWorkspace } from '@/features/knowledge-points/KnowledgePointsWorkspace';

export const metadata = { title: '智启课源 · 知识点' };

/**
 * 知识点（`/knowledge-points`）：按教材目录成树的知识点库 + 节点详情编辑 +
 * 表格导入校对 / AI 候选 / 教材提取面板。
 *
 * 壳与滚动容器由 layout 的 ModuleWorkspaceShell 统一提供（`knowledge-points` 已登记为
 * 业务根），页面只渲染业务组件；标题取自导航登记表，业务状态全部来自 FastAPI。
 */
export default function KnowledgePointsPage() {
  return <KnowledgePointsWorkspace />;
}
