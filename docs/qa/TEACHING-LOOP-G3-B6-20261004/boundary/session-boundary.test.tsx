import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AnalysisContextInput, DraftEnvelope, LessonPlanData, LessonView } from '@/contracts/lesson-plans';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { createLessonStore } from '@/features/lesson-plan/model/store';
import { useServerPersistence } from '@/features/lesson-plan/model/useServerPersistence';
import { useDraftPersistence } from '@/features/lesson-plan/model/useDraftPersistence';
import { initialServerCache, serverSessionKey } from '@/features/lesson-plan/model/server-cache';
import type { DraftRepository } from '@/features/lesson-plan/model/types';

function fullData(mark: string): LessonPlanData {
  return {
    title: `${mark}课题`, totalLessons: '3', currentLessonNo: '2', lessonTypes: ['review', 'other'],
    otherTypeText: `${mark}教师课型`, coreCompetencies: `${mark}核心素养`, keyPoints: `${mark}重点`,
    teachingDesign: `${mark}长正文「中文、引号 & < >」\n`.repeat(20),
    process: [
      { id: `${mark}-p1`, stage: `${mark}导入`, design: `${mark}环节正文\n`.repeat(10), secondary: `${mark}二次备课\n`.repeat(12) },
      { id: `${mark}-p2`, stage: `${mark}检测`, design: `${mark}课堂操作`, secondary: `${mark}教师补充` },
    ], exercises: `${mark}练习`, reflection: `${mark}教师反思`,
  };
}
const fixedContext: AnalysisContextInput = { analysisRunId: 'boundary-ready-run', selectedKnowledgePointIds: ['boundary-k1', 'boundary-k2'] };
function savedView(version = 1, mark = 'BASE'): LessonView {
  const revisionId = `boundary-fixed-${version}`;
  return { protocolVersion: 2, lessonPlanId: 'boundary-lesson', subjectId: 'chinese', classId: 'boundary-class', revision: version, currentRevisionId: revisionId, replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: 'boundary-lesson', revisionId, version, data: fullData(mark), contentHash: `boundary-hash-${version}`, source: 'manual',
      contextSnapshot: { subjectId: 'chinese', classId: 'boundary-class', classNameAtSave: '匿名样例班', analysis: {
        ...structuredClone(fixedContext), inputHash: 'boundary-input', scoreRevisionId: 'boundary-score', paperRevisionId: 'boundary-paper', className: null, classNameNote: '该成绩未记录班名',
        knowledgePoints: [
          { knowledgePointId: 'boundary-k1', knowledgeRevisionId: 'boundary-kr1', name: '知识点一', role: 'primary' },
          { knowledgePointId: 'boundary-k2', knowledgeRevisionId: 'boundary-kr2', name: '知识点二', role: 'secondary' },
        ],
      } }, analysisRunId: fixedContext.analysisRunId, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-04T00:00:00Z' },
  };
}
function storageBag(failRemove = false) {
  const values = new Map<string, string>();
  const storage = {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => { values.set(key, value); }),
    removeItem: vi.fn((key: string) => { if (failRemove) throw new Error('删除恢复缓存失败（隔离注入）'); values.delete(key); }),
    clear: () => values.clear(), key: (index: number) => [...values.keys()][index] ?? null,
    get length() { return values.size; },
  } satisfies Storage;
  return { storage, values };
}
async function elapsed(milliseconds = 3600) { await act(async () => { await vi.advanceTimersByTimeAsync(milliseconds); }); }
beforeEach(() => { vi.useFakeTimers(); localStorage.clear(); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); localStorage.clear(); });

