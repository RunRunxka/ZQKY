/**
 * 对话 store · 确认续跑回归（2026-10-19）。
 *
 * 关键缺陷：上一轮 message.end 已把 GenerationToken 置 terminal，而 submitReply 仍用旧
 * token 的 makeEmitter，恢复流事件会被全部丢弃；同时 /agent/confirm 缺 modelProfileId
 * 会直接 422。这里用内存仓储 + 假服务锁住：续跑必须用会话模型档位、新 token，并把
 * text/tool/end 写回同一助手消息。
 */
import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository } from '@/services/chat-repository';
import type {
  ChatService,
  ChatServiceEvent,
  ChatServiceReplyRequest,
  ChatServiceRequest,
} from './chat-service';
import { createChatStore } from './store';

function waitingCard(interactionId: string) {
  return {
    interactionId,
    intro: '写操作确认',
    status: 'waiting' as const,
    questions: [
      {
        questionId: `${interactionId}-q`,
        prompt: '生成并保存这份教案草稿？',
        options: [{ label: '确认执行' }, { label: '放弃' }],
        allowFreeText: false,
        multiSelect: false,
      },
    ],
  };
}

describe('对话 store · 确认续跑', () => {
  it('submitReply 用会话模型档位续跑，并把恢复流写回同一助手消息', async () => {
    const repository = createMemoryChatRepository();
    const submitReply = vi.fn(
      async (request: ChatServiceReplyRequest, emit?: (event: ChatServiceEvent) => void) => {
        expect(request.modelProfileId).toBe('p1');
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        emit?.({
          ...base,
          type: 'reply-accepted',
          interactionId: request.interactionId,
          submissionId: request.submissionId,
          answers: request.answers,
        });
        emit?.({ ...base, type: 'text', delta: '已生成教案草稿。' });
        emit?.({
          ...base,
          type: 'tool',
          call: {
            callId: 'tool-1',
            kind: 'skill',
            name: 'create_lesson_plan_draft',
            status: 'done',
            detail: 'lessonId=L1',
          },
        });
        emit?.({ ...base, type: 'end', finishReason: 'stop' });
        return { accepted: true };
      },
    );
    const service: ChatService = {
      kind: 'real',
      async run(request, emit) {
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        emit({ ...base, type: 'turn-start' });
        emit({ ...base, type: 'wait-user', interaction: waitingCard('confirm-1') });
        emit({ ...base, type: 'end', finishReason: 'stop' });
      },
      submitReply,
    };
    const store = createChatStore({ repository, service });
    await store.getState().init();
    await store.getState().send('生成《荷塘月色》教案', { id: 'p1', modelLabel: '模型一' });
    expect(store.getState().waitingInteractionId).toBe('confirm-1');

    const accepted = await store.getState().submitReply([
      { questionId: 'confirm-1-q', labels: ['确认执行'] },
    ]);
    expect(accepted).toBe(true);
    expect(submitReply).toHaveBeenCalledTimes(1);

    const assistant = store.getState().messages.at(-1)!;
    expect(assistant.role).toBe('assistant');
    expect(assistant.content).toBe('已生成教案草稿。');
    expect(assistant.status).toBe('done');
    expect(assistant.toolCalls?.some((call) => call.name === 'create_lesson_plan_draft')).toBe(true);
    expect(store.getState().waitingInteractionId).toBeNull();
    expect(store.getState().sending).toBe(false);
  });

  it('会话没有模型档位时不发确认请求，如实提示', async () => {
    const repository = createMemoryChatRepository();
    const submitReply = vi.fn();
    const service: ChatService = {
      kind: 'real',
      async run(request, emit) {
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        emit({ ...base, type: 'wait-user', interaction: waitingCard('confirm-2') });
        emit({ ...base, type: 'end', finishReason: 'stop' });
      },
      submitReply,
    };
    const store = createChatStore({ repository, service });
    await store.getState().init();
    await store.getState().send('生成教案', { id: 'p1', modelLabel: '模型一' });
    store.getState().setModel(null);
    expect(store.getState().waitingInteractionId).toBe('confirm-2');

    const accepted = await store.getState().submitReply([
      { questionId: 'confirm-2-q', labels: ['确认执行'] },
    ]);
    expect(accepted).toBe(false);
    expect(submitReply).not.toHaveBeenCalled();
    expect(store.getState().serviceNotice).toContain('模型档位');
  });

  it('续跑流弹出下一张卡时，不清掉新卡的等待状态', async () => {
    const repository = createMemoryChatRepository();
    const submitReply = vi.fn(
      async (request: ChatServiceReplyRequest, emit?: (event: ChatServiceEvent) => void) => {
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        emit?.({
          ...base,
          type: 'reply-accepted',
          interactionId: request.interactionId,
          submissionId: request.submissionId,
          answers: request.answers,
        });
        // 例如：先选班级，确认后同一续跑流里立刻又弹出「生成并保存」确认卡。
        emit?.({ ...base, type: 'wait-user', interaction: waitingCard('confirm-next') });
        emit?.({ ...base, type: 'end', finishReason: 'stop' });
        return { accepted: true };
      },
    );
    const service: ChatService = {
      kind: 'real',
      async run(request, emit) {
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        emit({ ...base, type: 'wait-user', interaction: waitingCard('confirm-first') });
        emit({ ...base, type: 'end', finishReason: 'stop' });
      },
      submitReply,
    };
    const store = createChatStore({ repository, service });
    await store.getState().init();
    await store.getState().send('生成教案', { id: 'p1', modelLabel: '模型一' });
    expect(store.getState().waitingInteractionId).toBe('confirm-first');

    await store.getState().submitReply([
      { questionId: 'confirm-first-q', labels: ['确认执行'] },
    ]);
    expect(store.getState().waitingInteractionId).toBe('confirm-next');
  });

  it('usage 事件：输入取最近一次调用，输出按轮累计', async () => {
    const repository = createMemoryChatRepository();
    const service: ChatService = {
      kind: 'real',
      async run(request, emit) {
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        emit({
          ...base,
          type: 'usage',
          usage: { inputTokens: 1000, outputTokens: 50, totalTokens: 1050 },
        });
        emit({
          ...base,
          type: 'usage',
          usage: { inputTokens: 1200, outputTokens: 30, totalTokens: 1230, cachedInputTokens: 400 },
        });
        emit({ ...base, type: 'end', finishReason: 'stop' });
      },
    };
    const store = createChatStore({ repository, service });
    await store.getState().init();
    await store.getState().send('你好', { id: 'p1', modelLabel: '模型一' });
    const assistant = store.getState().messages.at(-1)!;
    expect(assistant.usage).toEqual({
      inputTokens: 1200,
      outputTokens: 80,
      totalTokens: 1230,
      cachedInputTokens: 400,
    });
  });

  it('重试沿用原轮的扩展快照（思考强度不丢失）', async () => {
    const repository = createMemoryChatRepository();
    const run = vi.fn(
      async (request: ChatServiceRequest, emit: (event: ChatServiceEvent) => void) => {
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        emit({ ...base, type: 'end', finishReason: 'stop' });
      },
    );
    const service: ChatService = { kind: 'real', run };
    const store = createChatStore({ repository, service });
    await store.getState().init();
    await store.getState().send('你好', { id: 'p1', modelLabel: '模型一' }, {
      mcps: [],
      skills: [],
      capability: { value: '', label: '对话', config: { reasoningEffort: 'low' } },
    });
    const user = store.getState().messages.find((message) => message.role === 'user')!;

    await store.getState().retry(user.id, { id: 'p1', modelLabel: '模型一' });

    expect(run).toHaveBeenCalledTimes(2);
    const second = run.mock.calls[1]![0] as { extensions?: { capability?: { config?: Record<string, unknown> } } };
    expect(second.extensions?.capability?.config?.reasoningEffort).toBe('low');
  });

  it('确认续跑携带触发该卡的思考强度', async () => {
    const repository = createMemoryChatRepository();
    const submitReply = vi.fn(async (_request: ChatServiceReplyRequest) => {
      void _request;
      return { accepted: true };
    });
    const service: ChatService = {
      kind: 'real',
      async run(request, emit) {
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        emit({ ...base, type: 'wait-user', interaction: waitingCard('confirm-effort') });
        emit({ ...base, type: 'end', finishReason: 'stop' });
      },
      submitReply,
    };
    const store = createChatStore({ repository, service });
    await store.getState().init();
    await store.getState().send('生成教案', { id: 'p1', modelLabel: '模型一' }, {
      mcps: [],
      skills: [],
      capability: { value: '', label: '对话', config: { reasoningEffort: 'high' } },
    });

    await store.getState().submitReply([
      { questionId: 'confirm-effort-q', labels: ['确认执行'] },
    ]);

    const request = submitReply.mock.calls[0]?.[0] as ChatServiceReplyRequest;
    expect(request.reasoningEffort).toBe('high');
  });
});
