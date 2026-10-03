/**
 * F20-I 成绩流 hook 单测：五步状态机推导、逻辑确认冻结（submissionId 复用 / StrictMode /
 * 迟到响应失效）与校对草稿的 409/422 保留语义。
 *
 * 只 stub `fetch`（真实 `patchScoreImport` + 真实 `api-client`），不 mock 服务模块。
 */

import { StrictMode, useEffect } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ApiError } from '@/services/api-client';
import type { ScoreImportView } from '@/contracts/scores';
import {
  hasUsableMapping,
  scoreFlowStep,
  stablePayloadKey,
  useFrozenSubmission,
  useScoreDrafts,
  type ScoreDraftsController,
  type SubmissionController,
} from './hooks';

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

function importView(overrides: Partial<ScoreImportView> = {}): ScoreImportView {
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
    mapping: {
      workSheet: '成绩',
      headerRow: 1,
      studentNoColumn: 'B',
      nameColumn: 'C',
      itemColumns: [{ itemId: 'i-1', column: 'D' }],
    },
    baseScoreRevisionId: null,
    warnings: [],
    issues: [],
    rowCount: 2,
    resolvedRowCount: 2,
    missingCellCount: 0,
    requiredAcknowledgements: { absences: [], missing: null },
    createdAt: '2026-10-01T00:00:00Z',
    updatedAt: '2026-10-01T00:00:00Z',
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/* ------------------------------------------------------------------ 五步状态机 */

describe('成绩流五步推导（upload → 映射 → 校对 → 承认 → 确认）', () => {
  it('无批次 → 上传；无可用映射 → 映射；有映射 → 校对；请求承认 → 承认；已确认 → 确认', () => {
    expect(scoreFlowStep(null)).toBe('upload');
    expect(scoreFlowStep(importView({ mapping: null }))).toBe('mapping');
    expect(
      scoreFlowStep(
        importView({
          mapping: { workSheet: '成绩', itemColumns: [{ itemId: 'i-1', column: 'D' }] },
        }),
      ),
    ).toBe('mapping');
    expect(scoreFlowStep(importView())).toBe('review');
    expect(scoreFlowStep(importView(), { acknowledgeRequested: true })).toBe('acknowledge');
    expect(scoreFlowStep(importView({ state: 'confirmed' }), { acknowledgeRequested: true })).toBe(
      'confirmed',
    );
    expect(scoreFlowStep(importView({ state: 'cancelled' }))).toBe('upload');
  });

  it('hasUsableMapping 要求工作表 + 身份列 + 计分叶列', () => {
    expect(hasUsableMapping(importView())).toBe(true);
    expect(hasUsableMapping(importView({ mapping: { workSheet: '成绩', itemColumns: [] } }))).toBe(
      false,
    );
    expect(
      hasUsableMapping(
        importView({ mapping: { workSheet: '', studentNoColumn: 'B', itemColumns: [{ itemId: 'i', column: 'D' }] } }),
      ),
    ).toBe(false);
  });
});

describe('stablePayloadKey', () => {
  it('字段顺序无关、数组顺序有关、忽略 undefined', () => {
    expect(stablePayloadKey({ a: 1, b: [2, 3] })).toBe(stablePayloadKey({ b: [2, 3], a: 1 }));
    expect(stablePayloadKey({ a: [1, 2] })).not.toBe(stablePayloadKey({ a: [2, 1] }));
    expect(stablePayloadKey({ a: 1, b: undefined })).toBe(stablePayloadKey({ a: 1 }));
  });
});

/* ------------------------------------------------------------------ 逻辑确认冻结 */

let latestSubmission: SubmissionController<{ note: string }, { ok: string }> | null = null;

function SubmissionHarness() {
  const controller = useFrozenSubmission<{ note: string }, { ok: string }>();
  useEffect(() => {
    latestSubmission = controller;
  });
  return (
    <div data-testid="submission">
      {controller.phase}
      {controller.frozen ? `|${controller.frozen.submissionId}|${controller.frozen.payload.note}` : ''}
      {controller.result ? `|${controller.result.ok}` : ''}
      {controller.error ? `|err:${controller.error.code}` : ''}
      {controller.unknownNotice ? '|unknown' : ''}
    </div>
  );
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

describe('逻辑确认冻结：submissionId 与载荷在明确结果前不换', () => {
  for (const strict of [false, true]) {
    const label = strict ? 'StrictMode' : '普通模式对照';
    it(`${label}：成功 → 结果落地、phase=succeeded、冻结释放`, async () => {
      render(strict ? <StrictMode><SubmissionHarness /></StrictMode> : <SubmissionHarness />);
      const run = vi.fn().mockResolvedValue({ ok: 'done' });
      await act(async () => {
        await latestSubmission!.submit({ note: 'a' }, run);
      });
      expect(screen.getByTestId('submission')).toHaveTextContent('succeeded|done');
      expect(latestSubmission!.frozen).toBeNull();
      expect(run).toHaveBeenCalledTimes(1);
      expect(run.mock.calls[0][0].submissionId).toMatch(UUID_PATTERN);
    });
  }

  it('结果未知（无响应）：保留冻结，重试复用同一 submissionId 与同一载荷', async () => {
    render(<SubmissionHarness />);
    const first = vi
      .fn()
      .mockRejectedValue(new ApiError('SERVICE_UNAVAILABLE', '后端服务未运行或无法连接。', 0, true));
    await act(async () => {
      await latestSubmission!.submit({ note: '原始载荷' }, first);
    });
    expect(screen.getByTestId('submission')).toHaveTextContent('unknown');
    expect(screen.getByTestId('submission')).not.toHaveTextContent('succeeded');
    const frozenId = latestSubmission!.frozen?.submissionId;
    expect(frozenId).toMatch(UUID_PATTERN);

    const second = vi.fn().mockResolvedValue({ ok: 'replayed' });
    await act(async () => {
      await latestSubmission!.submit({ note: '刷新后被修改的载荷' }, second);
    });
    expect(second.mock.calls[0][0].submissionId).toBe(frozenId);
    expect(second.mock.calls[0][0].payload).toEqual({ note: '原始载荷' });
    expect(screen.getByTestId('submission')).toHaveTextContent('succeeded|replayed');
  });

  it('明确失败后载荷变化 = 新的逻辑确认：换 submissionId', async () => {
    render(<SubmissionHarness />);
    const first = vi.fn().mockRejectedValue(new ApiError('VALIDATION_ERROR', '校验未通过', 422, false));
    await act(async () => {
      await latestSubmission!.submit({ note: '旧载荷' }, first);
    });
    const oldId = latestSubmission!.frozen?.submissionId;
    const second = vi.fn().mockResolvedValue({ ok: 'new' });
    await act(async () => {
      await latestSubmission!.submit({ note: '新载荷' }, second);
    });
    expect(second.mock.calls[0][0].submissionId).not.toBe(oldId);
    expect(second.mock.calls[0][0].payload).toEqual({ note: '新载荷' });
  });

  it('冻结复制嵌套载荷，调用方在途修改数组不会改变未知结果重试包', async () => {
    render(<SubmissionHarness />);
    let reject!: (error: ApiError) => void;
    const first = vi.fn().mockReturnValue(new Promise((_, rejectPromise) => { reject = rejectPromise; }));
    const original = { note: '原载荷', scopes: ['甲'] };
    act(() => { void latestSubmission!.submit(original, first); });
    original.scopes.push('乙');
    await act(async () => { reject(new ApiError('SERVICE_UNAVAILABLE', '回执丢失', 0, true)); });
    const second = vi.fn().mockResolvedValue({ ok: 'replayed' });
    await act(async () => { await latestSubmission!.submit({ note: '新载荷' }, second); });
    expect(second.mock.calls[0][0]).toEqual(first.mock.calls[0][0]);
    expect(second.mock.calls[0][0].payload).toEqual({ note: '原载荷', scopes: ['甲'] });
  });

  it('在途重复点击不产生第二个请求；明确失败（409/422）后按钮解锁并可复用同一标识', async () => {
    render(<SubmissionHarness />);
    let release!: (value: { ok: string }) => void;
    const gate = new Promise<{ ok: string }>((resolve) => {
      release = resolve;
    });
    const run = vi.fn().mockReturnValue(gate);
    act(() => {
      void latestSubmission!.submit({ note: 'a' }, run);
      void latestSubmission!.submit({ note: 'a' }, run);
    });
    expect(run).toHaveBeenCalledTimes(1);
    expect(latestSubmission!.busy).toBe(true);
    await act(async () => {
      release({ ok: 'first' });
    });
    expect(screen.getByTestId('submission')).toHaveTextContent('succeeded');

    const conflict = vi
      .fn()
      .mockRejectedValue(new ApiError('SCORE_IMPORT_REVISION_CONFLICT', '版本冲突', 409, false));
    await act(async () => {
      await latestSubmission!.submit({ note: 'a' }, conflict);
    });
    expect(screen.getByTestId('submission')).toHaveTextContent(
      'err:SCORE_IMPORT_REVISION_CONFLICT',
    );
    expect(latestSubmission!.busy).toBe(false);
    const idAfterConflict = latestSubmission!.frozen?.submissionId;
    const retry = vi.fn().mockResolvedValue({ ok: 'retried' });
    await act(async () => {
      await latestSubmission!.submit({ note: 'a' }, retry);
    });
    expect(retry.mock.calls[0][0].submissionId).toBe(idAfterConflict);
  });

  it('release 后迟到的成功不写状态（操作身份 + 代次失效）', async () => {
    render(<SubmissionHarness />);
    let release!: (value: { ok: string }) => void;
    const gate = new Promise<{ ok: string }>((resolve) => {
      release = resolve;
    });
    const run = vi.fn().mockReturnValue(gate);
    act(() => {
      void latestSubmission!.submit({ note: 'a' }, run);
    });
    act(() => latestSubmission!.release());
    await act(async () => {
      release({ ok: 'late' });
    });
    expect(screen.getByTestId('submission')).toHaveTextContent('idle');
    expect(latestSubmission!.result).toBeNull();
  });

  it('卸载后迟到的失败不写状态', async () => {
    const ui = render(<SubmissionHarness />);
    let reject!: (error: unknown) => void;
    const gate = new Promise<{ ok: string }>((_resolve, rejectFn) => {
      reject = rejectFn;
    });
    act(() => {
      void latestSubmission!.submit({ note: 'a' }, vi.fn().mockReturnValue(gate));
    });
    ui.unmount();
    await act(async () => {
      reject(new ApiError('SCORE_ACKNOWLEDGEMENT_MISMATCH', '承认范围不一致', 422, false));
    });
    expect(latestSubmission!.error).toBeNull();
  });
});

/* ------------------------------------------------------------------ 校对草稿 */

let latestDrafts: ScoreDraftsController | null = null;

function DraftsHarness({ view }: { view: ScoreImportView | null }) {
  const controller = useScoreDrafts(view);
  useEffect(() => {
    latestDrafts = controller;
  });
  return (
    <div data-testid="drafts">
      {controller.dirty ? 'dirty' : 'clean'}
      {controller.saving ? '|saving' : ''}
      {controller.conflict ? `|conflict:${controller.conflict.currentRevision}` : ''}
      {controller.issues.length > 0 ? `|issues:${controller.issues.length}` : ''}
      {controller.notice ? `|notice` : ''}
    </div>
  );
}

describe('校对草稿：409/422 保留编辑与校对状态', () => {
  it('保存成功：按原表坐标提交 PATCH，草稿清空', async () => {
    const fetchMock = stubFetch((url) => {
      if (url.includes('/score-imports/imp-1')) return jsonResponse(true, 200, importView({ revision: 4 }));
      return jsonResponse(false, 404, { code: 'NOT_FOUND', message: url });
    });
    render(<DraftsHarness view={importView()} />);
    act(() => {
      latestDrafts!.setParticipant(3, 'part-9');
      latestDrafts!.setCell(4, 'E', '7.5');
    });
    expect(screen.getByTestId('drafts')).toHaveTextContent('dirty');
    await act(async () => {
      await latestDrafts!.save();
    });
    const patch = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === 'PATCH');
    const body = JSON.parse(String((patch?.[1] as RequestInit).body));
    expect(body).toEqual({
      expectedRevision: 3,
      rows: [
        { rowNo: 3, participantId: 'part-9' },
        { rowNo: 4, cells: [{ row: 4, column: 'E', text: '7.5' }] },
      ],
    });
    expect(screen.getByTestId('drafts')).toHaveTextContent('clean');
    expect(screen.getByTestId('drafts')).toHaveTextContent('notice');
  });

  it('409：保留编辑并给出服务端当前版本', async () => {
    stubFetch(() =>
      jsonResponse(false, 409, {
        code: 'SCORE_IMPORT_REVISION_CONFLICT',
        message: '批次已被其他操作更新。',
        details: { currentRevision: 9 },
      }),
    );
    render(<DraftsHarness view={importView()} />);
    act(() => latestDrafts!.setCell(2, 'D', '6'));
    await act(async () => {
      await latestDrafts!.save();
    });
    const node = screen.getByTestId('drafts');
    expect(node).toHaveTextContent('conflict:9');
    expect(node).toHaveTextContent('dirty'); // 编辑绝不因 409 被清掉
  });

  it('422：保留校对状态并逐条保留行列定位', async () => {
    stubFetch(() =>
      jsonResponse(false, 422, {
        code: 'SCORE_CELL_OVER_MAX',
        message: '单元格超过满分。',
        details: {
          issues: [{ row: 2, column: 'D', code: 'SCORE_CELL_OVER_MAX', message: '超过满分 4 分。' }],
        },
      }),
    );
    render(<DraftsHarness view={importView()} />);
    act(() => latestDrafts!.setCell(2, 'D', '99'));
    await act(async () => {
      await latestDrafts!.save();
    });
    const node = screen.getByTestId('drafts');
    expect(node).toHaveTextContent('issues:1');
    expect(node).toHaveTextContent('dirty');
    expect(latestDrafts!.issues[0]).toMatchObject({ row: 2, column: 'D' });
  });

  it('StrictMode 双挂载后仍可保存；卸载后迟到响应不写状态', async () => {
    stubFetch(() => jsonResponse(true, 200, importView({ revision: 5 })));
    const ui = render(
      <StrictMode>
        <DraftsHarness view={importView()} />
      </StrictMode>,
    );
    act(() => latestDrafts!.setCell(2, 'D', '4'));
    await act(async () => {
      await latestDrafts!.save();
    });
    expect(screen.getByTestId('drafts')).toHaveTextContent('clean');

    let release!: () => void;
    const gate = new Promise<Response>((resolve) => {
      release = () => resolve(jsonResponse(true, 200, importView({ revision: 6 })));
    });
    vi.stubGlobal('fetch', vi.fn(() => gate));
    act(() => latestDrafts!.setCell(3, 'E', '8'));
    let pending: Promise<ScoreImportView | null> = Promise.resolve(null);
    act(() => {
      pending = latestDrafts!.save();
    });
    ui.unmount();
    release();
    await act(async () => {
      await pending;
    });
    expect(latestDrafts!.notice).toBeNull();
    await waitFor(() => expect(screen.queryByTestId('drafts')).toBeNull());
  });

  it('切换批次（视图身份变化）清空草稿：编辑不跨批次偷渡', async () => {
    const ui = render(<DraftsHarness view={importView()} />);
    act(() => latestDrafts!.setCell(2, 'D', '4'));
    expect(screen.getByTestId('drafts')).toHaveTextContent('dirty');
    ui.rerender(
      <DraftsHarness view={importView({ importId: 'imp-2', assessmentId: 'as-2' })} />,
    );
    await waitFor(() => expect(screen.getByTestId('drafts')).toHaveTextContent('clean'));
  });
});
