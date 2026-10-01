'use client';

/**
 * 知识点模块共用的数据获取原语。
 *
 * 与题库模块的 `features/question-bank/hooks.ts` 同构但**独立维护**（模块级依赖隔离：
 * 本模块不 import 其他 feature 的文件；两份都只是薄薄的 React 适配，语义由
 * `@/services/api-client` 与 `workflow-jobs-api` 的契约锁定）。
 *
 * 三态显式（loading / ready / failed）：读取失败必须能显示 `ApiError` 的 code/message
 * 与重试入口，调用方不得把失败当空列表。
 *
 * `useKnowledgeJob` 观察 `knowledge` 域的 AI 候选任务：
 * - 守卫 `jobId` + attempt 窗口：任务被重试/接管后停止把旧 attempt 的结果当作当前结果
 *   （重试收据用 `retryObservationWindow`：接受 N/N+1，N+2 视为被更新的尝试接管）；
 * - 显式操作（重试/取消）绑定 `{jobId, attempt 窗口, 观察代次}`：`reset` / 接管新任务 /
 *   卸载都会让代次前进，**迟到的成功与失败都不写状态**，不污染新任务（B2-RV10）；
 * - 每次 effect setup 都恢复挂载标志（StrictMode 的 setup→cleanup→setup 不能永久失效，
 *   B2-RV09）；cleanup 正确 abort（页面停止观察**不取消任务**，刷新后按持久 jobId 继续查询）；
 * - `pending` + `pendingLabel` 让调用方把在途操作显示成按钮 busy 与可读文案。
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '@/services/api-client';
import type { JobDomain, JobView } from '@/contracts/teaching-loop';
import { isJobTerminal } from '@/contracts/teaching-loop';
import {
  cancelJob,
  observeJob,
  retryJob,
  retryObservationWindow,
  type ObserveJobOptions,
} from '@/services/workflow-jobs-api';

export type AsyncState<T> =
  | { phase: 'loading' }
  | { phase: 'ready'; data: T }
  | { phase: 'failed'; error: ApiError };

/** 把任意异常归一为 ApiError，保证界面能显示 code 与是否可重试。 */
export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError(
    'UNEXPECTED_ERROR',
    error instanceof Error ? error.message : '请求失败，请重试。',
    0,
    true,
  );
}

export interface AsyncResource<T> {
  state: AsyncState<T>;
  reload: () => void;
  /**
   * 最近一次**成功**读取的数据（读取失败或重新加载期间保持可用）。
   * 消费方据此在刷新失败时继续显示上一次成功的数据，而不是清空视图。
   */
  lastData: T | null;
}

/** 带 abort 与重试的三态资源；`key` 变化即重新加载并取消上一次请求。 */
export function useAsyncResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  key: string,
): AsyncResource<T> {
  const [state, setState] = useState<AsyncState<T>>({ phase: 'loading' });
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;
  const lastData = useRef<T | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setState({ phase: 'loading' });
    loadRef.current(controller.signal).then(
      (data) => {
        if (!active) return;
        lastData.current = data;
        setState({ phase: 'ready', data });
      },
      (error: unknown) => {
        if (active) setState({ phase: 'failed', error: asApiError(error) });
      },
    );
    return () => {
      active = false;
      controller.abort();
    };
  }, [tick, key]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { state, reload, lastData: lastData.current };
}

/* ------------------------------------------------------------------ 任务观察 */

/** 在途的显式操作；同一时刻最多一个（重复点击不会产生第二个请求）。 */
export type KnowledgeJobPending = 'retry' | 'cancel' | null;

const PENDING_LABELS: Record<'retry' | 'cancel', string> = {
  retry: '正在重试…',
  cancel: '正在取消…',
};

/**
 * 观察窗口：只接受 `[minAttempt, maxAttempt]` 内的 attempt。
 * 重试必须用 `retryObservationWindow(retryView)`（收据 N → 接受 N/N+1；N+2 视为被接管）。
 */
