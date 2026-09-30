import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  API_BASE_PATH,
  apiRequestBlob,
  fetchCapabilities,
  fetchHealth,
  filenameFromDisposition,
  isAbortError,
} from './api-client';

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

  it('错误信封的 details 随 ApiError 保留（409 currentRevision）', async () => {
    stubFetch(async () =>
      jsonResponse(false, 409, {
        code: 'REVISION_CONFLICT',
        message: '版本已变化。',
        requestId: 'req-9',
        retryable: false,
        details: { currentRevision: 7 },
      }),
    );
    const error = await rejected(fetchHealth());
    expect(error.code).toBe('REVISION_CONFLICT');
    expect(error.details).toEqual({ currentRevision: 7 });
  });

  it('错误信封的 422 行列错误 issues 结构完整保留', async () => {
    const issues = [
      { row: 3, column: 'D', code: 'INVALID_SCORE', message: '超出满分。' },
      { row: 5, field: 'studentNo', code: 'UNKNOWN_STUDENT', message: '名单中不存在。' },
    ];
    stubFetch(async () =>
      jsonResponse(false, 422, {
        code: 'INVALID_REQUEST',
        message: '请求参数不合法。',
        retryable: false,
        details: { issues },
      }),
    );
    const error = await rejected(fetchHealth());
    expect(error.details?.issues).toEqual(issues);
  });

  it('AbortError 原样抛出，不转换成 SERVICE_UNAVAILABLE', async () => {
    const controller = new AbortController();
    stubFetch(async () => {
      controller.abort();
      throw new DOMException('已取消', 'AbortError');
    });
    let caught: unknown;
    try {
      await fetchHealth(controller.signal);
    } catch (error) {
      caught = error;
    }
    expect(isAbortError(caught)).toBe(true);
    expect(caught).not.toBeInstanceOf(ApiError);
  });

  it('isAbortError 把非取消错误判为 false', () => {
    expect(isAbortError(new ApiError('REQUEST_FAILED', 'x', 400, false))).toBe(false);
    expect(isAbortError(new Error('boom'))).toBe(false);
    expect(isAbortError(null)).toBe(false);
  });

  it('apiRequestBlob 返回文件与 Content-Disposition 文件名', async () => {
    // jsdom 的 Blob 没有 text()；替身只需满足本适配器读取的接口。
    const blob = {
      size: 10,
      type: 'application/vnd.openxmlformats',
      text: async () => 'docx-bytes',
    } as unknown as Blob;
    stubFetch(async () => ({
      ok: true,
      status: 200,
      headers: {
        get: (name: string) =>
          name.toLowerCase() === 'content-disposition'
            ? "attachment; filename*=UTF-8''%E7%BB%83%E4%B9%A0.docx"
            : null,
      },
      blob: async () => blob,
    }));
    const download = await apiRequestBlob('/export-artifacts/abc/download');
    expect(download.fileName).toBe('练习.docx');
    expect(await download.blob.text()).toBe('docx-bytes');
  });

  it('apiRequestBlob 失败时转换为 ApiError 并保留 details', async () => {
    stubFetch(async () => ({
      ...jsonResponse(false, 404, {
        code: 'NOT_FOUND',
        message: '产物不存在。',
        retryable: false,
        details: { fields: ['artifact'] },
      }),
      headers: { get: () => null },
      blob: async () => new Blob([]),
    }));
    const error = await rejected(apiRequestBlob('/export-artifacts/missing/download'));
    expect(error.code).toBe('NOT_FOUND');
    expect(error.details?.fields).toEqual(['artifact']);
  });

  it('filenameFromDisposition 回退普通 filename 与空值', () => {
    expect(filenameFromDisposition('attachment; filename="a.docx"')).toBe('a.docx');
    expect(filenameFromDisposition(null)).toBeNull();
    expect(filenameFromDisposition('attachment')).toBeNull();
  });
});
