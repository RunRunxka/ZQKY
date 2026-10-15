import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { KnowledgeDonut } from './KnowledgeDonut';

const DISTRIBUTION = [
  { knowledgePointId: 'kp-1', name: '函数', itemCount: 3, totalScoreUnits: 3000, scoreRatio: 0.6 },
  { knowledgePointId: 'kp-2', name: '数列', itemCount: 2, totalScoreUnits: 2000, scoreRatio: 0.4 },
];

// 测试环境的 canvas 降级（getContext 返回 null）由 tests/setup.ts 统一提供。
afterEach(cleanup);

describe('KnowledgeDonut 无 canvas 环境', () => {
  it('拿不到 2D 上下文时明确提示「无法绘制」，图例仍逐项可读', () => {
    render(<KnowledgeDonut distribution={DISTRIBUTION} />);
    expect(screen.getByTestId('paper-donut-canvas-unavailable')).toBeInTheDocument();
    expect(screen.getByText('函数')).toBeInTheDocument();
  });
});

describe('KnowledgeDonut 图例联动', () => {
  it('悬停图例项时高亮该项，移出后恢复（无 canvas 环境也成立）', () => {
    render(<KnowledgeDonut distribution={DISTRIBUTION} />);
    const legend = screen.getByRole('list', { name: '知识点占比图例' });
    const [first, second] = Array.from(legend.querySelectorAll('li'));

    fireEvent.mouseEnter(first);
    expect(first).toHaveClass('highlighted');
    expect(second).not.toHaveClass('highlighted');

    fireEvent.mouseEnter(second);
    expect(second).toHaveClass('highlighted');
    expect(first).not.toHaveClass('highlighted');

    fireEvent.mouseLeave(second);
    expect(legend.querySelector('.highlighted')).toBeNull();
  });

  it('图例仍逐项给出题数、分值与服务端占比', () => {
    render(<KnowledgeDonut distribution={DISTRIBUTION} />);
    expect(screen.getByText('函数')).toBeInTheDocument();
    expect(screen.getByText(/3 题 · 30 分 · 60/)).toBeInTheDocument();
  });
});
