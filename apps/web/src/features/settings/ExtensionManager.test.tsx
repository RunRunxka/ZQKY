import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ExtensionManager } from './ExtensionManager';
import { BUILTIN_SKILLS, readExtensions, saveExtension } from '@/services/extension-catalog';

beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    clear: () => values.clear(),
  });
});

afterEach(cleanup);

describe('设置页扩展管理（Skill 分区）', () => {
  it('口径如实：说明技能会随问答发送且不执行工具，不写成模拟', () => {
    render(<ExtensionManager kind="skill" />);
    expect(screen.getByText(/已启用的技能会随本轮问答发送给模型/)).toBeVisible();
    expect(screen.getByText(/不执行工具、不访问外部服务/)).toBeVisible();
    expect(screen.queryByText(/模拟模式/)).toBeNull();
  });

  it('MCP 分区明确标注未实现，不能写成可用能力', () => {
    render(<ExtensionManager kind="mcp" />);
    expect(screen.getByText(/当前未实现/)).toBeVisible();
    expect(screen.getByText(/不会连接、检测或执行任何外部服务/)).toBeVisible();
    // 只有 Skill 分区提供内置技能载入入口
    expect(screen.queryByRole('button', { name: '载入内置教学技能' })).toBeNull();
  });

  it('载入内置教学技能：写入目录、默认启用并回报数量', () => {
    render(<ExtensionManager kind="skill" />);
    fireEvent.click(screen.getByRole('button', { name: '载入内置教学技能' }));
    const skills = readExtensions().filter((item) => item.kind === 'skill');
    expect(skills).toHaveLength(BUILTIN_SKILLS.length);
    expect(skills.every((item) => item.enabled && item.content.trim() !== '')).toBe(true);
    expect(screen.getByText(new RegExp(`已载入内置教学技能 ${BUILTIN_SKILLS.length} 个`))).toBeVisible();
    expect(screen.getByText('教案规范')).toBeVisible();
  });

  it('技能说明为空时如实提示本轮不生效', () => {
    saveExtension({
      id: 'empty',
      kind: 'skill',
      name: '空说明技能',
      description: '',
      content: '   ',
      enabled: true,
    });
    render(<ExtensionManager kind="skill" />);
    expect(screen.getByText(/未填写技能说明，本轮不会生效/)).toBeVisible();
  });

  it('技能说明非空时不显示不生效提示', () => {
    saveExtension({
      id: 'ready',
      kind: 'skill',
      name: '教案规范',
      description: '按模板栏目输出',
      content: '按七个栏目输出。',
      enabled: true,
    });
    render(<ExtensionManager kind="skill" />);
    expect(screen.queryByText(/未填写技能说明/)).toBeNull();
  });
});
