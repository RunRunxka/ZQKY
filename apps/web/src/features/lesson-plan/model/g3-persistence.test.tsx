import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LessonView } from '@/contracts/lesson-plans';
import { ApiError } from '@/services/api-client';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { createLessonStore } from './store';
import { useServerPersistence } from './useServerPersistence';
import { useDraftPersistence } from './useDraftPersistence';
import { emptyData } from './defaults';
import { initialServerCache, serverSessionKey, writeServerCache } from './server-cache';

function saved(version = 1, title = '可信已保存正文'): LessonView {
  const revisionId = `g3-fixed-${version}`;
  return { protocolVersion: 2, lessonPlanId: 'g3-lesson', subjectId: 'chinese', classId: 'g3-class', revision: version, currentRevisionId: revisionId, replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: 'g3-lesson', revisionId, version,
      data: { ...structuredClone(emptyData), title, reflection: '教师反思', process: [{ id: 'original-stage', stage: '原环节', design: '原活动', secondary: '原二次备课' }] },
      contentHash: `g3-hash-${version}`, source: 'manual', contextSnapshot: { subjectId: 'chinese', classId: 'g3-class', classNameAtSave: '匿名隔离班', analysis: null },
      analysisRunId: null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-04T00:00:00Z' } };
}
function deferred<T>() { let resolve!: (result: T) => void, reject!: (cause: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
function host(overrides: Partial<typeof lessonPlanApi> = {}, storage = localStorage, view = saved()) {
  const api = { ...lessonPlanApi, getLesson: vi.fn(async () => saved()), saveLesson: vi.fn<typeof lessonPlanApi.saveLesson>(async (_id, body) => { const next = saved(2); next.currentRevision.data = structuredClone(body.data); return next; }), ...overrides };
  const store = createLessonStore();
  const hook = renderHook(() => useServerPersistence(store, { view, api, storage }));
  return { hook, store, api };
}
beforeEach(() => { localStorage.clear(); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); localStorage.clear(); });

describe('G3 discard terminates the old write intent', () => {
  it.each([false, true])('restores the trusted whole body and never writes abandoned A, immediate unmount=%s', async (unmount) => {
    vi.useFakeTimers(); const { hook, store, api } = host();
    act(() => { store.getState().set({ title: '明确放弃A', process: [{ id: 'abandoned-stage', stage: 'A', design: '放弃的长正文', secondary: '放弃的二次备课' }] }); hook.result.current.setContext({ analysisRunId: 'abandoned-run', selectedKnowledgePointIds: ['abandoned-kp'] }); });
    act(() => { expect(hook.result.current.discard()).toBe(true); });
    expect(store.getState().data).toEqual(saved().currentRevision.data);
    expect(store.getState().past).toEqual([]); expect(store.getState().future).toEqual([]);
    expect(hook.result.current.cache?.context).toBeNull(); expect(hook.result.current.dirty).toBe(false);
    if (unmount) hook.unmount();
    await act(async () => { vi.advanceTimersByTime(3600); });
    expect(api.saveLesson).not.toHaveBeenCalled(); expect(localStorage.getItem(serverSessionKey('g3-lesson'))).toBeNull();
  });
  it('flush, keep and lifecycle events cannot recreate discarded A while the route remains mounted', async () => {
    vi.useFakeTimers(); const { hook, store, api } = host();
    act(() => store.getState().set({ title: '弃稿A' })); act(() => { expect(hook.result.current.discard()).toBe(true); });
    await act(async () => { await hook.result.current.flush(); await hook.result.current.save(); hook.result.current.keep(); window.dispatchEvent(new Event('pagehide')); window.dispatchEvent(new Event('beforeunload')); vi.advanceTimersByTime(1800); });
    expect(api.saveLesson).not.toHaveBeenCalled(); expect(localStorage.getItem(serverSessionKey('g3-lesson'))).toBeNull(); expect(store.getState().data).toEqual(saved().currentRevision.data);
  });
  it('failed navigation leaves a usable editor: later B starts a fresh save and A cannot return through Undo', async () => {
    vi.useFakeTimers(); const { hook, store, api } = host();
    act(() => store.getState().set({ title: '弃稿A' })); act(() => { expect(hook.result.current.discard()).toBe(true); });
    act(() => store.getState().undo()); expect(store.getState().data.title).toBe('可信已保存正文');
    act(() => store.getState().set({ title: '导航失败后明确新编辑B' }));
    expect(JSON.parse(localStorage.getItem(serverSessionKey('g3-lesson'))!).data.title).toBe('导航失败后明确新编辑B');
    await act(async () => { vi.advanceTimersByTime(600); });
    expect(api.saveLesson).toHaveBeenCalledTimes(1); expect(vi.mocked(api.saveLesson).mock.calls[0][1]).toMatchObject({ expectedRevision: 1, data: { title: '导航失败后明确新编辑B' } }); expect(hook.result.current.dirty).toBe(false);
  });
  it.each(['discard', 'save'])('a recovery-key deletion error keeps the unique input and stops automatic writes until explicit %s retry', async (decision) => {
    vi.useFakeTimers(); const { hook, store, api } = host();
    act(() => store.getState().set({ title: '删除失败时唯一教师输入A' })); const raw = localStorage.getItem(serverSessionKey('g3-lesson')), before = structuredClone(store.getState().data);
    const removal = vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('受控删除拒绝'); });
    act(() => { expect(hook.result.current.discard()).toBe(false); });
    expect(store.getState().data).toEqual(before); expect(localStorage.getItem(serverSessionKey('g3-lesson'))).toBe(raw); expect(hook.result.current.error?.message).toContain('删除');
    await act(async () => { window.dispatchEvent(new Event('pagehide')); vi.advanceTimersByTime(2400); });
    expect(api.saveLesson).not.toHaveBeenCalled(); expect(localStorage.getItem(serverSessionKey('g3-lesson'))).toBe(raw);
    removal.mockRestore();
    if (decision === 'discard') { act(() => { expect(hook.result.current.discard()).toBe(true); }); expect(store.getState().data).toEqual(saved().currentRevision.data); expect(localStorage.getItem(serverSessionKey('g3-lesson'))).toBeNull(); }
    else { await act(async () => { expect(await hook.result.current.save()).toBe(true); }); expect(api.saveLesson).toHaveBeenCalledTimes(1); expect(vi.mocked(api.saveLesson).mock.calls[0][1].data).toEqual(before); }
  });
  it.each(['busy', 'unknown', 'auxiliary', 'exclusive'])('refuses %s instead of pretending an issued write is reversible', async (kind) => {
    vi.useFakeTimers(); const reply = deferred<LessonView>(), saveLesson = vi.fn(() => reply.promise); const { hook, store } = host({ saveLesson });
    act(() => store.getState().set({ title: '在途或失权仍保留的稿' }));
    let saving: Promise<boolean> | undefined;
    if (kind === 'busy' || kind === 'unknown') { act(() => { saving = hook.result.current.save(); }); if (kind === 'unknown') await act(async () => { reply.reject(new ApiError('RESPONSE_LOST', '隔离丢响应', 0, true)); await saving; }); }
    else act(() => { if (kind === 'auxiliary') hook.result.current.setAuxiliaryBusy(true); else hook.result.current.setExclusive(true); });
    const raw = localStorage.getItem(serverSessionKey('g3-lesson')); act(() => { expect(hook.result.current.discard()).toBe(false); });
    expect(store.getState().data.title).toBe('在途或失权仍保留的稿'); expect(localStorage.getItem(serverSessionKey('g3-lesson'))).toBe(raw);
    if (kind === 'busy') await act(async () => { reply.resolve(saved(2)); await saving; });
  });
  it('does not use a view older than the cache fixed identity as a discard baseline', () => {
    const cache = initialServerCache(saved(3)); cache.data.title = '更高基线上的唯一稿'; cache.editRevision = 4; cache.acknowledgedEditRevision = 3; writeServerCache(localStorage, cache); const raw = localStorage.getItem(serverSessionKey('g3-lesson'));
    const { hook, store, api } = host(); act(() => { expect(hook.result.current.discard()).toBe(false); });
    expect(store.getState().data.title).toBe('更高基线上的唯一稿'); expect(localStorage.getItem(serverSessionKey('g3-lesson'))).toBe(raw); expect(api.saveLesson).not.toHaveBeenCalled();
  });
});

