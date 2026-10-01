/**
 * V00 · RV09/RV10 vitest 探针（真实 hooks.ts + 真实 workflow-jobs-api.ts，只 mock API 边界）。
 *
 * 与 p09_frontend_hooks.cjs 覆盖同一组判据，本文件走仓库要求的 vitest 入口：
 *   NODE_OPTIONS=--no-experimental-webstorage npx vitest run \
 *     --config docs/qa/TEACHING-LOOP-B3/V00-probes/v00-vitest.config.ts
 */
import React from 'react';
import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, act } from '@testing-library/react';

const retryDeferred = { resolve: null as null | ((value: unknown) => void) };
const cancelDeferred = { resolve: null as null | ((value: unknown) => void) };

vi.mock('@/services/workflow-jobs-api', async () => {
  const actual = await vi.importActual<typeof import('@/services/workflow-jobs-api')>(
    '@/services/workflow-jobs-api',
  );
  return {
    ...actual,
    observeJob: () => new Promise(() => {}),
    retryJob: () =>
      new Promise((resolve) => {
        retryDeferred.resolve = resolve;
      }),
    cancelJob: () =>
      new Promise((resolve) => {
        cancelDeferred.resolve = resolve;
      }),
  };
});

import { useKnowledgeJob } from '@/features/knowledge-points/hooks';
import type { JobView } from '@/contracts/teaching-loop';

function view(overrides: Partial<JobView>): JobView {
  return {
    jobId: 'A',
    domain: 'knowledge',
    kind: 'suggestion',
    attempt: 1,
    state: 'running',
    result: null,
    error: null,
    ...overrides,
  } as JobView;
}

type Controller = ReturnType<typeof useKnowledgeJob>;

function Harness({
  onReady,
  onTerminal,
}: {
  onReady: (controller: Controller) => void;
  onTerminal?: (job: JobView) => void;
}) {
  const controller = useKnowledgeJob({ onTerminal });
  onReady(controller);
  return (
    <div>
      <span data-testid="state">
        {controller.view ? `${controller.view.jobId}:${controller.view.state}:${controller.view.attempt}` : 'null'}
      </span>
      <span data-testid="pending">{controller.pending ?? 'none'}</span>
      <span data-testid="error">{controller.actionError?.code ?? 'none'}</span>
    </div>
  );
}

afterEach(() => {
  cleanup();
  retryDeferred.resolve = null;
  cancelDeferred.resolve = null;
});

