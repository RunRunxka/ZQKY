'use client';

/**
 * 学情五图（R6-FE）：全部用 Chart.js（或等价的 token 化 DOM 色阶），数据分别来自
 * item-stats / knowledge-stats / student-knowledge / distribution。
 *
 * 口径（本卡裁定，覆盖归档的折线版趋势图）：
 * 1. 小题得分率趋势：**红色柱状图**（横轴题号、纵轴得分率 %），红色取自全站 token `--danger`；
 * 2. 小题得分热力图：题号 × 得分率档色阶（低→高：红→橙→黄→绿），保留归档口径；
 * 3. 知识点得分率排行：褐色/蓝色横向条形（按得分率从低到高，最薄弱在最上；≤60% 标褐）；
 * 4. 学生 × 知识点薄弱热力图：矩阵（行=学生 label，列=知识点；null 显示「尚无」而非 0）；
 * 5. 得分率分数段分布：柱状（低/中/高分档计数）。
 *
 * 每张卡各自持有数据源与重试入口：任一来源失败只影响该卡，不静默画出空图，也不影响其他卡。
 */

import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  Tooltip,
  type ChartConfiguration,
} from 'chart.js';
import {
  barGradient,
  barRadius,
  readToken,
  barChartTheme,
  useResolvedThemeKey,
} from '@/components/charts/chart-theme';
import type { AsyncState } from './score-hooks';
import { useAsyncResource } from './score-hooks';
import { learningAnalysisApi as api } from '@/services/learning-analysis-api';
import type {
  DistributionResponse,
  ItemStatView,
  KnowledgeStatsResponse,
  StudentKnowledgeResponse,
} from '@/contracts/learning-analysis';

/* ------------------------------------------------------------------ 色板（项目 token） */

/** 红色柱：优先取全站 token `--danger`（globals.css: #c62d21），读取不到时用同值兜底。 */
const DANGER_FALLBACK = '#c62d21';
/** 项目蓝（`--blue`）与薄弱褐（本卡新增，仅用于排行条的薄弱档；不新增独立主题）。 */
const BLUE_FALLBACK = '#2563eb';
const WEAK_BROWN = '#8a5a2e';

/** 得分率（0–1）→ 档色（低=红、中=黄、高=绿；null=中性）。 */
const HEAT_BANDS: readonly { upper: number; color: string }[] = [
  { upper: 40, color: '#e05c5c' },
  { upper: 60, color: '#eaa14e' },
  { upper: 80, color: '#d8c94f' },
  { upper: 100, color: '#5abf7a' },
];
const HEAT_NONE = '#e6ebf2';

function heatColor(rate: number | null): string {
  if (rate === null) return HEAT_NONE;
  const pct = Math.round(rate * 100);
  return HEAT_BANDS.find((band) => pct < band.upper)?.color ?? HEAT_BANDS[HEAT_BANDS.length - 1].color;
}

/** 得分率小数 → 百分比文本（一位小数；null 不显示 0）。 */
function rateText(rate: number | null): string {
  if (rate === null) return '—';
  return `${Math.round(rate * 1000) / 10}%`;
}

/* ------------------------------------------------------------------ 卡片外壳（独立错误/空态） */

function ChartCard({
  title,
  caption,
  testId,
  state,
  onRetry,
  isEmpty,
  emptyText,
  children,
}: {
  title: string;
  caption: string;
  testId: string;
  state: AsyncState<unknown>;
  onRetry: () => void;
  isEmpty: boolean;
  emptyText: string;
  children: ReactNode;
}) {
  return (
    <section className="la-chart-card" data-testid={testId} aria-label={title}>
      <div className="la-chart-head">
        <h3>{title}</h3>
        <p className="la-chart-caption">{caption}</p>
      </div>
      {state.phase === 'loading' && (
        <p className="la-chart-state" role="status">
          正在读取数据…
        </p>
      )}
      {state.phase === 'failed' && (
        <div className="space-banner error" role="alert" data-testid={`${testId}-error`}>
          {title}数据读取失败（{state.error.code}）：{state.error.message}
          <div className="la-chart-actions">
            <button className="space-button" onClick={onRetry}>
              重试
            </button>
          </div>
        </div>
      )}
      {state.phase !== 'failed' && isEmpty && state.phase === 'ready' && (
        <p className="la-chart-state" data-testid={`${testId}-empty`}>
          {emptyText}
        </p>
      )}
      {state.phase === 'ready' && !isEmpty && children}
    </section>
  );
}

/* ------------------------------------------------------------------ 1. 小题得分率趋势（红色柱） */

