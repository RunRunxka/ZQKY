import { expect, test, type Page } from '@playwright/test';

async function seed(page: Page, long = false) {
  await page.addInitScript(({ longText }) => {
    const now = '2026-09-08T00:00:00.000Z';
    const text = longText
      ? Array.from({ length: 100 }, (_, i) => `第 ${i} 段正文。这是用于验证阅读位置的足够长的测试材料。`).join('\n\n')
      : '# 标题\n\n相同的句子。\n\n相同的句子。';
    const materials = ['a', 'b'].map((id) => ({
      id, title: `材料${id.toUpperCase()}`, text, filename: null, sourceKind: 'text', sourceUrl: null,
      charCount: text.length, sizeBytes: text.length * 3, positionPct: 0,
      workspaceIds: ['review-ws'], createdAt: now, updatedAt: now,
    }));
    localStorage.setItem('zhiqikeyuan:reading-materials', JSON.stringify(materials));
    localStorage.setItem('zhiqikeyuan:reading-workspaces', JSON.stringify([{
      id: 'review-ws', title: '审查集合', description: '', activeMaterialId: 'a',
      tabs: materials.map((m) => ({ materialId: m.id, addedAt: now })), createdAt: now, updatedAt: now,
    }]));
  }, { longText: long });
  await page.goto('/reading/review-ws');
  await expect(page.getByRole('heading', { name: '审查集合' })).toBeVisible();
}

const reader = (page: Page) => page.locator('.reading-layout > .reading-pane:not(aside)');

test('R28: material library button changes the rendered route, not only the URL', async ({ page }) => {
  await seed(page);
  await page.getByRole('button', { name: '材料库…', exact: true }).click();
  await expect(page).toHaveURL(/\/reading\/materials$/);
  await expect(page.getByRole('heading', { name: '阅读材料库', exact: true })).toBeVisible();
});

test('R29: highlighting the second identical paragraph only marks that occurrence', async ({ page }, testInfo) => {
  await seed(page);
  await reader(page).locator('p[data-loc]').nth(1).evaluate((paragraph) => {
    const range = document.createRange();
    range.selectNodeContents(paragraph);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    paragraph.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
  });
  await page.getByRole('button', { name: '高亮（yellow）', exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath('duplicate-highlight.png') });
  await expect(reader(page).locator('mark')).toHaveCount(1);
  await expect(reader(page).locator('p[data-loc]').nth(0).locator('mark')).toHaveCount(0);
});

test('R30: switching to an unread material restores position zero', async ({ page }, testInfo) => {
  await seed(page, true);
  await reader(page).evaluate((el) => { el.scrollTop = (el.scrollHeight - el.clientHeight) * 0.6; });
  await expect.poll(() => reader(page).evaluate((el) => el.scrollTop)).toBeGreaterThan(100);
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('zhiqikeyuan:reading-materials')!)[0].positionPct)).toBeGreaterThan(0);
  await page.getByRole('tab', { name: /^材料B/ }).click();
  await expect(reader(page).locator('header strong')).toHaveText('材料B');
  await page.screenshot({ path: testInfo.outputPath('unread-position.png') });
  await expect.poll(() => reader(page).evaluate((el) => el.scrollTop)).toBe(0);
});

test('R31: collapsing navigation gives the reader additional width', async ({ page }, testInfo) => {
  await seed(page);
  const before = (await reader(page).boundingBox())!.width;
  await page.getByRole('button', { name: '收起导航', exact: true }).click();
  await expect(page.getByRole('complementary', { name: '阅读导航' })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('collapsed-navigation.png') });
  await expect.poll(async () => (await reader(page).boundingBox())!.width).toBeGreaterThan(before);
});
