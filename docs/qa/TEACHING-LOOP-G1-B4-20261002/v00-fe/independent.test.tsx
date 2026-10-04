import { StrictMode } from 'react';
import fs from 'node:fs';
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ScoreImportReview } from '@/features/assessments/ScoreImportReview';
import { ScorePanel } from '@/features/assessments/ScorePanel';
import { AssessmentsWorkspace } from '@/features/assessments/AssessmentsWorkspace';
import { RichBlocks } from '@/components/ui/RichContentRenderer';
import type { ScoreImportView } from '@/contracts/scores';

const receipts: unknown[] = [];
const rowData = () => ({ items: [{ rowNo: 2, participantId: 'p1', cells: [
  { row: 2, column: 'C', text: '2', effectiveStatus: 'recorded', scoreUnits: 200 },
] }], total: 1, offset: 0, limit: 50 });
function scoreView(revision = 1, importId = 'i1'): ScoreImportView {
  return { importId, assessmentId: 'a1', assessmentTitle: '独立样本', state: 'reviewing', revision,
    previewVersion: revision, fileAsset: { assetId: 'source', kind: 'score_sheet', blobKey: 'blobs/test',
      sha256: 'test', mediaType: 'text/csv', byteSize: 10, originalName: '独立.csv' },
    mapping: { workSheet: 'CSV', headerRow: 1, studentNoColumn: 'A', nameColumn: 'B',
      itemColumns: [{ itemId: 'q1', column: 'C' }], attendanceColumn: 'D', totalColumn: 'E' },
    rowCount: 1, resolvedRowCount: 1, missingCellCount: 0,
    requiredAcknowledgements: { absences: [], missing: null },
    createdAt: '2026-10-02T00:00:00Z', updatedAt: '2026-10-02T00:00:00Z' };
}
const reviewProps = { reloadToken: 0, leaves: [{ itemId: 'q1', questionNo: 'Q1' }],
  participants: [{ participantId: 'p1', classId: 'class1', name: '独立甲', attendance: 'present' as const }],
  assessmentRevision: 1, onReload: () => {}, onReloadAssessment: () => {}, onChanged: () => {}, onOpenHistory: () => {} };
function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => structuredClone(body) } as Response;
}
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
const confirmed = { importId: 'i1', state: 'confirmed', revisionId: 'sr1', assessmentRevision: 2,
  activeScoreRevisionId: 'sr1', replayed: false };
beforeEach(() => {
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: { configurable: true, value: function(this: HTMLDialogElement) { this.setAttribute('open', ''); } },
    close: { configurable: true, value: function(this: HTMLDialogElement) { this.removeAttribute('open'); } },
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals();
  Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
  Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
});
afterAll(() => fs.writeFileSync('docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe/component-receipts.json', JSON.stringify(receipts, null, 2)));

