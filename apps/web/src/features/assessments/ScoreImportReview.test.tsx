import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ScoreImportView, ScoreImportRowView } from '@/contracts/scores';
import { ScoreImportReview } from './ScoreImportReview';

const participants = [
  { participantId: 'p-absent', classId: 'c-1', name: '甲', attendance: 'present' as const },
  { participantId: 'p-exempt', classId: 'c-1', name: '乙', attendance: 'present' as const },
  { participantId: 'p-zero', classId: 'c-1', name: '丙', attendance: 'present' as const },
  { participantId: 'p-missing', classId: 'c-1', name: '丁', attendance: 'present' as const },
];

function view(overrides: Partial<ScoreImportView> = {}): ScoreImportView {
  return {
    importId: 'import-1', assessmentId: 'assessment-1', assessmentTitle: '期中',
    state: 'reviewing', revision: 1, previewVersion: 1,
    fileAsset: { assetId: 'asset-1', kind: 'score_sheet', blobKey: 'blobs/abc', sha256: 'abc',
      mediaType: 'text/csv', byteSize: 128, originalName: '成绩.csv' },
    mapping: { workSheet: '成绩', headerRow: 1, studentNoColumn: 'A', nameColumn: 'B',
      itemColumns: [{ itemId: 'i-1', column: 'C' }, { itemId: 'i-2', column: 'D' }, { itemId: 'i-3', column: 'E' }] },
    rowCount: 4, resolvedRowCount: 4, missingCellCount: 1,
    requiredAcknowledgements: { absences: [{ classId: 'c-1', participantIds: ['p-absent'] }],
      missing: { participantIds: ['p-missing'], cellCount: 1 } },
    createdAt: '2026-10-02T00:00:00Z', updatedAt: '2026-10-02T00:00:00Z', ...overrides,
  };
}

function row(rowNo: number, participantId: string, texts: string[]): ScoreImportRowView {
  return { rowNo, participantId, cells: texts.map((text, index) => ({ row: rowNo,
    column: String.fromCharCode(67 + index), text, isFormula: false })), issues: [] };
}
const sourceRows = [
  row(2, 'p-absent', ['缺考', '', '']), row(3, 'p-exempt', ['免考', '', '']),
  row(4, 'p-zero', ['0', '3', '5']), row(5, 'p-missing', ['2', '', '5']),
];

function response(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

function stubFetch(confirm?: (body: Record<string, unknown>) => Promise<Response>, tableRows = sourceRows) {
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input).endsWith('/confirm')) {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      bodies.push(body);
      if (confirm) return confirm(body);
      return response(200, { importId: 'import-1', state: 'confirmed', revisionId: 'revision-1',
        assessmentRevision: 2, activeScoreRevisionId: 'revision-1', replayed: false });
    }
    return response(200, { items: tableRows, total: tableRows.length, offset: 0, limit: 50 });
  }));
  return bodies;
}

function ui(importView = view(), onChanged = vi.fn()) {
  return <StrictMode><ScoreImportReview view={importView} reloadToken={0}
    leaves={[{ itemId: 'i-1', questionNo: 'Q1' }, { itemId: 'i-2', questionNo: 'Q2' }, { itemId: 'i-3', questionNo: 'Q3' }]}
    participants={participants} assessmentRevision={1} onReload={() => {}}
    onReloadAssessment={() => {}} onChanged={onChanged} onOpenHistory={() => {}} />
  </StrictMode>;
}

function openConfirmation() {
  fireEvent.click(screen.getByTestId('score-open-confirm'));
  fireEvent.click(screen.getByTestId('score-confirm-submit'));
}

beforeEach(() => {
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); } },
    close: { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); } },
  });
});
afterEach(() => {
  cleanup();
  Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
  Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
  vi.unstubAllGlobals();
});

