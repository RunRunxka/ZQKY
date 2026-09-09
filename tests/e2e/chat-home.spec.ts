import { test, expect } from '@playwright/test';

// 隔离测试目录与模拟上游；不访问用户会话或供应商。视觉数据沿用参考页的长短组合。
const answer =
  '你好！我是智启课源，你的学习伙伴。\n\n我可以帮你：\n\n- **讲解概念**——从直觉到细节，一起理解数学、物理、编程等学科\n- **梳理知识**——整理知识点之间的联系，建立清晰的学习框架\n- **推敲教学思路**——设计课堂提问，讨论适合学生的解释方式\n\n你现在想学点什么？告诉我你的目标，我们就开始吧！';
test.beforeEach(async ({ page }) => {
  const connection = {
    id: 'visual-connection',
    displayName: '隔离验收连接',
    protocol: 'openai-chat',
    hasCredential: true,
  };
  const profiles = ['deepseek-v4-flash', 'gpt-test'].map((modelId, index) => ({
    id: `visual-${index}`,
    connectionId: connection.id,
    displayName: `验收模型 ${index + 1}`,
    modelId,
    purpose: 'chat',
    contextTokens: 8000,
    maxOutputTokens: 512,
    supportedParams: [],
    capabilities: { chat: 'verified' },
    connection,
  }));
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      json: {
        revision: 1,
        defaultChatProfileId: profiles[0].id,
        profiles,
        connections: [connection],
      },
    }),
  );
  await page.route('**/api/v1/chat/stream', (route) =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: [
        'event: message.start',
        'data: {"requestId":"visual","messageId":"visual-reply"}',
        '',
        'event: text.delta',
        `data: ${JSON.stringify({ messageId: 'visual-reply', text: answer })}`,
        '',
        'event: message.end',
        'data: {"messageId":"visual-reply","finishReason":"stop"}',
        '',
        '',
      ].join('\n'),
    }),
  );
});

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 390, height: 844 },
]) {
  test(`主页复刻 ${viewport.width}：发送、恢复、菜单和工作区可达`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    await page.goto('/chat');
    await expect(page.getByRole('button', { name: '选择模型' })).toBeEnabled();
    await page.screenshot({ path: testInfo.outputPath(`home-empty-${viewport.width}.png`) });
    await page.getByRole('textbox', { name: '输入问题' }).fill('你好');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    await expect(page.locator('.answer-markdown')).toContainText('告诉我你的目标');
    await page.reload();
    await expect(page.locator('.answer-markdown')).toContainText('告诉我你的目标');
    await expect(page.locator('canvas[aria-label="智启课源"]')).toBeVisible();
    await expect(page.locator('.chat-send-button')).toHaveCSS('border-radius', '50%');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    const mainWidth = (await page.locator('.chat-main').boundingBox())!.width;
    expect(mainWidth).toBe(viewport.width >= 768 ? viewport.width - 220 - 236 : viewport.width);
    if (viewport.width >= 768) {
      expect((await page.locator('.global-nav').boundingBox())?.width).toBe(220);
      expect((await page.locator('.chat-composer').boundingBox())?.width).toBe(Math.min(912, mainWidth - 48));
      await expect(page.getByRole('button', { name: '学习问答', exact: true })).toHaveAttribute(
        'aria-current',
        'page',
      );
    }
    await page.screenshot({ path: testInfo.outputPath(`home-answer-${viewport.width}.png`) });
    await page.getByRole('button', { name: '选择模型' }).click();
    await expect(page.getByRole('dialog', { name: '选择问答模型' })).toBeVisible();
    await page.getByRole('textbox', { name: '搜索模型' }).fill('gpt-test');
    await page.getByRole('button', { name: /验收模型 2/ }).click();
    await expect(page.getByRole('button', { name: '选择模型' })).toContainText('验收模型 2');
    await expect(page.getByRole('button', { name: '选择模型' })).toBeFocused();
    if (viewport.width < 768) {
      const sendBox = (await page.locator('.chat-send-button').boundingBox())!;
      const modelBox = (await page.getByRole('button', { name: '选择模型' }).boundingBox())!;
      expect(Math.abs(sendBox.y - modelBox.y)).toBeLessThan(10);
    }
    await page.getByRole('button', { name: '会话详情' }).click();
    await expect(page.getByRole('button', { name: '关闭结果工作区' })).toBeVisible();
    await page.waitForTimeout(260); // 最终布局截图；中间帧另由动态用例保存。
    await page.screenshot({ path: testInfo.outputPath(`home-panel-${viewport.width}.png`) });
    await page.getByRole('button', { name: '关闭结果工作区' }).click();
    await expect(page.locator('.chat-workspace')).toHaveCount(0);
    await page.getByRole('button', { name: '打开会话列表' }).click();
    if (viewport.width >= 768) {
      await expect(page.getByRole('textbox', { name: '搜索会话' })).not.toBeVisible();
      await page.getByRole('button', { name: '打开会话列表' }).click();
    }
    await expect(page.getByRole('textbox', { name: '搜索会话' })).toBeVisible();
  });
}

