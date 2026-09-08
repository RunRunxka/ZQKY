import { afterEach, describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository } from '@/services/chat-repository';
import { createChatStore } from './store';
import type { ChatStreamInput, ChatStreamHandlers } from '@/services/chat-stream';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

const PROFILE = {
  id: 'profile-1',
  modelLabel: '模拟模型 · sim-chat-1',
  contextTokens: 8000,
  maxOutputTokens: 512,
};

function makeStreamScript(
  script: Array<(input: ChatStreamInput, handlers: ChatStreamHandlers) => Promise<void>>,
) {
  const calls: Omit<ChatStreamInput, 'signal'>[] = [];
  const stream = vi.fn((input: ChatStreamInput, handlers: ChatStreamHandlers) => {
    calls.push({
      requestId: input.requestId,
      modelProfileId: input.modelProfileId,
      messages: input.messages,
      ...(input.maxOutputTokens !== undefined ? { maxOutputTokens: input.maxOutputTokens } : {}),
      ...(input.params ? { params: input.params } : {}),
    });
    return script[calls.length - 1]!(input, handlers);
  });
  return { stream, calls };
}

describe('chat store', () => {
  afterEach(() => vi.restoreAllMocks());

  it('S5-A：已归档会话不出现在侧栏列表，仍可按 id 选择', async () => {
    const repository = createMemoryChatRepository();
    await repository.save({
      id: 'archived-1',
      title: '已归档会话',
      messages: [
        { id: 'm1', role: 'user', content: '历史问题', status: 'done' },
      ],
      createdAt: '2026-09-08T08:00:00.000Z',
      updatedAt: '2026-09-08T08:00:00.000Z',
      archived: true,
    });
    await repository.save({
      id: 'live-1',
      title: '普通会话',
      messages: [],
      createdAt: '2026-09-08T09:00:00.000Z',
      updatedAt: '2026-09-08T09:00:00.000Z',
    });
    const { stream } = makeStreamScript([]);
    const store = createChatStore({ repository, stream });
    await store.getState().init();
    const ids = store.getState().conversations.map((c) => c.id);
    expect(ids).toEqual(['live-1']);
    // 默认活动会话不落在已归档会话上
    expect(store.getState().activeId).toBe('live-1');
    // 归档会话仍可显式载入（从 /space/chat-history 重新打开）
    await store.getState().selectConversation('archived-1');
    expect(store.getState().activeId).toBe('archived-1');
    expect(store.getState().messages[0]).toMatchObject({ content: '历史问题' });
  });

  it('初始化未完成时发送会等待完成而不是静默丢弃', async () => {    const repository = createMemoryChatRepository();
    const gate = deferred<void>();
    const slowRepo = {
      ...repository,
      list: async () => {
        await gate.promise;
        return repository.list();
      },
    };
    const { stream, calls } = makeStreamScript([
      async (_input, handlers) => {
        handlers.onText?.('回答');
        handlers.onEnd?.('stop');
      },
    ]);
    const store = createChatStore({ repository: slowRepo, stream });
    const pending = store.getState().send('早到的问题', PROFILE);
    gate.resolve();
    await pending;
    expect(calls).toHaveLength(1);
    const messages = store.getState().messages;
    expect(messages[0]).toMatchObject({ role: 'user', content: '早到的问题', status: 'done' });
    expect(messages[1]).toMatchObject({ role: 'assistant', content: '回答', status: 'done' });
  });

  it('发送后流式内容逐段追加并持久化，结束原因与用量写入消息', async () => {
    const repository = createMemoryChatRepository();
    const { stream } = makeStreamScript([
      async (_input, handlers) => {
        handlers.onStart?.({ requestId: 'r', messageId: 'm1', modelProfileId: PROFILE.id });
        handlers.onText?.('你好');
        handlers.onText?.('，世界');
        handlers.onUsage?.({ inputTokens: 5, outputTokens: 3 });
        handlers.onEnd?.('stop');
      },
    ]);
    const store = createChatStore({ repository, stream });
    await store.getState().init();
    store.getState().newConversation();
    await store.getState().send('打个招呼', PROFILE);

    const messages = store.getState().messages;
    expect(messages).toHaveLength(2);
    expect(messages[0]).toMatchObject({ role: 'user', content: '打个招呼', status: 'done' });
    expect(messages[1]).toMatchObject({
      role: 'assistant',
      content: '你好，世界',
      status: 'done',
      finishReason: 'stop',
      usage: { outputTokens: 3 },
      modelLabel: PROFILE.modelLabel,
    });
    const saved = await repository.load(store.getState().activeId!);
    expect(saved?.messages[1].content).toBe('你好，世界');
    expect((await repository.list())[0].title).toContain('打个招呼');
  });

  it('停止后保留部分内容并标记已停止，不再自动重发', async () => {
    const repository = createMemoryChatRepository();
    const { stream } = makeStreamScript([
      async (input, handlers) => {
        handlers.onText?.('部分内容');
        void input;
        throw new DOMException('aborted', 'AbortError');
      },
    ]);
    const store = createChatStore({ repository, stream });
    await store.getState().init();
    store.getState().newConversation();
    await store.getState().send('问题', PROFILE);

    const messages = store.getState().messages;
    expect(messages[1].status).toBe('stopped');
    expect(messages[1].content).toBe('部分内容');
    expect(stream).toHaveBeenCalledTimes(1); // 没有静默自动重试
  });

  it('上游失败时保留用户消息，重试不重复追加用户消息', async () => {
    const repository = createMemoryChatRepository();
    const { stream, calls } = makeStreamScript([
      async (_input, handlers) => {
        handlers.onError?.({ code: 'RATE_LIMITED', message: '上游限流', retryable: true });
      },
      async (_input, handlers) => {
        handlers.onText?.('重试成功');
        handlers.onEnd?.('stop');
      },
    ]);
    const store = createChatStore({ repository, stream });
    await store.getState().init();
    store.getState().newConversation();
    await store.getState().send('第一问', PROFILE);

    expect(store.getState().messages[1].status).toBe('error');
    expect(store.getState().messages[0].content).toBe('第一问'); // 已输入内容不丢

    await store.getState().retryLast(PROFILE);
    const messages = store.getState().messages;
    expect(messages.filter((message) => message.role === 'user')).toHaveLength(1); // 无重复发送
    expect(messages).toHaveLength(2);
    expect(messages[1].content).toBe('重试成功');
    expect(calls[1].messages.map((m) => m.content)).toEqual(['第一问']);
  });

  it('发送中禁止重复发送，直到流结束', async () => {
    const repository = createMemoryChatRepository();
    const gate = deferred<void>();
    const { stream } = makeStreamScript([
      async () => {
        await gate.promise;
      },
    ]);
    const store = createChatStore({ repository, stream });
    await store.getState().init();
    store.getState().newConversation();
    const first = store.getState().send('第一问', PROFILE);
    expect(store.getState().sending).toBe(true);
    await store.getState().send('第二问', PROFILE); // 应被忽略
    gate.resolve();
    await first;
    const calls = stream.mock.calls;
    expect(calls).toHaveLength(1);
  });

  it('切换会话后再返回，历史从仓储恢复；换模型不删除历史', async () => {
    const repository = createMemoryChatRepository();
    const { stream } = makeStreamScript([
      async (_input, handlers) => {
        handlers.onText?.('会话一的回答');
        handlers.onEnd?.('stop');
      },
    ]);
    const store = createChatStore({ repository, stream });
    await store.getState().init();
    store.getState().newConversation();
    const firstId = store.getState().activeId!;
    await store.getState().send('问题', PROFILE);

    store.getState().newConversation();
    expect(store.getState().activeId).not.toBe(firstId);
    await store.getState().selectConversation(firstId);
    const messages = store.getState().messages;
    expect(messages).toHaveLength(2); // 换模型/换会话后历史仍在
    expect(messages[1].modelLabel).toBe(PROFILE.modelLabel);
  });

  it('流异常中断且未收到 message.end 时如实标记为已停止', async () => {
    const repository = createMemoryChatRepository();
    const { stream } = makeStreamScript([
      async (_input, handlers) => {
        handlers.onText?.('收到一半');
        // 既没有 onEnd 也没有 onError，直接正常返回（模拟断流）
      },
    ]);
    const store = createChatStore({ repository, stream });
    await store.getState().init();
    store.getState().newConversation();
    await store.getState().send('问题', PROFILE);
    expect(store.getState().messages[1].status).toBe('stopped');
    expect(store.getState().messages[1].content).toBe('收到一半');
  });

  it('推理增量累积到消息的 reasoning 字段，不影响正文', async () => {
    const repository = createMemoryChatRepository();
    const { stream } = makeStreamScript([
      async (_input, handlers) => {
        handlers.onReasoning?.('思考');
        handlers.onReasoning?.('继续');
        handlers.onText?.('正文');
        handlers.onEnd?.('stop');
      },
    ]);
    const store = createChatStore({ repository, stream });
    await store.getState().init();
    store.getState().newConversation();
    await store.getState().send('问题', PROFILE);
    const messages = store.getState().messages;
    expect(messages[1].reasoning).toBe('思考继续');
    expect(messages[1].content).toBe('正文');
  });
});

