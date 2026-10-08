import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AssessmentsWorkspace } from './AssessmentsWorkspace';

function response(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}
const student = (id: string, name: string) => ({ id, name, studentNo: `00${id}`, revision: 1, memberships: [] });

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('已挂载施测接收真实名单操作的工作区通知', () => {
  it.each(['add', 'import', 'transfer'] as const)('%s 后刷新同班施测且保留合法勾选/出勤/人次', async (operation) => {
    const members = [student('a', '甲'), student('b', '乙')];
    const writes: { url: string; body: unknown }[] = [];
    const batch = {
      importId: 'roster-batch', classId: 'class-a', className: '一班', state: 'reviewing', revision: 1,
      fileAsset: { originalName: '名单.csv' }, headers: ['学号', '姓名'],
      mapping: { name: '姓名', studentNo: '学号' }, warnings: [], issues: [],
      rows: [{ rowNo: 1, name: '丙', studentNo: '00c', decision: null, matchedStudentId: null,
        matchedStudentName: null, suggestion: 'create', issues: [] }],
    };
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'POST') {
        const body = typeof init.body === 'string' ? JSON.parse(init.body) : 'multipart';
        writes.push({ url, body });
        if (url.endsWith('/roster-imports')) return response(batch, 201);
        if (url.endsWith('/confirm')) {
          members.push(student('c', '丙'));
          return response({ importId: batch.importId, applied: [{ rowNo: 1 }], ignored: [], replayed: false });
        }
        if (url.endsWith('/transfer')) {
          members.splice(0, 1);
          return response({ ...student('a', '甲'), revision: 2, memberships: [] });
        }
        members.push(student('c', '丙'));
        return response(student('c', '丙'), 201);
      }
      if (url.includes('/classes/class-a/students')) return response({ items: structuredClone(members), total: members.length });
      if (url.includes('/classes?')) return response({ items: ['a', 'b'].map((id) => ({
        id: `class-${id}`, name: `${id === 'a' ? '一' : '二'}班`, code: id, schoolYear: '2026', studentCount: members.length,
      })), total: 2 });
      if (url.includes('textbook-taxonomy')) return response({ grades: [], subjects: [], stages: [], editions: [] });
      if (url.endsWith('/roster-imports/roster-batch')) return response(batch);
      return response({ items: [], total: 0, offset: 0, limit: 100 });
    }));
    render(<StrictMode><AssessmentsWorkspace /></StrictMode>);
    fireEvent.click(await screen.findByTestId('assessments-class-class-a'));
    fireEvent.click(screen.getByTestId('assessments-tab-assessment'));
    await screen.findByLabelText('参测 甲');
    fireEvent.change(screen.getByLabelText('乙 出勤'), { target: { value: 'exempt' } });
    fireEvent.change(screen.getByLabelText('乙 人次序号'), { target: { value: '3' } });
    fireEvent.change(screen.getByLabelText('甲 出勤'), { target: { value: 'absent' } });
    fireEvent.change(screen.getByLabelText('甲 人次序号'), { target: { value: '2' } });
    if (operation !== 'transfer') fireEvent.click(screen.getByLabelText('参测 甲'));
    fireEvent.click(screen.getByTestId('assessments-tab-roster'));
    if (operation === 'add') {
      fireEvent.change(screen.getByLabelText('学生姓名'), { target: { value: '丙' } });
      fireEvent.change(screen.getByLabelText('学生学号'), { target: { value: '00c' } });
      fireEvent.submit(screen.getByRole('form', { name: '添加学生' }));
      await screen.findByTestId('assessments-student-c');
    } else if (operation === 'import') {
      fireEvent.change(screen.getByLabelText('名单文件'), { target: { files: [new File(['学号,姓名\n00c,丙'], '名单.csv')] } });
      fireEvent.click(screen.getByRole('button', { name: '上传名单' }));
      await screen.findByLabelText('第 1 行处理');
      fireEvent.change(screen.getByLabelText('第 1 行处理'), { target: { value: 'create' } });
      fireEvent.click(screen.getByRole('button', { name: '确认名单' }));
      await screen.findByTestId('roster-import-result');
    } else {
      fireEvent.change(screen.getByLabelText('转班学生'), { target: { value: 'a' } });
      fireEvent.change(screen.getByLabelText('转入班级'), { target: { value: 'class-b' } });
      fireEvent.click(screen.getByRole('button', { name: '确认转班' }));
      await screen.findByTestId('roster-transfer-result');
    }
    fireEvent.click(screen.getByTestId('assessments-tab-assessment'));
    if (operation === 'transfer') {
      await waitFor(() => expect(screen.queryByLabelText('参测 甲')).not.toBeInTheDocument());
      await screen.findByTestId('assessments-roster-notice');
      expect(screen.getByTestId('assessments-roster-notice')).toHaveTextContent('已撤销其参测选择及人次草稿');
      expect(writes[0].body).toMatchObject({ fromClassId: 'class-a', toClassId: 'class-b', expectedStudentRevision: 1 });
    } else {
      expect(await screen.findByLabelText('参测 丙')).toBeChecked();
      expect(screen.getByLabelText('参测 甲')).not.toBeChecked();
      expect(screen.getByLabelText('甲 出勤')).toHaveValue('absent');
      expect(screen.getByLabelText('甲 人次序号')).toHaveValue(2);
    }
    expect(screen.getByLabelText('参测 乙')).toBeChecked();
    expect(screen.getByLabelText('乙 出勤')).toHaveValue('exempt');
    expect(screen.getByLabelText('乙 人次序号')).toHaveValue(3);
    expect(writes).toHaveLength(operation === 'import' ? 2 : 1);
  });
});

/* ------------------------------------------------------------------ 状态条：名称优先 */

