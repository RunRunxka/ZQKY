/**
 * 集合写锁（H1-BOOKS-COMMIT-SAFETY v1；BOOKS-CS-FOLLOWUP v1 收敛）。
 *
 * 解决的问题：`localStorage` 没有 CAS，"读整表 → 改 → 写整表"在另一个标签页同时写入时
 * 会用旧快照覆盖对方已保存的内容；仅靠"写前检测 + 有界重试"覆盖不到
 * "检测之后、写入之前"的并发窗口。
 *
 * 方案：按集合键串行化的**互斥临界区**——
 * 1. **生产路径只认浏览器原生 Web Locks**（`navigator.locks`，exclusive）：真正的跨标签页互斥，
 *    锁随持有上下文销毁自动释放，不存在悬挂锁；
 * 2. 没有原生 Web Locks 时**不静默降级**：`withCollectionLock` 返回 `{ok:false, reason:'unavailable'}`，
 *    仓储据此如实返回 `unsupported`（"本次修改未保存"），读取与草稿不受影响。
 *    H1 批次的 `localStorage` 回退锁是启发式（取号 + settle + 读回校验，存在双入场窗口），
 *    已整体删除：宁可不写，也不留一条无法保证互斥的写入路径。
 * 3. 互斥由**可注入 provider**（`CollectionLockProvider`）提供：生产默认 Web Locks；
 *    单元测试经 `__setCollectionLockProviderForTests` 注入 in-process 互斥（同一 JS 环境内真实互斥，
 *    不产生第二套跨标签页协议），注入是否生效由返回值与 `__getCollectionLockProviderKindForTests` 可见。
 * 4. 同一标签页内所有请求经模块级队列串行化；临界区内的嵌套请求**入队延后**，不重入、不死锁；
 * 5. 调用方在临界区内完成"读快照 → 变更 → 写修订号 → 写数据 → 写后校验"（见 books-store 事务）。
 *
 * 如实边界：`withCollectionLock` 只保证"取得互斥后进入临界区"，不宣称强原子性——
 * 绕过本协议的写入者仍可能落在校验与写入之间的亚毫秒窗口，写后校验发现即报 conflict，不静默成功。
 */

export type CollectionLockKind = 'web-locks' | 'in-memory' | 'unavailable';

/**
 * 互斥 provider：`acquire` 在 `waitMs` 预算内取得锁则返回释放函数，未取得返回 null。
 * `kind === 'unavailable'` 表示当前环境**没有任何**可用的互斥设施（生产：无原生 Web Locks）——
 * 调用方必须按"不可写"处理，不得降级为无锁写入。
 */
export interface CollectionLockProvider {
  readonly kind: CollectionLockKind;
  acquire(lockName: string, waitMs: number): Promise<(() => void) | null>;
}

export type LockFailureReason = 'conflict' | 'unavailable';

export type LockOutcome<T> = { ok: true; value: T } | { ok: false; reason: LockFailureReason };

const DEFAULT_WAIT_MS = 1500;

/** 锁名（跨标签页协议：仅原生 Web Locks 使用；e2e 按同名查询 held/pending） */
export function collectionLockName(collectionKey: string): string {
  return `zqky-collection:${collectionKey}`;
}

// ===== 原生 Web Locks（生产默认 provider） =====

interface WebLockManagerLike {
  request(name: string, options: { mode: 'exclusive'; signal?: AbortSignal }, callback: () => unknown): Promise<unknown>;
}

function webLocks(): WebLockManagerLike | null {
  if (typeof navigator === 'undefined') return null;
  const candidate = (navigator as unknown as { locks?: WebLockManagerLike }).locks;
  return candidate && typeof candidate.request === 'function' ? candidate : null;
}

/**
 * 用原生 Web Locks 实现 acquire/release。预算耗尽时 abort 挂起的请求并按"未取得"返回；
 * 若恰好已被授予（W3C 规范：授予后 abort 被忽略），**立即释放**——宁可报告未取得，
 * 也绝不留下悬挂锁（临界区由调用方在 finally 中释放）。
 */
function acquireWebLock(lockName: string, waitMs: number): Promise<(() => void) | null> {
  const locks = webLocks();
  if (!locks) return Promise.resolve(null);
  return new Promise<(() => void) | null>((resolve) => {
    const controller = typeof AbortController === 'function' ? new AbortController() : null;
    let settled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const finish = (release: (() => void) | null): void => {
      if (settled) return;
      settled = true;
      if (timer !== null) clearTimeout(timer);
      resolve(release);
    };
    timer = setTimeout(() => {
      controller?.abort(); // 取消挂起的等待；已授予时被忽略
      finish(null);
    }, waitMs);
    void locks
      .request(
        lockName,
        controller ? { mode: 'exclusive', signal: controller.signal } : { mode: 'exclusive' },
        () =>
          new Promise<void>((releaseOwn) => {
            if (settled) {
              // 已对外报"未取得"：立即释放，绝不悬挂
              releaseOwn();
              return;
            }
            finish(() => releaseOwn());
          }),
      )
      .catch(() => finish(null)); // abort / 底层拒绝：按未取得处理，不留未处理拒绝
  });
}

