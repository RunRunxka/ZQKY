// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { attachFluidShader, SITE_FLUID_PARAMS, type FluidParams } from './fluid-shader';

/** 最小 2D 上下文替身：只实现本实现真正调用到的方法。 */
function fakeContext(): CanvasRenderingContext2D {
  const gradient = { addColorStop: vi.fn() };
  return {
    globalCompositeOperation: 'source-over',
    fillStyle: '',
    fillRect: vi.fn(),
    createRadialGradient: vi.fn(() => gradient),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
  } as unknown as CanvasRenderingContext2D;
}

function fakeCanvas(context: CanvasRenderingContext2D | null): HTMLCanvasElement {
  return {
    width: 0,
    height: 0,
    getContext: (type: string) => (type === '2d' ? context : null),
  } as unknown as HTMLCanvasElement;
}

/** 只区分「减少动画」查询；其余（粗指针）一律为否。 */
function stubMatchMedia(reduced: boolean): void {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query.includes('prefers-reduced-motion') ? reduced : false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

let rafCalls = 0;
let cancelledIds: number[] = [];

beforeEach(() => {
  stubMatchMedia(false);
  delete document.documentElement.dataset.motion;
  rafCalls = 0;
  cancelledIds = [];
  // 不让 rAF 回调真的执行：单测只关心「调度一次」与「停止」的语义
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => {
    rafCalls += 1;
    return 7;
  });
  vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id: number) => {
    cancelledIds.push(id);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  delete document.documentElement.dataset.motion;
});

describe('流体背景（自研实现）', () => {
  it('拿不到 2D 上下文时返回空句柄，不抛错也不调度帧', () => {
    const handle = attachFluidShader(fakeCanvas(null), SITE_FLUID_PARAMS);
    expect(() => {
      handle.setParams(SITE_FLUID_PARAMS);
      handle.stir(0.5, 0.5, 1, 1);
      handle.dispose();
    }).not.toThrow();
    expect(rafCalls).toBe(0);
  });

  it('常态只调度一次下一帧（不递归执行），dispose 停止循环并移除监听', () => {
    const remove = vi.spyOn(window, 'removeEventListener');
    const handle = attachFluidShader(fakeCanvas(fakeContext()), SITE_FLUID_PARAMS);
    expect(rafCalls).toBe(1);
    handle.dispose();
    expect(cancelledIds).toEqual([7]);
    expect(remove).toHaveBeenCalledWith('resize', expect.any(Function));
    expect(remove).toHaveBeenCalledWith('pointermove', expect.any(Function));
  });

  it('系统 prefers-reduced-motion 命中时只画一帧，退出帧循环', () => {
    stubMatchMedia(true);
    const handle = attachFluidShader(fakeCanvas(fakeContext()), SITE_FLUID_PARAMS);
    expect(rafCalls).toBe(1);
    expect(cancelledIds).toEqual([7]);
    handle.dispose();
  });

  it('本地 data-motion=reduced 命中时同样退出帧循环', () => {
    document.documentElement.dataset.motion = 'reduced';
    const handle = attachFluidShader(fakeCanvas(fakeContext()), SITE_FLUID_PARAMS);
    expect(cancelledIds).toEqual([7]);
    handle.dispose();
  });

  it('setParams 只热更新参数，不重新挂载也不重复调度', () => {
    const handle = attachFluidShader(fakeCanvas(fakeContext()), SITE_FLUID_PARAMS);
    const next: FluidParams = { ...SITE_FLUID_PARAMS, color1: '#123456', speed: 30 };
    handle.setParams(next);
    expect(rafCalls).toBe(1);
    handle.dispose();
  });

  it('粗指针设备不注册指针视差监听', () => {
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: query.includes('pointer: coarse'),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
    const add = vi.spyOn(window, 'addEventListener');
    const handle = attachFluidShader(fakeCanvas(fakeContext()), SITE_FLUID_PARAMS);
    expect(add).not.toHaveBeenCalledWith('pointermove', expect.any(Function), expect.anything());
    handle.dispose();
  });
});
