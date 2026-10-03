/**
 * F10-QB：补题任务 hook（`question` 域）的六态 / 重试窗口 / StrictMode / 迟到响应回归。
 *
 * 真实 `useQuestionJob` + 真实 `observeJob`（只 stub `fetch`，不 mock 服务模块）：
 * - RV09：StrictMode 的 setup→cleanup→setup 下接管与终态回调不能永久失效；
 * - RV10：重试/取消绑定 `{jobId, attempt, 观察代次}`；reset/切换任务/卸载后迟到的成功与失败都不写状态；
 * - RV01 语义：重试收据 queued(N) 后接受 queued(N) → running/终态(N+1)；attempt ≥ N+2 视为被接管；
 *   轮询一直是 queued 就一直是排队中，**绝不**当成成功（不把轮询次数当完成）。
 */

import { StrictMode, useEffect } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { GenerationJobView } from '@/contracts/question-bank';
import type { JobView } from '@/contracts/teaching-loop';
import { useQuestionJob, type QuestionJobController } from './jobs';

function generation(overrides: Partial<GenerationJobView> = {}): GenerationJobView {
  return {
    jobId: 'job-1',
    state: 'queued',
    attempt: 1,
    importId: null,
    candidateCount: 0,
    errorCode: null,
    ...overrides,
  };
}

function view(overrides: Partial<JobView> & Pick<JobView, 'jobId' | 'state'>): JobView {
  return {
    domain: 'question',
    kind: 'generate',
    attempt: 1,
    result: null,
    error: null,
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

function stubFetch(
  handler: (url: string, init: RequestInit | undefined) => Response | Promise<Response>,
) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(String(input), init)),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function pendingResponse(): Promise<Response> {
  return new Promise<Response>(() => {});
}

function calls(fetchMock: ReturnType<typeof stubFetch>, fragment: string) {
  return fetchMock.mock.calls.filter(([url]) => String(url).includes(fragment));
}

let latest: QuestionJobController | null = null;

function Harness({ onTerminal }: { onTerminal?: (view: GenerationJobView) => void }) {
  const controller = useQuestionJob({
    onTerminal,
    // 观察不等待真实计时：测试里由 fetch stub 决定读到的状态序列
    polling: { sleep: async () => undefined },
  });
  useEffect(() => {
    latest = controller;
  });
  return (
    <div data-testid="state">
      {controller.view
        ? `${controller.view.jobId}:${controller.view.state}@${controller.view.attempt}`
        : 'null'}
      {controller.pending ? `|${controller.pending}` : ''}
      {controller.pendingLabel ? `|${controller.pendingLabel}` : ''}
      {controller.observationNotice ? '|notice' : ''}
    </div>
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  latest = null;
});

describe('首次创建：真实 queued@0 收据的首次 claim 窗口', () => {
  it('queued@0 → running@1 → succeeded@1 持续观察，终态携带候选批次', async () => {
    let reads = 0;
    let releaseTerminal!: () => void;
    const terminalGate = new Promise<Response>((resolve) => {
      releaseTerminal = () =>
        resolve(
          jsonResponse(
            view({
              jobId: 'job-1',
              state: 'succeeded',
              attempt: 1,
              result: { importId: 'imp-first', candidateCount: 1 },
            }),
          ),
        );
    });
    stubFetch(() => {
      reads += 1;
      return reads === 1
        ? jsonResponse(view({ jobId: 'job-1', state: 'running', attempt: 1 }))
        : terminalGate;
    });
    const onTerminal = vi.fn();
    render(<Harness onTerminal={onTerminal} />);

    act(() => latest!.adopt(generation({ attempt: 0 })));

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('running@1'));
    expect(latest!.observing).toBe(true);
    expect(latest!.observationNotice).toBeNull();
    expect(onTerminal).not.toHaveBeenCalled();
    await act(async () => releaseTerminal());
    await waitFor(() => expect(onTerminal).toHaveBeenCalledTimes(1));
    expect(latest!.view).toMatchObject({ state: 'succeeded', attempt: 1, importId: 'imp-first' });
    expect(latest!.observing).toBe(false);
  });

  for (const state of ['succeeded', 'failed', 'cancelled', 'interrupted'] as const) {
    it(`queued@0 → ${state}@1 收敛到真实终态，不误报接管`, async () => {
      stubFetch(() =>
        jsonResponse(
          view({
            jobId: 'job-1',
            state,
            attempt: 1,
            result: state === 'succeeded' ? { importId: 'imp-first', candidateCount: 1 } : null,
            error:
              state === 'failed'
                ? { code: 'UPSTREAM_UNAVAILABLE', message: '模型服务不可用' }
                : null,
          }),
        ),
      );
      const onTerminal = vi.fn();
      render(<Harness onTerminal={onTerminal} />);

      act(() => latest!.adopt(generation({ attempt: 0 })));

      await waitFor(() => {
        expect(onTerminal).toHaveBeenCalledTimes(1);
        expect(latest!.view).toMatchObject({
          state,
          attempt: 1,
          importId: state === 'succeeded' ? 'imp-first' : null,
          candidateCount: state === 'succeeded' ? 1 : 0,
        });
      });
      expect(latest!.observationNotice).toBeNull();
      expect(latest!.observing).toBe(false);
      if (state === 'failed') expect(latest!.view?.errorCode).toBe('UPSTREAM_UNAVAILABLE');
    });
  }

  it('queued@0 → succeeded@2 超出首次窗口，拒绝别轮候选', async () => {
    stubFetch(() =>
      jsonResponse(
        view({
          jobId: 'job-1',
          state: 'succeeded',
          attempt: 2,
          result: { importId: 'imp-other', candidateCount: 9 },
        }),
      ),
    );
    const onTerminal = vi.fn();
    render(<Harness onTerminal={onTerminal} />);

    act(() => latest!.adopt(generation({ attempt: 0 })));

    await waitFor(() => expect(latest!.observationNotice).toContain('接管'));
    expect(latest!.view).toMatchObject({
      state: 'queued',
      attempt: 0,
      importId: null,
      candidateCount: 0,
    });
    expect(latest!.observing).toBe(false);
    expect(onTerminal).not.toHaveBeenCalled();
  });

  it('已 running@1 的收据只观察 attempt 1，不接受新的 attempt 2', async () => {
    stubFetch(() =>
      jsonResponse(
        view({
          jobId: 'job-1',
          state: 'succeeded',
          attempt: 2,
          result: { importId: 'imp-other', candidateCount: 9 },
        }),
      ),
    );
    const onTerminal = vi.fn();
    render(<Harness onTerminal={onTerminal} />);

    act(() => latest!.adopt(generation({ state: 'running', attempt: 1 })));

    await waitFor(() => expect(latest!.observationNotice).toContain('接管'));
    expect(latest!.view).toMatchObject({ state: 'running', attempt: 1, importId: null });
    expect(onTerminal).not.toHaveBeenCalled();
  });
});

