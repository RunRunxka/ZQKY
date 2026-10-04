import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AnalysisRunView, ClassReportRow, FixedKnowledge, Page } from '@/contracts/b4';
import type { LessonView } from '@/contracts/lesson-plans';
import type { ModelProfileView } from '@/contracts/model-settings';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
import { LessonPlanWorkspace } from './LessonPlanWorkspace';
import { defaultSourceApi } from './model/workspace-services';
import { emptyData } from './model/defaults';
import { serverSessionKey } from './model/server-cache';

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router, usePathname: () => '/lesson-plans' }));
const lessonId = 'b6-metadata-document', classId = 'b6-metadata-class', runId = 'b6-metadata-report';
const point: FixedKnowledge = { knowledgePointId: 'b6-metadata-kp', knowledgeRevisionId: 'b6-metadata-kr', name: '匿名固定知识点', role: 'primary' };
const report: AnalysisRunView = { runId, assessmentId: 'b6-metadata-assessment', subjectId: 'chinese',
  scoreRevisionId: 'b6-metadata-score', paperRevisionId: 'b6-metadata-paper', paperTitle: '匿名固定卷', inputHash: 'b6-metadata-input',
  ruleCode: 'any_loss_v1', selectionSnapshot: { selectedParticipantIds: [], uniqueStudentCount: 0, participantCount: 0,
    leafCount: 1, stateCounts: { recorded: 0, missing: 0, absent: 0, exempt: 0 } }, participants: [], knowledgePoints: [point],
  job: { jobId: 'b6-metadata-job', domain: 'teaching', kind: 'analysis', attempt: 1, state: 'succeeded', result: {}, error: null },
  reportReady: true, createdAt: '2026-10-04T00:00:00Z' };
const classRow: ClassReportRow = { classId, className: null, classNameNote: '该成绩未记录班名', knowledgePoint: point,
  selectedCount: 0, validCount: 0, needsCount: 0, incompleteCount: 0, noEvidenceCount: 0, fullCreditCount: 0,
  numerator: 0, denominator: 0, ratio: null };
const view: LessonView = { protocolVersion: 2, lessonPlanId: lessonId, subjectId: 'chinese', classId, revision: 1,
  currentRevisionId: 'b6-metadata-fixed', replayed: false, currentRevision: { protocolVersion: 2, lessonPlanId: lessonId,
    revisionId: 'b6-metadata-fixed', version: 1, data: { ...structuredClone(emptyData), title: 'B6已保存可信正文' },
    contentHash: 'b6-metadata-hash', source: 'manual', contextSnapshot: { subjectId: 'chinese', classId,
      classNameAtSave: '匿名班级', analysis: { analysisRunId: runId, inputHash: report.inputHash, scoreRevisionId: report.scoreRevisionId,
        paperRevisionId: report.paperRevisionId, className: null, classNameNote: '该成绩未记录班名', knowledgePoints: [point] } },
    analysisRunId: runId, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [],
    reviewState: 'unreviewed', createdAt: '2026-10-04T00:00:00Z' } };
function profile(label = '正常模型'): ModelProfileView { return { id: label, connectionId: 'b6-metadata-connection', displayName: label,
  modelId: 'b6-fixture-model', purpose: 'chat', contextTokens: null, maxOutputTokens: 20000, supportedParams: [],
  reasoningEnabled: null, reasoningEffort: null, reasoningStyle: null, capabilities: { chat: 'claimed' }, connection: null,
  createdAt: '2026-10-04T00:00:00Z', updatedAt: '2026-10-04T00:00:00Z' }; }
