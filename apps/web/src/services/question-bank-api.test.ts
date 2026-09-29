import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, API_BASE_PATH } from '@/services/api-client';
import type {
  DraftView,
  QuestionConfirmRequest,
  QuestionContent,
  QuestionMetadata,
} from '@/contracts/question-bank';
import {
  applyQuestionSuggestion,
  confirmQuestionImport,
  createQuestionImport,
  deleteQuestion,
  getQuestion,
  getQuestionImport,
  listQuestionImports,
  listQuestions,
  mergeQuestionDrafts,
  normalizeOrganizeResult,
  organizeQuestions,
  patchQuestion,
  patchQuestionDraft,
  questionBankQuery,
  splitQuestionDraft,
} from '@/services/question-bank-api';

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

const METADATA: QuestionMetadata = {
  stageId: 'stage-junior',
  gradeId: 'grade-7',
  subjectId: 'math',
  editionId: 'renjiao',
  knowledgeTags: ['有理数'],
  difficulty: 'easy',
};

const CONTENT: QuestionContent = {
  type: 'single_choice',
  stemMarkdown: '下列说法正确的是？',
  options: [
    { key: 'A', textMarkdown: '选项 A' },
    { key: 'B', textMarkdown: '选项 B' },
  ],
  answer: { choiceKeys: ['A'], accepted: null, textMarkdown: null },
  explanationMarkdown: null,
  assetIds: [],
};

