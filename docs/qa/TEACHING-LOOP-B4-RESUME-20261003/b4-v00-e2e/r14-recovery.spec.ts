import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { startBookInterruptedRecovery } from '../../../../tests/e2e/helpers/book-interrupted-recovery';

// Independent oracles read browser storage and native locks; they do not call book services.
const BOOKS_KEY = 'zhiqikeyuan:books';
const BOOK_LOCK_NAME = `zqky-collection:${BOOKS_KEY}`;
const INTERRUPTED = '生成已中断（无执行器在跑）';
type Scenario = 'normal' | 'page-failure';
type RecoveryHandle = ReturnType<typeof startBookInterruptedRecovery>;
type RecoveryResult = Awaited<RecoveryHandle['result']>;
type RecoveryCleanup = Awaited<ReturnType<RecoveryHandle['cleanup']>>;

interface ContinueEvent {
  atMs: number;
  isTrusted: boolean;
  pathname: string;
  stage: string;
  disabled: boolean;
  rawBooks: string | null;
}

function describeError(value: unknown) {
  return value instanceof Error
    ? { name: value.name, message: value.message, stack: value.stack }
    : { name: 'ThrownValue', message: String(value) };
}

async function readBookFacts(page: Page, bookId: string, pageId: string) {
  return page.evaluate(
    ({ key, id, pid }) => {
      const raw = window.localStorage.getItem(key);
      if (raw === null) throw new Error('Independent oracle: books collection missing');
      const list: unknown = JSON.parse(raw);
      if (!Array.isArray(list) || list.some((item) => !item || typeof item.id !== 'string')) {
        throw new Error('Independent oracle: books collection malformed');
      }
      const matches = list.filter((item) => item.id === id);
      if (matches.length !== 1) throw new Error(`Independent oracle: book ${id} not unique/present`);
      const book = matches[0];
      if (typeof book.status !== 'string' || !Array.isArray(book.pages)) {
        throw new Error(`Independent oracle: book ${id} status/pages malformed`);
      }
      if (!book.run || typeof book.run.runId !== 'string' || typeof book.run.status !== 'string') {
        throw new Error(`Independent oracle: book ${id} run missing/malformed`);
      }
      const notePages = book.pages.filter((item: { id?: unknown }) => item.id === pid);
      if (notePages.length !== 1 || !Array.isArray(notePages[0].blocks)) {
        throw new Error(`Independent oracle: note page ${pid} not unique/present`);
      }
      const notes = notePages[0].blocks.filter((block: { type?: unknown }) => block.type === 'user_note');
      if (notes.length !== 1 || typeof notes[0].content !== 'string') {
        throw new Error(`Independent oracle: note on ${pid} missing/malformed`);
      }
      const pages: Array<{ id: string; status: string }> = book.pages.map((item: { id?: unknown; status?: unknown }) => {
        if (typeof item.id !== 'string' || typeof item.status !== 'string') {
          throw new Error(`Independent oracle: page identity/status malformed in ${id}`);
        }
        return { id: item.id, status: item.status };
      });
      return {
        bookId: book.id as string,
        title: book.title as string,
        bookStatus: book.status as string,
        runId: book.run.runId as string,
        runStatus: book.run.status as string,
        run: book.run as Record<string, unknown>,
        runScenario: (book.runScenario ?? null) as Record<string, unknown> | null,
        pageId: pid,
        note: notes[0].content as string,
        pages,
        bookIds: list.map((item) => item.id as string).sort(),
      };
    },
    { key: BOOKS_KEY, id: bookId, pid: pageId },
  );
}

async function readLocks(page: Page) {
  return page.evaluate(
    async ({ name, key }) => {
      const locks = await navigator.locks.query();
      return {
        held: (locks.held ?? []).filter((lock) => lock.name === name).length,
        pending: (locks.pending ?? []).filter((lock) => lock.name === name).length,
        legacyLock: window.localStorage.getItem(`${key}-lock`),
      };
    },
    { name: BOOK_LOCK_NAME, key: BOOKS_KEY },
  );
}

