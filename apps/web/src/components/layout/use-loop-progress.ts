'use client';

/**
 * 传递带数据装配（F2-LOOP）：把 `services/loop-progress` 的读取包成组件生命周期。
 *
 * - effect 内发起读取，卸载/重载即 abort；迟到的结果一律不写状态；
 * - 首次读取显示「读取中…」，任何来源失败都只降级为对应工位「未知」，不把失败当空数据；
 * - 不轮询、不设定时器：状态只在挂载 / 学科变化 / 显式 reload 时读取。
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  deriveLoopProgress,
  loadLoopSnapshot,
  pendingLoopProgress,
  type LoopProgress,
  type LoopProgressServices,
} from '@/services/loop-progress';

export interface UseLoopProgressOptions {
  /** 有学科上下文的页面传入；没有时按全学科读取（读数不小、也不猜）。 */
  subjectId?: string | null;
  services?: LoopProgressServices;
}

export interface LoopProgressState {
  progress: LoopProgress;
  /** 首次读取中：所有工位显示「读取中…」，不给任何结论。 */
  loading: boolean;
  /** 至少一个来源读取失败：对应工位显示「未知」，整条带照常渲染。 */
  degraded: boolean;
  reload: () => void;
}

export function useLoopProgress({ subjectId = null, services }: UseLoopProgressOptions = {}): LoopProgressState {
  const [progress, setProgress] = useState<LoopProgress>(pendingLoopProgress);
  const [loading, setLoading] = useState(true);
  const [degraded, setDegraded] = useState(false);
  const [tick, setTick] = useState(0);
  const servicesRef = useRef(services);
  servicesRef.current = services;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    const injected = servicesRef.current;
    loadLoopSnapshot({
      subjectId,
      ...(injected ? { services: injected } : {}),
      signal: controller.signal,
    }).then(
      (snapshot) => {
        if (!active) return;
        setProgress(deriveLoopProgress(snapshot));
        setDegraded([snapshot.papers, snapshot.assessments, snapshot.runs, snapshot.practices, snapshot.lessons].some((entry) => entry === null));
        setLoading(false);
      },
      () => {
        /* 中止或意外异常：保持当前显示，不改写状态 */
      },
    );
    return () => {
      active = false;
      controller.abort();
    };
  }, [subjectId, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { progress, loading, degraded, reload };
}

export default useLoopProgress;
