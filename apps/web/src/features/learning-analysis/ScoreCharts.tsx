'use client';
import { useEffect, useMemo, useRef } from 'react';
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartConfiguration,
} from 'chart.js';
import type { ItemStatView } from '@/contracts/b4';

/**
 * 学情可视化（C2）：小题得分趋势图 + 小题得分热力图。
 *
 * 数据为后端 item-stats 的匿名聚合（题号 × 全班得分率），不含任何个人身份。
 * 趋势图参考"红色曲线 + 渐变填充"风格：横轴题号、纵轴得分率（%）；热力图按
 * 得分率红→绿渐变着色（低=红、中=黄、高=绿），一行格子，悬停显示明细。
 */

const RED = '#c22a45';

export function ScoreTrendChart({ stats }: { stats: ItemStatView[] }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const labels = useMemo(() => stats.map((s) => s.itemPath), [stats]);
  const rates = useMemo(() => stats.map((s) => (s.scoreRate === null ? null : Math.round(s.scoreRate * 1000) / 10)), [stats]);

  useEffect(() => {
    const el = canvas.current;
    if (!el || stats.length === 0) return;
    ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Filler, Tooltip);
    const gradient = el.getContext('2d');
    let fill: CanvasGradient | null = null;
    if (gradient) {
      fill = gradient.createLinearGradient(0, 0, 0, 260);
      fill.addColorStop(0, 'rgba(194, 42, 69, 0.28)');
      fill.addColorStop(1, 'rgba(194, 42, 69, 0.02)');
    }
    const config: ChartConfiguration = {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: '得分率 %',
            data: rates,
            borderColor: RED,
            backgroundColor: fill ?? 'rgba(194, 42, 69, 0.12)',
            fill: true,
            tension: 0.38,
            borderWidth: 2.5,
            pointRadius: 3,
            pointBackgroundColor: RED,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { min: 0, max: 100, ticks: { callback: (v) => `${v}` } },
          x: { grid: { display: false } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const raw = ctx.dataset.data[ctx.dataIndex] as number | null;
                return raw === null || raw === undefined ? '无有效作答' : `得分率 ${raw}%`;
              },
            },
          },
        },
      },
    };
    const chart = new ChartJS(el, config);
    return () => chart.destroy();
  }, [labels, rates, stats.length]);

  if (stats.length === 0) return <p className="b4-meta">本次报告没有小题数据。</p>;
  return (
    <div className="analysis-trend" data-testid="analysis-trend-chart">
      <h4>小题得分趋势图</h4>
      <div className="analysis-trend-canvas">
        <canvas ref={canvas} role="img" aria-label="小题得分趋势图：横轴题号，纵轴得分率" />
      </div>
    </div>
  );
}

/** 得分率 → 色（低=红、中=黄、高=绿；null=灰）。 */
function heatColor(rate: number | null): string {
  if (rate === null) return 'var(--line)';
  const pct = Math.round(rate * 100);
  if (pct < 40) return '#e05c5c';
  if (pct < 60) return '#eaa14e';
  if (pct < 80) return '#d8c94f';
  return '#5abf7a';
}

export function ScoreHeatmap({ stats }: { stats: ItemStatView[] }) {
  if (stats.length === 0) return null;
  return (
    <div className="analysis-heatmap" data-testid="analysis-heatmap">
      <h4>小题得分热力图（%）</h4>
      <div className="analysis-heatmap-row" role="table" aria-label="小题得分热力图">
        {stats.map((s) => {
          const pct = s.scoreRate === null ? null : Math.round(s.scoreRate * 100);
          return (
            <div key={s.itemId} className="analysis-heat-cell" title={`${s.itemPath}：${pct === null ? '无有效作答' : `${pct}%`}（有效 ${s.recordedCount} 人 / 满分 ${s.maxScoreUnits}）`}>
              <span className="analysis-heat-no">{s.itemPath}</span>
              <span className="analysis-heat-value" style={{ background: heatColor(s.scoreRate) }}>
                {pct === null ? '—' : pct}
              </span>
            </div>
          );
        })}
      </div>
      <div className="analysis-heat-legend" aria-hidden="true">
        <span>低</span>
        <i style={{ background: '#e05c5c' }} />
        <i style={{ background: '#eaa14e' }} />
        <i style={{ background: '#d8c94f' }} />
        <i style={{ background: '#5abf7a' }} />
        <span>高</span>
      </div>
    </div>
  );
}
