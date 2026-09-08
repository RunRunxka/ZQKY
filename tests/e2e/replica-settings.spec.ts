import { expect, test } from '@playwright/test';
test.use({ video: process.env.REPLICA_VIDEO === '1' ? 'on' : 'off' });
test('设置内扩展管理、兼容入口与减少动画', async ({ page }) => {
  await page.goto('/mcp');
  await expect(page).toHaveURL(/\/settings#mcp$/);
  await expect(
    page
      .getByRole('navigation', { name: '项目功能导航' })
      .getByRole('button', { name: 'MCP', exact: true }),
  ).toHaveCount(0);
  await page.getByRole('button', { name: '添加 MCP', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('名称', { exact: true }).fill('课程检索示例');
  await dialog.getByLabel('描述', { exact: true }).fill('隔离测试数据');
  await dialog.getByRole('button', { name: '保存模拟配置' }).click();
  await page.getByRole('switch', { name: '启用 课程检索示例' }).click();
  await expect(page.getByRole('switch', { name: '启用 课程检索示例' })).toBeChecked();
  await page.reload();
  await expect(page.getByRole('switch', { name: '启用 课程检索示例' })).toBeChecked();
  await page.goto('/skills');
  await expect(page).toHaveURL(/\/settings#skills$/);
  await expect(
    page.getByRole('navigation', { name: '设置分类' }).getByRole('link', { name: /Skills/ }),
  ).toHaveAttribute('aria-current', 'location');
  await page.screenshot({ path: 'test-results/replica-settings-desktop.png' });
  await page
    .getByRole('navigation', { name: '设置分类' })
    .getByRole('link', { name: /外观/ })
    .click();
  await page.getByLabel('减少动画', { exact: true }).check();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'reduced');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: 'test-results/replica-settings-mobile.png' });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
