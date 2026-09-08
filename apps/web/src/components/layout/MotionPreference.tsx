'use client';
import { useEffect } from 'react';
export function MotionPreference() {
  useEffect(() => {
    const update = () => {
      try {
        document.documentElement.dataset.motion =
          window.localStorage.getItem('zqky.motion') === 'reduced' ? 'reduced' : 'system';
      } catch {
        /* Keep system preference. */
      }
    };
    update();
    window.addEventListener('storage', update);
    return () => window.removeEventListener('storage', update);
  }, []);
  return null;
}
