import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository, type ChatRepository } from '@/services/chat-repository';
import { conversationProjection, selectMessagesForRequest } from './context-budget';
import type { AskUserInteraction } from '@/contracts/chat';
import {
  createMockChatService,
  createRealChatService,
  type ChatService,
  type ChatServiceEvent,
  type ChatServiceRequest,
  type MockChatService,
} from './chat-service';
import { createChatStore } from './store';

function turn(request: ChatServiceRequest) {
  return { sessionId: request.sessionId, turnId: request.turnId };
}

function askCard(status: AskUserInteraction['status'], interactionId = 'ask-1'): AskUserInteraction {
  return {
    interactionId,
    intro: '确认一下',
    questions: [
      { questionId: 'q1', prompt: '第一题', options: [{ label: 'A' }, { label: 'B' }], multiSelect: false },
      {
        questionId: 'q2',
        prompt: '第二题',
        options: [{ label: 'X' }, { label: 'Y' }],
        multiSelect: true,
        allowFreeText: true,
      },
    ],
    status,
    drafts: {},
  };
}

/** 计数包装：保留真实模拟服务的等待/提交内部状态，仅统计 run 调用次数 */
function countedMock(arm?: { ask?: boolean }) {
  const base: MockChatService = createMockChatService({ chunkDelayMs: 0 });
  if (arm?.ask) base.armAskUser();
  let runs = 0;
  const service: MockChatService = {
    kind: 'mock',
    armFailure: () => base.armFailure(),
    armAskUser: () => base.armAskUser(),
    armReplyFailure: () => base.armReplyFailure(),
    run: (request, emit) => {
      runs += 1;
      return base.run(request, emit);
    },
    submitReply: (request) => base.submitReply!(request),
  };
  return { service, runs: () => runs };
}

function mockStore(repo: ChatRepository, service: MockChatService) {
  const store = createChatStore({ mode: 'mock', repository: repo, services: { mock: service } });
  return store;
}

