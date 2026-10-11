'use client';
import { useEffect, useRef } from 'react';
import { ArcElement, Chart as ChartJS, Legend, Tooltip, type ChartConfiguration } from 'chart.js';

/** 试卷知识点占比环状图（C4-3）：纯 Chart.js（注册 ArcElement），数据来自后端聚合。 */
export function KnowledgeDonut({
  distribution,
}: {
  distribution: Array<{ name: string; itemCount: number; totalScoreUnits: number; scoreRatio: number | null }>;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    if (!el || distribution.length === 0) return;
    ChartJS.register(ArcElement, Tooltip, Legend);
    const palette = ['#2563eb', '#38bdf8', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#94a3b8'];
    const config: ChartConfiguration = {
      type: 'doughnut',
      data: {
        labels: distribution.map((b) => b.name),
        datasets: [
          {
            data: distribution.map((b) => b.totalScoreUnits),
            backgroundColor: distribution.map((_, i) => palette[i % palette.length]),
            borderWidth: 2,
            borderColor: '#fff',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const bucket = distribution[ctx.dataIndex]!;
                const parts = [`${bucket.itemCount} 题`, `${bucket.totalScoreUnits} 分`];
                if (bucket.scoreRatio !== null) parts.push(`${Math.round(bucket.scoreRatio * 100)}%`);
                return `${bucket.name}：${parts.join(' · ')}`;
              },
            },
          },
        },
      },
    };
    const chart = new ChartJS(el, config);
    return () => chart.destroy();
  }, [distribution]);

  if (distribution.length === 0) {
    return <p className="b4-meta">该试卷还没有小题或知识点关联；导入校对并关联知识点后这里会显示占比。</p>;
  }
  return (
    <div className="paper-donut" data-testid="paper-knowledge-donut">
      <h4>AI 试题知识点分类占比</h4>
      <div className="paper-donut-canvas">
        <canvas ref={canvas} role="img" aria-label="试卷知识点占比环状图" />
      </div>
    </div>
  );
}
