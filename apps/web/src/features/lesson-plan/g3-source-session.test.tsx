import React from 'react';
import { act, cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AnalysisRunView, ClassReportRow, FixedKnowledge, Page } from '@/contracts/b4';
import type { AnalysisContextInput, LessonView } from '@/contracts/lesson-plans';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
import { LessonPlanWorkspace } from './LessonPlanWorkspace';
import { defaultSourceApi } from './model/workspace-services';
import { emptyData } from './model/defaults';
import { serverSessionKey } from './model/server-cache';
import { createLessonStore } from './model/store';
import { useServerPersistence } from './model/useServerPersistence';

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router, usePathname: () => '/lesson-plans' }));
const lessonId = 'author-source-lesson', classId = 'author-source-class';
const context = (id = 'base'): AnalysisContextInput => ({ analysisRunId: `author-source-${id}`, selectedKnowledgePointIds: [`author-kp-${id}`] });
function point(id: string): FixedKnowledge { return { knowledgePointId: `author-kp-${id}`, knowledgeRevisionId: `author-kr-${id}`, name: `匿名知识点 ${id}`, role: 'primary' }; }
function report(id = 'base'): AnalysisRunView { return { runId: context(id).analysisRunId, assessmentId: `author-assessment-${id}`, subjectId: 'chinese', scoreRevisionId: `author-score-${id}`, paperRevisionId: `author-paper-${id}`, paperTitle: `固定卷 ${id}`, inputHash: `author-input-${id}`, ruleCode: 'any_loss_v1', selectionSnapshot: { selectedParticipantIds: [], uniqueStudentCount: 0, participantCount: 0, leafCount: 1, stateCounts: { recorded: 0, missing: 0, absent: 0, exempt: 0 } }, participants: [], knowledgePoints: [point(id)], job: { jobId: `author-analysis-${id}`, domain: 'teaching', kind: 'analysis', attempt: 1, state: 'succeeded', result: {}, error: null }, reportReady: true, createdAt: '2026-10-04T00:00:00Z' }; }
function row(id = 'base'): ClassReportRow { return { classId, className: null, classNameNote: '该成绩未记录班名', knowledgePoint: point(id), selectedCount: 0, validCount: 0, needsCount: 0, incompleteCount: 0, noEvidenceCount: 0, fullCreditCount: 0, numerator: 0, denominator: 0, ratio: null }; }
function lesson(version = 1, chosen: AnalysisContextInput | null = context()): LessonView {
  const mark = chosen?.analysisRunId.split('-').at(-1) ?? 'base', fixed = `author-source-fixed-${version}`;
  return { protocolVersion: 2, lessonPlanId: lessonId, subjectId: 'chinese', classId, revision: version, currentRevisionId: fixed, replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: lessonId, revisionId: fixed, version, data: { ...structuredClone(emptyData), title: '可信来源正文BASE', teachingDesign: '可信长正文', process: [{ id: 'trusted-p', stage: '可信环节', design: '可信活动', secondary: '可信二次备课' }] }, contentHash: `author-source-hash-${version}`, source: 'manual', contextSnapshot: { subjectId: 'chinese', classId, classNameAtSave: '匿名例班', analysis: chosen ? { analysisRunId: chosen.analysisRunId, inputHash: `author-input-${mark}`, scoreRevisionId: `author-score-${mark}`, paperRevisionId: `author-paper-${mark}`, className: null, classNameNote: '该成绩未记录班名', knowledgePoints: [point(mark)] } : null }, analysisRunId: chosen?.analysisRunId ?? null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-04T00:00:00Z' } };
}
function page<T>(items: T[], query: { offset?: number; limit?: number } = {}): Page<T> { return { items, total: items.length, offset: query.offset ?? 0, limit: query.limit ?? 200 }; }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((yes) => { resolve = yes; }); return { promise, resolve }; }
function mount(overrides: Partial<typeof defaultSourceApi> = {}) {
  const sources = { ...defaultSourceApi, listClasses: vi.fn(async (query) => page([], query)), taxonomy: vi.fn(async () => ({ stages: [], grades: [], subjects: [], editions: [] })), listProfiles: vi.fn(async () => []), listRuns: vi.fn(async (query) => page([report(), report('next')], query)), getRun: vi.fn(async (id) => report(id === context().analysisRunId ? 'base' : 'next')), listClassesReport: vi.fn(async (id, query) => page([row(id === context().analysisRunId ? 'base' : 'next')], query)), listPractices: vi.fn(async (query) => page([], query)), ...overrides };
  const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async (_id, body) => { const next = lesson(2, body.context); next.currentRevision.data = structuredClone(body.data); return next; });
  const api = { ...lessonPlanApi, getLesson: vi.fn(async () => lesson()), saveLesson };
  render(<NavigationPreference><LessonPlanWorkspace initialLessonPlanId={lessonId} services={{ lessonApi: api, sourceApi: sources }} /></NavigationPreference>);
  return { sources, saveLesson };
}
async function ready() { await screen.findByLabelText('课题'); fireEvent.click(screen.getByRole('button', { name: '刷新来源列表' })); await screen.findByRole('checkbox', { name: /匿名知识点 base/ }); }
async function discard() { fireEvent.change(screen.getByLabelText('课题'), { target: { value: '来源等待中的弃稿A' } }); fireEvent.click(screen.getByRole('button', { name: '学习问答' })); await act(async () => {}); fireEvent.click(screen.getByRole('button', { name: '明确放弃未保存编辑后离开' })); await act(async () => {}); }
beforeEach(() => {
  localStorage.clear(); router.push.mockClear(); router.replace.mockClear();
  Object.defineProperty(window, 'matchMedia', { configurable: true, value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })) });
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} unobserve() {} });
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.removeAttribute('open'); } });
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear(); });

