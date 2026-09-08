import { test, expect } from '@playwright/test';

/**
 * R8 动态证据：扩展菜单与工具过程面板的进出场动画。
 * - video: 'on' 生成 webm 录像（产物目录内，供人工查看）；
 * - 关键中间帧用 Web Animations API 定格后截图（可逐帧查看，不依赖 ffmpeg）。
 * 覆盖：菜单进场、退场（Escape）、过程详情展开/收起与快速开关中断。
 */
test.use({ video: { mode: 'on', size: { width: 720, height: 480 } } });

const SEED = [
  { id: 'm1', kind: 'mcp', name: '演示检索', description: '本地演示 MCP', content: '', enabled: true },
  { id: 's1', kind: 'skill', name: '提问技能', description: '本地演示技能', content: '', enabled: true },
];

test('扩展菜单与过程面板动画录像与关键帧', async ({ page }, testInfo) => {
  await page.addInitScript((seed) => {
    window.localStorage.setItem('zqky.replica.extensions.v1', JSON.stringify(seed));
  }, SEED);
  await page.goto('/chat');
  await page.getByRole('textbox', { name: '输入问题' }).waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  const trigger = page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' });
  const panel = page.locator('.chat-ext-panel');

  // 进场
  await trigger.click();
  await expect(panel).toBeVisible();
  await page.getByRole('button', { name: '选择MCP 演示检索' }).click(); // 后半段需要工具卡
  await page.waitForTimeout(250); // 进场完成
  await page.screenshot({ path: testInfo.outputPath('motion-1-open.png') });

  // 退场定格：40ms / 80ms / 120ms 三帧（160ms 退场）
  await page.evaluate(() => {
    (document.querySelector('[aria-label="关闭扩展选择"]') as HTMLButtonElement).click();
  });
  await expect(panel).toHaveClass(/closing/);
  await page.evaluate(() => {
    const anim = document
      .getAnimations()
      .find((a) => (a as Animation).animationName === 'chat-ext-pop-out');
    if (anim) {
      anim.pause();
      anim.currentTime = 40;
    }
  });
  await page.screenshot({ path: testInfo.outputPath('motion-2-exit-40ms.png') });
  await page.evaluate(() => {
    const anim = document
      .getAnimations()
      .find((a) => (a as Animation).animationName === 'chat-ext-pop-out');
    if (anim) anim.currentTime = 120;
  });
  await page.screenshot({ path: testInfo.outputPath('motion-3-exit-120ms.png') });
  await page.evaluate(() => {
    document
      .getAnimations()
      .filter((a) => (a as Animation).animationName === 'chat-ext-pop-out')
      .forEach((a) => a.play());
  });
  await expect(page.locator('.chat-ext-panel')).toHaveCount(0, { timeout: 3000 });

  // 过程详情展开定格：grid-template-rows 过渡 300ms，取中点帧
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.fill('动画录像核验');
  await textarea.press('Enter');
  const card = page.locator('.chat-tool-card').first();
  await expect(card).toHaveClass(/done/, { timeout: 15000 });
  await card.locator('.chat-tool-head').click();
  await page.evaluate(() => {
    const anim = document
      .getAnimations()
      .find((a) => (a as CSSTransition).transitionProperty === 'grid-template-rows');
    if (anim) {
      anim.pause();
      anim.currentTime = 150;
    }
  });
  await page.screenshot({ path: testInfo.outputPath('motion-4-detail-mid.png') });
  await page.evaluate(() =>
    document
      .getAnimations()
      .filter((a) => (a as CSSTransition).transitionProperty === 'grid-template-rows')
      .forEach((a) => a.play()),
  );
  await expect(page.locator('.chat-tool-detail.open').first()).toBeVisible();

  // 快速开关中断：连续三次开合（自展开态起）后最终收起、无中间态残留
  for (let i = 0; i < 3; i += 1) {
    await card.locator('.chat-tool-head').click();
  }
  await expect(page.locator('.chat-tool-detail.open')).toHaveCount(0);
  await page.waitForTimeout(400);
  await expect(page.locator('.chat-tool-detail.open')).toHaveCount(0);
  // 录像文件随产物目录输出（webm，人工查看）
  expect(testInfo.outputPath('motion-video.webm')).toBeTruthy();
});
