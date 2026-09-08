import { describe, expect, it, vi, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { WorkspaceShell } from './WorkspaceShell';
import { navigation } from '@/services/navigation';

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/lesson-plans',
  useRouter: () => ({ push }),
}));

function renderShell() {
  return render(
    <WorkspaceShell pageTitle="教案工作台">
      <main>页面内容</main>
    </WorkspaceShell>,
  );
}

describe('WorkspaceShell 导航', () => {
  afterEach(cleanup);

  it('渲染全部登记入口（隐藏项除外），规划中模块的可访问名称统一携带状态', () => {
    renderShell();
    for (const item of navigation) {
      // S5-A：hidden 项（如 /notebooks）只保留路由与规划页解析，不出现在侧栏
      if (item.hidden) {
        expect(
          screen.queryByRole('button', { name: new RegExp(item.label) }),
        ).not.toBeInTheDocument();
        continue;
      }
      const name = item.status === 'planned' ? `${item.label}（规划中）` : item.label;
      expect(screen.getByRole('button', { name }), `缺少入口：${item.label}`).toBeInTheDocument();
    }
    expect(screen.getByRole('button', { name: '教案工作台' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('展开项目导航后显示分组标题与完整标签', () => {
    renderShell();
    fireEvent.click(screen.getByRole('button', { name: '展开项目导航' }));
    expect(screen.getByText('教学工作台')).toBeInTheDocument();
    expect(screen.getByText('教学资源')).toBeInTheDocument();
    expect(screen.getByText('扩展能力')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '收起项目导航' })).toBeInTheDocument();
  });

  it('手机导航抽屉包含全部入口（隐藏项除外），可打开与关闭', () => {
    renderShell();
    fireEvent.click(screen.getByRole('button', { name: '打开功能导航' }));
    const dialog = screen.getByRole('dialog', { name: '功能导航' });
    expect(dialog).toBeInTheDocument();
    for (const item of navigation) {
      if (item.hidden) continue;
      const name = item.status === 'planned' ? `${item.label}（规划中）` : item.label;
      expect(within(dialog).getByRole('button', { name })).toBeInTheDocument();
    }
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: '功能导航' })).not.toBeInTheDocument();
  });
});
