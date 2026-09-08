import { test, expect } from '@playwright/test';

// e2e 环境只启动前端：用路由级模拟上游验证 UI 全流程（模拟服务器仅用于测试）；
// 真实供应商验收在未获凭证时单独标注未执行。
const PROFILES = [
  {
    id: 'profile-1',
    connectionId: 'conn-1',
    displayName: '模拟模型',
    modelId: 'sim-chat-1',
    purpose: 'chat',
    contextTokens: 8000,
    maxOutputTokens: 512,
    supportedParams: ['temperature'],
    capabilities: { chat: 'verified' },
    connection: { displayName: '模拟连接', protocol: 'openai-chat', hasCredential: true },
    createdAt: '2026-09-06T00:00:00Z',
    updatedAt: '2026-09-06T00:00:00Z',
  },
];

const SSE_OK = [
  'event: message.start',
  'data: {"requestId":"req-1","messageId":"m1","modelProfileId":"profile-1"}',
  '',
  'event: text.delta',
  'data: {"messageId":"m1","text":"你好，"}',
  '',
  'event: text.delta',
  'data: {"messageId":"m1","text":"这是模拟回答。"}',
  '',
  'event: usage',
  'data: {"messageId":"m1","inputTokens":9,"outputTokens":6}',
  '',
  'event: message.end',
  'data: {"messageId":"m1","finishReason":"stop"}',
  '',
  '',
].join('\n');

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      json: {
        revision: 1,
        defaultChatProfileId: 'profile-1',
        profiles: PROFILES,
        connections: [
          { id: 'conn-1', displayName: '模拟连接', protocol: 'openai-chat', hasCredential: true },
        ],
      },
    }),
  );
  await page.route('**/api/v1/model-profiles', (route) => route.fulfill({ json: PROFILES }));
  await page.route('**/api/v1/chat/stream', (route) =>
    route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: SSE_OK,
    }),
  );
});

test('发送消息后流式回答可见，标注模型与用量，历史在刷新后恢复', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/chat');
  const input = page.getByPlaceholder('输入问题，Enter 发送，Shift+Enter 换行');
  await expect(input).toBeVisible();
  await input.fill('你好');
  await page.getByRole('button', { name: '发送' }).click();

  await expect(page.getByText('你好，这是模拟回答。')).toBeVisible();
  await expect(
    page.locator('.chat-bubble-foot', { hasText: '模拟模型 · sim-chat-1' }),
  ).toBeVisible();
  await expect(page.getByText(/输出 6 tokens/)).toBeVisible();

  await page.reload();
  await expect(page.getByText('你好，这是模拟回答。')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('chat-1440.png') });

  // 手机视口
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: testInfo.outputPath('chat-390.png') });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('发送中显示停止按钮且禁止重复发送', async ({ page }) => {
  await page.route('**/api/v1/chat/stream', async () => {
    await new Promise(() => {}); // 挂起的流
  });
  await page.goto('/chat');
  const input = page.getByPlaceholder('输入问题，Enter 发送，Shift+Enter 换行');
  await input.fill('长问题');
  await page.getByRole('button', { name: '发送' }).click();
  const stopButton = page.getByRole('button', { name: '停止' });
  await expect(stopButton).toBeVisible();
  await expect(page.getByRole('button', { name: '发送' })).toHaveCount(0);
  await stopButton.click();
  await expect(page.getByText('已停止')).toBeVisible();
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible();
});

test('发送前 HTTP 错误（如未配置凭证）展示准确原因，用户消息保留且可重试', async ({ page }) => {
  await page.route('**/api/v1/chat/stream', (route) =>
    route.fulfill({
      status: 400,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        code: 'MODEL_NOT_CONFIGURED',
        message: '该模型连接未保存凭证，请先在设置中填写 API Key。',
        requestId: 'req-err',
        retryable: false,
      }),
    }),
  );
  await page.goto('/chat');
  const input = page.getByPlaceholder('输入问题，Enter 发送，Shift+Enter 换行');
  await input.fill('我的问题不会丢');
  await page.getByRole('button', { name: '发送' }).click();

  await expect(page.locator('.chat-error')).toContainText('MODEL_NOT_CONFIGURED');
  await expect(page.locator('.chat-bubble.user')).toContainText('我的问题不会丢');
  await expect(page.locator('.chat-error').getByRole('button', { name: '重试' })).toBeVisible();
});

test('未配置任何模型时提示先去设置而不是假对话', async ({ page }) => {
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      json: { revision: 1, defaultChatProfileId: null, profiles: [], connections: [] },
    }),
  );
  await page.route('**/api/v1/model-profiles', (route) => route.fulfill({ json: [] }));
  await page.goto('/chat');
  await expect(page.getByText(/还没有可用的模型/)).toBeVisible();
  await expect(page.locator('.chat-banner').getByRole('link', { name: '设置' })).toBeVisible();
  await expect(page.getByRole('button', { name: '发送' })).toBeDisabled();
});
