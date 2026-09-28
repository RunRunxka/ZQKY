'use client';
import { useCallback, useEffect, useState } from 'react';
import {
  emptyTaughtScope,
  loadTaughtScope,
  type TaughtScopeSnapshot,
} from '@/services/taught-scope';

/**
 * 任教范围读取 hook（RAG-REBUILD v1.0 · F1-CHAT）。
 *
 * - `enabled=false`（非教材模式）时不发任何请求；
 * - 读取失败保持 `state='failed'` 与可读 `error`，**不伪造空范围**；
 * - 卸载/重挂时中止在途请求；`reload()` 供界面显式重试。
 */
export function useTaughtScope(enabled: boolean): {
  /** 完整快照（含 selection/taxonomy/reason/revision） */
  scope: TaughtScopeSnapshot;
  /** loading | ready | empty | failed（failed 不是空范围） */
  state: TaughtScopeSnapshot['state'];
  error: string | null;
  reload: () => void;
} {
  const [scope, setScope] = useState<TaughtScopeSnapshot>(emptyTaughtScope);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let cancelled = false;
    void loadTaughtScope(controller.signal)
      .then((next) => {
        if (!cancelled) setScope(next);
      })
      .catch(() => {
        if (!cancelled)
          setScope({
            ...emptyTaughtScope(),
            state: 'failed',
            error: '任教范围读取失败，请重试。',
          });
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [enabled, tick]);
  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { scope, state: scope.state, error: scope.error, reload };
}
