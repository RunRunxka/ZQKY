import { test, expect } from '@playwright/test';

// 与 services/navigation.ts 登记表一致的规划模块路由
// （/chat、/settings、/space、/knowledge-bases、/notebooks 自 D03/S5 起为已实现页面，
//  /reading 自 S5-D、/co-writer 与 /whisper 自 S5-E 起为实现页面，各自由对应 spec 覆盖）
const plannedRoutes = [
  '/papers',
  '/question-bank',
  '/templates',
  '/agents',
];

test('全部登记路由可直达并刷新，规划页内容统一且无假提交', async ({ page }) => {
  for (const route of plannedRoutes) {
    await page.goto(route);
    await expect(page.locator('.planned-page')).toBeVisible();
    await expect(page.locator('.planned-page .small-badge')).toHaveText('规划中');
    await expect(page.locator('.planned-page h1')).not.toHaveText('');
    await expect(page.locator('.planned-capabilities li').first()).toBeVisible();
    await page.reload();
    await expect(page.locator('.planned-page')).toBeVisible();
    expect(await page.locator('.planned-page form').count()).toBe(0);
    expect(await page.locator('.planned-page button').count()).toBe(0);
  }
});

test('导航可访问名称在收起、展开与底部入口保持一致', async ({ page }) => {
  await page.goto('/papers');
  await page.getByRole('button', { name: '收起项目导航' }).click();
  await expect(page.locator('.app-shell.nav-expanded')).toHaveCount(0);
  await page.getByRole('button', { name: '展开项目导航' }).click();
  await expect(page.locator('.app-shell.nav-expanded')).toHaveCount(1);
  await expect(page.locator('.global-nav .nav-group-label').first()).toBeHidden();
  for (const name of [
    '学习问答',
    '沉浸阅读',
    '智能组卷（规划中）',
    '教材资料库',
    '题库（规划中）',
    '模板中心（规划中）',
    'Agent 任务（规划中）',
    '设置',
  ]) {
    await expect(page.getByRole('button', { name, exact: true })).toHaveCount(1);
  }
  await page.getByRole('button', { name: '收起项目导航' }).click();
  await expect(page.getByRole('button', { name: '智能组卷（规划中）', exact: true })).toHaveCount(
    1,
  );
});

test('教案编辑后经新规划入口往返不丢草稿', async ({ page }) => {
  await page.goto('/lesson-plans');
  const title = page.getByRole('textbox', { name: '课题', exact: true });
  await title.fill('导航往返验证');
  await page.getByRole('button', { name: '智能组卷（规划中）', exact: true }).click();
  await expect(page).toHaveURL(/\/papers$/);
  await expect(page.getByRole('heading', { name: '智能组卷' })).toBeVisible();
  await page.getByRole('button', { name: '教案工作台', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '课题', exact: true })).toHaveValue(
    '导航往返验证',
  );
});

test('手机导航抽屉显示全部入口与规划标记，可进入规划页', async ({ page }, testInfo) => {
  for (const size of [
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    await page.goto('/papers');
    await expect(page.locator('.planned-page')).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`planned-${size.width}.png`) });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
  await page.getByRole('button', { name: '打开功能导航' }).click();
  const dialog = page.getByRole('dialog', { name: '功能导航' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('教学资源')).toBeVisible();
  await expect(
    dialog.getByRole('button', { name: '智能组卷（规划中）', exact: true }),
  ).toBeVisible();
  await expect(dialog.getByRole('button', { name: '设置', exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('mobile-drawer.png') });
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await page.getByRole('button', { name: '打开功能导航' }).click();
  await expect(dialog).toHaveCount(1);
  await dialog.getByRole('button', { name: '题库（规划中）', exact: true }).click();
  await expect(page).toHaveURL(/\/question-bank$/);
  await expect(page.locator('.planned-page')).toBeVisible();
  await expect(dialog).toHaveCount(0);
});

test('未知路径仍显示404而不是伪业务页面', async ({ page }) => {
  await page.goto('/definitely-missing');
  await expect(page.getByRole('heading', { name: '页面不存在' })).toBeVisible();
});

test('教材资料库页提供书籍与课程直达入口（T4：桌面侧栏不再有书籍顶级项）', async ({ page }) => {
  await page.goto('/knowledge-bases');
  const entry = page.locator('.kb-library-links');
  await expect(entry).toBeVisible();
  const booksLink = entry.locator('a[href="/books"]');
  const coursesLink = entry.locator('a[href="/courses"]');
  await expect(booksLink).toContainText('书籍');
  await expect(coursesLink).toContainText('课程');
  await booksLink.click();
  await expect(page).toHaveURL(/\/books$/);
  await expect(page.getByRole('heading', { name: '书籍' })).toBeVisible();
  await page.goto('/knowledge-bases');
  await page.locator('.kb-library-links a[href="/courses"]').click();
  await expect(page).toHaveURL(/\/courses$/);
  await expect(page.getByRole('heading', { name: '课程' })).toBeVisible();
});

test('教材资料库页入口在三种视口下不产生横向溢出', async ({ page }) => {
  for (const size of [
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    await page.goto('/knowledge-bases');
    await expect(page.locator('.kb-library-links')).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      `${size.width} 横向溢出`,
    ).toBe(true);
  }
});