function ItemTrendCanvas({ stats }: { stats: ItemStatView[] }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);

  const themeKey = useResolvedThemeKey();
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    let chart: ChartJS | null = null;
    try {
      ChartJS.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);
      const danger = readToken('--danger', DANGER_FALLBACK);
      const theme = barChartTheme();
      const config: ChartConfiguration<'bar'> = {
        type: 'bar',
        plugins: [theme.focusPlugin],
        data: {
          labels: stats.map((stat) => stat.itemPath),
          datasets: [
            {
              label: '得分率 %',
              // 无有效作答的题为 null：留空并在 tooltip 说明，不补 0。
              data: stats.map((stat) =>
                stat.scoreRate === null ? null : Math.round(stat.scoreRate * 1000) / 10,
              ),
              backgroundColor: barGradient(danger),
              hoverBackgroundColor: danger,
              borderRadius: barRadius(),
              borderSkipped: false,
              maxBarThickness: 32,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: theme.animation,
          transitions: theme.transitions,
          interaction: theme.interaction(),
          scales: {
            y: {
              ...theme.valueAxis,
              min: 0,
              max: 100,
              ticks: { ...theme.valueAxis.ticks, callback: (value) => `${value}` },
              title: { ...theme.valueAxis.title, display: true, text: '得分率 %' },
            },
            x: {
              ...theme.categoryAxis,
              title: { ...theme.categoryAxis.title, display: true, text: '题号' },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              ...theme.tooltip,
              callbacks: {
                label: (context) => {
                  const raw = context.dataset.data[context.dataIndex] as number | null;
                  return raw === null || raw === undefined ? '无有效作答' : `得分率 ${raw}%`;
                },
              },
            },
          },
        },
      };
      chart = new ChartJS(element, config);
      setFailed(false);
    } catch {
      setFailed(true);
    }
    return () => {
      chart?.destroy();
    };
  }, [stats, themeKey]);

  if (failed) {
    return (
      <p className="la-chart-state" role="status" data-testid="la-trend-fallback">
        当前环境无法绘制图表，直接列出数据：
        {stats.map((stat) => `${stat.itemPath} ${rateText(stat.scoreRate)}`).join('；')}
      </p>
    );
  }
  return (
    <div className="la-chart-canvas">
      <canvas ref={canvas} role="img" aria-label="小题得分率趋势：横轴题号，纵轴得分率" />
    </div>
  );
}

export function ItemTrendCard({ runId }: { runId: string }) {
  const resource = useAsyncResource(
    (signal) => api.getAnalysisItemStats(runId, signal),
    `la-item-stats|${runId}`,
  );
  const stats = resource.lastData;
  return (
    <ChartCard
      title="小题得分率趋势"
      caption="红色柱：横轴题号、纵轴得分率 %（无有效作答的题留空，不补 0）"
      testId="la-trend-card"
      state={resource.state}
      onRetry={resource.reload}
      isEmpty={(stats ?? []).length === 0}
      emptyText="本次报告还没有小题得分数据。"
    >
      {stats && <ItemTrendCanvas stats={stats} />}
    </ChartCard>
  );
}

/* ------------------------------------------------------------------ 2. 小题得分热力图 */

