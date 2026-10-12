'use client';

/**
 * `teaching` 域后台任务观察客户端（重建期最小解耦，R5-FE 2026-10-11）。
 *
 * 归档实现在 `@/services/workflow-jobs-api` + `@/services/use-workflow-job`（跨域公共任务客户端：
 * knowledge / question / teaching 三域共用）；重建期这两个公共件与其冻结契约
 * `@/contracts/teaching-loop` 尚未回归，而试卷页的「AI 知识点关联建议」只需要 **teaching 域**的
 * 创建后观察、取消与重试。本文件据此以最小体积复刻同一份 HTTP 契约，**不是新协议**：
 *
 *   GET  /api/v1/workflow-jobs/{jobId}?domain=teaching
 *   POST /api/v1/workflow-jobs/{jobId}/cancel   body {domain:'teaching'}
 *   POST /api/v1/workflow-jobs/{jobId}/retry    body {domain:'teaching'}
 *
 * 行为与归档一致：
 * - 六态显式：只有服务端给出的终态才算结束——轮询仍在 `queued` 就是仍在排队，**不得**当作成功；
 * - 重试收据冻结观察窗口 `[N, N+1]`：`attempt ≥ N+2` 说明任务已被更新的尝试接管，停止观察并给
 *   可读说明（不把别轮结果当本轮）；首次创建的 queued 收据同样按窗口观察；
 * - 显式操作（重试/取消）绑定 `{jobId, attempt, 观察代次}`：`reset` / 接管新任务 / 卸载都让代次
 *   前进，迟到的成功与失败都不写状态（B2-RV10）；
 * - 每次 effect setup 都恢复挂载标志（StrictMode 的 setup→cleanup→setup 不能永久失效，
 *   B2-RV09）；cleanup 正确 abort（页面停止观察**不取消任务**）；
 * - `pending` + `pendingLabel` 让调用方把在途操作显示成按钮 busy 与可读文案。
 *
 * 待 `@/services/workflow-jobs-api` 与 `@/services/use-workflow-job` 回归后，本文件应删除并改回
 * 导入（见 `@/contracts/assessments` 顶部同一条说明）。
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  isTeachingJobTerminal,
  type TeachingJobDomain,
  type TeachingJobView,
} from '@/contracts/assessments';
import { ApiError } from '@/services/api-client';
import { apiRequest } from '@/services/api-client';

/** 本模块所有请求都固定这一域，避免调用方传错域看到别人的任务。 */
export const TEACHING_JOB_DOMAIN: TeachingJobDomain = 'teaching';

/** 轮询间隔（毫秒）：开始 2 秒，持续 30 秒后 5 秒。 */
export function pollIntervalMs(elapsedMs: number): number {
  return elapsedMs >= 30_000 ? 5000 : 2000;
}

export function fetchJob(
  domain: TeachingJobDomain,
  jobId: string,
  signal?: AbortSignal,
): Promise<TeachingJobView> {
  return apiRequest<TeachingJobView>(
    `/workflow-jobs/${encodeURIComponent(jobId)}?domain=${encodeURIComponent(domain)}`,
    { signal },
  );
}

function jobAction(
  domain: TeachingJobDomain,
  jobId: string,
  action: 'cancel' | 'retry',
): Promise<TeachingJobView> {
  return apiRequest<TeachingJobView>(
    `/workflow-jobs/${encodeURIComponent(jobId)}/${action}`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ domain }),
    },
  );
}

/** 协作式取消（幂等）：queued 立即取消；running 置取消标志，迟到结果不发布。 */
export function cancelJob(domain: TeachingJobDomain, jobId: string): Promise<TeachingJobView> {
  return jobAction(domain, jobId, 'cancel');
}

/** 重试仅对终态（failed/interrupted/cancelled）有效；保留冻结输入与模型指纹。 */
export function retryJob(domain: TeachingJobDomain, jobId: string): Promise<TeachingJobView> {
  return jobAction(domain, jobId, 'retry');
}

export interface ObserveJobOptions {
  signal?: AbortSignal;
  /** 每当状态变化时回调（含首次与终态）。 */
  onUpdate?: (view: TeachingJobView) => void;
  /**
   * 接受的**最小** attempt（重试收据的 N）：低于它视为旧尝试，停止观察并返回 null。
   * 重试后的合法窗口是 [N, N+1]：重排队（N）→ claim（N+1）→ 终态（N+1）；
   * attempt ≥ N+2 说明任务已被**更新的**尝试接管，同样返回 null。
   */
  minAttempt?: number;
  /** 接受的**最大** attempt；两者都不给表示不设防。 */
  maxAttempt?: number;
  /** 测试注入点：等待实现与计时来源。 */
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>;
  now?: () => number;
}

/** 重试/创建收据：把响应（queued，attempt=N）冻结成观察窗口 [N, N+1]。 */
export function retryObservationWindow(view: Pick<TeachingJobView, 'attempt'>): {
  minAttempt: number;
  maxAttempt: number;
} {
  return { minAttempt: view.attempt, maxAttempt: view.attempt + 1 };
}

function defaultSleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason ?? new DOMException('已取消', 'AbortError'));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal?.reason ?? new DOMException('已取消', 'AbortError'));
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

/**
 * 观察一个后台任务直到终态；被取消（AbortSignal）返回 null。
 *
 * 页面停止观察**不取消任务**（取消只走 `cancelJob`）；刷新后按持久 jobId 继续查询。
 */
