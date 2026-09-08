import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, API_BASE_PATH, fetchCapabilities, fetchHealth } from './api-client';

function stubFetch(implementation: (url: string) => Promise<unknown>) {
  const fetchMock = vi.fn((input: RequestInfo | URL) =>
    implementation(typeof input === 'string' ? input : input.toString()),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function jsonResponse(ok: boolean, status: number, body: unknown) {
  return { ok, status, json: async () => body } as Response;
}

async function rejected(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    return error as ApiError;
  }
  throw new Error('预期请求失败，但请求成功了');
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('api-client', () => {
  it('用同源相对路径请求 /api/v1 并解析成功响应', async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(true, 200, { service: 'zhiqikeyuan-api', apiVersion: 'v1', capabilities: [] }),
    );
    const data = await fetchCapabilities();
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_PATH}/capabilities`, expect.anything());
    expect(data.service).toBe('zhiqikeyuan-api');
    expect(data.capabilities).toEqual([]);
  });

  it('解析健康检查响应', async () => {
    stubFetch(async () =>
      jsonResponse(true, 200, {
        status: 'ok',
        service: 'zhiqikeyuan-api',
        apiVersion: 'v1',
        time: '2026-09-06T00:00:00Z',
      }),
    );
    const health = await fetchHealth();
    expect(health.status).toBe('ok');
  });

  it('后端错误信封转换为 ApiError 并保留 code 与 requestId', async () => {
    stubFetch(async () =>
      jsonResponse(false, 501, {
        code: 'FEATURE_NOT_IMPLEMENTED',
        message: '接口尚未实现。',
        requestId: 'req-1',
        retryable: false,
      }),
    );
    const error = await rejected(fetchCapabilities());
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe('FEATURE_NOT_IMPLEMENTED');
    expect(error.status).toBe(501);
    expect(error.requestId).toBe('req-1');
    expect(error.message).toBe('接口尚未实现。');
  });

  it('fetch 网络失败时报告后端未运行，而不是假成功', async () => {
    stubFetch(async () => {
      throw new TypeError('Failed to fetch');
    });
    const error = await rejected(fetchHealth());
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe('SERVICE_UNAVAILABLE');
    expect(error.status).toBe(0);
    expect(error.message).toContain('后端服务未运行');
  });

  it('代理返回非 JSON 的 5xx 时报告后端不可用', async () => {
    stubFetch(async () => jsonResponse(false, 502, { detail: 'Bad Gateway' }));
    const error = await rejected(fetchHealth());
    expect(error.code).toBe('SERVICE_UNAVAILABLE');
    expect(error.status).toBe(502);
  });

  it('非 JSON 的 4xx 响应按请求失败处理', async () => {
    stubFetch(async () => jsonResponse(false, 404, { detail: 'Not Found' }));
    const error = await rejected(fetchHealth());
    expect(error.code).toBe('REQUEST_FAILED');
    expect(error.retryable).toBe(false);
  });
});
