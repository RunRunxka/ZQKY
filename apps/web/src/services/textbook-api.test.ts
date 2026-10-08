import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, API_BASE_PATH } from '@/services/api-client';
import type { DocumentMetadataInput } from '@/contracts/textbook';
import {
  cancelJob,
  checkScope,
  commitImport,
  createEmbeddingProfile,
  createImport,
  createLibrary,
  deleteDocument,
  deleteLibrary,
  deleteEmbeddingProfile,
  discardImport,
  fetchTextbookTaxonomy,
  getDocument,
  getDocumentSource,
  getImport,
  getIndexStatus,
  getJob,
  getLibrary,
  getTeachingSettings,
  listDocuments,
  listEmbeddingModels,
  listEmbeddingProfiles,
  listJobs,
  listLibraries,
  patchDocument,
  patchImport,
  patchLibrary,
  probeEmbeddingModel,
  putTeachingSettings,
  retireEmbeddingProfile,
  retryJob,
  startRebuild,
  textbookQuery,
} from '@/services/textbook-api';

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

function ok(body: unknown): Response {
  return jsonResponse(true, 200, body);
}

function call(fetchMock: FetchMock, index = 0) {
  const [input, init] = fetchMock.mock.calls[index] as [RequestInfo | URL, RequestInit?];
  return { url: typeof input === 'string' ? input : input.toString(), init };
}

async function rejected(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    return error as ApiError;
  }
  throw new Error('预期请求失败，但请求成功了');
}

