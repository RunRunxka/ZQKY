/**
 * 「从教材提取知识点」面板（任务③）：预览清单 / 就绪与原因 / 默认勾选 / 发起与逐册六态 /
 * 未就绪 409 逐册原因 / 无默认模型时禁用。
 *
 * 断言方向（与任务卡一致）：
 * - 预览只读：没有预览就不发起；未就绪书册置灰且显示服务端原因，默认不勾选；
 * - 发起请求体带 submissionId / modelProfileId（默认问答模型）/ subjectId / 仅勾选的就绪书册；
 * - 202 只代表受理：每册一个任务卡，逐册观察六态；成功后提示「候选已进待确认批次」并给批次入口；
 * - 未就绪 409 逐册列出原因且**没有任何任务被受理**；无默认模型时入口禁用并指向「模型设置」。
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { ModelCatalog } from '@/contracts/model-settings';
import { ExtractionPanel } from './ExtractionPanel';

/* ---------------------------------------------------------------- 模型目录夹具 */

/** 云端默认档案（可用）：提取与 AI 候选同类，允许本机或云端；这里用云端。 */
function catalog(overrides: Partial<ModelCatalog> = {}): ModelCatalog {
  return {
    revision: 1,
    defaultChatProfileId: 'p-chat-1',
    connections: [
      {
        id: 'conn-1',
        displayName: 'DeepSeek 云端',
        providerId: 'deepseek',
        providerLabel: 'DeepSeek',
        protocol: 'openai-chat',
        apiFormat: 'auto',
        apiVersion: null,
        baseUrl: '',
        resolvedBaseUrl: 'https://api.deepseek.com/v1',
        hasCredential: true,
        hasManagedCredential: false,
        callable: true,
        callableReason: null,
        credentialScope: 'process',
        extraHeaderNames: [],
        createdAt: '2026-10-01T00:00:00Z',
        updatedAt: '2026-10-01T00:00:00Z',
      },
    ],
    profiles: [
      {
        id: 'p-chat-1',
        connectionId: 'conn-1',
        displayName: '云端问答',
        modelId: 'deepseek-chat',
        purpose: 'chat',
        contextTokens: 8192,
        maxOutputTokens: 2048,
        supportedParams: [],
        reasoningEnabled: null,
        reasoningEffort: null,
        reasoningStyle: null,
        capabilities: {},
        connection: {
          displayName: 'DeepSeek 云端',
          providerId: 'deepseek',
          providerLabel: 'DeepSeek',
          protocol: 'openai-chat',
          apiFormat: 'auto',
          hasCredential: true,
        },
        createdAt: '2026-10-01T00:00:00Z',
        updatedAt: '2026-10-01T00:00:00Z',
      },
    ],
    ...overrides,
  };
}

const PREVIEW = {
  subjectId: 'math',
  documents: [
    {
      documentId: 'doc-1',
      title: '七年级上册',
      gradeIds: ['grade-7'],
      revisionId: 'rev-1',
      chunkCount: 1200,
      approxChars: 58000,
      indexReady: true,
      reason: null,
    },
    {
      documentId: 'doc-2',
      title: '七年级下册',
      gradeIds: [],
      revisionId: null,
      chunkCount: 0,
      approxChars: 0,
      indexReady: false,
      reason: '该教材尚未发布有效修订。',
    },
  ],
  totalDocuments: 2,
  readyDocuments: 1,
  totalChunks: 1200,
  approxChars: 58000,
};

const SUBJECTS = [{ id: 'math', label: '数学' }];
const GRADES = [{ id: 'grade-7', label: '七年级' }];

const FAST_POLLING = { sleep: () => Promise.resolve(), now: () => Date.now() };

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
    return String(url).includes(fragment) && (!method || (request?.method ?? 'GET') === method);
  });
}

function bodyAt(fetchMock: ReturnType<typeof stubApi>, fragment: string, method: string) {
  const matched = calls(fetchMock, fragment, method);
  return JSON.parse(String((matched[0]?.[1] as RequestInit).body)) as Record<string, unknown>;
}