test('动态球、侧栏、工作区退出中断与减少动画', async ({ page }, testInfo) => {
  await page.goto('/chat');
  await page.getByRole('textbox', { name: '输入问题' }).fill('动画检查');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  const canvas = page.locator('canvas[aria-label="智启课源"]');
  await expect(canvas).toBeVisible();
  const pixels = () => canvas.evaluate((node) => (node as HTMLCanvasElement).toDataURL());
  const first = await pixels();
  await expect.poll(pixels).not.toBe(first);
  await page.getByRole('button', { name: '收起项目导航' }).click();
  await expect(page.locator('.global-nav')).toHaveCSS('width', '56px');
  await page.getByRole('button', { name: '展开项目导航' }).click();
  await expect(page.locator('.global-nav')).toHaveCSS('width', '220px');
  await page.getByRole('button', { name: '会话详情' }).click();
  await page.waitForTimeout(240);
  // 冻结退出动画中间帧；退出期间不可接收焦点或点击。
  await page.getByRole('button', { name: '关闭结果工作区' }).click();
  await expect(page.locator('.chat-info.closing')).toHaveAttribute('inert', '');
  await page.evaluate(() => {
    for (const animation of document.getAnimations()) {
      if ((animation as CSSAnimation).animationName === 'chat-home-viewer-out') {
        animation.pause();
        animation.currentTime = 110;
      }
    }
  });
  await page.screenshot({ path: testInfo.outputPath('viewer-exit-mid.png') });
  // 关闭动画尚未卸载时再打开，必须恢复可交互状态。
  await page.getByRole('button', { name: '会话详情' }).click();
  await expect(page.locator('.chat-info')).not.toHaveAttribute('inert');
  await page.waitForTimeout(260);
  await expect(page.locator('.chat-workspace')).toBeVisible();
  const resize = (await page.getByRole('separator', { name: '调整工作区宽度' }).boundingBox())!;
  await page.mouse.move(resize.x + resize.width / 2, resize.y + 100);
  await page.mouse.down();
  await page.mouse.move(resize.x - 25, resize.y + 100);
  await expect(page.locator('body')).toHaveAttribute('data-chat-resizing', 'true');
  await page.keyboard.press('Escape');
  await expect(page.locator('.chat-workspace')).toHaveCount(0);
  await expect(page.locator('body')).not.toHaveAttribute('data-chat-resizing');
  await page.mouse.up();
  await page.getByRole('button', { name: '会话详情' }).click();
  await page.waitForTimeout(260);
  await page.getByRole('button', { name: '关闭结果工作区' }).click();
  await expect(page.locator('.chat-workspace')).toHaveCount(0);
  await page.evaluate(() => (document.documentElement.dataset.motion = 'reduced'));
  await page.waitForTimeout(100);
  const still = await pixels();
  await page.waitForTimeout(180);
  expect(await pixels()).toBe(still);
  await page.screenshot({ path: testInfo.outputPath('reduced-motion.png') });
  await page.evaluate(() => (document.documentElement.dataset.motion = 'system'));
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForTimeout(100);
  const systemStill = await pixels();
  await page.waitForTimeout(180);
  expect(await pixels()).toBe(systemStill);
});
