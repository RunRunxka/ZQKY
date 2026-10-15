import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { useResolvedThemeKey } from './chart-theme';

describe('useResolvedThemeKey 图表主题键', () => {
  afterEach(() => {
    delete document.documentElement.dataset.theme;
  });

  it('应用内切换 data-theme 时立即变化，图表据此重建', async () => {
    document.documentElement.dataset.theme = 'light';
    const { result } = renderHook(() => useResolvedThemeKey());
    expect(result.current).toBe('light');

    await act(async () => {
      document.documentElement.dataset.theme = 'dark';
      // MutationObserver 回调为微任务，等待其执行
      await Promise.resolve();
    });
    expect(result.current).toBe('dark');

    await act(async () => {
      document.documentElement.dataset.theme = 'light';
      await Promise.resolve();
    });
    expect(result.current).toBe('light');
  });
});
