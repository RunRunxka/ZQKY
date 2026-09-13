import { test, expect, type Page } from '@playwright/test';

/**
 * 模型管理嵌套交互回归（B-MODEL-ACCEPT v1 发现并修复的缺陷）。
 *
 * 官方 e2e 不启动后端，用 page.route 提供确定的目录/目录响应；
 * 只验证交互行为（嵌套层级、未保存确认、焦点返回），不宣称真实上游。
 */

const connection = {
  id: 'c1',
  displayName: '回归供应商',
  providerId: 'deepseek',
  providerLabel: 'DeepSeek',
  protocol: 'openai-chat',
  apiFormat: 'auto',
  apiVersion: null,
  baseUrl: 'https://api.deepseek.com',
  resolvedBaseUrl: 'https://api.deepseek.com',
  hasCredential: true,
  hasManagedCredential: true,
  callable: true,
  callableReason: null,
  credentialScope: 'process',
  credentialEnvName: 'ZQKY_API_KEY_c1',
  extraHeaderNames: [],
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};
const profile = {
  id: 'p1',
  connectionId: 'c1',
  displayName: '回归模型',
  modelId: 'deepseek-chat',
  purpose: 'chat',
  contextTokens: null,
  maxOutputTokens: null,
  supportedParams: [],
  params: {},
  reasoningEnabled: null,
  reasoningEffort: null,
  reasoningStyle: 'thinking_type',
  capabilities: { chat: 'unknown' },
  connection: { displayName: '回归供应商', providerId: 'deepseek', providerLabel: 'DeepSeek', protocol: 'openai-chat', apiFormat: 'auto', hasCredential: true },
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};

async function stub(page: Page) {
  await page.route('**/api/v1/model-providers', (route) =>
    route.fulfill({ status: 200, json: { providers: [{
      providerId: 'deepseek', label: 'DeepSeek', aliases: [], mode: 'standard', authMode: 'api_key',
      apiFormats: ['auto', 'openai_chat', 'openai_responses'], defaultApiFormat: 'auto',
      defaultApiBase: 'https://api.deepseek.com', baseUrlsByFormat: {}, supportsWireApiSelection: true,
      supportsModelDiscovery: true, requiresKey: true, isLegacy: false, legacyOf: [], thinkingStyle: 'thinking_type',
    }], legacy: [] } }),
  );
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({ status: 200, json: { revision: 3, defaultChatProfileId: null, connections: [connection], profiles: [profile] } }),
  );
  await page.route('**/api/v1/model-connections/*/models', (route) =>
    route.fulfill({ status: 200, json: { models: [{ id: 'deepseek-chat' }, { id: 'deepseek-reasoner' }], source: 'upstream' } }),
  );
}

async function gotoModels(page: Page) {
  await stub(page);
  await page.goto('/settings#models');
  await expect(page.getByRole('heading', { name: '问答模型' })).toBeVisible();
  await expect(page.getByRole('button', { name: /的详情/ }).first()).toBeVisible();
}

test.describe('模型管理嵌套交互', () => {
  test('详情内打开二级面板后 Escape：只关最内层，详情保留', async ({ page }) => {
    await gotoModels(page);
    await page.getByRole('button', { name: /的详情/ }).first().click();
    await expect(page.getByRole('dialog')).toHaveCount(1);
    const name = await page.getByRole('dialog').getAttribute('aria-label');

    await page.getByRole('button', { name: /从服务获取/ }).click();
    await expect(page.getByRole('dialog', { name: '从服务获取模型' })).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog', { name: '从服务获取模型' })).toBeHidden({ timeout: 10000 });
    await expect(page.getByRole('dialog')).toHaveCount(1);
    expect(await page.getByRole('dialog').getAttribute('aria-label')).toBe(name);
  });

  test('详情有未保存修改时，经二级面板 Escape 返回不丢草稿', async ({ page }) => {
    await gotoModels(page);
    await page.getByRole('button', { name: /的详情/ }).first().click();
    await page.getByLabel(/^Base URL/).fill('https://edited.example.com/v1');
    await page.getByRole('button', { name: /从服务获取/ }).click();
    await expect(page.getByRole('dialog', { name: '从服务获取模型' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByLabel(/^Base URL/)).toHaveValue('https://edited.example.com/v1', { timeout: 10000 });
  });

  test('详情有未保存修改时直接关闭：先确认再丢弃', async ({ page }) => {
    await gotoModels(page);
    await page.getByRole('button', { name: /的详情/ }).first().click();
    await page.getByLabel(/^Base URL/).fill('https://edited.example.com/v1');
    await page.getByRole('button', { name: '关闭对话框' }).click();
    await expect(page.getByRole('alertdialog', { name: '放弃未保存的更改' })).toBeVisible();
    await page.getByRole('button', { name: '继续编辑' }).click();
    await expect(page.getByLabel(/^Base URL/)).toHaveValue('https://edited.example.com/v1');
  });

  test('关闭详情后焦点回到触发卡片', async ({ page }) => {
    await gotoModels(page);
    const trigger = page.getByRole('button', { name: /的详情/ }).first();
    const label = await trigger.getAttribute('aria-label');
    await trigger.click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toBeHidden({ timeout: 10000 });
    await expect(page.getByRole('button', { name: label! })).toBeFocused();
  });
});
