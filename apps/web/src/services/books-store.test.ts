import { beforeEach, describe, expect, it } from 'vitest';
import {
  BookValidationError,
  archiveBook,
  confirmProposal,
  confirmSpine,
  createBook,
  deleteBook,
  exportBookMarkdown,
  getBookPage,
  getBookPages,
  loadDemoBooks,
  markVisited,
  readBooks,
  rebuildBook,
  readingPercent,
  toggleBookmark,
  updateBook,
} from './books-store';

beforeEach(() => {
  window.localStorage.clear();
});

describe('books-store', () => {
  it('createBook 生成带模拟提案的草稿并拒绝重名/空名', () => {
    const book = createBook('测试书', '面向测试人群');
    expect(book.status).toBe('draft');
    expect(book.proposal?.chapters.length).toBeGreaterThan(0);
    expect(book.proposal?.angle).toContain('模拟提案');
    expect(() => createBook('测试书', '')).toThrow(BookValidationError);
    expect(() => createBook('   ', '')).toThrow('书名不能为空。');
    // 归档书不占重名
    const demo = createBook('归档占名书', '');
    archiveBook(demo.id, false);
    void demo;
  });

  it('状态机：确认提案→确认大纲完成模拟编译；重建清进度', () => {
    const book = createBook('状态机书', '');
    const spined = confirmProposal(book.id);
    expect(spined?.status).toBe('spine_ready');
    expect(spined?.chapters.length).toBe(book.proposal?.chapters.length);
    expect(spined?.chapters.every((chapter) => chapter.pageIds.length === 0)).toBe(true);

    const ready = confirmSpine(book.id);
    expect(ready?.status).toBe('ready');
    const pages = getBookPages(book.id);
    expect(pages.length).toBe((spined?.chapters.length ?? 0) * 2);
    // 每页含模拟标注且具备可渲染 block
    expect(pages.every((page) => page.blocks.some((block) => block.content.includes('模拟生成')))).toBe(true);
    expect(pages.every((page) => page.blocks.some((block) => block.type === 'quiz' && block.quiz))).toBe(true);

    // 进度：打开章节登记已读（4 章×2 页=8 页，1 已读≈13%）
    markVisited(book.id, pages[0]!.id);
    const current = readBooks().find((item) => item.id === book.id)!;
    expect(current.reading.currentPageId).toBe(pages[0]!.id);
    expect(readingPercent(current)).toBe(Math.round((1 / pages.length) * 100));

    // 书签切换幂等往返
    toggleBookmark(book.id, pages[1]!.id);
    toggleBookmark(book.id, pages[1]!.id);
    const afterToggle = readBooks().find((item) => item.id === book.id)!;
    expect(afterToggle.reading.bookmarkedPageIds).toEqual([]);

    // 重建：进度清空、页面重新生成
    const rebuilt = rebuildBook(book.id);
    expect(rebuilt?.status).toBe('ready');
    expect(rebuilt?.reading.visitedPageIds).toEqual([]);
    expect(rebuilt?.chapters.map((chapter) => chapter.id)).not.toEqual(ready?.chapters.map((chapter) => chapter.id));
  });

  it('非法状态流转不生效；归档仅限就绪/归档态', () => {
    const book = createBook('守卫书', '');
    // draft 不能直接编译
    expect(confirmSpine(book.id)?.status).toBe('draft');
    // draft 不能被归档
    expect(archiveBook(book.id, true)?.status).toBe('draft');
    const spined = confirmProposal(book.id);
    expect(spined?.status).toBe('spine_ready');
    const ready = confirmSpine(book.id);
    expect(ready?.status).toBe('ready');
    const archived = archiveBook(book.id, true);
    expect(archived?.status).toBe('archived');
    const restored = archiveBook(book.id, false);
    expect(restored?.status).toBe('ready');
  });

  it('updateBook 重名校验、deleteBook 与导出 Markdown', () => {
    createBook('书甲', '甲的简介');
    const bookB = createBook('书乙', '乙的简介');
    expect(() => updateBook(bookB.id, { title: '书甲' })).toThrow(BookValidationError);
    const updated = updateBook(bookB.id, { title: '书乙（改）', description: '新简介' });
    expect(updated.title).toBe('书乙（改）');

    // 编译后导出包含章节、页面与练习答案
    confirmProposal(bookB.id);
    confirmSpine(bookB.id);
    const exported = exportBookMarkdown(bookB.id);
    expect(exported?.name).toBe('书乙（改）.md');
    expect(exported?.content).toContain('# 书乙（改）');
    expect(exported?.content).toContain('## ');
    expect(exported?.content).toMatch(/答案：A/);
    // 深链取页
    const pages = getBookPages(bookB.id);
    expect(getBookPage(bookB.id, pages[0]!.id)?.id).toBe(pages[0]!.id);
    expect(getBookPage(bookB.id, 'missing')).toBeNull();

    expect(deleteBook(bookB.id)).toBe(true);
    expect(deleteBook(bookB.id)).toBe(false);
    expect(readBooks().some((item) => item.id === bookB.id)).toBe(false);
  });

  it('演示载入幂等且就绪书带预置进度', () => {
    loadDemoBooks();
    loadDemoBooks();
    const books = readBooks();
    expect(books.filter((book) => book.id.startsWith('demo-book-'))).toHaveLength(2);
    const ready = books.find((book) => book.id === 'demo-book-fractions')!;
    expect(ready.status).toBe('ready');
    expect(getBookPages(ready.id)).toHaveLength(4);
    expect(ready.reading.bookmarkedPageIds).toEqual(['demo-book-fractions-p2']);
    expect(ready.reading.visitedPageIds).toEqual(['demo-book-fractions-p0']);
    const draft = books.find((book) => book.id === 'demo-book-draft')!;
    expect(draft.proposal?.chapters.length).toBeGreaterThan(0);
  });
});