const METADATA: DocumentMetadataInput = {
  title: '七年级数学上册',
  stageId: 'stage-junior',
  gradeIds: ['grade-7'],
  subjectId: 'math',
  editionId: 'renjiao',
  publicationLabel: '2024 年版',
  volumeLabel: '上册',
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('textbookQuery', () => {
  it('只拼接有值的参数并做编码', () => {
    expect(
      textbookQuery({ kind: 'base', gradeId: undefined, subjectId: '', editionId: null }),
    ).toBe('?kind=base');
    expect(textbookQuery({ includeDeleted: false })).toBe('');
    expect(textbookQuery({ includeDeleted: true })).toBe('?includeDeleted=true');
    expect(textbookQuery({ gradeId: '七年级/上' })).toBe(
      '?gradeId=%E4%B8%83%E5%B9%B4%E7%BA%A7%2F%E4%B8%8A',
    );
  });
});

describe('教材字典与逻辑库', () => {
  it('GET /textbook-taxonomy 返回字典', async () => {
    const fetchMock = stubFetch(() =>
      ok({
        stages: [],
        grades: [{ id: 'g7', label: '七年级', stageId: 's1' }],
        subjects: [],
        editions: [],
      }),
    );
    const taxonomy = await fetchTextbookTaxonomy();
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/textbook-taxonomy`);
    expect(call(fetchMock).init?.method).toBeUndefined();
    expect(taxonomy.grades).toHaveLength(1);
  });

  it('GET /textbook-libraries 按 kind 与筛选条件拼接查询串', async () => {
    const fetchMock = stubFetch(() => ok({ libraries: [] }));
    await listLibraries({ kind: 'personal', gradeId: 'g7', subjectId: 'math', editionId: 'rj' });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/textbook-libraries?kind=personal&gradeId=g7&subjectId=math&editionId=rj`,
    );
    await listLibraries({ kind: 'base' });
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/textbook-libraries?kind=base`);
    await listLibraries();
    expect(call(fetchMock, 2).url).toBe(`${API_BASE_PATH}/textbook-libraries`);
  });

  it('GET /textbook-libraries/{id} 对 id 编码', async () => {
    const fetchMock = stubFetch(() => ok({ libraryId: 'lib 1', documents: [] }));
    await getLibrary('lib 1');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/textbook-libraries/lib%201`);
  });

  it('POST /textbook-libraries 提交 JSON 请求体', async () => {
    const fetchMock = stubFetch(() => ok({ libraryId: 'lib-1' }));
    await createLibrary({
      kind: 'base',
      displayName: '七年级数学',
      gradeId: 'g7',
      subjectId: 'math',
      editionId: 'rj',
    });
    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/textbook-libraries`);
    expect(init?.method).toBe('POST');
    expect(init?.headers).toMatchObject({ 'content-type': 'application/json' });
    expect(JSON.parse(String(init?.body))).toEqual({
      kind: 'base',
      displayName: '七年级数学',
      gradeId: 'g7',
      subjectId: 'math',
      editionId: 'rj',
    });
  });

  it('PATCH /textbook-libraries/{id} 带 expectedRevision', async () => {
    const fetchMock = stubFetch(() => ok({ libraryId: 'lib-1', revision: 3 }));
    await patchLibrary('lib-1', { expectedRevision: 2, displayName: '改名' });
    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/textbook-libraries/lib-1`);
    expect(init?.method).toBe('PATCH');
    expect(JSON.parse(String(init?.body))).toEqual({ expectedRevision: 2, displayName: '改名' });
  });

  it('DELETE /textbook-libraries/{id} 以请求体传 expectedRevision，并允许 204', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 204, null));
    const result = await deleteLibrary('lib-1', { expectedRevision: 5 });
    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/textbook-libraries/lib-1`);
    expect(init?.method).toBe('DELETE');
    expect(JSON.parse(String(init?.body))).toEqual({ expectedRevision: 5 });
    expect(result).toBeNull();
  });
});

describe('书册与原文', () => {
  it('GET /textbooks 拼接 libraryId 等筛选', async () => {
    const fetchMock = stubFetch(() => ok({ documents: [] }));
    await listDocuments({ libraryId: 'lib-1', includeDeleted: true });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/textbooks?libraryId=lib-1&includeDeleted=true`,
    );
  });

  it('GET /textbooks/{id} 与 PATCH 使用同一路径的不同方法', async () => {
    const fetchMock = stubFetch(() => ok({ documentId: 'doc-1' }));
    await getDocument('doc-1');
    await patchDocument('doc-1', {
      expectedRevision: 1,
      metadata: METADATA,
      libraryIds: ['lib-1'],
    });
    expect(call(fetchMock, 0).url).toBe(`${API_BASE_PATH}/textbooks/doc-1`);
    expect(call(fetchMock, 0).init?.method).toBeUndefined();
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/textbooks/doc-1`);
    expect(call(fetchMock, 1).init?.method).toBe('PATCH');
    expect(JSON.parse(String(call(fetchMock, 1).init?.body))).toEqual({
      expectedRevision: 1,
      metadata: METADATA,
      libraryIds: ['lib-1'],
    });
  });

  it('DELETE /textbooks/{id} 返回服务端视图', async () => {
    const fetchMock = stubFetch(() =>
      ok({ documentId: 'doc-1', deletedAt: '2026-09-28T00:00:00Z' }),
    );
    const result = await deleteDocument('doc-1', { expectedRevision: 4 });
    expect(call(fetchMock).init?.method).toBe('DELETE');
    expect(JSON.parse(String(call(fetchMock).init?.body))).toEqual({ expectedRevision: 4 });
    expect(result?.documentId).toBe('doc-1');
  });

  it('GET /textbook-revisions/{id}/source 拼接字符区间', async () => {
    const fetchMock = stubFetch(() => ok({ documentRevisionId: 'rev-1', text: '原文' }));
    await getDocumentSource('rev 1', 0, 1200);
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/textbook-revisions/rev%201/source?charStart=0&charEnd=1200`,
    );
  });
});

