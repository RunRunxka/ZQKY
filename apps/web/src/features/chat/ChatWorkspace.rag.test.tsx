import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChatWorkspace } from './ChatWorkspace';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
import type { RagResultV2, ScopeSnapshot } from './model/rag-v2';

vi.mock('@/features/chat/vendor/thinking-orbs', () => ({ ThinkingOrb: () => null }));
vi.mock('next/navigation', () => ({ usePathname: () => '/chat', useRouter: () => ({ push: vi.fn() }) }));

/** 模型目录按用例配置：详解需要当前聊天模型；缺省视为无云模型配置 */
const catalogState = vi.hoisted(() => ({ catalog: null as unknown }));
vi.mock('@/features/model-settings/useModelCatalog', () => ({
  useModelCatalog: () => ({
    catalog: catalogState.catalog,
    loading: false,
    error: catalogState.catalog ? null : '没有云模型配置',
    refresh: vi.fn(),
  }),
}));
vi.mock('@/services/chat-repository', async (original) => {
  const actual = await original<typeof import('@/services/chat-repository')>();
  return { ...actual, createIdbChatRepository: () => actual.createMemoryChatRepository() };
});

const selection = { gradeId: 'g1', subjectId: 's1', editionId: 'e1', documentIds: ['d1'] };
const scope: ScopeSnapshot = {
  schemaVersion: 2,
  selection,
  documents: [{ documentId: 'd1', documentRevisionId: 'r1', metadataRevisionId: 'm1' }],
  embeddingGenerationId: 'gen-1',
  scopeHash: 'a'.repeat(64),
};
const result: RagResultV2 = {
  contractVersion: 2,
  resultId: 'res-1',
  status: 'ok',
  scopeSnapshot: scope,
  points: [{ pointId: 'p1', title: '集合表示', summary: '列举法或描述法。', evidenceIds: ['ev-1'] }],
  evidence: [
    {
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
        kind: 'markdown',
        lineStart: 10,
        lineEnd: 12,
        pageStart: null,
        pageEnd: null,
        blockStart: null,
        blockEnd: null,
      },
      isSuperseded: false,
    },
  ],
  reason: null,
};

const followUpCard = {
  interactionId: 'i1',
  status: 'waiting',
  intro: '可继续追问细节，或跳过结束本轮。',
  questions: [
    {
      questionId: 'textbook-follow-up',
      header: '继续追问',
      prompt: '定位是否符合题意？',
      options: [{ label: '细讲解题思路' }, { label: '重新核对知识点' }],
      multiSelect: false,
      allowFreeText: true,
    },
  ],
};

const ragStatus = (over: Record<string, unknown> = {}) => ({
  retrieval: {
    denseLimit: 50,
    lexicalLimit: 50,
    rrfK: 60,
    vectorStore: true,
    queryEmbedding: true,
    available: true,
    reason: null,
  },
  summarization: { available: true, reason: null, model: 'qwen2.5:7b', providerUrl: 'http://127.0.0.1:11434' },
  sourceAccess: { available: true, reason: null, verifiesHash: true },
  scope: { ready: true, reason: null, selection },
  generation: null,
  humanQuality: 'not_run',
  ...over,
});

type Route = (url: string, init?: RequestInit) => Response | Promise<Response> | undefined;