describe('StrictMode：接管与观察不能永久失效', () => {
  for (const strict of [false, true]) {
    const label = strict ? 'StrictMode' : '普通模式对照';
    it(`${label}：adopt 终态 → 视图生效且 onTerminal 恰好一次`, () => {
      const onTerminal = vi.fn();
      render(
        strict ? (
          <StrictMode>
            <Harness onTerminal={onTerminal} />
          </StrictMode>
        ) : (
          <Harness onTerminal={onTerminal} />
        ),
      );
      act(() =>
        latest!.adopt(generation({ state: 'succeeded', importId: 'imp-9', candidateCount: 2 })),
      );
      expect(screen.getByTestId('state')).toHaveTextContent('job-1:succeeded@1');
      expect(onTerminal).toHaveBeenCalledTimes(1);
      expect(onTerminal.mock.calls[0][0]).toMatchObject({
        state: 'succeeded',
        importId: 'imp-9',
        candidateCount: 2,
      });
    });
  }

  it('StrictMode：adopt queued 后继续观察并收敛到终态（结果字段来自任务视图）', async () => {
    let reads = 0;
    stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-1')) {
        reads += 1;
        if (reads === 1) return jsonResponse(view({ jobId: 'job-1', state: 'queued', attempt: 1 }));
        return jsonResponse(
          view({
            jobId: 'job-1',
            state: 'succeeded',
            attempt: 1,
            result: { importId: 'imp-3', candidateCount: 1 },
          }),
        );
      }
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    const onTerminal = vi.fn();
    render(
      <StrictMode>
        <Harness onTerminal={onTerminal} />
      </StrictMode>,
    );
    await act(async () => {
      latest!.adopt(generation());
    });
    await waitFor(() => expect(onTerminal).toHaveBeenCalledTimes(1));
    expect(onTerminal.mock.calls[0][0]).toMatchObject({ state: 'succeeded', importId: 'imp-3' });
    expect(screen.getByTestId('state')).toHaveTextContent('job-1:succeeded@1');
    expect(latest!.observing).toBe(false);
  });
});