export interface JobObservationWindow {
  minAttempt?: number;
  maxAttempt?: number;
}

/** 精确窗口：非重试场景只接受当前 attempt（等价于旧 `expectedAttempt`）。 */
function exactWindow(attempt: number | undefined): JobObservationWindow {
  return typeof attempt === 'number' ? { minAttempt: attempt, maxAttempt: attempt } : {};
}

export interface KnowledgeJobController {
  view: JobView | null;
  observing: boolean;
  actionError: ApiError | null;
  /** 观察被中止的说明（attempt 已变 / 已取消）；不是任务失败。 */
  observationNotice: string | null;
  /** 在途的显式操作；非 null 时按钮应显示 busy 与 `pendingLabel`。 */
  pending: KnowledgeJobPending;
  /** 与 `pending` 配套的按钮文案；没有在途操作时为 null。 */
  pendingLabel: string | null;
  /** 用 POST /retry 返回的初始视图接管观察；终态自动停止。 */
  adopt: (view: JobView) => void;
  /** 重试当前任务（新 attempt）；失败时给出可读错误。 */
  retry: () => void;
  /** 协作式取消当前任务；终态由观察/返回值收敛。 */
  cancel: () => void;
  /** 清空本地任务视图（发起新任务前调用）；在途操作随之失效。 */
  reset: () => void;
}

export interface KnowledgeJobOptions {
  /** 观察到的终态（含 succeeded/failed/cancelled/interrupted）。 */
  onTerminal?: (view: JobView) => void;
  /** 测试注入点：透传给 `observeJob` 的等待实现与计时来源。 */
  polling?: Pick<ObserveJobOptions, 'sleep' | 'now'>;
}