describe('G3 keeps the local discard boundary', () => {
  it('local discard restores the acknowledged draft and prevents delayed/unmount flush from saving A; later B remains saveable', async () => {
    vi.useFakeTimers(); const original = { schemaVersion: 1 as const, revision: 7, updatedAt: '2026-10-04T00:00:00Z', data: saved().currentRevision.data };
    const repository = { load: vi.fn(async () => structuredClone(original)), save: vi.fn() }, store = createLessonStore(), notice = vi.fn();
    const hook = renderHook(() => useDraftPersistence(store, repository, notice)); await act(async () => {});
    act(() => store.getState().set({ title: '本地弃稿A' })); act(() => { expect(hook.result.current.discardPending()).toBe(true); });
    expect(store.getState().data).toEqual(original.data); expect(store.getState().past).toEqual([]);
    await act(async () => { window.dispatchEvent(new Event('pagehide')); vi.advanceTimersByTime(2400); }); expect(repository.save).not.toHaveBeenCalled();
    act(() => store.getState().set({ title: '本地新编辑B' })); await act(async () => { vi.advanceTimersByTime(600); });
    expect(repository.save).toHaveBeenCalledTimes(1); expect(repository.save.mock.calls[0][0]).toMatchObject({ revision: 8, data: { title: '本地新编辑B' } }); hook.unmount(); await act(async () => {}); expect(repository.save).toHaveBeenCalledTimes(1);
  });
  it('local issued write cannot be discarded', async () => {
    vi.useFakeTimers(); const reply = deferred<void>(), repository = { load: vi.fn(async () => null), save: vi.fn(() => reply.promise) }, store = createLessonStore(), notice = vi.fn();
    const hook = renderHook(() => useDraftPersistence(store, repository, notice)); await act(async () => {}); act(() => store.getState().set({ title: '已发出的本地稿' })); await act(async () => { vi.advanceTimersByTime(600); });
    act(() => { expect(hook.result.current.discardPending()).toBe(false); }); expect(store.getState().data.title).toBe('已发出的本地稿'); await act(async () => reply.resolve());
  });
});
