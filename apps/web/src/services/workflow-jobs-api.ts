/**
 * 公共任务客户端（TEACHING-LOOP B0）。
 *
 * 对应后端 `app/api/v1/workflow_jobs.py`：
 *   GET  /api/v1/workflow-jobs/{jobId}?domain=…
 *   POST /api/v1/workflow-jobs/{jobId}/cancel   body {domain}
 *   POST /api/v1/workflow-jobs/{jobId}/retry    body {domain}
 *
 * 类型来自冻结契约 `@/contracts/teaching-loop`；失败一律抛 `ApiError`
 * （含 `details`），不把失败降级成"任务完成"。`202` 只代表接受任务。
 */

import { apiRequest } from '@/services/api-client';
import { isJobTerminal, type JobDomain, type JobState, type JobView } from '@/contracts/teaching-loop';

/** 轮询间隔（毫秒）：开始 2 秒，持续 30 秒后 5 秒。 */
export function pollIntervalMs(elapsedMs: number): number {
  return elapsedMs >= 30_000 ? 5000 : 2000;
}

export function fetchJob(
  domain: JobDomain,
  jobId: string,
  signal?: AbortSignal,
): Promise<JobView> {
  return apiRequest<JobView>(
    `/workflow-jobs/${encodeURIComponent(jobId)}?domain=${encodeURIComponent(domain)}`,
    { signal },
  );
}

function jobAction(domain: JobDomain, jobId: string, action: 'cancel' | 'retry'): Promise<JobView> {
  return apiRequest<JobView>(
    `/workflow-jobs/${encodeURIComponent(jobId)}/${action}`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ domain }),
    },
  );
}

/** 协作式取消（幂等）：queued 立即取消；running 置取消标志，迟到结果不发布。 */
export function cancelJob(domain: JobDomain, jobId: string): Promise<JobView> {
  return jobAction(domain, jobId, 'cancel');
}

/** 重试仅对终态（failed/interrupted/cancelled）有效；保留冻结输入与模型指纹。 */
export function retryJob(domain: JobDomain, jobId: string): Promise<JobView> {
  return jobAction(domain, jobId, 'retry');
}

export interface JobObservation {
  state: JobState;
  /** 页面观察对象在任务被重试/接管后应停止把旧 attempt 的结果当作当前结果。 */
  attempt: number;
}

export interface ObserveJobOptions {
  signal?: AbortSignal;
  /** 每当状态变化时回调（含首次与终态）。 */
  onUpdate?: (view: JobView) => void;
  /**
   * 接受的**最小** attempt（重试收据的 N）：低于它视为旧尝试，停止观察并返回 null。
   * 重试后的合法窗口是 [N, N+1]：重排队（N）→ claim（N+1）→ 终态（N+1）；
   * attempt ≥ N+2 说明任务已被**更新的**尝试接管，同样返回 null（B3/G0 · B2-RV01/RV10）。
   */
  minAttempt?: number;
  /** 接受的**最大** attempt；两者都不给表示不设防（旧调用方保持原行为）。 */
  maxAttempt?: number;
  /**
   * 精确 attempt（兼容旧调用）：等价于 minAttempt = maxAttempt = expectedAttempt。
   * 新代码请改用 `retryObservationWindow()` 或 min/max。
   */
  expectedAttempt?: number;
  /** 测试注入点：等待实现与计时来源。 */
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>;
  now?: () => number;
}

/** 重试收据：把 retry 响应（queued，attempt=N）冻结成观察窗口 [N, N+1]。 */
export function retryObservationWindow(view: Pick<JobView, 'attempt'>): {
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
  domain: JobDomain,
  jobId: string,
  options: ObserveJobOptions = {},
): Promise<JobView | null> {
  const { signal, onUpdate, expectedAttempt, sleep = defaultSleep, now = () => Date.now() } = options;
  const minAttempt = expectedAttempt ?? options.minAttempt;
  const maxAttempt = expectedAttempt ?? options.maxAttempt;
  const startedAt = now();

  for (;;) {
    if (signal?.aborted) {
      return null;
    }
    let view: JobView;
    try {
      view = await fetchJob(domain, jobId, signal);
    } catch (error) {
      if (signal?.aborted) {
        return null;
      }
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
    if (isJobTerminal(view.state)) {
      return view;
    }
    try {
      await sleep(pollIntervalMs(now() - startedAt), signal);
    } catch (error) {
      if (signal?.aborted) {
        return null;
      }
      throw error;
    }
  }
}
