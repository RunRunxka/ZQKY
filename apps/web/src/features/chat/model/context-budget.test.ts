import { describe, expect, it } from 'vitest';
import { selectMessagesForRequest } from './context-budget';
import type { ChatMessage } from '@/contracts/chat';

function message(
  role: ChatMessage['role'],
  content: string,
  status: ChatMessage['status'] = 'done',
): ChatMessage {
  return { id: `m-${Math.random().toString(36).slice(2)}`, role, content, status };
}

describe('上下文预算', () => {
  it('预算充足时保留全部消息', () => {
    const messages = [
      message('user', '第一问'),
      message('assistant', '第一答'),
      message('user', '第二问'),
    ];
    const selected = selectMessagesForRequest(messages, 1000);
    expect(selected).toHaveLength(3);
    expect(selected.at(-1)?.content).toBe('第二问');
  });

  it('超预算时从最旧开始丢弃，保留最近消息与其回复', () => {
    const messages = [
      message('user', '旧'.repeat(600)),
      message('assistant', '答'.repeat(600)),
      message('user', '新问题'),
    ];
    const selected = selectMessagesForRequest(messages, 800);
    // 最后一条用户消息 + 预算内最近的助手回复
    expect(selected).toHaveLength(2);
    expect(selected[0]?.content).toBe('答'.repeat(600));
    expect(selected[1]?.content).toBe('新问题');
  });

  it('失败或流式中的空 assistant 占位不发送', () => {
    const messages = [
      message('user', '问题'),
      message('assistant', '', 'error'),
      message('user', '换个问法'),
    ];
    const selected = selectMessagesForRequest(messages, 1000);
    expect(selected).toHaveLength(2);
    expect(selected.every((item) => item.content.length > 0)).toBe(true);
  });

  it('最后一条用户消息即使超预算也保留', () => {
    const messages = [message('user', '超'.repeat(5000))];
    const selected = selectMessagesForRequest(messages, 100);
    expect(selected).toHaveLength(1);
    expect(selected[0]?.content).toBe('超'.repeat(5000));
  });
});
