import { test, expect, type Page, type TestInfo } from '@playwright/test';

type MotionSample = {
  time: number;
  transform: string;
  opacity: string;
  computedTransform: string;
  active: boolean;
  focusInside: boolean;
};
type MotionEvent = { type: string; sample: MotionSample | null };
type MotionProbe = {
  read: () => MotionSample | null;
  stop: () => { samples: MotionSample[]; events: MotionEvent[] };
};
type ProbeWindow = Window & { __uiMotionProbe?: MotionProbe };

// Observe real DOM styles rather than inferring activity from a timer or visibility.
async function observeMotion(page: Page, selector: string) {
  await page.evaluate((targetSelector) => {
    const targetWindow = window as ProbeWindow;
    targetWindow.__uiMotionProbe?.stop();
    const samples: MotionSample[] = [];
    const events: MotionEvent[] = [];
    const read = () => {
      const target = document.querySelector<HTMLElement>(targetSelector);
      const dialog = target?.closest('dialog');
      if (!target || !dialog?.open) return null;
      const style = getComputedStyle(target);
      const transformed =
        style.transform !== 'none' && !new DOMMatrixReadOnly(style.transform).isIdentity;
      return {
        time: performance.now(),
        transform: target.style.transform,
        opacity: target.style.opacity,
        computedTransform: style.transform,
        active:
          (target.style.transform !== '' && transformed) ||
          (target.style.opacity !== '' && Number.parseFloat(style.opacity) < 0.999),
        focusInside: dialog.contains(document.activeElement),
      };
    };
    const record = () => {
      const sample = read();
      if (sample && samples.length < 600) samples.push(sample);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' || event.key === 'Enter') {
        events.push({ type: `keydown:${event.key}`, sample: read() });
      }
    };
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onMedia = () => {
      events.push({ type: `system:${media.matches ? 'reduce' : 'normal'}`, sample: read() });
    };
    const observer = new MutationObserver(record);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['style'],
    });
    document.addEventListener('keydown', onKey, true);
    media.addEventListener('change', onMedia);
    let frame = 0;
    const sampleFrame = () => {
      record();
      frame = requestAnimationFrame(sampleFrame);
    };
    frame = requestAnimationFrame(sampleFrame);
    targetWindow.__uiMotionProbe = {
      read,
      stop: () => {
        observer.disconnect();
        cancelAnimationFrame(frame);
        document.removeEventListener('keydown', onKey, true);
        media.removeEventListener('change', onMedia);
        return { samples, events };
      },
    };
  }, selector);
}

async function waitForActiveMotion(page: Page) {
  return page.waitForFunction(
    () => {
      const sample = (window as ProbeWindow).__uiMotionProbe?.read();
      return sample?.active ? sample : false;
    },
    undefined,
    { polling: 'raf', timeout: 3000 },
  );
}

async function attachProbe(page: Page, info: TestInfo, name: string, activeBeforeAction: unknown) {
  const evidence = await page.evaluate(() => (window as ProbeWindow).__uiMotionProbe?.stop());
  expect(evidence?.samples.some((sample) => sample.active)).toBe(true);
  await info.attach(name, {
    body: JSON.stringify({ activeBeforeAction, ...evidence }, null, 2),
    contentType: 'application/json',
  });
  return evidence!;
}

async function expectNoReplay(page: Page) {
  const samples = await page.evaluate(
    () =>
      new Promise<MotionSample[]>((resolve) => {
        const started = performance.now();
        const result: MotionSample[] = [];
        const sampleFrame = () => {
          const sample = (window as ProbeWindow).__uiMotionProbe?.read();
          if (sample) result.push(sample);
          if (performance.now() - started >= 300) resolve(result);
          else requestAnimationFrame(sampleFrame);
        };
        requestAnimationFrame(sampleFrame);
      }),
  );
  expect(samples.length).toBeGreaterThan(1);
  expect(
    samples.every((sample) => !sample.active && sample.transform === '' && sample.opacity === ''),
  ).toBe(true);
  return samples;
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.addInitScript(() => localStorage.setItem('zqky.motion', 'system'));
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '隔离动效验收：服务暂不可用' }),
    }),
  );
  await page.goto('/books');
  await expect(page.locator('.unified-shell')).toHaveAttribute('data-navigation-ready', 'true');
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'system');
});