describe('追问卡与同轮续答（真实模拟脚本）', () => {
  it('等待期间轮次保持活动：无 end、run 只调一次、卡可交互', async () => {
    const { service, runs } = countedMock({ ask: true });
    const store = mockStore(createMemoryChatRepository(), service);
    await store.getState().init();
    const run = store.getState().send('问题', null);
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBeTruthy());
    const message = store.getState().messages[1];
    expect(message.asks).toHaveLength(1);
    expect(message.asks?.[0].status).toBe('waiting');
    expect(message.asks?.[0].questions).toHaveLength(2);
    expect(message.status).toBe('streaming');
    expect(store.getState().sending).toBe(true);
    expect(message.content).not.toContain('续答完成'); // 还没有结束事件
    expect(runs()).toBe(1); // 没有第二次普通 run
    store.getState().stop(); // 清理：取消等待
    await run;
  });

  it('回答后同 turnId 继续：卡→续写→第二卡→跳过→完成，run 仍只调一次', async () => {
    const { service, runs } = countedMock({ ask: true });
    const store = mockStore(createMemoryChatRepository(), service);
    await store.getState().init();
    const run = store.getState().send('问题', null);
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBeTruthy());

    // 卡 1：单选 + 多选/自由文本
    expect(
      await store.getState().submitReply([
        { questionId: 'q-style', labels: ['按知识点讲解'], freeText: '' },
        {
          questionId: 'q-materials',
          labels: ['结合课标', '给出示例'],
          freeText: '多给例子',
        },
      ]),
    ).toBe(true);
    const card1 = store.getState().messages[1].asks?.[0];
    expect(card1?.status).toBe('answered');
    expect(card1?.followUp).toContain('按知识点讲解');
    expect(card1?.followUp).toContain('结合课标、给出示例');
    expect(card1?.followUp).toContain('多给例子');

    // 卡 2：同一轮内的第二张追问卡
    await vi.waitFor(() =>
      expect((store.getState().waitingInteractionId ?? '').startsWith('ask-2')).toBe(true),
    );
    const card2Id = store.getState().waitingInteractionId!;
    expect(card2Id).not.toBe(card1?.interactionId);
    expect(store.getState().messages[1].asks).toHaveLength(2);
    // 全部跳过提交
    expect(
      await store.getState().submitReply([
        { questionId: 'q-summary', labels: [], freeText: '', skipped: true },
      ]),
    ).toBe(true);
    await run;
    const message = store.getState().messages[1];
    expect(message.status).toBe('done');
    expect(message.content).toContain('【模拟回复】');
    expect(message.asks?.[1].status).toBe('answered');
    expect(message.asks?.[1].answers?.[0].skipped).toBe(true);
    expect(message.asks?.[1].followUp ?? '').toContain('跳过');
    expect(store.getState().waitingInteractionId).toBeNull();
    expect(store.getState().sending).toBe(false);
    expect(runs()).toBe(1); // 全程一次 run：同 sessionId/turnId 继续，没有另开一轮
  });

  it('主输入框回答当前追问：走同一提交接口，自由文本计入第一道未答题', async () => {
    const { service, runs } = countedMock({ ask: true });
    const store = mockStore(createMemoryChatRepository(), service);
    await store.getState().init();
    const run = store.getState().send('问题', null);
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBeTruthy());
    expect(await store.getState().submitComposerReply('我想要按题目场景讲解，多给例子')).toBe(
      true,
    );
    expect(store.getState().draft).toBe(''); // 接受后清空输入
    // 第二卡：跳过完成整轮
    await vi.waitFor(() =>
      expect((store.getState().waitingInteractionId ?? '').startsWith('ask-2')).toBe(true),
    );
    expect(
      await store.getState().submitReply([
        { questionId: 'q-summary', labels: [], freeText: '', skipped: true },
      ]),
    ).toBe(true);
    await run;
    const asks = store.getState().messages[1].asks!;
    expect(asks[0].answers?.[0]).toMatchObject({
      labels: [],
      freeText: '我想要按题目场景讲解，多给例子',
    });
    expect(asks[0].answers?.[1].skipped).toBe(true);
    expect(asks[0].followUp).toContain('我想要按题目场景讲解，多给例子');
    expect(runs()).toBe(1);
  });

  it('提交失败保留草稿与选项，可重试成功（卡片级失败）', async () => {
    const { service, runs } = countedMock({ ask: true });
    service.armReplyFailure();
    const store = mockStore(createMemoryChatRepository(), service);
    await store.getState().init();
    const run = store.getState().send('问题', null);
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBeTruthy());
    store
      .getState()
      .setAskDraft(store.getState().waitingInteractionId!, 'q-style', {
        labels: ['按知识点讲解'],
        freeText: '',
      });
    const first = await store.getState().submitReply([
      { questionId: 'q-style', labels: ['按知识点讲解'], freeText: '' },
      { questionId: 'q-materials', labels: ['给出示例'], freeText: '' },
    ]);
    expect(first).toBe(false);
    const failed = store.getState().messages[1].asks?.[0];
    expect(failed?.status).toBe('failed');
    expect(failed?.error?.code).toBe('MOCK_REPLY_ERROR');
    expect(store.getState().waitingInteractionId).toContain('ask-1'); // 等待仍在，可重试

    // 重试：同一等待上下文，成功
    expect(
      await store.getState().submitReply([
        { questionId: 'q-style', labels: ['按知识点讲解'], freeText: '' },
        { questionId: 'q-materials', labels: ['给出示例'], freeText: '' },
      ]),
    ).toBe(true);
    expect(store.getState().messages[1].asks?.[0].status).toBe('answered');
    // 完成整轮
    await vi.waitFor(() =>
      expect((store.getState().waitingInteractionId ?? '').startsWith('ask-2')).toBe(true),
    );
    expect(
      await store.getState().submitReply([
        { questionId: 'q-summary', labels: [], freeText: '', skipped: true },
      ]),
    ).toBe(true);
    await run;
    expect(runs()).toBe(1);
  });

  it('等待中取消：卡标记中断、消息已停止，此后提交被拒绝', async () => {
    const { service } = countedMock({ ask: true });
    const repo = createMemoryChatRepository();
    const store = mockStore(repo, service);
    await store.getState().init();
    const run = store.getState().send('问题', null);
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBeTruthy());
    store.getState().stop();
    await run;
    const message = store.getState().messages[1];
    expect(message.status).toBe('stopped');
    expect(message.asks?.[0].status).toBe('interrupted');
    expect(store.getState().waitingInteractionId).toBeNull();
    expect(
      await store.getState().submitReply([
        { questionId: 'q-style', labels: ['A'], freeText: '' },
      ]),
    ).toBe(false);
    expect(message.asks?.[0].status).toBe('interrupted');
    const saved = await repo.load(store.getState().activeId!);
    expect(saved?.messages[1].asks?.[0].status).toBe('interrupted'); // 中断状态已持久化
  });

  it('重复 wait-user 事件就地更新：不重复建卡、不覆盖已填草稿；轮次结束时收尾', async () => {
    let emitWaiting!: () => void;
    let finish!: () => void;
    const gate = new Promise<void>((r) => (finish = r));
    const service: ChatService = {
      kind: 'real',
      run: async (request, emit) => {
        emit({ ...turn(request), type: 'wait-user', interaction: askCard('preview') });
        emitWaiting = () =>
          emit({ ...turn(request), type: 'wait-user', interaction: askCard('waiting') });
        await gate;
      },
    };
    const store = createChatStore({
      repository: createMemoryChatRepository(),
      services: { real: service },
    });
    await store.getState().init();
    const run = store.getState().send('问题', { id: 'p', modelLabel: '测试' });
    // 预览阶段：卡片已建但未开放作答
    await vi.waitFor(() =>
      expect(store.getState().messages[1].asks?.[0]?.status).toBe('preview'),
    );
    expect(store.getState().waitingInteractionId).toBeNull(); // preview 不开放提交
    // 同一 interactionId 的第二次事件（preview→waiting）：就地更新并开放作答
    emitWaiting();
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('ask-1'));
    store.getState().setAskDraft('ask-1', 'q1', { labels: ['A'], freeText: '' });
    const asks = store.getState().messages[1].asks;
    expect(asks).toHaveLength(1); // 不重复建卡
    expect(asks?.[0].status).toBe('waiting');
    expect(asks?.[0].drafts.q1).toEqual({ labels: ['A'], freeText: '' }); // 不覆盖草稿
    finish(); // 结束本轮（无 end 事件）：断流收尾 + 追问收尾
    await run;
    const message = store.getState().messages[1];
    expect(message.status).toBe('stopped');
    expect(message.asks?.[0].status).toBe('interrupted');
    expect(store.getState().waitingInteractionId).toBeNull();
  });
});