export function ItemHeatmapCard({ runId }: { runId: string }) {
  const resource = useAsyncResource(
    (signal) => api.getAnalysisItemStats(runId, signal),
    `la-item-heatmap|${runId}`,
  );
  const stats = resource.lastData;
  return (
    <ChartCard
      title="小题得分热力图"
      caption="题号 × 得分率档色阶（低→高：红→橙→黄→绿；灰=无有效作答）"
      testId="la-heatmap-card"
      state={resource.state}
      onRetry={resource.reload}
      isEmpty={(stats ?? []).length === 0}
      emptyText="本次报告还没有小题得分数据。"
    >
      {stats && (
        <div className="analysis-heatmap" data-testid="analysis-heatmap">
          <div className="analysis-heatmap-row" role="list" aria-label="小题得分热力图">
            {stats.map((stat) => {
              const pct = stat.scoreRate === null ? null : Math.round(stat.scoreRate * 100);
              return (
                <div
                  key={stat.itemId}
                  role="listitem"
                  className="analysis-heat-cell"
                  title={`${stat.itemPath}：${pct === null ? '无有效作答' : `${pct}%`}（有效 ${stat.recordedCount} 人 / 满分 ${stat.maxScoreUnits}）`}
                >
                  <span className="analysis-heat-no">{stat.itemPath}</span>
                  <span
                    className="analysis-heat-value"
                    style={{ background: heatColor(stat.scoreRate) }}
                  >
                    {pct === null ? '—' : pct}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="analysis-heat-legend" aria-hidden="true">
            <span>低</span>
            {HEAT_BANDS.map((band) => (
              <i key={band.upper} style={{ background: band.color }} />
            ))}
            <span>高</span>
            <span className="analysis-heat-legend-note">灰=无有效作答（不补 0）</span>
          </div>
        </div>
      )}
    </ChartCard>
  );
}

/* ------------------------------------------------------------------ 3. 知识点得分率排行 */

function KnowledgeRankingCanvas({ items }: { items: KnowledgeStatsResponse['items'] }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);

  const themeKey = useResolvedThemeKey();
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    let chart: ChartJS | null = null;
    try {
      ChartJS.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);
      const blue = readToken('--blue', BLUE_FALLBACK);
      const theme = barChartTheme();
      // 倒序展示：按得分率从低到高（最薄弱在最上），褐色标出 ≤60% 的薄弱知识点。
      const ordered = [...items].sort((a, b) => a.scoreRate - b.scoreRate);
      const config: ChartConfiguration<'bar'> = {
        type: 'bar',
        plugins: [theme.focusPlugin],
        data: {
          labels: ordered.map((item) => (item.path ? `${item.name}（${item.path}）` : item.name)),
          datasets: [
            {
              label: '得分率 %',
              data: ordered.map((item) => Math.round(item.scoreRate * 1000) / 10),
              backgroundColor: (context) =>
                barGradient((ordered[context.dataIndex]?.scoreRate ?? 1) < 0.6 ? WEAK_BROWN : blue, true)(
                  context,
                ),
              hoverBackgroundColor: ordered.map((item) =>
                item.scoreRate < 0.6 ? WEAK_BROWN : blue,
              ),
              borderRadius: barRadius(true),
              borderSkipped: false,
              maxBarThickness: 22,
            },
          ],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          animation: theme.animation,
          transitions: theme.transitions,
          interaction: theme.interaction(true),
          scales: {
            x: {
              ...theme.valueAxis,
              min: 0,
              max: 100,
              title: { ...theme.valueAxis.title, display: true, text: '得分率 %' },
            },
            // 横向条形的类目轴不反转：第一条（得分率最低、最薄弱）在最上。
            y: { ...theme.categoryAxis },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              ...theme.tooltip,
              callbacks: {
                label: (context) => {
                  const item = ordered[context.dataIndex];
                  return `得分率 ${context.parsed.x}%（${item.questionCount} 道题）`;
                },
              },
            },
          },
        },
      };
      chart = new ChartJS(element, config);
      setFailed(false);
    } catch {
      setFailed(true);
    }
    return () => {
      chart?.destroy();
    };
  }, [items, themeKey]);

  if (failed) {
    return (
      <p className="la-chart-state" role="status" data-testid="la-knowledge-fallback">
        当前环境无法绘制图表，直接列出数据：
        {items.map((item) => `${item.name} ${rateText(item.scoreRate)}`).join('；')}
      </p>
    );
  }
  return (
    <div className="la-chart-canvas la-chart-canvas-ranking">
      <canvas ref={canvas} role="img" aria-label="知识点得分率排行：横向条形，从低到高" />
    </div>
  );
}

export function KnowledgeRankingCard({ runId }: { runId: string }) {
  const resource = useAsyncResource(
    (signal) => api.getAnalysisKnowledgeStats(runId, signal),
    `la-knowledge-stats|${runId}`,
  );
  const items = resource.lastData?.items;
  return (
    <ChartCard
      title="知识点得分率排行"
      caption="横向条形（按得分率从低到高，最薄弱在最上；褐色=低于 60% 的薄弱知识点）"
      testId="la-knowledge-card"
      state={resource.state}
      onRetry={resource.reload}
      isEmpty={(items ?? []).length === 0}
      emptyText="本次报告还没有知识点聚合数据（知识点库关联为空？）。"
    >
      {items && <KnowledgeRankingCanvas items={items} />}
    </ChartCard>
  );
}

/* ------------------------------------------------------------------ 4. 学生 × 知识点薄弱热力图 */

