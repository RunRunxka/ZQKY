import { ChatWorkspace } from '@/features/chat/ChatWorkspace';

export const metadata = { title: '智启课源 · 学习问答' };

/**
 * 会话深链（S2）：`/chat/[sessionId]` 定位具体会话；无效 id 由界面明确提示。
 *
 * R-10：可选 `?message=<messageId>` 用于在**该会话内**定位来源消息。messageId 只在这里
 * 透传，不做跨会话匹配；找不到时由界面提示"原消息已不存在"。
 */
export default async function ChatSessionPage({
  params,
  searchParams,
}: {
  params: Promise<{ sessionId: string }>;
  searchParams: Promise<{ message?: string | string[] }>;
}) {
  const { sessionId } = await params;
  const query = await searchParams;
  const raw = query.message;
  const messageId = Array.isArray(raw) ? raw[0] : raw;
  return (
    <ChatWorkspace
      initialSessionId={sessionId}
      initialMessageId={messageId?.trim() ? messageId : undefined}
    />
  );
}