function draftView(overrides: Partial<DraftView> = {}): DraftView {
  return {
    draftId: 'd-1',
    importId: 'imp-1',
    revision: 3,
    content: CONTENT,
    metadata: METADATA,
    sourceSpans: [{ blockId: 'b-1', charStart: 10, charEnd: 40 }],
    extractionMethod: 'rule',
    reviewState: 'needs_review',
    missingAnswerAcknowledged: false,
    warnings: [],
    duplicateOfQuestionId: null,
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('questionBankQuery', () => {
  it('只拼接有值的参数并做编码（数字 0 保留）', () => {
    expect(questionBankQuery({ draftId: 'd-1' })).toBe('?draftId=d-1');
    expect(questionBankQuery({ draftId: undefined, status: null, q: '' })).toBe('');
    expect(questionBankQuery({ offset: 0, limit: 20 })).toBe('?offset=0&limit=20');
    expect(questionBankQuery({ q: '一元/二次' })).toBe(
      '?q=%E4%B8%80%E5%85%83%2F%E4%BA%8C%E6%AC%A1',
    );
  });
});

describe('导入批次', () => {
  it('POST /question-imports 以 multipart 上传并带上可选分类字段', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 201, { importId: 'imp-1' }));
    const file = new File(['题干'], '七年级数学.md', { type: 'text/markdown' });

    await createQuestionImport(file, { subjectId: 'math', gradeId: 'grade-7' });

    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/question-imports`);
    expect(init?.method).toBe('POST');
    // 不手写 content-type，交给 fetch 生成 multipart boundary
    expect((init?.headers as Record<string, string> | undefined)?.['content-type']).toBeUndefined();
    const form = init?.body as FormData;
    expect(form).toBeInstanceOf(FormData);
    expect(form.get('file')).toBe(file);
    expect(form.get('subjectId')).toBe('math');
    expect(form.get('gradeId')).toBe('grade-7');
  });

  it('未填写分类时只发送 file 部件', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 201, {}));
    await createQuestionImport(new File(['x'], 'a.md'), { subjectId: '', gradeId: undefined });
    const form = call(fetchMock).init?.body as FormData;
    expect(form.get('subjectId')).toBeNull();
    expect(form.get('gradeId')).toBeNull();
    expect(form.get('file')).toBeInstanceOf(File);
  });

  it('GET /question-imports 列出批次', async () => {
    const fetchMock = stubFetch(() =>
      ok({
        imports: [
          {
            importId: 'imp-1',
            ownerId: 'local-user',
            state: 'needs_review',
            revision: 1,
            uploadedFileName: 'a.md',
            uploadedBytes: 10,
            draftCount: 2,
            reviewedCount: 1,
            unassignedCount: 3,
            warnings: [],
            createdAt: '2026-09-28T00:00:00Z',
          },
        ],
      }),
    );

    const list = await listQuestionImports();
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/question-imports`);
    expect(call(fetchMock).init?.method).toBeUndefined();
    expect(list.imports[0]?.unassignedCount).toBe(3);
  });

  it('GET /question-imports/{id} 按 id 编码取详情', async () => {
    const fetchMock = stubFetch(() => ok({ importId: 'imp/1' }));
    await getQuestionImport('imp/1');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/question-imports/imp%2F1`);
  });
});

describe('草稿校对', () => {
  it('PATCH /question-drafts/{id} 发送 expectedRevision 与显式 reviewState', async () => {
    const fetchMock = stubFetch(() => ok(draftView({ reviewState: 'needs_review' })));

    const updated = await patchQuestionDraft('d-1', {
      expectedRevision: 3,
      content: CONTENT,
      metadata: METADATA,
      reviewState: 'reviewed',
      missingAnswerAcknowledged: true,
    });

    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/question-drafts/d-1`);
    expect(init?.method).toBe('PATCH');
    expect((init?.headers as Record<string, string>)['content-type']).toBe('application/json');
    expect(bodyOf(fetchMock)).toMatchObject({
      expectedRevision: 3,
      reviewState: 'reviewed',
      missingAnswerAcknowledged: true,
    });
    expect(updated.reviewState).toBe('needs_review');
  });

  it('POST /question-imports/{id}/split 的 draftId 走查询参数', async () => {
    const fetchMock = stubFetch(() => ok({ importId: 'imp-1' }));

    await splitQuestionDraft('imp-1', 'd-1', { expectedRevision: 2, charOffset: 120 });

    const { url, init } = call(fetchMock);
    expect(url).toBe(`${API_BASE_PATH}/question-imports/imp-1/split?draftId=d-1`);
    expect(init?.method).toBe('POST');
    expect(bodyOf(fetchMock)).toEqual({ expectedRevision: 2, charOffset: 120 });
  });

  it('split 未指定草稿时不写 draftId 查询参数', async () => {
    const fetchMock = stubFetch(() => ok({ importId: 'imp-1' }));
    await splitQuestionDraft('imp-1', null, { expectedRevision: 2, charOffset: 120 });
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/question-imports/imp-1/split`);
  });

  it('POST /question-imports/{id}/merge 发送 expectedRevisions 映射', async () => {
    const fetchMock = stubFetch(() => ok({ importId: 'imp-1' }));

    await mergeQuestionDrafts('imp-1', { expectedRevisions: { 'd-1': 2, 'd-2': 5 } });

    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/question-imports/imp-1/merge`);
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(bodyOf(fetchMock)).toEqual({ expectedRevisions: { 'd-1': 2, 'd-2': 5 } });
  });
});

