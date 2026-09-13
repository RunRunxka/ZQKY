import { test, expect, type Page } from '@playwright/test';

/**
 * 模型管理（contract-v1，e2e）。
 *
 * 后端不可达，全部经 page.route 提供确定的接口替身，验证：
 * 供应商卡片 → 详情弹窗 → 模型发现来源 → 认证状态 → 三视口无横向溢出。
 * 真实上游与真实凭证验证单独记录，不用本文件冒充。
 */

const providerDirectory = {
  providers: [
    {
      providerId: 'deepseek',
      label: 'DeepSeek',
      aliases: ['deepseek'],
      mode: 'standard',
      authMode: 'api_key',
      apiFormats: ['auto', 'openai_chat', 'openai_responses'],
      defaultApiFormat: 'auto',
      defaultApiBase: 'https://api.deepseek.com',
      baseUrlsByFormat: {},
      supportsWireApiSelection: true,
      supportsModelDiscovery: true,
      requiresKey: true,
      isLegacy: false,
      legacyOf: [],
      thinkingStyle: 'thinking_type',
    },
    {
      providerId: 'openai_codex',
      label: 'OpenAI Codex',
      aliases: ['openai-codex'],
      mode: 'oauth',
      authMode: 'oauth',
      apiFormats: [],
      defaultApiFormat: 'auto',
      defaultApiBase: 'https://chatgpt.com/backend-api',
      baseUrlsByFormat: {},
      supportsWireApiSelection: false,
      supportsModelDiscovery: true,
      requiresKey: false,
      isLegacy: false,
      legacyOf: [],
      thinkingStyle: null,
      authAvailable: false,
      authUnavailableReason: '尚未配置 Codex OAuth 应用凭据，无法发起真实登录。',
    },
  ],
  legacy: [],
};

const deepseekConnection = {
  id: 'conn-1',
  displayName: 'DeepSeek 主账号',
  providerId: 'deepseek',
  providerLabel: 'DeepSeek',
  protocol: 'openai-chat',
  apiFormat: 'auto',
  apiVersion: null,
  baseUrl: '',
  resolvedBaseUrl: 'https://api.deepseek.com',
  hasCredential: true,
  credentialScope: 'process',
  credentialEnvName: 'ZQKY_API_KEY_conn-1',
  extraHeaderNames: [],
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};

const profile = {
  id: 'prof-1',
  connectionId: 'conn-1',
  displayName: 'DeepSeek Chat',
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
  connection: {
    displayName: 'DeepSeek 主账号',
    providerId: 'deepseek',
    providerLabel: 'DeepSeek',
    protocol: 'openai-chat',
    apiFormat: 'auto',
    hasCredential: true,
  },
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};

async function stubApi(
  page: Page,
  overrides: {
    connections?: unknown[];
    profiles?: unknown[];
    discovery?: unknown;
    discoveryStatus?: number;
    auth?: unknown;
  } = {},
) {
  await page.route('**/api/v1/model-providers', (route) =>
    route.fulfill({ status: 200, json: providerDirectory }),
  );
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      status: 200,
      json: {
        revision: 5,
        defaultChatProfileId: null,
        connections: overrides.connections ?? [deepseekConnection],
        profiles: overrides.profiles ?? [profile],
      },
    }),
  );
  await page.route('**/api/v1/model-connections/*/models', (route) =>
    route.fulfill({
      status: overrides.discoveryStatus ?? 200,
      json: overrides.discovery ?? { models: [{ id: 'deepseek-chat' }, { id: 'deepseek-reasoner' }], source: 'upstream' },
    }),
  );
  await page.route('**/api/v1/model-connections/*/auth', (route) =>
    route.fulfill({
      status: 200,
      json:
        overrides.auth ?? {
          connection: 'connected',
          authMode: 'api_key',
          provider: 'deepseek',
          available: true,
        },
    }),
  );
}

