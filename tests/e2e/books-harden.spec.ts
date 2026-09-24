import { expect, test, type Page } from '@playwright/test';

/**
 * H1-BOOKS-HARDEN v1 浏览器回归（main 审查 M22-01～06）。
 *
 * 覆盖（均在本项目真实浏览器 + 真实 localStorage 上执行，隔离 context）：
 * 1. 首次读取目录失败 → 可见错误 + 「重试读取」，成功后清除旧错误（M22-04）；
 * 2. 双标签页失权 → 第一标签页停止并如实提示、不再续租；释放后用户可继续（M22-03）；
 * 3. 生成中删除 → 租约立即释放且不再续租、迟到事件不复活（M22-01）；
 * 4. 笔记输入框与 contenteditable 内 ←/→ 不翻页，普通阅读仍可翻页（M22-06）；
 * 5. 最终完成写入失败 → 不假报完成（卡片不是「可阅读」）+ 「重试生成」真的完成（M22-05）；
 * 6. 同一 tick 连点「强制重新生成」→ 引擎互斥（复用同一操作），页最终完整、无残留错误（M22-02）。
 *
 * 边界（如实记录）：
 * - 组合输入（IME isComposing）与修饰键在真实浏览器里无法稳定构造，测试在组件层
 *   （`features/books/PageReader.test.tsx`）；本 spec 覆盖输入框/可编辑元素与普通上下文两组真实键盘。
 * - 全部为本地模拟执行器与本地注入，不接真实 LLM/供应商；M22-01 的定时器/监听释放细节由单测覆盖。
 * - 隔离：Playwright 每个 test 独立 context；不触碰用户 5173 的数据。
 */

const DRAFT_TITLE = '修辞手法小册（演示草稿）';
const READY_TITLE = '分数入门（演示书籍）';

function strip(page: Page) {
  return page.locator('.book-pipeline-strip');
}

async function waitForRunSettled(page: Page): Promise<void> {
  await expect(strip(page)).toHaveCount(0, { timeout: 40000 });
}

/** 载入演示数据并打开演示草稿书 */
async function openDemoDraft(page: Page): Promise<void> {
  await page.goto('/books');
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await page
    .locator('.space-persona-card', { hasText: DRAFT_TITLE })
    .getByRole('button', { name: '继续创建' })
    .click();
  await expect(page).toHaveURL(/\/books\/demo-book-draft$/);
  await expect(page.getByText('提案（模拟）')).toBeVisible();
}

