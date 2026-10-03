/**
 * B3/G0-C · B2-RV09/RV10：知识点任务 hook 的 StrictMode 与「迟到响应」回归。
 *
 * 真实 `useKnowledgeJob` + 真实 `observeJob`（只 stub `fetch`，不 mock 服务模块）：
 * - **RV09**：`<StrictMode>` 的 setup→cleanup→setup 下 `apply()` 不能永久失效，
 *   终态与 `onTerminal` 必须照常到达（普通模式作为对照）；
 * - **RV10**：重试/取消绑定 `{jobId, attempt 窗口, 观察代次}`；`reset`/接管新任务/卸载后
 *   迟到的成功与失败都不写状态；在途操作有可解释的 `pending` + `pendingLabel`；
 *   重试按 `retryObservationWindow` 接受 N/N+1，N+2 视为被更新的尝试接管。
 *
 * 这里断言的是审查探针 `probes/ui_job_probe.cjs` 的**反向**（缺陷不再复现）。
 */

import { StrictMode, useEffect } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { JobView } from '@/contracts/teaching-loop';
import { useKnowledgeJob, type KnowledgeJobController } from './hooks';

function view(overrides: Partial<JobView> & Pick<JobView, 'jobId' | 'state'>): JobView {
  return {
    domain: 'knowledge',
    kind: 'suggestion',
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

/** 永不返回的响应（模拟"观察中/请求在途"）。 */
function pendingResponse(): Promise<Response> {
  return new Promise<Response>(() => {});
}

function calls(fetchMock: ReturnType<typeof stubFetch>, fragment: string) {
  return fetchMock.mock.calls.filter(([url]) => String(url).includes(fragment));
}

let latest: KnowledgeJobController | null = null;

function Harness({
  onTerminal,
}: {
  onTerminal?: (view: JobView) => void;
}) {
  const controller = useKnowledgeJob({
    onTerminal,
    // 观察不等待真实计时：测试里由 fetch stub 决定读到的状态序列
    polling: { sleep: async () => undefined },
  });
  // 测试探针：每次渲染后记录最新控制器（渲染期间不写外部变量）
  useEffect(() => {
    latest = controller;
  });
  return (
    <div data-testid="state">
      {controller.view ? `${controller.view.jobId}:${controller.view.state}@${controller.view.attempt}` : 'null'}
      {controller.pending ? `|${controller.pending}` : ''}
      {controller.pendingLabel ? `|${controller.pendingLabel}` : ''}
    </div>
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  latest = null;
});

/* ------------------------------------------------------------------ RV09 */

describe('首次创建排队收据的执行尝试窗口', () => {
  for (const state of ['succeeded', 'failed', 'cancelled', 'interrupted'] as const) {
    it(`queued@0 接受 ${state}@1 并交付终态一次`, async () => {
      stubFetch(() => jsonResponse(view({ jobId: 'initial', state, attempt: 1 })));
      const onTerminal = vi.fn();
      render(<StrictMode><Harness onTerminal={onTerminal} /></StrictMode>);
      act(() => latest!.adopt(view({ jobId: 'initial', state: 'queued', attempt: 0 })));
      await waitFor(() => expect(onTerminal).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent(`initial:${state}@1`));
      expect(latest!.observationNotice).toBeNull();
    });
  }
  it('queued@0 拒绝 attempt2 接管，running@1 拒绝 attempt2', async () => {
    stubFetch(() => jsonResponse(view({ jobId: 'initial', state: 'succeeded', attempt: 2 })));
    const onTerminal = vi.fn();
    render(<Harness onTerminal={onTerminal} />);
    act(() => latest!.adopt(view({ jobId: 'initial', state: 'queued', attempt: 0 })));
    await waitFor(() => expect(latest!.observationNotice).toContain('接管'));
    expect(onTerminal).not.toHaveBeenCalled();
    act(() => latest!.adopt(view({ jobId: 'initial', state: 'running', attempt: 1 })));
    await waitFor(() => expect(latest!.observationNotice).toContain('接管'));
    expect(onTerminal).not.toHaveBeenCalled();
    expect(screen.getByTestId('state')).toHaveTextContent('initial:running@1');
  });
});

describe('B2-RV09：StrictMode 下任务 hook 不能永久失效', () => {
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
      act(() => latest!.adopt(view({ jobId: 'job-A', state: 'succeeded' })));
      expect(screen.getByTestId('state')).toHaveTextContent('job-A:succeeded@1');
      expect(onTerminal).toHaveBeenCalledTimes(1);
    });
  }

  it('StrictMode：adopt 非终态后仍能继续观察并收敛到终态', async () => {
    let reads = 0;
    stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-A')) {
        reads += 1;
        return reads === 1
          ? jsonResponse(view({ jobId: 'job-A', state: 'queued' }))
          : jsonResponse(view({ jobId: 'job-A', state: 'succeeded' }));
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
      latest!.adopt(view({ jobId: 'job-A', state: 'queued' }));
    });
    await waitFor(() => expect(onTerminal).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId('state')).toHaveTextContent('job-A:succeeded@1');
    expect(latest!.observing).toBe(false);
  });

  it('StrictMode：卸载 cleanup 后重新 setup（模拟挂载）仍可接管新任务', () => {
    render(
      <StrictMode>
        <Harness />
      </StrictMode>,
    );
    // StrictMode 已跑过 setup→cleanup→setup；这里再接管两次任务证明标志已恢复
    act(() => latest!.adopt(view({ jobId: 'job-1', state: 'failed' })));
    act(() => latest!.adopt(view({ jobId: 'job-2', state: 'cancelled' })));
    expect(screen.getByTestId('state')).toHaveTextContent('job-2:cancelled@1');
  });
});

