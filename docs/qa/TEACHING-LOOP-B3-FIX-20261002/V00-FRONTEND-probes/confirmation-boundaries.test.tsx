import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AssessmentsPanel } from '@/features/assessments/AssessmentsPanel';
import { ScoreImportReview } from '@/features/assessments/ScoreImportReview';
import { HistoryPanel } from '@/features/assessments/HistoryPanel';
import { ParticipantAttendanceEditor } from '@/features/assessments/ParticipantAttendanceEditor';
import { ParticipantAddPanel } from '@/features/assessments/ParticipantAddPanel';
import type { ScoreImportView } from '@/contracts/scores';
import type { AssessmentParticipantView } from '@/contracts/assessments';

function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }); }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }
const now = '2026-10-02T00:00:00Z';
const student = { id: 'independent-student', studentNo: '00129', name: '独立甲', status: 'active', revision: 3, memberships: [], createdAt: now };
const assessment = { assessmentId: 'independent-assessment', paperRevisionId: 'fixed-paper-17', paperId: 'paper-3', paperTitle: '固定卷标题', subjectId: 'math', title: '独立施测', assessmentType: 'exam', heldOn: '2026-10-02', activeScoreRevisionId: 'score-v1', state: 'open', revision: 7, classIds: ['class-acceptance'], participantCount: 1, createdAt: now };
const participant: AssessmentParticipantView = { participantId: 'independent-participant', studentId: student.id, studentNoSnapshot: student.studentNo, nameSnapshot: student.name, classId: 'class-acceptance', attemptNo: 2, attendance: 'present', classConfirmed: false, classConfirmationNote: null, classConfirmationAt: null };
const scoreRevision = { revisionId: 'score-v1', assessmentId: assessment.assessmentId, paperRevisionId: assessment.paperRevisionId, version: 1, state: 'confirmed', sourceImportId: 'import-acceptance', baseRevisionId: null,
  participantSnapshot: [{ participantId: participant.participantId, studentId: student.id, studentNo: student.studentNo, name: student.name, classId: participant.classId, attemptNo: 2, attendance: 'present' }], itemSnapshot: [{ itemId: 'leaf-acceptance', itemPath: '1(2)', maxScoreUnits: 200 }], confirmedAt: now, createdAt: now };