export function StudentKnowledgeCard({ runId }: { runId: string }) {
  const resource = useAsyncResource(
    (signal) => api.getAnalysisStudentKnowledge(runId, signal),
    `la-student-knowledge|${runId}`,
  );
  const data: StudentKnowledgeResponse | null = resource.lastData;
  const students = data?.students ?? [];
  const points = data?.knowledgePoints ?? [];
  return (
    <ChartCard
      title="学生 × 知识点薄弱热力图"
      caption="行=学生（后端给的代称 label，前端不做姓名推断）、列=知识点；「尚无」=没有有效依据，不显示 0"
      testId="la-student-card"
      state={resource.state}
      onRetry={resource.reload}
      isEmpty={students.length === 0 || points.length === 0}
      emptyText="本次报告还没有学生 × 知识点矩阵数据。"
    >
      {data && (
        <div className="la-matrix-wrap" tabIndex={0} aria-label="学生 × 知识点矩阵，可横向滚动">
          <table className="la-matrix" data-testid="la-student-matrix">
            <caption className="visually-hidden">学生 × 知识点得分率矩阵（后端聚合）</caption>
            <thead>
              <tr>
                <th scope="col">学生</th>
                {data.knowledgePoints.map((point) => (
                  <th key={point.knowledgePointId} scope="col" title={point.name}>
                    {point.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.students.map((student, rowIndex) => (
                <tr key={`${student.label}-${rowIndex}`}>
                  <th scope="row">{student.label}</th>
                  {data.knowledgePoints.map((point) => {
                    const cell = student.cells.find(
                      (candidate) => candidate.knowledgePointId === point.knowledgePointId,
                    );
                    const rate = cell?.scoreRate ?? null;
                    const text = rate === null ? '尚无' : rateText(rate);
                    return (
                      <td
                        key={point.knowledgePointId}
                        className={rate === null ? 'la-matrix-cell empty' : 'la-matrix-cell'}
                        style={rate === null ? undefined : { background: heatColor(rate) }}
                        data-testid={`la-student-cell-${rowIndex}-${point.knowledgePointId}`}
                        title={`${student.label} · ${point.name}：${
                          rate === null ? '尚无有效依据' : rateText(rate)
                        }${cell ? `（${cell.questionCount} 道题）` : ''}`}
                      >
                        {text}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </ChartCard>
  );
}

/* ------------------------------------------------------------------ 5. 得分率分数段分布 */

function DistributionCanvas({ buckets }: { buckets: DistributionResponse['buckets'] }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);

  const themeKey = useResolvedThemeKey();
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    let chart: ChartJS | null = null;
    try {
      ChartJS.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);
      const blue = readToken('--blue', BLUE_FALLBACK);
      const theme = barChartTheme();
      const config: ChartConfiguration<'bar'> = {
        type: 'bar',
        plugins: [theme.focusPlugin],
        data: {
          labels: buckets.map((bucket) => bucket.label),
          datasets: [
            {
              label: '小题数',
              data: buckets.map((bucket) => bucket.count),
              backgroundColor: barGradient(blue),
              hoverBackgroundColor: blue,
              borderRadius: barRadius(),
              borderSkipped: false,
              maxBarThickness: 44,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: theme.animation,
          transitions: theme.transitions,
          interaction: theme.interaction(),
          scales: {
            y: {
              ...theme.valueAxis,
              beginAtZero: true,
              ticks: { ...theme.valueAxis.ticks, precision: 0 },
              title: { ...theme.valueAxis.title, display: true, text: '题数' },
            },
            x: {
              ...theme.categoryAxis,
              title: { ...theme.categoryAxis.title, display: true, text: '得分率分档' },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              ...theme.tooltip,
              callbacks: { label: (context) => `${context.parsed.y} 道小题` },
            },
          },
        },
      };
      chart = new ChartJS(element, config);
      setFailed(false);
    } catch {
      setFailed(true);
    }
    return () => {
      chart?.destroy();
    };
  }, [buckets, themeKey]);

  if (failed) {
    return (
      <p className="la-chart-state" role="status" data-testid="la-distribution-fallback">
        当前环境无法绘制图表，直接列出数据：
        {buckets.map((bucket) => `${bucket.label} ${bucket.count} 题`).join('；')}
      </p>
    );
  }
  return (
    <div className="la-chart-canvas">
      <canvas ref={canvas} role="img" aria-label="得分率分数段分布：低/中/高分档计数" />
    </div>
  );
}

export function DistributionCard({ runId }: { runId: string }) {
  const resource = useAsyncResource(
    (signal) => api.getAnalysisDistribution(runId, signal),
    `la-distribution|${runId}`,
  );
  const buckets = resource.lastData?.buckets;
  return (
    <ChartCard
      title="得分率分数段分布"
      caption="柱状：低/中/高分档的小题计数（分档口径由后端给出）"
      testId="la-distribution-card"
      state={resource.state}
      onRetry={resource.reload}
      isEmpty={(buckets ?? []).length === 0}
      emptyText="本次报告还没有分数段分布数据。"
    >
      {buckets && <DistributionCanvas buckets={buckets} />}
    </ChartCard>
  );
}
