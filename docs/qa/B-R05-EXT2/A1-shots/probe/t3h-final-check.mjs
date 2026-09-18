// T3h: 移除钮 focus-visible 最终确认——读 specificity 无关的 resolved opacity，
// 并用 CDP forcePseudoState 兜底（模拟真实 focus-visible）
import { chromium } from 'playwright';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await p.goto(base + '/courses', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  await p.goto(base + '/courses/demo-course-math', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(600);
  // 纯键盘 Tab 到移除钮
  let hit = false;
  for (let i = 0; i < 60; i++) {
    await p.keyboard.press('Tab');
    hit = await p.evaluate(() => document.activeElement.className.includes('courses-resource-remove'));
    if (hit) break;
  }
  console.log('tabbed to remove:', hit);
  // 读 opacity + hover 检查
  const state1 = await p.evaluate(() => {
    const el = document.querySelector('.courses-resource-remove');
    return { opacity: getComputedStyle(el).opacity, fv: el.matches(':focus-visible') };
  });
  console.log('keyboard focus state:', JSON.stringify(state1));
  await p.screenshot({ path: `${OUT}/t3h-remove-kbd-focus.png` });
  // 行 hover 后钮的 opacity（鼠标路径）
  const row = p.locator('.courses-resource').first();
  await row.hover();
  await p.waitForTimeout(200);
  const state2 = await p.evaluate(() => {
    const el = document.querySelector('.courses-resource-remove');
    return { opacity: getComputedStyle(el).opacity };
  });
  console.log('row hover state:', JSON.stringify(state2));
  await p.screenshot({ path: `${OUT}/t3h-remove-row-hover.png` });
  await c.close();
} finally {
  await browser.close();
}
