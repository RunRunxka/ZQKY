'use client';
import { useEffect, useRef, useState } from 'react';
import { ApiError } from '@/services/api-client';
import { asApiError, useFrozenSubmission, type FrozenSubmission, type SubmissionReceipt } from '@/features/assessments/hooks';
import { assertWriteSize, validateOperation } from './server-cache';

export interface OperationRecovery {
  ready: boolean;
  read: () => FrozenSubmission<unknown> | null;
  write: (operation: FrozenSubmission<unknown> | null) => void;
}
export function browserOperationRecovery(key: string, storage?: Storage): OperationRecovery {
  return { ready: true,
    read() { const raw = (storage ?? localStorage).getItem(key); if (raw === null) return null; const parsed = JSON.parse(raw); if (parsed.schemaVersion !== 1 || !parsed.operation) throw new Error('操作恢复缓存结构不正确'); return parsed.operation; },
    write(operation) { if (operation) (storage ?? localStorage).setItem(key, JSON.stringify({ schemaVersion: 1, operation })); else (storage ?? localStorage).removeItem(key); },
  };
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
  useEffect(() => {
    if (!recovery.ready) return;
    alive.current = true; ownLoad.current = crypto.randomUUID(); blocked.current = false; setReady(false); setCacheError(''); release();
    try { const operation = recoveryRef.current.read(); if (operation) { validateOperation(operation, contextKey); if (!recover(operation as FrozenSubmission<T>)) throw new Error('原操作恢复失败'); } setReady(true); }
    catch (cause) { blocked.current = true; setCacheError(`操作恢复缓存读取失败：${(cause as Error).message}。原字节保持，发送暂停。`); }
    return () => { alive.current = false; };
  }, [contextKey, recovery.ready, recover, release]);
  async function run(payload: T, send: (operation: FrozenSubmission<T>) => Promise<R>, editRevision: number, load = ownLoad.current): Promise<SubmissionReceipt<T, R> | null> {
    if (!ready || blocked.current) return null;
    const currentIdentity = contextKey; const failure: { error: ApiError | null } = { error: null };
    lastFailure.current = null;
    const receipt = await submission.submitWithReceipt(payload, async (operation) => {
      try { recoveryRef.current.write(operation); }
      catch (cause) { blocked.current = true; failure.error = new ApiError('RECOVERY_CACHE_FAILED', `发送前恢复缓存写入失败：${(cause as Error).message}。尚未发送HTTP。`, 503, true); setCacheError(failure.error.message); throw failure.error; }
      try { assertWriteSize({ ...operation.payload, submissionId: operation.submissionId }); return await send(operation); } catch (cause) { failure.error = asApiError(cause); throw cause; }
    }, { contextKey, originalEditGeneration: editRevision, loadGeneration: load });
    if (!alive.current || identity.current !== currentIdentity) return receipt;
    lastFailure.current = failure.error;
    if ((receipt?.current && receipt.operation.metadata?.contextKey === currentIdentity) || (failure.error && failure.error.status !== 0 && failure.error.code !== 'RECOVERY_CACHE_FAILED')) {
      try { recoveryRef.current.write(null); } catch (cause) { blocked.current = true; setCacheError(`回执已收到，但操作恢复缓存清理失败：${(cause as Error).message}。请保留原稿并重试原包。`); }
    }
    return receipt;
  }
  return { ...submission, state: submission.phase, pending: submission.frozen, ready, cacheError, loadGeneration: ownLoad.current, run, lastFailure: () => lastFailure.current };
}
