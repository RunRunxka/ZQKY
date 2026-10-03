'use client';

/**
 * `question` 域后台任务的观察控制器（TEACHING-LOOP B3 · F10-QB）。
 *
 * 与 `features/knowledge-points/hooks.ts` 的 `useKnowledgeJob` 同构但**独立维护**（模块级依赖
 * 隔离：本模块不 import 其他 feature 的文件），语义由 `@/services/workflow-jobs-api` 与
 * `@/services/question-bank-api` 的契约锁定：
 *
 * - 六态显式：`queued → running → succeeded|failed|cancelled|interrupted`；只有服务端给出的
 *   终态才算结束——轮询仍在 `queued` 就是仍在排队，**不得**当作成功（B3/G0 · RV01）；
 * - 首次创建的 queued 收据与重试均观察 `[N, N+1]`：接受 queued(N) →
 *   running/终态(N+1)；attempt ≥ N+2 说明任务已被更新的尝试接管，停止观察并给可读说明；
 * - 显式操作（重试/取消）绑定 `{jobId, attempt, 观察代次}`：`reset` / 接管新任务 / 卸载都会让
 *   代次前进，迟到的成功与失败都不写状态（B2-RV10）；
 * - 每次 effect setup 都恢复挂载标志（StrictMode 的 setup→cleanup→setup 不能永久失效，
 *   B2-RV09）；cleanup 正确 abort（页面停止观察**不取消任务**）；
 * - `pending` + `pendingLabel` 让调用方把在途操作显示成按钮 busy 与可读文案。
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { GenerationJobView } from '@/contracts/question-bank';
import { isJobTerminal, type JobView } from '@/contracts/teaching-loop';
import { ApiError } from '@/services/api-client';
import { mergeGenerationObservation } from '@/services/question-bank-api';
import {
  cancelJob,
  observeJob,
  retryJob,
  retryObservationWindow,
  type ObserveJobOptions,
} from '@/services/workflow-jobs-api';

export type GenerationPending = 'retry' | 'cancel' | null;

const PENDING_LABELS: Record<'retry' | 'cancel', string> = {
  retry: '正在重试…',
  cancel: '正在取消…',
};

interface ObservationWindow {
  minAttempt?: number;
  maxAttempt?: number;
}

/** 已 running 的收据只接受本次 attempt；终态收据直接结束观察。 */
export function exactAttemptWindow(attempt: number | undefined): ObservationWindow {
  return typeof attempt === 'number' ? { minAttempt: attempt, maxAttempt: attempt } : {};
}

/**
 * 重试收据 → 观察窗口 `[N, N+1]`（CTRL 冻结的 `retryObservationWindow`；
 * attempt ≥ N+2 说明被更新的尝试接管）；视图没有 attempt 时不设防。
 */
export function retryAttemptWindow(view: { attempt?: number }): ObservationWindow {
  return typeof view.attempt === 'number' ? retryObservationWindow({ attempt: view.attempt }) : {};
}

/** 创建收据仍在 queued 时，首次 claim 合法地将 attempt 从 N 推进到 N+1。 */
function creationAttemptWindow(view: GenerationJobView): ObservationWindow {
  return view.state === 'queued' ? retryAttemptWindow(view) : exactAttemptWindow(view.attempt);
}

/** 接管任务后 attempt 前进方向不合法（响应比本地还旧）时不得接管。 */
function isStaleReceipt(receipt: JobView, active: { jobId: string; attempt: number }): boolean {
  return receipt.jobId !== active.jobId || receipt.attempt < active.attempt;
}

export interface QuestionJobOptions {
  /** 观察到终态（含 succeeded/failed/cancelled/interrupted）时回调一次。 */
  onTerminal?: (view: GenerationJobView) => void;
  /** 测试注入点：透传给 `observeJob` 的等待实现与计时来源。 */
  polling?: Pick<ObserveJobOptions, 'sleep' | 'now'>;
}

export interface QuestionJobController {
  view: GenerationJobView | null;
  observing: boolean;
  actionError: ApiError | null;
  /** 观察被中止的说明（attempt 已变 / 被接管）；不是任务失败。 */
  observationNotice: string | null;
  /** 在途的显式操作；非 null 时按钮应显示 busy 与 `pendingLabel`。 */
  pending: GenerationPending;
  pendingLabel: string | null;
  /** 用创建接口返回的初始视图接管观察；终态自动停止。 */
  adopt: (view: GenerationJobView) => void;
  /** 重试当前任务（新 attempt；沿用服务端冻结的输入与模型）。 */
  retry: () => void;
  /** 协作式取消当前任务；终态由观察/返回值收敛。 */
  cancel: () => void;
  /** 清空本地任务视图（发起新任务前调用）；在途操作随之失效。 */
  reset: () => void;
}

function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError(
    'UNEXPECTED_ERROR',
    error instanceof Error ? error.message : '请求失败，请重试。',
    0,
    true,
  );
}

