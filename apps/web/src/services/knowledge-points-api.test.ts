import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, API_BASE_PATH } from '@/services/api-client';
import type { KnowledgePointView } from '@/contracts/knowledge';
import {
  archiveKnowledgePoint,
  confirmKnowledgeImport,
  createKnowledgeExtractionJobs,
  createKnowledgeImport,
  createKnowledgePoint,
  createKnowledgeSuggestionJob,
  createTextbookLink,
  deleteKnowledgePoint,
  deleteTextbookLink,
  discardKnowledgeImport,
  getKnowledgeImport,
  getKnowledgePoint,
  knowledgeQuery,
  listKnowledgeImports,
  listKnowledgePoints,
  listTextbookLinks,
  patchKnowledgeImport,
  previewKnowledgeExtraction,
  restoreKnowledgePoint,
  updateKnowledgePoint,
} from '@/services/knowledge-points-api';

type FetchMock = ReturnType<typeof vi.fn>;

function stubFetch(handler: (url: string, init?: RequestInit) => unknown) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init)),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock as unknown as FetchMock;
}

function jsonResponse(ok: boolean, status: number, body: unknown, headers?: HeadersInit) {
  return { ok, status, json: async () => body, headers: new Headers(headers) } as Response;
}

function ok(body: unknown, status = 200): Response {
  return jsonResponse(true, status, body);
}

function call(fetchMock: FetchMock, index = 0) {
  const [input, init] = fetchMock.mock.calls[index] as [RequestInfo | URL, RequestInit?];
  return { url: typeof input === 'string' ? input : input.toString(), init };
}

function bodyOf(fetchMock: FetchMock, index = 0): unknown {
  const raw = call(fetchMock, index).init?.body;
  return typeof raw === 'string' ? JSON.parse(raw) : raw;
}

async function rejected(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    return error as ApiError;
  }
  throw new Error('预期请求失败，但请求成功了');
}