function page<T>(items: T[], query: { offset?: number; limit?: number } = {}): Page<T> {
  return { items, total: items.length, offset: query.offset ?? 0, limit: query.limit ?? 200 };
}
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; }
function mount(overrides: Partial<typeof defaultSourceApi> = {}) {
  const sources = { ...defaultSourceApi, listClasses: vi.fn(async query => page([], query)),
    taxonomy: vi.fn(async () => ({ stages: [], subjects: [{ id: 'chinese', label: '语文' }],
      grades: [{ id: 'b6-grade', label: '正常年级', stageId: 'primary' }], editions: [{ id: 'b6-edition', label: '正常版本' }] })),
    listProfiles: vi.fn(async () => [profile()]), listRuns: vi.fn(async query => page([report], query)),
    getRun: vi.fn(async () => report), listClassesReport: vi.fn(async (_id, query) => page([classRow], query)),
    listPractices: vi.fn(async query => page([], query)), ...overrides };
  const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>();
  render(<NavigationPreference><LessonPlanWorkspace initialLessonPlanId={lessonId} initialAnalysisRunId={runId}
    services={{ lessonApi: { ...lessonPlanApi, getLesson: vi.fn(async () => structuredClone(view)), saveLesson }, sourceApi: sources }} /></NavigationPreference>);
  return { sources, saveLesson };
}
async function open() {
  await screen.findByDisplayValue('B6已保存可信正文'); await act(async () => {});
  const details = screen.getByText('班级、固定学情与生成来源').closest('details')!;
  details.open = true; fireEvent(details, new Event('toggle'));
  await act(async () => {});
}
function expectMetadata(label = '正常模型') {
  expect(screen.getByRole('option', { name: `${label} · b6-fixture-model` })).toBeInTheDocument();
  expect(screen.getByRole('option', { name: '正常年级' })).toBeInTheDocument();
  expect(screen.getByRole('option', { name: '正常版本' })).toBeInTheDocument();
  expect(screen.queryByText('正在读取真实来源…')).not.toBeInTheDocument();
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

describe('B6 source metadata and teacher selection have independent read ownership', () => {
  it('opened metadata completes after an explicit report read and releases loading', async () => {
    const late = deferred<ModelProfileView[]>(); const { sources, saveLesson } = mount({ listProfiles: vi.fn(() => late.promise) }); await open();
    const initialRecovery = localStorage.getItem(serverSessionKey(lessonId)); expect(initialRecovery).toBeNull();
    expect(screen.getByText('正在读取真实来源…')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: runId } });
    await screen.findByRole('checkbox', { name: /匿名固定知识点/ });
    const reportCalls = vi.mocked(sources.getRun).mock.calls.length;
    await act(async () => late.resolve([profile()]));
    expectMetadata(); expect(screen.getByLabelText('固定学情报告')).toHaveValue(runId);
    expect(screen.getByRole('checkbox', { name: /匿名固定知识点/ })).toBeChecked();
    expect(vi.mocked(sources.getRun).mock.calls).toHaveLength(reportCalls);
    expect(localStorage.getItem(serverSessionKey(lessonId))).toBe(initialRecovery);
    expect(saveLesson).not.toHaveBeenCalled();
  });
  it('late metadata does not restore the initial report after a new explicit unlinked selection', async () => {
    const late = deferred<ModelProfileView[]>(); const { sources } = mount({ listProfiles: vi.fn(() => late.promise) }); await open();
    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: '' } }); await act(async () => {});
    await act(async () => late.resolve([profile()]));
    expectMetadata(); expect(screen.getByLabelText('固定学情报告')).toHaveValue('');
    expect(screen.queryByRole('checkbox', { name: /匿名固定知识点/ })).not.toBeInTheDocument();
    expect(vi.mocked(sources.getRun)).not.toHaveBeenCalled();
    expect(JSON.parse(localStorage.getItem(serverSessionKey(lessonId))!).context).toBeNull();
  });
  it('consecutive metadata refreshes retain the newest owner and ignore an older late list', async () => {
    const older = deferred<ModelProfileView[]>(), newer = deferred<ModelProfileView[]>(); let calls = 0;
    mount({ listProfiles: vi.fn(() => ++calls === 1 ? Promise.resolve([profile()]) : calls === 2 ? older.promise : newer.promise) });
    await open(); await screen.findByRole('checkbox', { name: /匿名固定知识点/ });
    fireEvent.click(screen.getByRole('button', { name: '刷新来源列表' })); fireEvent.click(screen.getByRole('button', { name: '刷新来源列表' }));
    await act(async () => newer.resolve([profile('最新模型')]));
    expectMetadata('最新模型');
    await act(async () => older.resolve([profile('旧迟到模型')]));
    expectMetadata('最新模型'); expect(screen.queryByRole('option', { name: /旧迟到模型/ })).not.toBeInTheDocument();
  });
  it('metadata refresh does not cancel a pending explicit report intent', async () => {
    const late = deferred<AnalysisRunView>();
    const nextPoint: FixedKnowledge = { ...point, knowledgePointId: 'b6-next-kp', knowledgeRevisionId: 'b6-next-kr', name: '教师新报告知识点' };
    const nextReport: AnalysisRunView = { ...report, runId: 'b6-next-report', scoreRevisionId: 'b6-next-score', knowledgePoints: [nextPoint] };
    const { sources } = mount({ listRuns: vi.fn(async query => page([report, nextReport], query)),
      getRun: vi.fn(async id => id === nextReport.runId ? late.promise : report),
      listClassesReport: vi.fn(async (id, query) => page([{ ...classRow, knowledgePoint: id === nextReport.runId ? nextPoint : point }], query)) });
    await open(); await screen.findByRole('checkbox', { name: /匿名固定知识点/ });
    expect(vi.mocked(sources.getRun).mock.calls.filter(([id]) => id === runId)).toHaveLength(1);
    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: nextReport.runId } }); await act(async () => {});
    fireEvent.click(screen.getByRole('button', { name: '刷新来源列表' })); await act(async () => {});
    try {
      expectMetadata();
      expect(vi.mocked(sources.getRun).mock.calls.filter(([id]) => id === runId)).toHaveLength(1);
      expect(vi.mocked(sources.getRun).mock.calls.filter(([id]) => id === nextReport.runId)).toHaveLength(1);
      await act(async () => late.resolve(nextReport));
      expect(screen.getByLabelText('固定学情报告')).toHaveValue(nextReport.runId);
      fireEvent.click(screen.getByRole('checkbox', { name: /教师新报告知识点/ }));
      expect(screen.getByRole('checkbox', { name: /教师新报告知识点/ })).toBeChecked();
      expect(JSON.parse(localStorage.getItem(serverSessionKey(lessonId))!).context).toEqual({
        analysisRunId: nextReport.runId, selectedKnowledgePointIds: [nextPoint.knowledgePointId] });
    } finally { await act(async () => late.resolve(nextReport)); }
  });
  it('metadata delayed across discard cannot restore the old report, recovery key or writes', async () => {
    const late = deferred<ModelProfileView[]>(); const { sources, saveLesson } = mount({ listProfiles: vi.fn(() => late.promise) }); await open();
    vi.useFakeTimers(); fireEvent.change(screen.getByLabelText('课题'), { target: { value: '待丢弃教师稿A' } });
    fireEvent.click(screen.getByRole('button', { name: '学习问答' })); await act(async () => {});
    fireEvent.click(screen.getByRole('button', { name: '明确放弃未保存编辑后离开' })); await act(async () => {});
    expect(localStorage.getItem(serverSessionKey(lessonId))).toBeNull();
    await act(async () => late.resolve([profile('旧迟到模型')]));
    await act(async () => { window.dispatchEvent(new Event('pagehide')); window.dispatchEvent(new Event('beforeunload')); vi.advanceTimersByTime(2400); });
    expect(screen.getByLabelText('课题')).toHaveValue('B6已保存可信正文');
    expect(screen.getByLabelText('固定学情报告')).toHaveValue(runId);
    expect(screen.queryByRole('option', { name: /旧迟到模型/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /匿名固定知识点/ })).not.toBeInTheDocument();
    expect(screen.queryByText('正在读取真实来源…')).not.toBeInTheDocument();
    expect(vi.mocked(sources.getRun)).not.toHaveBeenCalled(); expect(saveLesson).not.toHaveBeenCalled();
    expect(localStorage.getItem(serverSessionKey(lessonId))).toBeNull();
    vi.useRealTimers(); vi.mocked(sources.listProfiles).mockResolvedValue([profile('新模型')]);
    fireEvent.click(screen.getByRole('button', { name: '刷新来源列表' }));
    await waitFor(() => expectMetadata('新模型'));
  });
});
