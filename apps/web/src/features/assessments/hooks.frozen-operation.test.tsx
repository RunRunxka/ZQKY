import { StrictMode, type ReactNode } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/services/api-client';
import { useFrozenSubmission, type FrozenSubmission } from './hooks';

afterEach(() => cleanup());
const metadata = { contextKey: 'practice:p1', originalEditGeneration: 2, loadGeneration: 'mount-1' };
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; };

describe('original submission acknowledgement', () => {
  it('captures the first edit generation and payload before the initial response', async () => {
    const { result } = renderHook(() => useFrozenSubmission<{ score: number }, number>());
    const response = deferred<number>();
    const body = { score: 2 };
    let waiting!: ReturnType<typeof result.current.submitWithReceipt>;
    act(() => { waiting = result.current.submitWithReceipt(body, () => response.promise, metadata); });
    body.score = 3;
    const first = result.current.frozen!;
    expect(first.payload).toEqual({ score: 2 });
    expect(first.metadata).toEqual(metadata);
    expect(first.operationId).toBe(first.submissionId);
    let receipt!: Awaited<typeof waiting>;
    await act(async () => { response.resolve(4); receipt = await waiting; });
    expect(receipt).toEqual({ result: 4, operation: first, current: true });
    expect(receipt!.operation.metadata!.originalEditGeneration).toBe(2);
  });

  it('replays the same ID, payload and first metadata after the caller edits again', async () => {
    const { result } = renderHook(() => useFrozenSubmission<{ text: string }, number>());
    const wire: FrozenSubmission<{ text: string }>[] = [];
    const run = vi.fn(async (operation: FrozenSubmission<{ text: string }>) => { wire.push(operation); if (wire.length === 1) throw new ApiError('NETWORK_ERROR', 'lost', 0, true); return 4; });
    await act(async () => { await result.current.submitWithReceipt({ text: 'A' }, run, metadata); });
    expect(result.current.phase).toBe('unknown');
    let receipt!: Awaited<ReturnType<typeof result.current.submitWithReceipt>>;
    await act(async () => { receipt = await result.current.submitWithReceipt({ text: 'B' }, run, { ...metadata, originalEditGeneration: 3 }); });
    expect(wire).toHaveLength(2);
    expect(wire[1]).toBe(wire[0]);
    expect(receipt!.operation.payload.text).toBe('A');
    expect(receipt!.operation.metadata).toEqual(metadata);
  });

  it('does not replay another document operation into a new context', async () => {
    const { result } = renderHook(() => useFrozenSubmission<{ score: number }, number>());
    await act(async () => { await result.current.submitWithReceipt({ score: 2 }, async () => { throw new ApiError('NETWORK_ERROR', 'lost', 0, true); }, metadata); });
    const run = vi.fn(async () => 4);
    await act(async () => { expect(await result.current.submitWithReceipt({ score: 3 }, run, { ...metadata, contextKey: 'practice:p2' })).toBeNull(); });
    expect(run).not.toHaveBeenCalled();
    expect(result.current.error?.code).toBe('SUBMISSION_CONTEXT_MISMATCH');
    expect(result.current.frozen?.payload.score).toBe(2);
  });

  it('deduplicates pending clicks and marks a released late receipt as obsolete', async () => {
    const { result } = renderHook(() => useFrozenSubmission<{ score: number }, number>());
    const response = deferred<number>();
    const run = vi.fn(() => response.promise);
    let waiting!: ReturnType<typeof result.current.submitWithReceipt>;
    act(() => { waiting = result.current.submitWithReceipt({ score: 2 }, run, metadata); });
    await act(async () => { expect(await result.current.submitWithReceipt({ score: 3 }, run, metadata)).toBeNull(); });
    act(() => result.current.release());
    let receipt!: Awaited<typeof waiting>;
    await act(async () => { response.resolve(4); receipt = await waiting; });
    expect(run).toHaveBeenCalledTimes(1);
    expect(receipt?.current).toBe(false);
    expect(result.current.phase).toBe('idle');
    expect(result.current.result).toBeNull();
  });

  it('restores the original operation without automatically sending, including duplicate StrictMode setup', async () => {
    const initial = renderHook(() => useFrozenSubmission<{ score: number }, number>());
    await act(async () => { await initial.result.current.submitWithReceipt({ score: 2 }, async () => { throw new ApiError('NETWORK_ERROR', 'lost', 0, true); }, metadata); });
    const operation = structuredClone(initial.result.current.frozen!);
    initial.unmount();
    const wrapper = ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode>;
    const { result } = renderHook(() => useFrozenSubmission<{ score: number }, number>(), { wrapper });
    act(() => { expect(result.current.recoverFrozen(operation)).toBe(true); expect(result.current.recoverFrozen(operation)).toBe(true); });
    expect(result.current.phase).toBe('unknown');
    const run = vi.fn(async () => 4);
    expect(run).not.toHaveBeenCalled();
    let receipt!: Awaited<ReturnType<typeof result.current.submitWithReceipt>>;
    await act(async () => { receipt = await result.current.submitWithReceipt({ score: 3 }, run, { ...metadata, loadGeneration: 'mount-2', originalEditGeneration: 3 }); });
    expect(run).toHaveBeenCalledTimes(1);
    expect(receipt!.operation.submissionId).toBe(operation.submissionId);
    expect(receipt!.operation.metadata!.loadGeneration).toBe('mount-1');
    expect(receipt!.operation.payload.score).toBe(2);
  });

  it('rejects recovery whose payload differs from its recorded hash', () => {
    const { result } = renderHook(() => useFrozenSubmission<{ score: number }, number>());
    act(() => { expect(result.current.recoverFrozen({ operationId: 's1', submissionId: 's1', payloadKey: '{"score":2}', payload: { score: 3 }, metadata })).toBe(false); });
    expect(result.current.phase).toBe('idle');
  });

  it('refuses to replace an existing original generation or load identity during recovery', async () => {
    const { result } = renderHook(() => useFrozenSubmission<{ score: number }, number>());
    await act(async () => { await result.current.submitWithReceipt({ score: 2 }, async () => { throw new ApiError('NETWORK_ERROR', 'lost', 0, true); }, metadata); });
    const first = result.current.frozen!;
    for (const changed of [{ ...metadata, originalEditGeneration: 3 }, { ...metadata, loadGeneration: 'mount-2' }, { ...metadata, contextKey: 'practice:p2' }]) {
      act(() => { expect(result.current.recoverFrozen({ ...first, metadata: changed })).toBe(false); });
      expect(result.current.frozen).toBe(first);
    }
    act(() => { expect(result.current.recoverFrozen(structuredClone(first))).toBe(true); });
    expect(result.current.frozen).toBe(first);
  });
});
