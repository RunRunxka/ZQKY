import { StrictMode, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PracticesWorkspace } from './PracticesWorkspace';
import { PracticeEditor } from './PracticeEditor';
import { PracticeExports } from './PracticeExports';
import { PracticeConversion } from './PracticeConversion';
import { RichReview } from '@/features/learning-analysis/ui';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { listAssessments } from '@/services/assessments-api';
import type { PracticeQuery } from '@/services/teaching-loop-b4-api';
import { ApiError } from '@/services/api-client';
import type { ApiErrorDetails } from '@/contracts/api';
import { deferred, page, practice, revision, rich, run, suggestion } from './test-fixtures';
import { PRACTICE_RECOVERY_PREFIX } from './session';
import type { ExportArtifact, PracticeSetView } from '@/contracts/b4';

vi.mock('@/services/assessments-api', () => ({
  listClasses: vi.fn(async () => ({ items: [{ id: 'class-a', name: '当前班名', code: 'A' }], total: 1, offset: 0, limit: 50 })),
  listClassStudents: vi.fn(async () => ({ items: [{ id: 'student-a', name: '甲', studentNo: '001', memberships: [] }], total: 1 })),
  listAssessments: vi.fn(async () => ({ items: [{ assessmentId: 'assessment-fixed', title: '固定施测标题' }], total: 1, offset: 0, limit: 200 })),
}));
vi.mock('@/services/workflow-jobs-api', () => ({ observeJob: vi.fn(async () => null), retryObservationWindow: (job: { attempt: number }) => ({ minAttempt: job.attempt, maxAttempt: job.attempt + 1 }), retryJob: vi.fn(), cancelJob: vi.fn() }));
afterEach(() => { cleanup(); for (const key of Object.keys(localStorage)) if (key.startsWith(PRACTICE_RECOVERY_PREFIX)) localStorage.removeItem(key); vi.clearAllMocks(); });
const unlocked = () => undefined;
function api(overrides: Partial<typeof b4Api> = {}): typeof b4Api { return { ...b4Api, listPractices: vi.fn(async () => page([practice])), getPractice: vi.fn(async () => practice), getAnalysisRun: vi.fn(async () => run), listPracticeExports: vi.fn(async () => page([])), ...overrides }; }
function savedView(score: string, number: number): PracticeSetView { return { ...practice, revision: number, currentRevision: { ...revision, draftItems: [{ ...revision.draftItems[0], maxScore: score, itemStructure: { nodes: [{ ...revision.draftItems[0].itemStructure.nodes[0], maxScore: score }] } }] } }; }
function EditorHost({ services }: { services: typeof b4Api }) { const [view, setView] = useState(practice); return <PracticeEditor view={view} services={services} onSaved={setView} onLocked={unlocked} />; }

