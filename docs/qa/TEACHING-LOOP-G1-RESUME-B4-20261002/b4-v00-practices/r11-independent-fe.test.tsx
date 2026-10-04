// Independent R11 controlled component evidence only; no real API/browser claim.
// Keep real async resource and observed-job hooks, controlling API responses.
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LearningAnalysisWorkspace } from '@/features/learning-analysis/LearningAnalysisWorkspace';
import { b4Api } from '@/services/teaching-loop-b4-api';
import * as assessments from '@/services/assessments-api';
import * as jobs from '@/services/workflow-jobs-api';
import type { ObserveJobOptions } from '@/services/workflow-jobs-api';
import type { AnalysisReceipt, AnalysisRunView, FrozenParticipant } from '@/contracts/b4';
import type { AssessmentView } from '@/contracts/assessments';
import type { ScoreRevisionView } from '@/contracts/scores';
import type { JobView } from '@/contracts/teaching-loop';

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) =>
    <a href={href} {...props}>{children}</a>,
}));
vi.mock('@/services/assessments-api', () => ({
  listAssessments: vi.fn(), listScoreRevisions: vi.fn(), getScoreRevision: vi.fn(),
  getAssessment: vi.fn(), getPaperAsset: vi.fn(),
}));
vi.mock('@/services/workflow-jobs-api', () => ({
  observeJob: vi.fn(), retryJob: vi.fn(), cancelJob: vi.fn(),
  retryObservationWindow: (job: JobView) => ({ minAttempt: job.attempt, maxAttempt: job.attempt + 1 }),
}));

type Source = 'a' | 'b';
const timestamp = '2026-10-02T00:00:00Z';
const observations = new Map<string, { options: ObserveJobOptions; finish: (view: JobView | null) => void }>();
function page<T>(items: T[], limit = 20) { return { items, total: items.length, offset: 0, limit }; }
function participant(source: Source): FrozenParticipant {
  return { participantId: `r11-participant-${source}`, studentId: `r11-student-${source}`,
    studentNo: source === 'a' ? '00001' : '00002', name: `R11学生${source}`, classId: `r11-class-${source}`,
    className: null, classNameNote: '该成绩未记录班名', attemptNo: 1, attendance: 'present' };
}
function assessment(source: Source): AssessmentView {
  return { assessmentId: `r11-assessment-${source}`, paperRevisionId: `r11-paper-${source}`,
    paperId: `r11-paper-id-${source}`, paperTitle: `R11固定原卷${source}`, subjectId: 'math',
    title: `R11施测${source}`, assessmentType: 'exam', heldOn: '2026-10-02',
    activeScoreRevisionId: `r11-score-${source}`, state: 'open', revision: 0,
    classIds: [`r11-class-${source}`], participantCount: 1, createdAt: timestamp };
}
function score(source: Source): ScoreRevisionView {
  return { revisionId: `r11-score-${source}`, assessmentId: `r11-assessment-${source}`,
    paperRevisionId: `r11-paper-${source}`, version: 1, state: 'confirmed', sourceImportId: null,
    baseRevisionId: null, participantSnapshot: [participant(source)],
    itemSnapshot: [{ itemId: `r11-item-${source}`, itemPath: '1', maxScoreUnits: 100 }],
    confirmedAt: timestamp, createdAt: timestamp };
}
function report(source: Source, ready: boolean): AnalysisRunView {
  // These counts are literal backend fixture facts, never production aggregation.
  return { runId: `r11-run-${source}`, assessmentId: `r11-assessment-${source}`, subjectId: 'math',
    scoreRevisionId: `r11-score-${source}`, paperRevisionId: `r11-paper-${source}`,
    paperTitle: `R11固定原卷${source}`, inputHash: source.repeat(64), ruleCode: 'any_loss_v1',
    selectionSnapshot: { selectedParticipantIds: [`r11-participant-${source}`], uniqueStudentCount: 1,
      participantCount: 1, leafCount: 1, stateCounts: { recorded: 1, missing: 0, absent: 0, exempt: 0 } },
    participants: [participant(source)], knowledgePoints: [],
    job: { jobId: `r11-job-${source}`, domain: 'teaching', kind: 'analysis', attempt: ready ? 1 : 0,
      state: ready ? 'succeeded' : 'queued', result: null, error: null },
    reportReady: ready, createdAt: timestamp };
}
function receipt(source: Source): AnalysisReceipt {
  const run = report(source, false);
  return { runId: run.runId, inputHash: run.inputHash, scoreRevisionId: run.scoreRevisionId,
    paperRevisionId: run.paperRevisionId, job: run.job, replayed: false, reused: false };
}
function controlledAPI(initial: Source[] = []) {
  const created = new Set(initial);
  const ready = new Set<Source>();
  const list = vi.fn<typeof b4Api.listAnalysisRuns>(async (query) => {
    const current: Source = query?.assessmentId === 'r11-assessment-b' ? 'b' : 'a';
    return page(created.has(current) ? [report(current, ready.has(current))] : []);
  });
  const create = vi.fn<typeof b4Api.createAnalysisRun>(async (id) => {
    const current: Source = id === 'r11-assessment-b' ? 'b' : 'a';
    created.add(current);
    return receipt(current);
  });
  const get = vi.fn<typeof b4Api.getAnalysisRun>(async (id) => {
    const current: Source = id === 'r11-run-b' ? 'b' : 'a';
    return report(current, ready.has(current));
  });
  const api: typeof b4Api = { ...b4Api, listAnalysisRuns: list, createAnalysisRun: create,
    getAnalysisRun: get, listAnalysisClasses: vi.fn(async () => page([], 50)),
    listAnalysisStudents: vi.fn(async () => page([], 50)), listAnalysisEvidence: vi.fn(async () => page([], 50)),
    listAnalysisNotes: vi.fn(async () => page([], 50)) };
  return { api, ready, create, get, list };
}
async function emitSuccess(source: Source) {
  const observation = observations.get(`r11-job-${source}`);
  expect(observation).toBeDefined();
  const succeeded = report(source, true).job;
  await act(async () => {
    observation!.options.onUpdate?.(succeeded);
    observation!.finish(succeeded);
  });
}
function history() { return screen.getByRole('region', { name: '固定报告历史' }); }
function historyRun(source: Source) {
  return within(history()).getByRole('button', { name: new RegExp(`报告 r11-run-${source}`) });
}

