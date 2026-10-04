import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LessonView } from '@/contracts/lesson-plans';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { createLessonStore } from '@/features/lesson-plan/model/store';
import { useServerPersistence } from '@/features/lesson-plan/model/useServerPersistence';
import { serverSessionKey } from '@/features/lesson-plan/model/server-cache';
import { emptyData } from '@/features/lesson-plan/model/defaults';

function fixedView(version = 1, title = '已保存正文'): LessonView {
  const revisionId = `diagnostic-fixed-${version}`;
  return {
    protocolVersion: 2, lessonPlanId: 'diagnostic-lesson', subjectId: 'chinese', classId: 'diagnostic-class',
    revision: version, currentRevisionId: revisionId, replayed: false,
    currentRevision: {
      protocolVersion: 2, lessonPlanId: 'diagnostic-lesson', revisionId, version,
      data: { ...structuredClone(emptyData), title }, contentHash: `diagnostic-hash-${version}`,
      source: 'manual', contextSnapshot: { subjectId: 'chinese', classId: 'diagnostic-class', classNameAtSave: '隔离诊断班级', analysis: null },
      analysisRunId: null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [],
      reviewState: 'unreviewed', createdAt: '2026-10-03T00:00:00Z',
    },
  };
}

beforeEach(() => { localStorage.clear(); vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); localStorage.clear(); });

describe('B5 independent discard diagnostics — pass means reproduction, not fix', () => {
  it('accepted explicit discard still sends abandoned text after the original 600ms debounce if route commitment is delayed', async () => {
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async () => fixedView(2, '应当放弃的编辑'));
    const services = { ...lessonPlanApi, saveLesson };
    const store = createLessonStore();
    const hook = renderHook(() => useServerPersistence(store, { view: fixedView(), api: services }));

    act(() => store.getState().set({ title: '应当放弃的编辑' }));
    expect(hook.result.current.dirty).toBe(true);
    expect(localStorage.getItem(serverSessionKey('diagnostic-lesson'))).not.toBeNull();
    act(() => { expect(hook.result.current.discard()).toBe(true); });
    expect(localStorage.getItem(serverSessionKey('diagnostic-lesson'))).toBeNull();
    expect(saveLesson).not.toHaveBeenCalled();

    // The Next navigation may retain the old subtree while awaiting its destination.
    // Reproduce exactly that mounted interval; no fake HTTP server or real drafts.
    await act(async () => { vi.advanceTimersByTime(600); });
    expect(saveLesson).toHaveBeenCalledTimes(1);
    expect(saveLesson.mock.calls[0][1]).toMatchObject({ expectedRevision: 1, data: { title: '应当放弃的编辑' } });
    expect(localStorage.getItem(serverSessionKey('diagnostic-lesson'))).not.toBeNull();
    expect(hook.result.current.cache?.serverRevision).toBe(2);
  });

  it('control: an immediate unmount after discard cancels the debounce and sends nothing', async () => {
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async () => fixedView(2, '应当放弃的编辑'));
    const services = { ...lessonPlanApi, saveLesson };
    const store = createLessonStore();
    const hook = renderHook(() => useServerPersistence(store, { view: fixedView(), api: services }));
    act(() => store.getState().set({ title: '应当放弃的编辑' }));
    act(() => { expect(hook.result.current.discard()).toBe(true); });
    hook.unmount();
    await act(async () => { vi.advanceTimersByTime(600); });
    expect(saveLesson).not.toHaveBeenCalled();
    expect(localStorage.getItem(serverSessionKey('diagnostic-lesson'))).toBeNull();
  });
});
