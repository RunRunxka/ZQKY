'use client';

/**
 * `/assessments/**` 的数据获取原语与逻辑确认状态机（TEACHING-LOOP B3 · F20-I；R5-FE 取回最小子集）。
 *
 * 与知识点/题库模块的 hooks 同构但**独立维护**（模块级依赖隔离；各自都只是薄薄的 React
 * 适配，语义由 `@/services/api-client` 与契约镜像锁定）。要点：
 *
 * - 三态显式（loading / ready / failed）：读取失败必须能显示 `ApiError` 的 code/message
 *   与重试入口，**调用方不得把失败当空列表**；`lastData` 让刷新失败时继续显示上一次成功数据；
 * - **StrictMode 安全**：每次 effect setup 都恢复挂载标志（B2-RV09 的教训）；
 * - **逻辑确认冻结**（F20-I）：点确认即冻结 `submissionId` + 当时原样 payload，
 *   结果未知（拿不到响应）时重试必须复用同一 `submissionId` 与同一载荷；
 *   只有已有明确结果后，载荷变化才可开启新的逻辑确认。
 *
 * 重建期取回说明（R5-FE 2026-10-11）：归档 hooks 里的成绩草稿（`useScoreDrafts`）、
 * 原表行读取（`loadAllImportRows`）与班名映射（`useClassNameMap`）属于成绩分析批次，
 * 本模块不持有。
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '@/services/api-client';

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
  /** 最近一次**成功**读取的数据（读取失败或重新加载期间保持可用）。 */
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
  /**
   * 最近一次**成功**读取（连同它的 key）：同一 key 刷新失败时继续可用；
   * key 变化（切换班级/试卷）即视为没有数据，避免把上一个实体的视图当成本次的数据。
   */
  const lastRef = useRef<{ key: string; data: T } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setState({ phase: 'loading' });
    loadRef.current(controller.signal).then(
      (data) => {
        if (!active) return;
        lastRef.current = { key, data };
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
  const lastData = lastRef.current && lastRef.current.key === key ? lastRef.current.data : null;
  return { state, reload, lastData };
}

/* ------------------------------------------------------------------ 逻辑确认冻结 */

export type SubmissionPhase = 'idle' | 'in-flight' | 'succeeded' | 'failed' | 'unknown';

export interface FrozenSubmission<T> {
  operationId: string;
  submissionId: string;
  payloadKey: string;
  /** 冻结时的原样载荷：重试必须原样重发，不得被后来的编辑偷换。 */
  payload: T;
}

/** 深拷贝并递归 `Object.freeze`：冻结后的载荷不会被后续编辑原地改写。 */
function immutableSubmission<T>(value: FrozenSubmission<T>): FrozenSubmission<T> {
  const copy = structuredClone(value);
  const seen = new WeakSet<object>();
  const freeze = (entry: unknown) => {
    if (!entry || typeof entry !== 'object' || seen.has(entry)) return;
    seen.add(entry);
    Object.values(entry).forEach(freeze);
    Object.freeze(entry);
  };
  freeze(copy);
  return copy;
}

/** 稳定序列化：键排序后 JSON 化，保证「同载荷」判定与字段顺序无关。 */
export function stablePayloadKey(value: unknown): string {
  const seen = new WeakSet<object>();
  const canonical = (input: unknown): unknown => {
    if (Array.isArray(input)) return input.map(canonical);
    if (input && typeof input === 'object') {
      if (seen.has(input as object)) return '[循环]';
      seen.add(input as object);
      const entries = Object.entries(input as Record<string, unknown>)
        .filter(([, entry]) => entry !== undefined)
        .sort(([a], [b]) => a.localeCompare(b));
      return Object.fromEntries(entries.map(([key, entry]) => [key, canonical(entry)]));
    }
    return input;
  };
  return JSON.stringify(canonical(value));
}

export interface SubmissionController<T, R> {
  /** 当前逻辑确认（含失败后仍复用同一标识）；成功后自动释放。 */
  frozen: FrozenSubmission<T> | null;
  phase: SubmissionPhase;
  /** 在途（按钮 busy）；同一时刻只有一个请求。 */
  busy: boolean;
  result: R | null;
  /** 服务端明确失败（4xx/5xx 信封）。 */
  error: ApiError | null;
  /** 结果未知（没有拿到响应）：必须重试同一标识，不得换标识重做。 */
  unknownNotice: string | null;
  /** 发起（或重试）当前逻辑确认；返回值：成功时的结果，否则 null。 */
  submit: (payload: T, run: (submission: FrozenSubmission<T>) => Promise<R>) => Promise<R | null>;
  /** 释放冻结（用户明确要形成新的逻辑确认时调用）。 */
  release: () => void;
}

/**
 * 逻辑确认：冻结 `submissionId` + 原样 payload。
 *
 * - 同一载荷重复点击 → **不产生第二个请求**（在途去重）；
 * - 结果未知（status 0）后重试 → 复用同一 `submissionId` 与同一冻结载荷；
 * - 载荷变化（例如行决策变化）→ 新的逻辑确认 → 新标识；
 * - 明确结果（成功 2xx / 明确失败信封）后解除按钮锁定；成功后自动释放冻结；
 * - 卸载或 `release` 后，迟到响应不写状态。
 */
export function useFrozenSubmission<T, R>(): SubmissionController<T, R> {
  const [frozen, setFrozen] = useState<FrozenSubmission<T> | null>(null);
  const [phase, setPhase] = useState<SubmissionPhase>('idle');
  const [result, setResult] = useState<R | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [unknownNotice, setUnknownNotice] = useState<string | null>(null);
  const mounted = useRef(true);
  const epoch = useRef(0);
  const busyRef = useRef(false);
  const frozenRef = useRef<FrozenSubmission<T> | null>(null);
  const unknownRef = useRef(false);

  useEffect(() => {
    // 每次 setup 恢复挂载标志：StrictMode 的 setup→cleanup→setup 不能永久失效（B2-RV09）
    mounted.current = true;
    return () => {
      mounted.current = false;
      epoch.current += 1;
    };
  }, []);

  const setFrozenSubmission = useCallback((next: FrozenSubmission<T> | null) => {
    frozenRef.current = next;
    setFrozen(next);
  }, []);

  const release = useCallback(() => {
    epoch.current += 1; // 在途响应失效
    busyRef.current = false;
    unknownRef.current = false;
    setFrozenSubmission(null);
    setPhase('idle');
    setUnknownNotice(null);
    setError(null);
  }, [setFrozenSubmission]);

  const submit = useCallback(
    async (
      payload: T,
      run: (submission: FrozenSubmission<T>) => Promise<R>,
    ): Promise<R | null> => {
      if (busyRef.current) return null; // 在途重复点击：不再发第二个请求
      const payloadKey = stablePayloadKey(payload);
      const existing = frozenRef.current;
      const submission: FrozenSubmission<T> =
        existing && (unknownRef.current || existing.payloadKey === payloadKey)
          ? existing // 同一逻辑确认：复用冻结载荷与标识（结果未知后的重试）
          : immutableSubmission({
              operationId: crypto.randomUUID(),
              submissionId: crypto.randomUUID(),
              payloadKey,
              payload,
            });
      if (submission !== existing) {
        setFrozenSubmission(submission);
      }
      const token = epoch.current;
      busyRef.current = true;
      setPhase('in-flight');
      setError(null);
      setUnknownNotice(null);
      try {
        const payloadResult = await run(submission);
        if (!mounted.current || token !== epoch.current) return null; // 迟到成功同样不写
        setResult(payloadResult);
        setPhase('succeeded');
        unknownRef.current = false;
        // 明确成功：解锁并释放冻结（同一逻辑确认已经完成）
        epoch.current += 1;
        busyRef.current = false;
        setFrozenSubmission(null);
        setUnknownNotice(null);
        return payloadResult;
      } catch (cause) {
        if (!mounted.current || token !== epoch.current) return null; // 迟到失败同样不写
        busyRef.current = false;
        const apiError = asApiError(cause);
        if (apiError.status === 0) {
          // 拿不到响应：服务端可能已写入也可能没有；不换标识，原样重试即幂等
          setPhase('unknown');
          unknownRef.current = true;
          setUnknownNotice(
            `确认结果未知（${apiError.code}）：${apiError.message} 可能已写入也可能未写入；` +
              '请直接重试——同一个提交标识与原样载荷会按幂等处理，不会重复写入。',
          );
          return null;
        }
        setError(apiError);
        unknownRef.current = false;
        setPhase('failed');
        setUnknownNotice(null);
        return null;
      }
    },
    [setFrozenSubmission],
  );

  return {
    frozen,
    phase,
    busy: phase === 'in-flight',
    result,
    error,
    unknownNotice,
    submit,
    release,
  };
}
