import type { ChatMessage } from '@/contracts/chat';

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

/**
 * 上下文预算（可解释的截断规则）：
 * - 预算按 1 token ≈ 2 个字符估算（中文偏保守），并预留输出上限对应的输入空间；
 * - 从最新消息向前保留，超预算的更早消息丢弃；
 * - 始终保留最后一条用户消息（即使超预算）；
 * - 助手消息按对话投影计入（含已确认追问交流与续答，R12）。
 */
export function selectMessagesForRequest(
  messages: ChatMessage[],
  budgetChars: number,
): { role: 'user' | 'assistant' | 'system'; content: string }[] {
  const eligible = messages
    .map((message) =>
      message.asks?.length ? { ...message, content: conversationProjection(message) } : message,
    )
    .filter((message) => {
      if (message.role === 'user') return message.content.trim().length > 0;
      if (message.role === 'assistant') return message.content.trim().length > 0;
      return true; // system
    });
  if (eligible.length === 0) return [];

  const selected: ChatMessage[] = [];
  let total = 0;
  for (let index = eligible.length - 1; index >= 0; index -= 1) {
    const message = eligible[index];
    const isLastUser = index === eligible.length - 1 && message.role === 'user';
    if (!isLastUser && total + message.content.length > budgetChars) {
      break;
    }
    total += message.content.length;
    selected.unshift(message);
  }
  return selected.map((message) => ({
    role: message.role as 'user' | 'assistant' | 'system',
    content: message.content,
  }));
}
