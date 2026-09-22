import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

/**
 * H1-BOOKS-PIPELINE I3 组件测试（PageReader 状态闭环）。
 * 服务替身经 vi.mock('@/services/book-generation') 注入（I1 冻结 §4.4 API 形状）；
 * 书籍数据经真实 books-store 键写入 localStorage（隔离测试数据，不触碰真实草稿）。
 * 覆盖：pending/planning/generating/ready/partial/error 六种页状态渲染、块失败卡与重试调用、
 * 页失败面板最多 5 条、未生成页打开不登记已读、作答版本不匹配提示与重新作答、旧数据缺 status 按 ready。
 */

const generationMock = vi.hoisted(() => ({
  retryBlock: vi.fn(),
  regeneratePage: vi.fn(),
  startRun: vi.fn(),
  getRepair: vi.fn(),
}));

vi.mock('@/services/book-generation', () => ({
  retryBlock: (...args: unknown[]) => generationMock.retryBlock(...args),
  regeneratePage: (...args: unknown[]) => generationMock.regeneratePage(...args),
  startRun: (...args: unknown[]) => generationMock.startRun(...args),
  getRepair: (...args: unknown[]) => generationMock.getRepair(...args),
}));

const routerMock = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: routerMock.push, replace: routerMock.replace }),
}));

import { PageReader } from './PageReader';
import type { ReplicaBook } from '@/services/books-store';

const BOOK_KEY = 'zhiqikeyuan:books';
const QUIZ_KEY = 'zhiqikeyuan:book-quiz-attempts';

interface TestBlock {
  id: string;
  type: string;
  title?: string;
  content: string;
  language?: string;
  quiz?: { options: Record<string, string>; correct: string; explanation?: string };
  status?: 'pending' | 'generating' | 'ready' | 'error';
  failure?: { kind: 'content' | 'storage' | 'internal' | 'unknown'; message: string; retryable: boolean; simulated: true };
  contentVersion?: string;
}

interface TestPage {
  id: string;
  bookId: string;
  chapterId: string;
  title: string;
  order: number;
  blocks: TestBlock[];
  status?: 'pending' | 'planning' | 'generating' | 'ready' | 'partial' | 'error';
  error?: string;
}

interface TestBook {
  id: string;
  title: string;
  description: string;
  status: string;
  proposal: null;
  chapters: { id: string; title: string; summary: string; pageIds: string[] }[];
  reading: { currentPageId: string | null; visitedPageIds: string[]; bookmarkedPageIds: string[] };
  createdAt: string;
  updatedAt: string;
  pages?: TestPage[];
}

function textBlock(id: string, content: string, extra: Partial<TestBlock> = {}): TestBlock {
  return { id, type: 'text', content, ...extra };
}

function quizBlock(id: string, extra: Partial<TestBlock> = {}): TestBlock {
  return {
    id,
    type: 'quiz',
    title: '本页小练',
    content: '这一页的主要目标是？',
    quiz: {
      options: { A: '理解本页概念并能举例', B: '背诵全文' },
      correct: 'A',
      explanation: '书籍页面以理解为目标（模拟生成）。',
    },
    ...extra,
  };
}

type FailureKind = 'content' | 'storage' | 'internal' | 'unknown';
function failure(kind: FailureKind, message: string, retryable = true) {
  return { kind, message, retryable, simulated: true as const };
}

function buildBook(overrides: {
  pages: TestPage[];
  pageStatuses?: boolean;
  status?: string;
}): TestBook {
  const chapters = [
    { id: 'ch1', title: '第一章', summary: '章节小结（模拟生成）。', pageIds: overrides.pages.map((page) => page.id) },
  ];
  return {
    id: 'test-book',
    title: '测试书',
    description: '',
    status: overrides.status ?? 'ready',
    proposal: null,
    chapters,
    reading: { currentPageId: null, visitedPageIds: [], bookmarkedPageIds: [] },
    createdAt: '2026-09-20T00:00:00.000Z',
    updatedAt: '2026-09-20T00:00:00.000Z',
    pages: overrides.pages,
  };
}

function seedBook(book: TestBook): void {
  window.localStorage.setItem(BOOK_KEY, JSON.stringify([book]));
}

