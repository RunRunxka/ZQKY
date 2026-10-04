import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ScoreImportView } from '@/contracts/scores';
import { ScorePanel } from '@/features/assessments/ScorePanel';
import { ScoreImportReview } from '@/features/assessments/ScoreImportReview';
import { AssessmentsWorkspace } from '@/features/assessments/AssessmentsWorkspace';

function view(revision = 1): ScoreImportView {
  return {
    importId: 'probe-import', assessmentId: 'probe-assessment', assessmentTitle: '隔离施测',
    state: 'reviewing', revision, previewVersion: revision,
    fileAsset: { assetId: 'probe-asset', kind: 'score_sheet', blobKey: 'blobs/probe',
      sha256: 'probe', mediaType: 'text/csv', byteSize: 10, originalName: 'probe.csv' },
    mapping: { workSheet: '成绩', headerRow: 1, studentNoColumn: 'A', nameColumn: 'B',
      itemColumns: [{ itemId: 'probe-item', column: 'C' }], attendanceColumn: 'D', totalColumn: 'E' },
    rowCount: 1, resolvedRowCount: 1, missingCellCount: 0,
    requiredAcknowledgements: { absences: [], missing: null },
    createdAt: '2026-10-02T00:00:00Z', updatedAt: '2026-10-02T00:00:00Z',
  };
}
function response(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}
const sourceRows = { items: [{ rowNo: 2, participantId: 'probe-participant', cells: [
  { row: 2, column: 'C', text: '2', effectiveStatus: 'recorded', scoreUnits: 200 },
] }], total: 1, offset: 0, limit: 50 };

beforeEach(() => {
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); } },
    close: { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); } },
  });
});
afterEach(() => {
  cleanup(); vi.unstubAllGlobals();
  Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
  Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
});

