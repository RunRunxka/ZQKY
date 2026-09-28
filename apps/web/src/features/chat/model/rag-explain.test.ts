import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository } from '@/services/chat-repository';
import type { ChatService, ChatServiceEvent, ChatServiceRequest } from './chat-service';
import { createChatStore, type ChatDeps } from './store';
import type { RagExplainRequest, RagResultV2, ScopeSnapshot } from './rag-v2';

const selection = {
  gradeId: 'g1',
  subjectId: 's1',
  editionId: 'e1',
  documentIds: ['d1'],
};

const scope: ScopeSnapshot = {
  schemaVersion: 2,
  selection,
  documents: [{ documentId: 'd1', documentRevisionId: 'r1', metadataRevisionId: 'm1' }],
  embeddingGenerationId: 'gen-1',
  scopeHash: 'a'.repeat(64),
};

const evidence = {
  evidenceId: 'ev-1',
  documentRevisionId: 'r1',
  normalizedTextSha256: 'b'.repeat(64),
  charStart: 0,
  charEnd: 12,
  documentId: 'd1',
  title: '高中数学 必修一',
  editionLabel: '人教A版',
  subjectLabel: '数学',
  chapterPath: ['第一章'],
  text: '集合的表示方法。',
  originalFileSha256: 'c'.repeat(64),
  locator: {
    kind: 'markdown' as const,
    lineStart: 10,
    lineEnd: 12,
    pageStart: null,
    pageEnd: null,
    blockStart: null,
    blockEnd: null,
  },
  isSuperseded: false,
};

const result: RagResultV2 = {
  contractVersion: 2,
  resultId: 'res-1',
  status: 'ok',
  scopeSnapshot: scope,
  points: [{ pointId: 'p1', title: '集合表示', summary: '列举法或描述法。', evidenceIds: ['ev-1'] }],
  evidence: [evidence],
  reason: null,
};

const extensions = {
  mcps: [],
  skills: [],
  capability: { value: 'rag', label: 'RAG 模式' },
};

const clarification = {
  interactionId: 'i1',
  status: 'waiting' as const,
  intro: '可继续追问细节，或跳过结束本轮。',
  questions: [
    {
      questionId: 'textbook-follow-up',
      header: '继续追问',
      prompt: '定位是否符合题意？你希望进一步理解哪一步？',
      options: [{ label: '细讲解题思路' }, { label: '重新核对知识点' }],
      multiSelect: false,
      allowFreeText: true,
    },
  ],
};

/** 一发即终态的教材轮：message.start → rag.result → 整段正文 → 追问卡 → end */
function ragService() {
  const calls = { reply: 0, cancel: 0 };
  const service: ChatService = {
    kind: 'real',
    cancel: async () => {
      calls.cancel += 1;
      return { accepted: true };
    },
    submitReply: async () => {
      calls.reply += 1;
      return { accepted: true };
    },
    run: async (request: ChatServiceRequest, emit: (event: ChatServiceEvent) => void) => {
      const base = { sessionId: request.sessionId, turnId: request.turnId };
      emit({ ...base, type: 'turn-start', scopeSnapshot: scope, eventId: 1 });
      emit({ ...base, type: 'rag-result', result, eventId: 2 });
      emit({ ...base, type: 'text', delta: '教材知识点与学生原文摘录。', replace: true, eventId: 3 });
      emit({ ...base, type: 'wait-user', interaction: clarification, eventId: 4 });
      emit({ ...base, type: 'end', finishReason: 'stop', eventId: 5 });
    },
  };
  return { service, calls };
}

/** 详解流注入点（测试替身）类型 */
type ExplainStream = ChatDeps['explainStream'];
const profileA = { id: 'profile-a', modelLabel: '模型 A · chat', contextTokens: 8000, maxOutputTokens: 2048 };
const profileB = { id: 'profile-b', modelLabel: '模型 B · chat', contextTokens: 8000, maxOutputTokens: 2048 };

/** 已完成一轮定位的 store（终态 + 可用的详解引导卡） */
async function locatedStore(explainStream: ExplainStream) {
  const { service, calls } = ragService();
  const repo = createMemoryChatRepository();
  const store = createChatStore({ repository: repo, service, explainStream });
  store.getState().setRagScopeSelection(selection);
  store.getState().setChatProfile(profileA);
  await store.getState().init();
  await store.getState().send('原题', null, extensions);
  const message = store.getState().messages[1]!;
  const guidance = message.asks?.find((a) => a.kind === 'guidance');
  return { store, repo, serviceCalls: calls, message, guidance };
}

