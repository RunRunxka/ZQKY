import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { LearningAnalysisWorkspace } from './LearningAnalysisWorkspace';
import { b4Api, type AnalysisQuery } from '@/services/teaching-loop-b4-api';
import { ApiError } from '@/services/api-client';
import { classRow, deferred, evidenceRow, page, participant, point, run } from '@/features/practices/test-fixtures';

vi.mock('@/services/assessments-api', () => ({
  listAssessments: vi.fn(async () => ({ items: [{ assessmentId: 'assessment-old', title: '历史施测', heldOn: '2026-10-01', activeScoreRevisionId: 'score-active' }], total: 1, offset: 0, limit: 50 })),
  listScoreRevisions: vi.fn(async () => ({ items: [{ revisionId: 'score-old', assessmentId: 'assessment-old', paperRevisionId: 'paper-old', version: 1, state: 'confirmed' }], total: 1 })),
  getScoreRevision: vi.fn(async (id: string) => ({ revisionId: id, assessmentId: 'assessment-old', paperRevisionId: 'paper-old', state: 'confirmed', version: 1, participantSnapshot: [participant, { ...participant, participantId: 'pb', attemptNo: 2 }] })),
  getAssessment: vi.fn(async () => ({ assessment: { paperId: 'paper-id', paperRevisionId: 'paper-old' }, participants: [] })),
  getPaperAsset: vi.fn(),
  // 班名只读映射（固定成绩快照不含班名）：默认给一个真实班名，缺失态由用例覆盖。
  listClasses: vi.fn(async () => ({ items: [{ id: 'class-a', name: '七一班', code: 'A' }], total: 1, offset: 0, limit: 200 })),
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
  it('报告列表默认只看未归档；归档/恢复需二次确认并刷新列表', async () => {
    const items = [{ ...run }];
    const queries: Array<AnalysisQuery | undefined> = [];
    const list = vi.fn(async (query?: AnalysisQuery) => { queries.push(query); return page(items); });
    const archive = vi.fn(async (id: string) => ({ ...run, runId: id, archivedAt: '2026-10-06T00:00:00Z' }));
    const restore = vi.fn(async (id: string) => ({ ...run, runId: id, archivedAt: null }));
    render(<LearningAnalysisWorkspace services={services({ listAnalysisRuns: list, archiveAnalysisRun: archive, restoreAnalysisRun: restore })} />);
    const history = await screen.findByRole('region', { name: '固定报告历史' });
    await within(history).findByRole('button', { name: /已准备/ });
    expect(queries[0]).toMatchObject({ archived: false });
    fireEvent.click(within(history).getByRole('button', { name: '归档' }));
    expect(archive).not.toHaveBeenCalled();
    expect(within(history).getByText(/归档只隐藏列表入口，报告与快照保留且仍可查看/)).toBeInTheDocument();
    fireEvent.click(within(history).getByRole('button', { name: '确认归档' }));
    await waitFor(() => expect(archive).toHaveBeenCalledWith(run.runId));
    await within(history).findByText(`已归档报告「${run.paperTitle} · 2026-10-02」：列表入口隐藏，报告与快照保留且仍可查看。`);
    await waitFor(() => expect(queries.length).toBeGreaterThan(1));
    items[0] = { ...run, archivedAt: '2026-10-06T00:00:00Z' };
    fireEvent.click(within(history).getByLabelText('显示已归档'));
    await within(history).findByText('已归档');
    expect(queries.at(-1)?.archived).toBeUndefined();
    fireEvent.click(within(history).getByRole('button', { name: '恢复' }));
    expect(restore).not.toHaveBeenCalled();
    fireEvent.click(within(history).getByRole('button', { name: '确认恢复' }));
    await waitFor(() => expect(restore).toHaveBeenCalledWith(run.runId));
    await within(history).findByText(`已恢复报告「${run.paperTitle} · 2026-10-02」：重新出现在未归档列表。`);
  });
  it('归档失败如实报错并保留重试入口，不伪装成功', async () => {
    const archive = vi.fn(async () => { throw new ApiError('SERVICE_UNAVAILABLE', '响应丢失', 0, true); });
    render(<LearningAnalysisWorkspace services={services({ archiveAnalysisRun: archive })} />);
    const history = await screen.findByRole('region', { name: '固定报告历史' });
    fireEvent.click(await within(history).findByRole('button', { name: '归档' }));
    fireEvent.click(within(history).getByRole('button', { name: '确认归档' }));
    await within(history).findByText('SERVICE_UNAVAILABLE');
    expect(within(history).getByRole('button', { name: '确认归档' })).toBeEnabled();
    fireEvent.click(within(history).getByRole('button', { name: '确认归档' }));
    await waitFor(() => expect(archive).toHaveBeenCalledTimes(2));
    expect(archive.mock.calls[0]).toEqual(archive.mock.calls[1]);
  });
  it('已归档报告仍可查看事实，但不提供新建练习入口', async () => {
    const archivedRun = { ...run, archivedAt: '2026-10-06T00:00:00Z' };
    render(<LearningAnalysisWorkspace initialRunId={run.runId} services={services({ listAnalysisRuns: vi.fn(async () => page([archivedRun])), getAnalysisRun: vi.fn(async () => archivedRun) })} />);
    expect(await screen.findByText(/该报告已归档/)).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: '报告事实与证据' })).toBeInTheDocument();
    expect(screen.getByText('已归档报告不能新建练习；在报告历史恢复后此入口自动恢复。')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '创建针对练习' })).not.toBeInTheDocument();
  });

  it('班名有值用班名 + 短号次行；缺失才显示未记录班名（两态）', async () => {
    const namedRun = { ...run, participants: [{ ...participant, className: '七一班' }] };
    const namedRow = { ...classRow, className: '七一班' };
    const namedStudent = { participant: { ...participant, className: '七一班' }, knowledgePoint: point, observation: 'needs_consolidation' as const, informationIncomplete: false, expectedCount: 2, validCount: 2, stateCounts: { recorded: 2, missing: 0, absent: 0, exempt: 0 }, totalScoreUnits: 0, totalMaxScoreUnits: 100 };
    render(<LearningAnalysisWorkspace initialAssessmentId="assessment-old" initialScoreRevisionId="score-old" initialRunId={run.runId} services={services({
      listAnalysisRuns: vi.fn(async () => page([namedRun])), getAnalysisRun: vi.fn(async () => namedRun),
      listAnalysisClasses: vi.fn(async () => page([namedRow])), listAnalysisStudents: vi.fn(async () => page([namedStudent])),
    })} />);
    // 班级筛选下拉用班名；班级依据行班名为主、短号降为次行小字
    expect(within(await screen.findByLabelText('报告班级筛选')).getByRole('option', { name: '七一班 · class-a' })).toBeInTheDocument();
    const header = await screen.findByRole('rowheader', { name: /七一班/ });
    expect(header).toHaveTextContent('class-a'); expect(header).toHaveTextContent('固定知识点');
    // 固定成绩快照只冻结 classId：有班名时不显示「该成绩未记录班名」
    expect((await screen.findAllByText(/学号 001 · 班级 七一班 · class-a/)).length).toBeGreaterThan(0);
    expect(screen.queryByText('该成绩未记录班名')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: '学生依据' }));
    expect(await screen.findByText('班级 七一班 · class-a')).toBeInTheDocument();
    cleanup();
    // 缺失态：短号 + 后端 note（不伪造名称）
    render(<LearningAnalysisWorkspace initialRunId={run.runId} services={services()} />);
    expect(await screen.findByText('后端比例 0.123456')).toBeInTheDocument();
    expect(within(screen.getByLabelText('报告班级筛选')).getByRole('option', { name: 'class-a · 该成绩未记录班名' })).toBeInTheDocument();
    expect(screen.getAllByText('该成绩未记录班名').length).toBeGreaterThan(0);
  });

  it('报告链与已归档说明用原卷标题 + 时间；备注用姓名/知识点名映射，映射不到才短号', async () => {
    const archivedRun = { ...run, archivedAt: '2026-10-06T00:00:00Z' };
    const notes = vi.fn(async () => page([
      { noteId: 'n1', runId: run.runId, participantId: 'pa', knowledgePointId: 'kp-1', note: '甲的具体判断', createdAt: '2026-10-06T08:00:00Z', replayed: false },
      { noteId: 'n2', runId: run.runId, participantId: 'missing-p', knowledgePointId: null, note: '映射不到的人次', createdAt: '2026-10-06T08:00:00Z', replayed: false },
    ]));
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    render(<LearningAnalysisWorkspace initialRunId={run.runId} services={services({
      listAnalysisRuns: vi.fn(async () => page([archivedRun])), getAnalysisRun: vi.fn(async () => archivedRun), listAnalysisNotes: notes,
    })} />);
    // 详情链：原卷标题 + 时间为主文本，成绩/报告/原卷标识降为次行短号（run.createdAt 只有日期就不补时分）
    const link = await screen.findByRole('link', { name: '固定原卷 · 2026-10-02' });
    expect(link).toHaveAttribute('href', '/assessments?assessmentId=assessment-old&step=history');
    expect(await screen.findByText('成绩修订 score-ol… · 报告 run-old · 原卷修订 paper-ol…')).toBeInTheDocument();
    // 已归档说明行同样用原卷标题 + 时间，而不是 runId
    expect(await screen.findByText(/报告「固定原卷 · 2026-10-02」与快照保留/)).toBeInTheDocument();
    // 复制按钮给完整 ID（不是短号）
    fireEvent.click(screen.getByRole('button', { name: '复制 ID' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('runId=run-old\nscoreRevisionId=score-old\npaperRevisionId=paper-old'));
    expect(await screen.findByRole('button', { name: '已复制' })).toBeInTheDocument();
    // 备注视图：人次/知识点用 run 内名称映射，映射不到才短号
    fireEvent.click(screen.getByRole('tab', { name: '教师备注' }));
    expect(await screen.findByText(/· 甲 · 人次1 · 固定知识点/)).toBeInTheDocument();
    expect(await screen.findByText(/· missing-… · 全部知识点/)).toBeInTheDocument();
  });
});