function importView(ack: ScoreImportView['requiredAcknowledgements'], overrides: Partial<ScoreImportView> = {}): ScoreImportView {
  return { importId: 'import-acceptance', assessmentId: assessment.assessmentId, assessmentTitle: assessment.title, state: 'reviewing', revision: 4, previewVersion: 9,
    fileAsset: { assetId: 'asset-a', originalName: '独立.csv', sha256: '0'.repeat(64), mimeType: 'text/csv', sizeBytes: 70, ownerType: 'score_import', ownerId: 'import-acceptance', relativePath: '' },
    mapping: { workSheet: 'CSV', headerRow: 1, studentNoColumn: 'A', nameColumn: 'B', itemColumns: [{ itemId: 'leaf-acceptance', column: 'C' }] },
    baseScoreRevisionId: null, rowCount: 1, resolvedRowCount: 1, missingCellCount: 0, requiredAcknowledgements: ack, issues: [], warnings: [], createdAt: now, updatedAt: now, ...overrides } as ScoreImportView;
}
function scoreProps(view: ScoreImportView) { return { view, reloadToken: 0, leaves: [{ itemId: 'leaf-acceptance', questionNo: '1(2)' }], participants: [{ participantId: participant.participantId, classId: participant.classId, name: student.name, attendance: 'present' as const }], assessmentRevision: 7, onReload: vi.fn(), onReloadAssessment: vi.fn(), onChanged: vi.fn(), onOpenHistory: vi.fn() }; }
function scoreRows(status: 'recorded' | 'missing' | 'absent' | 'exempt') {
  return { items: [{ rowNo: 11, participantId: participant.participantId, participantName: student.name, candidates: [], cells: [{ row: 11, column: 'C', text: '', originalText: '', correctedText: null, effectiveStatus: status, scoreUnits: status === 'recorded' ? 0 : null }], issues: [] }], total: 1, offset: 0, limit: 50 };
}
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.removeAttribute('open'); } });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Independent authoritative score acknowledgements', () => {
  for (const status of ['recorded', 'missing', 'absent', 'exempt'] as const) {
    it(`${status} effective status supersedes raw blank; request exactly follows server acknowledgement`, async () => {
      const ack = { absences: status === 'absent' ? [{ classId: participant.classId, participantIds: [participant.participantId] }] : [], missing: status === 'missing' ? { participantIds: [participant.participantId], cellCount: 1 } : null };
      const bodies: unknown[] = [];
      vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).includes('/confirm')) { bodies.push(JSON.parse(String(init?.body))); return Promise.resolve(response({ importId: 'import-acceptance', state: 'confirmed', revisionId: 'score-v2', assessmentRevision: 8, activeScoreRevisionId: 'score-v2', replayed: false })); }
        return Promise.resolve(response(scoreRows(status)));
      }));
      const props = scoreProps(importView(ack));
      render(<StrictMode><ScoreImportReview {...props} /></StrictMode>);
      await screen.findByTestId('score-row-11');
      expect(screen.getByTestId('score-cell-status-11-C')).toHaveTextContent(status === 'recorded' ? '0' : status === 'missing' ? '空白' : status === 'absent' ? '缺考' : '免考');
      fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
      if (status === 'absent') fireEvent.click(screen.getByRole('checkbox', { name: /承认.*缺考/ }));
      if (status === 'missing') fireEvent.click(screen.getByRole('checkbox', { name: /承认空白/ }));
      if (status !== 'missing') expect(screen.queryByRole('checkbox', { name: /承认空白/ })).not.toBeInTheDocument();
      fireEvent.click(screen.getByTestId('score-open-confirm'));
      fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '确认入库' }));
      await screen.findByTestId('score-confirm-result');
      expect(bodies).toHaveLength(1);
      expect(bodies[0]).toMatchObject({ expectedImportRevision: 4, expectedAssessmentRevision: 7, previewVersion: 9, baseScoreRevisionId: null, absences: ack.absences, missing: ack.missing });
      expect(props.onChanged).toHaveBeenCalledTimes(1);
    });
  }
  it('missing authority field blocks confirmation even when all displayed cells are recorded', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(response(scoreRows('recorded')))));
    render(<ScoreImportReview {...scoreProps(importView(undefined))} />);
    await screen.findByTestId('score-row-11'); fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    expect(screen.getByTestId('score-ack-unavailable')).toBeInTheDocument();
    expect(screen.getByTestId('score-open-confirm')).toBeDisabled();
  });
  it('UNKNOWN score confirm remains original request after refreshed revision/ack state', async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes('/confirm')) { bodies.push(JSON.parse(String(init?.body))); return bodies.length === 1 ? Promise.reject(new TypeError('post-commit connection dropped')) : Promise.resolve(response({ importId: 'import-acceptance', state: 'confirmed', revisionId: 'score-v2', assessmentRevision: 8, activeScoreRevisionId: 'score-v2', replayed: true })); }
      return Promise.resolve(response(scoreRows('recorded')));
    }));
    const props = scoreProps(importView({ absences: [], missing: null }));
    const ui = render(<ScoreImportReview {...props} />);
    await screen.findByTestId('score-row-11'); fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
    fireEvent.click(screen.getByTestId('score-open-confirm'));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '确认入库' }));
    await screen.findByTestId('score-confirm-unknown');
    // Explicit comparison read may advance versions while the original commit outcome is still unknown.
    ui.rerender(<ScoreImportReview {...props} view={importView({ absences: [], missing: null }, { revision: 5, previewVersion: 10 })} assessmentRevision={8} />);
    fireEvent.click(screen.getByTestId('score-open-confirm'));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '确认入库' }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toEqual(bodies[0]);
  });
});

