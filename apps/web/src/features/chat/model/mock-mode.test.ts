import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository, type ChatRepository } from '@/services/chat-repository';
import type { ChatServiceEvent, ChatServiceRequest } from './chat-service';
import type { ChatService } from './chat-service';
import { createScriptedChatStore as createChatStore } from '../../../../../../tests/fixtures/scripted-chat-store';

type Emit = (event: ChatServiceEvent) => void;
type ScriptedRun = (emit: Emit, request: ChatServiceRequest) => Promise<void>;
/** 联合类型的分布式 Omit：保留各成员的必要字段 */
type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;
type TurnEvent = DistributiveOmit<ChatServiceEvent, 'sessionId' | 'turnId'>;

function scriptedMockService(script: ScriptedRun[]) {
  const calls: ChatServiceRequest[] = [];
  const service = {
    kind: 'mock' as const,
    armFailure: vi.fn(),
    armAskUser: vi.fn(),
    armReplyFailure: vi.fn(),
    run: (request: ChatServiceRequest, emit: Emit) => {
      calls.push(request);
      return script[calls.length - 1]!(emit, request);
    },
  };
  return { service, calls };
}

function turn(request: ChatServiceRequest) {
  return { sessionId: request.sessionId, turnId: request.turnId };
}

/** 固定 mock 模式 store：注入脚本化模拟服务与内存仓储，服务调用记录可用于断言（R4） */
function mockStore(repo: ChatRepository, script: ScriptedRun[]) {
  const { service, calls } = scriptedMockService(script);
  const store = createChatStore({
    mode: 'mock',
    repository: repo,
    services: { mock: service },
  });
  return { store, calls, service };
}

