// T3j: 全量级联枚举——所有匹配移除钮且含 opacity 声明的规则（按层叠顺序）
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
    if (await p.evaluate(() => document.activeElement.className.includes('courses-resource-remove'))) break;
  }
  const rules = await p.evaluate(() => {
    const el = document.querySelector('.courses-resource-remove');
    const found = [];
    for (const sheet of document.styleSheets) {
      let list; try { list = sheet.cssRules; } catch { continue; }
      const walk = (rules, media) => {
        for (const rule of rules) {
          if (rule.type === 1) {
            if (rule.selectorText) {
              try {
                if (el.matches(rule.selectorText) && rule.style.getPropertyValue('opacity') !== '') {
                  found.push({ media: media || '-', sel: rule.selectorText, opacity: rule.style.getPropertyValue('opacity'), sheet: sheet.href ? sheet.href.split('/').pop() : 'inline' });
                }
              } catch {}
            }
          } else if (rule.type === 4 && rule.cssRules) {
            walk(rule.cssRules, rule.conditionText);
          } else if (rule.cssRules && rule.type !== 1) {
            walk(rule.cssRules, media);
          }
        }
      };
      walk(list, null);
    }
    return { found, computed: getComputedStyle(el).opacity, fv: el.matches(':focus-visible'), hovered: el.matches(':hover') };
  });
  console.log(JSON.stringify(rules, null, 2));
  await c.close();
} finally {
  await browser.close();
}