describe('G3-BOUNDARY full-content independent oracles', () => {
  it('successful discard restores all fields/context and survives keep/flush/pagehide/queued periods, then a new B can save', async () => {
    const original = savedView(), bag = storageBag(), store = createLessonStore(), writes: unknown[] = [];
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async (_id, body) => { writes.push(structuredClone(body)); return { ...savedView(2, 'B'), currentRevision: { ...savedView(2, 'B').currentRevision, data: structuredClone(body.data) } }; });
    const hook = renderHook(() => useServerPersistence(store, { view: original, api: { ...lessonPlanApi, saveLesson }, storage: bag.storage }));
    act(() => { store.getState().replace(fullData('A')); hook.result.current.setContext({ analysisRunId: 'unsaved-A-run', selectedKnowledgePointIds: ['unsaved-A-kp'] }); });
    act(() => { expect(hook.result.current.discard()).toBe(true); });
    expect(store.getState().data).toEqual(fullData('BASE'));
    expect(hook.result.current.cache?.context).toEqual(fixedContext);
    expect(hook.result.current.cache?.serverRevision).toBe(1);
    expect(hook.result.current.cache?.serverRevisionId).toBe('boundary-fixed-1');
    expect(hook.result.current.dirty).toBe(false);
    act(() => store.getState().undo());
    expect(store.getState().data).toEqual(fullData('BASE'));
    act(() => { hook.result.current.keep(); window.dispatchEvent(new Event('pagehide')); window.dispatchEvent(new Event('beforeunload', { cancelable: true })); });
    await act(async () => { await hook.result.current.flush().catch(() => {}); await hook.result.current.save(); });
    await elapsed();
    expect(writes).toEqual([]);
    expect(bag.values.get(serverSessionKey(original.lessonPlanId))).toBeUndefined();
    act(() => store.getState().replace(fullData('B')));
    await elapsed(600);
    expect(saveLesson).toHaveBeenCalledTimes(1);
    expect(saveLesson.mock.calls[0][1]).toMatchObject({ expectedRevision: 1, data: fullData('B'), context: fixedContext });
    expect(store.getState().data).toEqual(fullData('B'));
  });

  it('delete failure preserves the only full A draft and exact recovery bytes while every implicit entry stays paused', async () => {
    const original = savedView(), bag = storageBag(true), store = createLessonStore();
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async () => savedView(2, 'A'));
    const hook = renderHook(() => useServerPersistence(store, { view: original, api: { ...lessonPlanApi, saveLesson }, storage: bag.storage }));
    act(() => { store.getState().replace(fullData('A')); hook.result.current.setContext({ analysisRunId: 'A-ready', selectedKnowledgePointIds: ['A-kp'] }); });
    const key = serverSessionKey(original.lessonPlanId), bytes = bag.values.get(key), cache = structuredClone(hook.result.current.cache);
    act(() => { expect(hook.result.current.discard()).toBe(false); });
    expect(store.getState().data).toEqual(fullData('A'));
    expect(hook.result.current.cache).toEqual(cache);
    expect(bag.values.get(key)).toBe(bytes);
    const writtenBefore = bag.storage.setItem.mock.calls.length;
    act(() => { hook.result.current.keep(); window.dispatchEvent(new Event('pagehide')); window.dispatchEvent(new Event('beforeunload', { cancelable: true })); });
    await act(async () => { await hook.result.current.flush().catch(() => {}); });
    await elapsed();
    expect(saveLesson).not.toHaveBeenCalled();
    expect(bag.storage.setItem).toHaveBeenCalledTimes(writtenBefore);
    expect(store.getState().data).toEqual(fullData('A'));
    expect(bag.values.get(key)).toBe(bytes);
    expect(hook.result.current.error).not.toBeNull();
  });

  it('an older known view cannot masquerade as the saved baseline of a higher recovered CAS', async () => {
    const bag = storageBag(), newer = initialServerCache(savedView(5, 'TRUSTED-5'));
    newer.data = fullData('A'); newer.editRevision = 8; newer.acknowledgedEditRevision = 7;
    const key = serverSessionKey('boundary-lesson'); bag.values.set(key, JSON.stringify(newer));
    const before = bag.values.get(key), store = createLessonStore(), saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async () => savedView(6, 'A'));
    const hook = renderHook(() => useServerPersistence(store, { view: savedView(1, 'STALE-1'), api: { ...lessonPlanApi, saveLesson }, storage: bag.storage }));
    let discarded = false; act(() => { discarded = hook.result.current.discard(); });
    expect(store.getState().data).not.toEqual(fullData('STALE-1'));
    expect(hook.result.current.cache?.serverRevision).toBe(5);
    expect(hook.result.current.cache?.serverRevisionId).toBe('boundary-fixed-5');
    if (!discarded) {
      expect(store.getState().data).toEqual(fullData('A'));
      expect(bag.values.get(key)).toBe(before);
    } else {
      await act(async () => { await hook.result.current.flush().catch(() => {}); hook.result.current.keep(); window.dispatchEvent(new Event('pagehide')); });
    }
    await elapsed();
    expect(saveLesson).not.toHaveBeenCalled();
  });

  it('exclusive ownership rejects discard without removing recovery data', () => {
    const bag = storageBag(), store = createLessonStore();
    const hook = renderHook(() => useServerPersistence(store, { view: savedView(), api: lessonPlanApi, storage: bag.storage }));
    act(() => { store.getState().replace(fullData('A')); hook.result.current.setExclusive(true); });
    const key = serverSessionKey('boundary-lesson'), bytes = bag.values.get(key);
    act(() => { expect(hook.result.current.discard()).toBe(false); });
    expect(bag.storage.removeItem).not.toHaveBeenCalled();
    expect(bag.values.get(key)).toBe(bytes);
    expect(store.getState().data).toEqual(fullData('A'));
  });

  it('local discard restores the full real saved envelope, unload flush stays quiet and new B still saves', async () => {
    const original: DraftEnvelope = { schemaVersion: 1, revision: 9, updatedAt: '2026-10-04T00:00:00Z', data: fullData('LOCAL-BASE') };
    const save = vi.fn<DraftRepository['save']>(), repository: DraftRepository = { load: async () => structuredClone(original), save }, store = createLessonStore();
    const notice = vi.fn(); const hook = renderHook(() => useDraftPersistence(store, repository, notice));
    await act(async () => { await Promise.resolve(); });
    act(() => store.getState().replace(fullData('LOCAL-A')));
    act(() => { expect(hook.result.current.discardPending()).toBe(true); });
    expect(store.getState().data).toEqual(fullData('LOCAL-BASE'));
    act(() => { window.dispatchEvent(new Event('pagehide')); });
    await act(async () => { await hook.result.current.flushDraft(); });
    await elapsed();
    expect(save).not.toHaveBeenCalled();
    act(() => store.getState().replace(fullData('LOCAL-B')));
    await elapsed(600);
    expect(save).toHaveBeenCalledTimes(1);
    expect(save.mock.calls[0][0].data).toEqual(fullData('LOCAL-B'));
    const calls = save.mock.calls.length;
    hook.unmount();
    await act(async () => { await Promise.resolve(); });
    expect(save).toHaveBeenCalledTimes(calls);
  });
});
