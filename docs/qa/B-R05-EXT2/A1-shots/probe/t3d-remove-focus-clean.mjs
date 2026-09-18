// T3d: 纯净键盘路径复测移除钮 focus-visible（无程序化 focus 起点）
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
  // 从页面顶部开始纯键盘 Tab（无任何程序化 focus）
  let result = null;
  for (let i = 0; i < 60; i++) {
    await p.keyboard.press('Tab');
    const state = await p.evaluate(() => {
      const el = document.activeElement;
      return {
        name: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30),
        cls: (typeof el.className === 'string' ? el.className : '').slice(0, 50),
        opacity: getComputedStyle(el).opacity,
        isFocusVisible: el.matches(':focus-visible'),
      };
    });
    if (state.cls.includes('courses-resource-remove')) { result = state; console.log(`tab ${i + 1} HIT:`, JSON.stringify(state)); break; }
    if (i < 40) continue;
  }
  console.log('RESULT clean-keyboard remove-btn:', JSON.stringify(result));
  await p.screenshot({ path: `${OUT}/t3d-remove-focus-clean.png` });
  await c.close();
} finally {
  await browser.close();
}
