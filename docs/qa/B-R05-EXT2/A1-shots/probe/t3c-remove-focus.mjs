// T3c: 真实键盘 Tab 到移除钮，验证 focus-visible 显隐
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
  await p.getByRole('button', { name: '编辑', exact: true }).focus();
  // Tab 到移除钮：编辑→归档→删除→编辑大纲→cb1→cb2→附加资料→移除
  let result = null;
  for (let i = 0; i < 10; i++) {
    await p.keyboard.press('Tab');
    const state = await p.evaluate(() => {
      const el = document.activeElement;
      return {
        name: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30),
        cls: (typeof el.className === 'string' ? el.className : '').slice(0, 50),
        opacity: getComputedStyle(el).opacity,
      };
    });
    console.log(`tab ${i + 1}:`, JSON.stringify(state));
    if (state.cls.includes('courses-resource-remove')) { result = state; break; }
  }
  console.log('RESULT remove-btn keyboard focus:', JSON.stringify(result));
  await p.screenshot({ path: `${OUT}/t3c-remove-focus-visible.png` });
  await c.close();
} finally {
  await browser.close();
}
