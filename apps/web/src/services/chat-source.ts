/**
 * 聊天来源链接的单一拼装点（R-10）。
 *
 * 业务页（笔记/题库）回链聊天会话时只能用它，避免各页各自拼接出
 * `?mode=mock` 之类的过期参数，或把 messageId 当成 sessionId。
 */

/** 由**真实会话 id**生成聊天深链。messageId 不属于此函数职责（仅用于会话内定位）。 */
export function conversationSourceHref(sessionId: string): string {
  return `/chat/${encodeURIComponent(sessionId)}`;
}
