import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SlidingGroup } from './SlidingGroup';

/** jsdom 不做布局：按按钮序号伪造 offset 几何（每个 80px 宽、间隔 4px）。 */
function fakeLayout() {
  const geometry = (element: HTMLElement) => {
    const index = element.parentElement ? Array.from(element.parentElement.children).indexOf(element) : 0;
    return { left: 3 + index * 84, width: element.tagName === 'BUTTON' ? 80 : 0 };
  };
  vi.spyOn(HTMLElement.prototype, 'offsetLeft', 'get').mockImplementation(function (this: HTMLElement) {
    return geometry(this).left;
  });
  vi.spyOn(HTMLElement.prototype, 'offsetTop', 'get').mockReturnValue(3);
  vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockImplementation(function (this: HTMLElement) {
    return geometry(this).width;
  });
  vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(30);
}

function Tabs({ initial = 'a' }: { initial?: string }) {
  const [tab, setTab] = useState(initial);
  return (
    <SlidingGroup activeKey={tab} className="space-tabs" role="tablist" aria-label="视图">
      {['a', 'b', 'c'].map((id) => (
        <button
          key={id}
          role="tab"
          aria-selected={tab === id}
          className={tab === id ? 'current' : ''}
          onClick={() => setTab(id)}
        >
          {id.toUpperCase()}
        </button>
      ))}
    </SlidingGroup>
  );
}

beforeEach(() => {
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
    callback(0);
    return 0;
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('SlidingGroup 滑动指示器', () => {
  it('原样透传 role / aria / 类名，不改变子按钮语义', () => {
    fakeLayout();
    render(<Tabs />);
    const list = screen.getByRole('tablist', { name: '视图' });
    expect(list).toHaveClass('space-tabs');
    expect(list).toHaveAttribute('data-sliding-indicator', '');
    expect(screen.getByRole('tab', { name: 'A' })).toHaveAttribute('aria-selected', 'true');
  });

  it('量出当前项位置后才进入就绪态，切换后滑块跟到新当前项', () => {
    fakeLayout();
    render(<Tabs />);
    const list = screen.getByRole('tablist');
    expect(list).toHaveAttribute('data-indicator-ready', 'true');
    expect(list.style.getPropertyValue('--indicator-x')).toBe('3px');
    expect(list.style.getPropertyValue('--indicator-w')).toBe('80px');
    expect(list.style.getPropertyValue('--indicator-h')).toBe('30px');

    act(() => {
      fireEvent.click(screen.getByRole('tab', { name: 'C' }));
    });
    expect(list.style.getPropertyValue('--indicator-x')).toBe('171px');
    expect(screen.getByRole('tab', { name: 'C' })).toHaveAttribute('aria-selected', 'true');
  });

  it('当前项不可见（零宽）时不就绪，滑块隐藏、由按钮自身样式兜底', () => {
    // 不伪造布局：jsdom 下 offsetWidth 恒为 0
    render(<Tabs />);
    expect(screen.getByRole('tablist')).toHaveAttribute('data-indicator-ready', 'false');
  });

  it('underline 变体写入 data-sliding-indicator="underline"', () => {
    fakeLayout();
    render(
      <SlidingGroup activeKey="x" variant="underline" role="tablist" aria-label="卷面">
        <button className="current">学生卷</button>
      </SlidingGroup>,
    );
    expect(screen.getByRole('tablist', { name: '卷面' })).toHaveAttribute(
      'data-sliding-indicator',
      'underline',
    );
  });
});