test.describe('模型管理 contract-v1', () => {
  test('供应商卡片打开详情，模型与参数可见', async ({ page }, testInfo) => {
    await stubApi(page);
    await page.goto('/settings');
    await expect(page.getByText('DeepSeek 主账号')).toBeVisible();
    // 卡片层不直接展示模型
    await expect(page.getByText('deepseek-chat')).toHaveCount(0);

    await page.getByRole('button', { name: '打开 DeepSeek 主账号 的详情' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByText('deepseek-chat')).toBeVisible();
    await expect(page.getByText('用于问答')).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('model-detail-1440.png'), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });

  test('发现列表只追加且显示来源', async ({ page }) => {
    await stubApi(page);
    await page.goto('/settings');
    await page.getByRole('button', { name: '打开 DeepSeek 主账号 的详情' }).click();
    await page.getByRole('button', { name: /从服务获取/ }).click();
    await expect(page.getByText('来自上游实时接口')).toBeVisible();
    // 已有模型显示为已添加且不可再选；新模型可选
    await expect(page.getByText('已添加')).toBeVisible();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('checkbox', { name: 'deepseek-chat 已添加' })).toBeDisabled();
    await expect(dialog.getByRole('checkbox', { name: 'deepseek-reasoner' })).toBeEnabled();
  });

  test('发现接口失败时给出错误并可重试，不冒充空列表', async ({ page }) => {
    await stubApi(page, { discoveryStatus: 500, discovery: { code: 'UPSTREAM_ERROR', message: '上游返回错误。' } });
    await page.goto('/settings');
    await page.getByRole('button', { name: '打开 DeepSeek 主账号 的详情' }).click();
    await page.getByRole('button', { name: /从服务获取/ }).click();
    const alert = page.getByRole('alert').first();
    await expect(alert).toBeVisible();
    await expect(page.getByRole('button', { name: /重试/ })).toBeVisible();
  });

  test('无模型列表接口的供应商明确说明需手工添加', async ({ page }) => {
    const codexConnection = {
      ...deepseekConnection,
      id: 'conn-codex',
      displayName: 'Codex',
      providerId: 'openai_codex',
      providerLabel: 'OpenAI Codex',
      protocol: 'openai-responses',
      hasCredential: false,
    };
    await stubApi(page, {
      connections: [codexConnection],
      profiles: [],
      discovery: { models: [], source: 'manual', note: '该供应商没有公开模型列表接口，请手工添加模型 ID。' },
      auth: {
        connection: 'disconnected',
        authMode: 'oauth',
        provider: 'openai_codex',
        available: false,
        unavailableReason: '尚未配置 Codex OAuth 应用凭据，无法发起真实登录。',
      },
    });
    await page.goto('/settings');
    await page.getByRole('button', { name: '打开 Codex 的详情' }).click();
    // 认证区如实说明不可用原因，不显示伪造的授权地址
    await expect(page.getByText('尚未配置 Codex OAuth 应用凭据')).toBeVisible();
    await page.getByRole('button', { name: /从服务获取/ }).click();
    await expect(page.getByText(/没有公开的模型列表接口/)).toBeVisible();
  });

  test('打开卡片不切换默认模型，用于问答才触发默认写入', async ({ page }) => {
    let defaultWrites = 0;
    await stubApi(page);
    await page.route('**/api/v1/model-defaults', async (route) => {
      defaultWrites += 1;
      await route.fulfill({
        status: 200,
        json: { revision: 6, defaultChatProfileId: 'prof-1', connections: [deepseekConnection], profiles: [profile] },
      });
    });
    await page.goto('/settings');
    await page.getByRole('button', { name: '打开 DeepSeek 主账号 的详情' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    expect(defaultWrites).toBe(0);
    await page.getByRole('button', { name: '用于问答' }).click();
    await expect.poll(() => defaultWrites).toBe(1);
  });

  test('手机视口详情可滚动且无横向溢出', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await stubApi(page);
    await page.goto('/settings');
    await page.getByRole('button', { name: '打开 DeepSeek 主账号 的详情' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('button', { name: '保存修改' })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('model-detail-390.png'), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });

  test('1920 视口供应商网格与详情', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await stubApi(page);
    await page.goto('/settings');
    await expect(page.getByText('DeepSeek 主账号')).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('model-grid-1920.png'), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });

  test('供应商目录读取失败不阻塞已有连接展示', async ({ page }) => {
    await page.route('**/api/v1/model-providers', (route) =>
      route.fulfill({ status: 503, json: { code: 'SERVICE_UNAVAILABLE', message: '目录暂不可用', retryable: true } }),
    );
    await page.route('**/api/v1/model-catalog', (route) =>
      route.fulfill({
        status: 200,
        json: { revision: 5, defaultChatProfileId: null, connections: [deepseekConnection], profiles: [profile] },
      }),
    );
    await page.goto('/settings');
    // 连接仍可见（用连接自带的 providerLabel），不因目录失败而清空
    await expect(page.getByText('DeepSeek 主账号')).toBeVisible();
  });
});
