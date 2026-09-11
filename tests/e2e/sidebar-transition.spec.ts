import { test, expect, type Page } from '@playwright/test';

// 在隔离浏览器中采集整段软导航，防止终态断言漏掉重挂载时的展开闪动。
async function observeNavigation(page: Page) {
  await page.evaluate(() => {
    const samples: { width: number; expanded: boolean; path: string }[] = [];
    let frame = 0;
    const sample = () => {
      const nav = document.querySelector('.global-nav');
      if (nav)
        samples.push({
          width: nav.getBoundingClientRect().width,
          expanded: !!nav.closest('.nav-expanded'),
          path: location.pathname,
        });
      frame = requestAnimationFrame(sample);
    };
    sample();
    Object.assign(window, {
      stopNavigationSamples: () => {
        cancelAnimationFrame(frame);
        return samples;
      },
    });
  });
}

async function geometry(page: Page) {
  return page.locator('.global-nav').evaluate((nav) => {
    const nodes = [
      nav,
      ...nav.querySelectorAll('.sidebar-brand, .nav-toggle, .global-nav-item, .avatar'),
    ];
    return nodes.map((node) => {
      const box = node.getBoundingClientRect(),
        css = getComputedStyle(node);
      return {
        x: box.x,
        y: box.y,
        width: box.width,
        height: box.height,
        gap: css.gap,
        padding: css.padding,
        font: css.fontFamily,
        fontSize: css.fontSize,
      };
    });
  });
}

for (const width of [1440, 1920]) {
  test(`软导航全程侧栏不跳变，样式跟随学习问答 ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 1080 });
    await page.goto('/chat');
    await expect(page.locator('.unified-shell')).toHaveAttribute('data-navigation-ready', 'true');
    for (const expanded of [true, false]) {
      if (!expanded) {
        await page.getByRole('button', { name: '收起项目导航' }).click();
        await expect(page.locator('.global-nav')).toHaveCSS('width', '56px');
      }
      const baseline = await geometry(page);
      for (const [route, label] of [
        ['/lesson-plans', '教案工作台'],
        ['/chat', '学习问答'],
        ['/space', '学习空间'],
        ['/chat', '学习问答'],
        ['/co-writer', '协同写作'],
        ['/chat', '学习问答'],
        ['/reading', '沉浸阅读'],
        ['/chat', '学习问答'],
        ['/settings', '设置'],
        ['/chat', '学习问答'],
        ['/papers', '智能组卷（规划中）'],
        ['/chat', '学习问答'],
      ]) {
        await observeNavigation(page);
        await page
          .getByRole('navigation')
          .getByRole('button', { name: label, exact: true })
          .click();
        await expect(page).toHaveURL(new RegExp(`${route}$`));
        await expect(
          page.getByRole('navigation').getByRole('button', { name: label, exact: true }),
        ).toHaveAttribute('aria-current', 'page');
        await page.evaluate(() => new Promise(requestAnimationFrame));
        const samples = await page.evaluate(() =>
          (
            window as unknown as {
              stopNavigationSamples: () => { width: number; expanded: boolean; path: string }[];
            }
          ).stopNavigationSamples(),
        );
        expect(samples.length).toBeGreaterThan(0);
        expect(
          samples.every(
            (sample) =>
              sample.expanded === expanded && Math.abs(sample.width - (expanded ? 220 : 56)) < 0.1,
          ),
        ).toBe(true);
        expect(await geometry(page)).toEqual(baseline);
        await info.attach(`${expanded ? 'expanded' : 'collapsed'}-${route.slice(1)}-frames`, {
          body: JSON.stringify(samples),
          contentType: 'application/json',
        });
      }
      await page.goBack();
      await expect(
        page.getByRole('navigation').getByRole('button', { name: '智能组卷（规划中）' }),
      ).toHaveAttribute('aria-current', 'page');
      expect(await geometry(page)).toEqual(baseline);
      await page.goForward();
      await expect(page.locator('.chat-toolbar')).toBeVisible();
      expect(await geometry(page)).toEqual(baseline);
    }
    await page.screenshot({ path: info.outputPath('chat-collapsed.png') });
    await page.reload();
    await expect(page.getByRole('button', { name: '展开项目导航' })).toBeVisible();
    await expect(page.locator('.global-nav')).toHaveCSS('width', '56px');
  });
}

test('各板块使用同一折叠时长并响应减少动画', async ({ page }) => {
  for (const route of ['/chat', '/lesson-plans', '/space', '/settings']) {
    await page.goto(route);
    await expect(page.locator('.unified-shell')).toHaveAttribute('data-navigation-ready', 'true');
    await expect(page.locator('.unified-shell')).toHaveCSS('transition-duration', '0.2s');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect(page.locator('.unified-shell')).toHaveCSS('transition-duration', '1e-05s');
    await page.emulateMedia({ reducedMotion: 'no-preference' });
  }
});

test('手机跨板块打开抽屉，菜单字体和尺寸沿用学习问答', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/chat');
  let baseline: unknown;
  for (const label of ['教案工作台', '学习空间', '设置', '学习问答']) {
    await page.getByRole('button', { name: '打开功能导航' }).click();
    const drawer = page.getByRole('dialog', { name: '功能导航' });
    await expect(drawer).toHaveCSS('transform', 'none');
    await expect(drawer.locator('[aria-current="page"]')).toBeFocused();
    const styles = await drawer.locator('.global-nav-item').evaluateAll((nodes) =>
      nodes.map((node) => {
        const css = getComputedStyle(node),
          box = node.getBoundingClientRect();
        return {
          x: box.x,
          y: box.y,
          width: box.width,
          height: box.height,
          font: css.fontFamily,
          fontSize: css.fontSize,
          gap: css.gap,
        };
      }),
    );
    if (!baseline) baseline = styles;
    else expect(styles).toEqual(baseline);
    await page.screenshot({ path: info.outputPath(`mobile-before-${label}.png`) });
    await drawer.getByRole('button', { name: label, exact: true }).click();
    await expect(drawer).toHaveCount(0);
  }
});
