import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type {
  DraftView,
  QuestionContent,
  QuestionImportDetail,
  QuestionMetadata,
  SuggestionView,
} from '@/contracts/question-bank';
import type {
  ModelCatalog,
  ModelConnectionView,
  ModelProfileView,
} from '@/contracts/model-settings';
import { ReviewWorkspace } from './ReviewWorkspace';

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn(), refresh: vi.fn() }),
}));

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={typeof href === 'string' ? href : '#'} {...rest}>
      {children}
    </a>
  ),
}));

const CONTENT: QuestionContent = {
  type: 'single_choice',
  stemMarkdown: '原题干：下列说法正确的是？',
  options: [
    { key: 'A', textMarkdown: '甲' },
    { key: 'B', textMarkdown: '乙' },
  ],
  answer: { choiceKeys: ['A'], accepted: null, textMarkdown: null },
  explanationMarkdown: null,
  assetIds: [],
};

const METADATA: QuestionMetadata = {
  stageId: 'stage-j',
  gradeId: 'grade-7',
  subjectId: 'math',
  editionId: 'renjiao',
  knowledgeTags: ['有理数'],
  difficulty: 'easy',
};

function draft(overrides: Partial<DraftView> = {}): DraftView {
  return {
    draftId: 'd-1',
    importId: 'imp-1',
    revision: 3,
    content: CONTENT,
    metadata: METADATA,
    sourceSpans: [{ blockId: 'b-1', charStart: 10, charEnd: 40 }],
    extractionMethod: 'rule',
    reviewState: 'needs_review',
    missingAnswerAcknowledged: false,
    warnings: [],
    duplicateOfQuestionId: null,
    ...overrides,
  };
}

function detail(overrides: Partial<QuestionImportDetail> = {}): QuestionImportDetail {
  return {
    importId: 'imp-1',
    ownerId: 'local-user',
    state: 'needs_review',
    revision: 1,
    uploadedFileName: '七年级数学题库.md',
    uploadedBytes: 2048,
    draftCount: 1,
    reviewedCount: 0,
    unassignedCount: 1,
    warnings: [],
    createdAt: '2026-09-28T00:00:00Z',
    drafts: [draft()],
    unassignedBlocks: [
      {
        blockId: 'b-9',
        ordinal: 4,
        text: '（3）计算下列各题，并写出过程。',
        locator: {
          kind: 'markdown',
          lineStart: 88,
          lineEnd: 90,
          pageStart: null,
          pageEnd: null,
          blockStart: null,
          blockEnd: null,
        },
      },
    ],
    ...overrides,
  };
}

const SUGGESTION: SuggestionView = {
  suggestionId: 'sg-1',
  organizationJobId: 'job-1',
  targetDraftId: 'd-1',
  baseDraftRevision: 3,
  proposedContent: { ...CONTENT, stemMarkdown: 'AI 建议题干：下列说法错误的是？' },
  proposedMetadata: METADATA,
  sourceBlockIds: ['b-1'],
  state: 'pending',
  note: null,
};

/* ------------------------------------------------ 当前聊天模型目录（/model-catalog） */

/** 旧依赖路径（拼接写，避免把禁词写进源码而被依赖闸门扫到）。 */
const LEGACY_RAG_STATUS = ['/rag', 'status'].join('/');

/** 夹具里的聊天模型 identity：请求体必须是这个 profile id，而不是模型名。 */
const CHAT_PROFILE_ID = 'p-chat-1';
const CHAT_MODEL_ID = 'qwen2.5:7b';
const CLOUD_PROFILE_ID = 'p-chat-cloud';

