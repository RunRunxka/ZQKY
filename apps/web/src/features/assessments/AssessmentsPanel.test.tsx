import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { AssessmentView } from '@/contracts/assessments';
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
    selectedPaper={{ paperId: key, paperRevisionId: `${key}-revision`, title: key, version: 1,
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
    expect(select).toHaveBeenCalledExactlyOnceWith('created-assessment', '期中');
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

/* ------------------------------------------------------------------ 归档 / 过滤 / 移除人次 */

function assessment(overrides: Partial<AssessmentView> = {}): AssessmentView {
  return {
    assessmentId: 'as-open', paperRevisionId: 'old-revision', paperId: 'paper-1',
    paperTitle: '原卷', subjectId: 'subject-1', title: '期中', assessmentType: 'exam',
    heldOn: '2026-10-01', state: 'open', revision: 2, classIds: ['old-class'],
    participantCount: 1, createdAt: '2026-10-01T00:00:00Z', ...overrides,
  };
}

function participant(id: string, name: string, attemptNo = 1) {
  return {
    participantId: id, studentId: `student-${id}`, studentNoSnapshot: `00${id}`,
    nameSnapshot: name, classId: 'old-class', attemptNo, attendance: 'present',
    classConfirmed: false, classConfirmationNote: null, classConfirmationAt: null,
  };
}

describe('施测归档、已归档过滤与移除人次', () => {
  it('默认隐藏已归档施测；开关显示全部，归档/恢复各用自己的 revision', async () => {
    const writes: { url: string; body: unknown }[] = [];
    const reads: string[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'POST') {
        writes.push({ url, body: JSON.parse(String(init.body)) });
        if (url.endsWith('/assessments/as-open/archive')) {
          return response(200, assessment({ state: 'archived', revision: 3 }));
        }
        return response(200, assessment({ assessmentId: 'as-arch', title: '月考', revision: 6 }));
      }
      if (url.includes('/assessments?')) {
        reads.push(url);
        return response(200, {
          items: [
            assessment(),
            assessment({ assessmentId: 'as-arch', title: '月考', state: 'archived', revision: 5 }),
          ],
          total: 2, offset: 0, limit: 100,
        });
      }
      if (url.includes('/students')) {
        return response(200, { items: [{ id: 'student-1', name: '甲', studentNo: '0001' }], total: 1 });
      }
      return response(200, { items: [], total: 0, offset: 0, limit: 100 });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(panel('old'));
    await screen.findByTestId('assessments-assessment-as-open');
    expect(screen.queryByTestId('assessments-assessment-as-arch')).not.toBeInTheDocument();
    expect(screen.getByTestId('assessments-archived-hidden')).toBeInTheDocument();

    const confirmSpy = vi.fn(() => true);
    vi.stubGlobal('confirm', confirmSpy);
    const before = reads.length;
    fireEvent.click(screen.getByTestId('assessments-assessment-archive-as-open'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(writes[0]).toEqual({
      url: '/api/v1/assessments/as-open/archive',
      body: { expectedRevision: 2 },
    });
    await waitFor(() => expect(reads.length).toBeGreaterThan(before));

    fireEvent.click(screen.getByLabelText('显示已归档施测'));
    await screen.findByTestId('assessments-assessment-as-arch');
    expect(screen.getByTestId('assessments-assessment-archived-as-arch')).toHaveTextContent('已归档');
    fireEvent.click(screen.getByTestId('assessments-assessment-restore-as-arch'));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1]).toEqual({
      url: '/api/v1/assessments/as-arch/restore',
      body: { expectedRevision: 5 },
    });
  });

  it('移除人次成功用返回的 participants 刷新展示', async () => {
    const deletes: string[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'DELETE') {
        deletes.push(url);
        return response(200, {
          assessment: assessment({ revision: 5, participantCount: 1 }),
          participants: [participant('p-2', '乙')],
          replayed: false,
        });
      }
      if (url.includes('/assessments?')) {
        return response(200, { items: [assessment()], total: 1, offset: 0, limit: 100 });
      }
      if (url.includes('/assessments/as-open')) {
        return response(200, {
          assessment: assessment({ revision: 4, participantCount: 2 }),
          participants: [participant('p-1', '甲'), participant('p-2', '乙')],
        });
      }
      if (url.includes('/students')) return response(200, { items: [], total: 0 });
      return response(200, { items: [], total: 0, offset: 0, limit: 100 });
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('confirm', vi.fn(() => true));
    render(panel('old', vi.fn(), vi.fn(), 'as-open'));
    await screen.findByTestId('assessments-detail-participant-p-1');
    fireEvent.click(screen.getByTestId('assessments-remove-participant-p-1'));
    await waitFor(() => expect(deletes).toHaveLength(1));
    expect(deletes[0]).toBe('/api/v1/assessments/as-open/participants/p-1?expectedRevision=4');
    await waitFor(() =>
      expect(screen.queryByTestId('assessments-detail-participant-p-1')).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId('assessments-detail-participant-p-2')).toBeInTheDocument();
    expect(screen.getByTestId('assessments-participant-removed')).toHaveTextContent('已移除人次：甲');
  });

  it('移除人次 409 原样显示服务端 message 且不改变列表', async () => {
    const message = '该人次已有学情报告引用，不能移除。';
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'DELETE') {
        return response(409, { code: 'PARTICIPANT_REMOVE_BLOCKED', message });
      }
      if (url.includes('/assessments?')) {
        return response(200, { items: [assessment()], total: 1, offset: 0, limit: 100 });
      }
      if (url.includes('/assessments/as-open')) {
        return response(200, {
          assessment: assessment({ revision: 4, participantCount: 1 }),
          participants: [participant('p-1', '甲')],
        });
      }
      if (url.includes('/students')) return response(200, { items: [], total: 0 });
      return response(200, { items: [], total: 0, offset: 0, limit: 100 });
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('confirm', vi.fn(() => true));
    render(panel('old', vi.fn(), vi.fn(), 'as-open'));
    await screen.findByTestId('assessments-detail-participant-p-1');
    fireEvent.click(screen.getByTestId('assessments-remove-participant-p-1'));
    const alert = await screen.findByTestId('assessments-remove-error-p-1');
    expect(alert).toHaveTextContent(message);
    expect(screen.getByTestId('assessments-detail-participant-p-1')).toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ 详情区名称与彻底删除 */

function detailStub(
  mutate: (url: string, init: RequestInit) => Response | null,
  detailAssessment: Partial<AssessmentView> = {},
) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const handled = mutate(url, init ?? {});
    if (handled) return handled;
    if (url.includes('/assessments?')) {
      return response(200, { items: [assessment(detailAssessment)], total: 1, offset: 0, limit: 100 });
    }
    if (url.includes('/assessments/as-open')) {
      return response(200, {
        assessment: assessment({ revision: 4, participantCount: 1, ...detailAssessment }),
        participants: [participant('p-1', '甲')],
      });
    }
    if (url.includes('/students')) return response(200, { items: [], total: 0 });
    return response(200, { items: [], total: 0, offset: 0, limit: 100 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('施测详情区：名称优先与彻底删除（受引用守卫的三态）', () => {
  it('详情 chips 显示原卷标题与编辑版本，不再显示 revision id', async () => {
    detailStub(() => null, { paperTitle: '一元一次方程原卷' });
    render(panel('old', vi.fn(), vi.fn(), 'as-open'));
    const detail = await screen.findByTestId('assessments-detail-as-open');
    expect(detail).toHaveTextContent('原卷 一元一次方程原卷');
    expect(detail).toHaveTextContent('编辑版本 r4');
    expect(detail).not.toHaveTextContent('原卷修订');
    expect(detail).not.toHaveTextContent('old-revision');
  });

  it('删除成功：DELETE 用详情 revision，取消选择并给回执', async () => {
    const deletes: string[] = [];
    vi.stubGlobal('confirm', vi.fn(() => true));
    const select = vi.fn();
    detailStub((url, init) => {
      if (init.method === 'DELETE' && url.includes('/assessments/as-open')) {
        deletes.push(url);
        return response(200, { deleted: true, assessmentId: 'as-open' });
      }
      return null;
    });
    render(panel('old', select, vi.fn(), 'as-open'));
    await screen.findByTestId('assessments-detail-participant-p-1');
    fireEvent.click(screen.getByTestId('assessments-detail-delete-as-open'));
    await waitFor(() => expect(deletes).toHaveLength(1));
    expect(deletes[0]).toBe('/api/v1/assessments/as-open?expectedRevision=4');
    expect(await screen.findByTestId('assessments-detail-delete-notice')).toHaveTextContent(
      '已彻底删除施测「期中」',
    );
    expect(select).toHaveBeenCalledWith(null);
  });

  it('ASSESSMENT_IN_USE 409：逐项列出引用计数，「改为归档」走归档端点', async () => {
    const message = '施测仍被引用，不能删除（成绩版本 1 条、学情报告 1 条）；请先处理相关数据。';
    const writes: { url: string; body: unknown }[] = [];
    vi.stubGlobal('confirm', vi.fn(() => true));
    detailStub((url, init) => {
      if (init.method === 'DELETE' && url.includes('/assessments/as-open')) {
        return response(409, {
          code: 'ASSESSMENT_IN_USE',
          message,
          details: { counts: { scoreRevisions: 1, scoreImports: 0, analysisRuns: 1, practiceConversions: 0 } },
        });
      }
      if (init.method === 'POST' && url.endsWith('/assessments/as-open/archive')) {
        writes.push({ url, body: JSON.parse(String(init.body)) });
        return response(200, assessment({ state: 'archived', revision: 5 }));
      }
      return null;
    });
    render(panel('old', vi.fn(), vi.fn(), 'as-open'));
    await screen.findByTestId('assessments-detail-participant-p-1');
    fireEvent.click(screen.getByTestId('assessments-detail-delete-as-open'));
    const guard = await screen.findByTestId('assessments-detail-delete-guard');
    expect(guard).toHaveTextContent(message);
    expect(guard).toHaveTextContent('成绩版本 1 条');
    expect(guard).toHaveTextContent('学情报告 1 条');
    expect(guard).not.toHaveTextContent('成绩导入批次');
    expect(guard).not.toHaveTextContent('练习转换');
    // 被拒绝不改变参测人次列表
    expect(screen.getByTestId('assessments-detail-participant-p-1')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('assessments-detail-delete-guard-archive'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toEqual({
      url: '/api/v1/assessments/as-open/archive',
      body: { expectedRevision: 4 },
    });
  });
});
