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

const TAXONOMY_OK = () =>
  jsonResponse(true, 200, {
    stages: [{ id: 'stage-j', label: '初中' }],
    grades: [{ id: 'grade-7', label: '七年级', stageId: 'stage-j' }],
    subjects: [{ id: 'math', label: '数学' }],
    editions: [{ id: 'renjiao', label: '人教版' }],
  });

/** `/rag/status`：AI 整理的本机模型来源（v1.1 契约）。 */
export function ragStatus(
  summarization: {
    available: boolean;
    reason: string | null;
    model: string | null;
    providerUrl?: string | null;
  } = { available: true, reason: null, model: 'qwen2.5:7b' },
): Response {
  return jsonResponse(true, 200, {
    retrieval: {
      available: true,
      reason: null,
      vectorStore: true,
      queryEmbedding: true,
      denseLimit: 50,
      lexicalLimit: 50,
      rrfK: 60,
    },
    summarization: {
      available: summarization.available,
      reason: summarization.reason,
      model: summarization.model,
      providerUrl: summarization.providerUrl ?? 'http://127.0.0.1:11434',
    },
    sourceAccess: { available: true, reason: null, verifiesHash: true },
    scope: { ready: true, reason: null, selection: null },
    generation: null,
    humanQuality: 'not_run',
  });
}