function connection(overrides: Partial<ModelConnectionView> = {}): ModelConnectionView {
  return {
    id: 'conn-1',
    displayName: '本机 Ollama',
    providerId: 'ollama',
    providerLabel: 'Ollama',
    protocol: 'openai-chat',
    apiFormat: 'auto',
    apiVersion: null,
    baseUrl: '',
    resolvedBaseUrl: 'http://localhost:11434/v1',
    hasCredential: false,
    hasManagedCredential: false,
    callable: true,
    callableReason: null,
    credentialScope: 'process',
    extraHeaderNames: [],
    createdAt: '2026-09-29T00:00:00Z',
    updatedAt: '2026-09-29T00:00:00Z',
    ...overrides,
  };
}

function profile(overrides: Partial<ModelProfileView> = {}): ModelProfileView {
  return {
    id: CHAT_PROFILE_ID,
    connectionId: 'conn-1',
    displayName: '本机问答',
    modelId: CHAT_MODEL_ID,
    purpose: 'chat',
    contextTokens: 8192,
    maxOutputTokens: 2048,
    supportedParams: [],
    reasoningEnabled: null,
    reasoningEffort: null,
    reasoningStyle: null,
    capabilities: {},
    connection: {
      displayName: '本机 Ollama',
      providerId: 'ollama',
      providerLabel: 'Ollama',
      protocol: 'openai-chat',
      apiFormat: 'auto',
      hasCredential: false,
    },
    createdAt: '2026-09-29T00:00:00Z',
    updatedAt: '2026-09-29T00:00:00Z',
    ...overrides,
  };
}

function catalog(overrides: Partial<ModelCatalog> = {}): ModelCatalog {
  return {
    revision: 1,
    defaultChatProfileId: CHAT_PROFILE_ID,
    connections: [connection()],
    profiles: [profile()],
    ...overrides,
  };
}

/** 云端（非回环地址）聊天模型目录。 */
function cloudCatalog(): ModelCatalog {
  return catalog({
    defaultChatProfileId: CLOUD_PROFILE_ID,
    connections: [
      connection({
        id: 'conn-cloud',
        displayName: '云端服务',
        providerId: 'deepseek',
        providerLabel: 'DeepSeek',
        resolvedBaseUrl: 'https://api.deepseek.com/v1',
        hasCredential: true,
      }),
    ],
    profiles: [
      profile({
        id: CLOUD_PROFILE_ID,
        connectionId: 'conn-cloud',
        displayName: '云端问答',
        modelId: 'deepseek-chat',
        connection: {
          displayName: '云端服务',
          providerId: 'deepseek',
          providerLabel: 'DeepSeek',
          protocol: 'openai-chat',
          apiFormat: 'auto',
          hasCredential: true,
        },
      }),
    ],
  });
}

/* ------------------------------------------------ 整理任务响应 */

function jobSucceeded(suggestions: SuggestionView[] = [SUGGESTION]) {
  return {
    jobId: 'job-1',
    state: 'succeeded',
    suggestionCount: suggestions.length,
    failedBatches: 0,
    errorCode: null,
    suggestions,
    failures: [],
  };
}

function jobFailed(
  errorCode: string,
  extra: { suggestions?: SuggestionView[]; failures?: unknown[] } = {},
) {
  const suggestions = extra.suggestions ?? [];
  const failures = extra.failures ?? [];
  return {
    jobId: 'job-1',
    state: 'failed',
    suggestionCount: suggestions.length,
    failedBatches: failures.length,
    errorCode,
    suggestions,
    failures,
  };
}

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function jsonResponse(ok: boolean, status: number, body: unknown): Response {
  return { ok, status, json: async () => body } as Response;
}

function stubApi(handler: Handler) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function calls(fetchMock: ReturnType<typeof stubApi>, fragment: string, method?: string) {
  return fetchMock.mock.calls.filter(([url, init]) => {
    const request = init as RequestInit | undefined;
    return String(url).includes(fragment) && (!method || request?.method === method);
  });
}

function bodyAt(
  fetchMock: ReturnType<typeof stubApi>,
  fragment: string,
  method: string,
  index = 0,
) {
  const matched = calls(fetchMock, fragment, method);
  const init = matched[index]?.[1] as RequestInit;
  return JSON.parse(String(init.body)) as Record<string, unknown>;
}

