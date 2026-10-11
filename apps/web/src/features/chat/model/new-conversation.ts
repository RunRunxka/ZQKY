/** 新会话形状（推倒重做：无课程归属字段）。 */
import type { Conversation } from '@/contracts/chat';

export function buildNewConversation(id: string, title: string, now: () => string): Conversation {
  return {
    id,
    title,
    createdAt: now(),
    updatedAt: now(),
    messages: [],
    modelProfileId: undefined,
  } as Conversation;
}
