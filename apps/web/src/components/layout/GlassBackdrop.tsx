'use client';
import { useEffect, useRef, useState } from 'react';
import { getBlob } from './wallpaper-store';
import { attachFluidShader, SITE_FLUID_PARAMS, type FluidParams, type FluidShaderHandle } from './fluid-shader';
import { fluidToneColors } from './fluid-tones';

type BackdropView = { kind: 'none' | 'image' | 'video'; src: string };

const clamp = (value: number, lo: number, hi: number): number =>
  Math.min(hi, Math.max(lo, value));

/**
 * 玻璃主题背景层（"Free backdrop" 与流体板的形态），三形态互斥：
 * - ambient + 流体开：Canvas 2D 流体画布（fluid-shader.ts 自研实现）
 *   覆盖住 CSS 环境光（见 data-glass-fluid-ok）；
 * - ambient + 流体关：仅 CSS 环境光；
 * - wallpaper：图片/视频层（IndexedDB 引用，blob.type 自动区分）。
 * 旋钮经 `zqky:glass-change` 事件即时同步；跨页签走 storage 事件。
 */
export function GlassBackdrop() {
  const [wall, setWall] = useState<BackdropView>({ kind: 'none', src: '' });
  const [fluidActive, setFluidActive] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const handleRef = useRef<FluidShaderHandle | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | undefined;

    /** 从 localStorage 组装当前流体参数（深浅/色调/明暗方案）。 */
    const fluidParams = (): FluidParams => {
      const dark = document.documentElement.dataset.glassScheme === 'dark';
      const hue = clamp(Number(window.localStorage.getItem('zqky.glass-fluid-hue')) || 0, 0, 360);
      const depth = clamp(Number(window.localStorage.getItem('zqky.glass-fluid-depth')) || 25, 0, 100);
      return { ...SITE_FLUID_PARAMS, ...fluidToneColors(dark, hue, depth) };
    };

    const apply = async () => {
      try {
        const on = window.localStorage.getItem('zqky.glass') === 'on';
        const source = window.localStorage.getItem('zqky.glass-bg');
        const wallpaper = window.localStorage.getItem('zqky.glass-wallpaper') ?? '';
        const fluidOn =
          window.localStorage.getItem('zqky.glass-fluid') === null ||
          window.localStorage.getItem('zqky.glass-fluid') === 'true';

        // 壁纸形态
        if (!on || source !== 'wallpaper' || wallpaper === '') {
          setWall({ kind: 'none', src: '' });
        } else if (wallpaper.startsWith('idb:')) {
          const blob = await getBlob(wallpaper.slice(4));
          if (cancelled) return;
          if (!blob) {
            setWall({ kind: 'none', src: '' });
          } else {
            if (objectUrl !== undefined) URL.revokeObjectURL(objectUrl);
            const url = URL.createObjectURL(blob);
            objectUrl = url;
            setWall({ kind: blob.type.startsWith('video/') ? 'video' : 'image', src: url });
          }
        } else if (wallpaper.startsWith('data:video/')) {
          setWall({ kind: 'video', src: wallpaper });
        } else if (wallpaper.startsWith('data:image/')) {
          setWall({ kind: 'image', src: wallpaper });
        } else {
          setWall({ kind: 'none', src: '' });
        }

        // 流体形态：仅 环境光来源 + 玻璃开 + 流体开
        const nextFluid = on && source !== 'wallpaper' && fluidOn;
        setFluidActive(nextFluid);
        // 已挂载的句柄热更新参数（色调/深浅/明暗即时生效）
        if (handleRef.current !== undefined) {
          handleRef.current.setParams(fluidParams());
        }
      } catch {
        setWall({ kind: 'none', src: '' });
      }
    };

    void apply();
    const onChange = () => void apply();
    window.addEventListener('storage', onChange);
    window.addEventListener('zqky:glass-change', onChange);
    return () => {
      cancelled = true;
      window.removeEventListener('storage', onChange);
      window.removeEventListener('zqky:glass-change', onChange);
      if (objectUrl !== undefined) URL.revokeObjectURL(objectUrl);
    };
  }, []);

  // 挂载/卸载流体画布（fluidActive 变化时；含 2D 上下文失败降级标记）
  useEffect(() => {
    if (!fluidActive) {
      handleRef.current?.dispose();
      handleRef.current = undefined;
      delete document.documentElement.dataset.glassFluidOk;
      return;
    }
    const canvas = canvasRef.current;
    if (!canvas) return;
    // 2D 上下文预检：拿不到时立刻回落 CSS 环境光，不留空白画布。
    // 这里预检与 attachFluidShader 内部取的是同一种上下文，getContext 会返回
    // 同一个对象，不会像 WebGL→2D 那样把一个 canvas 的上下文槽位占掉。
    if (canvas.getContext('2d') === null) {
      document.documentElement.dataset.glassFluidOk = 'off';
      setFluidActive(false);
      return;
    }
    try {
      const dark = document.documentElement.dataset.glassScheme === 'dark';
      const hue = clamp(Number(window.localStorage.getItem('zqky.glass-fluid-hue')) || 0, 0, 360);
      const depth = clamp(Number(window.localStorage.getItem('zqky.glass-fluid-depth')) || 25, 0, 100);
      const params: FluidParams = {
        ...SITE_FLUID_PARAMS,
        ...fluidToneColors(dark, hue, depth),
      };
      const handle = attachFluidShader(canvas, params);
      handleRef.current = handle;
      document.documentElement.dataset.glassFluidOk = 'on';
    } catch {
      // 绘制失败绝不能拖垮主题：回落 CSS 环境光（移除画布层）。
      document.documentElement.dataset.glassFluidOk = 'off';
      setFluidActive(false);
    }
    return () => {
      handleRef.current?.dispose();
      handleRef.current = undefined;
      delete document.documentElement.dataset.glassFluidOk;
    };
  }, [fluidActive]);

  if (wall.kind !== 'none') {
    return (
      <div data-glass-backdrop data-media={wall.kind} aria-hidden="true">
        {wall.kind === 'image' ? (
          // 壁纸是用户本机选择的文件（objectURL/data URL），全屏 cover 且需被
          // backdrop-filter 采样，next/image 的优化与懒加载在此不适用
          // （与 DSH 插件的直连元素做法一致）。
          // eslint-disable-next-line @next/next/no-img-element
          <img src={wall.src} alt="" />
        ) : (
          <video src={wall.src} autoPlay loop muted playsInline />
        )}
      </div>
    );
  }
  if (fluidActive) {
    return (
      <div data-glass-ambient aria-hidden="true">
        <canvas ref={canvasRef} data-glass-fluid-canvas />
      </div>
    );
  }
  return null;
}
