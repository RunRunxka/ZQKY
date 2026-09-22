import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

/**
 * H1-BOOKS-HARDEN v1：书籍详情首次读取失败（M22-04 原缺陷回归）。
 *
 * 原缺陷：`BooksRoute` 首次 `readBooks()` 失败只 setError、不 setBooks，渲染先命中
 * 「正在读取书籍…」加载分支 → 错误被永久掩盖，也没有重试入口；读取成功也不清旧 error。
 * 现在：错误可见 + 「重试读取」+ 读取成功清除旧错误。
 *
 * 数据隔离：真实 books-store 写入 jsdom 临时存储；读取失败用 Storage.prototype.getItem 注入。
 */

const routerMock = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
const paramsMock = vi.hoisted(() => ({ value: {} as Record<string, string | undefined> }));

vi.mock('next/navigation', () => ({
  useParams: () => paramsMock.value,
  useRouter: () => ({ push: routerMock.push, replace: routerMock.replace }),
}));

// 执行器替身：本用例只验证目录读取分支，不启动生成
vi.mock('@/services/book-generation', () => ({
  getLease: () => null,
  getRun: () => null,
  getRunExit: () => null,
  resumeRun: () => null,
  startRun: () => null,
  stopRun: () => undefined,
}));

import { BooksRoute } from './BooksRoute';
import { createBook } from '@/services/books-store';

const BOOKS_KEY = 'zhiqikeyuan:books';

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  paramsMock.value = {};
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
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('书籍详情首次读取失败（M22-04 缺陷回归）', () => {
  it('错误可见且有重试入口，不被「正在读取书籍…」加载分支掩盖；成功后清除旧错误', async () => {
    const book = (await createBook('读取成功后的书', '')).value!;
    paramsMock.value = { bookId: book.id };

    let denyReads = true;
    const original = Storage.prototype.getItem;
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (
      this: Storage,
      name: string,
    ) {
      if (denyReads && name === BOOKS_KEY) throw new Error('browser: read denied');
      return original.call(this, name);
    });

    render(<BooksRoute />);

    // 错误如实呈现（不再显示"正在读取书籍…"假装进度）
    expect(await screen.findByText(/书籍目录读取失败/)).toBeVisible();
    expect(screen.queryByText('正在读取书籍…')).toBeNull();
    expect(screen.getByRole('button', { name: '重试读取' })).toBeEnabled();
    // 读取失败期间不写入、不清空本地数据
    denyReads = false;
    expect(JSON.parse(window.localStorage.getItem(BOOKS_KEY)!)).toHaveLength(1);

    fireEvent.click(screen.getByRole('button', { name: '重试读取' }));

    expect(await screen.findByText('读取成功后的书')).toBeVisible();
    expect(screen.queryByText(/书籍目录读取失败/)).toBeNull();
    expect(screen.getByText('提案（模拟）')).toBeVisible();
    spy.mockRestore();
  });

  it('目录读取成功但没有这本书：显示"不存在"而不是加载态', async () => {
    paramsMock.value = { bookId: 'missing-book' };
    render(<BooksRoute />);

    expect(await screen.findByText(/书籍「missing-book」不存在/)).toBeVisible();
    expect(screen.queryByText('正在读取书籍…')).toBeNull();
    expect(screen.queryByText(/书籍目录读取失败/)).toBeNull();
  });
});
