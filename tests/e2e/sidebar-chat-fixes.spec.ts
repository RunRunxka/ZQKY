import { test, expect } from '@playwright/test';

const routes = [
  ['/chat', '学习问答'],
  ['/lesson-plans', '教案工作台'],
  ['/co-writer', '协同写作'],
  ['/reading', '沉浸阅读'],
  ['/space', '学习空间'],
  ['/knowledge-bases', '教材资料库'],
  ['/books', '教材资料库'],
  ['/papers', '智能组卷（规划中）'],
  ['/question-bank', '题库（规划中）'],
  ['/templates', '模板中心（规划中）'],
  ['/agents', 'Agent 任务（规划中）'],
  ['/settings', '设置'],
  ['/space/chat-history', '学习空间'],
];
test('全站侧栏图标、宽度和当前菜单一致，折叠偏好跨路由保留', async ({ page }, info) => {
  let icons: string[] = [];
  for (const [route, name] of routes) {
    await page.goto(route);
    const nav = page.getByRole('navigation', { name: '项目功能导航' });
    await expect(nav.getByRole('button', { name, exact: true })).toHaveAttribute(
      'aria-current',
      'page',
    );
    await expect(nav.locator('[aria-current="page"]')).toHaveCount(1);
    expect((await nav.boundingBox())!.width).toBe(220);
    expect((await nav.boundingBox())!.y).toBe(0);
    const currentIcons = await nav
      .locator('.global-nav-item svg')
      .evaluateAll((nodes) => nodes.map((node) => node.innerHTML));
    if (!icons.length) icons = currentIcons;
    else expect(currentIcons).toEqual(icons);
  }
  await page.getByRole('button', { name: '收起项目导航' }).click();
  await page.getByRole('navigation').getByRole('button', { name: '学习问答', exact: true }).click();
  await expect(page.getByRole('button', { name: '展开项目导航' })).toBeVisible();
  await expect(page.locator('.global-nav')).toHaveCSS('width', '56px');
  // 学习记录并入全站导航（UX-PERF-CLOSEOUT v1）：聊天区不再有独立中栏，
  // 也不留下 236px 空列；聊天主区紧邻导航。
  await expect(page.locator('.chat-page > .chat-sessions')).toHaveCount(0);
  const sidebarSessions = page.locator('.global-nav > .sidebar-content');
  await expect(sidebarSessions).toBeHidden(); // 收起态只有图标栏
  const navBox = (await page.locator('.global-nav').boundingBox())!;
  expect((await page.locator('.chat-main').boundingBox())!.x).toBe(navBox.x + navBox.width);
  await page.getByRole('button', { name: '展开项目导航' }).click();
  await expect(sidebarSessions).toBeVisible();
  // 侧栏展开有 200ms grid-template-columns 过渡：等宽度稳定后再量几何，
  // 否则会取到过渡中间值（例如 62px）而不是最终 220px。
  await expect(page.locator('.global-nav')).toHaveCSS('width', '220px');
  const expandedNav = (await page.locator('.global-nav').boundingBox())!;
  expect(expandedNav.width).toBe(220);
  expect((await page.locator('.chat-main').boundingBox())!.x).toBe(
    expandedNav.x + expandedNav.width,
  );
  // 会话区在主导航下方独立滚动，底部导航仍可见
  const sessionsBox = (await sidebarSessions.boundingBox())!;
  const bottomBox = (await page.locator('.global-nav .nav-bottom').boundingBox())!;
  expect(sessionsBox.y).toBeGreaterThan(0);
  expect(sessionsBox.y + sessionsBox.height).toBeLessThanOrEqual(bottomBox.y + bottomBox.height);
  await expect(bottomBox.y + bottomBox.height).toBeLessThanOrEqual(900);
  await page.screenshot({ path: info.outputPath('sidebar-learning-records.png') });
});

for (const [route, name] of [
  ['/chat', '学习问答'],
  ['/lesson-plans', '教案工作台'],
  ['/space/chat-history', '学习空间'],
]) {
  test(`手机抽屉焦点、遮罩、关闭与当前菜单 ${route}`, async ({ page }, info) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(route);
    const trigger = page.getByRole('button', { name: '打开功能导航' });
    await trigger.click();
    const drawer = page.getByRole('dialog', { name: '功能导航' });
      const current = drawer.getByRole('button', { name, exact: true });
      await expect(current).toBeFocused();
      await expect(drawer).toHaveCSS('transform', 'none');
    await expect(current).toHaveAttribute('aria-current', 'page');
    await expect(drawer.locator('[aria-current="page"]')).toHaveCount(1);
    expect(
      await drawer.evaluate((el) => getComputedStyle(el, '::backdrop').backgroundColor),
    ).not.toBe('rgba(0, 0, 0, 0)');
      await page.screenshot({ path: info.outputPath('mobile-drawer.png') });
      await drawer.getByRole('button', { name: '关闭功能导航' }).focus();
    await page.keyboard.press('Shift+Tab');
    await expect(drawer.getByRole('button', { name: '设置', exact: true })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(drawer.getByRole('button', { name: '关闭功能导航' })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(drawer).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await trigger.click();
    await drawer.getByRole('button', { name: '关闭功能导航' }).click();
    await expect(trigger).toBeFocused();
    await trigger.click();
    await page.mouse.click(380, 430);
    await expect(drawer).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await trigger.click();
    await drawer.getByRole('button', { name: '设置', exact: true }).click();
    await expect(page).toHaveURL(/\/settings$/);
    await page.getByRole('button', { name: '打开功能导航' }).click();
    await expect(
      page.getByRole('dialog').getByRole('button', { name: '设置', exact: true }),
    ).toBeFocused();
  });
}

test('聊天不再提供模拟模式，也不创建模拟数据库', async ({ page }) => {
  await page.goto('/chat?mode=mock');
  await expect(page.getByRole('textbox', { name: '输入问题' })).toBeVisible();
  await expect(page.getByRole('button', { name: '模拟', exact: true })).toHaveCount(0);
  await expect(page.getByRole('group', { name: '对话模式' })).toHaveCount(0);
  expect(
    await page.evaluate(async () => (await indexedDB.databases()).map((db) => db.name)),
  ).not.toContain('zhiqikeyuan-chat-mock');
});
