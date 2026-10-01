import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { JobView } from '@/contracts/teaching-loop';
import type { KnowledgePointView } from '@/contracts/knowledge';
import { SuggestionPanel } from './SuggestionPanel';

const PROFILE_ID = 'p-chat-1';

function catalog() {
  return {
    revision: 1,
    defaultChatProfileId: PROFILE_ID,
    connections: [
      {
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
        createdAt: '2026-09-30T00:00:00Z',
        updatedAt: '2026-09-30T00:00:00Z',
      },
    ],
    profiles: [
      {
        id: PROFILE_ID,
        connectionId: 'conn-1',
        displayName: '本机问答',
        modelId: 'qwen2.5:7b',
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
        createdAt: '2026-09-30T00:00:00Z',
        updatedAt: '2026-09-30T00:00:00Z',
      },
    ],
  };
}

function point(): KnowledgePointView {
  return {
    id: 'kp-1',
    subjectId: 'math',
    code: 'M.7.1',
    name: '有理数',
    description: '',
    parentId: null,
    parentCode: null,
    sortOrder: 0,
    status: 'active',
    revision: 1,
    revisionId: 'kr-1',
    version: 1,
    aliases: [],
    createdAt: '2026-09-30T00:00:00Z',
  };
}

function jobView(overrides: Partial<JobView> = {}): JobView {
  return {
    jobId: 'job-1',
    domain: 'knowledge',
    kind: 'suggestion',
    attempt: 1,
    state: 'queued',
    result: null,
    error: null,
    ...overrides,
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

function baseline(url: string, method: string): Response | null {
  if (url.endsWith('/api/v1/model-catalog')) return jsonResponse(true, 200, catalog());
  if (url.includes('/textbook-links') && method === 'GET') {
    return jsonResponse(true, 200, { items: [] });
  }
  return null;
}

/** 队列式任务状态替身：GET /workflow-jobs 依次返回给定状态，用尽后返回最后一个。 */
function jobQueueRouter(sequence: JobView[], overrides: Record<string, Handler> = {}) {
  let index = 0;
  return stubApi((url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    for (const [key, handler] of Object.entries(overrides)) {
      if (key.startsWith(`${method} `) && url.startsWith(key.slice(method.length + 1))) {
        return handler(url, init);
      }
    }
    if (url.includes('/workflow-jobs/job-1') && method === 'GET') {
      const view = sequence[Math.min(index, sequence.length - 1)];
      index += 1;
      return jsonResponse(true, 200, view);
    }
    const base = baseline(url, method);
    if (base) return base;
    return jsonResponse(false, 500, {
      code: 'UNEXPECTED_TEST_REQUEST',
      message: `${method} ${url} 未在测试路由中声明`,
    });
  });
}

function defaultRouter(overrides: Record<string, Handler> = {}) {
  return stubApi((url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    for (const [key, handler] of Object.entries(overrides)) {
      if (key.startsWith(`${method} `) && url.startsWith(key.slice(method.length + 1))) {
        return handler(url, init);
      }
    }
    const base = baseline(url, method);
    if (base) return base;
    return jsonResponse(false, 500, {
      code: 'UNEXPECTED_TEST_REQUEST',
      message: `${method} ${url} 未在测试路由中声明`,
    });
  });
}

function renderPanel(overrides: Partial<Parameters<typeof SuggestionPanel>[0]> = {}) {
  const props = {
    subjects: [{ id: 'math', label: '数学' }],
    taxonomyReady: true,
    defaultSubjectId: 'math',
    selectedPoint: null,
    onOpenBatch: vi.fn(),
    polling: { sleep: () => Promise.resolve(), now: () => 0 },
    ...overrides,
  };
  return { props, view: render(<SuggestionPanel {...props} />) };
}

/** 从零开始添加一份资料（AI 候选至少需要一份证据）。 */
async function addMaterial(text = '有理数的定义') {
  fireEvent.change(await screen.findByLabelText('新增资料文本'), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: '添加资料块' }));
}

