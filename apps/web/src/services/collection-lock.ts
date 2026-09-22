/**
 * 集合写锁（H1-BOOKS-COMMIT-SAFETY v1）。
 *
 * 解决的问题：`localStorage` 没有 CAS，"读整表 → 改 → 写整表"在另一个标签页同时写入时
 * 会用旧快照覆盖对方已保存的内容；仅靠"写前检测 + 有界重试"覆盖不到
 * "检测之后、写入之前"的并发窗口（H1-BOOKS-HARDEN v1 的写标记协议即止步于此）。
 *
 * 方案：按集合键串行化的**互斥临界区**——
 * 1. 主路径用浏览器原生 Web Locks（`navigator.locks`，exclusive）：真正的跨标签页互斥，
 *    锁随持有上下文销毁自动释放，不存在悬挂锁；
 * 2. 回退路径（jsdom/无 Web Locks 环境）用 `localStorage` 锁记录 {owner, nonce, ticket, acquiredAt}：
 *    取号写入 → 等一个 settle 窗口 → 读回校验；未通过即视为未取得（后写者胜，先写者在下一次
 *    校验发现自己被取代），退避重试直到等待预算耗尽；
 * 3. 同一标签页内所有请求经模块级队列串行化；临界区内的嵌套请求**入队延后**，不重入、不死锁；
 * 4. 调用方在临界区内完成"读快照 → 变更 → 写修订号 → 写数据 → 写后校验"（见 books-store 事务）。
 *
 * 如实边界：回退路径不是硬件级互斥（无 CAS），它把竞争窗口压到一个 settle 窗口并在写后校验；
 * 未通过校验者绝不报告成功。配合写后读回校验，本模块保证"报告成功的写入不会被协议内旧快照覆盖"。
 */

export interface CollectionLockOptions {
  /** 取得锁的等待预算（毫秒）；耗尽即视为 conflict */
  waitMs?: number;
  /** 回退路径：锁记录被视为失效的时长（毫秒） */
  staleMs?: number;
  /** 回退路径：取号后等待多久再读回校验（毫秒） */
  settleMs?: number;
}

export type LockFailureReason = 'conflict' | 'unavailable';

export type LockOutcome<T> = { ok: true; value: T } | { ok: false; reason: LockFailureReason };

const DEFAULT_WAIT_MS = 1500;
const DEFAULT_STALE_MS = 4000;
const DEFAULT_SETTLE_MS = 24;
const BACKOFF_START_MS = 6;
const BACKOFF_CAP_MS = 80;

interface LockRecord {
  owner: string;
  nonce: string;
  ticket: number;
  acquiredAt: number;
}

