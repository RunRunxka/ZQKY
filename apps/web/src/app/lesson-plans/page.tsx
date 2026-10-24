import { LessonWorkbench } from '@/features/lesson-plan/LessonWorkbench';

export const metadata = { title: '智启课源 · 教案工作台' };

/**
 * 教案工作台（`/lesson-plans`，R12：magic-resume 形态的三栏沉浸式编辑器）。
 *
 * 裸页面：壳与滚动容器由 `ModuleWorkspaceShell` 统一提供——`lesson-plans` 已登记在
 * `independentRoots`，页面本身不再自包 `WorkspaceShell`。
 *
 * 页面结构：64px 顶栏（课题名 + 保存胶囊 + 撤销/重做 + 本地教案 + 导出）
 * + 三栏（模块轨与排版 / 当前章节与 AI 生成 / A4 校样台）+ 右侧悬浮 dock；
 * 列宽可拖拽、面板可折叠、三栏独立滚动。正文按 Word 模板四表还原（第 3 页起），
 * 封面与目录在导出时生成；目录页码取预览分页（`sectionPages`）。
 * 数据：本机草稿自动保存；云端为可选的 CAS autosave；AI 只产候选，采用后才进草稿。
 */
export default function LessonPlansPage() {
  return <LessonWorkbench />;
}