/** 等模型目录就绪（入口可用）后点击发起。 */
async function startJob() {
  await waitFor(() => expect(screen.getByTestId('kp-suggestion-model')).toHaveTextContent('使用'));
  fireEvent.click(screen.getByRole('button', { name: /发起 AI 候选/ }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('AI 候选：任务六态、重试与卸载停止轮询', () => {
  it('queued → running → interrupted 显示中断横幅；重试后按新 attempt 收敛到 succeeded 并切批次', async () => {
    let retryCount = 0;
    const fetchMock = jobQueueRouter(
      [
        jobView({ state: 'running', attempt: 1 }),
        jobView({ state: 'interrupted', attempt: 1 }),
        jobView({
          state: 'succeeded',
          attempt: 2,
          result: { importId: 'imp-ai', candidateCount: 2 },
        }),
      ],
      {
        'POST /api/v1/knowledge-suggestion-jobs': () =>
          jsonResponse(true, 202, jobView({ state: 'queued', attempt: 1 })),
        'POST /api/v1/workflow-jobs/job-1/retry': () => {
          retryCount += 1;
          return jsonResponse(true, 200, jobView({ state: 'running', attempt: 2 }));
        },
      },
    );
    const { props } = renderPanel();

    await addMaterial();
    await startJob();

    // 发起请求带冻结的 profile id 与资料证据
    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-suggestion-jobs', 'POST')).toHaveLength(1),
    );
    const request = JSON.parse(
      String((calls(fetchMock, '/knowledge-suggestion-jobs', 'POST')[0]?.[1] as RequestInit).body),
    ) as Record<string, unknown>;
    expect(request.modelProfileId).toBe(PROFILE_ID);
    expect(request.materials).toEqual([{ id: 'm1', text: '有理数的定义' }]);
    expect(request.subjectId).toBe('math');

    // 中断：解除「进行中」并给出显式重试入口
    expect(await screen.findByTestId('kp-interrupted')).toHaveTextContent(
      '候选已中断（无执行器在跑）',
    );
    expect(screen.getByTestId('kp-suggestion-state')).toHaveTextContent('已中断');
    expect(screen.queryByText('观察中…')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /重试（沿用冻结模型）/ }));
    await waitFor(() => expect(retryCount).toBe(1));
    expect(
      JSON.parse(
        String(
          (calls(fetchMock, '/workflow-jobs/job-1/retry', 'POST')[0]?.[1] as RequestInit).body,
        ),
      ),
    ).toEqual({ domain: 'knowledge' });

    // 新 attempt（2）成功：切到生成的候选批次
    await waitFor(() => expect(props.onOpenBatch).toHaveBeenCalledWith('imp-ai'));
    expect(await screen.findByTestId('kp-suggestion-succeeded')).toHaveTextContent('imp-ai');
    expect(screen.getByTestId('kp-suggestion-state')).toHaveTextContent('已完成');
  });

  it('卸载即停止轮询：不再发起新的任务查询', async () => {
    const abortableSleep = (_ms: number, signal?: AbortSignal) =>
      new Promise<void>((_resolve, reject) => {
        signal?.addEventListener('abort', () => reject(new DOMException('已取消', 'AbortError')), {
          once: true,
        });
      });
    const fetchMock = jobQueueRouter([jobView({ state: 'running', attempt: 1 })], {
      'POST /api/v1/knowledge-suggestion-jobs': () =>
        jsonResponse(true, 202, jobView({ state: 'queued', attempt: 1 })),
    });
    const { view } = renderPanel({ polling: { sleep: abortableSleep, now: () => 0 } });

    await addMaterial();
    await startJob();
    // GET 请求不写 method（apiRequest 只在显式传入时才有），按路径片段统计
    await waitFor(() => expect(calls(fetchMock, '/workflow-jobs/job-1').length).toBe(1));

    const before = calls(fetchMock, '/workflow-jobs/job-1').length;
    view.unmount();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(calls(fetchMock, '/workflow-jobs/job-1').length).toBe(before);
  });

  it('任务的 attempt 已被接管时停止观察并如实说明，不显示旧尝试结果', async () => {
    jobQueueRouter([jobView({ state: 'running', attempt: 5 })], {
      'POST /api/v1/knowledge-suggestion-jobs': () =>
        jsonResponse(true, 202, jobView({ state: 'queued', attempt: 1 })),
    });
    renderPanel();

    await addMaterial();
    await startJob();

    expect(await screen.findByText(/该任务已被新的尝试接管/)).toBeInTheDocument();
  });

  it('模型不可用时不发起任务并禁用入口', async () => {
    const fetchMock = defaultRouter({
      'GET /api/v1/model-catalog': () =>
        jsonResponse(true, 200, { ...catalog(), defaultChatProfileId: null }),
    });
    renderPanel();

    expect(await screen.findByTestId('kp-suggestion-model')).toHaveTextContent(
      '聊天配置还没有默认模型',
    );
    expect(screen.getByRole('button', { name: /发起 AI 候选/ })).toBeDisabled();
    expect(calls(fetchMock, '/knowledge-suggestion-jobs', 'POST')).toHaveLength(0);
  });

  it('没有证据时不发请求并给出可读原因（后端语义前置）', async () => {
    const fetchMock = defaultRouter();
    renderPanel();

    await waitFor(() =>
      expect(screen.getByTestId('kp-suggestion-model')).toHaveTextContent('使用'),
    );
    fireEvent.click(screen.getByRole('button', { name: /发起 AI 候选/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('至少需要一份证据');
    expect(calls(fetchMock, '/knowledge-suggestion-jobs', 'POST')).toHaveLength(0);
  });

  it('选中知识点的教材依据不可用（503）时如实提示，可用资料文本继续', async () => {
    defaultRouter({
      'GET /api/v1/knowledge-points/kp-1/textbook-links': () =>
        jsonResponse(false, 503, {
          code: 'TEXTBOOK_EVIDENCE_UNAVAILABLE',
          message: '教材目录未装配。',
          retryable: true,
        }),
    });
    renderPanel({ selectedPoint: point() });

    expect(await screen.findByTestId('kp-suggestion-evidence-unavailable')).toHaveTextContent(
      '教材依据暂不可用（服务未就绪）',
    );
    expect(screen.getByLabelText('把选中知识点的教材依据作为证据')).toBeDisabled();
  });

  it('学科随默认筛选带出；没有学科时入口禁用并给出可读原因（不猜造学科）', async () => {
    const fetchMock = defaultRouter();
    const first = renderPanel({ defaultSubjectId: 'math' });
    expect(await screen.findByLabelText('批次学科')).toHaveValue('math');
    first.view.unmount();

    renderPanel({ defaultSubjectId: '' });
    await waitFor(() =>
      expect(screen.getByTestId('kp-suggestion-model')).toHaveTextContent('使用'),
    );
    await addMaterial();
    expect(screen.getByTestId('kp-subject-required')).toHaveTextContent('请先选择批次学科');
    const start = screen.getByRole('button', { name: /发起 AI 候选/ });
    expect(start).toBeDisabled();
    fireEvent.click(start);
    expect(calls(fetchMock, '/knowledge-suggestion-jobs', 'POST')).toHaveLength(0);
  });
});
