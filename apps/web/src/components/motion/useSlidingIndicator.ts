'use client';

import { useLayoutEffect, type RefObject } from 'react';

/**
 * 分段控件 / 页签的滑动指示器：测量当前项（`.current` / `.selected` / `.active` /
 * `aria-selected` / `aria-pressed`）
 * 相对容器的位置，写入容器 CSS 变量，由容器 `::before` 画出滑块（样式见 motion.css
 * `[data-sliding-indicator]`）。
 *
 * - 只写 CSS 变量，不改子元素、不抢焦点，键盘与读屏语义完全不变；
 * - 首次测量后才置 `data-indicator-ready`，避免滑块从左上角「飞入」；
 * - 无当前项时置 `data-indicator-ready="false"`，滑块隐藏，按钮自身的 `.current` 底色兜底；
 * - 减少动画由全站 motion.css 统一把 transition 压到 0.01ms，这里不需要单独判断。
 */
export function useSlidingIndicator(
  container: RefObject<HTMLElement | null>,
  activeKey: unknown,
) {
  useLayoutEffect(() => {
    const root = container.current;
    if (!root) return;
    const measure = () => {
      const active = root.querySelector<HTMLElement>(
        ':scope > :is(.current, .selected, .active, [aria-selected="true"], [aria-pressed="true"])',
      );
      if (!active || active.offsetWidth === 0) {
        root.setAttribute('data-indicator-ready', 'false');
        return;
      }
      root.style.setProperty('--indicator-x', `${active.offsetLeft}px`);
      root.style.setProperty('--indicator-y', `${active.offsetTop}px`);
      root.style.setProperty('--indicator-w', `${active.offsetWidth}px`);
      root.style.setProperty('--indicator-h', `${active.offsetHeight}px`);
      // 先落位置再开过渡：首帧不动画，之后切换才滑动。
      if (root.getAttribute('data-indicator-ready') !== 'true') {
        requestAnimationFrame(() => {
          if (container.current === root) root.setAttribute('data-indicator-ready', 'true');
        });
      }
    };
    measure();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(measure);
    observer.observe(root);
    for (const child of Array.from(root.children)) observer.observe(child);
    return () => observer.disconnect();
  }, [container, activeKey]);
}
