/**
 * `services/assessments-api.ts` 单测：只 stub `fetch`，验证路径/查询串/multipart 编码与
 * **错误映射**（409 的 `details.currentRevision`、422 的 `details.issues` 必须原样保留，
 * 不把失败降级为空列表或假成功）。
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, API_BASE_PATH } from '@/services/api-client';
import {
  addAssessmentParticipants,
  assessmentsQuery,
  confirmScoreImport,
  correctScoreRevision,
  createAssessment,
  createScoreImport,
  getAssessment,
  getPaperRevisionContent,
  getScoreMatrix,
  listAssessments,
  listClasses,
  listScoreImportRows,
  listScoreImports,
  patchScoreImport,
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
