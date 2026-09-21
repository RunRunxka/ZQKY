// T5: 书籍列表交互——搜索过滤/清空恢复、两击删除（确认+取消）、载入幂等、新建 busy
import { chromium } from 'playwright';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
const log = [];
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await p.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  const countAfterLoad1 = await p.locator('.space-persona-card').count();
  // 幂等：再点一次
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  const countAfterLoad2 = await p.locator('.space-persona-card').count();
  log.push({ step: 'demo idempotent', countAfterLoad1, countAfterLoad2 });
  console.log('demo idempotent:', countAfterLoad1, '->', countAfterLoad2);

  // 搜索过滤
  const search = p.getByRole('searchbox', { name: '搜索书籍' });
  await search.fill('分数');
  await p.waitForTimeout(300);
  const filteredCount = await p.locator('.space-persona-card').count();
  const countText = await p.locator('.books-search-count').innerText();
  log.push({ step: 'search filter', filteredCount, countText });
  console.log('search:', filteredCount, countText);
  await p.screenshot({ path: `${OUT}/t5-books-search-filtered.png` });
  await search.fill('');
  await p.waitForTimeout(300);
  const restoredCount = await p.locator('.space-persona-card').count();
  log.push({ step: 'search cleared', restoredCount });
  console.log('cleared:', restoredCount);

  // 两击删除——取消路径
  const firstCard = p.locator('.space-persona-card').first();
  await firstCard.getByRole('button', { name: '删除' }).click();
  await p.waitForTimeout(200);
  const hasConfirm = await firstCard.getByRole('button', { name: '确认删除' }).count();
  const hasCancel = await firstCard.getByRole('button', { name: '取消' }).count();
  log.push({ step: 'delete two-step shown', hasConfirm, hasCancel });
  console.log('two-step:', hasConfirm, hasCancel);
  await p.screenshot({ path: `${OUT}/t5-books-delete-confirm.png` });
  await firstCard.getByRole('button', { name: '取消' }).click();
  await p.waitForTimeout(200);
  const afterCancel = await p.locator('.space-persona-card').count();
  log.push({ step: 'delete cancelled', afterCancel });
  console.log('cancel restore:', afterCancel);

  // 两击删除——确认路径
  const titleBefore = await p.locator('.space-persona-card').first().locator('.space-card-title').innerText();
  await p.locator('.space-persona-card').first().getByRole('button', { name: '删除' }).click();
  await p.waitForTimeout(200);
  await p.locator('.space-persona-card').first().getByRole('button', { name: '确认删除' }).click();
  await p.waitForTimeout(400);
  const afterDelete = await p.locator('.space-persona-card').count();
  const titlesAfter = await p.locator('.space-card-title').allInnerTexts();
  log.push({ step: 'delete confirmed', titleBefore, afterDelete, titlesAfter });
  console.log('deleted:', titleBefore, '->', afterDelete, titlesAfter);
  await p.screenshot({ path: `${OUT}/t5-books-after-delete.png` });

  // 新建书籍 busy 态
  await p.getByRole('button', { name: '新建书籍' }).click();
  await p.waitForTimeout(300);
  await p.locator('.space-form input').first().fill('验收测试书籍');
  await p.locator('.space-form input').nth(1).fill('A1 验收交互测试');
  const submitBtn = p.getByRole('button', { name: /创建（生成模拟提案）/ });
  await submitBtn.click();
  // 立即读按钮状态（350ms 窗口）
  const busy = await p.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('.space-form-footer button'));
    const b = btns[btns.length - 1];
    return { disabled: b.disabled, hasSpin: !!b.querySelector('.space-spin') };
  });
  log.push({ step: 'create busy', busy });
  console.log('create busy:', JSON.stringify(busy));
  await p.screenshot({ path: `${OUT}/t5-books-create-busy.png` });
  await p.waitForTimeout(800);
  log.push({ step: 'create done url', url: p.url() });
  console.log('after create url:', p.url());
  await c.close();
} finally {
  await browser.close();
  require('node:fs').writeFileSync(`${OUT}/t5-books-interact.json`, JSON.stringify(log, null, 2));
}
