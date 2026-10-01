import { afterEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AssessmentsPanel } from '@/features/assessments/AssessmentsPanel';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('unmounted old class/paper form still switches parent selection when create response arrives', async () => {
  let complete!: (response: Response) => void;
  const responseGate = new Promise<Response>((resolve) => { complete = resolve; });
  const result = { assessment: { assessmentId: 'old-assessment', revision: 1 },
                   participants: [] };
  const fetched = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'POST') return responseGate;
    const url = String(input);
    return { ok: true, status: 200, json: async () => url.includes('/students')
      ? { items: [{ id: 'student-old', name: '甲', studentNo: '0001' }], total: 1 }
      : { items: [], total: 0 } } as Response;
  });
  vi.stubGlobal('fetch', fetched);
  const select = vi.fn();
  const changed = vi.fn();
  const ui = render(<AssessmentsPanel
    selectedPaper={{ paperId: 'old-paper', paperRevisionId: 'old-paper-revision', title: '旧卷',
                     scoredLeafCount: 1, totalScoreUnits: 100 }}
    classId="old-class" className="旧班" selectedAssessmentId={null}
    onSelectAssessment={select} onOpenScore={() => {}} refreshToken={0} onChanged={changed} />);
  await screen.findByLabelText('参测 甲');
  fireEvent.change(screen.getByLabelText('施测标题'), { target: { value: '旧班旧卷施测' } });
  fireEvent.submit(screen.getByRole('form', { name: '新建施测' }));
  await waitFor(() => expect(fetched.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(true));
  ui.unmount(); // Real workspace class/paper key change unmounts this form.
  await act(async () => {
    complete({ ok: true, status: 201, json: async () => result } as Response);
  });
  expect(select).toHaveBeenCalledWith('old-assessment');
  expect(changed).toHaveBeenCalledTimes(1);
});
