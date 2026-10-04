'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { StoreApi } from 'zustand/vanilla';
import type { AnalysisContextInput, LessonView } from '@/contracts/lesson-plans';
import { ApiError } from '@/services/api-client';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { asApiError, stablePayloadKey, useFrozenSubmission, type FrozenSubmission } from '@/features/assessments/hooks';
import type { LessonState } from './store';
import { assertWriteSize, initialServerCache, readServerCache, serverSessionKey, writeServerCache, type LessonOperationKind, type SaveContent, type ServerLessonCache } from './server-cache';

export interface ServerBinding { view: LessonView; api: typeof lessonPlanApi; storage?: Storage; onSaved?: (view: LessonView) => void }
export interface ServerSessionIdentity { documentId: string; loadGeneration: string; writeEpoch: number }
export type ServerSyncState = 'idle' | 'saving' | 'saved' | 'failed' | 'conflict' | 'unknown' | 'cache_error';
export function useServerPersistence(store: StoreApi<LessonState>, binding?: ServerBinding) {
  const save = useFrozenSubmission<SaveContent, LessonView>();
  const releaseSave = save.release, recoverSave = save.recoverFrozen;
  const cache = useRef<ServerLessonCache | null>(null);
  const known = useRef<LessonView | null>(null);
  const bindingRef = useRef(binding); bindingRef.current = binding;
  const mounted = useRef(false), hydration = useRef(false), blocked = useRef(false), exclusive = useRef(false), auxiliaryBusy = useRef(false);
  const loadGeneration = useRef('');
  const writeEpoch = useRef(0), paused = useRef<'discarded' | 'remove_failed' | null>(null);
  const discardGeneration = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const running = useRef<Promise<boolean> | null>(null);
  const auto = useRef<(epoch: number) => void>(() => {});
  const [, redraw] = useState(0);
  const [ready, setReady] = useState(false);
  const [syncState, setSyncState] = useState<ServerSyncState>('idle');
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState('');
  const notify = useCallback(() => { if (mounted.current) redraw((number) => number + 1); }, []);
  const stateRef = useRef(syncState); stateRef.current = syncState;
  const renderedSession = cache.current ? Object.freeze({ documentId: cache.current.documentId, loadGeneration: loadGeneration.current, writeEpoch: writeEpoch.current }) : null;
  const storage = () => bindingRef.current?.storage ?? localStorage;
  const persist = useCallback(() => {
    if (!mounted.current || paused.current) return paused.current === 'discarded';
    if (blocked.current || !cache.current) return false;
    try { writeServerCache(bindingRef.current?.storage ?? localStorage, cache.current); return true; }
    catch (cause) { if (mounted.current) { setError(new ApiError('RECOVERY_CACHE_FAILED', `恢复缓存写入失败：${(cause as Error).message}。输入保持，发送暂停。`, 503, true)); setSyncState('cache_error'); } return false; }
  }, []);
  const schedule = () => { clearTimeout(timer.current); const epoch = writeEpoch.current; timer.current = setTimeout(() => auto.current(epoch), 600); };
  const docId = binding?.view.lessonPlanId;
  useEffect(() => {
    if (!docId) { setReady(false); return; }
    mounted.current = true; blocked.current = false; paused.current = null; writeEpoch.current += 1; loadGeneration.current = crypto.randomUUID();
    releaseSave(); setReady(false); setError(null); setNotice(''); setSyncState('idle');
    const view = bindingRef.current!.view; known.current = structuredClone(view);
    try {
      const restored = readServerCache(bindingRef.current?.storage ?? localStorage, docId);
      cache.current = restored ?? initialServerCache(view);
      const current = cache.current;
      hydration.current = true; store.getState().hydrate(structuredClone(current.data), current.editRevision); hydration.current = false;
      if (current.operations.save && !recoverSave(current.operations.save as FrozenSubmission<SaveContent>)) throw new Error('原保存操作无法恢复');
      if (Object.values(current.operations).some(Boolean)) { setSyncState('unknown'); setNotice('原操作结果未知；恢复不会自动发送，请重试原操作。'); }
      else if (current.serverRevision < view.revision || (current.serverRevision === view.revision && current.serverRevisionId !== view.currentRevisionId)) {
        if (current.editRevision === current.acknowledgedEditRevision) {
          cache.current = initialServerCache(view); hydration.current = true; store.getState().hydrate(cache.current.data, 0); hydration.current = false;
        } else { setSyncState('conflict'); setNotice('后台版本较新；本机编辑保持，请查看差异后明确选择版本。'); }
      } else setSyncState(current.editRevision === current.acknowledgedEditRevision ? 'saved' : 'idle');
      setReady(true);
    } catch (cause) { blocked.current = true; cache.current = null; setError(new ApiError('RECOVERY_CACHE_FAILED', `恢复缓存读取失败：${(cause as Error).message}。原字节未覆盖，保存暂停。`, 503, true)); setSyncState('cache_error'); setReady(true); }
    const unsubscribe = store.subscribe((next, previous) => {
      if (hydration.current || next.revision === previous.revision || !cache.current) return;
      if (paused.current === 'discarded') { paused.current = null; writeEpoch.current += 1; setNotice('离开未完成；当前新编辑可正常保存。'); }
      cache.current.data = structuredClone(next.data); cache.current.editRevision = next.revision;
      cache.current.source = 'manual';
      if (persist() && !Object.values(cache.current.operations).some(Boolean) && stateRef.current !== 'conflict' && !exclusive.current) {
        setSyncState('idle'); clearTimeout(timer.current); const epoch = writeEpoch.current; timer.current = setTimeout(() => auto.current(epoch), 600);
      }
      notify();
    });
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (cache.current && (cache.current.editRevision !== cache.current.acknowledgedEditRevision || Object.values(cache.current.operations).some(Boolean))) { persist(); event.preventDefault(); event.returnValue = ''; }
    };
    const pageHide = () => { if (cache.current) persist(); };
    window.addEventListener('beforeunload', beforeUnload); window.addEventListener('pagehide', pageHide);
    return () => { mounted.current = false; writeEpoch.current += 1; unsubscribe(); clearTimeout(timer.current); window.removeEventListener('beforeunload', beforeUnload); window.removeEventListener('pagehide', pageHide); };
  }, [docId, store, releaseSave, recoverSave, persist, notify]);
  useEffect(() => {
    if (!binding || !cache.current || binding.view.lessonPlanId !== cache.current.documentId) return;
    const view = binding.view;
    if (!known.current || view.revision >= known.current.revision) known.current = structuredClone(view);
    if (view.revision > cache.current.serverRevision || (view.revision === cache.current.serverRevision && view.currentRevisionId !== cache.current.serverRevisionId)) {
      if (!Object.values(cache.current.operations).some(Boolean)) { setSyncState('conflict'); setNotice('后台版本或固定修订身份已变化；本机稿保持，请对照后选择。'); }
    }
  }, [binding]);
  function acceptReceipt(view: LessonView): boolean {
    const current = cache.current, latest = known.current;
    if (!current || !latest || view.lessonPlanId !== current.documentId || view.revision < current.serverRevision || (view.revision === current.serverRevision && view.currentRevisionId !== current.serverRevisionId) || view.revision < latest.revision ||
        (view.revision === latest.revision && view.currentRevisionId !== latest.currentRevisionId)) {
      setSyncState('conflict'); setNotice('原操作已收到回执；已知后台版本较新或固定身份冲突，本机输入与版本保持。'); return false;
    }
    known.current = structuredClone(view); current.serverRevision = view.revision; current.serverRevisionId = view.currentRevisionId; return true;
  }
  async function refreshLatest() {
    if (!bindingRef.current || !cache.current) return;
    const identity = cache.current.documentId, load = loadGeneration.current, epoch = writeEpoch.current;
    try {
      const view = await bindingRef.current.api.getLesson(identity);
      if (!mounted.current || load !== loadGeneration.current || epoch !== writeEpoch.current || cache.current?.documentId !== identity) return;
      if (!known.current || view.revision >= known.current.revision) known.current = structuredClone(view);
      if (view.revision > cache.current.serverRevision || (view.revision === cache.current.serverRevision && view.currentRevisionId !== cache.current.serverRevisionId)) setSyncState('conflict');
      notify();
      return view;
    } catch (cause) { if (mounted.current && load === loadGeneration.current && epoch === writeEpoch.current && cache.current?.documentId === identity) setError(asApiError(cause)); }
  }
  async function saveOnce(): Promise<boolean> {
    clearTimeout(timer.current);
    if (running.current) return running.current;
    const current = cache.current, active = bindingRef.current;
    if (!mounted.current || !current || !active || blocked.current || exclusive.current) return false;
    if (paused.current === 'discarded') return current.editRevision === current.acknowledgedEditRevision;
    // A failed removal paused automatic writes. Only this explicit save may resume them.
    if (paused.current === 'remove_failed') { paused.current = null; writeEpoch.current += 1; }
    const unknown = current.operations.save !== null;
    if (Object.entries(current.operations).some(([kind, operation]) => kind !== 'save' && operation)) return false;
    if (!unknown && (stateRef.current === 'conflict' || (known.current && (known.current.revision > current.serverRevision || (known.current.revision === current.serverRevision && known.current.currentRevisionId !== current.serverRevisionId))))) return false;
    if (!unknown && current.editRevision === current.acknowledgedEditRevision) return true;
    const identity = current.documentId, load = loadGeneration.current, epoch = writeEpoch.current;
    const promise = (async () => {
      setSyncState('saving'); setError(null); const failure: { error: ApiError | null } = { error: null };
      const receipt = await save.submitWithReceipt({ expectedRevision: current.serverRevision, data: structuredClone(current.data), context: structuredClone(current.context), source: current.source }, async (operation) => {
        current.operations.save = operation;
        if (!persist()) { failure.error = new ApiError('RECOVERY_CACHE_FAILED', '发送前恢复缓存写入失败，尚未发送HTTP', 503, true); throw failure.error; }
        try { const body = { ...operation.payload, submissionId: operation.submissionId }; assertWriteSize(body); return await active.api.saveLesson(identity, body); }
        catch (cause) { failure.error = asApiError(cause); throw cause; }
      }, { contextKey: `lesson|${identity}|save`, originalEditGeneration: current.editRevision, loadGeneration: load });
      if (!mounted.current || load !== loadGeneration.current || epoch !== writeEpoch.current || paused.current || cache.current?.documentId !== identity) return false;
      if (!receipt) {
        if (failure.error && failure.error.status !== 0) { if (failure.error.code !== 'RECOVERY_CACHE_FAILED') { current.operations.save = null; persist(); } setError(failure.error); setSyncState(failure.error.status === 409 ? 'conflict' : failure.error.code === 'RECOVERY_CACHE_FAILED' ? 'cache_error' : 'failed'); if (failure.error.status === 409) await refreshLatest(); }
        else { setSyncState('unknown'); setNotice('保存结果未知，请重试原保存包；当前编辑和首次操作代次保持。'); }
        notify(); return false;
      }
      if (!receipt.current || receipt.operation.metadata?.contextKey !== `lesson|${identity}|save`) return false;
      current.operations.save = null;
      if (!acceptReceipt(receipt.result)) { persist(); notify(); return false; }
      const original = receipt.operation.metadata;
      if (original.loadGeneration === loadGeneration.current) current.acknowledgedEditRevision = Math.max(current.acknowledgedEditRevision, original.originalEditGeneration);
      const clean = current.editRevision === current.acknowledgedEditRevision;
      setSyncState(clean ? 'saved' : 'idle'); setNotice(clean ? '后台稿已保存。' : '原稿已保存；之后的编辑仍保留，尚未保存。');
      persist(); active.onSaved?.(receipt.result); notify();
      if (!clean && !unknown) schedule();
      return clean;
    })();
    running.current = promise;
    try { return await promise; }
    finally { if (running.current === promise) running.current = null; }
  }
  auto.current = (epoch) => { if (mounted.current && epoch === writeEpoch.current && !paused.current && cache.current && !Object.values(cache.current.operations).some(Boolean) && stateRef.current !== 'conflict' && stateRef.current !== 'cache_error') void saveOnce(); };
  async function flush(): Promise<void> {
    clearTimeout(timer.current);
    if (!mounted.current || paused.current === 'remove_failed') throw new Error('恢复缓存删除失败，输入保持，自动保存已暂停；请明确保存或重试放弃');
    if (paused.current === 'discarded') return;
    if (!cache.current || blocked.current) throw new Error('恢复缓存不可用，保存暂停');
    if (running.current && !(await running.current) && stateRef.current !== 'idle') throw new Error('在途保存尚未成功，原稿保持');
    if (Object.values(cache.current.operations).some(Boolean)) throw new Error('原操作结果未知，请显式恢复后继续');
    if (cache.current.editRevision !== cache.current.acknowledgedEditRevision && !(await saveOnce())) throw new Error('后台保存未完成，原稿保持');
    if (cache.current.editRevision !== cache.current.acknowledgedEditRevision) return flush();
  }
  function captureSession(): Readonly<ServerSessionIdentity> | null {
    if (!mounted.current || !cache.current) return null;
    return Object.freeze({ documentId: cache.current.documentId, loadGeneration: loadGeneration.current, writeEpoch: writeEpoch.current });
  }
  function isCurrentSession(session: Readonly<ServerSessionIdentity> | null): boolean {
    return !!session && mounted.current && !blocked.current && paused.current !== 'remove_failed' &&
      cache.current?.documentId === session.documentId && loadGeneration.current === session.loadGeneration && writeEpoch.current === session.writeEpoch;
  }
  function setContext(context: AnalysisContextInput | null, session = renderedSession): boolean {
    if (!cache.current || !isCurrentSession(session) || exclusive.current) return false;
    if (stablePayloadKey(context) === stablePayloadKey(cache.current.context)) return true;
    cache.current.context = structuredClone(context); store.getState().set({});
    return true;
  }
  function chooseLatest(keepInput: boolean) {
    if (!cache.current || !known.current || running.current || Object.values(cache.current.operations).some(Boolean) || blocked.current) return;
    const current = cache.current, view = known.current;
    if (view.revision < current.serverRevision || (view.revision === current.serverRevision && view.currentRevisionId !== current.serverRevisionId)) return;
    current.serverRevision = view.revision; current.serverRevisionId = view.currentRevisionId;
    if (!keepInput) { hydration.current = true; store.getState().replace(view.currentRevision.data); hydration.current = false; current.data = structuredClone(view.currentRevision.data); current.editRevision = store.getState().revision; current.acknowledgedEditRevision = current.editRevision; const source = initialServerCache(view); current.context = source.context; }
    setSyncState(keepInput ? 'idle' : 'saved'); setError(null); setNotice(keepInput ? '已明确采用后台版本基线，本机输入保持；请再次保存。' : '已明确恢复后台正文。'); persist(); notify();
  }
  function setOperation(kind: LessonOperationKind, operation: FrozenSubmission<unknown> | null) {
    if (!mounted.current || !cache.current || blocked.current || paused.current) throw new Error('恢复缓存不可用或离开后的旧写入已暂停');
    cache.current.operations[kind] = operation;
    if (!persist()) throw new Error('发送前恢复缓存写入失败');
    notify();
  }
  function acknowledgeApplied(view: LessonView, operation: FrozenSubmission<unknown>): boolean {
    if (!cache.current || !mounted.current || paused.current || !acceptReceipt(view)) return false;
    if (operation.metadata?.loadGeneration !== loadGeneration.current || operation.metadata.originalEditGeneration !== store.getState().revision) { if (cache.current.editRevision === cache.current.acknowledgedEditRevision && stablePayloadKey(cache.current.data) !== stablePayloadKey(view.currentRevision.data)) { hydration.current = true; store.getState().set({}); hydration.current = false; cache.current.editRevision = store.getState().revision; } persist(); setSyncState(cache.current.editRevision === cache.current.acknowledgedEditRevision ? 'saved' : 'idle'); setNotice('原采用操作已确认，之后的本机输入保持；请对照后台版本。'); notify(); return false; }
    hydration.current = true; store.getState().replace(structuredClone(view.currentRevision.data)); hydration.current = false;
    cache.current.data = structuredClone(store.getState().data); cache.current.editRevision = store.getState().revision; cache.current.acknowledgedEditRevision = cache.current.editRevision;
    setSyncState('saved'); persist(); bindingRef.current?.onSaved?.(view); notify(); return true;
  }
  const setExclusive = useCallback((value: boolean) => { exclusive.current = value; notify(); }, [notify]);
  const setAuxiliaryBusy = useCallback((value: boolean) => { auxiliaryBusy.current = value; notify(); }, [notify]);
  function discard(): boolean {
    const current = cache.current, trusted = known.current;
    if (!mounted.current || !current || !trusted || blocked.current || running.current || save.busy || auxiliaryBusy.current || exclusive.current || stateRef.current === 'cache_error' || Object.values(current.operations).some(Boolean)) return false;
    if (trusted.lessonPlanId !== current.documentId || trusted.revision !== current.serverRevision || trusted.currentRevisionId !== current.serverRevisionId || trusted.currentRevision.lessonPlanId !== current.documentId || trusted.currentRevision.revisionId !== current.serverRevisionId || trusted.currentRevision.version !== current.serverRevision) {
      setNotice('可信已保存正文与当前固定基线不一致；请读取并人工对照后再放弃。'); return false;
    }
    // Revoke queued callbacks before touching storage. Hydration below does not create an edit.
    clearTimeout(timer.current); writeEpoch.current += 1; paused.current = 'remove_failed';
    try { storage().removeItem(serverSessionKey(current.documentId)); }
    catch (cause) {
      setError(new ApiError('RECOVERY_CACHE_FAILED', `恢复缓存删除失败：${(cause as Error).message}。当前输入保持，自动保存已暂停；请明确保存或重试放弃。`, 503, true));
      setSyncState('failed'); notify(); return false;
    }
    const clean = initialServerCache(trusted), revision = store.getState().revision;
    clean.editRevision = revision; clean.acknowledgedEditRevision = revision;
    cache.current = clean; paused.current = 'discarded'; discardGeneration.current += 1;
    hydration.current = true; store.getState().hydrate(structuredClone(clean.data), revision); hydration.current = false;
    releaseSave(); setError(null); setSyncState('saved'); setNotice('已放弃未保存编辑并恢复可信正文；若离开未完成，之后的新编辑可重新保存。'); notify(); return true;
  }
  return { ready, syncState, error, notice, cache: cache.current, latest: known.current,
    loadGeneration: loadGeneration.current, writeEpoch: writeEpoch.current, discardGeneration: discardGeneration.current, busy: save.busy || !!running.current || auxiliaryBusy.current,
    exclusive: exclusive.current,
    dirty: !!cache.current && cache.current.editRevision !== cache.current.acknowledgedEditRevision,
    unknown: !!cache.current && Object.values(cache.current.operations).some(Boolean),
    save: saveOnce, flush, keep: persist, refreshLatest, setContext, captureSession, isCurrentSession, chooseLatest, setOperation, acknowledgeApplied,
    setExclusive,
    setAuxiliaryBusy,
    markRule() { if (cache.current && !paused.current) { cache.current.source = 'rule'; persist(); } },
    discard,
  };
}
export type ServerPersistence = ReturnType<typeof useServerPersistence>;
