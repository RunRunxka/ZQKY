import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LessonView } from '@/contracts/lesson-plans';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { LessonPlanWorkspace } from '@/features/lesson-plan/LessonPlanWorkspace';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
import { emptyData } from '@/features/lesson-plan/model/defaults';
import { serverSessionKey } from '@/features/lesson-plan/model/server-cache';

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router, usePathname: () => '/lesson-plans' }));

function view(): LessonView {
  return { protocolVersion: 2, lessonPlanId: 'diagnostic-lesson', subjectId: 'chinese', classId: 'diagnostic-class', revision: 1, currentRevisionId: 'diagnostic-fixed', replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: 'diagnostic-lesson', revisionId: 'diagnostic-fixed', version: 1,
      data: { ...structuredClone(emptyData), title: '已保存正文' }, contentHash: 'diagnostic-hash', source: 'manual',
      contextSnapshot: { subjectId: 'chinese', classId: 'diagnostic-class', classNameAtSave: '隔离诊断班级', analysis: null },
      analysisRunId: null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-03T00:00:00Z' } };
}
function deferred<T>() { let resolve!: (result: T) => void; const promise = new Promise<T>((accept) => { resolve = accept; }); return { promise, resolve }; }
function host(api: typeof lessonPlanApi, history = false) {
  return render(<NavigationPreference><LessonPlanWorkspace initialLessonPlanId="diagnostic-lesson" initialRevisionId={history ? 'diagnostic-history' : undefined} services={{ lessonApi: api }} /></NavigationPreference>);
}

beforeEach(() => {
  localStorage.clear(); router.push.mockClear(); router.replace.mockClear();
  Object.defineProperty(window, 'matchMedia', { configurable: true, value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })) });
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} unobserve() {} });
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.removeAttribute('open'); } });
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear(); });

describe('B5 actual workspace diagnostics — pass means reproduction, not fix', () => {
  it('the explicit discard leave button grants navigation but queued autosave still transmits while Next retains the subtree', async () => {
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async (_id, body) => { const next = view(); next.revision = 2; next.currentRevisionId = 'diagnostic-fixed-2'; next.currentRevision = { ...next.currentRevision, data: body.data, revisionId: 'diagnostic-fixed-2', version: 2 }; return next; });
    const api = { ...lessonPlanApi, getLesson: vi.fn(async () => view()), saveLesson };
    host(api); await screen.findByLabelText('课题'); vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('课题'), { target: { value: '明确放弃的正文' } });
    fireEvent.click(screen.getByRole('button', { name: '学习问答' }));
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByRole('dialog', { name: '离开当前教案' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '明确放弃未保存编辑后离开' }));
    await act(async () => { await Promise.resolve(); });
    expect(router.push).toHaveBeenCalledWith('/chat');
    expect(localStorage.getItem(serverSessionKey('diagnostic-lesson'))).toBeNull();
    await act(async () => { vi.advanceTimersByTime(600); });
    expect(saveLesson).toHaveBeenCalledTimes(1);
    expect(saveLesson.mock.calls[0][1].data.title).toBe('明确放弃的正文');
  });

  it('a history-copy latest-read response overwrites teacher edits made during its awaited read', async () => {
    const response = deferred<LessonView>();
    const saved = view();
    const getLesson = vi.fn<typeof lessonPlanApi.getLesson>().mockResolvedValueOnce(saved).mockResolvedValueOnce(saved).mockImplementationOnce(() => response.promise);
    const fixed = { ...saved.currentRevision, revisionId: 'diagnostic-history', version: 0, data: { ...saved.currentRevision.data, title: '历史复制正文' } };
    const api = { ...lessonPlanApi, getLesson, getLessonRevision: vi.fn(async () => fixed) };
    host(api, true); await screen.findByLabelText('课题');
    fireEvent.click(screen.getByRole('button', { name: '打开当前版本准备复制历史正文' }));
    await screen.findByRole('button', { name: '明确复制历史正文到当前编辑' });
    fireEvent.click(screen.getByRole('button', { name: '明确复制历史正文到当前编辑' }));
    expect(getLesson).toHaveBeenCalledTimes(3);
    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('课题'), { target: { value: '等待读取时教师新输入' } });
    expect(screen.getByLabelText('课题')).toHaveValue('等待读取时教师新输入');
    await act(async () => { response.resolve(saved); });
    expect(screen.getByLabelText('课题')).toHaveValue('历史复制正文');
    expect(JSON.parse(localStorage.getItem(serverSessionKey('diagnostic-lesson'))!).data.title).toBe('历史复制正文');
    // Lost current placement is undoable, but the late read still changed the draft.
    fireEvent.click(screen.getByRole('button', { name: '撤销' }));
    expect(screen.getByLabelText('课题')).toHaveValue('等待读取时教师新输入');
  });

  it('required behavior: history copy must preserve a newer edit until the teacher reconfirms it', async () => {
    const response = deferred<LessonView>();
    const saved = view();
    const getLesson = vi.fn<typeof lessonPlanApi.getLesson>().mockResolvedValueOnce(saved).mockResolvedValueOnce(saved).mockImplementationOnce(() => response.promise);
    const fixed = { ...saved.currentRevision, revisionId: 'diagnostic-history', version: 0, data: { ...saved.currentRevision.data, title: '历史复制正文' } };
    const api = { ...lessonPlanApi, getLesson, getLessonRevision: vi.fn(async () => fixed) };
    host(api, true); await screen.findByLabelText('课题');
    fireEvent.click(screen.getByRole('button', { name: '打开当前版本准备复制历史正文' }));
    await screen.findByRole('button', { name: '明确复制历史正文到当前编辑' });
    fireEvent.click(screen.getByRole('button', { name: '明确复制历史正文到当前编辑' }));
    expect(getLesson).toHaveBeenCalledTimes(3);
    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('课题'), { target: { value: '等待读取时教师新输入' } });
    await act(async () => { response.resolve(saved); });
    expect.soft(screen.getByLabelText('课题')).toHaveValue('等待读取时教师新输入');
    expect.soft(JSON.parse(localStorage.getItem(serverSessionKey('diagnostic-lesson'))!).data.title).toBe('等待读取时教师新输入');
    expect.soft(screen.queryByRole('button', { name: '明确复制历史正文到当前编辑' })).toBeInTheDocument();
  });
});
