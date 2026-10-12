/**
 * 知识点域任务观察客户端（重建期最小解耦，R3-FE 2026-10-11）。
 *
 * 归档实现在 `@/services/workflow-jobs-api`（跨域公共任务客户端：knowledge / question /
 * teaching 三域共用）；重建期该服务与其冻结契约 `@/contracts/teaching-loop` 尚未回归，
 * 而知识点页的「AI 候选 / 教材提取」只需要**知识域**的观察与取消/重试。
 * 本文件据此以最小体积复刻同一份 HTTP 契约，**不是新协议**：
 *
 *   GET  /api/v1/workflow-jobs/{jobId}?domain=knowledge
 *   POST /api/v1/workflow-jobs/{jobId}/cancel   body {domain:'knowledge'}
 *   POST /api/v1/workflow-jobs/{jobId}/retry    body {domain:'knowledge'}
 *
 * 行为与归档一致：失败一律抛 `ApiError`（不把失败降级成「任务完成」）；`202` 只代表接受任务；
 * 被取消（AbortSignal）返回 `null`，页面停止观察**不取消任务**；刷新后按持久 jobId 继续查询；
 * 重试收据用 `retryObservationWindow()` 冻结观察窗口 [N, N+1]，`attempt ≥ N+2` 视为被更新的
 * 尝试接管（返回 null，不把别轮结果当本轮）。
 *
 * 待 `@/services/workflow-jobs-api` 回归后，本文件应删除并改回导入（见 contracts/knowledge.ts
 * 顶部同一条说明）。
 */

import { apiRequest } from '@/services/api-client';
import {
  isKnowledgeJobTerminal,
  type KnowledgeJobDomain,
  type KnowledgeJobState,
  type KnowledgeJobView,
} from '@/contracts/knowledge';

/** 知识点域任务（本模块所有请求都固定这一域，避免调用方传错域看到别人的任务）。 */
export const KNOWLEDGE_JOB_DOMAIN: KnowledgeJobDomain = 'knowledge';

/** 轮询间隔（毫秒）：开始 2 秒，持续 30 秒后 5 秒。 */
export function pollIntervalMs(elapsedMs: number): number {
  return elapsedMs >= 30_000 ? 5000 : 2000;
}

export function fetchJob(
  domain: KnowledgeJobDomain,
  jobId: string,
  signal?: AbortSignal,
): Promise<KnowledgeJobView> {
  return apiRequest<KnowledgeJobView>(
    `/workflow-jobs/${encodeURIComponent(jobId)}?domain=${encodeURIComponent(domain)}`,
    { signal },
  );
}

function jobAction(
  domain: KnowledgeJobDomain,
  jobId: string,
  action: 'cancel' | 'retry',
): Promise<KnowledgeJobView> {
  return apiRequest<KnowledgeJobView>(
    `/workflow-jobs/${encodeURIComponent(jobId)}/${action}`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ domain }),
    },
  );
}

/** 协作式取消（幂等）：queued 立即取消；running 置取消标志，迟到结果不发布。 */
export function cancelJob(domain: KnowledgeJobDomain, jobId: string): Promise<KnowledgeJobView> {
  return jobAction(domain, jobId, 'cancel');
}

/** 重试仅对终态（failed/interrupted/cancelled）有效；保留冻结输入与模型指纹。 */
export function retryJob(domain: KnowledgeJobDomain, jobId: string): Promise<KnowledgeJobView> {
  return jobAction(domain, jobId, 'retry');
}

export interface JobObservation {
  state: KnowledgeJobState;
  /** 页面观察对象在任务被重试/接管后应停止把旧 attempt 的结果当作当前结果。 */
  attempt: number;
}

export interface ObserveJobOptions {
  signal?: AbortSignal;
  /** 每当状态变化时回调（含首次与终态）。 */
  onUpdate?: (view: KnowledgeJobView) => void;
  /**
   * 接受的**最小** attempt（重试收据的 N）：低于它视为旧尝试，停止观察并返回 null。
   * 重试后的合法窗口是 [N, N+1]：重排队（N）→ claim（N+1）→ 终态（N+1）；
   * attempt ≥ N+2 说明任务已被**更新的**尝试接管，同样返回 null。
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
export function retryObservationWindow(view: Pick<KnowledgeJobView, 'attempt'>): {
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
  domain: KnowledgeJobDomain,
  jobId: string,
  options: ObserveJobOptions = {},
): Promise<KnowledgeJobView | null> {
  const { signal, onUpdate, expectedAttempt, sleep = defaultSleep, now = () => Date.now() } = options;
  const minAttempt = expectedAttempt ?? options.minAttempt;
  const maxAttempt = expectedAttempt ?? options.maxAttempt;
  const startedAt = now();

  for (;;) {
    if (signal?.aborted) {
      return null;
    }
    let view: KnowledgeJobView;
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
    if (isKnowledgeJobTerminal(view.state)) {
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
