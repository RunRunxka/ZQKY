import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ExtensionPicker } from './ExtensionPicker';
import type { ExtensionEntry } from '@/services/extension-catalog';

const ENTRIES: ExtensionEntry[] = [
  { id: 'm1', kind: 'mcp', name: '搜索工具', description: '演示检索', content: '', enabled: true },
  { id: 'm2', kind: 'mcp', name: '计算工具', description: '', content: '', enabled: true },
  { id: 'm3', kind: 'mcp', name: '未启用工具', description: '', content: '', enabled: false },
  { id: 's1', kind: 'skill', name: '提问技能', description: '演示技能', content: '', enabled: true },
];

function renderPicker(selected: string[] = [], onToggle = vi.fn()) {
  const result = render(
    <ExtensionPicker entries={ENTRIES} selected={selected} onToggle={onToggle} />,
  );
  return { ...result, onToggle };
}

function openPanel() {
  fireEvent.click(screen.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' }));
}

afterEach(cleanup);

describe('聊天扩展选择器', () => {
  it('分开展示已启用的 MCP 与 Skills，未启用项不出现，可搜索', () => {
    renderPicker();
    openPanel();
    const dialog = screen.getByRole('dialog', { name: '选择本轮扩展' });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '选择MCP 搜索工具' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '选择MCP 计算工具' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '选择技能 提问技能' })).toBeInTheDocument();
    expect(screen.queryByText('未启用工具')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '管理 MCP' })).toHaveAttribute(
      'href',
      '/settings#mcp',
    );
    expect(screen.getByRole('link', { name: '管理 Skills' })).toHaveAttribute(
      'href',
      '/settings#skills',
    );

    fireEvent.change(screen.getByRole('textbox', { name: '搜索扩展' }), {
      target: { value: '计算' },
    });
    expect(screen.getByRole('button', { name: '选择MCP 计算工具' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '选择MCP 搜索工具' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '选择技能 提问技能' })).not.toBeInTheDocument();
  });

  it('点击切换选择并回调，选中态随 selected 属性展示', () => {
    const { onToggle } = renderPicker(['m1']);
    openPanel();
    expect(screen.getByRole('button', { name: '移除MCP 搜索工具' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    fireEvent.click(screen.getByRole('button', { name: '移除MCP 搜索工具' }));
    expect(onToggle).toHaveBeenCalledWith('m1');
    fireEvent.click(screen.getByRole('button', { name: '选择技能 提问技能' }));
    expect(onToggle).toHaveBeenCalledWith('s1');
  });

  it('Escape 关闭面板：先播放退场动画（inert）再卸载，焦点恢复触发按钮', async () => {
    renderPicker();
    const trigger = screen.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' });
    fireEvent.click(trigger);
    const dialog = screen.getByRole('dialog', { name: '选择本轮扩展' });
    fireEvent.keyDown(dialog, { key: 'Escape' });
    // 退场动画期间保持挂载、inert 且不获得焦点
    expect(dialog).toHaveClass('closing');
    expect(dialog).toHaveAttribute('inert');
    expect(trigger).toHaveFocus();
    // 动画结束后卸载
    await vi.waitFor(
      () => expect(screen.queryByRole('dialog', { name: '选择本轮扩展' })).not.toBeInTheDocument(),
      { timeout: 1000 },
    );
  });

  it('没有已启用扩展时给出空态说明', () => {
    render(<ExtensionPicker entries={[]} selected={[]} onToggle={vi.fn()} />);
    openPanel();
    expect(screen.getByText('还没有已启用的扩展。可在设置中添加并启用。')).toBeVisible();
  });

  it('R10：菜单打开时内部点击不关闭，外部点击关闭且不抢焦点', () => {
    renderPicker();
    openPanel();
    // 内部点击（选择选项）不关闭
    fireEvent.click(screen.getByRole('button', { name: '选择MCP 搜索工具' }));
    expect(screen.getByRole('dialog', { name: '选择本轮扩展' })).toBeInTheDocument();
    // 外部点击：关闭（退场动画期间挂载），焦点留在用户点击的位置，不抢回触发器
    const outside = document.createElement('button');
    document.body.appendChild(outside);
    outside.focus();
    fireEvent.pointerDown(outside);
    expect(screen.getByRole('dialog', { name: '选择本轮扩展' })).toHaveClass('closing');
    expect(screen.queryByRole('button', { name: '选择本轮扩展（MCP 与技能）' })).not.toHaveFocus();
    expect(outside).toHaveFocus();
    outside.remove();
  });

  it('R9：进入发送状态时已打开的菜单关闭，选项不再可操作', async () => {    const onToggle = vi.fn();
    const { rerender } = renderPicker(['m1'], onToggle);
    openPanel();
    expect(screen.getByRole('dialog', { name: '选择本轮扩展' })).toBeInTheDocument();
    // 焦点仍在菜单内（搜索框）时父级进入发送状态：菜单自动关闭且选项禁用
    rerender(<ExtensionPicker entries={ENTRIES} selected={['m1']} onToggle={onToggle} disabled />);
    const dialog = screen.queryByRole('dialog', { name: '选择本轮扩展' });
    if (dialog) {
      // 退场动画期间保持挂载但 inert，选项不可操作
      expect(dialog).toHaveAttribute('inert');
      fireEvent.click(screen.getByRole('button', { name: '移除MCP 搜索工具' }));
      fireEvent.click(screen.getByRole('button', { name: '选择MCP 计算工具' }));
    }
    expect(onToggle).not.toHaveBeenCalled();
    await vi.waitFor(
      () => expect(screen.queryByRole('dialog', { name: '选择本轮扩展' })).not.toBeInTheDocument(),
      { timeout: 1000 },
    );
  });
});