function pointView(overrides: Partial<KnowledgePointView> = {}): KnowledgePointView {
  return {
    id: 'kp-1',
    subjectId: 'math',
    code: 'M.7.1',
    name: '有理数',
    description: '整数与分数',
    parentId: null,
    parentCode: null,
    sortOrder: 0,
    status: 'active',
    revision: 3,
    revisionId: 'kr-3',
    version: 2,
    aliases: ['有理数概念'],
    createdAt: '2026-09-30T00:00:00Z',
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('knowledgeQuery', () => {
  it('只拼接有值的参数并做编码（数字 0 保留）', () => {
    expect(knowledgeQuery({ subjectId: 'math', status: 'active' })).toBe(
      '?subjectId=math&status=active',
    );
    expect(knowledgeQuery({ q: undefined, parentId: null, offset: 0 })).toBe('?offset=0');
    expect(knowledgeQuery({ q: '有理/数' })).toBe('?q=%E6%9C%89%E7%90%86%2F%E6%95%B0');
    expect(knowledgeQuery({})).toBe('');
  });
});

describe('知识点', () => {
  it('GET /knowledge-points 拼接筛选与分页；无筛选只请求路径', async () => {
    const fetchMock = stubFetch(() => ok({ items: [], total: 0, offset: 0, limit: 50 }));
    await listKnowledgePoints({
      subjectId: 'math',
      status: 'archived',
      q: '函数',
      offset: 0,
      limit: 20,
    });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/knowledge-points?subjectId=math&status=archived&q=%E5%87%BD%E6%95%B0&offset=0&limit=20`,
    );

    await listKnowledgePoints();
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/knowledge-points`);
  });

  it('GET /knowledge-points 支持 scope 与 gradeId（任教范围 / 学科全部 + 年级过滤）', async () => {
    const fetchMock = stubFetch(() => ok({ items: [], total: 0, offset: 0, limit: 50 }));
    await listKnowledgePoints({ scope: 'taught', gradeId: 'grade-7', limit: 100 });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/knowledge-points?scope=taught&gradeId=grade-7&limit=100`,
    );

    await listKnowledgePoints({ subjectId: 'math', scope: 'subject' });
    expect(call(fetchMock, 1).url).toBe(
      `${API_BASE_PATH}/knowledge-points?subjectId=math&scope=subject`,
    );
  });

  it('scope=taught 未就绪时原样抛出 409 KNOWLEDGE_SCOPE_UNAVAILABLE（不当空列表）', async () => {
    stubFetch(() =>
      jsonResponse(false, 409, {
        code: 'KNOWLEDGE_SCOPE_UNAVAILABLE',
        message: '尚未保存任教范围，无法按任教范围筛选知识点。',
        retryable: false,
      }),
    );
    const error = await rejected(listKnowledgePoints({ scope: 'taught' }));
    expect(error.code).toBe('KNOWLEDGE_SCOPE_UNAVAILABLE');
    expect(error.status).toBe(409);
    expect(error.message).toContain('尚未保存任教范围');
  });

  it('DELETE /knowledge-points/{id} 带 expectedRevision；引用计数随 409 错误保留', async () => {
    const fetchMock = stubFetch(() => ({ ok: true, status: 204, json: async () => null }));
    await deleteKnowledgePoint('kp 1', 3);
    expect(call(fetchMock).init?.method).toBe('DELETE');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/knowledge-points/kp%201?expectedRevision=3`);

    stubFetch(() =>
      jsonResponse(false, 409, {
        code: 'KNOWLEDGE_POINT_IN_USE',
        message: '知识点仍在使用中：存在教材依据、原卷题目或题库引用，先解除引用或改用归档。',
        retryable: false,
        details: {
          counts: [
            { library: 'knowledge', key: 'textbookKnowledgeLinks', count: 2 },
            { library: 'teaching', key: 'paperItemKnowledge', count: 0 },
            { library: 'question_bank', key: 'questionKnowledgeLinks', count: 6 },
            { library: 'question_bank', key: 'questionDraftKnowledgeLinks', count: 1 },
          ],
        },
      }),
    );
    const error = await rejected(deleteKnowledgePoint('kp-1', 3));
    expect(error.code).toBe('KNOWLEDGE_POINT_IN_USE');
    expect(error.status).toBe(409);
    // 错误信封的 details 原样保留（界面据此渲染原因清单，不重新请求）
    const details = error.details as { counts?: unknown } | undefined;
    expect(details?.counts).toEqual([
      { library: 'knowledge', key: 'textbookKnowledgeLinks', count: 2 },
      { library: 'teaching', key: 'paperItemKnowledge', count: 0 },
      { library: 'question_bank', key: 'questionKnowledgeLinks', count: 6 },
      { library: 'question_bank', key: 'questionDraftKnowledgeLinks', count: 1 },
    ]);
  });

  it('POST /knowledge-points 用 JSON 提交人工建立请求', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 201, pointView()));
    await createKnowledgePoint({
      subjectId: 'math',
      code: 'M.7.1',
      name: '有理数',
      parentCode: 'M.7',
      sortOrder: 1,
      aliases: ['有理数概念'],
    });

    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/knowledge-points`);
    expect(init?.method).toBe('POST');
    expect((init?.headers as Record<string, string>)['content-type']).toBe('application/json');
    expect(bodyOf(fetchMock)).toEqual({
      subjectId: 'math',
      code: 'M.7.1',
      name: '有理数',
      parentCode: 'M.7',
      sortOrder: 1,
      aliases: ['有理数概念'],
    });
  });

  it('GET /knowledge-points/{id} 与 PATCH 使用同一路径并按 id 编码', async () => {
    const fetchMock = stubFetch(() => ok(pointView({ id: 'kp/1' })));
    await getKnowledgePoint('kp/1');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/knowledge-points/kp%2F1`);

    await updateKnowledgePoint('kp/1', {
      expectedRevision: 3,
      name: '有理数与无理数',
      clearFields: ['description'],
    });
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/knowledge-points/kp%2F1`);
    expect(call(fetchMock, 1).init?.method).toBe('PATCH');
    expect(bodyOf(fetchMock, 1)).toEqual({
      expectedRevision: 3,
      name: '有理数与无理数',
      clearFields: ['description'],
    });
  });

  it('归档 / 恢复走各自的 POST 路径并带 expectedRevision', async () => {
    const fetchMock = stubFetch(() => ok(pointView({ status: 'archived' })));
    await archiveKnowledgePoint('kp-1', 3);
    await restoreKnowledgePoint('kp-1', 4);
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/knowledge-points/kp-1/archive`);
    expect(bodyOf(fetchMock)).toEqual({ expectedRevision: 3 });
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/knowledge-points/kp-1/restore`);
    expect(bodyOf(fetchMock, 1)).toEqual({ expectedRevision: 4 });
  });
});

describe('教材依据', () => {
  it('GET / POST / DELETE 教材依据（DELETE 带 expectedRevision 查询参数，204 归一为 undefined）', async () => {
    const fetchMock = stubFetch((url, init) => {
      if (init?.method === 'DELETE')
        return { ok: true, status: 204, json: async () => null } as Response;
      if (init?.method === 'POST') return ok({ linkId: 'ln-1' }, 201);
      return ok({ items: [] });
    });

    await listTextbookLinks('kp/1');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/knowledge-points/kp%2F1/textbook-links`);

    await createTextbookLink('kp/1', {
      expectedRevision: 3,
      documentRevisionId: 'rev-9',
      charStart: 100,
      charEnd: 160,
      source: 'human',
    });
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/knowledge-points/kp%2F1/textbook-links`);
    expect(bodyOf(fetchMock, 1)).toMatchObject({
      expectedRevision: 3,
      documentRevisionId: 'rev-9',
      charStart: 100,
      charEnd: 160,
    });

    await expect(deleteTextbookLink('kp/1', 'ln/2', 3)).resolves.toBeUndefined();
    expect(call(fetchMock, 2).url).toBe(
      `${API_BASE_PATH}/knowledge-points/kp%2F1/textbook-links/ln%2F2?expectedRevision=3`,
    );
    expect(call(fetchMock, 2).init?.method).toBe('DELETE');
  });

  it('教材不可用（503 TEXTBOOK_EVIDENCE_UNAVAILABLE）原样抛 ApiError，不当成空列表', async () => {
    stubFetch(() =>
      jsonResponse(false, 503, {
        code: 'TEXTBOOK_EVIDENCE_UNAVAILABLE',
        message: '教材目录未装配。',
        retryable: true,
      }),
    );

    const error = await rejected(listTextbookLinks('kp-1'));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe('TEXTBOOK_EVIDENCE_UNAVAILABLE');
    expect(error.status).toBe(503);
    expect(error.retryable).toBe(true);
  });
});

describe('表格导入', () => {
  it('POST /knowledge-imports 以 multipart 上传并带 subjectId / mappingJson / sheetName', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 201, { importId: 'imp-1' }));
    const file = new File(['编码,名称\nM.1,有理数'], '知识点.csv', { type: 'text/csv' });

    await createKnowledgeImport(file, {
      subjectId: 'math',
      mapping: { code: '编码', name: '名称' },
      sheetName: 'Sheet1',
    });

    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/knowledge-imports`);
    expect(init?.method).toBe('POST');
    // 不手写 content-type，交给 fetch 生成 multipart boundary
    expect((init?.headers as Record<string, string> | undefined)?.['content-type']).toBeUndefined();
    const form = init?.body as FormData;
    expect(form).toBeInstanceOf(FormData);
    expect(form.get('file')).toBe(file);
    expect(form.get('subjectId')).toBe('math');
    expect(form.get('mappingJson')).toBe(JSON.stringify({ code: '编码', name: '名称' }));
    expect(form.get('sheetName')).toBe('Sheet1');
  });

  it('未提供映射与工作表时只发送 file 与 subjectId', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 201, { importId: 'imp-1' }));
    await createKnowledgeImport(new File(['x'], 'a.csv'), { subjectId: 'math' });
    const form = call(fetchMock).init?.body as FormData;
    expect(form.get('mappingJson')).toBeNull();
    expect(form.get('sheetName')).toBeNull();
    expect(form.get('subjectId')).toBe('math');
  });

  it('列表 / 详情 / 补丁 / 确认 路径与请求体', async () => {
    const fetchMock = stubFetch(() => ok({ importId: 'imp-1', revision: 2 }));

    await listKnowledgeImports({ state: 'reviewing', offset: 0, limit: 50 });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/knowledge-imports?state=reviewing&offset=0&limit=50`,
    );

    await getKnowledgeImport('imp/1');
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/knowledge-imports/imp%2F1`);

    await patchKnowledgeImport('imp-1', {
      expectedRevision: 2,
      rows: [{ rowNo: 3, decision: 'update', expectedRevision: 7 }],
    });
    expect(call(fetchMock, 2).init?.method).toBe('PATCH');
    expect(bodyOf(fetchMock, 2)).toEqual({
      expectedRevision: 2,
      rows: [{ rowNo: 3, decision: 'update', expectedRevision: 7 }],
    });

    await confirmKnowledgeImport('imp-1', {
      expectedRevision: 2,
      submissionId: 'sub-1',
      actions: [{ rowNo: 3, decision: 'update' }],
    });
    expect(call(fetchMock, 3).url).toBe(`${API_BASE_PATH}/knowledge-imports/imp-1/confirm`);
    expect(bodyOf(fetchMock, 3)).toEqual({
      expectedRevision: 2,
      submissionId: 'sub-1',
      actions: [{ rowNo: 3, decision: 'update' }],
    });
  });

  it('确认重放结果（replayed: true）原样返回，不在这里改写', async () => {
    stubFetch(() =>
      ok({
        importId: 'imp-1',
        state: 'confirmed',
        created: [],
        updated: [],
        ignored: [],
        replayed: true,
      }),
    );
    const result = await confirmKnowledgeImport('imp-1', {
      expectedRevision: 2,
      submissionId: 'sub-1',
    });
    expect(result.replayed).toBe(true);
    expect(result.state).toBe('confirmed');
  });
});