beforeEach(() => {
  vi.resetAllMocks();
  observations.clear();
  vi.mocked(assessments.listAssessments).mockResolvedValue(page([assessment('a'), assessment('b')], 50));
  vi.mocked(assessments.listScoreRevisions).mockImplementation(async (id) => {
    const current: Source = id === 'r11-assessment-b' ? 'b' : 'a';
    return { items: [score(current)], total: 1 };
  });
  vi.mocked(assessments.getScoreRevision).mockImplementation(async (id) => score(id === 'r11-score-b' ? 'b' : 'a'));
  vi.mocked(assessments.getAssessment).mockImplementation(async (id) => ({
    assessment: assessment(id === 'r11-assessment-b' ? 'b' : 'a'), participants: [],
  }));
  vi.mocked(jobs.observeJob).mockImplementation((_domain, id, options = {}) =>
    new Promise<JobView | null>((finish) => { observations.set(id, { options, finish }); }));
});
afterEach(() => { cleanup(); observations.clear(); vi.restoreAllMocks(); });

describe('R11 independent report-history terminal synchronization', () => {
  it('a newly created queued run becomes ready in its fixed history when its observed job succeeds', async () => {
    const backend = controlledAPI();
    render(<LearningAnalysisWorkspace initialAssessmentId="r11-assessment-a"
      initialScoreRevisionId="r11-score-a" services={backend.api} />);
    fireEvent.click(await screen.findByLabelText('分析人次 R11学生a 1'));
    fireEvent.click(screen.getByRole('button', { name: '创建本次报告' }));
    await within(history()).findByRole('button', { name: /报告 r11-run-a/ });
    expect(historyRun('a')).toHaveTextContent('尚未准备');
    await waitFor(() => expect(observations.has('r11-job-a')).toBe(true));
    expect(backend.create).toHaveBeenCalledTimes(1);
    expect(backend.create.mock.calls[0]).toEqual(['r11-assessment-a', expect.objectContaining({
      scoreRevisionId: 'r11-score-a', selectedParticipantIds: ['r11-participant-a'], ruleCode: 'any_loss_v1',
    })]);
    backend.ready.add('a');
    await emitSuccess('a');
    await screen.findByRole('region', { name: '报告事实与证据' });
    expect(screen.getByText('任务成功')).toBeVisible();
    // This is the correct behavior assertion. Do not expect the known stale label.
    await waitFor(() => expect(historyRun('a')).toHaveTextContent('已准备'));
    expect(historyRun('a')).not.toHaveTextContent('尚未准备');
    expect(historyRun('a')).toHaveTextContent('成绩 r11-score-a');
  });

  it('late success of a replaced source/run cannot contaminate the new history, and manual refresh synchronizes its readiness', async () => {
    const backend = controlledAPI(['a', 'b']);
    render(<LearningAnalysisWorkspace initialAssessmentId="r11-assessment-a"
      initialScoreRevisionId="r11-score-a" initialRunId="r11-run-a" services={backend.api} />);
    await waitFor(() => expect(observations.has('r11-job-a')).toBe(true));
    expect(historyRun('a')).toHaveTextContent('尚未准备');
    const oldObservation = observations.get('r11-job-a')!;
    fireEvent.change(screen.getByLabelText('分析施测'), { target: { value: 'r11-assessment-b' } });
    await screen.findByRole('option', { name: 'v1 · r11-score-b' });
    fireEvent.change(screen.getByLabelText('分析成绩修订'), { target: { value: 'r11-score-b' } });
    fireEvent.click(await within(history()).findByRole('button', { name: /报告 r11-run-b/ }));
    await waitFor(() => expect(observations.has('r11-job-b')).toBe(true));
    expect(oldObservation.options.signal?.aborted).toBe(true);
    backend.ready.add('a');
    await emitSuccess('a');
    expect(screen.getByLabelText('分析施测')).toHaveValue('r11-assessment-b');
    expect(screen.getByLabelText('分析成绩修订')).toHaveValue('r11-score-b');
    expect(within(history()).queryByRole('button', { name: /报告 r11-run-a/ })).not.toBeInTheDocument();
    expect(historyRun('b')).toHaveTextContent('尚未准备');
    expect(within(screen.getByRole('region', { name: '所选固定报告' })).getByText('固定成绩 r11-score-b')).toBeVisible();
    backend.ready.add('b');
    // No observed terminal is emitted for B: a user refresh discovers the
    // literal backend ready view and must synchronize that same history row.
    fireEvent.click(within(screen.getByRole('region', { name: '所选固定报告' }))
      .getByRole('button', { name: '刷新报告状态' }));
    await screen.findByRole('region', { name: '报告事实与证据' });
    await waitFor(() => expect(historyRun('b')).toHaveTextContent('已准备'));
    expect(historyRun('b')).not.toHaveTextContent('尚未准备');
    expect(within(history()).queryByRole('button', { name: /报告 r11-run-a/ })).not.toBeInTheDocument();
  });
});
