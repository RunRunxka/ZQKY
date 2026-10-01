/**
 * V00-B2 · V8 独立前端探针（自建用例，不复用实现者测试）：
 *
 * 1. 教材依据「不可用」与「没有依据」的文案区分（TextbookLinksPanel，真实组件 + 受控 mock）；
 * 2. AI 候选六态渲染 + 取消/重试路径 + attempt 守卫 + **卸载停止轮询**（SuggestionPanel）；
 * 3. 六态文案映射逐项核对（labels.ts）。
 *
 * 全部 mock 在模块边界（services/*），组件本体是真代码；不触网、不写存储。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { JobView } from '@/contracts/teaching-loop';
import type { KnowledgePointView } from '@/contracts/knowledge';
import { ApiError } from '@/services/api-client';

const mocks = {
  listTextbookLinks: vi.fn(),
  createKnowledgeSuggestionJob: vi.fn(),
  loadModelCatalog: vi.fn(),
  listDocuments: vi.fn(),
  observeJob: vi.fn(),
  cancelJob: vi.fn(),
  retryJob: vi.fn(),
};

vi.mock('@/services/knowledge-points-api', () => ({
  listTextbookLinks: (...args: unknown[]) => mocks.listTextbookLinks(...args),
  createKnowledgeSuggestionJob: (...args: unknown[]) => mocks.createKnowledgeSuggestionJob(...args),
  createTextbookLink: vi.fn(),
  deleteTextbookLink: vi.fn(),
}));
vi.mock('@/services/textbook-api', () => ({
  listDocuments: (...args: unknown[]) => mocks.listDocuments(...args),
}));
vi.mock('@/services/model-settings-api', () => ({
  loadModelCatalog: (...args: unknown[]) => mocks.loadModelCatalog(...args),
}));
vi.mock('@/services/workflow-jobs-api', () => ({
  observeJob: (...args: unknown[]) => mocks.observeJob(...args),
  cancelJob: (...args: unknown[]) => mocks.cancelJob(...args),
  retryJob: (...args: unknown[]) => mocks.retryJob(...args),
}));

import { TextbookLinksPanel } from '@/features/knowledge-points/TextbookLinksPanel';
import { SuggestionPanel } from '@/features/knowledge-points/SuggestionPanel';
import { jobStateLabel } from '@/features/knowledge-points/labels';

const PROFILE_ID = 'p-chat-v00';

function point(): KnowledgePointView {
  return {
    id: 'kp-1',
    subjectId: 'math',
    code: 'V00-KP',
    name: '函数单调性',
    description: '',
    parentId: null,
    parentCode: null,
    sortOrder: 0,
    status: 'active',
    revision: 0,
    revisionId: 'kpr-1',
    version: 1,
    aliases: [],
    createdAt: '2026-10-01T00:00:00Z',
  } as KnowledgePointView;
}

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
        resolvedBaseUrl: 'http://127.0.0.1:11434/v1',
        hasCredential: false,
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
        createdAt: '2026-10-01T00:00:00Z',
        updatedAt: '2026-10-01T00:00:00Z',
      },
    ],
  };
}

function jobView(overrides: Partial<JobView>): JobView {
  return {
    jobId: 'job-v00',
    domain: 'knowledge',
    kind: 'suggestion',
    attempt: 1,
    state: 'queued',
    result: null,
    error: null,
    ...overrides,
  } as JobView;
}

/** 可控观察句柄：把 onUpdate 暴露给用例，并记录 signal/expectedAttempt。 */
function deferredObservation() {
  const signals: AbortSignal[] = [];
  const attempts: (number | undefined)[] = [];
  let push: ((view: JobView) => void) | null = null;
  let finish: ((value: JobView | null) => void) | null = null;
  const promise = new Promise<JobView | null>((resolve) => {
    finish = resolve;
  });
  return {
    signals,
    attempts,
    promise,
    emit(view: JobView) {
      push?.(view);
    },
    end(value: JobView | null = null) {
      finish?.(value);
    },
    install() {
      mocks.observeJob.mockImplementation(
        (
          _domain: string,
          _jobId: string,
          options: { signal?: AbortSignal; expectedAttempt?: number; onUpdate?: (v: JobView) => void },
        ) => {
          if (options.signal) signals.push(options.signal);
          attempts.push(options.expectedAttempt);
          push = options.onUpdate ?? null;
          return promise;
        },
      );
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listDocuments.mockResolvedValue({ documents: [] });
  mocks.loadModelCatalog.mockResolvedValue(catalog());
  mocks.listTextbookLinks.mockResolvedValue({ items: [] });
});

afterEach(() => {
  cleanup();
});

describe('V8 教材依据：不可用 ≠ 没有依据', () => {
  it('V8.1 503 TEXTBOOK_EVIDENCE_UNAVAILABLE → 显示「暂不可用」且不显示「没有教材依据」', async () => {
    mocks.listTextbookLinks.mockRejectedValue(
      new ApiError('TEXTBOOK_EVIDENCE_UNAVAILABLE', '教材目录未装配。', 503, true),
    );
    render(<TextbookLinksPanel point={point()} onPointChanged={() => {}} />);
    const banner = await screen.findByTestId('kp-evidence-unavailable');
    expect(banner.textContent).toContain('教材依据暂不可用（服务未就绪）');
    expect(screen.queryByTestId('kp-evidence-empty')).toBeNull();
    expect(screen.queryByText(/^没有教材依据$/)).toBeNull();
  });

  it('V8.2 成功读取且 0 条 → 显示「没有教材依据」，不显示「暂不可用」', async () => {
    mocks.listTextbookLinks.mockResolvedValue({ items: [] });
    render(<TextbookLinksPanel point={point()} onPointChanged={() => {}} />);
    const empty = await screen.findByTestId('kp-evidence-empty');
    expect(empty.textContent).toContain('没有教材依据');
    expect(screen.queryByTestId('kp-evidence-unavailable')).toBeNull();
  });

  it('V8.3 其它读取错误 → 显示带错误码的失败横幅与重试，不伪装成空', async () => {
    mocks.listTextbookLinks.mockRejectedValue(new ApiError('UPSTREAM_UNAVAILABLE', '上游不可用。', 503));
    render(<TextbookLinksPanel point={point()} onPointChanged={() => {}} />);
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('教材依据读取失败（UPSTREAM_UNAVAILABLE）');
    expect(screen.queryByTestId('kp-evidence-empty')).toBeNull();
  });
});

describe('V8 AI 候选：六态与取消/重试/卸载', () => {
  async function startSuggestionPanel(observation: ReturnType<typeof deferredObservation>) {
    observation.install();
    mocks.createKnowledgeSuggestionJob.mockResolvedValue(jobView({ state: 'queued', attempt: 1 }));
    mocks.cancelJob.mockResolvedValue(jobView({ state: 'cancelled', attempt: 1 }));
    mocks.retryJob.mockResolvedValue(jobView({ state: 'queued', attempt: 2 }));
    const rendered = render(
      <SuggestionPanel
        subjects={[{ id: 'math', label: '数学' }]}
        taxonomyReady
        defaultSubjectId="math"
        selectedPoint={null}
        onOpenBatch={() => {}}
        polling={{ sleep: async () => {}, now: () => 0 }}
      />,
    );
    await screen.findByTestId('kp-suggestion-model');
    // 模型目录是异步读取的：等模型可用（否则入口是 disabled，点击不会发起任务）
    await waitFor(() =>
      expect(screen.getByText('发起 AI 候选').closest('button')).not.toBeDisabled(),
    );
    fireEvent.change(screen.getByLabelText('新增资料文本'), {
      target: { value: 'V00 探针资料：函数 f(x)=x^2。' },
    });
    fireEvent.click(screen.getByText('添加资料块'));
    fireEvent.click(screen.getByText('发起 AI 候选'));
    await waitFor(() => expect(mocks.createKnowledgeSuggestionJob).toHaveBeenCalled());
    expect(mocks.createKnowledgeSuggestionJob.mock.calls.at(-1)?.[0]).toMatchObject({
      modelProfileId: PROFILE_ID,
      subjectId: 'math',
    });
    return rendered;
  }

  it('V8.4 queued/running 显示六态文案与取消入口；取消后回到终态并可重试', async () => {
    const observation = deferredObservation();
    await startSuggestionPanel(observation);
    await waitFor(() => expect(screen.getByTestId('kp-suggestion-state').textContent).toBe('排队中'));
    observation.emit(jobView({ state: 'running', attempt: 1 }));
    await waitFor(() => expect(screen.getByTestId('kp-suggestion-state').textContent).toBe('生成中'));
    const cancel = screen.getByText('取消任务');
    fireEvent.click(cancel);
    await waitFor(() => expect(mocks.cancelJob).toHaveBeenCalledWith('knowledge', 'job-v00'));
    await waitFor(() => expect(screen.getByTestId('kp-suggestion-state').textContent).toBe('已取消'));
    expect(screen.getByText('重试（沿用冻结模型）')).toBeTruthy();
  });

  it('V8.5 重试走 retryJob 并接管新 attempt（第 2 次尝试）', async () => {
    const observation = deferredObservation();
    await startSuggestionPanel(observation);
    observation.emit(jobView({ state: 'failed', attempt: 1, error: null }));
    await waitFor(() => expect(screen.getByTestId('kp-suggestion-state').textContent).toBe('失败'));
    fireEvent.click(screen.getByText('重试（沿用冻结模型）'));
    await waitFor(() => expect(mocks.retryJob).toHaveBeenCalledWith('knowledge', 'job-v00'));
    await waitFor(() => expect(screen.getByTestId('kp-suggestion-state').textContent).toBe('排队中'));
    expect(screen.getByText('第 2 次尝试')).toBeTruthy();
    expect(observation.attempts).toContain(2);
  });

  it('V8.6 interrupted：显示「已中断」+ 重试；succeeded：显示「已完成」且无取消/重试', async () => {
    const observation = deferredObservation();
    await startSuggestionPanel(observation);
    observation.emit(jobView({ state: 'interrupted', attempt: 1 }));
    await waitFor(() => expect(screen.getByTestId('kp-suggestion-state').textContent).toBe('已中断'));
    expect(screen.getByText('重试（沿用冻结模型）')).toBeTruthy();
    expect(screen.queryByText('取消任务')).toBeNull();

    const second = deferredObservation();
    cleanup();
    await startSuggestionPanel(second);
    second.emit(jobView({ state: 'succeeded', attempt: 1, result: { importId: 'imp-1', candidateCount: 3 } }));
    await waitFor(() => expect(screen.getByTestId('kp-suggestion-state').textContent).toBe('已完成'));
    expect(screen.queryByText('取消任务')).toBeNull();
    expect(screen.queryByText('重试（沿用冻结模型）')).toBeNull();
  });

  it('V8.7 观察被 attempt 取代返回 null → 停止观察并给出说明（不把旧 attempt 当结果）', async () => {
    const observation = deferredObservation();
    await startSuggestionPanel(observation);
    observation.end(null);
    await waitFor(() =>
      expect(screen.getByText(/该任务已被新的尝试接管/)).toBeTruthy(),
    );
    expect(screen.queryByText('观察中…')).toBeNull();
  });

  it('V8.8 组件卸载 → 观察信号 abort（停止轮询；不取消任务）', async () => {
    const observation = deferredObservation();
    const rendered = await startSuggestionPanel(observation);
    await waitFor(() => expect(observation.signals.length).toBeGreaterThan(0));
    expect(observation.signals.every((signal) => !signal.aborted)).toBe(true);
    rendered.unmount();
    expect(observation.signals.every((signal) => signal.aborted)).toBe(true);
    expect(mocks.cancelJob).not.toHaveBeenCalled();
  });

  it('V8.9 六态文案映射逐项核对', () => {
    expect(jobStateLabel('queued')).toBe('排队中');
    expect(jobStateLabel('running')).toBe('生成中');
    expect(jobStateLabel('succeeded')).toBe('已完成');
    expect(jobStateLabel('failed')).toBe('失败');
    expect(jobStateLabel('cancelled')).toBe('已取消');
    expect(jobStateLabel('interrupted')).toBe('已中断');
  });
});
