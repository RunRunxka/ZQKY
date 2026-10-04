import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test';

// 每例使用隔离 context，通过界面载入本地演示。API 503 是明确的失败替身；
// 本测试不调用真实模型，不编译、重建、附加资料或保存书稿/大纲。
test.use({ storageState: { cookies: [], origins: [] } });

const viewports = [
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 1024, height: 768 },
  { width: 390, height: 844 },
];
const readyTitle = '分数入门（演示书籍）';
const draftTitle = '修辞手法小册（演示草稿）';
const courseTitle = '七年级数学（演示课程）';

type LayoutEvidence = {
  stage: string;
  url: string;
  rootOverflow: number;
  workspaceOverflow: number | null;
};

async function waitForEntrance(page: Page): Promise<void> {
  await expect(page.locator('.unified-shell')).toHaveAttribute('data-navigation-ready', 'true');
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  await expect
    .poll(() =>
      page
        .locator('[data-motion-reveal], .books-reader, .workspace-modal-body')
        .evaluateAll((nodes) =>
          nodes.every(
            (node) =>
              !(node instanceof HTMLElement) ||
              (node.style.transform === '' && node.style.opacity === ''),
          ),
        ),
    )
    .toBe(true);
}

async function captureStage(
  page: Page,
  info: TestInfo,
  stage: string,
  anchor: Locator,
  evidence: LayoutEvidence[],
): Promise<void> {
  await expect(anchor).toBeVisible();
  // 正文和大纲在窄屏首屏下方；验证真实滚动可到达，而非要求所有详情同时塞进首屏。
  await anchor.scrollIntoViewIfNeeded();
  await waitForEntrance(page);
  await expect(anchor).toBeInViewport();
  const layout = await page.evaluate(() => {
    const workspace = document.querySelector<HTMLElement>('.module-workspace-content');
    return {
      rootOverflow: document.documentElement.scrollWidth - innerWidth,
      workspaceOverflow: workspace ? workspace.scrollWidth - workspace.clientWidth : null,
    };
  });
  expect(layout.rootOverflow, `${stage}: 根页面横向溢出`).toBeLessThanOrEqual(1);
  if (layout.workspaceOverflow !== null) {
    expect(layout.workspaceOverflow, `${stage}: 工作区横向溢出`).toBeLessThanOrEqual(1);
  }
  evidence.push({ stage, url: page.url(), ...layout });
  await page.screenshot({ path: info.outputPath(`${stage}.png`), animations: 'disabled' });
}

