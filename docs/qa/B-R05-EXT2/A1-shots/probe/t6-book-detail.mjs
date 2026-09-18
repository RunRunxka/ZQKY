// T6: 书籍详情——提案分支 busy、大纲确认 busy+加载提示、阅读器翻页/书签/侧栏高亮
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const log = [];
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await p.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);

  // --- 提案分支：/books/demo-book-draft ---
  await p.goto(base + '/books/demo-book-draft', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(500);
  const hasProposal = await p.getByText('提案（模拟）').count();
  log.push({ step: 'draft proposal view', hasProposal });
  console.log('draft view proposal:', hasProposal);
  const confirmBtn = p.getByRole('button', { name: '确认提案（进入大纲）' });
  await confirmBtn.click();
  const busy1 = await p.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('.space-card-actions .space-button'));
    const b = btns[btns.length - 1];
    return b ? { disabled: b.disabled, hasSpin: !!b.querySelector('.space-spin'), text: b.textContent.trim() } : null;
  });
  log.push({ step: 'confirm proposal busy', busy1 });
  console.log('proposal busy:', JSON.stringify(busy1));
  await p.screenshot({ path: `${OUT}/t6-proposal-busy.png` });
  await p.waitForTimeout(800);
  const spineShown = await p.getByText(/章节大纲（/).count();
  log.push({ step: 'after proposal -> spine', spineShown, url: p.url() });
  console.log('after proposal url:', p.url(), 'spine:', spineShown);

  // --- spine 确认 busy + 编译加载提示 ---
  const spineBtn = p.getByRole('button', { name: '确认大纲并编译（模拟）' });
  await spineBtn.click();
  const busy2 = await p.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('.space-card-actions .space-button'));
    const b = btns[btns.length - 1];
    const loading = document.querySelector('.books-loading');
    return { disabled: b ? b.disabled : null, hasSpin: b ? !!b.querySelector('.space-spin') : null, loadingText: loading ? loading.textContent.trim() : null };
  });
  log.push({ step: 'spine confirm busy + loading', busy2 });
  console.log('spine busy:', JSON.stringify(busy2));
  await p.screenshot({ path: `${OUT}/t6-spine-busy-loading.png` });
  await p.waitForTimeout(800);
  const notice = await p.getByRole('status').allInnerTexts();
  log.push({ step: 'spine done notice', notice, url: p.url() });
  console.log('spine done:', JSON.stringify(notice), p.url());

  // --- 就绪书阅读器（重新载入演示数据恢复演示书） ---
  await p.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  await p.goto(base + '/books/demo-book-fractions', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(700);
  const url1 = p.url();
  log.push({ step: 'ready book resume url', url1 });
  console.log('resume url:', url1);
  // 侧栏当前页高亮
  const cur = await p.evaluate(() => {
    const a = document.querySelector('nav[aria-label="章节目录"] a[aria-current="page"]');
    return a ? a.getAttribute('href') : null;
  });
  log.push({ step: 'sidebar current', cur });
  console.log('current page:', cur);
  // 翻页（键盘 ArrowRight）
  await p.keyboard.press('ArrowRight');
  await p.waitForTimeout(500);
  const url2 = p.url();
  log.push({ step: 'arrow right page', url2 });
  console.log('after ArrowRight:', url2);
  // 书签添加
  const bookmarkBtn = p.getByRole('button', { name: '添加书签' });
  const bmCount = await bookmarkBtn.count();
  if (bmCount > 0) {
    await bookmarkBtn.click();
    await p.waitForTimeout(400);
    const removed = await p.getByRole('button', { name: '移除书签' }).count();
    const signCount = await p.getByLabel('章节目录').getByText('签').count();
    log.push({ step: 'bookmark toggle', removed, signCount });
    console.log('bookmark:', removed, signCount);
  } else {
    const rb = await p.getByRole('button', { name: '移除书签' }).count();
    log.push({ step: 'bookmark already set', removedBtn: rb });
    console.log('bookmark already:', rb);
    await p.getByRole('button', { name: '移除书签' }).click();
    await p.waitForTimeout(300);
    const addAgain = await p.getByRole('button', { name: '添加书签' }).count();
    log.push({ step: 'bookmark removed', addAgain });
    console.log('bookmark removed, add again:', addAgain);
  }
  await p.screenshot({ path: `${OUT}/t6-reader-page.png` });
  await c.close();
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t6-book-detail.json`, JSON.stringify(log, null, 2));
}