describe('保存队列（交付复核 S3 回归：并发 flush 不得丢脏数据）', () => {
  it('保存进行中到达的新变更由后续 flush 串行落盘，不因防抖 timer 被取消而丢失', async () => {
    const base = createMemoryChatRepository();
    let releaseFirst!: () => void;
    const gate = new Promise<void>((r) => (releaseFirst = r));
    const saves: number[] = [];
    const repository = {
      list: base.list.bind(base),
      load: base.load.bind(base),
      remove: base.remove.bind(base),
      save: async (c: Parameters<typeof base.save>[0], expected?: number) => {
        const revision = await base.save(c, expected);
        saves.push(c.messages.length);
        return revision;
      },
    };
    // 首次保存挂起：模拟慢速 IDB 写入
    const slow = {
      ...repository,
      save: async (c: Parameters<typeof base.save>[0], expected?: number) => {
        if (!saves.length) {
          await gate;
          const revision = await repository.save(c, expected);
          return revision;
        }
        return repository.save(c, expected);
      },
    };
    const store = createChatStore({ repository: slow as never });
    await store.getState().init();
    store.getState().newConversation(); // change A：进入 dirty，flush 启动并卡在首保存
    const first = store.getState().flush();
    await new Promise((r) => setTimeout(r, 0)); // 让 run1 取到 A 的快照并挂起在慢保存上
    store.getState().setDraft('保存期间到达的草稿'); // change B：保存进行中到达
    const second = store.getState().flush(); // 并发 flush：必须串行排队处理 B，而非返回在途 Promise
    releaseFirst();
    expect(await first).toBe(true);
    expect(await second).toBe(true);
    // B 最终落盘：内存库中草稿已持久化
    const saved = await base.load(store.getState().activeId!);
    expect(saved?.draft).toBe('保存期间到达的草稿');
    expect(saves.length).toBeGreaterThanOrEqual(2);
    store.getState().dispose();
  });
});