/** 默认路由：模型目录 + 预览 + 任务视图；未声明的请求一律显式失败。 */
function router(
  overrides: Record<string, Handler> = {},
  options: { catalog?: ModelCatalog; jobs?: Record<string, unknown> } = {},
) {
  return stubApi((url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    for (const [key, handler] of Object.entries(overrides)) {
      const prefix = key.slice(method.length + 1);
      if (key.startsWith(`${method} `) && (url === prefix || url.startsWith(`${prefix}?`))) {
        return handler(url, init);
      }
    }
    if (url.endsWith('/model-catalog')) {
      return jsonResponse(true, 200, options.catalog ?? catalog());
    }
    if (url.includes('/knowledge-extraction/preview')) {
      return jsonResponse(true, 200, PREVIEW);
    }
    for (const [jobId, view] of Object.entries(options.jobs ?? {})) {
      if (url.includes(`/workflow-jobs/${jobId}`) && method === 'GET') {
        return jsonResponse(true, 200, view);
      }
    }
    return jsonResponse(false, 500, {
      code: 'UNEXPECTED_TEST_REQUEST',
      message: `${method} ${url} 未在测试路由中声明`,
    });
  });
}

function renderPanel(props: Partial<Parameters<typeof ExtractionPanel>[0]> = {}) {
  return render(
    <ExtractionPanel
      subjects={SUBJECTS}
      grades={GRADES}
      taxonomyReady
      defaultSubjectId=""
      onOpenBatch={vi.fn()}
      polling={FAST_POLLING}
      {...props}
    />,
  );
}

