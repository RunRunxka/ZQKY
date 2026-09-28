import { afterEach, describe, expect, it, vi } from 'vitest';
import { createRealChatService, type ChatServiceEvent, type ChatServiceRequest } from './chat-service';
import { fetchRagStatus, streamExplain, streamRag, normalizeRagStatus } from './rag-service';
import type { RagExplainRequest, RagResultV2, ScopeSnapshot } from './rag-v2';

const scope: ScopeSnapshot = {
  schemaVersion: 2,
  selection: { gradeId: 'g1', subjectId: 's1', editionId: 'e1', documentIds: ['d1'] },
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
  chapterPath: ['第一章', '1.1 集合'],
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
  points: [{ pointId: 'p1', title: '集合表示', summary: '可用列举法或描述法。', evidenceIds: ['ev-1'] }],
  evidence: [evidence],
  reason: null,
};

const request = (): ChatServiceRequest => ({
  sessionId: 's1',
  turnId: 't1',
  messages: [{ role: 'user', content: '求函数定义域' }],
  signal: new AbortController().signal,
  rag: { sessionId: 's1', turnId: 't1', question: '求函数定义域', lastEventId: 0, status: 'active', scope: { kind: 'selection', selection: scope.selection } },
});

const frame = (id: number, name: string, body = {}) =>
  `id: ${id}\nevent: ${name}\ndata: ${JSON.stringify({ sessionId: 's1', turnId: 't1', ...body })}\n\n`;

function serve(text: string) {
  const fetcher = vi
    .fn()
    .mockResolvedValue(new Response(text, { headers: { 'content-type': 'text/event-stream' } }));
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}
afterEach(() => vi.unstubAllGlobals());