function readBook(): TestBook {
  const raw = window.localStorage.getItem(BOOK_KEY);
  return (JSON.parse(raw ?? '[]') as TestBook[]).find((item) => item.id === 'test-book')!;
}

function seedAttempt(pageId: string, blockId: string, choice: string, blockVersion?: string): void {
  const existing = JSON.parse(window.localStorage.getItem(QUIZ_KEY) ?? '[]') as unknown[];
  existing.push({
    attemptId: `att-${existing.length + 1}`,
    bookId: 'test-book',
    pageId,
    blockId,
    choice,
    correct: choice === 'A',
    attemptedAt: '2026-09-20T00:00:00.000Z',
    ...(blockVersion !== undefined ? { blockVersion } : {}),
  });
  window.localStorage.setItem(QUIZ_KEY, JSON.stringify(existing));
}

function renderReader(book: TestBook) {
  return render(<PageReader book={book as unknown as ReplicaBook} pageId={book.pages![0]!.id} />);
}

/** 修复结果替身（形状 = H1-BOOKS-HARDEN v1 冻结的 RepairResult） */
function completedRepair(blockIds: string[]) {
  return {
    status: 'completed' as const,
    operationId: 'rep-test',
    bookId: 'test-book',
    pageId: 'p1',
    runId: 'run-1',
    blockIds,
    writtenBlockIds: blockIds,
    droppedWrites: 0,
  };
}

beforeEach(() => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })),
  );
  window.localStorage.clear();
  // HARDEN v1：修复入口返回真实异步结果（Promise<RepairResult>），启动返回执行器句柄
  generationMock.retryBlock.mockImplementation((_bookId: string, _pageId: string, blockId: string) =>
    Promise.resolve(completedRepair([blockId])),
  );
  generationMock.regeneratePage.mockResolvedValue(completedRepair(['b1']));
  generationMock.startRun.mockReturnValue({ bookId: 'test-book', runId: 'run-1', status: 'running' });
  generationMock.getRepair.mockReturnValue(null);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('六种页状态渲染', () => {
  it('pending：排队提示与「生成本章」按钮，点击调用 startRun', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'pending',
          blocks: [],
        },
      ],
    });
    seedBook(book);
    renderReader(book);

    expect(screen.getByText('本章尚未生成，将按顺序生成——也可以现在开始。')).toBeVisible();
    const button = screen.getByRole('button', { name: '生成本章' });
    fireEvent.click(button);
    expect(generationMock.startRun).toHaveBeenCalledWith('test-book', { source: 'user' });
    // 无生成中提示
    expect(screen.queryByText('正在编译本页…')).toBeNull();
    expect(screen.queryByText('正在规划本页的块…')).toBeNull();
    expect(screen.queryByText('正在载入本章…')).toBeNull();
  });

  it('planning：显示「正在规划本页的块…」状态行', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'planning',
          blocks: [],
        },
      ],
    });
    seedBook(book);
    renderReader(book);

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('正在规划本页的块…');
    expect(screen.queryByText('本章尚未生成，将按顺序生成——也可以现在开始。')).toBeNull();
  });

  it('generating：显示「正在编译本页…」，已完成块可见、生成中/排队块占位按状态分开', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'generating',
          blocks: [
            textBlock('b-ready', '已完成的内容（模拟生成）', { status: 'ready' }),
            textBlock('b-pending', '未开始', { status: 'pending', type: 'callout' }),
            textBlock('b-gen', '正在写', { status: 'generating' }),
          ],
        },
      ],
    });
    seedBook(book);
    renderReader(book);

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('正在编译本页…');
    expect(screen.getByText('已完成的内容（模拟生成）')).toBeVisible();
    // 生成中只数真正在写的块；排队的块不得写成"正在生成"（§5.1 生成中/排队两态）
    expect(screen.getAllByText(/^正在生成 \w+ 块…$/)).toHaveLength(1);
    expect(screen.getByText('正在生成 text 块…')).toBeVisible();
    expect(screen.getByText('callout 块等待生成…')).toBeVisible();
    expect(screen.queryByText('正在生成 callout 块…')).toBeNull();
  });

  it('ready：正常内容，无状态行/排队/失败面板', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'ready',
          blocks: [textBlock('b1', '正文内容（模拟生成）'), quizBlock('q1')],
        },
      ],
    });
    seedBook(book);
    renderReader(book);

    expect(screen.getByText('正文内容（模拟生成）')).toBeVisible();
    expect(screen.getByRole('button', { name: 'A. 理解本页概念并能举例' })).toBeVisible();
    expect(screen.queryByText('正在编译本页…')).toBeNull();
    expect(screen.queryByText('本章尚未生成，将按顺序生成——也可以现在开始。')).toBeNull();
    expect(screen.queryByText(/个块失败/)).toBeNull();
    // 模拟标注逐字保留
    expect(
      screen.getByText(
        '本页内容为本地模拟编译产物（显式标注），非模型生成；练习作答与页内笔记本地持久化，跨会话恢复（参考为服务端 attempt）。',
      ),
    ).toBeVisible();
  });

  it('partial：失败块呈现失败卡，其余块可用，页失败面板出现', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'partial',
          blocks: [
            textBlock('b1', '可读内容（模拟生成）'),
            textBlock('b-err', '失败内容', { status: 'error', failure: failure('content', '本地模拟：内容生成返回不可解析结果。') }),
          ],
        },
      ],
    });
    seedBook(book);
    renderReader(book);

    expect(screen.getByText('可读内容（模拟生成）')).toBeVisible();
    expect(screen.getByText('文本 块生成失败')).toBeVisible();
    expect(screen.getByText('1 个块失败')).toBeVisible();
    expect(screen.getByRole('button', { name: '重新生成本页' })).toBeVisible();
  });

  it('error：显示页级失败面板与页错误信息', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'error',
          error: '本地模拟：该页编译失败。',
          blocks: [],
        },
      ],
    });
    seedBook(book);
    renderReader(book);

    expect(screen.getByText('页面生成失败')).toBeVisible();
    expect(screen.getByText('本地模拟：该页编译失败。')).toBeVisible();
    expect(screen.getByRole('button', { name: '重新生成本页' })).toBeVisible();
  });
});