/** 确认提案→（可选）注入模拟场景→确认大纲，进入异步编译 */
async function confirmAndCompile(
  page: Page,
  scenario?: 'block' | 'page' | 'provider' | 'storage' | 'finish',
): Promise<void> {
  await page.getByRole('button', { name: '确认提案（进入大纲）' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已确认提案' })).toBeVisible();
  await expect(page.getByText(/章节大纲（4 章）/)).toBeVisible();

  if (scenario) {
    await page.getByRole('button', { name: '模拟执行器设置（仅本地模拟）' }).click();
    const label =
      scenario === 'block'
        ? /注入块失败/
        : scenario === 'page'
          ? /注入整页失败/
          : scenario === 'provider'
            ? /模拟供应商连续失败暂停/
            : scenario === 'storage'
              ? /模拟存储写入失败/
              : /模拟最终完成写入失败/;
    await page.getByLabel(label).check();
  }

  await page.getByRole('button', { name: '确认大纲并编译（模拟）' }).click();
  await expect(page).toHaveURL(/\/books\/demo-book-draft\/pages\//, { timeout: 15000 });
}

test.describe('H1 书籍加固（HARDEN v1）', () => {
  test('首次读取目录失败：错误可见 + 重试读取成功并清除旧错误（含 390 窄视口不溢出）', async ({ page }) => {
    // 窄视口：新增的错误面板与重试入口不得造成页面级横向溢出
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/books');
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await expect(page.locator('.space-persona-card', { hasText: DRAFT_TITLE })).toBeVisible();

    // 注入：本标签页后续导航中读取书籍集合一律失败（真实浏览器存储拒绝路径）
    await page.addInitScript(() => {
      const original = Storage.prototype.getItem;
      let deny = true;
      Storage.prototype.getItem = function patched(this: Storage, name: string) {
        if (deny && name === 'zhiqikeyuan:books') throw new Error('e2e: read denied');
        return original.call(this, name) as string | null;
      };
      (window as unknown as { __zqkyAllowBooksRead?: () => void }).__zqkyAllowBooksRead = () => {
        deny = false;
      };
    });

    await page.goto('/books/demo-book-draft');
    // 错误必须可见，不能停在"正在读取书籍…"
    await expect(page.getByText(/书籍目录读取失败/)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('正在读取书籍…')).toHaveCount(0);
    await expect(page.getByRole('button', { name: '重试读取' })).toBeEnabled();
    const overflowInError = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflowInError).toBeLessThanOrEqual(1);

    // 解除注入后重试：内容出现，旧错误消失
    await page.evaluate(() =>
      (window as unknown as { __zqkyAllowBooksRead?: () => void }).__zqkyAllowBooksRead?.(),
    );
    await page.getByRole('button', { name: '重试读取' }).click();
    await expect(page.getByText('提案（模拟）')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/书籍目录读取失败/)).toHaveCount(0);
  });

  test('双标签页失权：第一标签页停止并提示、不再续租；释放所有权后可继续生成', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page);
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 30000 });

    const bookId = 'demo-book-draft';
    const second = await page.context().newPage();
    try {
      await second.goto(page.url());
      await expect(second.getByText('本书正在另一个标签页生成')).toBeVisible({ timeout: 15000 });

      // 第二个标签页"接管"租约（写入自己的 owner + nonce，心跳新鲜）
      await second.evaluate((id) => {
        const key = `zhiqikeyuan:book-lease:${id}`;
        const current = JSON.parse(window.localStorage.getItem(key) ?? '{}') as { runId?: string };
        window.localStorage.setItem(
          key,
          JSON.stringify({
            owner: 'e2e-other-owner',
            runId: current.runId ?? '',
            heartbeatAt: Date.now(),
            nonce: 'e2e-other-lease',
          }),
        );
      }, bookId);

      // 第一标签页在下一次归属校验（步进/心跳）后如实停止，并提示失权；
      // 此时租约在别人手里，界面如实显示"另一个标签页生成"而不是"已中断"
      await expect(page.getByText(/已失去或无法确认本书的生成所有权/)).toBeVisible({ timeout: 15000 });
      await expect(strip(page)).toContainText('本书正在另一个标签页生成');
      await expect(strip(page).getByRole('button', { name: '暂停生成' })).toHaveCount(0);

      // 停止续租：跨过一个心跳周期，租约仍是接管方的记录
      await page.waitForTimeout(1500);
      const lease = await page.evaluate(
        (id) => window.localStorage.getItem(`zhiqikeyuan:book-lease:${id}`),
        bookId,
      );
      expect(JSON.parse(lease!) as { owner: string }).toMatchObject({ owner: 'e2e-other-owner' });
    } finally {
      await second.close();
    }

    // 接管方释放后，用户显式继续生成 → 从断点完成
    await page.evaluate((id) => window.localStorage.removeItem(`zhiqikeyuan:book-lease:${id}`), bookId);
    await strip(page).getByRole('button', { name: '继续生成' }).click();
    await waitForRunSettled(page);
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 20000 });
  });

  test('生成中删除：租约立即释放且不再续租，迟到事件不复活', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page);
    await expect(strip(page)).toBeVisible();

    const bookId = 'demo-book-draft';
    // 客户端路由返回列表：执行器是模块级的，仍然在跑（用租约存在证明这一点）
    await page.getByRole('link', { name: '返回书籍列表' }).click();
    await expect(page.getByRole('heading', { name: '书籍' })).toBeVisible({ timeout: 15000 });
    const leaseBefore = await page.evaluate(
      (id) => window.localStorage.getItem(`zhiqikeyuan:book-lease:${id}`),
      bookId,
    );
    expect(leaseBefore).not.toBeNull();

    const card = page.locator('.space-persona-card', { hasText: DRAFT_TITLE });
    await card.getByRole('button', { name: '删除' }).click();
    await card.getByRole('button', { name: '确认删除' }).click();
    await expect(card).toHaveCount(0);

    // 删除入口停止任务：租约立即释放，且心跳不再把它写回来
    const leaseAfter = await page.evaluate(
      (id) => window.localStorage.getItem(`zhiqikeyuan:book-lease:${id}`),
      bookId,
    );
    expect(leaseAfter).toBeNull();
    await page.waitForTimeout(1500);
    expect(
      await page.evaluate((id) => window.localStorage.getItem(`zhiqikeyuan:book-lease:${id}`), bookId),
    ).toBeNull();

    await page.reload();
    await expect(page.locator('.space-persona-card', { hasText: DRAFT_TITLE })).toHaveCount(0);
  });

  test('笔记与 contenteditable 内 ←/→ 不翻页；普通阅读仍可翻页', async ({ page }) => {
    await page.goto('/books');
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await page.getByRole('link', { name: `打开书籍 ${READY_TITLE}` }).click();
    await page.goto('/books/demo-book-fractions/pages/demo-book-fractions-p1');
    await expect(page.getByText('第 2/4 页')).toBeVisible();

    // 笔记输入框内：方向键属于编辑，不得翻页
    const note = page.getByLabel('我的笔记内容');
    await note.click();
    await note.press('ArrowRight');
    await expect(page).toHaveURL(/\/pages\/demo-book-fractions-p1$/);
    await note.press('ArrowLeft');
    await expect(page).toHaveURL(/\/pages\/demo-book-fractions-p1$/);

    // 可编辑元素（contenteditable）内：同样不翻页
    await page.evaluate(() => {
      const editable = document.createElement('div');
      editable.id = 'e2e-editable';
      editable.setAttribute('contenteditable', 'true');
      editable.setAttribute('aria-label', 'e2e 富文本笔记');
      document.body.appendChild(editable);
      editable.focus();
    });
    await page.keyboard.press('ArrowRight');
    await expect(page).toHaveURL(/\/pages\/demo-book-fractions-p1$/);

    // 普通阅读上下文：←/→ 翻页仍然有效
    await page.evaluate(() => {
      document.getElementById('e2e-editable')?.remove();
    });
    await page.keyboard.press('ArrowRight');
    await expect(page).toHaveURL(/\/pages\/demo-book-fractions-p2$/);
    await page.keyboard.press('ArrowLeft');
    await expect(page).toHaveURL(/\/pages\/demo-book-fractions-p1$/);
  });

  test('最终完成写入失败：不假报完成，卡片显示生成失败，「重试生成」后真正完成', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page, 'finish');

    const banner = page.getByRole('alert').filter({ hasText: '生成失败（本地模拟）' });
    await expect(banner).toBeVisible({ timeout: 40000 });
    await expect(banner).toContainText(/最终完成状态写入失败/);
    await expect(page.getByText('可阅读')).toHaveCount(0);

    await page.goto('/books');
    const card = page.locator('.space-persona-card', { hasText: DRAFT_TITLE });
    await expect(card.getByText('生成失败')).toBeVisible();
    await expect(card.getByText('可阅读')).toHaveCount(0);

    // 恢复入口：重试生成（一次性注入不再触发）→ 真正完成
    await card.getByRole('button', { name: '查看' }).click();
    await expect(page.getByRole('button', { name: '重试生成' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: '重试生成' }).click();
    // 失败横幅消失 = 书籍离开 error（重新进入生成）
    await expect(banner).toHaveCount(0, { timeout: 20000 });
    // 等重试真正完成再离开页面：整页导航会销毁本标签页的模块级执行器，
    // 在生成中途跳走会让书停在"已中断"（那是既定语义，不是本用例要验的东西）
    await page.waitForFunction(
      (id) => {
        const raw = window.localStorage.getItem('zhiqikeyuan:books');
        if (!raw) return false;
        const list = JSON.parse(raw) as Array<{ id: string; status: string }>;
        return list.find((item) => item.id === id)?.status === 'ready';
      },
      'demo-book-draft',
      { timeout: 25000 },
    );

    await page.goto('/books');
    await expect(
      page.locator('.space-persona-card', { hasText: DRAFT_TITLE }).getByText('可阅读'),
    ).toBeVisible();
  });

  test('同一 tick 连点「强制重新生成」：互斥生效，页最终完整且无残留错误提示', async ({ page }) => {
    await page.goto('/books');
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await page.getByRole('link', { name: `打开书籍 ${READY_TITLE}` }).click();
    await page.goto('/books/demo-book-fractions/pages/demo-book-fractions-p1');
    await expect(page.getByText('第 2/4 页')).toBeVisible();
    const blocksBefore = await page.locator('.books-block').count();

    // 同一 tick 内连点两次（第二次点击时 React 尚未提交忙态 → 真的打到引擎的互斥判定）
    const clicks = await page.evaluate(() => {
      const button = Array.from(document.querySelectorAll('button')).find((item) =>
        item.textContent?.includes('强制重新生成'),
      ) as HTMLButtonElement | undefined;
      if (!button) return 0;
      button.click();
      button.click();
      return 2;
    });
    expect(clicks).toBe(2);

    // 真的在重新生成（块占位取代正文），随后回到完整就绪；块数不变、无错误提示
    await expect(page.locator('.book-reader-block-generating').first()).toBeVisible({ timeout: 20000 });
    await expect(page.locator('.book-reader-block-generating')).toHaveCount(0, { timeout: 40000 });
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 20000 });
    expect(await page.locator('.books-block').count()).toBe(blocksBefore);
    await expect(page.getByText(/重新生成未完成/)).toHaveCount(0);
  });
});