describe('服务端有效矩阵的成绩承认范围', () => {
  it('保存校对在途及成功但新权威预览未读回均阻断，r2重新承认后才确认新分数', async () => {
    let finish!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => { finish = resolve; });
    const patches: Record<string, unknown>[] = [];
    const confirms: Record<string, unknown>[] = [];
    let persistedText = '0';
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'PATCH') {
        patches.push(JSON.parse(String(init.body)));
        return pending;
      }
      if (init?.method === 'POST') {
        confirms.push(JSON.parse(String(init.body)));
        expect(persistedText).toBe('1');
        return response(200, { importId: 'import-1', revisionId: 'new-r2', assessmentRevision: 2, replayed: false });
      }
      return response(200, { items: sourceRows, total: sourceRows.length });
    }));
    const rendered = render(ui());
    await screen.findByLabelText('第 4 行 列 C 校正');
    fireEvent.change(screen.getByLabelText('第 4 行 列 C 校正'), { target: { value: '1' } });
    fireEvent.click(screen.getByTestId('score-save-drafts'));
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(screen.getByTestId('score-goto-acknowledge')).toBeDisabled();
    expect(confirms).toHaveLength(0);
    persistedText = '1';
    await act(async () => finish(response(200, view({ revision: 2, previewVersion: 2 }))));
    expect(await screen.findByTestId('score-waiting-preview')).toBeInTheDocument();
    expect(screen.getByTestId('score-goto-acknowledge')).toBeDisabled();
    expect(confirms).toHaveLength(0);
    rendered.rerender(ui(view({ revision: 2, previewVersion: 2 })));
    await waitFor(() => expect(screen.getByTestId('score-goto-acknowledge')).toBeEnabled());
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    expect(screen.getByLabelText('承认 c-1 缺考 1 人次')).not.toBeChecked();
    fireEvent.click(screen.getByLabelText('承认 c-1 缺考 1 人次'));
    fireEvent.click(screen.getByLabelText('承认空白 1 个单元覆盖 1 人次'));
    openConfirmation();
    await screen.findByTestId('score-confirm-result');
    expect(patches[0]).toMatchObject({ expectedRevision: 1, rows: [{ rowNo: 4, cells: [{ row: 4, column: 'C', text: '1' }] }] });
    expect(confirms).toHaveLength(1);
    expect(confirms[0]).toMatchObject({ expectedImportRevision: 2, previewVersion: 2 });
  });

  it('确认响应未知时刷新版本和映射守卫仍允许原submission及完整包重放', async () => {
    let attempts = 0;
    const bodies = stubFetch(async () => {
      attempts += 1;
      if (attempts === 1) throw new TypeError('response lost');
      return response(200, { importId: 'import-1', revisionId: 'fixed-r1', assessmentRevision: 2, replayed: true });
    });
    const current = view({ requiredAcknowledgements: { absences: [], missing: null } });
    const rendered = render(ui(current));
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    openConfirmation();
    await screen.findByTestId('score-confirm-unknown');
    rendered.rerender(<StrictMode><ScoreImportReview view={{ ...current, revision: 8, previewVersion: 8 }}
      reloadToken={1} leaves={[]} participants={participants} assessmentRevision={9} mappingPending
      onReload={() => {}} onReloadAssessment={() => {}} onChanged={() => {}} onOpenHistory={() => {}} /></StrictMode>);
    fireEvent.click(screen.getByTestId('score-open-confirm'));
    fireEvent.click(screen.getByTestId('score-confirm-submit'));
    await screen.findByTestId('score-confirm-result');
    expect(bodies).toHaveLength(2);
    expect(bodies[1]).toEqual(bodies[0]);
    expect(bodies[1]).toMatchObject({ expectedImportRevision: 1, expectedAssessmentRevision: 1, previewVersion: 1 });
  });

  it.each([false, true])('承认后编辑（已打开弹窗=%s）失效承认且所有旧确认入口零POST', async (opened) => {
    const bodies = stubFetch();
    render(ui());
    await screen.findByLabelText('第 4 行 列 C 校正');
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    fireEvent.click(screen.getByLabelText('承认 c-1 缺考 1 人次'));
    fireEvent.click(screen.getByLabelText('承认空白 1 个单元覆盖 1 人次'));
    if (opened) fireEvent.click(screen.getByTestId('score-open-confirm'));
    const oldSubmit = screen.queryByTestId('score-confirm-submit');
    fireEvent.change(screen.getByLabelText('第 4 行 列 C 校正'), { target: { value: '1' } });
    if (oldSubmit) fireEvent.click(oldSubmit);
    expect(screen.getByText('有未保存的校对')).toBeInTheDocument();
    expect(screen.getByTestId('score-goto-acknowledge')).toBeDisabled();
    expect(screen.queryByTestId('score-open-confirm')).not.toBeInTheDocument();
    expect(screen.queryByTestId('score-confirm-submit')).not.toBeInTheDocument();
    expect(bodies).toHaveLength(0);
  });

  it('缺考/免考标记覆盖整人次，显式 0 和真正 missing 组合只承认真实缺口', async () => {
    const bodies = stubFetch();
    render(ui());
    await screen.findByTestId('score-cell-status-4-C');
    expect(screen.getByTestId('score-cell-status-4-C')).toHaveTextContent('0');
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    expect(screen.queryByLabelText(/承认空白 [25] 个/)).not.toBeInTheDocument();
    expect(screen.getByTestId('score-open-confirm')).toBeDisabled();
    fireEvent.click(screen.getByLabelText('承认 c-1 缺考 1 人次'));
    fireEvent.click(screen.getByLabelText('承认空白 1 个单元覆盖 1 人次'));
    openConfirmation();
    await screen.findByTestId('score-confirm-result');
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatchObject({ absences: [{ classId: 'c-1', participantIds: ['p-absent'] }],
      missing: { participantIds: ['p-missing'], cellCount: 1 }, previewVersion: 1 });
  });

  it('缺考加原件剩余空白可真实发出 missing=null 的合法确认', async () => {
    const bodies = stubFetch();
    render(ui(view({ missingCellCount: 0, requiredAcknowledgements: {
      absences: [{ classId: 'c-1', participantIds: ['p-absent'] }], missing: null } })));
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    fireEvent.click(screen.getByLabelText('承认 c-1 缺考 1 人次'));
    expect(screen.getByTestId('score-ack-missing')).toHaveTextContent('没有空白单元');
    expect(screen.queryByLabelText(/承认空白/)).not.toBeInTheDocument();
    expect(screen.getByTestId('score-open-confirm')).toBeEnabled();
    openConfirmation();
    await screen.findByTestId('score-confirm-result');
    expect(bodies[0]).toMatchObject({ missing: null });
  });

  it('已校正的服务端范围优先于原表文本/施测 attendance，刷新后承认失效', async () => {
    const bodies = stubFetch();
    const current = view({ requiredAcknowledgements: { absences: [], missing: {
      participantIds: ['p-absent'], cellCount: 3 } } });
    const rendered = render(ui(current));
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    expect(screen.queryByLabelText(/承认 .* 缺考/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('承认空白 3 个单元覆盖 1 人次'));
    expect(screen.getByTestId('score-open-confirm')).toBeEnabled();
    rendered.rerender(ui({ ...current, revision: 2, previewVersion: 2 }));
    await waitFor(() => expect(screen.getByTestId('score-open-confirm')).toBeDisabled());
    expect(screen.getByLabelText('承认空白 3 个单元覆盖 1 人次')).not.toBeChecked();
    expect(bodies).toHaveLength(0);
  });

  it('旧服务端缺少权威范围时明确提示并阻断确认', () => {
    const bodies = stubFetch();
    // 模拟跨版本响应缺字段；不能默认为没有 missing/absent。
    const legacy = view();
    delete (legacy as Partial<ScoreImportView>).requiredAcknowledgements;
    render(ui(legacy));
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    expect(screen.getByTestId('score-ack-unavailable')).toHaveTextContent('刷新对照');
    expect(screen.getByTestId('score-open-confirm')).toBeDisabled();
    expect(bodies).toHaveLength(0);
  });

  it('422承认不一致保留校对页面与服务端定位，没有成功回执', async () => {
    const bodies = stubFetch(async () => response(422, { code: 'SCORE_ACKNOWLEDGEMENT_MISMATCH',
      message: '预览已变化', details: { issues: [{ row: 5, column: 'D', code: 'SCORE_ACKNOWLEDGEMENT_MISMATCH', message: '该格仍为空' }] } }));
    const changed = vi.fn();
    render(ui(view(), changed));
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    fireEvent.click(screen.getByLabelText('承认 c-1 缺考 1 人次'));
    fireEvent.click(screen.getByLabelText('承认空白 1 个单元覆盖 1 人次'));
    openConfirmation();
    await screen.findByTestId('score-ack-mismatch');
    expect(bodies).toHaveLength(1);
    expect(screen.queryByTestId('score-confirm-result')).not.toBeInTheDocument();
    expect(changed).not.toHaveBeenCalled();
    expect(screen.getByTestId('score-import-review')).toBeInTheDocument();
  });

  it('单格展示有效缺考与有效0，同时保留原件空白和已保存校正；草稿另行标识', async () => {
    stubFetch(undefined, [{ rowNo: 2, participantId: 'p-absent', cells: [
      { row: 2, column: 'C', text: '', originalText: '', effectiveStatus: 'absent', scoreUnits: null },
      { row: 2, column: 'D', text: '0', originalText: '', correctedText: '0', effectiveStatus: 'recorded', scoreUnits: 0 },
    ] }]);
    render(ui());
    expect(await screen.findByTestId('score-cell-status-2-C')).toHaveTextContent('缺考');
    expect(screen.getByTestId('score-cell-status-2-D')).toHaveTextContent('0');
    expect(screen.getByTestId('score-original-2-D')).toHaveTextContent('原件：（空白）');
    expect(screen.getByTestId('score-corrected-2-D')).toHaveTextContent('已保存校正：0');
    fireEvent.change(screen.getByLabelText('第 2 行 列 D 校正'), { target: { value: '免考' } });
    expect(screen.getByTestId('score-cell-status-2-D')).toHaveTextContent('免考');
    expect(screen.getByText('未保存校正预览')).toBeInTheDocument();
    expect(screen.getByTestId('score-corrected-2-D')).toHaveTextContent('已保存校正：0');
  });
});
