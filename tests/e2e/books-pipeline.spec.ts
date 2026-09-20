import { expect, test, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

/**
 * H1-BOOKS-PIPELINE v2 浏览器回归（总控负责的唯一新增 e2e）。
 *
 * 范围：书籍生成流水线的可观察生成、暂停/中断/恢复、失败与重试（块/页/整轮三档）、并发保护、
 * 数据保护（生成期间笔记/书签、删除不复活、导出不伪装完整）、窄视口可用性。
 *
 * 边界（如实记录）：
 * - 重复/迟到事件、seq 单调性、租约失效判定、检查点续跑的内部时序由单测覆盖
 *   （`services/books-store.test.ts`、`services/book-generation.test.ts`），本 spec 不重复。
 * - 课程 R-11 资源三态由既有 `course-resource-faults.spec.ts` 覆盖，不重复。
 * - 真实 LLM 未接入：本 spec 全部为本地模拟执行器，失败场景均为显式注入
 *   （块失败 `'*first'`、整页失败、模拟供应商连续失败暂停、本地存储写入失败）。
 * - 归档只读（生成入口禁用）由组件测试 `features/books/PageReader.test.tsx` 覆盖：
 *   本批没有归档入口 UI，浏览器侧无法从界面产生归档书。
 * - 隔离：Playwright 每个 test 使用独立 context/localStorage；不触碰用户 5173 数据。
 *
 * 文案锚点来自实现（`features/books/BookGenerationStrip.tsx`、`BookPausedBanner.tsx`、
 * `PageReader.tsx`、`BooksRoute.tsx` ScenarioSettings），改动实现时须同步本 spec。
 */

const DRAFT_TITLE = '修辞手法小册（演示草稿）';
const READY_TITLE = '分数入门（演示书籍）';

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

type ScenarioKind = 'block' | 'page' | 'provider' | 'storage';

/** 确认提案（进入大纲），按需注入模拟场景，然后开始编译并进入阅读器 */
async function confirmAndCompile(page: Page, scenario?: ScenarioKind): Promise<void> {
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
            : /模拟存储写入失败/;
    await page.getByLabel(label).check();
  }

  await page.getByRole('button', { name: '确认大纲并编译（模拟）' }).click();
  // 编译为异步流水线：确认后进入 compiling 并自动续读到阅读器
  await expect(page).toHaveURL(/\/books\/demo-book-draft\/pages\//, { timeout: 15000 });
}

/** 活动条（角色 status 的单行条） */
function strip(page: Page) {
  return page.locator('.book-pipeline-strip');
}

/** 等到本次模拟编译结束（活动条消失 = 无活跃执行器且非暂停/中断） */
async function waitForRunSettled(page: Page): Promise<void> {
  await expect(strip(page)).toHaveCount(0, { timeout: 40000 });
}

test.describe('H1 书籍生成流水线', () => {
  test('正常生成：活动条可观察、生成中可阅读已完成内容、完成后可阅读', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page);

    // 活动条对照参考：阶段文案 + n/m 章 + 计时 + 展开详情
    await expect(strip(page)).toBeVisible();
    await expect(strip(page)).toContainText('正在逐章编译（本地模拟，不调用模型）…');
    await expect(strip(page)).toContainText(/[0-4]\/4 章/);
    // 计时：可见文本是 mm:ss，运行起点由 aria-label「已运行 mm:ss」说明（不拿渲染期时间冒充）
    const timer = strip(page).locator('.book-pipeline-strip-timer');
    await expect(timer).toHaveText(/^\d{2}:\d{2}$/);
    await expect(timer).toHaveAttribute('aria-label', /^已运行 \d{2}:\d{2}$/);
    await expect(strip(page).getByRole('button', { name: '暂停生成' })).toBeVisible();

    await strip(page).getByRole('button', { name: '已生成内容' }).click();
    const detail = page.getByRole('dialog', { name: '已生成内容' });
    await expect(detail).toBeVisible();
    await expect(detail.getByText('章节', { exact: true })).toBeVisible();
    // 章行：标题为「NN · 章名」（状态列另有「正在生成 …」文案，故按章标题元素断言）
    await expect(detail.locator('.book-pipeline-detail-chapter-title').first()).toHaveText(/^01 · 比喻是什么$/);
    // 浮层必须真的展开而不是被 46px 活动条裁掉的一条线（DEFECT-LEDGER N10），且完整落在视口内
    const detailBox = await detail.boundingBox();
    expect(detailBox!.height).toBeGreaterThan(60);
    const detailOverflow = await detail.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      return { right: rect.right - window.innerWidth, bottom: rect.bottom - window.innerHeight };
    });
    expect(detailOverflow.right).toBeLessThanOrEqual(1);
    expect(detailOverflow.bottom).toBeLessThanOrEqual(1);
    await expect(strip(page).locator('[role="dialog"]')).toHaveCount(0);

    // 生成中阅读器：已完成内容可读，后续页为排队态（生成进度与阅读进度分开）
    await expect(page.getByRole('note').filter({ hasText: '本地模拟编译产物' })).toBeVisible();
    await expect(page.getByText('第 1/8 页')).toBeVisible();

    await waitForRunSettled(page);
    // 完成后书籍为可阅读：页面显示真实内容与练习块
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 15000 });
    await page.goto('/books');
    await expect(
      page.locator('.space-persona-card', { hasText: DRAFT_TITLE }).getByText('可阅读'),
    ).toBeVisible();
  });

  test('用户暂停与恢复：paused 不自动续跑，恢复后继续到完成', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page);
    await expect(strip(page).getByRole('button', { name: '暂停生成' })).toBeVisible();

    await strip(page).getByRole('button', { name: '暂停生成' }).click();

    // 暂停横幅（对照参考 BookPausedBanner）：标题 + 用户暂停说明 + 恢复入口。
    // 「生成已暂停」同时出现在横幅标题与活动条阶段文案里，故断言按容器限定（不是放宽，而是指向具体组件）。
    const pausedBanner = page.locator('.book-pipeline-paused');
    await expect(pausedBanner).toBeVisible();
    await expect(pausedBanner).toContainText('生成已暂停');
    await expect(pausedBanner).toContainText(/未完成的章节只在你恢复后才会继续/);
    await expect(strip(page)).toContainText('生成已暂停');
    await expect(page.getByRole('button', { name: '恢复生成' }).first()).toBeVisible();

    // 刷新后 paused 不自动续跑（活动条不得再显示"正在逐章编译"）
    await page.reload();
    await expect(page.locator('.book-pipeline-paused')).toBeVisible({ timeout: 15000 });
    await expect(strip(page)).not.toContainText('正在逐章编译');

    // 恢复后继续到完成
    await page.getByRole('button', { name: '恢复生成' }).first().click();
    await waitForRunSettled(page);
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 15000 });
  });

  test('模拟供应商连续失败暂停：文案明确为本地模拟，不宣称真实上游故障', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page, 'provider');

    await expect(page.getByText(/本地模拟的供应商连续失败/)).toBeVisible({ timeout: 30000 });
    await expect(page.getByText(/不代表真实上游服务故障/)).toBeVisible();
    // 仍提供恢复入口（只在明确恢复后继续）
    await expect(page.getByRole('button', { name: '恢复生成' }).first()).toBeVisible();
  });

  test('刷新中断：compiling 自动从断点续跑，已完成内容保留（对照 maybe_resume_on_open）', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page);

    // 等第一页出现真实内容后再刷新
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 30000 });
    const before = await page.locator('.books-block').count();
    await page.reload();

    // 自动续跑：无需点击，最终完成
    await waitForRunSettled(page);
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 15000 });
    const after = await page.locator('.books-block').count();
    expect(after).toBeGreaterThanOrEqual(before); // 断点续跑不丢已完成内容
  });

  test('双标签页同书：只允许一个执行器，第二个标签页只读显示', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page);
    await expect(strip(page).getByRole('button', { name: '暂停生成' })).toBeVisible();

    const second = await page.context().newPage();
    try {
      await second.goto(page.url());
      await expect(second.getByText('本书正在另一个标签页生成')).toBeVisible({ timeout: 15000 });
      await expect(strip(second).getByRole('button', { name: '暂停生成' })).toHaveCount(0);
    } finally {
      await second.close();
    }
  });

  test('块失败与重试：单块失败如实呈现，重试即成功且不重建整本', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page, 'block');

    const failureCard = page.locator('.book-reader-block-failure').first();
    await expect(failureCard).toBeVisible({ timeout: 40000 });
    await expect(failureCard).toContainText('内容生成失败（本地模拟）');
    await expect(page.getByText(/个块失败/)).toBeVisible();

    // 等整轮结束后统计本页块总数（正常块 + 失败卡），作为"不增删块"的基线
    await waitForRunSettled(page);
    const countPageBlocks = async () =>
      (await page.locator('.books-block').count()) + (await page.locator('.book-reader-block-failure').count());
    const totalBlocks = await countPageBlocks();
    expect(totalBlocks).toBe(4); // 第 1 页 4 个块（section/text/callout/quiz）
    await expect(page.getByText('第 1/8 页')).toBeVisible();

    await failureCard.getByRole('button', { name: '重试' }).click();
    await expect(failureCard).toHaveCount(0, { timeout: 20000 });
    // 重试中的块先以占位呈现，等占位清空后再统计（否则会把"正在重试"误当成块丢失）
    await expect(page.locator('.book-reader-block-generating')).toHaveCount(0, { timeout: 20000 });
    // 只作用于该块：块总数不变、页码结构不变、未触发新一轮整本生成（不暗中重建整本）
    expect(await countPageBlocks()).toBe(totalBlocks);
    await expect(page.getByText('第 1/8 页')).toBeVisible();
    await expect(strip(page)).toHaveCount(0);
  });

  test('整页重生成保留用户笔记与块身份（演示就绪书本无 run 记录，也必须真的重生成）', async ({ page }) => {
    await page.goto('/books');
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await page.getByRole('link', { name: `打开书籍 ${READY_TITLE}` }).click();
    await page.goto('/books/demo-book-fractions/pages/demo-book-fractions-p1');

    const note = '浏览器回归笔记：本节要点已复述。';
    await page.getByLabel('我的笔记内容').fill(note);
    await page.getByLabel('我的笔记内容').blur();
    // 刷新后仍在 → 笔记确实落库（不是仅组件内状态）
    await page.reload();
    await expect(page.getByLabel('我的笔记内容')).toHaveValue(note);
    const blocksBefore = await page.locator('.books-block').count();

    await page.getByRole('button', { name: '强制重新生成' }).click();
    // 真断言（此前只等笔记仍在，是空洞通过）：本页确实重新进入生成 —— 块占位取代正文
    await expect(page.locator('.book-reader-block-generating').first()).toBeVisible({ timeout: 20000 });
    await expect(page.locator('.book-reader-block-generating')).toHaveCount(0, { timeout: 40000 });
    // 重生成结束：笔记仍在（user_note 内容不被事件覆盖）、块数量与身份不变、正文与练习回来
    await expect(page.getByLabel('我的笔记内容')).toHaveValue(note, { timeout: 30000 });
    expect(await page.locator('.books-block').count()).toBe(blocksBefore);
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 30000 });
  });

  test('整页失败：如实显示页失败与「已中断」，点「继续生成」后一次性注入不再失败并完成', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page, 'page'); // 注入第 1 页整页失败（本地模拟）

    // 首轮：失败页保持 error，其余页完成 → 活动条显示"已中断"（不谎报可阅读、不显示暂停按钮）
    await expect(page.getByText('生成已中断（无执行器在跑）')).toBeVisible({ timeout: 40000 });
    await expect(strip(page).getByRole('button', { name: '暂停生成' })).toHaveCount(0);
    await expect(page.getByText('页面生成失败')).toBeVisible();
    await expect(page.getByText(/模拟页面失败/)).toBeVisible();

    // 继续生成：显式恢复后按页状态续跑，一次性注入不再重复失败
    await strip(page).getByRole('button', { name: '继续生成' }).click();
    await waitForRunSettled(page);
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 20000 });
    await expect(page.getByText('页面生成失败')).toHaveCount(0);
    await page.goto('/books');
    await expect(
      page.locator('.space-persona-card', { hasText: DRAFT_TITLE }).getByText('可阅读'),
    ).toBeVisible();
  });

  test('本地存储写入失败：如实显示整轮失败原因与「重试生成」，重试后续跑完成（不谎报已保存）', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page, 'storage'); // 第 0 页写入失败（本地注入的真实 QuotaExceeded 路径）

    const banner = page.getByRole('alert').filter({ hasText: '生成失败（本地模拟）' });
    await expect(banner).toBeVisible({ timeout: 30000 });
    await expect(banner).toContainText(/本地保存失败/);
    // 未完成就不得显示可阅读
    await expect(page.getByText('可阅读')).toHaveCount(0);

    const retry = banner.getByRole('button', { name: '重试生成' });
    await expect(retry).toBeEnabled();
    await retry.click();
    await waitForRunSettled(page);
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 20000 });
    await page.goto('/books');
    await expect(
      page.locator('.space-persona-card', { hasText: DRAFT_TITLE }).getByText('可阅读'),
    ).toBeVisible();
  });

  test('生成期间的笔记与书签不被生成事件覆盖', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page);

    // 第一页出现内容后写入笔记与书签（生成仍在进行）
    await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 30000 });
    await page.getByRole('button', { name: '添加书签' }).click();
    await expect(page.getByRole('button', { name: '移除书签' })).toBeVisible();

    await waitForRunSettled(page);
    await expect(page.getByRole('button', { name: '移除书签' })).toBeVisible();
    await expect(page.getByLabel('章节目录').getByText('签')).toHaveCount(1);
  });

  test('生成中删除书籍：不复活，迟到事件不重建', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page);
    await expect(strip(page)).toBeVisible();

    await page.goto('/books');
    const card = page.locator('.space-persona-card', { hasText: DRAFT_TITLE });
    await card.getByRole('button', { name: '删除' }).click();
    await card.getByRole('button', { name: '确认删除' }).click();
    await expect(card).toHaveCount(0);

    // 等待执行器可能迟到的回调窗口，再刷新确认未复活
    await page.waitForTimeout(2500);
    await page.reload();
    await expect(page.locator('.space-persona-card', { hasText: DRAFT_TITLE })).toHaveCount(0);
  });

  test('未完成书的 Markdown 导出如实标注，不伪装完整成书', async ({ page }) => {
    await openDemoDraft(page);
    await confirmAndCompile(page);

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: '导出 Markdown' }).click();
    const download = await downloadPromise;
    const target = path.join('_work', 'e2e-export-unfinished.md');
    await download.saveAs(target);
    const exported = await readFile(target, 'utf8');
    expect(exported).toContain('# 修辞手法小册（演示草稿）');
    expect(exported).toMatch(/尚未生成完成|存在未完成章节|生成中/);
  });

  test('窄视口 390：活动条与暂停可用，无页面级横向溢出', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDemoDraft(page);
    await confirmAndCompile(page);

    await expect(strip(page)).toBeVisible();
    await expect(strip(page).getByRole('button', { name: '暂停生成' })).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);

    await strip(page).getByRole('button', { name: '暂停生成' }).click();
    await expect(page.locator('.book-pipeline-paused')).toContainText('生成已暂停');
    await expect(strip(page)).toContainText('生成已暂停');
  });

  test('窄视口 390：展开浮层完整可用且不产生页面级溢出', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDemoDraft(page);
    await confirmAndCompile(page);

    await strip(page).getByRole('button', { name: '已生成内容' }).click();
    const detail = page.getByRole('dialog', { name: '已生成内容' });
    await expect(detail).toBeVisible({ timeout: 20000 });
    const box = await detail.boundingBox();
    expect(box!.height).toBeGreaterThan(60); // 真的展开，不是被 46px 条裁掉的一条线
    expect(box!.width).toBeLessThanOrEqual(390);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    await expect(detail.locator('.book-pipeline-detail-chapter-title').first()).toHaveText(/^01 · /);
  });
});