describe('导入草稿', () => {
  it('POST /textbook-imports 以 multipart 发送 file 与 metadataJson 信封', async () => {
    const fetchMock = stubFetch(() => ok({ draft: { importId: 'imp-1' } }));
    const file = new File(['# 标题'], 'book.md', { type: 'text/markdown' });
    await createImport(file, {
      metadata: METADATA,
      targetDocumentId: 'doc-1',
      expectedCurrentRevisionId: 'rev-1',
      confirmMetadata: true,
    });
    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/textbook-imports`);
    expect(init?.method).toBe('POST');
    // multipart 不得手写 content-type，交给 fetch 生成 boundary
    expect((init?.headers as Record<string, string>)['content-type']).toBeUndefined();
    const form = init?.body as FormData;
    expect(form).toBeInstanceOf(FormData);
    expect((form.get('file') as File).name).toBe('book.md');
    // 更新目标与期望修订在 metadataJson 信封里（不是独立表单字段）
    expect(JSON.parse(String(form.get('metadataJson')))).toEqual({
      metadata: METADATA,
      targetDocumentId: 'doc-1',
      expectedCurrentRevisionId: 'rev-1',
      confirmMetadata: true,
    });
  });

  it('未填写元数据/无更新目标时省略 metadataJson 部件', async () => {
    const fetchMock = stubFetch(() => ok({ draft: { importId: 'imp-2' } }));
    await createImport(new File(['x'], 'a.docx'), null);
    await createImport(new File(['x'], 'a.docx'), {});
    const first = call(fetchMock, 0).init?.body as FormData;
    expect(first.get('metadataJson')).toBeNull();
    expect(first.get('file')).not.toBeNull();
    const second = call(fetchMock, 1).init?.body as FormData;
    expect(second.get('metadataJson')).toBeNull();
  });

  it('GET/PATCH /textbook-imports/{id} 使用草稿 id 与 expectedRevision', async () => {
    const fetchMock = stubFetch(() => ok({ importId: 'imp-1', revision: 2 }));
    await getImport('imp-1');
    await patchImport('imp-1', { expectedRevision: 1, metadata: METADATA });
    expect(call(fetchMock, 0).url).toBe(`${API_BASE_PATH}/textbook-imports/imp-1`);
    expect(call(fetchMock, 1).init?.method).toBe('PATCH');
    expect(JSON.parse(String(call(fetchMock, 1).init?.body))).toEqual({
      expectedRevision: 1,
      metadata: METADATA,
    });
  });

  it('POST /textbook-imports/{id}/commit 提交幂等键与库归属，返回裸 JobView', async () => {
    const fetchMock = stubFetch(() => ok({ jobId: 'job-1', state: 'queued', attempt: 1 }));
    const job = await commitImport('imp-1', {
      expectedRevision: 3,
      submissionId: 'sub-12345678',
      libraryIds: ['lib-1', 'lib-2'],
      acknowledgeWarnings: true,
    });
    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/textbook-imports/imp-1/commit`);
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({
      expectedRevision: 3,
      submissionId: 'sub-12345678',
      libraryIds: ['lib-1', 'lib-2'],
      acknowledgeWarnings: true,
    });
    // v1.1 冻结：commit 直接返回 JobView，不再有 {draft, job} 包裹
    expect(job.jobId).toBe('job-1');
    expect(job.state).toBe('queued');
  });
});

describe('入库任务', () => {
  it('GET /textbook-jobs 与 GET /textbook-jobs/{id}', async () => {
    const fetchMock = stubFetch(() => ok({ jobs: [] }));
    await listJobs();
    await getJob('job 1');
    expect(call(fetchMock, 0).url).toBe(`${API_BASE_PATH}/textbook-jobs`);
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/textbook-jobs/job%201`);
  });

  it('POST cancel/retry 到对应子路径', async () => {
    const fetchMock = stubFetch(() => ok({ jobId: 'job-1', state: 'cancelled' }));
    await cancelJob('job-1');
    await retryJob('job-1');
    expect(call(fetchMock, 0).url).toBe(`${API_BASE_PATH}/textbook-jobs/job-1/cancel`);
    expect(call(fetchMock, 0).init?.method).toBe('POST');
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/textbook-jobs/job-1/retry`);
    expect(call(fetchMock, 1).init?.method).toBe('POST');
  });
});

describe('任教范围', () => {
  it('GET/PUT /teaching-settings 与 POST /teaching-settings/scope-check', async () => {
    const fetchMock = stubFetch(() => ok({ ownerId: 'local-user', revision: 1 }));
    const selection = { gradeId: 'g7', subjectId: 'math', editionId: 'rj', documentIds: ['doc-1'] };
    await getTeachingSettings();
    await putTeachingSettings({ expectedRevision: 1, selection });
    await checkScope(selection);
    expect(call(fetchMock, 0).url).toBe(`${API_BASE_PATH}/teaching-settings`);
    expect(call(fetchMock, 1).init?.method).toBe('PUT');
    expect(call(fetchMock, 2).url).toBe(`${API_BASE_PATH}/teaching-settings/scope-check`);
    expect(call(fetchMock, 2).init?.method).toBe('POST');
    expect(JSON.parse(String(call(fetchMock, 2).init?.body))).toEqual({ selection });
  });
});

