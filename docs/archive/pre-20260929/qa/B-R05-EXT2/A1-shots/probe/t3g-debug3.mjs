// T3g: 调试3——document.styleSheets 枚举 + opacity 全局来源
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
  const sheets = await p.evaluate(() => {
    const names = [];
    for (const sheet of document.styleSheets) {
      names.push(sheet.href ? sheet.href.split('/').pop() : `inline(${sheet.cssRules.length})`);
    }
    return names;
  });
  console.log('sheets:', JSON.stringify(sheets));
  // 直接在移除钮 focus 状态下读 opacity 与所有 cssRules 中含 courses-resource-remove 的规则
  for (let i = 0; i < 60; i++) {
    await p.keyboard.press('Tab');
    const hit = await p.evaluate(() => document.activeElement.className.includes('courses-resource-remove'));
    if (hit) break;
  }
  const dbg = await p.evaluate(() => {
    const found = [];
    for (const sheet of document.styleSheets) {
      let rules; try { rules = sheet.cssRules; } catch { continue; }
      const walk = (list) => {
        for (const rule of list) {
          if (rule.cssRules) { walk(rule.cssRules); continue; }
          if (rule.cssText && rule.cssText.includes('courses-resource-remove')) found.push({ href: sheet.href ? sheet.href.split('/').pop() : 'inline', text: rule.cssText.slice(0, 200) });
        }
      };
      walk(rules);
    }
    const el = document.querySelector('.courses-resource-remove');
    return { found, opacity: getComputedStyle(el).opacity, fv: el.matches(':focus-visible') };
  });
  console.log(JSON.stringify(dbg, null, 2));
  await c.close();
} finally {
  await browser.close();
}
