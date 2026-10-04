import { StrictMode, useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PracticesWorkspace } from '@/features/practices/PracticesWorkspace';
import { LearningAnalysisWorkspace } from '@/features/learning-analysis/LearningAnalysisWorkspace';
import { PracticeEditor } from '@/features/practices/PracticeEditor';
import { practice, revision, page, deferred, run, classRow } from '@/features/practices/test-fixtures';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { ApiError } from '@/services/api-client';
import type { PracticeSetView } from '@/contracts/b4';

vi.mock('next/link', () => ({ default: ({ children, ...props }: React.ComponentProps<'a'>) => <a {...props}>{children}</a> }));
vi.mock('@/services/assessments-api', () => ({ listAssessments: vi.fn(async () => page([])), getAssessment: vi.fn(async () => ({ assessment: { paperId: 'paper-id', paperRevisionId: 'paper-old' }, participants: [] })), listScoreRevisions: vi.fn(async () => page([])), getScoreRevision: vi.fn(), getPaperAsset: vi.fn() }));
vi.mock('@/services/workflow-jobs-api', () => ({ observeJob: vi.fn(async () => null), retryObservationWindow: (job: { attempt: number }) => ({ minAttempt: job.attempt, maxAttempt: job.attempt + 1 }), retryJob: vi.fn(), cancelJob: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
const noOp = () => undefined;
function api(overrides: Partial<typeof b4Api> = {}): typeof b4Api { return { ...b4Api, listPractices: vi.fn(async () => page([practice])), getPractice: vi.fn(async () => practice), listPracticeExports: vi.fn(async () => page([])), ...overrides }; }
function saved(score: string, number: number): PracticeSetView { return { ...practice, revision: number, currentRevision: { ...revision, draftItems: [{ ...revision.draftItems[0], maxScore: score, itemStructure: { nodes: [{ ...revision.draftItems[0].itemStructure.nodes[0], maxScore: score }] } }] } }; }
function Host({ services }: { services: typeof b4Api }) { const [view, setView] = useState(practice); return <PracticeEditor view={view} services={services} onSaved={setView} onLocked={noOp} />; }

describe('B4 independent correct-behavior probes', () => {
  it('unknown teacher-note replay preserves newer post-send text', async () => {
    const first = deferred<Awaited<ReturnType<typeof b4Api.createAnalysisNote>>>();
    const create = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValueOnce({ noteId: 'n1', runId: run.runId, note: '已发送的备注', participantId: null, knowledgePointId: null, createdAt: '', replayed: true });
    const services = api({ listAnalysisRuns: vi.fn(async () => page([run])), getAnalysisRun: vi.fn(async () => run), listAnalysisClasses: vi.fn(async () => page([classRow])), listAnalysisNotes: vi.fn(async () => page([])), createAnalysisNote: create });
    render(<LearningAnalysisWorkspace initialRunId={run.runId} services={services} />);
    fireEvent.click(await screen.findByRole('tab', { name: '教师备注' }));
    const note = await screen.findByLabelText('教师备注内容');
    fireEvent.change(note, { target: { value: '已发送的备注' } });
    fireEvent.click(screen.getByRole('button', { name: '追加教师备注' }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    fireEvent.change(note, { target: { value: '请求发出后的新备注' } });
    await act(async () => first.reject(new ApiError('REQUEST_FAILED', 'response lost', 0, true)));
    fireEvent.click(await screen.findByRole('button', { name: '重试原备注提交' }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(2));
    expect(create.mock.calls[0]).toEqual(create.mock.calls[1]);
    await waitFor(() => expect(screen.getByRole('button', { name: '追加教师备注' })).toBeInTheDocument());
    expect(note).toHaveValue('请求发出后的新备注');
  });
  it('unknown save replay acknowledges original packet without discarding post-send edits', async () => {
    const first = deferred<PracticeSetView>();
    const patch = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValueOnce(saved('2', 2));
    render(<StrictMode><Host services={api({ patchPracticeDraft: patch })} /></StrictMode>);
    const total = screen.getByLabelText('第1题整题满分');
    const leaf = screen.getByLabelText('第1题节点1满分');
    fireEvent.change(total, { target: { value: '2' } }); fireEvent.change(leaf, { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    fireEvent.change(total, { target: { value: '3' } }); fireEvent.change(leaf, { target: { value: '3' } });
    await act(async () => first.reject(new ApiError('REQUEST_FAILED', 'response lost', 0, true)));
    fireEvent.click(await screen.findByRole('button', { name: '重试原草稿保存' }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(2));
    expect(patch.mock.calls[0]).toEqual(patch.mock.calls[1]);
    await screen.findByText('草稿已保存。审核需要另行确认。');
    expect(total).toHaveValue('3');
    expect(leaf).toHaveValue('3');
    expect(screen.getByRole('button', { name: '独立审核此草稿' })).toBeDisabled();
  });
  it('switching practice cannot silently discard unsaved score and selected nodes', async () => {
    const other: PracticeSetView = { ...practice, practiceSetId: 'practice-b', title: '第二练习', currentRevision: { ...revision, practiceSetId: 'practice-b', practiceRevisionId: 'draft-b', title: '第二练习' }, revisions: [] };
    const patch = vi.fn();
    render(<PracticesWorkspace initialPracticeSetId="practice-a" services={api({ listPractices: vi.fn(async () => page([practice, other])), getPractice: vi.fn(async (id) => id === 'practice-a' ? practice : other), patchPracticeDraft: patch })} />);
    fireEvent.change(await screen.findByLabelText('第1题整题满分'), { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: /^第二练习\s+练习/ }));
    await screen.findByRole('heading', { name: '第二练习' });
    fireEvent.click(screen.getByRole('button', { name: /^固定练习\s+练习/ }));
    const restored = await screen.findByLabelText('第1题整题满分');
    expect(patch).not.toHaveBeenCalled();
    expect(restored).toHaveValue('5');
  });
});
