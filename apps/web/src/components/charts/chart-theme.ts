'use client';

/**
 * Chart.js 全站主题（学情五图 / 对话图表预览共用）。
 *
 * 风格取向（参考 evilcharts 一类的「安静数据卡」）：
 * - 柱体自上而下的同色渐变 + 顶部圆角、底边直角，柱宽克制；
 * - 网格只留横向虚线、去掉轴线，刻度用 --muted 小字；
 * - 浅底提示框（白底 + 细边 + 大圆角），与全站弹层同一视觉；
 * - 入场：柱子自基线逐根升起 / 环形逐段展开（按数据序号错开 ≤ 360ms），减少动画时关闭；
 * - 悬停聚焦：指向某根柱 / 某段环时，其余数据项淡出（柱 30%、环 20%，150ms），突出当前项。
 *
 * 只读颜色/字体 token，不在模块顶层读 document（调用发生在 effect 内）。
 */

import { useEffect, useState } from 'react';
import type { Chart, Plugin, ScriptableContext } from 'chart.js';
import { resolvedThemeIsDark } from '@/components/layout/theme-preference';

export function readToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** 与 MotionPreference 同口径：系统偏好或应用内「减少动画」任一开启即关闭图表动画。 */
export function chartMotionReduced(): boolean {
  if (typeof window === 'undefined') return true;
  return (
    document.documentElement.dataset.motion === 'reduced' ||
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
  );
}