describe('AI 整理建议', () => {
  it('POST organize 发送 draftIds/includeUnassigned/modelProfileId 并透传建议明细', async () => {
    const fetchMock = stubFetch(() =>
      ok({
        jobId: 'job-1',
        state: 'succeeded',
        suggestionCount: 1,
        failedBatches: 0,
        errorCode: null,
        suggestions: [
          {
            suggestionId: 'sg-1',
            organizationJobId: 'job-1',
            targetDraftId: 'd-1',
            baseDraftRevision: 3,
            proposedContent: CONTENT,
            proposedMetadata: METADATA,
            sourceBlockIds: ['b-1'],
            state: 'pending',
            note: null,
          },
        ],
      }),
    );

    const result = await organizeQuestions('imp-1', {
      draftIds: ['d-1'],
      includeUnassigned: false,
      // v1.1：当前聊天模型 profile id（本地/云端一视同仁），原样透传
      modelProfileId: 'p-chat-1',
    });

    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/question-imports/imp-1/organize`);
    expect(bodyOf(fetchMock)).toEqual({
      draftIds: ['d-1'],
      includeUnassigned: false,
      modelProfileId: 'p-chat-1',
    });
    // 不得把模型名当 profile id 发出去
    expect((bodyOf(fetchMock) as { modelProfileId: string }).modelProfileId).not.toBe(
      CONTENT.stemMarkdown,
    );
    expect(result.suggestionCount).toBe(1);
    expect(result.suggestions).toHaveLength(1);
    expect(result.suggestions[0]?.suggestionId).toBe('sg-1');
  });

  it('透传任务级错误码与失败批原因，不由客户端改写', async () => {
    stubFetch(() =>
      ok({
        jobId: 'job-3',
        state: 'failed',
        suggestionCount: 0,
        failedBatches: 1,
        errorCode: 'ORGANIZER_MODEL_RESELECT_REQUIRED',
        suggestions: [],
        failures: [{ batchIndex: 0, code: 'ORGANIZER_INVALID_JSON', message: '不是合法 JSON。' }],
      }),
    );

    const result = await organizeQuestions('imp-1', {
      draftIds: [],
      includeUnassigned: true,
      modelProfileId: 'p-chat-1',
    });

    expect(result.errorCode).toBe('ORGANIZER_MODEL_RESELECT_REQUIRED');
    expect(result.failures[0]).toEqual({
      batchIndex: 0,
      code: 'ORGANIZER_INVALID_JSON',
      message: '不是合法 JSON。',
    });
  });

  it('响应未带建议明细时归一为空数组而不是伪造', () => {
    const result = normalizeOrganizeResult({
      jobId: 'job-2',
      state: 'failed',
      suggestionCount: 4,
      failedBatches: 2,
      errorCode: 'UPSTREAM_UNAVAILABLE',
    });
    expect(result.suggestions).toEqual([]);
    expect(result.suggestionCount).toBe(4);
    expect(result.failedBatches).toBe(2);
    expect(result.errorCode).toBe('UPSTREAM_UNAVAILABLE');
  });

  it('响应形状不认识时给出失败态而不是假成功', () => {
    expect(normalizeOrganizeResult(null)).toMatchObject({
      state: 'failed',
      suggestions: [],
      errorCode: 'INVALID_RESPONSE',
    });
    expect(normalizeOrganizeResult({ suggestions: [{}] }).suggestions).toEqual([]);
  });

  it('POST /question-suggestions/{sid}/apply 带 expectedDraftRevision 且可忽略', async () => {
    const fetchMock = stubFetch(() => ok(draftView()));

    await applyQuestionSuggestion('sg/1', { expectedDraftRevision: 3, accept: false });

    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/question-suggestions/sg%2F1/apply`);
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(bodyOf(fetchMock)).toEqual({ expectedDraftRevision: 3, accept: false });
  });
});