describe('B3-FIX r7 independent score edit probes', () => {
  it('F-REVIEW-01 rejects confirmation after a new unsaved edit in acknowledgement stage', async () => {
    const confirms: unknown[] = [];
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith('/confirm')) {
        confirms.push(JSON.parse(String(init?.body)));
        return response(200, { importId: 'probe-import', state: 'confirmed', revisionId: 'probe-revision',
          assessmentRevision: 2, activeScoreRevisionId: 'probe-revision', replayed: false });
      }
      return response(200, sourceRows);
    }));
    render(<StrictMode><ScoreImportReview view={view()} reloadToken={0}
      leaves={[{ itemId: 'probe-item', questionNo: 'Q1' }]}
      participants={[{ participantId: 'probe-participant', classId: 'probe-class', name: '探针甲', attendance: 'present' }]}
      assessmentRevision={1} onReload={() => {}} onReloadAssessment={() => {}}
      onChanged={() => {}} onOpenHistory={() => {}} /></StrictMode>);
    await screen.findByLabelText('第 2 行 列 C 校正');
    fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    expect(screen.getByTestId('score-open-confirm')).toBeEnabled();
    fireEvent.change(screen.getByLabelText('第 2 行 列 C 校正'), { target: { value: '1' } });
    expect(screen.getByTestId('score-cell-status-2-C')).toHaveTextContent('1');
    expect(screen.getByText('有未保存的校对')).toBeInTheDocument();
    // Actual user sequence: acknowledgement stage remains present, and both confirms are usable.
    fireEvent.click(screen.getByTestId('score-open-confirm'));
    fireEvent.click(screen.getByTestId('score-confirm-submit'));
    await screen.findByTestId('score-confirm-result');
    console.info('F-REVIEW-01 receipt', JSON.stringify({ visibleCorrection: '1', persistedSource: '2', confirms }));
    expect(confirms, 'Unsaved edits must prevent a confirmation of the older persisted matrix').toHaveLength(0);
  });

  it('F-REVIEW-02 preserves edits made after the mapping save request starts', async () => {
    let finish!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => { finish = resolve; });
    const patches: unknown[] = [];
    let latest = view();
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'PATCH') {
        patches.push(JSON.parse(String(init.body)));
        return pending;
      }
      if (url.includes('/score-imports?')) return response(200, { items: [latest], total: 1 });
      if (url.includes('/rows')) return response(200, sourceRows);
      if (url.includes('/score-imports/')) return response(200, latest);
      if (url.includes('/score-revisions')) return response(200, { items: [], total: 0 });
      if (url.includes('/content')) return response(200, { items: [{ itemId: 'probe-item',
        parentItemId: null, questionNo: 'Q1', ordinal: 1, isScored: true, maxScoreUnits: 200 }], blocks: [] });
      return response(200, { assessment: { assessmentId: 'probe-assessment', paperId: 'probe-paper',
        paperRevisionId: 'probe-paper-revision', title: '隔离施测', participantCount: 1, revision: 1 },
      participants: [{ participantId: 'probe-participant', classId: 'probe-class',
        nameSnapshot: '探针甲', attendance: 'present' }] });
    }));
    render(<StrictMode><ScorePanel assessmentId="probe-assessment" onOpenHistory={() => {}}
      refreshToken={0} onChanged={() => {}} /></StrictMode>);
    await waitFor(() => expect(screen.getByLabelText('总分列')).toHaveValue('E'));
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'F' } });
    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(screen.getByLabelText('总分列')).toBeEnabled();
    fireEvent.change(screen.getByLabelText('总分列'), { target: { value: 'G' } });
    expect(screen.getByLabelText('总分列')).toHaveValue('G');
    latest = view(2);
    latest.mapping.totalColumn = 'F';
    await act(async () => finish(response(200, latest)));
    await screen.findByTestId('assessments-mapping-notice');
    console.info('F-REVIEW-02 receipt', JSON.stringify({ patch: patches[0], expectedUnsaved: 'G', actualInput: (screen.getByLabelText('总分列') as HTMLInputElement).value }));
    expect(screen.getByLabelText('总分列'), 'A late success must preserve edits made after its request snapshot').toHaveValue('G');
  });

  it('F-REVIEW-03 refreshes an already visited assessment roster after adding a class member', async () => {
    const members = [{ id: 'probe-student-one', name: '原名单甲', studentNo: '001', revision: 1, memberships: [] }];
    let memberReads = 0;
    const posts: unknown[] = [];
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/students') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body));
        posts.push(body);
        const next = { id: 'probe-student-two', name: body.name, studentNo: body.studentNo, revision: 1, memberships: [] };
        members.push(next);
        return response(201, next);
      }
      if (url.includes('/classes/probe-class/students')) {
        memberReads += 1;
        return response(200, { items: structuredClone(members), total: members.length, offset: 0, limit: 50 });
      }
      if (url.includes('/classes?')) return response(200, { items: [{ id: 'probe-class',
        code: 'probe', name: '探针班', schoolYear: '2026', gradeId: 'grade-1', status: 'active',
        revision: 1, studentCount: members.length }], total: 1 });
      if (url.includes('textbook-taxonomy')) return response(200, { grades: [], subjects: [], stages: [], editions: [] });
      return response(200, { items: [], total: 0, offset: 0, limit: 100 });
    }));
    render(<AssessmentsWorkspace />);
    fireEvent.click(await screen.findByTestId('assessments-class-probe-class'));
    fireEvent.click(screen.getByTestId('assessments-tab-assessment'));
    await screen.findByRole('checkbox', { name: '参测 原名单甲' });
    fireEvent.click(screen.getByTestId('assessments-tab-roster'));
    fireEvent.change(screen.getByLabelText('学生姓名'), { target: { value: '新名单乙' } });
    fireEvent.change(screen.getByLabelText('学生学号'), { target: { value: '002' } });
    fireEvent.submit(screen.getByRole('form', { name: '添加学生' }));
    await screen.findByTestId('assessments-student-probe-student-two');
    fireEvent.click(screen.getByTestId('assessments-tab-assessment'));
    console.info('F-REVIEW-03 receipt', JSON.stringify({ posts, memberReads,
      currentRosterNames: members.map((member) => member.name),
      assessmentChoices: screen.queryAllByRole('checkbox').map((checkbox) => checkbox.getAttribute('aria-label')) }));
    expect(screen.queryByRole('checkbox', { name: '参测 新名单乙' }),
      'An already visited assessment panel must observe newly added class members').toBeInTheDocument();
  });
});
