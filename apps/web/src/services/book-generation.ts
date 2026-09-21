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
}

// ===== 模块级注册表（不随 React 组件卸载取消） =====

interface RunState {
  bookId: string;
  runId: string;
  scenario: Required<Pick<BookRunScenario, 'stageDelayMs' | 'blockDelayMs'>> &
    BookRunScenario;
  status: BookRunHandle['status'];
  /** 取消信号：stop()/pause()/失败/完成后置 true，所有迟到回调据此丢弃 */
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
    };
  } catch {
    return null;
  }
}

function writeLease(bookId: string, record: LeaseRecord): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(leaseKey(bookId), JSON.stringify(record));
  } catch {
    // 租约写入失败不阻断生成（本地存储满时由数据写入路径真实报错）
  }
}

function clearLease(bookId: string): void {
  if (typeof window === 'undefined') return;
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
 * 书籍不存在或 runId 不匹配（删除/换 run 后的迟到事件）静默跳过；
 * 仓储抛错（读被拒/写满）不在此吞掉，由调用方走 storage 失败路径。
 */
function applyStored(bookId: string, runId: string, event: BookRunEvent): void {
  const latest = readBooks().find((item) => item.id === bookId);
  if (!latest || latest.run?.runId !== runId) return;
  applyRunEvent(bookId, runId, event, readRunSeqFromBook(latest) + 1);
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

function failTheRun(state: RunState, failure: { kind: BookFailureKind; message: string }): void {
  if (state.cancelled) return;
  state.pending = [];
  releaseStorageFailOnce();
  try {
    failBookRun(state.bookId, state.runId, failure);
  } catch {
    // 失败路径自身写库被拒（存储已坏）：状态留在内存，UI 由读取错误路径呈现
  }
  stopTimers(state);
  state.status = 'failed';
  state.cancelled = true;
  clearLease(state.bookId);
  registry.delete(state.bookId);
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
  const book = readBooks().find((item) => item.id === bookId);
  if (!book || book.status !== 'compiling') return null;
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
  const state: RunState = {
    bookId,
    runId,
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
  // 租约：每标签页一个 ownerId，心跳 1s
  writeLease(bookId, { owner: ownerId(), runId, heartbeatAt: Date.now() });
  state.heartbeatTimer = setInterval(() => {
    if (state.cancelled) return;
    writeLease(bookId, { owner: ownerId(), runId, heartbeatAt: Date.now() });
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
  try {
    return readBooks().find((item) => item.id === state.bookId) ?? null;
  } catch {
    return null;
  }
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
  const book = freshBook(state);
  if (!book || book.status !== 'compiling') return false;
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
    try {
      finishBookRun(state.bookId, state.runId);
    } catch {
      // 结束落库失败（存储坏）：保持 compiling，读取错误路径呈现
    }
    state.status = 'finished';
    state.cancelled = true;
    stopTimers(state);
    registry.delete(state.bookId);
    clearLease(state.bookId);
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
        state.cancelled = true;
        stopTimers(state);
        registry.delete(state.bookId);
        clearLease(state.bookId);
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
    blockStatusOf(freshBook(state), pageId, plan.blocks[ctx.blockIndex]!.blockId) === 'ready' &&
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
  // 注入失败只发生一次：内存标记 + 落库后的块状态共同判定
  // （块已带 failure/error 即表示注入已经发生过，刷新续跑不再重复失败）
  const injectFail =
    state.scenario.failBlockIds?.includes(planned.blockId) === true &&
    !state.failedOnceBlockIds.has(planned.blockId) &&
    blockStatusOf(freshBook(state), pageId, planned.blockId) !== 'error';
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
      state.status = 'paused';
      state.cancelled = true; // 用户暂停：本执行器停止；恢复由用户显式触发（paused 不自动续跑）
      stopTimers(state);
      registry.delete(state.bookId);
      clearLease(state.bookId);
    },
    resume() {
      if (state.status !== 'paused') return;
      resumeBookRun(state.bookId, state.runId);
      void startRun(state.bookId, { source: 'user' });
    },
    stop() {
      if (state.cancelled) return;
      flush(state); // 中止保留断点：先写盘再停（不改动书籍状态，检查点已随事件更新）
      state.status = 'stopped';
      state.cancelled = true;
      stopTimers(state);
      registry.delete(state.bookId);
      clearLease(state.bookId);
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
 */
export function resumeRun(bookId: string): BookRunHandle | null {
  const book = readBooks().find((item) => item.id === bookId);
  if (!book) return null;
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

/** 中止（卸载/删除）：保留断点（flush 后停止，不改动书籍状态） */
export function stopRun(bookId: string, reason: string): void {
  void reason;
  const state = registry.get(bookId);
  if (!state) return;
  handleFor(state).stop();
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
 */
function writableRunId(book: ReplicaBook): string | null {
  const ensured = book.run?.runId ? book : (ensureBookRun(book.id) ?? book);
  return ensured.run?.runId ?? null;
}

/**
 * 单块重试：仓储复位该块 + 即时重新生成（failBlockIds 语义：首次失败，重试即成功）。
 * 仅作用于该块；user_note 等既有内容不会被覆盖（仓储保留）。
 */
export function retryBlock(bookId: string, pageId: string, blockId: string): void {
  const before = readBooks().find((item) => item.id === bookId);
  if (!before || !repairWritable(before)) return;
  if (!writableRunId(before)) return;
  retryBlockInStore(bookId, pageId, blockId);
  void regenerateBlocks(bookId, pageId, [blockId]);
}

/** 整页重生成：仓储复位整页（保留 user_note 内容与块身份）+ 即时逐块重新生成 */
export function regeneratePage(bookId: string, pageId: string): void {
  const before = readBooks().find((item) => item.id === bookId);
  if (!before || !repairWritable(before)) return;
  if (!writableRunId(before)) return;
  regeneratePageInStore(bookId, pageId);
  void regenerateBlocks(bookId, pageId, null);
}

/**
 * 即时块生成（重试/重生成路径）：不注册长执行器，逐块 block-start→block-ready 落库，
 * 全部完成后 page-ready 复核页状态。每步与每条事件前重读最新记录（删除/换 run 后丢弃），
 * seq 由 applyStored 从最新记录现取——与队列写盘共用同一序号空间，不会被当作重复事件丢弃。
 */
async function regenerateBlocks(
  bookId: string,
  pageId: string,
  onlyBlockIds: string[] | null,
): Promise<void> {
  const book0 = readBooks().find((item) => item.id === bookId);
  if (!book0) return;
  const scenario = { ...DEFAULT_RUN_SCENARIO, ...(book0.runScenario ?? {}) };
  const blockDelay = scenario.blockDelayMs ?? DEFAULT_BLOCK_DELAY_MS;
  const plan = planPage(bookId, pageId);
  if (!plan) return;
  for (const planned of plan.blocks) {
    if (onlyBlockIds !== null && !onlyBlockIds.includes(planned.blockId)) continue;
    await delay(blockDelay);
    // 迟到回调校验：书籍仍存在、run 匹配、块仍待生成（非 ready）
    const book = readBooks().find((item) => item.id === bookId);
    if (!book) return; // 删除后丢弃
    const runId = book.run?.runId;
    if (!runId) return;
    if (blockStatusOf(book, pageId, planned.blockId) === 'ready') continue;
    applyStored(bookId, runId, { type: 'block-start', pageId, blockId: planned.blockId });
    applyStored(bookId, runId, {
      type: 'block-ready',
      pageId,
      blockId: planned.blockId,
      block: plannedToBlockPayload(planned),
    });
  }
  const book = readBooks().find((item) => item.id === bookId);
  if (!book) return;
  const runId = book.run?.runId;
  if (!runId) return;
  // 页复核：仍有失败块则 partial（page-ready 事件内的派生逻辑负责），否则 ready
  applyStored(bookId, runId, { type: 'page-ready', pageId });
}
