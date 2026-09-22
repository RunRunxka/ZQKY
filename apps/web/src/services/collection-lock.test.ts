import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  __getCollectionLockProviderKindForTests,
  __resetCollectionLockQueuesForTests,
  __setCollectionLockProviderForTests,
  collectionLockName,
  createInMemoryCollectionLockProvider,
  withCollectionLock,
  type CollectionLockProvider,
} from './collection-lock';

/**
 * BOOKS-CS-FOLLOWUP v1：集合锁设施自身的契约回归（A1 挑刺 F3）。
 *
 * 生产路径只认原生 Web Locks；没有它时 `withCollectionLock` 返回 `unavailable`，绝不走
 * localStorage 回退锁（旧的启发式取号 + settle，存在双入场窗口，已整体删除）。
 * 单元测试的互斥一律经 `__setCollectionLockProviderForTests` **显式注入**，注入是否生效可见。
 */

const KEY = 'zhiqikeyuan:probe-collection';
const LOCK_KEY = `${KEY}-lock`;

beforeEach(() => {
  window.localStorage.clear();
  __resetCollectionLockQueuesForTests();
});

afterEach(() => {
  __resetCollectionLockQueuesForTests();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('集合锁 provider 契约（无 Web Locks 不静默降级）', () => {
  it('jsdom 没有原生 Web Locks：默认 provider = unavailable，返回未取得且不写任何锁记录', async () => {
    expect(typeof navigator).not.toBe('undefined');
    expect((navigator as unknown as { locks?: unknown }).locks).toBeUndefined();
    // 默认（未注入）时如实报告"无可用互斥"——不存在隐式的 in-process 降级
    expect(__getCollectionLockProviderKindForTests()).toBe('unavailable');

    let ran = false;
    const outcome = await withCollectionLock(KEY, () => {
      ran = true;
      return 'x';
    });

    expect(outcome).toEqual({ ok: false, reason: 'unavailable' });
    expect(ran).toBe(false); // 没有互斥保障就不进入临界区（宁可不写，也不裸写）
    expect(window.localStorage.getItem(LOCK_KEY)).toBeNull();
    expect(window.localStorage.length).toBe(0); // 回退锁已删除：锁设施不写 localStorage
  });

  it('注入是否生效可见：非法 provider 被拒，不改变当前实现', () => {
    const bogus = { kind: 'nonsense', acquire: null } as unknown as CollectionLockProvider;
    expect(__setCollectionLockProviderForTests(bogus)).toBe(false);
    expect(__getCollectionLockProviderKindForTests()).toBe('unavailable'); // 未被非法注入替换

    const missingAcquire = { kind: 'in-memory' } as unknown as CollectionLockProvider;
    expect(__setCollectionLockProviderForTests(missingAcquire)).toBe(false);
    expect(__getCollectionLockProviderKindForTests()).toBe('unavailable');

    expect(__setCollectionLockProviderForTests(createInMemoryCollectionLockProvider())).toBe(true);
    expect(__getCollectionLockProviderKindForTests()).toBe('in-memory');
    expect(__setCollectionLockProviderForTests(null)).toBe(true);
    expect(__getCollectionLockProviderKindForTests()).toBe('unavailable');
  });

  it('in-process 互斥：持有时他人拿不到；预算耗尽返回未取得；释放后队列继续', async () => {
    const provider = createInMemoryCollectionLockProvider();
    const name = collectionLockName(KEY);

    const first = await provider.acquire(name, 100);
    expect(first).not.toBeNull();
    // 第一个仍持有时，第二个在预算内拿不到（真实互斥，不是"都拿到"）
    expect(await provider.acquire(name, 10)).toBeNull();

    first!();
    const second = await provider.acquire(name, 100);
    expect(second).not.toBeNull();
    second!();
  });

  it('同标签页请求串行：临界区不重叠、顺序保持', async () => {
    expect(__setCollectionLockProviderForTests(createInMemoryCollectionLockProvider())).toBe(true);
    const order: string[] = [];
    let inside = 0;
    const task = (label: string, ms: number) =>
      withCollectionLock(KEY, async () => {
        inside += 1;
        expect(inside).toBe(1); // 串行：临界区内不会出现第二个请求
        order.push(`${label}:start`);
        await new Promise((resolve) => setTimeout(resolve, ms));
        order.push(`${label}:end`);
        inside -= 1;
      });

    const outcomes = await Promise.all([task('a', 20), task('b', 0), task('c', 0)]);

    expect(outcomes.every((outcome) => outcome.ok)).toBe(true);
    expect(order).toEqual(['a:start', 'a:end', 'b:start', 'b:end', 'c:start', 'c:end']);
  });

  it('临界区内抛出原样上抛，且锁在 finally 中释放（不会堵死后续请求）', async () => {
    expect(__setCollectionLockProviderForTests(createInMemoryCollectionLockProvider())).toBe(true);

    await expect(
      withCollectionLock(KEY, () => {
        throw new Error('参数校验失败');
      }),
    ).rejects.toThrow('参数校验失败');

    const after = await withCollectionLock(KEY, () => 'ok');
    expect(after).toEqual({ ok: true, value: 'ok' });
  });

  it('取锁设施自身异常按冲突处理（保守：不静默放行、不进入临界区）', async () => {
    expect(
      __setCollectionLockProviderForTests({
        kind: 'in-memory',
        acquire: () => Promise.reject(new Error('acquire exploded')),
      }),
    ).toBe(true);

    let ran = false;
    const outcome = await withCollectionLock(KEY, () => {
      ran = true;
      return 'x';
    });
    expect(outcome).toEqual({ ok: false, reason: 'conflict' });
    expect(ran).toBe(false);
  });

  it('撤销注入（null）后回到生产语义：无 Web Locks 即 unavailable，且不写任何本地键', async () => {
    expect(__setCollectionLockProviderForTests(createInMemoryCollectionLockProvider())).toBe(true);
    expect(__getCollectionLockProviderKindForTests()).toBe('in-memory');
    expect(await withCollectionLock(KEY, () => 42)).toEqual({ ok: true, value: 42 });
    expect(window.localStorage.getItem(LOCK_KEY)).toBeNull();

    // H1 批次的 localStorage 回退锁已删除：撤销注入后 jsdom 就是"无可用互斥"（不降级写入）
    expect(__setCollectionLockProviderForTests(null)).toBe(true);
    expect(__getCollectionLockProviderKindForTests()).toBe('unavailable');
    expect(await withCollectionLock(KEY, () => 42)).toEqual({ ok: false, reason: 'unavailable' });
    expect(window.localStorage.getItem(LOCK_KEY)).toBeNull();
  });
});