describe('Independent R01 score confirmation authority', () => {
  it.each([false, true])('new unsaved edit invalidates acknowledgement; dialog already open=%s', async (dialogOpen) => {
    const posts: unknown[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith('/confirm')) { posts.push(JSON.parse(String(init?.body))); return response(confirmed); }
      return response(rowData());
    }));
    render(<StrictMode><ScoreImportReview view={scoreView()} {...reviewProps}/></StrictMode>);
    await screen.findByLabelText('第 2 行 列 C 校正');
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    if (dialogOpen) { fireEvent.click(screen.getByTestId('score-open-confirm')); expect(screen.getByTestId('score-confirm-submit')).toBeEnabled(); }
    fireEvent.change(screen.getByLabelText('第 2 行 列 C 校正'), { target: { value: '1' } });
    expect(screen.getByText('有未保存的校对')).toBeVisible();
    expect(screen.getByTestId('score-goto-acknowledge')).toBeDisabled();
    expect(screen.queryByTestId('score-open-confirm')).toBeNull();
    expect(screen.queryByTestId('score-confirm-submit')).toBeNull();
    expect(posts).toEqual([]);
    receipts.push({ case: 'R01-dirty', dialogOpen, confirmRequests: posts.length });
  });

  it('saving blocks all confirmation, waits for authoritative preview and requires the new missing acknowledgement', async () => {
    const pending = deferred<Response>(); const patches: unknown[] = [], posts: Record<string, unknown>[] = [];
    const next = scoreView(2); next.missingCellCount = 1;
    next.requiredAcknowledgements = { absences: [], missing: { cellCount: 1, participantIds: ['p1'] } };
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'PATCH') { patches.push(JSON.parse(String(init.body))); return pending.promise; }
      if (String(url).endsWith('/confirm')) { posts.push(JSON.parse(String(init?.body))); return response(confirmed); }
      return response(rowData());
    }));
    const ui = render(<StrictMode><ScoreImportReview view={scoreView()} {...reviewProps}/></StrictMode>);
    fireEvent.change(await screen.findByLabelText('第 2 行 列 C 校正'), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('第 2 行 列 C 校正'), { target: { value: '' } });
    fireEvent.click(screen.getByTestId('score-save-drafts'));
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(screen.getByLabelText('第 2 行 列 C 校正')).toBeDisabled();
    expect(screen.getByTestId('score-goto-acknowledge')).toBeDisabled();
    expect(posts).toHaveLength(0);
    await act(async () => pending.resolve(response(next)));
    expect(screen.getByTestId('score-waiting-preview')).toBeVisible();
    expect(screen.getByTestId('score-goto-acknowledge')).toBeDisabled();
    ui.rerender(<StrictMode><ScoreImportReview view={next} {...reviewProps}/></StrictMode>);
    await waitFor(() => expect(screen.getByTestId('score-goto-acknowledge')).toBeEnabled());
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    expect(screen.getByTestId('score-open-confirm')).toBeDisabled();
    fireEvent.click(screen.getByLabelText('承认空白 1 个单元覆盖 1 人次'));
    fireEvent.click(screen.getByTestId('score-open-confirm')); fireEvent.click(screen.getByTestId('score-confirm-submit'));
    await screen.findByTestId('score-confirm-result');
    expect(posts).toHaveLength(1);
    expect(posts[0]).toMatchObject({ expectedImportRevision: 2, previewVersion: 2, missing: { cellCount: 1, participantIds: ['p1'] } });
    expect(patches[0]).toMatchObject({ rows: [{ rowNo: 2, cells: [{ row: 2, column: 'C', text: '' }] }] });
    receipts.push({ case: 'R01-save-preview', patches, confirms: posts });
  });

  it('unknown outcome replays the identical frozen body even if current preview and mapping are blocked', async () => {
    const posts: Record<string, unknown>[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith('/confirm')) { posts.push(JSON.parse(String(init?.body)));
        if (posts.length === 1) throw new TypeError('lost response after server commit');
        return response({ ...confirmed, replayed: true }); }
      return response(rowData());
    }));
    const ui = render(<StrictMode><ScoreImportReview view={scoreView()} {...reviewProps}/></StrictMode>);
    await screen.findByLabelText('第 2 行 列 C 校正');
    fireEvent.click(screen.getByTestId('score-goto-acknowledge')); fireEvent.click(screen.getByTestId('score-open-confirm'));
    fireEvent.click(screen.getByTestId('score-confirm-submit')); await screen.findByTestId('score-confirm-unknown');
    expect(screen.getByLabelText('第 2 行 列 C 校正')).toBeDisabled();
    const newer = scoreView(99); newer.requiredAcknowledgements = { absences: [], missing: { cellCount: 8, participantIds: ['other'] } };
    ui.rerender(<StrictMode><ScoreImportReview view={newer} mappingPending {...reviewProps}/></StrictMode>);
    fireEvent.click(screen.getByTestId('score-open-confirm')); fireEvent.click(screen.getByTestId('score-confirm-submit'));
    await screen.findByTestId('score-confirm-result');
    expect(posts).toHaveLength(2); expect(posts[1]).toEqual(posts[0]);
    expect(posts[0].submissionId).toEqual(expect.any(String)); expect(posts[0].previewVersion).toBe(1);
    receipts.push({ case: 'R01-unknown', confirms: posts });
  });
});

