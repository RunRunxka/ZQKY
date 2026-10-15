'use client';

/**
 * 试卷知识点占比环状图（R5-FE 2026-10-11，沿用归档 `KnowledgeDonut` 并核对配色与图例）。
 *
 * 数据只来自后端聚合 `GET /papers/{id}/knowledge-distribution`：本组件**不自己算比例**，
 * 占比一律用服务端给的 `scoreRatio`；服务端未给出时显示「占比未知」，不冒充 0%。
 *
 * 与归档实现的差异（已核对）：
 * - 调和色板沿用归档同一组颜色（蓝主题打头），保证多色但不出第二套主题；
 * - 图例改为**组件内 HTML 图例**（名称 + 题数 + 分值 + 百分比），既满足「图例含百分比」，
 *   也让占比在无 canvas 的环境（jsdom / 读屏）仍然可读；Chart.js 内置图例关闭以免重复；
 * - **补齐 Chart.js v4 的显式注册**：归档只注册了 `ArcElement`，在本仓库的 tree-shaking 入口下
 *   会缺 `DoughnutController`（真实浏览器实测「当前环境无法绘制环形图」）；本实现注册
 *   `DoughnutController + ArcElement + Tooltip`，仍不引第三方图表库、不注册无关控制器；
 * - Chart.js 只在浏览器里确实拿到 2D 上下文时创建；拿不到（如 jsdom）时明确提示「图形不可用」
 *   并保留 HTML 图例，不静默留空白。
 *
 * 卡片标题由调用方（页面）给出：本组件只负责图与图例，不重复画标题。
 */

import { useEffect, useRef, useState } from 'react';
import {
  ArcElement,
  Chart as ChartJS,
  DoughnutController,
  Tooltip,
  type ChartConfiguration,
} from 'chart.js';
import type { KnowledgeDistributionBucket } from '@/contracts/papers';
import {
  chartEnterAnimation,
  chartFocusPlugin,
  chartTooltipTheme,
  focusAlpha,
  focusTransitions,
  setChartFocus,
  withAlpha,
} from '@/components/charts/chart-theme';
import {
  KNOWLEDGE_DONUT_PALETTE,
  formatScoreUnits,
  ratioPercentText,
} from './labels';

export function KnowledgeDonut({
  distribution,
}: {
  distribution: readonly KnowledgeDistributionBucket[];
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<ChartJS | null>(null);
  const [canvasUnavailable, setCanvasUnavailable] = useState(false);
  const [highlighted, setHighlighted] = useState<number | null>(null);

  /** 图例与扇区联动：悬停图例项 = 聚焦对应扇区（其余淡出）并弹出其提示框；无图形时只高亮图例。 */
  const highlight = (index: number | null) => {
    setHighlighted(index);
    const chart = chartRef.current;
    if (!chart) return;
    const active = index === null ? [] : [{ datasetIndex: 0, index }];
    chart.setActiveElements(active);
    chart.tooltip?.setActiveElements(active, { x: 0, y: 0 });
    setChartFocus(chart, index);
  };

  useEffect(() => {
    const element = canvas.current;
    if (!element || distribution.length === 0) return;
    ChartJS.register(DoughnutController, ArcElement, Tooltip);
    const config: ChartConfiguration<'doughnut'> = {
      type: 'doughnut',
      // 指向扇区时同步高亮对应图例项（反向联动）
      plugins: [chartFocusPlugin(setHighlighted)],
      data: {
        labels: distribution.map((bucket) => bucket.name),
        datasets: [
          {
            data: distribution.map((bucket) => bucket.totalScoreUnits),
            // 非聚焦扇区淡到 20%（beui / transitions.dev 环图口径）
            backgroundColor: (context) =>
              withAlpha(
                KNOWLEDGE_DONUT_PALETTE[context.dataIndex % KNOWLEDGE_DONUT_PALETTE.length],
                focusAlpha(context.chart, context.dataIndex, 0.2),
              ),
            hoverBackgroundColor: distribution.map(
              (_, index) => KNOWLEDGE_DONUT_PALETTE[index % KNOWLEDGE_DONUT_PALETTE.length],
            ),
            borderWidth: 0,
            spacing: 3,
            borderRadius: 3,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '66%',
        animation: chartEnterAnimation(),
        transitions: focusTransitions(),
        // 图例由组件内的 HTML 列表给出（含百分比，读屏可读）
        plugins: {
          legend: { display: false },
          tooltip: {
            ...chartTooltipTheme(),
            callbacks: {
              label: (context) => {
                const bucket = distribution[context.dataIndex];
                if (!bucket) return '';
                return `${bucket.name}：${bucket.itemCount} 题 · ${formatScoreUnits(
                  bucket.totalScoreUnits,
                )} 分 · ${ratioPercentText(bucket.scoreRatio)}`;
              },
            },
          },
        },
      },
    };
    let chart: ChartJS | null = null;
    try {
      chart = new ChartJS(element, config);
      // 拿不到 2D 上下文时 Chart.js 不抛错而是留下未初始化实例：不登记，并同样给出「图形不可用」提示。
      if (chart.ctx) {
        chartRef.current = chart;
      } else {
        chart = null;
        setCanvasUnavailable(true);
      }
    } catch {
      // 无 2D 上下文（jsdom / 极老浏览器）：保留 HTML 图例并明确说明
      setCanvasUnavailable(true);
      return;
    }
    return () => {
      chartRef.current = null;
      chart?.destroy();
    };
  }, [distribution]);

  if (distribution.length === 0) {
    return (
      <p className="assessments-hint" data-testid="paper-knowledge-donut-empty">
        该试卷还没有小题或知识点关联；导入校对并关联知识点后这里会显示占比。
      </p>
    );
  }

  return (
    <div className="paper-donut" data-testid="paper-knowledge-donut">
      <p className="assessments-hint">
        按当前修订的 primary 知识点聚合，取各知识点小题满分占比；未关联知识点的题目计入服务端给出的
        「未分类」桶。
      </p>
      <div className="paper-donut-body">
        <div className="paper-donut-canvas">
          <canvas ref={canvas} role="img" aria-label="试卷知识点占比环状图" />
          {canvasUnavailable && (
            <p className="assessments-hint" data-testid="paper-donut-canvas-unavailable">
              当前环境无法绘制环形图；下方图例给出每个知识点的题数、分值与占比。
            </p>
          )}
        </div>
        <ul className="paper-donut-legend" aria-label="知识点占比图例">
          {distribution.map((bucket, index) => (
            <li
              className={
                highlighted === index
                  ? 'paper-donut-legend-item highlighted'
                  : 'paper-donut-legend-item'
              }
              key={bucket.knowledgePointId}
              onMouseEnter={() => highlight(index)}
              onMouseLeave={() => highlight(null)}
            >
              <span
                className="paper-donut-swatch"
                aria-hidden
                style={{
                  background:
                    KNOWLEDGE_DONUT_PALETTE[index % KNOWLEDGE_DONUT_PALETTE.length],
                }}
              />
              <span className="paper-donut-legend-name">{bucket.name}</span>
              <span className="paper-donut-legend-value">
                {bucket.itemCount} 题 · {formatScoreUnits(bucket.totalScoreUnits)} 分 ·{' '}
                {ratioPercentText(bucket.scoreRatio)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
