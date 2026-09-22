/**
 * 书籍本地仓储（S5-C，H1-BOOKS-PIPELINE v2 扩展）。
 * 参考产品书籍由后端流水线（ideation→exploration→spine→compilation，WebSocket 流式）生成；
 * 目标项目无后端，此处为本地确定性模拟：提案/大纲/编译均为模板生成，界面显式标注【模拟】。
 * 状态机（对照参考 book-types.ts BookStatus 七态）：
 * draft（含提案）→ spine_ready（已确认大纲）→ compiling（逐页逐块模拟编译，执行器见 book-generation.ts）
 * → ready（编译完成，可阅读）→ archived（归档）；
 * compiling 期间可 paused（user/provider）/ error（storage/internal），恢复/重试后回到 compiling。
 * 阅读进度（已读/书签/百分比）本地持久化；导出为本地 Markdown（未完成章节如实标注）。
 *
 * 兼容规则（任务卡 §4.2）：旧四态数据照常可读；缺 status 的页面/块读取期按 ready 派生，不写回；
 * run 缺失表示无历史运行。损坏/结构非法仍走 local-collection 抛错路径，不当作空库、不覆盖。
 */

export type BookStatus = 'draft' | 'spine_ready' | 'compiling' | 'paused' | 'ready' | 'error' | 'archived';
export type PageStatus = 'pending' | 'planning' | 'generating' | 'ready' | 'partial' | 'error';
export type BlockStatus = 'pending' | 'generating' | 'ready' | 'error';
export type BookFailureKind = 'content' | 'storage' | 'internal' | 'unknown';
export type RunPauseKind = 'user' | 'provider';
/**
 * 阅读器 Block 类型（对照参考 BlockRenderer 的 14 类全覆盖）：
 * text/section/callout/quiz/placeholder + code/timeline/flash_cards/figure/
 * user_note/deep_dive/concept_graph/interactive/animation。
 * 其中 interactive/animation/concept_graph/figure 为显式模拟形态（真实生成未接入）。
 */
export type BookBlockType =
  | 'text'
  | 'section'
  | 'callout'
  | 'quiz'
  | 'placeholder'
  | 'code'
  | 'timeline'
  | 'flash_cards'
  | 'figure'
  | 'user_note'
  | 'deep_dive'
  | 'concept_graph'
  | 'interactive'
  | 'animation';

/** 块失败记录（simulated: true —— 本批全部失败均为本地显式模拟，非真实上游故障） */
export interface BlockFailure {
  kind: BookFailureKind;
  message: string;
  retryable: boolean;
  simulated: true;
}

export interface BookBlock {
  id: string;
  type: BookBlockType;
  title?: string;
  /** 文本类为 Markdown；code 为源码；timeline/flash_cards/concept_graph 为行结构文本 */
  content: string;
  /** 代码块语言（code 专用） */
  language?: string;
  /** quiz 专用 */
  quiz?: { options: Record<string, string>; correct: string; explanation?: string };
  /** 生成状态（旧数据缺省，读取期按 ready 派生，不写回） */
  status?: BlockStatus;
  /** 最近一次失败（仅 error 块携带） */
  failure?: BlockFailure;
  /** 内容版本（块重新生成后变化；作答版本关系用） */
  contentVersion?: string;
}

/** 页面运行状态（旧数据缺省，读取期按 ready 派生，不写回） */
export interface BookPage {
  id: string;
  bookId: string;
  chapterId: string;
  title: string;
  order: number;
  blocks: BookBlock[];
  status?: PageStatus;
  /** 整页失败原因（status=error 时） */
  error?: string;
  /** 生成尝试次数 */
  attempts?: number;
  /** 完成时间戳 */
  generatedAt?: string;
}

export interface BookChapter {
  id: string;
  title: string;
  summary: string;
  pageIds: string[];
}

/** 模拟提案（参考 BookProposal 的本地形态） */
export interface BookProposal {
  angle: string;
  audience: string;
  chapters: string[];
}

export interface BookReading {
  currentPageId: string | null;
  visitedPageIds: string[];
  bookmarkedPageIds: string[];
}

/** 模拟执行场景（book-generation.ts 消费；runScenario 随书籍记录持久化以支持刷新续跑） */
export interface BookRunScenario {
  stageDelayMs?: number;
  blockDelayMs?: number;
  failBlockIds?: string[];
  failPages?: number;
  providerPauseAfterPages?: number;
  storageFailureAt?: { pageIndex: number } | null;
  /** 模拟"最终完成状态写入失败"（一次性：已因 storage 失败过的运行不再注入） */
  storageFailureOnFinish?: boolean;
}

/** 运行检查点（对照参考 GenerationOverview/engine 的本地形态；随书籍记录持久化） */
export interface BookRunCheckpoint {
  runId: string;
  status: 'running' | 'paused' | 'stopped' | 'finished' | 'failed';
  stage: 'preparing' | 'compilation';
  cursor: { chapterIndex: number; pageIndex: number; blockIndex: number };
  pauseKind?: RunPauseKind;
  pauseReason?: string;
  failure?: { kind: BookFailureKind; message: string };
  startedAt: number;
  updatedAt: number;
  finishedAt?: number;
}

/** 流水线事件（applyRunEvent 的唯一输入；执行器逐条产出，seq 单调递增） */
export type BookRunEvent =
  | { type: 'run-start' }
  | { type: 'page-start'; chapterIndex: number; pageIndex: number }
  | { type: 'page-planned'; pageId: string; blockIds: string[] }
  | { type: 'block-start'; pageId: string; blockId: string }
  | { type: 'block-ready'; pageId: string; blockId: string; block: BookBlock }
  | { type: 'block-error'; pageId: string; blockId: string; failure: BlockFailure }
  | { type: 'page-ready'; pageId: string }
  | { type: 'page-error'; pageId: string; message: string }
  | { type: 'run-paused'; kind: RunPauseKind; reason: string }
  | { type: 'run-finished' }
  | { type: 'run-failed'; failure: { kind: BookFailureKind; message: string } };

export interface ReplicaBook {
  id: string;
  title: string;
  description: string;
  status: BookStatus;
  proposal: BookProposal | null;
  chapters: BookChapter[];
  reading: BookReading;
  createdAt: string;
  updatedAt: string;
  /** 最近一次运行检查点（缺失表示无历史运行） */
  run?: BookRunCheckpoint | null;
  /** 最近一次运行的模拟场景（缺失表示默认场景） */
  runScenario?: BookRunScenario | null;
}

const KEY = 'zhiqikeyuan:books';
const QUIZ_KEY = 'zhiqikeyuan:book-quiz-attempts';
const EVENT = 'zqky:books';

import { readStrictList, writeStrictList } from './local-collection';

