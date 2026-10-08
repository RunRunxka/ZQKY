import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ScoreImportView } from '@/contracts/scores';
import { ScorePanel } from './ScorePanel';

function view(id = 'imp-1', revision = 1): ScoreImportView & { mapping: NonNullable<ScoreImportView['mapping']> } {
  return {
    importId: id, assessmentId: 'as-1', assessmentTitle: '期中', state: 'reviewing',
    revision, previewVersion: revision, fileAsset: { assetId: 'asset-1', kind: 'score_sheet',
      blobKey: 'blobs/abc', sha256: 'abc', mediaType: 'text/csv', byteSize: 128, originalName: '成绩.csv' },
    mapping: { workSheet: '成绩', headerRow: 1, studentNoColumn: 'A', nameColumn: 'B',
      itemColumns: [{ itemId: 'i-1', column: 'C' }], attendanceColumn: 'D', totalColumn: 'E' },
    rowCount: 1, resolvedRowCount: 1, missingCellCount: 0,
    requiredAcknowledgements: { absences: [], missing: null },
    createdAt: '2026-10-02T00:00:00Z', updatedAt: '2026-10-02T00:00:00Z',
  };
}
function response(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}
function setup(mutate: (url: string, init: RequestInit) => Promise<Response>, currentView: ScoreImportView = view()) {
  let latest = currentView;
  const fetched = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === 'POST' || init?.method === 'PATCH') return mutate(url, init);
    if (url.includes('/score-imports?')) return response(200, { items: [view(), view('imp-2')], total: 2 });
    if (url.includes('/score-imports/') && url.includes('/rows')) return response(200,
      { items: [{ rowNo: 2, participantId: 'p-1', cells: [{ row: 2, column: 'C', text: '2',
        effectiveStatus: 'recorded', scoreUnits: 200 }] }], total: 1 });
    if (url.includes('/score-imports/')) return response(200, url.includes('imp-2') ? view('imp-2') : latest);
    if (url.includes('/score-revisions')) return response(200, { items: [], total: 0 });
    if (url.includes('/content')) return response(200, { items: [{ itemId: 'i-1', parentItemId: null,
      questionNo: 'Q1', ordinal: 1, isScored: true, maxScoreUnits: 200 }], blocks: [] });
    return response(200, { assessment: { assessmentId: 'as-1', paperId: 'paper-1',
      paperRevisionId: 'pr-1', title: '期中', participantCount: 1, revision: 4 },
    participants: [{ participantId: 'p-1', classId: 'c-1', nameSnapshot: '甲', attendance: 'present' }] });
  });
  vi.stubGlobal('fetch', fetched);
  return { fetched, setView: (next: ScoreImportView) => { latest = next; } };
}
function ui(changed = vi.fn()) {
  return <StrictMode><ScorePanel assessmentId="as-1" onOpenHistory={() => {}} refreshToken={0} onChanged={changed} /></StrictMode>;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('成绩映射与明确刷新预览', () => {
  it('映射保存200但权威读取尚为r1时阻断旧确认，r2读回才允许重新承认', async () => {
    const bodies: unknown[] = [];
    const fixture = setup(async (_url, init) => {
      bodies.push(JSON.parse(String(init.body)));
      const next = view('imp-1', 2);
      next.mapping.totalColumn = 'F';
      return response(200, next);
    });
    render(ui());
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    expect(screen.getByTestId('score-open-confirm')).toBeEnabled();
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'F' } });
    expect(screen.getByTestId('score-open-confirm')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    await screen.findByTestId('assessments-mapping-waiting-preview');
    expect(screen.getByTestId('score-open-confirm')).toBeDisabled();
    expect(screen.getByLabelText('总分列')).toHaveValue('F');
    expect(bodies).toHaveLength(1);
    const current = view('imp-1', 2);
    current.mapping.totalColumn = 'F';
    fixture.setView(current);
    fireEvent.click(screen.getByTestId('score-ack-refresh'));
    await waitFor(() => expect(screen.queryByTestId('assessments-mapping-waiting-preview')).not.toBeInTheDocument());
    expect(screen.getByTestId('score-goto-acknowledge')).toBeEnabled();
    expect(bodies).toHaveLength(1);
  });

  it.each([409, 422, 0])('映射在途较新编辑在失败%s与显式刷新后仍保留', async (status) => {
    let finish!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => { finish = resolve; });
    const fixture = setup(async () => {
      const result = await pending;
      if (status === 0) throw new TypeError('network failed');
      return result;
    });
    render(ui());
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'F' } });
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'G' } });
    await act(async () => finish(response(status || 200, { code: 'MAPPING_REFUSED', message: '保存失败',
      details: { currentRevision: 3, issues: [{ row: 1, column: 'F', code: 'MAPPING_REFUSED', message: '列冲突' }] } })));
    await screen.findByTestId('assessments-mapping-error');
    const next = view('imp-1', 3);
    next.mapping.totalColumn = 'H';
    fixture.setView(next);
    fireEvent.click(screen.getByTestId('score-ack-refresh'));
    await waitFor(() => expect(screen.getByText(/批次 r3 · 预览 v3/)).toBeInTheDocument());
    expect(screen.getByLabelText('总分列')).toHaveValue('G');
    expect(screen.getByTestId('assessments-mapping-dirty')).toBeInTheDocument();
    expect(screen.getByTestId('score-goto-acknowledge')).toBeDisabled();
  });

  it.each(['success', 'failure'] as const)('切批次后迟到映射%s不能擦除新批次编辑', async (outcome) => {
    let finish!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => { finish = resolve; });
    setup(() => pending);
    render(ui());
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'F' } });
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    fireEvent.click(screen.getByTestId('assessments-import-imp-2'));
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'G' } });
    await act(async () => finish(outcome === 'success' ? response(200, view('imp-1', 2))
      : response(409, { code: 'OLD_MAPPING_CONFLICT', message: '旧批次保存冲突' })));
    expect(screen.getByLabelText('总分列')).toHaveValue('G');
    expect(screen.getByTestId('assessments-mapping-dirty')).toBeInTheDocument();
    expect(screen.queryByTestId('assessments-mapping-error')).not.toBeInTheDocument();
    expect(screen.queryByTestId('assessments-mapping-notice')).not.toBeInTheDocument();
  });

  it('映射卸载后迟到200不改变新挂载的未保存输入', async () => {
    let finish!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => { finish = resolve; });
    setup(() => pending);
    const first = render(ui());
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'F' } });
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    first.unmount();
    render(ui());
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'G' } });
    await act(async () => finish(response(200, view('imp-1', 2))));
    expect(screen.getByLabelText('总分列')).toHaveValue('G');
    expect(screen.getByTestId('assessments-mapping-dirty')).toBeInTheDocument();
    expect(screen.queryByTestId('assessments-mapping-notice')).not.toBeInTheDocument();
  });

  it('映射保存200只清请求快照，保留在途较新G并以权威r2再次保存', async () => {
    let finish!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => { finish = resolve; });
    const bodies: Record<string, unknown>[] = [];
    const fixture = setup(async (_url, init) => {
      bodies.push(JSON.parse(String(init.body)));
      if (bodies.length === 1) return pending;
      const latest = view('imp-1', 3);
      latest.mapping.totalColumn = 'G';
      fixture.setView(latest);
      return response(200, latest);
    });
    render(ui());
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'F' } });
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'G' } });
    const persisted = view('imp-1', 2);
    persisted.mapping.totalColumn = 'F';
    fixture.setView(persisted);
    await act(async () => finish(response(200, persisted)));
    await screen.findByTestId('assessments-mapping-notice');
    expect(screen.getByLabelText('总分列')).toHaveValue('G');
    expect(screen.getByTestId('assessments-mapping-dirty')).toHaveTextContent('未保存');
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toMatchObject({ expectedRevision: 2, mapping: { totalColumn: 'G' } });
    await waitFor(() => expect(screen.queryByTestId('assessments-mapping-dirty')).not.toBeInTheDocument());
  });

  it('原有出勤/总分列读回并随计分列修改完整保存', async () => {
    const bodies: unknown[] = [];
    setup(async (_url, init) => { bodies.push(JSON.parse(String(init.body))); return response(200, view('imp-1', 2)); });
    render(ui());
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    expect(screen.getByLabelText('出勤列')).toHaveValue('D');
    fireEvent.change(screen.getByLabelText('Q1 列字母'), { target: { value: 'f' } });
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    await screen.findByTestId('assessments-mapping-notice');
    expect(bodies[0]).toMatchObject({ expectedRevision: 1, mapping: {
      attendanceColumn: 'D', totalColumn: 'E', itemColumns: [{ itemId: 'i-1', column: 'F' }],
    } });
  });

  it('明确刷新用导入/施测/base三个独立版本，刷新后保存未完成的校对与映射编辑', async () => {
    const bodies: unknown[] = [];
    const fixture = setup(async (_url, init) => {
      bodies.push(JSON.parse(String(init.body)));
      fixture.setView(view('imp-1', 2));
      return response(200, view('imp-1', 2));
    });
    render(ui());
    await screen.findByLabelText('第 2 行 列 C 校正');
    fireEvent.change(screen.getByLabelText('第 2 行 列 C 校正'), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'Z' } });
    fireEvent.click(screen.getByRole('button', { name: '明确刷新成绩预览' }));
    await screen.findByTestId('assessments-preview-notice');
    await waitFor(() => expect(screen.getByText(/批次 r2 · 预览 v2/)).toBeInTheDocument());
    expect(bodies[0]).toEqual({ expectedImportRevision: 1, expectedAssessmentRevision: 4, baseScoreRevisionId: null });
    expect(await screen.findByLabelText('第 2 行 列 C 校正')).toHaveValue('1');
    expect(screen.getByLabelText('总分列')).toHaveValue('Z');
  });

  it('刷新CAS失败保留校对并显示当前版本', async () => {
    setup(async () => response(409, { code: 'SCORE_IMPORT_REVISION_CONFLICT', message: '批次已变化', details: { currentRevision: 8 } }));
    render(ui());
    await screen.findByLabelText('第 2 行 列 C 校正');
    fireEvent.change(screen.getByLabelText('第 2 行 列 C 校正'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: '明确刷新成绩预览' }));
    expect(await screen.findByTestId('assessments-preview-error')).toHaveTextContent('当前版本 8');
    expect(screen.getByLabelText('第 2 行 列 C 校正')).toHaveValue('1');
    expect(screen.queryByTestId('assessments-preview-notice')).not.toBeInTheDocument();
  });

  it('总分/出勤映射422定位到原物理列，保留教师编辑', async () => {
    const bodies: unknown[] = [];
    setup(async (_url, init) => { bodies.push(JSON.parse(String(init.body))); return response(422, {
      code: 'SCORE_MAPPING_INVALID', message: '总分列与计分叶冲突', details: { issues: [
        { row: 1, column: 'F', field: 'totalColumn', code: 'SCORE_MAPPING_INVALID', message: '同一物理列不能同时作为总分和小题得分' },
      ] },
    }); });
    render(ui());
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'f' } });
    fireEvent.change(screen.getByLabelText('Q1 列字母'), { target: { value: 'F' } });
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    expect(await screen.findByTestId('assessments-mapping-issues')).toHaveTextContent('原表第 1 行 · 列 F · 字段 totalColumn');
    expect(screen.getByLabelText('总分列')).toHaveValue('f');
    expect(screen.getByLabelText('出勤列')).toHaveValue('D');
    expect(bodies[0]).toMatchObject({ mapping: { totalColumn: 'F', attendanceColumn: 'D' } });
  });

  it.each(['success', 'failure'] as const)('切批次后迟到预览%s不污染当前批次', async (outcome) => {
    let complete!: (value: Response) => void;
    const gate = new Promise<Response>((resolve) => { complete = resolve; });
    const { fetched } = setup(() => gate);
    render(ui());
    await screen.findByLabelText('总分列');
    fireEvent.click(screen.getByRole('button', { name: '明确刷新成绩预览' }));
    await waitFor(() => expect(fetched.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1));
    fireEvent.click(screen.getByTestId('assessments-import-imp-2'));
    await waitFor(() => expect(screen.getByTestId('assessments-import-imp-2')).toHaveAttribute('aria-pressed', 'true'));
    await act(async () => complete(outcome === 'success' ? response(200, view('imp-1', 2))
      : response(422, { code: 'OLD_ERROR', message: '旧批次失败' })));
    expect(screen.queryByTestId('assessments-preview-notice')).not.toBeInTheDocument();
    expect(screen.queryByTestId('assessments-preview-error')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '明确刷新成绩预览' })).toBeEnabled();
  });

  it('卸载后迟到上传成功不通知父级', async () => {
    let complete!: (value: Response) => void;
    const gate = new Promise<Response>((resolve) => { complete = resolve; });
    const { fetched } = setup(() => gate);
    const changed = vi.fn();
    const rendered = render(ui(changed));
    await screen.findByLabelText('总分列');
    fireEvent.change(screen.getByLabelText('成绩表格文件'), { target: { files: [new File(['成绩'], '成绩.csv')] } });
    fireEvent.submit(screen.getByRole('form', { name: '上传成绩表' }));
    await waitFor(() => expect(fetched.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1));
    rendered.unmount();
    await act(async () => complete(response(201, view('old-upload'))));
    expect(changed).not.toHaveBeenCalled();
  });
});

