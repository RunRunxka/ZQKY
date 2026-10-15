import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Chart, ScriptableContext } from 'chart.js';
import {
  barChartTheme,
  barGradient,
  chartEnterAnimation,
  chartFocusOf,
  chartFocusPlugin,
  focusAlpha,
  setChartFocus,
  withAlpha,
} from './chart-theme';

function fakeChart(chartArea?: { top: number; bottom: number; left: number; right: number }) {
  const stops: Array<[number, string]> = [];
  const chart = {
    chartArea,
    update: vi.fn(),
    getActiveElements: vi.fn(() => [] as Array<{ index: number }>),
    ctx: {
      createLinearGradient: vi.fn(() => ({
        addColorStop: (offset: number, color: string) => stops.push([offset, color]),
      })),
    },
  };
  return { chart: chart as unknown as Chart & typeof chart, stops };
}

afterEach(() => {
  delete document.documentElement.dataset.motion;
});

describe('chart-theme', () => {
  it('withAlpha 把六位十六进制转成 rgba，其它写法原样返回', () => {
    expect(withAlpha('#2563eb', 0.5)).toBe('rgba(37, 99, 235, 0.5)');
    expect(withAlpha('rgb(1, 2, 3)', 0.5)).toBe('rgb(1, 2, 3)');
  });

  it('柱体渐变：图表区未布局时退回基色；布局后生成同色由实到浅的渐变', () => {
    const empty = fakeChart();
    const color = barGradient('#c62d21')({ chart: empty.chart, dataIndex: 0 } as unknown as ScriptableContext<'bar'>);
    expect(color).toBe('#c62d21');

    const laid = fakeChart({ top: 0, bottom: 100, left: 0, right: 100 });
    barGradient('#c62d21')({ chart: laid.chart, dataIndex: 0 } as unknown as ScriptableContext<'bar'>);
    expect(laid.stops).toEqual([
      [0.15, 'rgba(198, 45, 33, 0.95)'],
      [1, 'rgba(198, 45, 33, 0.42)'],
    ]);
  });

  it('悬停聚焦：非聚焦项淡出、聚焦项不变；同值不重复重绘', () => {
    const { chart, stops } = fakeChart({ top: 0, bottom: 100, left: 0, right: 100 });
    expect(chartFocusOf(chart)).toBeNull();
    expect(setChartFocus(chart, 2)).toBe(true);
    expect(setChartFocus(chart, 2)).toBe(false);
    expect(chart.update).toHaveBeenCalledTimes(1);
    expect(focusAlpha(chart, 2, 0.3)).toBe(1);
    expect(focusAlpha(chart, 0, 0.3)).toBe(0.3);

    barGradient('#2563eb')({ chart, dataIndex: 0 } as unknown as ScriptableContext<'bar'>);
    expect(stops[0][1]).toBe(`rgba(37, 99, 235, ${0.95 * 0.3})`);
  });

  it('聚焦插件：指针离开图表区时清除聚焦并通知', () => {
    const { chart } = fakeChart();
    const onFocus = vi.fn();
    const plugin = chartFocusPlugin(onFocus);
    const afterEvent = plugin.afterEvent as (chart: Chart, args: unknown) => void;

    chart.getActiveElements.mockReturnValue([{ index: 1 }]);
    afterEvent(chart, { inChartArea: true, event: { type: 'mousemove' } });
    expect(chartFocusOf(chart)).toBe(1);
    expect(onFocus).toHaveBeenLastCalledWith(1);

    afterEvent(chart, { inChartArea: false, event: { type: 'mouseout' } });
    expect(chartFocusOf(chart)).toBeNull();
    expect(onFocus).toHaveBeenLastCalledWith(null);
  });

  it('减少动画时关闭入场与提示框动画', () => {
    document.documentElement.dataset.motion = 'reduced';
    expect(chartEnterAnimation()).toBe(false);
    expect(barChartTheme().tooltip.animation).toBe(false);
  });

  it('入场按数据序号错开，封顶 360ms；聚焦切换不错开', () => {
    const animation = chartEnterAnimation();
    if (!animation) throw new Error('expected animation');
    expect(animation.delay({ type: 'data', mode: 'default', dataIndex: 3 })).toBe(84);
    expect(animation.delay({ type: 'data', mode: 'default', dataIndex: 99 })).toBe(360);
    expect(animation.delay({ type: 'data', mode: 'focus', dataIndex: 3 })).toBe(0);
  });
});
