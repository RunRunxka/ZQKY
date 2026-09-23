import type { ChatMessage, ChatRole } from '@/contracts/chat';

/**
 * 消息的对话投影（R12）：正文 + 已确认追问交流 + 逐卡续写，按时间顺序。
 * - 已确认答案以"问题：回答"行进入投影；未提交草稿不冒充已提交回答；
 * - 无追问卡的消息原样返回（旧纯 content 历史兼容，不重复正文）；
 * - 复制、服务请求上下文、预算计算共用同一投影，避免消费者各自适配。
 */
export function conversationProjection(m: ChatMessage): string {
  if (!m.asks?.length) return m.content;
  const parts: string[] = [];
  if (m.content) parts.push(m.content);
  for (const ask of m.asks) {
    if (ask.status === 'answered' && ask.answers?.length) {
      const lines = ask.questions
        .map((q) => {
          const answer = ask.answers!.find((a) => a.questionId === q.questionId);
          if (!answer || answer.skipped || (!answer.labels.length && !answer.freeText?.trim()))
            return null;
          const answerText = [answer.labels.join('、'), answer.freeText?.trim()]
            .filter(Boolean)
            .join('；');
          return `${q.prompt}：${answerText}`;
        })
        .filter(Boolean);
      if (lines.length) parts.push(`【追问回答】\n${lines.join('\n')}`);
    }
    if (ask.followUp) parts.push(ask.followUp);
  }
  return parts.join('\n');
}

/** 请求消息形状（与后端 LLMMessage 对齐） */
export interface RequestMessage {
  role: ChatRole;
  content: string;
}

/**
 * 对话历史 → 可发送的整条消息：统一走对话投影（R12），无正文的空占位
 * （失败/流式中的助手占位）与 system 空行不发送。
 */
export function projectRequestHistory(messages: ChatMessage[]): RequestMessage[] {
  const projected: RequestMessage[] = [];
  for (const message of messages) {
    const content = message.asks?.length ? conversationProjection(message) : message.content;
    if (!content.trim()) continue;
    projected.push({ role: message.role, content });
  }
  return projected;
}

/** 历史裁剪容量：字符、条数、后端单条上限（三者都是硬约束） */
export interface HistoryCapacity {
  /** 课程块与当前问题之外剩余的字符容量 */
  chars: number;
  /** 还能容纳的历史条数（已为课程块与当前问题留位） */
  count: number;
  /** 后端单条消息字符上限：超过该值的整条消息无法发送 */
  maxChars: number;
}

/**
 * 从最新向前保留**整条**历史消息（绝不拼接半条消息）：
 * - 某一条放不下（字符、条数或单条上限任一不满足）即停止，其后更旧的消息一并丢弃，
 *   保证发送的是连续的近期上下文，而不是带空洞的历史；
 * - 返回值中的 `dropped` 是**因预算被丢弃**的历史条数（调用方保证其中不含当前问题）。
 */
export function takeNewestMessages(
  entries: RequestMessage[],
  capacity: HistoryCapacity,
): { messages: RequestMessage[]; dropped: number } {
  if (entries.length === 0) return { messages: [], dropped: 0 };
  const selected: RequestMessage[] = [];
  let total = 0;
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    const entry = entries[index]!;
    const fits =
      entry.content.length <= capacity.maxChars &&
      selected.length < capacity.count &&
      total + entry.content.length <= capacity.chars;
    if (!fits) return { messages: selected, dropped: index + 1 };
    total += entry.content.length;
    selected.unshift(entry);
  }
  return { messages: selected, dropped: 0 };
}

/**
 * 旧预算入口（R12 投影的兼容包装，供历史行为断言/旧调用方读取）。
 *
 * **不是产品路径**：真实请求统一由 `buildChatRequest`（课程块 + 历史 + 当前问题的
 * 同一预算与后端限制）构建。本函数**不保证当前问题可容纳**，也不做后端限制自检——
 * 当前问题放不下必须由 `buildChatRequest` 明确失败（ok:false），不得静默丢弃。
 * 新代码不要使用本函数。
 */
export function selectMessagesForRequest(
  messages: ChatMessage[],
  budgetChars: number,
): RequestMessage[] {
  return takeNewestMessages(projectRequestHistory(messages), {
    chars: budgetChars,
    count: Number.POSITIVE_INFINITY,
    maxChars: Number.POSITIVE_INFINITY,
  }).messages;
}
