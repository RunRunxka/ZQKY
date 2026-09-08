import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository, type ChatRepository } from '@/services/chat-repository';
import type { TurnExtensionSnapshot } from '@/contracts/chat';
import { createMockChatService, type ChatService, type MockChatService } from './chat-service';
import { createChatStore } from './store';

const COMPOSER_SNAPSHOT: TurnExtensionSnapshot = {
  mcps: [],
  skills: [],
  capability: {
    value: 'deep_question',
    label: '智能出题',
    config: {
      mode: 'custom',
      topic: '光合作用',
      num_questions: 5,
      difficulty: 'auto',
      question_types: ['choice'],
      paper_name: '',
    },
  },
  persona: { id: 'p1', name: '耐心的小学老师' },
  knowledge: [{ id: 'k1', name: '课程标准库' }],
  historyRefs: [{ id: 'c1', title: '上节课的讨论' }],
  attachments: [
    { filename: '课件.pdf', kind: 'doc', size: 2048, mimeType: 'application/pdf' },
  ],
};

function mockStore(
  repo: ChatRepository,
  service: MockChatService,
) {
  return createChatStore({ mode: 'mock', repository: repo, services: { mock: service } });
}

describe('S2 输入区：完整配置快照', () => {
  it('发送时冻结能力/人设/知识/引用/附件（深拷贝，后续编辑不影响已冻结快照）', async () => {
    const store = mockStore(createMemoryChatRepository(), createMockChatService({ chunkDelayMs: 0 }));
    await store.getState().init();
    const snapshot = structuredClone(COMPOSER_SNAPSHOT);
    const run = store.getState().send('出 5 道题', null, snapshot);
    // 发送后编辑源对象：已冻结快照不得跟随变化
    (snapshot.capability!.config as Record<string, unknown>).topic = '被篡改的主题';
    snapshot.attachments!.push({ filename: 'late.txt', kind: 'doc', size: 1 });
    await run;
    const message = store.getState().messages[1]!;
    expect(message.extensions?.capability).toEqual(COMPOSER_SNAPSHOT.capability);
    expect(message.extensions?.persona).toEqual({ id: 'p1', name: '耐心的小学老师' });
    expect(message.extensions?.knowledge).toEqual([{ id: 'k1', name: '课程标准库' }]);
    expect(message.extensions?.historyRefs).toEqual([{ id: 'c1', title: '上节课的讨论' }]);
    expect(message.extensions?.attachments).toHaveLength(1);
    store.getState().dispose();
  });

  it('模拟服务按快照复述能力与配置，并如实说明附件未读取内容', async () => {
    const store = mockStore(createMemoryChatRepository(), createMockChatService({ chunkDelayMs: 0 }));
    await store.getState().init();
    const run = store.getState().send('出 5 道题', null, structuredClone(COMPOSER_SNAPSHOT));
    await run;
    const content = store.getState().messages[1]!.content;
    expect(content).toContain('【模拟回复】');
    expect(content).toContain('本轮能力：智能出题');
    expect(content).toContain('主题=光合作用');
    expect(content).toContain('角色人设：耐心的小学老师');
    expect(content).toContain('课程标准库');
    expect(content).toContain('未执行真实检索');
    expect(content).toContain('引用会话：「上节课的讨论」');
    expect(content).toContain('附件 1 个：课件.pdf');
    expect(content).toContain('未读取文件内容');
    store.getState().dispose();
  });

  it('重试沿用原快照（含能力配置），不读取最新表单', async () => {
    const requests: TurnExtensionSnapshot[] = [];
    const gates: (() => void)[] = [];
    const service: ChatService = {
      kind: 'real',
      run: async (request, emit) => {
        requests.push(request.extensions ?? { mcps: [], skills: [] });
        void emit({ sessionId: request.sessionId, turnId: request.turnId, type: 'turn-start' });
        // 先给一点正文：零正文失败占位在重试时会被移除（R12 规则），无法作为重试对象
        void emit({
          sessionId: request.sessionId,
          turnId: request.turnId,
          type: 'text',
          delta: '第一轮回答内容',
        });
        await new Promise<void>((resolve) => gates.push(resolve));
      },
    };
    const store = createChatStore({
      repository: createMemoryChatRepository(),
      services: { real: service },
    });
    await store.getState().init();
    const firstRun = store
      .getState()
      .send('出题', { id: 'p', modelLabel: '测试' }, structuredClone(COMPOSER_SNAPSHOT));
    await vi.waitFor(() => expect(requests).toHaveLength(1));
    store.getState().stop();
    gates[0]!();
    await firstRun;
    expect(store.getState().messages.at(-1)?.status).toBe('stopped');
    // 真实模式重试需要有效模型档案（与发送一致，不静默回退）
    const retryRun = store.getState().retryLast({ id: 'p', modelLabel: '测试' });
    await vi.waitFor(() => expect(requests).toHaveLength(2));
    store.getState().stop();
    gates[1]!();
    await retryRun;
    expect(requests[1]?.capability).toEqual(COMPOSER_SNAPSHOT.capability);
    expect(requests[1]?.attachments).toHaveLength(1);
    store.getState().dispose();
  });
});
