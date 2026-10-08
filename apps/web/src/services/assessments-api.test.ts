/**
 * `services/assessments-api.ts` 单测：只 stub `fetch`，验证路径/查询串/multipart 编码与
 * **错误映射**（409 的 `details.currentRevision`、422 的 `details.issues` 必须原样保留，
 * 不把失败降级为空列表或假成功）。
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, API_BASE_PATH } from '@/services/api-client';
import {
  addAssessmentParticipants,
  archiveAssessment,
  archiveClass,
  archivePaper,
  archiveStudent,
  assessmentsQuery,
  batchAddStudents,
  confirmScoreImport,
  correctScoreRevision,
  createAssessment,
  createScoreImport,
  deleteAssessment,
  deleteClass,
  deletePaper,
  discardRosterImport,
  discardScoreImport,
  getAssessment,
  getPaperRevisionContent,
  getScoreMatrix,
  listAssessments,
  listClasses,
  listClassStudents,
  listScoreImportRows,
  listScoreImports,
  listStudents,
  patchScoreImport,
  removeAssessmentParticipant,
  restoreAssessment,
  restoreClass,
  restorePaper,
  restoreStudent,
} from '@/services/assessments-api';

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

async function rejected(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    return error;
  }
  throw new Error('请求本应失败，但没有抛出 ApiError。');
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function importView(overrides: Record<string, unknown> = {}) {
  return {
    importId: 'imp-1',
    assessmentId: 'as-1',
    assessmentTitle: '期中',
    state: 'reviewing',
    revision: 3,
    previewVersion: 2,
    fileAsset: {
      assetId: 'asset-1',
      kind: 'score_sheet',
      blobKey: 'blobs/abc',
      sha256: 'abc',
      mediaType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      byteSize: 256,
      originalName: '成绩.xlsx',
    },
    mapping: null,
    baseScoreRevisionId: null,
    warnings: [],
    issues: [],
    rowCount: 3,
    resolvedRowCount: 2,
    missingCellCount: 1,
    createdAt: '2026-10-01T00:00:00Z',
    updatedAt: '2026-10-01T00:00:00Z',
    ...overrides,
  };
}

describe('assessmentsQuery', () => {
  it('跳过空值并做 URL 编码', () => {
    expect(
      assessmentsQuery({ assessmentId: 'a 1', offset: 0, limit: 50, state: undefined, empty: '' }),
    ).toBe(`?assessmentId=a+1&offset=0&limit=50`);
    expect(assessmentsQuery({})).toBe('');
  });
});

describe('名单与原卷读取', () => {
  it('班级列表带 status/offset/limit', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 50 }));
    await listClasses({ status: 'active', offset: 0, limit: 50 });
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/classes?status=active&offset=0&limit=50`);
    expect(call(fetchMock).init?.headers).toMatchObject({ accept: 'application/json' });
  });

  it('固定修订内容路径正确编码 revisionId', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { paperId: 'p1', paperRevisionId: 'r1', items: [] }),
    );
    await getPaperRevisionContent('p1', 'rev/1');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/papers/p1/revisions/rev%2F1/content`);
  });
});

describe('施测请求体', () => {
  it('创建施测：submissionId + participants + 显式班级确认字段原样编码', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 201, { assessment: {}, participants: [], replayed: false }),
    );
    await createAssessment({
      submissionId: 'sub-1',
      paperRevisionId: 'pr-1',
      title: '第一次月考',
      assessmentType: 'exam',
      heldOn: '2026-10-01',
      classIds: ['c-1'],
      participants: [
        { studentId: 's-1', classId: 'c-1', attendance: 'present', attemptNo: 1 },
        {
          studentId: 's-2',
          classId: 'c-1',
          attendance: 'present',
          attemptNo: 1,
          classConfirmed: true,
          classConfirmationNote: '名单未覆盖当日归属',
        },
      ],
    });
    expect(bodyOf(fetchMock)).toMatchObject({
      submissionId: 'sub-1',
      classIds: ['c-1'],
      participants: [
        { studentId: 's-1', classId: 'c-1', attendance: 'present', attemptNo: 1 },
        {
          studentId: 's-2',
          classId: 'c-1',
          classConfirmed: true,
          classConfirmationNote: '名单未覆盖当日归属',
        },
      ],
    });
  });

  it('补录人次：expectedRevision 与 participants 一起提交', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { assessment: {}, participants: [], replayed: false }),
    );
    await addAssessmentParticipants('as-1', {
      submissionId: 'sub-2',
      expectedRevision: 4,
      participants: [{ studentId: 's-3', classId: 'c-1' }],
    });
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/assessments/as-1/participants`);
    expect(bodyOf(fetchMock)).toMatchObject({ expectedRevision: 4 });
  });

  it('施测列表与详情路径', async () => {
    const fetchMock = stubFetch((url) =>
      url.includes('/assessments/as-9')
        ? jsonResponse(true, 200, { assessment: { assessmentId: 'as-9' }, participants: [] })
        : jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 50 }),
    );
    await listAssessments({ classId: 'c-1' });
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/assessments?classId=c-1`);
    await getAssessment('as-9');
    expect(call(fetchMock, 1).url).toBe(`${API_BASE_PATH}/assessments/as-9`);
  });
});

describe('成绩导入客户端', () => {
  it('上传：multipart 只带 file 与显式工作表/基准版本', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 201, importView()));
    const file = new File([new Uint8Array([1, 2, 3])], '成绩.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    await createScoreImport('as-1', file, { workSheet: '成绩', baseScoreRevisionId: 'rev-0' });
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/assessments/as-1/score-imports`);
    const form = call(fetchMock).init?.body as FormData;
    expect(form).toBeInstanceOf(FormData);
    expect(form.get('file')).toBe(file);
    expect(form.get('workSheet')).toBe('成绩');
    expect(form.get('baseScoreRevisionId')).toBe('rev-0');
    // 不手写 content-type：boundary 由 fetch 生成（api-client 只补 accept）
    expect(call(fetchMock).init?.headers).toEqual({ accept: 'application/json' });
  });

  it('批次列表/详情/行分页路径与查询串', async () => {
    const fetchMock = stubFetch((url) => {
      if (url.includes('/rows')) {
        return jsonResponse(true, 200, { items: [], total: 200, offset: 50, limit: 50 });
      }
      if (url.includes('/score-imports/imp-1')) {
        return jsonResponse(true, 200, importView());
      }
      return jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 50 });
    });
    await listScoreImports({ assessmentId: 'as-1' });
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/score-imports?assessmentId=as-1`);
    await listScoreImportRows('imp-1', { offset: 50, limit: 50 });
    expect(call(fetchMock, 1).url).toBe(
      `${API_BASE_PATH}/score-imports/imp-1/rows?offset=50&limit=50`,
    );
  });

  it('PATCH：mapping 与行校正都按原表坐标提交（不携带未声明的多余字段）', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 200, importView()));
    await patchScoreImport('imp-1', {
      expectedRevision: 3,
      mapping: {
        workSheet: '成绩',
        headerRow: 1,
        studentNoColumn: 'B',
        nameColumn: 'C',
        itemColumns: [
          { itemId: 'i-1', column: 'D' },
          { itemId: 'i-2', column: 'E' },
        ],
      },
      rows: [
        { rowNo: 2, participantId: 'part-1' },
        { rowNo: 3, cells: [{ row: 3, column: 'E', text: '0' }] },
      ],
    });
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/score-imports/imp-1`);
    expect(call(fetchMock).init?.method).toBe('PATCH');
    expect(bodyOf(fetchMock)).toEqual({
      expectedRevision: 3,
      mapping: {
        workSheet: '成绩',
        headerRow: 1,
        studentNoColumn: 'B',
        nameColumn: 'C',
        itemColumns: [
          { itemId: 'i-1', column: 'D' },
          { itemId: 'i-2', column: 'E' },
        ],
      },
      rows: [
        { rowNo: 2, participantId: 'part-1' },
        { rowNo: 3, cells: [{ row: 3, column: 'E', text: '0' }] },
      ],
    });
  });

  it('409 版本冲突：currentRevision 与错误码原样保留，不降级为空结果', async () => {
    stubFetch(() =>
      jsonResponse(false, 409, {
        code: 'SCORE_IMPORT_REVISION_CONFLICT',
        message: '批次已被其他操作更新。',
        retryable: false,
        details: { currentRevision: 7 },
      }),
    );
    const error = await rejected(patchScoreImport('imp-1', { expectedRevision: 3 }));
    expect(error.code).toBe('SCORE_IMPORT_REVISION_CONFLICT');
    expect(error.status).toBe(409);
    expect(error.details?.currentRevision).toBe(7);
  });

  it('422 行列问题：issues 逐条保留（行号 + 列字母）', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(false, 422, {
        code: 'SCORE_CELL_OVER_MAX',
        message: '单元格得分超过满分。',
        details: {
          issues: [
            { row: 3, column: 'E', code: 'SCORE_CELL_OVER_MAX', message: '超过满分 8 分。' },
            { row: 5, column: 'D', code: 'SCORE_CELL_INVALID', message: '不是合法分数。' },
          ],
        },
      }),
    );
    const error = await rejected(
      patchScoreImport('imp-1', {
        expectedRevision: 4,
        rows: [{ rowNo: 3, cells: [{ row: 3, column: 'E', text: '99' }] }],
      }),
    );
    expect(error.status).toBe(422);
    expect(error.details?.issues).toEqual([
      { row: 3, column: 'E', code: 'SCORE_CELL_OVER_MAX', message: '超过满分 8 分。' },
      { row: 5, column: 'D', code: 'SCORE_CELL_INVALID', message: '不是合法分数。' },
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('确认：三个版本字段 + 承认范围 + submissionId 原样提交，重放结果被保留', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, {
        importId: 'imp-1',
        state: 'confirmed',
        revisionId: 'rev-1',
        assessmentRevision: 5,
        activeScoreRevisionId: 'rev-1',
        replayed: true,
      }),
    );
    const result = await confirmScoreImport('imp-1', {
      expectedImportRevision: 8,
      expectedAssessmentRevision: 4,
      baseScoreRevisionId: null,
      previewVersion: 6,
      submissionId: 'sub-9',
      absences: [{ classId: 'c-1', participantIds: ['p-9'] }],
      missing: { participantIds: ['p-2'], cellCount: 3 },
    });
    expect(result.replayed).toBe(true);
    expect(result.revisionId).toBe('rev-1');
    expect(bodyOf(fetchMock)).toMatchObject({
      expectedImportRevision: 8,
      expectedAssessmentRevision: 4,
      baseScoreRevisionId: null,
      previewVersion: 6,
      submissionId: 'sub-9',
      absences: [{ classId: 'c-1', participantIds: ['p-9'] }],
      missing: { participantIds: ['p-2'], cellCount: 3 },
    });
  });
});

describe('只读矩阵与修正', () => {
  it('矩阵分页：totalUnits 只在全员 recorded 时非空，null 原样保留', async () => {
    stubFetch(() =>
      jsonResponse(true, 200, {
        revision: { revisionId: 'rev-1', version: 1, state: 'confirmed' },
        items: [{ itemId: 'i-1', itemPath: '16(1)', maxScoreUnits: 400 }],
        rows: [
          {
            participant: { participantId: 'p-1', totalUnits: 400, totalMaxUnits: 400 },
            cells: [{ itemId: 'i-1', status: 'recorded', scoreUnits: 400 }],
          },
          {
            participant: { participantId: 'p-2', totalUnits: null, totalMaxUnits: 400 },
            cells: [{ itemId: 'i-1', status: 'missing', scoreUnits: null }],
          },
        ],
        total: 2,
        offset: 0,
        limit: 50,
        missingParticipantIds: ['p-2'],
        missingCellCount: 1,
        absentClassIds: [],
      }),
    );
    const page = await getScoreMatrix('rev-1', { offset: 0, limit: 50 });
    expect(page.rows[0].participant.totalUnits).toBe(400);
    expect(page.rows[1].participant.totalUnits).toBeNull();
    expect(page.missingCellCount).toBe(1);
  });

  it('修正：base 与提交标识、理由、逐格校正原样提交', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, {
        revisionId: 'rev-2',
        baseRevisionId: 'rev-1',
        version: 2,
        assessmentRevision: 6,
        activeScoreRevisionId: 'rev-2',
        replayed: false,
      }),
    );
    const result = await correctScoreRevision('as-1', {
      baseScoreRevisionId: 'rev-1',
      expectedAssessmentRevision: 5,
      submissionId: 'sub-11',
      reason: '漏批第 3 行',
      corrections: [
        { participantId: 'p-1', itemId: 'i-2', status: 'recorded', scoreText: '7.5' },
        { participantId: 'p-2', itemId: 'i-2', status: 'missing' },
      ],
    });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/assessments/as-1/score-revisions/correct`,
    );
    expect(result.version).toBe(2);
    expect(bodyOf(fetchMock)).toMatchObject({
      baseScoreRevisionId: 'rev-1',
      submissionId: 'sub-11',
      corrections: [
        { participantId: 'p-1', itemId: 'i-2', status: 'recorded', scoreText: '7.5' },
        { participantId: 'p-2', itemId: 'i-2', status: 'missing' },
      ],
    });
  });
});

describe('归档 / 恢复 / 放弃 / 移除（本批新增端点）', () => {
  it('班级归档/恢复：路径带 id 且请求体只含 expectedRevision', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { id: 'c-1', status: 'archived', revision: 5 }),
    );
    await archiveClass('c 1', { expectedRevision: 4 });
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/classes/c%201/archive`);
    expect(bodyOf(fetchMock)).toEqual({ expectedRevision: 4 });

    const restoreMock = stubFetch(() =>
      jsonResponse(true, 200, { id: 'c-1', status: 'active', revision: 6 }),
    );
    await restoreClass('c-1', { expectedRevision: 5 });
    expect(call(restoreMock).init?.method).toBe('POST');
    expect(call(restoreMock).url).toBe(`${API_BASE_PATH}/classes/c-1/restore`);
    expect(bodyOf(restoreMock)).toEqual({ expectedRevision: 5 });
  });

  it('学生归档/恢复：/students/{id}/archive|restore 只提交 expectedRevision', async () => {
    const archiveMock = stubFetch(() => jsonResponse(true, 200, { id: 's-1', status: 'archived' }));
    await archiveStudent('s-1', { expectedRevision: 8 });
    expect(call(archiveMock).init?.method).toBe('POST');
    expect(call(archiveMock).url).toBe(`${API_BASE_PATH}/students/s-1/archive`);
    expect(bodyOf(archiveMock)).toEqual({ expectedRevision: 8 });

    const fetchMock = stubFetch(() => jsonResponse(true, 200, { id: 's-1', status: 'active' }));
    await restoreStudent('s-1', { expectedRevision: 9 });
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/students/s-1/restore`);
    expect(bodyOf(fetchMock)).toEqual({ expectedRevision: 9 });
  });

  it('班级成员：includeArchived=true 才带查询参数，旧 (classId, signal) 调用不带参数且信号透传', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 50 }),
    );
    await listClassStudents('c-1', { includeArchived: true });
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/classes/c-1/students?includeArchived=true`,
    );

    const plain = stubFetch(() =>
      jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 50 }),
    );
    const controller = new AbortController();
    await listClassStudents('c-1', controller.signal);
    expect(call(plain).url).toBe(`${API_BASE_PATH}/classes/c-1/students`);
    expect(call(plain).init?.signal).toBe(controller.signal);
  });

  it('学生列表：status 并入查询串', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 50 }),
    );
    await listStudents({ status: 'archived', limit: 20 });
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/students?status=archived&limit=20`);
  });

  it('放弃名单批次：POST /roster-imports/{id}/discard 提交 expectedRevision', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { importId: 'imp-1', state: 'cancelled', revision: 4 }),
    );
    const view = await discardRosterImport('imp-1', { expectedRevision: 3 });
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/roster-imports/imp-1/discard`);
    expect(bodyOf(fetchMock)).toEqual({ expectedRevision: 3 });
    expect(view.state).toBe('cancelled');
  });

  it('原卷归档/恢复：/papers/{id}/archive|restore 只提交 expectedRevision', async () => {
    const archiveMock = stubFetch(() => jsonResponse(true, 200, { paperId: 'p-1', status: 'archived' }));
    await archivePaper('p-1', { expectedRevision: 2 });
    expect(call(archiveMock).url).toBe(`${API_BASE_PATH}/papers/p-1/archive`);
    expect(bodyOf(archiveMock)).toEqual({ expectedRevision: 2 });

    const restoreMock = stubFetch(() => jsonResponse(true, 200, { paperId: 'p-1', status: 'active' }));
    await restorePaper('p-1', { expectedRevision: 3 });
    expect(call(restoreMock).init?.method).toBe('POST');
    expect(call(restoreMock).url).toBe(`${API_BASE_PATH}/papers/p-1/restore`);
    expect(bodyOf(restoreMock)).toEqual({ expectedRevision: 3 });
  });

  it('施测归档/恢复：/assessments/{id}/archive|restore 只提交 expectedRevision', async () => {
    const archiveMock = stubFetch(() => jsonResponse(true, 200, { assessmentId: 'as-1', state: 'archived' }));
    await archiveAssessment('as-1', { expectedRevision: 6 });
    expect(call(archiveMock).url).toBe(`${API_BASE_PATH}/assessments/as-1/archive`);
    expect(bodyOf(archiveMock)).toEqual({ expectedRevision: 6 });

    const restoreMock = stubFetch(() => jsonResponse(true, 200, { assessmentId: 'as-1', state: 'open' }));
    await restoreAssessment('as-1', { expectedRevision: 7 });
    expect(call(restoreMock).init?.method).toBe('POST');
    expect(call(restoreMock).url).toBe(`${API_BASE_PATH}/assessments/as-1/restore`);
    expect(bodyOf(restoreMock)).toEqual({ expectedRevision: 7 });
  });

  it('移除人次：DELETE 走查询参数 expectedRevision，且不带请求体', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, { assessment: { assessmentId: 'as-1' }, participants: [], replayed: false }),
    );
    await removeAssessmentParticipant('as-1', 'p 1', 8);
    expect(call(fetchMock).init?.method).toBe('DELETE');
    expect(call(fetchMock).url).toBe(
      `${API_BASE_PATH}/assessments/as-1/participants/p%201?expectedRevision=8`,
    );
    expect(call(fetchMock).init?.body).toBeUndefined();
  });

  it('放弃成绩批次：POST /score-imports/{id}/discard 返回批次视图', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 200, importView({ state: 'cancelled', revision: 5 })));
    const view = await discardScoreImport('imp-1', { expectedRevision: 4 });
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/score-imports/imp-1/discard`);
    expect(bodyOf(fetchMock)).toEqual({ expectedRevision: 4 });
    expect(view.state).toBe('cancelled');
    expect(view.revision).toBe(5);
  });
});

describe('彻底删除与批量学生（本批新增端点）', () => {
  /** `details.counts` 不在公共 `ApiErrorDetails` 里（受引用守卫专用），按结构化读取。 */
  function detailsCounts(error: ApiError): Record<string, number> | undefined {
    return (error.details as unknown as { counts?: Record<string, number> } | undefined)?.counts;
  }

  it('彻底删除班级：DELETE /classes/{id} 走查询参数 expectedRevision，无请求体', async () => {
    const fetchMock = stubFetch(() => jsonResponse(true, 200, { deleted: true, classId: 'c-1' }));
    const result = await deleteClass('c 1', 4);
    expect(call(fetchMock).init?.method).toBe('DELETE');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/classes/c%201?expectedRevision=4`);
    expect(call(fetchMock).init?.body).toBeUndefined();
    expect(result).toEqual({ deleted: true, classId: 'c-1' });
  });

  it('彻底删除原卷：409 PAPER_HAS_CONFIRMED_REVISION 的 details.counts 原样保留', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(false, 409, {
        code: 'PAPER_HAS_CONFIRMED_REVISION',
        message: '该原卷存在已确认修订，不能删除（已确认原卷只能归档）。',
        details: { counts: { confirmedRevisions: 2 } },
      }),
    );
    const error = await rejected(deletePaper('p-1', 2));
    expect(call(fetchMock).init?.method).toBe('DELETE');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/papers/p-1?expectedRevision=2`);
    expect(error.code).toBe('PAPER_HAS_CONFIRMED_REVISION');
    expect(detailsCounts(error)).toEqual({ confirmedRevisions: 2 });
  });

  it('彻底删除施测：409 ASSESSMENT_IN_USE 的逐项计数原样保留', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(false, 409, {
        code: 'ASSESSMENT_IN_USE',
        message: '施测仍被引用，不能删除（成绩版本 1 条、学情报告 1 条）。',
        details: {
          counts: { scoreRevisions: 1, scoreImports: 0, analysisRuns: 1, practiceConversions: 0 },
        },
      }),
    );
    const error = await rejected(deleteAssessment('as-1', 3));
    expect(call(fetchMock).init?.method).toBe('DELETE');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/assessments/as-1?expectedRevision=3`);
    expect(error.message).toContain('施测仍被引用');
    expect(detailsCounts(error)).toMatchObject({ scoreRevisions: 1, analysisRuns: 1 });
  });

  it('批量添加学生：POST /classes/{id}/students/batch 原样编码 submissionId/items/joinedOn', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse(true, 200, {
        created: [{ id: 's-1', name: '甲', revision: 1, memberships: [] }],
        skipped: [{ index: 1, reason: '学号 T2 已存在', code: 'STUDENT_NO_CONFLICT', existingStudentId: 's-9', existingName: '乙' }],
        replayed: false,
      }),
    );
    const result = await batchAddStudents('c-1', {
      submissionId: 'sub-1',
      items: [{ studentNo: 'T1', name: '甲' }, { studentNo: 'T2', name: '乙' }],
      joinedOn: '2026-10-08',
    });
    expect(call(fetchMock).init?.method).toBe('POST');
    expect(call(fetchMock).url).toBe(`${API_BASE_PATH}/classes/c-1/students/batch`);
    expect(call(fetchMock).init?.headers).toMatchObject({ 'content-type': 'application/json' });
    expect(bodyOf(fetchMock)).toEqual({
      submissionId: 'sub-1',
      items: [{ studentNo: 'T1', name: '甲' }, { studentNo: 'T2', name: '乙' }],
      joinedOn: '2026-10-08',
    });
    expect(result.created).toHaveLength(1);
    expect(result.skipped[0]).toMatchObject({ index: 1, existingStudentId: 's-9', existingName: '乙' });
  });

  it('批量添加学生：归档班级 409 CLASS_ARCHIVED 与行非法 422 issues[].row 都不降级为成功', async () => {
    const archivedMock = stubFetch(() =>
      jsonResponse(false, 409, { code: 'CLASS_ARCHIVED', message: '归档班级不再接收新归属。' }),
    );
    const archivedError = await rejected(
      batchAddStudents('c-1', { submissionId: 'sub-1', items: [{ name: '甲' }] }),
    );
    expect(archivedError.code).toBe('CLASS_ARCHIVED');
    expect(call(archivedMock).url).toBe(`${API_BASE_PATH}/classes/c-1/students/batch`);

    const invalidMock = stubFetch(() =>
      jsonResponse(false, 422, {
        code: 'ROSTER_ROW_INVALID',
        message: '第 0 行姓名为空，整批未写入。',
        details: { issues: [{ row: 0, field: 'name', code: 'ROSTER_ROW_INVALID', message: '姓名必须是非空字符串。' }] },
      }),
    );
    const invalidError = await rejected(
      batchAddStudents('c-1', { submissionId: 'sub-2', items: [{ name: ' ' }] }),
    );
    expect(invalidError.status).toBe(422);
    expect(invalidError.details?.issues?.[0].row).toBe(0);
    expect(call(invalidMock).init?.method).toBe('POST');
  });
});
