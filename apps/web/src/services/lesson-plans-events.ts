/**
 * 教案写操作完成后的跨页面失效信号。
 *
 * 对话与教案工作台是两个独立 store（且没有全局查询缓存），Agent 在 /chat 里成功
 * 创建/应用教案后，已打开的「本地教案」对话框需要重新拉列表。这里只用浏览器事件
 * 广播（客户端生命周期内触发，不读模块顶层 window），不引入新的全局状态。
 */

export const LESSON_PLANS_CHANGED_EVENT = 'zqky:lesson-plans-changed';

/** 会改变教案列表/正文的 Agent 工具（工具成功收尾时广播）。 */
export const LESSON_WRITE_TOOLS: ReadonlySet<string> = new Set([
  'create_lesson_plan_draft',
  'apply_lesson_proposal',
]);

export function notifyLessonPlansChanged(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(LESSON_PLANS_CHANGED_EVENT));
}
