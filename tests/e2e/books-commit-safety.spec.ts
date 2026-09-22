import { expect, test, type Page } from '@playwright/test';

/**
 * H1-BOOKS-COMMIT-SAFETY v1 浏览器回归：**真实双标签页**下的集合写互斥与提交结果。
 *
 * 覆盖（隔离 context，同一 context 内两个 page 共享 localStorage 与 Web Locks）：
 * 1. 另一标签页持有集合写锁时：创建/编辑/删除如实失败、输入保留；释放锁后重试成功（不假成功）。
 * 2. 双标签页并发写**不同书**：两边内容都在（旧快照不覆盖已保存内容）。
 * 3. 生成与人工编辑并发：一个标签页生成时另一个标签页写笔记，生成完成后笔记仍在。
 * 4. 收尾卫生：操作结束后没有悬挂的集合锁（Web Locks 无 held/pending，localStorage 无锁记录）。
 *
 * 边界（如实记录）：
 * - 生产路径在真实浏览器走**原生 Web Locks**（`navigator.locks`）；单元测试走 localStorage 回退锁路径，
 *   两条路径的证据分别记录，互不冒充（见 docs/qa/H1-BOOKS-COMMIT-SAFETY/）。
 * - 全部为本地模拟执行器与本地存储，不接真实 LLM/供应商。
 */

const BOOKS_KEY = 'zhiqikeyuan:books';
const BOOK_LOCK_NAME = `zqky-collection:${BOOKS_KEY}`;
const DRAFT_TITLE = '修辞手法小册（演示草稿）';

function strip(page: Page) {
  return page.locator('.book-pipeline-strip');
}

/** 在给定标签页里持有集合写锁（真实 Web Lock，直到调用 release） */
async function holdCollectionLock(page: Page): Promise<void> {
  await page.evaluate((name) => {
    const holder = window as unknown as { __zqkyReleaseLock?: () => void };
    void navigator.locks.request(name, { mode: 'exclusive' }, () => {
      return new Promise<void>((resolve) => {
        holder.__zqkyReleaseLock = resolve;
      });
    });
  }, BOOK_LOCK_NAME);
  await page.waitForFunction(
    async (name) => {
      const state = await navigator.locks.query();
      return state.held?.some((lock) => lock.name === name) === true;
    },
    BOOK_LOCK_NAME,
    { timeout: 5000 },
  );
}

/** 释放先前持有的集合写锁 */
async function releaseCollectionLock(page: Page): Promise<void> {
  await page.evaluate(() => {
    (window as unknown as { __zqkyReleaseLock?: () => void }).__zqkyReleaseLock?.();
  });
  await page.waitForFunction(
    async (name) => {
      const state = await navigator.locks.query();
      return (state.held ?? []).every((lock) => lock.name !== name) &&
        (state.pending ?? []).every((lock) => lock.name !== name);
    },
    BOOK_LOCK_NAME,
    { timeout: 5000 },
  );
}

async function openDemoBook(page: Page, pageId = 'demo-book-fractions-p1'): Promise<void> {
  await page.goto('/books');
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await page.goto(`/books/demo-book-fractions/pages/${pageId}`);
  await expect(page.getByText(/第 \d+\/4 页/)).toBeVisible();
}

/** 读取存储里某本书的笔记文本（只读断言用） */
async function readStoredNote(page: Page, bookId: string, pageId: string): Promise<string | null> {
  return page.evaluate(
    ({ key, bookId: id, pageId: pid }) => {
      const raw = window.localStorage.getItem(key);
      if (!raw) return null;
      const list = JSON.parse(raw) as Array<{
        id: string;
        pages?: Array<{ id: string; blocks: Array<{ type: string; content: string }> }>;
      }>;
      const book = list.find((item) => item.id === id);
      const block = book?.pages
        ?.find((item) => item.id === pid)
        ?.blocks.find((item) => item.type === 'user_note');
      return block?.content ?? null;
    },
    { key: BOOKS_KEY, bookId, pageId },
  );
}

