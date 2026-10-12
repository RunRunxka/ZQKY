import { LearningAnalysisWorkspace } from '@/features/learning-analysis/LearningAnalysisWorkspace';

export const metadata = { title: '智启课源 · 学情分析' };

/**
 * 学情分析（`/learning-analysis`，需求 5）：顶部筛选（班级 / 试卷 / 时间粒度）+ 小题分成绩单导入
 * + 五图（红色柱趋势 / 小题热力图 / 知识点排行 / 学生×知识点矩阵 / 分数段分布）+ AI 评价与导出。
 *
 * 壳与滚动容器由 layout 的 `ModuleWorkspaceShell` 统一提供（`learning-analysis` 业务根由总控登记），
 * 页面只渲染业务组件；标题取自导航登记表，业务状态全部来自 FastAPI。
 */
export default function LearningAnalysisPage() {
  return <LearningAnalysisWorkspace />;
}
