import { expect, test, type Page } from '@playwright/test';

/**
 * H1-BOOKS-COMMIT-SAFETY v1 浏览器回归（BOOKS-CS-FOLLOWUP v1 订正测试口径）：
 * **真实双标签页**下的集合写互斥与提交结果。
 *
 * 覆盖（隔离 context，同一 context 内两个 page 共享 localStorage 与 Web Locks）：
 * 1. 另一标签页持有集合写锁时：创建/编辑/删除如实失败、输入保留；释放锁后重试成功（不假成功）。
 * 2. **同一本书不同页**并发写：后写者胜但不损坏其他页（不是"不同书"场景）。
 * 3. **不同 bookId、不同内容**的双标签页并发写：两边内容都在（旧快照不覆盖另一本书），
 *    生成结束后无覆盖、无悬挂锁。
 * 4. 生成与人工编辑并发：一个标签页生成时另一个标签页写笔记，生成完成后笔记仍在。
 * 5. 收尾卫生：操作结束后没有悬挂的集合锁（Web Locks 无 held/pending，localStorage 无锁记录）。
 *
 * 边界（如实记录）：
 * - 生产路径在真实浏览器走**原生 Web Locks**（`navigator.locks`）；没有原生 Web Locks 时写操作
 *   如实返回 `unsupported`（不静默降级），单元测试经显式注入的 in-process 互斥覆盖事务语义。
 *   两条路径的证据分别记录，互不冒充（见 docs/qa/H1-BOOKS-COMMIT-SAFETY/ 与 BOOKS-CS-FOLLOWUP/）。
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

/** 存储里现有书籍 id 列表（只读断言用） */
async function readStoredBookIds(page: Page): Promise<string[]> {
  return page.evaluate((key) => {
    const raw = window.localStorage.getItem(key);
    return (JSON.parse(raw ?? '[]') as Array<{ id: string }>).map((item) => item.id);
  }, BOOKS_KEY);
}

/** 收尾卫生：该标签页没有悬挂的集合写锁（原生 Web Locks 无 held/pending，且无 localStorage 锁记录） */
async function expectNoDanglingCollectionLock(page: Page): Promise<void> {
  const lockState = await page.evaluate(async (name) => {
    const state = await navigator.locks.query();
    return {
      held: (state.held ?? []).filter((lock) => lock.name === name).length,
      pending: (state.pending ?? []).filter((lock) => lock.name === name).length,
    };
  }, BOOK_LOCK_NAME);
  expect(lockState).toEqual({ held: 0, pending: 0 });
  expect(await page.evaluate((key) => window.localStorage.getItem(`${key}-lock`), BOOKS_KEY)).toBeNull();
}

/**
 * 新建一本书 → 确认提案 → 确认大纲（本地模拟执行器开始生成）→ 打开第 2 页（含 user_note 块）。
 * 返回 bookId 与 pageId，供"不同 bookId 并发写"用例使用。
 */