/** #rrggbb → rgba()；非六位十六进制原样返回（让 Chart.js 自行解析）。 */
export function withAlpha(color: string, alpha: number): string {
  const match = /^#([0-9a-f]{6})$/i.exec(color.trim());
  if (!match) return color;
  const value = Number.parseInt(match[1], 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
}

/* ------------------------------------------------------------ 悬停聚焦 */

type FocusableChart = Chart & { $zqkyFocus?: number | null };

/** 当前聚焦的数据序号（无聚焦为 null）。 */
export function chartFocusOf(chart: Chart): number | null {
  return (chart as FocusableChart).$zqkyFocus ?? null;
}

/**
 * 设置聚焦项并以自定义过渡模式 `focus` 重绘（150ms、无错开延迟）；同值不重绘，返回是否变化。
 * 不能用内置 `active` 模式：它会让本次更新的全部数据项按 hover* 样式解析（所有柱都变实色）。
 * Chart.js 运行时支持任意自定义模式名（对应 options.transitions[mode]），类型声明未列出，故收窄断言。
 */
export function setChartFocus(chart: Chart, index: number | null): boolean {
  const holder = chart as FocusableChart;
  // 未初始化的实例（无 2D 上下文）不重绘
  if (!chart.ctx || (holder.$zqkyFocus ?? null) === index) return false;
  holder.$zqkyFocus = index;
  chart.update('focus' as unknown as 'none');
  return true;
}

/**
 * 悬停聚焦插件（放在图表配置顶层 `plugins: [...]`）：指针所在列/段即聚焦项，离开图表区清除。
 * 用 afterEvent 而不是 options.onHover——后者只在指针位于图表区内时回调，移出时不会清除。
 */
export function chartFocusPlugin(onFocusChange?: (index: number | null) => void): Plugin {
  return {
    id: 'zqkyFocus',
    afterEvent(chart, args) {
      const leaving = !args.inChartArea || args.event.type === 'mouseout';
      const index = leaving ? null : (chart.getActiveElements()[0]?.index ?? null);
      if (setChartFocus(chart, index)) onFocusChange?.(index);
    },
  };
}

/** `focus` 过渡：聚焦切换只做 150ms 颜色过渡（纯色可插值；渐变无法插值时直接切换），不重放入场动画。 */
export function focusTransitions() {
  return { focus: { animation: { duration: 150, easing: 'easeOutCubic' as const } } };
}

/** 非聚焦项的透明度系数：有聚焦且不是自己时淡出。 */
export function focusAlpha(chart: Chart, dataIndex: number, dimmed: number): number {
  const focus = chartFocusOf(chart);
  return focus !== null && focus !== dataIndex ? dimmed : 1;
}

/**
 * 柱体渐变：沿柱子生长方向由实到浅（竖柱自上而下、横条自右向左）；非聚焦柱整体淡到 30%。
 * 图表区尚未布局时（首帧）退回纯色，避免 Chart.js 拿到 undefined。
 */
export function barGradient(color: string, horizontal = false) {
  return (context: ScriptableContext<'bar'>) => {
    const { chart } = context;
    const area = chart.chartArea;
    if (!area) return color;
    const alpha = focusAlpha(chart, context.dataIndex, 0.3);
    const gradient = horizontal
      ? chart.ctx.createLinearGradient(area.right, 0, area.left, 0)
      : chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
    gradient.addColorStop(0.15, withAlpha(color, 0.95 * alpha));
    gradient.addColorStop(1, withAlpha(color, (horizontal ? 0.55 : 0.42) * alpha));
    return gradient;
  };
}

/** 顶端圆角、基线直角（横条为右端圆角）。 */
export function barRadius(horizontal = false) {
  return horizontal
    ? { topLeft: 0, bottomLeft: 0, topRight: 6, bottomRight: 6 }
    : { topLeft: 6, topRight: 6, bottomLeft: 0, bottomRight: 0 };
}

/** 浅底提示框：白底 + 细边 + 10px 圆角，与全站弹层同一视觉；切换数据点时位置平滑过渡。 */
export function chartTooltipTheme() {
  const muted = readToken('--muted', '#5f6b7b');
  const ink = readToken('--ink', '#172033');
  const line = readToken('--line', '#dde5ef');
  const family = readToken('--font-ui', 'sans-serif');
  return {
    backgroundColor: 'rgba(255, 255, 255, 0.97)',
    borderColor: line,
    borderWidth: 1,
    titleColor: ink,
    bodyColor: muted,
    titleFont: { family, size: 12, weight: 600 as const },
    bodyFont: { family, size: 12 },
    padding: { x: 12, y: 10 },
    cornerRadius: 10,
    caretSize: 0,
    displayColors: false,
    animation: chartMotionReduced()
      ? (false as const)
      : { duration: 160, easing: 'easeOutCubic' as const },
  };
}

/** 入场动画：620ms easeOutQuart，按数据序号错开（每项 28ms，封顶 360ms）；减少动画时关闭。 */
export function chartEnterAnimation() {
  if (chartMotionReduced()) return false as const;
  return {
    duration: 620,
    easing: 'easeOutQuart' as const,
    delay: (context: { type: string; mode: string; dataIndex: number }) =>
      context.type === 'data' && context.mode === 'default'
        ? Math.min(context.dataIndex * 28, 360)
        : 0,
  };
}

/**
 * 柱状图主题片段：数值轴 / 类目轴 / 提示框 / 入场动画 / 悬停口径。
 * 以普通对象返回（不套 ChartOptions 联合类型），调用方按图展开并覆盖 min/max/标题/回调。
 */
export function barChartTheme() {
  const muted = readToken('--muted', '#5f6b7b');
  const line = readToken('--line', '#dde5ef');
  const family = readToken('--font-ui', 'sans-serif');
  const tickFont = { family, size: 11 };
  return {
    valueAxis: {
      // Chart.js 4：border.dash 作用于该轴的网格线（横向虚线）。
      border: { display: false, dash: [3, 4] },
      grid: { color: line, drawTicks: false },
      ticks: { color: muted, padding: 8, font: tickFont },
      title: { color: muted, font: tickFont },
    },
    categoryAxis: {
      border: { display: false },
      grid: { display: false },
      ticks: { color: muted, padding: 6, font: tickFont },
      title: { color: muted, font: tickFont },
    },
    tooltip: chartTooltipTheme(),
    animation: chartEnterAnimation(),
    transitions: focusTransitions(),
    focusPlugin: chartFocusPlugin(),
    /** 悬停整列命中：鼠标落在柱子所在行/列的任何位置都能看到提示，不必精确指在柱体上。 */
    interaction(horizontal = false) {
      return { mode: 'index' as const, intersect: false, axis: horizontal ? ('y' as const) : ('x' as const) };
    },
  };
}

/**
 * 当前生效的主题键（'light' | 'dark'）：切换应用内主题或系统深浅时变化。
 * 图表组件把它加入挂载 effect 的依赖——主题变了就用新颜色重建图表（颜色在创建时读取 token）。
 */
export function useResolvedThemeKey(): 'light' | 'dark' {
  const [key, setKey] = useState<'light' | 'dark'>('light');
  useEffect(() => {
    const root = document.documentElement;
    // 无 matchMedia 的环境（如 jsdom）只跟随应用内显式主题，不抛错
    const media = window.matchMedia?.('(prefers-color-scheme: dark)') ?? null;
    const update = () => setKey(resolvedThemeIsDark() ? 'dark' : 'light');
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ['data-theme'] });
    update();
    media?.addEventListener('change', update);
    return () => {
      observer.disconnect();
      media?.removeEventListener('change', update);
    };
  }, []);
  return key;
}
