import { test, expect } from '@playwright/test';

// e2e 环境只启动前端（5174），后端不可达：验证“服务停止时展示准确错误”，不伪造可用状态
test('设置页在后端不可用时展示准确错误与重试入口', async ({ page }, testInfo) => {
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      status: 503,
      json: { code: 'SERVICE_UNAVAILABLE', message: '后端服务不可用。', retryable: true },
    }),
  );
  await page.goto('/settings');
  const alert = page.getByText('无法读取模型设置');
  await expect(alert).toBeVisible();
  await expect(alert).toContainText('后端服务不可用');
  await expect(page.getByRole('button', { name: '重试' })).toBeVisible();
  // 不渲染任何可提交的连接/模型表单，避免误以为功能可用
  await expect(page.locator('.settings-form')).toHaveCount(0);
  await expect(page.locator('.settings-card')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('settings-backend-down.png') });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