describe('块失败卡与重试调用', () => {
  it('失败卡含分类/不可重试标记/原因，「重试」调用 retryBlock；本地存储类失败不写“供应商错误”', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'partial',
          blocks: [
            textBlock('b-err', '失败内容', {
              status: 'error',
              failure: failure('storage', '写入本地数据失败（存储可能已满）。', false),
            }),
          ],
        },
      ],
    });
    seedBook(book);
    renderReader(book);

    expect(screen.getByText('文本 块生成失败')).toBeVisible();
    expect(screen.getByText('本地存储写入失败 · 不可重试')).toBeVisible();
    expect(screen.getByText('写入本地数据失败（存储可能已满）。')).toBeVisible();
    // 不可重试：按钮禁用，不调用
    const retry = screen.getByRole('button', { name: '重试' });
    expect(retry).toBeDisabled();
    fireEvent.click(retry);
    expect(generationMock.retryBlock).not.toHaveBeenCalled();
  });

  it('可重试失败块点击「重试」调用 retryBlock(bookId, pageId, blockId)', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'partial',
          blocks: [
            textBlock('b-err', '失败内容', {
              status: 'error',
              failure: failure('content', '本地模拟：内容生成返回不可解析结果。'),
            }),
          ],
        },
      ],
    });
    seedBook(book);
    renderReader(book);

    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(generationMock.retryBlock).toHaveBeenCalledWith('test-book', 'p1', 'b-err');
  });
});

