import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AssessmentsWorkspace } from '@/features/assessments/AssessmentsWorkspace';

function response(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}
const student = (id: string, name: string) => ({ id, name, studentNo: `00${id}`, revision: 1, memberships: [] });
const loadingText = '正在刷新参测名单，已有合法人次草稿保留。';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('R06 controlled roster readiness, retaining every original workspace assertion', () => {
  it.each(['add', 'import', 'transfer'] as const)('%s 后刷新同班施测且保留合法勾选/出勤/人次', async (operation) => {
    const members = [student('a', '甲'), student('b', '乙')];
    const writes: { url: string; body: unknown }[] = [];
    const gates: { release: () => void; url: string }[] = [];
    const observation: Record<string, unknown> = { operation, serviceDoubles: true, controlledDelay: 'Promise gate, no timed sleep or repeated trial' };
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
      if (url.includes('/classes/class-a/students')) {
        const body = { items: structuredClone(members), total: members.length };
        if (writes.length > 0) {
          await new Promise<void>((resolve) => gates.push({ release: resolve, url }));
        }
        return response(body);
      }
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
      // The original positive roster read needs the gate released first.
      await waitFor(() => expect(gates.length).toBeGreaterThanOrEqual(2));
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
    await waitFor(() => expect(gates.length).toBeGreaterThanOrEqual(2));
    // Real workspace/hooks continue rendering the previous same-key data while these reads are pending.
    expect(screen.getByText(loadingText)).toBeInTheDocument();
    expect(screen.getByLabelText('参测 乙')).toBeChecked();
    expect(screen.getByLabelText('乙 出勤')).toHaveValue('exempt');
    expect(screen.getByLabelText('乙 人次序号')).toHaveValue(3);
    expect(screen.getByLabelText('甲 出勤')).toHaveValue('absent');
    expect(screen.getByLabelText('甲 人次序号')).toHaveValue(2);
    if (operation === 'transfer') expect(screen.getByLabelText('参测 甲')).toBeChecked();
    else expect(screen.getByLabelText('参测 甲')).not.toBeChecked();
    observation.pending = { gatedReads: gates.length, alphaPresent: Boolean(screen.queryByLabelText('参测 甲')),
      noticePresent: Boolean(screen.queryByTestId('assessments-roster-notice')), loadingPresent: Boolean(screen.queryByText(loadingText)) };
    console.info('R06_PENDING', JSON.stringify(observation));

    // Start the original negative wait while reads are genuinely pending. Capture its FIRST success,
    // before any new positive notice wait can make the original timing appear safe.
    const originalNegative = operation === 'transfer' ? waitFor(() => {
      expect(screen.queryByLabelText('参测 甲')).not.toBeInTheDocument();
      if (!observation.negativeFirstSuccess) observation.negativeFirstSuccess = {
        noticePresent: Boolean(screen.queryByTestId('assessments-roster-notice')),
        loadingPresent: Boolean(screen.queryByText(loadingText)),
        betaPresent: Boolean(screen.queryByLabelText('参测 乙')),
      };
    }) : null;
    for (const gate of gates) gate.release();
    if (operation === 'transfer') {
      await originalNegative;
      observation.afterNegativeReturned = { noticePresent: Boolean(screen.queryByTestId('assessments-roster-notice')),
        loadingPresent: Boolean(screen.queryByText(loadingText)) };
      console.info('R06_NEGATIVE_RETURNED', JSON.stringify(observation));
      // Diagnostic synchronization only; the original notice/payload and surviving draft assertions below remain exact.
      await screen.findByTestId('assessments-roster-notice');
      expect(screen.getByTestId('assessments-roster-notice')).toHaveTextContent('已撤销其参测选择及人次草稿');
      expect(writes[0].body).toMatchObject({ fromClassId: 'class-a', toClassId: 'class-b', expectedStudentRevision: 1 });
      expect(screen.queryByLabelText('甲 出勤')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('甲 人次序号')).not.toBeInTheDocument();
      expect(screen.getByRole('form', { name: '新建施测' })).toHaveTextContent('参测 1 人次');
    } else {
      if (operation === 'add') await screen.findByTestId('assessments-student-c');
      expect(await screen.findByLabelText('参测 丙')).toBeChecked();
      expect(screen.getByLabelText('参测 甲')).not.toBeChecked();
      expect(screen.getByLabelText('甲 出勤')).toHaveValue('absent');
      expect(screen.getByLabelText('甲 人次序号')).toHaveValue(2);
      expect(screen.getByRole('form', { name: '新建施测' })).toHaveTextContent('参测 2 人次');
    }
    expect(screen.getByLabelText('参测 乙')).toBeChecked();
    expect(screen.getByLabelText('乙 出勤')).toHaveValue('exempt');
    expect(screen.getByLabelText('乙 人次序号')).toHaveValue(3);
    expect(writes).toHaveLength(operation === 'import' ? 2 : 1);
    observation.final = { alphaPresent: Boolean(screen.queryByLabelText('参测 甲')), betaChecked: true,
      betaAttendance: 'exempt', betaAttemptNo: 3, noticePresent: Boolean(screen.queryByTestId('assessments-roster-notice')),
      loadingPresent: Boolean(screen.queryByText(loadingText)), writeCount: writes.length, allOriginalSemanticAssertionsPassed: true };
    console.info('R06_FINAL', JSON.stringify(observation));
  });
});
