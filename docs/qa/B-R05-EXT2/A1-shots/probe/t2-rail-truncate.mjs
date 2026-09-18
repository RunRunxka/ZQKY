// T2: 窄视口 rail 滚动行为 + 1440 sticky 恢复 + 长文案截断（ellipsis）
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const results = [];
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
try {
  // --- 390: rail static，滚动后 top 随文档移动 ---
  const ctx390 = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p390 = await ctx390.newPage();
  await p390.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p390.getByRole('button', { name: '载入演示数据' }).click();
  await p390.waitForTimeout(400);
  await p390.goto(base + '/books/demo-book-fractions', { waitUntil: 'domcontentloaded' });
  await p390.waitForTimeout(600);
  const before = await p390.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    const cs = getComputedStyle(rail);
    const reader = document.querySelector('.books-reader') || rail.nextElementSibling;
    return { pos: cs.position, maxH: cs.maxHeight, railTop: rail.getBoundingClientRect().top, scrollY: window.scrollY, readerRight: reader ? reader.getBoundingClientRect().right : null, railBottom: rail.getBoundingClientRect().bottom };
  });
  await p390.evaluate(() => window.scrollTo(0, 300));
  await p390.waitForTimeout(200);
  const after = await p390.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    return { railTop: rail.getBoundingClientRect().top, scrollY: window.scrollY, pos: getComputedStyle(rail).position };
  });
  results.push({ test: '390 rail static+flows', before, after });
  console.log('390 before:', JSON.stringify(before));
  console.log('390 after-scroll:', JSON.stringify(after));
  await p390.screenshot({ path: `${OUT}/t2-rail-390-scrolled.png` });

  // 正文不被遮挡：rail 与正文在单列流中上下排列，rail bottom <= reader top
  const noOverlap = await p390.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    const reader = document.querySelector('.books-reader');
    const rb = rail.getBoundingClientRect();
    const rr = reader.getBoundingClientRect();
    return { railBottom: rb.bottom, readerTop: rr.top, railLeft: rb.left, railRight: rb.right, readerLeft: rr.left, readerRight: rr.right };
  });
  results.push({ test: '390 rail/reader geometry', noOverlap });
  console.log('390 geometry:', JSON.stringify(noOverlap));
  await ctx390.close();

  // --- 1440: rail sticky 恢复 + 滚动后 top 保持 ---
  const ctx1440 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p1440 = await ctx1440.newPage();
  await p1440.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p1440.getByRole('button', { name: '载入演示数据' }).click();
  await p1440.waitForTimeout(400);
  await p1440.goto(base + '/books/demo-book-fractions', { waitUntil: 'domcontentloaded' });
  await p1440.waitForTimeout(600);
  const s1 = await p1440.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    return { pos: getComputedStyle(rail).position, top: getComputedStyle(rail).top, railTop: rail.getBoundingClientRect().top, scrollY: window.scrollY };
  });
  await p1440.evaluate(() => window.scrollTo(0, 400));
  await p1440.waitForTimeout(200);
  const s2 = await p1440.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    return { pos: getComputedStyle(rail).position, railTop: rail.getBoundingClientRect().top, scrollY: window.scrollY };
  });
  results.push({ test: '1440 rail sticky', s1, s2 });
  console.log('1440 at-top:', JSON.stringify(s1));
  console.log('1440 after-scroll:', JSON.stringify(s2));

  // --- 长文案截断：课程卡片长名、单元长名、资料长名（用临时种子课程长名） ---
  // 环境准备：直写 courses 种子（含超长名称）——属测试数据准备，与 shoot.mjs 字段一致
  const LONG = '这是一门用于验收长文案截断行为的超长课程名称会超出卡片宽度必须以省略号结尾而不是把布局撑破ABCDEF';
  const UNIT_LONG = '超长单元名称用于验证大纲标题截断省略号行为大纲标题文本格式必须保持正确且不换行撑破卡片XYZ';
  const RES_LONG = '超长资料名称用于验证课程资料行标签截断省略号行为不会把不可用后缀挤出视口之外MNOPQ';
  const seedCourses = [{
    id: 'seed-long', name: LONG, description: '长名课程', color: 'blue', instructions: '', status: 'active',
    createdAt: '2026-09-08T01:00:00.000Z', updatedAt: '2026-09-08T02:00:00.000Z',
    syllabus: [{ id: 'lu-1', position: 0, title: UNIT_LONG, topics: ['主题甲', '主题乙'], covered: false }],
    resources: [{ id: 'lr-1', kind: 'knowledge_base', refId: 'missing-kb', label: RES_LONG }],
  }];
  const ctx2 = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await ctx2.addInitScript((courses) => {
    window.localStorage.setItem('zhiqikeyuan:courses', JSON.stringify(courses));
  }, seedCourses);
  const p2 = await ctx2.newPage();
  await p2.goto(base + '/courses', { waitUntil: 'domcontentloaded' });
  await p2.waitForTimeout(500);
  const cardCheck = await p2.evaluate(() => {
    const name = document.querySelector('.courses-card-name');
    if (!name) return { found: false };
    const cs = getComputedStyle(name);
    const r = name.getBoundingClientRect();
    return { found: true, ellipsis: cs.textOverflow, overflowX: cs.overflowX, whiteSpace: cs.whiteSpace, clientW: name.clientWidth, scrollW: name.scrollWidth, right: Math.round(r.right) };
  });
  await p2.screenshot({ path: `${OUT}/t2-longname-courses-390.png` });
  results.push({ test: '390 course card long name truncate', cardCheck });
  console.log('390 long course name:', JSON.stringify(cardCheck));

  await p2.goto(base + '/courses/seed-long', { waitUntil: 'domcontentloaded' });
  await p2.waitForTimeout(600);
  const detailCheck = await p2.evaluate(() => {
    const unit = document.querySelector('.courses-unit-title');
    const res = document.querySelector('.courses-resource-text');
    const suffix = document.querySelector('.courses-resource-suffix');
    const row = document.querySelector('.courses-resource-row');
    const out = { unit: null, res: null, suffix: null, rowRight: null };
    if (unit) { const cs = getComputedStyle(unit); out.unit = { ellipsis: cs.textOverflow, clientW: unit.clientWidth, scrollW: unit.scrollWidth }; }
    if (res) { const cs = getComputedStyle(res); out.res = { ellipsis: cs.textOverflow, clientW: res.clientWidth, scrollW: res.scrollWidth }; }
    if (suffix) { out.suffix = { right: Math.round(suffix.getBoundingClientRect().right), text: suffix.textContent }; }
    if (row) { out.rowRight = Math.round(row.getBoundingClientRect().right); }
    return out;
  });
  await p2.screenshot({ path: `${OUT}/t2-longname-course-detail-390.png` });
  results.push({ test: '390 course detail long unit/resource truncate', detailCheck });
  console.log('390 long detail:', JSON.stringify(detailCheck));
  await ctx2.close();
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t2-rail-truncate.json`, JSON.stringify(results, null, 2));
}
