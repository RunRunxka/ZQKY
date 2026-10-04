'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, type ComponentProps, type ReactNode } from 'react';

type LeaveGuard = () => Promise<boolean>;
type NavigationAction = () => void | Promise<void>;
interface NavigationGuardController {
  readonly hasProvider: boolean;
  register: (contextKey: string, guard: LeaveGuard) => () => void;
  requestNavigation: (action: NavigationAction) => Promise<boolean>;
}

const NavigationGuardContext = createContext<NavigationGuardController | null>(null);
const HISTORY_POSITION = '__zqkyNavigationPosition';

function historyPosition(state: unknown): number | null {
  const value = state && typeof state === 'object' ? (state as Record<string, unknown>)[HISTORY_POSITION] : null;
  return Number.isSafeInteger(value) ? value as number : null;
}

function stampHistory(state: unknown, position: number): unknown {
  // Next's private history state is preserved. Primitive foreign entries use recovery caches.
  return state === null || typeof state === 'object'
    ? { ...state as Record<string, unknown> | null, [HISTORY_POSITION]: position }
    : state;
}

export function NavigationGuardProvider({ children }: { children: ReactNode }) {
  const guards = useRef(new Map<string, { guard: LeaveGuard }>());
  const registrations = useRef(0);
  const busy = useRef(false);
  const mounted = useRef(true);
  const epoch = useRef(0);

  const register = useCallback((key: string, guard: LeaveGuard) => {
    const registration = { guard };
    guards.current.set(key, registration);
    registrations.current += 1;
    return () => {
      if (guards.current.get(key) === registration) { guards.current.delete(key); registrations.current += 1; }
    };
  }, []);

  const requestNavigation = useCallback(async (action: NavigationAction): Promise<boolean> => {
    if (busy.current || !mounted.current) return false;
    busy.current = true;
    const token = epoch.current;
    const registeredAtStart = registrations.current;
    try {
      for (const [key, entry] of [...guards.current]) {
        let permitted: boolean;
        try { permitted = await entry.guard(); } catch { return false; }
        if (!permitted || !mounted.current || token !== epoch.current || registeredAtStart !== registrations.current || guards.current.get(key) !== entry) return false;
      }
      if (!mounted.current || token !== epoch.current || registeredAtStart !== registrations.current) return false;
      await action(); // Preserve legacy beforeNavigate errors for the caller's existing UI.
      return true;
    } finally {
      if (token === epoch.current) busy.current = false;
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    const history = window.history;
    const originalPush = history.pushState;
    const originalReplace = history.replaceState;
    let position = historyPosition(history.state) ?? 0;
    let currentHref = window.location.href;
    let alive = true;
    let transition: { sourceHref: string; sourcePosition: number; delta: number; phase: 'restoring' | 'waiting' | 'replaying' } | null = null;

    originalReplace.call(history, stampHistory(history.state, position), '', currentHref);
    const push: History['pushState'] = (data: unknown, unused: string, url?: string | URL | null) => {
      originalPush.call(history, stampHistory(data, position + 1), unused, url);
      position += 1;
      currentHref = window.location.href;
    };
    const replace: History['replaceState'] = (data: unknown, unused: string, url?: string | URL | null) => {
      originalReplace.call(history, stampHistory(data, position), unused, url);
      currentHref = window.location.href;
    };
    history.pushState = push;
    history.replaceState = replace;

    const pop = (event: PopStateEvent) => {
      const targetPosition = historyPosition(event.state);
      if (transition?.phase === 'replaying') {
        transition = null;
        if (targetPosition !== null) position = targetPosition;
        currentHref = window.location.href;
        return; // Exactly this accepted traversal reaches Next's normal popstate handler.
      }
      if (transition) {
        event.stopImmediatePropagation();
        if (window.location.href !== transition.sourceHref) {
          if (targetPosition !== null) history.go(transition.sourcePosition - targetPosition);
          return;
        }
        position = transition.sourcePosition;
        currentHref = transition.sourceHref;
        if (transition.phase !== 'restoring') return;
        const pending = transition;
        pending.phase = 'waiting';
        void requestNavigation(() => {
          if (!alive || transition !== pending) return;
          pending.phase = 'replaying';
          history.go(pending.delta);
        }).then((permitted) => {
          if (!permitted && transition === pending) transition = null;
        });
        return;
      }
      if (!guards.current.size || targetPosition === null || targetPosition === position) {
        if (targetPosition !== null) position = targetPosition;
        currentHref = window.location.href;
        return;
      }
      const delta = targetPosition - position;
      event.stopImmediatePropagation();
      transition = { sourceHref: currentHref, sourcePosition: position, delta, phase: 'restoring' };
      // Restore the exact history entry before opening an asynchronous leave decision.
      history.go(-delta);
    };
    window.addEventListener('popstate', pop, true);
    return () => {
      alive = false;
      mounted.current = false;
      epoch.current += 1;
      busy.current = false;
      transition = null;
      window.removeEventListener('popstate', pop, true);
      if (history.pushState === push) history.pushState = originalPush;
      if (history.replaceState === replace) history.replaceState = originalReplace;
    };
  }, [requestNavigation]);

  const value = useMemo(() => ({ hasProvider: true, register, requestNavigation }), [register, requestNavigation]);
  return <NavigationGuardContext.Provider value={value}>{children}</NavigationGuardContext.Provider>;
}

const unguarded: NavigationGuardController = {
  hasProvider: false,
  register: () => () => {},
  requestNavigation: async (action) => { await action(); return true; },
};

export function useNavigationGuard(): NavigationGuardController {
  return useContext(NavigationGuardContext) ?? unguarded;
}

type GuardedLinkProps = Omit<ComponentProps<typeof Link>, 'href' | 'onNavigate'> & { href: string };

function RegisteredGuardedLink({ controller, href, replace, scroll, ...props }: GuardedLinkProps & { controller: NavigationGuardController }) {
  const router = useRouter();
  return <Link {...props} href={href} replace={replace} scroll={scroll} onNavigate={(event) => {
    event.preventDefault();
    void controller.requestNavigation(() => {
      if (replace) router.replace(href, { scroll });
      else router.push(href, { scroll });
    }).catch(() => {});
  }} />;
}

export function GuardedLink(props: GuardedLinkProps) {
  const controller = useContext(NavigationGuardContext);
  // Existing standalone component hosts retain normal Link behaviour and require no router hook.
  return controller ? <RegisteredGuardedLink {...props} controller={controller} /> : <Link {...props} />;
}
