import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AnalysisRunView, ClassReportRow, FixedKnowledge, Page } from '@/contracts/b4';
import type { AnalysisContextInput, LessonPlanData, LessonView } from '@/contracts/lesson-plans';
import type { ClassView } from '@/contracts/roster';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { LessonPlanWorkspace } from '@/features/lesson-plan/LessonPlanWorkspace';
import { defaultSourceApi } from '@/features/lesson-plan/model/workspace-services';
import { serverSessionKey } from '@/features/lesson-plan/model/server-cache';

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router, usePathname: () => '/lesson-plans' }));
const lessonId = 'boundary-source-lesson', classId = 'boundary-source-class';
const baseContext: AnalysisContextInput = { analysisRunId: 'boundary-source-BASE', selectedKnowledgePointIds: ['boundary-source-kp-BASE'] };
function body(mark: string): LessonPlanData {
  return { title: `${mark}课题`, totalLessons: '3', currentLessonNo: '2', lessonTypes: ['review', 'other'], otherTypeText: `${mark}教师课型`,
    coreCompetencies: `${mark}核心素养`, keyPoints: `${mark}重点`, teachingDesign: `${mark}长正文「中文、&、<、>」\n`.repeat(14),
    process: [{ id: `${mark}-p1`, stage: `${mark}导入`, design: `${mark}活动\n`.repeat(8), secondary: `${mark}长二次备课\n`.repeat(8) },
      { id: `${mark}-p2`, stage: `${mark}检测`, design: `${mark}检测`, secondary: `${mark}补充` }],
    exercises: `${mark}课堂练习`, reflection: `${mark}教师反思` };
}
function point(mark: string): FixedKnowledge {
  return { knowledgePointId: `boundary-source-kp-${mark}`, knowledgeRevisionId: `boundary-source-kr-${mark}`, name: `知识点 ${mark}`, role: 'primary' };
}
function run(mark: string): AnalysisRunView {
  return { runId: `boundary-source-${mark}`, assessmentId: `boundary-source-assessment-${mark}`, subjectId: 'chinese', scoreRevisionId: `boundary-source-score-${mark}`,
    paperRevisionId: `boundary-source-paper-${mark}`, paperTitle: `固定原卷 ${mark}`, inputHash: `boundary-source-input-${mark}`, ruleCode: 'any_loss_v1',
    selectionSnapshot: { selectedParticipantIds: [], uniqueStudentCount: 0, participantCount: 0, leafCount: 1, stateCounts: { recorded: 0, missing: 0, absent: 0, exempt: 0 } },
    participants: [], knowledgePoints: [point(mark)], job: { jobId: `boundary-source-job-${mark}`, domain: 'teaching', kind: 'analysis', attempt: 1, state: 'succeeded', result: {}, error: null },
    reportReady: true, createdAt: '2026-10-04T00:00:00Z' };
}
function lesson(version = 1, data = body('BASE'), context: AnalysisContextInput | null = baseContext): LessonView {
  const revisionId = `boundary-source-fixed-${version}`;
  return { protocolVersion: 2, lessonPlanId: lessonId, subjectId: 'chinese', classId, revision: version, currentRevisionId: revisionId, replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: lessonId, revisionId, version, data: structuredClone(data), contentHash: `boundary-source-body-${version}`, source: 'manual',
      contextSnapshot: { subjectId: 'chinese', classId, classNameAtSave: '匿名样例班', analysis: context ? { analysisRunId: context.analysisRunId,
        inputHash: 'boundary-source-input-BASE', scoreRevisionId: 'boundary-source-score-BASE', paperRevisionId: 'boundary-source-paper-BASE',
        className: null, classNameNote: '该成绩未记录班名', knowledgePoints: [point('BASE')] } : null },
      analysisRunId: context?.analysisRunId ?? null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-04T00:00:00Z' } };
}
function page<T>(items: T[], query: { offset?: number; limit?: number } = {}): Page<T> {
  return { items, total: items.length, offset: query.offset ?? 0, limit: query.limit ?? 200 };
}
function classRow(mark: string): ClassReportRow {
  return { classId, className: null, classNameNote: '该成绩未记录班名', knowledgePoint: point(mark), selectedCount: 0, validCount: 0, needsCount: 0,
    incompleteCount: 0, noEvidenceCount: 0, fullCreditCount: 0, numerator: 0, denominator: 0, ratio: null };
}

/** Check actual form values; process identifiers are additionally checked in the next real save payload. */
function assertVisibleBody(expected: LessonPlanData) {
  expect(screen.getByLabelText('课题')).toHaveValue(expected.title);
  expect(screen.getByLabelText('本课题总课时')).toHaveValue(Number(expected.totalLessons));
  expect(screen.getByLabelText('本节课')).toHaveValue(Number(expected.currentLessonNo));
  expect(screen.getByRole('checkbox', { name: '复习课' })).toBeChecked();
  expect(screen.getByRole('checkbox', { name: '其它' })).toBeChecked();
  for (const name of ['新课', '试题讲评课', '实验课']) expect(screen.getByRole('checkbox', { name })).not.toBeChecked();
  expect(screen.getByLabelText('其他课型说明')).toHaveValue(expected.otherTypeText);
  for (const [section, value] of [
    ['core', expected.coreCompetencies], ['key', expected.keyPoints], ['design', expected.teachingDesign],
    ['exercises', expected.exercises], ['reflection', expected.reflection],
  ]) expect(document.querySelector(`#field-${section} textarea`)).toHaveValue(value);
  const processes = document.querySelectorAll('.process-editor');
  expect(processes).toHaveLength(expected.process.length);
  expected.process.forEach((process, index) => {
    expect(processes[index].querySelector('input')).toHaveValue(process.stage);
    const texts = processes[index].querySelectorAll('textarea');
    expect(texts[0]).toHaveValue(process.design); expect(texts[1]).toHaveValue(process.secondary);
  });
}
function sourceDisplay() {
  return { report: (screen.getByLabelText('固定学情报告') as HTMLSelectElement).value,
    provenance: screen.getByLabelText('教案正文来源').textContent };
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

describe('G3-BOUNDARY actual complete workspace source and discard', () => {
  it('discards a fully loaded unsaved A report and complete A body through public navigation, restores BASE, then saves only a fresh edit', async () => {
    const saved = lesson(), key = serverSessionKey(lessonId);
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async (_id, payload) => lesson(2, payload.data, payload.context));
    const klass: ClassView = { id: classId, code: 'anonymous-example', name: '匿名样例班', schoolYear: '2026', gradeId: 'g1', status: 'active', revision: 1, studentCount: 0, createdAt: '2026-10-04T00:00:00Z' };
    const sources: typeof defaultSourceApi = { ...defaultSourceApi,
      getRun: vi.fn(async (id) => run(id === run('A').runId ? 'A' : 'BASE')),
      listClasses: vi.fn(async (query) => page([klass], query)), taxonomy: vi.fn(async () => ({ stages: [], grades: [], subjects: [], editions: [] })), listProfiles: vi.fn(async () => []),
      listRuns: vi.fn(async (query) => page([run('BASE'), run('A')], query)),
      listClassesReport: vi.fn(async (id, query) => page([classRow(id === run('A').runId ? 'A' : 'BASE')], query)),
      listPractices: vi.fn(async (query) => page([], query)),
    };
    render(<NavigationPreference><LessonPlanWorkspace initialLessonPlanId={lessonId} services={{ lessonApi: { ...lessonPlanApi, getLesson: vi.fn(async () => structuredClone(saved)), saveLesson }, sourceApi: sources }} /></NavigationPreference>);
    await screen.findByLabelText('课题');
    fireEvent.click(screen.getByRole('button', { name: '刷新来源列表' }));
    await screen.findByRole('checkbox', { name: /知识点 BASE/ });
    assertVisibleBody(body('BASE'));
    expect(screen.getByRole('checkbox', { name: /知识点 BASE/ })).toBeChecked();
    expect(sourceDisplay().report).toBe(run('BASE').runId);
    expect(saveLesson).not.toHaveBeenCalled();

    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: run('A').runId } });
    await act(async () => {});
    fireEvent.click(screen.getByRole('checkbox', { name: /知识点 A/ }));
    await act(async () => {});
    const aContext = { analysisRunId: run('A').runId, selectedKnowledgePointIds: [point('A').knowledgePointId] };
    expect(sourceDisplay().report).toBe(run('A').runId);
    expect(screen.getByRole('checkbox', { name: /知识点 A/ })).toBeChecked();
    expect(JSON.parse(localStorage.getItem(key)!).context).toEqual(aContext);

    const raw = JSON.stringify({ schemaVersion: 1, data: body('A') });
    const upload = new File([raw], 'boundary-complete-A.json', { type: 'application/json' });
    // jsdom capability adapter only; the actual EditorOverlays import handler parses and validates the file.
    Object.defineProperty(upload, 'text', { value: async () => raw });
    const fileInput = document.querySelector<HTMLInputElement>('input[type="file"][accept*="json"]');
    expect(fileInput).not.toBeNull();
    fireEvent.change(fileInput!, { target: { files: [upload] } });
    await act(async () => {});
    assertVisibleBody(body('A'));
    const beforeDiscard = JSON.parse(localStorage.getItem(key)!);
    expect(beforeDiscard.data).toEqual(body('A')); expect(beforeDiscard.context).toEqual(aContext);
    expect(saveLesson).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '学习问答' }));
    await act(async () => {});
    expect(screen.getByRole('dialog', { name: '离开当前教案' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '明确放弃未保存编辑后离开' }));
    await act(async () => {});
    expect(router.push).toHaveBeenCalledWith('/chat');
    assertVisibleBody(body('BASE'));
    expect(sourceDisplay().report).toBe(run('BASE').runId);
    expect(screen.queryByRole('checkbox', { name: /知识点 A/ })).not.toBeInTheDocument();
    expect(sourceDisplay().provenance).toContain('后台固定 v1');
    expect(sourceDisplay().provenance).toContain('boundary-source-fixed-1');
    expect(sourceDisplay().provenance).toContain(baseContext.analysisRunId);
    expect(localStorage.getItem(key)).toBeNull(); expect(saveLesson).not.toHaveBeenCalled();
    const afterDiscard = sourceDisplay();

    await act(async () => { await vi.advanceTimersByTimeAsync(3600); });
    assertVisibleBody(body('BASE'));
    expect(sourceDisplay()).toEqual(afterDiscard);
    expect(localStorage.getItem(key)).toBeNull(); expect(saveLesson).not.toHaveBeenCalled();
    const afterCycles = { ...sourceDisplay(), recoveryRaw: localStorage.getItem(key), saveCalls: structuredClone(saveLesson.mock.calls) };

    // The only subsequent change is the title; the complete real save payload proves all BASE fields and process IDs were restored.
    fireEvent.change(screen.getByLabelText('课题'), { target: { value: 'B课题' } });
    await act(async () => { await vi.advanceTimersByTimeAsync(600); });
    expect(saveLesson).toHaveBeenCalledTimes(1);
    const payload = saveLesson.mock.calls[0][1], expectedFresh = { ...body('BASE'), title: 'B课题' };
    expect(payload.data).toEqual(expectedFresh); expect(payload.context).toEqual(baseContext); expect(payload.expectedRevision).toBe(1);
    const afterFresh = JSON.parse(localStorage.getItem(key)!);
    expect(afterFresh.data).toEqual(expectedFresh); expect(afterFresh.context).toEqual(baseContext);
    expect(afterFresh.serverRevision).toBe(2); expect(afterFresh.serverRevisionId).toBe('boundary-source-fixed-2');
    expect(sourceDisplay().report).toBe(run('BASE').runId);
    expect(sourceDisplay().provenance).toContain('后台固定 v2');
    expect(saved).toEqual(lesson());
    console.log('WORKSPACE_SOURCE_DISCARD_FACTS ' + JSON.stringify({ component: 'actual LessonPlanWorkspace including ServerControls, EditorOverlays and LeaveProtection', mode: 'controlled business reads in jsdom; not real browser or FastAPI', beforeDiscard, afterDiscard, afterCycles, freshSave: structuredClone(saveLesson.mock.calls), afterFresh, displayAfterFresh: sourceDisplay() }));
  });
});
