import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { chromium, expect } from '@playwright/test';

const [chainPath, output, mode] = process.argv.slice(2);
assert(['diagnostic', 'acceptance'].includes(mode));
assert(chainPath && output && !fs.existsSync(output), 'New explicit output directory required');
const chain = JSON.parse(fs.readFileSync(chainPath, 'utf8'));
assert(chain.seed.dataDir.includes('zqky-b4-v00-'), 'Only this batch synthetic seed');
fs.mkdirSync(output, { recursive: true });
const observations = [], responses = [], forbiddenWrites = [];
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
await context.route('**/api/v1/**', async route => {
  if (route.request().method() !== 'GET') {
    forbiddenWrites.push({ url: route.request().url(), method: route.request().method() });
    await route.abort('blockedbyclient');
  } else await route.continue();
});
const page = await context.newPage();
page.on('response', response => responses.push({ url: response.url(), status: response.status() }));
let failure;
async function capture(locator, name) {
  await expect(locator).toBeVisible({ timeout: 15000 });
  await locator.scrollIntoViewIfNeeded();
  const bounds = await locator.boundingBox();
  await page.screenshot({ path: path.join(output, name + '.png') });
  observations.push({ name, url: page.url(), bounds, viewport: page.viewportSize(),
    horizontalOverflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth) });
}
function luminance(rgb) {
  const parts = rgb.match(/[\d.]+/g).slice(0, 3).map(Number).map(n => n / 255)
    .map(n => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4);
  return parts[0] * .2126 + parts[1] * .7152 + parts[2] * .0722;
}
try {
  await page.goto('http://127.0.0.1:5174/practices?practiceSetId=' + encodeURIComponent(chain.created.practiceSetId));
  const exports = page.getByRole('region', { name: '固定练习导出', exact: true });
  await capture(exports.getByRole('heading', { name: '固定审核版本导出', exact: true }), 'mobile-exports-heading');
  const downloads = exports.getByRole('button', { name: /^下载/ });
  await expect(downloads).toHaveCount(3, { timeout: 15000 });
  for (let i = 0; i < 3; i++) await capture(downloads.nth(i), 'mobile-download-' + i);
  await page.goto('http://127.0.0.1:5174/learning-analysis?runId=' + encodeURIComponent(chain.returnedAnalysis.runId));
  const facts = page.getByRole('region', { name: '报告事实与证据', exact: true });
  await capture(facts.getByRole('heading', { name: '本次固定依据', exact: true }), 'mobile-returned-facts');
  await facts.getByRole('tab', { name: '全部题证据', exact: true }).click();
  const details = facts.locator(':scope > [role="tabpanel"] > details');
  await expect(details).toHaveCount(8, { timeout: 15000 });
  await details.first().locator(':scope > summary').click();
  await capture(details.first().locator(':scope > summary'), 'mobile-returned-first-leaf');
  await details.first().getByText('原始来源与回流映射', { exact: true }).click();
  await capture(details.first().locator('pre'), 'mobile-returned-mapping');
  const selectedMeta = page.getByRole('region', { name: '固定报告历史', exact: true }).locator('button.primary .b4-meta');
  await expect(selectedMeta).toHaveCount(1);
  const style = await selectedMeta.evaluate(element => ({ text: element.textContent,
    color: getComputedStyle(element).color, background: getComputedStyle(element.closest('button')).backgroundColor }));
  const a = luminance(style.color), b = luminance(style.background);
  observations.push({ name: 'selected-history-contrast', ...style, contrast: (Math.max(a,b) + .05) / (Math.min(a,b) + .05) });
  await capture(selectedMeta, 'mobile-selected-history');
  assert.equal(forbiddenWrites.length, 0);
  assert(observations.every(o => !o.horizontalOverflow));
  assert(observations.find(o => o.name === 'selected-history-contrast').contrast >= 4.5,
    'Selected history metadata requires readable 4.5 contrast');
} catch (error) { failure = { name: error.name, message: error.message, stack: error.stack }; }
finally {
  await context.tracing.stop({ path: path.join(output, 'trace.zip') });
  await context.close();
  await browser.close();
  fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify({ mode, chainPath, observations,
    responses, forbiddenWrites, failure, contextClosed: true, browserClosed: true }, null, 2));
}
if (failure) { console.error(failure.stack); process.exitCode = 1; }
else console.log(JSON.stringify({ mode, screenshots: observations.filter(o => o.bounds).length, contextClosed: true, browserClosed: true }));