describe('取消：协作式取消与在途 pending', () => {
  it('cancel 走 question 域通道；响应 cancelled 后视图收敛且不再观察', async () => {
    const fetchMock = stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-1/cancel')) {
        return jsonResponse(view({ jobId: 'job-1', state: 'cancelled', attempt: 1 }));
      }
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    const onTerminal = vi.fn();
    render(<Harness onTerminal={onTerminal} />);
    act(() => latest!.adopt(generation({ state: 'running' })));
    act(() => {
      latest!.cancel();
      latest!.cancel(); // 在途重复点击：不得再发一次
    });
    expect(calls(fetchMock, '/cancel')).toHaveLength(1);
    expect(screen.getByTestId('state')).toHaveTextContent('正在取消…');

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('cancelled'));
    expect(onTerminal).toHaveBeenCalledTimes(1);
    const cancelCall = calls(fetchMock, '/cancel')[0];
    expect(String(cancelCall?.[0])).toContain('/workflow-jobs/job-1/cancel');
    expect(JSON.parse(String((cancelCall?.[1] as RequestInit).body))).toEqual({
      domain: 'question',
    });
  });
});

describe('重试：retryObservationWindow [N, N+1]（RV01 语义）', () => {
  it('收据 queued(N) → 接受 running(N)/终态(N+1)，终态回调带 N+1', async () => {
    let reads = 0;
    const fetchMock = stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-1/retry')) {
        return jsonResponse(view({ jobId: 'job-1', state: 'queued', attempt: 2 }));
      }
      if (url.includes('/workflow-jobs/job-1')) {
        reads += 1;
        if (reads === 1)
          return jsonResponse(view({ jobId: 'job-1', state: 'running', attempt: 2 }));
        return jsonResponse(
          view({
            jobId: 'job-1',
            state: 'succeeded',
            attempt: 3,
            result: { importId: 'imp-7', candidateCount: 2 },
          }),
        );
      }
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    const onTerminal = vi.fn();
    render(<Harness onTerminal={onTerminal} />);
    act(() =>
      latest!.adopt(generation({ state: 'interrupted', attempt: 1, errorCode: 'INTERRUPTED' })),
    );
    onTerminal.mockClear();

    await act(async () => {
      latest!.retry();
    });
    await waitFor(() => expect(onTerminal).toHaveBeenCalledTimes(1));
    expect(onTerminal.mock.calls[0][0]).toMatchObject({
      state: 'succeeded',
      attempt: 3,
      importId: 'imp-7',
      candidateCount: 2,
    });
    expect(screen.getByTestId('state')).toHaveTextContent('job-1:succeeded@3');
    expect(calls(fetchMock, '/workflow-jobs/job-1?')).toHaveLength(2);
  });

  it('轮询持续 queued(N) 只是排队中：不显示成功、不回调终态（不把轮询当完成）', async () => {
    let reads = 0;
    stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-1/retry')) {
        return jsonResponse(view({ jobId: 'job-1', state: 'queued', attempt: 2 }));
      }
      if (url.includes('/workflow-jobs/job-1')) {
        reads += 1;
        // 前 6 次都是 queued(N)：调度慢 ≠ 成功；之后挂起（仍在观察）
        if (reads <= 6) return jsonResponse(view({ jobId: 'job-1', state: 'queued', attempt: 2 }));
        return pendingResponse();
      }
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    const onTerminal = vi.fn();
    render(<Harness onTerminal={onTerminal} />);
    act(() => latest!.adopt(generation({ state: 'failed', attempt: 1 })));
    onTerminal.mockClear();

    await act(async () => {
      latest!.retry();
    });
    await waitFor(() => expect(reads).toBeGreaterThanOrEqual(6));
    expect(onTerminal).not.toHaveBeenCalled();
    expect(latest!.view?.state).toBe('queued');
    expect(latest!.view?.attempt).toBe(2);
    expect(latest!.observing).toBe(true);
    expect(screen.getByTestId('state')).not.toHaveTextContent('succeeded');
  });

  it('attempt ≥ N+2（被更新的尝试接管）：停止观察并给说明，不认别轮结果', async () => {
    stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-1/retry')) {
        return jsonResponse(view({ jobId: 'job-1', state: 'queued', attempt: 2 }));
      }
      if (url.includes('/workflow-jobs/job-1')) {
        return jsonResponse(
          view({ jobId: 'job-1', state: 'succeeded', attempt: 4, result: { candidateCount: 9 } }),
        );
      }
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    const onTerminal = vi.fn();
    render(<Harness onTerminal={onTerminal} />);
    act(() => latest!.adopt(generation({ state: 'failed', attempt: 1 })));
    onTerminal.mockClear();

    await act(async () => {
      latest!.retry();
    });
    await waitFor(() => expect(latest!.observationNotice).not.toBeNull());
    expect(latest!.observationNotice).toContain('接管');
    expect(latest!.view?.state).toBe('queued');
    expect(latest!.view?.attempt).toBe(2);
    expect(latest!.view?.candidateCount).toBe(0);
    expect(onTerminal).not.toHaveBeenCalled();
  });
});