describe('Embedding 与索引代', () => {
  it('GET /embedding-models、POST /embedding-probes、GET|POST /embedding-profiles', async () => {
    const fetchMock = stubFetch(() => ok({ profiles: [], activeProfileId: null }));
    await listEmbeddingModels();
    await probeEmbeddingModel({ modelName: 'bge-m3' });
    await listEmbeddingProfiles();
    await createEmbeddingProfile({ modelName: 'bge-m3', normalization: 'l2' });
    expect(call(fetchMock, 0).url).toBe(`${API_BASE_PATH}/embedding-models`);
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/embedding-probes`);
    expect(call(fetchMock, 1).init?.method).toBe('POST');
    expect(JSON.parse(String(call(fetchMock, 1).init?.body))).toEqual({ modelName: 'bge-m3' });
    expect(call(fetchMock, 2).url).toBe(`${API_BASE_PATH}/embedding-profiles`);
    expect(call(fetchMock, 3).url).toBe(`${API_BASE_PATH}/embedding-profiles`);
    expect(call(fetchMock, 3).init?.method).toBe('POST');
    expect(JSON.parse(String(call(fetchMock, 3).init?.body))).toEqual({
      modelName: 'bge-m3',
      normalization: 'l2',
    });
  });

  it('GET /textbook-index/status 与 POST /textbook-index/rebuilds', async () => {
    const fetchMock = stubFetch(() => ok({ activeGenerationId: null }));
    await getIndexStatus();
    await startRebuild({ submissionId: 'sub-abcdefgh', profileId: 'profile-1' });
    expect(call(fetchMock, 0).url).toBe(`${API_BASE_PATH}/textbook-index/status`);
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/textbook-index/rebuilds`);
    expect(call(fetchMock, 1).init?.method).toBe('POST');
    expect(JSON.parse(String(call(fetchMock, 1).init?.body))).toEqual({
      submissionId: 'sub-abcdefgh',
      profileId: 'profile-1',
    });
  });
});

describe('错误语义', () => {
  it('后端错误信封转换为 ApiError 并保留 code/status/retryable/requestId', async () => {
    stubFetch(() =>
      jsonResponse(false, 409, {
        code: 'REVISION_CONFLICT',
        message: '版本冲突，请刷新后重试。',
        requestId: 'req-9',
        retryable: false,
      }),
    );
    const error = await rejected(listLibraries({ kind: 'base' }));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe('REVISION_CONFLICT');
    expect(error.status).toBe(409);
    expect(error.retryable).toBe(false);
    expect(error.requestId).toBe('req-9');
    expect(error.message).toBe('版本冲突，请刷新后重试。');
  });

  it('无信封的 503 归类为可重试的服务不可用', async () => {
    stubFetch(() => jsonResponse(false, 503, 'oops'));
    const error = await rejected(getIndexStatus());
    expect(error.code).toBe('SERVICE_UNAVAILABLE');
    expect(error.retryable).toBe(true);
  });

  it('网络异常不返回空数据，抛可重试 ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new Error('offline'))),
    );
    const error = await rejected(listJobs());
    expect(error.code).toBe('SERVICE_UNAVAILABLE');
    expect(error.status).toBe(0);
  });
});

describe('导入放弃与 Embedding 配置停用/删除（本批新增端点）', () => {
  it('放弃导入草稿：POST /textbook-imports/{id}/discard 提交 expectedRevision 并返回草稿视图', async () => {
    const fetchMock = stubFetch(() =>
      ok({ importId: 'imp-1', state: 'discarded', revision: 3 }),
    );
    const draft = await discardImport('imp 1', { expectedRevision: 2 });
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/textbook-imports/imp%201/discard`);
    expect(JSON.parse(String(call(fetchMock).init?.body))).toEqual({ expectedRevision: 2 });
    expect(draft.state).toBe('discarded');
  });

  it('停用配置：POST /embedding-profiles/{id}/retire 无请求体，返回含 retiredAt 的视图', async () => {
    const fetchMock = stubFetch(() =>
      ok({ profileId: 'prof-1', retiredAt: '2026-10-07T00:00:00Z', isActive: false }),
    );
    const profile = await retireEmbeddingProfile('prof-1');
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/embedding-profiles/prof-1/retire`);
    expect(call(fetchMock).init?.body).toBeUndefined();
    expect(profile.retiredAt).toBe('2026-10-07T00:00:00Z');
    expect(profile.isActive).toBe(false);
  });

  it('删除配置：DELETE /embedding-profiles/{id} 允许 204（归一为 undefined）', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 204, null));
    const result = await deleteEmbeddingProfile('prof-1');
    expect(call(fetchMock).init?.method).toBe('DELETE');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/embedding-profiles/prof-1`);
    expect(call(fetchMock).init?.body).toBeUndefined();
    expect(result).toBeUndefined();
  });
});