/* ------------------------------------------------------------------ 放弃未确认批次 */

function summary(importId: string, state: ScoreImportView['state'], revision = 1) {
  return {
    importId, assessmentId: 'as-1', state, revision, rowCount: 1,
    createdAt: '2026-10-02T00:00:00Z', updatedAt: '2026-10-02T00:00:00Z',
  };
}

function stubBatches(
  post: (url: string, init: RequestInit) => Promise<Response> | Response,
  mutate: () => { discarded: boolean },
) {
  const fetched = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === 'POST') return post(url, init);
    const { discarded } = mutate();
    if (url.includes('/score-imports?')) return response(200, { items: [
      summary('imp-1', discarded ? 'cancelled' : 'reviewing', discarded ? 2 : 1),
      summary('imp-2', 'confirmed', 4),
    ], total: 2, offset: 0, limit: 50 });
    if (url.includes('/score-imports/') && url.includes('/rows')) return response(200, { items: [], total: 0 });
    if (url.includes('/score-imports/')) return response(200, url.includes('imp-2')
      ? view('imp-2', 4)
      : { ...view('imp-1', discarded ? 2 : 1), state: discarded ? 'cancelled' : 'reviewing' });
    if (url.includes('/score-revisions')) return response(200, { items: [], total: 0 });
    if (url.includes('/content')) return response(200, { items: [], blocks: [] });
    return response(200, { assessment: { assessmentId: 'as-1', paperId: 'paper-1',
      paperRevisionId: 'pr-1', title: '期中', participantCount: 1, revision: 4 }, participants: [] });
  });
  vi.stubGlobal('fetch', fetched);
  return fetched;
}

