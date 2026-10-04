import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { LessonView } from '@/contracts/lesson-plans';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { createLessonStore } from '@/features/lesson-plan/model/store';
import { useServerPersistence } from '@/features/lesson-plan/model/useServerPersistence';
import { serverSessionKey } from '@/features/lesson-plan/model/server-cache';
import { emptyData } from '@/features/lesson-plan/model/defaults';

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); localStorage.clear(); });

describe('B5 independent required behavior — current failure retained', () => {
  it('explicitly discarded edits must not autosave or recreate recovery data while the destination route is still loading', async () => {
    vi.useFakeTimers(); localStorage.clear();
    const revisionId = 'required-fixed-1';
    const saved: LessonView = { protocolVersion: 2, lessonPlanId: 'required-lesson', subjectId: 'chinese', classId: 'required-class', revision: 1, currentRevisionId: revisionId, replayed: false,
      currentRevision: { protocolVersion: 2, lessonPlanId: 'required-lesson', revisionId, version: 1,
        data: { ...structuredClone(emptyData), title: '可信已保存正文' }, contentHash: 'required-hash-1', source: 'manual',
        contextSnapshot: { subjectId: 'chinese', classId: 'required-class', classNameAtSave: '隔离班', analysis: null },
        analysisRunId: null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-03T00:00:00Z' } };
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async () => saved);
    const services = { ...lessonPlanApi, saveLesson };
    const store = createLessonStore();
    const hook = renderHook(() => useServerPersistence(store, { view: saved, api: services }));
    act(() => store.getState().set({ title: '教师明确放弃的正文' }));
    act(() => { expect(hook.result.current.discard()).toBe(true); });
    await act(async () => { vi.advanceTimersByTime(600); });
    expect.soft(saveLesson).not.toHaveBeenCalled();
    expect.soft(localStorage.getItem(serverSessionKey('required-lesson'))).toBeNull();
  });
});
