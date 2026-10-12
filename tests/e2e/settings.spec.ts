import { test, expect } from '@playwright/test';

/** R9 设置页套件：三个面板渲染；后端不可用时显示错误态而非伪造可用。 */

test('/settings：外观 / 模型与连接 / 关于三个面板渲染', async ({ page }) => {
  await page.goto('/settings');
  await expect(page.locator('.settings-document')).toBeVisible();
  await expect(page.getByText('外观', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('模型与连接').first()).toBeVisible();
  await expect(page.getByText('关于智启课源').first()).toBeVisible();
});

test('/settings：模型目录不可用时给出错误与重试（不伪造可用）', async ({ page }) => {
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      status: 503,
      json: { code: 'SERVICE_UNAVAILABLE', message: '后端服务不可用。', retryable: true },
    }),
  );
  await page.goto('/settings');
  await expect(page.getByText('后端服务不可用').first()).toBeVisible();
  await expect(page.getByRole('button', { name: '重试' }).first()).toBeVisible();
});