describe('练习保存、审核与正式题', () => {
  it('保存中更晚的结构/约束编辑保留，未再次保存前零审核POST', async () => {
    const pending = deferred<PracticeSetView>();
    const patch = vi.fn().mockImplementationOnce(() => pending.promise).mockResolvedValueOnce(savedView('4', 3));
    const review = vi.fn();
    render(<StrictMode><EditorHost services={api({ patchPracticeDraft: patch, reviewPractice: review })} /></StrictMode>);
    const total = screen.getByLabelText('第1题整题满分'); const leaf = screen.getByLabelText('第1题节点1满分');
    fireEvent.change(total, { target: { value: '3' } }); fireEvent.change(leaf, { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    fireEvent.change(total, { target: { value: '4' } }); fireEvent.change(leaf, { target: { value: '4' } });
    await act(async () => pending.resolve(savedView('3', 2)));
    expect(total).toHaveValue('4'); expect(leaf).toHaveValue('4'); expect(screen.getByRole('button', { name: '独立审核此草稿' })).toBeDisabled(); expect(review).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(2));
    expect(patch.mock.calls[1][1]).toMatchObject({ expectedRevision: 2, items: [{ maxScore: '4' }] });
    await waitFor(() => expect(screen.getByRole('button', { name: '独立审核此草稿' })).toBeEnabled());
    expect(review).not.toHaveBeenCalled();
  });
  it('409与422保输入和结构；未知保存只重试原包', async () => {
    const patch = vi.fn().mockRejectedValueOnce(new ApiError('REVISION_CONFLICT', '并发更新', 409, false, 'r1', { currentRevision: 2 }))
      .mockRejectedValueOnce(new ApiError('BAD_SCORE', '分值不匹配', 422, false, 'r2', { issues: [{ field: 'items[0].maxScore', code: 'TOTAL_MISMATCH', message: '计分叶合计不匹配' }] }))
      .mockRejectedValueOnce(new ApiError('SERVICE_UNAVAILABLE', '响应未知', 0, true)).mockResolvedValueOnce(savedView('2', 2));
    render(<EditorHost services={api({ patchPracticeDraft: patch })} />);
    const total = screen.getByLabelText('第1题整题满分'); fireEvent.change(total, { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await screen.findByText('REVISION_CONFLICT'); expect(total).toHaveValue('2');
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await screen.findByText('BAD_SCORE'); expect(total).toHaveValue('2');
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await screen.findByRole('button', { name: '重试原草稿保存' }); expect(total).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重试原草稿保存' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(4));
    expect(patch.mock.calls[2][1]).toEqual(patch.mock.calls[3][1]);
  });
  it('建议显示真实缺口但不隐式写草稿；采用正式修订后支持显式节点来源', async () => {
    const suggest = vi.fn(async () => ({ items: [suggestion], requestedCount: 3, selectedCount: 1, coverage: { 'kp-1': 1 }, gaps: ['仅有1道满足约束的正式题'] }));
    const empty = { ...practice, currentRevision: { ...revision, draftItems: [], items: [] } };
    const patch = vi.fn(); render(<PracticeEditor view={empty} services={api({ suggestPractice: suggest, patchPracticeDraft: patch })} onSaved={unlocked} onLocked={unlocked} />);
    fireEvent.click(screen.getByRole('button', { name: '获取正式题建议' })); await screen.findByText('仅有1道满足约束的正式题');
    expect(screen.getByText('草稿还没有选题，请显式采用正式题建议。')).toBeInTheDocument(); expect(patch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '作为一计分叶加入，随后复核结构' }));
    expect(screen.getByLabelText('第1题节点1题面块1')).toBeChecked(); expect(screen.getByLabelText('第1题节点1题面块2')).toBeChecked();
    expect(screen.getByRole('button', { name: '独立审核此草稿' })).toBeDisabled();
  });
  it('独立审核响应未知时冻结同一CAS和submissionId，不发新版本确认', async () => {
    const review = vi.fn().mockRejectedValueOnce(new ApiError('SERVICE_UNAVAILABLE', '已提交但响应未知', 0, true)).mockResolvedValueOnce({ ...practice, revision: 2 });
    render(<EditorHost services={api({ reviewPractice: review })} />);
    fireEvent.click(screen.getByRole('button', { name: '独立审核此草稿' })); await screen.findByRole('button', { name: '重试原审核提交' });
    expect(screen.getByLabelText('第1题整题满分')).toBeDisabled(); expect(screen.getByRole('button', { name: '保存草稿' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重试原审核提交' })); await waitFor(() => expect(review).toHaveBeenCalledTimes(2));
    expect(review.mock.calls[0]).toEqual(review.mock.calls[1]); expect(review.mock.calls[1][1]).toMatchObject({ expectedRevision: 1 });
  });
});

describe('固定导出与转换', () => {
  const reviewed = { ...revision, practiceRevisionId: 'reviewed-a', state: 'reviewed' as const, reviewedAt: '2026-10-02' };
  it('学生预览不挂载教师块；202无成功下载，成绩模板须转换后指定施测', async () => {
    const create = vi.fn(async () => ({ exportId: 'export-a', practiceRevisionId: reviewed.practiceRevisionId, inputHash: 'h', job: { jobId: 'export-job', domain: 'teaching' as const, kind: 'export', attempt: 0, state: 'queued' as const, result: null, error: null }, replayed: false, reused: false }));
    const { rerender } = render(<><RichReview content={rich} assetScope="student" teacher={false} /><PracticeExports revision={reviewed} services={api({ createPracticeExport: create })} convertedAssessmentId={null} onLocked={unlocked} /></>);
    expect(screen.queryByText('教师答案甲')).not.toBeInTheDocument(); expect(screen.queryByText('教师解析乙')).not.toBeInTheDocument(); expect(screen.getByRole('button', { name: '生成成绩模板 XLSX' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '生成学生 DOCX' })); await screen.findByText('已接受，排队中'); expect(screen.queryByRole('button', { name: '下载学生 DOCX' })).not.toBeInTheDocument();
    rerender(<PracticeExports revision={reviewed} services={api({ createPracticeExport: create })} convertedAssessmentId="new-assessment" onLocked={unlocked} />);
    await waitFor(() => expect(screen.getByLabelText('模板施测ID')).toHaveValue('new-assessment'));
  });
  it('切固定修订时旧导出列表迟到不替换新修订产物', async () => {
    const newer = { ...reviewed, practiceRevisionId: 'reviewed-b', version: 2 };
    const set = { ...practice, currentRevision: reviewed, revisions: [reviewed, newer] };
    const old = deferred<ReturnType<typeof page<ExportArtifact>>>();
    const artifact: ExportArtifact = { artifactId: 'artifact-b', exportId: 'export-b', practiceRevisionId: newer.practiceRevisionId, variant: 'student', assessmentId: null, fileAssetId: 'f', filename: '新版本.docx', mediaType: 'application/docx', sha256: 's', byteSize: 10, downloadUrl: '', createdAt: '' };
    render(<PracticesWorkspace initialPracticeSetId="practice-a" services={api({ getPractice: vi.fn(async () => set), getPracticeRevision: vi.fn(async () => newer), listPracticeExports: vi.fn((_set, id) => id === 'reviewed-a' ? old.promise : Promise.resolve(page([artifact]))) })} />);
    fireEvent.click(await screen.findByRole('button', { name: /v2 · 已审核/ })); await screen.findByText(/新版本.docx/);
    await act(async () => old.resolve(page([{ ...artifact, practiceRevisionId: reviewed.practiceRevisionId, filename: '旧版本迟到.docx' }])));
    expect(screen.queryByText(/旧版本迟到.docx/)).not.toBeInTheDocument(); expect(screen.getByText(/新版本.docx/)).toBeInTheDocument();
  });
  it('导出未知只重试原variant/名单包；错误的固定产物身份不下载', async () => {
    const wrongJob = { jobId: 'export-job', domain: 'teaching' as const, kind: 'export', attempt: 1, state: 'succeeded' as const, result: { artifactId: 'wrong-artifact', exportId: 'export-a', practiceRevisionId: 'another-revision', variant: 'score_template', assessmentId: 'assessment-fixed' }, error: null };
    const create = vi.fn().mockRejectedValueOnce(new ApiError('SERVICE_UNAVAILABLE', '响应未知', 0, true)).mockResolvedValueOnce({ exportId: 'export-a', practiceRevisionId: reviewed.practiceRevisionId, inputHash: 'h', job: wrongJob, replayed: true, reused: false });
    const getArtifact = vi.fn(); const download = vi.fn();
    render(<PracticeExports revision={reviewed} services={api({ createPracticeExport: create, getExportArtifact: getArtifact, downloadExportArtifact: download })} convertedAssessmentId="assessment-fixed" onLocked={unlocked} />);
    fireEvent.click(screen.getByRole('button', { name: '生成成绩模板 XLSX' })); await screen.findByRole('button', { name: '重试原导出提交' });
    expect(screen.getByLabelText('模板施测ID')).toBeDisabled(); expect(screen.getByRole('button', { name: '生成学生 DOCX' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重试原导出提交' })); await screen.findByText('EXPORT_IDENTITY_MISMATCH');
    expect(create.mock.calls[0]).toEqual(create.mock.calls[1]); expect(create.mock.calls[1][2]).toMatchObject({ variant: 'score_template', assessmentId: 'assessment-fixed' });
    expect(getArtifact).not.toHaveBeenCalled(); expect(download).not.toHaveBeenCalled();
  });
  it.each(['job-result', 'artifact-metadata'] as const)('相同版本/variant的旧exportId不能冒充当前任务产物：%s', async (fault) => {
    const artifact: ExportArtifact = { artifactId: 'artifact-current', exportId: fault === 'artifact-metadata' ? 'old-export' : 'export-current', practiceRevisionId: reviewed.practiceRevisionId, variant: 'student', assessmentId: null, fileAssetId: 'f', filename: '本次.docx', mediaType: 'application/docx', sha256: 's', byteSize: 10, downloadUrl: '', createdAt: '' };
    const job = { jobId: 'job-current', domain: 'teaching' as const, kind: 'export', state: 'succeeded' as const, attempt: 1, result: { artifactId: artifact.artifactId, exportId: fault === 'job-result' ? 'old-export' : 'export-current', practiceRevisionId: reviewed.practiceRevisionId, variant: 'student', assessmentId: null }, error: null };
    const getArtifact = vi.fn(async () => artifact); const download = vi.fn();
    render(<PracticeExports revision={reviewed} services={api({ createPracticeExport: vi.fn(async () => ({ exportId: 'export-current', practiceRevisionId: reviewed.practiceRevisionId, inputHash: 'fixed', job, replayed: false, reused: false })), getExportArtifact: getArtifact, downloadExportArtifact: download })} convertedAssessmentId={null} onLocked={unlocked} />);
    fireEvent.click(screen.getByRole('button', { name: '生成学生 DOCX' })); await screen.findByText('EXPORT_IDENTITY_MISMATCH');
    expect(getArtifact).toHaveBeenCalledTimes(fault === 'job-result' ? 0 : 1); expect(download).not.toHaveBeenCalled(); expect(screen.queryByRole('button', { name: '下载学生 DOCX' })).not.toBeInTheDocument();
  });
  it('转换未知保完整人次原包，同包重试返回原施测并进入F20定位', async () => {
    const converted = { conversionId: 'conversion-a', paperId: 'paper-new', paperRevisionId: 'paper-revision-new', assessmentId: 'assessment-new', practiceRevisionId: reviewed.practiceRevisionId, replayed: true };
    const convert = vi.fn().mockRejectedValueOnce(new ApiError('SERVICE_UNAVAILABLE', '提交后响应丢失', 0, true)).mockResolvedValueOnce(converted);
    const onConverted = vi.fn(); render(<PracticeConversion revision={reviewed} services={api({ convertPractice: convert })} onConverted={onConverted} onLocked={unlocked} />);
    await screen.findByRole('option', { name: '当前班名 · A' }); fireEvent.change(screen.getByLabelText('练习施测班级'), { target: { value: 'class-a' } });
    fireEvent.click(await screen.findByLabelText('练习参测 甲')); fireEvent.change(screen.getByLabelText('练习施测日期'), { target: { value: '2026-10-02' } });
    fireEvent.change(screen.getByLabelText('甲 练习出勤'), { target: { value: 'exempt' } }); fireEvent.change(screen.getByLabelText('甲 练习人次'), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: '转换固定练习为施测' })); await screen.findByRole('button', { name: '重试原转换提交' });
    expect(screen.getByLabelText('练习施测日期')).toBeDisabled(); expect(screen.getByLabelText('甲 练习人次')).toHaveValue(3);
    fireEvent.click(screen.getByRole('button', { name: '重试原转换提交' })); await waitFor(() => expect(onConverted).toHaveBeenCalledWith(converted));
    expect(convert.mock.calls[0]).toEqual(convert.mock.calls[1]);
    expect(convert.mock.calls[1][2]).toMatchObject({ classIds: ['class-a'], participants: [{ studentId: 'student-a', classId: 'class-a', attendance: 'exempt', attemptNo: 3 }] });
    expect(screen.getByRole('link', { name: '进入现有成绩工作区' })).toHaveAttribute('href', '/assessments?assessmentId=assessment-new&step=score');
  });
  it('转换入口可按既有禁用模式置灰，且不发任何转换请求', async () => {
    const convert = vi.fn();
    render(<PracticeConversion revision={reviewed} services={api({ convertPractice: convert })} onConverted={unlocked} onLocked={unlocked} disabled />);
    expect(screen.getByText(/该练习已归档：转换为施测的入口已禁用/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '转换固定练习为施测' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '转换固定练习为施测' }));
    expect(convert).not.toHaveBeenCalled();
  });
});

describe('练习归档与恢复', () => {
  it('列表默认只看active；归档/恢复需二次确认并刷新列表', async () => {
    const items: PracticeSetView[] = [{ ...practice }];
    const queries: Array<PracticeQuery | undefined> = [];
    const list = vi.fn(async (query?: PracticeQuery) => { queries.push(query); return page([...items]); });
    const archive = vi.fn(async (id: string) => ({ ...practice, practiceSetId: id, status: 'archived' as const, revision: practice.revision + 1 }));
    const restore = vi.fn(async (id: string) => ({ ...practice, practiceSetId: id, status: 'active' as const, revision: practice.revision + 2 }));
    render(<PracticesWorkspace services={api({ listPractices: list, archivePracticeSet: archive, restorePracticeSet: restore })} />);
    fireEvent.click(await screen.findByRole('button', { name: '归档' }));
    expect(archive).not.toHaveBeenCalled();
    expect(screen.getByText(/归档后不能编辑\/导出\/转为施测，历史修订与既有产物保留/)).toBeInTheDocument();
    expect(queries[0]).toMatchObject({ status: 'active' });
    fireEvent.click(screen.getByRole('button', { name: '确认归档' }));
    await waitFor(() => expect(archive).toHaveBeenCalledWith(practice.practiceSetId, { expectedRevision: practice.revision }));
    await screen.findByText(`已归档练习「${practice.title}」：不能编辑/导出/转为施测，历史修订与既有产物保留。`);
    await waitFor(() => expect(queries.length).toBeGreaterThan(1));
    items[0] = { ...practice, status: 'archived', revision: practice.revision + 1 };
    fireEvent.click(screen.getByLabelText('显示已归档'));
    await screen.findByText('已归档');
    await waitFor(() => expect(queries.at(-1)?.status).toBeUndefined());
    fireEvent.click(screen.getByRole('button', { name: '恢复' }));
    expect(restore).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '确认恢复' }));
    await waitFor(() => expect(restore).toHaveBeenCalledWith(practice.practiceSetId, { expectedRevision: practice.revision + 1 }));
    await screen.findByText(`已恢复练习「${practice.title}」：可继续编辑、导出与转换为施测。`);
  });
  it('已归档练习的编辑/导出/转换入口置灰，不锁住练习列表，也不自动提交', async () => {
    const reviewedArchived = { ...revision, practiceRevisionId: 'reviewed-archived', state: 'reviewed' as const, reviewedAt: '2026-10-02' };
    const archivedSet: PracticeSetView = { ...practice, status: 'archived', revision: 2, currentRevision: reviewedArchived, revisions: [reviewedArchived] };
    const create = vi.fn(); const convert = vi.fn(); const newDraft = vi.fn();
    render(<PracticesWorkspace initialPracticeSetId={practice.practiceSetId} services={api({
      listPractices: vi.fn(async () => page([archivedSet])), getPractice: vi.fn(async () => archivedSet),
      getPracticeRevision: vi.fn(async () => reviewedArchived), createPracticeExport: create, convertPractice: convert, createPracticeRevision: newDraft,
    })} />);
    expect(await screen.findByText(/该练习已归档：编辑、导出与转换为施测入口已禁用/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '从此审核版建立新草稿' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '生成学生 DOCX' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '转换固定练习为施测' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '从此审核版建立新草稿' }));
    fireEvent.click(screen.getByRole('button', { name: '生成学生 DOCX' }));
    fireEvent.click(screen.getByRole('button', { name: '转换固定练习为施测' }));
    expect(newDraft).not.toHaveBeenCalled(); expect(create).not.toHaveBeenCalled(); expect(convert).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /^固定练习\s+练习/ })).toBeEnabled();
  });
});

