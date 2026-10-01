// B-R05-EXTEND v2 前后对照截图脚本（只写本证据目录，不碰正式数据）
// 用法：node docs/qa/B-R05-EXT2/shoot.mjs before|after
// 前置：5174 上运行本批构建产物（node scripts/run-web.mjs start 5174）
// 种子方式复用 tests/e2e/books-courses.spec.ts 的演示数据路径（隔离上下文）。
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const phase = process.argv[2] ?? 'before';
const outDir = path.join(path.dirname(fileURLToPath(import.meta.url)), phase);
const base = 'http://127.0.0.1:5174';

/** 书籍：不注入 localStorage 种子（类型校验严格），改用页面「载入演示数据」按钮（与 e2e 同路径）。
 *  演示书 id：demo-book-fractions（ready，含预置阅读进度）、demo-book-draft（draft，待确认提案）。 */
/** 课程种子：一本进行中（含大纲单元、约定）、一本已归档（字段与 courses-store 类型严格一致） */
const COURSES_SEED = [
  {
    id: 'seed-course-active',
    name: '七年级数学上册',
    description: '覆盖有理数、整式与一元一次方程的教学课程。',
    color: 'blue',
    instructions: '每单元结束后安排一次课堂练习；作业当天批改。',
    status: 'active',
    createdAt: '2026-09-08T01:00:00.000Z',
    updatedAt: '2026-09-08T02:00:00.000Z',
    syllabus: [
      { id: 'u-1', position: 0, title: '第一单元 有理数', topics: ['正负数', '数轴'], covered: true },
      { id: 'u-2', position: 1, title: '第二单元 整式', topics: ['单项式', '多项式'], covered: false },
      { id: 'u-3', position: 2, title: '第三单元 一元一次方程', topics: ['方程概念', '解方程'], covered: false },
    ],
    resources: [],
  },
  {
    id: 'seed-course-archived',
    name: '已结课：八年级物理启蒙',
    description: '已完成并归档的课程。',
    color: 'gray',
    instructions: '',
    status: 'archived',
    createdAt: '2026-09-07T01:00:00.000Z',
    updatedAt: '2026-09-07T02:00:00.000Z',
    syllabus: [{ id: 'u-4', position: 0, title: '第一单元 声现象', topics: ['声音的产生'], covered: true }],
    resources: [],
  },
];

async function seed(page) {
  await page.addInitScript(({ courses }) => {
    window.localStorage.setItem('zhiqikeyuan:courses', JSON.stringify(courses));
  }, { courses: COURSES_SEED });
}

/** 书籍页面：点「载入演示数据」（幂等），再等卡片出现 */
async function loadDemoBooks(page) {
  const button = page.getByRole('button', { name: '载入演示数据' });
  if (await button.count()) {
    await button.click();
    await page.waitForTimeout(400);
  }
}

const VIEWPORTS = [
  ['1440x900', { width: 1440, height: 900 }],
  ['1920x1080', { width: 1920, height: 1080 }],
  ['390x844', { width: 390, height: 844 }],
];

const PAGES = [
  ['books', '/books', true],
  ['book-detail', '/books/demo-book-fractions', true],
  ['courses', '/courses', false],
  ['course-detail', '/courses/seed-course-active', false],
];

const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
try {
  for (const [name, viewport] of VIEWPORTS) {
    for (const [slug, url, isBooks] of PAGES) {
      const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
      const page = await context.newPage();
      await seed(page);
      if (isBooks) {
        // 先到列表页载入演示书籍（幂等），再进入目标地址；否则详情页会显示「不存在」
        await page.goto(`${base}/books`, { waitUntil: 'networkidle' });
        await loadDemoBooks(page);
        if (url !== '/books') await page.goto(`${base}${url}`, { waitUntil: 'networkidle' });
      } else {
        await page.goto(`${base}${url}`, { waitUntil: 'networkidle' });
      }
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(outDir, `${slug}-${name}.png`), fullPage: true });
      await page.keyboard.press('Tab');
      await page.screenshot({ path: path.join(outDir, `${slug}-${name}-focus.png`), fullPage: false });
      // 窄视口溢出量测（供报告引用）
      if (name === '390x844') {
        const overflow = await page.evaluate(() => {
          const vw = window.innerWidth;
          const offenders = [];
          for (const el of document.querySelectorAll('*')) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.right > vw + 1) {
              offenders.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 40), right: +r.right.toFixed(1) });
            }
          }
          return { scrollWidth: document.documentElement.scrollWidth, innerWidth: vw, offenders: offenders.slice(0, 6), offenderCount: offenders.length };
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