/** 状态条与深链测试的 fetch 桩：班级名/施测标题/原卷修订都来自真实端点形状。 */
function stubContext(assessmentTitle: string | null) {
  const deleted = assessmentTitle === null;
  const paper = {
    paperId: 'paper-1', subjectId: 'subject-1', title: '一元一次方程原卷', status: 'active',
    revision: 3, currentRevisionId: 'rev-1', currentState: 'confirmed', version: 2,
    totalScoreUnits: 10000, totalScore: '100', itemCount: 1, scoredLeafCount: 1,
    blockingIssueCount: 0, createdAt: '2026-10-01T00:00:00Z',
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/classes/class-a/students')) {
      return response({ items: [student('a', '甲')], total: 1 });
    }
    if (url.includes('/classes?')) {
      return response({ items: [{ id: 'class-a', name: '测试一班', code: 'A', schoolYear: '2026', studentCount: 1 }], total: 1 });
    }
    if (url.includes('/assessments/as-deep') || url.includes('/assessments/as-picked')) {
      if (deleted) return response({ code: 'ASSESSMENT_NOT_FOUND', message: '施测不存在' }, 404);
      return response({
        assessment: {
          assessmentId: url.includes('as-deep') ? 'as-deep' : 'as-picked',
          paperRevisionId: 'rev-1', paperId: 'paper-1', paperTitle: '一元一次方程原卷',
          title: assessmentTitle, assessmentType: 'exam', heldOn: '2026-10-01',
          state: 'open', revision: 1, classIds: ['class-a'], participantCount: 1,
        },
        participants: [],
      });
    }
    if (url.includes('/assessments?')) {
      return response({ items: [{ assessmentId: 'as-picked', title: assessmentTitle ?? '旧标题', paperRevisionId: 'rev-1',
        paperId: 'paper-1', paperTitle: '一元一次方程原卷', assessmentType: 'exam', heldOn: '2026-10-01',
        state: 'open', revision: 1, classIds: ['class-a'], participantCount: 1 }], total: 1 });
    }
    if (url.includes('/revisions/rev-1/content')) {
      return response({ paperId: 'paper-1', paperRevisionId: 'rev-1', version: 2, state: 'confirmed',
        subjectId: 'subject-1', title: '一元一次方程原卷', totalScoreUnits: 10000, totalScore: '100',
        confirmedAt: '2026-10-01T00:00:00Z', createdAt: '2026-10-01T00:00:00Z', items: [], blocks: [], issues: [] });
    }
    if (url.includes('/papers/paper-1')) return response(paper);
    if (url.includes('/papers?')) return response({ items: [paper], total: 1, offset: 0, limit: 100 });
    if (url.includes('/knowledge-points')) return response({ items: [], total: 0 });
    if (url.includes('/model-profiles')) return response([]);
    if (url.includes('/textbook-taxonomy')) return response({ grades: [], subjects: [], stages: [], editions: [] });
    return response({ items: [], total: 0, offset: 0, limit: 100 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('状态条名称化与深链回填', () => {
  it('班级/原卷/施测显示名称与版本，ID 降为小字并保留可复制文本', async () => {
    stubContext('期中考试');
    const writes: string[] = [];
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn(async (text: string) => { writes.push(text); }) },
    });
    render(<StrictMode><AssessmentsWorkspace /></StrictMode>);
    fireEvent.click(await screen.findByTestId('assessments-class-class-a'));
    expect(screen.getByTestId('assessments-context-class')).toHaveTextContent('班级：测试一班');
    // 未选择时原卷/施测给明确的空态文案，不显示 id
    expect(screen.getByTestId('assessments-context-paper')).toHaveTextContent('原卷：未选用');
    expect(screen.getByTestId('assessments-context-assessment')).toHaveTextContent('施测：未选择');

    fireEvent.click(screen.getByTestId('assessments-tab-paper'));
    fireEvent.click(await screen.findByTestId('assessments-select-paper-paper-1'));
    await waitFor(() =>
      expect(screen.getByTestId('assessments-context-paper')).toHaveTextContent('原卷：一元一次方程原卷 · v2'),
    );

    fireEvent.click(screen.getByTestId('assessments-tab-assessment'));
    fireEvent.click(await screen.findByTestId('assessments-assessment-as-picked'));
    await waitFor(() =>
      expect(screen.getByTestId('assessments-context-assessment')).toHaveTextContent('施测：期中考试'),
    );
    // ID 小字行只给短号；复制按钮写入完整 id（不是短号）
    const idLine = screen.getByTestId('assessments-context-ids');
    expect(idLine).toHaveTextContent('班级 class-a');
    expect(idLine).toHaveTextContent('原卷修订 rev-1');
    expect(idLine).toHaveTextContent('施测 as-picke…');
    fireEvent.click(screen.getByTestId('assessments-copy-ids'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toContain('classId=class-a');
    expect(writes[0]).toContain('assessmentId=as-picked');
    await waitFor(() => expect(screen.getByTestId('assessments-copy-ids')).toHaveTextContent('已复制'));
  });

  it('深链只有 id 时回读标题；回读失败回落「施测 <短号>」不伪造名称', async () => {
    stubContext('深链施测');
    const first = render(<StrictMode><AssessmentsWorkspace initialAssessmentId="as-deep" initialStep="score" /></StrictMode>);
    await waitFor(() =>
      expect(screen.getByTestId('assessments-context-assessment')).toHaveTextContent('施测：深链施测'),
    );
    first.unmount();

    cleanup();
    stubContext(null);
    render(<StrictMode><AssessmentsWorkspace initialAssessmentId="as-deep" initialStep="score" /></StrictMode>);
    await waitFor(() =>
      expect(screen.getByTestId('assessments-context-assessment')).toHaveTextContent('施测：施测 as-deep'),
    );
  });
});