function tabOwnerId(): string {
  if (typeof window === 'undefined') return 'server';
  try {
    const existing = window.sessionStorage.getItem('zhiqikeyuan:lock-owner');
    if (existing) return existing;
    const created = `lock-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    window.sessionStorage.setItem('zhiqikeyuan:lock-owner', created);
    return created;
  } catch {
    return 'no-session';
  }
}

function lockRecordKey(collectionKey: string): string {
  return `${collectionKey}-lock`;
}

function readLockRecord(collectionKey: string): LockRecord | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(lockRecordKey(collectionKey));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<LockRecord>;
    if (
      typeof parsed.owner !== 'string' ||
      typeof parsed.nonce !== 'string' ||
      typeof parsed.ticket !== 'number' ||
      typeof parsed.acquiredAt !== 'number'
    ) {
      return null;
    }
    return {
      owner: parsed.owner,
      nonce: parsed.nonce,
      ticket: parsed.ticket,
      acquiredAt: parsed.acquiredAt,
    };
  } catch {
    return null;
  }
}

function writeLockRecord(collectionKey: string, record: LockRecord): boolean {
  if (typeof window === 'undefined') return false;
  try {
    window.localStorage.setItem(lockRecordKey(collectionKey), JSON.stringify(record));
    return true;
  } catch {
    return false;
  }
}

/** 只清自己的锁记录；别人的记录保持原样（避免释放他人的临界区） */
function removeLockRecord(collectionKey: string, owner: string, nonce: string): void {
  if (typeof window === 'undefined') return;
  const current = readLockRecord(collectionKey);
  if (current && (current.owner !== owner || current.nonce !== nonce)) return;
  try {
    window.localStorage.removeItem(lockRecordKey(collectionKey));
  } catch {
    // 忽略清理失败
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
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

/** 仅测试使用：清空同标签页队列状态（不触碰其它标签页的锁记录） */
export function __resetCollectionLockQueuesForTests(): void {
  tabQueues.clear();
  if (optionsOverride !== null) optionsOverride = null;
}

/** 仅测试使用：缩短等待预算/settle，便于确定性地构造"锁被占"与"锁释放后可写" */
export function __setCollectionLockOptionsForTests(
  options: CollectionLockOptions | null,
): void {
  optionsOverride = options;
}

let optionsOverride: CollectionLockOptions | null = null;

/** 仅测试/诊断使用：读当前锁记录（不修改） */
export function peekCollectionLock(
  collectionKey: string,
): { owner: string; ticket: number; ageMs: number } | null {
  const record = readLockRecord(collectionKey);
  if (!record) return null;
  return { owner: record.owner, ticket: record.ticket, ageMs: Date.now() - record.acquiredAt };
}

// ===== Web Locks 主路径 =====

interface WebLockManagerLike {
  request(name: string, options: { mode: 'exclusive'; signal?: AbortSignal }, callback: () => unknown): Promise<unknown>;
}

function webLocks(): WebLockManagerLike | null {
  if (typeof navigator === 'undefined') return null;
  const candidate = (navigator as unknown as { locks?: WebLockManagerLike }).locks;
  return candidate && typeof candidate.request === 'function' ? candidate : null;
}

/**
 * 在原生 Web Locks 下执行临界区：等待预算由 AbortSignal 控制，超时视为 conflict。
 * `run` 自身抛出的异常照常抛出（例如参数校验错误），不会被误报为冲突。
 */
async function runWithWebLock<T>(
  collectionKey: string,
  run: () => Promise<T>,
  waitMs: number,
): Promise<LockOutcome<T> | { ok: 'run-error'; cause: unknown }> {
  const locks = webLocks();
  if (!locks) return { ok: false, reason: 'unavailable' };
  const hasAbort = typeof AbortController === 'function';
  const controller = hasAbort ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), waitMs) : null;
  try {
    const outcome = (await locks.request(
      `zqky-collection:${collectionKey}`,
      controller ? { mode: 'exclusive', signal: controller.signal } : { mode: 'exclusive' },
      async () => {
        try {
          return { ok: true as const, value: await run() };
        } catch (cause) {
          return { ok: false as const, cause };
        }
      },
    )) as { ok: true; value: T } | { ok: false; cause: unknown };
    if (outcome.ok) return { ok: true, value: outcome.value };
    return { ok: 'run-error', cause: outcome.cause };
  } catch {
    // 预算耗尽（abort）或底层拒绝：按冲突处理
    return { ok: false, reason: 'conflict' };
  } finally {
    if (timer !== null) clearTimeout(timer);
  }
}

// ===== localStorage 回退路径 =====

async function tryAcquireFallbackLock(
  collectionKey: string,
  settleMs: number,
  staleMs: number,
): Promise<(() => void) | null> {
  const owner = tabOwnerId();
  const nonce = `n-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  const current = readLockRecord(collectionKey);
  const now = Date.now();
  if (current && current.owner !== owner && now - current.acquiredAt < staleMs) return null;
  const ticket = (current?.ticket ?? 0) + 1;
  if (!writeLockRecord(collectionKey, { owner, nonce, ticket, acquiredAt: Date.now() })) return null;
  // settle：让可能同时在取号的另一标签页把记录写出来，再读回确认自己仍是持有者
  await sleep(settleMs);
  const back = readLockRecord(collectionKey);
  if (!back || back.owner !== owner || back.nonce !== nonce || back.ticket !== ticket) return null;
  return () => removeLockRecord(collectionKey, owner, nonce);
}

async function runWithFallbackLock<T>(
  collectionKey: string,
  run: () => Promise<T>,
  waitMs: number,
  settleMs: number,
  staleMs: number,
): Promise<LockOutcome<T>> {
  const deadline = Date.now() + waitMs;
  let backoff = BACKOFF_START_MS;
  for (;;) {
    const release = await tryAcquireFallbackLock(collectionKey, settleMs, staleMs);
    if (release) {
      try {
        return { ok: true, value: await run() };
      } finally {
        release();
      }
    }
    if (Date.now() >= deadline) return { ok: false, reason: 'conflict' };
    await sleep(backoff + Math.random() * backoff);
    backoff = Math.min(backoff * 2, BACKOFF_CAP_MS);
  }
}

// ===== 对外入口 =====

/**
 * 在集合互斥临界区内执行 `run`。同标签页请求自动串行；跨标签页由 Web Locks/回退锁互斥。
 * 未取得锁（预算内未收敛）返回 `{ok:false, reason}`，调用方必须按冲突处理（不得当作成功）。
 * `run` 自身抛出的异常原样抛出（参数校验等语义不因加锁改变）。
 */
export function withCollectionLock<T>(
  collectionKey: string,
  run: () => Promise<T> | T,
  options?: CollectionLockOptions,
): Promise<LockOutcome<T>> {
  const effective = { ...optionsOverride, ...options };
  const waitMs = effective.waitMs ?? DEFAULT_WAIT_MS;
  const settleMs = effective.settleMs ?? DEFAULT_SETTLE_MS;
  const staleMs = effective.staleMs ?? DEFAULT_STALE_MS;
  return enqueue(collectionKey, async () => {
    const primary = await runWithWebLock(collectionKey, () => Promise.resolve(run()), waitMs);
    if (primary.ok === true) return primary;
    if (primary.ok === 'run-error') throw primary.cause;
    if (primary.reason === 'conflict') return primary; // 原生锁超时：不再叠加长等待
    return runWithFallbackLock(collectionKey, () => Promise.resolve(run()), waitMs, settleMs, staleMs);
  });
}
