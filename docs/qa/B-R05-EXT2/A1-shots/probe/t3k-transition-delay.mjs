// T3k: Tab 后等待过渡完成再读 opacity
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
  for (let i = 0; i < 60; i++) {
    await p.keyboard.press('Tab');
    if (await p.evaluate(() => document.activeElement.className.includes('courses-resource-remove'))) break;
  }
  await p.waitForTimeout(600); // 等 150ms 过渡完成 + 余量
  const state = await p.evaluate(() => {
    const el = document.querySelector('.courses-resource-remove');
    return { opacity: getComputedStyle(el).opacity, fv: el.matches(':focus-visible'), focused: el === document.activeElement };
  });
  console.log('after 600ms:', JSON.stringify(state));
  await p.screenshot({ path: `${OUT}/t3k-remove-focus-settled.png` });
  await c.close();
} finally {
  await browser.close();
}