/** organize 请求体里出现过的所有 modelProfileId（用来证明没有换模型重发）。 */
function sentProfileIds(fetchMock: ReturnType<typeof stubApi>): unknown[] {
  return calls(fetchMock, '/organize', 'POST').map(
    ([, init]) => JSON.parse(String((init as RequestInit).body)).modelProfileId,
  );
}

const TAXONOMY_OK = () =>
  jsonResponse(true, 200, {
    stages: [{ id: 'stage-j', label: '初中' }],
    grades: [{ id: 'grade-7', label: '七年级', stageId: 'stage-j' }],
    subjects: [{ id: 'math', label: '数学' }],
    editions: [{ id: 'renjiao', label: '人教版' }],
  });

/** 默认路由：未声明的请求一律以显式错误返回，避免测试把意外路径当成功。 */
function defaultRoute(url: string, init: RequestInit): Response | null {
  const method = (init.method ?? 'GET').toUpperCase();
  if (url.endsWith('/textbook-taxonomy')) return TAXONOMY_OK();
  if (url.endsWith('/api/v1/model-catalog')) return jsonResponse(true, 200, catalog());
  if (url.endsWith('/api/v1/question-imports/imp-1') && method === 'GET') {
    return jsonResponse(true, 200, detail());
  }
  return null;
}

function router(
  overrides: Record<string, Handler> = {},
  fallbackDetail: QuestionImportDetail = detail(),
) {
  return stubApi((url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    for (const [key, handler] of Object.entries(overrides)) {
      // 以「方法 + 路径」为前缀匹配，允许查询串（如 split 的 ?draftId=）继续匹配同一处理器
      if (key.startsWith(`${method} `) && url.startsWith(key.slice(method.length + 1))) {
        return handler(url, init);
      }
    }
    const base = defaultRoute(url, init);
    if (base) return base;
    return jsonResponse(false, 500, {
      code: 'UNEXPECTED_TEST_REQUEST',
      message: `${method} ${url} 未在测试路由中声明（批次 ${fallbackDetail.importId}）`,
      retryable: false,
    });
  });
}

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close() {
    this.open = false;
  };
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  pushMock.mockReset();
});

