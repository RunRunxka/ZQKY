import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { HistoryRegistrations } from './HistoryRegistrations';

const mocks = vi.hoisted(() => ({
  readKnowledge: vi.fn(),
  subscribeKnowledge: vi.fn(),
}));

vi.mock('@/services/knowledge-catalog', () => ({
  readKnowledge: mocks.readKnowledge,
  subscribeKnowledge: mocks.subscribeKnowledge,
}));

beforeEach(() => {
  mocks.subscribeKnowledge.mockReturnValue(() => {});
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('历史登记（只读）', () => {
  it('列出现有本地登记并链接到既有详情路由', () => {
    mocks.readKnowledge.mockReturnValue([
      {
        id: 'kb-1',
        name: '课程标准库 1',
        description: '旧登记',
        docs: [{ id: 'd1', name: 'a.md' }],
      },
    ]);
    render(<HistoryRegistrations />);

    expect(screen.getByText('课程标准库 1')).toBeInTheDocument();
    expect(screen.getByText('登记文档 1')).toBeInTheDocument();
    expect(screen.getByText(/历史本地登记/)).toBeInTheDocument();
    expect(screen.getByText(/不参与真实检索/)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /课程标准库 1/ });
    expect(link).toHaveAttribute('href', `/knowledge-bases/${encodeURIComponent('课程标准库 1')}`);
  });

  it('读取失败显示错误与重试，不当作空目录', () => {
    mocks.readKnowledge.mockImplementation(() => {
      throw new Error('知识来源目录格式不兼容，原数据已保留。');
    });
    render(<HistoryRegistrations />);

    expect(screen.getByRole('alert')).toHaveTextContent('知识来源目录格式不兼容');
    expect(screen.queryByText('没有历史本地登记')).not.toBeInTheDocument();

    mocks.readKnowledge.mockReturnValue([]);
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(screen.getByText('没有历史本地登记')).toBeInTheDocument();
  });

  it('空登记显示空态而不是错误', () => {
    mocks.readKnowledge.mockReturnValue([]);
    render(<HistoryRegistrations />);
    expect(screen.getByText('没有历史本地登记')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
