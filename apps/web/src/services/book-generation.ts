/**
 * 模拟书籍生成执行器（H1-BOOKS-PIPELINE v2，任务卡 §4.4）。
 *
 * 定位：模块级单例注册表 + 每书租约，驱动 compiling 书籍"逐页逐块"的显式模拟流水线。
 * 不接真实 LLM：所有"生成"均为本地确定性模板（与 books-store 的 simulateBlocks 同源），
 * 失败/暂停场景全部为显式模拟注入。换真实服务时只替换本执行器，仓储（applyRunEvent）不变。
 *
 * 关键语义（对照参考 deeptutor/book/engine.py 与任务卡）：
 * - 正常路径必须由事件推进（pending→generating→ready 逐块落库），禁止先同步生成整本再播放假进度。
 * - 块级 200ms 合并写盘；页完成/暂停/失败/结束/pagehide 立即 flush；seq 落库时按最新记录现取
 *   （队列写盘与即时重试共用同一单调序号空间，见 applyStored）。
 * - stop() 后迟到回调必须被 bookId+runId 校验丢弃（AbortSignal 语义）。
 * - 连续 2 页失败触发 provider 暂停（CONSECUTIVE_PAGE_FAILURE_LIMIT，engine.py:105）；
 *   provider 暂停为"模拟供应商连续失败"，绝不可表述为真实上游故障。
 * - 注入场景在解析时展开通配（`'*first'` → 全书第一个块），UI 开关必须真的命中；
 *   块失败与整页失败都是**一次性**注入（重试/恢复/刷新续跑即成功，不会卡在同一触发点）。
 * - storageFailureAt 触发的写入失败必须走 local-collection 的真实抛错路径并落到 error（kind storage），
 *   不得谎报"已保存"；同一 run 只注入一次（重试即成功）。
 * - 租约：zhiqikeyuan:book-lease:<bookId>（ownerId 存 sessionStorage，心跳 1s，>3s 失效）。
 *   他标签页持活租约时本标签不得启动第二个执行器。
 * - 自动续跑：compiling 且无活跃执行器且租约可用（mine 或失效）时可续跑（按页状态续，
 *   见 drive）；paused 无论何种情况都不自动续跑（对照 maybe_resume_on_open 的显式不做）。
 *   续跑时机由界面在"打开书籍/刷新"处触发一次，不在每次状态变化时自动重启——
 *   否则一次页失败后的"已中断"会被立刻自动接管，用户永远看不到中断态与失败原因。
 * - 页/块级修复（retryBlock/regeneratePage）走即时路径，不与长执行器共用注册表；
 *   对已 ready 的书同样可用（阅读器「强制重新生成」「重试块」），书籍状态不变；
 *   无 run 记录的书（演示书/旧四态就绪书）会补建检查点作为写入容器，不再是静默无操作。
 *
 * H1-BOOKS-HARDEN v1（M22-01～03/05）追加的语义，详见 docs/qa/H1-BOOKS-HARDEN/TASK-CARD.md：
 * - **统一收尾**：所有非运行出口（完成/失败/暂停/停止/删除/读失败/失权）都经 teardownRun，
 *   保证合并写盘定时器、心跳、pagehide 监听、注册表与**自有租约**全部释放；不再有
 *   "执行器已退出但仍显示 running、心跳继续续租、恢复被旧句柄挡住"的状态。
 * - **删除与读取失败分开**：readBookForRun 返回 ok/missing/denied。删除→静默收尾不复活；
 *   读取被拒→尝试落库一次 kind storage 失败（尽力），随后收尾，界面据此给出恢复入口。
 * - **租约归属**：记录带 nonce；获取为"写入后读回校验"，每步与每次心跳都校验归属，
 *   失权（owner/nonce 不匹配或记录消失）立即 lease-lost 收尾并停止续租；
 *   清租约只在 owner+nonce 匹配时执行。本地存储没有 CAS，本批不宣称强原子性。
 * - **修复的真实异步结果与操作身份**：retryBlock/regeneratePage 返回 Promise<RepairResult>；
 *   启动时冻结 runId，每次写入前核对归属，运行身份变化即丢弃（绝不借用新 runId 写入）；
 *   同页同目标重复点击复用同一 Promise，不同目标/显式取消走 cancelRepairs。
 * - **最终完成写入失败不假报成功**：finishBookRun 抛错时不设 finished、不只清句柄，
 *   走 kind storage 失败落库并给出「重试生成」入口（注入开关 storageFailureOnFinish，一次性）。
 */

import {
  applyRunEvent,
  ensureBookRun,
  failBookRun,
  finishBookRun,
  pauseBookRun,
  readBooks,
  resumeBookRun,
  setRunScenario,
  regeneratePage as regeneratePageInStore,
  retryBlock as retryBlockInStore,
  type BookBlock,
  type BookFailureKind,
  type BookRunCheckpoint,
  type BookRunEvent,
  type BookRunScenario,
  type ReplicaBook,
} from './books-store';

export type { BookRunScenario };

export const CONSECUTIVE_PAGE_FAILURE_LIMIT = 2;
export const RUN_LEASE_STALE_MS = 3000;
const LEASE_HEARTBEAT_MS = 1000;
const BLOCK_WRITE_MERGE_MS = 200;

/** 默认节奏（任务卡 §4.4）：准备段 300ms、逐块 220ms */
const DEFAULT_STAGE_DELAY_MS = 300;
const DEFAULT_BLOCK_DELAY_MS = 220;

export const DEFAULT_RUN_SCENARIO: BookRunScenario = {
  stageDelayMs: DEFAULT_STAGE_DELAY_MS,
  blockDelayMs: DEFAULT_BLOCK_DELAY_MS,
};

export interface BookRunHandle {
  bookId: string;
  runId: string;
  pause(): void;
  resume(): void;
  stop(): void;
  readonly status: 'running' | 'paused' | 'stopped' | 'finished' | 'failed';
}

export interface BookLeaseInfo {
  owner: string;
  runId: string;
  heartbeatAt: number;
  live: boolean;
  mine: boolean;
}

interface LeaseRecord {
  owner: string;
  runId: string;
  heartbeatAt: number;
  /** 本次获取的随机标识：写后读回校验与失权判定都用它（新增于 HARDEN v1） */
  nonce: string;
}

// ===== 模块级注册表（不随 React 组件卸载取消） =====

interface RunState {
  bookId: string;
  runId: string;
  /** 本次获取的租约 nonce（归属校验与只清自有租约的凭据） */
  leaseNonce: string;
  scenario: Required<Pick<BookRunScenario, 'stageDelayMs' | 'blockDelayMs'>> &
    BookRunScenario;
  status: BookRunHandle['status'];
  /** 取消信号：收尾（停止/暂停/失败/完成/失权/删除）后置 true，所有迟到回调据此丢弃 */
  cancelled: boolean;
  /** 待合并写盘的事件队列（block 级 200ms 合并；关键事件立即 flush）。seq 在落库时按最新记录现取 */
  pending: BookRunEvent[];
  mergeTimer: ReturnType<typeof setTimeout> | null;
  heartbeatTimer: ReturnType<typeof setInterval> | null;
  pagehideHandler: (() => void) | null;
  /** 连续页失败计数（provider 暂停阈值判定，engine.py:1481-1485） */
  consecutivePageFailures: number;
  /** 已失败一次的注入块（failBlockIds 语义：首次失败，重试即成功） */
  failedOnceBlockIds: Set<string>;
}

/** 模块级单例：同一书同一时刻最多一个执行器 */
const registry = new Map<string, RunState>();

// ===== 运行收尾（所有非运行出口的唯一路径） =====

/**
 * 执行器退出原因。区分"删除"与"读取失败"与"失去租约"，界面据此给出不同提示与恢复入口。
 * `finished` 走完全部页且最终状态已落库；`interrupted` 走完全部页但仍有未完成页（既定"已中断"语义）。
 */
export type RunExitReason =
  | 'finished'
  | 'interrupted'
  | 'failed'
  | 'paused'
  | 'stopped'
  | 'deleted'
  | 'read-denied'
  | 'lease-lost';

