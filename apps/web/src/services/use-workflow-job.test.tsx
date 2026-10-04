import { StrictMode } from 'react';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { JobView } from '@/contracts/teaching-loop';
import { useObservedJob } from './use-workflow-job';
import { observeJob, retryJob, cancelJob } from './workflow-jobs-api';

vi.mock('./workflow-jobs-api', () => ({
  observeJob: vi.fn(), retryJob: vi.fn(), cancelJob: vi.fn(),
  retryObservationWindow: (view: JobView) => ({ minAttempt: view.attempt, maxAttempt: view.attempt + 1 }),
}));
const job = (id: string, state: JobView['state'], attempt: number): JobView => ({ jobId: id, domain: 'teaching', kind: 'paper_knowledge', state, attempt, result: null, error: null });
beforeEach(() => vi.clearAllMocks());
afterEach(cleanup);
describe('公共原卷任务观察', () => {
  it('StrictMode接受真实queued0->terminal1，并冻结首次窗口拒绝后续2', async () => {
    vi.mocked(observeJob).mockImplementation(async (_domain, id, options) => {
      expect(options).toMatchObject({ minAttempt: 0, maxAttempt: 1 });
      const terminal = job(id, 'succeeded', 1); options?.onUpdate?.(terminal); return terminal;
    });
    const terminal = vi.fn();
    const hook = renderHook(() => useObservedJob('teaching', { onTerminal: terminal }), { wrapper: StrictMode });
    act(() => hook.result.current.adopt(job('a', 'queued', 0)));
    await waitFor(() => expect(hook.result.current.view?.state).toBe('succeeded'));
    expect(terminal).toHaveBeenCalledTimes(1);
  });
  it.each(['retry', 'cancel'] as const)('reset后旧%s成功不能接管新任务', async (action) => {
    let resolve!: (view: JobView) => void;
    vi.mocked(observeJob).mockImplementation(async () => new Promise(() => {}));
    vi.mocked(action === 'retry' ? retryJob : cancelJob).mockReturnValue(new Promise((r) => { resolve = r; }));
    const hook = renderHook(() => useObservedJob('teaching'));
    act(() => hook.result.current.adopt(job('old', 'failed', 1)));
    act(() => hook.result.current[action]());
    expect(hook.result.current.pending).toBe(action);
    act(() => { hook.result.current.reset(); hook.result.current.adopt(job('next', 'queued', 0)); });
    await act(async () => resolve(job('old', 'queued', 1)));
    expect(hook.result.current.view?.jobId).toBe('next');
    expect(hook.result.current.pending).toBeNull();
  });
  it('卸载后旧显式操作失败无终态副作用', async () => {
    let reject!: (error: Error) => void;
    vi.mocked(retryJob).mockReturnValue(new Promise((_r, j) => { reject = j; }));
    const terminal = vi.fn();
    const hook = renderHook(() => useObservedJob('teaching', { onTerminal: terminal }));
    act(() => hook.result.current.adopt(job('old', 'failed', 1)));
    terminal.mockClear();
    act(() => hook.result.current.retry()); hook.unmount();
    await act(async () => reject(new Error('late')));
    expect(terminal).not.toHaveBeenCalled();
  });
});
