import { afterEach, describe, expect, it, vi } from 'vitest';
import { API_BASE_PATH } from './api-client';
import { cancelJob, fetchJob, observeJob, pollIntervalMs, retryJob } from './workflow-jobs-api';

const VIEW = {
  jobId: 'job-1',
  domain: 'teaching' as const,
  kind: 'export',
  attempt: 1,
  state: 'running' as const,
  result: null,
  error: null,
};

function stubJson(body: unknown, status = 200) {
  const fetchMock = vi.fn(async () => ({ ok: status < 400, status, json: async () => body }));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('workflow-jobs-api', () => {
  it('fetchJob 使用 domain 查询参数并解析 JobView', async () => {
    const fetchMock = stubJson(VIEW);
    const view = await fetchJob('teaching', 'job-1');
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_PATH}/workflow-jobs/job-1?domain=teaching`,
      expect.anything(),
    );
    expect(view.state).toBe('running');
    expect(view.jobId).toBe('job-1');
  });

  it('cancelJob / retryJob 以 JSON body 提交 domain', async () => {
    const fetchMock = stubJson(VIEW);
    await cancelJob('question', 'job-9');
    expect(fetchMock).toHaveBeenLastCalledWith(
      `${API_BASE_PATH}/workflow-jobs/job-9/cancel`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ domain: 'question' }),
      }),
    );
    await retryJob('question', 'job-9');
    expect(fetchMock).toHaveBeenLastCalledWith(
      `${API_BASE_PATH}/workflow-jobs/job-9/retry`,
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('observeJob 轮询到终态并回调中间状态', async () => {
    const states = ['queued', 'running', 'succeeded'] as const;
    let index = 0;
    const fetchMock = vi.fn(async () => {
      const state = states[Math.min(index, states.length - 1)];
      index += 1;
      return {
        ok: true,
        status: 200,
        json: async () => ({ ...VIEW, state, result: state === 'succeeded' ? { ok: true } : null }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);
    const seen: string[] = [];
    const sleep = vi.fn(async () => undefined);

    const final = await observeJob('teaching', 'job-1', {
      onUpdate: (view) => seen.push(view.state),
      sleep,
    });

    expect(seen).toEqual(['queued', 'running', 'succeeded']);
    expect(final?.state).toBe('succeeded');
    expect(final?.result).toEqual({ ok: true });
    expect(sleep).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledWith(2000, undefined);
  });

  it('observeJob 在 attempt 变化时停止观察并返回 null（旧页面不认新一轮结果）', async () => {
    stubJson({ ...VIEW, attempt: 2, state: 'succeeded' });
    const final = await observeJob('teaching', 'job-1', { expectedAttempt: 1 });
    expect(final).toBeNull();
  });

  it('observeJob 被取消时返回 null 而不是报错', async () => {
    const controller = new AbortController();
    stubJson(VIEW);
    const final = await observeJob('teaching', 'job-1', { signal: controller.signal, sleep: async () => controller.abort() });
    // 第一次 sleep 后取消：下一次循环以 signal.aborted 返回 null。
    expect(final).toBeNull();
  });

  it('pollIntervalMs 前 30 秒 2 秒，之后 5 秒', () => {
    expect(pollIntervalMs(0)).toBe(2000);
    expect(pollIntervalMs(29_999)).toBe(2000);
    expect(pollIntervalMs(30_000)).toBe(5000);
  });
});