export interface RunExit {
  reason: RunExitReason;
  message?: string;
  at: number;
}

const runExits = new Map<string, RunExit>();

/**
 * 统一收尾：释放合并写盘定时器、心跳、pagehide 监听、注册表条目、自有租约，并取消本书在途修复。
 * 任何非运行出口都必须经过这里——M22-01 的根因就是"分支直接 return"导致这些资源残留。
 */
function teardownRun(state: RunState, reason: RunExitReason, message?: string): void {
  if (state.cancelled) return;
  state.cancelled = true;
  state.pending = [];
  stopTimers(state);
  state.status =
    reason === 'finished'
      ? 'finished'
      : reason === 'paused'
        ? 'paused'
        : reason === 'failed'
          ? 'failed'
          : 'stopped';
  if (registry.get(state.bookId) === state) registry.delete(state.bookId);
  cancelRepairs(state.bookId, `执行器已收尾（${reason}）`);
  clearOwnLease(state.bookId, state.runId, state.leaseNonce);
  // 未显式给出文案时按出口类型生成（界面可如实提示，而不是只看到一个空原因）
  const text = message ?? (reason === 'finished' ? undefined : exitMessage(reason, state.bookId));
  runExits.set(state.bookId, { reason, ...(text ? { message: text } : {}), at: Date.now() });
}

/** 最近一次执行器收尾原因（无记录返回 null）；供界面如实提示读失败/失权，而不是静默停止 */
export function getRunExit(bookId: string): RunExit | null {
  return runExits.get(bookId) ?? null;
}

// ===== 读取最新记录（区分"已删除"与"读取被拒"） =====

type BookRead =
  | { kind: 'ok'; book: ReplicaBook }
  | { kind: 'missing' }
  | { kind: 'denied'; error: string };

/** 读取一本书的最新记录；读取异常不再折叠成 null（否则删除与读取失败无法区分） */
function readBookForRun(bookId: string): BookRead {
  try {
    const book = readBooks().find((item) => item.id === bookId);
    return book ? { kind: 'ok', book } : { kind: 'missing' };
  } catch (cause) {
    return {
      kind: 'denied',
      error: cause instanceof Error ? cause.message : '本地存储读取失败',
    };
  }
}

function exitMessage(reason: RunExitReason, bookId: string, detail?: string): string {
  switch (reason) {
    case 'deleted':
      return `书籍（${bookId}）已被删除：生成任务已收尾，迟到写入不会复活它。`;
    case 'read-denied':
      return `本地存储读取失败：本次生成已停止，原数据未修改，可稍后重试生成。${detail ? `（${detail}）` : ''}`;
    case 'lease-lost':
      // 归属校验失败可能是"别人接管"也可能是"租约读取被拒"（无法确认所有权）；两者都停止生成，
      // 文案如实写成"已失去或无法确认"，不单方面断言是别的标签页（独立验收 A1 挑刺）。
      return '已失去或无法确认本书的生成所有权（另一个标签页可能已接管，也可能是本地存储读取失败）：本标签页执行器已停止并停止续租。';
    case 'stopped':
      return detail ?? '生成任务已停止（书籍状态变化或运行身份变化），已完成内容保留。';
    case 'interrupted':
      return '本轮已走完全部页面，但仍有未完成页：书籍保持"已中断"，可从断点继续生成。';
    default:
      return detail ?? '';
  }
}

// ===== 工具 =====

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function ownerId(): string {
  if (typeof window === 'undefined') return 'server';
  try {
    const existing = window.sessionStorage.getItem('zhiqikeyuan:book-lease-owner');
    if (existing) return existing;
    const created = uid('owner');
    window.sessionStorage.setItem('zhiqikeyuan:book-lease-owner', created);
    return created;
  } catch {
    return 'no-session';
  }
}

function leaseKey(bookId: string): string {
  return `zhiqikeyuan:book-lease:${bookId}`;
}

function readLease(bookId: string): LeaseRecord | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(leaseKey(bookId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<LeaseRecord>;
    if (typeof parsed.owner !== 'string' || typeof parsed.runId !== 'string') return null;
    return {
      owner: parsed.owner,
      runId: parsed.runId,
      heartbeatAt: typeof parsed.heartbeatAt === 'number' ? parsed.heartbeatAt : 0,
      nonce: typeof parsed.nonce === 'string' ? parsed.nonce : '',
    };
  } catch {
    return null;
  }
}

function writeLease(bookId: string, record: LeaseRecord): boolean {
  if (typeof window === 'undefined') return false;
  try {
    window.localStorage.setItem(leaseKey(bookId), JSON.stringify(record));
    return true;
  } catch {
    // 租约写入失败不阻断生成（本地存储满时由数据写入路径真实报错）
    return false;
  }
}

/**
 * 获取（或接管）租约：写入后**读回校验**。
 *
 * localStorage 没有 CAS，两个标签页可以"同时"通过检查再各自写入（后写者胜）。
 * 这里先拒绝活租约（非本标签页），写入本标签页本次 nonce 后读回：读回不是本次 nonce
 * （被并发写覆盖，或写入根本没成功）即视为未取得，调用方不得启动执行器。
 * 取得之后还有每步/心跳的归属校验（ownsLease），失权即停止——见 teardownRun。
 */
function acquireLease(bookId: string, runId: string): string | null {
  if (leaseHeldByOther(bookId)) return null;
  const owner = ownerId();
  const nonce = uid('lease');
  if (!writeLease(bookId, { owner, runId, heartbeatAt: Date.now(), nonce })) return null;
  const back = readLease(bookId);
  if (!back || back.owner !== owner || back.nonce !== nonce || back.runId !== runId) return null;
  return nonce;
}

/** 归属校验：本标签页仍持有本次获取的租约（记录消失也算失权：别人清掉/接管了它） */
function ownsLease(state: Pick<RunState, 'bookId' | 'runId' | 'leaseNonce'>): boolean {
  const record = readLease(state.bookId);
  return (
    record !== null &&
    record.owner === ownerId() &&
    record.nonce === state.leaseNonce &&
    record.runId === state.runId
  );
}

/** 只清本标签页持有的租约（owner+nonce 匹配）；不误删其他标签页刚取得的租约 */
function clearOwnLease(bookId: string, runId: string, nonce: string): void {
  if (typeof window === 'undefined') return;
  const record = readLease(bookId);
  if (record && (record.owner !== ownerId() || record.nonce !== nonce || record.runId !== runId)) {
    return; // 已不是本标签页的租约：保留现场，不动别人的记录
  }
  try {
    window.localStorage.removeItem(leaseKey(bookId));
  } catch {
    // 忽略清理失败
  }
}

/** 对外租约视图：心跳超时视为失效；owner 与本标签一致视为 mine */
export function getLease(bookId: string): BookLeaseInfo | null {
  const record = readLease(bookId);
  if (!record) return null;
  const live = Date.now() - record.heartbeatAt < RUN_LEASE_STALE_MS;
  return {
    owner: record.owner,
    runId: record.runId,
    heartbeatAt: record.heartbeatAt,
    live,
    mine: record.owner === ownerId(),
  };
}

/** 他标签页持活租约时本标签不得启动第二个执行器 */
function leaseHeldByOther(bookId: string): boolean {
  const lease = getLease(bookId);
  return lease !== null && lease.live && !lease.mine;
}

// ===== 存储写失败注入（storageFailureAt） =====

const BOOKS_KEY = 'zhiqikeyuan:books';

/** 生效中的写入失败补丁（未注入时为 null）；release 按此记录逐项还原 */
interface StorageFailPatch {
  /** 被替换的属性宿主：Storage 实例与其原型（原型路径是 jsdom 等实现的唯一可行路径） */
  instanceOwner: Storage;
  instanceOwnDescriptor: PropertyDescriptor | undefined;
  prototypeOwner: object | null;
  prototypeDescriptor: PropertyDescriptor | undefined;
}

let storagePatch: StorageFailPatch | null = null;

function throwIfInjected(key: string): void {
  if (key === BOOKS_KEY) {
    throw new DOMException('The quota has been exceeded.', 'QuotaExceededError');
  }
}

