'use client';
import { useEffect, useState } from 'react';
import { getVideoBlob } from './wallpaper-store';

type BackdropView = { kind: 'none' | 'image' | 'video'; src: string };

/**
 * 玻璃主题的自定义壁纸层（DSH "Free backdrop" 的平移）：
 * 独立的 fixed 元素（z-index:-1），image 直接 data URL，video 为浏览器原生
 * <video>（loop + muted 保证自动播放；直连元素而非 iframe，backdrop-filter
 * 才能对其采样磨砂）。开启条件：玻璃开 + 背景来源=壁纸 + 有壁纸数据。
 * 同页变更经 `zqky:glass-change` 自定义事件同步，跨页签走 storage 事件。
 */
export function GlassBackdrop() {
  const [view, setView] = useState<BackdropView>({ kind: 'none', src: '' });

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | undefined;

    const apply = async () => {
      try {
        const on = window.localStorage.getItem('zqky.glass') === 'on';
        const source = window.localStorage.getItem('zqky.glass-bg');
        const wallpaper = window.localStorage.getItem('zqky.glass-wallpaper') ?? '';
        if (!on || source !== 'wallpaper' || wallpaper === '') {
          setView({ kind: 'none', src: '' });
          return;
        }
        if (wallpaper.startsWith('idb:')) {
          const blob = await getVideoBlob(wallpaper.slice(4));
          if (cancelled) return;
          if (!blob) {
            setView({ kind: 'none', src: '' });
            return;
          }
          if (objectUrl !== undefined) URL.revokeObjectURL(objectUrl);
          const url = URL.createObjectURL(blob);
          objectUrl = url;
          setView({ kind: 'video', src: url });
        } else if (wallpaper.startsWith('data:video/')) {
          setView({ kind: 'video', src: wallpaper });
        } else {
          setView({ kind: 'image', src: wallpaper });
        }
      } catch {
        setView({ kind: 'none', src: '' });
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

  if (view.kind === 'none') return null;
  return (
    <div data-glass-backdrop data-media={view.kind} aria-hidden="true">
      {view.kind === 'image' ? (
        // 壁纸是用户本机选择的 data URL，全屏 cover 且需被 backdrop-filter 采样，
        // next/image 的优化与懒加载在此不适用（与 DSH 插件的直连元素做法一致）。
        // eslint-disable-next-line @next/next/no-img-element
        <img src={view.src} alt="" />
      ) : (
        <video src={view.src} autoPlay loop muted playsInline />
      )}
    </div>
  );
}
