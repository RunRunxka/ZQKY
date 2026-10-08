/**
 * `services/lesson-plans-api.ts` 传输层单测：本批新增的教案归档恢复与列表筛选。
 * 只 stub `fetch`，验证方法/路径/请求体与查询串；错误语义由 feature 级测试覆盖。
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { API_BASE_PATH } from '@/services/api-client';
import {
  archiveLessonPlan,
  listLessons,
  restoreLessonPlan,
} from '@/services/lesson-plans-api';

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

describe('教案归档/恢复', () => {
  it('POST /lesson-plans/{id}/archive|restore 提交 expectedRevision 并返回 LessonView', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { lessonPlanId: 'lesson-1', revision: 5 }),
    );
    const archived = await archiveLessonPlan('lesson 1', { expectedRevision: 4 });
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/lesson-plans/lesson%201/archive`);
    expect(bodyOf(fetchMock)).toEqual({ expectedRevision: 4 });
    expect(archived.lessonPlanId).toBe('lesson-1');

    const restoreMock = stubFetch(() =>
      jsonResponse(true, 200, { lessonPlanId: 'lesson-1', revision: 6 }),
    );
    await restoreLessonPlan('lesson-1', { expectedRevision: 5 });
    expect(call(restoreMock).init?.method).toBe('POST');
    expect(call(restoreMock).url).toBe(`${API_BASE_PATH}/lesson-plans/lesson-1/restore`);
    expect(bodyOf(restoreMock)).toEqual({ expectedRevision: 5 });
  });
});

describe('教案列表筛选', () => {
  it('archived 等筛选并入查询串', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 50 }),
    );
    await listLessons({ subjectId: 'math', archived: true });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/lesson-plans?subjectId=math&archived=true`,
    );
  });
});