/** 生产默认 provider：只认原生 Web Locks，缺失即 unavailable */
const webLocksProvider: CollectionLockProvider = {
  get kind(): CollectionLockKind {
    return webLocks() ? 'web-locks' : 'unavailable';
  },
  acquire: (lockName, waitMs) => acquireWebLock(lockName, waitMs),
};

// ===== in-process 互斥（单元测试注入用；同一 JS 环境内真实互斥） =====

/**
 * 进程内 FIFO 互斥 provider：按锁名排队，`waitMs` 预算内未轮到则返回 null。
 * 供 jsdom 单测注入（`__setCollectionLockProviderForTests`），**不是**生产路径：
 * 它只覆盖同一 JS 环境，不声称跨标签页互斥。
 */
export function createInMemoryCollectionLockProvider(): CollectionLockProvider {
  const queues = new Map<string, Promise<void>>();
  return {
    kind: 'in-memory',
    acquire(lockName, waitMs) {
      return new Promise<(() => void) | null>((resolve) => {
        const previous = queues.get(lockName) ?? Promise.resolve();
        let releaseNext: () => void = () => {};
        const slot = new Promise<void>((next) => {
          releaseNext = next;
        });
        // 同步登记：后续请求排在本请求之后（不依赖微任务顺序，避免"同时取得"）
        queues.set(lockName, slot);
        void slot.then(() => {
          if (queues.get(lockName) === slot) queues.delete(lockName);
        });
        let done = false;
        const timer = setTimeout(() => {
          if (done) return;
          done = true;
          resolve(null); // 预算耗尽：未取得（槽位由下面让出，不堵住队列）
        }, waitMs);
        void previous.then(() => {
          if (done) {
            releaseNext();
            return;
          }
          done = true;
          clearTimeout(timer);
          resolve(() => releaseNext());
        });
      });
    },
  };
}

// ===== provider 注入（测试） =====

let providerOverride: CollectionLockProvider | null = null;

/**
 * 测试注入 provider。返回**是否真的生效**（false 表示参数不合法、注入被忽略）——
 * 调用方必须检查它，注入失败时测试应失败而不是静默放行。
 */
export function __setCollectionLockProviderForTests(provider: CollectionLockProvider | null): boolean {
  if (provider === null) {
    providerOverride = null;
    return true;
  }
  const valid =
    (provider.kind === 'web-locks' || provider.kind === 'in-memory' || provider.kind === 'unavailable') &&
    typeof provider.acquire === 'function';
  if (!valid) return false;
  providerOverride = provider;
  return providerOverride === provider;
}

/** 当前实际生效的 provider 类型（测试断言"注入未生效"用） */
export function __getCollectionLockProviderKindForTests(): CollectionLockKind {
  return (providerOverride ?? webLocksProvider).kind;
}

// ===== 同标签页串行队列（避免重入与死锁） =====

/** 每个集合键一条 Promise 链：同标签页写请求依次执行，临界区内的嵌套请求排在后面 */
const tabQueues = new Map<string, Promise<unknown>>();

function enqueue<T>(collectionKey: string, run: () => Promise<T>): Promise<T> {
  const key = typeof window === 'undefined' ? '\u0000server' : collectionKey;
  const previous = tabQueues.get(key) ?? Promise.resolve();
  // 前一个任务无论成功或失败都继续执行下一个（否则一次失败会永久堵住队列）
  const next = previous.then(run, run);
  tabQueues.set(key, next);
  return next;
}

/** 仅测试使用：清空同标签页队列状态并撤销 provider 注入（不触碰任何持久化数据） */
export function __resetCollectionLockQueuesForTests(): void {
  tabQueues.clear();
  providerOverride = null;
}

// ===== 对外入口 =====

/**
 * 在集合互斥临界区内执行 `run`。同标签页请求自动串行；跨标签页由原生 Web Locks 互斥。
 * - 未取得锁（预算内未收敛）返回 `{ok:false, reason:'conflict'}`；
 * - 当前环境无可用互斥（无原生 Web Locks 且无测试注入）返回 `{ok:false, reason:'unavailable'}`，
 *   调用方必须按"不可写"处理（**绝不**降级为无锁写入）；
 * - `run` 自身抛出的异常原样抛出（参数校验等语义不因加锁改变），锁在 finally 中释放。
 */
export function withCollectionLock<T>(
  collectionKey: string,
  run: () => Promise<T> | T,
): Promise<LockOutcome<T>> {
  const provider = providerOverride ?? webLocksProvider;
  if (provider.kind === 'unavailable') {
    // 无互斥保障：不进入临界区、不写任何数据（对调用方是明确的"本次修改未保存"）
    return Promise.resolve({ ok: false, reason: 'unavailable' } satisfies LockOutcome<T>);
  }
  return enqueue(collectionKey, async () => {
    let release: (() => void) | null;
    try {
      release = await provider.acquire(collectionLockName(collectionKey), DEFAULT_WAIT_MS);
    } catch {
      // 取锁设施自身异常：按冲突处理（保守，不静默放行）
      return { ok: false, reason: 'conflict' } satisfies LockOutcome<T>;
    }
    if (!release) return { ok: false, reason: 'conflict' } satisfies LockOutcome<T>;
    try {
      return { ok: true, value: await run() } satisfies LockOutcome<T>;
    } finally {
      release();
    }
  });
}