describe('教材 RAG v2 通道', () => {
  it('RAG 与追问澄清走专用通道，请求体含范围与游标，不携带云模型/普通历史', async () => {
    const chat = vi.fn();
    const fetcher = serve(
      frame(1, 'message.start', { scopeSnapshot: scope }) +
        frame(2, 'rag.result', { result }) +
        frame(3, 'text.delta', { text: '整段正文' }) +
        frame(4, 'message.end', { finishReason: 'stop' }),
    );
    const events: ChatServiceEvent[] = [];
    await createRealChatService({ stream: chat }).run(
      {
        ...request(),
        modelProfileId: 'cloud-secret-profile',
        extensions: { mcps: [], skills: [], capability: { value: 'ask_questions', label: '追问澄清' } },
      },
      (e) => events.push(e),
    );
    expect(chat).not.toHaveBeenCalled();
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/rag/stream');
    const body = JSON.parse(fetcher.mock.calls[0][1].body);
    expect(body).toMatchObject({
      question: '求函数定义域',
      sessionId: 's1',
      turnId: 't1',
      afterEventId: 0,
      scope: { kind: 'selection', selection: scope.selection },
    });
    expect(body.modelProfileId).toBeUndefined();
    expect(body.messages).toBeUndefined();
    expect(body.subject).toBeUndefined();
    expect(events.map((e) => e.type)).toEqual(['turn-start', 'rag-result', 'text', 'end']);
    expect(events[0]).toMatchObject({ type: 'turn-start', scopeSnapshot: scope });
    expect(events[1]).toMatchObject({ type: 'rag-result', result: { resultId: 'res-1' } });
    // v2：text.delta 是整段渲染好的正文 → 替换语义
    expect(events[2]).toMatchObject({ type: 'text', delta: '整段正文', replace: true });
  });

  it('同轮重连回传冻结快照与持久化游标；重复事件按游标去重', async () => {
    const card = {
      interactionId: 'i1',
      status: 'waiting',
      questions: [{ questionId: 'q1', prompt: '请补充条件', options: [{ label: '细讲解题思路' }], allowFreeText: true }],
    };
    const answers = [{ questionId: 'q1', labels: [], freeText: 'x>0' }];
    const fetcher = serve(
      frame(2, 'text.delta', { text: '旧文本' }) +
        frame(3, 'rag.result', { result }) +
        frame(4, 'wait-user', card) +
        frame(5, 'reply.accepted', { interactionId: 'i1', submissionId: 'a1', answers }) +
        frame(6, 'message.end'),
    );
    const events: ChatServiceEvent[] = [];
    await streamRag(
      {
        ...request(),
        rag: {
          sessionId: 's1',
          turnId: 't1',
          question: '原题',
          lastEventId: 2,
          status: 'interrupted',
          scope: { kind: 'frozen', snapshot: scope },
        },
      },
      (e) => events.push(e),
    );
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toMatchObject({
      question: '原题',
      afterEventId: 2,
      scope: { kind: 'frozen', snapshot: scope },
    });
    // 游标 2 之前的（含 2）事件是已持久化内容：重送不重复追加，只处理 3 之后的事件
    expect(events.map((e) => e.type)).toEqual([
      'rag-result',
      'wait-user',
      'reply-accepted',
      'end',
    ]);
    // v2 wait-user 为扁平载荷：直接解析题目与选项
    expect(events[1]).toMatchObject({
      type: 'wait-user',
      interaction: { interactionId: 'i1', questions: [{ questionId: 'q1' }] },
    });
  });

  it('缺事件编号、编号缺口、身份不符、结构非法一律协议错误，不污染消息', async () => {
    serve(`event: text.delta\ndata: ${JSON.stringify({ sessionId: 's1', turnId: 't1', text: 'x' })}\n\n`);
    await expect(streamRag(request(), vi.fn())).rejects.toMatchObject({ code: 'RAG_PROTOCOL_ERROR' });
    serve(frame(2, 'text.delta', { text: '缺首事件' }));
    await expect(streamRag(request(), vi.fn())).rejects.toMatchObject({ code: 'RAG_PROTOCOL_ERROR' });
    serve(frame(1, 'text.delta', { text: '另一轮', turnId: 'other' }));
    await expect(streamRag(request(), vi.fn())).rejects.toMatchObject({ code: 'RAG_PROTOCOL_ERROR' });
    // rag.result 结构非法（缺 contractVersion）同样拒绝，不把半成品当结果
    serve(frame(1, 'rag.result', { result: { resultId: 'x' } }));
    await expect(streamRag(request(), vi.fn())).rejects.toMatchObject({ code: 'RAG_PROTOCOL_ERROR' });
    // message.start 缺范围快照：v2 协议不完整
    serve(frame(1, 'message.start', {}));
    await expect(streamRag(request(), vi.fn())).rejects.toMatchObject({ code: 'RAG_PROTOCOL_ERROR' });
  });

  it('未收到明确结束事件的断流不能当作完成', async () => {
    serve(frame(1, 'message.start', { scopeSnapshot: scope }) + frame(2, 'text.delta', { text: '部分内容' }));
    const events: ChatServiceEvent[] = [];
    await expect(streamRag(request(), (e) => events.push(e))).rejects.toMatchObject({
      code: 'RAG_DISCONNECTED',
    });
    expect(events.some((e) => e.type === 'end')).toBe(false);
  });

  it('恢复过期显示后端原因，不重建原轮或请求普通聊天', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ code: 'RAG_TURN_EXPIRED', message: '本轮已过期，请重新提问。' }), {
        status: 410,
      }),
    );
    vi.stubGlobal('fetch', fetcher);
    await expect(streamRag(request(), vi.fn())).rejects.toMatchObject({
      code: 'RAG_TURN_EXPIRED',
      message: '本轮已过期，请重新提问。',
    });
    expect(fetcher).toHaveBeenCalledOnce();
  });
});

