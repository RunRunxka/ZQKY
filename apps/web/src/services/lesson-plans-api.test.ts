/**
 * 教案 `/api/v1` 客户端：端点、请求体形状、容错归一与失败语义（409 带 currentRevision）。
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, API_BASE_PATH } from '@/services/api-client';
import {
  createLessonPlan,
  downloadLessonExport,
  exportLessonPlan,
  getLessonPlan,
  lessonPlansApi,
  listLessonPlans,
  normalizeLessonList,
  normalizeLessonView,
  patchLessonPlanDraft,
  uploadLessonSource,
} from '@/services/lesson-plans-api';
import { emptyLessonData, withLessonDefaults } from '@/features/lesson-plan/model/lesson-data';

type FetchMock = ReturnType<typeof vi.fn>;

function stubFetch(handler: (url: string, init?: RequestInit) => unknown) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init)),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock as unknown as FetchMock;
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    headers: new Headers({ 'content-type': 'application/json' }),
  } as unknown as Response;
}

function call(fetchMock: FetchMock, index = 0) {
  const [input, init] = fetchMock.mock.calls[index] as [RequestInfo | URL, RequestInit?];
  return { url: typeof input === 'string' ? input : input.toString(), init };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('lesson-plans-api', () => {
  it('创建：POST /lesson-plans，body 为 {submissionId, subjectId, classId, data}', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(201, {
        lessonPlanId: 'plan-1',
        revision: 1,
        currentRevisionId: 'rev-1',
        currentRevision: { lessonPlanId: 'plan-1', revisionId: 'rev-1', version: 1, data: { title: '新教案' } },
      }),
    );
    const view = await createLessonPlan({
      submissionId: 'sub-1',
      subjectId: 'math',
      classId: 'class-1',
      context: null,
      data: emptyLessonData(),
    });
    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/lesson-plans`);
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toMatchObject({
      submissionId: 'sub-1',
      subjectId: 'math',
      classId: 'class-1',
      context: null,
    });
    expect(view.lessonPlanId).toBe('plan-1');
    expect(view.revision).toBe(1);
    expect(view.currentRevision.data.title).toBe('新教案');
    // 契约里 v2 字段全 optional：边界层原样透传，进入工作台时由 withLessonDefaults 补全。
    expect(withLessonDefaults(view.currentRevision.data).basic).toMatchObject({
      courseName: '',
      audience: '',
    });
    expect(withLessonDefaults(view.currentRevision.data).processV2).toEqual([]);
  });

  it('读取：GET /lesson-plans/{id}，接受扁平 data 返回', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(200, { lessonPlanId: 'plan/2', revision: 4, data: { title: '扁平', reflection: '反思' } }),
    );
    const view = await getLessonPlan('plan/2');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/lesson-plans/plan%2F2`);
    expect(view.currentRevision.data.reflection).toBe('反思');
    expect(view.revision).toBe(4);
  });

  it('autosave：PATCH /lesson-plans/{id}/draft，带 expectedRevision 与幂等 submissionId', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(200, { lessonPlanId: 'plan-1', revision: 5, currentRevision: { data: { title: 't' } } }),
    );
    const view = await patchLessonPlanDraft('plan-1', {
      submissionId: 'sub-9',
      expectedRevision: 4,
      data: emptyLessonData(),
      context: null,
      source: 'manual',
    });
    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/lesson-plans/plan-1/draft`);
    expect(init?.method).toBe('PATCH');
    expect(JSON.parse(String(init?.body))).toMatchObject({ submissionId: 'sub-9', expectedRevision: 4, source: 'manual', context: null });
    expect(view.revision).toBe(5);
  });

  it('409 冲突：原样抛出 ApiError（含 details.currentRevision），不静默重试', async () => {
    stubFetch(() => jsonResponse(409, { code: 'REVISION_CONFLICT', message: '版本冲突', retryable: false, details: { currentRevision: 7 } }));
    await expect(
      patchLessonPlanDraft('plan-1', { submissionId: 'sub', expectedRevision: 4, data: emptyLessonData(), context: null, source: 'manual' }),
    ).rejects.toMatchObject({ status: 409, details: { currentRevision: 7 } });
  });

  it('列表：GET /lesson-plans；数组返回也能归一；结构损坏如实报错', async () => {
    stubFetch(() => jsonResponse(200, [{ lessonPlanId: 'p1', title: 'A', revision: 2, updatedAt: '2026-10-12T00:00:00Z' }]));
    const page = await listLessonPlans();
    expect(page.items).toHaveLength(1);
    expect(page.total).toBe(1);

    stubFetch(() => jsonResponse(200, { nonsense: true }));
    await expect(listLessonPlans()).rejects.toThrow(/结构无法识别/);
  });

  it('导出：POST /lesson-plans/{id}/export 返回 artifact；下载走 export-artifacts', async () => {
    const fetchMock = stubFetch((url) => {
      if (url.endsWith('/export')) {
        return jsonResponse(202, { artifact: { artifactId: 'art-1', fileName: '荷塘月色.docx' } });
      }
      return {
        ok: true,
        status: 200,
        blob: async () => new Blob(['docx']),
        headers: new Headers({ 'content-disposition': "attachment; filename*=UTF-8''%E6%95%99%E6%A1%88.docx" }),
      } as unknown as Response;
    });
    const receipt = await exportLessonPlan('plan-1', {
      data: emptyLessonData(),
      style: {
        fontId: 'puhuiti',
        baseSize: 14,
        headingSize: 16,
        labelSize: 12,
        lineHeight: 1.7,
        pageMargin: 48,
        moduleGap: 16,
        paragraphGap: 6,
      },
      modules: [],
    });
    expect(call(fetchMock, 0).url).toBe(`${API_BASE_PATH}/lesson-plans/plan-1/export`);
    expect(call(fetchMock, 0).init?.method).toBe('POST');
    expect(receipt.artifact).toEqual({ artifactId: 'art-1', fileName: '荷塘月色.docx' });

    const downloaded = await downloadLessonExport('art-1');
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/export-artifacts/art-1/download`);
    expect(downloaded.fileName).toBe('教案.docx');
  });

  it('上传学情文件：multipart（不手写 content-type），响应缺 assetRef 时报错', async () => {
    const fetchMock = stubFetch(() => jsonResponse(201, { assetRef: 'asset-1', fileName: '七一班.xlsx' }));
    const file = new File(['x'], '七一班.xlsx');
    const result = await uploadLessonSource(file);
    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/lesson-plans/source-uploads`);
    expect(init?.method).toBe('POST');
    expect(init?.body).toBeInstanceOf(FormData);
    expect((init?.headers as Record<string, string> | undefined)?.['content-type']).toBeUndefined();
    expect(result.assetRef).toBe('asset-1');

    stubFetch(() => jsonResponse(201, { fileId: 'x' }));
    await expect(uploadLessonSource(file)).rejects.toThrow(/assetRef/);
  });

  it('normalizeLessonView：缺 lessonPlanId 或正文时抛错（不伪造空文档）', () => {
    expect(() => normalizeLessonView({ revision: 1 })).toThrow(/lessonPlanId/);
    expect(() => normalizeLessonView({ lessonPlanId: 'p', revision: 1, currentRevision: {} })).toThrow(/缺少正文/);
    expect(normalizeLessonList({ items: [], total: 0 }).items).toEqual([]);
  });

  it('服务不可达：ApiError SERVICE_UNAVAILABLE（不降级为空文档）', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('failed to fetch'))));
    await expect(getLessonPlan('plan-1')).rejects.toBeInstanceOf(ApiError);
  });

  it('导出对象包含全部端点（页面可注入替身）', () => {
    expect(Object.keys(lessonPlansApi).sort()).toEqual(
      [
        'createLessonPlan',
        'deleteLessonPlan',
        'downloadLessonExport',
        'exportLessonPlan',
        'getLessonPlan',
        'listLessonPlans',
        'patchLessonPlanDraft',
        'uploadLessonSource',
      ].sort(),
    );
  });
});
