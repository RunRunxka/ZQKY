'use client';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

type MotionState = { ready: boolean; reduced: boolean };
const MotionContext = createContext<MotionState>({ ready: false, reduced: true });

/** CSS and imperative animation share the same system + application preference. */
export function MotionPreference({ children }: { children?: ReactNode }) {
  const [preference, setPreference] = useState<MotionState>({ ready: false, reduced: true });
  useEffect(() => {
    const root = document.documentElement;
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => {
      const reduced = media.matches || root.dataset.motion === 'reduced';
      setPreference((previous) =>
        previous.ready && previous.reduced === reduced ? previous : { ready: true, reduced },
      );
    };
    const readStoredPreference = () => {
      try {
        root.dataset.motion =
          window.localStorage.getItem('zqky.motion') === 'reduced' ? 'reduced' : 'system';
      } catch {
        // A failed preference read never hides content or enables motion.
        root.dataset.motion = 'reduced';
      }
      update();
    };
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ['data-motion'] });
    readStoredPreference();
    media.addEventListener('change', update);
    window.addEventListener('storage', readStoredPreference);
    return () => {
      observer.disconnect();
      media.removeEventListener('change', update);
      window.removeEventListener('storage', readStoredPreference);
    };
  }, []);
  return <MotionContext.Provider value={preference}>{children}</MotionContext.Provider>;
}

export function useMotionPreference() {
  return useContext(MotionContext);
}