describe('页失败面板', () => {
  it('最多列 5 条失败块，超出部分不逐条列出；「重试块」调用 retryBlock', () => {
    const blocks: TestBlock[] = [
      textBlock('b-ok', '可读内容（模拟生成）'),
      ...Array.from({ length: 7 }, (_, i) =>
        textBlock(`b-err-${i}`, '失败', {
          status: 'error',
          failure: failure('content', `本地模拟：第 ${i + 1} 块内容生成失败。`),
        }),
      ),
    ];
    const book = buildBook({
      pages: [
        { id: 'p1', bookId: 'test-book', chapterId: 'ch1', title: '第一章（1/1）', order: 0, status: 'partial', blocks },
      ],
    });
    seedBook(book);
    renderReader(book);

    expect(screen.getByText('7 个块失败')).toBeVisible();
    expect(screen.getAllByRole('button', { name: '重试块' })).toHaveLength(5);
    // 面板最多列 5 条：第 6/7 条不出现在面板列表中（各自的失败卡在正文按块呈现，与面板条数上限分开）
    const panel = document.querySelector('.book-reader-page-failures-list');
    expect(panel?.textContent ?? '').not.toContain('第 6 块内容生成失败。');
    expect(panel?.textContent ?? '').not.toContain('第 7 块内容生成失败。');

    fireEvent.click(screen.getAllByRole('button', { name: '重试块' })[0]!);
    expect(generationMock.retryBlock).toHaveBeenCalledWith('test-book', 'p1', 'b-err-0');
  });

  it('「重新生成本页」调用 regeneratePage', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'partial',
          blocks: [
            textBlock('b-err', '失败内容', { status: 'error', failure: failure('content', '本地模拟失败。') }),
          ],
        },
      ],
    });
    seedBook(book);
    renderReader(book);

    fireEvent.click(screen.getByRole('button', { name: '重新生成本页' }));
    expect(generationMock.regeneratePage).toHaveBeenCalledWith('test-book', 'p1');
  });
});

describe('阅读器工具栏与已读登记', () => {
  it('保留「第 N/M 页」与书签按钮锚点；新增「强制重新生成」调用 regeneratePage', () => {
    const book = buildBook({
      pages: [
        { id: 'p1', bookId: 'test-book', chapterId: 'ch1', title: '第一章（1/2）', order: 0, status: 'ready', blocks: [textBlock('b1', '内容')] },
        { id: 'p2', bookId: 'test-book', chapterId: 'ch1', title: '第一章（2/2）', order: 1, status: 'ready', blocks: [textBlock('b2', '内容二')] },
      ],
    });
    seedBook(book);
    renderReader(book);

    expect(screen.getByText('第 1/2 页')).toBeVisible();
    expect(screen.getByRole('button', { name: '添加书签' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '添加书签' }));
    expect(screen.getByRole('button', { name: '移除书签' })).toBeVisible();
    expect(readBook().reading.bookmarkedPageIds).toEqual(['p1']);

    fireEvent.click(screen.getByRole('button', { name: '强制重新生成' }));
    expect(generationMock.regeneratePage).toHaveBeenCalledWith('test-book', 'p1');
  });

  it('ready 页打开登记已读；未生成页（pending/generating/error）打开只不登记', async () => {
    const readyBook = buildBook({
      pages: [
        { id: 'p1', bookId: 'test-book', chapterId: 'ch1', title: '第一章（1/1）', order: 0, status: 'ready', blocks: [textBlock('b1', '内容')] },
      ],
    });
    seedBook(readyBook);
    const { unmount } = renderReader(readyBook);
    await waitFor(() => expect(readBook().reading.visitedPageIds).toEqual(['p1']));
    unmount();

    for (const status of ['pending', 'generating', 'error'] as const) {
      window.localStorage.clear();
      const pageBook = buildBook({
        pages: [
          {
            id: 'p1',
            bookId: 'test-book',
            chapterId: 'ch1',
            title: '第一章（1/1）',
            order: 0,
            status,
            ...(status === 'error' ? { error: '本地模拟：该页编译失败。' } : {}),
            blocks: [],
          },
        ],
      });
      seedBook(pageBook);
      const rendered = renderReader(pageBook);
      // 等待 effect 执行后断言未登记
      await waitFor(() => expect(screen.getByText('第 1/1 页')).toBeVisible());
      expect(readBook().reading.visitedPageIds).toEqual([]);
      rendered.unmount();
    }
  });
});

