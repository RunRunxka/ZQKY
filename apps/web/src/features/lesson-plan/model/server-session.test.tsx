import { StrictMode } from 'react';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LessonView } from '@/contracts/lesson-plans';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { ApiError } from '@/services/api-client';
import { createLessonStore } from './store';
import { useServerPersistence } from './useServerPersistence';
import { initialServerCache, readServerCache, serverSessionKey, loadLegacyRaw, LEGACY_KEY, writeServerCache } from './server-cache';
import { emptyData } from './defaults';

function view(version = 1, title = '原稿', id = `fixed-${version}`): LessonView { return { protocolVersion: 2, lessonPlanId: 'lesson-a', subjectId: 'chinese', classId: 'class-a', revision: version, currentRevisionId: id, replayed: false, currentRevision: { protocolVersion: 2, lessonPlanId: 'lesson-a', revisionId: id, version, data: { ...structuredClone(emptyData), title }, contentHash: `hash-${version}`, source: 'manual', contextSnapshot: { subjectId: 'chinese', classId: 'class-a', classNameAtSave: '隔离班级', analysis: null }, analysisRunId: null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-03T00:00:00Z' } }; }
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
function api(overrides: Partial<typeof lessonPlanApi> = {}) { return { ...lessonPlanApi, getLesson: vi.fn(async () => view()), saveLesson: vi.fn(async () => view(2, '编辑2')), ...overrides }; }
beforeEach(() => { localStorage.clear(); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); localStorage.clear(); });

describe('F30-L server session author checks', () => {
  it('600ms serial save freezes input2, keeps inflight3 and writes trailing3 with newer CAS', async () => {
    vi.useFakeTimers(); const first = deferred<LessonView>(); const saveLesson = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValueOnce(view(3, '编辑3')); const store = createLessonStore(view().currentRevision.data);
    const hook = renderHook(() => useServerPersistence(store, { view: view(), api: api({ saveLesson }) }));
    act(() => store.getState().set({ title: '编辑2' })); await act(async () => { vi.advanceTimersByTime(599); }); expect(saveLesson).not.toHaveBeenCalled(); await act(async () => { vi.advanceTimersByTime(1); }); expect(saveLesson).toHaveBeenCalledTimes(1);
    act(() => store.getState().set({ title: '编辑3' })); await act(async () => { vi.advanceTimersByTime(700); }); expect(saveLesson).toHaveBeenCalledTimes(1);
    await act(async () => first.resolve(view(2, '编辑2'))); expect(store.getState().data.title).toBe('编辑3'); expect(hook.result.current.dirty).toBe(true); expect(hook.result.current.cache?.serverRevision).toBe(2);
    await act(async () => { vi.advanceTimersByTime(600); }); expect(saveLesson).toHaveBeenCalledTimes(2); expect(saveLesson.mock.calls[0][1]).toMatchObject({ expectedRevision: 1, data: { title: '编辑2' } }); expect(saveLesson.mock.calls[1][1]).toMatchObject({ expectedRevision: 2, data: { title: '编辑3' } }); expect(hook.result.current.dirty).toBe(false); expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });
  it('unknown replay preserves complete original HTTP and first metadata, never clears inflight3', async () => {
    const first = deferred<LessonView>(); const saveLesson = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValueOnce(view(2, '编辑2')); const store = createLessonStore();
    const hook = renderHook(() => useServerPersistence(store, { view: view(), api: api({ saveLesson }) }));
    act(() => store.getState().set({ title: '编辑2' })); let saving!: Promise<boolean>; act(() => { saving = hook.result.current.save(); }); await waitFor(() => expect(saveLesson).toHaveBeenCalledTimes(1)); const frozen = structuredClone(hook.result.current.cache!.operations.save);
    act(() => store.getState().set({ title: '编辑3' })); await act(async () => { first.reject(new ApiError('RESPONSE_LOST', '200响应丢失', 0, true)); await saving; }); expect(hook.result.current.syncState).toBe('unknown');
    await act(async () => { await hook.result.current.save(); }); expect(saveLesson.mock.calls[1]).toEqual(saveLesson.mock.calls[0]); expect(frozen?.metadata).toMatchObject({ originalEditGeneration: 1 }); expect(hook.result.current.cache?.acknowledgedEditRevision).toBe(1); expect(hook.result.current.dirty).toBe(true); expect(store.getState().data.title).toBe('编辑3');
    await new Promise((resolve) => setTimeout(resolve, 650)); expect(saveLesson).toHaveBeenCalledTimes(2);
  });
  it('StrictMode recovered unknown never autosends or rebinds original load/edit generations', async () => {
    const original = initialServerCache(view()); original.data.title = '保留3'; original.editRevision = 3;
    const payload = { expectedRevision: 1, data: { ...original.data, title: '原包2' }, context: null, source: 'manual' as const };
    const { stablePayloadKey } = await import('@/features/assessments/hooks'); original.operations.save = { operationId: 'original-operation', submissionId: 'original-operation', payload, payloadKey: stablePayloadKey(payload), metadata: { contextKey: 'lesson|lesson-a|save', originalEditGeneration: 2, loadGeneration: 'original-load' } }; writeServerCache(localStorage, original);
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async () => view(2, '原包2')); const store = createLessonStore(); const hook = renderHook(() => useServerPersistence(store, { view: view(), api: api({ saveLesson }) }), { wrapper: StrictMode });
    expect(saveLesson).not.toHaveBeenCalled(); expect(store.getState().data.title).toBe('保留3'); expect(hook.result.current.cache?.operations.save).toEqual(original.operations.save);
    await act(async () => { await hook.result.current.save(); }); expect(saveLesson.mock.calls[0][1]).toEqual({ ...payload, submissionId: 'original-operation' }); expect(hook.result.current.cache?.acknowledgedEditRevision).toBe(0); expect(hook.result.current.dirty).toBe(true); expect(store.getState().data.title).toBe('保留3');
  });
  it.each(['higher', 'equal-conflict'])('late ACK cannot regress a trusted %s view or clear dirty', async (kind) => {
    const first = deferred<LessonView>(); const saveLesson = vi.fn(() => first.promise), onSaved = vi.fn(), store = createLessonStore(); const services = api({ saveLesson });
    const hook = renderHook(({ current }) => useServerPersistence(store, { view: current, api: services, onSaved }), { initialProps: { current: view() } });
    act(() => store.getState().set({ title: '本机输入' })); let promise!: Promise<boolean>; act(() => { promise = hook.result.current.save(); }); await waitFor(() => expect(saveLesson).toHaveBeenCalledTimes(1));
    hook.rerender({ current: kind === 'higher' ? view(4, '他人新版本') : view(2, '可信其他身份', 'other-fixed-2') }); await act(async () => { first.resolve(view(2, '旧ACK')); await promise; });
    expect(hook.result.current.syncState).toBe('conflict'); expect(hook.result.current.dirty).toBe(true); expect(store.getState().data.title).toBe('本机输入'); expect(onSaved).not.toHaveBeenCalled(); expect(hook.result.current.latest?.currentRevisionId).toBe(kind === 'higher' ? 'fixed-4' : 'other-fixed-2');
    await act(async () => { await hook.result.current.save(); }); expect(saveLesson).toHaveBeenCalledTimes(1);
  });
  it('409 gets actual owned current body and requires manual baseline adoption', async () => {
    const saveLesson = vi.fn().mockRejectedValueOnce(new ApiError('REVISION_CONFLICT', '冲突', 409, false, undefined, { currentRevision: 5 })).mockResolvedValueOnce(view(6, '本机稿')); const services = api({ saveLesson, getLesson: vi.fn(async () => view(5, '服务器稿')) }); const store = createLessonStore(); const hook = renderHook(() => useServerPersistence(store, { view: view(), api: services }));
    act(() => store.getState().set({ title: '本机稿' })); await act(async () => { await hook.result.current.save(); }); expect(hook.result.current.syncState).toBe('conflict'); expect(hook.result.current.latest?.currentRevision.data.title).toBe('服务器稿'); expect(store.getState().data.title).toBe('本机稿'); await act(async () => { await hook.result.current.save(); }); expect(saveLesson).toHaveBeenCalledTimes(1);
    act(() => hook.result.current.chooseLatest(true)); await act(async () => { await hook.result.current.save(); }); expect(saveLesson.mock.calls[1][1].expectedRevision).toBe(5); expect(hook.result.current.dirty).toBe(false);
  });
  it('corrupt/read-failed cache remains exact and blocks HTTP; not an empty draft', () => {
    const key = serverSessionKey('lesson-a'); localStorage.setItem(key, '{damaged'); const saveLesson = vi.fn(), store = createLessonStore(); const hook = renderHook(() => useServerPersistence(store, { view: view(), api: api({ saveLesson }) })); expect(hook.result.current.syncState).toBe('cache_error'); expect(localStorage.getItem(key)).toBe('{damaged'); expect(saveLesson).not.toHaveBeenCalled();
  });
  it('failed recovery write prevents HTTP and preserves editor input', async () => {
    const storage = { getItem: vi.fn(() => null), setItem: vi.fn(() => { throw new Error('quota'); }), removeItem: vi.fn() } as unknown as Storage; const saveLesson = vi.fn(), store = createLessonStore(); const hook = renderHook(() => useServerPersistence(store, { view: view(), api: api({ saveLesson }), storage })); act(() => store.getState().set({ title: '未丢输入' })); await act(async () => { await hook.result.current.save(); }); expect(saveLesson).not.toHaveBeenCalled(); expect(store.getState().data.title).toBe('未丢输入'); expect(hook.result.current.syncState).toBe('cache_error');
  });
  it('accepted whole-field replacement retains one undo step and undo saves a new version', async () => {
    const store = createLessonStore(); const hook = renderHook(() => useServerPersistence(store, { view: view(), api: api() })); const before = structuredClone(store.getState().data); const operation = { submissionId: 'apply-one', operationId: 'apply-one', payload: {}, payloadKey: '{}', metadata: { contextKey: 'lesson|lesson-a|apply', originalEditGeneration: 0, loadGeneration: hook.result.current.loadGeneration } };
    act(() => { expect(hook.result.current.acknowledgeApplied(view(2, '只改标题样本'), operation)).toBe(true); }); expect(store.getState().past).toEqual([before]); act(() => store.getState().undo()); expect(store.getState().data).toEqual(before); expect(hook.result.current.dirty).toBe(true); expect(hook.result.current.cache?.serverRevision).toBe(2);
  });
  it('strict legacy envelope keeps raw timezone, duplicate ordered lesson types and refuses extra fields', () => {
    const data = { ...structuredClone(emptyData), lessonTypes: ['review', 'new', 'review'] }; const raw = JSON.stringify({ schemaVersion: 1, revision: 7, updatedAt: '2026-10-03T08:00:00+08:00', data }); localStorage.setItem(LEGACY_KEY, raw); expect(loadLegacyRaw(localStorage)?.raw).toBe(raw); expect(loadLegacyRaw(localStorage)?.envelope.data.lessonTypes).toEqual(data.lessonTypes); expect(localStorage.getItem(LEGACY_KEY)).toBe(raw); localStorage.setItem(LEGACY_KEY, JSON.stringify({ ...JSON.parse(raw), extra: 1 })); expect(() => loadLegacyRaw(localStorage)).toThrow('完整信封');
  });
  it('cache validates payload identity rather than silently accepting tampered content', () => {
    const cache = initialServerCache(view()); cache.operations.save = { operationId: 'same', submissionId: 'same', payloadKey: 'wrong-key', payload: {}, metadata: { contextKey: 'lesson|lesson-a|save', originalEditGeneration: 0, loadGeneration: 'load' } }; localStorage.setItem(serverSessionKey('lesson-a'), JSON.stringify(cache)); expect(() => readServerCache(localStorage, 'lesson-a')).toThrow('原操作');
  });
});