function installScorePanelFetch(pending: ReturnType<typeof deferred<Response>>, patches: Record<string, unknown>[], latest: { value: ScoreImportView }) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === 'PATCH') { patches.push(JSON.parse(String(init.body))); return pending.promise; }
    if (url.includes('/score-imports?')) return response({ items: [latest.value], total: 1 });
    if (url.includes('/rows')) return response(rowData());
    if (url.includes('/score-imports/')) return response(latest.value);
    if (url.includes('/score-revisions')) return response({ items: [], total: 0 });
    if (url.includes('/content')) return response({ items: [{ itemId: 'q1', parentItemId: null, questionNo: 'Q1', ordinal: 1, isScored: true, maxScoreUnits: 200 }], blocks: [] });
    return response({ assessment: { assessmentId: 'a1', paperId: 'paper', paperRevisionId: 'pr1', title: '独立样本', participantCount: 1, revision: 1 },
      participants: [{ participantId: 'p1', classId: 'class1', nameSnapshot: '独立甲', attendance: 'present' }] });
  }));
}
const panelProps = { assessmentId: 'a1', onOpenHistory: () => {}, refreshToken: 0, onChanged: () => {} };
describe('Independent R02 mapping generations', () => {
  it.each(['success', '409', '422', 'network'])('preserves newer G after F save with %s and explicit refresh', async (outcome) => {
    const pending = deferred<Response>(); const patches: Record<string, unknown>[] = [], latest = { value: scoreView() };
    installScorePanelFetch(pending, patches, latest);
    render(<StrictMode><ScorePanel {...panelProps}/></StrictMode>);
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'F' } });
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    await waitFor(() => expect(patches).toHaveLength(1));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'G' } });
    expect(screen.getByLabelText('总分列')).toHaveValue('G');
    if (outcome === 'success') { latest.value = scoreView(2); latest.value.mapping!.totalColumn = 'F'; await act(async () => pending.resolve(response(latest.value))); }
    else if (outcome === 'network') await act(async () => pending.reject(new TypeError('offline')));
    else await act(async () => pending.resolve(response({ code: 'MAPPING_REJECTED', message: '独立拒绝', retryable: false, requestId: 'independent', details: { currentRevision: 2, issues: [{ code: 'BAD_COLUMN', message: '坏列', column: 'F', row: 2 }] } }, Number(outcome))));
    await waitFor(() => expect(screen.getByRole('button', { name: '保存映射并重算' })).toBeEnabled());
    expect(screen.getByLabelText('总分列')).toHaveValue('G');
    expect(screen.getByTestId('assessments-mapping-dirty')).toBeVisible();
    fireEvent.click(screen.getAllByRole('button', { name: '刷新对照', exact: true })[0]);
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('G'));
    expect(screen.getByTestId('assessments-mapping-dirty')).toBeVisible();
    expect(patches[0]).toMatchObject({ mapping: { totalColumn: 'F' } });
    expect(screen.getByTestId('score-goto-acknowledge')).toBeDisabled();
    receipts.push({ case: 'R02-generation', outcome, patch: patches[0], visibleInput: 'G', dirty: true });
  });

  it.each(['success', '409', '422'])('late %s from unmounted old import cannot overwrite new context H', async (outcome) => {
    const pending = deferred<Response>(), patches: Record<string, unknown>[] = [], latest = { value: scoreView() };
    installScorePanelFetch(pending, patches, latest);
    const ui = render(<StrictMode><ScorePanel key="old" {...panelProps}/></StrictMode>);
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'F' } });
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' })); await waitFor(() => expect(patches).toHaveLength(1));
    latest.value = scoreView(1, 'i2');
    ui.rerender(<StrictMode><ScorePanel key="new" {...panelProps} assessmentId="a2"/></StrictMode>);
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'H' } });
    await act(async () => pending.resolve(outcome === 'success' ? response(scoreView(2)) : response({ code: 'OLD_REJECTED', message: '旧请求失败', retryable: false }, Number(outcome))));
    expect(screen.getByLabelText('总分列')).toHaveValue('H');
    expect(screen.getByTestId('assessments-mapping-dirty')).toBeVisible();
    expect(screen.queryByTestId('assessments-mapping-notice')).toBeNull();
    expect(screen.queryByTestId('assessments-mapping-error')).toBeNull();
  });
});