// Separate capture listener counts actual DOM clicks, independently of helper result counters.
async function installClickProbe(page: Page) {
  await page.evaluate((key) => {
    const holder = window as unknown as {
      __r14IndependentProbe?: { events: ContinueEvent[]; listener: (event: MouseEvent) => void };
    };
    if (holder.__r14IndependentProbe) throw new Error('Independent click probe already installed');
    const events: ContinueEvent[] = [];
    const listener = (event: MouseEvent) => {
      const button = event.target instanceof Element ? event.target.closest('button') : null;
      const strip = button?.closest('.book-pipeline-strip');
      if (!(button instanceof HTMLButtonElement) || !strip || button.textContent?.trim() !== '继续生成') return;
      events.push({
        atMs: Date.now(),
        isTrusted: event.isTrusted,
        pathname: location.pathname,
        stage: strip.querySelector('.book-pipeline-strip-stage')?.textContent?.trim() ?? '',
        disabled: button.disabled,
        rawBooks: window.localStorage.getItem(key),
      });
    };
    holder.__r14IndependentProbe = { events, listener };
    document.addEventListener('click', listener, true);
  }, BOOKS_KEY);
}

async function removeClickProbe(page: Page) {
  return page.evaluate(() => {
    const holder = window as unknown as {
      __r14IndependentProbe?: { events: ContinueEvent[]; listener: (event: MouseEvent) => void };
    };
    const probe = holder.__r14IndependentProbe;
    if (!probe) throw new Error('Independent click probe disappeared before cleanup');
    document.removeEventListener('click', probe.listener, true);
    delete holder.__r14IndependentProbe;
    return { events: probe.events, listenerRemoved: !holder.__r14IndependentProbe };
  });
}

