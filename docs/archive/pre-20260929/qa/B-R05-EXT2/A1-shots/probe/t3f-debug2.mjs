// T3f: 调试2——移除钮自身的 opacity 匹配规则 + 行 hover 检查
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
  for (let i = 0; i < 60; i++) {
    await p.keyboard.press('Tab');
    const hit = await p.evaluate(() => document.activeElement.className.includes('courses-resource-remove'));
    if (hit) break;
  }
  const dbg = await p.evaluate(() => {
    const el = document.querySelector('.courses-resource-remove');
    const out = { selfMatches: [], parentHover: null, inlineStyle: el.getAttribute('style'), isFocusVisible: el.matches(':focus-visible'), focused: el === document.activeElement };
    for (const sheet of document.styleSheets) {
      let rules; try { rules = sheet.cssRules; } catch { continue; }
      const walk = (list) => {
        for (const rule of list) {
          if (rule.cssRules) { walk(rule.cssRules); continue; }
          if (!rule.selectorText) continue;
          try { if (el.matches(rule.selectorText)) out.selfMatches.push(rule.selectorText); } catch {}
        }
      };
      walk(rules);
    }
    return out;
  });
  console.log(JSON.stringify(dbg, null, 2));
  await c.close();
} finally {
  await browser.close();
}