describe('迟到响应不污染新任务（RV10）', () => {
  for (const action of ['retry', 'cancel'] as const) {
    for (const outcome of ['success', 'failure'] as const) {
      for (const invalidation of ['switch', 'unmount'] as const) {
        it(`${invalidation} 后旧 ${action} 的迟到 ${outcome} 不更新状态或终态回调`, async () => {
          let release!: () => void;
          const actionGate = new Promise<Response>((resolve) => {
            release = () =>
              resolve(
                outcome === 'success'
                  ? jsonResponse(
                      view({
                        jobId: 'job-old',
                        state: action === 'cancel' ? 'cancelled' : 'queued',
                        attempt: 1,
                      }),
                    )
                  : jsonResponse({ code: 'REVISION_CONFLICT', message: '旧操作已失效' }, 409),
              );
          });
          stubFetch((url) => (url.includes(`/job-old/${action}`) ? actionGate : pendingResponse()));
          const onTerminal = vi.fn();
          const ui = render(<Harness onTerminal={onTerminal} />);
          act(() =>
            latest!.adopt(
              generation({
                jobId: 'job-old',
                state: action === 'cancel' ? 'running' : 'failed',
                attempt: 1,
              }),
            ),
          );
          onTerminal.mockClear();
          act(() => latest![action]());
          expect(latest!.pending).toBe(action);

          if (invalidation === 'switch') {
            act(() => {
              latest!.reset();
              latest!.adopt(generation({ jobId: 'job-new', attempt: 0 }));
            });
          } else {
            ui.unmount();
          }
          const before = latest!.view;
          const pendingBefore = latest!.pending;

          await act(async () => release());

          expect(latest!.view).toBe(before);
          expect(latest!.pending).toBe(pendingBefore);
          expect(latest!.actionError).toBeNull();
          expect(onTerminal).not.toHaveBeenCalled();
          if (invalidation === 'switch') {
            expect(screen.getByTestId('state')).toHaveTextContent('job-new:queued@0');
          }
        });
      }
    }
  }

  it('reset/接管新任务后，迟到的旧 retry 成功不接管新任务', async () => {
    let releaseRetry!: (body: JobView) => void;
    const retryGate = new Promise<Response>((resolve) => {
      releaseRetry = (body) => resolve(jsonResponse(body));
    });
    const fetchMock = stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-old/retry')) return retryGate;
      if (url.includes('/workflow-jobs/job-new')) return pendingResponse();
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    render(<Harness />);

    act(() => latest!.adopt(generation({ jobId: 'job-old', state: 'failed', attempt: 1 })));
    act(() => latest!.retry());
    expect(calls(fetchMock, '/retry')).toHaveLength(1);

    await act(async () => {
      latest!.reset();
      latest!.adopt(generation({ jobId: 'job-new', state: 'queued', attempt: 1 }));
    });
    expect(screen.getByTestId('state')).toHaveTextContent('job-new:queued@1');

    await act(async () => {
      releaseRetry(view({ jobId: 'job-old', state: 'queued', attempt: 2 }));
    });
    expect(screen.getByTestId('state')).toHaveTextContent('job-new:queued@1');
    expect(screen.getByTestId('state')).not.toHaveTextContent('job-old');
    expect(latest!.actionError).toBeNull();
  });

  it('卸载后迟到的 retry 响应不写状态', async () => {
    let releaseRetry!: (body: JobView) => void;
    const retryGate = new Promise<Response>((resolve) => {
      releaseRetry = (body) => resolve(jsonResponse(body));
    });
    stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-1/retry')) return retryGate;
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    const ui = render(<Harness />);
    act(() => latest!.adopt(generation({ state: 'failed' })));
    act(() => latest!.retry());
    ui.unmount();

    await act(async () => {
      releaseRetry(view({ jobId: 'job-1', state: 'queued', attempt: 2 }));
    });
    expect(latest!.view?.state).toBe('failed');
  });

  it('重试失败给出可读 actionError，且不会把按钮永久留在 busy', async () => {
    stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-1/retry')) {
        return jsonResponse(
          { code: 'REVISION_CONFLICT', message: 'running 的任务不能重试。', retryable: false },
          409,
        );
      }
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    render(<Harness />);
    act(() => latest!.adopt(generation({ state: 'failed' })));

    await act(async () => {
      latest!.retry();
    });
    await waitFor(() => expect(latest!.actionError?.code).toBe('REVISION_CONFLICT'));
    expect(latest!.pending).toBeNull();
    expect(latest!.view?.state).toBe('failed');
  });
});
