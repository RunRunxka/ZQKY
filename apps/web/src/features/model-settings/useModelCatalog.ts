'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ModelCatalog } from '@/contracts/model-settings';
import { loadModelCatalog } from '@/services/model-settings-api';

export function useModelCatalog() {
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const epoch = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++epoch.current;
    setLoading(true);
    try {
      const next = await loadModelCatalog();
      if (request === epoch.current) {
        setCatalog(next);
        setError(null);
      }
      return next;
    } catch (e) {
      if (request === epoch.current)
        setError(e instanceof Error ? e.message : '读取模型配置失败。');
      return null;
    } finally {
      if (request === epoch.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
    const reload = () => {
      void refresh();
    };
    window.addEventListener('focus', reload);
    window.addEventListener('model-catalog-changed', reload);
    const requestEpoch = epoch;
    return () => {
      requestEpoch.current++;
      window.removeEventListener('focus', reload);
      window.removeEventListener('model-catalog-changed', reload);
    };
  }, [refresh]);
  return { catalog, error, loading, refresh };
}
