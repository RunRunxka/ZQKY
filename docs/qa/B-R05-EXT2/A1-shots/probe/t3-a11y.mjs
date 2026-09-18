// T3: 键盘焦点可达性 + aria 断言前提核对（四页）
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const results = [];
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
async function tabProbe(page, count) {
  const seen = [];
  for (let i = 0; i < count; i++) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return { tag: 'body' };
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      // 焦点环可见性：outline 或 box-shadow 非 none
      const ring = (cs.outlineStyle !== 'none' && cs.outlineWidth !== '0px') || (cs.boxShadow !== 'none' && cs.boxShadow !== '');
      return {
        tag: el.tagName,
        name: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30),
        cls: (typeof el.className === 'string' ? el.className : '').slice(0, 40),
        ring,
        visible: r.width > 0 && r.height > 0,
      };
    });
    seen.push(info);
  }
  return seen;
}
try {
  // 书籍列表
  const c1 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p1 = await c1.newPage();
  await p1.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p1.getByRole('button', { name: '载入演示数据' }).click();
  await p1.waitForTimeout(400);
  // 从地址栏聚焦开始
  await p1.evaluate(() => document.activeElement.blur());
  const booksTab = await tabProbe(p1, 10);
  results.push({ test: 'books tab sequence', booksTab });
  console.log('books tabs:', JSON.stringify(booksTab, null, 1));
  // 搜索框存在
  const searchBox = await p1.getByRole('searchbox', { name: '搜索书籍' }).count();
  console.log('searchbox count:', searchBox);
  // 书籍详情：nav aria-label 章节目录
  await p1.goto(base + '/books/demo-book-fractions', { waitUntil: 'domcontentloaded' });
  await p1.waitForTimeout(600);
  const navRail = await p1.evaluate(() => {
    const nav = document.querySelector('nav[aria-label="章节目录"]');
    if (!nav) return null;
    const links = nav.querySelectorAll('a');
    const first = nav.querySelector('a');
    return { exists: true, linkCount: links.length, firstHref: first ? first.getAttribute('href') : null };
  });
  console.log('nav rail:', JSON.stringify(navRail));
  results.push({ test: 'nav aria-label 章节目录', navRail });
  // 侧栏当前页高亮 aria-current
  const current = await p1.evaluate(() => {
    const el = document.querySelector('nav[aria-label="章节目录"] a[aria-current="page"]');
    return el ? { href: el.getAttribute('href'), cls: el.className } : null;
  });
  console.log('aria-current:', JSON.stringify(current));
  results.push({ test: 'aria-current page', current });
  await c1.close();

  // 课程详情：勾选框/移除钮/返回链接/banner
  const c2 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p2 = await c2.newPage();
  await p2.goto(base + '/courses', { waitUntil: 'domcontentloaded' });
  await p2.getByRole('button', { name: '载入演示数据' }).click();
  await p2.waitForTimeout(400);
  await p2.goto(base + '/courses/demo-course-math', { waitUntil: 'domcontentloaded' });
  await p2.waitForTimeout(600);
  const checks = await p2.evaluate(() => {
    const out = {};
    out.bannerNote = !!Array.from(document.querySelectorAll('[role="note"]')).find((n) => n.textContent.includes('课程学习会话未接入'));
    out.syllabusHeading = (document.querySelector('h2.space-group-label') || {}).textContent || '';
    const cb = document.querySelector('input[type="checkbox"]');
    out.checkboxLabel = cb ? cb.getAttribute('aria-label') : null;
    const rm = document.querySelector('.courses-resource-remove');
    out.removeLabel = rm ? rm.getAttribute('aria-label') : null;
    out.backLink = !!Array.from(document.querySelectorAll('a')).find((a) => a.textContent.trim() === '返回课程列表');
    const suffixEl = document.querySelector('.courses-resource-suffix');
    out.suffixText = suffixEl ? suffixEl.textContent : null;
    const pb = document.querySelector('[role="progressbar"]');
    out.progressbar = pb ? { now: pb.getAttribute('aria-valuenow'), min: pb.getAttribute('aria-valuemin'), max: pb.getAttribute('aria-valuemax') } : null;
    return out;
  });
  console.log('course-detail checks:', JSON.stringify(checks, null, 1));
  results.push({ test: 'course-detail aria premises', checks });
  // Tab 可达性：勾选框与移除钮
  await p2.evaluate(() => document.activeElement.blur());
  const courseTab = await tabProbe(p2, 8);
  console.log('course tabs:', JSON.stringify(courseTab));
  results.push({ test: 'course tab sequence', courseTab });
  await c2.close();
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t3-a11y.json`, JSON.stringify(results, null, 2));
}
