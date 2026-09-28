'use client';

/**
 * 题库模块共用的数据获取原语。
 *
 * `useAsyncResource` 保持显式三态（loading / ready / failed）：失败必须能显示
 * `ApiError` 的 code/message 与重试入口，调用方不得把失败当空列表。
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

export function errorText(error: unknown): string {
  return asApiError(error).message;
}

export interface AsyncResource<T> {
  state: AsyncState<T>;
  reload: () => void;
}

export function useAsyncResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  /** 资源身份键：键变化即重新加载。 */
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
