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
  // 文案随 SKILL-INJECT v1 更新：MCP 分区已如实标注未实现，按钮不再自称“模拟配置”
  await dialog.getByRole('button', { name: '保存', exact: true }).click();
  await page.getByRole('switch', { name: '启用 课程检索示例' }).click();
  await expect(page.getByRole('switch', { name: '启用 课程检索示例' })).toBeChecked();
  await page.reload();
  await expect(page.getByRole('switch', { name: '启用 课程检索示例' })).toBeChecked();
  await page.goto('/skills');
  await expect(page).toHaveURL(/\/settings#skills$/);
  await expect(
    page.getByRole('navigation', { name: '设置分类' }).getByRole('link', { name: /Skills/ }),
  ).toHaveAttribute('aria-current', 'location');
  // SKILL-INJECT v1：内置教学技能可在真实浏览器一次载入，卡片与启用态可见
  await expect(page.getByText('还没有技能。可载入内置教学技能，或添加自己的技能。')).toBeVisible();
  await page.getByRole('button', { name: '载入内置教学技能' }).click();
  await expect(page.getByText('教案规范')).toBeVisible();
  await expect(page.getByText('课标对齐')).toBeVisible();
  await expect(page.getByText('命题规范')).toBeVisible();
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
