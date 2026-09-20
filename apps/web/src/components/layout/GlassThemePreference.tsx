'use client';
import { useEffect } from 'react';

const clamp = (value: number, lo: number, hi: number): number =>
  Math.min(hi, Math.max(lo, value));

/**
 * 玻璃质感主题偏好：读取 localStorage(zqky.glass*) 并把开关与旋钮写到
 * <html> 上（data-glass / data-glass-scheme / data-glass-bg + CSS 变量），
 * 由 glass.css 在对应属性组合下生效。关闭即原生界面，无残留。
 * 壁纸层本体由 GlassBackdrop 渲染；本组件只负责属性与变量。
 * 同页变更经 `zqky:glass-change` 事件同步，跨标签页走 storage 事件。
 * 模式仿 MotionPreference，不依赖任何 DSH 运行时。
 */
export function GlassThemePreference() {
  useEffect(() => {
    const apply = () => {
      try {
        const root = document.documentElement;
        const on = window.localStorage.getItem('zqky.glass') === 'on';
        root.dataset.glass = on ? 'on' : 'off';
        root.dataset.glassScheme =
          window.localStorage.getItem('zqky.glass-scheme') === 'dark' ? 'dark' : 'light';
        if (on) {
          const blur = clamp(Number(window.localStorage.getItem('zqky.glass-blur')) || 16, 0, 40);
          const frost = clamp(Number(window.localStorage.getItem('zqky.glass-frost')) || 60, 0, 100);
          root.style.setProperty('--glass-blur', `${blur}px`);
          root.style.setProperty('--glass-alpha', String(0.3 + (frost / 100) * 0.5));
          // 壁纸旋钮（DSH "Free backdrop" 的 wallpaper blur / frost / video dim）。
          const wpBlur = clamp(Number(window.localStorage.getItem('zqky.glass-wallpaper-blur')) || 0, 0, 40);
          const wpFrost = clamp(Number(window.localStorage.getItem('zqky.glass-wallpaper-frost')) || 0, 0, 100);
          const videoBrightness = clamp(Number(window.localStorage.getItem('zqky.glass-video-brightness')) || 45, 0, 100);
          root.style.setProperty('--glass-wallpaper-blur', `${wpBlur}px`);
          root.style.setProperty('--glass-wallpaper-frost', String(wpFrost / 100));
          root.style.setProperty('--glass-video-dim', String(((100 - videoBrightness) / 100) * 0.65));
          const wallpaper = window.localStorage.getItem('zqky.glass-wallpaper') ?? '';
          const source = window.localStorage.getItem('zqky.glass-bg');
          const wallpaperOn = source === 'wallpaper' && wallpaper !== '';
          root.dataset.glassBg = wallpaperOn ? 'wallpaper' : 'ambient';
          // 指针效果与边缘渐隐开关。悬浮微倾（3D 倾斜）按用户偏好默认关闭。
          const flag = (key: string, dflt = true): boolean => {
            const raw = window.localStorage.getItem(key);
            return raw === null ? dflt : raw === 'true';
          };
          root.dataset.glassSpot = flag('zqky.glass-spotlight') ? 'on' : 'off';
          root.dataset.glassPress = flag('zqky.glass-press', false) ? 'on' : 'off';
          root.dataset.glassFades = flag('zqky.glass-fades') ? 'on' : 'off';
          root.dataset.glassFluid = flag('zqky.glass-fluid') ? 'on' : 'off';
        } else {
          root.dataset.glassBg = 'ambient';
          root.dataset.glassSpot = 'off';
          root.dataset.glassPress = 'off';
          root.dataset.glassFades = 'off';
          root.dataset.glassFluid = 'off';
        }
      } catch {
        /* 保留默认外观 */
      }
    };
    apply();
    window.addEventListener('storage', apply);
    window.addEventListener('zqky:glass-change', apply);
    return () => {
      window.removeEventListener('storage', apply);
      window.removeEventListener('zqky:glass-change', apply);
    };
  }, []);
  return null;
}