/** 读取预览：选学科 → 点按钮。 */
async function loadPreview() {
  fireEvent.change(screen.getByLabelText('提取学科'), { target: { value: 'math' } });
  fireEvent.click(screen.getByRole('button', { name: /读取提取预览/ }));
  await screen.findByTestId('kp-extract-documents');
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('教材提取：预览与勾选', () => {
  it('预览展示书册表（标题/年级/分块/字数/就绪）与合计；未就绪置灰并显示原因，默认不勾选', async () => {
    router();
    renderPanel();
    await loadPreview();

    const list = screen.getByTestId('kp-extract-documents');
    expect(within(list).getByText('七年级上册')).toBeInTheDocument();
    expect(within(list).getByText('年级 七年级')).toBeInTheDocument();
    expect(within(list).getByText('分块 1,200')).toBeInTheDocument();
    expect(within(list).getByText('约 58,000 字')).toBeInTheDocument();
    expect(within(list).getByText('索引就绪')).toBeInTheDocument();

    const totals = screen.getByTestId('kp-extract-totals');
    expect(totals).toHaveTextContent('书册 2');
    expect(totals).toHaveTextContent('就绪 1');
    // 默认勾选就绪书册（自动勾选在预览数据就绪后的 effect 里，等它落到 DOM）
    await waitFor(() => expect(totals).toHaveTextContent('已勾选 1 册'));

    // 就绪书册默认勾选；未就绪书册禁用 + 原因可见
    expect(screen.getByLabelText('选择书册 七年级上册')).toBeChecked();
    const blocked = screen.getByLabelText('选择书册 七年级下册');
    expect(blocked).toBeDisabled();
    expect(blocked).not.toBeChecked();
    expect(screen.getByTestId('kp-extract-reason-doc-2')).toHaveTextContent(
      '该教材尚未发布有效修订。',
    );
  });

  it('预览读取失败显示错误与重试，不发任务；未读预览时「开始提取」禁用', async () => {
    const fetchMock = router({
      'GET /api/v1/knowledge-extraction/preview': () =>
        jsonResponse(false, 503, {
          code: 'TEXTBOOK_EVIDENCE_UNAVAILABLE',
          message: '教材目录未装配，无法预览提取来源。',
          retryable: true,
        }),
    });
    renderPanel();

    expect(screen.getByTestId('kp-extract-start')).toBeDisabled();

    fireEvent.change(screen.getByLabelText('提取学科'), { target: { value: 'math' } });
    fireEvent.click(screen.getByRole('button', { name: /读取提取预览/ }));

    const banner = await screen.findByTestId('kp-extract-preview-error');
    expect(banner).toHaveTextContent('TEXTBOOK_EVIDENCE_UNAVAILABLE');
    expect(banner).toHaveTextContent('这不代表该学科没有教材');
    expect(calls(fetchMock, '/knowledge-extraction-jobs', 'POST')).toHaveLength(0);
    expect(screen.getByTestId('kp-extract-start')).toBeDisabled();
  });
});

describe('教材提取：发起与逐册任务', () => {
  it('发起：请求体带默认问答模型与仅勾选的就绪书册；202 后逐册观察六态并给批次入口', async () => {
    const onOpenBatch = vi.fn();
    const fetchMock = router(
      {
        'POST /api/v1/knowledge-extraction-jobs': () =>
          jsonResponse(true, 202, [
            {
              jobId: 'job-1',
              domain: 'knowledge',
              kind: 'suggestion',
              attempt: 0,
              state: 'queued',
              result: null,
              error: null,
            },
          ]),
      },
      {
        jobs: {
          'job-1': {
            jobId: 'job-1',
            domain: 'knowledge',
            kind: 'suggestion',
            attempt: 1,
            state: 'succeeded',
            result: { importId: 'imp-ai-1', candidateCount: 8 },
            error: null,
          },
        },
      },
    );
    renderPanel({ onOpenBatch, defaultSubjectId: 'math' });
    await loadPreview();

    fireEvent.click(screen.getByTestId('kp-extract-start'));

    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-extraction-jobs', 'POST')).toHaveLength(1),
    );
    const body = bodyAt(fetchMock, '/knowledge-extraction-jobs', 'POST');
    expect(body.modelProfileId).toBe('p-chat-1');
    expect(body.subjectId).toBe('math');
    expect(body.documentIds).toEqual(['doc-1']);
    expect(typeof body.submissionId).toBe('string');
    expect(String(body.submissionId)).not.toBe('');

    // 每册一个任务卡：观察六态后显示成功与候选数
    const jobCard = await screen.findByTestId('kp-extract-job-job-1');
    await waitFor(() =>
      expect(screen.getByTestId('kp-extract-state-job-1')).toHaveTextContent('已完成'),
    );
    expect(jobCard).toHaveTextContent('候选 8 条');
    expect(jobCard).toHaveTextContent('候选批次 imp-ai-1');

    const summary = await screen.findByTestId('kp-extract-summary');
    expect(summary).toHaveTextContent('候选已进待确认批次，去「表格导入」页签校对入库');
    fireEvent.click(within(summary).getByTestId('kp-extract-open-imp-ai-1'));
    expect(onOpenBatch).toHaveBeenCalledWith('imp-ai-1');
  });

  it('未就绪书册 409：逐册列出原因且没有任务被受理（不头前移到成功）', async () => {
    const fetchMock = router({
      'POST /api/v1/knowledge-extraction-jobs': () =>
        jsonResponse(false, 409, {
          code: 'KNOWLEDGE_EXTRACTION_NOT_READY',
          message: '以下教材尚未就绪，无法发起提取：七年级下册。',
          retryable: false,
          details: {
            documents: [
              { documentId: 'doc-2', title: '七年级下册', reason: '该教材尚未发布有效修订。' },
            ],
          },
        }),
    });
    renderPanel({ defaultSubjectId: 'math' });
    await loadPreview();

    fireEvent.click(screen.getByTestId('kp-extract-start'));

    const banner = await screen.findByTestId('kp-extract-not-ready');
    expect(banner).toHaveTextContent('本次没有受理任何任务');
    expect(banner).toHaveTextContent('七年级下册：该教材尚未发布有效修订。');
    expect(await screen.findByTestId('kp-extract-error')).toHaveTextContent(
      'KNOWLEDGE_EXTRACTION_NOT_READY',
    );
    expect(screen.queryByTestId('kp-extract-job-job-1')).not.toBeInTheDocument();
    expect(calls(fetchMock, '/workflow-jobs')).toHaveLength(0);
  });

  it('没有默认问答模型时禁用入口并指向「模型设置」', async () => {
    const fetchMock = router(
      {},
      { catalog: catalog({ defaultChatProfileId: null, profiles: [] }) },
    );
    renderPanel({ defaultSubjectId: 'math' });

    const modelLine = await screen.findByTestId('kp-extract-model');
    expect(modelLine).toHaveTextContent('请到「模型设置」选择默认问答模型');
    expect(within(modelLine).getByRole('link', { name: '去设置默认问答模型' })).toHaveAttribute(
      'href',
      '/settings#models',
    );
    await loadPreview();
    expect(screen.getByTestId('kp-extract-start')).toBeDisabled();
    expect(calls(fetchMock, '/knowledge-extraction-jobs', 'POST')).toHaveLength(0);
  });
});