describe('作答版本关系', () => {
  it('版本不匹配：不把旧作答显示为新题答案，如实提示并允许重新作答；历史保留', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'ready',
          blocks: [quizBlock('q1', { contentVersion: 'v2' })],
        },
      ],
    });
    seedBook(book);
    // 旧版作答（blockVersion v1，与新题 v2 不匹配）
    seedAttempt('p1', 'q1', 'B', 'v1');
    renderReader(book);

    expect(
      screen.getByText('该题内容已更新；当前显示的是旧版题目的作答记录（旧作答 B 已保留在历史中）。'),
    ).toBeVisible();
    // 未恢复旧作答：选项可点（未禁用），无旧判定文案
    expect(screen.queryByText('回答错误，正确答案 A。')).toBeNull();
    const option = screen.getByRole('button', { name: 'B. 背诵全文' });
    expect(option).toBeEnabled();

    // 重新作答：正常判定并新增历史
    fireEvent.click(screen.getByRole('button', { name: 'A. 理解本页概念并能举例' }));
    expect(screen.getByRole('status', { name: '' })).toHaveTextContent('回答正确。');
    const attempts = JSON.parse(window.localStorage.getItem(QUIZ_KEY) ?? '[]') as { blockId: string; choice: string }[];
    expect(attempts.filter((item) => item.blockId === 'q1')).toHaveLength(2);
  });

  it('版本匹配：恢复最近一次作答为当前题答案', () => {
    const book = buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'ready',
          blocks: [quizBlock('q1', { contentVersion: 'v2' })],
        },
      ],
    });
    seedBook(book);
    seedAttempt('p1', 'q1', 'B', 'v2');
    renderReader(book);

    expect(screen.queryByText(/该题内容已更新/)).toBeNull();
    expect(screen.getByRole('status', { name: '' })).toHaveTextContent('回答错误，正确答案 A。');
  });
});

describe('旧数据兼容', () => {
  it('缺 status 的旧页面/块按 ready 渲染：内容可见、登记已读、无状态行', async () => {
    const book = buildBook({
      pages: [
        { id: 'p1', bookId: 'test-book', chapterId: 'ch1', title: '第一章（1/1）', order: 0, blocks: [textBlock('b1', '旧数据内容（模拟生成）'), quizBlock('q1')] },
      ],
    });
    seedBook(book);
    renderReader(book);

    expect(screen.getByText('旧数据内容（模拟生成）')).toBeVisible();
    expect(screen.queryByText('正在编译本页…')).toBeNull();
    expect(screen.queryByText('本章尚未生成，将按顺序生成——也可以现在开始。')).toBeNull();
    expect(screen.queryByText(/个块失败/)).toBeNull();
    await waitFor(() => expect(readBook().reading.visitedPageIds).toEqual(['p1']));
    // 旧作答（无 blockVersion 字段）按匹配处理：恢复显示
    seedAttempt('p1', 'q1', 'B');
    cleanup();
    const rendered = renderReader(book);
    expect(rendered.getByRole('status', { name: '' })).toHaveTextContent('回答错误，正确答案 A。');
  });
});

describe('归档只读（A3：按钮可点但什么都不发生 = 静默无操作）', () => {
  const ARCHIVED_NOTE =
    '已归档（只读）：生成、重试与重新生成入口已禁用以保持归档内容不被改写；如需继续编辑，请先在书籍列表取消归档。';

  it('归档书（含失败块）：重新生成与重试入口全部禁用，给出同一说明，且不调用执行器', () => {
    const book = buildBook({
      status: 'archived',
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'partial',
          blocks: [
            textBlock('b1', '可读内容（模拟生成）'),
            textBlock('b-err', '失败内容', { status: 'error', failure: failure('content', '本地模拟失败。') }),
          ],
        },
      ],
    });
    seedBook(book);
    renderReader(book);

    expect(screen.getByText(ARCHIVED_NOTE)).toBeVisible();
    const regenerate = screen.getByRole('button', { name: '强制重新生成' });
    const regeneratePageButton = screen.getByRole('button', { name: '重新生成本页' });
    const retry = screen.getByRole('button', { name: '重试' });
    expect(regenerate).toBeDisabled();
    expect(regeneratePageButton).toBeDisabled();
    expect(retry).toBeDisabled();
    fireEvent.click(regenerate);
    fireEvent.click(regeneratePageButton);
    fireEvent.click(retry);
    expect(generationMock.regeneratePage).not.toHaveBeenCalled();
    expect(generationMock.retryBlock).not.toHaveBeenCalled();
    // 归档书仍可读（只读不等于隐藏内容）
    expect(screen.getByText('可读内容（模拟生成）')).toBeVisible();
  });

  it('归档书的未生成页：「生成本章」禁用并说明同一原因', () => {
    const book = buildBook({
      status: 'archived',
      pages: [
        { id: 'p1', bookId: 'test-book', chapterId: 'ch1', title: '第一章（1/1）', order: 0, status: 'pending', blocks: [] },
      ],
    });
    seedBook(book);
    renderReader(book);

    expect(screen.getByText(ARCHIVED_NOTE)).toBeVisible();
    const start = screen.getByRole('button', { name: '生成本章' });
    expect(start).toBeDisabled();
    fireEvent.click(start);
    expect(generationMock.startRun).not.toHaveBeenCalled();
  });
});

