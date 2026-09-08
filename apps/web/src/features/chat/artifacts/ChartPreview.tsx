'use client';
import { useEffect, useRef } from 'react';
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  type ChartConfiguration,
} from 'chart.js';
import type { ChatArtifact } from '@/contracts/chat';

/**
 * Chart.js 预览（对照参考 react-chartjs-2 用法）：data.config 为 Chart.js 配置
 * （本地演示数据）；配置缺失或渲染异常时回退展示配置原文。
 */
export function ChartPreview({ artifact }: { artifact: ChatArtifact }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    let chart: ChartJS | null = null;
    try {
      ChartJS.register(
        CategoryScale,
        LinearScale,
        BarElement,
        LineElement,
        PointElement,
        Title,
        Tooltip,
        Legend,
      );
      const raw =
        artifact.data && typeof artifact.data === 'object' && 'config' in artifact.data
          ? (artifact.data as { config?: unknown }).config
          : null;
      if (!raw || typeof raw !== 'object') throw new Error('missing config');
      chart = new ChartJS(el, raw as ChartConfiguration);
    } catch {
      if (holder.current) holder.current.dataset.failed = 'true';
    }
    return () => {
      chart?.destroy();
    };
  }, [artifact.data]);

  return (
    <div className="chat-chart-preview" ref={holder}>
      <canvas ref={canvas} role="img" aria-label={artifact.title} />
      {holder.current?.dataset.failed === 'true' && (
        <pre className="chat-chart-fallback">{artifact.content}</pre>
      )}
    </div>
  );
}
