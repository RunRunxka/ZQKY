/**
 * `services/teaching-loop-b4-api.ts` 传输层单测：本批新增的学情运行/练习集归档恢复与列表筛选。
 * 只 stub `fetch`，验证方法/路径/请求体与查询串；错误语义由 feature 级测试覆盖。
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { API_BASE_PATH } from '@/services/api-client';
import {
  archiveAnalysisRun,
  archivePracticeSet,
  deletePracticeSet,
  listAnalysisRuns,
  listPractices,
  restoreAnalysisRun,
  restorePracticeSet,
} from '@/services/teaching-loop-b4-api';

type FetchMock = ReturnType<typeof vi.fn>;

function stubFetch(handler: (url: string, init?: RequestInit) => unknown) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init)),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock as unknown as FetchMock;
}

function jsonResponse(ok: boolean, status: number, body: unknown) {
  return { ok, status, json: async () => body } as Response;
}

function call(fetchMock: FetchMock, index = 0) {
  const [input, init] = fetchMock.mock.calls[index] as [RequestInfo | URL, RequestInit?];
  return { url: typeof input === 'string' ? input : input.toString(), init };
}

function bodyOf(fetchMock: FetchMock, index = 0): unknown {
  const raw = call(fetchMock, index).init?.body;
  return typeof raw === 'string' ? JSON.parse(raw) : raw;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('学情运行归档/恢复', () => {
  it('POST /analysis-runs/{id}/archive|restore 提交空对象请求体', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { runId: 'run-1', archivedAt: '2026-10-07T00:00:00Z' }),
    );
    const archived = await archiveAnalysisRun('run 1');
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/analysis-runs/run%201/archive`);
    expect(bodyOf(fetchMock)).toEqual({});
    expect(archived.archivedAt).toBe('2026-10-07T00:00:00Z');

    const restoreMock = stubFetch(() =>
      jsonResponse(true, 200, { runId: 'run-1', archivedAt: null }),
    );
    await restoreAnalysisRun('run-1');
    expect(call(restoreMock).init?.method).toBe('POST');
    expect(call(restoreMock).url).toBe(`${API_BASE_PATH}/analysis-runs/run-1/restore`);
    expect(bodyOf(restoreMock)).toEqual({});
  });

  it('列表 archived 筛选并入查询串（false 也写入，不静默丢筛选）', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 50 }),
    );
    await listAnalysisRuns({ archived: false, offset: 0, limit: 20 });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/analysis-runs?archived=false&offset=0&limit=20`,
    );
  });
});

describe('练习集归档/恢复', () => {
  it('POST /practice-sets/{id}/archive|restore 提交 expectedRevision', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { practiceSetId: 'set-1', status: 'archived' }),
    );
    const archived = await archivePracticeSet('set-1', { expectedRevision: 3 });
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/practice-sets/set-1/archive`);
    expect(bodyOf(fetchMock)).toEqual({ expectedRevision: 3 });
    expect(archived.status).toBe('archived');

    const restoreMock = stubFetch(() =>
      jsonResponse(true, 200, { practiceSetId: 'set-1', status: 'active' }),
    );
    await restorePracticeSet('set-1', { expectedRevision: 4 });
    expect(call(restoreMock).init?.method).toBe('POST');
    expect(call(restoreMock).url).toBe(`${API_BASE_PATH}/practice-sets/set-1/restore`);
    expect(bodyOf(restoreMock)).toEqual({ expectedRevision: 4 });
  });

  it('列表 status 筛选并入查询串', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 50 }),
    );
    await listPractices({ analysisRunId: 'run-1', status: 'archived' });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/practice-sets?analysisRunId=run-1&status=archived`,
    );
  });

  it('DELETE /practice-sets/{id}?expectedRevision=N 走查询参数、无请求体，回执原样返回', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { deleted: true, practiceSetId: 'set-1' }),
    );
    const receipt = await deletePracticeSet('set 1', 3);
    expect(call(fetchMock).init?.method).toBe('DELETE');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/practice-sets/set%201?expectedRevision=3`);
    expect(call(fetchMock).init?.body).toBeUndefined();
    expect(receipt).toEqual({ deleted: true, practiceSetId: 'set-1' });
  });

  it('被引用 409 PRACTICE_IN_USE 原样抛出，逐项计数保留在 details.counts', async () => {
    stubFetch(() =>
      jsonResponse(false, 409, {
        code: 'PRACTICE_IN_USE',
        message: '练习集仍被引用，不能删除（已审核版本 1 条、施测转换 2 条）。',
        retryable: false,
        details: { counts: { reviewedRevisions: 1, exports: 0, conversions: 2 } },
      }),
    );
    await expect(deletePracticeSet('set-1', 1)).rejects.toMatchObject({
      code: 'PRACTICE_IN_USE',
      status: 409,
      details: { counts: { reviewedRevisions: 1, conversions: 2 } },
    });
  });
});
