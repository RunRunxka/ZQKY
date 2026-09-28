'use client';

/**
 * 教材模块共用的数据获取原语。
 *
 * - `useAsyncResource`：显式三态（loading / ready / failed），失败保留 `ApiError`，
 *   调用方必须区分「失败」与「空目录」；重载用 `reload`。
 * - `usePolling`：仅 `active` 为真时轮询，组件卸载立即停止；上一次回调未返回前不排下一次，
 *   避免请求堆叠。测试可用 `intervalMs` 缩小间隔，生产默认 ≥1s。
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

/** 面向用户的错误文案（不吞掉原因）。 */
export function errorText(error: unknown): string {
  return asApiError(error).message;
}

export interface AsyncResource<T> {
  state: AsyncState<T>;
  reload: () => void;
}

export function useAsyncResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  /** 资源身份键：键变化即重新加载（避免把内联函数放进依赖导致的重复请求）。 */
  key: string,
): AsyncResource<T> {
  const [state, setState] = useState<AsyncState<T>>({ phase: 'loading' });
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setState({ phase: 'loading' });
    loadRef.current(controller.signal).then(
      (data) => {
        if (active) setState({ phase: 'ready', data });
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
  return { state, reload };
}

/**
 * 轮询：`active` 为假（或卸载）时不排下一次；间隔默认 1500ms（≥1s）。
 * 回调自身的异常由回调负责展示，这里不吞掉也不重复抛出。
 */
export function usePolling(
  run: () => void | Promise<void>,
  active: boolean,
  intervalMs = 1500,
): void {
  const runRef = useRef(run);
  runRef.current = run;

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        await runRef.current();
      } catch {
        /* 回调内部已把失败写进状态；这里仅避免未处理拒绝 */
      }
      if (!cancelled) timer = setTimeout(() => void tick(), intervalMs);
    };
    timer = setTimeout(() => void tick(), intervalMs);
    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [active, intervalMs]);
}
