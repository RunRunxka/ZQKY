import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository, type ChatRepository } from '@/services/chat-repository';
import type {
  ChatServiceEvent,
  ChatServiceRequest,
  ChatToolCall,
} from './chat-service';
import type { TurnExtensionSnapshot } from '@/contracts/chat';
import { createScriptedChatStore as createChatStore } from '../../../../../../tests/fixtures/scripted-chat-store';

type Emit = (event: ChatServiceEvent) => void;
type ScriptedRun = (emit: Emit, request: ChatServiceRequest) => Promise<void>;

function turn(request: ChatServiceRequest) {
  return { sessionId: request.sessionId, turnId: request.turnId };
}

function scriptedService(script: ScriptedRun[]) {
  const requests: ChatServiceRequest[] = [];
  const service = {
    kind: 'mock' as const,
    armFailure: () => undefined,
    armAskUser: () => undefined,
    armReplyFailure: () => undefined,
    run: (request: ChatServiceRequest, emit: Emit) => {
      requests.push(request);
      return script[requests.length - 1]!(emit, request);
    },
  };
  return { service, requests };
}

function mockStore(repo: ChatRepository, script: ScriptedRun[]) {
  const { service, requests } = scriptedService(script);
  const store = createChatStore({ mode: 'mock', repository: repo, services: { mock: service } });
  return { store, requests };
}

const SNAPSHOT: TurnExtensionSnapshot = {
  mcps: [{ id: 'm1', name: '目录工具', description: '演示 MCP' }],
  skills: [{ id: 's1', name: '教学技能', description: '演示 Skill' }],
};

function tool(
  t: { sessionId: string; turnId: string },
  call: ChatToolCall,
): ChatServiceEvent {
  return { ...t, type: 'tool', call };
}

describe('扩展快照与重试', () => {
  it('发送时冻结快照：发送后修改源对象不影响消息与请求', async () => {
    const { store, requests } = mockStore(createMemoryChatRepository(), [
      async (emit, request) => {
        emit({ ...turn(request), type: 'end', finishReason: 'stop' });
      },
    ]);
    await store.getState().init();
    const source: TurnExtensionSnapshot = structuredClone(SNAPSHOT);
    await store.getState().send('问题', null, source);

    source.mcps[0]!.name = '发送后改名'; // 模拟目录在发送后变化
    source.skills = [];
    expect(requests[0].extensions?.mcps[0].name).toBe('目录工具');
    expect(requests[0].extensions?.skills).toHaveLength(1);
    const message = store.getState().messages[1];
    expect(message.extensions?.mcps[0].name).toBe('目录工具');
    expect(message.extensions?.skills).toHaveLength(1);
  });

  it('技能说明正文随快照一起冻结，不引用可变目录对象', async () => {
    const { store, requests } = mockStore(createMemoryChatRepository(), [
      async (emit, request) => {
        emit({ ...turn(request), type: 'end', finishReason: 'stop' });
      },
    ]);
    await store.getState().init();
    const source: TurnExtensionSnapshot = {
      mcps: [],
      skills: [{ id: 's1', name: '教案规范', description: '', content: '按七个栏目输出。' }],
    };
    await store.getState().send('问题', null, source);
    source.skills[0]!.content = '发送后改写的正文';
    expect(requests[0].extensions?.skills[0]?.content).toBe('按七个栏目输出。');
    expect(store.getState().messages[1].extensions?.skills[0]?.content).toBe('按七个栏目输出。');
  });

  it('无扩展时请求不带 extensions 字段，流程不变', async () => {
    const { store, requests } = mockStore(createMemoryChatRepository(), [
      async (emit, request) => {
        emit({ ...turn(request), type: 'text', delta: '【模拟回复】内容' });
        emit({ ...turn(request), type: 'end', finishReason: 'stop' });
      },
    ]);
    await store.getState().init();
    await store.getState().send('问题', null);
    expect('extensions' in requests[0]).toBe(false);
    expect(store.getState().messages[1].extensions).toBeUndefined();
    expect(store.getState().messages[1].content).toBe('【模拟回复】内容');
  });

  it('重试沿用原请求快照，不读取最新目录', async () => {
    const { store, requests } = mockStore(createMemoryChatRepository(), [
      async (emit, request) => {
        emit({
          ...turn(request),
          type: 'error',
          error: { code: 'MOCK_TOOL_ERROR', message: '模拟工具失败', retryable: true },
        });
      },
      async (emit, request) => {
        emit({ ...turn(request), type: 'end', finishReason: 'stop' });
      },
    ]);
    await store.getState().init();
    await store.getState().send('问题', null, structuredClone(SNAPSHOT));
    expect(store.getState().messages.at(-1)?.status).toBe('error');

    // “目录”此时已变化：重试仍应使用第一轮冻结的快照
    await store.getState().retryLast(null);
    expect(requests).toHaveLength(2);
    expect(requests[1].extensions?.mcps[0].name).toBe('目录工具');
    expect(requests[1].extensions?.skills[0].name).toBe('教学技能');
    expect(store.getState().messages.at(-1)?.extensions?.mcps[0].name).toBe('目录工具');
  });
});

