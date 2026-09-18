// T3i: 正确枚举 CSSOM 规则（不误判 CSSStyleRule），确认浏览器内存中的规则与顺序
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
  const rules = await p.evaluate(() => {
    const found = [];
    for (const sheet of document.styleSheets) {
      let list; try { list = sheet.cssRules; } catch { continue; }
      const walk = (rules, media) => {
        for (const rule of rules) {
          if (rule.type === 1) { // CSSStyleRule
            if (rule.selectorText && rule.selectorText.includes('courses-resource-remove')) {
              found.push({ media: media || '-', sel: rule.selectorText, opacity: rule.style.getPropertyValue('opacity') });
            }
          } else if (rule.type === 4 && rule.cssRules) { // media
            walk(rule.cssRules, rule.conditionText);
          }
        }
      };
      walk(list, null);
    }
    return found;
  });
  console.log(JSON.stringify(rules, null, 2));
  await c.close();
} finally {
  await browser.close();
}
