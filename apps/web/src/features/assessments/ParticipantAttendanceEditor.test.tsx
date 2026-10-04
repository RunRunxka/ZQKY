import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { AssessmentParticipantView } from '@/contracts/assessments';
import { ParticipantAttendanceEditor } from './ParticipantAttendanceEditor';

const participant: AssessmentParticipantView = {
  participantId: 'p-1', studentId: 'student-1', studentNoSnapshot: '0001', nameSnapshot: '甲',
  classId: 'c-1', attemptNo: 2, attendance: 'present', classConfirmed: true,
  classConfirmationNote: '教师确认', classConfirmationAt: '2026-10-02T00:00:00Z',
};

function response(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}
function result() {
  return { assessment: { assessmentId: 'as-1', revision: 4 }, participants: [{ ...participant, attendance: 'absent' }], replayed: false };
}
function ui(changed = vi.fn(), refresh = vi.fn(), id = 'p-1') {
  return <StrictMode><ParticipantAttendanceEditor key={id} assessmentId="as-1"
    participant={{ ...participant, participantId: id }} revision={3} onChanged={changed} onRefresh={refresh} /></StrictMode>;
}
function editAndSave() {
  fireEvent.change(screen.getByLabelText('甲 人次 2 校正出勤'), { target: { value: 'absent' } });
  fireEvent.change(screen.getByLabelText('甲 人次 2 出勤校正理由'), { target: { value: '实际缺考，核对签到表' } });
  fireEvent.click(screen.getByRole('button', { name: '保存出勤校正' }));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('参测人次出勤校正', () => {
  it('StrictMode 只提交一次，带当前CAS版本、理由和冻结标识，成功提示明确刷新预览', async () => {
    const fetched = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toContain('/participants/p-1/attendance');
      expect(init?.method).toBe('PATCH');
      return response(200, result());
    });
    vi.stubGlobal('fetch', fetched);
    const changed = vi.fn();
    render(ui(changed));
    editAndSave();
    await screen.findByRole('status');
    expect(fetched).toHaveBeenCalledTimes(1);
    const body = JSON.parse(String(fetched.mock.calls[0]?.[1]?.body));
    expect(body).toMatchObject({ attendance: 'absent', expectedRevision: 3, reason: '实际缺考，核对签到表' });
    expect(body.submissionId).toBeTruthy();
    expect(changed).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('status')).toHaveTextContent('明确刷新预览');
  });

  it('409保留出勤和理由，展示当前版本并提供显式刷新', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response(409, { code: 'ASSESSMENT_REVISION_CONFLICT',
      message: '施测已变化', details: { currentRevision: 5 } })));
    const changed = vi.fn();
    const refresh = vi.fn();
    render(ui(changed, refresh));
    editAndSave();
    const error = await screen.findByRole('alert');
    expect(error).toHaveTextContent('当前版本 5');
    expect(screen.getByLabelText('甲 人次 2 校正出勤')).toHaveValue('absent');
    expect(screen.getByLabelText('甲 人次 2 出勤校正理由')).toHaveValue('实际缺考，核对签到表');
    fireEvent.click(screen.getByRole('button', { name: '刷新出勤对照' }));
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(changed).not.toHaveBeenCalled();
  });

  it('响应丢失后锁住编辑，重试同submissionId与原payload', async () => {
    const bodies: unknown[] = [];
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      bodies.push(JSON.parse(String(init?.body)));
      if (bodies.length === 1) throw new TypeError('connection lost');
      return response(200, { ...result(), replayed: true });
    }));
    render(ui());
    editAndSave();
    await screen.findByRole('alert');
    expect(screen.getByLabelText('甲 人次 2 出勤校正理由')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重试原出勤校正' }));
    await screen.findByRole('status');
    expect(bodies).toHaveLength(2);
    expect(bodies[1]).toEqual(bodies[0]);
  });

  it.each(['success', 'failure'] as const)('切人次后迟到%s不更新新上下文', async (outcome) => {
    let complete!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => { complete = resolve; });
    const fetched = vi.fn(() => pending);
    vi.stubGlobal('fetch', fetched);
    const changed = vi.fn();
    const rendered = render(ui(changed));
    editAndSave();
    await waitFor(() => expect(fetched).toHaveBeenCalledTimes(1));
    rendered.rerender(ui(changed, vi.fn(), 'p-2'));
    await act(async () => complete(outcome === 'success' ? response(200, result())
      : response(422, { code: 'ATTENDANCE_INVALID', message: '旧人次失败' })));
    expect(changed).not.toHaveBeenCalled();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByLabelText('甲 人次 2 出勤校正理由')).toHaveValue('');
  });
});
