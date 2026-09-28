import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository } from '@/services/chat-repository';
import { ApiError } from '@/services/api-client';
import { createChatStore } from './store';
import type { ChatService, ChatServiceEvent, ChatServiceRequest } from './chat-service';

const extensions = { mcps: [], skills: [], capability: { value: 'rag', label: 'RAG 模式' } };
const interaction = { interactionId: 'i1', status: 'waiting' as const, questions: [{ questionId: 'q1', prompt: '补充原题条件', allowFreeText: true }] };
const answer = [{ questionId: 'q1', labels: [], freeText: 'x>0' }];
function pending(signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }));
}
function event(req: ChatServiceRequest, body: Omit<ChatServiceEvent, 'sessionId' | 'turnId'>): ChatServiceEvent {
  return { sessionId: req.sessionId, turnId: req.turnId, ...body } as ChatServiceEvent;
}

describe('教材轮次交付状态', () => {
  it('无需云模型；服务不可用时保留原输入，且不创建用户消息或调用推理', async () => {
    const service: ChatService = { kind: 'real', run: vi.fn(), checkRagAvailable: async () => ({ available: false, detail: '本地模型未启动' }) };
    const store = createChatStore({ repository: createMemoryChatRepository(), service });
    await store.getState().init(); store.getState().setDraft('原题');
    await store.getState().send('原题', null, extensions);
    expect(store.getState().draft).toBe('原题'); expect(store.getState().messages).toEqual([]);
    expect(store.getState().serviceNotice).toContain('本地模型未启动');
    expect(service.run).not.toHaveBeenCalled(); store.getState().dispose();
  });

  it('刷新恢复同 session/turn/cursor，文本与追问草稿不丢失，不创建第二条回答', async () => {
    const repo = createMemoryChatRepository();
    let firstRequest!: ChatServiceRequest;
    const cancel = vi.fn();
    const first = createChatStore({ repository: repo, service: { kind: 'real', cancel, run: async (req, emit) => {
      firstRequest = req;
      emit(event(req, { type: 'turn-start', eventId: 1 }));
      emit({ sessionId: req.sessionId, turnId: req.turnId, type: 'text', delta: '原文', eventId: 2 });
      emit({ sessionId: req.sessionId, turnId: req.turnId, type: 'wait-user', interaction, eventId: 3 });
      await pending(req.signal);
    } } });
    await first.getState().init();
    const running = first.getState().send('原题', null, extensions);
    await vi.waitFor(() => expect(first.getState().waitingInteractionId).toBe('i1'));
    first.getState().setAskDraft('i1', 'q1', { labels: [], freeText: '未提交草稿' });
    first.getState().setDraft('主输入草稿');
    first.getState().dispose(); await running; await first.getState().flush();
    expect(cancel).not.toHaveBeenCalled();
    const replay = vi.fn(async (req: ChatServiceRequest, emit: (e: ChatServiceEvent) => void) => {
      expect(req.rag).toMatchObject({ turnId: firstRequest.turnId, lastEventId: 3, question: '原题' });
      emit({ sessionId: req.sessionId, turnId: req.turnId, type: 'text', delta: '原文', eventId: 2 });
      emit({ sessionId: req.sessionId, turnId: req.turnId, type: 'reply-accepted', interactionId: 'i1', submissionId: 'a1', answers: answer, eventId: 4 });
      emit({ sessionId: req.sessionId, turnId: req.turnId, type: 'text', delta: '续答', eventId: 5 });
      emit({ sessionId: req.sessionId, turnId: req.turnId, type: 'end', finishReason: 'stop', eventId: 6 });
    });
    const second = createChatStore({ repository: repo, service: { kind: 'real', run: replay } });
    await second.getState().init();
    const restored = second.getState().messages[1];
    expect(restored.rag?.status).toBe('interrupted');
    expect(restored.asks?.[0].drafts.q1.freeText).toBe('未提交草稿');
    await second.getState().resumeRag(restored.id);
    expect(second.getState().messages).toHaveLength(2);
    expect(second.getState().messages[1]).toMatchObject({ content: '原文', status: 'done', rag: { lastEventId: 6, status: 'terminal' } });
    expect(second.getState().messages[1].asks?.[0]).toMatchObject({ status: 'answered', followUp: '续答' });
    expect(second.getState().draft).toBe('主输入草稿'); second.getState().dispose();
  });

  it('取消即本地终态并调用后端取消；迟到事件和迟到ACK不复活卡片', async () => {
    let emitLate!: (e: ChatServiceEvent) => void, req!: ChatServiceRequest;
    let ack!: (value: { accepted: boolean }) => void;
    const cancel = vi.fn().mockResolvedValue(undefined);
    const service: ChatService = { kind: 'real', cancel,
      run: async (request, emit) => { req = request; emitLate = emit; emit({ sessionId: req.sessionId, turnId: req.turnId, type: 'wait-user', interaction, eventId: 1 }); await pending(req.signal); },
      submitReply: vi.fn(() => new Promise<{ accepted: boolean }>((resolve) => { ack = resolve; })),
    };
    const store = createChatStore({ repository: createMemoryChatRepository(), service }); await store.getState().init();
    const running = store.getState().send('原题', null, extensions);
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('i1'));
    const submitting = store.getState().submitReply(answer);
    await vi.waitFor(() => expect(service.submitReply).toHaveBeenCalledOnce());
    store.getState().stop();
    expect(cancel).toHaveBeenCalledWith({ sessionId: req.sessionId, turnId: req.turnId, channel: 'rag' });
    expect(store.getState().messages[1].status).toBe('stopped');
    emitLate({ sessionId: req.sessionId, turnId: req.turnId, type: 'text', delta: '迟到结果', eventId: 2 });
    ack({ accepted: true }); expect(await submitting).toBe(false); await running;
    expect(store.getState().messages[1].content).toBe('');
    expect(store.getState().messages[1].asks?.[0].status).toBe('interrupted');
    expect(store.getState().messages[1].rag?.status).toBe('terminal'); store.getState().dispose();
  });

  it('提交网络异常后复用相同幂等键和答案，收到 SSE 确认才恢复真实已答状态', async () => {
    let req!: ChatServiceRequest, send!: (e: ChatServiceEvent) => void;
    const submissions: Array<{ submissionId: string; answers: unknown }> = [];
    const service: ChatService = { kind: 'real', run: async (request, emit) => { req = request; send = emit; emit({ sessionId: req.sessionId, turnId: req.turnId, type: 'wait-user', interaction, eventId: 1 }); await pending(req.signal); },
      submitReply: async (reply) => {
        submissions.push(reply);
        if (submissions.length === 1) throw new Error('连接中断');
        send({ sessionId: req.sessionId, turnId: req.turnId, type: 'reply-accepted', interactionId: 'i1', submissionId: reply.submissionId, answers: reply.answers, eventId: 2 });
        return { accepted: true };
      },
    };
    const store = createChatStore({ repository: createMemoryChatRepository(), service }); await store.getState().init();
    const running = store.getState().send('原题', null, extensions); await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('i1'));
    expect(await store.getState().submitReply(answer)).toBe(false);
    expect(store.getState().messages[1].asks?.[0].pendingSubmission).toBeTruthy();
    expect(await store.getState().submitReply([{ questionId: 'q1', labels: [], freeText: '不同内容' }])).toBe(true);
    expect(submissions[0].submissionId).toBe(submissions[1].submissionId);
    expect(submissions[1].answers).toEqual(answer);
    expect(store.getState().messages[1].asks?.[0].status).toBe('answered');
    store.getState().stop(); await running; store.getState().dispose();
  });

  it('恢复过期落真实错误终态，草稿仍在，不静默重推理', async () => {
    const repo = createMemoryChatRepository();
    const service: ChatService = { kind: 'real', run: async () => { throw new ApiError('RAG_DISCONNECTED', '断流', 0, true); } };
    const store = createChatStore({ repository: repo, service }); await store.getState().init();
    await store.getState().send('原题', null, extensions);
    store.getState().setDraft('另一个草稿');
    service.run = vi.fn(async () => { throw new ApiError('RAG_TURN_EXPIRED', '恢复窗口已过期，请重新提问。', 410, false); });
    await store.getState().resumeRag(store.getState().messages[1].id);
    expect(store.getState().messages[1]).toMatchObject({ status: 'error', error: { code: 'RAG_TURN_EXPIRED' }, rag: { status: 'terminal' } });
    expect(service.run).toHaveBeenCalledOnce(); expect(store.getState().draft).toBe('另一个草稿'); store.getState().dispose();
  });

  it('回答提交期间新增的输入不会被迟到确认清空；明确校验拒绝允许修改后重试', async () => {
    let ack!: (value: { accepted: boolean }) => void;
    let attempts = 0;
    const service: ChatService = { kind: 'real', run: async (req, emit) => {
      emit({ sessionId: req.sessionId, turnId: req.turnId, type: 'wait-user', interaction, eventId: 1 });
      await pending(req.signal);
    }, submitReply: async () => {
      attempts++;
      if (attempts === 1) throw new ApiError('RAG_INPUT_TOO_LONG', '补充过长', 422, false);
      return new Promise<{ accepted: boolean }>((resolve) => { ack = resolve; });
    } };
    const store = createChatStore({ repository: createMemoryChatRepository(), service }); await store.getState().init();
    const run = store.getState().send('原题', null, extensions); await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('i1'));
    expect(await store.getState().submitReply(answer)).toBe(false);
    expect(store.getState().messages[1].asks?.[0].pendingSubmission).toBeUndefined();
    store.getState().setDraft('原补充');
    const submission = store.getState().submitComposerReply('原补充');
    await vi.waitFor(() => expect(attempts).toBe(2));
    store.getState().setDraft('提交期间新写的草稿');
    ack({ accepted: true }); expect(await submission).toBe(true);
    expect(store.getState().draft).toBe('提交期间新写的草稿');
    store.getState().stop(); await run; store.getState().dispose();
  });
});