describe('Independent assessment create outcomes and unknown receipt', () => {
  function props() { return { selectedPaper: { paperId: assessment.paperId, paperRevisionId: assessment.paperRevisionId, title: '独立卷', totalScoreUnits: 200, scoredLeafCount: 1 }, classId: participant.classId, className: '独立班', selectedAssessmentId: null, onSelectAssessment: vi.fn(), onOpenScore: vi.fn(), refreshToken: 0, onChanged: vi.fn() }; }
  function setupCreate(write: (init?: RequestInit) => Promise<Response>) {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') return write(init);
      if (/\/assessments\/new-current(?:\?|$)/.test(String(input))) return Promise.resolve(response({ assessment: { ...assessment, assessmentId: 'new-current' }, participants: [participant] }));
      return Promise.resolve(response(String(input).includes('/students') ? { items: [student], total: 1, offset: 0, limit: 50 } : { items: [], total: 0, offset: 0, limit: 100 }));
    }));
  }
  for (const status of [200, 409, 422]) {
    for (const invalidate of ['unmount', 'same-panel-selection-switch'] as const) {
      it(`create ${status} after ${invalidate} cannot select old assessment or signal a parent change`, async () => {
        const gate = deferred<Response>(); setupCreate(() => gate.promise);
        const p = props(); const ui = render(<StrictMode><AssessmentsPanel {...p} /></StrictMode>);
        await screen.findByTestId(`assessments-participant-${student.id}`);
        fireEvent.change(screen.getByLabelText('施测标题'), { target: { value: 'late-owned' } }); fireEvent.click(screen.getByRole('button', { name: '创建施测' }));
        if (invalidate === 'unmount') ui.unmount(); else ui.rerender(<StrictMode><AssessmentsPanel {...p} selectedAssessmentId="new-current" /></StrictMode>);
        await act(async () => gate.resolve(status === 200 ? response({ assessment, participants: [participant], replayed: false }) : response({ code: status === 409 ? 'REVISION_CONFLICT' : 'PARTICIPANT_CLASS_UNCONFIRMED', message: 'controlled late error', details: { currentRevision: 11, issues: [{ row: 0, field: 'classId', code: 'CLASS', message: '人工确认' }] } }, status)));
        expect(p.onSelectAssessment).not.toHaveBeenCalled(); expect(p.onChanged).not.toHaveBeenCalled();
      });
    }
  }
  it('UNKNOWN assessment create cannot be silently replaced by edited title and a new submissionId', async () => {
    const bodies: Record<string, unknown>[] = [];
    setupCreate((init) => { bodies.push(JSON.parse(String(init?.body))); return bodies.length === 1 ? Promise.reject(new TypeError('commit receipt lost')) : Promise.resolve(response({ assessment, participants: [participant], replayed: true })); });
    const p = props(); render(<AssessmentsPanel {...p} />);
    await screen.findByTestId(`assessments-participant-${student.id}`);
    fireEvent.change(screen.getByLabelText('施测标题'), { target: { value: 'original-owned' } }); fireEvent.click(screen.getByRole('button', { name: '创建施测' }));
    await screen.findByText(/确认结果未知/);
    fireEvent.change(screen.getByLabelText('施测标题'), { target: { value: 'later-edited-title' } }); fireEvent.click(screen.getByRole('button', { name: '创建施测' }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toEqual(bodies[0]);
  });
});

describe('Independent history correction unknown receipt and old immutable input', () => {
  it('UNKNOWN correction replays original reason, CAS/base and submissionId despite subsequent edit', async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'POST') { bodies.push(JSON.parse(String(init.body))); return bodies.length === 1 ? Promise.reject(new TypeError('correction committed but receipt lost')) : Promise.resolve(response({ revisionId: 'score-v2', baseRevisionId: 'score-v1', version: 2, assessmentRevision: 8, activeScoreRevisionId: 'score-v2', replayed: true })); }
      if (url.includes('/matrix')) return Promise.resolve(response({ revision: scoreRevision, items: scoreRevision.itemSnapshot, rows: [], total: 0, offset: 0, limit: 50, missingCellCount: 0 }));
      if (url.includes('/assessments/') && url.includes('/score-revisions')) return Promise.resolve(response({ items: [scoreRevision], total: 1 }));
      if (url.includes('/score-revisions/')) return Promise.resolve(response(scoreRevision));
      return Promise.resolve(response({ assessment, participants: [participant] }));
    }));
    render(<HistoryPanel assessmentId={assessment.assessmentId} refreshToken={0} onChanged={vi.fn()} />);
    await screen.findByRole('option', { name: /独立甲/ });
    fireEvent.change(screen.getByLabelText('修正人次'), { target: { value: participant.participantId } });
    fireEvent.change(screen.getByLabelText('修正计分叶'), { target: { value: 'leaf-acceptance' } });
    fireEvent.change(screen.getByLabelText('修正分数'), { target: { value: '1.25' } }); fireEvent.click(screen.getByRole('button', { name: /加入修正列表/ }));
    fireEvent.change(screen.getByLabelText('修正理由'), { target: { value: 'original-reason' } }); fireEvent.click(screen.getByTestId('assessments-correct-submit'));
    await screen.findByTestId('assessments-correct-unknown');
    fireEvent.change(screen.getByLabelText('修正理由'), { target: { value: 'changed-after-unknown' } }); fireEvent.click(screen.getByTestId('assessments-correct-submit'));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toEqual(bodies[0]);
  });
});

