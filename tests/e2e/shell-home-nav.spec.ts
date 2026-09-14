import { test, expect, type Page } from '@playwright/test';

/**
 * B-H0R-SHELL v1 正式回归：R-02（唯一主页）、R-04（唯一当前菜单）、R-06（404/错误页统一壳）。
 * 不依赖后端；只验证公共壳、导航与状态页。
 */

const MAIN_NAV = 'nav[aria-label="项目功能导航"]';

async function currentItem(page: Page) {
  const nav = page.locator(MAIN_NAV);
  await expect(nav.locator('[aria-current="page"]')).toHaveCount(1);
  return nav.locator('[aria-current="page"]');
}

test.describe('R-02 唯一主页 /chat', () => {
  test('品牌按钮返回 /chat 且可访问名称与主页一致', async ({ page }) => {
    await page.goto('/settings');
    const brand = page.locator('.sidebar-brand');
    await expect(brand).toHaveAttribute('aria-label', '返回学习问答');
    await brand.click();
    await expect(page).toHaveURL(/\/chat$/);
  });

  test('手机头部品牌按钮同样返回 /chat', async ({ page }) => {
    // 桌面由左侧 sidebar-brand 承担；头部品牌在窄视口才显示，两处都必须回主页
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/books');
    const brand = page.locator('header .brand');
    await expect(brand).toBeVisible();
    await brand.click();
    await expect(page).toHaveURL(/\/chat$/);
  });

  test('404 与规划页的返回入口都指向 /chat', async ({ page }) => {
    await page.goto('/definitely-missing');
    await expect(page.getByRole('link', { name: '返回学习问答' })).toHaveAttribute('href', '/chat');
    await page.goto('/papers');
    await expect(page.getByRole('link', { name: '返回学习问答' })).toHaveAttribute('href', '/chat');
  });

  test('标题不再把教案工作台当作全站主页', async ({ page }) => {
    await page.goto('/chat');
    await expect(page).toHaveTitle(/学习问答/);
    await page.goto('/definitely-missing');
    await expect(page).toHaveTitle(/页面不存在/);
    expect(await page.title()).not.toContain('教案工作台');
  });
});

test.describe('R-04 每个已实现路由都有唯一当前菜单', () => {
  const implemented = [
    ['/chat', '学习问答'],
    ['/lesson-plans', '教案工作台'],
    ['/co-writer', '协同写作'],
    ['/reading', '沉浸阅读'],
    ['/reading/materials', '沉浸阅读'],
    ['/space', '学习空间'],
    ['/space/chat-history', '学习空间'],
    ['/space/personas', '学习空间'],
    ['/knowledge-bases', '教材资料库'],
    ['/books', '书籍'],
    ['/settings', '设置'],
    ['/papers', '智能组卷'],
    ['/question-bank', '题库'],
  ] as const;

  for (const [route, expected] of implemented) {
    test(`${route} 桌面侧栏当前项为「${expected}」`, async ({ page }) => {
      await page.goto(route);
      await expect(page.locator(MAIN_NAV)).toBeVisible();
      const item = await currentItem(page);
      await expect(item).toHaveAttribute('aria-label', new RegExp(`^${expected}`));
    });
  }

  const hiddenWithParent = [
    ['/whisper', '协同写作'],
    ['/notebooks', '学习空间'],
    ['/courses', '书籍'],
  ] as const;

  for (const [route, parent] of hiddenWithParent) {
    test(`隐藏直达页 ${route} 标记可见父菜单「${parent}」`, async ({ page }) => {
      await page.goto(route);
      const item = await currentItem(page);
      await expect(item).toHaveAttribute('aria-label', new RegExp(`^${parent}`));
    });
  }

  test('详情页保持父级当前菜单（唯一）', async ({ page }) => {
    await page.goto('/space/questions');
    await expect(await currentItem(page)).toHaveAttribute('aria-label', /^学习空间/);
    await page.goto('/notebooks/unknown-id');
    await expect(await currentItem(page)).toHaveAttribute('aria-label', /^学习空间/);
  });

  test('手机抽屉标记隐藏项自身且仍唯一', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/whisper');
    await page.getByRole('button', { name: '打开功能导航' }).click();
    const panel = page.getByRole('dialog', { name: '功能导航' });
    await expect(panel.locator('[aria-current="page"]')).toHaveCount(1);
    await expect(panel.getByRole('button', { name: 'Whisper 密室' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });
});

test.describe('R-06 404/错误页统一公共壳', () => {
  test('未知路径 404 保留公共壳、导航与唯一当前项', async ({ page }) => {
    await page.goto('/definitely-missing');
    await expect(page.locator(MAIN_NAV)).toBeVisible();
    await expect(page.locator('.app-shell')).toHaveCount(1);
    await expect(page.locator('.status-page')).toHaveCount(1);
    await expect(page.getByRole('heading', { name: '页面不存在' })).toBeVisible();
    // 404 没有对应菜单项，不应谎报当前项
    await expect(page.locator(`${MAIN_NAV} [aria-current="page"]`)).toHaveCount(0);
  });

  test('独立模块内未知深层路径也恰好一层壳', async ({ page }) => {
    await page.goto('/books/unknown-book/pages/unknown-page');
    await expect(page.locator(MAIN_NAV)).toHaveCount(1);
    await expect(page.locator('.app-shell')).toHaveCount(1);
  });

  test('404 返回入口可用', async ({ page }) => {
    await page.goto('/definitely-missing');
    await page.getByRole('link', { name: '返回学习问答' }).click();
    await expect(page).toHaveURL(/\/chat$/);
  });
});

test.describe('折叠保持与手机抽屉', () => {
  test('折叠偏好跨页保持一致（含 404 与独立模块）', async ({ page }) => {
    await page.goto('/chat');
    await page.getByRole('button', { name: '收起项目导航' }).click();
    await expect(page.locator('.app-shell')).not.toHaveClass(/nav-expanded/);
    for (const route of ['/books', '/definitely-missing', '/settings']) {
      await page.goto(route);
      await expect(page.locator('.app-shell')).not.toHaveClass(/nav-expanded/);
    }
  });

  test('手机抽屉焦点圈定、Escape 关闭并返回触发按钮', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/books');
    const trigger = page.getByRole('button', { name: '打开功能导航' });
    await trigger.click();
    const panel = page.getByRole('dialog', { name: '功能导航' });
    await expect(panel).toBeVisible();
    await expect(panel.locator('[aria-current="page"]')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(panel).toBeHidden();
    await expect(trigger).toBeFocused();
  });
});