describe('教材 v2 落库与详解轮（RAG-REBUILD v1.0）', () => {
  it('rag.result 与正文、游标在同一次会话持久化提交（刷新后结构化依据不丢）', async () => {
    const saves: { content: string; lastEventId: number; hasResult: boolean }[] = [];
    const { service } = ragService();
    const memory = createMemoryChatRepository();
    const repo = {
      ...memory,
      list: memory.list.bind(memory),
      load: memory.load.bind(memory),
      remove: memory.remove.bind(memory),
      async save(conversation: Parameters<typeof memory.save>[0], expected?: number) {
        const message = conversation.messages[1];
        saves.push({
          content: message?.content ?? '',
          lastEventId: message?.rag?.lastEventId ?? -1,
          hasResult: !!message?.ragResult,
        });
        return memory.save(conversation, expected);
      },
    };
    const store = createChatStore({ repository: repo, service });
    store.getState().setRagScopeSelection(selection);
    await store.getState().init();
    await store.getState().send('原题', null, extensions);
    // 结构化结果首次落盘的同一份记录里必须已带正文与游标（不存在“先存结果后存正文”）
    const withResult = saves.filter((entry) => entry.hasResult);
    expect(withResult.length).toBeGreaterThan(0);
    expect(withResult[0]!.content).toBe('教材知识点与学生原文摘录。');
    // 结果与正文合并写入时游标已推进到正文（≥3），而不是停在只含结果的 2
    expect(withResult[0]!.lastEventId).toBeGreaterThanOrEqual(3);
    expect(saves.some((entry) => entry.hasResult && !entry.content)).toBe(false);
    // 刷新（同一仓储重新载入）后结构化依据、范围、正文与游标都在
    const reloaded = createChatStore({ repository: memory, service });
    await reloaded.getState().init();
    const restored = reloaded.getState().messages[1]!;
    expect(restored.ragResult?.resultId).toBe('res-1');
    expect(restored.ragEvidence?.[0]?.evidenceId).toBe('ev-1');
    expect(restored.ragScope?.scopeHash).toBe(scope.scopeHash);
    expect(restored.content).toBe('教材知识点与学生原文摘录。');
    expect(restored.rag?.lastEventId).toBe(5);
    expect(restored.status).toBe('done');
    store.getState().dispose();
    reloaded.getState().dispose();
  });

  it('终态 ok 后创建详解引导卡（不占用等待身份）；忽略只置 dismissed，不调用 reply/cancel/LLM', async () => {
    const explainStream = vi.fn();
    const { store, guidance, serviceCalls } = await locatedStore(explainStream);
    expect(guidance).toBeTruthy();
    expect(store.getState().waitingInteractionId).toBeNull();
    store.getState().skipAskQuestion(guidance!.interactionId);
    expect(
      store
        .getState()
        .messages[1]!.asks!.find((a) => a.kind === 'guidance')!
        .guidance?.dismissed,
    ).toBe(true);
    expect(serviceCalls.reply).toBe(0);
    expect(serviceCalls.cancel).toBe(0);
    expect(explainStream).not.toHaveBeenCalled();
    store.getState().dispose();
  });

  it('no_evidence 不出现详解引导，只提示补充信息', async () => {
    const service: ChatService = {
      kind: 'real',
      run: async (request, emit) => {
        const base = { sessionId: request.sessionId, turnId: request.turnId };
        const empty: RagResultV2 = {
          ...result,
          resultId: 'res-empty',
          status: 'no_evidence',
          points: [],
          evidence: [],
          reason: '当前教材范围没有找到足够依据。',
        };
        emit({ ...base, type: 'turn-start', scopeSnapshot: scope, eventId: 1 });
        emit({ ...base, type: 'rag-result', result: empty, eventId: 2 });
        emit({
          ...base,
          type: 'wait-user',
          interaction: {
            interactionId: 'i2',
            status: 'waiting',
            intro: '教材证据不足，请补充后重新定位。',
            questions: [
              {
                questionId: 'textbook-follow-up',
                prompt: '请补充完整题干。',
                options: [],
                multiSelect: false,
                allowFreeText: true,
              },
            ],
          },
          eventId: 3,
        });
        emit({ ...base, type: 'end', finishReason: 'stop', eventId: 4 });
      },
    };
    const store = createChatStore({ repository: createMemoryChatRepository(), service });
    store.getState().setRagScopeSelection(selection);
    await store.getState().init();
    await store.getState().send('原题', null, extensions);
    const message = store.getState().messages[1]!;
    expect(message.ragResult?.status).toBe('no_evidence');
    expect(message.asks?.some((a) => a.kind === 'guidance')).toBe(false);
    store.getState().dispose();
  });

  it('详解轮冻结当前模型与证据：独立 turnId、不占等待身份；重试沿用冻结模型', async () => {
    const explainCalls: RagExplainRequest[] = [];
    const explainStream = vi.fn(
      async (
        body: RagExplainRequest,
        handlers: { onStart?: (i: { messageId: string; modelProfileId: string }) => void; onText: (d: string) => void; onEnd?: (r: string) => void },
      ) => {
        explainCalls.push(body);
        handlers.onStart?.({ messageId: 'm1', modelProfileId: body.modelProfileId });
        handlers.onText('详解正文');
        handlers.onEnd?.('stop');
      },
    );
    const { store, guidance, message } = await locatedStore(
      explainStream as unknown as ExplainStream,
    );
    const guidanceId = guidance!.interactionId;
    store.getState().setAskFocus(guidanceId, 'explain-direction');
    store.getState().setAskDraft(guidanceId, 'explain-direction', {
      labels: ['细讲解题思路'],
      freeText: '',
      disposition: 'unanswered',
    });
    expect(await store.getState().continueAsk(guidanceId)).toBe(true);
    expect(explainCalls).toHaveLength(1);
    const first = explainCalls[0]!;
    expect(first).toMatchObject({
      sessionId: store.getState().activeId,
      modelProfileId: 'profile-a',
      originalQuestion: '原题',
      followUp: '细讲解题思路',
      scopeSnapshot: scope,
      evidenceRefs: [
        {
          evidenceId: 'ev-1',
          documentRevisionId: 'r1',
          normalizedTextSha256: 'b'.repeat(64),
          charStart: 0,
          charEnd: 12,
        },
      ],
    });
    // 独立轮次：新 turnId、不占用服务端等待身份、原 RAG 轮 id 保持不变
    expect(first.turnId).not.toBe(message.rag?.turnId);
    expect(store.getState().waitingInteractionId).toBeNull();
    const explainMessage = store.getState().messages.at(-1)!;
    expect(explainMessage.ragExplain).toMatchObject({
      turnId: first.turnId,
      modelProfileId: 'profile-a',
      followUp: '细讲解题思路',
      status: 'done',
    });
    expect(explainMessage.modelProfileId).toBe('profile-a');
    expect(explainMessage.content).toContain('详解正文');
    // 默认聊天模型变化后重试：仍用冻结的 profile-a 与同一 turnId/证据
    store.getState().setChatProfile(profileB);
    await store.getState().retryExplain(explainMessage.id);
    expect(explainCalls).toHaveLength(2);
    expect(explainCalls[1]!.turnId).toBe(first.turnId);
    expect(explainCalls[1]!.modelProfileId).toBe('profile-a');
    expect(explainCalls[1]!.evidenceRefs).toEqual(first.evidenceRefs);
    expect(store.getState().messages.at(-1)!.ragExplain?.modelProfileId).toBe('profile-a');
    store.getState().dispose();
  });

  it('没有可用聊天模型时保留选择、不消耗卡片、不创建空助手消息', async () => {
    const explainStream = vi.fn();
    const { store, guidance } = await locatedStore(
      explainStream as unknown as ExplainStream,
    );
    const before = store.getState().messages.length;
    store.getState().setChatProfile(null);
    const guidanceId = guidance!.interactionId;
    store.getState().setAskDraft(guidanceId, 'explain-direction', {
      labels: ['重新核对知识点'],
      freeText: '',
      disposition: 'unanswered',
    });
    expect(await store.getState().continueAsk(guidanceId)).toBe(false);
    expect(explainStream).not.toHaveBeenCalled();
    expect(store.getState().messages).toHaveLength(before);
    const card = store
      .getState()
      .messages[1]!.asks!.find((a) => a.interactionId === guidanceId)!;
    expect(card.status).toBe('waiting');
    expect(card.drafts['explain-direction']?.labels).toEqual(['重新核对知识点']);
    expect(store.getState().serviceNotice).toContain('模型');
    store.getState().dispose();
  });

  it('停止详解真的中断上游（AbortSignal aborted），消息如实标记已停止', async () => {
    const seen: AbortSignal[] = [];
    const explainStream = vi.fn(
      (_body: RagExplainRequest, _handlers: unknown, signal?: AbortSignal) => {
        if (signal) seen.push(signal);
        return new Promise<void>((_resolve, reject) => {
          signal?.addEventListener('abort', () =>
            reject(Object.assign(new Error('aborted'), { name: 'AbortError' })),
          );
        });
      },
    );
    const { store, guidance } = await locatedStore(
      explainStream as unknown as ExplainStream,
    );
    const guidanceId = guidance!.interactionId;
    store.getState().setAskDraft(guidanceId, 'explain-direction', {
      labels: ['细讲解题思路'],
      freeText: '',
      disposition: 'unanswered',
    });
    const dispatching = store.getState().continueAsk(guidanceId);
    await vi.waitFor(() => expect(seen).toHaveLength(1));
    expect(seen[0].aborted).toBe(false);
    store.getState().stop();
    expect(seen[0].aborted).toBe(true);
    await dispatching;
    const explainMessage = store.getState().messages.at(-1)!;
    expect(explainMessage.status).toBe('stopped');
    expect(explainMessage.ragExplain?.status).toBe('stopped');
    store.getState().dispose();
  });
});