/** 尝试在给定宿主上定义补丁；返回补丁是否真的生效（defineProperty 可能被实现忽略）。 */
function defineSetItemPatch(owner: object, patched: Storage['setItem']): boolean {
  try {
    Object.defineProperty(owner, 'setItem', {
      configurable: true,
      writable: true,
      enumerable: false,
      value: patched,
    });
    return (owner as { setItem?: Storage['setItem'] }).setItem === patched;
  } catch {
    return false;
  }
}

/**
 * 注入一次性真实写失败：让 local-collection.writeStrictList 在写书籍键时收到
 * QuotaExceededError（回滚 + 抛 CollectionStorageError），覆盖到下一次写盘 flush 结束为止。
 *
 * 直接给 Storage 实例赋 setItem 在部分实现（jsdom 的 Storage 代理）上是静默无效的，
 * 因此先试实例、读回确认，未生效再落到原型上——否则"注入"永不抛错，界面会谎报已保存。
 * 两条路径都无法生效时保持未注入（写入真实成功，不伪造失败结论）。
 */
function armStorageFailOnce(): void {
  if (typeof window === 'undefined' || storagePatch !== null) return;
  const instanceOwner = window.localStorage;
  const original = instanceOwner.setItem.bind(instanceOwner);
  const patched = ((key: string, value: string) => {
    throwIfInjected(key);
    return original(key, value);
  }) as Storage['setItem'];
  const prototypeOwner: object | null = Object.getPrototypeOf(instanceOwner) as object | null;
  const patch: StorageFailPatch = {
    instanceOwner,
    instanceOwnDescriptor: Object.getOwnPropertyDescriptor(instanceOwner, 'setItem'),
    prototypeOwner,
    prototypeDescriptor: prototypeOwner
      ? Object.getOwnPropertyDescriptor(prototypeOwner, 'setItem')
      : undefined,
  };
  const instancePatched = defineSetItemPatch(instanceOwner, patched);
  if (instancePatched) {
    storagePatch = patch;
    return;
  }
  if (prototypeOwner && patch.prototypeDescriptor && defineSetItemPatch(prototypeOwner, patched)) {
    storagePatch = patch;
  }
}

function releaseStorageFailOnce(): void {
  const patch = storagePatch;
  if (patch === null) return;
  storagePatch = null;
  try {
    if (patch.instanceOwnDescriptor) {
      Object.defineProperty(patch.instanceOwner, 'setItem', patch.instanceOwnDescriptor);
    } else {
      Reflect.deleteProperty(patch.instanceOwner, 'setItem');
    }
    if (patch.prototypeOwner && patch.prototypeDescriptor) {
      Object.defineProperty(patch.prototypeOwner, 'setItem', patch.prototypeDescriptor);
    }
  } catch {
    // 还原失败保留现场：写入路径下一拍由 local-collection 如实报错
  }
}

// ===== 事件提交（经仓储唯一写入口 applyRunEvent） =====

function emit(state: RunState, event: BookRunEvent, immediate = false): void {
  if (state.cancelled) return;
  state.pending.push(event);
  if (immediate) {
    flush(state);
    return;
  }
  if (state.mergeTimer === null) {
    state.mergeTimer = setTimeout(() => {
      state.mergeTimer = null;
      flush(state);
    }, BLOCK_WRITE_MERGE_MS);
  }
}

/** 已见事件序号（落库 seq 的唯一依据：读取最新记录，不缓存整本快照） */
function readRunSeqFromBook(book: ReplicaBook): number {
  const memo = (book.run as unknown as { lastSeq?: number } | undefined) ?? undefined;
  return memo?.lastSeq ?? 0;
}

/**
 * 逐条落库：每条事件前重读最新记录，seq = 已见序号 + 1。
 * 队列写盘与即时重试/重生成路径共用同一单调序号空间——各自维护本地计数器时，
 * 两条路径交错会让落后的一方被仓储当作"重复/迟到事件"静默丢弃，
 * 表现为块永远停在 pending、或页已生成完而书籍仍停在 compiling。
 * 书籍不存在或 runId 不匹配（删除/换 run 后的迟到事件）静默跳过并返回 false：
 * 调用方据此统计"因归属校验被丢弃的写入"，而不是把它当成写成功。
 * 仓储抛错（读被拒/写满）不在此吞掉，由调用方走 storage 失败路径。
 */
function applyStored(bookId: string, runId: string, event: BookRunEvent): boolean {
  const latest = readBooks().find((item) => item.id === bookId);
  if (!latest || latest.run?.runId !== runId) return false;
  applyRunEvent(bookId, runId, event, readRunSeqFromBook(latest) + 1);
  return true;
}

/** flush 前置守卫：storageFailureAt 注入条件（在写盘前判定，独立于 applyRunEvent 是否抛错） */
function shouldInjectStorageFailure(state: RunState): boolean {
  if (!state.scenario.storageFailureAt) return false;
  const book = readBooks().find((item) => item.id === state.bookId);
  if (!book) return false;
  // 一次性注入（对照 failBlockIds"首次失败、重试即成功"）：同一 run 已因本地写入失败而失败过，
  // 恢复后不再重复注入——触发点（已完成页数达阈值）在续跑时仍然成立，否则会永远卡在同一页。
  if (book.run?.failure?.kind === 'storage') return false;
  const pages = (book as unknown as { pages?: Array<{ status?: string }> }).pages ?? [];
  const done = pages.filter((page) => page.status === 'ready' || page.status === 'partial' || page.status === undefined).length;
  return done === state.scenario.storageFailureAt.pageIndex;
}

/**
 * 写盘：逐条经 applyRunEvent 落库。storageFailureAt 命中时注入真实写失败，
 * local-collection 抛 CollectionStorageError → failBookRun(kind storage)，绝不谎报"已保存"。
 */
function flush(state: RunState): void {
  if (state.mergeTimer !== null) {
    clearTimeout(state.mergeTimer);
    state.mergeTimer = null;
  }
  if (state.pending.length === 0) return;
  const batch = state.pending;
  state.pending = [];
  const inject = shouldInjectStorageFailure(state);
  if (inject) armStorageFailOnce();
  try {
    for (const event of batch) {
      applyStored(state.bookId, state.runId, event);
    }
  } catch (cause) {
    // local-collection 真实抛错（读拒/写满回滚后抛）：整轮失败，kind storage
    releaseStorageFailOnce();
    failTheRun(state, {
      kind: 'storage',
      message:
        cause instanceof Error
          ? `本地保存失败（${cause.message}）已停止生成，原数据保留。`
          : '本地保存失败，已停止生成，原数据保留。',
    });
    return;
  }
  if (inject) releaseStorageFailOnce();
}

/** 整轮失败：先落库失败原因（尽力），再统一收尾——避免"内存 failed 而资源未释放" */
function failTheRun(state: RunState, failure: { kind: BookFailureKind; message: string }): void {
  if (state.cancelled) return;
  state.pending = [];
  releaseStorageFailOnce();
  try {
    failBookRun(state.bookId, state.runId, failure);
  } catch {
    // 失败路径自身写库被拒（存储已坏）：状态留在内存，UI 由读取错误路径呈现
  }
  teardownRun(state, 'failed', failure.message);
}

/**
 * 驱动期间读取最新记录被存储拒绝（M22-01）：与"删除"区分开。
 * 待写事件的 seq 需从最新记录现取，读不到就不能再落库，因此立即丢弃队列并收尾；
 * 尽力把失败原因写进 run 检查点（给出显式「重试生成」入口）；写也被拒则只保留内存记录与收尾原因。
 */
function handleRunReadDenied(state: RunState, error: string): void {
  if (state.cancelled) return;
  state.pending = [];
  try {
    failBookRun(state.bookId, state.runId, {
      kind: 'storage',
      message: `本地存储读取失败（${error}）：本次生成已停止，原数据未修改，可重试生成。`,
    });
  } catch {
    // 读/写都不可用：保持既有数据不动，由界面读取错误路径呈现
  }
  teardownRun(state, 'read-denied', error);
}

