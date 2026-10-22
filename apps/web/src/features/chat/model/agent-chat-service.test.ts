import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ChatServiceEvent } from './chat-service';

const streamAgentMock = vi.fn();
const confirmAgentMock = vi.fn();

vi.mock('@/services/agent-stream', () => ({
  streamAgent: (...args: unknown[]) => streamAgentMock(...args),
  confirmAgent: (...args: unknown[]) => confirmAgentMock(...args),
}));

// 在 mock 之后导入被测模块
const { createAgentChatService } = await import('./agent-chat-service');

function collect() {
  const events: ChatServiceEvent[] = [];
  return { events, emit: (event: ChatServiceEvent) => events.push(event) };
}

afterEach(() => {
  streamAgentMock.mockReset();
  confirmAgentMock.mockReset();
});

describe('Agent 通道服务', () => {
  it('把 agent-stream 事件翻译为统一事件（text/tool/wait-user/end）', async () => {
    const { events, emit } = collect();
    streamAgentMock.mockImplementation(async (_input, handlers) => {
      handlers.onStart?.({ requestId: 'r', messageId: 'm', threadId: 'session-1', modelProfileId: 'p1' });
      handlers.onToolCall?.({ name: 'list_classes', args: {}, callId: 'c1' });
      handlers.onToolResult?.({ name: 'list_classes', callId: 'c1', output: '三一班' });
      handlers.onText?.('你有 1 个班级');
      handlers.onWaitConfirm?.({ confirmId: 'k1', payload: { kind: 'confirm', summary: '应用调整？' } });
      handlers.onEnd?.('stop');
    });
    const service = createAgentChatService();
    await service.run(
      {
        sessionId: 'session-1',
        turnId: 'turn-1',
        messages: [{ role: 'user', content: '我有哪些班级' }],
        modelProfileId: 'p1',
        signal: new AbortController().signal,
      },
      emit,
    );
    const types = events.map((e) => e.type);
    expect(types).toContain('turn-start');
    expect(types).toContain('tool');
    expect(types).toContain('text');
    expect(types).toContain('wait-user');
    expect(types.at(-1)).toBe('end');
    // 工具事件映射为 skill 过程
    const tool = events.find((e) => e.type === 'tool');
    expect(tool?.call?.name).toBe('list_classes');
    expect(tool?.call?.kind).toBe('skill');
    // wait-user 映射为可作答的选择/确认卡
    const wait = events.find((e) => e.type === 'wait-user');
    expect(wait?.interaction?.interactionId).toBe('k1');
    expect(wait?.interaction?.status).toBe('waiting');
    expect(wait?.interaction?.questions?.[0]?.options?.length).toBeGreaterThan(0);
    // threadId 与 sessionId 对齐
    expect(streamAgentMock.mock.calls[0]?.[0]?.threadId).toBe('session-1');
  });

  it('把 usage 事件映射为统一事件（真实 token 用量）', async () => {
    const { events, emit } = collect();
    streamAgentMock.mockImplementation(async (_input, handlers) => {
      handlers.onUsage?.({ inputTokens: 1000, outputTokens: 50, cachedInputTokens: 200 });
      handlers.onEnd?.('stop');
    });
    const service = createAgentChatService();
    await service.run(
      {
        sessionId: 'session-1',
        turnId: 'turn-1',
        messages: [{ role: 'user', content: '你好' }],
        modelProfileId: 'p1',
        signal: new AbortController().signal,
      },
      emit,
    );
    const usage = events.find((event) => event.type === 'usage');
    expect(usage?.usage).toEqual({
      inputTokens: 1000,
      outputTokens: 50,
      cachedInputTokens: 200,
    });
  });

  it('submitReply 把确认卡决定映射为 approve/reject 并调 confirmAgent', async () => {
    confirmAgentMock.mockResolvedValue(undefined);
    const service = createAgentChatService();
    const ack = await service.submitReply!({
      sessionId: 'session-1',
      turnId: 'turn-1',
      interactionId: 'k1',
      submissionId: 'sub-12345678',
      modelProfileId: 'p1',
      reasoningEffort: 'high',
      answers: [{ questionId: 'k1-q', labels: ['确认执行'] }],
      signal: new AbortController().signal,
    });
    expect(ack.accepted).toBe(true);
    const input = confirmAgentMock.mock.calls[0]?.[0];
    expect(input.decision).toBe('approve');
    expect(input.confirmId).toBe('k1');
    expect(input.threadId).toBe('session-1');
    expect(input.modelProfileId).toBe('p1');
    expect(input.reasoningEffort).toBe('high');
  });

  it('submitReply 把选择卡选定值经 value 传给后端', async () => {
    confirmAgentMock.mockResolvedValue(undefined);
    const service = createAgentChatService();
    await service.submitReply!({
      sessionId: 'session-1',
      turnId: 'turn-1',
      interactionId: 'sel-1',
      submissionId: 'sub-12345678',
      modelProfileId: 'p1',
      answers: [{ questionId: 'sel-1-q', labels: ['三年级二班'] }],
      signal: new AbortController().signal,
    });
    const input = confirmAgentMock.mock.calls[0]?.[0];
    expect(input.decision).toBe('approve');
    expect(input.value).toBe('三年级二班');
  });

  it('submitReply 把恢复流事件写回同一轮（reply-accepted/text/tool/end）', async () => {
    const { events, emit } = collect();
    confirmAgentMock.mockImplementation(async (_input, handlers) => {
      handlers.onStart?.({ requestId: 'r', messageId: 'm', threadId: 'session-1', modelProfileId: 'p1' });
      handlers.onText?.('已生成教案');
      handlers.onToolResult?.({ name: 'create_lesson_plan_draft', callId: 'c2', output: 'lessonId=L1' });
      handlers.onEnd?.('stop');
    });
    const service = createAgentChatService();
    const ack = await service.submitReply!(
      {
        sessionId: 'session-1',
        turnId: 'turn-1',
        interactionId: 'k1',
        submissionId: 'sub-12345678',
        modelProfileId: 'p1',
        answers: [{ questionId: 'k1-q', labels: ['确认执行'] }],
        signal: new AbortController().signal,
      },
      emit,
    );
    expect(ack.accepted).toBe(true);
    const types = events.map((event) => event.type);
    expect(types[0]).toBe('reply-accepted');
    expect(types).toContain('text');
    expect(types).toContain('tool');
    expect(types.at(-1)).toBe('end');
    const tool = events.find((event) => event.type === 'tool');
    expect(tool?.call?.name).toBe('create_lesson_plan_draft');
  });

  it('submitReply 缺模型档位时如实报错且不请求后端', async () => {
    const service = createAgentChatService();
    const ack = await service.submitReply!({
      sessionId: 'session-1',
      turnId: 'turn-1',
      interactionId: 'k1',
      submissionId: 'sub-12345678',
      answers: [{ questionId: 'k1-q', labels: ['确认执行'] }],
      signal: new AbortController().signal,
    });
    expect(ack.accepted).toBe(false);
    expect(ack.code).toBe('MODEL_PROFILE_MISSING');
    expect(confirmAgentMock).not.toHaveBeenCalled();
  });

  it('confirmAgent 失败时 submitReply 返回未接受与错误码', async () => {
    confirmAgentMock.mockRejectedValue({ code: 'UPSTREAM_ERROR', message: '上游异常' });
    const service = createAgentChatService();
    const ack = await service.submitReply!({
      sessionId: 'session-1',
      turnId: 'turn-1',
      interactionId: 'k1',
      submissionId: 'sub-12345678',
      modelProfileId: 'p1',
      answers: [{ questionId: 'k1-q', labels: ['放弃'] }],
      signal: new AbortController().signal,
    });
    expect(ack.accepted).toBe(false);
    expect(ack.code).toBe('UPSTREAM_ERROR');
  });
});
