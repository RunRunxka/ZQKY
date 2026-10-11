import { describe, expect, it, vi } from 'vitest';
import { createRealChatService, type ChatServiceEvent } from './chat-service';
import { streamChat, type ChatStreamInput } from '@/services/chat-stream';

function collect() {
  const events: ChatServiceEvent[] = [];
  return { events, emit: (event: ChatServiceEvent) => events.push(event) };
}

describe('真实聊天服务（骨架）', () => {
  it('显式注入 stream 时走普通 /chat/stream：SSE 回调映射为统一事件', async () => {
    const { events, emit } = collect();
    const stream = vi.fn(
      async (input: ChatStreamInput, handlers: Parameters<typeof streamChat>[1]) => {
        expect(input.requestId).not.toBe('');
        handlers.onStart?.({ requestId: 'req', messageId: 'm1', modelProfileId: 'p1' });
        handlers.onText?.('你好');
        handlers.onReasoning?.('推理');
        handlers.onUsage?.({ inputTokens: 3, outputTokens: 2 });
        handlers.onEnd?.('stop');
      },
    );
    const service = createRealChatService({ stream });
    await service.run(
      {
        sessionId: 'session-1',
        turnId: 'turn-1',
        messages: [{ role: 'user', content: '问' }],
        modelProfileId: 'p1',
        signal: new AbortController().signal,
      },
      emit,
    );
    expect(events.map((e) => e.type)).toEqual(['turn-start', 'text', 'reasoning', 'usage', 'end']);
    const textEvent = events[1];
    expect(textEvent?.type === 'text' ? textEvent.delta : null).toBe('你好');
  });

  it('注入 stream 时 submitReply 明确不支持追问（REPLY_NOT_SUPPORTED）', async () => {
    const service = createRealChatService({ stream: async () => undefined });
    const ack = await service.submitReply!({
      sessionId: 's',
      turnId: 't',
      interactionId: 'x',
      submissionId: 'sub-1',
      answers: [],
      signal: new AbortController().signal,
    });
    expect(ack.accepted).toBe(false);
    expect(ack.code).toBe('REPLY_NOT_SUPPORTED');
  });

  it('未注入 stream 时默认走 Agent 通道（submitReply 委托 Agent 确认）', async () => {
    const service = createRealChatService();
    expect(typeof service.submitReply).toBe('function');
    expect(service.cancel).toBeTypeOf('function');
  });
});
