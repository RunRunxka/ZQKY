/**
 * `/assessments/**` 的数据原语单测（R5-FE 2026-10-11）。
 *
 * 只测会被页面直接依赖的两条硬约束：
 * 1. `useAsyncResource` 的三态显式——读取失败**不能**被当成空数据，且同一 key 刷新失败时
 *    继续保留上一次成功数据（切 key 时立刻丢弃，避免把别的班级/试卷的数据当成本次的）；
 * 2. `useFrozenSubmission` 的幂等——结果未知（拿不到响应）后重试必须复用同一 `submissionId`
 *    与原样载荷；在途重复点击不产生第二个请求；明确失败后换载荷才是新的逻辑确认。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { ApiError } from '@/services/api-client';
import { asApiError, stablePayloadKey, useAsyncResource, useFrozenSubmission } from './hooks';

beforeEach(() => {
  vi.useRealTimers();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('useAsyncResource：三态与 lastData', () => {
  it('成功给出 ready + lastData', async () => {
    const load = vi.fn(async () => ({ items: ['a'], total: 1 }));
    const { result } = renderHook(() => useAsyncResource(load, 'k1'));
    expect(result.current.state.phase).toBe('loading');
    await waitFor(() => expect(result.current.state.phase).toBe('ready'));
    expect(result.current.lastData).toEqual({ items: ['a'], total: 1 });
  });

  it('失败是 failed（带 code），不是空数据；lastData 保持 null', async () => {
    const load = vi.fn(async () => {
      throw new ApiError('SERVICE_UNAVAILABLE', '后端服务未运行或无法连接。', 0, true);
    });
    const { result } = renderHook(() => useAsyncResource(load, 'k1'));
    await waitFor(() => expect(result.current.state.phase).toBe('failed'));
    expect(result.current.state.phase === 'failed' && result.current.state.error.code).toBe(
      'SERVICE_UNAVAILABLE',
    );
    expect(result.current.lastData).toBeNull();
  });

  it('同一 key 刷新失败：state 变 failed，lastData 仍保留上一次成功数据', async () => {
    let calls = 0;
    const load = vi.fn(async () => {
      calls += 1;
      if (calls > 1) throw new ApiError('SERVICE_UNAVAILABLE', '断线', 0, true);
      return { items: ['第一页'], total: 1 };
    });
    const { result } = renderHook(() => useAsyncResource(load, 'k1'));
    await waitFor(() => expect(result.current.state.phase).toBe('ready'));
    result.current.reload();
    await waitFor(() => expect(result.current.state.phase).toBe('failed'));
    expect(result.current.lastData).toEqual({ items: ['第一页'], total: 1 });
  });

  it('切 key 立即丢弃上一次数据（不能把别的班级/试卷的数据当本次的）', async () => {
    const load = vi.fn(async (signal: AbortSignal) => ({
      items: [signal.aborted ? 'aborted' : 'x'],
      total: 1,
    }));
    const { result, rerender } = renderHook(
      ({ key }: { key: string }) => useAsyncResource(load, key),
      { initialProps: { key: 'class-a' } },
    );
    await waitFor(() => expect(result.current.state.phase).toBe('ready'));
    rerender({ key: 'class-b' });
    expect(result.current.lastData).toBeNull();
  });
});

describe('useFrozenSubmission：结果未知后的重试复用同一 submissionId', () => {
  type Payload = { expectedRevision: number; note: string };
  type Result = { ok: true };

  it('在途重复点击不产生第二个请求', async () => {
    let release: (value: Result) => void = () => {};
    const run = vi.fn(
      () =>
        new Promise<Result>((resolve) => {
          release = resolve;
        }),
    );
    const { result } = renderHook(() => useFrozenSubmission<Payload, Result>());
    const payload: Payload = { expectedRevision: 1, note: 'a' };
    let first: Promise<Result | null> = Promise.resolve(null);
    await act(async () => {
      first = result.current.submit(payload, run);
    });
    // 在途：同一载荷的第二次点击不发第二个请求
    let second: Result | null = { ok: true };
    await act(async () => {
      second = await result.current.submit(payload, run);
    });
    expect(second).toBeNull();
    await act(async () => {
      release({ ok: true });
      await first;
    });
    expect(run).toHaveBeenCalledTimes(1);
    expect(result.current.phase).toBe('succeeded');
    // 成功后自动释放冻结：同一载荷再提交是新的一次逻辑确认
    expect(result.current.frozen).toBeNull();
  });

  it('status 0（拿不到响应）→ unknown，重试复用同 submissionId 与原样载荷', async () => {
    const seen: { submissionId: string; payload: Payload }[] = [];
    const run = vi.fn(async (frozen: { submissionId: string; payload: Payload }) => {
      seen.push({ submissionId: frozen.submissionId, payload: frozen.payload });
      if (seen.length === 1) {
        throw new ApiError('SERVICE_UNAVAILABLE', '后端服务未运行或无法连接。', 0, true);
      }
      return { ok: true } as Result;
    });
    const { result } = renderHook(() => useFrozenSubmission<Payload, Result>());
    const payload: Payload = { expectedRevision: 7, note: 'q' };
    expect(await result.current.submit(payload, run)).toBeNull();
    await waitFor(() => expect(result.current.phase).toBe('unknown'));
    expect(result.current.unknownNotice).toContain('同一个提交标识');

    // 重试：载荷与标识都必须与第一次一致（幂等），并且确实成功
    const retry = await result.current.submit(payload, run);
    expect(retry).toEqual({ ok: true });
    expect(seen).toHaveLength(2);
    expect(seen[1].submissionId).toBe(seen[0].submissionId);
    expect(seen[1].payload).toEqual(payload);
  });

  it('明确失败（4xx）记录错误，载荷变化后是新标识', async () => {
    const ids: string[] = [];
    const run = vi.fn(async (frozen: { submissionId: string; payload: Payload }) => {
      ids.push(frozen.submissionId);
      throw new ApiError('ROSTER_IMPORT_BLOCKING_ISSUES', '还有未解决的行', 409, false);
    });
    const { result } = renderHook(() => useFrozenSubmission<Payload, Result>());
    expect(await result.current.submit({ expectedRevision: 1, note: 'a' }, run)).toBeNull();
    await waitFor(() => expect(result.current.phase).toBe('failed'));
    expect(result.current.error?.code).toBe('ROSTER_IMPORT_BLOCKING_ISSUES');
    expect(await result.current.submit({ expectedRevision: 1, note: 'b' }, run)).toBeNull();
    expect(ids).toHaveLength(2);
    expect(ids[1]).not.toBe(ids[0]);
  });

  it('asApiError 归一未知异常，stablePayloadKey 与字段顺序无关', () => {
    expect(asApiError(new Error('炸了')).code).toBe('UNEXPECTED_ERROR');
    expect(asApiError(new ApiError('X', 'x', 400, false)).code).toBe('X');
    expect(stablePayloadKey({ a: 1, b: [2, 3] })).toBe(stablePayloadKey({ b: [2, 3], a: 1 }));
    // undefined 字段与缺失等价（口径与归档一致）
    expect(stablePayloadKey({ a: 1, b: undefined })).toBe(stablePayloadKey({ a: 1 }));
  });
});
