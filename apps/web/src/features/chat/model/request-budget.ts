/** 对话请求组装（骨架版）：历史裁剪与字符预算账目；无课程/教材块。 */

import type { ChatMessage, RequestBudgetRecord } from '@/contracts/chat';

export const BACKEND_REQUEST_LIMITS = {
  /** 后端单条消息字符上限（与 /chat/stream 校验一致） */
  maxMessageChars: 32000,
  /** 后端消息总长度字符上限 */
  maxTotalChars: 128000,
} as const;

export interface BackendRequestLimits {
  maxMessageChars: number;
  maxTotalChars: number;
}

export type RequestNote = string;

export interface BuildChatRequestInput {
  history: ChatMessage[];
  question: string;
  contextTokens?: number | null;
  maxOutputTokens?: number | null;
  limits?: BackendRequestLimits;
}

export interface BuildRequestResult {
  messages: { role: 'user' | 'assistant' | 'system'; content: string }[];
  record: RequestBudgetRecord;
  notes: RequestNote[];
}

/** 会话投影（估算字符用）：只取正文。 */
export function conversationProjection(message: ChatMessage): string {
  return message.content ?? '';
}

/** 历史请求视角：只带非空正文的 user/assistant 消息。 */
export function requestHistory(messages: ChatMessage[]): ChatMessage[] {
  return messages.filter(
    (m) => (m.role === 'user' || m.role === 'assistant') && !!m.content.trim(),
  );
}

function estimateBudgetChars(contextTokens?: number | null, maxOutputTokens?: number | null): number {
  const context = typeof contextTokens === 'number' && contextTokens > 0 ? contextTokens : 8192;
  const output = typeof maxOutputTokens === 'number' && maxOutputTokens > 0 ? maxOutputTokens : 2048;
  // 1 token ≈ 2 字符的保守估计；为输出预留空间
  const raw = (context - output) * 2;
  return Math.max(2000, Math.min(raw, BACKEND_REQUEST_LIMITS.maxTotalChars));
}

/**
 * 组装一次请求：历史按预算从旧到新裁剪（保留当前问题完整），产出预算账目。
 * 账目只记录**发送时**的事实，不改写历史正文。
 */
export function buildChatRequest(input: BuildChatRequestInput): BuildRequestResult {
  const limits = input.limits ?? BACKEND_REQUEST_LIMITS;
  const inputBudgetChars = estimateBudgetChars(input.contextTokens, input.maxOutputTokens);
  const question = input.question.slice(0, limits.maxMessageChars);
  const notes: RequestNote[] = [];
  let used = question.length;
  const history = requestHistory(input.history);
  const keptReversed: BuildRequestResult['messages'] = [];
  let dropped = 0;
  for (let index = history.length - 1; index >= 0; index -= 1) {
    const message = history[index]!;
    if (used + message.content.length > inputBudgetChars) {
      dropped += 1;
      continue;
    }
    used += message.content.length;
    keptReversed.push({ role: message.role as 'user' | 'assistant', content: message.content });
  }
  const messages: BuildRequestResult['messages'] = [...keptReversed.reverse()];
  messages.push({ role: 'user', content: question });
  if (dropped > 0) notes.push(`已按上下文预算裁剪 ${dropped} 条较早历史（当前问题完整保留）。`);
  const record: RequestBudgetRecord = {
    totalChars: used,
    inputBudgetChars,
    maxMessageChars: limits.maxMessageChars,
    maxTotalChars: limits.maxTotalChars,
    historyDroppedMessages: dropped,
  };
  return { messages, record, notes };
}
