'use client';

import { useRef, type RefObject } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { useMotionPreference } from '@/components/layout/MotionPreference';

gsap.registerPlugin(useGSAP);

export type EntrancePreset = 'page' | 'panel' | 'modal' | 'drawer';
export interface EntranceOptions {
  preset: EntrancePreset;
  triggerKey?: string | number;
  enabled?: boolean;
}

function isVisible(node: HTMLElement) {
  const rect = node.getBoundingClientRect();
  if (getComputedStyle(node).visibility === 'hidden' || rect.width <= 0 || rect.height <= 0)
    return false;
  let left = Math.max(0, rect.left),
    right = Math.min(window.innerWidth, rect.right);
  let top = Math.max(0, rect.top),
    bottom = Math.min(window.innerHeight, rect.bottom);
  // Scroll containers can clip a region even when its rectangle intersects the viewport.
  for (let parent = node.parentElement; parent; parent = parent.parentElement) {
    const style = getComputedStyle(parent);
    const bounds = parent.getBoundingClientRect();
    if (/auto|scroll|hidden|clip/.test(style.overflowX)) {
      left = Math.max(left, bounds.left);
      right = Math.min(right, bounds.right);
    }
    if (/auto|scroll|hidden|clip/.test(style.overflowY)) {
      top = Math.max(top, bounds.top);
      bottom = Math.min(bottom, bounds.bottom);
    }
  }
  return right > left && bottom > top;
}

/** Stable UI identities only: never pass streamed text, fetched objects or polling ticks. */
export function useEntrance(
  scope: RefObject<HTMLElement | null>,
  { preset, triggerKey = 'initial', enabled = true }: EntranceOptions,
) {
  const { ready, reduced } = useMotionPreference();
  const entered = useRef(new Set<string | number>());
  const overlayEntered = useRef(false);

  useGSAP(
    () => {
      const root = scope.current;
      if (!enabled) {
        overlayEntered.current = false;
        return;
      }
      if (!ready || !root || root.closest('[hidden]')) return;
      if (preset === 'panel' && !isVisible(root)) return;
      const once = preset === 'page' || preset === 'panel';
      if (once && entered.current.has(triggerKey)) return;
      if (!once && overlayEntered.current) return;
      if (reduced) {
        if (once) entered.current.add(triggerKey);
        else overlayEntered.current = true;
        return;
      }
      const targets =
        preset === 'page'
          ? Array.from(root.querySelectorAll<HTMLElement>('[data-motion-reveal]'))
              .filter((node) => {
                const parentReveal = node.parentElement?.closest('[data-motion-reveal]');
                return (
                  !node.closest('[hidden]') &&
                  (!parentReveal || !root.contains(parentReveal)) &&
                  isVisible(node)
                );
              })
              .slice(0, 6)
          : [root];
      if (targets.length === 0) return;
      if (once) entered.current.add(triggerKey);
      else overlayEntered.current = true;

      const from =
        preset === 'drawer'
          ? { xPercent: -100 }
          : {
              opacity: 0,
              y: preset === 'page' ? 10 : preset === 'modal' ? 8 : 6,
              ...(preset === 'modal' ? { scale: 0.985 } : {}),
            };
      gsap.fromTo(targets, from, {
        opacity: 1,
        y: 0,
        xPercent: 0,
        scale: 1,
        duration:
          preset === 'page' ? 0.28 : preset === 'panel' ? 0.18 : preset === 'modal' ? 0.22 : 0.2,
        stagger: preset === 'page' ? 0.035 : 0,
        ease: 'power2.out',
        clearProps: 'opacity,transform',
        overwrite: 'auto',
      });
    },
    { scope, dependencies: [ready, reduced, enabled, preset, triggerKey], revertOnUpdate: true },
  );
}
