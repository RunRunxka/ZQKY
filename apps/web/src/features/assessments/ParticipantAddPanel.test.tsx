import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { AssessmentDetailView } from '@/contracts/assessments';
import { ParticipantAddPanel } from './ParticipantAddPanel';

const detail = { assessment: { assessmentId: 'as-1', revision: 3, classIds: ['c-1'] },
  participants: [{ participantId: 'p-1', studentId: 'student-1', attemptNo: 1 }] } as AssessmentDetailView;
function response(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}
function result() { return { assessment: { assessmentId: 'as-1', revision: 4 }, participants: [], replayed: false }; }
function setup(post: (body: Record<string, unknown>) => Promise<Response>) {
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'POST') { const body = JSON.parse(String(init.body)); bodies.push(body); return post(body); }
    return response(200, { items: [{ id: 'student-1', name: '甲', studentNo: '0001' }], total: 1 });
  }));
  return bodies;
}
function ui(changed = vi.fn(), refresh = vi.fn(), id = 'as-1') {
  return <StrictMode><ParticipantAddPanel key={id} detail={{ ...detail, assessment: { ...detail.assessment, assessmentId: id } }} onChanged={changed} onRefresh={refresh} /></StrictMode>;
}
async function fill() {
  await screen.findByRole('option', { name: '甲 · 学号 0001' });
  fireEvent.change(screen.getByLabelText('补录学生'), { target: { value: 'student-1' } });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('既有施测补录/补考人次', () => {
  it('StrictMode新增补考人次使用服务器学生id、独立人次和CAS，不发送姓名快照', async () => {
    const bodies = setup(async () => response(201, result()));
    const changed = vi.fn(); render(ui(changed)); await fill();
    expect(screen.getByLabelText('补录人次序号')).toHaveValue(2);
    fireEvent.change(screen.getByLabelText('补录出勤'), { target: { value: 'absent' } });
    fireEvent.click(screen.getByRole('button', { name: '新增参测人次' }));
    expect(await screen.findByTestId('participant-add-result')).toHaveTextContent('明确刷新预览');
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatchObject({ expectedRevision: 3, participants: [{ studentId: 'student-1', classId: 'c-1', attemptNo: 2, attendance: 'absent' }] });
    expect((bodies[0].participants as Record<string, unknown>[])[0]).not.toHaveProperty('nameSnapshot');
    expect(bodies[0].submissionId).toBeTruthy(); expect(changed).toHaveBeenCalledTimes(1);
  });

  it('409保留学生、人次和出勤，刷新由教师显式操作', async () => {
    setup(async () => response(409, { code: 'ASSESSMENT_REVISION_CONFLICT', message: '施测已变化', details: { currentRevision: 6 } }));
    const refresh = vi.fn(); render(ui(vi.fn(), refresh)); await fill();
    fireEvent.change(screen.getByLabelText('补录出勤'), { target: { value: 'exempt' } });
    fireEvent.click(screen.getByRole('button', { name: '新增参测人次' }));
    expect(await screen.findByTestId('participant-add-error')).toHaveTextContent('版本 6');
    expect(screen.getByLabelText('补录学生')).toHaveValue('student-1');
    expect(screen.getByLabelText('补录人次序号')).toHaveValue(2);
    expect(screen.getByLabelText('补录出勤')).toHaveValue('exempt');
    fireEvent.click(screen.getByRole('button', { name: '刷新参测对照' })); expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('历史归属422定位保留，填写依据后才能显式确认本次班级重试', async () => {
    let calls = 0;
    const bodies = setup(async () => ++calls === 1 ? response(422, { code: 'PARTICIPANT_CLASS_UNCONFIRMED', message: '需确认本班',
      details: { issues: [{ row: 0, field: 'classId', code: 'PARTICIPANT_CLASS_UNCONFIRMED', message: '核对学生归属' }] } }) : response(201, result()));
    render(ui()); await fill(); fireEvent.click(screen.getByRole('button', { name: '新增参测人次' }));
    expect(await screen.findByTestId('participant-add-error')).toHaveTextContent('classId');
    expect(screen.getByRole('button', { name: '显式确认补录班级并重试' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('补录班级确认依据'), { target: { value: '教师核对历史签到表' } });
    fireEvent.click(screen.getByRole('button', { name: '显式确认补录班级并重试' }));
    await screen.findByTestId('participant-add-result');
    expect(bodies[1]).toMatchObject({ participants: [{ classConfirmed: true, classConfirmationNote: '教师核对历史签到表' }] });
    expect(bodies[1].submissionId).not.toBe(bodies[0].submissionId);
  });

  it('响应丢失后冻结同标识与原包，不换CAS版本或人次', async () => {
    let calls = 0;
    const bodies = setup(async () => { if (++calls === 1) throw new TypeError('lost'); return response(201, { ...result(), replayed: true }); });
    render(ui()); await fill(); fireEvent.click(screen.getByRole('button', { name: '新增参测人次' }));
    await screen.findByRole('alert'); expect(screen.getByLabelText('补录人次序号')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重试原人次补录' })); await screen.findByTestId('participant-add-result');
    expect(bodies).toHaveLength(2); expect(bodies[1]).toEqual(bodies[0]);
  });

  it.each(['success', 'failure'] as const)('切施测后迟到%s不通知父级或显示旧回执', async (outcome) => {
    let complete!: (value: Response) => void;
    const gate = new Promise<Response>((resolve) => { complete = resolve; });
    const bodies = setup(() => gate); const changed = vi.fn(); const rendered = render(ui(changed));
    await fill(); fireEvent.click(screen.getByRole('button', { name: '新增参测人次' }));
    await waitFor(() => expect(bodies).toHaveLength(1)); rendered.rerender(ui(changed, vi.fn(), 'as-2'));
    await act(async () => complete(outcome === 'success' ? response(201, result()) : response(422, { code: 'OLD_ERROR', message: '旧施测错误' })));
    expect(changed).not.toHaveBeenCalled(); expect(screen.queryByTestId('participant-add-result')).not.toBeInTheDocument();
    expect(screen.queryByTestId('participant-add-error')).not.toBeInTheDocument(); expect(screen.getByLabelText('补录学生')).toHaveValue('');
  });

  it('补录班级下拉显示班名；名称读取失败回落短号并提示', async () => {
    const stubClasses = (handler: () => Response) =>
      vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/classes?')) return handler();
        return response(200, { items: [{ id: 'student-1', name: '甲', studentNo: '0001' }], total: 1 });
      }));
    stubClasses(() => response(200, { items: [{ id: 'c-1', name: '七一班' }], total: 1 }));
    const first = render(ui());
    expect(await screen.findByRole('option', { name: '七一班' })).toHaveValue('c-1');
    first.unmount();
    cleanup();

    // 映射读取失败：回落短号 + 明确提示（不把失败当空目录）
    stubClasses(() => response(503, { code: 'SERVICE_UNAVAILABLE', message: '班级列表不可用' }));
    render(ui());
    expect(await screen.findByRole('option', { name: 'c-1' })).toHaveValue('c-1');
    expect(screen.getByText('班级名称读取失败，下拉暂显示班级短号；不影响补录本身。')).toBeInTheDocument();
  });
});