describe('AI 候选任务', () => {
  it('POST /knowledge-suggestion-jobs 提交冻结模型与证据，返回任务视图（202 只代表接受）', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 202, {
        jobId: 'job-1',
        domain: 'knowledge',
        kind: 'suggestion',
        attempt: 1,
        state: 'queued',
        result: null,
        error: null,
      }),
    );

    const view = await createKnowledgeSuggestionJob({
      modelProfileId: 'p-chat-1',
      subjectId: 'math',
      materials: [{ id: 'm1', text: '有理数的定义' }],
      textbookEvidence: [{ documentRevisionId: 'rev-9', charStart: 0, charEnd: 40 }],
      instructions: '只提出上位概念',
    });

    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/knowledge-suggestion-jobs`);
    expect(init?.method).toBe('POST');
    expect(bodyOf(fetchMock)).toEqual({
      modelProfileId: 'p-chat-1',
      subjectId: 'math',
      materials: [{ id: 'm1', text: '有理数的定义' }],
      textbookEvidence: [{ documentRevisionId: 'rev-9', charStart: 0, charEnd: 40 }],
      instructions: '只提出上位概念',
    });
    expect(view.state).toBe('queued');
    expect(view.attempt).toBe(1);
  });

  it('错误信封（含 details.issues）转换为 ApiError 并保留定位信息', async () => {
    stubFetch(() =>
      jsonResponse(false, 422, {
        code: 'KNOWLEDGE_SUGGESTION_NO_EVIDENCE',
        message: 'AI 候选至少需要一份证据。',
        retryable: false,
        details: { fields: ['materials', 'textbookEvidence'] },
      }),
    );

    const error = await rejected(
      createKnowledgeSuggestionJob({ modelProfileId: 'p-1', subjectId: 'math' }),
    );
    expect(error.code).toBe('KNOWLEDGE_SUGGESTION_NO_EVIDENCE');
    expect(error.details?.fields).toEqual(['materials', 'textbookEvidence']);
  });

  it('网络失败转换为可重试的 SERVICE_UNAVAILABLE，不返回空列表', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new Error('connect ECONNREFUSED'))),
    );
    const error = await rejected(listKnowledgePoints());
    expect(error.code).toBe('SERVICE_UNAVAILABLE');
    expect(error.status).toBe(0);
    expect(error.retryable).toBe(true);
  });
});

describe('放弃未确认批次', () => {
  it('POST /knowledge-imports/{id}/discard 提交 expectedRevision 并返回权威批次视图', async () => {
    const fetchMock = stubFetch(() =>
      ok({
        importId: 'imp-1',
        source: 'file',
        subjectId: 'math',
        state: 'cancelled',
        revision: 4,
        rows: [],
        createdAt: '2026-10-01T00:00:00Z',
        updatedAt: '2026-10-01T00:00:00Z',
      }),
    );
    const view = await discardKnowledgeImport('imp 1', { expectedRevision: 3 });
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/knowledge-imports/imp%201/discard`);
    expect(bodyOf(fetchMock)).toEqual({ expectedRevision: 3 });
    expect(view.state).toBe('cancelled');
    expect(view.revision).toBe(4);
  });
});