function stopTimers(state: RunState): void {
  if (state.mergeTimer !== null) {
    clearTimeout(state.mergeTimer);
    state.mergeTimer = null;
  }
  if (state.heartbeatTimer !== null) {
    clearInterval(state.heartbeatTimer);
    state.heartbeatTimer = null;
  }
  if (state.pagehideHandler !== null && typeof window !== 'undefined') {
    window.removeEventListener('pagehide', state.pagehideHandler);
    state.pagehideHandler = null;
  }
}

// ===== 页面计划（确定性模板：与 books-store simulateBlocks 同源） =====

interface PlannedBlock {
  blockId: string;
  type: string;
  title?: string;
  content: string;
  language?: string;
  quiz?: { options: Record<string, string>; correct: string; explanation?: string };
}

interface PagePlan {
  pageId: string;
  chapterIndex: number;
  pageIndex: number;
  blocks: PlannedBlock[];
}

/** 页计划的块集合：按骨架页现有块 id（重试/重生成后保留身份）产生最终内容 */
function planPage(bookId: string, pageId: string): PagePlan | null {
  const book = readBooks().find((item) => item.id === bookId);
  if (!book) return null;
  const internal = book as unknown as {
    chapters: Array<{ title: string; pageIds: string[] }>;
    pages?: Array<{ id: string; blocks: Array<{ id: string; type: string }> }>;
  };
  const pages = internal.pages ?? [];
  const page = pages.find((item) => item.id === pageId);
  if (!page) return null;
  const chapterIndex = internal.chapters.findIndex((chapter) => chapter.pageIds.includes(pageId));
  if (chapterIndex === -1) return null;
  const chapter = internal.chapters[chapterIndex]!;
  const offset = chapter.pageIds.indexOf(pageId);
  const template = finalizeBlocks(chapter.title, `${chapter.title} · 第${offset + 1}页`);
  // 块内容按索引与模板对齐（骨架与模板同源生成，序列一致）；user_note 内容由仓储保留，不覆盖
  const blocks: PlannedBlock[] = page.blocks.map((skeleton, index) => {
    const tpl = template[index];
    return {
      blockId: skeleton.id,
      type: skeleton.type,
      ...(tpl?.title !== undefined ? { title: tpl.title } : {}),
      content: tpl?.content ?? '',
      ...(tpl?.language !== undefined ? { language: tpl.language } : {}),
      ...(tpl?.quiz !== undefined ? { quiz: tpl.quiz } : {}),
    };
  });
  return { pageId, chapterIndex, pageIndex: offset, blocks };
}

/** 与 books-store simulateBlocks 同源的最终内容模板（本模块持有副本，避免导出仓储私有函数） */
function finalizeBlocks(chapterTitle: string, pageTitle: string): Array<{
  type: string;
  title?: string;
  content: string;
  language?: string;
  quiz?: { options: Record<string, string>; correct: string; explanation?: string };
}> {
  const blocks: Array<{
    type: string;
    title?: string;
    content: string;
    language?: string;
    quiz?: { options: Record<string, string>; correct: string; explanation?: string };
  }> = [
    {
      type: 'section',
      title: chapterTitle,
      content: `本节围绕「${pageTitle}」展开（模拟生成内容，用于验证阅读器结构与进度，不代表模型产出）。`,
    },
    {
      type: 'text',
      content: `## ${pageTitle}\n\n- 先看一个具体例子；\n- 再理解定义与依据；\n- 最后完成本页小练习。\n\n（模拟生成）`,
    },
    {
      type: 'callout',
      title: '学习提示',
      content: '把本页要点用自己的话复述一遍，再进入下一页（模拟生成）。',
    },
    {
      type: 'quiz',
      title: '本页小练',
      content: `「${pageTitle}」这一页的主要目标是？`,
      quiz: {
        options: { A: '理解本页概念并能举例', B: '背诵全文' },
        correct: 'A',
        explanation: '书籍页面以理解为目标（模拟生成）。',
      },
    },
  ];
  if (pageTitle.endsWith('第2页')) {
    blocks.push(
      {
        type: 'code',
        title: '示例代码（模拟生成）',
        language: 'python',
        content: 'def solve(x):\n    # 模拟示例：两倍\n    return x * 2\n\nprint(solve(21))',
      },
      {
        type: 'timeline',
        title: '学习路径时间线（模拟生成）',
        content: ['第 1 步 :: 认识基本概念', '第 2 步 :: 完成第一组练习', '第 3 步 :: 综合应用与复述'].join('\n'),
      },
      {
        type: 'flash_cards',
        title: '记忆卡（点击翻面；模拟生成）',
        content: ['本页的关键词是什么？ :: 参考本页 section 标题', '下一页要做什么？ :: 完成综合练习'].join('\n'),
      },
      {
        type: 'deep_dive',
        title: '深入探究（展开查看；模拟生成）',
        content: '扩展阅读方向：把本页概念与生活实例对照，尝试向别人讲解一遍（模拟生成）。',
      },
      {
        type: 'figure',
        title: '插图位（模拟占位）',
        content: '真实图像生成/上传未接入；此处保留图注结构。',
      },
      {
        type: 'concept_graph',
        title: '概念关联（模拟静态展示）',
        content: [`${chapterTitle} - ${pageTitle}`, `${pageTitle} - 练习巩固`].join('\n'),
      },
      {
        type: 'user_note',
        title: '我的笔记（本地保存）',
        content: '',
      },
      {
        type: 'interactive',
        title: '互动组件（显式模拟占位）',
        content: '真实互动课件生成未接入；本块仅保留前端占位与说明。',
      },
      {
        type: 'animation',
        title: '动画演示（显式模拟占位）',
        content: '真实教学动画生成未接入；本块仅保留前端占位与说明。',
      },
    );
  }
  return blocks;
}

/**
 * 块内容版本（对照参考 Block 的 content_version）：按生成内容的确定性哈希计算。
 *
 * 为什么必须真实写入：`recordQuizAttempt.blockVersion` 与 `quizAttemptMatches` 构成作答版本关系，
 * 但只定义字段而从不产出值时，那条关系在生产路径上永远为“匹配”，是声明与实现不一致
 * （独立验收 A1 复核项）。写入后语义为：内容相同 → 版本相同（同一道题，旧作答仍然有效）；
 * 内容真的变了（模板调整/未来接真实生成）→ 版本变化，旧作答按旧版记录如实提示，不冒充新题答案。
 */
