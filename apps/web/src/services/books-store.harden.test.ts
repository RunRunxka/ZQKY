import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  confirmProposal,
  confirmSpine,
  createBook,
  deleteBook,
  getBookPages,
  readBooks,
  setUserNote,
  updateBook,
  type ReplicaBook,
} from './books-store';

/**
 * H1-BOOKS-HARDEN v1：多书共享集合（zhiqikeyuan:books 单键）的并发写入回归。
 *
 * 缺陷模型：本标签页"读快照 → 决策 → 整表回写"期间，另一个标签页写了同一个键。
 * 旧实现会用过期整表把别的书的新内容覆盖掉（丢失更新）。修复为：
 * 写标记（sidecar 键）冲突检测 + 写前重放 + 写后读回校验（有界重试）。
 *
 * 替身说明：第二个写入者由本项目的**真实写入路径**（updateBook）扮演，注入点选择
 * "本标签页第一次读列表之后、写入之前"的读取，等价于另一标签页在这个窗口内完成一次读改写。
 * 这是模型化的并发注入，不是真实第二个浏览器进程。
 */
describe('books-store（共享集合并发写入，HARDEN v1）', () => {
  const BOOKS_KEY = 'zhiqikeyuan:books';

  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('决策期间其他标签页更新了别的书：本次写入重放在最新快照上，两边都不丢', () => {
    const mine = createBook('本标签页的书', '');
    const peer = createBook('另一标签页的书', '旧简介');

    const original = Storage.prototype.getItem;
    let injected = false;
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (
      this: Storage,
      name: string,
    ) {
      const value = original.call(this, name);
      // 第一次读取共享集合之后立刻让"另一个标签页"改它自己的那本书（真实读改写路径）
      if (!injected && name === BOOKS_KEY) {
        injected = true;
        updateBook(peer.id, { description: '另一标签页写入的简介' });
      }
      return value;
    });

    updateBook(mine.id, { description: '本标签页写入的简介' });
    spy.mockRestore();

    expect(injected).toBe(true);
    const after = readBooks();
    // 本标签页的变更落地
    expect(after.find((item) => item.id === mine.id)!.description).toBe('本标签页写入的简介');
    // 另一标签页对其他书的更新没有被整表回写覆盖
    expect(after.find((item) => item.id === peer.id)!.description).toBe('另一标签页写入的简介');
    expect(after).toHaveLength(2);
  });

  it('创建书籍时其他标签页新增的书不被整表覆盖', () => {
    createBook('已有书', '');
    const original = Storage.prototype.getItem;
    let injected = false;
    let peerId = '';
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (
      this: Storage,
      name: string,
    ) {
      const value = original.call(this, name);
      if (!injected && name === BOOKS_KEY) {
        injected = true;
        peerId = createBook('另一标签页新建的书', '').id;
      }
      return value;
    });

    const created = createBook('本标签页新建的书', '');
    spy.mockRestore();

    const after = readBooks();
    expect(after.map((item) => item.id)).toEqual(
      expect.arrayContaining([created.id, peerId, after.find((item) => item.title === '已有书')!.id]),
    );
    expect(after).toHaveLength(3);
  });

  it('删除书籍时其他标签页的书仍保留（不整表丢弃）', () => {
    const doomed = createBook('待删除的书', '');
    const other = createBook('另一标签页保留的书', '');

    const original = Storage.prototype.getItem;
    let injected = false;
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (
      this: Storage,
      name: string,
    ) {
      const value = original.call(this, name);
      if (!injected && name === BOOKS_KEY) {
        injected = true;
        updateBook(other.id, { description: '删除期间的另一处更新' });
      }
      return value;
    });

    const deleted = deleteBook(doomed.id);
    spy.mockRestore();

    expect(deleted).toBe(true);
    const after = readBooks();
    expect(after.map((item) => item.id)).toEqual([other.id]);
    expect(after[0]!.description).toBe('删除期间的另一处更新');
  });

  it('同一本书的连续写入保持单调更新（写后读回校验，不被并发写入卡住）', () => {
    const book = createBook('连写书', '');
    for (let index = 0; index < 4; index += 1) {
      updateBook(book.id, { description: `第 ${index} 次写入` });
    }
    const stored = readBooks().find((item) => item.id === book.id) as ReplicaBook;
    expect(stored.description).toBe('第 3 次写入');
  });

  it('A1 挑刺：笔记写入始终无法落地时返回 false（写后读回校验，不谎报已保存）', () => {
    const book = createBook('笔记落地书', '');
    confirmProposal(book.id);
    confirmSpine(book.id);
    const notePage = getBookPages(book.id)[1]!; // 第 2 页含 user_note 块
    const note = notePage.blocks.find((block) => block.type === 'user_note')!;
    const before = window.localStorage.getItem('zhiqikeyuan:books')!;

    const original = Storage.prototype.setItem;
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (
      this: Storage,
      name: string,
      value: string,
    ) {
      const result = original.call(this, name, value);
      // 每次写入书籍集合后，立刻被"另一标签页"的旧版本整表覆盖（模拟本标签页写入始终不落地）
      if (name === 'zhiqikeyuan:books') original.call(this, name, before);
      return result;
    });
    const saved = setUserNote(book.id, notePage.id, note.id, '这段笔记不会落地');
    spy.mockRestore();

    expect(saved).toBe(false);
    // 收敛重放有界（不无限重试）且未破坏原有数据
    expect(JSON.parse(window.localStorage.getItem('zhiqikeyuan:books')!)).toHaveLength(1);
    const storedNote = getBookPages(book.id)
      .find((page) => page.id === notePage.id)!
      .blocks.find((block) => block.id === note.id)!;
    expect(storedNote.content).toBe('');
  });
});