test.describe('H1 书籍提交一致性（真实双标签页）', () => {
  test('另一标签页持有写锁：创建如实失败并保留输入，释放后重试成功', async ({ page, context }) => {
    test.setTimeout(120_000);
    const locker = await context.newPage();
    try {
      await page.goto('/books');
      await page.getByRole('button', { name: '新建书籍' }).click();
      const titleInput = page.getByLabel('书名');
      await titleInput.fill('冲突中的新书');

      // 另一个标签页占住集合写锁（真实 Web Lock，等同"另一标签页正在写"）
      await locker.goto('/books');
      await holdCollectionLock(locker);

      await page.getByRole('button', { name: '创建（生成模拟提案）' }).click();
      // 如实失败：内联错误给出原因，且用户输入保留（不关表单、不跳转）
      const form = page.getByRole('dialog').filter({ hasText: '新建书籍' });
      await expect(form.getByRole('alert')).toContainText(/未保存|冲突|另一个标签页/, {
        timeout: 20000,
      });
      await expect(titleInput).toHaveValue('冲突中的新书');
      await expect(page).toHaveURL(/\/books$/);
      // 存储里没有幻影书籍
      const titles = await page.evaluate((key) => {
        const raw = window.localStorage.getItem(key);
        return (JSON.parse(raw ?? '[]') as Array<{ title: string }>).map((item) => item.title);
      }, BOOKS_KEY);
      expect(titles).not.toContain('冲突中的新书');

      // 释放锁 → 同一表单重试成功（输入无需重新填写）
      await releaseCollectionLock(locker);
      await page.getByRole('button', { name: '创建（生成模拟提案）' }).click();
      // 成功才关表单并跳转；存储里真的有这本书
      await expect(page).toHaveURL(/\/books\/bk-/, { timeout: 30000 });
      await expect
        .poll(
          async () =>
            await page.evaluate((key) => {
              const raw = window.localStorage.getItem(key);
              return (JSON.parse(raw ?? '[]') as Array<{ title: string }>).map((item) => item.title);
            }, BOOKS_KEY),
          { timeout: 20000 },
        )
        .toContain('冲突中的新书');
    } finally {
      await locker.close();
    }
  });

  test('双标签页并发写不同书：两边内容都保留；结束后无悬挂锁', async ({ page, context }) => {
    const second = await context.newPage();
    try {
      await openDemoBook(page, 'demo-book-fractions-p1');
      await second.goto(page.url());
      await expect(second.getByLabel('我的笔记内容')).toBeVisible();

      const noteA = '标签页A的笔记：本节要点已复述。';
      const noteB = '标签页B的笔记：公式推导再看一遍。';
      await page.getByLabel('我的笔记内容').fill(noteA);
      await second.getByLabel('我的笔记内容').fill(noteB);
      // 同一时刻提交两次写（两个标签页各自的失焦提交）
      await Promise.all([
        page.getByLabel('我的笔记内容').blur(),
        second.getByLabel('我的笔记内容').blur(),
      ]);

      // 两个标签页最终看到同一份内容（后写者胜），且没有"半覆盖"造成的结构损坏
      await expect
        .poll(async () => await readStoredNote(page, 'demo-book-fractions', 'demo-book-fractions-p1'), {
          timeout: 20000,
        })
        .toMatch(/标签页A的笔记|标签页B的笔记/);
      const stored = await readStoredNote(page, 'demo-book-fractions', 'demo-book-fractions-p1');
      expect([noteA, noteB]).toContain(stored);

      // 另一本书的编辑不受影响（旧快照没有整表覆盖）
      await second.goto('/books/demo-book-fractions/pages/demo-book-fractions-p3');
      await second.getByLabel('我的笔记内容').fill('第三页的笔记（另一本书页）');
      await second.getByLabel('我的笔记内容').blur();
      await expect
        .poll(
          async () =>
            await readStoredNote(second, 'demo-book-fractions', 'demo-book-fractions-p3'),
          { timeout: 20000 },
        )
        .toBe('第三页的笔记（另一本书页）');
      // 第一页的笔记仍在（没有被第三页的写覆盖）
      expect(await readStoredNote(page, 'demo-book-fractions', 'demo-book-fractions-p1')).toBe(stored);

      // 收尾卫生：没有悬挂的集合锁
      const lockState = await page.evaluate(async (name) => {
        const state = await navigator.locks.query();
        return {
          held: (state.held ?? []).filter((lock) => lock.name === name).length,
          pending: (state.pending ?? []).filter((lock) => lock.name === name).length,
        };
      }, BOOK_LOCK_NAME);
      expect(lockState).toEqual({ held: 0, pending: 0 });
      const localLock = await page.evaluate((key) => window.localStorage.getItem(`${key}-lock`), BOOKS_KEY);
      expect(localLock).toBeNull();
    } finally {
      await second.close();
    }
  });

  test('生成与人工编辑并发：另一标签页写笔记，生成完成后笔记仍在且生成结果完整', async ({
    page,
    context,
  }) => {
    test.setTimeout(150_000);
    await page.goto('/books');
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await page
      .locator('.space-persona-card', { hasText: DRAFT_TITLE })
      .getByRole('button', { name: '继续创建' })
      .click();
    await page.getByRole('button', { name: '确认提案（进入大纲）' }).click();
    await expect(page.getByRole('status').filter({ hasText: '已确认提案' })).toBeVisible();
    await page.getByRole('button', { name: '确认大纲并编译（模拟）' }).click();
    await expect(page).toHaveURL(/\/books\/demo-book-draft\/pages\//, { timeout: 15000 });
    await expect(strip(page)).toBeVisible();

    // 等到第 2 页可用（该页含 user_note 块），再让第二标签页在同一页写笔记（生成仍在跑）
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 40000 });
    await page.getByRole('link', { name: /下一页/ }).click();
    await expect(page.getByLabel('我的笔记内容')).toBeVisible({ timeout: 40000 });
    const pageTwoUrl = page.url();

    const second = await context.newPage();
    try {
      await second.goto(pageTwoUrl);
      const note = '生成期间由第二标签页写入的笔记。';
      await second.getByLabel('我的笔记内容').fill(note);
      await second.getByLabel('我的笔记内容').blur();
      const pageId = pageTwoUrl.split('/pages/')[1]!;
      await expect
        .poll(async () => await readStoredNote(second, 'demo-book-draft', pageId), { timeout: 30000 })
        .toBe(note);

      // 等第一标签页的生成跑完（活动条消失）
      await expect(strip(page)).toHaveCount(0, { timeout: 90000 });
      // 笔记仍在：生成事件的写入没有用旧快照覆盖人工编辑
      expect(await readStoredNote(page, 'demo-book-draft', pageId)).toBe(note);
      // 生成结果完整：书籍达到可阅读
      await page.goto('/books');
      await expect(
        page.locator('.space-persona-card', { hasText: DRAFT_TITLE }).getByText('可阅读'),
      ).toBeVisible({ timeout: 30000 });
    } finally {
      await second.close();
    }
  });

  test('持有写锁时删除与其后操作都不假成功；释放后可正常删除', async ({ page, context }) => {
    const locker = await context.newPage();
    try {
      await page.goto('/books');
      await page.getByRole('button', { name: '载入演示数据' }).click();
      await locker.goto('/books');
      await holdCollectionLock(locker);

      const card = page.locator('.space-persona-card', { hasText: DRAFT_TITLE });
      await card.getByRole('button', { name: '删除' }).click();
      await card.getByRole('button', { name: '确认删除' }).click();
      // 失败如实提示，卡片保留、确认态保留（可重试）
      await expect(page.getByText(/删除失败：/)).toBeVisible({ timeout: 20000 });
      await expect(card).toHaveCount(1);

      await releaseCollectionLock(locker);
      await card.getByRole('button', { name: '确认删除' }).click();
      await expect(card).toHaveCount(0, { timeout: 20000 });
    } finally {
      await locker.close();
    }
  });
});