const UUID_SHAPE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** 默认路由：未声明的请求一律以显式错误返回，避免测试把意外路径当成功。 */
function defaultRoute(url: string, init: RequestInit): Response | null {
  const method = (init.method ?? 'GET').toUpperCase();
  if (url.endsWith('/textbook-taxonomy')) return TAXONOMY_OK();
  if (url.endsWith('/api/v1/rag/status')) return ragStatus();
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

describe('AI 整理建议（v1.1：只用本机模型）', () => {
  it('建议先展示不覆盖草稿；发出的 modelProfileId 是本机模型名而不是聊天 profileId', async () => {
    const fetchMock = router({
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(true, 200, {
          jobId: 'job-1',
          state: 'succeeded',
          suggestionCount: 1,
          failedBatches: 0,
          errorCode: null,
          suggestions: [SUGGESTION],
        }),
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

    // 本机模型状态来自 /rag/status（默认路由），界面如实显示模型名
    expect(await screen.findByTestId('qb-organizer-model')).toHaveTextContent(
      '使用本机模型 qwen2.5:7b',
    );
    fireEvent.click(screen.getByRole('button', { name: /AI 整理草稿/ }));

    expect(await screen.findByText('AI 建议题干：下列说法错误的是？')).toBeInTheDocument();
    // 建议只是展示，草稿表单未被覆盖
    expect((screen.getByLabelText('题干') as HTMLTextAreaElement).value).toBe(
      '原题干：下列说法正确的是？',
    );
    const organizeBody = bodyAt(fetchMock, '/question-imports/imp-1/organize', 'POST');
    expect(organizeBody.modelProfileId).toBe('qwen2.5:7b');
    expect(String(organizeBody.modelProfileId)).not.toMatch(UUID_SHAPE);

    fireEvent.click(screen.getByRole('button', { name: '应用建议' }));

    await waitFor(() =>
      expect((screen.getByLabelText('题干') as HTMLTextAreaElement).value).toBe(
        'AI 建议题干：下列说法错误的是？',
      ),
    );
    expect(screen.getByTestId('qb-review-state')).toHaveTextContent('待校对');
    const applyBody = bodyAt(fetchMock, '/question-suggestions/sg-1/apply', 'POST');
    expect(applyBody).toEqual({ expectedDraftRevision: 3, accept: true });
    expect(screen.getByRole('button', { name: '应用建议' })).toBeDisabled();
  });

  it('本机模型未报告名称时传空串（服务端默认），仍不是 UUID', async () => {
    const fetchMock = router({
      'GET /api/v1/rag/status': () => ragStatus({ available: true, reason: null, model: null }),
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(true, 200, {
          jobId: 'job-1',
          state: 'succeeded',
          suggestionCount: 0,
          failedBatches: 0,
          errorCode: null,
        }),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    expect(await screen.findByTestId('qb-organizer-model')).toHaveTextContent('使用本机默认模型');
    fireEvent.click(screen.getByRole('button', { name: /AI 整理草稿/ }));

    await waitFor(() => expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(1));
    const body = bodyAt(fetchMock, '/question-imports/imp-1/organize', 'POST');
    expect(body.modelProfileId).toBe('');
    expect(String(body.modelProfileId)).not.toMatch(UUID_SHAPE);
  });

  it('忽略建议只提交 accept:false，草稿内容不变', async () => {
    const fetchMock = router({
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(true, 200, {
          jobId: 'job-1',
          state: 'succeeded',
          suggestionCount: 1,
          failedBatches: 0,
          errorCode: null,
          suggestions: [SUGGESTION],
        }),
      'POST /api/v1/question-suggestions/sg-1/apply': () =>
        jsonResponse(true, 200, draft({ revision: 4, reviewState: 'needs_review' })),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /AI 整理草稿/ }));
    await screen.findByText('AI 建议题干：下列说法错误的是？');
    fireEvent.click(screen.getByRole('button', { name: '忽略' }));

    await waitFor(() =>
      expect(bodyAt(fetchMock, '/question-suggestions/sg-1/apply', 'POST')).toEqual({
        expectedDraftRevision: 3,
        accept: false,
      }),
    );
    expect((screen.getByLabelText('题干') as HTMLTextAreaElement).value).toBe(
      '原题干：下列说法正确的是？',
    );
  });

  it('本机概况模型不可用时按钮禁用并显示原因，且不发起整理', async () => {
    const fetchMock = router({
      'GET /api/v1/rag/status': () =>
        ragStatus({
          available: false,
          reason: '本机概括模型不可用：未在本机 Ollama 找到 qwen2.5:7b。',
          model: null,
        }),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    expect(await screen.findByTestId('qb-organizer-model')).toHaveTextContent(
      '未在本机 Ollama 找到 qwen2.5:7b',
    );
    const button = screen.getByRole('button', { name: /AI 整理草稿/ });
    expect(button).toBeDisabled();
    expect(screen.getByText(/在本机模型可用前不可点/)).toBeInTheDocument();

    fireEvent.click(button);
    expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(0);
  });

  it('/rag/status 读取失败时按钮禁用并显示错误码', async () => {
    const fetchMock = router({
      'GET /api/v1/rag/status': () =>
        jsonResponse(false, 503, {
          code: 'SERVICE_UNAVAILABLE',
          message: '教材 RAG v2 服务未装配。',
          retryable: true,
        }),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    expect(await screen.findByTestId('qb-organizer-model')).toHaveTextContent(
      /读取本机模型状态失败（SERVICE_UNAVAILABLE）/,
    );
    expect(screen.getByRole('button', { name: /AI 整理草稿/ })).toBeDisabled();
    expect(calls(fetchMock, '/organize', 'POST')).toHaveLength(0);
  });

  it('整理返回 ORGANIZER_MODEL_MISSING 时给出可读原因且草稿未变', async () => {
    const fetchMock = router({
      'POST /api/v1/question-imports/imp-1/organize': () =>
        jsonResponse(true, 200, {
          jobId: 'job-1',
          state: 'failed',
          suggestionCount: 0,
          failedBatches: 1,
          errorCode: 'ORGANIZER_MODEL_MISSING',
        }),
    });
    render(<ReviewWorkspace importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: /AI 整理草稿/ }));

    expect(await screen.findByText(/本机没有该整理模型/)).toBeInTheDocument();
    expect(screen.getByText(/草稿未被修改/)).toBeInTheDocument();
    expect((screen.getByLabelText('题干') as HTMLTextAreaElement).value).toBe(
      '原题干：下列说法正确的是？',
    );
    expect(calls(fetchMock, '/question-suggestions', 'POST')).toHaveLength(0);
  });
});
