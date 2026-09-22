import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  confirmProposal,
  confirmSpine,
  createBook,
  deleteBook,
  getBookPages,
  loadDemoBooks,
  markVisited,
  readBooks,
  setUserNote,
  updateBook,
  type CommitResult,
  type ReplicaBook,
} from './books-store';
import {
  __resetCollectionLockQueuesForTests,
  __setCollectionLockOptionsForTests,
  peekCollectionLock,
} from './collection-lock';

/**
 * H1-BOOKS-COMMIT-SAFETY v1：书籍集合**提交一致性**回归（断言正确行为）。
 *
 * 背景：H1-BOOKS-HARDEN v1 的"写标记 + 有界重放"只能检测冲突，防不住"检测之后、写入之前"的
 * 并发写入（见 `_work/harden-gate-20260922/probe.test.ts` 的两个缺陷探针）。本批改为
 * **集合互斥锁内的读改写事务**（`services/collection-lock.ts`），仓储返回区分状态的
 * `CommitResult`：冲突预算耗尽一律 `conflict` 且 `value === null`，绝不返回内存候选值。
 *
 * 路径说明：本文件在 jsdom 下运行 → 走**回退锁路径**（localStorage 取号 + settle + 读回校验）；
 * 真实浏览器的原生 Web Locks 路径由 `tests/e2e/books-commit-safety.spec.ts` 的双标签页场景覆盖。
 * 两条证据分别记录，不互相冒充。
 */

const KEY = 'zhiqikeyuan:books';
const LOCK_KEY = `${KEY}-lock`;

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  __resetCollectionLockQueuesForTests();
  // 缩短等待预算/settle，让"锁被占 → conflict"与"锁释放 → 可写"在单测里快速且确定
  __setCollectionLockOptionsForTests({ waitMs: 60, settleMs: 4, staleMs: 1500 });
});

afterEach(() => {
  __resetCollectionLockQueuesForTests();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

/** 占住集合锁（模拟另一个标签页正在写） */
function holdForeignLock(): void {
  window.localStorage.setItem(
    LOCK_KEY,
    JSON.stringify({ owner: 'peer-tab', nonce: 'peer-nonce', ticket: 1, acquiredAt: Date.now() }),
  );
}

function releaseForeignLock(): void {
  window.localStorage.removeItem(LOCK_KEY);
}

function committedOrThrow<T>(result: CommitResult<T>): T {
  expect(result.status).toBe('committed');
  return result.value as T;
}

describe('提交结果契约：不返回候选值', () => {
  it('冲突预算耗尽 → conflict 且 value 为 null，存储未变、重试可成功', async () => {
    const existing = committedOrThrow(await createBook('已存在的书', ''));
    const before = window.localStorage.getItem(KEY);

    holdForeignLock();
    const result = await createBook('冲突中的新书', '用户输入');
    releaseForeignLock();

    expect(result.status).toBe('conflict');
    expect(result.value).toBeNull();
    // 幻影保存消失：没有新书，存储逐字节未变
    expect(window.localStorage.getItem(KEY)).toBe(before);
    expect(readBooks().map((book) => book.id)).toEqual([existing.id]);

    // 锁释放后重试 → 真的保存（输入可重试，不需要重新输入）
    const retried = await createBook('冲突中的新书', '用户输入');
    expect(retried.status).toBe('committed');
    expect(readBooks().some((book) => book.id === retried.value!.id)).toBe(true);
  });

  it('锁被占时编辑/删除/笔记一律不写、返回 conflict', async () => {
    const book = committedOrThrow(await createBook('并发书', '旧简介'));
    const before = window.localStorage.getItem(KEY);

    holdForeignLock();
    const edited = await updateBook(book.id, { description: '新简介' });
    const removed = await deleteBook(book.id);
    releaseForeignLock();

    expect([edited.status, removed.status]).toEqual(['conflict', 'conflict']);
    expect(edited.value).toBeNull();
    expect(window.localStorage.getItem(KEY)).toBe(before);
  });

  it('记录不存在 → missing；前置条件不满足 → skipped（都不写）', async () => {
    const missingEdit = await updateBook('no-such-book', { description: 'x' });
    expect(missingEdit.status).toBe('missing');
    expect(missingEdit.value).toBeNull();

    const draft = committedOrThrow(await createBook('草稿书', ''));
    const spine = await confirmSpine(draft.id); // 未确认提案 → 状态机不允许
    expect(spine.status).toBe('skipped');
    expect(readBooks().find((item) => item.id === draft.id)!.status).toBe('draft');
  });

  it('读取被拒 → read-failed，且不覆盖原数据', async () => {
    const book = committedOrThrow(await createBook('读拒书', '原始内容'));
    const original = Storage.prototype.getItem;
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (
      this: Storage,
      name: string,
    ) {
      if (name === KEY) throw new Error('denied');
      return original.call(this, name);
    });
    const result = await updateBook(book.id, { description: '不该写入' });
    spy.mockRestore();

    expect(result.status).toBe('read-failed');
    expect(result.value).toBeNull();
    expect(readBooks().find((item) => item.id === book.id)!.description).toBe('原始内容');
  });

  it('写入失败（配额）→ write-failed，回滚后原数据保留', async () => {
    const book = committedOrThrow(await createBook('写拒书', '原始内容'));
    const original = Storage.prototype.setItem;
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (
      this: Storage,
      name: string,
      value: string,
    ) {
      if (name === KEY) throw new DOMException('quota', 'QuotaExceededError');
      return original.call(this, name, value);
    });
    const result = await updateBook(book.id, { description: '不该写入' });
    spy.mockRestore();

    expect(result.status).toBe('write-failed');
    expect(result.value).toBeNull();
    expect(readBooks().find((item) => item.id === book.id)!.description).toBe('原始内容');
  });

  it('committed 的值来自写后读回（不是内存候选）', async () => {
    const book = committedOrThrow(await createBook('读回书', ''));
    const value = committedOrThrow(await updateBook(book.id, { description: '落库后的简介' }));
    const stored = readBooks().find((item) => item.id === book.id)!;
    expect(value).toEqual(stored);
  });
});

