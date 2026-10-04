import { StrictMode, useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PracticeEditor } from './PracticeEditor';
import { PracticesWorkspace } from './PracticesWorkspace';
import { PRACTICE_RECOVERY_PREFIX, recoveryKey } from './session';
import { practice, revision, page, deferred } from './test-fixtures';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { ApiError } from '@/services/api-client';
import type { PracticeSetView } from '@/contracts/b4';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => '/practices' }));
vi.mock('@/services/workflow-jobs-api', () => ({ observeJob: vi.fn(async () => null), retryObservationWindow: (job: { attempt: number }) => ({ minAttempt: job.attempt, maxAttempt: job.attempt + 1 }), retryJob: vi.fn(), cancelJob: vi.fn() }));
afterEach(() => {
  cleanup();
  for (const key of Object.keys(localStorage)) if (key.startsWith(PRACTICE_RECOVERY_PREFIX)) localStorage.removeItem(key);
  vi.restoreAllMocks();
});
const noop = () => undefined;
function api(overrides: Partial<typeof b4Api> = {}): typeof b4Api {
  return { ...b4Api, listPractices: vi.fn(async () => page([practice])), getPractice: vi.fn(async () => practice), listPracticeExports: vi.fn(async () => page([])), ...overrides };
}
function saved(score: string, number: number): PracticeSetView {
  return { ...practice, revision: number, currentRevision: { ...revision, draftItems: [{ ...revision.draftItems[0], maxScore: score, itemStructure: { nodes: [{ ...revision.draftItems[0].itemStructure.nodes[0], maxScore: score }] } }] } };
}
function Host({ services }: { services: typeof b4Api }) {
  const [view, setView] = useState(practice);
  return <PracticeEditor view={view} services={services} onSaved={setView} onLocked={noop} />;
}
function changeScore(score: string) {
  fireEvent.change(screen.getByLabelText('第1题整题满分'), { target: { value: score } });
  fireEvent.change(screen.getByLabelText('第1题节点1满分'), { target: { value: score } });
}
const other: PracticeSetView = { ...practice, practiceSetId: 'practice-b', title: '第二练习', currentRevision: { ...revision, practiceSetId: 'practice-b', practiceRevisionId: 'draft-b', title: '第二练习' }, revisions: [] };
function workspace(overrides: Partial<typeof b4Api> = {}) {
  return api({ listPractices: vi.fn(async () => page([practice, other])), getPractice: vi.fn(async (id) => id === 'practice-a' ? practice : other), getPracticeRevision: vi.fn(async () => revision), ...overrides });
}
async function switchOther() { fireEvent.click(await screen.findByRole('button', { name: /^第二练习\s+练习/ })); await screen.findByRole('dialog', { name: '处理未保存练习' }); }

