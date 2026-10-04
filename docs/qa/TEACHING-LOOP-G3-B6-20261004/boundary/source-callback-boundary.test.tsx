import React, { useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AnalysisRunView, ClassReportRow, FixedKnowledge, Page } from '@/contracts/b4';
import type { AnalysisContextInput, LessonPlanData, LessonView } from '@/contracts/lesson-plans';
import type { ClassView } from '@/contracts/roster';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { DocumentGateway } from '@/features/lesson-plan/components/DocumentGateway';
import { SourcePanel, initialGenerationInputs } from '@/features/lesson-plan/components/SourcePanel';
import { useLessonEditor } from '@/features/lesson-plan/model/EditorContext';
import { useLessonDocument } from '@/features/lesson-plan/model/DocumentContext';
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
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((yes) => { resolve = yes; }); return { promise, resolve }; }
function Controls() {
  const editor = useLessonEditor(), doc = useLessonDocument();
  const [inputs, setInputs] = useState(initialGenerationInputs), [decision, setDecision] = useState('pending');
  if (!editor.ready) return <p>等待真实保存 hook 恢复</p>;
  return <><SourcePanel value={inputs} onChange={setInputs} />
    <button onClick={() => editor.replace(body('A'))}>改写全部字段 A</button>
    <button onClick={() => setDecision(String(editor.server!.discard()))}>明确放弃 A（实际持久化）</button>
    <output aria-label="来源边界放弃结果">{decision}</output>
    <output aria-label="来源边界正文">{JSON.stringify(editor.data)}</output>
    <output aria-label="来源边界缓存">{JSON.stringify(editor.server?.cache)}</output>
    <output aria-label="来源边界显示上下文">{JSON.stringify(doc.selection.context)}</output>
  </>;
}
beforeEach(() => {
  localStorage.clear(); router.push.mockClear(); router.replace.mockClear();
  Object.defineProperty(window, 'matchMedia', { configurable: true, value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })) });
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); localStorage.clear(); });

describe('G3-BOUNDARY actual SourcePanel late business read', () => {
  it('a source read started before discard must not change restored context, recreate recovery data or submit a new revision', async () => {
    const late = deferred<AnalysisRunView>(), saved = lesson();
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async (_id, payload) => lesson(2, payload.data, payload.context));
    const getRun = vi.fn<typeof defaultSourceApi.getRun>(async (id) => id === run('A').runId ? late.promise : run('BASE'));
    const klass: ClassView = { id: classId, code: 'anonymous-example', name: '匿名样例班', schoolYear: '2026', gradeId: 'g1', status: 'active', revision: 1, studentCount: 0, createdAt: '2026-10-04T00:00:00Z' };
    const sources: typeof defaultSourceApi = { ...defaultSourceApi, getRun,
      listClasses: vi.fn(async (query) => page([klass], query)), taxonomy: vi.fn(async () => ({ stages: [], grades: [], subjects: [], editions: [] })), listProfiles: vi.fn(async () => []),
      listRuns: vi.fn(async (query) => page([run('BASE'), run('A')], query)),
      listClassesReport: vi.fn(async (id, query) => page([classRow(id === run('A').runId ? 'A' : 'BASE')], query)),
      listPractices: vi.fn(async (query) => page([], query)),
    };
    render(<NavigationPreference><DocumentGateway initialLessonPlanId={lessonId} services={{ lessonApi: { ...lessonPlanApi, getLesson: vi.fn(async () => structuredClone(saved)), saveLesson }, sourceApi: sources }}><Controls /></DocumentGateway></NavigationPreference>);
    await screen.findByLabelText('来源边界正文');
    fireEvent.click(screen.getByRole('button', { name: '刷新来源列表' }));
    await screen.findByRole('checkbox', { name: /知识点 BASE/ });
    expect(screen.getByLabelText('固定学情报告')).toHaveValue(run('BASE').runId);
    expect(screen.getByRole('checkbox', { name: /知识点 BASE/ })).toBeChecked();
    expect(JSON.parse(screen.getByLabelText('来源边界缓存').textContent!).context).toEqual(baseContext);
    expect(saveLesson).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: run('A').runId } });
    expect(getRun.mock.calls.map((args) => args[0])).toEqual([run('BASE').runId, run('A').runId]);
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: '改写全部字段 A' }));
    expect(JSON.parse(screen.getByLabelText('来源边界正文').textContent!)).toEqual(body('A'));
    const key = serverSessionKey(lessonId), beforeDiscard = JSON.parse(localStorage.getItem(key)!);
    fireEvent.click(screen.getByRole('button', { name: '明确放弃 A（实际持久化）' }));
    expect(screen.getByLabelText('来源边界放弃结果')).toHaveTextContent('true');
    expect(JSON.parse(screen.getByLabelText('来源边界正文').textContent!)).toEqual(body('BASE'));
    expect(JSON.parse(screen.getByLabelText('来源边界缓存').textContent!).context).toEqual(baseContext);
    expect(localStorage.getItem(key)).toBeNull();
    const afterDiscard = JSON.parse(screen.getByLabelText('来源边界缓存').textContent!);

    await act(async () => late.resolve(run('A')));
    const afterRead = { data: JSON.parse(screen.getByLabelText('来源边界正文').textContent!),
      cache: JSON.parse(screen.getByLabelText('来源边界缓存').textContent!), displayedContext: JSON.parse(screen.getByLabelText('来源边界显示上下文').textContent!),
      recoveryRaw: localStorage.getItem(key) };
    await act(async () => { await vi.advanceTimersByTimeAsync(3600); });
    const afterCycles = { data: JSON.parse(screen.getByLabelText('来源边界正文').textContent!),
      cache: JSON.parse(screen.getByLabelText('来源边界缓存').textContent!), displayedContext: JSON.parse(screen.getByLabelText('来源边界显示上下文').textContent!),
      recoveryRaw: localStorage.getItem(key), saveCalls: structuredClone(saveLesson.mock.calls) };
    console.log('SOURCE_CALLBACK_BOUNDARY_FACTS ' + JSON.stringify({ component: 'actual DocumentGateway + SourcePanel + EditorContext + useServerPersistence', mode: 'controlled business reads in jsdom; not real browser',
      beforeDiscard, afterDiscard, afterRead, afterCycles }));
    expect.soft(afterRead.data).toEqual(body('BASE'));
    expect.soft(afterRead.cache.context).toEqual(baseContext);
    expect.soft(afterRead.displayedContext).toEqual(baseContext);
    expect.soft(afterRead.recoveryRaw).toBeNull();
    expect.soft(afterCycles.cache.context).toEqual(baseContext);
    expect.soft(afterCycles.cache.serverRevision).toBe(1);
    expect.soft(afterCycles.cache.serverRevisionId).toBe('boundary-source-fixed-1');
    expect.soft(afterCycles.recoveryRaw).toBeNull();
    expect.soft(saveLesson).not.toHaveBeenCalled();
    expect.soft(saved).toEqual(lesson());
  });
});