export function useKnowledgeJob(options: KnowledgeJobOptions = {}): KnowledgeJobController {
  const [view, setView] = useState<JobView | null>(null);
  const [observing, setObserving] = useState(false);
  const [actionError, setActionError] = useState<ApiError | null>(null);
  const [observationNotice, setObservationNotice] = useState<string | null>(null);
  const [pending, setPending] = useState<KnowledgeJobPending>(null);

  const mounted = useRef(true);
  const observation = useRef<AbortController | null>(null);
  /**
   * 观察代次：`reset` / 接管新任务（`adopt`）/ 卸载都会前进。观察回调与显式操作的
   * 迟到响应先比代次，代次不符一律不写状态（B3/G0 · B2-RV10）。
   */
  const epoch = useRef(0);
  const current = useRef<{ jobId: string; attempt: number } | null>(null);
  const pendingRef = useRef<KnowledgeJobPending>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    // 每次 setup 都恢复挂载标志：StrictMode 的 setup→cleanup→setup 不能永久失效（B2-RV09）
    mounted.current = true;
    return () => {
      mounted.current = false;
      epoch.current += 1;
      observation.current?.abort();
    };
  }, []);

  const setPendingAction = useCallback((next: KnowledgeJobPending) => {
    pendingRef.current = next;
    setPending(next);
  }, []);

  const apply = useCallback((next: JobView) => {
    if (!mounted.current) return;
    current.current = { jobId: next.jobId, attempt: next.attempt };
    setView(next);
    if (isJobTerminal(next.state)) {
      observation.current?.abort();
      setObserving(false);
      optionsRef.current.onTerminal?.(next);
    }
  }, []);

  /** 新一代次：让上一轮观察与在途操作的迟到响应失效，并换一个观察控制器。 */
  const beginEpoch = useCallback(() => {
    epoch.current += 1;
    observation.current?.abort();
    const controller = new AbortController();
    observation.current = controller;
    setPendingAction(null);
    return { token: epoch.current, controller };
  }, [setPendingAction]);

  const watch = useCallback(
    (
      token: number,
      controller: AbortController,
      jobId: string,
      window: JobObservationWindow,
    ) => {
      setObserving(true);
      setObservationNotice(null);
      const { sleep, now } = optionsRef.current.polling ?? {};
      void observeJob('knowledge', jobId, {
        signal: controller.signal,
        minAttempt: window.minAttempt,
        maxAttempt: window.maxAttempt,
        sleep,
        now,
        onUpdate: (next) => {
          if (token !== epoch.current) return; // 代次已失效：不写进当前视图
          if (next.jobId !== jobId) return;
          apply(next);
        },
      }).then(
        (terminal) => {
          if (token !== epoch.current || !mounted.current || controller.signal.aborted) return;
          setObserving(false);
          if (terminal === null) {
            // attempt 已被新任务接管：停在这里，绝不把旧 attempt 的结果当本轮结果
            setObservationNotice('该任务已被新的尝试接管，页面已停止显示旧尝试的结果。');
          }
        },
        (cause: unknown) => {
          if (token !== epoch.current || !mounted.current || controller.signal.aborted) return;
          setObserving(false);
          setActionError(asApiError(cause));
        },
      );
    },
    [apply],
  );

  const adoptWindow = useCallback(
    (next: JobView, window: JobObservationWindow) => {
      setActionError(null);
      setObservationNotice(null);
      const { token, controller } = beginEpoch();
      apply(next);
      if (!isJobTerminal(next.state)) {
        watch(token, controller, next.jobId, window);
      } else {
        setObserving(false);
      }
    },
    [apply, beginEpoch, watch],
  );

  /** 接管新视图（POST 返回的初始视图）：只接受它自己的 attempt。 */
  const adopt = useCallback(
    (next: JobView) => adoptWindow(next, exactWindow(next.attempt)),
    [adoptWindow],
  );

  /**
   * 显式操作（重试/取消）的统一通道：
   * 绑定调用时的 `{jobId, 观察代次}`；响应到达后先核代次（reset/接管新任务/卸载即失效），
   * 再核 `{jobId, attempt 不回退}`；重试按 `retryObservationWindow(retryView)` 观察
   * （收据 N → 接受 N/N+1，N+2 视为被更新的尝试接管）。
   */
  const operate = useCallback(
    (
      action: 'retry' | 'cancel',
      run: (domain: JobDomain, jobId: string) => Promise<JobView>,
    ) => {
      const active = current.current;
      if (!active || pendingRef.current) return; // 无任务 / 已有在途操作：不重复提交
      const token = epoch.current;
      setActionError(null);
      setObservationNotice(null);
      setPendingAction(action);
      run('knowledge', active.jobId).then(
        (next) => {
          if (!mounted.current || token !== epoch.current) return; // 迟到成功：不污染新任务
          if (next.jobId !== active.jobId || next.attempt < active.attempt) {
            // 身份或 attempt 对不上：不接管别轮视图，也不把按钮永久留在 busy
            setPendingAction(null);
            return;
          }
          adoptWindow(
            next,
            action === 'retry' ? retryObservationWindow(next) : exactWindow(next.attempt),
          );
        },
        (cause: unknown) => {
          if (!mounted.current || token !== epoch.current) return; // 迟到失败：同样不污染
          setPendingAction(null);
          setActionError(asApiError(cause));
        },
      );
    },
    [adoptWindow, setPendingAction],
  );

  const retry = useCallback(() => operate('retry', retryJob), [operate]);
  const cancel = useCallback(() => operate('cancel', cancelJob), [operate]);

  const reset = useCallback(() => {
    epoch.current += 1; // 在途观察与操作全部失效
    observation.current?.abort();
    observation.current = null;
    current.current = null;
    setPendingAction(null);
    setView(null);
    setObserving(false);
    setActionError(null);
    setObservationNotice(null);
  }, [setPendingAction]);

  return {
    view,
    observing,
    actionError,
    observationNotice,
    pending,
    pendingLabel: pending ? PENDING_LABELS[pending] : null,
    adopt,
    retry,
    cancel,
    reset,
  };
}
