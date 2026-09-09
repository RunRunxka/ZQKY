import { test, expect } from '@playwright/test';

test('R20 真实模式粘贴附件必须先说明不支持，不得静默发出纯文字请求', async ({ page }) => {
  const profile = {
    id: 'fixture-profile',
    connectionId: 'fixture-connection',
    displayName: '审查夹具',
    modelId: 'fixture',
    purpose: 'chat',
    contextTokens: 8000,
    maxOutputTokens: 512,
    connection: { hasCredential: true, displayName: '审查夹具', protocol: 'openai-chat' },
  };
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({ json: { revision: 1, defaultChatProfileId: profile.id, profiles: [profile], connections: [] } }),
  );
  let calls = 0;
  await page.route('**/api/v1/chat/stream', (route) => {
    calls++;
    return route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'event: text.delta\ndata: {"text":"fixture response"}\n\nevent: message.end\ndata: {"finishReason":"stop"}\n\n',
    });
  });
  await page.goto('/chat');
  const input = page.getByRole('textbox', { name: '输入问题' });
  await expect(input).toBeEnabled();
  await page.evaluate(() => {
    const data = new DataTransfer();
    data.items.add(new File(['attachment content'], 'review.txt', { type: 'text/plain' }));
    document.querySelector('textarea')!.dispatchEvent(
      new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }),
    );
  });
  await input.fill('请分析附件');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: /附件|解析/ })).toBeVisible();
  expect(calls).toBe(0);
});
