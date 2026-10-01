// T1: 四页 × 三视口 溢出审计 + 截图；T2 前置：窄视口 rail 行为
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const results = [];
const viewports = [
  { name: '1440x900', width: 1440, height: 900 },
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '390x844', width: 390, height: 844 },
];
const pages = [
  { key: 'books', url: '/books' },
  { key: 'book-detail', url: '/books/demo-book-fractions' },
  { key: 'courses', url: '/courses' },
  { key: 'course-detail', url: '/courses/demo-course-math' },
];

const auditScript = () => {
  const vw = window.innerWidth;
  const doc = document.documentElement;
  const overflows = [];
  document.querySelectorAll('body *').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.right > vw + 1) {
      const cls = (typeof el.className === 'string' ? el.className : '').slice(0, 70);
      overflows.push({ tag: el.tagName, cls, right: Math.round(r.right), text: (el.textContent || '').trim().slice(0, 30) });
    }
  });
  const rail = document.querySelector('.books-rail');
  return {
    scrollWidth: doc.scrollWidth,
    innerWidth: vw,
    overflowCount: overflows.length,
    overflowSample: overflows.slice(0, 6),
    railPosition: rail ? getComputedStyle(rail).position : null,
  };
};

const browser = await chromium.launch({ headless: true, channel: 'msedge' });
try {
  for (const vp of viewports) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await ctx.newPage();
    // 种子：书籍走「载入演示数据」按钮路径；课程直写 localStorage（shoot.mjs 字段一致）
    await page.goto(base + '/books', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await page.waitForTimeout(500);
    await page.goto(base + '/courses', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await page.waitForTimeout(500);
    for (const p of pages) {
      await page.goto(base + p.url, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(600);
      const a = await page.evaluate(auditScript);
      await page.screenshot({ path: `${OUT}/t1-${p.key}-${vp.name}.png`, fullPage: false });
      results.push({ item: `viewport ${vp.name} ${p.key}`, ...a });
      console.log(`${vp.name} ${p.key}: scrollWidth=${a.scrollWidth} innerWidth=${a.innerWidth} overflow=${a.overflowCount} rail=${a.railPosition} sample=${JSON.stringify(a.overflowSample)}`);
    }
    await ctx.close();
  }
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t1-viewport-audit.json`, JSON.stringify(results, null, 2));
}
