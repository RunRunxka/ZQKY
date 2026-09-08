import { ChatWorkspace } from '@/features/chat/ChatWorkspace';

export const metadata = { title: '智启课源 · 学习问答' };

/** 会话深链（S2）：/chat/[sessionId] 定位到具体会话；无效 id 由界面明确提示 */
export default async function ChatSessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <ChatWorkspace initialSessionId={sessionId} />;
}
