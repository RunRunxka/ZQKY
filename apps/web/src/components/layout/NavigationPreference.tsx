'use client';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

const storageKey = 'zhiqikeyuan:nav-expanded';
const NavigationContext = createContext<{
  expanded: boolean;
  ready: boolean;
  toggle: () => void;
} | null>(null);

/** 根布局持有偏好，切换不同业务壳时不重新展开再读取存储。 */
export function NavigationPreference({ children }: { children: ReactNode }) {
  const [expanded, setExpanded] = useState(true);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    try {
      setExpanded(localStorage.getItem(storageKey) !== 'false');
    } catch {
      /* 本地偏好不可用时保持展开 */
    }
    setReady(true);
  }, []);

  function toggle() {
    const next = !expanded;
    setExpanded(next);
    try {
      localStorage.setItem(storageKey, String(next));
    } catch {
      /* 偏好保存失败不阻止折叠 */
    }
  }

  return (
    <NavigationContext.Provider value={{ expanded, ready, toggle }}>
      {children}
    </NavigationContext.Provider>
  );
}

export function useNavigationPreference() {
  const preference = useContext(NavigationContext);
  if (!preference) throw new Error('WorkspaceShell requires NavigationPreference');
  return preference;
}