describe('HARDEN v1：全局翻页键的输入排除（M22-06 原缺陷回归）', () => {
  function twoPageBook(): TestBook {
    return buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/2）',
          order: 0,
          status: 'ready',
          blocks: [
            textBlock('b1', '第一页正文（模拟生成）'),
            { id: 'b-note', type: 'user_note', title: '我的笔记（本地保存）', content: '', status: 'ready' },
          ],
        },
        {
          id: 'p2',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（2/2）',
          order: 1,
          status: 'ready',
          blocks: [textBlock('b2', '第二页正文（模拟生成）')],
        },
      ],
    });
  }

  it('笔记输入框内 ←/→ 不翻页；普通阅读时 ←/→ 仍然翻页', () => {
    const book = twoPageBook();
    seedBook(book);
    renderReader(book);

    const note = screen.getByLabelText('我的笔记内容');
    note.focus();
    fireEvent.keyDown(note, { key: 'ArrowRight' });
    fireEvent.keyDown(note, { key: 'ArrowLeft' });
    expect(routerMock.push).not.toHaveBeenCalled();

    // 正文上下文（焦点不在输入元素上）：翻页仍然有效
    fireEvent.keyDown(document.body, { key: 'ArrowRight' });
    expect(routerMock.push).toHaveBeenCalledWith('/books/test-book/pages/p2');
    expect(routerMock.push).toHaveBeenCalledTimes(1);
  });

  it('contenteditable、组合输入与修饰键都不触发翻页', () => {
    const book = twoPageBook();
    seedBook(book);
    renderReader(book);

    const editable = document.createElement('div');
    editable.setAttribute('contenteditable', 'true');
    editable.setAttribute('aria-label', '富文本笔记');
    document.body.appendChild(editable);
    fireEvent.keyDown(editable, { key: 'ArrowRight' });
    expect(routerMock.push).not.toHaveBeenCalled();

    // 组合输入进行中（中文输入法用 ←/→ 选字）
    fireEvent.keyDown(document.body, { key: 'ArrowRight', isComposing: true });
    expect(routerMock.push).not.toHaveBeenCalled();

    // 修饰键：Ctrl/Alt/Meta/Shift + 方向键是编辑器/浏览器快捷键
    fireEvent.keyDown(document.body, { key: 'ArrowRight', ctrlKey: true });
    fireEvent.keyDown(document.body, { key: 'ArrowRight', altKey: true });
    fireEvent.keyDown(document.body, { key: 'ArrowRight', metaKey: true });
    fireEvent.keyDown(document.body, { key: 'ArrowRight', shiftKey: true });
    expect(routerMock.push).not.toHaveBeenCalled();

    // 已被其他处理器消费的事件不重复翻页
    const consumed = new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true });
    consumed.preventDefault();
    window.dispatchEvent(consumed);
    expect(routerMock.push).not.toHaveBeenCalled();

    editable.remove();
    fireEvent.keyDown(document.body, { key: 'ArrowRight' });
    expect(routerMock.push).toHaveBeenCalledWith('/books/test-book/pages/p2');
  });
});

