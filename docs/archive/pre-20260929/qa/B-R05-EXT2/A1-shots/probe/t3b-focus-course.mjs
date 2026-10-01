// T3b: 课程详情页内容区 Tab 焦点（跳过侧栏），验证勾选框/移除钮/附加资料按钮可达 + 焦点环
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
const results = [];
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await p.goto(base + '/courses', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  await p.goto(base + '/courses/demo-course-math', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(600);
  // 直接聚焦内容区首个按钮（编辑），然后 Tab 向后走
  const seq = await p.evaluate(() => {
    const focusables = Array.from(document.querySelectorAll('.space-content a[href], .space-content button, .space-content input')).filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
    return focusables.slice(0, 14).map((el) => ({
      tag: el.tagName,
      name: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 26),
      cls: (typeof el.className === 'string' ? el.className : '').slice(0, 36),
    }));
  });
  console.log('content focusables:', JSON.stringify(seq, null, 1));
  results.push({ test: 'course detail content focusables', seq });
  // 键盘实际走查：聚焦编辑按钮后 Tab 4 次
  await p.getByRole('button', { name: '编辑', exact: true }).focus();
  const walked = [];
  for (let i = 0; i < 6; i++) {
    await p.keyboard.press('Tab');
    walked.push(await p.evaluate(() => {
      const el = document.activeElement;
      const cs = getComputedStyle(el);
      return {
        name: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 26),
        cls: (typeof el.className === 'string' ? el.className : '').slice(0, 36),
        ring: (cs.outlineStyle !== 'none' && cs.outlineWidth !== '0px') || cs.boxShadow !== 'none',
      };
    }));
  }
  console.log('tab walk:', JSON.stringify(walked, null, 1));
  results.push({ test: 'course detail tab walk', walked });
  // 移除钮 keyboard focus 显隐（760px 以上默认 opacity:0，focus-visible 应显）
  const rmVisible = await p.evaluate(() => {
    const rm = document.querySelector('.courses-resource-remove');
    if (!rm) return null;
    rm.focus();
    return { opacityAfterFocus: getComputedStyle(rm).opacity };
  });
  console.log('remove btn focus opacity:', JSON.stringify(rmVisible));
  results.push({ test: 'remove btn keyboard focus visibility', rmVisible });
  await p.screenshot({ path: `${OUT}/t3b-course-focus.png` });
  await c.close();
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t3b-focus-course.json`, JSON.stringify(results, null, 2));
}