describe('G2 编辑代次与原操作恢复', () => {
  it.each(['first-200', 'unknown-replay'])('%s 只确认原分值2，保留在途后分值3及dirty', async (mode) => {
    const first = deferred<PracticeSetView>();
    const patch = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValueOnce(saved('2', 2));
    render(<StrictMode><Host services={api({ patchPracticeDraft: patch })} /></StrictMode>);
    changeScore('2'); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
    changeScore('3');
    if (mode === 'first-200') await act(async () => first.resolve(saved('2', 2)));
    else {
      await act(async () => first.reject(new ApiError('RESPONSE_LOST', '响应丢失', 0, true)));
      fireEvent.click(await screen.findByRole('button', { name: '重试原草稿保存' }));
      await waitFor(() => expect(patch).toHaveBeenCalledTimes(2));
      expect(patch.mock.calls[1]).toEqual(patch.mock.calls[0]);
    }
    await screen.findByText('发送的草稿已保存；之后的编辑仍保留，尚未保存，请再次保存后审核。');
    expect(screen.getByLabelText('第1题整题满分')).toHaveValue('3'); expect(screen.getByLabelText('第1题节点1满分')).toHaveValue('3');
    expect(screen.getByRole('button', { name: '独立审核此草稿' })).toBeDisabled();
    expect(patch.mock.calls[0][1]).toMatchObject({ expectedRevision: 1, submissionId: expect.any(String), items: [{ maxScore: '2' }] });
  });
  it('读取较高服务端版本后，迟到旧receipt不退输入或已采用CAS', async () => {
    const first = deferred<PracticeSetView>(); const patch = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValueOnce(saved('3', 5)); const onSaved = vi.fn();
    const services = api({ patchPracticeDraft: patch });
    const rendered = render(<PracticeEditor view={practice} services={services} onSaved={onSaved} onLocked={noop} />);
    changeScore('2'); fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(1)); changeScore('3');
    rendered.rerender(<PracticeEditor view={{ ...saved('9', 4), currentRevision: { ...saved('9', 4).currentRevision, practiceRevisionId: 'new-fixed' } }} services={services} onSaved={onSaved} onLocked={noop} />);
    expect(screen.getByRole('button', { name: '保存草稿' })).toBeDisabled(); expect(screen.getByRole('button', { name: '获取正式题建议' })).toBeDisabled();
    await act(async () => first.resolve(saved('2', 2)));
    expect(onSaved).not.toHaveBeenCalled(); expect(screen.getByLabelText('第1题整题满分')).toHaveValue('3');
    await screen.findByText('原操作已收到回执；服务器已知版本或固定身份较新，本地输入与版本保持。');
    fireEvent.click(screen.getByRole('button', { name: '保留输入并采用最新版本' }));
    expect(screen.getByText(/编辑版本 4 · 有未保存修改/)).toBeInTheDocument(); expect(screen.getByRole('button', { name: '独立审核此草稿' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(2));
    expect(patch.mock.calls[1][1]).toMatchObject({ expectedRevision: 4, items: [{ maxScore: '3' }] });
    expect(patch.mock.calls[1][1].submissionId).not.toBe(patch.mock.calls[0][1].submissionId);
  });
  it('相同CAS不同固定修订身份的receipt不覆盖正文', async () => {
    const first = deferred<PracticeSetView>(); const patch = vi.fn(() => first.promise); const onSaved = vi.fn();
    const services = api({ patchPracticeDraft: patch });
    const rendered = render(<PracticeEditor view={practice} services={services} onSaved={onSaved} onLocked={noop} />);
    changeScore('2'); fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(1)); changeScore('3');
    rendered.rerender(<PracticeEditor view={{ ...saved('9', 2), currentRevision: { ...saved('9', 2).currentRevision, practiceRevisionId: 'other-identity' } }} services={services} onSaved={onSaved} onLocked={noop} />);
    await act(async () => first.resolve(saved('2', 2)));
    expect(onSaved).not.toHaveBeenCalled(); expect(screen.getByLabelText('第1题整题满分')).toHaveValue('3');
    expect(screen.getByRole('button', { name: '保存草稿' })).toBeDisabled(); expect(screen.getByRole('button', { name: '获取正式题建议' })).toBeDisabled();
    expect(screen.getByText(/固定身份冲突：同编辑版本/)).toBeInTheDocument();
  });
  it('换练习后旧对象迟到receipt只记录，不能替换新对象或阻塞其保存', async () => {
    const first = deferred<PracticeSetView>(); const patch = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValueOnce({ ...other, revision: 2 }); const onSaved = vi.fn();
    const services = api({ patchPracticeDraft: patch }); const rendered = render(<PracticeEditor view={practice} services={services} onSaved={onSaved} onLocked={noop} />);
    changeScore('2'); fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    rendered.rerender(<PracticeEditor view={other} services={services} onSaved={onSaved} onLocked={noop} />);
    await act(async () => first.resolve(saved('2', 2))); expect(onSaved).not.toHaveBeenCalled(); expect(screen.getByLabelText('第1题整题满分')).toHaveValue('1');
    changeScore('4'); fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(2)); expect(patch.mock.calls[1][0]).toBe(other.practiceSetId);
  });
  it('未知原包重放即使后来已读更高版本仍允许恢复，不能冒充新的CAS保存', async () => {
    const first = deferred<PracticeSetView>(); const patch = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValueOnce(saved('2', 2)); const onSaved = vi.fn();
    const services = api({ patchPracticeDraft: patch }); const rendered = render(<PracticeEditor view={practice} services={services} onSaved={onSaved} onLocked={noop} />);
    changeScore('2'); fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(1)); changeScore('3');
    await act(async () => first.reject(new ApiError('RESPONSE_LOST', '响应丢失', 0, true)));
    rendered.rerender(<PracticeEditor view={saved('9', 4)} services={services} onSaved={onSaved} onLocked={noop} />);
    expect(screen.getByRole('button', { name: '重试原草稿保存' })).toBeEnabled(); fireEvent.click(screen.getByRole('button', { name: '重试原草稿保存' }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(2)); expect(patch.mock.calls[0]).toEqual(patch.mock.calls[1]);
    await screen.findByText('原操作已收到回执；服务器已知版本或固定身份较新，本地输入与版本保持。');
    expect(screen.getByLabelText('第1题整题满分')).toHaveValue('3'); expect(screen.getByRole('button', { name: '保存草稿' })).toBeDisabled(); expect(onSaved).not.toHaveBeenCalled();
  });
  it('unknown卸载重载保留首次操作包且零自动请求，成功重放不清后续编辑', async () => {
    const first = deferred<PracticeSetView>(); const patch = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValueOnce(saved('2', 2));
    const services = api({ patchPracticeDraft: patch }); const rendered = render(<Host services={services} />);
    changeScore('2'); fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(1)); changeScore('3');
    await act(async () => first.reject(new ApiError('RESPONSE_LOST', '响应丢失', 0, true))); await screen.findByRole('button', { name: '重试原草稿保存' });
    const original = JSON.parse(localStorage.getItem(recoveryKey(practice.practiceSetId))!); rendered.unmount();
    render(<StrictMode><Host services={services} /></StrictMode>);
    await screen.findByRole('button', { name: '重试原草稿保存' }); expect(patch).toHaveBeenCalledTimes(1); expect(screen.getByLabelText('第1题整题满分')).toHaveValue('3');
    fireEvent.click(screen.getByRole('button', { name: '重试原草稿保存' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(2));
    expect(patch.mock.calls[0]).toEqual(patch.mock.calls[1]);
    expect(JSON.parse(localStorage.getItem(recoveryKey(practice.practiceSetId))!).editGeneration).toBe(original.editGeneration);
    expect(screen.getByLabelText('第1题整题满分')).toHaveValue('3'); expect(screen.getByRole('button', { name: '独立审核此草稿' })).toBeDisabled();
  });
  it('发送前恢复缓存写失败会阻止PATCH，输入保留可重试', async () => {
    const patch = vi.fn(); render(<Host services={api({ patchPracticeDraft: patch })} />); changeScore('5');
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota'); });
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await screen.findByText('RECOVERY_CACHE_FAILED');
    expect(patch).not.toHaveBeenCalled(); expect(screen.getByLabelText('第1题整题满分')).toHaveValue('5');
  });
  it('坏缓存不当空稿覆盖，不发送PATCH或审核', async () => {
    const raw = '{broken'; localStorage.setItem(recoveryKey(practice.practiceSetId), raw);
    const patch = vi.fn(); const review = vi.fn(); render(<Host services={api({ patchPracticeDraft: patch, reviewPractice: review })} />);
    await screen.findByText(/恢复缓存读取失败/); expect(localStorage.getItem(recoveryKey(practice.practiceSetId))).toBe(raw);
    expect(screen.getByRole('button', { name: '保存草稿' })).toBeDisabled(); expect(screen.getByRole('button', { name: '独立审核此草稿' })).toBeDisabled(); expect(patch).not.toHaveBeenCalled(); expect(review).not.toHaveBeenCalled();
  });
});