function blockContentVersion(planned: PlannedBlock): string {
  const payload = JSON.stringify([
    planned.type,
    planned.title ?? '',
    planned.content,
    planned.language ?? '',
    planned.quiz ?? null,
  ]);
  let hash = 2166136261;
  for (let index = 0; index < payload.length; index += 1) {
    hash ^= payload.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return `v1-${hash.toString(16).padStart(8, '0')}`;
}

function plannedToBlockPayload(planned: PlannedBlock): BookBlock {
  return {
    id: planned.blockId,
    type: planned.type as BookBlock['type'],
    ...(planned.title !== undefined ? { title: planned.title } : {}),
    content: planned.content,
    ...(planned.language !== undefined ? { language: planned.language } : {}),
    ...(planned.quiz !== undefined ? { quiz: planned.quiz } : {}),
    contentVersion: blockContentVersion(planned),
    status: 'ready',
  };
}

// ===== 执行主体 =====

interface StartRunOptions {
  scenario?: BookRunScenario;
  source?: 'user' | 'auto-open' | 'retry';
}

function checkpointOf(book: ReplicaBook): BookRunCheckpoint | null {
  return book.run ?? null;
}

function pageListOf(book: ReplicaBook): string[] {
  return book.chapters.flatMap((chapter) => chapter.pageIds);
}

/** 全书第一个块的 id（按页面顺序取第一个非空块）；无骨架页时返回 null */
function firstBlockIdOf(book: ReplicaBook): string | null {
  const pages =
    (book as unknown as { pages?: Array<{ blocks?: Array<{ id: string }> }> }).pages ?? [];
  for (const page of pages) {
    const first = page.blocks?.[0];
    if (first?.id) return first.id;
  }
  return null;
}

/**
 * 展开场景里的通配写法（只认 `'*first'` → 全书第一个块）。
 *
 * UI 的「注入块失败」开关写的是 `failBlockIds: ['*first']`；执行器按精确块 id 匹配，
 * 不展开时通配符永不命中——开关看着打开、实际什么都没注入（静默无操作）。
 * 展开结果会随 setRunScenario 持久化，续跑/重试沿用同一真实块 id。
 * 无法展开（书还没有页面骨架）时该通配被丢弃并如实留空：注入不到任何块，而不是假装命中。
 */
export function expandRunScenario(book: ReplicaBook, scenario: BookRunScenario): BookRunScenario {
  const ids = scenario.failBlockIds;
  if (!ids || ids.length === 0) return scenario;
  const first = firstBlockIdOf(book);
  const expanded = Array.from(
    new Set(ids.flatMap((id) => (id === '*first' ? (first ? [first] : []) : [id]))),
  );
  return { ...scenario, failBlockIds: expanded };
}

/**
 * 需要注入整页失败的页数（按全局页序）。
 * `failPages` 直接要求前 N 页失败；`providerPauseAfterPages`（模拟供应商连续失败暂停）
 * 本身没有别的失败来源——不注入页失败时该开关同样是静默无操作，因此取两者较大值：
 * 供应商场景会先让页失败，累积到阈值后暂停（对照 engine.py:105/1481-1485）。
 */
function pageFailureInjectCount(scenario: BookRunScenario): number {
  return Math.max(scenario.failPages ?? 0, scenario.providerPauseAfterPages ?? 0);
}

/**
 * 启动（或接管）一书的模拟执行器。仅当书籍 compiling 且租约可用时成功；
 * 他标签页持活租约、书籍非 compiling 时返回 null；本标签已有活跃执行器时返回现有句柄（不重复启动）。
 */
export function startRun(
  bookId: string,
  options?: StartRunOptions,
): BookRunHandle | null {
  const existing = registry.get(bookId);
  if (existing && (existing.status === 'running' || existing.status === 'paused')) {
    return handleFor(existing);
  }
  if (leaseHeldByOther(bookId)) return null; // 他标签页在跑：只读显示生成中
  const read = readBookForRun(bookId);
  // 读取被拒或书不存在：不启动执行器（不伪造"正在生成"）
  if (read.kind !== 'ok' || read.book.status !== 'compiling') return null;
  const book = read.book;
  const checkpoint = checkpointOf(book);
  // 场景解析：通配符（'*first'）在此展开为实际块 id，UI 的注入开关才真的命中
  const requested = expandRunScenario(book, options?.scenario ?? book.runScenario ?? {});
  const scenario: RunState['scenario'] = {
    ...requested,
    stageDelayMs: requested.stageDelayMs ?? DEFAULT_STAGE_DELAY_MS,
    blockDelayMs: requested.blockDelayMs ?? DEFAULT_BLOCK_DELAY_MS,
  };
  if (options?.scenario) {
    // 持久化本次生效的模拟设置：续跑/重试沿用同一节奏与注入场景（否则静默回落到默认值）
    try {
      setRunScenario(bookId, scenario);
    } catch {
      // 存储写入失败：按当前设置继续运行，落库错误由事件路径如实呈现
    }
  }
  const runId = checkpoint?.runId ?? uid('run');
  // 租约：写入后读回校验；未取得（他标签页并发写入/写入失败）就不启动执行器
  const leaseNonce = acquireLease(bookId, runId);
  if (!leaseNonce) return null;
  const state: RunState = {
    bookId,
    runId,
    leaseNonce,
    scenario,
    status: 'running',
    cancelled: false,
    pending: [],
    mergeTimer: null,
    heartbeatTimer: null,
    pagehideHandler: null,
    consecutivePageFailures: 0,
    failedOnceBlockIds: new Set<string>(),
  };
  registry.set(bookId, state);
  runExits.delete(bookId); // 新一轮开始：清掉上一轮的收尾原因，旧提示不复现
  // 心跳 1s：每次先校验归属，失权立即收尾并停止续租（不再盲写租约）
  state.heartbeatTimer = setInterval(() => {
    if (state.cancelled) return;
    if (!ownsLease(state)) {
      teardownRun(state, 'lease-lost');
      return;
    }
    writeLease(bookId, { owner: ownerId(), runId, heartbeatAt: Date.now(), nonce: leaseNonce });
  }, LEASE_HEARTBEAT_MS);
  if (typeof window !== 'undefined') {
    state.pagehideHandler = () => flush(state);
    window.addEventListener('pagehide', state.pagehideHandler);
  }
  void options?.source;
  emit(state, { type: 'run-start' }, true);
  void drive(state);
  return handleFor(state);
}

/** 驱动上下文：每步重新读取最新书籍记录，从检查点推进（pageSeq 为全局页序） */
interface DriveContext {
  pageSeq: number;
  currentPageId: string | null;
  blockIndex: number;
  currentPlan: PagePlan | null;
}

/**
 * 驱动循环：每步读取最新书籍记录，经 stepOnce 推进；所有迟到回调先校验 cancelled。
 * 一律从全局首页开始，由 stepOnce 跳过已完成（ready/partial）页——检查点游标指向"最后开始的页"，
 * 用它当起点会跳过它之前仍未完成的页（页失败、被整页重生成复位），续跑就永远修不好那些页。
 */
async function drive(state: RunState): Promise<void> {
  const stageDelay = state.scenario.stageDelayMs ?? DEFAULT_STAGE_DELAY_MS;
  await delay(stageDelay);
  if (state.cancelled) return;
  // 起步前再校验一次归属：停在准备段的窗口里可能已被别的标签页接管
  if (!ownsLease(state)) {
    teardownRun(state, 'lease-lost');
    return;
  }
  const ctx: DriveContext = { pageSeq: 0, currentPageId: null, blockIndex: 0, currentPlan: null };
  while (!state.cancelled) {
    const proceed = await stepOnce(state, ctx);
    if (!proceed) return;
  }
}

function pageStatusOf(book: ReplicaBook, pageId: string): string | undefined {
  const pages = (book as unknown as { pages?: Array<{ id: string; status?: string }> }).pages ?? [];
  return pages.find((page) => page.id === pageId)?.status;
}

/** 页的失败尝试次数（持久化字段；整页失败注入的一次性判据） */
function pageAttemptsOf(book: ReplicaBook, pageId: string): number {
  const pages = (book as unknown as { pages?: Array<{ id: string; attempts?: number }> }).pages ?? [];
  return pages.find((page) => page.id === pageId)?.attempts ?? 0;
}

function blockStatusOf(
  book: ReplicaBook | null,
  pageId: string,
  blockId: string,
): string | undefined {
  if (!book) return undefined;
  const pages = (book as unknown as { pages?: Array<{ id: string; blocks: Array<{ id: string; status?: string }> }> }).pages ?? [];
  return pages.find((page) => page.id === pageId)?.blocks.find((block) => block.id === blockId)?.status;
}

function freshBook(state: RunState): ReplicaBook | null {
  const read = readBookForRun(state.bookId);
  if (read.kind === 'missing') {
    // 删除分支（M22-01）：静默收尾，不写任何事件、不复活记录
    teardownRun(state, 'deleted');
    return null;
  }
  if (read.kind === 'denied') {
    handleRunReadDenied(state, read.error);
    return null;
  }
  if (read.book.status !== 'compiling') {
    // 状态已被他处改变（暂停/归档/重建）：停止本执行器，但已完成内容与断点保留
    teardownRun(
      state,
      'stopped',
      `书籍状态已变为「${read.book.status}」，本标签页执行器已停止（已完成内容保留）。`,
    );
    return null;
  }
  return read.book;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

/** 单次驱动步进：处理一个块（或一步页级行动）。返回 false 表示驱动已停止（cancelled/状态变化）。 */
async function stepOnce(
  state: RunState,
  ctx: DriveContext,
): Promise<boolean> {
  const blockDelay = state.scenario.blockDelayMs ?? DEFAULT_BLOCK_DELAY_MS;
  // 每步开始先校验归属（M22-03）：失权立即收尾，不再按旧身份继续驱动或写入
  if (!ownsLease(state)) {
    teardownRun(state, 'lease-lost');
    return false;
  }
  const book = freshBook(state);
  if (!book) return false; // 已收尾（删除/读取失败/书籍状态已变化）
  const pages = pageListOf(book);
  // 前进到下一个未完成页；缺 status 的旧页按 ready 处理（§4.2 兼容规则，不因兼容数据重复生成）
  while (ctx.pageSeq < pages.length) {
    const pageId = pages[ctx.pageSeq]!;
    const status = pageStatusOf(book, pageId);
    if (status !== undefined && status !== 'ready' && status !== 'partial') break;
    ctx.pageSeq += 1;
  }
  if (ctx.pageSeq >= pages.length) {
    // 收尾：run-finished 入队后立即 flush，同一批内先落库所有待写页/块事件、再落收尾事件，
    // 因此不存在"内容已生成但书籍停在 compiling"的窗口；是否 ready 由 finishBookRun 按
    // "是否仍有未完成页"判定（§4.3：仍有 error/pending/generating 页 → 保持 compiling = 已中断）。
    emit(state, { type: 'run-finished' }, true);
    if (state.cancelled) return false; // flush 期间失败（storage）：错误路径已接管，不再覆盖状态
    // 最终完成落库（M22-05）：失败绝不假报成功——不设 finished、不只清句柄，而是按 storage 失败
    // 落库并给出「重试生成」入口。注入一次性：本运行已因 storage 失败过就不再注入（否则重试必再败）。
    const injectFinishFailure =
      state.scenario.storageFailureOnFinish === true && book.run?.failure?.kind !== 'storage';
    if (injectFinishFailure) armStorageFailOnce();
    let settled: ReplicaBook | null;
    try {
      settled = finishBookRun(state.bookId, state.runId);
    } catch (cause) {
      releaseStorageFailOnce();
      failTheRun(state, {
        kind: 'storage',
        message: `最终完成状态写入失败（${
          cause instanceof Error ? cause.message : '本地存储拒绝写入'
        }）：本次生成未标记为完成，可重试生成。`,
      });
      return false;
    }
    releaseStorageFailOnce();
    if (!settled) {
      teardownRun(state, 'stopped', '完成状态未写入：书籍已被删除或运行身份已变化。');
      return false;
    }
    teardownRun(state, settled.status === 'ready' ? 'finished' : 'interrupted');
    return false;
  }
  const pageId = pages[ctx.pageSeq]!;
  if (ctx.currentPageId !== pageId) {
    // 新页开始：page-start + page-planned（或注入整页失败）
    ctx.currentPageId = pageId;
    const plan = planPage(state.bookId, pageId);
    if (!plan) {
      ctx.pageSeq += 1;
      return true;
    }
    ctx.currentPlan = plan;
    emit(state, { type: 'page-start', chapterIndex: plan.chapterIndex, pageIndex: plan.pageIndex }, true);
    emit(state, { type: 'page-planned', pageId, blockIds: plan.blocks.map((b) => b.blockId) }, true);
    // 整页失败注入是一次性的（对照 failBlockIds 的"首次失败、重试即成功"语义）：
    // 以页自身持久化的 attempts 为判据——同一页失败过一次后，重试/恢复/刷新续跑都不再注入，
    // 否则恢复后会在同一触发点无限失败，用户永远出不来。
    const injectPageFailure =
      ctx.pageSeq < pageFailureInjectCount(state.scenario) && pageAttemptsOf(book, pageId) === 0;
    if (injectPageFailure) {
      emit(
        state,
        { type: 'page-error', pageId, message: '本页生成失败（模拟页面失败：本地注入，非模型产出）。' },
        true,
      );
      state.consecutivePageFailures += 1;
      const limit = state.scenario.providerPauseAfterPages ?? CONSECUTIVE_PAGE_FAILURE_LIMIT;
      if (state.consecutivePageFailures >= limit) {
        // 模拟供应商连续失败暂停：绝不宣称真实上游故障
        emit(
          state,
          {
            type: 'run-paused',
            kind: 'provider',
            reason: '模拟供应商连续失败（本地注入场景，非真实上游故障）。',
          },
          true,
        );
        state.status = 'paused';
        teardownRun(state, 'paused', '模拟供应商连续失败（本地注入场景，非真实上游故障）。');
        return false;
      }
      ctx.currentPageId = null; // 下一轮处理下一页
      ctx.pageSeq += 1;
      return true;
    }
    ctx.blockIndex = 0;
    return true;
  }
  // 当前页：逐块推进
  const plan = ctx.currentPlan ?? planPage(state.bookId, pageId);
  if (!plan) {
    ctx.pageSeq += 1;
    ctx.currentPageId = null;
    return true;
  }
  ctx.currentPlan = plan;
  // 跳过已完成块（断点续跑；注入失败块除外——重试即成功由 retryBlock 路径处理）
  while (
    ctx.blockIndex < plan.blocks.length &&
    blockStatusOf(book, pageId, plan.blocks[ctx.blockIndex]!.blockId) === 'ready' &&
    state.scenario.failBlockIds?.includes(plan.blocks[ctx.blockIndex]!.blockId) !== true
  ) {
    ctx.blockIndex += 1;
  }
  if (ctx.blockIndex >= plan.blocks.length) {
    // 本页完成
    emit(state, { type: 'page-ready', pageId }, true);
    state.consecutivePageFailures = 0; // 页不失败时清零（engine.py:1471-1475）
    ctx.pageSeq += 1;
    ctx.currentPageId = null;
    return true;
  }
  const planned = plan.blocks[ctx.blockIndex]!;
  emit(state, { type: 'block-start', pageId, blockId: planned.blockId });
  await delay(blockDelay);
  if (state.cancelled) return false; // 迟到回调丢弃（stop/pause 后）
  // 等待期间可能被删除、存储读取被拒或失去租约：先重新读取并如实收尾，不按旧身份继续写入
  if (!ownsLease(state)) {
    teardownRun(state, 'lease-lost');
    return false;
  }
  const current = freshBook(state);
  if (!current) return false;
  // 注入失败只发生一次：内存标记 + 落库后的块状态共同判定
  // （块已带 failure/error 即表示注入已经发生过，刷新续跑不再重复失败）
  const injectFail =
    state.scenario.failBlockIds?.includes(planned.blockId) === true &&
    !state.failedOnceBlockIds.has(planned.blockId) &&
    blockStatusOf(current, pageId, planned.blockId) !== 'error';
  if (injectFail) {
    state.failedOnceBlockIds.add(planned.blockId);
    emit(state, {
      type: 'block-error',
      pageId,
      blockId: planned.blockId,
      failure: {
        kind: 'content',
        message: '模拟块生成失败（本地注入：首次失败，重试即成功；非模型产出）。',
        retryable: true,
        simulated: true,
      },
    });
  } else {
    emit(state, {
      type: 'block-ready',
      pageId,
      blockId: planned.blockId,
      block: plannedToBlockPayload(planned),
    });
  }
  ctx.blockIndex += 1;
  return true;
}

function handleFor(state: RunState): BookRunHandle {
  return {
    bookId: state.bookId,
    runId: state.runId,
    get status() {
      return state.status;
    },
    pause() {
      if (state.status !== 'running' || state.cancelled) return;
      flush(state); // 暂停前立即写盘
      pauseBookRun(state.bookId, 'user', 'Paused by user.');
      // 用户暂停：本执行器停止；恢复由用户显式触发（paused 不自动续跑）
      teardownRun(state, 'paused', '已暂停（用户暂停）：未完成内容只在你恢复后继续。');
    },
    resume() {
      if (state.status !== 'paused') return;
      resumeBookRun(state.bookId, state.runId);
      void startRun(state.bookId, { source: 'user' });
    },
    stop() {
      if (state.cancelled) return;
      flush(state); // 中止保留断点：先写盘再停（不改动书籍状态，检查点已随事件更新）
      teardownRun(state, 'stopped', '生成已停止（已完成内容与断点保留）。');
    },
  };
}

/** 当前活跃执行器句柄（无执行器返回 null） */
export function getRun(bookId: string): BookRunHandle | null {
  const state = registry.get(bookId);
  if (!state) return null;
  return handleFor(state);
}

/**
 * 恢复运行：paused / error（§4.3 可恢复态，如本地写入失败）只能由用户显式调用；
 * compiling 无执行器（已中断）时可由自动续跑调用。他标签页持活租约时不启动。
 * 读取被拒时不启动（不伪造"正在生成"）。
 */
export function resumeRun(bookId: string): BookRunHandle | null {
  const read = readBookForRun(bookId);
  if (read.kind !== 'ok') return null;
  const book = read.book;
  if (book.status === 'paused' || book.status === 'error') {
    const runId = book.run?.runId ?? '';
    const resumed = resumeBookRun(bookId, runId);
    if (!resumed || resumed.status !== 'compiling') return null;
    return startRun(bookId, { source: 'user' });
  }
  if (book.status === 'compiling') {
    return startRun(bookId, { source: 'auto-open' });
  }
  return null;
}

/**
 * 中止（卸载/删除）：保留断点（flush 后停止，不改动书籍状态）。
 * 同时取消本书在途的页/块修复——没有长执行器时它们仍在写盘，删除入口必须先停它们（M22-01）。
 */
export function stopRun(bookId: string, reason: string): void {
  const state = registry.get(bookId);
  if (state && !state.cancelled) {
    flush(state);
    teardownRun(state, 'stopped', `生成已停止（${reason}）：已完成内容与断点保留。`);
  }
  cancelRepairs(bookId, `已停止（${reason}）`);
}

// ===== 块/页级重试（无活跃执行器时的即时补生成路径） =====

/**
 * 即时修复可否写入：运行中/可恢复（compiling/paused/error）与已完成书（ready）。
 * ready 是阅读器「强制重新生成」「重试块」的真实场景——页状态由页自身诚实表达（本页回到生成中），
 * 书籍状态保持 ready（活动条不显示、不触发自动续跑）。
 * draft/spine_ready 无页面骨架，archived 为归档只读（对照参考 can_resume 不含归档），一律不写入。
 */
function repairWritable(book: ReplicaBook): boolean {
  return (
    book.status === 'compiling' ||
    book.status === 'paused' ||
    book.status === 'error' ||
    book.status === 'ready'
  );
}

/**
 * 修复入口的写入容器：本书已有 run 时沿用，没有（演示书、旧四态就绪书）则补建一个。
 * 页/块级修复经 applyRunEvent 落库并以 runId 校验归属，缺 run 会让整个入口静默无操作。
 * 返回的 runId 会被**冻结**为本次操作的身份：此后每一步都按它校验，绝不改成最新的 runId。
 */
function writableRunId(book: ReplicaBook): string | null {
  const ensured = book.run?.runId ? book : (ensureBookRun(book.id) ?? book);
  return ensured.run?.runId ?? null;
}

/** 页/块修复的真实异步结果（M22-02：不再是 fire-and-forget 的 void） */
export interface RepairResult {
  status: 'completed' | 'superseded' | 'cancelled' | 'skipped' | 'failed';
  operationId: string;
  bookId: string;
  pageId: string;
  /** 启动时冻结的运行身份；写入必须与之一致（变更即丢弃，不借用新 runId） */
  runId: string | null;
  /** 本次操作的目标块（单块重试为 1 个，整页重生成为整页计划） */
  blockIds: string[];
  writtenBlockIds: string[];
  /** 因归属校验失败（书籍删除/运行身份变化）而丢弃的写入次数 */
  droppedWrites: number;
  /** status='failed' 时的原因（本地存储写入失败等） */
  error?: string;
}

interface RepairState {
  operationId: string;
  bookId: string;
  pageId: string;
  runId: string;
  blockIds: string[];
  cancelled: boolean;
  /** 取消是被同一页的新操作取代（终态 superseded）还是显式取消（终态 cancelled） */
  supersededByNewOp?: boolean;
  cancelReason?: string;
  writtenBlockIds: string[];
  droppedWrites: number;
}

/** 在途修复（键 = bookId::pageId）：同一页同一时刻只有一个操作，重复目标复用同一 Promise */
const repairs = new Map<string, { state: RepairState; promise: Promise<RepairResult> }>();

function repairKey(bookId: string, pageId: string): string {
  return `${bookId}::${pageId}`;
}

/**
 * 在途操作是否**覆盖**本次请求目标：覆盖 → 复用同一操作（重复点击、整页重生成中重试其中一块
 * 都由在途操作一并完成），否则 → 取代（例如在途只重试一块、新请求要重生成整页）。
 */
function coversTargets(existing: string[], requested: string[]): boolean {
  return requested.length > 0 && requested.every((id) => existing.includes(id));
}

/** 在途修复摘要（界面忙态/测试可读；无在途返回 null） */
export function getRepair(
  bookId: string,
  pageId: string,
): { operationId: string; runId: string; blockIds: string[]; writtenBlockIds: string[] } | null {
  const entry = repairs.get(repairKey(bookId, pageId));
  if (!entry) return null;
  return {
    operationId: entry.state.operationId,
    runId: entry.state.runId,
    blockIds: [...entry.state.blockIds],
    writtenBlockIds: [...entry.state.writtenBlockIds],
  };
}

/** 取消一本书的在途修复（删除/停止/收尾/被新操作取代时调用）；返回被取消的操作数 */
export function cancelRepairs(bookId: string, reason = 'cancelled'): number {
  let cancelled = 0;
  for (const entry of repairs.values()) {
    if (entry.state.bookId !== bookId || entry.state.cancelled) continue;
    entry.state.cancelled = true;
    entry.state.cancelReason = reason;
    cancelled += 1;
  }
  return cancelled;
}

function repairResult(
  state: RepairState,
  status: RepairResult['status'],
  error?: string,
): RepairResult {
  return {
    status,
    operationId: state.operationId,
    bookId: state.bookId,
    pageId: state.pageId,
    runId: state.runId,
    blockIds: [...state.blockIds],
    writtenBlockIds: [...state.writtenBlockIds],
    droppedWrites: state.droppedWrites,
    ...(error !== undefined ? { error } : {}),
  };
}

/**
 * 单块重试：仓储复位该块 + 即时重新生成（failBlockIds 语义：首次失败，重试即成功）。
 * 仅作用于该块；user_note 等既有内容不会被覆盖（仓储保留）。
 *
 * 返回值：真实异步结果。同一页同一目标块已在途 → 复用同一 Promise（重复点击不产生第二遍生成）；
 * 同页不同目标 → 取代在途操作（旧操作剩余写入丢弃，终态 superseded）。
 * 不可写入（书籍状态/缺运行身份）→ 立即以 skipped 解析，不静默无操作。
 */
export function retryBlock(bookId: string, pageId: string, blockId: string): Promise<RepairResult> {
  return startRepair(bookId, pageId, [blockId], () => retryBlockInStore(bookId, pageId, blockId));
}

/** 整页重生成：仓储复位整页（保留 user_note 内容与块身份）+ 即时逐块重新生成 */
export function regeneratePage(bookId: string, pageId: string): Promise<RepairResult> {
  return startRepair(bookId, pageId, null, () => regeneratePageInStore(bookId, pageId));
}

/**
 * 修复入口统一编排：读记录 → 判定可写 → **冻结运行身份** → 复位（仓储）→ 逐块异步补齐。
 * 复位与后续写入都绑定启动时冻结的 runId；运行身份变化时丢弃写入并如实报告。
 */
function startRepair(
  bookId: string,
  pageId: string,
  onlyBlockIds: string[] | null,
  resetInStore: () => void,
): Promise<RepairResult> {
  const read = readBookForRun(bookId);
  if (read.kind !== 'ok') {
    return Promise.resolve(
      skippedRepair(bookId, pageId, null, onlyBlockIds, read.kind === 'missing' ? '书籍不存在或已被删除。' : read.error),
    );
  }
  const book = read.book;
  if (!repairWritable(book)) {
    return Promise.resolve(
      skippedRepair(bookId, pageId, null, onlyBlockIds, `书籍当前状态（${book.status}）不接受页/块修复。`),
    );
  }
  let runId: string | null;
  try {
    runId = writableRunId(book);
  } catch (cause) {
    return Promise.resolve(
      skippedRepair(bookId, pageId, null, onlyBlockIds, cause instanceof Error ? cause.message : '无法建立写入检查点。'),
    );
  }
  if (!runId) {
    return Promise.resolve(skippedRepair(bookId, pageId, null, onlyBlockIds, '本书缺少可用的运行记录。'));
  }
  // 目标块：单块重试按请求块，整页重生成按页面计划（冻结启动时的计划，避免半途换目标）
  const plan = planPage(bookId, pageId);
  const blockIds = onlyBlockIds ?? (plan?.blocks.map((block) => block.blockId) ?? []);
  const key = repairKey(bookId, pageId);
  const existing = repairs.get(key);
  if (existing && !existing.state.cancelled && coversTargets(existing.state.blockIds, blockIds)) {
    return existing.promise; // 在途操作已覆盖本次目标：幂等加入，不启动第二遍生成
  }
  if (existing) {
    existing.state.cancelled = true; // 目标未被覆盖：取代在途操作
    existing.state.supersededByNewOp = true;
    existing.state.cancelReason = '被同一页的新操作取代';
  }
  const state: RepairState = {
    operationId: uid('rep'),
    bookId,
    pageId,
    runId,
    blockIds,
    cancelled: false,
    writtenBlockIds: [],
    droppedWrites: 0,
  };
  let settle!: (result: RepairResult) => void;
  const promise = new Promise<RepairResult>((resolve) => {
    settle = resolve;
  });
  repairs.set(key, { state, promise });
  const finish = (status: RepairResult['status'], error?: string): RepairResult => {
    const result = repairResult(state, status, error);
    const current = repairs.get(key);
    if (current?.state === state) repairs.delete(key);
    settle(result);
    return result;
  };
  try {
    resetInStore(); // 仓储复位（块 → pending / 整页 → pending；user_note 内容与块身份保留）
  } catch (cause) {
    return Promise.resolve(
      finish('failed', cause instanceof Error ? cause.message : '本地存储写入失败：本次修复未开始。'),
    );
  }
  void runRepair(state, finish, onlyBlockIds);
  return promise;
}

function skippedRepair(
  bookId: string,
  pageId: string,
  runId: string | null,
  blockIds: string[] | null,
  error: string,
): RepairResult {
  return {
    status: 'skipped',
    operationId: uid('rep'),
    bookId,
    pageId,
    runId,
    blockIds: blockIds ?? [],
    writtenBlockIds: [],
    droppedWrites: 0,
    error,
  };
}

/**
 * 即时块生成（重试/重生成路径）：不注册长执行器，逐块 block-start→block-ready 落库，
 * 全部完成后 page-ready 复核页状态。
 *
 * 身份规则（M22-02）：每一步与每条写入前重新读取记录，并核对**启动时冻结的 runId**——
 * 运行身份变化（重建/换轮次/换标签页接管）即丢弃本次操作剩余写入并如实记入 droppedWrites，
 * 绝不重新取当前 runId 继续写（这正是旧实现让旧任务**借用新 runId** 的路径）。
 * seq 由 applyStored 从最新记录现取，与队列写盘共用同一序号空间，不会被当作重复事件丢弃。
 */
async function runRepair(
  state: RepairState,
  finish: (status: RepairResult['status'], error?: string) => RepairResult,
  onlyBlockIds: string[] | null,
): Promise<void> {
  /** 被取消时的终态：被新操作取代 → superseded；显式取消/收尾 → cancelled */
  const stopNow = (): void => {
    finish(state.supersededByNewOp ? 'superseded' : 'cancelled', state.cancelReason);
  };
  const read0 = readBookForRun(state.bookId);
  if (read0.kind !== 'ok') {
    finish(
      read0.kind === 'missing' ? 'cancelled' : 'failed',
      read0.kind === 'missing' ? '书籍已删除，本次修复写入已丢弃。' : `本地存储读取失败：${read0.error}`,
    );
    return;
  }
  const scenario = { ...DEFAULT_RUN_SCENARIO, ...(read0.book.runScenario ?? {}) };
  const blockDelay = scenario.blockDelayMs ?? DEFAULT_BLOCK_DELAY_MS;
  const plan = planPage(state.bookId, state.pageId);
  if (!plan) {
    finish('skipped', '页面计划不存在（页面已被删除或骨架缺失）。');
    return;
  }
  for (const planned of plan.blocks) {
    if (state.cancelled) {
      stopNow();
      return;
    }
    if (onlyBlockIds !== null && !onlyBlockIds.includes(planned.blockId)) continue;
    await delay(blockDelay);
    if (state.cancelled) {
      stopNow();
      return;
    }
    const read = readBookForRun(state.bookId);
    if (read.kind === 'missing') {
      state.droppedWrites += 1;
      finish('cancelled', '书籍已删除，本次修复写入已丢弃。');
      return;
    }
    if (read.kind === 'denied') {
      state.droppedWrites += 1;
      finish('failed', `本地存储读取失败：${read.error}`);
      return;
    }
    if (read.book.run?.runId !== state.runId) {
      // 运行身份已变化：丢弃而不借用新 runId 写入（迟到写入被拒）
      state.droppedWrites += 1;
      finish('superseded', '运行身份已变化（重新编译或换轮次），本次修复写入已丢弃。');
      return;
    }
    if (blockStatusOf(read.book, state.pageId, planned.blockId) === 'ready') continue; // 已由他处完成，不重复写
    try {
      const appliedStart = applyStored(state.bookId, state.runId, {
        type: 'block-start',
        pageId: state.pageId,
        blockId: planned.blockId,
      });
      const appliedReady = applyStored(state.bookId, state.runId, {
        type: 'block-ready',
        pageId: state.pageId,
        blockId: planned.blockId,
        block: plannedToBlockPayload(planned),
      });
      if (!appliedStart || !appliedReady) {
        state.droppedWrites += 1;
        finish('superseded', '写入时归属校验失败（运行身份已变化），本次修复写入已丢弃。');
        return;
      }
      // 写后读回校验（独立验收 A1 挑刺）：仓储可能因"书籍状态不再可写"而静默拒绝整条写入
      // （例如修复期间书籍被归档/暂停）。那时不得把该块计入 writtenBlockIds，也不得报 completed。
      const after = readBookForRun(state.bookId);
      const landed =
        after.kind === 'ok' && blockStatusOf(after.book, state.pageId, planned.blockId) === 'ready';
      if (!landed) {
        state.droppedWrites += 1;
        const runChanged = after.kind === 'ok' && after.book.run?.runId !== state.runId;
        finish(
          runChanged ? 'superseded' : 'failed',
          runChanged
            ? '运行身份已变化（重新编译或换轮次），本次修复写入已丢弃。'
            : '写入未生效：书籍当前状态不接受生成（可能已被归档或暂停），本次修复已停止。',
        );
        return;
      }
      state.writtenBlockIds.push(planned.blockId);
    } catch (cause) {
      finish('failed', cause instanceof Error ? cause.message : '本地存储写入失败。');
      return;
    }
  }
  const readEnd = readBookForRun(state.bookId);
  if (readEnd.kind !== 'ok') {
    state.droppedWrites += 1;
    finish(
      readEnd.kind === 'missing' ? 'cancelled' : 'failed',
      readEnd.kind === 'missing' ? '书籍已删除，页状态未复核。' : `本地存储读取失败：${readEnd.error}`,
    );
    return;
  }
  if (readEnd.book.run?.runId !== state.runId) {
    state.droppedWrites += 1;
    finish('superseded', '运行身份已变化（重新编译或换轮次），页状态未复核。');
    return;
  }
  try {
    // 页复核：仍有失败块则 partial（page-ready 事件内的派生逻辑负责），否则 ready
    if (!applyStored(state.bookId, state.runId, { type: 'page-ready', pageId: state.pageId })) {
      state.droppedWrites += 1;
      finish('superseded', '写入时归属校验失败（运行身份已变化），页状态未复核。');
      return;
    }
  } catch (cause) {
    finish('failed', cause instanceof Error ? cause.message : '本地存储写入失败。');
    return;
  }
  finish('completed');
}
