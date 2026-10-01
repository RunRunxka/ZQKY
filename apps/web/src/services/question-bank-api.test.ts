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
  createQuestionGenerationJob,
  createQuestionImport,
  deleteQuestion,
  generationFieldsFromJobView,
  getQuestion,
  getQuestionImport,
  listQuestionImports,
  listQuestions,
  mergeGenerationObservation,
  mergeOrganizeObservation,
  mergeQuestionDrafts,
  normalizeGenerationResult,
  normalizeOrganizeResult,
  organizeFieldsFromJobView,
  organizeJobPending,
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

  it('六态：保留 attempt（含 0）与 interrupted 状态，未知状态按失败处理', () => {
    const interrupted = normalizeOrganizeResult({
      jobId: 'job-9',
      state: 'interrupted',
      attempt: 0,
      suggestionCount: 1,
      failedBatches: 0,
      errorCode: null,
      suggestions: [],
      failures: [],
    });
    expect(interrupted.state).toBe('interrupted');
    expect(interrupted.attempt).toBe(0);
    expect(organizeJobPending(interrupted)).toBe(false);

    const running = normalizeOrganizeResult({ jobId: 'job-10', state: 'running', attempt: 2 });
    expect(organizeJobPending(running)).toBe(true);

    // 未知状态不能当成功：按 failed 处理并保留原响应其它字段
    const unknown = normalizeOrganizeResult({ jobId: 'job-11', state: 'paused', attempt: 3 });
    expect(unknown.state).toBe('failed');
    expect(unknown.attempt).toBe(3);

    // 缺 attempt 时不补 0（0 是真实尝试号，不能与「缺省」混为一谈）
    expect(normalizeOrganizeResult({ jobId: 'job-12', state: 'queued' }).attempt).toBeUndefined();
  });

  it('任务观察合并：状态/尝试号来自任务视图，建议只在服务端给出时更新', () => {
    const base = normalizeOrganizeResult({
      jobId: 'job-1',
      state: 'running',
      attempt: 1,
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
      failures: [],
    });

    // 任务视图只有状态（result 为 null）：建议保持上一份权威数据，不猜造、不清零
    const observing = mergeOrganizeObservation(base, {
      jobId: 'job-1',
      domain: 'question',
      kind: 'organize',
      attempt: 1,
      state: 'running',
      result: null,
      error: null,
    });
    expect(observing.state).toBe('running');
    expect(observing.suggestions.map((item) => item.suggestionId)).toEqual(['sg-1']);

    // 终态任务视图带 result：采用服务端给出的建议与错误码
    const done = mergeOrganizeObservation(observing, {
      jobId: 'job-1',
      domain: 'question',
      kind: 'organize',
      attempt: 2,
      state: 'failed',
      result: {
        suggestionCount: 1,
        failedBatches: 1,
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
        failures: [{ batchIndex: 1, code: 'ORGANIZER_INVALID_JSON', message: '不是合法 JSON。' }],
      },
      error: { code: 'ORGANIZER_INVALID_JSON', message: '不是合法 JSON。', retryable: false },
    });
    expect(done.state).toBe('failed');
    expect(done.attempt).toBe(2);
    expect(done.failedBatches).toBe(1);
    expect(done.failures[0]?.batchIndex).toBe(1);
    // 任务视图没给 errorCode 时用错误信封补充（仍是服务端给出的码）
    expect(done.errorCode).toBe('ORGANIZER_INVALID_JSON');
  });

  it('organizeFieldsFromJobView 只取明确给出的字段', () => {
    const patch = organizeFieldsFromJobView({
      jobId: 'job-7',
      domain: 'question',
      kind: 'organize',
      attempt: 4,
      state: 'succeeded',
      result: { suggestionCount: 0 },
      error: null,
    });
    expect(patch.jobId).toBe('job-7');
    expect(patch.state).toBe('succeeded');
    expect(patch.attempt).toBe(4);
    expect(patch.suggestionCount).toBe(0);
    expect(patch).not.toHaveProperty('suggestions');
    expect(patch).not.toHaveProperty('failures');
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

  it('GET /questions 支持按正式知识点筛选（knowledgePointId）', async () => {
    const fetchMock = stubFetch(() => ok({ questions: [], total: 0, offset: 0, limit: 20 }));
    await listQuestions({ subjectId: 'math', knowledgePointId: 'kp/1', offset: 0, limit: 20 });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/questions?subjectId=math&knowledgePointId=kp%2F1&offset=0&limit=20`,
    );
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

describe('AI 补题（生成）', () => {
  it('POST /question-generation-jobs 原样发送冻结载荷（模型 profile id、知识点、题数）', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 202, {
        jobId: 'job-1',
        state: 'queued',
        attempt: 0,
        importId: null,
        candidateCount: 0,
        errorCode: null,
      }),
    );

    const view = await createQuestionGenerationJob({
      modelProfileId: 'p-chat-1',
      subjectId: 'math',
      knowledgePointIds: ['kp-1'],
      questionTypes: ['single_choice'],
      difficulty: 'easy',
      count: 2,
      instructions: '只考有理数。',
    });

    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/question-generation-jobs`);
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(bodyOf(fetchMock)).toEqual({
      modelProfileId: 'p-chat-1',
      subjectId: 'math',
      knowledgePointIds: ['kp-1'],
      questionTypes: ['single_choice'],
      difficulty: 'easy',
      count: 2,
      instructions: '只考有理数。',
    });
    // attempt=0 是真实尝试号：保留 0，不当作缺省
    expect(view.attempt).toBe(0);
    expect(view.state).toBe('queued');
    expect(view.importId).toBeNull();
  });

  it('归一补题响应：未知状态按失败处理；空 importId 归一为 null，缺失 attempt 不补 0', () => {
    const unknown = normalizeGenerationResult({
      jobId: 'job-2',
      state: 'paused',
      attempt: 3,
      importId: '',
      candidateCount: 1,
      errorCode: '',
    });
    expect(unknown.state).toBe('failed');
    expect(unknown.attempt).toBe(3);
    expect(unknown.importId).toBeNull();
    expect(unknown.errorCode).toBeNull();
    expect(normalizeGenerationResult({ jobId: 'job-3', state: 'queued' })).not.toHaveProperty(
      'attempt',
    );
    expect(normalizeGenerationResult(null)).toMatchObject({
      jobId: '',
      state: 'failed',
      errorCode: 'INVALID_RESPONSE',
    });
  });

  it('任务观察合并：状态/尝试号来自任务视图，importId 只在服务端给出时更新', () => {
    const base = normalizeGenerationResult({
      jobId: 'job-1',
      state: 'running',
      attempt: 1,
      importId: null,
      candidateCount: 0,
      errorCode: null,
    });

    const observing = mergeGenerationObservation(base, {
      jobId: 'job-1',
      domain: 'question',
      kind: 'generate',
      attempt: 1,
      state: 'running',
      result: null,
      error: null,
    });
    expect(observing?.state).toBe('running');
    expect(observing?.importId).toBeNull();
    expect(observing?.candidateCount).toBe(0);

    const done = mergeGenerationObservation(observing, {
      jobId: 'job-1',
      domain: 'question',
      kind: 'generate',
      attempt: 2,
      state: 'succeeded',
      result: { importId: 'imp-9', candidateCount: 2 },
      error: null,
    });
    expect(done?.attempt).toBe(2);
    expect(done?.state).toBe('succeeded');
    expect(done?.importId).toBe('imp-9');
    expect(done?.candidateCount).toBe(2);
    // 视图缺失时不凭空造结果
    expect(mergeGenerationObservation(null, {
      jobId: 'job-1',
      domain: 'question',
      kind: 'generate',
      attempt: 1,
      state: 'running',
      result: null,
      error: null,
    })).toBeNull();
  });

  it('generationFieldsFromJobView 只取明确给出的字段；错误码可由错误信封补充', () => {
    const patch = generationFieldsFromJobView({
      jobId: 'job-7',
      domain: 'question',
      kind: 'generate',
      attempt: 4,
      state: 'failed',
      result: { candidateCount: 0 },
      error: { code: 'UPSTREAM_UNAVAILABLE', message: '模型服务当前不可用。', retryable: true },
    });
    expect(patch).toMatchObject({ jobId: 'job-7', state: 'failed', attempt: 4, candidateCount: 0 });
    expect(patch).not.toHaveProperty('importId');
    expect(patch).not.toHaveProperty('errorCode');

    const merged = mergeGenerationObservation(
      normalizeGenerationResult({ jobId: 'job-7', state: 'running', attempt: 3 }),
      {
        jobId: 'job-7',
        domain: 'question',
        kind: 'generate',
        attempt: 4,
        state: 'failed',
        result: null,
        error: { code: 'UPSTREAM_UNAVAILABLE', message: '模型服务当前不可用。', retryable: true },
      },
    );
    expect(merged?.errorCode).toBe('UPSTREAM_UNAVAILABLE');
    expect(merged?.attempt).toBe(4);
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