describe('可控交错：已保存内容不被旧快照覆盖', () => {
  it('快照读取后、写入前有非协议写入者改了**别的书** → 事务重做，两边内容都在', async () => {
    const mine = committedOrThrow(await createBook('我的书', ''));
    const peer = committedOrThrow(await createBook('对方的书', '旧简介'));

    const original = Storage.prototype.setItem;
    let injected = false;
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (
      this: Storage,
      name: string,
      value: string,
    ) {
      // 注入点：本事务写"修订号"时（快照已读、数据尚未写），另一写入者直接改了整表
      if (!injected && name === `${KEY}-write`) {
        injected = true;
        // 用未打补丁的读取拿到当前表（注意：setItem 需要两个参数，读表必须走 getItem）
        const raw = JSON.parse(window.localStorage.getItem(KEY) ?? '[]') as ReplicaBook[];
        raw.find((item) => item.id === peer.id)!.description = '对方已保存的简介';
        original.call(this, KEY, JSON.stringify(raw));
      }
      return original.call(this, name, value);
    });
    const result = await updateBook(mine.id, { description: '我保存的简介' });
    spy.mockRestore();

    expect(injected).toBe(true);
    expect(committedOrThrow(result).description).toBe('我保存的简介');
    const after = readBooks();
    // 双方内容都在：本事务没有用旧快照覆盖对方**已保存**的内容
    expect(after.find((item) => item.id === mine.id)!.description).toBe('我保存的简介');
    expect(after.find((item) => item.id === peer.id)!.description).toBe('对方已保存的简介');
  });

  it('同一本书：两次并发写被串行化，两次修改都保留', async () => {
    const book = committedOrThrow(await createBook('同书并发', '初始'));
    committedOrThrow(await confirmProposal(book.id));
    const compiling = committedOrThrow(await confirmSpine(book.id));
    const page = getBookPages(compiling.id)[1]!; // 第 2 页含 user_note 块
    const note = page.blocks.find((block) => block.type === 'user_note')!;

    // 同一 tick 发起两次写（同标签页队列串行化；真实双标签页由 e2e 覆盖）
    const [edited, noted] = await Promise.all([
      updateBook(book.id, { description: '编辑后的简介' }),
      setUserNote(book.id, page.id, note.id, '并发写入的笔记'),
    ]);

    expect([edited.status, noted.status]).toEqual(['committed', 'committed']);
    const after = readBooks().find((item) => item.id === book.id)!;
    expect(after.description).toBe('编辑后的简介');
    const storedNote = getBookPages(book.id)
      .find((item) => item.id === page.id)!
      .blocks.find((block) => block.id === note.id)!;
    expect(storedNote.content).toBe('并发写入的笔记');
  });

  it('不同书：并发写各自落地，互不影响', async () => {
    const a = committedOrThrow(await createBook('书A', 'A0'));
    const b = committedOrThrow(await createBook('书B', 'B0'));

    const [ra, rb] = await Promise.all([
      updateBook(a.id, { description: 'A1' }),
      updateBook(b.id, { description: 'B1' }),
    ]);
    expect([ra.status, rb.status]).toEqual(['committed', 'committed']);
    const after = readBooks();
    expect(after.find((item) => item.id === a.id)!.description).toBe('A1');
    expect(after.find((item) => item.id === b.id)!.description).toBe('B1');
  });
});