export class BookValidationError extends Error {}

/** 练习作答记录（对照参考 QuizAttempt 的本地形态；持久化，跨会话恢复） */
export interface BookQuizAttempt {
  attemptId: string;
  bookId: string;
  pageId: string;
  blockId: string;
  choice: string;
  correct: boolean;
  attemptedAt: string;
  /** 作答时块的 contentVersion（缺失视为旧数据/首次生成前的块） */
  blockVersion?: string;
}

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function readList(): ReplicaBook[] {
  return readStrictList<ReplicaBook>(KEY).filter(
    (item): item is ReplicaBook =>
      item && typeof item.id === 'string' && typeof item.title === 'string',
  );
}

function notify(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(EVENT));
}

export function readBooks(): ReplicaBook[] {
  return readList();
}

export function subscribeBooks(listener: () => void): () => void {
  const storage = (event: StorageEvent) => {
    if (event.key === KEY || event.key === null) listener();
  };
  window.addEventListener(EVENT, listener);
  window.addEventListener('storage', storage);
  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener('storage', storage);
  };
}

function findBook(id: string): ReplicaBook | undefined {
  return readList().find((book) => book.id === id);
}

/**
 * 共享集合的有界收敛写入。
 *
 * 背景：书籍列表是**所有标签页共用的一个存储键**，直接"读过就写"会在"本标签页决策期间
 * 别的标签页写了集合"时用过期整表把别人的更新覆盖掉（改其他书时最危险）。
 * localStorage 没有 CAS，因此用**写标记（sidecar 键）**做冲突检测：
 * 1. 先读标记 → 读快照 → 计算变更；
 * 2. 写前再读标记：若标记变化（其他标签页在本标签页决策期间写过共享集合），丢弃本次结果，
 *    在新快照上重放变更（有界，最多 3 次）；
 * 3. 写入后再读回：目标书内容确实落地才算成功，否则重放。
 *
 * 如实边界：标记与列表是两个键，写入不是原子的；本协议消除的是"决策期间被并发写入"这一类
 * 丢失更新（窗口从整个变更计算缩短到两次读标记之间），不宣称强原子性。标记读写失败时降级为
 * 单标签页语义（不因标记故障阻断业务写入）。
 *
 * `mutate` 返回 null 表示本次变更不适用（调用方据此走原语义）。
 */
const WRITE_CONVERGE_ATTEMPTS = 3;

/** 写标记键由集合键派生（每个共享集合各有一个标记，互不干扰） */
function writeStampKey(key: string): string {
  return `${key}-write`;
}

interface WriteStamp {
  seq: number;
  writer: string;
}

