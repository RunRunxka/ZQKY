import { test, expect } from '@playwright/test';

const viewports = [
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 1024, height: 768 },
  { width: 390, height: 844 },
];
const routes = [
  '/chat',
  '/knowledge-bases',
  '/knowledge-points',
  '/question-bank',
  '/assessments',
  '/learning-analysis',
  '/practices',
  '/lesson-plans',
  '/books',
  '/courses',
  '/settings',
  '/papers',
  '/co-writer',
  '/reading',
  '/space',
  '/templates',
  '/ui-missing-page',
];

for (const viewport of viewports) {
  test(`全站视觉基础：${viewport.width}，空态与失败可见、排版对齐`, async ({ page }, info) => {
    test.setTimeout(120000);
    await page.setViewportSize(viewport);
    // Deliberate failure coverage in an isolated context; no production backend or credentials.
    await page.route('**/api/v1/**', (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '隔离视觉验收：服务暂不可用' }),
      }),
    );
    const measurements = [];
    for (const route of routes) {
      await page.goto(route);
      await expect(page.locator('.unified-shell')).toHaveAttribute('data-navigation-ready', 'true');
      await page.evaluate(() => document.fonts.ready);
      await expect
        .poll(() =>
          page
            .locator('[data-motion-reveal]')
            .evaluateAll((nodes) =>
              nodes.every((node) => !(node instanceof HTMLElement) || node.style.transform === ''),
            ),
        )
        .toBe(true);
      await expect(page.locator('h1:visible, h2:visible').first()).toBeVisible();
      const layout = await page.evaluate(() => {
        const header = document.querySelector<HTMLElement>('.space-header');
        const content = document.querySelector<HTMLElement>('.space-content');
        const shell = document.querySelector<HTMLElement>('.unified-shell');
        return {
          overflow: document.documentElement.scrollWidth - innerWidth,
          header: header
            ? { x: header.getBoundingClientRect().x, width: header.getBoundingClientRect().width }
            : null,
          content: content
            ? { x: content.getBoundingClientRect().x, width: content.getBoundingClientRect().width }
            : null,
          sidebarWidth: shell?.querySelector<HTMLElement>('.global-nav')?.getBoundingClientRect()
            .width,
        };
      });
      expect(layout.overflow, route).toBeLessThanOrEqual(1);
      if (layout.header && layout.content) {
        expect(
          Math.abs(layout.header.x - layout.content.x),
          `${route}: left alignment`,
        ).toBeLessThanOrEqual(1);
        expect(
          Math.abs(layout.header.width - layout.content.width),
          `${route}: shared width`,
        ).toBeLessThanOrEqual(1);
      }
      if (viewport.width >= 768) expect(layout.sidebarWidth, route).toBe(220);
      measurements.push({ route, ...layout });
      await page.screenshot({ path: info.outputPath(`${route.slice(1)}-${viewport.width}.png`) });
    }
    await info.attach('layout-measurements', {
      body: JSON.stringify(measurements, null, 2),
      contentType: 'application/json',
    });
  });
}

test('700px 手机布局的可见输入与下拉保持44px触控高度', async ({ page }, info) => {
  await page.setViewportSize({ width: 700, height: 844 });
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '隔离服务不可用' }),
    }),
  );
  const evidence = [];
  for (const route of [
    '/knowledge-points',
    '/question-bank?tab=library',
    '/assessments',
    '/learning-analysis',
    '/practices',
    '/knowledge-bases',
    '/settings',
  ]) {
    await page.goto(route);
    await expect(page.locator('.unified-shell')).toHaveAttribute('data-navigation-ready', 'true');
    const fields = await page
      .locator(
        'input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):not([type="range"]), select',
      )
      .evaluateAll((nodes) =>
        nodes
          .map((node) => ({
            name:
              node.getAttribute('aria-label') ?? node.getAttribute('placeholder') ?? node.className,
            height: node.getBoundingClientRect().height,
          }))
          .filter((field) => field.height > 0),
      );
    expect(
      fields.every((field) => field.height >= 43.5),
      `${route}: ${JSON.stringify(fields)}`,
    ).toBe(true);
    evidence.push({ route, fields });
  }
  expect(evidence.reduce((count, item) => count + item.fields.length, 0)).toBeGreaterThan(0);
  await info.attach('700px-touch-targets', {
    body: JSON.stringify(evidence, null, 2),
    contentType: 'application/json',
  });
});

test('应用减少动画实时停止GSAP，抽屉关闭与焦点不等待动画', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '隔离服务不可用' }),
    }),
  );
  await page.goto('/settings');
  await page.getByRole('checkbox', { name: '减少动画' }).check();
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'reduced');
  await page.getByRole('button', { name: '打开功能导航' }).click();
  const drawer = page.getByRole('dialog', { name: '功能导航' });
  await expect(drawer).toHaveCSS('transform', 'none');
  await expect(drawer.locator('[aria-current="page"]')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(drawer).toHaveCount(0);
  await expect(page.getByRole('button', { name: '打开功能导航' })).toBeFocused();
  await page.getByRole('checkbox', { name: '减少动画' }).uncheck();
  await page.getByRole('button', { name: '打开功能导航' }).click();
  await expect(drawer).toBeVisible();
  await page.evaluate(() => {
    document.documentElement.dataset.motion = 'reduced';
  });
  await expect(drawer).toHaveCSS('transform', 'none');
  await page.keyboard.press('Escape');
  await expect(drawer).toHaveCount(0);
});
