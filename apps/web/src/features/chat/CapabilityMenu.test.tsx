import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { CapabilityMenu } from './CapabilityMenu';
import { CapabilityConfigCard } from './CapabilityConfigCard';
import { createDefaultCapabilityForms } from '@/services/capability-catalog';

afterEach(cleanup);

function openMenu() {
  fireEvent.click(screen.getByRole('button', { name: /^选择业务能力，当前：/ }));
  return screen.getByRole('dialog', { name: '选择业务能力' });
}

describe('模式选择菜单', () => {
  it('单层列表展示全部模式，当前能力带勾选态；不再有“更多能力”飞出层入口', () => {
    render(<CapabilityMenu value="" onSelect={vi.fn()} />);
    const dialog = openMenu();
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: /^对话/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(within(dialog).getByRole('button', { name: /^智能出题/ })).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: /^可视化/ })).toBeInTheDocument();
    // RAG 模式取代原“更多能力”的位置：同级一行，不再是二级菜单入口
    expect(within(dialog).getByRole('button', { name: /^RAG 模式/ })).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: /^更多能力/ })).toBeNull();
    expect(dialog.querySelector('.chat-cap-more')).toBeNull();
    expect(dialog.querySelector('.chat-cap-flyout')).toBeNull();
    // 已移除的三项能力不得回流
    expect(within(dialog).queryByRole('button', { name: /^深度求解/ })).toBeNull();
    expect(within(dialog).queryByRole('button', { name: /^深度研究/ })).toBeNull();
    expect(within(dialog).queryByRole('button', { name: /^沉浸观看/ })).toBeNull();
  });

  it('真实模式：教材入口可选，未实现的出题与可视化仍禁用', () => {
    const unavailable = new Set(['deep_question', 'visualize']);
    render(<CapabilityMenu value="" onSelect={vi.fn()} unavailable={unavailable} />);
    const dialog = openMenu();
    const quiz = within(dialog).getByRole('button', { name: /^智能出题/ });
    expect(quiz).toBeDisabled();
    expect(within(dialog).getAllByText('真实服务未接入').length).toBeGreaterThan(0);
    expect(within(dialog).getByRole('button', { name: /^对话/ })).toBeEnabled();
    // 教材入口独立于普通云模型，选择后由服务可用性检查给出真实结果。
    const rag = within(dialog).getByRole('button', { name: /^RAG 模式/ });
    expect(rag).toBeEnabled();
    expect(rag).not.toHaveTextContent('未接入 · 规划中');
    expect(within(dialog).getByRole('button', { name: /^追问澄清/ })).toBeEnabled();
  });

  it('选择能力回调并关闭菜单', () => {
    const onSelect = vi.fn();
    render(<CapabilityMenu value="" onSelect={onSelect} />);
    const dialog = openMenu();
    fireEvent.click(within(dialog).getByRole('button', { name: /^智能出题/ }));
    expect(onSelect).toHaveBeenCalledWith('deep_question');
  });
});

describe('能力配置卡', () => {
  it('校验错误可见时确认禁用；修复后可确认并显示已确认徽标', () => {
    const forms = createDefaultCapabilityForms();
    const { rerender } = render(
      <CapabilityConfigCard
        capability="deep_question"
        forms={forms}
        confirmed={false}
        errors={['出题主题不能为空。']}
        onConfirm={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/出题主题不能为空。/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '确认' })).toBeDisabled();
    expect(screen.getByText('必填')).toBeInTheDocument();

    rerender(
      <CapabilityConfigCard
        capability="deep_question"
        forms={forms}
        confirmed={false}
        errors={[]}
        onConfirm={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: '确认' })).toBeEnabled();
  });

  it('出题表单字段：模式分段、主题输入、数量、难度与题型多选', () => {
    render(
      <CapabilityConfigCard
        capability="deep_question"
        forms={createDefaultCapabilityForms()}
        confirmed={false}
        errors={[]}
        onConfirm={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText('出题模式')).toBeInTheDocument();
    expect(screen.getByLabelText('出题主题')).toBeInTheDocument();
    expect(screen.getByRole('group', { name: '出题模式' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '选择题' }).length).toBeGreaterThan(0);
  });

  it('已移除的研究配置不再渲染（随“更多能力”一并删除）', () => {
    render(
      <CapabilityConfigCard
        capability="deep_research"
        forms={createDefaultCapabilityForms()}
        confirmed={false}
        errors={[]}
        onConfirm={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    expect(screen.queryByText('研究设置')).toBeNull();
    expect(screen.queryByText('产出类型')).toBeNull();
    expect(screen.queryByText('研究深度')).toBeNull();
  });
});
