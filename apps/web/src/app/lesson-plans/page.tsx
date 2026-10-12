import { LessonWorkbench } from '@/features/lesson-plan/LessonWorkbench';

export const metadata = { title: '智启课源 · 教案工作台' };

/**
 * 教案工作台（`/lesson-plans`，需求 2，三栏沉浸式旗舰模块）。
 *
 * 裸页面：壳与滚动容器由 `ModuleWorkspaceShell` 统一提供——需要总控把 `lesson-plans`
 * 登记进该壳的 `independentRoots`（与 textbooks / knowledge-points 等业务根同级），
 * 页面本身不再自包 `WorkspaceShell`（本卡不改导航与壳文件）。
 *
 * 页面结构：64px 工作台顶栏（教案名称 + 同步状态 + 撤销/重做 + 云端 + 导出）
 * + 三栏（布局排版 / 内容编辑与生成 / A4 预览），列宽可拖拽、三栏独立滚动。
 * 数据：本机草稿自动保存；云端为可选的 CAS autosave；AI 只产候选，采用后才进草稿；
 * 封面与目录不预览，导出由后端组装后下载。
 */
export default function LessonPlansPage() {
  return <LessonWorkbench />;
}
