import { test, expect } from '@playwright/test';

/**
 * R9 学习问答套件：composer 控件（附件 / 上下文环 / 模型选择）、无模式切换、减少动画可用。
 * 模型目录以路由级 mock 提供；对话流本身不在此套件（由后端 pytest + 探针覆盖）。
 */

const PROFILE = {
  id: 'profile-1',
  connectionId: 'conn-1',
  displayName: '模拟模型',
  modelId: 'sim-chat-1',
  purpose: 'chat',
  contextTokens: 8000,
  maxOutputTokens: 512,
  supportedParams: [],
  reasoningEnabled: null,
  reasoningEffort: null,
  contextWindow: { tokens: 8000, source: 'profile', note: null },
  reasoningSupport: {
    supported: true,
    levels: [
      { value: 'low', label: '低' },
      { value: 'medium', label: '中' },
      { value: 'high', label: '高' },
    ],
    default: 'medium',
    style: 'openai_effort',
    source: 'registry',
    note: null,
  },
  capabilities: {},
  connection: { displayName: '模拟连接', protocol: 'openai-chat', hasCredential: true },
  createdAt: '2026-10-12T00:00:00Z',
  updatedAt: '2026-10-12T00:00:00Z',
};

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      json: {
        revision: 1,
        defaultChatProfileId: 'profile-1',
        profiles: [PROFILE],
        connections: [PROFILE.connection],
      },
    }),
  );
});

test('/chat：composer 控件齐备（附件 / 上下文环 / 思考强度受支持档位 / 模型选择）', async ({
  page,
}) => {
  await page.goto('/chat');
  await expect(page.locator('.chat-page')).toBeVisible();
  await expect(page.getByRole('button', { name: '添加附件' })).toBeVisible();
  await expect(page.getByLabel(/上下文占用/)).toBeVisible();
  // 思考强度：仅列受支持档位（低/中/高）
  const effort = page.getByLabel('思考强度');
  await expect(effort).toBeVisible();
  await expect(effort.locator('option')).toHaveCount(4); // 默认 + 三档
  await expect(page.locator('.model-selector').first()).toBeVisible();
  // 无模式切换：不出现「追问澄清 / RAG」等选项文案
  await expect(page.getByText('追问澄清')).toHaveCount(0);
  await expect(page.getByText('RAG')).toHaveCount(0);
});

test('/chat：空输入不可发送，输入后可发送', async ({ page }) => {
  await page.goto('/chat');
  const send = page.getByRole('button', { name: '发送' });
  await expect(send).toBeDisabled();
  await page.getByLabel('输入问题').fill('函数的单调性');
  await expect(send).toBeEnabled();
});

test('/chat：prefers-reduced-motion 下仍可用', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/chat');
  await expect(page.getByLabel('输入问题')).toBeVisible();
  await expect(page.getByRole('button', { name: '添加附件' })).toBeVisible();
});
