// B-R05-EXTEND v4 前后对照截图脚本（只写本证据目录，不碰正式数据）
// 用法：node docs/qa/B-R05-EXT4/shoot.mjs before|after
// 前置：5174 上运行本批构建产物（node scripts/run-web.mjs start 5174）
// 种子：教案用 tests/fixtures/lesson-plan.json（与 lesson-plan.spec.ts 同源）；设置页不注入数据。
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const phase = process.argv[2] ?? 'before';
const outDir = path.join(path.dirname(fileURLToPath(import.meta.url)), phase);
const base = 'http://127.0.0.1:5174';
const LESSON_KEY = 'zhiqikeyuan:lesson-plan:v1';
const lessonFixture = JSON.parse(
  fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '../../../tests/fixtures/lesson-plan.json'), 'utf8'),
);

async function seed(page) {
  await page.addInitScript(
    ({ key, draft }) => {
      if (!window.localStorage.getItem(key)) window.localStorage.setItem(key, JSON.stringify(draft));
    },
    { key: LESSON_KEY, draft: lessonFixture },
  );
}

const VIEWPORTS = [
  ['1440x900', { width: 1440, height: 900 }],
  ['1920x1080', { width: 1920, height: 1080 }],
  ['390x844', { width: 390, height: 844 }],
];

const PAGES = [
  ['settings', '/settings'],
  ['settings-models', '/settings#models'],
  ['lesson-plans', '/lesson-plans'],
];

const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
try {
  for (const [name, viewport] of VIEWPORTS) {
    for (const [slug, url] of PAGES) {
      const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
      const page = await context.newPage();
      await seed(page);
      await page.goto(`${base}${url}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(700);
      await page.screenshot({ path: path.join(outDir, `${slug}-${name}.png`), fullPage: true });
      await page.keyboard.press('Tab');
      await page.screenshot({ path: path.join(outDir, `${slug}-${name}-focus.png`), fullPage: false });

      if (name === '390x844') {
        const overflow = await page.evaluate(() => {
          const vw = window.innerWidth;
          const offenders = [];
          for (const el of document.querySelectorAll('*')) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.right > vw + 1) {
              offenders.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 44), right: +r.right.toFixed(1) });
            }
          }
          return {
            scrollWidth: document.documentElement.scrollWidth,
            innerWidth: vw,
            offenderCount: offenders.length,
            offenders: offenders.slice(0, 6),
          };
        });
        console.log(`${phase} ${slug} @390 overflow:`, JSON.stringify(overflow));
      }
      await context.close();
      console.log(`shot ${slug} ${name}`);
    }
  }
  console.log(`done: ${phase}`);
} finally {
  await browser.close();
}
