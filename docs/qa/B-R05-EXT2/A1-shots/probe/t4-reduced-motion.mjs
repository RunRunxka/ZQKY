// T4: reducedMotion=reduce 下，transition 时长应为 0（全局机制压制）
import { chromium } from 'playwright';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  const p = await c.newPage();
  // 书籍列表卡片 hover transition
  await p.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  const booksRM = await p.evaluate(() => {
    const card = document.querySelector('.books-page .space-persona-card');
    const fill = document.querySelector('.space-reading-bar-fill');
    const arrow = document.querySelector('.books-card-arrow');
    return {
      cardTransition: card ? getComputedStyle(card).transitionDuration : null,
      fillTransition: fill ? getComputedStyle(fill).transitionDuration : null,
      arrowTransition: arrow ? getComputedStyle(arrow).transitionDuration : null,
    };
  });
  console.log('books reduce:', JSON.stringify(booksRM));
  await p.screenshot({ path: `${OUT}/t4-books-reduced.png` });
  // 课程：进度条 + 资料行 + 移除钮
  await p.goto(base + '/courses/demo-course-math', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(600);
  const courseRM = await p.evaluate(() => {
    const fill = document.querySelector('.courses-progress-fill');
    const row = document.querySelector('.courses-resource');
    const rm = document.querySelector('.courses-resource-remove');
    const unit = document.querySelector('.courses-unit');
    return {
      progressFillTransition: fill ? getComputedStyle(fill).transitionDuration : null,
      resourceRowTransition: row ? getComputedStyle(row).transitionDuration : null,
      removeBtnTransition: rm ? getComputedStyle(rm).transitionDuration : null,
      unitTransition: unit ? getComputedStyle(unit).transitionDuration : null,
    };
  });
  console.log('course reduce:', JSON.stringify(courseRM));
  await p.screenshot({ path: `${OUT}/t4-course-reduced.png` });
  await c.close();
} finally {
  await browser.close();
}