describe('成绩导入批次的放弃', () => {
  it('未确认批次显示放弃并可置为已取消；已确认批次不显示放弃', async () => {
    const confirmSpy = vi.fn(() => true);
    vi.stubGlobal('confirm', confirmSpy);
    const writes: { url: string; body: unknown }[] = [];
    const state = { discarded: false };
    stubBatches((url, init) => {
      writes.push({ url, body: JSON.parse(String(init.body)) });
      state.discarded = true;
      return response(200, { ...view('imp-1', 2), state: 'cancelled' });
    }, () => state);
    render(ui());
    await screen.findByTestId('assessments-discard-import-imp-1');
    expect(screen.queryByTestId('assessments-discard-import-imp-2')).not.toBeInTheDocument();
    expect(screen.getByTestId('assessments-import-imp-2')).toHaveTextContent('已确认入库');
    fireEvent.click(screen.getByTestId('assessments-discard-import-imp-1'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(writes[0]).toEqual({
      url: '/api/v1/score-imports/imp-1/discard',
      body: { expectedRevision: 1 },
    });
    await waitFor(() => expect(screen.getByTestId('assessments-import-imp-1')).toHaveTextContent('已取消'));
  });

  it('放弃失败显示服务端 message，批次仍可校对', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    const state = { discarded: false };
    stubBatches(
      () => response(409, { code: 'SCORE_IMPORT_CONFIRMED', message: '该成绩批次已确认，不能放弃' }),
      () => state,
    );
    render(ui());
    await screen.findByTestId('assessments-discard-import-imp-1');
    fireEvent.click(screen.getByTestId('assessments-discard-import-imp-1'));
    const alert = await screen.findByTestId('assessments-discard-error');
    expect(alert).toHaveTextContent('该成绩批次已确认，不能放弃');
    expect(screen.getByTestId('assessments-import-imp-1')).toHaveTextContent('校对中');
  });
});

/* ------------------------------------------------------------------ 名称优先 */

describe('名称优先：批次文件名与原卷标题', () => {
  it('批次主文本用上传文件名（缺失回落短号），importId 收进次行小字；施测提示用原卷标题', async () => {
    const summaries = [
      { importId: 'imp-file', assessmentId: 'as-1', uploadedFileName: '期中成绩单.xlsx',
        state: 'reviewing', revision: 1, rowCount: 12, createdAt: '', updatedAt: '' },
      { importId: 'imp-long-identifier', assessmentId: 'as-1', uploadedFileName: null,
        state: 'confirmed', revision: 3, rowCount: 9, createdAt: '', updatedAt: '' },
    ];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/score-imports?')) return response(200, { items: summaries, total: 2 });
      if (url.includes('/rows')) return response(200, { items: [], total: 0 });
      if (url.includes('/score-imports/imp-file')) return response(200, view('imp-file'));
      if (url.includes('/score-imports/imp-long-identifier')) return response(200, view('imp-long-identifier'));
      if (url.includes('/score-revisions')) return response(200, { items: [], total: 0 });
      if (url.includes('/content')) return response(200, { items: [], blocks: [] });
      return response(200, {
        assessment: { assessmentId: 'as-1', paperId: 'paper-1', paperRevisionId: 'pr-1',
          paperTitle: '一元一次方程原卷', title: '期中', participantCount: 1, revision: 4 },
        participants: [],
      });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(ui());
    await screen.findByTestId('assessments-import-imp-file');
    // 主文本 = 文件名；importId 降为小字（短号），仍可核对
    expect(screen.getByTestId('assessments-import-imp-file')).toHaveTextContent('期中成绩单.xlsx');
    expect(screen.getByTestId('assessments-import-imp-file')).toHaveTextContent('批次 imp-file');
    expect(screen.getByTestId('assessments-import-imp-file')).toHaveTextContent('行 12');
    // 文件名为空：回落「批次 <短号>」，不显示一串 id
    expect(screen.getByTestId('assessments-import-imp-long-identifier')).toHaveTextContent('批次 imp-long…');
    // 施测提示显示原卷标题，不显示 paperRevisionId
    expect(await screen.findByText(/原卷「一元一次方程原卷」/)).toBeInTheDocument();
    expect(screen.queryByText(/原卷修订 pr-1/)).not.toBeInTheDocument();
  });
});