describe('从教材提取（任务③）', () => {
  it('GET /knowledge-extraction/preview 带 subjectId，返回扁平合计字段', async () => {
    const fetchMock = stubFetch(() =>
      ok({
        subjectId: 'math',
        documents: [
          {
            documentId: 'doc-1',
            title: '七年级上册',
            gradeIds: ['grade-7'],
            revisionId: 'rev-1',
            chunkCount: 120,
            approxChars: 45678,
            indexReady: true,
            reason: null,
          },
          {
            documentId: 'doc-2',
            title: '七年级下册',
            gradeIds: [],
            revisionId: null,
            chunkCount: 0,
            approxChars: 0,
            indexReady: false,
            reason: '该教材尚未发布有效修订。',
          },
        ],
        totalDocuments: 2,
        readyDocuments: 1,
        totalChunks: 120,
        approxChars: 45678,
      }),
    );
    const preview = await previewKnowledgeExtraction('math');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/knowledge-extraction/preview?subjectId=math`);
    expect(preview.totalDocuments).toBe(2);
    expect(preview.readyDocuments).toBe(1);
    expect(preview.totalChunks).toBe(120);
    expect(preview.approxChars).toBe(45678);
    expect(preview.documents[1].reason).toBe('该教材尚未发布有效修订。');
  });

  it('预览读取失败不降级为空教材清单（503 TEXTBOOK_EVIDENCE_UNAVAILABLE 原样抛出）', async () => {
    stubFetch(() =>
      jsonResponse(false, 503, {
        code: 'TEXTBOOK_EVIDENCE_UNAVAILABLE',
        message: '教材目录未装配，无法预览提取来源。',
        retryable: true,
      }),
    );
    const error = await rejected(previewKnowledgeExtraction('math'));
    expect(error.code).toBe('TEXTBOOK_EVIDENCE_UNAVAILABLE');
    expect(error.status).toBe(503);
  });

  it('POST /knowledge-extraction-jobs 提交冻结请求体并返回每册一个任务视图', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 202, [
        {
          jobId: 'job-1',
          domain: 'knowledge',
          kind: 'suggestion',
          attempt: 0,
          state: 'queued',
          result: null,
          error: null,
        },
        {
          jobId: 'job-2',
          domain: 'knowledge',
          kind: 'suggestion',
          attempt: 0,
          state: 'queued',
          result: null,
          error: null,
        },
      ]),
    );
    const views = await createKnowledgeExtractionJobs({
      submissionId: 'sub-1',
      modelProfileId: 'p-chat-1',
      subjectId: 'math',
      documentIds: ['doc-1', 'doc-3'],
    });
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/knowledge-extraction-jobs`);
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(bodyOf(fetchMock)).toEqual({
      submissionId: 'sub-1',
      modelProfileId: 'p-chat-1',
      subjectId: 'math',
      documentIds: ['doc-1', 'doc-3'],
    });
    expect(views.map((view) => view.jobId)).toEqual(['job-1', 'job-2']);
  });

  it('未就绪书册 409 KNOWLEDGE_EXTRACTION_NOT_READY 逐册保留原因，不部分受理', async () => {
    stubFetch(() =>
      jsonResponse(false, 409, {
        code: 'KNOWLEDGE_EXTRACTION_NOT_READY',
        message: '以下教材尚未就绪，无法发起提取：七年级下册。',
        retryable: false,
        details: {
          documents: [
            {
              documentId: 'doc-2',
              title: '七年级下册',
              reason: '该教材尚未发布有效修订。',
            },
          ],
        },
      }),
    );
    const error = await rejected(
      createKnowledgeExtractionJobs({
        submissionId: 'sub-1',
        modelProfileId: 'p-chat-1',
        subjectId: 'math',
        documentIds: ['doc-2'],
      }),
    );
    expect(error.code).toBe('KNOWLEDGE_EXTRACTION_NOT_READY');
    expect(error.status).toBe(409);
    const details = error.details as { documents?: unknown } | undefined;
    expect(details?.documents).toEqual([
      { documentId: 'doc-2', title: '七年级下册', reason: '该教材尚未发布有效修订。' },
    ]);
  });
});