describe('Independent R03 mounted workspace roster changes', () => {
  it('observes create/import/transfer without class switch, preserving legal check/attendance/attempt drafts', async () => {
    const members = [
      { id: 's1', name: '保留甲', studentNo: '001', revision: 1, memberships: [] },
      { id: 's2', name: '转走乙', studentNo: '002', revision: 1, memberships: [] },
    ];
    const writes: unknown[] = []; let reads = 0;
    const rosterBatch = { importId: 'ri1', classId: 'class1', className: '独立班', state: 'reviewing', revision: 1,
      fileAsset: scoreView().fileAsset, headers: ['姓名', '学号'], mapping: { name: '姓名', studentNo: '学号' }, warnings: [], issues: [],
      rows: [{ rowNo: 1, name: '导入丁', studentNo: '004', matchedStudentId: null, matchedStudentName: null, suggestion: 'create', decision: null, issues: [] }], createdAt: '', updatedAt: '' };
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/students') && init?.method === 'POST') { const body = JSON.parse(String(init.body)); writes.push(body); const next = { id: 's3', name: body.name, studentNo: body.studentNo, revision: 1, memberships: [] }; members.push(next); return response(next, 201); }
      if (url.endsWith('/roster-imports') && init?.method === 'POST') return response(rosterBatch, 201);
      if (url.endsWith('/ri1/confirm')) { writes.push(JSON.parse(String(init?.body))); members.push({ id: 's4', name: '导入丁', studentNo: '004', revision: 1, memberships: [] }); return response({ importId: 'ri1', state: 'confirmed', applied: [{ studentId: 's4', rowNo: 1 }], ignored: [], replayed: false }); }
      if (url.endsWith('/s2/transfer')) { writes.push(JSON.parse(String(init?.body))); const index = members.findIndex(x => x.id === 's2'); const removed = members.splice(index, 1)[0]; return response({ ...removed, revision: 2 }); }
      if (url.includes('/classes/class1/students')) { reads += 1; return response({ items: members, total: members.length, offset: 0, limit: 50 }); }
      if (url.includes('/classes?')) return response({ items: ['class1', 'class2'].map((id, i) => ({ id, name: i ? '转入班' : '独立班', code: id, schoolYear: '2026', gradeId: 'grade', status: 'active', revision: 1, studentCount: 2 })), total: 2 });
      if (url.includes('textbook-taxonomy')) return response({ grades: [], subjects: [], stages: [], editions: [] });
      return response({ items: [], total: 0, offset: 0, limit: 100 });
    }));
    render(<StrictMode><AssessmentsWorkspace/></StrictMode>);
    fireEvent.click(await screen.findByTestId('assessments-class-class1')); fireEvent.click(screen.getByTestId('assessments-tab-assessment'));
    await screen.findByRole('checkbox', { name: '参测 保留甲' });
    fireEvent.click(screen.getByRole('checkbox', { name: '参测 保留甲' }));
    fireEvent.change(screen.getByLabelText('保留甲 出勤'), { target: { value: 'exempt' } });
    fireEvent.change(screen.getByLabelText('保留甲 人次序号'), { target: { value: '3' } });
    fireEvent.click(screen.getByTestId('assessments-tab-roster'));
    fireEvent.change(screen.getByLabelText('学生姓名'), { target: { value: '新增丙' } });
    fireEvent.change(screen.getByLabelText('学生学号'), { target: { value: '003' } });
    fireEvent.submit(screen.getByRole('form', { name: '添加学生' })); await screen.findByTestId('assessments-student-s3');
    fireEvent.click(screen.getByTestId('assessments-tab-assessment')); await screen.findByRole('checkbox', { name: '参测 新增丙' });
    expect(screen.getByRole('checkbox', { name: '参测 保留甲' })).not.toBeChecked();
    expect(screen.getByLabelText('保留甲 出勤')).toHaveValue('exempt'); expect(screen.getByLabelText('保留甲 人次序号')).toHaveValue(3);
    fireEvent.click(screen.getByTestId('assessments-tab-roster'));
    fireEvent.change(screen.getByLabelText('名单文件'), { target: { files: [new File(['姓名,学号\n导入丁,004'], '独立名单.csv', { type: 'text/csv' })] } });
    fireEvent.click(screen.getByRole('button', { name: '上传名单', exact: true })); await screen.findByLabelText('第 1 行处理');
    fireEvent.change(screen.getByLabelText('第 1 行处理'), { target: { value: 'create' } });
    fireEvent.click(screen.getByRole('button', { name: '确认名单' })); await screen.findByTestId('roster-import-result');
    fireEvent.click(screen.getByTestId('assessments-tab-assessment')); await screen.findByRole('checkbox', { name: '参测 导入丁' });
    expect(screen.getByRole('checkbox', { name: '参测 保留甲' })).not.toBeChecked(); expect(screen.getByLabelText('保留甲 人次序号')).toHaveValue(3);
    fireEvent.click(screen.getByTestId('assessments-tab-roster'));
    fireEvent.change(screen.getByLabelText('转班学生'), { target: { value: 's2' } });
    fireEvent.change(screen.getByLabelText('转入班级'), { target: { value: 'class2' } });
    fireEvent.click(screen.getByRole('button', { name: '确认转班' })); await screen.findByTestId('roster-transfer-result');
    fireEvent.click(screen.getByTestId('assessments-tab-assessment'));
    await waitFor(() => expect(screen.queryByRole('checkbox', { name: '参测 转走乙' })).toBeNull());
    expect(screen.getByText(/转走乙已不在本班当前名单/)).toBeVisible();
    expect(screen.getByRole('checkbox', { name: '参测 保留甲' })).not.toBeChecked();
    expect(screen.getByLabelText('保留甲 出勤')).toHaveValue('exempt'); expect(screen.getByLabelText('保留甲 人次序号')).toHaveValue(3);
    receipts.push({ case: 'R03-workspace', writes, reads, finalRoster: members.map(x => x.name) });
  });
});