/* ------------------------------------------------------------------ RV10 */

describe('B2-RV10：迟到响应不污染新任务（旧探针反向）', () => {
  it('reset/切换任务后，迟到的旧 retry 成功不接管新任务；重复点击不产生第二个请求', async () => {
    let releaseRetry!: (body: JobView) => void;
    const retryGate = new Promise<Response>((resolve) => {
      releaseRetry = (body) => resolve(jsonResponse(body));
    });
    const fetchMock = stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-old/retry')) return retryGate;
      if (url.includes('/workflow-jobs/job-new')) return pendingResponse(); // 新任务观察中
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    render(<Harness />);

    act(() => latest!.adopt(view({ jobId: 'job-old', state: 'failed' })));
    act(() => {
      latest!.retry();
      latest!.retry(); // 在途重复点击：不得再发一次
    });
    expect(calls(fetchMock, '/retry')).toHaveLength(1);
    // pending 可解释：按钮 busy + 文案
    expect(screen.getByTestId('state')).toHaveTextContent('job-old:failed@1');
    expect(screen.getByTestId('state')).toHaveTextContent('retry');
    expect(screen.getByTestId('state')).toHaveTextContent('正在重试…');

    await act(async () => {
      latest!.reset();
      latest!.adopt(view({ jobId: 'job-new', state: 'queued' }));
    });
    expect(screen.getByTestId('state')).toHaveTextContent('job-new:queued@1');
    expect(screen.getByTestId('state')).not.toHaveTextContent('正在重试…');

    await act(async () => {
      releaseRetry(view({ jobId: 'job-old', state: 'queued', attempt: 2 }));
    });
    // 迟到的旧响应：视图仍是新任务，也没有把旧 job 的观察接回来
    expect(screen.getByTestId('state')).toHaveTextContent('job-new:queued@1');
    expect(screen.getByTestId('state')).not.toHaveTextContent('job-old');
    expect(latest!.view?.jobId).toBe('job-new');
    expect(latest!.actionError).toBeNull();
  });

  it('reset/切换任务后，迟到的旧 retry 失败不写 actionError', async () => {
    let rejectRetry!: (error: unknown) => void;
    const retryGate = new Promise<Response>((_resolve, reject) => {
      rejectRetry = reject;
    });
    stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-old/retry')) return retryGate;
      if (url.includes('/workflow-jobs/job-new')) return pendingResponse();
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    render(<Harness />);

    act(() => latest!.adopt(view({ jobId: 'job-old', state: 'failed' })));
    act(() => latest!.retry());
    await act(async () => {
      latest!.reset();
      latest!.adopt(view({ jobId: 'job-new', state: 'queued' }));
    });

    await act(async () => {
      rejectRetry(new Error('旧任务重试失败'));
    });
    expect(latest!.actionError).toBeNull();
    expect(screen.getByTestId('state')).toHaveTextContent('job-new:queued@1');
    expect(screen.getByTestId('state')).not.toHaveTextContent('正在重试…');
  });

  it('reset/切换任务后，迟到的旧 cancel 成功也不接管新任务', async () => {
    let releaseCancel!: (body: JobView) => void;
    const cancelGate = new Promise<Response>((resolve) => {
      releaseCancel = (body) => resolve(jsonResponse(body));
    });
    const fetchMock = stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-old/cancel')) return cancelGate;
      if (url.includes('/workflow-jobs/job-new')) return pendingResponse();
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    render(<Harness />);

    act(() => latest!.adopt(view({ jobId: 'job-old', state: 'running' })));
    act(() => latest!.cancel());
    expect(calls(fetchMock, '/cancel')).toHaveLength(1);
    expect(screen.getByTestId('state')).toHaveTextContent('正在取消…');

    await act(async () => {
      latest!.reset();
      latest!.adopt(view({ jobId: 'job-new', state: 'running' }));
    });
    await act(async () => {
      releaseCancel(view({ jobId: 'job-old', state: 'cancelled', attempt: 1 }));
    });
    expect(screen.getByTestId('state')).toHaveTextContent('job-new:running@1');
    expect(screen.getByTestId('state')).not.toHaveTextContent('job-old');
  });

  it('卸载后迟到的 retry 响应不写状态（挂载标志失效）', async () => {
    let releaseRetry!: (body: JobView) => void;
    const retryGate = new Promise<Response>((resolve) => {
      releaseRetry = (body) => resolve(jsonResponse(body));
    });
    stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-old/retry')) return retryGate;
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    const ui = render(<Harness />);
    act(() => latest!.adopt(view({ jobId: 'job-old', state: 'failed' })));
    act(() => latest!.retry());
    ui.unmount();

    await act(async () => {
      releaseRetry(view({ jobId: 'job-old', state: 'queued', attempt: 2 }));
    });
    // 卸载后不再有新的渲染状态：旧的 failed 视图没有被迟到的 queued 顶掉
    expect(latest!.view?.state).toBe('failed');
  });

  it('重试按 retryObservationWindow 观察：接受 N/N+1 并收敛终态', async () => {
    const reads = [
      view({ jobId: 'job-A', state: 'running', attempt: 3 }),
      view({ jobId: 'job-A', state: 'succeeded', attempt: 3 }),
    ];
    let index = 0;
    const fetchMock = stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-A/retry')) {
        return jsonResponse(view({ jobId: 'job-A', state: 'queued', attempt: 2 }));
      }
      if (url.includes('/workflow-jobs/job-A')) {
        const next = reads[Math.min(index, reads.length - 1)];
        index += 1;
        return jsonResponse(next);
      }
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    const onTerminal = vi.fn();
    render(<Harness onTerminal={onTerminal} />);
    act(() => latest!.adopt(view({ jobId: 'job-A', state: 'failed', attempt: 1 })));
    onTerminal.mockClear(); // 上面这次是 adopt 的终态；只看重试观察这一段

    await act(async () => {
      latest!.retry();
    });
    await waitFor(() => expect(onTerminal).toHaveBeenCalledTimes(1));
    expect(onTerminal.mock.calls[0][0]).toMatchObject({
      jobId: 'job-A',
      state: 'succeeded',
      attempt: 3,
    });
    expect(screen.getByTestId('state')).toHaveTextContent('job-A:succeeded@3');
    expect(calls(fetchMock, '/workflow-jobs/job-A?')).toHaveLength(2);
  });

  it('attempt 超出 [N, N+1] 窗口时停止观察：不把更新尝试的结果当本轮', async () => {
    stubFetch((url) => {
      if (url.includes('/workflow-jobs/job-A/retry')) {
        return jsonResponse(view({ jobId: 'job-A', state: 'queued', attempt: 2 }));
      }
      if (url.includes('/workflow-jobs/job-A')) {
        return jsonResponse(view({ jobId: 'job-A', state: 'succeeded', attempt: 4 }));
      }
      return jsonResponse({ code: 'UNEXPECTED_TEST_REQUEST', message: url }, 500);
    });
    const onTerminal = vi.fn();
    render(<Harness onTerminal={onTerminal} />);
    act(() => latest!.adopt(view({ jobId: 'job-A', state: 'failed', attempt: 1 })));
    onTerminal.mockClear(); // 上面这次是 adopt 的终态；只看重试观察这一段

    await act(async () => {
      latest!.retry();
    });
    await waitFor(() => expect(latest!.observationNotice).not.toBeNull());
    expect(latest!.observationNotice).toContain('接管');
    expect(latest!.view?.state).toBe('queued'); // 停在重试收据，不认 attempt 4
    expect(latest!.view?.attempt).toBe(2);
    expect(onTerminal).not.toHaveBeenCalled();
  });
});