describe('练习来源名称优先', () => {
  it('列表/详情/编辑用来源原卷标题 + 时间，练习与修订 ID 收进次行小字', async () => {
    render(<PracticesWorkspace initialPracticeSetId={practice.practiceSetId} services={api({ getPracticeRevision: vi.fn(async () => revision) })} />);
    const item = await screen.findByRole('button', { name: /固定练习\s+练习/ });
    expect(item).toHaveTextContent('来源报告 固定原卷 · 2026-10-02 09:30');
    expect(item).toHaveAttribute('title', expect.stringContaining(`练习 ${practice.practiceSetId}`));
    expect(await screen.findByRole('link', { name: '来源报告 固定原卷 · 2026-10-02 09:30' })).toHaveAttribute('href', expect.stringContaining('/learning-analysis?runId=run-old'));
    expect(screen.getByText(/来源报告 固定原卷 · 2026-10-02 09:30 · 练习修订 draft-a · 后端总分/)).toBeInTheDocument();
    // 编辑区同样按名称显示来源（ID 完整值进 title）
    expect(screen.getByText(/来源报告 固定原卷 · 编辑版本 1 · 当前草稿已保存/)).toBeInTheDocument();
  });

  it('转换区把班级 id 映射为班名，来源报告用标题 + 时间', async () => {
    const reviewed = { ...revision, practiceRevisionId: 'reviewed-a', state: 'reviewed' as const, reviewedAt: '2026-10-02' };
    render(<PracticeConversion revision={reviewed} services={api()} onConverted={unlocked} onLocked={unlocked} />);
    expect(await screen.findByText(/固定练习「固定练习」v1（reviewed…）；来源报告 固定原卷 · 2026-10-02 09:30/)).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText('练习施测班级'), { target: { value: 'class-a' } });
    fireEvent.click(await screen.findByLabelText('练习参测 甲'));
    expect(await screen.findByText('甲 · 当前班名')).toBeInTheDocument();
  });

  it('导出产物按施测标题显示名单来源；名称读取失败回落短号且不弹错', async () => {
    const reviewed = { ...revision, practiceRevisionId: 'reviewed-a', state: 'reviewed' as const, reviewedAt: '2026-10-02' };
    const artifact: ExportArtifact = { artifactId: 'artifact-1', exportId: 'export-1', practiceRevisionId: reviewed.practiceRevisionId, variant: 'score_template', assessmentId: 'assessment-fixed', fileAssetId: 'f', filename: '成绩模板.xlsx', mediaType: 'application/xlsx', sha256: 's', byteSize: 10, downloadUrl: '', createdAt: '' };
    const rendered = render(<PracticeExports revision={reviewed} services={api({ listPracticeExports: vi.fn(async () => page([artifact])) })} convertedAssessmentId={null} onLocked={unlocked} />);
    expect(await screen.findByText('名单来源施测 固定施测标题')).toBeInTheDocument();
    rendered.unmount();
    vi.mocked(listAssessments).mockRejectedValueOnce(new ApiError('DB_BROKEN', '读取损坏', 500, false));
    render(<PracticeExports revision={reviewed} services={api({ listPracticeExports: vi.fn(async () => page([artifact])) })} convertedAssessmentId={null} onLocked={unlocked} />);
    expect(await screen.findByText('名单来源施测 assessme…')).toBeInTheDocument();
    expect(screen.getByText(/施测名称读取失败/)).toBeInTheDocument();
    expect(screen.queryByText('DB_BROKEN')).not.toBeInTheDocument();
  });
});

