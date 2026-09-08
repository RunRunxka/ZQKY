import { describe, expect, it, vi } from 'vitest';
import {
  createMockChatService,
  createRealChatService,
  type ChatServiceEvent,
} from './chat-service';
import { streamChat, type ChatStreamInput } from '@/services/chat-stream';

function collect() {
  const events: ChatServiceEvent[] = [];
  return { events, emit: (event: ChatServiceEvent) => events.push(event) };
}

describe('真实聊天服务', () => {
  it('把 SSE 回调映射为带会话与轮次的统一事件', async () => {
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
    expect(events.map((e) => [e.type, e.sessionId, e.turnId])).toEqual([
      ['turn-start', 'session-1', 'turn-1'],
      ['text', 'session-1', 'turn-1'],
      ['reasoning', 'session-1', 'turn-1'],
      ['usage', 'session-1', 'turn-1'],
      ['end', 'session-1', 'turn-1'],
    ]);
  });
});

describe('模拟聊天服务', () => {
  it('回复带【模拟回复】标识并分块流式输出', async () => {
    const { events, emit } = collect();
    const service = createMockChatService({ chunkDelayMs: 0 });
    await service.run(
      {
        sessionId: 's',
        turnId: 't',
        messages: [{ role: 'user', content: '你好' }],
        signal: new AbortController().signal,
      },
      emit,
    );
    const text = events
      .filter((e) => e.type === 'text')
      .map((e) => e.delta)
      .join('');
    expect(text).toContain('【模拟回复】');
    expect(text).toContain('你好');
    expect(events.at(-1)?.type).toBe('end');
    // 过程与阶段事件进入统一通道
    expect(events.some((e) => e.type === 'process')).toBe(true);
    expect(events.some((e) => e.type === 'stage')).toBe(true);
  });

  it('布防失败后先输出部分文本再返回可重试错误', async () => {
    const { events, emit } = collect();
    const service = createMockChatService({ chunkDelayMs: 0 });
    service.armFailure();
    await service.run(
      {
        sessionId: 's',
        turnId: 't',
        messages: [{ role: 'user', content: '问' }],
        signal: new AbortController().signal,
      },
      emit,
    );
    const error = events.find((e) => e.type === 'error');
    expect(error?.error?.code).toBe('MOCK_ERROR');
    expect(error?.error?.retryable).toBe(true);
    // 下一次恢复正常
    const second = collect();
    await service.run(
      {
        sessionId: 's',
        turnId: 't2',
        messages: [{ role: 'user', content: '问' }],
        signal: new AbortController().signal,
      },
      second.emit,
    );
    expect(second.events.at(-1)?.type).toBe('end');
  });

  it('中止后停止输出并抛出中止异常', async () => {
    const { events, emit } = collect();
    const controller = new AbortController();
    const service = createMockChatService({ chunkDelayMs: 5 });
    const run = service.run(
      {
        sessionId: 's',
        turnId: 't',
        messages: [{ role: 'user', content: '问' }],
        signal: controller.signal,
      },
      emit,
    );
    controller.abort();
    await expect(run).rejects.toMatchObject({ name: 'AbortError' });
    const text = events
      .filter((e) => e.type === 'text')
      .map((e) => e.delta)
      .join('');
    expect(text.length).toBeLessThan('【模拟回复】已收到你的问题'.length);
  });
});
