import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { JobView } from '@/contracts/textbook';
import { JobsPanel } from './JobsPanel';

function job(overrides: Partial<JobView> = {}): JobView {
  return {
    jobId: 'job-1',
    kind: 'ingest',
    state: 'running',
    targetGenerationId: 'gen-1',
    baseGenerationId: null,
    documentId: 'doc-1',
    inputRevisionId: 'rev-1',
    attempt: 1,
    progress: {
      documentsDone: 1,
      documentsTotal: 3,
      chunksDone: 40,
      chunksTotal: 100,
      currentTitle: '七年级数学上册',
    },
    errorCode: null,
    errorMessage: null,
    retryable: false,
    createdAt: '2026-09-28T00:00:00Z',
    updatedAt: '2026-09-28T00:01:00Z',
    ...overrides,
  };
}

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response;
const failed = (status: number, body: unknown) =>
  ({ ok: false, status, json: async () => body }) as Response;

function stubApi(handler: (url: string, init: RequestInit) => Response) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
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
});

describe('入库任务面板', () => {
  it('展示阶段/进度/错误，取消与重试调用服务端并刷新列表', async () => {
    const jobs = [
      job(),
      job({
        jobId: 'job-2',
        state: 'failed',
        errorCode: 'EMBEDDING_UNAVAILABLE',
        errorMessage: '本机 Embedding 服务不可用。',
        retryable: true,
        progress: {
          documentsDone: 0,
          documentsTotal: 3,
          chunksDone: 0,
          chunksTotal: 100,
          currentTitle: null,
        },
      }),
    ];
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/cancel')) return ok({ ...job({ state: 'cancelled' }) });
      if (url.includes('/retry')) return ok({ ...job({ jobId: 'job-2', state: 'queued' }) });
      if (init.method === undefined) return ok({ jobs });
      throw new Error(`未预期的请求 ${url} ${String(init.method)}`);
    });

    render(<JobsPanel onClose={() => {}} pollIntervalMs={5000} />);

    expect(await screen.findByText(/执行中/)).toBeInTheDocument();
    expect(screen.getByText('已完成教材 1/3')).toBeInTheDocument();
    expect(screen.getByText('已完成块 40/100')).toBeInTheDocument();
    expect(screen.getByText('当前：七年级数学上册')).toBeInTheDocument();
    expect(screen.getByText(/EMBEDDING_UNAVAILABLE/)).toBeInTheDocument();
    expect(screen.getByText(/本机 Embedding 服务不可用/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '取消任务' }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/textbook-jobs/job-1/cancel',
        expect.objectContaining({ method: 'POST' }),
      );
    });

    fireEvent.click(screen.getByRole('button', { name: '重试任务' }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/textbook-jobs/job-2/retry',
        expect.objectContaining({ method: 'POST' }),
      );
    });
  });

  it('列表读取失败显示错误与重试，不显示空态', async () => {
    let attempt = 0;
    stubApi(() => {
      attempt += 1;
      if (attempt === 1) {
        return failed(503, {
          code: 'SERVICE_UNAVAILABLE',
          message: '后端服务不可用。',
          retryable: true,
        });
      }
      return ok({ jobs: [job({ state: 'succeeded' })] });
    });

    render(<JobsPanel onClose={() => {}} pollIntervalMs={5000} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('入库任务读取失败');
    expect(screen.queryByText('还没有入库任务')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('已完成教材 1/3')).toBeInTheDocument();
  });

  it('空列表显示空态', async () => {
    stubApi(() => ok({ jobs: [] }));
    render(<JobsPanel onClose={() => {}} pollIntervalMs={5000} />);
    expect(await screen.findByText('还没有入库任务')).toBeInTheDocument();
  });

  it('按间隔轮询，卸载后停止', async () => {
    let calls = 0;
    stubApi(() => {
      calls += 1;
      return ok({ jobs: [job()] });
    });

    const view = render(<JobsPanel onClose={() => {}} pollIntervalMs={60} />);
    await screen.findByText(/执行中/);
    await waitFor(() => expect(calls).toBeGreaterThan(1));

    const settled = calls;
    view.unmount();
    await new Promise((resolve) => setTimeout(resolve, 200));
    expect(calls).toBe(settled);
  });
});