describe('RV09 StrictMode 与 RV10 迟到响应（真实 hook + 真实观察窗口）', () => {
  it('普通模式与 StrictMode 双 setup 下 adopt(终态) 都生效且 onTerminal 恰一次', async () => {
    for (const strict of [false, true]) {
      let terminalCalls = 0;
      let controller: Controller | null = null;
      const element = (
        <div>
          <Harness
            onReady={(next) => {
              controller = next;
            }}
            onTerminal={() => {
              terminalCalls += 1;
            }}
          />
          <button
            type="button"
            onClick={() => controller?.adopt(view({ state: 'succeeded', attempt: 1 }))}
          >
            adopt
          </button>
        </div>
      );
      const ui = render(strict ? <StrictMode>{element}</StrictMode> : element);
      await act(async () => {
        fireEvent.click(ui.getByRole('button'));
      });
      expect(ui.getByTestId('state').textContent).toBe('A:succeeded:1');
      expect(terminalCalls).toBe(1);
      cleanup();
    }
  });

  it('迟到的 retry 响应不污染 reset/adopt 之后的新任务，也不把按钮留在 busy', async () => {
    let controller: Controller | null = null;
    const ui = render(
      <div>
        <Harness onReady={(next) => (controller = next)} />
        <button type="button" data-testid="adopt-a"
          onClick={() => controller?.adopt(view({ jobId: 'A', state: 'failed', attempt: 1 }))}>
          a
        </button>
        <button type="button" data-testid="retry" onClick={() => controller?.retry()}>
          r
        </button>
        <button type="button" data-testid="reset" onClick={() => controller?.reset()}>
          x
        </button>
        <button type="button" data-testid="adopt-b"
          onClick={() => controller?.adopt(view({ jobId: 'B', state: 'succeeded', attempt: 3 }))}>
          b
        </button>
      </div>,
    );
    await act(async () => { fireEvent.click(ui.getByTestId('adopt-a')); });
    await act(async () => { fireEvent.click(ui.getByTestId('retry')); });
    expect(ui.getByTestId('pending').textContent).toBe('retry');
    await act(async () => { fireEvent.click(ui.getByTestId('reset')); });
    expect(ui.getByTestId('pending').textContent).toBe('none');
    await act(async () => { fireEvent.click(ui.getByTestId('adopt-b')); });
    await act(async () => {
      retryDeferred.resolve?.(view({ jobId: 'A', state: 'succeeded', attempt: 2 }));
      await Promise.resolve();
    });
    expect(ui.getByTestId('state').textContent).toBe('B:succeeded:3');
  });

  it('迟到的 cancel 响应不污染新任务', async () => {
    let controller: Controller | null = null;
    const ui = render(
      <div>
        <Harness onReady={(next) => (controller = next)} />
        <button type="button" data-testid="adopt-a"
          onClick={() => controller?.adopt(view({ jobId: 'A', state: 'running', attempt: 1 }))}>
          a
        </button>
        <button type="button" data-testid="cancel" onClick={() => controller?.cancel()}>
          c
        </button>
        <button type="button" data-testid="reset" onClick={() => controller?.reset()}>
          x
        </button>
        <button type="button" data-testid="adopt-b"
          onClick={() => controller?.adopt(view({ jobId: 'B', state: 'succeeded', attempt: 9 }))}>
          b
        </button>
      </div>,
    );
    await act(async () => { fireEvent.click(ui.getByTestId('adopt-a')); });
    await act(async () => { fireEvent.click(ui.getByTestId('cancel')); });
    await act(async () => { fireEvent.click(ui.getByTestId('reset')); });
    await act(async () => { fireEvent.click(ui.getByTestId('adopt-b')); });
    await act(async () => {
      cancelDeferred.resolve?.(view({ jobId: 'A', state: 'cancelled', attempt: 2 }));
      await Promise.resolve();
    });
    expect(ui.getByTestId('state').textContent).toBe('B:succeeded:9');
    expect(ui.getByTestId('error').textContent).toBe('none');
  });
});

describe('RV01 观察窗口（真实 observeJob）', () => {
  it('重试收据 N 接受 [N, N+1]、拒绝 N+2 与更早 attempt', async () => {
    const actual = await vi.importActual<typeof import('@/services/workflow-jobs-api')>(
      '@/services/workflow-jobs-api',
    );
    const sleep = async () => {};
    const fetchJob = vi
      .spyOn(await import('@/services/api-client'), 'apiRequest')
      .mockResolvedValueOnce(view({ attempt: 2, state: 'queued' }) as never)
      .mockResolvedValueOnce(view({ attempt: 3, state: 'succeeded' }) as never)
      .mockResolvedValueOnce(view({ attempt: 5, state: 'succeeded' }) as never)
      .mockResolvedValueOnce(view({ attempt: 1, state: 'succeeded' }) as never);

    const window = actual.retryObservationWindow({ attempt: 2 });
    expect(window).toEqual({ minAttempt: 2, maxAttempt: 3 });
    const updates: number[] = [];
    const accepted = await actual.observeJob('knowledge', 'job-1', {
      ...window,
      onUpdate: (next) => updates.push(next.attempt),
      sleep,
    });
    expect(accepted?.attempt).toBe(3);
    expect(updates).toEqual([2, 3]);

    const rejectedNewer = await actual.observeJob('knowledge', 'job-1', { ...window, sleep });
    expect(rejectedNewer).toBeNull();
    const rejectedOlder = await actual.observeJob('knowledge', 'job-1', { ...window, sleep });
    expect(rejectedOlder).toBeNull();
    fetchJob.mockRestore();
  });
});