describe('Independent attendance frozen replay and unmount guard', () => {
  it('unknown locks attendance/reason and replay uses exact body; normal current receipt notifies once', async () => {
    const bodies: unknown[] = [];
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      bodies.push(JSON.parse(String(init?.body)));
      return bodies.length === 1 ? Promise.reject(new TypeError('receipt lost')) : Promise.resolve(response({ assessment, participants: [participant], replayed: true }));
    }));
    const changed = vi.fn(); render(<StrictMode><ParticipantAttendanceEditor assessmentId={assessment.assessmentId} participant={participant} revision={7} onChanged={changed} onRefresh={vi.fn()} /></StrictMode>);
    fireEvent.change(screen.getByLabelText('独立甲 人次 2 校正出勤'), { target: { value: 'absent' } });
    fireEvent.change(screen.getByLabelText('独立甲 人次 2 出勤校正理由'), { target: { value: 'explicit-absence' } }); fireEvent.click(screen.getByRole('button', { name: '保存出勤校正' }));
    await screen.findByRole('button', { name: '重试原出勤校正' });
    expect(screen.getByLabelText('独立甲 人次 2 校正出勤')).toBeDisabled(); expect(screen.getByLabelText('独立甲 人次 2 出勤校正理由')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重试原出勤校正' }));
    await waitFor(() => expect(changed).toHaveBeenCalledTimes(1)); expect(bodies).toHaveLength(2); expect(bodies[1]).toEqual(bodies[0]);
  });
  for (const status of [200, 409]) it(`attendance late ${status} after unmount causes zero parent callback`, async () => {
    const gate = deferred<Response>(); vi.stubGlobal('fetch', vi.fn(() => gate.promise));
    const changed = vi.fn(); const ui = render(<ParticipantAttendanceEditor assessmentId={assessment.assessmentId} participant={participant} revision={7} onChanged={changed} onRefresh={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('独立甲 人次 2 出勤校正理由'), { target: { value: 'late-owned' } }); fireEvent.click(screen.getByRole('button', { name: '保存出勤校正' })); ui.unmount();
    await act(async () => gate.resolve(response(status === 200 ? { assessment, participants: [participant], replayed: false } : { code: 'REVISION_CONFLICT', message: 'late conflict' }, status)));
    expect(changed).not.toHaveBeenCalled();
  });
});

describe('Independent re-examination usability', () => {
  it('ready existing student with attempt2 remains selectable; selection defaults to attempt3 and POST sends that person, not a name', async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') { bodies.push(JSON.parse(String(init.body))); return Promise.resolve(response({ assessment: { ...assessment, revision: 8 }, participants: [participant], replayed: false })); }
      return Promise.resolve(response({ items: [student], total: 1, offset: 0, limit: 50 }));
    }));
    const changed = vi.fn(); render(<ParticipantAddPanel detail={{ assessment: assessment as never, participants: [participant] }} onChanged={changed} onRefresh={vi.fn()} />);
    await waitFor(() => expect(screen.getByLabelText('补录学生')).toBeEnabled());
    expect(screen.getByRole('option', { name: /独立甲/ })).toBeEnabled();
    fireEvent.change(screen.getByLabelText('补录学生'), { target: { value: student.id } });
    expect(screen.getByLabelText('补录人次序号')).toHaveValue(3);
    fireEvent.click(screen.getByRole('button', { name: '新增参测人次' }));
    await waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
    expect(bodies[0]).toMatchObject({ expectedRevision: 7, participants: [{ studentId: student.id, classId: participant.classId, attemptNo: 3, attendance: 'present' }] });
    expect(JSON.stringify(bodies[0])).not.toContain(student.name);
  });
});
