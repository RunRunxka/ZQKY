import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const manifest = process.env.G2_V00_SEED_JSON;
if (!manifest) throw new Error('Isolated seed required');
const seed = JSON.parse(readFileSync(manifest, 'utf8')) as { practiceA: { practiceSetId: string }; practiceB: { practiceSetId: string; title: string } };
for (const [width, height] of [[390, 844], [1024, 768], [1440, 900]] as const) {
  test(`dirty leave dialog keyboard and viewport ${width}x${height}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height }); await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(`/practices?practiceSetId=${encodeURIComponent(seed.practiceA.practiceSetId)}`);
    await page.getByLabel('第1题整题满分', { exact: true }).fill('5');
    await page.getByRole('button', { name: new RegExp(`G2独立第二练习\\s+练习 ${seed.practiceB.practiceSetId}`) }).click();
    const dialog = page.getByRole('dialog', { name: '处理未保存练习' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('button', { name: '取消并继续编辑', exact: true })).toBeFocused();
    const box = await dialog.boundingBox(); expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0); expect(box!.x + box!.width).toBeLessThanOrEqual(width + 1);
    expect(box!.y).toBeGreaterThanOrEqual(0); expect(box!.y + box!.height).toBeLessThanOrEqual(height + 1);
    await info.attach('dialog', { body: await page.screenshot(), contentType: 'image/png' });
    await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible();
    await expect(page.getByLabel('第1题整题满分', { exact: true })).toHaveValue('5');
    await info.attach('keyboard-cancel-preserves-input', { body: await page.screenshot(), contentType: 'image/png' });
  });
}