describe('守卫与恢复', () => {
  it('终态后迟到的 wait-user 被拒绝，不建卡', async () => {
      const service: ChatService = {
      kind: 'real',
      run: async (request, emit) => {
        emit({ ...turn(request), type: 'end', finishReason: 'stop' });
        emit({ ...turn(request), type: 'wait-user', interaction: askCard('waiting') });
      },
    };
    const store = createChatStore({ repository: createMemoryChatRepository(), services: { real: service } });
    await store.getState().init();
    await store.getState().send('问题', { id: 'p', modelLabel: '测试' });
    expect(store.getState().messages[1].asks).toBeUndefined();
    expect(store.getState().waitingInteractionId).toBeNull();
  });

  it('刷新恢复：未完成等待标记中断、不可提交；草稿与问题保留；旧历史兼容', async () => {
    const repo = createMemoryChatRepository();
    await repo.save({
      id: 'hist',
      title: '中断追问',
      createdAt: '2026-09-07',
      updatedAt: '2026-09-07',
      messages: [
        { id: 'u', role: 'user', content: '问题', status: 'done' },
        {
          id: 'a',
          role: 'assistant',
          content: '前半',
          status: 'streaming',
          asks: [
            {
              ...askCard('waiting'),
              drafts: { q1: { labels: ['A'], freeText: '草稿文本' } },
            },
          ],
        },
        // 旧历史：纯 content 消息兼容
        { id: 'old', role: 'assistant', content: '旧回答', status: 'done' },
      ],
    } as never);
    const store = createChatStore({ repository: repo, services: { real: { kind: 'real', run: async () => undefined } } });
    await store.getState().init();
    const message = store.getState().messages[1];
    expect(message.asks?.[0].status).toBe('interrupted');
    expect(message.asks?.[0].drafts.q1).toEqual({ labels: ['A'], freeText: '草稿文本' });
    expect(store.getState().waitingInteractionId).toBeNull();
    expect(store.getState().messages[2].content).toBe('旧回答'); // 旧历史兼容
    // 不可向失效旧卡提交
    expect(
      await store.getState().submitReply([{ questionId: 'q1', labels: ['A'], freeText: '' }]),
    ).toBe(false);
    expect(message.asks?.[0].status).toBe('interrupted');
  });

  it('提交进行中取消：卡片明确失败（WAIT_CANCELLED），轮次照常收尾', async () => {
    let replyStarted!: () => void;
    const service: ChatService = {
      kind: 'real',
      run: async (request, emit) => {
        emit({ ...turn(request), type: 'wait-user', interaction: askCard('waiting') });
        await new Promise<void>((_, reject) => {
          request.signal.addEventListener(
            'abort',
            () => reject(new DOMException('aborted', 'AbortError')),
            { once: true },
          );
        });
      },
      submitReply: async (request) => {
        await new Promise<void>((resolve) => {
          replyStarted = resolve;
          request.signal.addEventListener('abort', () => resolve(), { once: true });
        });
        if (request.signal.aborted) throw new DOMException('aborted', 'AbortError');
        return { accepted: true };
      },
    };
    const store = createChatStore({ repository: createMemoryChatRepository(), services: { real: service } });
    await store.getState().init();
    const run = store.getState().send('问题', { id: 'p', modelLabel: '测试' });
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('ask-1'));
    const submitting = store.getState().submitReply([
      { questionId: 'q1', labels: ['A'], freeText: '' },
    ]);
    await vi.waitFor(() => expect(replyStarted).toBeTruthy());
    store.getState().stop(); // 提交进行中取消
    await expect(submitting).resolves.toBe(false);
    await run;
    const card = store.getState().messages[1].asks?.[0];
    // R11 语义：中止后的迟到结果不归提交所有——卡片保持停止时的中断状态
    expect(card?.status).toBe('interrupted');
    expect(store.getState().messages[1].status).toBe('stopped');
  });

  it('真实服务未发出追问时提交被拒，且不静默转模拟', async () => {
    const mockRun = vi.fn(async () => undefined);
    const real = createRealChatService({
      stream: async (_input, handlers) => {
        handlers.onEnd?.('stop');
      },
    });
    const store = createChatStore({
      repository: createMemoryChatRepository(),
      services: {
        real,
        mock: {
          kind: 'mock',
          armFailure: vi.fn(),
          armAskUser: vi.fn(),
          armReplyFailure: vi.fn(),
          run: mockRun,
        },
      },
    });
    await store.getState().init();
    await store.getState().send('问题', { id: 'p', modelLabel: '测试' });
    // 无有效等待上下文：提交直接拒绝，绝不调用模拟服务代替
    expect(
      await store.getState().submitReply([{ questionId: 'q', labels: [], freeText: '' }]),
    ).toBe(false);
    expect(mockRun).not.toHaveBeenCalled();
  });

  it('真实服务显式不支持追问回答：卡片明确失败（REPLY_NOT_SUPPORTED）', async () => {
      let finish!: () => void;
    const gate = new Promise<void>((r) => (finish = r));
    const service: ChatService = {
      kind: 'real',
      run: async (request, emit) => {
        emit({ ...turn(request), type: 'wait-user', interaction: askCard('waiting') });
        await gate;
      },
    };
    const store = createChatStore({
      repository: createMemoryChatRepository(),
      services: { real: service },
    });
    await store.getState().init();
    const run = store.getState().send('问题', { id: 'p', modelLabel: '测试' });
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('ask-1'));
    // 真实服务含显式拒绝实现（submitReply 返回 accepted:false）
    const real = createRealChatService({ stream: async () => undefined });
    expect(
      (
        await real.submitReply!({
          sessionId: 's',
          turnId: 't',
          interactionId: 'x',
          submissionId: 'sub',
          answers: [],
          signal: new AbortController().signal,
        })
      ).code,
    ).toBe('REPLY_NOT_SUPPORTED');
    // 无 submitReply 的服务接入时：卡片明确失败，不静默换服务
    let finish2!: () => void;
    const gate2 = new Promise<void>((r) => (finish2 = r));
    const plainStore = createChatStore({
      repository: createMemoryChatRepository(),
      services: {
        real: {
          kind: 'real',
          run: async (request, emit) => {
            emit({ ...turn(request), type: 'wait-user', interaction: askCard('waiting') });
            await gate2;
          },
        },
      },
    });
    await plainStore.getState().init();
    const run2 = plainStore.getState().send('问题', { id: 'p', modelLabel: '测试' });
    await vi.waitFor(() => expect(plainStore.getState().waitingInteractionId).toBe('ask-1'));
    expect(
      await plainStore.getState().submitReply([
        { questionId: 'q1', labels: ['A'], freeText: '' },
      ]),
    ).toBe(false);
    expect(plainStore.getState().messages[1].asks?.[0].status).toBe('failed');
    expect(plainStore.getState().messages[1].asks?.[0].error?.code).toBe(
      'REPLY_NOT_SUPPORTED',
    );
    finish();
    finish2();
    await run;
    await run2;
  });
});

