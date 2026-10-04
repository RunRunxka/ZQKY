import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { LearningAnalysisWorkspace } from './LearningAnalysisWorkspace';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { ApiError } from '@/services/api-client';
import { classRow, deferred, evidenceRow, page, participant, run } from '@/features/practices/test-fixtures';

vi.mock('@/services/assessments-api', () => ({
  listAssessments: vi.fn(async () => ({ items: [{ assessmentId: 'assessment-old', title: '历史施测', heldOn: '2026-10-01', activeScoreRevisionId: 'score-active' }], total: 1, offset: 0, limit: 50 })),
  listScoreRevisions: vi.fn(async () => ({ items: [{ revisionId: 'score-old', assessmentId: 'assessment-old', paperRevisionId: 'paper-old', version: 1, state: 'confirmed' }], total: 1 })),
  getScoreRevision: vi.fn(async (id: string) => ({ revisionId: id, assessmentId: 'assessment-old', paperRevisionId: 'paper-old', state: 'confirmed', version: 1, participantSnapshot: [participant, { ...participant, participantId: 'pb', attemptNo: 2 }] })),
  getAssessment: vi.fn(async () => ({ assessment: { paperId: 'paper-id', paperRevisionId: 'paper-old' }, participants: [] })),
  getPaperAsset: vi.fn(),
}));
vi.mock('@/services/workflow-jobs-api', () => ({ observeJob: vi.fn(async () => null), retryObservationWindow: (job: { attempt: number }) => ({ minAttempt: job.attempt, maxAttempt: job.attempt + 1 }), retryJob: vi.fn(), cancelJob: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
function services(overrides: Partial<typeof b4Api> = {}): typeof b4Api { return { ...b4Api, listAnalysisRuns: vi.fn(async () => page([run])), getAnalysisRun: vi.fn(async () => run), listAnalysisClasses: vi.fn(async () => page([classRow])), listAnalysisStudents: vi.fn(async () => page([])), listAnalysisEvidence: vi.fn(async () => page([evidenceRow])), listAnalysisNotes: vi.fn(async () => page([])), ...overrides }; }

describe('固定学情工作区', () => {
  it('手动刷新固定报告同步历史准备状态', async () => {
    let current = { ...run, reportReady: false };
    const api = services({ listAnalysisRuns: vi.fn(async () => page([current])), getAnalysisRun: vi.fn(async () => current) });
    render(<LearningAnalysisWorkspace initialRunId={run.runId} services={api} />);
    const history = await screen.findByRole('region', { name: '固定报告历史' });
    await within(history).findByRole('button', { name: /尚未准备/ });
    current = run;
    fireEvent.click(await screen.findByRole('button', { name: '刷新报告状态' }));
    await screen.findByRole('region', { name: '报告事实与证据' });
    expect(await within(history).findByRole('button', { name: /已准备/ })).toHaveTextContent(`报告 ${run.runId}`);
    expect(within(history).queryByRole('button', { name: /尚未准备/ })).not.toBeInTheDocument();
  });
  it('不把历史入口换成active；同学生必须明确选择一个补考人次', async () => {
    const create = vi.fn(async () => ({ runId: run.runId, inputHash: 'hash', scoreRevisionId: 'score-old', paperRevisionId: 'paper-old', job: run.job, replayed: false, reused: false }));
    render(<StrictMode><LearningAnalysisWorkspace initialAssessmentId="assessment-old" initialScoreRevisionId="score-old" services={services({ createAnalysisRun: create })} /></StrictMode>);
    const first = await screen.findByLabelText('分析人次 甲 1');
    fireEvent.click(first); fireEvent.click(screen.getByLabelText('分析人次 甲 2'));
    expect(first).not.toBeChecked(); expect(screen.getByLabelText('分析人次 甲 2')).toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: '创建本次报告' }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create.mock.calls[0]).toEqual(['assessment-old', expect.objectContaining({ scoreRevisionId: 'score-old', selectedParticipantIds: ['pb'], ruleCode: 'any_loss_v1' })]);
  });
  it('原样显示后端比例和缺班名；全部题证据含有效0分和真实富块', async () => {
    render(<LearningAnalysisWorkspace initialRunId={run.runId} services={services()} />);
    expect(await screen.findByText('后端比例 0.123456')).toBeInTheDocument();
    expect(screen.getAllByText('该成绩未记录班名').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('tab', { name: '全部题证据' }));
    expect(await screen.findByText(/有效记录 0 \/ 1/)).toBeInTheDocument();
    expect(screen.getByText('固定共同材料')).toBeInTheDocument(); expect(screen.getByText('固定题干')).toBeInTheDocument();
    expect(screen.getByText('教师答案甲')).toBeInTheDocument(); expect(screen.getByText('教师解析乙')).toBeInTheDocument();
  });
  it('读取失败保留明确错误，不伪装空报告；迟到旧筛选不盖新筛选', async () => {
    const old = deferred<ReturnType<typeof page<typeof classRow>>>();
    const api = services({ listAnalysisClasses: vi.fn((_id, query) => query?.knowledgePointId ? Promise.resolve(page([{ ...classRow, needsCount: 7 }])) : old.promise) });
    render(<LearningAnalysisWorkspace initialRunId={run.runId} services={api} />);
    await screen.findByLabelText('报告知识点筛选');
    fireEvent.change(screen.getByLabelText('报告知识点筛选'), { target: { value: 'kp-1' } });
    await screen.findByRole('cell', { name: '7' });
    await act(async () => old.resolve(page([classRow])));
    expect(screen.getByRole('cell', { name: '7' })).toBeInTheDocument();
    cleanup();
    render(<LearningAnalysisWorkspace services={services({ listAnalysisRuns: vi.fn(async () => { throw new ApiError('DB_BROKEN', '读取损坏', 500, false); }) })} />);
    await screen.findByText('DB_BROKEN'); expect(screen.queryByText('此来源还没有分析报告。')).not.toBeInTheDocument();
  });
  it('追加备注的迟到成功保留新输入；未知结果冻结原包并锁住页签', async () => {
    const saving = deferred<Awaited<ReturnType<typeof b4Api.createAnalysisNote>>>();
    const note = vi.fn().mockImplementationOnce(() => saving.promise).mockRejectedValueOnce(new ApiError('SERVICE_UNAVAILABLE', '响应丢失', 0, true)).mockResolvedValue({ noteId: 'note', runId: run.runId, note: '第二次', participantId: null, knowledgePointId: null, createdAt: '', replayed: true });
    render(<LearningAnalysisWorkspace initialRunId={run.runId} services={services({ createAnalysisNote: note })} />);
    await screen.findByLabelText('报告知识点筛选'); fireEvent.click(screen.getByRole('tab', { name: '教师备注' }));
    const input = await screen.findByLabelText('教师备注内容');
    fireEvent.change(input, { target: { value: '发送时备注' } }); fireEvent.click(screen.getByRole('button', { name: '追加教师备注' }));
    await waitFor(() => expect(note).toHaveBeenCalledTimes(1)); fireEvent.change(input, { target: { value: '第二次' } });
    await act(async () => saving.resolve({ noteId: 'note', runId: run.runId, note: '发送时备注', participantId: null, knowledgePointId: null, createdAt: '', replayed: false }));
    expect(input).toHaveValue('第二次');
    fireEvent.click(screen.getByRole('button', { name: '追加教师备注' }));
    await screen.findByRole('button', { name: '重试原备注提交' });
    expect(input).toBeDisabled(); expect(screen.getByRole('tab', { name: '全部题证据' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重试原备注提交' }));
    await waitFor(() => expect(note).toHaveBeenCalledTimes(3));
    expect(note.mock.calls[1][1]).toEqual(note.mock.calls[2][1]);
  });
  it.each(['first-200', 'unknown-replay'])('G2 %s只确认备注A，保存途中继续输入B不清空', async (mode) => {
    const first = deferred<Awaited<ReturnType<typeof b4Api.createAnalysisNote>>>();
    const original = { noteId: 'note-a', runId: run.runId, note: '备注A', participantId: null, knowledgePointId: null, createdAt: '', replayed: true };
    const create = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValueOnce(original);
    render(<StrictMode><LearningAnalysisWorkspace initialRunId={run.runId} services={services({ createAnalysisNote: create })} /></StrictMode>);
    fireEvent.click(await screen.findByRole('tab', { name: '教师备注' }));
    const input = await screen.findByLabelText('教师备注内容');
    fireEvent.change(input, { target: { value: '备注A' } }); fireEvent.click(screen.getByRole('button', { name: '追加教师备注' }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1)); fireEvent.change(input, { target: { value: '后续备注B' } });
    if (mode === 'first-200') await act(async () => first.resolve(original));
    else {
      await act(async () => first.reject(new ApiError('RESPONSE_LOST', '丢回执', 0, true)));
      fireEvent.click(await screen.findByRole('button', { name: '重试原备注提交' }));
      await waitFor(() => expect(create).toHaveBeenCalledTimes(2)); expect(create.mock.calls[1]).toEqual(create.mock.calls[0]);
    }
    await screen.findByText('原备注已追加；发送后的新备注仍保留，尚未追加。');
    expect(input).toHaveValue('后续备注B'); expect(screen.getByRole('button', { name: '追加教师备注' })).toBeEnabled();
  });
});