describe('确认入库', () => {
  it('POST confirm 发送幂等 submissionId、items 与重复处理', async () => {
    const fetchMock = stubFetch(() =>
      ok({
        confirmedQuestionIds: ['q-1'],
        linkedQuestionIds: [],
        skippedDraftIds: [],
        failures: [],
      }),
    );
    const body: QuestionConfirmRequest = {
      submissionId: 'sub-1234',
      importId: 'imp-1',
      items: [{ draftId: 'd-1', expectedDraftRevision: 3 }],
      duplicateResolutions: [
        { draftId: 'd-2', action: 'link_existing', existingQuestionId: 'q-9' },
      ],
    };

    const result = await confirmQuestionImport('imp-1', body);

    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/question-imports/imp-1/confirm`);
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(bodyOf(fetchMock)).toEqual(body);
    expect(result.confirmedQuestionIds).toEqual(['q-1']);
  });

  it('HTTP 200 + failures 表示整体未入库并逐条给原因', async () => {
    stubFetch(() =>
      ok({
        confirmedQuestionIds: [],
        linkedQuestionIds: [],
        skippedDraftIds: [],
        failures: [
          { draftId: 'd-1', code: 'DRAFT_NOT_REVIEWED', message: '草稿尚未标记为已校对。' },
        ],
      }),
    );

    const result = await confirmQuestionImport('imp-1', {
      submissionId: 'sub-1234',
      importId: 'imp-1',
      items: [{ draftId: 'd-1', expectedDraftRevision: 3 }],
      duplicateResolutions: [],
    });

    expect(result.confirmedQuestionIds).toEqual([]);
    expect(result.failures[0]?.code).toBe('DRAFT_NOT_REVIEWED');
  });
});

describe('已入库题目', () => {
  it('GET /questions 拼接筛选与分页（offset=0 保留）', async () => {
    const fetchMock = stubFetch(() => ok({ questions: [], total: 0, offset: 0, limit: 20 }));

    await listQuestions({
      subjectId: 'math',
      gradeId: 'grade-7',
      editionId: 'renjiao',
      status: 'confirmed',
      q: '二次函数',
      offset: 0,
      limit: 20,
    });

    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/questions?subjectId=math&gradeId=grade-7&editionId=renjiao&status=confirmed&q=%E4%BA%8C%E6%AC%A1%E5%87%BD%E6%95%B0&offset=0&limit=20`,
    );
  });

  it('GET /questions 无筛选时只请求路径', async () => {
    const fetchMock = stubFetch(() => ok({ questions: [], total: 0, offset: 0, limit: 20 }));
    await listQuestions();
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/questions`);
  });

  it('GET /questions/{id} 与 PATCH /questions/{id} 使用同一路径', async () => {
    const fetchMock = stubFetch((url) =>
      url.includes('/questions/q-1') ? ok({ questionId: 'q-1' }) : ok({}),
    );

    await getQuestion('q-1');
    await patchQuestion('q-1', { expectedRevision: 2, content: CONTENT, metadata: METADATA });

    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/questions/q-1`);
    expect(call(fetchMock).init?.method).toBeUndefined();
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/questions/q-1`);
    expect(call(fetchMock, 1).init?.method).toBe('PATCH');
    expect(bodyOf(fetchMock, 1)).toMatchObject({ expectedRevision: 2 });
  });

  it('DELETE /questions/{id} 带可选 expectedRevision 查询参数，204 归一为 undefined', async () => {
    const fetchMock = stubFetch(
      () => ({ ok: true, status: 204, json: async () => null }) as Response,
    );

    await deleteQuestion('q-1', 7);
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/questions/q-1?expectedRevision=7`);
    expect(call(fetchMock).init?.method).toBe('DELETE');

    await expect(deleteQuestion('q-1')).resolves.toBeUndefined();
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/questions/q-1`);
  });
});

describe('错误信封', () => {
  it('把 REVISION_CONFLICT 信封转换为 ApiError', async () => {
    stubFetch(() =>
      jsonResponse(false, 409, {
        code: 'REVISION_CONFLICT',
        message: '草稿已被更新。',
        retryable: false,
      }),
    );

    const error = await rejected(
      patchQuestionDraft('d-1', {
        expectedRevision: 1,
        content: CONTENT,
        metadata: METADATA,
      }),
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe('REVISION_CONFLICT');
    expect(error.status).toBe(409);
    expect(error.message).toBe('草稿已被更新。');
  });

  it('503 SERVICE_UNAVAILABLE 标记为可重试', async () => {
    stubFetch(() =>
      jsonResponse(false, 503, {
        code: 'SERVICE_UNAVAILABLE',
        message: '题库服务未装配。',
        retryable: true,
      }),
    );

    const error = await rejected(listQuestionImports());
    expect(error.code).toBe('SERVICE_UNAVAILABLE');
    expect(error.retryable).toBe(true);
  });

  it('网络失败转换为可重试的 SERVICE_UNAVAILABLE，不返回空列表', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new Error('connect ECONNREFUSED'))),
    );

    const error = await rejected(listQuestions());
    expect(error.code).toBe('SERVICE_UNAVAILABLE');
    expect(error.status).toBe(0);
    expect(error.retryable).toBe(true);
  });
});