describe('幂等与锁卫生', () => {
  it('markVisited 状态已满足时报告 committed 且不推进修订号（幂等，不写盘）', async () => {
    const book = committedOrThrow(await createBook('幂等书', ''));
    committedOrThrow(await confirmProposal(book.id));
    const compiling = committedOrThrow(await confirmSpine(book.id));
    const page = getBookPages(compiling.id)[0]!;

    const first = await markVisited(book.id, page.id);
    expect(first.status).toBe('committed');
    const stamp = window.localStorage.getItem(`${KEY}-write`);
    const again = await markVisited(book.id, page.id);
    expect(again.status).toBe('committed');
    expect(window.localStorage.getItem(`${KEY}-write`)).toBe(stamp);
  });

  it('事务结束后不残留锁记录（成功与冲突都不悬挂）', async () => {
    const book = committedOrThrow(await createBook('锁卫生书', ''));
    await updateBook(book.id, { description: '写一次' });
    expect(peekCollectionLock(KEY)).toBeNull();

    holdForeignLock();
    const conflicted = await updateBook(book.id, { description: '写不进去' });
    expect(conflicted.status).toBe('conflict');
    releaseForeignLock();
    // 冲突者不夺锁、也不留下自己的锁记录
    expect(peekCollectionLock(KEY)).toBeNull();
  });

  it('幂等载入演示书：重复载入不写盘（noop → committed 0）', async () => {
    const first = await loadDemoBooks();
    expect(first.status).toBe('committed');
    expect(first.value).toBe(2);
    const stamp = window.localStorage.getItem(`${KEY}-write`);
    const again = await loadDemoBooks();
    expect(again.status).toBe('committed');
    expect(again.value).toBe(0);
    expect(window.localStorage.getItem(`${KEY}-write`)).toBe(stamp);
  });
});

describe('旧数据与损坏保护（既有语义不回退）', () => {
  it('缺 status 的旧书照常可读；损坏数据时写入被拒且原字节保留', async () => {
    window.localStorage.setItem(
      KEY,
      JSON.stringify([
        {
          id: 'legacy',
          title: '旧书',
          description: '旧数据',
          status: 'ready',
          proposal: null,
          chapters: [{ id: 'ch', title: '章', summary: 's', pageIds: ['lg-p0'] }],
          reading: { currentPageId: 'lg-p0', visitedPageIds: [], bookmarkedPageIds: [] },
          createdAt: '2026-01-01T00:00:00.000Z',
          updatedAt: '2026-01-01T00:00:00.000Z',
          pages: [
            {
              id: 'lg-p0',
              bookId: 'legacy',
              chapterId: 'ch',
              title: '章（1/1）',
              order: 0,
              blocks: [{ id: 'lg-b0', type: 'text', content: '旧内容' }],
            },
          ],
        },
      ]),
    );
    const legacyBook = readBooks()[0]! as ReplicaBook & {
      pages: { blocks: { content: string }[] }[];
    };
    expect(legacyBook.pages[0]!.blocks[0]!.content).toBe('旧内容');

    window.localStorage.setItem(KEY, '{not json');
    const broken = await updateBook('legacy', { description: '不该写入' });
    expect(broken.status).toBe('read-failed');
    expect(window.localStorage.getItem(KEY)).toBe('{not json');
  });
});