test('公共 Modal 入场中 Escape、快速重开与焦点恢复，不创建书籍', async ({ page }, info) => {
  const trigger = page.getByRole('button', { name: '新建书籍', exact: true });
  const modal = page.getByRole('dialog', { name: '新建书籍', exact: true });
  const storedBooks = await page.evaluate(() => localStorage.getItem('zhiqikeyuan:books'));
  await observeMotion(page, '.workspace-modal-body');
  await trigger.focus();
  await trigger.press('Enter');
  const firstActivity = await waitForActiveMotion(page);
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
  await expect(trigger).toBeFocused();
  const firstEvidence = await attachProbe(
    page,
    info,
    'modal-interrupted',
    await firstActivity.jsonValue(),
  );
  expect(
    firstEvidence.events.find((event) => event.type === 'keydown:Escape')?.sample?.active,
  ).toBe(true);

  await observeMotion(page, '.workspace-modal-body');
  await trigger.press('Enter');
  const secondActivity = await waitForActiveMotion(page);
  await modal.getByRole('textbox', { name: '书名', exact: true }).fill('动效验收临时书名');
  await expect(modal.getByRole('textbox', { name: '书名', exact: true })).toHaveValue(
    '动效验收临时书名',
  );
  await expect(modal.locator('.workspace-modal-body')).toHaveCSS('transform', 'none');
  await expect(modal.locator('.workspace-modal-body')).toHaveCSS('opacity', '1');
  expect(
    await modal
      .locator('.workspace-modal-body')
      .evaluate((node) => node.getAttribute('style') ?? ''),
  ).not.toMatch(/(?:transform|opacity):/);
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await attachProbe(page, info, 'modal-reopened', await secondActivity.jsonValue());
  expect(await page.evaluate(() => localStorage.getItem('zhiqikeyuan:books'))).toBe(storedBooks);
});

test('手机抽屉响应 system/app 减少动画，恢复时不补播，重开仍入场', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const trigger = page.getByRole('button', { name: '打开功能导航' });
  const drawer = page.getByRole('dialog', { name: '功能导航' });
  for (const source of ['system', 'app'] as const) {
    await observeMotion(page, '.mobile-nav-panel');
    await trigger.focus();
    await trigger.press('Enter');
    const activity = await waitForActiveMotion(page);
    if (source === 'system') {
      await page.emulateMedia({ reducedMotion: 'reduce' });
    } else {
      const atChange = await page.evaluate(() => {
        const sample = (window as ProbeWindow).__uiMotionProbe?.read();
        document.documentElement.dataset.motion = 'reduced';
        return sample;
      });
      expect(atChange?.active).toBe(true);
      await info.attach('app-reduce-at-change', {
        body: JSON.stringify(atChange),
        contentType: 'application/json',
      });
    }
    await expect(drawer).toHaveCSS('transform', 'none');
    await expect(drawer.locator('[aria-current="page"]')).toBeFocused();
    if (source === 'system') await page.emulateMedia({ reducedMotion: 'no-preference' });
    else
      await page.evaluate(() => {
        document.documentElement.dataset.motion = 'system';
      });
    const restoredSamples = await expectNoReplay(page);
    await expect(drawer).toBeVisible();
    await expect(drawer.locator('[aria-current="page"]')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(drawer).toHaveCount(0);
    await expect(trigger).toBeFocused();
    const evidence = await attachProbe(
      page,
      info,
      `${source}-reduce-interrupted`,
      await activity.jsonValue(),
    );
    // The provider may already have reverted GSAP before this media listener runs.
    // Activity immediately before emulateMedia is retained in activeBeforeAction.
    if (source === 'system')
      expect(evidence.events.some((event) => event.type === 'system:reduce')).toBe(true);
    await info.attach(`${source}-restored-without-replay`, {
      body: JSON.stringify(restoredSamples, null, 2),
      contentType: 'application/json',
    });

    await observeMotion(page, '.mobile-nav-panel');
    await trigger.press('Enter');
    const reopenedActivity = await waitForActiveMotion(page);
    await page.keyboard.press('Escape');
    await expect(drawer).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await attachProbe(page, info, `${source}-reopened`, await reopenedActivity.jsonValue());
  }
});

test('抽屉入场中键盘导航到施测，单壳、焦点与滚动锁正确清理', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  const previousOverflow = await page.evaluate(() => document.body.style.overflow);
  await observeMotion(page, '.mobile-nav-panel');
  const trigger = page.getByRole('button', { name: '打开功能导航' });
  await trigger.focus();
  await trigger.press('Enter');
  const drawer = page.getByRole('dialog', { name: '功能导航' });
  const destination = drawer.getByRole('button', { name: '施测与成绩', exact: true });
  await destination.focus();
  const activity = await waitForActiveMotion(page);
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/assessments$/);
  await expect(drawer).toHaveCount(0);
  await expect(page.locator('.app-shell')).toHaveCount(1);
  await expect(page.locator('.unified-shell')).toHaveCount(1);
  await expect(page.locator('nav[aria-label="项目功能导航"] [aria-current="page"]')).toHaveCount(1);
  await expect(page.getByRole('heading', { name: '施测与成绩', exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe(previousOverflow);
  await expect(trigger).toBeFocused();
  const evidence = await attachProbe(
    page,
    info,
    'drawer-navigation-interrupted',
    await activity.jsonValue(),
  );
  expect(evidence.events.findLast((event) => event.type === 'keydown:Enter')?.sample?.active).toBe(
    true,
  );

  await trigger.press('Enter');
  await expect(drawer.getByRole('button', { name: '施测与成绩', exact: true })).toBeFocused();
  await expect(drawer.locator('[aria-current="page"]')).toHaveCount(1);
  const close = drawer.getByRole('button', { name: '关闭功能导航' });
  await close.focus();
  await page.keyboard.press('Shift+Tab');
  await expect(drawer.getByRole('button', { name: '设置', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(close).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(drawer).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe(previousOverflow);
  expect(pageErrors).toEqual([]);
});
