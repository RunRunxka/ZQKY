'use client';
import { useCallback, useEffect, useState } from 'react';
import { fetchCapabilities } from '@/services/api-client';
import type { ApiCapability } from '@/contracts/api';
import { fetchRagStatus, type RagServiceStatus } from './rag-service';

export interface CapabilityStatusState {
  /** `/capabilities` 按 feature 索引；未完成或失败为 null */
  features: Record<string, ApiCapability> | null;
  /** 归一后的 `/rag/status`（分项可用性）；未完成或失败为 null */
  rag: RagServiceStatus | null;
  /** 两个接口各自的失败原因（null = 尚未失败） */
  capsError: string | null;
  ragError: string | null;
  /** 首轮读取中（两个接口都还没结果） */
  loading: boolean;
  /** 重新读取（失败后的可重试入口） */
  reload(): void;
}

/**
 * 「对话能力边界」的数据源（F1-CHAT v1.1 · 修复 A1 r1 D6）。
 *
 * 并行读 `/capabilities` 与 `/rag/status`；**任一失败都如实记录失败原因**，
 * 由展示层显示「状态未知 / 读取失败（可重试）」，不回落成「规划中」或「可用」。
 * 面板关闭即中止在途请求（AbortController）。
 */
export function useCapabilityStatus(enabled = true): CapabilityStatusState {
  const [features, setFeatures] = useState<Record<string, ApiCapability> | null>(null);
  const [rag, setRag] = useState<RagServiceStatus | null>(null);
  const [capsError, setCapsError] = useState<string | null>(null);
  const [ragError, setRagError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let cancelled = false;
    setLoading(true);
    void Promise.all([
      fetchCapabilities(controller.signal)
        .then((response) => {
          if (cancelled) return;
          const indexed: Record<string, ApiCapability> = {};
          for (const item of response.capabilities ?? []) indexed[item.feature] = item;
          setFeatures(indexed);
          setCapsError(null);
        })
        .catch((error: unknown) => {
          if (cancelled || controller.signal.aborted) return;
          setFeatures(null);
          setCapsError(error instanceof Error ? error.message : '无法读取能力清单。');
        }),
      fetchRagStatus(controller.signal)
        .then((status) => {
          if (cancelled) return;
          setRag(status);
          setRagError(null);
        })
        .catch((error: unknown) => {
          if (cancelled || controller.signal.aborted) return;
          setRag(null);
          setRagError(error instanceof Error ? error.message : '无法读取教材服务状态。');
        }),
    ]).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [enabled, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { features, rag, capsError, ragError, loading, reload };
}
