import { StrictMode } from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ScoreImportView } from '@/contracts/scores';
import { ScoreImportReview } from '@/features/assessments/ScoreImportReview';
import { ScorePanel } from '@/features/assessments/ScorePanel';
import { AssessmentsPanel } from '@/features/assessments/AssessmentsPanel';

function response(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => structuredClone(body) } as Response;
}
function scoreView(revision = 1): ScoreImportView {
  return { importId: 'i1', assessmentId: 'a1', assessmentTitle: '复查', state: 'reviewing',
    revision, previewVersion: revision,
    fileAsset: { assetId: 'asset', kind: 'score_sheet', blobKey: 'blobs/test', sha256: 'test',
      mediaType: 'text/csv', byteSize: 30, originalName: 'review.csv' },
    mapping: { workSheet: 'CSV', headerRow: 1, studentNoColumn: 'A', nameColumn: 'B',
      itemColumns: [{ itemId: 'q1', column: 'C' }], totalColumn: 'E', attendanceColumn: 'D' },
    rowCount: 1, resolvedRowCount: 1, missingCellCount: 0,
    requiredAcknowledgements: { absences: [], missing: null }, createdAt: '', updatedAt: '' };
}
const rows = { items: [{ rowNo: 2, participantId: 'p1', cells: [
  { row: 2, column: 'C', text: '2', effectiveStatus: 'recorded', scoreUnits: 200 },
] }], total: 1, offset: 0, limit: 50 };
const reviewProps = { reloadToken: 0, leaves: [{ itemId: 'q1', questionNo: 'Q1' }],
  participants: [{ participantId: 'p1', classId: 'c1', name: '甲', attendance: 'present' as const }],
  assessmentRevision: 1, onReload: () => {}, onReloadAssessment: () => {},
  onChanged: () => {}, onOpenHistory: () => {} };
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

it('unknown confirm replays original body after authoritative view is already confirmed', async () => {
  const posts: unknown[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input).endsWith('/confirm')) {
      posts.push(JSON.parse(String(init?.body)));
      if (posts.length === 1) throw new TypeError('response lost after commit');
      return response({ importId: 'i1', revisionId: 'sr1', state: 'confirmed',
        activeScoreRevisionId: 'sr1', assessmentRevision: 2, replayed: true });
    }
    return response(rows);
  }));
  const ui = render(<StrictMode><ScoreImportReview view={scoreView()} {...reviewProps}/></StrictMode>);
  await screen.findByLabelText('第 2 行 列 C 校正');
  fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
  fireEvent.click(screen.getByTestId('score-open-confirm'));
  fireEvent.click(screen.getByTestId('score-confirm-submit'));
  await screen.findByTestId('score-confirm-unknown');
  const confirmed = { ...scoreView(2), state: 'confirmed' as const };
  ui.rerender(<StrictMode><ScoreImportReview view={confirmed} {...reviewProps}
    assessmentRevision={2} mappingPending /></StrictMode>);
  await screen.findByTestId('score-import-confirmed');
  expect(screen.getByTestId('score-open-confirm')).toBeEnabled();
  fireEvent.click(screen.getByTestId('score-open-confirm'));
  fireEvent.click(screen.getByTestId('score-confirm-submit'));
  await screen.findByTestId('score-confirm-result');
  expect(posts).toHaveLength(2);
  expect(posts[1]).toEqual(posts[0]);
  expect(posts[0]).toMatchObject({ expectedImportRevision: 1, previewVersion: 1,
    expectedAssessmentRevision: 1, submissionId: expect.any(String) });
});

it('mapping save followed by failing authoritative GET keeps saved mapping and blocks stale confirmation', async () => {
  let failView = false;
  const patched = scoreView(2); patched.mapping!.totalColumn = 'F';
  const posts: unknown[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === 'PATCH') { failView = true; return response(patched); }
    if (init?.method === 'POST') { posts.push(JSON.parse(String(init.body))); return response({}); }
    if (url.includes('/score-imports?')) return response({ items: [scoreView()], total: 1 });
    if (url.includes('/rows')) return response(rows);
    if (url.includes('/score-imports/')) return failView
      ? response({ code: 'FETCH_FAILED', message: 'read failed' }, 500) : response(scoreView());
    if (url.includes('/score-revisions')) return response({ items: [], total: 0 });
    if (url.includes('/content')) return response({ items: [{ itemId: 'q1', parentItemId: null,
      questionNo: 'Q1', ordinal: 1, isScored: true, maxScoreUnits: 200 }], blocks: [] });
    return response({ assessment: { assessmentId: 'a1', paperId: 'paper', paperRevisionId: 'pr1',
      title: '复查', participantCount: 1, revision: 1 }, participants: [] });
  }));
  render(<StrictMode><ScorePanel assessmentId="a1" onOpenHistory={() => {}}
    refreshToken={0} onChanged={() => {}} /></StrictMode>);
  await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
  fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'F' } });
  fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
  await screen.findByTestId('assessments-mapping-waiting-preview');
  expect(screen.getByLabelText('总分列')).toHaveValue('F');
  expect(screen.getByTestId('score-goto-acknowledge')).toBeDisabled();
  fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
  expect(posts).toHaveLength(0);
  expect(screen.queryByTestId('score-open-confirm')).toBeNull();
});

it('roster refresh failure preserves attendance and attempt drafts while blocking ordinary creation', async () => {
  let failRoster = false;
  const posts: unknown[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'POST') { posts.push(JSON.parse(String(init.body))); return response({}); }
    if (String(input).endsWith('/students')) return failRoster
      ? response({ code: 'ROSTER_UNAVAILABLE', message: 'roster failed' }, 500)
      : response({ items: [{ id: 's1', name: '甲', studentNo: '001' }], total: 1 });
    return response({ items: [], total: 0 });
  }));
  render(<StrictMode><AssessmentsPanel classId="c1" className="班级" selectedPaper={{
    paperId: 'paper', paperRevisionId: 'pr1', title: '复查', scoredLeafCount: 1, totalScoreUnits: 200,
  }} selectedAssessmentId={null} onSelectAssessment={() => {}} onOpenScore={() => {}}
    refreshToken={0} onChanged={() => {}} /></StrictMode>);
  await screen.findByLabelText('参测 甲');
  fireEvent.change(screen.getByLabelText('施测标题'), { target: { value: '测验' } });
  fireEvent.change(screen.getByLabelText('甲 出勤'), { target: { value: 'exempt' } });
  fireEvent.change(screen.getByLabelText('甲 人次序号'), { target: { value: '3' } });
  failRoster = true;
  fireEvent.click(screen.getByRole('button', { name: '刷新参测名单' }));
  await screen.findByTestId('assessments-roster-error');
  expect(screen.getByLabelText('甲 出勤')).toHaveValue('exempt');
  expect(screen.getByLabelText('甲 人次序号')).toHaveValue(3);
  expect(screen.getByRole('button', { name: '创建施测', exact: true })).toBeDisabled();
  fireEvent.submit(screen.getByRole('form', { name: '新建施测' }));
  expect(posts).toHaveLength(0);
  expect(screen.getByLabelText('施测标题')).toHaveValue('测验');
});