describe('审查 R11–R16 回归（探针场景迁移）', () => {
  function deferred<T>() {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((r) => {
      resolve = r;
    });
    return { promise, resolve };
  }
  const profile = { id: 'review', modelLabel: 'injected service' };
  function reviewCard(id = 'ask-1', status: AskUserInteraction['status'] = 'waiting'): AskUserInteraction {
    return {
      interactionId: id,
      status,
      intro: '澄清',
      questions: [
        {
          questionId: 'q1',
          prompt: '选择风格',
          options: [{ label: '选项A' }],
          multiSelect: false,
          allowFreeText: true,
        },
      ],
      drafts: {},
    };
  }
  async function harness(submitReply?: ChatService['submitReply']) {
    const runs: {
      request: ChatServiceRequest;
      emit: (event: ChatServiceEvent) => void;
      done: ReturnType<typeof deferred<void>>;
    }[] = [];    const service: ChatService = {
      kind: 'real',
      submitReply,
      run: async (request, emit) => {
        const done = deferred<void>();
        runs.push({ request, emit, done });
        await done.promise;
      },
    };
    const store = createChatStore({
      repository: createMemoryChatRepository(),
      services: { real: service },
    });
    await store.getState().init();
    function wait(index: number, interaction: AskUserInteraction) {
      const { request, emit } = runs[index]!;
      emit({
        type: 'wait-user',
        sessionId: request.sessionId,
        turnId: request.turnId,
        interaction,
      });
    }
    return { store, runs, wait };
  }

  it('R11：停止后迟到的 accepted 确认不得改写 interrupted 历史，提交返回 false', async () => {
    const ack = deferred<{ accepted: boolean }>();
    const h = await harness(() => ack.promise);
    const run = h.store.getState().send('问题', profile);
    await vi.waitFor(() => expect(h.runs).toHaveLength(1));
    h.wait(0, reviewCard());
    const reply = h.store.getState().submitReply([
      { questionId: 'q1', labels: ['选项A'], freeText: '' },
    ]);
    h.store.getState().stop();
    expect(h.store.getState().messages[1].asks?.[0].status).toBe('interrupted');
    ack.resolve({ accepted: true });
    expect(await reply).toBe(false); // 迟到确认不返回成功
    expect(h.store.getState().messages[1].asks?.[0].status).toBe('interrupted');
    h.runs[0]!.done.resolve();
    await run;
    h.store.getState().dispose();
  });

  it('R11：旧轮收尾不清空新轮的等待身份', async () => {
    const h = await harness();
    const oldRun = h.store.getState().send('旧问题', profile);
    await vi.waitFor(() => expect(h.runs).toHaveLength(1));
    h.store.getState().stop();
    const newRun = h.store.getState().send('新问题', profile);
    await vi.waitFor(() => expect(h.runs).toHaveLength(2));
    h.wait(1, reviewCard('new-ask'));
    expect(h.store.getState().waitingInteractionId).toBe('new-ask');
    h.runs[0]!.done.resolve();
    await oldRun;
    expect(h.store.getState().waitingInteractionId).toBe('new-ask'); // 旧 finally 不清新身份
    h.store.getState().stop();
    h.runs[1]!.done.resolve();
    await newRun;
    h.store.getState().dispose();
  });

  it('R13：非空预览按稳定 id 被完整 waiting 补全，草稿保留', async () => {
    const h = await harness();
    const run = h.store.getState().send('问题', profile);
    await vi.waitFor(() => expect(h.runs).toHaveLength(1));
    h.wait(0, {
      ...reviewCard('ask-1', 'preview'),
      intro: '半句',
      questions: [{ questionId: 'q1', prompt: '未完成', options: [] }],
    });
    h.store.getState().setAskDraft('ask-1', 'q1', { labels: ['选项A'], freeText: '草稿' });
    h.wait(0, {
      ...reviewCard('ask-1', 'waiting'),
      intro: '完整引言',
      questions: [...reviewCard('ask-1').questions, { questionId: 'q2', prompt: '第二题' }],
    });
    const card = h.store.getState().messages[1].asks?.[0];
    h.store.getState().stop();
    h.runs[0]!.done.resolve();
    await run;
    h.store.getState().dispose();
    expect(card?.questions).toHaveLength(2); // 权威更新
    expect(card?.intro).toBe('完整引言');
    expect(card?.questions[0].prompt).toBe('选择风格');
    expect(card?.drafts.q1).toEqual({ labels: ['选项A'], freeText: '草稿' }); // 草稿保留
  });

  it('R14：已答卡的重复 waiting 抢不走后续活动卡', async () => {
    const h = await harness(async () => ({ accepted: true }));
    const run = h.store.getState().send('问题', profile);
    await vi.waitFor(() => expect(h.runs).toHaveLength(1));
    h.wait(0, reviewCard('first'));
    expect(
      await h.store.getState().submitReply([{ questionId: 'q1', labels: ['选项A'], freeText: '' }]),
    ).toBe(true);
    h.wait(0, reviewCard('second'));
    h.wait(0, reviewCard('first')); // 迟到重复事件
    expect(h.store.getState().waitingInteractionId).toBe('second'); // 不被抢走
    h.store.getState().stop();
    h.runs[0]!.done.resolve();
    await run;
    h.store.getState().dispose();
  });

  it('R12：下一轮请求上下文包含已确认追问交流与可见续答', () => {
    const messages = [
      { id: 'u', role: 'user' as const, content: '帮我讲解', status: 'done' as const },
      {
        id: 'a',
        role: 'assistant' as const,
        content: '先确认偏好',
        status: 'done' as const,
        asks: [
          {
            ...reviewCard('ask', 'answered'),
            answers: [{ questionId: 'q1', labels: [], freeText: '使用小学例子' }],
            followUp: '据此给出的最终解释',
          },
        ],
      },
      { id: 'u2', role: 'user' as const, content: '展开刚才的例子', status: 'done' as const },
    ];
    const text = selectMessagesForRequest(messages, 10000)
      .map((m) => m.content)
      .join('\n');
    expect(text).toContain('使用小学例子'); // 已确认回答进入上下文
    expect(text).toContain('据此给出的最终解释'); // 续答进入上下文
  });

  it('R12：复制投影包含已确认回答与续答；未提交草稿不进入投影', () => {
    const message = {
      id: 'a',
      role: 'assistant' as const,
      content: '先确认偏好',
      status: 'done' as const,
      asks: [
        {
          ...reviewCard('ask', 'answered'),
          drafts: { q1: { labels: [], freeText: '未提交草稿' } },
          answers: [{ questionId: 'q1', labels: ['选项A'], freeText: '' }],
          followUp: '据此给出的最终解释',
        },
      ],
    };
    const projection = conversationProjection(message);
    expect(projection).toContain('先确认偏好');
    expect(projection).toContain('选项A'); // 已确认回答
    expect(projection).toContain('据此给出的最终解释'); // 同轮续写
    expect(projection).not.toContain('未提交草稿'); // 草稿不冒充已提交
  });

  it('R12：重试保留仅有追问的失败尝试及其草稿', async () => {
    const h = await harness();
    const firstRun = h.store.getState().send('问题', profile);
    await vi.waitFor(() => expect(h.runs).toHaveLength(1));
    h.wait(0, reviewCard());
    h.store.getState().setAskDraft('ask-1', 'q1', {
      labels: [],
      freeText: '尚未提交的草稿',
    });
    const originalId = h.store.getState().messages[1].id;
    h.store.getState().stop();
    h.runs[0]!.done.resolve();
    await firstRun;
    const retryRun = h.store.getState().retry(originalId, profile);
    await vi.waitFor(() => expect(h.runs).toHaveLength(2));
    const preserved = h.store.getState().messages.find((m) => m.id === originalId);
    h.store.getState().stop();
    h.runs[1]!.done.resolve();
    await retryRun;
    h.store.getState().dispose();
    expect(preserved?.asks?.[0].drafts.q1?.freeText).toBe('尚未提交的草稿');
    expect(preserved?.superseded).toBe(true);
  });

  it('R13 补充：waiting 后的过期 preview 不覆盖完整题目/选项/引言', async () => {
    let emitStalePreview!: () => void;
    let finish!: () => void;
    const gate = new Promise<void>((r) => (finish = r));
    const waiting: AskUserInteraction = {
      interactionId: 'ask',
      status: 'waiting',
      intro: '完整引言',
      drafts: {},
      questions: [
        { questionId: 'q1', prompt: '完整第一题', options: [{ label: 'A' }] },
        { questionId: 'q2', prompt: '完整第二题', options: [{ label: 'B' }] },
      ],
    };
    const service: ChatService = {
      kind: 'real',
      run: async (request, emit) => {
        const t = { sessionId: request.sessionId, turnId: request.turnId };
        emit({ ...t, type: 'wait-user', interaction: waiting });
        emitStalePreview = () =>
          emit({
            ...t,
            type: 'wait-user',
            interaction: {
              ...waiting,
              status: 'preview',
              intro: '半句',
              questions: [{ questionId: 'q1', prompt: '半题', options: [] }],
            },
          });
        await gate;
      },
    };
    const store = createChatStore({
      repository: createMemoryChatRepository(),
      services: { real: service },
    });
    await store.getState().init();
    const run = store.getState().send('问题', profile);
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('ask'));
    store.getState().setAskDraft('ask', 'q2', { labels: ['B'], freeText: '' });
    emitStalePreview();
    const card = store.getState().messages[1].asks?.[0];
    store.getState().stop();
    finish();
    await run;
    store.getState().dispose();
    expect(card?.status).toBe('waiting'); // 不降级
    expect(card?.questions).toEqual(waiting.questions); // 完整题目不回退
    expect(card?.intro).toBe('完整引言');
    expect(card?.drafts.q2?.labels).toEqual(['B']);
  });

  it.each(['error', 'disconnect'] as const)(
    'R11 补充：%s 后迟到的 accepted 确认不得重开中断卡',
    async (reason) => {
      let emitError!: () => void;
      const ack = deferred<{ accepted: boolean }>();
      let finish!: () => void;
      const gate = new Promise<void>((r) => (finish = r));
      const service: ChatService = {
        kind: 'real',
        run: async (request, emit) => {
          const t = { sessionId: request.sessionId, turnId: request.turnId };
          emit({ ...t, type: 'wait-user', interaction: reviewCard() });
          emitError = () => {
            if (reason === 'error')
              emit({
                ...t,
                type: 'error',
                error: { code: 'REVIEW_FAILURE', message: 'No acceptance before failure' },
              });
          };
          await gate;
        },
        submitReply: () => ack.promise,
      };
      const store = createChatStore({
        repository: createMemoryChatRepository(),
        services: { real: service },
      });
      await store.getState().init();
      const run = store.getState().send('问题', profile);
      await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('ask-1'));
      const reply = store.getState().submitReply([
        { questionId: 'q1', labels: ['选项A'], freeText: '' },
      ]);
      if (reason === 'error') emitError();
      finish(); // error 场景 run 仍挂起：直接结束（断流语义由 error/finish 组合覆盖）
      await run;
      expect(store.getState().messages[1].asks?.[0].status).toBe('interrupted');
      ack.resolve({ accepted: true });
      expect(await reply).toBe(false); // 迟到确认不重开中断卡
      expect(store.getState().messages[1].asks?.[0].status).toBe('interrupted');
      store.getState().dispose();
    },
  );

  // 交付复核（2026-09-07）终态顺序探针迁移：业务终态与 run Promise 生命周期区分
  it('终态顺序：error 已到达但 run 仍挂起时，迟到 accepted ACK 被拒绝', async () => {
    const streamDone = deferred<void>();
    const ack = deferred<{ accepted: boolean }>();
    let finish!: (type: 'error' | 'end') => void;
    const service: ChatService = {
      kind: 'real',
      submitReply: () => ack.promise,
      run: async (request, emit) => {
        const t = { sessionId: request.sessionId, turnId: request.turnId };
        finish = (type) =>
          emit(
            type === 'end'
              ? { ...t, type, finishReason: 'stop' }
              : { ...t, type, error: { code: 'REVIEW', message: 'Synthetic failure, no provider calls' } },
          );
        emit({ ...t, type: 'wait-user', interaction: reviewCard() });
        await streamDone.promise;
      },
    };
    const store = createChatStore({ repository: createMemoryChatRepository(), services: { real: service } });
    await store.getState().init();
    const run = store.getState().send('问题', profile);
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('ask-1'));
    const reply = store.getState().submitReply([
      { questionId: 'q1', labels: ['选项A'], freeText: '' },
    ]);
    finish('error'); // error 事件先到：卡中断、等待失效，但 run Promise 仍未返回
    expect(store.getState().messages[1].asks?.[0].status).toBe('interrupted');
    ack.resolve({ accepted: true });
    expect(await reply).toBe(false); // 迟到 ACK 不得接受
    expect(store.getState().messages[1].asks?.[0].status).toBe('interrupted');
    streamDone.resolve();
    await run;
    store.getState().dispose();
  });

  it('终态顺序：正常 end 后 run 返回，合法 accepted ACK 仍被接受且保留答案', async () => {
    const streamDone = deferred<void>();
    const ack = deferred<{ accepted: boolean }>();
    let finish!: (type: 'error' | 'end') => void;
    const service: ChatService = {
      kind: 'real',
      submitReply: () => ack.promise,
      run: async (request, emit) => {
        const t = { sessionId: request.sessionId, turnId: request.turnId };
        finish = (type) =>
          emit(
            type === 'end'
              ? { ...t, type, finishReason: 'stop' }
              : { ...t, type, error: { code: 'REVIEW', message: 'Synthetic failure, no provider calls' } },
          );
        emit({ ...t, type: 'wait-user', interaction: reviewCard() });
        await streamDone.promise;
      },
    };
    const store = createChatStore({ repository: createMemoryChatRepository(), services: { real: service } });
    await store.getState().init();
    const run = store.getState().send('问题', profile);
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('ask-1'));
    const reply = store.getState().submitReply([
      { questionId: 'q1', labels: ['选项A'], freeText: '' },
    ]);
    finish('end'); // 正常 end：通用断流兜底不得把 endReason 改写成 disconnect
    streamDone.resolve();
    await run;
    expect(store.getState().messages[1].status).toBe('done');
    ack.resolve({ accepted: true });
    expect(await reply).toBe(true); // 合法同步续答的迟到确认被接受
    const card = store.getState().messages[1].asks?.[0];
    expect(card?.status).toBe('answered'); // 答案保留，不被拒收为中断
    expect(card?.answers?.[0].labels).toEqual(['选项A']);
    store.getState().dispose();
  });
});