export async function observeJob(
  domain: TeachingJobDomain,
  jobId: string,
  options: ObserveJobOptions = {},
): Promise<TeachingJobView | null> {
  const { signal, onUpdate, sleep = defaultSleep, now = () => Date.now() } = options;
  const { minAttempt, maxAttempt } = options;
  const startedAt = now();

  for (;;) {
    if (signal?.aborted) return null;
    let view: TeachingJobView;
    try {
      view = await fetchJob(domain, jobId, signal);
    } catch (error) {
      if (signal?.aborted) return null;
      throw error;
    }
    if (
      (minAttempt !== undefined && view.attempt < minAttempt) ||
      (maxAttempt !== undefined && view.attempt > maxAttempt)
    ) {
      // 旧尝试或被更新的尝试：停止观察（不把别轮结果当本轮），但不取消任务
      return null;
    }
    onUpdate?.(view);
    if (isTeachingJobTerminal(view.state)) return view;
    try {
      await sleep(pollIntervalMs(now() - startedAt), signal);
    } catch (error) {
      if (signal?.aborted) return null;
      throw error;
    }
  }
}

/** 公共任务观察 hook：queued 收据接受一次 claim；显式操作绑定任务、尝试和本地观察代次。 */
export function useTeachingJob(options: {
  onTerminal?: (view: TeachingJobView) => void;
  polling?: Pick<ObserveJobOptions, 'sleep' | 'now'>;
} = {}) {
  const [view, setView] = useState<TeachingJobView | null>(null);
  const [observing, setObserving] = useState(false);
  const [pending, setPending] = useState<'retry' | 'cancel' | null>(null);
  const [actionError, setActionError] = useState<ApiError | null>(null);
  const [observationNotice, setObservationNotice] = useState<string | null>(null);
  const alive = useRef(true);
  const epoch = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const current = useRef<TeachingJobView | null>(null);
  const busy = useRef(false);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      epoch.current += 1;
      controller.current?.abort();
    };
  }, []);

  const reset = useCallback(() => {
    epoch.current += 1;
    controller.current?.abort();
    controller.current = null;
    current.current = null;
    busy.current = false;
    setPending(null);
    setView(null);
    setObserving(false);
    setActionError(null);
    setObservationNotice(null);
  }, []);

  const adopt = useCallback((receipt: TeachingJobView) => {
    if (!alive.current || receipt.domain !== TEACHING_JOB_DOMAIN) return;
    epoch.current += 1;
    const token = epoch.current;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    current.current = receipt;
    busy.current = false;
    setPending(null);
    setView(receipt);
    setActionError(null);
    setObservationNotice(null);
    if (isTeachingJobTerminal(receipt.state)) {
      setObserving(false);
      optionsRef.current.onTerminal?.(receipt);
      return;
    }
    setObserving(true);
    // 首次创建的 queued 收据同样按窗口观察：queued(N) → claim(N+1) → 终态(N+1)。
    const window = retryObservationWindow(receipt);
    void observeJob(TEACHING_JOB_DOMAIN, receipt.jobId, {
      ...window,
      ...optionsRef.current.polling,
      signal: abort.signal,
      onUpdate: (next) => {
        if (
          !alive.current ||
          token !== epoch.current ||
          abort.signal.aborted ||
          next.jobId !== receipt.jobId
        ) {
          return;
        }
        // 保持同代观察的单向尝试号：迟到 queued(N) 不能回写已观察的 running(N+1)。
        if (next.attempt < (current.current?.attempt ?? receipt.attempt)) return;
        current.current = next;
        setView(next);
        if (isTeachingJobTerminal(next.state)) {
          setObserving(false);
          optionsRef.current.onTerminal?.(next);
        }
      },
    })
      .then((terminal) => {
        if (!alive.current || token !== epoch.current || abort.signal.aborted) return;
        setObserving(false);
        if (!terminal) setObservationNotice('任务已被新的尝试接管，请刷新后查看最新状态。');
      })
      .catch((cause: unknown) => {
        if (!alive.current || token !== epoch.current || abort.signal.aborted) return;
        setObserving(false);
        setActionError(
          cause instanceof ApiError
            ? cause
            : new ApiError(
                'REQUEST_FAILED',
                cause instanceof Error ? cause.message : '读取任务失败',
                0,
                true,
              ),
        );
      });
  }, []);

  const operate = useCallback(
    (action: 'retry' | 'cancel') => {
      const active = current.current;
      if (!active || busy.current) return;
      const token = epoch.current;
      busy.current = true;
      setPending(action);
      setActionError(null);
      const run = action === 'retry' ? retryJob : cancelJob;
      void run(TEACHING_JOB_DOMAIN, active.jobId)
        .then((receipt) => {
          if (!alive.current || token !== epoch.current) return;
          busy.current = false;
          setPending(null);
          // 同一任务也不能让旧尝试或意外的后续两次尝试劫持本轮操作。
          if (
            receipt.jobId !== active.jobId ||
            receipt.attempt < active.attempt ||
            receipt.attempt > active.attempt + 1
          ) {
            setObservationNotice('操作响应已过期，请刷新查看任务。');
            return;
          }
          adopt(receipt);
        })
        .catch((cause: unknown) => {
          if (!alive.current || token !== epoch.current) return;
          busy.current = false;
          setPending(null);
          setActionError(
            cause instanceof ApiError
              ? cause
              : new ApiError(
                  'REQUEST_FAILED',
                  cause instanceof Error ? cause.message : '任务操作失败',
                  0,
                  true,
                ),
          );
        });
    },
    [adopt],
  );

  return {
    view,
    observing,
    pending,
    pendingLabel:
      pending === 'retry' ? '正在重试…' : pending === 'cancel' ? '正在取消…' : null,
    actionError,
    observationNotice,
    adopt,
    reset,
    retry: useCallback(() => operate('retry'), [operate]),
    cancel: useCallback(() => operate('cancel'), [operate]),
  };
}