async function createBookToSecondPage(page: Page, scenario: Scenario, title: string) {
  await page.goto('/books');
  await page.getByRole('button', { name: '新建书籍' }).click();
  await page.getByLabel('书名').fill(title);
  await page.getByLabel('简介').fill('独立验证本地模拟生成、真实笔记保存与有界恢复。');
  await page.getByRole('button', { name: '创建（生成模拟提案）' }).click();
  await expect(page).toHaveURL(/\/books\/bk-/, { timeout: 30000 });
  await page.getByRole('button', { name: '确认提案（进入大纲）' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已确认提案' })).toBeVisible();
  if (scenario === 'page-failure') {
    await page.getByRole('button', { name: '模拟执行器设置（仅本地模拟）' }).click();
    const failure = page.getByLabel(/注入整页失败/);
    await failure.check();
    await expect(failure).toBeChecked();
    await expect(page.getByLabel('整页失败页数')).toHaveValue('1');
  }
  await page.getByRole('button', { name: '确认大纲并编译（模拟）' }).click();
  await expect(page).toHaveURL(/\/books\/bk-.+\/pages\//, { timeout: 15000 });
  const bookId = new URL(page.url()).pathname.split('/books/')[1]!.split('/pages/')[0]!;
  if (scenario === 'page-failure') {
    await expect(page.getByText('页面生成失败', { exact: true })).toBeVisible({ timeout: 30000 });
    await expect(page.getByText(/模拟页面失败/)).toBeVisible();
  } else {
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 30000 });
  }
  // Move while the initial run is active; opening a fresh route after interruption can auto-resume.
  await page.getByRole('link', { name: /下一页/ }).click();
  await expect(page.getByLabel('我的笔记内容')).toBeVisible({ timeout: 30000 });
  const pageId = new URL(page.url()).pathname.split('/pages/')[1]!;
  await expect(page.getByText(/第 2\/\d+ 页/)).toBeVisible();
  return { bookId, pageId };
}

async function verifyScenario(page: Page, info: TestInfo, scenario: Scenario) {
  const startedAtMs = Date.now();
  const title = scenario === 'normal' ? 'R14独立正常生成书' : 'R14独立一次页故障书';
  const expectedNote = scenario === 'normal' ? '正常生成中的真实第二页笔记。' : '明确中断后保存的真实第二页笔记。';
  const expectedClicks = scenario === 'normal' ? 0 : 1;
  let target: { bookId: string; pageId: string } | undefined;
  let before: Awaited<ReturnType<typeof readBookFacts>> | undefined;
  let after: Awaited<ReturnType<typeof readBookFacts>> | undefined;
  let finalLocks: Awaited<ReturnType<typeof readLocks>> | undefined;
  let handle: RecoveryHandle | undefined;
  let result: RecoveryResult | undefined;
  let cleanup: RecoveryCleanup | undefined;
  let clickProbeInstalled = false;
  let clickProbe: Awaited<ReturnType<typeof removeClickProbe>> | undefined;
  let primaryFailure: ReturnType<typeof describeError> | undefined;
  const cleanupFailures: Array<ReturnType<typeof describeError>> = [];
  let deadline: number | undefined;
  try {
    target = await createBookToSecondPage(page, scenario, title);
    if (scenario === 'page-failure') {
      await expect(page.getByText(INTERRUPTED, { exact: true })).toBeVisible({ timeout: 40000 });
      await expect(page.locator('.book-pipeline-strip').getByRole('button', { name: '继续生成', exact: true })).toBeEnabled();
    } else {
      await expect(page.locator('.book-pipeline-strip')).toContainText('正在逐章编译（本地模拟，不调用模型）…');
    }
    await page.getByLabel('我的笔记内容').fill(expectedNote);
    await page.getByLabel('我的笔记内容').blur();
    await expect.poll(async () => (await readBookFacts(page, target!.bookId, target!.pageId)).note, { timeout: 30000 }).toBe(expectedNote);
    before = await readBookFacts(page, target.bookId, target.pageId);
    expect(before.bookStatus).toBe('compiling');
    expect(before.pages[1]!.id).toBe(target.pageId);
    expect(before.bookIds).toContain(target.bookId);
    if (scenario === 'page-failure') {
      expect(before.runStatus).toBe('stopped');
      expect(before.runScenario).toEqual(expect.objectContaining({ failPages: 1 }));
      expect(before.pages.filter((item) => item.status === 'error')).toHaveLength(1);
      await expect(page.getByText(INTERRUPTED, { exact: true })).toBeVisible();
    }
    await page.screenshot({ path: info.outputPath(`r14-${scenario}-before.png`), fullPage: true });
    await installClickProbe(page);
    clickProbeInstalled = true;
    // One original 120s completion window within the existing 180s test budget; no reset on recovery.
    deadline = Math.min(Date.now() + 120000, startedAtMs + 175000);
    handle = startBookInterruptedRecovery(page, { ...target, expectedNote, deadline });
    const completed = await Promise.all([
      handle.result,
      expect(page.locator('.book-pipeline-strip')).toHaveCount(0, { timeout: 120000 }),
    ]);
    result = completed[0];
    expect(result.bookId).toBe(target.bookId);
    expect(result.bookStatus).toBe('ready');
    expect(result.note).toBe(expectedNote);
    expect(result.branch).toBe(scenario === 'normal' ? 'normal' : 'recovered');
    expect(result.continueAttempts).toBe(expectedClicks);
    expect(result.continueClicks).toBe(expectedClicks);
    expect(result.completedAtMs).toBeLessThanOrEqual(deadline);
    clickProbe = await removeClickProbe(page);
    clickProbeInstalled = false;
    expect(clickProbe.listenerRemoved).toBe(true);
    expect(clickProbe.events).toHaveLength(expectedClicks);
    for (const event of clickProbe.events) {
      expect(event.isTrusted).toBe(true);
      expect(event.pathname).toBe(`/books/${target.bookId}/pages/${target.pageId}`);
      expect(event.stage).toBe(INTERRUPTED);
      expect(event.disabled).toBe(false);
      if (event.rawBooks === null) throw new Error('Independent Continue snapshot collection missing');
      const clickedBooks = JSON.parse(event.rawBooks) as Array<{ id: string; status: string; run: { runId: string }; pages: Array<{ id: string; blocks: Array<{ type: string; content: string }> }> }>;
      const clickedBook = clickedBooks.find((item) => item.id === target!.bookId);
      expect(clickedBook?.status).toBe('compiling');
      expect(clickedBook?.run.runId).toBe(before.runId);
      expect(clickedBook?.pages.find((item) => item.id === target!.pageId)?.blocks.find((block) => block.type === 'user_note')?.content).toBe(expectedNote);
    }
    after = await readBookFacts(page, target.bookId, target.pageId);
    expect(after.bookStatus).toBe('ready');
    expect(after.runStatus).toBe('finished');
    expect(after.runId).toBe(before.runId);
    expect(after.note).toBe(expectedNote);
    expect(after.bookIds).toEqual(before.bookIds);
    expect(after.bookIds).toContain(target.bookId);
    expect(after.pages.every((item) => item.status === 'ready' || item.status === 'partial')).toBe(true);
    await expect(page.getByLabel('我的笔记内容')).toHaveValue(expectedNote);
    await expect(page.getByText(INTERRUPTED, { exact: true })).toHaveCount(0);
    finalLocks = await readLocks(page);
    expect(finalLocks).toEqual({ held: 0, pending: 0, legacyLock: null });
    await page.screenshot({ path: info.outputPath(`r14-${scenario}-ready-reader.png`), fullPage: true });
    // Release the observer while its exact reader document is still alive; finally is idempotent.
    cleanup = await handle.cleanup();
    await page.goto('/books');
    await expect(page.locator('.space-persona-card', { hasText: title }).getByText('可阅读', { exact: true })).toBeVisible();
    await page.screenshot({ path: info.outputPath(`r14-${scenario}-ready-library.png`), fullPage: true });
  } catch (error) {
    primaryFailure = describeError(error);
    throw error; // Preserve the first real failure; metadata never converts it to success.
  } finally {
    if (handle) {
      try { cleanup = await handle.cleanup(); } catch (error) { cleanupFailures.push(describeError(error)); }
    }
    if (clickProbeInstalled) {
      try { clickProbe = await removeClickProbe(page); } catch (error) { cleanupFailures.push(describeError(error)); }
    }
    try {
      await info.attach('r14-independent-facts', {
        contentType: 'application/json',
        body: Buffer.from(JSON.stringify({ scenario, startedAtMs, deadline, target, expectedNote, expectedClicks, before, result, after, finalLocks, independentClickProbe: clickProbe, helperCleanup: cleanup, primaryFailure, cleanupFailures }, null, 2)),
      });
    } catch (error) {
      cleanupFailures.push(describeError(error));
    }
    if (!primaryFailure) {
      expect(cleanupFailures).toEqual([]);
      expect(cleanup?.resourcesReleased).toBe(true);
      expect(cleanup?.observerDisconnected).toBe(true);
      expect(cleanup?.timerCleared).toBe(true);
      expect(cleanup?.listenersRemoved).toBe(true);
      expect(cleanup?.contextClosed).toBe(false);
      expect(cleanup?.continueAttempts).toBe(expectedClicks);
      expect(cleanup?.continueClicks).toBe(expectedClicks);
      expect(cleanup?.resultStatus).toBe('ready');
      expect(cleanup?.failure).toBeNull();
      expect(cleanup?.cleanupErrors).toEqual([]);
    }
  }
}

test('R14独立正常生成：真实笔记保留，零次继续，最终ready及无悬挂锁', async ({ page }, info) => {
  test.setTimeout(180000);
  await verifyScenario(page, info, 'normal');
});

test('R14独立整页故障：真实UI注入与保存笔记，一次继续后ready及无悬挂锁', async ({ page }, info) => {
  test.setTimeout(180000);
  await verifyScenario(page, info, 'page-failure');
});