/** 本标签页身份（与生成租约 owner 同源约定：存 sessionStorage，仅用于区分写入者） */
function tabWriterId(): string {
  if (typeof window === 'undefined') return 'server';
  try {
    const existing = window.sessionStorage.getItem('zhiqikeyuan:books-tab');
    if (existing) return existing;
    const created = `tab-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    window.sessionStorage.setItem('zhiqikeyuan:books-tab', created);
    return created;
  } catch {
    return 'no-session';
  }
}

/** 读写标记：缺失（首次写入）归一化为 {seq:0, writer:''}，这样"首次写入期间被并发写"也能检出 */
function readWriteStamp(collectionKey: string): WriteStamp {
  if (typeof window === 'undefined') return { seq: 0, writer: '' };
  try {
    const raw = window.localStorage.getItem(writeStampKey(collectionKey));
    if (!raw) return { seq: 0, writer: '' };
    const parsed = JSON.parse(raw) as Partial<WriteStamp>;
    if (typeof parsed.seq !== 'number' || typeof parsed.writer !== 'string') {
      return { seq: 0, writer: '' };
    }
    return { seq: parsed.seq, writer: parsed.writer };
  } catch {
    return { seq: 0, writer: '' };
  }
}

function writeWriteStamp(collectionKey: string, stamp: WriteStamp): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(writeStampKey(collectionKey), JSON.stringify(stamp));
  } catch {
    // 标记写入失败：冲突检测降级，业务写入不受影响
  }
}

function writeListConverged<T>(
  key: string,
  mutate: (list: T[]) => T[] | null,
): T[] | null {
  let last: T[] | null = null;
  for (let attempt = 0; attempt < WRITE_CONVERGE_ATTEMPTS; attempt += 1) {
    const stampBefore = readWriteStamp(key);
    const list = readStrictList<T>(key);
    const next = mutate(list);
    if (next === null) return null;
    last = next;
    const stampNow = readWriteStamp(key);
    // 决策期间有其他标签页写过共享集合：本次结果基于过期快照，重放而不是覆盖
    if (stampNow.seq !== stampBefore.seq || stampNow.writer !== stampBefore.writer) {
      continue;
    }
    writeWriteStamp(key, { seq: stampNow.seq + 1, writer: tabWriterId() });
    writeStrictList(key, next);
    notify();
    if (JSON.stringify(readStrictList<T>(key)) === JSON.stringify(next)) return next;
    // 写后被并发覆盖（或写入未落地）：下一轮在新快照上重放本次变更
  }
  return last;
}

function mutateBook(id: string, mutate: (book: ReplicaBook) => ReplicaBook): ReplicaBook | null {
  let mutated: ReplicaBook | null = null;
  const result = writeListConverged<ReplicaBook>(KEY, (list) => {
    const idx = list.findIndex((book) => book.id === id);
    if (idx === -1) return null;
    const next: ReplicaBook = { ...mutate(list[idx]!), updatedAt: new Date().toISOString() };
    mutated = next;
    const out = [...list];
    out[idx] = next;
    return out;
  });
  return result === null ? null : mutated;
}

/**
 * 记录本书的模拟执行器设置（节奏与注入场景）。
 * 续跑/重试/自动续跑沿用同一设置——否则会静默回落到默认节奏，与用户选择不一致。
 */
export function setRunScenario(
  bookId: string,
  scenario: BookRunScenario | null,
): ReplicaBook | null {
  return mutateBook(bookId, (book) => ({ ...book, runScenario: scenario }));
}

// ===== 练习作答与用户笔记（跨会话持久化；修复“作答不持久化”差距） =====

function readQuizList(): BookQuizAttempt[] {
  return readStrictList<BookQuizAttempt>(QUIZ_KEY);
}

/** 记录一次作答（保留历史；渲染取每个 block 的最新一条；blockVersion 记录作答时内容版本） */
export function recordQuizAttempt(input: {
  bookId: string;
  pageId: string;
  blockId: string;
  choice: string;
  correct: boolean;
  blockVersion?: string;
}): BookQuizAttempt {
  const attempt: BookQuizAttempt = {
    attemptId: uid('att'),
    bookId: input.bookId,
    pageId: input.pageId,
    blockId: input.blockId,
    choice: input.choice,
    correct: input.correct,
    attemptedAt: new Date().toISOString(),
    ...(input.blockVersion !== undefined ? { blockVersion: input.blockVersion } : {}),
  };
  if (typeof window !== 'undefined') {
    // 收敛写入：并发追加不会互相覆盖（作答历史是共享集合，两个标签页同时作答不能只留一份）
    writeListConverged<BookQuizAttempt>(QUIZ_KEY, (list) => [...list, attempt]);
  }
  return attempt;
}

/** 作答与块当前内容的版本关系：block 重新生成（contentVersion 变化）后旧作答视为过期 */
export function quizAttemptMatches(
  block: Pick<BookBlock, 'contentVersion'>,
  attempt: Pick<BookQuizAttempt, 'blockVersion'> | null | undefined,
): boolean {
  if (!attempt) return false;
  // 旧数据任一侧缺版本：视为匹配（保留历史可用性，不追溯失效）
  if (attempt.blockVersion === undefined || block.contentVersion === undefined) return true;
  return attempt.blockVersion === block.contentVersion;
}

export function readQuizAttempts(filter?: { bookId?: string; pageId?: string; blockId?: string }): BookQuizAttempt[] {
  let list = readQuizList();
  if (filter?.bookId) list = list.filter((item) => item.bookId === filter.bookId);
  if (filter?.pageId) list = list.filter((item) => item.pageId === filter.pageId);
  if (filter?.blockId) list = list.filter((item) => item.blockId === filter.blockId);
  return list;
}

/** 某 block 的最新作答（无作答返回 null） */
export function latestQuizAttempt(bookId: string, pageId: string, blockId: string): BookQuizAttempt | null {
  const list = readQuizAttempts({ bookId, pageId, blockId });
  return list.length > 0 ? list[list.length - 1]! : null;
}

/** 保存 user_note block 的用户笔记（写回书籍记录内的 block 内容） */
export function setUserNote(bookId: string, pageId: string, blockId: string, text: string): boolean {
  let saved = false;
  // 收敛写入：在最新快照上定位并改写（其他标签页同时写别的书/同一书的其他块都不被整表覆盖）
  const result = writeListConverged<ReplicaBook>(KEY, (list) => {
    const idx = list.findIndex((item) => item.id === bookId);
    if (idx === -1) return null;
    const book = list[idx] as ReplicaBookInternal;
    if (!book.pages) return null;
    const page = book.pages.find((item) => item.id === pageId);
    if (!page) return null;
    const block = page.blocks.find((item) => item.id === blockId);
    if (!block || block.type !== 'user_note') return null;
    const nextBook: ReplicaBookInternal = {
      ...book,
      pages: book.pages.map((item) =>
        item.id !== pageId
          ? item
          : {
              ...item,
              blocks: item.blocks.map((candidate) =>
                candidate.id === blockId ? { ...candidate, content: text } : candidate,
              ),
            },
      ),
      updatedAt: new Date().toISOString(),
    };
    saved = true;
    const out = [...list];
    out[idx] = nextBook;
    return out;
  });
  if (result === null || !saved) return false;
  // 写后读回校验（独立验收 A1 挑刺）：只有笔记真的落到存储才算保存成功，
  // 不拿"回调里置过 saved"当已保存（收敛重放耗尽时写入可能并未落地）。
  return readStoredNote(bookId, pageId, blockId) === text;
}

/** 读取存储中的 user_note 内容（写后校验用；读取失败返回 null） */
function readStoredNote(bookId: string, pageId: string, blockId: string): string | null {
  try {
    const book = readList().find((item) => item.id === bookId) as ReplicaBookInternal | undefined;
    const block = book?.pages
      ?.find((page) => page.id === pageId)
      ?.blocks.find((candidate) => candidate.id === blockId);
    return block?.content ?? null;
  } catch {
    return null;
  }
}

// ===== 模拟生成（确定性模板，显式标注） =====

function simulateProposal(title: string, description: string): BookProposal {
  const theme = title.trim() || '新主题';
  return {
    angle: `围绕「${theme}」组织循序渐进的学习章节（模拟提案：本地模板生成，不调用模型）。`,
    audience: description.trim() || '希望系统学习该主题的学生',
    chapters: [`${theme}是什么`, `${theme}的核心概念`, `${theme}的常见问题`, `${theme}的练习与巩固`],
  };
}

function simulateBlocks(chapterTitle: string, pageTitle: string): BookBlock[] {
  const blocks: BookBlock[] = [
    {
      id: uid('blk'),
      type: 'section',
      title: chapterTitle,
      content: `本节围绕「${pageTitle}」展开（模拟生成内容，用于验证阅读器结构与进度，不代表模型产出）。`,
    },
    {
      id: uid('blk'),
      type: 'text',
      content: `## ${pageTitle}\n\n- 先看一个具体例子；\n- 再理解定义与依据；\n- 最后完成本页小练习。\n\n（模拟生成）`,
    },
    {
      id: uid('blk'),
      type: 'callout',
      title: '学习提示',
      content: '把本页要点用自己的话复述一遍，再进入下一页（模拟生成）。',
    },
    {
      id: uid('blk'),
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
  // 第二页补充参考其余 block 品类的模拟演示形态（真实生成未接入，内容为模板样例）
  if (pageTitle.endsWith('第2页')) {
    blocks.push(
      {
        id: uid('blk'),
        type: 'code',
        title: '示例代码（模拟生成）',
        language: 'python',
        content: 'def solve(x):\n    # 模拟示例：两倍\n    return x * 2\n\nprint(solve(21))',
      },
      {
        id: uid('blk'),
        type: 'timeline',
        title: '学习路径时间线（模拟生成）',
        content: [
          '第 1 步 :: 认识基本概念',
          '第 2 步 :: 完成第一组练习',
          '第 3 步 :: 综合应用与复述',
        ].join('\n'),
      },
      {
        id: uid('blk'),
        type: 'flash_cards',
        title: '记忆卡（点击翻面；模拟生成）',
        content: ['本页的关键词是什么？ :: 参考本页 section 标题', '下一页要做什么？ :: 完成综合练习'].join('\n'),
      },
      {
        id: uid('blk'),
        type: 'deep_dive',
        title: '深入探究（展开查看；模拟生成）',
        content: '扩展阅读方向：把本页概念与生活实例对照，尝试向别人讲解一遍（模拟生成）。',
      },
      {
        id: uid('blk'),
        type: 'figure',
        title: '插图位（模拟占位）',
        content: '真实图像生成/上传未接入；此处保留图注结构。',
      },
      {
        id: uid('blk'),
        type: 'concept_graph',
        title: '概念关联（模拟静态展示）',
        content: [`${chapterTitle} - ${pageTitle}`, `${pageTitle} - 练习巩固`].join('\n'),
      },
      {
        id: uid('blk'),
        type: 'user_note',
        title: '我的笔记（本地保存）',
        content: '',
      },
      {
        id: uid('blk'),
        type: 'interactive',
        title: '互动组件（显式模拟占位）',
        content: '真实互动课件生成未接入；本块仅保留前端占位与说明。',
      },
      {
        id: uid('blk'),
        type: 'animation',
        title: '动画演示（显式模拟占位）',
        content: '真实教学动画生成未接入；本块仅保留前端占位与说明。',
      },
    );
  }
  return blocks;
}

/** 存储页面与章节归属：页面不单独入库，编译产物内联在书籍记录的 pages */
interface ReplicaBookInternal extends ReplicaBook {
  pages?: BookPage[];
}

/** 构建一页的 pending 块骨架：块 id/类型/quiz 结构在规划期确定，内容暂空，由执行器经 block-ready 填充 */
function planPageBlocks(chapterTitle: string, pageTitle: string): BookBlock[] {
  return simulateBlocks(chapterTitle, pageTitle).map((block) => ({
    id: block.id,
    type: block.type,
    ...(block.title !== undefined ? { title: block.title } : {}),
    content: '',
    ...(block.language !== undefined ? { language: block.language } : {}),
    ...(block.quiz !== undefined ? { quiz: block.quiz } : {}),
    status: 'pending' as BlockStatus,
  }));
}

/**
 * 建章节 + 页面骨架（对照参考 compile spine 后的 pending 页/块）：
 * 每章 2 页确定性结构，页/块初始 pending；内容由执行器（book-generation.ts）经事件逐块落库。
 */
function buildBookSkeleton(book: ReplicaBook): { chapters: BookChapter[]; pages: BookPage[] } {
  const chapterTitles =
    book.proposal?.chapters ?? (book.chapters.length > 0 ? book.chapters.map((c) => c.title) : []);
  const chapters: BookChapter[] = chapterTitles.map((title) => ({
    id: uid('ch'),
    title,
    summary: `${title} 章节小结（模拟生成）。`,
    pageIds: [],
  }));
  const pages: BookPage[] = [];
  chapters.forEach((chapter) => {
    for (let offset = 0; offset < 2; offset += 1) {
      const pageId = uid('pg');
      chapter.pageIds.push(pageId);
      const pageTitle = `${chapter.title} · 第${offset + 1}页`;
      pages.push({
        id: pageId,
        bookId: book.id,
        chapterId: chapter.id,
        title: `${chapter.title}（${offset + 1}/2）`,
        order: pages.length,
        blocks: planPageBlocks(chapter.title, pageTitle),
        status: 'pending',
      });
    }
  });
  return { chapters, pages };
}

/** 定位页（读取最新记录；不缓存整本快照） */
function findPage(
  book: ReplicaBookInternal,
  pageId: string,
): { page: BookPage; pageIndex: number } | null {
  if (!book.pages) return null;
  const pageIndex = book.pages.findIndex((page) => page.id === pageId);
  if (pageIndex === -1) return null;
  return { page: book.pages[pageIndex]!, pageIndex };
}

function pageBlockStatuses(page: BookPage): BlockStatus[] {
  return page.blocks.map((block) => block.status ?? 'ready');
}

/**
 * 由块状态派生页状态（`page-ready` 事件的唯一判定）：
 * - 全部块 ready → ready（**唯一**的 ready 路径：只要还有 pending/generating 块就不可能判成 ready）；
 * - 存在 error 块 → partial（局部块失败，其余块可用；partial 刻意计入"完成"，对照 engine.py:110-118）；
 * - 仍有 pending/generating 块（块事件尚未落库的并发窗口）→ 保持"生成中"，不谎报完成；
 * - 无块 → 沿用调用方给定的页级兜底（骨架页/旧数据兼容）。
 */
function derivePageStatus(page: BookPage, fallback: PageStatus): PageStatus {
  const statuses = pageBlockStatuses(page);
  if (statuses.length === 0) return fallback;
  if (statuses.every((status) => status === 'ready')) return 'ready';
  if (statuses.some((status) => status === 'error')) return 'partial';
  return 'generating';
}

// ===== 业务操作 =====

export function createBook(title: string, description: string): ReplicaBook {
  const trimmed = title.trim();
  if (!trimmed) throw new BookValidationError('书名不能为空。');
  if (trimmed.length > 80) throw new BookValidationError('书名过长（不超过 80 字）。');
  const list = readList();
  if (list.some((book) => book.title === trimmed && book.status !== 'archived'))
    throw new BookValidationError('已存在同名书籍，请换一个书名。');
  const now = new Date().toISOString();
  const book: ReplicaBookInternal = {
    id: uid('bk'),
    title: trimmed,
    description: description.trim(),
    status: 'draft',
    proposal: simulateProposal(trimmed, description),
    chapters: [],
    reading: { currentPageId: null, visitedPageIds: [], bookmarkedPageIds: [] },
    createdAt: now,
    updatedAt: now,
  };
  // 收敛写入：其他标签页在本次创建期间新增的书不得被整表回写覆盖；重名在同一快照上复检
  const written = writeListConverged<ReplicaBook>(KEY, (current) => {
    if (current.some((item) => item.title === trimmed && item.status !== 'archived')) return null;
    return [...current, book];
  });
  if (written === null) throw new BookValidationError('已存在同名书籍，请换一个书名。');
  return book;
}

/** 确认提案（draft → spine_ready）：大纲按提案章节登记，尚未编译页面 */
export function confirmProposal(bookId: string): ReplicaBook | null {
  return mutateBook(bookId, (book) => {
    if (book.status !== 'draft' || !book.proposal) return book;
    return {
      ...book,
      status: 'spine_ready',
      chapters: book.proposal.chapters.map((title) => ({
        id: uid('ch'),
        title,
        summary: `${title} 章节小结（模拟生成）。`,
        pageIds: [],
      })),
    };
  });
}

/**
 * 确认大纲（spine_ready → compiling）：建章节+页面骨架（页/块 pending），写 run 检查点，
 * 清阅读进度（语义同旧版）。实际内容生成由执行器（book-generation.ts startRun）经事件推进。
 */
export function confirmSpine(bookId: string): ReplicaBook | null {
  return mutateBook(bookId, (book) => {
    if (book.status !== 'spine_ready') return book;
    const { chapters, pages } = buildBookSkeleton(book);
    const firstPageId = pages[0]?.id ?? null;
    const now = Date.now();
    const internal = book as ReplicaBookInternal;
    return {
      ...book,
      status: 'compiling',
      chapters,
      pages,
      reading: { currentPageId: firstPageId, visitedPageIds: [], bookmarkedPageIds: [] },
      run: {
        runId: uid('run'),
        status: 'running',
        stage: 'preparing',
        cursor: { chapterIndex: 0, pageIndex: 0, blockIndex: 0 },
        startedAt: now,
        updatedAt: now,
      },
      ...(internal.runScenario ? { runScenario: internal.runScenario } : {}),
    } satisfies ReplicaBookInternal;
  });
}

/**
 * 重建（模拟重新编译）：清空阅读进度后重建页面骨架并重新进入 compiling。
 * 允许从 ready/archived（旧语义）以及中断残留的 paused/error 重建。
 */
export function rebuildBook(bookId: string): ReplicaBook | null {
  return mutateBook(bookId, (book) => {
    if (
      book.status !== 'ready' &&
      book.status !== 'archived' &&
      book.status !== 'paused' &&
      book.status !== 'error'
    ) {
      return book;
    }
    const { chapters, pages } = buildBookSkeleton(book);
    const firstPageId = pages[0]?.id ?? null;
    const now = Date.now();
    return {
      ...book,
      status: 'compiling',
      chapters,
      pages,
      reading: { currentPageId: firstPageId, visitedPageIds: [], bookmarkedPageIds: [] },
      run: {
        runId: uid('run'),
        status: 'running',
        stage: 'preparing',
        cursor: { chapterIndex: 0, pageIndex: 0, blockIndex: 0 },
        startedAt: now,
        updatedAt: now,
      },
      runScenario: null,
    } satisfies ReplicaBookInternal;
  });
}

export function archiveBook(bookId: string, archived: boolean): ReplicaBook | null {
  return mutateBook(bookId, (book) => {
    // 仅就绪/归档态可切换；草稿、大纲、编译中、暂停、失败态不被归档覆盖
    if (book.status !== 'ready' && book.status !== 'archived') return book;
    return { ...book, status: archived ? 'archived' : 'ready' };
  });
}

export function deleteBook(bookId: string): boolean {
  let deleted = false;
  // 收敛写入：删除一本书不得连带回写覆盖其他标签页刚写入的其他书
  writeListConverged<ReplicaBook>(KEY, (list) => {
    const kept = list.filter((book) => book.id !== bookId);
    if (kept.length === list.length) return null;
    deleted = true;
    return kept;
  });
  return deleted;
}

export function updateBook(
  bookId: string,
  patch: { title?: string; description?: string },
): ReplicaBook {
  let updated: ReplicaBook | null = null;
  const result = writeListConverged<ReplicaBook>(KEY, (list) => {
    const idx = list.findIndex((book) => book.id === bookId);
    if (idx === -1) throw new BookValidationError('书籍不存在或已被删除。');
    if (patch.title !== undefined) {
      const trimmed = patch.title.trim();
      if (!trimmed) throw new BookValidationError('书名不能为空。');
      if (
        list.some(
          (book) => book.id !== bookId && book.title === trimmed && book.status !== 'archived',
        )
      )
        throw new BookValidationError('已存在同名书籍，请换一个书名。');
    }
    updated = {
      ...list[idx]!,
      ...(patch.title !== undefined ? { title: patch.title.trim() } : {}),
      ...(patch.description !== undefined ? { description: patch.description.trim() } : {}),
      updatedAt: new Date().toISOString(),
    };
    const out = [...list];
    out[idx] = updated;
    return out;
  });
  if (result === null || !updated) throw new BookValidationError('书籍不存在或已被删除。');
  return updated;
}

// ===== 生成流水线仓储（H1-BOOKS-PIPELINE v2；唯一写入口 applyRunEvent） =====

/** 事件已见序号（迟到/重复丢弃依据）：落在 run.lastSeq（未入合同字段，内部使用） */
interface RunSeqMemo {
  lastSeq?: number;
}
const RUN_SEQ_FIELD = 'lastSeq';

function readRunSeq(book: ReplicaBookInternal): number {
  const memo = (book.run as unknown as RunSeqMemo | undefined) ?? undefined;
  return memo?.[RUN_SEQ_FIELD] ?? 0;
}

function withRun(
  book: ReplicaBookInternal,
  runId: string,
  patch: (run: BookRunCheckpoint) => BookRunCheckpoint,
): ReplicaBookInternal {
  const run = book.run ?? undefined;
  const next: BookRunCheckpoint = run && run.runId === runId ? patch(run) : patch(emptyRun(runId));
  return { ...book, run: next } as ReplicaBookInternal;
}

function emptyRun(runId: string): BookRunCheckpoint {
  const now = Date.now();
  return {
    runId,
    status: 'running',
    stage: 'preparing',
    cursor: { chapterIndex: 0, pageIndex: 0, blockIndex: 0 },
    startedAt: now,
    updatedAt: now,
  };
}

/**
 * 执行器是否可对本书运行写入（删除后迟到事件在此被丢弃）。
 * 允许 `ready`：已完成书仍可做**页/块级局部修复**（阅读器「强制重新生成」「重试块」就在这个状态下点击），
 * 书籍状态本身不变，由页状态诚实表达"本页正在重新生成"；运行中的整轮推进另有 compiling 前置校验。
 * draft/spine_ready 无骨架，archived 为归档只读，均不接受生成事件。
 */
function runWritable(book: ReplicaBookInternal, runId: string): boolean {
  if (book.run?.runId !== runId) return false;
  return (
    book.status === 'compiling' ||
    book.status === 'paused' ||
    book.status === 'error' ||
    book.status === 'ready'
  );
}

/**
 * 唯一写入口：校验 bookId + runId + seq（重复/迟到事件忽略并返回当前记录）。
 * 所有写入遵循"读取最新 → 局部改 → 写回"，生成期间新增的笔记/书签/阅读进度不动。
 */
export function applyRunEvent(
  bookId: string,
  runId: string,
  event: BookRunEvent,
  seq = 0,
): ReplicaBook | null {
  return mutateBook(bookId, (rawBook) => {
    const book = rawBook as ReplicaBookInternal;
    if (!runWritable(book, runId)) return book;
    if (seq > 0 && seq <= readRunSeq(book)) return book; // 重复/迟到：忽略
    const next = applyEventToBook(book, runId, event);
    if (seq > 0) {
      (next.run as unknown as RunSeqMemo)[RUN_SEQ_FIELD] = seq;
    }
    return next;
  });
}

function touchRun(run: BookRunCheckpoint, extra?: Partial<BookRunCheckpoint>): BookRunCheckpoint {
  return { ...run, ...extra, updatedAt: Date.now() };
}

/**
 * 补建运行检查点（**仅当本书没有 run 时**写入，已有记录原样返回）。
 *
 * 用途：演示书与旧四态就绪书（`status: 'ready'`）从没有过 run，而执行器的页/块级修复
 * （`retryBlock` / `regeneratePage`）以 runId 作为写入容器的前提——没有 run 时那两处入口
 * 会静默无操作（按钮可点但什么都没发生）。此处补一个只作事件容器用的检查点：
 * 书本身是否还在生成由 `status` 决定，检查点只反映"这本书是否已经跑过一轮"。
 * 不改变书籍状态、阅读进度、页面/块内容；compiling 书补 'running'，其余补 'finished'（已完成一轮）。
 */
export function ensureBookRun(bookId: string): ReplicaBook | null {
  return mutateBook(bookId, (rawBook) => {
    const book = rawBook as ReplicaBookInternal;
    if (book.run?.runId) return book;
    const now = Date.now();
    const compiling = book.status === 'compiling';
    return {
      ...book,
      run: {
        runId: uid('run'),
        status: compiling ? 'running' : 'finished',
        stage: 'compilation',
        cursor: { chapterIndex: 0, pageIndex: 0, blockIndex: 0 },
        startedAt: now,
        updatedAt: now,
        ...(compiling ? {} : { finishedAt: now }),
      },
    } satisfies ReplicaBookInternal;
  });
}

function applyEventToBook(
  book: ReplicaBookInternal,
  runId: string,
  event: BookRunEvent,
): ReplicaBookInternal {
  switch (event.type) {
    case 'run-start':
      return withRun(book, runId, (run) => touchRun(run, { status: 'running', stage: 'compilation' }));
    case 'page-start':
      return withRun(book, runId, (run) =>
        touchRun(run, {
          status: 'running',
          stage: 'compilation',
          cursor: {
            chapterIndex: event.chapterIndex,
            pageIndex: event.pageIndex,
            blockIndex: 0,
          },
        }),
      );
    case 'page-planned': {
      const found = findPage(book, event.pageId);
      if (!found) return book;
      const pages = [...book.pages!];
      // 块骨架按事件携带的 blockIds 集合对齐（不重排，仅复位登记块状态；多余块保持原样）
      const planned = new Set(event.blockIds);
      pages[found.pageIndex] = {
        ...found.page,
        status: 'planning',
        blocks: found.page.blocks.map((block) =>
          planned.has(block.id)
            ? { ...block, status: 'pending' as BlockStatus, failure: undefined }
            : block,
        ),
      };
      return withRun({ ...book, pages }, runId, (run) => touchRun(run));
    }
    case 'block-start': {
      const found = findPage(book, event.pageId);
      if (!found) return book;
      const pages = [...book.pages!];
      const blocks = [...found.page.blocks];
      const blockIndex = blocks.findIndex((block) => block.id === event.blockId);
      if (blockIndex !== -1) {
        blocks[blockIndex] = { ...blocks[blockIndex]!, status: 'generating' };
      }
      pages[found.pageIndex] = { ...found.page, blocks, status: 'generating' };
      return withRun({ ...book, pages }, runId, (run) =>
        touchRun(run, { cursor: { ...run.cursor, blockIndex: Math.max(blockIndex, 0) } }),
      );
    }
    case 'block-ready': {
      const found = findPage(book, event.pageId);
      if (!found) return book;
      const pages = [...book.pages!];
      const blocks = [...found.page.blocks];
      const blockIndex = blocks.findIndex((block) => block.id === event.blockId);
      if (blockIndex !== -1) {
        const current = blocks[blockIndex]!;
        blocks[blockIndex] = {
          // 事件载荷先行，但保留本地用户已写入的 user_note 内容与既有 quiz 结构（防覆盖）
          ...event.block,
          id: current.id, // 块身份不变，只替换内容载荷
          type: current.type,
          ...(current.type === 'user_note' ? { content: current.content } : {}),
          ...(current.quiz !== undefined ? { quiz: current.quiz } : {}),
          status: 'ready',
          failure: undefined,
        };
      }
      pages[found.pageIndex] = { ...found.page, blocks, status: 'generating' };
      return withRun({ ...book, pages }, runId, (run) => touchRun(run));
    }
    case 'block-error': {
      const found = findPage(book, event.pageId);
      if (!found) return book;
      const pages = [...book.pages!];
      const blocks = [...found.page.blocks];
      const blockIndex = blocks.findIndex((block) => block.id === event.blockId);
      if (blockIndex !== -1) {
        blocks[blockIndex] = { ...blocks[blockIndex]!, status: 'error', failure: event.failure };
      }
      pages[found.pageIndex] = { ...found.page, blocks, status: 'generating' };
      return withRun({ ...book, pages }, runId, (run) => touchRun(run));
    }
    case 'page-ready': {
      const found = findPage(book, event.pageId);
      if (!found) return book;
      const pages = [...book.pages!];
      pages[found.pageIndex] = {
        ...found.page,
        status: derivePageStatus(found.page, 'ready'),
        generatedAt: new Date().toISOString(),
        error: undefined,
      };
      return withRun({ ...book, pages }, runId, (run) => touchRun(run));
    }
    case 'page-error': {
      const found = findPage(book, event.pageId);
      if (!found) return book;
      const pages = [...book.pages!];
      pages[found.pageIndex] = {
        ...found.page,
        status: 'error',
        error: event.message,
        attempts: (found.page.attempts ?? 0) + 1,
      };
      return withRun({ ...book, pages }, runId, (run) => touchRun(run));
    }
    case 'run-paused':
      return withRun(
        { ...book, status: 'paused' } as ReplicaBookInternal,
        runId,
        (run) =>
          touchRun(run, {
            status: 'paused' as const,
            pauseKind: event.kind,
            pauseReason: event.reason,
          }),
      );
    case 'run-finished':
      // 收尾事件只标记"执行器已走完全部页"；书籍是否 ready 由 finishBookRun 统一判定
      // （仍有 pending/planning/generating/error 页 → 保持 compiling = 已中断），
      // 避免事件路径抢先置 ready、绕过"未完成页不得显示已完成"的规则。
      return withRun(book, runId, (run) =>
        touchRun(run, { status: 'finished' as const, finishedAt: Date.now() }),
      );
    case 'run-failed':
      return withRun(
        { ...book, status: 'error' } as ReplicaBookInternal,
        runId,
        (run) =>
          touchRun(run, {
            status: 'failed' as const,
            failure: event.failure,
            finishedAt: Date.now(),
          }),
      );
    default:
      return book;
  }
}

/** 用户/模拟供应商暂停：→ paused；正在生成的页/块复位 pending（对照参考 pause 复位语义） */
export function pauseBookRun(
  bookId: string,
  kind: RunPauseKind,
  reason: string,
): ReplicaBook | null {
  return mutateBook(bookId, (rawBook) => {
    const book = rawBook as ReplicaBookInternal;
    if (book.status !== 'compiling') return book;
    const pages = (book.pages ?? []).map((page) => {
      if (page.status === 'planning' || page.status === 'generating') {
        return {
          ...page,
          status: 'pending' as PageStatus,
          blocks: page.blocks.map((block) =>
            block.status === 'generating' ? { ...block, status: 'pending' as BlockStatus } : block,
          ),
        };
      }
      return page;
    });
    const next: ReplicaBookInternal = { ...book, pages, status: 'paused' };
    if (book.run) {
      next.run = touchRun(book.run, {
        status: 'paused',
        pauseKind: kind,
        pauseReason: reason,
      });
    }
    return next;
  });
}

/** 恢复：paused / error(可恢复·storage)→compiling，清除暂停标注，从检查点续跑 */
export function resumeBookRun(bookId: string, runId: string): ReplicaBook | null {
  return mutateBook(bookId, (rawBook) => {
    const book = rawBook as ReplicaBookInternal;
    if (book.run?.runId !== runId) return book;
    if (book.status !== 'paused' && book.status !== 'error' && book.status !== 'compiling') return book;
    const next: ReplicaBookInternal = { ...book, status: 'compiling' };
    if (book.run) {
      next.run = touchRun(book.run, {
        status: 'running',
        pauseKind: undefined,
        pauseReason: undefined,
      });
    }
    return next;
  });
}

/** 整轮失败：→ error（kind storage/internal） */
export function failBookRun(
  bookId: string,
  runId: string,
  failure: { kind: BookFailureKind; message: string },
): ReplicaBook | null {
  return mutateBook(bookId, (rawBook) => {
    const book = rawBook as ReplicaBookInternal;
    if (book.run?.runId !== runId) return book;
    if (book.status !== 'compiling' && book.status !== 'paused' && book.status !== 'error') return book;
    const next: ReplicaBookInternal = { ...book, status: 'error' };
    if (book.run) {
      next.run = touchRun(book.run, {
        status: 'failed',
        failure,
        finishedAt: Date.now(),
      });
    }
    return next;
  });
}

/** 运行结束：全部页就绪（ready/partial；partial 刻意计入完成，对照 engine.py:110-118）→ready；仍有未完成页→保持 compiling（无执行器即"已中断"） */
export function finishBookRun(bookId: string, runId: string): ReplicaBook | null {
  return mutateBook(bookId, (rawBook) => {
    const book = rawBook as ReplicaBookInternal;
    if (book.run?.runId !== runId) return book;
    if (book.status !== 'compiling') return book;
    const pages = book.pages ?? [];
    const hasUnfinished = pages.some((page) => {
      const status = page.status ?? 'ready';
      return status === 'pending' || status === 'planning' || status === 'generating' || status === 'error';
    });
    const next: ReplicaBookInternal = { ...book, status: hasUnfinished ? 'compiling' : 'ready' };
    if (book.run) {
      next.run = touchRun(book.run, {
        status: hasUnfinished ? 'stopped' : 'finished',
        finishedAt: Date.now(),
      });
    }
    return next;
  });
}

/** 单块重试：pending + 清 failure；所在页进入 generating（仅作用于该块，不动其它块与用户内容） */
export function retryBlock(bookId: string, pageId: string, blockId: string): ReplicaBook | null {
  return mutateBook(bookId, (rawBook) => {
    const book = rawBook as ReplicaBookInternal;
    const found = book.pages ? findPage(book, pageId) : null;
    if (!found) return book;
    const pages = [...book.pages!];
    const blocks = [...found.page.blocks];
    const blockIndex = blocks.findIndex((block) => block.id === blockId);
    if (blockIndex === -1) return book;
    blocks[blockIndex] = { ...blocks[blockIndex]!, status: 'pending', failure: undefined };
    pages[found.pageIndex] = { ...found.page, blocks, status: 'generating' };
    return { ...book, pages, ...(book.run ? { run: touchRun(book.run) } : {}) } as ReplicaBookInternal;
  });
}

/**
 * 整页重生成：全部块复位 pending 并清 failure，**保留 user_note 内容与块 id 身份**；页→pending。
 * 由执行器（book-generation.retryBlock/regeneratePage）接管后续逐块生成。
 */
export function regeneratePage(bookId: string, pageId: string): ReplicaBook | null {
  return mutateBook(bookId, (rawBook) => {
    const book = rawBook as ReplicaBookInternal;
    const found = book.pages ? findPage(book, pageId) : null;
    if (!found) return book;
    const pages = [...book.pages!];
    pages[found.pageIndex] = {
      ...found.page,
      status: 'pending',
      error: undefined,
      blocks: found.page.blocks.map((block) => ({
        ...block,
        status: 'pending' as BlockStatus,
        failure: undefined,
      })),
    };
    return { ...book, pages, ...(book.run ? { run: touchRun(book.run) } : {}) } as ReplicaBookInternal;
  });
}

export function getBookPages(bookId: string): BookPage[] {
  const book = findBook(bookId) as ReplicaBookInternal | undefined;
  if (!book || !book.pages) return [];
  return [...book.pages].sort((a, b) => a.order - b.order);
}

export function getBookPage(bookId: string, pageId: string): BookPage | null {
  return getBookPages(bookId).find((page) => page.id === pageId) ?? null;
}

/**
 * 打开章节：currentPageId 始终更新；仅当该页已有内容（ready/partial，或旧数据缺 status）时登记 visited。
 * 未生成页打开只记录"当前在哪页"，不算已读（生成进度与阅读进度分离，任务卡 §5.7）。
 */
export function markVisited(bookId: string, pageId: string): void {
  mutateBook(bookId, (rawBook) => {
    const book = rawBook as ReplicaBookInternal;
    const page = book.pages?.find((item) => item.id === pageId);
    const pageReady = !page || page.status === undefined || page.status === 'ready' || page.status === 'partial';
    const visited = pageReady && !book.reading.visitedPageIds.includes(pageId)
      ? [...book.reading.visitedPageIds, pageId]
      : book.reading.visitedPageIds;
    if (
      book.reading.currentPageId === pageId &&
      visited === book.reading.visitedPageIds
    ) {
      return book; // 无变化不写
    }
    return {
      ...book,
      reading: { ...book.reading, currentPageId: pageId, visitedPageIds: visited },
    };
  });
}

export function toggleBookmark(bookId: string, pageId: string): void {
  mutateBook(bookId, (book) => {
    const marked = book.reading.bookmarkedPageIds.includes(pageId);
    return {
      ...book,
      reading: {
        ...book.reading,
        currentPageId: pageId,
        bookmarkedPageIds: marked
          ? book.reading.bookmarkedPageIds.filter((id) => id !== pageId)
          : [...book.reading.bookmarkedPageIds, pageId],
      },
    };
  });
}

export function readingPercent(book: ReplicaBook): number {
  const total = getBookPages(book.id).length;
  if (total === 0) return 0;
  return Math.round((book.reading.visitedPageIds.length / total) * 100);
}

// ===== 导出与演示 =====

/** 页状态的中文标注（导出用；如实描述，不伪装成完整成书） */
const PAGE_STATUS_EXPORT_LABEL: Record<PageStatus, string> = {
  pending: '排队等待生成',
  planning: '正在规划',
  generating: '生成中',
  ready: '已完成',
  partial: '部分块生成失败',
  error: '生成失败',
};

/** 导出 Markdown：未完成/失败页如实标注，文首注明存在未完成章节（任务卡 §5.7） */
export function exportBookMarkdown(bookId: string): { name: string; content: string } | null {
  const book = findBook(bookId);
  if (!book) return null;
  const internal = book as ReplicaBookInternal;
  const pages = internal.pages ?? [];
  const unfinished = pages.filter((page) => {
    const status = page.status ?? 'ready';
    return status === 'pending' || status === 'planning' || status === 'generating' || status === 'error';
  });
  const lines = [`# ${book.title}`, ''];
  if (book.description) lines.push(`> ${book.description}`, '');
  if (unfinished.length > 0) {
    lines.push(
      `> 注意：本书尚有 ${unfinished.length} 个章节页未生成完成（本地模拟编译，导出时如实标注，不代表完整成书）。`,
      '',
    );
  }
  for (const chapter of book.chapters) {
    lines.push(`## ${chapter.title}`, '');
    for (const pageId of chapter.pageIds) {
      const page = pages.find((item) => item.id === pageId);
      if (!page) continue;
      const status = page.status ?? 'ready';
      if (status !== 'ready' && status !== 'partial') {
        lines.push(`### ${page.title}`, '');
        lines.push(`> 本章尚未生成完成（状态：${PAGE_STATUS_EXPORT_LABEL[status]}${page.error ? `：${page.error}` : ''}）`, '');
        continue;
      }
      lines.push(`### ${page.title}`, '');
      if (status === 'partial') {
        lines.push(`> 本章部分内容生成失败（状态：${PAGE_STATUS_EXPORT_LABEL[status]}），以下仅包含已生成的块。`, '');
      }
      for (const block of page.blocks) {
        if (block.status === 'error' || block.status === 'pending' || block.status === 'generating') {
          const label =
            block.status === 'error'
              ? `块生成失败${block.failure ? `（${block.failure.kind}·本地模拟）` : ''}`
              : block.status === 'generating'
                ? '块生成中'
                : '块排队等待生成';
          lines.push(`> [${label}] ${block.title ?? block.type}`, '');
          continue;
        }
        if (block.type === 'quiz' && block.quiz) {
          lines.push(`**练习：${block.content}**`, '');
          for (const [key, value] of Object.entries(block.quiz.options)) {
            lines.push(`- ${key}. ${value}`);
          }
          lines.push('', `答案：${block.quiz.correct}${block.quiz.explanation ? `（${block.quiz.explanation}）` : ''}`, '');
        } else {
          if (block.title) lines.push(`**${block.title}**`, '');
          lines.push(block.content, '');
        }
      }
    }
  }
  return { name: `${book.title}.md`, content: lines.join('\n') };
}

const DEMO_BOOKS: ReplicaBookInternal[] = [
  {
    id: 'demo-book-fractions',
    title: '分数入门（演示书籍）',
    description: '面向小学生的分数主题书（模拟编译产物，显式演示数据）。',
    status: 'ready',
    proposal: null,
    chapters: [],
    reading: { currentPageId: null, visitedPageIds: [], bookmarkedPageIds: [] },
    createdAt: '2026-09-08T01:00:00.000Z',
    updatedAt: '2026-09-08T01:00:00.000Z',
    pages: [],
  },
  {
    id: 'demo-book-draft',
    title: '修辞手法小册（演示草稿）',
    description: '处于提案阶段的演示书，用于体验确认提案→确认大纲→模拟编译。',
    status: 'draft',
    proposal: {
      angle: '围绕常见修辞手法组织循序渐进的学习章节（模拟提案：本地模板生成，不调用模型）。',
      audience: '小学中高年级学生',
      chapters: ['比喻是什么', '拟人与夸张', '修辞的常见误区', '综合练习'],
    },
    chapters: [],
    reading: { currentPageId: null, visitedPageIds: [], bookmarkedPageIds: [] },
    createdAt: '2026-09-08T01:10:00.000Z',
    updatedAt: '2026-09-08T01:10:00.000Z',
    pages: [],
  },
];

/** 演示书编译产物（确定性内容，供 e2e 与演示使用；loadDemoBooks 时填充；页/块带 ready 状态） */
function buildDemoReadyBook(base: ReplicaBookInternal): ReplicaBookInternal {
  const chapterTitles = ['分数是什么', '比较分数大小'];
  const chapters: BookChapter[] = chapterTitles.map((title, index) => ({
    id: `${base.id}-c${index}`,
    title,
    summary: `${title} 章节小结（模拟生成）。`,
    pageIds: [],
  }));
  const pages: BookPage[] = [];
  chapters.forEach((chapter, index) => {
    for (let offset = 0; offset < 2; offset += 1) {
      const pageId = `${base.id}-p${index * 2 + offset}`;
      chapter.pageIds.push(pageId);
      pages.push({
        id: pageId,
        bookId: base.id,
        chapterId: chapter.id,
        title: `${chapter.title}（${offset + 1}/2）`,
        order: pages.length,
        blocks: simulateBlocks(chapter.title, `${chapter.title} · 第${offset + 1}页`).map((block) => ({
          ...block,
          status: 'ready' as BlockStatus,
        })),
        status: 'ready',
      });
    }
  });
  return {
    ...base,
    chapters,
    pages,
    reading: {
      currentPageId: pages[0]?.id ?? null,
      visitedPageIds: [`${base.id}-p0`],
      bookmarkedPageIds: [`${base.id}-p2`],
    },
  };
}

/** 显式载入演示书籍（幂等）；就绪书含预置阅读进度（1 已读 + 1 书签） */
export function loadDemoBooks(): void {
  // 收敛写入：并入演示书时不得覆盖其他标签页同时写入的其他书
  writeListConverged<ReplicaBook>(KEY, (existing) => {
    const merged = [...existing];
    for (const demo of DEMO_BOOKS) {
      if (merged.some((item) => item.id === demo.id)) continue;
      merged.push(demo.status === 'ready' ? buildDemoReadyBook(demo) : demo);
    }
    return merged;
  });
}
