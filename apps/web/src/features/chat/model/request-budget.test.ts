import { describe, expect, it } from 'vitest';
import { buildChatRequest, BACKEND_REQUEST_LIMITS } from './request-budget';
import type { ChatMessage } from '@/contracts/chat';

function message(id: string, role: 'user' | 'assistant', content: string): ChatMessage {
  return { id, role, content, status: 'done' };
}

describe('请求组装（骨架版）', () => {
  it('保留当前问题并携带历史', () => {
    const result = buildChatRequest({
      history: [message('m1', 'user', '第一问'), message('m2', 'assistant', '第一答')],
      question: '第二问',
      contextTokens: 8000,
      maxOutputTokens: 2000,
    });
    expect(result.messages.map((m) => m.content)).toEqual(['第一问', '第一答', '第二问']);
    expect(result.record.historyDroppedMessages).toBe(0);
    expect(result.record.totalChars).toBeGreaterThan(0);
  });

  it('超预算时裁剪较早历史，当前问题完整保留', () => {
    const long = 'x'.repeat(30000);
    const result = buildChatRequest({
      history: [message('m1', 'user', long), message('m2', 'assistant', long)],
      question: '最新问题',
      contextTokens: 8000,
      maxOutputTokens: 2000,
      limits: { maxMessageChars: BACKEND_REQUEST_LIMITS.maxMessageChars, maxTotalChars: 200000 },
    });
    expect(result.messages.at(-1)?.content).toBe('最新问题');
    expect(result.record.historyDroppedMessages).toBeGreaterThan(0);
    expect(result.notes.length).toBeGreaterThan(0);
  });
});
