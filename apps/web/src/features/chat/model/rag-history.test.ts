import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository } from '@/services/chat-repository';
import type { ChatService, ChatServiceRequest } from './chat-service';
import { createChatStore } from './store';
import type { ScopeSnapshot } from './rag-v2';

const selection = { gradeId: 'g1', subjectId: 's1', editionId: 'e1', documentIds: ['d1'] };

const scope: ScopeSnapshot = {
  schemaVersion: 2,
  selection,
  documents: [{ documentId: 'd1', documentRevisionId: 'r1', metadataRevisionId: 'm1' }],
  embeddingGenerationId: 'gen-1',
  scopeHash: 'a'.repeat(64),
};

/** 旧 v1 记录：rag 形状含 subject/citations/explanations，且没有 v2 新字段 */
function legacyConversation() {
  return {
    schemaVersion: 1,
    revision: 1,
    id: 'legacy-1',
    title: '旧教材会话',
    createdAt: '2026-09-01T00:00:00.000Z',
    updatedAt: '2026-09-01T00:05:00.000Z',
    messages: [
      { id: 'u1', role: 'user', content: '旧题：求导', status: 'done' },
      {
        id: 'a1',
        role: 'assistant',
        content: '旧 v1 正文（含教材定位与讲解）',
        status: 'done',
        modelLabel: '本地教材引擎',
        rag: {
          sessionId: 'legacy-1',
          turnId: 'turn-legacy',
          question: '旧题：求导',
          lastEventId: 9,
          status: 'active',
          subject: '数学',
          citations: [{ citation_id: 'c1', file: '必修一.md', text: '原文' }],
          explanations: ['旧讲解'],
        },
      },
    ],
  } as never;
}

describe('教材历史兼容（RAG-REBUILD v1.0）', () => {
  it('旧 v1 消息正常可读、不迁移、不清库，也不猜造 v2 引用', async () => {
    const repo = createMemoryChatRepository();
    await repo.save(legacyConversation() as never, 0);
    const service: ChatService = { kind: 'real', run: vi.fn() };
    const store = createChatStore({ repository: repo, service });
    await store.getState().init();
    const message = store.getState().messages[1]!;
    expect(message.content).toContain('旧 v1 正文');
    expect(message.ragResult).toBeUndefined();
    expect(message.ragEvidence).toBeUndefined();
    expect(message.ragScope).toBeUndefined();
    expect(message.ragExplain).toBeUndefined();
    // 旧字段原样保留（只读展示，不迁移也不清空）
    expect((message.rag as unknown as Record<string, unknown>).subject).toBe('数学');
    expect((message.rag as unknown as Record<string, unknown>).citations).toHaveLength(1);
    // 旧消息缺少 v2 字段不产生额外提示，也不会触发任何请求
    expect(store.getState().loadError).toBeNull();
    expect(service.run).not.toHaveBeenCalled();
    store.getState().dispose();
  });

  it('旧轮缺范围快照时「继续本轮」如实拒绝（不猜造范围、不发请求）', async () => {
    const repo = createMemoryChatRepository();
    await repo.save(legacyConversation() as never, 0);
    const run = vi.fn();
    const store = createChatStore({ repository: repo, service: { kind: 'real', run } });
    store.getState().setRagScopeSelection(null);
    await store.getState().init();
    store.getState().setRagScopeSelection(null);
    await store.getState().resumeRag('a1');
    expect(run).not.toHaveBeenCalled();
    expect(store.getState().serviceNotice).toContain('范围快照');
    store.getState().dispose();
  });

  it('续传回传该轮 message.start 的冻结快照原样（不替换为当前选择）', async () => {
    const repo = createMemoryChatRepository();
    await repo.save(
      {
        schemaVersion: 1,
        revision: 1,
        id: 'c-frozen',
        title: '冻结快照会话',
        createdAt: '2026-09-20T00:00:00.000Z',
        updatedAt: '2026-09-20T00:05:00.000Z',
        messages: [
          { id: 'u1', role: 'user', content: '原题', status: 'done' },
          {
            id: 'a1',
            role: 'assistant',
            content: '已收到的部分正文',
            status: 'stopped',
            rag: {
              sessionId: 'c-frozen',
              turnId: 'turn-1',
              question: '原题',
              lastEventId: 3,
              status: 'interrupted',
            },
            ragScope: scope,
          },
        ],
      } as never,
      0,
    );
    const seen: ChatServiceRequest[] = [];
    const store = createChatStore({
      repository: repo,
      service: {
        kind: 'real',
        // 只记录请求体后立即结束：断言续传入参，不依赖长时间挂起的流
        run: async (request) => {
          seen.push(request);
        },
      },
    });
    await store.getState().init();
    // 当前界面范围与被冻结的轮次不同：续传必须回传冻结快照
    store.getState().setRagScopeSelection({
      gradeId: 'g-other',
      subjectId: 's-other',
      editionId: 'e-other',
      documentIds: ['d-other'],
    });
    await store.getState().resumeRag('a1');
    expect(seen).toHaveLength(1);
    expect(seen[0]!.rag?.scope).toEqual({ kind: 'frozen', snapshot: scope });
    expect(seen[0]!.rag?.lastEventId).toBe(3);
    expect(seen[0]!.rag?.turnId).toBe('turn-1');
    store.getState().dispose();
  });
});
