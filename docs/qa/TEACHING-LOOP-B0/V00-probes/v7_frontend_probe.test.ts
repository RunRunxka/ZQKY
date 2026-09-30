/**
 * V7 前端公共客户端独立探针（V00 / TEACHING-LOOP B0，定向 vitest）。
 *
 * 覆盖：
 *   7① 409/422 信封的 details（currentRevision / issues）能到 ApiError.details
 *   7② AbortError 原样抛出且 isAbortError 为真（不变成 SERVICE_UNAVAILABLE）
 *   7③ apiRequestBlob 返回 {blob, fileName}（RFC5987 解码）且失败转 ApiError
 *   7④ observeJob 轮询至终态、expectedAttempt 不符返回 null、abort 返回 null，
 *       且"停止观察"不会调用取消接口
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ApiError,
  apiRequest,
  apiRequestBlob,
  filenameFromDisposition,
  isAbortError,
} from '@/services/api-client';
import {
  cancelJob,
  fetchJob,
  observeJob,
  pollIntervalMs,
  retryJob,
} from '@/services/workflow-jobs-api';
import { isJobTerminal, JOB_TERMINAL_STATES } from '@/contracts/teaching-loop';

const originalFetch = globalThis.fetch;

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

/** jsdom 的 Blob 没有 arrayBuffer()，用 FileReader 读内容（探针环境限制，非产品问题）。 */
function blobText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe('V7 公共客户端独立探针', () => {
  it('v7.1 409 信封 details.currentRevision 到达 ApiError.details', async () => {
    globalThis.fetch = vi.fn(async () =>
      jsonResponse(
        {
          code: 'REVISION_CONFLICT',
          message: '数据已被其他操作更新，请刷新后重试。',
          requestId: 'req-1',
          retryable: false,
          details: { currentRevision: 3 },
        },
        409,
      ),
    ) as unknown as typeof fetch;

    await expect(apiRequest('/whatever')).rejects.toMatchObject({
      code: 'REVISION_CONFLICT',
      status: 409,
      requestId: 'req-1',
      details: { currentRevision: 3 },
    });
    try {
      await apiRequest('/whatever');
      throw new Error('预期抛出 ApiError');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.details?.currentRevision).toBe(3);
      expect(apiError.retryable).toBe(false);
    }
  });

  it('v7.2 422 信封 details.issues 到达 ApiError.details', async () => {
    globalThis.fetch = vi.fn(async () =>
      jsonResponse(
        {
          code: 'INVALID_REQUEST',
          message: '请求参数不合法。',
          retryable: false,
          details: {
            issues: [
              { row: 2, column: 'score', code: 'NOT_A_NUMBER', message: '必须是数字' },
              { field: 'name', code: 'REQUIRED', message: '必填' },
            ],
          },
        },
        422,
      ),
    ) as unknown as typeof fetch;

    try {
      await apiRequest('/whatever');
      throw new Error('预期抛出 ApiError');
    } catch (error) {
      const apiError = error as ApiError;
      expect(apiError.code).toBe('INVALID_REQUEST');
      expect(apiError.details?.issues).toHaveLength(2);
      expect(apiError.details?.issues?.[0]).toMatchObject({
        row: 2,
        column: 'score',
        code: 'NOT_A_NUMBER',
      });
    }
  });

  it('v7.3 AbortError 原样抛出且 isAbortError 为真（不降级为 SERVICE_UNAVAILABLE）', async () => {
    const controller = new AbortController();
    globalThis.fetch = vi.fn(async (_url: unknown, init?: RequestInit) => {
      const signal = init?.signal ?? controller.signal;
      controller.abort();
      throw signal.reason ?? new DOMException('已取消', 'AbortError');
    }) as unknown as typeof fetch;

    let captured: unknown;
    try {
      await apiRequest('/whatever', { signal: controller.signal });
      throw new Error('预期抛出取消错误');
    } catch (error) {
      captured = error;
    }
    expect(isAbortError(captured)).toBe(true);
    expect(captured).not.toBeInstanceOf(ApiError);
    expect((captured as { name?: string }).name).toBe('AbortError');
    expect(isAbortError(new ApiError('SERVICE_UNAVAILABLE', 'x', 0, true))).toBe(false);
  });

  it('v7.4 连接失败仍转换为 SERVICE_UNAVAILABLE', async () => {
    globalThis.fetch = vi.fn(async () => {
      throw new TypeError('fetch failed');
    }) as unknown as typeof fetch;
    try {
      await apiRequest('/whatever');
      throw new Error('预期抛出 ApiError');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).code).toBe('SERVICE_UNAVAILABLE');
      expect((error as ApiError).status).toBe(0);
    }
  });

  it('v7.5 apiRequestBlob 返回 {blob, fileName} 并解码 RFC5987 文件名', async () => {
    const bytes = new TextEncoder().encode('学情导出内容');
    globalThis.fetch = vi.fn(
      async () =>
        new Response(bytes, {
          status: 200,
          headers: {
            'content-type': 'application/octet-stream',
            'content-disposition': `attachment; filename="fallback.bin"; filename*=UTF-8''%E5%AD%A6%E6%83%85%E5%AF%BC%E5%87%BA.csv`,
          },
        }),
    ) as unknown as typeof fetch;

    const { blob, fileName } = await apiRequestBlob('/exports/1');
    expect(fileName).toBe('学情导出.csv');
    expect(blob.size).toBe(bytes.byteLength);
    expect(blob.type).toBe('application/octet-stream');
    expect(await blobText(blob)).toBe('学情导出内容');
    expect(filenameFromDisposition('attachment; filename="plain.docx"')).toBe('plain.docx');
    expect(filenameFromDisposition(null)).toBeNull();
  });

  it('v7.6 apiRequestBlob 失败转换为 ApiError（含 details），不返回半截文件', async () => {
    globalThis.fetch = vi.fn(async () =>
      jsonResponse(
        {
          code: 'REVISION_CONFLICT',
          message: '冲突',
          retryable: false,
          details: { currentRevision: 9 },
        },
        409,
      ),
    ) as unknown as typeof fetch;
    try {
      await apiRequestBlob('/exports/1');
      throw new Error('预期抛出 ApiError');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).details?.currentRevision).toBe(9);
    }

    globalThis.fetch = vi.fn(async () => new Response('boom', { status: 502 })) as unknown as typeof fetch;
    try {
      await apiRequestBlob('/exports/1');
      throw new Error('预期抛出 ApiError');
    } catch (error) {
      expect((error as ApiError).code).toBe('SERVICE_UNAVAILABLE');
      expect((error as ApiError).status).toBe(502);
    }
  });

  it('v7.7 fetchJob / cancelJob / retryJob 使用冻结路由与 camelCase body', async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    globalThis.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url: String(url), init });
      return jsonResponse(
        { jobId: 'j1', domain: 'teaching', kind: 'export', attempt: 1, state: 'queued', result: null, error: null },
        200,
      );
    }) as unknown as typeof fetch;

    await fetchJob('teaching', 'j 1');
    await cancelJob('teaching', 'j1');
    await retryJob('teaching', 'j1');
    expect(calls[0].url).toBe('/api/v1/workflow-jobs/j%201?domain=teaching');
    expect(calls[1].url).toBe('/api/v1/workflow-jobs/j1/cancel');
    expect(calls[1].init?.method).toBe('POST');
    expect(JSON.parse(String(calls[1].init?.body))).toEqual({ domain: 'teaching' });
    expect(calls[2].url).toBe('/api/v1/workflow-jobs/j1/retry');
  });

  it('v7.8 observeJob 轮询至终态并回调每次状态', async () => {
    const views = [
      { jobId: 'j1', domain: 'teaching', kind: 'export', attempt: 1, state: 'queued', result: null, error: null },
      { jobId: 'j1', domain: 'teaching', kind: 'export', attempt: 1, state: 'running', result: null, error: null },
      {
        jobId: 'j1',
        domain: 'teaching',
        kind: 'export',
        attempt: 1,
        state: 'succeeded',
        result: { file: 'x' },
        error: null,
      },
    ] as const;
    let index = 0;
    globalThis.fetch = vi.fn(async () =>
      jsonResponse(views[Math.min(index++, views.length - 1)], 200),
    ) as unknown as typeof fetch;

    const seen: string[] = [];
    const sleep = vi.fn(async () => undefined);
    const view = await observeJob('teaching', 'j1', {
      sleep,
      onUpdate: (item) => seen.push(item.state),
    });
    expect(view?.state).toBe('succeeded');
    expect(view?.result).toEqual({ file: 'x' });
    expect(seen).toEqual(['queued', 'running', 'succeeded']);
    expect(sleep).toHaveBeenCalledTimes(2);
    expect(pollIntervalMs(0)).toBe(2000);
    expect(pollIntervalMs(30_000)).toBe(5000);
  });

  it('v7.9 observeJob: attempt 不符返回 null（不把新一轮结果当本轮）', async () => {
    let fetches = 0;
    globalThis.fetch = vi.fn(async () => {
      fetches += 1;
      return jsonResponse(
        { jobId: 'j1', domain: 'teaching', kind: 'export', attempt: 2, state: 'succeeded', result: {}, error: null },
        200,
      );
    }) as unknown as typeof fetch;
    const view = await observeJob('teaching', 'j1', { expectedAttempt: 1, sleep: async () => undefined });
    expect(view).toBeNull();
    expect(fetches).toBe(1);
  });

  it('v7.10 observeJob: abort 返回 null，且不调用取消接口', async () => {
    const controller = new AbortController();
    controller.abort();
    const urls: string[] = [];
    globalThis.fetch = vi.fn(async (url: string) => {
      urls.push(String(url));
      return jsonResponse(
        { jobId: 'j1', domain: 'teaching', kind: 'export', attempt: 1, state: 'queued', result: null, error: null },
        200,
      );
    }) as unknown as typeof fetch;
    const preAborted = await observeJob('teaching', 'j1', { signal: controller.signal });
    expect(preAborted).toBeNull();
    expect(urls).toEqual([]);

    let polls = 0;
    const live = new AbortController();
    globalThis.fetch = vi.fn(async (url: string) => {
      urls.push(String(url));
      polls += 1;
      return jsonResponse(
        { jobId: 'j1', domain: 'teaching', kind: 'export', attempt: 1, state: 'running', result: null, error: null },
        200,
      );
    }) as unknown as typeof fetch;
    const view = await observeJob('teaching', 'j1', {
      signal: live.signal,
      sleep: async () => {
        live.abort();
      },
    });
    expect(view).toBeNull();
    expect(polls).toBe(1);
    expect(urls.every((url) => !url.includes('/cancel'))).toBe(true);
    expect(isJobTerminal('running')).toBe(false);
    expect(JOB_TERMINAL_STATES).toEqual(['succeeded', 'failed', 'cancelled', 'interrupted']);
  });
});