describe('工具过程记录（按 callId 去重与收尾）', () => {
  it('同 callId 重复更新只维护一张卡片，状态原地变化', async () => {
    const { store } = mockStore(createMemoryChatRepository(), [
      async (emit, request) => {
        const t = turn(request);
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'running' }));
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'running', detail: '进度1' }));
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'done', detail: '完成' }));
        emit({ ...t, type: 'end', finishReason: 'stop' });
      },
    ]);
    await store.getState().init();
    await store.getState().send('问题', null);
    const calls = store.getState().messages[1].toolCalls;
    expect(calls).toHaveLength(1);
    expect(calls?.[0]).toMatchObject({ callId: 'c1', status: 'done', detail: '完成' });
    expect(calls?.[0].endedAt).toBeTruthy();
  });

  it('已终态的卡片不接受重开或改写', async () => {
    const { store } = mockStore(createMemoryChatRepository(), [
      async (emit, request) => {
        const t = turn(request);
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'running' }));
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'done', detail: '原始结果' }));
        // 迟到/重复更新：不得重开，也不得改写已完成过程
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'running' }));
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'error', detail: '改写' }));
        emit(tool(t, { callId: 'c2', kind: 'skill', name: '技能B', status: 'running' }));
        emit({ ...t, type: 'end', finishReason: 'stop' });
      },
    ]);
    await store.getState().init();
    await store.getState().send('问题', null);
    const calls = store.getState().messages[1].toolCalls!;
    expect(calls.find((c) => c.callId === 'c1')).toMatchObject({
      status: 'done',
      detail: '原始结果',
    });
    // 本轮 end 时仍在运行的第二张卡被收尾，不永久停留在运行中
    expect(calls.find((c) => c.callId === 'c2')).toMatchObject({ status: 'cancelled' });
  });

  it('end 之后迟到的工具事件不再修改消息', async () => {
    const { store } = mockStore(createMemoryChatRepository(), [
      async (emit, request) => {
        const t = turn(request);
        emit({ ...t, type: 'end', finishReason: 'stop' });
        emit(tool(t, { callId: 'late', kind: 'mcp', name: '迟到工具', status: 'running' }));
      },
    ]);
    await store.getState().init();
    await store.getState().send('问题', null);
    expect(store.getState().messages[1].toolCalls).toBeUndefined();
  });

  it('取消收尾：停止后运行中的工具变为已取消，消息标记已停止', async () => {
    const repo = createMemoryChatRepository();
    const { store } = mockStore(repo, [
      async (emit, request) => {
        const t = turn(request);
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'running' }));
        await new Promise<void>((resolve) => {
          request.signal.addEventListener('abort', () => resolve(), { once: true });
        });
      },
    ]);
    await store.getState().init();
    const run = store.getState().send('问题', null, structuredClone(SNAPSHOT));
    store.getState().stop();
    await run;
    const message = store.getState().messages[1];
    expect(message.status).toBe('stopped');
    expect(message.toolCalls?.[0]).toMatchObject({ callId: 'c1', status: 'cancelled' });
    const saved = await repo.load(store.getState().activeId!);
    expect(saved?.messages[1].toolCalls?.[0].status).toBe('cancelled');
  });

  it('断流收尾：未收到 end 时运行中的工具同样收尾', async () => {
    const { store } = mockStore(createMemoryChatRepository(), [
      async (emit, request) => {
        const t = turn(request);
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'running' }));
        // 既无 end 也无 error，直接返回（模拟断流）
      },
    ]);
    await store.getState().init();
    await store.getState().send('问题', null);
    const message = store.getState().messages[1];
    expect(message.status).toBe('stopped');
    expect(message.toolCalls?.[0].status).toBe('cancelled');
  });

  it('工具失败按明确错误收尾，保留过程，重试可用', async () => {
    const { store, requests } = mockStore(createMemoryChatRepository(), [
      async (emit, request) => {
        const t = turn(request);
        // 工具失败轮没有正文：过程记录必须随失败尝试保留
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'running' }));
        emit(tool(t, { callId: 'c1', kind: 'mcp', name: '工具A', status: 'error', detail: '【模拟失败】工具错误' }));
        emit({
          ...t,
          type: 'error',
          error: { code: 'MOCK_TOOL_ERROR', message: '模拟工具执行失败', retryable: true },
        });
      },
      async (emit, request) => {
        const t = turn(request);
        emit(tool(t, { callId: 'c2', kind: 'mcp', name: '工具A', status: 'running' }));
        emit(tool(t, { callId: 'c2', kind: 'mcp', name: '工具A', status: 'done', detail: '成功' }));
        emit({ ...t, type: 'end', finishReason: 'stop' });
      },
    ]);
    await store.getState().init();
    await store.getState().send('问题', null, structuredClone(SNAPSHOT));
    const failed = store.getState().messages.at(-1)!;
    expect(failed.status).toBe('error');
    expect(failed.content).toBe('');
    expect(failed.toolCalls?.[0]).toMatchObject({ callId: 'c1', status: 'error' });

    await store.getState().retryLast(null);
    const retried = store.getState().messages.at(-1)!;
    expect(retried.status).toBe('done');
    expect(requests[1].extensions?.mcps[0].name).toBe('目录工具'); // 按原快照重试
    expect(retried.superseded).toBeUndefined();
    // 失败尝试（含错误过程记录）被保留并标注
    const superseded = store.getState().messages.filter((m) => m.superseded);
    expect(superseded).toHaveLength(1);
    expect(superseded[0].toolCalls?.[0]).toMatchObject({ status: 'error' });
  });
});