function installFetch(routes: Route) {
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    const handled = routes(url, init);
    if (handled) return await handled;
    throw new Error(`不应调用 ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

/** 默认路由：范围就绪 + 服务可用；可覆盖单条 */
function defaultRoutes(over: Partial<Record<string, Route>> = {}) {
  const base: Record<string, Route> = {
    '/api/v1/teaching-settings': () =>
      Response.json({ ownerId: 'system', selection, revision: 1, updatedAt: null, scopeReady: true, scopeReason: null }),
    '/api/v1/textbook-taxonomy': () =>
      Response.json({
        stages: [{ id: 'st-1', label: '高中' }],
        grades: [{ id: 'g1', label: '高一', stageId: 'st-1' }],
        subjects: [{ id: 's1', label: '数学' }],
        editions: [{ id: 'e1', label: '人教A版' }],
      }),
    '/api/v1/rag/status': () => Response.json(ragStatus()),
  };
  const merged = { ...base, ...over };
  return (url: string, init?: RequestInit) => merged[url]?.(url, init);
}

async function openRag() {
  window.matchMedia = vi.fn().mockReturnValue({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
  render(
    <NavigationPreference>
      <ChatWorkspace />
    </NavigationPreference>,
  );
  fireEvent.click(screen.getByRole('button', { name: /^选择业务能力，当前：/ }));
  fireEvent.click(screen.getByRole('button', { name: /^RAG 模式/ }));
  const input = screen.getByRole('textbox', { name: '输入问题' });
  await waitFor(() => expect(input).not.toBeDisabled());
  return input;
}

beforeEach(() => {
  catalogState.catalog = null;
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('教材入口与 v2 追问/详解界面', () => {
  it('真实范围随请求发送；结果结构化展示、卡片可答并确认；终态后可发起详解', async () => {
    catalogState.catalog = {
      revision: 1,
      defaultChatProfileId: 'test-p',
      profiles: [
        {
          id: 'test-p',
          purpose: 'chat',
          modelId: 'test-m',
          displayName: '测试模型',
          connectionId: 'test-c',
          connection: { hasCredential: true },
          contextTokens: 8000,
          maxOutputTokens: 2048,
        },
      ],
      connections: [],
    };
    let sink!: ReadableStreamDefaultController<Uint8Array>;
    let turn: { sessionId: string; turnId: string } | null = null;
    let seq = 0;
    const push = (name: string, payload: object = {}) =>
      sink.enqueue(
        new TextEncoder().encode(
          `id: ${++seq}\nevent: ${name}\ndata: ${JSON.stringify({ ...turn, ...payload })}\n\n`,
        ),
      );
    const streamBodies: Record<string, unknown> = {};
    const fetcher = installFetch(
      defaultRoutes({
        '/api/v1/rag/stream': (_url, init) => {
          turn = JSON.parse(String(init?.body));
          streamBodies.stream = turn;
          const body = new ReadableStream<Uint8Array>({
            start(controller) {
              sink = controller;
            },
          });
          push('message.start', { scopeSnapshot: scope, messageId: 'm1' });
          push('rag.result', { result });
          push('text.delta', { text: '教材知识点：列举法或描述法。' });
          push('wait-user', followUpCard);
          return new Response(body, { headers: { 'content-type': 'text/event-stream' } });
        },
        '/api/v1/rag/reply': (_url, init) => {
          const reply = JSON.parse(String(init?.body));
          streamBodies.reply = reply;
          push('reply.accepted', {
            interactionId: reply.interactionId,
            submissionId: reply.submissionId,
            answers: reply.answers,
          });
          // 追问后重新定位：真实协议会再发一次 rag.result + 正文（项目既有顺序）
          push('rag.result', {
            result: {
              ...result,
              points: [
                {
                  pointId: 'p2',
                  title: '重新定位结果',
                  summary: '按补充条件重新定位后的结果。[1]',
                  evidenceIds: ['ev-1'],
                },
              ],
              presentation: { version: 'compact-v1', answerStyle: 'brief', bodyCharCount: 20 },
            },
          });
          push('text.delta', { text: '教材知识点：补充条件后的正文说明。' });
          push('message.end', { finishReason: 'stop' });
          sink.close();
          return Response.json({ accepted: true });
        },
        '/api/v1/rag/explain/stream': (_url, init) => {
          const body0 = JSON.parse(String(init?.body)) as {
            requestId: string;
            sessionId: string;
            turnId: string;
            modelProfileId: string;
          };
          streamBodies.explain = body0;
          const identity = {
            requestId: body0.requestId,
            sessionId: body0.sessionId,
            turnId: body0.turnId,
            messageId: 'em1',
            modelProfileId: body0.modelProfileId,
          };
          const encoder = new TextEncoder();
          const body = new ReadableStream<Uint8Array>({
            start(controller) {
              controller.enqueue(
                encoder.encode(
                  `event: message.start\ndata: ${JSON.stringify(identity)}\n\n`,
                ),
              );
              controller.enqueue(
                encoder.encode(
                  `event: text.delta\ndata: ${JSON.stringify({ ...identity, text: '详解：先看定义域。' })}\n\n`,
                ),
              );
              controller.enqueue(
                encoder.encode(
                  `event: message.end\ndata: ${JSON.stringify({ ...identity, finishReason: 'stop' })}\n\n`,
                ),
              );
              controller.close();
            },
          });
          return new Response(body, { headers: { 'content-type': 'text/event-stream' } });
        },
      }),
    );
    const input = await openRag();
    // 范围就绪横幅（真实读取，不是空范围）
    await screen.findByText(/本轮范围：高一 · 数学 · 人教A版 · 1 册/);
    fireEvent.change(input, { target: { value: '求函数定义域' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    await screen.findByText('教材追问');
    expect(streamBodies.stream).toMatchObject({
      question: '求函数定义域',
      afterEventId: 0,
      scope: { kind: 'selection', selection },
    });
    // 知识点回答头随结构化结果展示（紧凑视图）；来源默认折叠，条数可展开
    expect(await screen.findByText('教材知识点')).toBeInTheDocument();
    expect(screen.getByText('集合表示')).toBeInTheDocument();
    const sourceToggle = await screen.findByRole('button', { name: /查看教材依据（1 条）/ });
    expect(sourceToggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(sourceToggle);
    expect(screen.getByText('高中数学 必修一')).toBeInTheDocument();
    expect(screen.getByText(/第 10–12 行/)).toBeInTheDocument();
    expect(screen.queryByText('追问（本地模拟）')).not.toBeInTheDocument();
    // 卡片作答 → /rag/reply（带幂等 submissionId 与逐题答案）
    fireEvent.click(screen.getByRole('button', { name: /细讲解题思路/ }));
    fireEvent.click(screen.getByRole('button', { name: '继续' }));
    await waitFor(() => expect(streamBodies.reply).toBeTruthy());
    expect(streamBodies.reply).toMatchObject({
      interactionId: 'i1',
      answers: [{ questionId: 'textbook-follow-up', labels: ['细讲解题思路'], freeText: '' }],
    });
    expect((streamBodies.reply as { submissionId: string }).submissionId).toBeTruthy();
    // 追问后重新定位：新 rag.result 替换旧结果，紧凑知识点更新一次；
    // 同一份正文（content 里的渲染结果）不再作为第二遍出现在消息流里
    expect(await screen.findByText('按补充条件重新定位后的结果。')).toBeInTheDocument();
    expect(screen.queryByText('列举法或描述法。')).toBeNull();
    expect(screen.queryByText(/补充条件后的正文说明/)).toBeNull();
    // 终态后出现详解引导；选择方向 → 冻结当前聊天模型与证据发起详解
    const guidanceOption = await screen.findByRole('button', { name: /细讲解题思路/ });
    fireEvent.click(guidanceOption);
    fireEvent.click(await screen.findByRole('button', { name: /继续详解/ }));
    await waitFor(() => expect(streamBodies.explain).toBeTruthy());
    expect(streamBodies.explain).toMatchObject({
      modelProfileId: 'test-p',
      followUp: '细讲解题思路',
      originalQuestion: '求函数定义域',
      scopeSnapshot: scope,
      evidenceRefs: [{ evidenceId: 'ev-1' }],
    });
    await screen.findByText(/详解：先看定义域/);
    expect(fetcher.mock.calls.some(([url]) => url === '/api/v1/chat/stream')).toBe(false);
  });

  it('检索不可用时显示分项原因并保留输入，不切换普通聊天', async () => {
    const fetcher = installFetch(
      defaultRoutes({
        '/api/v1/rag/status': () =>
          Response.json(
            ragStatus({
              retrieval: {
                denseLimit: 50,
                lexicalLimit: 50,
                rrfK: 60,
                vectorStore: true,
                queryEmbedding: true,
                available: false,
                reason: '当前没有已发布的教材索引代。',
              },
            }),
          ),
      }),
    );
    const input = await openRag();
    await screen.findByText(/当前没有已发布的教材索引代/);
    fireEvent.change(input, { target: { value: '需要保留的题目' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    await screen.findByText(/当前没有已发布的教材索引代.*输入已保留/);
    expect(input).toHaveValue('需要保留的题目');
    expect(fetcher.mock.calls.some(([url]) => url === '/api/v1/rag/stream')).toBe(false);
    expect(fetcher.mock.calls.every(([url]) => !String(url).includes('/chat/stream'))).toBe(true);
  });

  it('范围未保存（不是读取失败）时发送前阻断并保留输入', async () => {
    const fetcher = installFetch(
      defaultRoutes({
        '/api/v1/teaching-settings': () =>
          Response.json({
            ownerId: 'system',
            selection: null,
            revision: 0,
            updatedAt: null,
            scopeReady: false,
            scopeReason: '尚未保存任教范围。',
          }),
      }),
    );
    const input = await openRag();
    await screen.findByText(/尚未保存可用的任教范围/);
    fireEvent.change(input, { target: { value: '未保存范围的题目' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    await screen.findByText(/请先在教材资料库保存任教范围。输入已保留/);
    expect(input).toHaveValue('未保存范围的题目');
    expect(fetcher.mock.calls.some(([url]) => url === '/api/v1/rag/stream')).toBe(false);
  });

  it('范围读取失败按失败处理（不是空范围）：显示错误并保留输入', async () => {
    const fetcher = installFetch(
      defaultRoutes({
        '/api/v1/teaching-settings': () =>
          Response.json({ code: 'SERVICE_UNAVAILABLE', message: '教材目录未就绪。' }, { status: 503 }),
      }),
    );
    const input = await openRag();
    await screen.findByText(/任教范围读取失败：/);
    expect(screen.getByText(/读取失败不等于没有范围/)).toBeInTheDocument();
    fireEvent.change(input, { target: { value: '读取失败时的题目' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    await screen.findByText(/任教范围读取失败：.*输入已保留/);
    expect(input).toHaveValue('读取失败时的题目');
    expect(fetcher.mock.calls.some(([url]) => url === '/api/v1/rag/stream')).toBe(false);
  });
});