export function useQuestionJob(options: QuestionJobOptions = {}): QuestionJobController {
  const [view, setView] = useState<GenerationJobView | null>(null);
  const [observing, setObserving] = useState(false);
  const [actionError, setActionError] = useState<ApiError | null>(null);
  const [observationNotice, setObservationNotice] = useState<string | null>(null);
  const [pending, setPending] = useState<GenerationPending>(null);

  const mounted = useRef(true);
  const observation = useRef<AbortController | null>(null);
  /** 观察代次：`reset` / 接管新任务 / 卸载都会前进（B2-RV10）。 */
  const epoch = useRef(0);
  const current = useRef<{ jobId: string; attempt: number } | null>(null);
  /** 最新视图的同步镜像：观察合并（只在服务端给出字段时更新）以它为准。 */
  const latest = useRef<GenerationJobView | null>(null);
  const pendingRef = useRef<GenerationPending>(null);
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

  const setPendingAction = useCallback((next: GenerationPending) => {
    pendingRef.current = next;
    setPending(next);
  }, []);

  const store = useCallback((next: GenerationJobView | null) => {
    latest.current = next;
    setView(next);
  }, []);

  const finishTerminal = useCallback((next: GenerationJobView) => {
    observation.current?.abort();
    setObserving(false);
    optionsRef.current.onTerminal?.(next);
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
    (token: number, controller: AbortController, jobId: string, window: ObservationWindow) => {
      setObserving(true);
      setObservationNotice(null);
      const { sleep, now } = optionsRef.current.polling ?? {};
      void observeJob('question', jobId, {
        signal: controller.signal,
        minAttempt: window.minAttempt,
        maxAttempt: window.maxAttempt,
        sleep,
        now,
        onUpdate: (next) => {
          if (token !== epoch.current) return; // 代次已失效：不写进当前视图
          if (next.jobId !== jobId) return;
          current.current = { jobId: next.jobId, attempt: next.attempt };
          const merged = mergeGenerationObservation(latest.current, next);
          if (!merged) return;
          store(merged);
          if (isJobTerminal(next.state)) finishTerminal(merged);
        },
      }).then(
        (terminal) => {
          if (token !== epoch.current || !mounted.current || controller.signal.aborted) return;
          setObserving(false);
          if (terminal === null) {
            // attempt 已被更新尝试接管：停在这里，绝不把旧 attempt 的结果当本轮结果
            setObservationNotice(
              '该任务已被新的尝试接管，页面已停止显示旧尝试的结果；请刷新或重新发起后查看最新状态。',
            );
          }
        },
        (cause: unknown) => {
          if (token !== epoch.current || !mounted.current || controller.signal.aborted) return;
          setObserving(false);
          setActionError(asApiError(cause));
        },
      );
    },
    [finishTerminal, store],
  );

  /** 接管任务视图：queued 创建/重试 [N, N+1]，已 running 收据精确观察。 */
  const adoptJobView = useCallback(
    (next: GenerationJobView, window: ObservationWindow) => {
      setActionError(null);
      setObservationNotice(null);
      const { token, controller } = beginEpoch();
      store(next);
      if (typeof next.attempt === 'number') {
        current.current = { jobId: next.jobId, attempt: next.attempt };
      } else {
        current.current = { jobId: next.jobId, attempt: 0 };
      }
      if (!isJobTerminal(next.state)) {
        watch(token, controller, next.jobId, window);
      } else {
        finishTerminal(next);
      }
    },
    [beginEpoch, finishTerminal, store, watch],
  );

  /** 接管创建接口收据（202）：queued 接受首次 claim；running/终态沿用实际 attempt。 */
  const adopt = useCallback(
    (next: GenerationJobView) => adoptJobView(next, creationAttemptWindow(next)),
    [adoptJobView],
  );

  /** 把 workflow 任务视图归一成补题视图（状态/尝试号来自任务视图，结果字段只在给出时更新）。 */
  const asGenerationView = useCallback((job: JobView): GenerationJobView => {
    const merged = mergeGenerationObservation(latest.current, job);
    return (
      merged ?? {
        jobId: job.jobId,
        state: job.state,
        attempt: job.attempt,
        importId: null,
        candidateCount: 0,
        errorCode: job.error?.code ?? null,
      }
    );
  }, []);

  /**
   * 显式操作（重试/取消）的统一通道：绑定调用时的 `{jobId, 观察代次}`；
   * 响应到达后先核代次（reset/接管新任务/卸载即失效），再核 `{jobId, attempt 不回退}`；
   * 重试按 `retryObservationWindow(retryView)` 观察（收据 N → 接受 N/N+1，N+2 视为被接管）。
   */
  const operate = useCallback(
    (action: 'retry' | 'cancel', run: (jobId: string) => Promise<JobView>) => {
      const active = current.current;
      if (!active || pendingRef.current) return; // 无任务 / 已有在途操作：不重复提交
      const token = epoch.current;
      setActionError(null);
      setObservationNotice(null);
      setPendingAction(action);
      run(active.jobId).then(
        (receipt) => {
          if (!mounted.current || token !== epoch.current) return; // 迟到成功：不污染新任务
          if (isStaleReceipt(receipt, active)) {
            // 身份或 attempt 对不上：不接管别轮视图，也不把按钮永久留在 busy
            setPendingAction(null);
            return;
          }
          adoptJobView(
            asGenerationView(receipt),
            action === 'retry' ? retryAttemptWindow(receipt) : exactAttemptWindow(receipt.attempt),
          );
        },
        (cause: unknown) => {
          if (!mounted.current || token !== epoch.current) return; // 迟到失败：同样不污染
          setPendingAction(null);
          setActionError(asApiError(cause));
        },
      );
    },
    [adoptJobView, asGenerationView, setPendingAction],
  );

  const retry = useCallback(
    () => operate('retry', (jobId) => retryJob('question', jobId)),
    [operate],
  );
  const cancel = useCallback(
    () => operate('cancel', (jobId) => cancelJob('question', jobId)),
    [operate],
  );

  const reset = useCallback(() => {
    epoch.current += 1; // 在途观察与操作全部失效
    observation.current?.abort();
    observation.current = null;
    current.current = null;
    setPendingAction(null);
    store(null);
    setObserving(false);
    setActionError(null);
    setObservationNotice(null);
  }, [setPendingAction, store]);

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
