/**
 * 聊天来源链接的单一拼装点（R-10）。
 *
 * 业务页（笔记/题库）回链聊天会话时只能用它，避免各页各自拼接出
 * `?mode=mock` 之类的过期参数，或把 messageId 当成 sessionId。
 */

/**
 * 由**真实会话 id**生成聊天深链；可选 messageId 仅用于**会话内**定位到具体消息。
 *
 * - 只有 sessionId：打开该会话。
 * - 带 messageId：先打开该会话，再在**该会话内**查找该消息并给出可识别提示。
 *   绝不跨会话搜索同名内容，也不猜测消息归属。
 */
export function conversationSourceHref(sessionId: string, messageId?: string | null): string {
  const base = `/chat/${encodeURIComponent(sessionId)}`;
  return messageId ? `${base}?message=${encodeURIComponent(messageId)}` : base;
}