for (const viewport of viewports) {
  test(`资源详情视觉：${viewport.width}，本地演示与失败替身`, async ({ page }, info) => {
    test.setTimeout(120000);
    await page.setViewportSize(viewport);
    await page.route('**/api/v1/**', (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '隔离资源视觉验收：服务暂不可用' }),
      }),
    );
    const evidence: LayoutEvidence[] = [];

    await page.goto('/books');
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await expect(page.getByRole('status').filter({ hasText: '已载入演示书籍' })).toBeVisible();
    const readyCard = page.locator('.space-persona-card', { hasText: readyTitle });
    const draftCard = page.locator('.space-persona-card', { hasText: draftTitle });
    await expect(page.locator('.space-persona-card')).toHaveCount(2);
    await expect(readyCard.getByText('可阅读', { exact: true })).toBeVisible();
    await expect(draftCard.getByRole('button', { name: '继续创建' })).toBeVisible();
    await captureStage(
      page,
      info,
      'books-list',
      readyCard.getByRole('link', { name: `打开书籍 ${readyTitle}` }),
      evidence,
    );
    await captureStage(
      page,
      info,
      'books-list-draft',
      draftCard.getByRole('link', { name: `打开书籍 ${draftTitle}` }),
      evidence,
    );

    await readyCard.getByRole('link', { name: `打开书籍 ${readyTitle}` }).click();
    await expect(page).toHaveURL(/\/books\/demo-book-fractions\/pages\/demo-book-fractions-p0$/);
    await expect(
      page.getByRole('heading', { name: readyTitle, exact: true, level: 1 }),
    ).toBeVisible();
    await expect(page.getByRole('note').filter({ hasText: '本地模拟编译产物' })).toBeVisible();
    await expect(page.getByText('第 1/4 页', { exact: true })).toBeVisible();
    const readerQuestion = page.getByText(/这一页的主要目标是/);
    await captureStage(page, info, 'books-reader', readerQuestion, evidence);
    await expect(
      page.locator('.books-reader').getByRole('link', { name: '下一页', exact: true }),
    ).toHaveAttribute('href', '/books/demo-book-fractions/pages/demo-book-fractions-p1');

    await page.goto('/books/demo-book-fractions/pages/not-a-page');
    const missingPage = page.getByText('章节页不存在或已被重建', { exact: true });
    const recoveryLink = page.getByRole('link', { name: '返回书籍首页' });
    await expect(recoveryLink).toBeVisible();
    await captureStage(page, info, 'books-missing-page', missingPage, evidence);
    await recoveryLink.click();
    await expect(page).toHaveURL(/\/books\/demo-book-fractions\/pages\/demo-book-fractions-p0$/);
    await captureStage(page, info, 'books-reader-recovered', readerQuestion, evidence);

    await page.goto('/books');
    await page
      .locator('.space-persona-card', { hasText: draftTitle })
      .getByRole('button', { name: '继续创建' })
      .click();
    await expect(page).toHaveURL(/\/books\/demo-book-draft$/);
    await expect(page.getByRole('heading', { name: draftTitle, exact: true })).toBeVisible();
    await expect(page.getByRole('note')).toContainText('本地模板模拟生成，不调用模型');
    await expect(page.getByRole('heading', { name: '拟定章节', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '确认提案（进入大纲）' })).toBeEnabled();
    await captureStage(
      page,
      info,
      'books-proposal',
      page.getByText('提案（模拟）', { exact: true }),
      evidence,
    );

    await page.goto('/courses');
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await expect(page.getByRole('status').filter({ hasText: '已载入演示课程' })).toBeVisible();
    const courseLink = page.getByRole('link', { name: `打开课程 ${courseTitle}` });
    await captureStage(page, info, 'courses-list', courseLink, evidence);
    await courseLink.click();
    await expect(page).toHaveURL(/\/courses\/demo-course-math$/);
    await expect(page.getByRole('note')).toContainText('以下大纲进度为学员手判');
    await captureStage(
      page,
      info,
      'course-detail',
      page.getByRole('heading', { name: courseTitle, exact: true }),
      evidence,
    );

    const outlineHeading = page.getByRole('heading', {
      name: '大纲（1/2 已完成，下一单元：一元一次方程）',
      exact: true,
    });
    await expect(
      page.getByRole('checkbox', { name: '标记「一元一次方程」为已完成' }),
    ).not.toBeChecked();
    await captureStage(page, info, 'course-outline', outlineHeading, evidence);
    await page.getByRole('button', { name: '编辑大纲', exact: true }).click();
    const outlineText = page.getByLabel('大纲文本', { exact: true });
    await expect(outlineText).toHaveValue(/一元一次方程/);
    await expect(page.getByRole('button', { name: '保存大纲', exact: true })).toBeEnabled();
    await captureStage(page, info, 'course-outline-edit', outlineText, evidence);
    await page.getByRole('button', { name: '取消', exact: true }).click();
    await expect(outlineText).toHaveCount(0);
    await expect(outlineHeading).toBeVisible();
    await expect(page.getByRole('progressbar', { name: '大纲完成进度' })).toHaveAttribute(
      'aria-valuenow',
      '50',
    );

    await page.getByRole('button', { name: '附加资料', exact: true }).click();
    const resourceDialog = page.getByRole('dialog', { name: '附加课程资料', exact: true });
    await expect(resourceDialog).toBeVisible();
    await expect(resourceDialog.getByRole('heading', { name: '书籍', exact: true })).toBeVisible();
    await expect(resourceDialog.getByText(readyTitle, { exact: true })).toBeVisible();
    await captureStage(
      page,
      info,
      'course-resource-modal',
      resourceDialog.getByText(readyTitle, { exact: true }),
      evidence,
    );
    const dialogLayout = await resourceDialog.evaluate((element) => {
      const bounds = element.getBoundingClientRect();
      return {
        left: bounds.left,
        right: bounds.right,
        top: bounds.top,
        bottom: bounds.bottom,
        width: innerWidth,
        height: innerHeight,
        contentOverflow: element.scrollWidth - element.clientWidth,
      };
    });
    expect(dialogLayout.left).toBeGreaterThanOrEqual(-1);
    expect(dialogLayout.right).toBeLessThanOrEqual(dialogLayout.width + 1);
    expect(dialogLayout.top).toBeGreaterThanOrEqual(-1);
    expect(dialogLayout.bottom).toBeLessThanOrEqual(dialogLayout.height + 1);
    expect(dialogLayout.contentOverflow).toBeLessThanOrEqual(1);
    await resourceDialog.getByRole('button', { name: '关闭对话框', exact: true }).click();
    await expect(resourceDialog).toHaveCount(0);

    await info.attach('resource-visual-layout', {
      body: JSON.stringify(
        { viewport, data: '本地演示；API 503 失败替身', stages: evidence },
        null,
        2,
      ),
      contentType: 'application/json',
    });
  });
}