const ns = 'http://schemas.openxmlformats.org/officeDocument/2006/math';
const expression = (text: string) => `<m:e><m:r><m:t>${text}</m:t></m:r></m:e>`;
describe('Independent R08 OMML complete delimiter projection', () => {
  it.each(['|', ',', ''])('all expressions, empty middle, complex fraction, separator=%s', async (separator) => {
    const xml = `<m:oMath xmlns:m="${ns}"><m:d><m:dPr><m:begChr m:val="["/><m:sepChr m:val="${separator}"/><m:endChr m:val="]"/></m:dPr>${expression('x')}<m:e/>` +
      `<m:e><m:f><m:num><m:r><m:t>y</m:t></m:r></m:num><m:den><m:r><m:t>2</m:t></m:r></m:den></m:f></m:e></m:d></m:oMath>`;
    const ui = render(<RichBlocks blocks={[{ id: 'd', kind: 'formula', ommlXml: xml }]}/>);
    await waitFor(() => expect(ui.container.querySelector('math')).not.toBeNull());
    expect(ui.container.querySelector('math')?.textContent).toBe(`[x${separator}${separator}y2]`);
    expect(ui.container.querySelectorAll('mfrac')).toHaveLength(1); expect(ui.queryByRole('status')).toBeNull();
    expect(ui.container.querySelector('pre')).toHaveTextContent(xml);
    receipts.push({ case: 'R08-projection', separator, mathText: ui.container.querySelector('math')?.textContent });
  });
  it.each([['default', expression('a') + expression('b'), '(a|b)'], ['empty', '<m:e/>', '()']])('%s delimiters are complete', async (_name, children, expected) => {
    const xml = `<m:oMath xmlns:m="${ns}"><m:d>${children}</m:d></m:oMath>`;
    const ui = render(<RichBlocks blocks={[{ id: 'd', kind: 'formula', ommlXml: xml }]}/>);
    await waitFor(() => expect(ui.container.querySelector('math')?.textContent).toBe(expected));
  });
  it.each(['<m:unknown/>', '<m:e><m:unknown/></m:e>', '<evil:script xmlns:evil="https://bad.test">secret</evil:script>'])('unsupported structure is explicit and preserves safe source %s', async (unsupported) => {
    const xml = `<m:oMath xmlns:m="${ns}"><m:d>${expression('first')}${unsupported}${expression('last')}</m:d></m:oMath>`;
    const ui = render(<RichBlocks blocks={[{ id: 'd', kind: 'formula', ommlXml: xml }]}/>);
    await waitFor(() => expect(ui.getByRole('status')).toBeInTheDocument());
    expect(ui.container.querySelector('math')).toBeNull(); expect(ui.container.querySelector('pre')).toHaveTextContent(xml);
    expect(ui.container.querySelector('script')).toBeNull();
  });
});
