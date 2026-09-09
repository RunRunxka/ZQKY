/**
 * 书籍本地仓储（S5-C）。
 * 参考产品书籍由后端流水线（ideation→exploration→spine→compilation，WebSocket 流式）生成；
 * 目标项目无后端，此处为本地确定性模拟：提案/大纲/编译均为模板生成，界面显式标注【模拟】。
 * 状态机（对照参考 book-types.ts BookStatus，去掉 compiling/paused/error 长流水线态）：
 * draft（含提案）→ spine_ready（已确认大纲）→ ready（模拟编译完成，可阅读）→ archived（归档）。
 * 阅读进度（已读/书签/百分比）本地持久化；导出为本地 Markdown。
 */

export type BookStatus = 'draft' | 'spine_ready' | 'ready' | 'archived';
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
}

export interface BookPage {
  id: string;
  bookId: string;
  chapterId: string;
  title: string;
  order: number;
  blocks: BookBlock[];
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
}

const KEY = 'zhiqikeyuan:books';
const QUIZ_KEY = 'zhiqikeyuan:book-quiz-attempts';
const EVENT = 'zqky:books';

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
}

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function readList(): ReplicaBook[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is ReplicaBook =>
        item && typeof item.id === 'string' && typeof item.title === 'string',
    );
  } catch {
    return [];
  }
}

function writeList(list: ReplicaBook[]): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(KEY, JSON.stringify(list));
  notify();
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

function mutateBook(id: string, mutate: (book: ReplicaBook) => ReplicaBook): ReplicaBook | null {
  const list = readList();
  const idx = list.findIndex((book) => book.id === id);
  if (idx === -1) return null;
  list[idx] = { ...mutate(list[idx]!), updatedAt: new Date().toISOString() };
  writeList(list);
  return list[idx]!;
}

// ===== 练习作答与用户笔记（跨会话持久化；修复“作答不持久化”差距） =====

function readQuizList(): BookQuizAttempt[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(QUIZ_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as BookQuizAttempt[]) : [];
  } catch {
    return [];
  }
}

/** 记录一次作答（保留历史；渲染取每个 block 的最新一条） */
export function recordQuizAttempt(input: {
  bookId: string;
  pageId: string;
  blockId: string;
  choice: string;
  correct: boolean;
}): BookQuizAttempt {
  const attempt: BookQuizAttempt = {
    attemptId: uid('att'),
    bookId: input.bookId,
    pageId: input.pageId,
    blockId: input.blockId,
    choice: input.choice,
    correct: input.correct,
    attemptedAt: new Date().toISOString(),
  };
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(QUIZ_KEY, JSON.stringify([...readQuizList(), attempt]));
    notify();
  }
  return attempt;
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
  const book = readInternal().find((item) => item.id === bookId);
  if (!book?.pages) return false;
  const page = book.pages.find((item) => item.id === pageId);
  if (!page) return false;
  const block = page.blocks.find((item) => item.id === blockId);
  if (!block || block.type !== 'user_note') return false;
  block.content = text;
  const idx = readInternal().findIndex((item) => item.id === bookId);
  if (idx === -1) return false;
  writeList(readInternal().map((item) => (item.id === bookId ? book : item)));
  notify();
  return true;
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

function readInternal(): ReplicaBookInternal[] {
  return readList() as ReplicaBookInternal[];
}

/** 同步模拟编译：每章 2 页确定性模板内容（对照参考 compilation，本地无 WS 流水线） */
function compileBook(book: ReplicaBook): { chapters: BookChapter[]; pages: BookPage[] } {
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
      pages.push({
        id: pageId,
        bookId: book.id,
        chapterId: chapter.id,
        title: `${chapter.title}（${offset + 1}/2）`,
        order: pages.length,
        blocks: simulateBlocks(chapter.title, `${chapter.title} · 第${offset + 1}页`),
      });
    }
  });
  return { chapters, pages };
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
  writeList([...list, book]);
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

/** 确认大纲并同步模拟编译（spine_ready → ready）：每章生成 2 页模拟内容 */
export function confirmSpine(bookId: string): ReplicaBook | null {
  return mutateBook(bookId, (book) => {
    if (book.status !== 'spine_ready') return book;
    const { chapters, pages } = compileBook(book);
    const firstPageId = pages[0]?.id ?? null;
    return {
      ...book,
      status: 'ready',
      chapters,
      pages,
      reading: { currentPageId: firstPageId, visitedPageIds: [], bookmarkedPageIds: [] },
    } satisfies ReplicaBookInternal;
  });
}

