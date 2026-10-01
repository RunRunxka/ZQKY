/**
 * F10-QB：AI 补题面板（六态 / 取消 / 真实重试 / 冻结模型 / 候选批次入口 / 失败文案）。
 *
 * 断言方向（任务卡 §3 F10-QB + RV01 语义）：
 * - 202 只代表接受：queued/running 期间只能显示「排队中」与取消入口，**不显示成功**；
 * - 重试收据 attempt=N（queued）→ 接受 queued(N)/running(N)/终态(N+1)；N+2 视为被接管并给说明；
 * - 重试不发送 modelProfileId（服务端沿用冻结输入与模型），也不产生第二个创建请求；
 * - 取消后没有候选批次；成功后的候选批次入口指向 `importId`，并说明候选必须人工校对。
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { ModelCatalog } from '@/contracts/model-settings';
import { GenerationPanel } from './GenerationPanel';
import { buildTaxonomyIndex } from './taxonomy';

/* ------------------------------------------------ 模型目录夹具（与 /chat 同来源） */

const CHAT_PROFILE_ID = 'p-chat-1';
const CHAT_MODEL_ID = 'qwen2.5:7b';

function catalog(overrides: Partial<ModelCatalog> = {}): ModelCatalog {
  return {
    revision: 1,
    defaultChatProfileId: CHAT_PROFILE_ID,
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
        createdAt: '2026-09-30T00:00:00Z',
        updatedAt: '2026-09-30T00:00:00Z',
      },
    ],
    ...overrides,
  };
}

const POINTS = {
  items: [
    {
      id: 'kp-1',
      subjectId: 'math',
      code: 'M1',
      name: '有理数',
      description: '',
      parentId: null,
      parentCode: null,
      sortOrder: 0,
      status: 'active',
      revision: 1,
      revisionId: 'kpr-1',
      version: 1,
      aliases: [],
      createdAt: '2026-10-01T00:00:00Z',
    },
  ],
  total: 1,
  offset: 0,
  limit: 200,
};

const TAXONOMY = buildTaxonomyIndex({
  stages: [{ id: 'stage-j', label: '初中' }],
  grades: [{ id: 'grade-7', label: '七年级', stageId: 'stage-j' }],
  subjects: [{ id: 'math', label: '数学' }],
  editions: [{ id: 'renjiao', label: '人教版' }],
});

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

