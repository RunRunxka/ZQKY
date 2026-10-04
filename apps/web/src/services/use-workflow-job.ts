'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { isJobTerminal, type JobDomain, type JobView } from '@/contracts/teaching-loop';
import { ApiError } from './api-client';
import { cancelJob, observeJob, retryJob, retryObservationWindow, type ObserveJobOptions } from './workflow-jobs-api';

/** 公共任务观察：queued 收据接受一次 claim；显式操作绑定任务、尝试和本地观察代次。 */
export function useObservedJob(domain: JobDomain, options: {
  onTerminal?: (view: JobView) => void;
  polling?: Pick<ObserveJobOptions, 'sleep' | 'now'>;
} = {}) {
  const [view, setView] = useState<JobView | null>(null);
  const [observing, setObserving] = useState(false);
  const [pending, setPending] = useState<'retry' | 'cancel' | null>(null);
  const [actionError, setActionError] = useState<ApiError | null>(null);
  const [observationNotice, setObservationNotice] = useState<string | null>(null);
  const alive = useRef(true);
  const epoch = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const current = useRef<JobView | null>(null);
  const busy = useRef(false);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; epoch.current += 1; controller.current?.abort(); };
  }, []);

  const reset = useCallback(() => {
    epoch.current += 1;
    controller.current?.abort();
    controller.current = null;
    current.current = null;
    busy.current = false;
    setPending(null); setView(null); setObserving(false); setActionError(null); setObservationNotice(null);
  }, []);

  useEffect(() => { reset(); }, [domain, reset]);

  const adopt = useCallback((receipt: JobView) => {
    if (!alive.current || receipt.domain !== domain) return;
    epoch.current += 1;
    const token = epoch.current;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    current.current = receipt;
    busy.current = false;
    setPending(null); setView(receipt); setActionError(null); setObservationNotice(null);
    if (isJobTerminal(receipt.state)) {
      setObserving(false); optionsRef.current.onTerminal?.(receipt); return;
    }
    setObserving(true);
    const window = receipt.state === 'queued' ? retryObservationWindow(receipt)
      : { minAttempt: receipt.attempt, maxAttempt: receipt.attempt };
    void observeJob(domain, receipt.jobId, {
      ...window, ...optionsRef.current.polling, signal: abort.signal,
      onUpdate: (next) => {
        if (!alive.current || token !== epoch.current || abort.signal.aborted || next.jobId !== receipt.jobId) return;
        // 保持同代观察的单向尝试号，迟到 queued(N) 不能回写已观察的 running(N+1)。
        if (next.attempt < (current.current?.attempt ?? receipt.attempt)) return;
        current.current = next; setView(next);
        if (isJobTerminal(next.state)) {
          setObserving(false); optionsRef.current.onTerminal?.(next);
        }
      },
    }).then((terminal) => {
      if (!alive.current || token !== epoch.current || abort.signal.aborted) return;
      setObserving(false);
      if (!terminal) setObservationNotice('任务已被新的尝试接管，请刷新后查看最新状态。');
    }).catch((cause: unknown) => {
      if (!alive.current || token !== epoch.current || abort.signal.aborted) return;
      setObserving(false);
      setActionError(cause instanceof ApiError ? cause : new ApiError('REQUEST_FAILED', cause instanceof Error ? cause.message : '读取任务失败', 0, true));
    });
  }, [domain]);

  const operate = useCallback((action: 'retry' | 'cancel') => {
    const active = current.current;
    if (!active || busy.current) return;
    const token = epoch.current;
    busy.current = true; setPending(action); setActionError(null);
    const run = action === 'retry' ? retryJob : cancelJob;
    void run(domain, active.jobId).then((receipt) => {
      if (!alive.current || token !== epoch.current) return;
      busy.current = false; setPending(null);
      // 同一任务也不能让旧尝试或意外的后续两次尝试劫持本轮操作。
      if (receipt.jobId !== active.jobId || receipt.attempt < active.attempt || receipt.attempt > active.attempt + 1) {
        setObservationNotice('操作响应已过期，请刷新查看任务。'); return;
      }
      adopt(receipt);
    }).catch((cause: unknown) => {
      if (!alive.current || token !== epoch.current) return;
      busy.current = false; setPending(null);
      setActionError(cause instanceof ApiError ? cause : new ApiError('REQUEST_FAILED', cause instanceof Error ? cause.message : '任务操作失败', 0, true));
    });
  }, [adopt, domain]);

  return { view, observing, pending, pendingLabel: pending === 'retry' ? '正在重试…' : pending === 'cancel' ? '正在取消…' : null,
    actionError, observationNotice, adopt, reset,
    retry: useCallback(() => operate('retry'), [operate]),
    cancel: useCallback(() => operate('cancel'), [operate]),
  };
}
