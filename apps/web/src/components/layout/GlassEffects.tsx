'use client';
import { useEffect } from 'react';

/** 参与聚光/微倾的玻璃面板（与 glass.css 的效果选择器保持一致）。 */
const PANE_SELECTOR = '.app-header, .global-nav, .chat-composer';

/**
 * 玻璃主题的指针效果层（DSH spotlight/press 的平移）+ 页面边缘渐隐：
 * - 聚光辉光：光标所在玻璃面板点亮跟随光标的径向光斑——JS 只写
 *   `--glass-mx/--glass-my` 变量与 `data-glass-spot-on` 标记，视觉全在
 *   CSS ::after（isolation + z-index:-1，光斑在内容之后、玻璃底之上），
 *   不向 React 树注入/移除节点。
 * - 悬浮微倾：面板朝光标方向轻微倾斜（inline transform，离开即清除；
 *   面板集合里没有包含 fixed 子元素的容器，不会引发重锚问题）。
 * - 边缘渐隐：视口上下 13px 模糊渐隐带（本组件渲染的兄弟节点）。
 * 由 <html> 的 data-glass-spot / data-glass-press / data-glass-fades 门控，
 * 设置里可独立开关；reduced-motion（系统或站内偏好）时跳过倾斜。
 */
export function GlassEffects() {
  useEffect(() => {
    let raf = 0;
    let lastEvent: PointerEvent | null = null;

    const motionReduced = (): boolean =>
      window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
      document.documentElement.dataset.motion === 'reduced';

    const frame = () => {
      raf = 0;
      const root = document.documentElement;
      const spotOn = root.dataset.glassSpot === 'on';
      const pressOn = root.dataset.glassPress === 'on';
      const ev = lastEvent;
      const panes = document.querySelectorAll<HTMLElement>(PANE_SELECTOR);
      if (!spotOn && !pressOn) {
        // 效果整体关闭：清干净任何残留标记与倾斜。
        panes.forEach((el) => {
          if (el.dataset.glassSpotOn) delete el.dataset.glassSpotOn;
          el.style.removeProperty('--glass-mx');
          el.style.removeProperty('--glass-my');
          if (el.style.transform) el.style.transform = '';
        });
        return;
      }
      panes.forEach((el) => {
        const r = el.getBoundingClientRect();
        const inside =
          !!ev &&
          ev.clientX >= r.left &&
          ev.clientX <= r.right &&
          ev.clientY >= r.top &&
          ev.clientY <= r.bottom;
        if (spotOn) {
          if (inside && ev) {
            el.dataset.glassSpotOn = 'on';
            el.style.setProperty('--glass-mx', `${(ev.clientX - r.left).toFixed(1)}px`);
            el.style.setProperty('--glass-my', `${(ev.clientY - r.top).toFixed(1)}px`);
          } else if (el.dataset.glassSpotOn) {
            delete el.dataset.glassSpotOn;
            el.style.removeProperty('--glass-mx');
            el.style.removeProperty('--glass-my');
          }
        } else if (el.dataset.glassSpotOn) {
          delete el.dataset.glassSpotOn;
          el.style.removeProperty('--glass-mx');
          el.style.removeProperty('--glass-my');
        }
        if (pressOn && !motionReduced()) {
          if (inside && ev && r.height > 0 && r.width > 0) {
            const rx = ((ev.clientY - r.top) / r.height - 0.5) * 1.6;
            const ry = ((ev.clientX - r.left) / r.width - 0.5) * -1.6;
            el.style.transform = `perspective(800px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)`;
          } else if (el.style.transform) {
            el.style.transform = '';
          }
        } else if (el.style.transform) {
          el.style.transform = '';
        }
      });
    };

    const schedule = (ev: PointerEvent | null) => {
      lastEvent = ev;
      if (!raf) raf = requestAnimationFrame(frame);
    };
    const onMove = (ev: PointerEvent) => schedule(ev);
    const onLeave = () => schedule(null);
    window.addEventListener('pointermove', onMove, { passive: true });
    document.documentElement.addEventListener('pointerleave', onLeave);
    return () => {
      window.removeEventListener('pointermove', onMove);
      document.documentElement.removeEventListener('pointerleave', onLeave);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <>
      <div data-glass-fade="top" aria-hidden="true" />
      <div data-glass-fade="bottom" aria-hidden="true" />
    </>
  );
}
