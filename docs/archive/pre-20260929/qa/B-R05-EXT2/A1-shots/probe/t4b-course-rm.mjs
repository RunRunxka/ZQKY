// T4b: 课程详情在 reduce 下的 transition（先载入演示数据再进详情）
import { chromium } from 'playwright';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  const p = await c.newPage();
  await p.goto(base + '/courses', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  await p.goto(base + '/courses/demo-course-math', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(800);
  const courseRM = await p.evaluate(() => {
    const fill = document.querySelector('.courses-progress-fill');
    const row = document.querySelector('.courses-resource');
    const rm = document.querySelector('.courses-resource-remove');
    const unit = document.querySelector('.courses-unit');
    return {
      hasFill: !!fill, hasRow: !!row, hasRm: !!rm, hasUnit: !!unit,
      progressFillTransition: fill ? getComputedStyle(fill).transitionDuration : null,
      resourceRowTransition: row ? getComputedStyle(row).transitionDuration : null,
      removeBtnTransition: rm ? getComputedStyle(rm).transitionDuration : null,
      unitTransition: unit ? getComputedStyle(unit).transitionDuration : null,
    };
  });
  console.log('course reduce:', JSON.stringify(courseRM));
  await p.screenshot({ path: `${OUT}/t4b-course-reduced.png` });
  await c.close();
} finally {
  await browser.close();
}