describe('历史恢复与兼容', () => {
  it('R5：恢复后再次选择历史会话，不复活 streaming/running，内容与过程保留', async () => {
    const repo = createMemoryChatRepository();
    await repo.save({
      id: 'interrupted',
      title: '中断历史',
      createdAt: '2026-09-07',
      updatedAt: '2026-09-07',
      messages: [
        { id: 'u', role: 'user', content: '问题', status: 'done' },
        {
          id: 'a',
          role: 'assistant',
          content: '部分内容',
          status: 'streaming',
          toolCalls: [
            { callId: 'c1', kind: 'mcp', name: '模拟工具', status: 'running', startedAt: '2026-09-07' },
          ],
        },
      ],
    } as never);
    const run = vi.fn(async () => undefined);
    const store = createChatStore({
      mode: 'mock',
      repository: repo,
      services: { mock: { kind: 'mock', run, armFailure() {}, armAskUser() {}, armReplyFailure() {} } },
    });
    await store.getState().init();
    expect(store.getState().messages[1].status).toBe('stopped');
    expect(store.getState().messages[1].toolCalls?.[0].status).toBe('cancelled');

    // 新建/切换会话后从历史重新选择原会话：与初始化同一套恢复语义
    store.getState().newConversation();
    await store.getState().selectConversation('interrupted');
    const reselected = store.getState().messages[1];
    expect(reselected.status).toBe('stopped');
    expect(reselected.toolCalls?.[0].status).toBe('cancelled');
    expect(reselected.content).toBe('部分内容'); // 消息内容保留
    expect(reselected.toolCalls).toHaveLength(1); // 工具历史保留，不清库
    expect(run).not.toHaveBeenCalled(); // 恢复不重放
  });

  it('刷新恢复过程记录：运行中卡片收尾为已取消，完成卡片保持，不重新执行', async () => {
    const repo = createMemoryChatRepository();
    await repo.save({
      id: 'hist',
      title: '历史会话',
      createdAt: '2026-09-07',
      updatedAt: '2026-09-07',
      extensions: { mcps: [{ id: 'm1', name: '目录工具', description: '' }], skills: [] },
      messages: [
        { id: 'u', role: 'user', content: '旧问题', status: 'done' },
        {
          id: 'a',
          role: 'assistant',
          content: '部分内容',
          status: 'streaming',
          extensions: { mcps: [{ id: 'm1', name: '目录工具', description: '' }], skills: [] },
          toolCalls: [
            { callId: 'c1', kind: 'skill', name: '技能A', status: 'done', startedAt: '2026-09-07' },
            { callId: 'c2', kind: 'mcp', name: '工具B', status: 'running', startedAt: '2026-09-07' },
          ],
        },
      ],
    } as never);
    const { service, requests } = scriptedService([async () => undefined]);
    const store = createChatStore({ mode: 'mock', repository: repo, services: { mock: service } });
    await store.getState().init();
    expect(requests).toHaveLength(0); // 恢复历史不重新执行
    const restored = store.getState().messages[1];
    expect(restored.status).toBe('stopped');
    expect(restored.toolCalls?.[0]).toMatchObject({ callId: 'c1', status: 'done' });
    expect(restored.toolCalls?.[1]).toMatchObject({ callId: 'c2', status: 'cancelled' });
    expect(restored.extensions?.mcps[0].name).toBe('目录工具');
  });

  it('旧历史没有扩展快照或过程字段时按空集合处理，不清空不重置', async () => {
    const repo = createMemoryChatRepository();
    await repo.save({
      id: 'old',
      title: '旧会话',
      createdAt: '2026-09-06',
      updatedAt: '2026-09-06',
      messages: [
        { id: 'u', role: 'user', content: '旧问题', status: 'done' },
        { id: 'a', role: 'assistant', content: '旧回答', status: 'done' },
      ],
    });
    const { service } = scriptedService([
      async (emit, request) => {
        emit({ ...turn(request), type: 'text', delta: '新回答' });
        emit({ ...turn(request), type: 'end', finishReason: 'stop' });
      },
    ]);
    const store = createChatStore({ mode: 'mock', repository: repo, services: { mock: service } });
    await store.getState().init();
    const messages = store.getState().messages;
    expect(messages.map((m) => m.content)).toEqual(['旧问题', '旧回答']);
    expect(messages[1].toolCalls).toBeUndefined();
    expect(messages[1].extensions).toBeUndefined();
    // 再次发送正常，不受旧数据影响
    store.getState().newConversation();
    await store.getState().send('新问题', null);
    expect(store.getState().messages[1]).toMatchObject({ status: 'done', content: '新回答' });
  });
});

