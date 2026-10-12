import { TextbookWorkspace } from '@/features/textbook/TextbookWorkspace';

export const metadata = { title: '智启课源 · 教材资料库' };

/**
 * 教材资料库（`/textbooks`）：基础库 / 我的教材 + 导入与入库任务面板。
 * 壳与滚动容器由 layout 的 ModuleWorkspaceShell 统一提供（`textbooks` 已登记为业务根），
 * 页面只渲染业务组件；标题取自导航登记表。
 */
export default function TextbooksPage() {
  return <TextbookWorkspace />;
}
