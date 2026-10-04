import { StrictMode } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NavigationGuardProvider, useNavigationGuard } from './navigation-guard';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const wrapper = ({ children }: { children: React.ReactNode }) => <StrictMode><NavigationGuardProvider>{children}</NavigationGuardProvider></StrictMode>;

describe('navigation decisions', () => {
  it('allows clean navigation and preserves an existing caller save error', async () => {
    const { result } = renderHook(() => useNavigationGuard(), { wrapper });
    const navigate = vi.fn();
    expect(await result.current.requestNavigation(navigate)).toBe(true);
    expect(navigate).toHaveBeenCalledTimes(1);
    await expect(result.current.requestNavigation(() => { throw new Error('local save failed'); })).rejects.toThrow('local save failed');
  });
  it('keeps the current document when its leave decision is cancelled or fails', async () => {
    const { result } = renderHook(() => useNavigationGuard(), { wrapper });
    const navigate = vi.fn();
    const remove = result.current.register('practice:p1', async () => false);
    expect(await result.current.requestNavigation(navigate)).toBe(false);
    remove();
    result.current.register('practice:p1', async () => { throw new Error('recovery failed'); });
    expect(await result.current.requestNavigation(navigate)).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });
  it('allows only one pending leave action and refuses a stale document decision', async () => {
    const { result } = renderHook(() => useNavigationGuard(), { wrapper });
    let answer!: (value: boolean) => void;
    const decision = new Promise<boolean>((resolve) => { answer = resolve; });
    const remove = result.current.register('practice:p1', () => decision);
    const first = vi.fn(); const second = vi.fn();
    const pending = result.current.requestNavigation(first);
    expect(await result.current.requestNavigation(second)).toBe(false);
    remove(); result.current.register('practice:p2', async () => true);
    answer(true);
    expect(await pending).toBe(false);
    expect(first).not.toHaveBeenCalled(); expect(second).not.toHaveBeenCalled();
  });
  it('an old unregister does not remove a newer registration with the same document key', async () => {
    const { result } = renderHook(() => useNavigationGuard(), { wrapper });
    const old = result.current.register('p1', async () => true);
    const current = vi.fn(async () => false);
    result.current.register('p1', current); old();
    expect(await result.current.requestNavigation(vi.fn())).toBe(false);
    expect(current).toHaveBeenCalledTimes(1);
  });
  it('does not bypass a new dirty document registered while another decision is pending', async () => {
    const { result } = renderHook(() => useNavigationGuard(), { wrapper });
    let answer!: (value: boolean) => void;
    result.current.register('p1', () => new Promise<boolean>((resolve) => { answer = resolve; }));
    const navigate = vi.fn(); const pending = result.current.requestNavigation(navigate);
    result.current.register('p2', async () => false); answer(true);
    expect(await pending).toBe(false); expect(navigate).not.toHaveBeenCalled();
  });
  it('does not navigate after the provider has unmounted while awaiting a decision', async () => {
    const { result, unmount } = renderHook(() => useNavigationGuard(), { wrapper });
    let answer!: (value: boolean) => void;
    result.current.register('p1', () => new Promise<boolean>((resolve) => { answer = resolve; }));
    const navigate = vi.fn(); const pending = result.current.requestNavigation(navigate);
    unmount(); answer(true);
    expect(await pending).toBe(false); expect(navigate).not.toHaveBeenCalled();
  });
  it('preserves Next private history fields and restores only its own method wrappers', () => {
    window.history.replaceState({ __NA: true, tree: ['next-tree'] }, '', '/practices');
    const pushBefore = window.history.pushState; const replaceBefore = window.history.replaceState;
    const { unmount } = renderHook(() => useNavigationGuard(), { wrapper });
    act(() => { window.history.pushState({ __NA: true, tree: ['another-tree'] }, '', '/practices?practiceSetId=p1'); window.history.replaceState({ __NA: true, tree: ['replaced-tree'] }, '', '/practices?practiceSetId=p2'); });
    expect(window.history.state.__NA).toBe(true);
    expect(window.history.state.tree).toEqual(['replaced-tree']);
    const position = window.history.state.__zqkyNavigationPosition;
    expect(position).toBeGreaterThanOrEqual(1);
    unmount();
    expect(window.history.pushState).toBe(pushBefore); expect(window.history.replaceState).toBe(replaceBefore);
  });
});
