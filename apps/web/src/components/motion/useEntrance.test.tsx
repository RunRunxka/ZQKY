import { StrictMode, useRef } from 'react';
import { act, cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import gsap from 'gsap';
import { MotionPreference } from '@/components/layout/MotionPreference';
import { useEntrance } from './useEntrance';

let systemReduced = false;
const mediaListeners = new Set<() => void>();
function Region({ visible = true, text = '内容' }: { visible?: boolean; text?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEntrance(ref, { preset: 'page', enabled: visible });
  return (
    <div ref={ref} hidden={!visible}>
      {Array.from({ length: 7 }, (_, index) => (
        <p data-motion-reveal key={index} data-testid={`item-${index}`}>
          {text}
        </p>
      ))}
    </div>
  );
}
function Drawer({ open }: { open: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEntrance(ref, { preset: 'drawer', enabled: open });
  return (
    <div ref={ref} data-testid="drawer" hidden={!open}>
      导航
    </div>
  );
}
const App = ({ visible = true, text }: { visible?: boolean; text?: string }) => (
  <MotionPreference>
    <Region visible={visible} text={text} />
  </MotionPreference>
);

beforeEach(() => {
  systemReduced = false;
  mediaListeners.clear();
  localStorage.clear();
  delete document.documentElement.dataset.motion;
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 400,
    bottom: 20,
    width: 400,
    height: 20,
    toJSON: () => ({}),
  });
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({
      get matches() {
        return systemReduced;
      },
      media: '(prefers-reduced-motion: reduce)',
      addEventListener: (_event: string, listener: () => void) => mediaListeners.add(listener),
      removeEventListener: (_event: string, listener: () => void) =>
        mediaListeners.delete(listener),
    })),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('workspace entrance boundaries', () => {
  it('skips CSS-hidden and off-screen regions', async () => {
    const tween = vi.spyOn(gsap, 'fromTo');
    function MarkedRegions() {
      const ref = useRef<HTMLDivElement>(null);
      useEntrance(ref, { preset: 'page' });
      return (
        <div ref={ref}>
          <p data-motion-reveal style={{ visibility: 'hidden' }}>
            隐藏标题
          </p>
          <p
            data-motion-reveal
            data-testid="offscreen"
            ref={(node) => {
              if (node)
                node.getBoundingClientRect = () => ({
                  x: 0,
                  y: 2000,
                  top: 2000,
                  left: 0,
                  right: 400,
                  bottom: 2020,
                  width: 400,
                  height: 20,
                  toJSON: () => ({}),
                });
            }}
          >
            屏外区域
          </p>
          <p data-motion-reveal data-testid="visible">
            首屏标题
          </p>
        </div>
      );
    }
    const view = render(
      <MotionPreference>
        <MarkedRegions />
      </MotionPreference>,
    );
    await waitFor(() => expect(tween).toHaveBeenCalledTimes(1));
    expect(tween.mock.calls[0][0]).toEqual([view.getByTestId('visible')]);
  });
  it('respects stored and system reduced motion without hiding content', async () => {
    localStorage.setItem('zqky.motion', 'reduced');
    const tween = vi.spyOn(gsap, 'fromTo');
    const view = render(<App />);
    await waitFor(() => expect(document.documentElement.dataset.motion).toBe('reduced'));
    expect(tween).not.toHaveBeenCalled();
    expect(view.getByTestId('item-0').style.opacity).toBe('');
    view.unmount();
    localStorage.clear();
    systemReduced = true;
    render(<App />);
    expect(tween).not.toHaveBeenCalled();
  });

  it('limits animation to six marked regions and does not replay on content updates', async () => {
    const tween = vi.spyOn(gsap, 'fromTo');
    const view = render(<App />);
    await waitFor(() => expect(tween).toHaveBeenCalledTimes(1));
    expect(tween.mock.calls[0][0]).toHaveLength(6);
    expect(view.getByTestId('item-6').style.opacity).toBe('');
    view.rerender(<App text="流式更新" />);
    expect(tween).toHaveBeenCalledTimes(1);
  });

  it('finishes immediately when local preference changes and does not replay when restored', async () => {
    const tween = vi.spyOn(gsap, 'fromTo');
    const view = render(<App />);
    await waitFor(() => expect(tween).toHaveBeenCalledTimes(1));
    const item = view.getByTestId('item-0');
    await act(async () => {
      document.documentElement.dataset.motion = 'reduced';
    });
    await waitFor(() => expect(item.style.transform).toBe(''));
    expect(item.style.opacity).toBe('');
    await act(async () => {
      document.documentElement.dataset.motion = 'system';
    });
    expect(tween).toHaveBeenCalledTimes(1);
  });

  it('reacts to system preference and releases listeners and tweens on unmount', async () => {
    const tween = vi.spyOn(gsap, 'fromTo');
    const view = render(<App />);
    await waitFor(() => expect(tween).toHaveBeenCalledTimes(1));
    const item = view.getByTestId('item-0');
    act(() => {
      systemReduced = true;
      mediaListeners.forEach((listener) => listener());
    });
    expect(item.style.transform).toBe('');
    expect(gsap.getTweensOf(item)).toHaveLength(0);
    view.unmount();
    expect(mediaListeners.size).toBe(0);
  });

  it('does not animate hidden panels until visible, and preserves their contents', async () => {
    const tween = vi.spyOn(gsap, 'fromTo');
    const view = render(<App visible={false} text="保留的编辑" />);
    expect(tween).not.toHaveBeenCalled();
    const item = view.getByTestId('item-0');
    view.rerender(<App visible text="保留的编辑" />);
    await waitFor(() => expect(tween).toHaveBeenCalledTimes(1));
    view.rerender(<App visible={false} text="保留的编辑" />);
    view.rerender(<App visible text="保留的编辑" />);
    expect(view.getByTestId('item-0')).toBe(item);
    expect(tween).toHaveBeenCalledTimes(1);
  });

  it('replays drawer entrance on reopening and cleans up under StrictMode', async () => {
    const tween = vi.spyOn(gsap, 'fromTo');
    const view = render(
      <MotionPreference>
        <Drawer open={false} />
      </MotionPreference>,
    );
    view.rerender(
      <MotionPreference>
        <Drawer open />
      </MotionPreference>,
    );
    await waitFor(() => expect(tween).toHaveBeenCalledTimes(1));
    const drawer = view.getByTestId('drawer');
    await act(async () => {
      document.documentElement.dataset.motion = 'reduced';
    });
    expect(drawer.style.transform).toBe('');
    await act(async () => {
      document.documentElement.dataset.motion = 'system';
    });
    expect(tween).toHaveBeenCalledTimes(1);
    view.rerender(
      <MotionPreference>
        <Drawer open={false} />
      </MotionPreference>,
    );
    expect(drawer.style.transform).toBe('');
    view.rerender(
      <MotionPreference>
        <Drawer open />
      </MotionPreference>,
    );
    expect(tween).toHaveBeenCalledTimes(2);
    view.unmount();
    expect(gsap.getTweensOf(drawer)).toHaveLength(0);
    const strict = render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
    const item = strict.getByTestId('item-0');
    strict.unmount();
    expect(gsap.getTweensOf(item)).toHaveLength(0);
    expect(mediaListeners.size).toBe(0);
  });
});
