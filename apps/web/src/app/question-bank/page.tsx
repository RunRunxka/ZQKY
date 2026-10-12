import { QuestionBankWorkspace } from '@/features/question-bank/QuestionBankWorkspace';

export const metadata = { title: '智启课源 · 题库' };

/**
 * 题库（`/question-bank`，需求 4）：按知识点与难度分类的题目库——
 * 顶部筛选条 + 左「知识点分类」树（含题量计数）+ 右「题目列表」（题干/难度徽标/编辑/删除/分页），
 * 「添加题目」「批量导入（含教材课后习题提取）」收进面板。
 *
 * 壳与滚动容器由 layout 的 ModuleWorkspaceShell 统一提供（`question-bank` 登记为业务根），
 * 页面只渲染业务组件；标题取自导航登记表，业务状态全部来自 FastAPI。
 */
export default function QuestionBankPage() {
  return <QuestionBankWorkspace />;
}