describe('教材服务状态（v2 分项）', () => {
  it('分别报告检索/本地概括/原文访问与范围，不使用单一 localOnly 结论', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        Response.json({
          retrieval: {
            denseLimit: 50,
            lexicalLimit: 50,
            rrfK: 60,
            vectorStore: true,
            queryEmbedding: true,
            available: false,
            reason: '当前没有已发布的教材索引代。',
          },
          summarization: {
            available: true,
            reason: null,
            model: 'qwen2.5:7b',
            providerUrl: 'http://127.0.0.1:11434',
          },
          sourceAccess: { available: true, reason: null, verifiesHash: true },
          scope: { ready: false, reason: '尚未保存任教范围。', selection: null },
          generation: null,
          humanQuality: 'not_run',
        }),
      ),
    );
    const status = await fetchRagStatus();
    expect(status.legacy).toBe(false);
    expect(status.available).toBe(false); // 检索不可用 且 范围未就绪
    expect(status.retrieval).toMatchObject({ available: false, vectorStore: true, denseLimit: 50 });
    expect(status.summarization).toMatchObject({ available: true, model: 'qwen2.5:7b' });
    expect(status.sourceAccess).toMatchObject({ available: true, verifiesHash: true });
    expect(status.scope).toMatchObject({ ready: false, selection: null });
    expect(status.detail).toContain('检索不可用');
    expect(status.detail).toContain('任教范围未就绪');
    expect(status.humanQuality).toBe('not_run');
  });

  it('旧结构（无 retrieval/scope）按不可用处理并给出可读原因，不崩', () => {
    const legacy = normalizeRagStatus({ available: true, detail: '本地就绪', humanQuality: 'ok' });
    expect(legacy.legacy).toBe(true);
    expect(legacy.available).toBe(false);
    expect(legacy.detail).toContain('本地就绪');
    expect(legacy.retrieval.available).toBe(false);
    expect(legacy.scope.ready).toBe(false);
    const broken = normalizeRagStatus(null);
    expect(broken.available).toBe(false);
    expect(broken.detail.length).toBeGreaterThan(0);
  });
});

describe('教材详解流（普通聊天 SSE，无游标）', () => {
  const explainBody: RagExplainRequest = {
    requestId: 'm1',
    sessionId: 's1',
    turnId: 'explain-1',
    modelProfileId: 'profile-a',
    originalQuestion: '求函数定义域',
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
    history: [{ role: 'user', content: '求函数定义域' }],
    maxOutputTokens: 2048,
  };

  it('解析 message.start / text.delta / message.end 并逐条给出增量', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        `event: message.start\ndata: ${JSON.stringify({ requestId: 'm1', sessionId: 's1', turnId: 'explain-1', messageId: 'msg-1', modelProfileId: 'profile-a' })}\n\n` +
          `event: text.delta\ndata: ${JSON.stringify({ requestId: 'm1', sessionId: 's1', turnId: 'explain-1', messageId: 'msg-1', text: '第一步' })}\n\n` +
          `event: text.delta\ndata: ${JSON.stringify({ requestId: 'm1', sessionId: 's1', turnId: 'explain-1', messageId: 'msg-1', text: '第二步' })}\n\n` +
          `event: message.end\ndata: ${JSON.stringify({ requestId: 'm1', sessionId: 's1', turnId: 'explain-1', messageId: 'msg-1', finishReason: 'stop' })}\n\n`,
        { headers: { 'content-type': 'text/event-stream' } },
      ),
    );
    vi.stubGlobal('fetch', fetcher);
    const deltas: string[] = [];
    let started: string | null = null;
    let finish: string | null = null;
    await streamExplain(explainBody, {
      onStart: (info) => {
        started = info.messageId;
      },
      onText: (delta) => deltas.push(delta),
      onEnd: (reason) => {
        finish = reason;
      },
    });
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/rag/explain/stream');
    const body = JSON.parse(fetcher.mock.calls[0][1].body);
    expect(body).toMatchObject({
      turnId: 'explain-1',
      modelProfileId: 'profile-a',
      followUp: '细讲解题思路',
      evidenceRefs: [{ evidenceId: 'ev-1' }],
    });
    expect(started).toBe('msg-1');
    expect(deltas).toEqual(['第一步', '第二步']);
    expect(finish).toBe('stop');
  });

  it('身份不符记为协议错误；AbortSignal 断开真的中断请求', async () => {
    serve(
      `event: text.delta\ndata: ${JSON.stringify({ requestId: 'm1', sessionId: 's1', turnId: 'other', text: '别轮' })}\n\n`,
    );
    await expect(streamExplain(explainBody, { onText: vi.fn() })).rejects.toMatchObject({
      code: 'RAG_PROTOCOL_ERROR',
    });

    const controller = new AbortController();
    const seen: AbortSignal[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init?: RequestInit) => {
        const signal = init?.signal as AbortSignal;
        seen.push(signal);
        return new Promise<Response>((_resolve, reject) => {
          signal.addEventListener('abort', () => {
            reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
          });
        });
      }),
    );
    const pending = streamExplain(explainBody, { onText: vi.fn() }, controller.signal);
    await vi.waitFor(() => expect(seen).toHaveLength(1));
    expect(seen[0].aborted).toBe(false);
    controller.abort();
    expect(seen[0].aborted).toBe(true);
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  });
});