async function createGeneratingBook(
  page: Page,
  title: string,
  description: string,
): Promise<{ bookId: string; pageId: string }> {
  await page.goto('/books');
  await page.getByRole('button', { name: '新建书籍' }).click();
  await page.getByLabel('书名').fill(title);
  await page.getByLabel('简介').fill(description);
  await page.getByRole('button', { name: '创建（生成模拟提案）' }).click();
  await expect(page).toHaveURL(/\/books\/bk-/, { timeout: 30000 });
  await page.getByRole('button', { name: '确认提案（进入大纲）' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已确认提案' })).toBeVisible();
  await page.getByRole('button', { name: '确认大纲并编译（模拟）' }).click();
  await expect(page).toHaveURL(/\/books\/bk-.+\/pages\//, { timeout: 15000 });
  const bookId = page.url().split('/books/')[1]!.split('/pages/')[0]!;
  // 第 1 页有内容后翻到第 2 页（该页含 user_note 块）；生成仍在继续
  await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 60000 });
  await page.getByRole('link', { name: /下一页/ }).click();
  await expect(page.getByLabel('我的笔记内容')).toBeVisible({ timeout: 60000 });
  const pageId = page.url().split('/pages/')[1]!;
  return { bookId, pageId };
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

  test('同一本书不同页并发写：后写者胜但不损坏其他页；结束后无悬挂锁', async ({ page, context }) => {
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

      // 同一页同一块：两个标签页最终看到同一份内容（后写者胜），且没有"半覆盖"造成的结构损坏
      await expect
        .poll(async () => await readStoredNote(page, 'demo-book-fractions', 'demo-book-fractions-p1'), {
          timeout: 20000,
        })
        .toMatch(/标签页A的笔记|标签页B的笔记/);
      const stored = await readStoredNote(page, 'demo-book-fractions', 'demo-book-fractions-p1');
      expect([noteA, noteB]).toContain(stored);

      // **同一本书的另一页**的编辑不受影响（旧快照没有整表覆盖）
      await second.goto('/books/demo-book-fractions/pages/demo-book-fractions-p3');
      await second.getByLabel('我的笔记内容').fill('第三页的笔记（同一本书另一页）');
      await second.getByLabel('我的笔记内容').blur();
      await expect
        .poll(
          async () =>
            await readStoredNote(second, 'demo-book-fractions', 'demo-book-fractions-p3'),
          { timeout: 20000 },
        )
        .toBe('第三页的笔记（同一本书另一页）');
      // 第一页的笔记仍在（没有被第三页的写覆盖）
      expect(await readStoredNote(page, 'demo-book-fractions', 'demo-book-fractions-p1')).toBe(stored);

      // 收尾卫生：没有悬挂的集合锁
      await expectNoDanglingCollectionLock(page);
    } finally {
      await second.close();
    }
  });

  test('双标签页并发写不同书：两边内容都在、无覆盖、结束后无悬挂锁', async ({ page, context }) => {
    test.setTimeout(180_000);
    const second = await context.newPage();
    try {
      // 两本**不同 bookId** 的书（各自生成中；第 2 页含 user_note 块）
      const bookA = await createGeneratingBook(page, '并发写书A', '甲书主题');
      const bookB = await createGeneratingBook(second, '并发写书B', '乙书主题');
      expect(bookA.bookId).not.toBe(bookB.bookId);

      const noteA = '书A的笔记：只在书A里。';
      const noteB = '书B的笔记：只在书B里。';
      // 同一时刻：一边写书 A 的笔记、另一边写书 B 的笔记（两个独立事务，并发提交）
      await page.getByLabel('我的笔记内容').fill(noteA);
      await second.getByLabel('我的笔记内容').fill(noteB);
      await Promise.all([
        page.getByLabel('我的笔记内容').blur(),
        second.getByLabel('我的笔记内容').blur(),
      ]);

      // 双方内容都存在于存储（旧快照没有把另一本书的内容覆盖掉）
      await expect
        .poll(async () => await readStoredNote(page, bookA.bookId, bookA.pageId), { timeout: 30000 })
        .toBe(noteA);
      await expect
        .poll(async () => await readStoredNote(second, bookB.bookId, bookB.pageId), { timeout: 30000 })
        .toBe(noteB);

      // 两本书都生成完（生成期间的事件写入也不得覆盖人工笔记）
      await expect(strip(page)).toHaveCount(0, { timeout: 120_000 });
      await expect(strip(second)).toHaveCount(0, { timeout: 120_000 });

      // 跨标签页复核：两边内容都还在（无覆盖、无半写）
      expect(await readStoredNote(second, bookA.bookId, bookA.pageId)).toBe(noteA);
      expect(await readStoredNote(page, bookB.bookId, bookB.pageId)).toBe(noteB);
      // 两本书都在（没有整表覆盖导致的记录丢失）
      const ids = await readStoredBookIds(page);
      expect(ids).toContain(bookA.bookId);
      expect(ids).toContain(bookB.bookId);

      // 收尾卫生：两个标签页都没有悬挂的集合锁
      await expectNoDanglingCollectionLock(page);
      await expectNoDanglingCollectionLock(second);
    } finally {
      await second.close();
    }
  });

  test('另一标签页持写锁：暂停如实失败且不显示「已暂停」；释放后暂停成功并在刷新后保持', async ({
    page,
    context,
  }) => {
    test.setTimeout(150_000);
    const locker = await context.newPage();
    try {
      const book = await createGeneratingBook(page, '暂停写锁书', '用于暂停提交结果');
      await page.goto(`/books/${book.bookId}/pages/${book.pageId}`);
      await expect(strip(page)).toBeVisible();

      // 另一标签页占住集合写锁（真实 Web Lock）：暂停状态提交会真实失败
      await locker.goto('/books');
      await holdCollectionLock(locker);
      await strip(page).getByRole('button', { name: '暂停生成' }).click();

      // 如实失败：给出"暂停未保存"提示，绝不显示"已暂停"
      await expect(page.getByText(/暂停未保存：/)).toBeVisible({ timeout: 30000 });
      await expect(page.getByText('生成已暂停')).toHaveCount(0);
      // 执行器仍在跑（未提交时不停止生成，可重试）
      await expect(strip(page)).toBeVisible();

      // 释放锁 → 再点暂停 → 这次真的提交并收尾
      // 注意：'生成已暂停' 同时出现在暂停横幅标题、横幅正文与活动条阶段文案，断言必须限定容器（strict mode）
      await releaseCollectionLock(locker);
      await strip(page).getByRole('button', { name: '暂停生成' }).click();
      const pausedBanner = page.locator('.book-pipeline-paused');
      await expect(pausedBanner).toBeVisible({ timeout: 30000 });
      await expect(pausedBanner).toContainText('生成已暂停');
      await expect(strip(page)).toContainText('生成已暂停');
      await expect(page.getByRole('button', { name: '恢复生成' }).first()).toBeVisible();

      // 刷新后仍为 paused（状态来自存储，不是内存）
      await page.reload();
      await expect(page.locator('.book-pipeline-paused')).toBeVisible({ timeout: 30000 });
      await expectNoDanglingCollectionLock(page);
    } finally {
      await locker.close();
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
