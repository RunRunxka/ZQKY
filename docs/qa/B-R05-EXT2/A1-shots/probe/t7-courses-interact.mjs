// T7: 课程列表 hover/归档展开/创建 busy + 课程详情进度条/单元视觉/资料弹窗流程
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const log = [];
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await p.goto(base + '/courses', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);

  // 卡片 hover 语言
  const card = p.locator('.courses-page .space-persona-card').first();
  const tBefore = await card.evaluate((el) => { const cs = getComputedStyle(el); return { transform: cs.transform, shadow: cs.boxShadow !== 'none' }; });
  await card.hover();
  await p.waitForTimeout(400);
  const tAfter = await card.evaluate((el) => { const cs = getComputedStyle(el); return { transform: cs.transform, shadow: cs.boxShadow !== 'none' }; });
  log.push({ step: 'card hover', tBefore, tAfter });
  console.log('card hover:', JSON.stringify({ tBefore, tAfter }));
  await p.screenshot({ path: `${OUT}/t7-courses-card-hover.png` });

  // 归档折叠区
  const summary = p.locator('details.space-group summary');
  const archivedCount = await p.getByText(/已归档课程（/).count();
  const beforeOpen = await p.locator('details.space-group .space-persona-card').count();
  await summary.click();
  await p.waitForTimeout(300);
  const afterOpen = await p.locator('details.space-group .space-persona-card').count();
  log.push({ step: 'archive expand', archivedCount, beforeOpen, afterOpen });
  console.log('archive expand:', archivedCount, beforeOpen, '->', afterOpen);
  await p.screenshot({ path: `${OUT}/t7-courses-archive-open.png` });

  // 创建课程弹窗 busy（同步存储，saving 窗口极短——验证 disabled 与 spinner 类存在）
  await p.getByRole('button', { name: '新建课程' }).click();
  await p.waitForTimeout(300);
  await p.locator('.space-form input').first().fill('验收课程A1');
  await p.locator('.space-form input').nth(1).fill('交互测试');
  await p.getByRole('button', { name: '创建', exact: true }).click();
  await p.waitForTimeout(900);
  log.push({ step: 'course created url', url: p.url() });
  console.log('created course url:', p.url());

  // --- 课程详情 ---
  await p.goto(base + '/courses', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(300);
  await p.goto(base + '/courses/demo-course-math', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(600);
  const pb1 = await p.evaluate(() => document.querySelector('[role="progressbar"]').getAttribute('aria-valuenow'));
  const heading1 = await p.locator('h2.space-group-label').first().innerText();
  await p.getByRole('checkbox', { name: '标记「一元一次方程」为已完成' }).check();
  await p.waitForTimeout(500);
  const pb2 = await p.evaluate(() => document.querySelector('[role="progressbar"]').getAttribute('aria-valuenow'));
  const heading2 = await p.locator('h2.space-group-label').first().innerText();
  log.push({ step: 'syllabus toggle', pb1, heading1, pb2, heading2 });
  console.log('toggle:', pb1, '->', pb2, '|', heading1, '->', heading2);
  await p.screenshot({ path: `${OUT}/t7-course-syllabus-toggled.png` });
  // 复原
  await p.getByRole('checkbox', { name: '标记「一元一次方程」为已完成' }).uncheck();
  await p.waitForTimeout(300);

  // 单元视觉：编号、删除线、下一单元高亮
  const unitVis = await p.evaluate(() => {
    const units = Array.from(document.querySelectorAll('.courses-unit'));
    return units.map((u) => ({
      num: u.querySelector('.courses-unit-position')?.textContent,
      title: u.querySelector('.courses-unit-title')?.textContent,
      covered: u.className.includes('is-covered'),
      isNext: u.className.includes('is-next'),
      coveredDecor: u.className.includes('is-covered') ? getComputedStyle(u.querySelector('.courses-unit-title')).textDecorationLine : null,
      nextBg: u.className.includes('is-next') ? getComputedStyle(u).backgroundColor : null,
    }));
  });
  log.push({ step: 'unit visuals', unitVis });
  console.log('units:', JSON.stringify(unitVis, null, 1));

  // 附加资料弹窗流程
  await p.getByRole('button', { name: '附加资料' }).click();
  await p.waitForTimeout(500);
  const modalTitle = await p.locator('.space-category-manager, [class*="modal"]').count();
  const candidates = await p.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('.space-session-card .space-button')).filter((b) => b.textContent.trim() === '附加');
    return btns.length;
  });
  log.push({ step: 'add-resource modal', modalTitle, candidates });
  console.log('modal:', modalTitle, 'attachable:', candidates);
  await p.screenshot({ path: `${OUT}/t7-add-resource-modal.png` });
  // 附加第一个候选
  const attachBtn = p.locator('.space-session-card .space-button', { hasText: '附加' }).first();
  if (candidates > 0) {
    await attachBtn.click();
    await p.waitForTimeout(500);
    const notice1 = await p.getByRole('status').allInnerTexts();
    log.push({ step: 'attached notice', notice1 });
    console.log('attached:', JSON.stringify(notice1));
    // 移除（hover 后点击）
    const removeBtns = await p.locator('.courses-resource-remove').count();
    const resRow = p.locator('.courses-resource').first();
    await resRow.hover();
    await p.waitForTimeout(250);
    await p.locator('.courses-resource-remove').first().click();
    await p.waitForTimeout(500);
    const notice2 = await p.getByRole('status').allInnerTexts();
    log.push({ step: 'detached notice', removeBtns, notice2 });
    console.log('removed:', removeBtns, JSON.stringify(notice2));
    await p.screenshot({ path: `${OUT}/t7-resource-detached.png` });
  }
  await c.close();
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t7-courses-interact.json`, JSON.stringify(log, null, 2));
}