function stubApi(handler: Handler) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(String(input), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function calls(fetchMock: ReturnType<typeof stubApi>, fragment: string, method?: string) {
  return fetchMock.mock.calls.filter(([url, init]) => {
    const request = init as RequestInit | undefined;
    return (
      String(url).includes(fragment) &&
      (!method || (request?.method ?? 'GET').toUpperCase() === method)
    );
  });
}

function bodyAt(fetchMock: ReturnType<typeof stubApi>, fragment: string, method: string, index = 0) {
  const matched = calls(fetchMock, fragment, method);
  return JSON.parse(String((matched[index]?.[1] as RequestInit).body)) as Record<string, unknown>;
}

function jobView(
  overrides: Partial<{
    jobId: string;
    state: string;
    attempt: number;
    result: Record<string, unknown> | null;
  }> = {},
) {
  return {
    jobId: 'job-1',
    domain: 'question',
    kind: 'generate',
    attempt: 1,
    state: 'queued',
    result: null,
    error: null,
    ...overrides,
  };
}

function defaultRoute(url: string, init: RequestInit): Response | null {
  const method = (init.method ?? 'GET').toUpperCase();
  if (url.endsWith('/api/v1/model-catalog')) return jsonResponse(catalog());
  if (url.includes('/api/v1/knowledge-points')) return jsonResponse(POINTS);
  if (!method.startsWith('GET') && url.includes('/question-generation-jobs')) return null;
  return null;
}

function router(overrides: Record<string, Handler> = {}) {
  return stubApi((url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    for (const [key, handler] of Object.entries(overrides)) {
      if (key.startsWith(`${method} `) && url.startsWith(key.slice(method.length + 1))) {
        return handler(url, init);
      }
    }
    const base = defaultRoute(url, init);
    if (base) return base;
    return jsonResponse(
      { code: 'UNEXPECTED_TEST_REQUEST', message: `${method} ${url} 未在测试路由中声明`, retryable: false },
      500,
    );
  });
}

function renderPanel(overrides: {
  onClose?: () => void;
  onOpenImport?: (importId: string) => void;
  onPublished?: () => void;
} = {}) {
  return render(
    <GenerationPanel
      taxonomy={TAXONOMY}
      onClose={overrides.onClose ?? (() => undefined)}
      onOpenImport={overrides.onOpenImport ?? (() => undefined)}
      onPublished={overrides.onPublished}
      // 观察不等待真实计时：由 fetch stub 决定读到的状态序列
      polling={{ sleep: async () => undefined }}
    />,
  );
}

async function fillValidForm() {
  fireEvent.change(await screen.findByLabelText('学科'), { target: { value: 'math' } });
  const point = await screen.findByLabelText('有理数（M1）');
  fireEvent.click(point);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('AI 补题：入口校验与请求语义', () => {
  it('提交发送点击时冻结的 profile id、学科与知识点；queued 只显示排队中，不显示成功', async () => {
    const fetchMock = router({
      'POST /api/v1/question-generation-jobs': () =>
        jsonResponse({ jobId: 'job-1', state: 'queued', attempt: 1, importId: null, candidateCount: 0, errorCode: null }, 202),
      'GET /api/v1/workflow-jobs/job-1': () =>
        new Promise<Response>(() => {
          /* 保持排队观察中 */
        }),
    });
    renderPanel();
    await fillValidForm();
    fireEvent.change(screen.getByLabelText('题数（1–10）'), { target: { value: '2' } });

    fireEvent.click(screen.getByTestId('qb-generation-submit'));

    await waitFor(() => expect(calls(fetchMock, '/question-generation-jobs', 'POST')).toHaveLength(1));
    const body = bodyAt(fetchMock, '/question-generation-jobs', 'POST');
    expect(body.modelProfileId).toBe(CHAT_PROFILE_ID);
    expect(body.modelProfileId).not.toBe(CHAT_MODEL_ID);
    expect(body.subjectId).toBe('math');
    expect(body.knowledgePointIds).toEqual(['kp-1']);
    expect(body.count).toBe(2);

    const pending = await screen.findByTestId('qb-generation-pending');
    expect(pending).toHaveTextContent('排队中不等于成功');
    expect(screen.getByTestId('qb-generation-state')).toHaveTextContent('排队中');
    expect(screen.queryByTestId('qb-generation-succeeded')).not.toBeInTheDocument();
    // 排队中提供取消入口
    expect(screen.getByTestId('qb-generation-cancel')).toBeEnabled();
  });

  it('未选学科且未选知识点：拒绝提交并说明原因，不发请求', async () => {
    const fetchMock = router({
      'POST /api/v1/question-generation-jobs': () => jsonResponse({}, 202),
    });
    renderPanel();
    await screen.findByTestId('qb-generation-submit');

    fireEvent.click(screen.getByTestId('qb-generation-submit'));

    expect(await screen.findByTestId('qb-generation-error')).toHaveTextContent('请先选择学科或至少一个知识点');
    expect(calls(fetchMock, '/question-generation-jobs', 'POST')).toHaveLength(0);
  });

  it('模型目录读取失败：入口禁用并显示错误，不当作「没有可用模型」', async () => {
    const fetchMock = router({
      'GET /api/v1/model-catalog': () =>
        jsonResponse({ code: 'SERVICE_UNAVAILABLE', message: '模型服务未装配。', retryable: true }, 503),
    });
    renderPanel();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/模型配置读取失败（SERVICE_UNAVAILABLE）/);
    expect(screen.getByTestId('qb-generation-submit')).toBeDisabled();
    expect(calls(fetchMock, '/question-generation-jobs', 'POST')).toHaveLength(0);
  });
});

describe('AI 补题：六态、取消与真实重试', () => {
  it('interrupted → 显式重试按 [N, N+1] 收敛成功并给出候选批次入口（不换模型）', async () => {
    let reads = 0;
    const fetchMock = router({
      'POST /api/v1/question-generation-jobs': () =>
        jsonResponse({ jobId: 'job-1', state: 'running', attempt: 1, importId: null, candidateCount: 0, errorCode: null }, 202),
      'GET /api/v1/workflow-jobs/job-1': () => {
        reads += 1;
        if (reads === 1) {
          return jsonResponse(jobView({ state: 'interrupted', attempt: 1 }));
        }
        if (reads === 2) return jsonResponse(jobView({ state: 'running', attempt: 2 }));
        return jsonResponse(
          jobView({
            state: 'succeeded',
            attempt: 3,
            result: { importId: 'imp-ai-1', candidateCount: 2 },
          }),
        );
      },
      'POST /api/v1/workflow-jobs/job-1/retry': () =>
        jsonResponse(jobView({ state: 'queued', attempt: 2 })),
    });
    const onOpenImport = vi.fn();
    const onPublished = vi.fn();
    renderPanel({ onOpenImport, onPublished });
    await fillValidForm();

    fireEvent.click(screen.getByTestId('qb-generation-submit'));

    // 第一次观察直接中断：显示中断说明与重试入口，不显示成功
    const interrupted = await screen.findByTestId('qb-generation-interrupted');
    expect(interrupted).toHaveTextContent('不会自动重新调用模型');
    expect(screen.queryByTestId('qb-generation-succeeded')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('qb-generation-retry'));

    const succeeded = await screen.findByTestId('qb-generation-succeeded');
    expect(succeeded).toHaveTextContent('生成 2 道待校对候选草稿');
    expect(succeeded).toHaveTextContent('AI 候选不会自动入库');
    await waitFor(() => expect(screen.getByTestId('qb-generation-state')).toHaveTextContent('已完成'));
    expect(screen.getByTestId('qb-generation-attempt')).toHaveTextContent('第 3 次尝试');
    expect(onPublished).toHaveBeenCalledTimes(1);

    // 重试只走 workflow-jobs 通道：没有第二个创建请求，也没有再发送 modelProfileId
    expect(calls(fetchMock, '/question-generation-jobs', 'POST')).toHaveLength(1);
    expect(bodyAt(fetchMock, '/workflow-jobs/job-1/retry', 'POST')).toEqual({ domain: 'question' });

    fireEvent.click(screen.getByTestId('qb-generation-import'));
    expect(onOpenImport).toHaveBeenCalledWith('imp-ai-1');
  });

  it('重试后轮询仍是 queued(N)：保持排队中，不显示成功（不把轮询次数当完成）', async () => {
    let reads = 0;
    router({
      'POST /api/v1/question-generation-jobs': () =>
        jsonResponse({ jobId: 'job-1', state: 'failed', attempt: 1, importId: null, candidateCount: 0, errorCode: 'UPSTREAM_UNAVAILABLE' }, 202),
      'GET /api/v1/workflow-jobs/job-1': () => {
        reads += 1;
        if (reads <= 5) {
          return jsonResponse(jobView({ state: 'queued', attempt: 2 }));
        }
        return new Promise<Response>(() => {
          /* 保持观察中 */
        });
      },
      'POST /api/v1/workflow-jobs/job-1/retry': () =>
        jsonResponse(jobView({ state: 'queued', attempt: 2 })),
    });
    renderPanel();
    await fillValidForm();
    fireEvent.click(screen.getByTestId('qb-generation-submit'));

    expect(await screen.findByTestId('qb-generation-failed')).toHaveTextContent('模型服务当前不可用');
    fireEvent.click(screen.getByTestId('qb-generation-retry'));

    await waitFor(() => expect(reads).toBeGreaterThanOrEqual(5));
    expect(screen.getByTestId('qb-generation-state')).toHaveTextContent('排队中');
    expect(screen.getByTestId('qb-generation-attempt')).toHaveTextContent('第 2 次尝试');
    expect(screen.queryByTestId('qb-generation-succeeded')).not.toBeInTheDocument();
  });

  it('attempt 超出 [N, N+1]：停止显示旧尝试结果并说明被新尝试接管', async () => {
    router({
      'POST /api/v1/question-generation-jobs': () =>
        jsonResponse({ jobId: 'job-1', state: 'failed', attempt: 1, importId: null, candidateCount: 0, errorCode: 'UPSTREAM_UNAVAILABLE' }, 202),
      'GET /api/v1/workflow-jobs/job-1': () =>
        jsonResponse(
          jobView({ state: 'succeeded', attempt: 4, result: { importId: 'imp-other', candidateCount: 5 } }),
        ),
      'POST /api/v1/workflow-jobs/job-1/retry': () =>
        jsonResponse(jobView({ state: 'queued', attempt: 2 })),
    });
    renderPanel();
    await fillValidForm();
    fireEvent.click(screen.getByTestId('qb-generation-submit'));
    await screen.findByTestId('qb-generation-failed');

    fireEvent.click(screen.getByTestId('qb-generation-retry'));

    const notice = await screen.findByTestId('qb-generation-observe-notice');
    expect(notice).toHaveTextContent('新的尝试接管');
    expect(screen.queryByTestId('qb-generation-succeeded')).not.toBeInTheDocument();
    expect(screen.getByTestId('qb-generation-state')).toHaveTextContent('排队中');
  });

  it('取消：协作式取消后显示取消说明，不出现成功徽标', async () => {
    const fetchMock = router({
      'POST /api/v1/question-generation-jobs': () =>
        jsonResponse({ jobId: 'job-1', state: 'running', attempt: 1, importId: null, candidateCount: 0, errorCode: null }, 202),
      'GET /api/v1/workflow-jobs/job-1': () =>
        new Promise<Response>(() => {
          /* 在途观察 */
        }),
      'POST /api/v1/workflow-jobs/job-1/cancel': () =>
        jsonResponse(jobView({ state: 'cancelled', attempt: 1 })),
    });
    renderPanel();
    await fillValidForm();
    fireEvent.click(screen.getByTestId('qb-generation-submit'));

    fireEvent.click(await screen.findByTestId('qb-generation-cancel'));
    await waitFor(() => expect(calls(fetchMock, '/workflow-jobs/job-1/cancel', 'POST')).toHaveLength(1));
    expect(await screen.findByTestId('qb-generation-cancelled')).toHaveTextContent('不会生成任何批次或草稿');
    expect(screen.queryByTestId('qb-generation-succeeded')).not.toBeInTheDocument();
    expect(screen.queryByTestId('qb-generation-import')).not.toBeInTheDocument();
  });

  it('创建失败（知识点已归档 422）：显示可读原因且没有任务视图', async () => {
    const fetchMock = router({
      'POST /api/v1/question-generation-jobs': () =>
        jsonResponse(
          { code: 'KNOWLEDGE_POINT_ARCHIVED', message: '知识点已归档，不能用于补题：kp-1。', retryable: false },
          422,
        ),
    });
    renderPanel();
    await fillValidForm();
    fireEvent.click(screen.getByTestId('qb-generation-submit'));

    const error = await screen.findByTestId('qb-generation-error');
    expect(error).toHaveTextContent('KNOWLEDGE_POINT_ARCHIVED');
    expect(error).toHaveTextContent('改选在用知识点');
    expect(error).toHaveTextContent('没有调用模型');
    expect(screen.queryByTestId('qb-generation-job')).not.toBeInTheDocument();
    expect(calls(fetchMock, '/question-generation-jobs', 'POST')).toHaveLength(1);
  });

  it('任务进行中冻结模型：排队中不可重复发起，冻结提示说明重试不会换模型', async () => {
    const fetchMock = router({
      'POST /api/v1/question-generation-jobs': () =>
        jsonResponse({ jobId: 'job-1', state: 'queued', attempt: 1, importId: null, candidateCount: 0, errorCode: null }, 202),
      'GET /api/v1/workflow-jobs/job-1': () =>
        new Promise<Response>(() => {
          /* 仍在排队 */
        }),
    });
    renderPanel();
    await fillValidForm();
    fireEvent.click(screen.getByTestId('qb-generation-submit'));

    const frozen = await screen.findByTestId('qb-generation-frozen');
    expect(frozen).toHaveTextContent('不会换成当前聊天模型');
    // 排队中不能重复点击发起（避免重复建任务）
    expect(screen.getByTestId('qb-generation-submit')).toBeDisabled();
    expect(calls(fetchMock, '/question-generation-jobs', 'POST')).toHaveLength(1);
  });
});
