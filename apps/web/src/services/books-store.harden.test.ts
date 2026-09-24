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
  __getCollectionLockProviderKindForTests,
  __resetCollectionLockQueuesForTests,
  __setCollectionLockProviderForTests,
  createInMemoryCollectionLockProvider,
  type CollectionLockProvider,
} from './collection-lock';

/**
 * H1-BOOKS-COMMIT-SAFETY v1：书籍集合**提交一致性**回归（断言正确行为）。
 *
 * 背景：H1-BOOKS-HARDEN v1 的"写标记 + 有界重放"只能检测冲突，防不住"检测之后、写入之前"的
 * 并发写入（见 `_work/harden-gate-20260922/probe.test.ts` 的两个缺陷探针）。本批改为
 * **集合互斥锁内的读改写事务**（`services/collection-lock.ts`），仓储返回区分状态的
 * `CommitResult`：未取得锁一律 `conflict`（无可用互斥设施则 `unsupported`）且 `value === null`，
 * 绝不返回内存候选值。
 *
 * 路径说明（BOOKS-CS-FOLLOWUP v1 订正）：生产路径**只认原生 Web Locks**，没有原生锁时
 * `withCollectionLock` 返回 `unavailable`（仓储映射为 `unsupported`），不存在 localStorage 回退锁。
 * 本文件在 jsdom 下运行，因此 beforeEach **显式注入** in-process 互斥 provider
 * （`__setCollectionLockProviderForTests`，注入生效由返回值 + kind 断言可见）；
 * 真实浏览器的原生 Web Locks 路径由 `tests/e2e/books-commit-safety.spec.ts` 的双标签页场景覆盖。
 * 两条证据分别记录，不互相冒充。
 */

const KEY = 'zhiqikeyuan:books';
const LOCK_KEY = `${KEY}-lock`;

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  __resetCollectionLockQueuesForTests();
  expect(__setCollectionLockProviderForTests(createInMemoryCollectionLockProvider())).toBe(true);
  expect(__getCollectionLockProviderKindForTests()).toBe('in-memory');
});

afterEach(() => {
  __resetCollectionLockQueuesForTests();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

/**
 * 可挂起的 provider：held 期间 acquire 立即返回 null（等同"另一个标签页一直持着集合锁"），
 * 释放后恢复真实 in-process 互斥。代替旧批次用 localStorage 锁记录伪造的"外部持锁"。
 */
function installGatedLockProvider(): { hold: () => void; release: () => void } {
  const inner = createInMemoryCollectionLockProvider();
  let held = false;
  const provider: CollectionLockProvider = {
    kind: 'in-memory',
    acquire: (name, waitMs) => (held ? Promise.resolve(null) : inner.acquire(name, waitMs)),
  };
  expect(__setCollectionLockProviderForTests(provider)).toBe(true);
  return {
    hold: () => {
      held = true;
    },
    release: () => {
      held = false;
    },
  };
}

function committedOrThrow<T>(result: CommitResult<T>): T {
  expect(result.status).toBe('committed');
  return result.value as T;
}

describe('提交结果契约：不返回候选值', () => {
  it('锁被占（未取得）→ conflict 且 value 为 null，存储未变、释放后重试成功', async () => {
    const existing = committedOrThrow(await createBook('已存在的书', ''));
    const before = window.localStorage.getItem(KEY);

    const gate = installGatedLockProvider();
    gate.hold();
    const result = await createBook('冲突中的新书', '用户输入');
    gate.release();

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

    const gate = installGatedLockProvider();
    gate.hold();
    const edited = await updateBook(book.id, { description: '新简介' });
    const removed = await deleteBook(book.id);
    gate.release();

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

  it('事务结束后不残留锁痕迹（成功与冲突都不悬挂）', async () => {
    const book = committedOrThrow(await createBook('锁卫生书', ''));
    await updateBook(book.id, { description: '写一次' });
    // 生产路径不再使用任何 localStorage 锁记录；成功路径也不留锁痕迹
    expect(window.localStorage.getItem(LOCK_KEY)).toBeNull();

    const gate = installGatedLockProvider();
    gate.hold();
    const conflicted = await updateBook(book.id, { description: '写不进去' });
    gate.release();
    expect(conflicted.status).toBe('conflict');
    // 冲突者不夺锁、也不留下自己的锁记录；释放后同一 provider 仍可正常取得
    expect(window.localStorage.getItem(LOCK_KEY)).toBeNull();
    const recovered = await updateBook(book.id, { description: '释放后写入' });
    expect(recovered.status).toBe('committed');
    expect(window.localStorage.getItem(LOCK_KEY)).toBeNull();
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

describe('缺原生 Web Locks 时不静默降级（F3）', () => {
  it('provider=unavailable：写返回 unsupported、存储逐字节未变、读取与草稿不受影响', async () => {
    const book = committedOrThrow(await createBook('已有书', '原始内容'));
    const before = window.localStorage.getItem(KEY);

    // 模拟"当前浏览器没有原生 Web Locks"（生产默认 provider 此时 kind 即为 unavailable）
    expect(
      __setCollectionLockProviderForTests({ kind: 'unavailable', acquire: () => Promise.resolve(null) }),
    ).toBe(true);
    expect(__getCollectionLockProviderKindForTests()).toBe('unavailable');

    const created = await createBook('不该被创建的书', '');
    const edited = await updateBook(book.id, { description: '不该写入' });
    const removed = await deleteBook(book.id);

    for (const result of [created, edited, removed]) {
      expect(result.status).toBe('unsupported');
      expect(result.value).toBeNull();
      // 原因如实说明"未保存 + 需要 Web Locks + 可在支持的浏览器重试"，不谎报成功
      expect(result.message).toContain('Web Locks');
      expect(result.message).toContain('未保存');
    }
    // 没有幻影写入、没有半写：存储逐字节未变
    expect(window.localStorage.getItem(KEY)).toBe(before);
    // 读取与草稿不受影响（读取路径不取锁）
    const stored = readBooks();
    expect(stored).toHaveLength(1);
    expect(stored[0]!.description).toBe('原始内容');
    expect(stored[0]!.status).toBe('draft');
    expect(stored[0]!.proposal?.chapters.length).toBeGreaterThan(0);
  });

  it('provider 恢复为 in-process 互斥后，同一本书的写入照常提交（不残留不可写状态）', async () => {
    const book = committedOrThrow(await createBook('恢复书', ''));
    expect(
      __setCollectionLockProviderForTests({ kind: 'unavailable', acquire: () => Promise.resolve(null) }),
    ).toBe(true);
    expect((await updateBook(book.id, { description: 'x' })).status).toBe('unsupported');

    expect(__setCollectionLockProviderForTests(createInMemoryCollectionLockProvider())).toBe(true);
    const recovered = await updateBook(book.id, { description: '恢复后写入' });
    expect(recovered.status).toBe('committed');
    expect(readBooks().find((item) => item.id === book.id)!.description).toBe('恢复后写入');
    // 仍然没有任何 localStorage 锁记录（回退锁已删除）
    expect(window.localStorage.getItem(LOCK_KEY)).toBeNull();
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