describe('练习彻底删除（受引用守卫的三态）', () => {
  /**
   * 列表行的「彻底删除」：编辑工作区写完锁（恢复稿读取 + 缓存就绪）之前会被禁用，
   * 点击命中禁用按钮不会触发；这里重试到二次确认区出现为止，确认没有提前发写请求。
   */
  async function openDeleteConfirm(setId: string) {
    await waitFor(() => {
      fireEvent.click(screen.getByTestId(`practices-delete-${setId}`));
      expect(screen.getByText(/物理删除、不可恢复/)).toBeInTheDocument();
    });
  }

  it('成功：二次确认后按 expectedRevision 物理删除、刷新列表并清空当前选择', async () => {
    const remove = vi.fn(async () => ({ deleted: true, practiceSetId: practice.practiceSetId }));
    const list = vi.fn(async () => page([practice]));
    render(<PracticesWorkspace initialPracticeSetId={practice.practiceSetId} services={api({ listPractices: list, deletePracticeSet: remove, getPracticeRevision: vi.fn(async () => revision) })} />);
    await openDeleteConfirm(practice.practiceSetId);
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '确认彻底删除' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(practice.practiceSetId, practice.revision));
    await screen.findByText(`已彻底删除练习「${practice.title}」：物理删除完成，不可恢复。`);
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1));
    await waitFor(() => expect(screen.queryByRole('heading', { name: practice.title })).not.toBeInTheDocument());
  });

  it('被引用 409 逐项渲染 counts 并给「改为归档」；乐观锁冲突走错误区不误报引用', async () => {
    const remove = vi.fn()
      .mockRejectedValueOnce(new ApiError('PRACTICE_IN_USE', '练习集仍被引用，不能删除（已审核版本 1 条、施测转换 2 条）；已审核版本只能归档。', 409, false, 'r1', { counts: { reviewedRevisions: 1, exports: 0, conversions: 2 } } as ApiErrorDetails))
      .mockRejectedValueOnce(new ApiError('REVISION_CONFLICT', '编辑版本已变化。', 409, false, 'r2', { currentRevision: 2 }));
    const archive = vi.fn(async (id: string) => ({ ...practice, practiceSetId: id, status: 'archived' as const, revision: practice.revision + 1 }));
    render(<PracticesWorkspace initialPracticeSetId={practice.practiceSetId} services={api({ deletePracticeSet: remove, archivePracticeSet: archive, getPracticeRevision: vi.fn(async () => revision) })} />);
    await openDeleteConfirm(practice.practiceSetId);
    fireEvent.click(screen.getByRole('button', { name: '确认彻底删除' }));
    const guard = await screen.findByTestId('practices-delete-guard');
    expect(guard).toHaveTextContent('PRACTICE_IN_USE');
    expect(guard).toHaveTextContent('已审核版本 1 条');
    expect(guard).toHaveTextContent('施测转换 2 条');
    expect(guard).not.toHaveTextContent('导出记录'); // 计数 0 的引用不列出
    fireEvent.click(screen.getByRole('button', { name: '改为归档（不删除历史）' }));
    await waitFor(() => expect(archive).toHaveBeenCalledWith(practice.practiceSetId, { expectedRevision: practice.revision }));
    await screen.findByText(`已归档练习「${practice.title}」：不能编辑/导出/转为施测，历史修订与既有产物保留。`);
    expect(screen.queryByTestId('practices-delete-guard')).not.toBeInTheDocument();
    // 第二次：乐观锁冲突不得伪装成引用问题
    await openDeleteConfirm(practice.practiceSetId);
    fireEvent.click(screen.getByRole('button', { name: '确认彻底删除' }));
    await screen.findByText('REVISION_CONFLICT');
    expect(screen.getByText('服务器当前编辑版本：2。输入已保留，请核对新版本。')).toBeInTheDocument();
    expect(screen.queryByTestId('practices-delete-guard')).not.toBeInTheDocument();
    expect(remove.mock.calls[0]).toEqual(remove.mock.calls[1]);
  });

  it('已归档练习同样可删（同一守卫），并在二次确认里点明', async () => {
    const archivedSet: PracticeSetView = { ...practice, status: 'archived', revision: 3 };
    const remove = vi.fn(async () => ({ deleted: true, practiceSetId: practice.practiceSetId }));
    render(<PracticesWorkspace services={api({ listPractices: vi.fn(async () => page([archivedSet])), deletePracticeSet: remove })} />);
    await openDeleteConfirm(practice.practiceSetId);
    expect(screen.getByText(/已归档练习同样受该守卫，不会因归档而可删/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认彻底删除' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(practice.practiceSetId, 3));
  });
});