describe('真实路径不发送扩展快照', () => {
  it('请求携带快照时，真实服务不把 extensions 转发给底层 SSE 客户端', async () => {
    const { createRealChatService } = await import('./chat-service');
    const inputs: Array<Record<string, unknown>> = [];
    const service = createRealChatService({
      stream: async (input) => {
        inputs.push(input as unknown as Record<string, unknown>);
      },
    });
    await service.run(
      {
        sessionId: 's',
        turnId: 't',
        messages: [{ role: 'user', content: '问' }],
        modelProfileId: 'p1',
        extensions: structuredClone(SNAPSHOT),
        signal: new AbortController().signal,
      },
      () => undefined,
    );
    expect(inputs).toHaveLength(1);
    expect('extensions' in inputs[0]).toBe(false);
  });

  it('带说明正文的技能转成 skills 下发，且只带名称与正文', async () => {
    const { createRealChatService } = await import('./chat-service');
    const inputs: Array<Record<string, unknown>> = [];
    const service = createRealChatService({
      stream: async (input) => {
        inputs.push(input as unknown as Record<string, unknown>);
      },
    });
    await service.run(
      {
        sessionId: 's',
        turnId: 't',
        messages: [{ role: 'user', content: '问' }],
        modelProfileId: 'p1',
        extensions: {
          mcps: [{ id: 'm1', name: '目录工具', description: '演示 MCP' }],
          skills: [
            { id: 's1', name: '教案规范', description: '演示 Skill', content: '按七个栏目输出。' },
            { id: 's2', name: '空正文', description: '' },
            { id: 's3', name: '  仅空白  ', description: '', content: '   ' },
          ],
        },
        signal: new AbortController().signal,
      },
      () => undefined,
    );
    expect(inputs).toHaveLength(1);
    expect(inputs[0].skills).toEqual([{ name: '教案规范', content: '按七个栏目输出。' }]);
    expect('extensions' in inputs[0]).toBe(false);
  });

  it('没有有效技能时不下发 skills 字段，MCP 也不下发', async () => {
    const { createRealChatService } = await import('./chat-service');
    const inputs: Array<Record<string, unknown>> = [];
    const service = createRealChatService({
      stream: async (input) => {
        inputs.push(input as unknown as Record<string, unknown>);
      },
    });
    await service.run(
      {
        sessionId: 's',
        turnId: 't',
        messages: [{ role: 'user', content: '问' }],
        modelProfileId: 'p1',
        extensions: structuredClone(SNAPSHOT),
        signal: new AbortController().signal,
      },
      () => undefined,
    );
    expect('skills' in inputs[0]).toBe(false);
  });
});
