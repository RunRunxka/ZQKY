import { StrictMode, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PracticesWorkspace } from './PracticesWorkspace';
import { PracticeEditor } from './PracticeEditor';
import { PracticeExports } from './PracticeExports';
import { PracticeConversion } from './PracticeConversion';
import { RichReview } from '@/features/learning-analysis/ui';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { ApiError } from '@/services/api-client';
import { deferred, page, practice, revision, rich, run, suggestion } from './test-fixtures';
import { PRACTICE_RECOVERY_PREFIX } from './session';
import type { ExportArtifact, PracticeSetView } from '@/contracts/b4';

vi.mock('@/services/assessments-api', () => ({
  listClasses: vi.fn(async () => ({ items: [{ id: 'class-a', name: '当前班名', code: 'A' }], total: 1, offset: 0, limit: 50 })),
  listClassStudents: vi.fn(async () => ({ items: [{ id: 'student-a', name: '甲', studentNo: '001', memberships: [] }], total: 1 })),
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
});
