import { PracticesWorkspace } from '@/features/practices/PracticesWorkspace';

export const metadata = { title: '智启课源 · 练习' };

/**
 * 练习（`/practices`，需求 8 收尾模块）。
 *
 * 裸页面：壳与滚动容器由 `ModuleWorkspaceShell` 统一提供——需要总控把 `practices`
 * 登记进该壳的 `independentRoots`（与 textbooks / question-bank / lesson-plans 等业务根同级，
 * 该文件的注释里已预留 `practices` 条目）并加导航登记（规格见交付说明）；
 * 页面本身不再自包 `WorkspaceShell`（本卡不改导航与壳文件）。
 *
 * 页面结构：新建练习（学情报告 / 教师描述，可组合）→ 已有练习列表 → 当前练习
 * （编辑与微调 → 确认门槛 → 导出预览：学生卷 / 教师卷 A4 分页 + docx / xlsx 下载）。
 * 数据全部来自 FastAPI；AI 只进候选，教师确认（审核）后才可导出。
 */
export default function PracticesPage() {
  return <PracticesWorkspace />;
}