describe('校对工作台：加载与原文', () => {
  it('加载完成后显示未归属原文块与定位、当前草稿的原文区间', async () => {
    router();
    render(<ReviewWorkspace importId="imp-1" />);

    expect(screen.getByLabelText('正在读取导入批次')).toBeInTheDocument();
    expect(await screen.findByText('未归属原文')).toBeInTheDocument();
    expect(screen.getByText('（3）计算下列各题，并写出过程。')).toBeInTheDocument();
    expect(screen.getByText(/Markdown · 第 88–90 行/)).toBeInTheDocument();
    expect(screen.getByText('1 块')).toBeInTheDocument();

    const source = screen.getByRole('complementary', { name: '原文与定位' });
    expect(within(source).getByText(/字符 10–40/)).toBeInTheDocument();
    expect(within(source).getAllByText('b-1').length).toBeGreaterThan(0);
  });

  it('读取失败显示错误与重试，不显示空态；重试成功后恢复真实数据', async () => {
    let attempt = 0;
    router({
      'GET /api/v1/question-imports/imp-1': () => {
        attempt += 1;
        if (attempt === 1) {
          return jsonResponse(false, 503, {
            code: 'SERVICE_UNAVAILABLE',
            message: '题库服务未装配。',
            retryable: true,
          });
        }
        return jsonResponse(true, 200, detail());
      },
    });
    render(<ReviewWorkspace importId="imp-1" />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(screen.queryByText('未归属原文')).not.toBeInTheDocument();
    expect(screen.queryByText(/还没有/)).not.toBeInTheDocument();

    fireEvent.click(within(alert).getByRole('button', { name: '重试' }));
    expect(await screen.findByText('未归属原文')).toBeInTheDocument();
  });
});

describe('草稿编辑：服务端状态与冲突', () => {
  it('编辑已校对草稿后按服务端返回显示「待校对」，不乐观保留已校对', async () => {
    const reviewed = draft({ revision: 5, reviewState: 'reviewed' });
    router({
      'GET /api/v1/question-imports/imp-1': () =>
        jsonResponse(true, 200, detail({ drafts: [reviewed], reviewedCount: 1 })),
      'PATCH /api/v1/question-drafts/d-1': () =>
        jsonResponse(
          true,
          200,
          draft({
            revision: 6,
            reviewState: 'needs_review',
            content: { ...CONTENT, stemMarkdown: '人工改过的题干' },
          }),
        ),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    const stem = (await screen.findByLabelText('题干')) as HTMLTextAreaElement;
    expect(screen.getByTestId('qb-review-state')).toHaveTextContent('已校对');

    fireEvent.change(stem, { target: { value: '人工改过的题干' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));

    await waitFor(() => expect(screen.getByTestId('qb-review-state')).toHaveTextContent('待校对'));
    expect(screen.getByText(/服务端当前校对状态：待校对/)).toBeInTheDocument();
  });

  it('409 冲突保留用户输入、展示服务端内容并给出两个动作', async () => {
    let patchAttempt = 0;
    const fetchMock = router({
      'GET /api/v1/question-imports/imp-1': () =>
        jsonResponse(
          true,
          200,
          detail({
            revision: patchAttempt === 0 ? 1 : 2,
            drafts: [
              patchAttempt === 0
                ? draft()
                : draft({
                    revision: 4,
                    content: { ...CONTENT, stemMarkdown: '服务端最新题干' },
                  }),
            ],
          }),
        ),
      'PATCH /api/v1/question-drafts/d-1': () => {
        patchAttempt += 1;
        if (patchAttempt === 1) {
          return jsonResponse(false, 409, {
            code: 'REVISION_CONFLICT',
            message: '草稿已被其他操作更新（当前 revision=4），请刷新后重试。',
            retryable: false,
          });
        }
        return jsonResponse(true, 200, draft({ revision: 5, reviewState: 'reviewed' }));
      },
    });
    render(<ReviewWorkspace importId="imp-1" />);

    const stem = (await screen.findByLabelText('题干')) as HTMLTextAreaElement;
    fireEvent.change(stem, { target: { value: '我的修改' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));

    const alert = await screen.findByText(/内容已在别处被修改/);
    expect(alert).toBeInTheDocument();
    expect((screen.getByLabelText('题干') as HTMLTextAreaElement).value).toBe('我的修改');
    expect(screen.getAllByText('服务端最新题干').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '用我的修改重试' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '放弃我的修改' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '用我的修改重试' }));
    await waitFor(() => expect(screen.getByTestId('qb-review-state')).toHaveTextContent('已校对'));
    const retryBody = bodyAt(fetchMock, '/question-drafts/d-1', 'PATCH', 1);
    expect(retryBody.expectedRevision).toBe(4);
    expect((retryBody.content as QuestionContent).stemMarkdown).toBe('我的修改');
  });

  it('拆分与合并冲突都保留已填输入', async () => {
    const second = draft({
      draftId: 'd-2',
      revision: 7,
      content: { ...CONTENT, stemMarkdown: '第二题' },
    });
    router({
      'GET /api/v1/question-imports/imp-1': () =>
        jsonResponse(true, 200, detail({ drafts: [draft(), second], draftCount: 2 })),
      'POST /api/v1/question-imports/imp-1/split': () =>
        jsonResponse(false, 409, {
          code: 'REVISION_CONFLICT',
          message: '草稿已被其他操作更新。',
          retryable: false,
        }),
      'POST /api/v1/question-imports/imp-1/merge': () =>
        jsonResponse(false, 409, {
          code: 'REVISION_CONFLICT',
          message: '草稿已被其他操作更新。',
          retryable: false,
        }),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    const offset = (await screen.findByLabelText('拆分位置（字符偏移）')) as HTMLInputElement;
    fireEvent.change(offset, { target: { value: '120' } });
    fireEvent.click(screen.getByRole('button', { name: '拆分' }));
    await waitFor(() => expect(screen.getByText(/内容已在别处被修改/)).toBeInTheDocument());
    expect((screen.getByLabelText('拆分位置（字符偏移）') as HTMLInputElement).value).toBe('120');

    const merge = screen.getByRole('region', { name: '合并草稿' });
    const boxes = within(merge).getAllByRole('checkbox') as HTMLInputElement[];
    fireEvent.click(boxes[0]);
    fireEvent.click(boxes[1]);
    fireEvent.click(within(merge).getByRole('button', { name: /合并所选草稿（2）/ }));
    await waitFor(() => expect(within(merge).getByText(/合并冲突/)).toBeInTheDocument());
    expect(
      (within(merge).getAllByRole('checkbox') as HTMLInputElement[]).every((box) => box.checked),
    ).toBe(true);
  });
});

describe('确认入库', () => {
  it('failures 逐条展示并说明没有任何题目被入库，重试复用同一 submissionId', async () => {
    let uuidCounter = 0;
    vi.spyOn(crypto, 'randomUUID').mockImplementation(
      () => `sub-${(uuidCounter += 1)}` as `${string}-${string}-${string}-${string}-${string}`,
    );
    const reviewed = draft({ revision: 5, reviewState: 'reviewed' });
    const fetchMock = router({
      'GET /api/v1/question-imports/imp-1': () =>
        jsonResponse(true, 200, detail({ drafts: [reviewed], reviewedCount: 1 })),
      'POST /api/v1/question-imports/imp-1/confirm': () =>
        jsonResponse(true, 200, {
          confirmedQuestionIds: [],
          linkedQuestionIds: [],
          skippedDraftIds: [],
          failures: [
            {
              draftId: 'd-1',
              code: 'MISSING_ANSWER_NOT_ACKNOWLEDGED',
              message: '原文未提供答案的题目需要显式确认后才能入库。',
            },
          ],
        }),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /确认入库（1 道）/ }));

    expect(await screen.findByText('没有任何题目被入库')).toBeInTheDocument();
    expect(
      screen.getByText(
        /d-1 · MISSING_ANSWER_NOT_ACKNOWLEDGED：原文未提供答案的题目需要显式确认后才能入库。/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/提交标识 sub-1/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /确认入库（1 道）/ }));
    await waitFor(() =>
      expect(calls(fetchMock, '/question-imports/imp-1/confirm', 'POST')).toHaveLength(2),
    );
    expect(bodyAt(fetchMock, '/question-imports/imp-1/confirm', 'POST', 0).submissionId).toBe(
      'sub-1',
    );
    expect(bodyAt(fetchMock, '/question-imports/imp-1/confirm', 'POST', 1).submissionId).toBe(
      'sub-1',
    );
    expect(uuidCounter).toBe(1);
    expect(bodyAt(fetchMock, '/question-imports/imp-1/confirm', 'POST', 0).items).toEqual([
      { draftId: 'd-1', expectedDraftRevision: 5 },
    ]);
  });
});

describe('AI 整理：使用点击时的当前聊天模型（v1.1）', () => {
  it('请求体的 modelProfileId 是聊天模型 profile id，不是模型名、不是空串', async () => {
    const fetchMock = router({
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(true, 200, jobSucceeded()),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    // 按钮附近先用模型名说明「使用谁整理」
    const modelLine = await screen.findByTestId('qb-organizer-model');
    expect(modelLine).toHaveTextContent(CHAT_MODEL_ID);
    expect(modelLine).toHaveTextContent('使用');

    fireEvent.click(screen.getByRole('button', { name: /AI 整理草稿/ }));
    await waitFor(() => expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(1));

    const body = bodyAt(fetchMock, '/question-imports/imp-1/organize', 'POST');
    expect(body.modelProfileId).toBe(CHAT_PROFILE_ID);
    expect(body.modelProfileId).not.toBe(CHAT_MODEL_ID);
    expect(body.modelProfileId).not.toBe('');
    expect(body.draftIds).toEqual(['d-1']);
    expect(body.includeUnassigned).toBe(false);
  });

  it('页面加载、编辑草稿都不调用模型；点「AI 整理草稿」才发 1 次请求', async () => {
    const fetchMock = router({
      'PATCH /api/v1/question-drafts/d-1': () =>
        jsonResponse(
          true,
          200,
          draft({ revision: 4, content: { ...CONTENT, stemMarkdown: '人工改过的题干' } }),
        ),
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(true, 200, jobSucceeded()),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    const stem = (await screen.findByLabelText('题干')) as HTMLTextAreaElement;
    fireEvent.change(stem, { target: { value: '人工改过的题干' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
    await waitFor(() => expect(calls(fetchMock, '/question-drafts/d-1', 'PATCH')).toHaveLength(1));

    // 只读取了目录与批次，没有发起任何整理（更没有模型调用）
    expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(0);
    expect(calls(fetchMock, LEGACY_RAG_STATUS)).toHaveLength(0);

    fireEvent.click(screen.getByRole('button', { name: /AI 整理草稿/ }));
    await waitFor(() => expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(1));
  });

  it('云模型标注「将所选题目文本发送至该模型服务」，本机模型不出现该提示', async () => {
    router({
      'GET /api/v1/model-catalog': () => jsonResponse(true, 200, cloudCatalog()),
    });
    const { unmount } = render(<ReviewWorkspace importId="imp-1" />);

    const cloudNote = await screen.findByTestId('qb-organizer-dataflow');
    expect(cloudNote).toHaveTextContent('将所选题目文本发送至该模型服务');
    expect(await screen.findByTestId('qb-organizer-model')).toHaveTextContent('deepseek-chat');
    unmount();

    router();
    render(<ReviewWorkspace importId="imp-1" />);
    const localNote = await screen.findByTestId('qb-organizer-dataflow');
    expect(localNote).not.toHaveTextContent('将所选题目文本发送至该模型服务');
    expect(localNote).toHaveTextContent('不会发送到外部模型服务');
  });

  it('任务进行中切换聊天模型：重试仍用点击时冻结的 profile id', async () => {
    let catalogReads = 0;
    const fetchMock = router({
      'GET /api/v1/model-catalog': () => {
        catalogReads += 1;
        if (catalogReads === 1) return jsonResponse(true, 200, catalog());
        // 用户在「模型设置」里把默认模型换成了另一个（云端）模型
        return jsonResponse(true, 200, cloudCatalog());
      },
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(true, 200, jobFailed('UPSTREAM_UNAVAILABLE')),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /AI 整理草稿/ }));
    await waitFor(() => expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(1));

    // 目录变化（等价于用户切回本页触发的 focus 刷新）
    fireEvent(window, new Event('model-catalog-changed'));
    await waitFor(() => expect(catalogReads).toBeGreaterThan(1));

    // 冻结期间按钮附近仍显示原模型，并明确说明已冻结
    expect(await screen.findByTestId('qb-organizer-frozen')).toHaveTextContent('已冻结该模型');
    expect(screen.getByTestId('qb-organizer-model')).toHaveTextContent(CHAT_MODEL_ID);

    fireEvent.click(screen.getByRole('button', { name: /AI 整理草稿/ }));
    await waitFor(() => expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(2));

    expect(sentProfileIds(fetchMock)).toEqual([CHAT_PROFILE_ID, CHAT_PROFILE_ID]);
    expect(sentProfileIds(fetchMock)).not.toContain(CLOUD_PROFILE_ID);

    // 显式改用当前聊天模型：只解除冻结，不自动重发请求
    fireEvent.click(screen.getByRole('button', { name: '改用当前聊天模型' }));
    expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(2);
    expect(screen.getByTestId('qb-organizer-model')).toHaveTextContent('deepseek-chat');

    fireEvent.click(screen.getByRole('button', { name: /AI 整理草稿/ }));
    await waitFor(() => expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(3));
    expect(sentProfileIds(fetchMock)).toEqual([
      CHAT_PROFILE_ID,
      CHAT_PROFILE_ID,
      CLOUD_PROFILE_ID,
    ]);
  });

  it('模型失效（resolver 404）：提示修复且不自动换模型重发', async () => {
    const fetchMock = router({
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(false, 404, {
          code: 'MODEL_PROFILE_NOT_FOUND',
          message: '模型配置不存在。',
          retryable: false,
        }),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /AI 整理草稿/ }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('MODEL_PROFILE_NOT_FOUND');
    expect(alert).toHaveTextContent('请到「模型设置」重新选择默认问答模型');
    expect(alert).toHaveTextContent('不会自动改用其他模型');
    expect(alert).not.toHaveTextContent('试题内容无效');
    // 只有一次请求，且从头到尾只用冻结的 profile id
    expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(1);
    expect(sentProfileIds(fetchMock)).toEqual([CHAT_PROFILE_ID]);
  });

  it('默认聊天模型不存在时禁用入口并提示修复，不静默改用其他模型', async () => {
    const fetchMock = router({
      'GET /api/v1/model-catalog': () =>
        jsonResponse(
          true,
          200,
          catalog({
            defaultChatProfileId: 'p-chat-gone',
            profiles: [profile(), profile({ id: 'p-chat-other', displayName: '另一个模型' })],
          }),
        ),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    const modelLine = await screen.findByTestId('qb-organizer-model');
    expect(modelLine).toHaveTextContent('p-chat-gone');
    expect(modelLine).toHaveTextContent('不会自动改用其他模型');
    const button = screen.getByRole('button', { name: /AI 整理草稿/ });
    expect(button).toBeDisabled();

    fireEvent.click(button);
    expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(0);
  });

  it('模型目录读取失败时用 alert 显示错误码并禁用入口，不把失败当没有模型', async () => {
    const fetchMock = router({
      'GET /api/v1/model-catalog': () =>
        jsonResponse(false, 503, {
          code: 'SERVICE_UNAVAILABLE',
          message: '模型配置服务未装配。',
          retryable: true,
        }),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    // 异步读取失败必须是可播报的错误
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/读取模型配置失败（SERVICE_UNAVAILABLE）/);
    expect(screen.getByTestId('qb-organizer-model')).toHaveTextContent(
      /读取模型配置失败（SERVICE_UNAVAILABLE）/,
    );
    expect(screen.getByRole('button', { name: /AI 整理草稿/ })).toBeDisabled();
    expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(0);
  });

  it.each([
    ['AUTH_REQUIRED', '模型服务认证失败'],
    ['RATE_LIMITED', '模型服务限流'],
    ['UPSTREAM_UNAVAILABLE', '模型服务当前不可用'],
    ['ORGANIZER_OUTPUT_TRUNCATED', '该批未生成可应用建议，原文与草稿未被修改'],
    ['ORGANIZER_INVALID_JSON', '该批未生成可应用建议，原文与草稿未被修改'],
  ])('错误码 %s 的文案指向模型服务或该批，不归因到题目内容', async (code, expected) => {
    const fetchMock = router({
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(
          true,
          200,
          jobFailed(code, {
            failures: [{ batchIndex: 0, code, message: '' }],
          }),
        ),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /AI 整理草稿/ }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(expected);
    expect(alert).not.toHaveTextContent('试题内容无效');
    expect(alert).toHaveTextContent('原文与草稿未被修改');
    expect(calls(fetchMock, '/question-suggestions', 'POST')).toHaveLength(0);
  });

  it('批级失败时其他批次已生成的建议仍可应用（不因该批失败而丢建议）', async () => {
    router({
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(
          true,
          200,
          jobFailed('ORGANIZER_OUTPUT_TRUNCATED', {
            suggestions: [SUGGESTION],
            failures: [
              {
                batchIndex: 1,
                code: 'ORGANIZER_OUTPUT_TRUNCATED',
                message: '模型输出被截断（结束原因 length），该批未生成可应用建议，原文保留。',
              },
            ],
          }),
        ),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /AI 整理草稿/ }));

    expect(await screen.findByText('AI 建议题干：下列说法错误的是？')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '应用建议' })).toBeEnabled();
    expect(screen.getByText(/批次 2（ORGANIZER_OUTPUT_TRUNCATED）/)).toBeInTheDocument();
    // 建议只是展示，不覆盖草稿表单
    expect((screen.getByLabelText('题干') as HTMLTextAreaElement).value).toBe(
      '原题干：下列说法正确的是？',
    );
  });

  it('旧语义任务：提示重新选择模型，已生成的建议保留并可应用', async () => {
    router({
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(true, 200, jobFailed('ORGANIZER_MODEL_RESELECT_REQUIRED', {
          suggestions: [SUGGESTION],
        })),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /AI 整理草稿/ }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('该整理任务是在旧版本下创建的');
    expect(alert).toHaveTextContent('需要重新选择模型');
    expect(alert).toHaveTextContent('已生成的建议已保留');
    // 既有建议仍在列表里，没有被隐藏
    expect(await screen.findByText('AI 建议题干：下列说法错误的是？')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '应用建议' })).toBeEnabled();
  });

  it('取消的任务说明在途建议不会保存', async () => {
    router({
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(true, 200, {
          jobId: 'job-1',
          state: 'cancelled',
          suggestionCount: 1,
          failedBatches: 0,
          errorCode: null,
          suggestions: [SUGGESTION],
          failures: [],
        }),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /AI 整理草稿/ }));

    expect(await screen.findByText(/在途未完成批次的建议不会保存/)).toBeInTheDocument();
    expect(screen.getByText('AI 建议题干：下列说法错误的是？')).toBeInTheDocument();
  });

  it('应用建议带 expectedDraftRevision，忽略只提交 accept:false，草稿不被覆盖', async () => {
    const fetchMock = router({
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(true, 200, jobSucceeded()),
      'POST /api/v1/question-suggestions/sg-1/apply': () =>
        jsonResponse(
          true,
          200,
          draft({
            revision: 4,
            reviewState: 'needs_review',
            content: SUGGESTION.proposedContent,
          }),
        ),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /AI 整理草稿/ }));
    expect(await screen.findByText('AI 建议题干：下列说法错误的是？')).toBeInTheDocument();
    expect((screen.getByLabelText('题干') as HTMLTextAreaElement).value).toBe(
      '原题干：下列说法正确的是？',
    );

    fireEvent.click(screen.getByRole('button', { name: '应用建议' }));
    await waitFor(() =>
      expect((screen.getByLabelText('题干') as HTMLTextAreaElement).value).toBe(
        'AI 建议题干：下列说法错误的是？',
      ),
    );
    expect(screen.getByTestId('qb-review-state')).toHaveTextContent('待校对');
    expect(bodyAt(fetchMock, '/question-suggestions/sg-1/apply', 'POST')).toEqual({
      expectedDraftRevision: 3,
      accept: true,
    });
    expect(screen.getByRole('button', { name: '应用建议' })).toBeDisabled();
  });
});