/** 重建（模拟重新编译）：清空阅读进度后重新生成页面 */
export function rebuildBook(bookId: string): ReplicaBook | null {
  return mutateBook(bookId, (book) => {
    if (book.status !== 'ready' && book.status !== 'archived') return book;
    const { chapters, pages } = compileBook(book);
    const firstPageId = pages[0]?.id ?? null;
    return {
      ...book,
      status: 'ready',
      chapters,
      pages,
      reading: { currentPageId: firstPageId, visitedPageIds: [], bookmarkedPageIds: [] },
    } satisfies ReplicaBookInternal;
  });
}

export function archiveBook(bookId: string, archived: boolean): ReplicaBook | null {
  return mutateBook(bookId, (book) => {
    // 仅就绪/归档态可切换；草稿与大纲态不被归档覆盖
    if (book.status !== 'ready' && book.status !== 'archived') return book;
    return { ...book, status: archived ? 'archived' : 'ready' };
  });
}

export function deleteBook(bookId: string): boolean {
  const list = readList();
  const kept = list.filter((book) => book.id !== bookId);
  if (kept.length === list.length) return false;
  writeList(kept);
  return true;
}

export function updateBook(
  bookId: string,
  patch: { title?: string; description?: string },
): ReplicaBook {
  const list = readList();
  const idx = list.findIndex((book) => book.id === bookId);
  if (idx === -1) throw new BookValidationError('书籍不存在或已被删除。');
  if (patch.title !== undefined) {
    const trimmed = patch.title.trim();
    if (!trimmed) throw new BookValidationError('书名不能为空。');
    if (list.some((book) => book.id !== bookId && book.title === trimmed && book.status !== 'archived'))
      throw new BookValidationError('已存在同名书籍，请换一个书名。');
  }
  list[idx] = {
    ...list[idx]!,
    ...(patch.title !== undefined ? { title: patch.title.trim() } : {}),
    ...(patch.description !== undefined ? { description: patch.description.trim() } : {}),
    updatedAt: new Date().toISOString(),
  };
  writeList(list);
  return list[idx]!;
}

// ===== 阅读进度 =====

export function getBookPages(bookId: string): BookPage[] {
  const book = findBook(bookId) as ReplicaBookInternal | undefined;
  if (!book || !book.pages) return [];
  return [...book.pages].sort((a, b) => a.order - b.order);
}

export function getBookPage(bookId: string, pageId: string): BookPage | null {
  return getBookPages(bookId).find((page) => page.id === pageId) ?? null;
}

/** 打开章节即登记已读（对照参考 markVisited） */
export function markVisited(bookId: string, pageId: string): void {
  mutateBook(bookId, (book) => {
    if (book.reading.visitedPageIds.includes(pageId)) return book;
    return {
      ...book,
      reading: {
        ...book.reading,
        currentPageId: pageId,
        visitedPageIds: [...book.reading.visitedPageIds, pageId],
      },
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

export function exportBookMarkdown(bookId: string): { name: string; content: string } | null {
  const book = findBook(bookId);
  if (!book) return null;
  const lines = [`# ${book.title}`, ''];
  if (book.description) lines.push(`> ${book.description}`, '');
  for (const chapter of book.chapters) {
    lines.push(`## ${chapter.title}`, '');
    for (const pageId of chapter.pageIds) {
      const page = getBookPage(bookId, pageId);
      if (!page) continue;
      lines.push(`### ${page.title}`, '');
      for (const block of page.blocks) {
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

/** 演示书编译产物（确定性内容，供 e2e 与演示使用；loadDemoBooks 时填充） */
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
        blocks: simulateBlocks(chapter.title, `${chapter.title} · 第${offset + 1}页`),
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
  const existing = readInternal();
  const merged = [...existing];
  for (const demo of DEMO_BOOKS) {
    if (merged.some((item) => item.id === demo.id)) continue;
    merged.push(demo.status === 'ready' ? buildDemoReadyBook(demo) : demo);
  }
  writeList(merged as ReplicaBook[]);
}