describe('G2 离开策略与按练习恢复', () => {
  it('切另一练习可取消保持分值、节点、约束，保留稿离开后返回可恢复', async () => {
    const patch = vi.fn(); render(<PracticesWorkspace initialPracticeSetId={practice.practiceSetId} services={workspace({ patchPracticeDraft: patch })} />);
    await screen.findByLabelText('第1题整题满分'); changeScore('5');
    fireEvent.change(screen.getByLabelText('第1题节点1题号'), { target: { value: '7(2)' } }); fireEvent.change(screen.getByLabelText('练习题量'), { target: { value: '4' } });
    await switchOther(); fireEvent.click(screen.getByRole('button', { name: '取消并继续编辑' }));
    expect(screen.getByLabelText('第1题整题满分')).toHaveValue('5'); expect(screen.getByLabelText('第1题节点1题号')).toHaveValue('7(2)'); expect(screen.getByLabelText('练习题量')).toHaveValue(4);
    await switchOther(); fireEvent.click(screen.getByRole('button', { name: '保留恢复稿并离开' })); await screen.findByRole('heading', { name: '第二练习' });
    fireEvent.click(screen.getByRole('button', { name: /^固定练习\s+练习/ })); await waitFor(() => expect(screen.getByLabelText('第1题整题满分')).toHaveValue('5'));
    expect(screen.getByLabelText('第1题节点1题号')).toHaveValue('7(2)'); expect(screen.getByLabelText('练习题量')).toHaveValue(4); expect(patch).not.toHaveBeenCalled();
  });
  it('只有明确放弃才删除当前练习恢复稿，另一练习不受影响', async () => {
    render(<PracticesWorkspace initialPracticeSetId={practice.practiceSetId} services={workspace()} />); await screen.findByLabelText('第1题整题满分'); changeScore('5');
    await switchOther(); fireEvent.click(screen.getByRole('button', { name: '明确放弃修改并离开' })); await screen.findByRole('heading', { name: '第二练习' });
    expect(localStorage.getItem(recoveryKey(practice.practiceSetId))).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /^固定练习\s+练习/ })); await waitFor(() => expect(screen.getByLabelText('第1题整题满分')).toHaveValue('1'));
  });
  it.each([409, 422, 0])('保存后离开遇%s保留原上下文和稿，不执行切换', async (status) => {
    const patch = vi.fn().mockRejectedValue(new ApiError('SAVE_REJECTED', '保存失败', status, true));
    render(<PracticesWorkspace initialPracticeSetId={practice.practiceSetId} services={workspace({ patchPracticeDraft: patch })} />); await screen.findByLabelText('第1题整题满分'); changeScore('5');
    await switchOther(); fireEvent.click(screen.getByRole('button', { name: '保存成功后离开' })); await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    await screen.findByText('操作未完成，输入和原练习保持。请取消离开，在工作区处理错误或未知结果。');
    expect(screen.queryByRole('heading', { name: '第二练习' })).not.toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: '取消并继续编辑' }));
    expect(screen.getByLabelText('第1题整题满分')).toHaveValue('5');
  });
  it('固定历史切换保留恢复稿，返回当前工作区恢复', async () => {
    render(<PracticesWorkspace initialPracticeSetId={practice.practiceSetId} services={workspace()} />); await screen.findByLabelText('第1题整题满分'); changeScore('5');
    fireEvent.click(screen.getByRole('button', { name: /v1 · 草稿/ })); await screen.findByRole('dialog', { name: '处理未保存练习' });
    fireEvent.click(screen.getByRole('button', { name: '保留恢复稿并离开' })); await screen.findByText(/此处查看固定草稿/);
    expect(screen.queryByLabelText('第1题整题满分')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '当前工作区' })); await waitFor(() => expect(screen.getByLabelText('第1题整题满分')).toHaveValue('5'));
  });
});
