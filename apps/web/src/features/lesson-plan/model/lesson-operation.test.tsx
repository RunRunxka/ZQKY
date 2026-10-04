import { StrictMode } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/services/api-client';
import { stablePayloadKey, type FrozenSubmission } from '@/features/assessments/hooks';
import { browserOperationRecovery, useLessonOperation } from './useLessonOperation';
import { assertWriteSize, LEGACY_KEY } from './server-cache';
import { emptyData } from './defaults';
afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); });
describe('F30-L other logical operation author checks', () => {
  it('create/import/generate/apply/reject helper freezes complete first package and first metadata on unknown replay', async () => {
    const key = 'zhiqikeyuan:test:lesson-op', context = 'lesson|new|create'; const send = vi.fn().mockRejectedValueOnce(new ApiError('RESPONSE_LOST', '响应丢失', 0, true)).mockResolvedValueOnce({ id: 'created' }); const hook = renderHook(() => useLessonOperation<{ title: string; types: string[] }, { id: string }>(context, browserOperationRecovery(key)), { wrapper: StrictMode });
    await act(async () => { await hook.result.current.run({ title: '原输入2', types: ['review', 'new'] }, send, 2, 'original-load'); }); const original = JSON.parse(localStorage.getItem(key)!).operation as FrozenSubmission<unknown>; expect(hook.result.current.state).toBe('unknown');
    let receipt; await act(async () => { receipt = await hook.result.current.run({ title: '后来3', types: ['new', 'review'] }, send, 3, 'new-load'); }); expect(send.mock.calls[1]).toEqual(send.mock.calls[0]); expect(receipt).toMatchObject({ operation: original, result: { id: 'created' }, current: true }); expect(original.metadata).toEqual({ contextKey: context, originalEditGeneration: 2, loadGeneration: 'original-load' }); expect(localStorage.getItem(key)).toBeNull();
  });
  it('StrictMode recovers unknown metadata without automatic HTTP or overwriting the original operation', async () => {
    const key = 'zhiqikeyuan:test:lesson-op'; const payload = { proposalId: 'fixed-proposal', expectedRevision: 4, selectedFields: ['process'] }; const original = { operationId: 'original', submissionId: 'original', payloadKey: stablePayloadKey(payload), payload, metadata: { contextKey: 'lesson|a|apply', originalEditGeneration: 2, loadGeneration: 'old-load' } }; localStorage.setItem(key, JSON.stringify({ schemaVersion: 1, operation: original })); const send = vi.fn(); const hook = renderHook(() => useLessonOperation('lesson|a|apply', browserOperationRecovery(key)), { wrapper: StrictMode }); expect(hook.result.current.pending).toEqual(original); expect(send).not.toHaveBeenCalled(); expect(JSON.parse(localStorage.getItem(key)!).operation).toEqual(original);
  });
  it('malformed operation cache remains original and blocks all HTTP', async () => {
    const key = 'zhiqikeyuan:test:lesson-op'; localStorage.setItem(key, '{bad'); const send = vi.fn(); const hook = renderHook(() => useLessonOperation('lesson|a|reject', browserOperationRecovery(key))); await act(async () => { await hook.result.current.run({}, send, 0); }); expect(send).not.toHaveBeenCalled(); expect(localStorage.getItem(key)).toBe('{bad'); expect(hook.result.current.cacheError).toContain('读取失败');
  });
  it('cache write failure stops sends and exposes error without retrying as an empty operation', async () => {
    const storage = { getItem: () => null, setItem: () => { throw new Error('quota'); }, removeItem: vi.fn() } as unknown as Storage; const send = vi.fn(); const hook = renderHook(() => useLessonOperation('lesson|a|generate', browserOperationRecovery('test-only', storage))); await act(async () => { await hook.result.current.run({ modelProfileId: 'model' }, send, 1); }); await act(async () => { await hook.result.current.run({ modelProfileId: 'changed' }, send, 2); }); expect(send).not.toHaveBeenCalled(); expect(hook.result.current.cacheError).toContain('尚未发送HTTP');
  });
  it('2MiB UTF8 preflight refuses large whole content while keeping raw local bytes untouched', () => { const original = 'original raw draft'; localStorage.setItem(LEGACY_KEY, original); const process = Array.from({ length: 16 }, (_, index) => ({ id: `${index}`, stage: '课堂', design: '中'.repeat(50000), secondary: '' })); expect(() => assertWriteSize({ data: { ...emptyData, process } })).toThrow('2MiB'); expect(localStorage.getItem(LEGACY_KEY)).toBe(original); });
});
