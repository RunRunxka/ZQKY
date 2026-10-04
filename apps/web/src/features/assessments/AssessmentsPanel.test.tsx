import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AssessmentsPanel } from './AssessmentsPanel';

function response(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((complete) => { resolve = complete; });
  return { promise, resolve };
}

function creation(assessmentId = 'created-assessment') {
  return { assessment: { assessmentId, title: '期中', revision: 1 }, participants: [], replayed: false };
}

function setupFetch(post: (init: RequestInit) => Promise<Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'POST') return post(init);
    if (String(input).endsWith('/assessments/selected-existing')) return response(200, {
      assessment: { assessmentId: 'selected-existing', participantCount: 0, revision: 1 }, participants: [],
    });
    const body = String(input).includes('/students')
      ? { items: [{ id: 'student-1', name: '甲', studentNo: '0001' }], total: 1 }
      : { items: [], total: 0 };
    return response(200, body);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function panel(key: string, select = vi.fn(), changed = vi.fn(), selectedAssessmentId: string | null = null) {
  return <StrictMode><AssessmentsPanel key={key}
    selectedPaper={{ paperId: key, paperRevisionId: `${key}-revision`, title: key,
      scoredLeafCount: 1, totalScoreUnits: 100 }}
    classId={`${key}-class`} className={key} selectedAssessmentId={selectedAssessmentId}
    onSelectAssessment={select} onOpenScore={() => {}} refreshToken={0} onChanged={changed} />
  </StrictMode>;
}

async function submit() {
  await screen.findByLabelText('参测 甲');
  fireEvent.change(screen.getByLabelText('施测标题'), { target: { value: '期中' } });
  fireEvent.submit(screen.getByRole('form', { name: '新建施测' }));
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('创建施测只提交当前上下文的有效结果', () => {
  it('StrictMode 下正常创建只选择一次，出勤和人次按教师输入发送', async () => {
    const fetchMock = setupFetch(async () => response(201, creation()));
    const select = vi.fn();
    const changed = vi.fn();
    render(panel('old', select, changed));
    await screen.findByLabelText('参测 甲');
    fireEvent.change(screen.getByLabelText('甲 出勤'), { target: { value: 'absent' } });
    fireEvent.change(screen.getByLabelText('甲 人次序号'), { target: { value: '2' } });
    await submit();
    await screen.findByTestId('assessments-create-result');
    expect(select).toHaveBeenCalledExactlyOnceWith('created-assessment');
    expect(changed).toHaveBeenCalledTimes(1);
    const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST');
    expect(posts).toHaveLength(1);
    expect(JSON.parse(String(posts[0][1]?.body))).toMatchObject({
      paperRevisionId: 'old-revision', classIds: ['old-class'],
      participants: [{ studentId: 'student-1', attendance: 'absent', attemptNo: 2 }],
    });
  });

  it.each(['success', 'failure'] as const)('卸载后迟到 %s 不更新父级', async (outcome) => {
    const gate = deferred<Response>();
    const fetchMock = setupFetch(() => gate.promise);
    const select = vi.fn();
    const changed = vi.fn();
    const ui = render(panel('old', select, changed));
    await submit();
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1));
    ui.unmount();
    await act(async () => gate.resolve(outcome === 'success'
      ? response(201, creation('old-assessment'))
      : response(422, { code: 'PARTICIPANT_CLASS_UNCONFIRMED', message: '旧班级不匹配' })));
    expect(select).not.toHaveBeenCalled();
    expect(changed).not.toHaveBeenCalled();
  });

  it.each(['class', 'paper'] as const)('切换 %s 重挂载后迟到成功不覆盖新选择', async (context) => {
    const gate = deferred<Response>();
    const fetchMock = setupFetch(() => gate.promise);
    const select = vi.fn();
    const changed = vi.fn();
    const ui = render(panel('old', select, changed));
    await submit();
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1));
    // 工作区使用班级/原卷修订 key，切换任一项使旧面板失效。
    ui.rerender(panel(`new-${context}`, select, changed));
    await screen.findByLabelText('参测 甲');
    await act(async () => gate.resolve(response(201, creation('old-assessment'))));
    expect(select).not.toHaveBeenCalled();
    expect(changed).not.toHaveBeenCalled();
    expect(screen.queryByTestId('assessments-create-result')).not.toBeInTheDocument();
    expect(screen.getByLabelText('施测标题')).toHaveValue('');
  });

  it('明确 422 保留表单与参测编辑，不选择失败结果', async () => {
    setupFetch(async () => response(422, { code: 'INVALID_TITLE', message: '标题不合法' }));
    const select = vi.fn();
    const changed = vi.fn();
    render(panel('old', select, changed));
    await submit();
    await screen.findByTestId('assessments-create-error');
    expect(screen.getByLabelText('施测标题')).toHaveValue('期中');
    expect(screen.getByLabelText('参测 甲')).toBeChecked();
    expect(select).not.toHaveBeenCalled();
    expect(changed).not.toHaveBeenCalled();
  });

  it('同班同卷改选已有施测后，旧创建成功不能覆盖教师选择', async () => {
    const gate = deferred<Response>();
    const fetched = setupFetch(() => gate.promise);
    const select = vi.fn(); const changed = vi.fn();
    const rendered = render(panel('old', select, changed));
    await submit();
    await waitFor(() => expect(fetched.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1));
    rendered.rerender(panel('old', select, changed, 'selected-existing'));
    await act(async () => gate.resolve(response(201, creation('old-assessment'))));
    expect(select).not.toHaveBeenCalled(); expect(changed).not.toHaveBeenCalled();
    expect(screen.queryByTestId('assessments-create-result')).not.toBeInTheDocument();
  });
});
