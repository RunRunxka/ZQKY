'use client';
import { useEffect, useRef, useState } from 'react';
import { ApiError } from '@/services/api-client';
import { asApiError, stablePayloadKey, useFrozenSubmission, type FrozenSubmission, type SubmissionReceipt } from '@/features/assessments/hooks';
import { assertWriteSize, validateOperation } from './server-cache';

export interface OperationRecovery {
  ready: boolean;
  read: () => FrozenSubmission<unknown> | null;
  write: (operation: FrozenSubmission<unknown> | null) => void;
  prepare?: (operation: FrozenSubmission<unknown>) => void;
  verifyWrite?: () => boolean | Promise<boolean>;
}
export type LessonCleanupOutcome<T, R> =
  | { type: 'success'; operation: FrozenSubmission<T>; receipt: SubmissionReceipt<T, R> }
  | { type: 'failure'; operation: FrozenSubmission<T>; error: ApiError };
export function browserOperationRecovery(key: string, storage?: Storage): OperationRecovery {
  return { ready: true,
    read() { const raw = (storage ?? localStorage).getItem(key); if (raw === null) return null; const parsed = JSON.parse(raw); if (parsed.schemaVersion !== 1 || !parsed.operation) throw new Error('操作恢复缓存结构不正确'); return parsed.operation; },
    write(operation) { if (operation) (storage ?? localStorage).setItem(key, JSON.stringify({ schemaVersion: 1, operation })); else (storage ?? localStorage).removeItem(key); },
  };
}
function clearAcknowledgedPackage(adapter: OperationRecovery, operation: FrozenSubmission<unknown>, contextKey: string, isCurrent: () => boolean) {
  const requireCurrent = () => { if (!isCurrent()) throw new Error('明确结果的原操作会话已变化，缓存保持'); };
  requireCurrent();
  validateOperation(operation, contextKey);
  const existing = adapter.read();
  if (existing !== null) {
    validateOperation(existing, contextKey);
    if (stablePayloadKey(existing) !== stablePayloadKey(operation)) throw new Error('待清理缓存不属于本次明确结果的原操作，原字节保持');
  }
  requireCurrent();
  // Storage read/remove is not an atomic cross-tab compare-and-swap.
  adapter.write(null);
  if (adapter.read() !== null) throw new Error('原操作恢复包清理后核验不一致');
  requireCurrent();
}
function exactFrozenOperationKey(operation: FrozenSubmission<unknown>): string {
  return stablePayloadKey(operation);
}
function writeOwnedPackage(adapter: OperationRecovery, operation: FrozenSubmission<unknown>, contextKey: string, isCurrent: () => boolean) {
  const requireCurrent = () => { if (!isCurrent()) throw new Error('原操作写入的会话已变化，原字节保持'); };
  requireCurrent();
  validateOperation(operation, contextKey);
  // 共享键可能属于另一已打开会话：读取失败或坏包不能当空，完整 foreign 包必须原字节保持并阻止本次发送。
  const existing = adapter.read();
  if (existing !== null) {
    validateOperation(existing, contextKey);
    if (exactFrozenOperationKey(existing) !== exactFrozenOperationKey(operation)) throw new Error('当前恢复缓存已属于另一原操作，原字节保持');
  }
  requireCurrent();
  adapter.prepare?.(operation);
  requireCurrent();
  adapter.write(operation);
  const written = adapter.read();
  if (written === null || exactFrozenOperationKey(written) !== exactFrozenOperationKey(operation)) throw new Error('原操作恢复包写后核验不一致');
  requireCurrent();
}
export function useLessonOperation<T, R>(contextKey: string, recovery: OperationRecovery) {
  const submission = useFrozenSubmission<T, R>();
  const recover = submission.recoverFrozen, release = submission.release;
  const [cacheError, setCacheError] = useState('');
  const [ready, setReady] = useState(false);
  const blocked = useRef(false), alive = useRef(false);
  const identity = useRef(contextKey); identity.current = contextKey;
  const recoveryRef = useRef(recovery); recoveryRef.current = recovery;
  const ownLoad = useRef('');
  const lastFailure = useRef<ApiError | null>(null);
  const recoveryFailure = useRef<{ kind: 'read' | 'write' | 'cleanup'; operation: FrozenSubmission<T> | null; contextKey: string; load: string; outcome: LessonCleanupOutcome<T, R> | null } | null>(null);
  const unsent = useRef(false);
  const [, redraw] = useState(0);
  useEffect(() => {
    if (!recovery.ready) return;
    alive.current = true; ownLoad.current = crypto.randomUUID(); blocked.current = false; recoveryFailure.current = null; unsent.current = false; setReady(false); setCacheError(''); release();
    try { const operation = recoveryRef.current.read(); if (operation) { validateOperation(operation, contextKey); if (!recover(operation as FrozenSubmission<T>)) throw new Error('原操作恢复失败'); } setReady(true); }
    catch (cause) { blocked.current = true; recoveryFailure.current = { kind: 'read', operation: null, contextKey, load: ownLoad.current, outcome: null }; setCacheError(`操作恢复缓存读取失败：${(cause as Error).message}。原字节保持，发送暂停。`); }
    return () => { alive.current = false; };
  }, [contextKey, recovery.ready, recover, release]);
  async function run(payload: T, send: (operation: FrozenSubmission<T>) => Promise<R>, editRevision: number, load = ownLoad.current): Promise<SubmissionReceipt<T, R> | null> {
    if (!ready || blocked.current || identity.current !== contextKey || !alive.current) return null;
    const currentIdentity = contextKey, currentLoad = ownLoad.current, originalUnknown = submission.phase === 'unknown' && !unsent.current; const failure: { error: ApiError | null } = { error: null };
    const sameLiveSession = () => alive.current && identity.current === currentIdentity && ownLoad.current === currentLoad;
    const sent: { operation: FrozenSubmission<T> | null } = { operation: null };
    lastFailure.current = null;
    const receipt = await submission.submitWithReceipt(payload, async (operation) => {
      sent.operation = operation;
      try { writeOwnedPackage(recoveryRef.current, operation, currentIdentity, sameLiveSession); }
      catch (cause) { blocked.current = true; unsent.current = !originalUnknown; recoveryFailure.current = { kind: 'write', operation: structuredClone(operation), contextKey: currentIdentity, load: currentLoad, outcome: null }; failure.error = new ApiError('RECOVERY_CACHE_FAILED', `发送前恢复缓存写入失败：${(cause as Error).message}。${originalUnknown ? '此次未发送HTTP；原操作结果仍未知，须重放原包。' : '尚未发送HTTP。'}`, 503, true); setCacheError(failure.error.message); throw failure.error; }
      try { assertWriteSize({ ...operation.payload, submissionId: operation.submissionId }); unsent.current = false; return await send(operation); } catch (cause) { failure.error = asApiError(cause); throw cause; }
    }, { contextKey, originalEditGeneration: editRevision, loadGeneration: load });
    if (!alive.current || identity.current !== currentIdentity || ownLoad.current !== currentLoad) return receipt;
    lastFailure.current = failure.error;
    const outcome: LessonCleanupOutcome<T, R> | null = receipt?.current && receipt.operation.metadata?.contextKey === currentIdentity
      ? { type: 'success', operation: receipt.operation, receipt }
      : sent.operation && failure.error && failure.error.status !== 0 && failure.error.code !== 'RECOVERY_CACHE_FAILED'
        ? { type: 'failure', operation: sent.operation, error: failure.error } : null;
    if (outcome) {
      try { clearAcknowledgedPackage(recoveryRef.current, outcome.operation, currentIdentity, sameLiveSession); }
      catch (cause) { if (sameLiveSession()) { blocked.current = true; recoveryFailure.current = { kind: 'cleanup', operation: outcome.operation, contextKey: currentIdentity, load: currentLoad, outcome }; setCacheError(`已收到明确结果，但操作恢复缓存清理失败：${(cause as Error).message}。请重试缓存清理；不会重新发送HTTP。`); } }
    }
    return receipt;
  }
  async function retryRecoveryWrite(): Promise<boolean> {
    const failed = recoveryFailure.current, adapter = recoveryRef.current, load = ownLoad.current;
    if (!alive.current || identity.current !== contextKey || !ready || submission.busy || !failed || failed.kind === 'read' || failed.contextKey !== contextKey || failed.load !== load) return false;
    const operation = failed.kind === 'write' ? failed.operation : null;
    const same = () => alive.current && identity.current === contextKey && ownLoad.current === load && recoveryFailure.current === failed && failed.contextKey === contextKey && !submission.busy;
    try {
      if (failed.kind === 'cleanup') {
        clearAcknowledgedPackage(adapter, failed.operation!, contextKey, same);
      } else {
        if (!operation) throw new Error('原操作恢复包缺失，无法重试写入');
        writeOwnedPackage(adapter, operation, contextKey, same);
      }
      if (adapter.verifyWrite && !(await adapter.verifyWrite())) throw new Error('完整后台恢复包尚未核验');
      await Promise.resolve();
      if (!same()) return false;
      if (operation && !recover(operation)) throw new Error('原操作身份无法保持，恢复暂停');
      blocked.current = false; recoveryFailure.current = null; setCacheError(''); redraw((value) => value + 1); return true;
    } catch (cause) { if (same()) setCacheError(`恢复缓存重试失败：${(cause as Error).message}。原操作与当前输入保持，未发送HTTP。`); return false; }
  }
  return { ...submission, state: submission.phase, pending: submission.frozen, ready, cacheError, loadGeneration: ownLoad.current, run, lastFailure: () => lastFailure.current,
    recoveryBlocked: blocked.current, canRetryRecovery: !!recoveryFailure.current && recoveryFailure.current.kind !== 'read', recoveryKind: recoveryFailure.current?.kind ?? null,
    cleanupOutcome: () => { const failed = recoveryFailure.current; return alive.current && identity.current === contextKey && failed?.kind === 'cleanup' && failed.contextKey === contextKey && failed.load === ownLoad.current ? failed.outcome : null; },
    resultUnknown: (submission.phase === 'unknown' || recoveryFailure.current?.kind === 'write') && !unsent.current, isRecoveryBlocked: () => blocked.current, retryRecoveryWrite };
}
