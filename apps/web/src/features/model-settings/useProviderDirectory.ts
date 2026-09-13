'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ModelProviderDirectory } from '@/contracts/model-settings';
import { loadProviderDirectory } from '@/services/model-settings-api';

/** 供应商目录只在挂载与显式刷新时读取；它是后端注册表的只读投影。 */
export function useProviderDirectory() {
  const [directory, setDirectory] = useState<ModelProviderDirectory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const epoch = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++epoch.current;
    try {
      const next = await loadProviderDirectory();
      if (request === epoch.current) {
        setDirectory(next);
        setError(null);
      }
      return next;
    } catch (e) {
      if (request === epoch.current)
        setError(e instanceof Error ? e.message : '读取供应商目录失败。');
      return null;
    }
  }, []);
  useEffect(() => {
    void refresh();
    const requestEpoch = epoch;
    return () => {
      requestEpoch.current++;
    };
  }, [refresh]);
  return { directory, error, refresh };
}
