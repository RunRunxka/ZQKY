// T3e: 调试级联——找出把移除钮 opacity 压为 0 的规则来源
import { chromium } from 'playwright';
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
  for (let i = 0; i < 60; i++) {
    await p.keyboard.press('Tab');
    const hit = await p.evaluate(() => document.activeElement.className.includes('courses-resource-remove'));
    if (hit) break;
  }
  const dbg = await p.evaluate(() => {
    const el = document.querySelector('.courses-resource-remove');
    const matched = [];
    for (const sheet of document.styleSheets) {
      let rules; try { rules = sheet.cssRules; } catch { continue; }
      const walk = (list) => {
        for (const rule of list) {
          if (rule.cssRules) { walk(rule.cssRules); continue; }
          if (!rule.selectorText) continue;
          try { if (el.matches(rule.selectorText)) matched.push({ sel: rule.selectorText, css: rule.style.cssText.slice(0, 120), href: sheet.href ? sheet.href.split('/').pop() : 'inline' }); } catch {}
        }
      };
      walk(rules);
    }
    return matched.filter((m) => m.css.includes('opacity'));
  });
  console.log(JSON.stringify(dbg, null, 2));
  await c.close();
} finally {
  await browser.close();
}
