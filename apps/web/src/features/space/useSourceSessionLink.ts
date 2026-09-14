'use client';
import { useEffect, useState } from 'react';
import { createIdbChatRepository } from '@/services/chat-repository';
import { conversationSourceHref } from '@/services/chat-source';

export type SourceLinkState =
  | { status: 'loading' }
  | { status: 'missing' } // 条目根本没有可靠会话身份
  | { status: 'unavailable' } // 有 sessionId，但该会话已不存在（删除/其他浏览器）
  | { status: 'ready'; href: string };

/**
 * 解析"来源会话"链接（R-10）。
 *
 * 只有条目带**可靠 sessionId** 时才去校验；会话不存在时给出 `unavailable`
 * （保留原内容、提示来源不可用），绝不猜测绑定或创建假会话。
 * 未提供 sessionId 或为空 → `missing`，业务页据此不显示链接。
 */
export function useSourceSessionLink(sessionId: string | undefined | null): SourceLinkState {
  const [state, setState] = useState<SourceLinkState>(
    sessionId ? { status: 'loading' } : { status: 'missing' },
  );
  useEffect(() => {
    if (!sessionId) {
      setState({ status: 'missing' });
      return;
    }
    let cancelled = false;
    setState({ status: 'loading' });
    const repo = createIdbChatRepository('zhiqikeyuan-chat');
    void (async () => {
      try {
        const conversation = await repo.load(sessionId);
        if (cancelled) return;
        setState(
          conversation
            ? { status: 'ready', href: conversationSourceHref(conversation.id) }
            : { status: 'unavailable' },
        );
      } catch {
        // 读取失败按"来源暂不可用"处理：不猜测、不回退到最近会话
        if (!cancelled) setState({ status: 'unavailable' });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);
  return state;
}