describe('HARDEN v1：修复入口的真实异步结果（M22-02 原缺陷回归）', () => {
  function partialBook(): TestBook {
    return buildBook({
      pages: [
        {
          id: 'p1',
          bookId: 'test-book',
          chapterId: 'ch1',
          title: '第一章（1/1）',
          order: 0,
          status: 'partial',
          blocks: [
            textBlock('b1', '可读内容（模拟生成）'),
            textBlock('b-err', '失败内容', { status: 'error', failure: failure('content', '本地模拟失败。') }),
          ],
        },
      ],
    });
  }

  it('重试结果 failure：如实显示原因，不谎报成功', async () => {
    const book = partialBook();
    seedBook(book);
    renderReader(book);

    generationMock.retryBlock.mockResolvedValue({
      ...completedRepair(['b-err']),
      status: 'failed',
      writtenBlockIds: [],
      error: '本地存储写入失败（存储可能已满）；本次修复未完成。',
    });
    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    expect(await screen.findByText(/本地存储写入失败（存储可能已满）/)).toBeVisible();
    expect(screen.getByText(/重新生成未完成/)).toBeVisible();
  });

  it('修复结果为 skipped（不可写入）：同样给出原因，不静默无操作', async () => {
    const book = partialBook();
    seedBook(book);
    renderReader(book);

    generationMock.retryBlock.mockResolvedValue({
      ...completedRepair(['b-err']),
      status: 'skipped',
      writtenBlockIds: [],
      error: '书籍当前状态（archived）不接受页/块修复。',
    });
    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    expect(await screen.findByText(/不接受页\/块修复/)).toBeVisible();
  });

  it('完成：忙态复位且不留下错误提示', async () => {
    const book = partialBook();
    seedBook(book);
    renderReader(book);

    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('button', { name: '重新生成本页' })).toBeEnabled();
    await waitFor(() => expect(screen.queryByText(/重新生成未完成/)).toBeNull());
  });

  it('忙态中重复点击不再发起第二次调用（互斥；真实去重由引擎的同目标复用保证）', async () => {
    const book = partialBook();
    seedBook(book);
    let release: (value: ReturnType<typeof completedRepair>) => void = () => {};
    generationMock.retryBlock.mockImplementation(
      () => new Promise((resolve) => { release = resolve; }),
    );
    renderReader(book);

    const retry = screen.getByRole('button', { name: '重试' });
    fireEvent.click(retry);
    await waitFor(() => expect(generationMock.retryBlock).toHaveBeenCalledTimes(1));
    // 重试中的按钮已进入忙态（disabled + 文案变化），第二次点击不会产生新的调用
    const busy = await screen.findByRole('button', { name: '正在重试…' });
    expect(busy).toBeDisabled();
    fireEvent.click(busy);
    expect(generationMock.retryBlock).toHaveBeenCalledTimes(1);
    release(completedRepair(['b-err']));
    await waitFor(() => expect(screen.queryByText(/重新生成未完成/)).toBeNull());
  });

  it('挂载时若本页已有在途修复，忙态如实恢复（不假装空闲）', () => {
    const book = partialBook();
    seedBook(book);
    generationMock.getRepair.mockReturnValue({
      operationId: 'rep-inflight',
      runId: 'run-1',
      blockIds: ['b-err'],
      writtenBlockIds: [],
    });
    renderReader(book);
    expect(screen.getByRole('button', { name: '强制重新生成' })).toBeDisabled();
    expect(generationMock.getRepair).toHaveBeenCalledWith('test-book', 'p1');
  });

  it('「生成本章」返回空句柄时给出显式原因（不静默无操作）', () => {
    const book = buildBook({
      pages: [
        { id: 'p1', bookId: 'test-book', chapterId: 'ch1', title: '第一章（1/1）', order: 0, status: 'pending', blocks: [] },
      ],
    });
    seedBook(book);
    generationMock.startRun.mockReturnValue(null);
    renderReader(book);

    fireEvent.click(screen.getByRole('button', { name: '生成本章' }));
    expect(generationMock.startRun).toHaveBeenCalledWith('test-book', { source: 'user' });
    expect(screen.getByText(/无法开始生成/)).toBeVisible();
  });
});