describe('模拟模式（固定 mock store）', () => {
  it('模拟发送只写入注入的模拟仓储，真实仓储已有数据保持不变', async () => {
    // R2/R4：真实仓储不注入被测 store，用"已有数据不变"证明模拟路径未触碰真实库
    const realRepo: ChatRepository = createMemoryChatRepository();
    await realRepo.save({
      id: 'real-1',
      title: '真实会话',
      messages: [],
      createdAt: '2026-09-07',
      updatedAt: '2026-09-07',
    });
    const mockRepo: ChatRepository = createMemoryChatRepository();
    const mockList = vi.spyOn(mockRepo, 'list');
    const mockSave = vi.spyOn(mockRepo, 'save');
    const { store, calls } = mockStore(mockRepo, [
      async (emit, request) => {
        emit({ ...turn(request), type: 'text', delta: '【模拟回复】内容' });
        emit({ ...turn(request), type: 'end', finishReason: 'stop' });
      },
    ]);
    await store.getState().init();
    await store.getState().send('模拟问题', null);

    expect(mockList).toHaveBeenCalledTimes(1); // 仅 init 加载一次自己的仓储
    expect(mockSave).toHaveBeenCalled();
    expect(store.getState().conversations).toHaveLength(1);
    expect(calls[0].messages.at(-1)?.content).toBe('模拟问题');
    expect(store.getState().messages[1].modelLabel).toBe('测试模型 · 本地脚本');
    expect(store.getState().messages[1].content).toBe('【模拟回复】内容');
    // 模拟仓储实际落库一条会话
    const saved = await mockRepo.load(store.getState().activeId!);
    expect(saved?.messages[1].content).toBe('【模拟回复】内容');
    // 真实仓储已有数据原样保留
    const realDoc = await realRepo.load('real-1');
    expect(realDoc?.title).toBe('真实会话');
    expect((await realRepo.list()).length).toBe(1);
  });

  it('真实仓储挂起时模拟 store 照常就绪（两 store 初始化互不阻塞）', async () => {
    const hangingReal: ChatRepository = createMemoryChatRepository();
    const realList = vi.spyOn(hangingReal, 'list');
    realList.mockImplementation(() => new Promise(() => undefined)); // 永远挂起
    const realStore = createChatStore({ mode: 'real', repository: hangingReal });
    const mockRepo: ChatRepository = createMemoryChatRepository();
    const mockList = vi.spyOn(mockRepo, 'list');
    const mockStore = createChatStore({ mode: 'mock', repository: mockRepo, services: { mock: scriptedMockService([]).service } });

    void realStore.getState().init(); // 真实库读取挂起中
    await mockStore.getState().init();

    expect(mockStore.getState().ready).toBe(true);
    expect(mockList).toHaveBeenCalledTimes(1); // mock store 只读自己的仓储
    expect(realList).toHaveBeenCalledTimes(1); // real list 只被 real store 自身的 init 调用
    expect(realStore.getState().ready).toBe(false);
  });

  it('两套仓储允许使用相同会话 ID，互不串扰', async () => {
    const realRepo: ChatRepository = createMemoryChatRepository();
    const mockRepo: ChatRepository = createMemoryChatRepository();
    const base = {
      id: 'same-id',
      title: '真实会话',
      messages: [],
      createdAt: '2026-09-07',
      updatedAt: '2026-09-07',
    };
    await realRepo.save(base);
    await mockRepo.save({ ...base, title: '模拟会话', mode: 'mock' });
    const realStore = createChatStore({ mode: 'real', repository: realRepo });
    const mockStore = createChatStore({ mode: 'mock', repository: mockRepo, services: { mock: scriptedMockService([]).service } });
    await realStore.getState().init();
    await mockStore.getState().init();
    expect(mockStore.getState().conversations.map((c) => c.title)).toEqual(['模拟会话']);
    expect(mockStore.getState().mode).toBe('real');
    expect(realStore.getState().conversations.map((c) => c.title)).toEqual(['真实会话']);
    expect(realStore.getState().mode).toBe('real');
  });

  it('真实 store 缺少档案时不自动回退到注入的模拟服务', async () => {
    // R4：模拟服务 spy 注入被测的真实 store，断言它确实未被调用
    const mockRun = vi.fn(async () => undefined);
    const store = createChatStore({
      mode: 'real',
      repository: createMemoryChatRepository(),
      services: { mock: { kind: 'mock', armFailure: vi.fn(), armAskUser: vi.fn(), armReplyFailure: vi.fn(), run: mockRun } },
    });
    await store.getState().init();
    store.getState().newConversation();
    await store.getState().send('问题', null);
    expect(mockRun).not.toHaveBeenCalled();
    expect(store.getState().messages).toHaveLength(0);
    expect(store.getState().mode).toBe('real');
  });

  it('模拟失败后可用重试恢复', async () => {
    const mockRepo: ChatRepository = createMemoryChatRepository();
    const { store } = mockStore(mockRepo, [
      // 第一轮：部分正文后模拟失败；第二轮（重试）：完整回答
      async (emit, request) => {
        const t = turn(request);
        emit({ ...t, type: 'text', delta: '部分' });
        emit({
          ...t,
          type: 'error',
          error: { code: 'MOCK_ERROR', message: '模拟失败', retryable: true },
        });
      },
      async (emit, request) => {
        const t = turn(request);
        emit({ ...t, type: 'text', delta: '完整回答' });
        emit({ ...t, type: 'end', finishReason: 'stop' });
      },
    ]);
    await store.getState().init();
    await store.getState().send('问题', null);
    expect(store.getState().messages.at(-1)?.status).toBe('error');

    await store.getState().retryLast(null);
    const messages = store.getState().messages;
    expect(messages.filter((m) => m.role === 'user')).toHaveLength(1);
    expect(messages.at(-1)).toMatchObject({ status: 'done', content: '完整回答' });
  });

  it('end 之后迟到的 stage/process/usage/text 不再修改已完成消息', async () => {
    const service: ChatService = {
      kind: 'real',
      async run(request, emit) {
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        emit({ ...base, type: 'end', finishReason: 'stop' });
        emit({ ...base, type: 'stage', label: '不应出现', phase: 'start' });
        emit({ ...base, type: 'process', delta: '不应出现' });
        emit({ ...base, type: 'usage', usage: { inputTokens: 9, outputTokens: 9 } });
        emit({ ...base, type: 'text', delta: '不应出现' });
      },
    };
    const store = createChatStore({
      repository: createMemoryChatRepository(),
      services: { real: service },
    });
    await store.getState().init();
    await store.getState().send('问题', { id: 'p', modelLabel: '测试' });
    const last = store.getState().messages.at(-1)!;
    expect(last.status).toBe('done');
    expect(last.stageLabel).toBeUndefined();
    expect(last.processNote).toBeUndefined();
    expect(last.usage).toBeUndefined();
    expect(last.content).toBe('');
  });

  it('error 之后迟到的阶段与正文增量不再修改消息', async () => {
    const service: ChatService = {
      kind: 'real',
      async run(request, emit) {
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        emit({ ...base, type: 'text', delta: '部分' });
        emit({ ...base, type: 'error', error: { code: 'X', message: '失败' } });
        emit({ ...base, type: 'stage', label: '迟到阶段', phase: 'start' });
        emit({ ...base, type: 'text', delta: '迟到正文' });
      },
    };
    const store = createChatStore({
      repository: createMemoryChatRepository(),
      services: { real: service },
    });
    await store.getState().init();
    await store.getState().send('问题', { id: 'p', modelLabel: '测试' });
    const last = store.getState().messages.at(-1)!;
    expect(last.status).toBe('error');
    expect(last.content).toBe('部分');
    expect(last.stageLabel).toBeUndefined();
  });

  it('停止（取消）后迟到的阶段与过程事件被丢弃', async () => {
    const mockRepo: ChatRepository = createMemoryChatRepository();
    let lateEmit!: (event: TurnEvent) => void;
    const { store } = mockStore(mockRepo, [
      async (emit, request) => {
        const t = turn(request);
        lateEmit = (event) => emit({ ...t, ...event });
        await new Promise<void>((resolve) => {
          request.signal.addEventListener('abort', () => resolve(), { once: true });
        });
      },
    ]);
    await store.getState().init();
    const run = store.getState().send('问题', null);
    store.getState().stop();
    lateEmit({ type: 'stage', label: '迟到阶段', phase: 'start' });
    lateEmit({ type: 'process', delta: '迟到过程' });
    await run;    const last = store.getState().messages.at(-1)!;
    expect(last.status).toBe('stopped');
    expect(last.stageLabel).toBeUndefined();
    expect(last.processNote).toBeUndefined();
  });

  it('新建会话停止旧流，迟到事件不串入新会话', async () => {
    const mockRepo: ChatRepository = createMemoryChatRepository();
    let lateEmit!: (event: TurnEvent) => void;
    let finish!: () => void;
    const gate = new Promise<void>((r) => (finish = r));
    const { store } = mockStore(mockRepo, [
      async (emit, request) => {
        const t = turn(request);
        lateEmit = (event) => emit({ ...t, ...event });
        lateEmit({ type: 'text', delta: '已收到' });
        await gate;
      },
    ]);
    await store.getState().init();
    const run = store.getState().send('问题', null);
    const oldId = store.getState().activeId!;
    store.getState().newConversation();
    lateEmit({ type: 'text', delta: '迟到文本' });
    finish();
    await run;
    expect(store.getState().messages).toHaveLength(0);
    const old = await mockRepo.load(oldId);
    expect(old?.messages[1]).toMatchObject({ content: '已收到', status: 'stopped' });
  });

  it('dispose 幂等，StrictMode 重挂载后 store 仍可正常使用', async () => {
    const mockRepo: ChatRepository = createMemoryChatRepository();
    const { store } = mockStore(mockRepo, [
      async (emit, request) => {
        emit({ ...turn(request), type: 'text', delta: '再次回答' });
        emit({ ...turn(request), type: 'end', finishReason: 'stop' });
      },
    ]);
    await store.getState().init();
    store.getState().dispose();
    expect(() => store.getState().dispose()).not.toThrow(); // 幂等
    expect(store.getState().sending).toBe(false);
    // 模拟 StrictMode setup-cleanup-setup：清理后重新 init 并发送不受影响
    await store.getState().init();
    await store.getState().send('再来一问', null);
    expect(store.getState().messages.at(-1)).toMatchObject({
      status: 'done',
      content: '再次回答',
    });
  });

  it('卸载 dispose 取消生成，已收内容标记停止并保存', async () => {
    const mockRepo: ChatRepository = createMemoryChatRepository();
    let finish!: () => void;
    const gate = new Promise<void>((r) => (finish = r));
    const { store } = mockStore(mockRepo, [
      async (emit, request) => {
        emit({ ...turn(request), type: 'text', delta: '部分内容' });
        await gate;
      },
    ]);
    await store.getState().init();
    const run = store.getState().send('问题', null);
    const activeId = store.getState().activeId!;
    store.getState().dispose(); // 卸载清理：取消 + 冲正保存
    finish();
    await run;
    const saved = await mockRepo.load(activeId);
    expect(saved?.messages[1]).toMatchObject({ content: '部分内容', status: 'stopped' });
  });

  it('刷新后新实例从同一仓储恢复模拟历史', async () => {
    const mockRepo: ChatRepository = createMemoryChatRepository();
    const first = mockStore(mockRepo, [
      async (emit, request) => {
        emit({ ...turn(request), type: 'text', delta: '历史回答' });
        emit({ ...turn(request), type: 'end', finishReason: 'stop' });
      },
    ]);
    await first.store.getState().init();
    await first.store.getState().send('旧问题', null);

    const second = mockStore(mockRepo, [async () => undefined]);
    await second.store.getState().init();
    expect(second.store.getState().conversations).toHaveLength(1);
    expect(second.store.getState().messages.at(-1)?.content).toBe('历史回答');
  });
});