describe('G3 source callbacks belong to the session that started them', () => {
  it('late report cannot clear restored BASE context or rearm saving; a fresh teacher selection remains usable', async () => {
    const late = deferred<AnalysisRunView>(); let first = true;
    const getRun = vi.fn<typeof defaultSourceApi.getRun>(async (id) => { if (id === context('next').analysisRunId && first) { first = false; return late.promise; } return report(id === context().analysisRunId ? 'base' : 'next'); });
    const { saveLesson } = mount({ getRun }); await ready();
    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: context('next').analysisRunId } }); vi.useFakeTimers(); await discard();
    expect(screen.getByLabelText('课题')).toHaveValue('可信来源正文BASE'); expect(screen.getByLabelText('固定学情报告')).toHaveValue(context().analysisRunId); expect(localStorage.getItem(serverSessionKey(lessonId))).toBeNull();
    await act(async () => late.resolve(report('next'))); await act(async () => { vi.advanceTimersByTime(2400); });
    expect(saveLesson).not.toHaveBeenCalled(); expect(localStorage.getItem(serverSessionKey(lessonId))).toBeNull(); expect(screen.getByLabelText('固定学情报告')).toHaveValue(context().analysisRunId); expect(screen.queryByRole('checkbox', { name: /匿名知识点 next/ })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: context('next').analysisRunId } }); await act(async () => {});
    fireEvent.click(screen.getByRole('checkbox', { name: /匿名知识点 next/ }));
    expect(JSON.parse(localStorage.getItem(serverSessionKey(lessonId))!).context).toEqual(context('next'));
    await act(async () => { vi.advanceTimersByTime(600); }); expect(saveLesson).toHaveBeenCalledTimes(1); expect(saveLesson.mock.calls[0][1]).toMatchObject({ context: context('next'), data: { title: '可信来源正文BASE' } });
  });
  it('discard also clears an already displayed unsaved report without hiding a subsequent fresh report', async () => {
    const { saveLesson } = mount(); await ready(); vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: context('next').analysisRunId } }); await act(async () => {}); fireEvent.click(screen.getByRole('checkbox', { name: /匿名知识点 next/ })); expect(screen.getByLabelText('固定学情报告')).toHaveValue(context('next').analysisRunId);
    await discard(); expect(screen.getByLabelText('固定学情报告')).toHaveValue(context().analysisRunId); expect(screen.queryByRole('checkbox', { name: /匿名知识点 next/ })).not.toBeInTheDocument();
    await act(async () => { vi.advanceTimersByTime(1800); }); expect(saveLesson).not.toHaveBeenCalled(); expect(localStorage.getItem(serverSessionKey(lessonId))).toBeNull();
    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: context().analysisRunId } }); await act(async () => {}); expect(screen.getByRole('checkbox', { name: /匿名知识点 base/ })).toBeChecked(); expect(localStorage.getItem(serverSessionKey(lessonId))).toBeNull();
  });
  it('after discard an old first page cannot trigger the second report page or commit partial source state', async () => {
    const late = deferred<Page<ClassReportRow>>(); const listClassesReport = vi.fn<typeof defaultSourceApi.listClassesReport>(async (id, query) => id === context('next').analysisRunId ? late.promise : page([row()], query)); const { saveLesson } = mount({ listClassesReport }); await ready();
    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: context('next').analysisRunId } }); vi.useFakeTimers(); await discard();
    await act(async () => late.resolve({ items: [row('next')], total: 2, offset: 0, limit: 200 })); await act(async () => { vi.advanceTimersByTime(1800); });
    expect(listClassesReport.mock.calls.filter((args) => args[0] === context('next').analysisRunId)).toHaveLength(1); expect(screen.getByLabelText('固定学情报告')).toHaveValue(context().analysisRunId); expect(saveLesson).not.toHaveBeenCalled(); expect(localStorage.getItem(serverSessionKey(lessonId))).toBeNull();
  });
  it('recovery-key deletion failure keeps the source operation paused until an explicit save', async () => {
    const { sources, saveLesson } = mount(); await ready(); vi.useFakeTimers(); fireEvent.change(screen.getByLabelText('课题'), { target: { value: '删除失败教师输入' } });
    const raw = localStorage.getItem(serverSessionKey(lessonId)); const removal = vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('作者受控删除失败'); });
    fireEvent.click(screen.getByRole('button', { name: '学习问答' })); await act(async () => {}); fireEvent.click(screen.getByRole('button', { name: '明确放弃未保存编辑后离开' })); await act(async () => {}); fireEvent.click(screen.getByRole('button', { name: '取消离开，继续编辑' }));
    const calls = vi.mocked(sources.getRun).mock.calls.length; fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: context('next').analysisRunId } }); await act(async () => { vi.advanceTimersByTime(1800); });
    expect(vi.mocked(sources.getRun).mock.calls).toHaveLength(calls); expect(screen.getByLabelText('固定学情报告')).toHaveValue(context().analysisRunId); expect(localStorage.getItem(serverSessionKey(lessonId))).toBe(raw); expect(saveLesson).not.toHaveBeenCalled(); expect(screen.getByLabelText('课题')).toHaveValue('删除失败教师输入');
    removal.mockRestore(); fireEvent.click(screen.getByRole('button', { name: '保存后台稿' })); await act(async () => {}); expect(saveLesson).toHaveBeenCalledTimes(1); expect(saveLesson.mock.calls[0][1]).toMatchObject({ context: context(), data: { title: '删除失败教师输入' } });
  });
  it('live session validation rejects an old captured context setter even before React renders the discard state', async () => {
    const api = { ...lessonPlanApi, saveLesson: vi.fn(), getLesson: vi.fn(async () => lesson()) }, store = createLessonStore(); const hook = renderHook(() => useServerPersistence(store, { view: lesson(), api }));
    const old = hook.result.current, identity = old.captureSession(); act(() => { store.getState().set({ title: '弃稿A' }); expect(old.discard()).toBe(true); expect(old.isCurrentSession(identity)).toBe(false); expect(old.setContext(null)).toBe(false); expect(old.setContext(null, identity)).toBe(false); });
    expect(hook.result.current.cache?.context).toEqual(context()); expect(hook.result.current.dirty).toBe(false); expect(localStorage.getItem(serverSessionKey(lessonId))).toBeNull();
    act(() => { expect(hook.result.current.setContext(context('next'), hook.result.current.captureSession())).toBe(true); }); expect(hook.result.current.cache?.context).toEqual(context('next')); expect(hook.result.current.dirty).toBe(true);
    await act(async () => {});
  });
});
