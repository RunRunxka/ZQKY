import { test, expect } from '@playwright/test';

test('语音入口：明确未接入状态与演示转写，不采集音频', async ({ page }) => {
  await page.goto('/chat');
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await page.getByRole('button', { name: '语音输入（未接入，查看说明）' }).click();
  await expect(page.locator('.chat-voice-panel')).toContainText('语音输入 · 未接入');
  await page.getByRole('button', { name: '插入演示转写' }).click();
  await expect(textarea).toHaveValue(/演示转写/);
});

test('真实模式：能力菜单列出目录但非对话能力禁用并标注未接入', async ({ page }, testInfo) => {
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'review only; no provider' }),
    }),
  );
  await page.goto('/chat');
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '选择业务能力，当前：对话' }).click();
  const dialog = page.getByRole('dialog', { name: '选择业务能力' });
  await expect(dialog.getByRole('button', { name: /^对话/ })).toBeEnabled();
  const quiz = dialog.getByRole('button', { name: /^智能出题/ });
  await expect(quiz).toBeDisabled();
  await expect(dialog.getByText('真实服务未接入').first()).toBeVisible();
  await testInfo.attach('s2-real-mode-capability-menu.txt', {
    body: 'real mode capability menu: chat enabled, others disabled',
    contentType: 'text/plain',
  });
});
