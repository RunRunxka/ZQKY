// T2d: 1440 宽、矮视口强制滚动，验证 sticky 吸顶生效（宽度断点 ≥900 不回退）
import { chromium } from 'playwright';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 600 } });
  const p = await c.newPage();
  await p.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  await p.goto(base + '/books/demo-book-fractions', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(600);
  const before = await p.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    const content = document.querySelector('.module-workspace-content');
    return { pos: getComputedStyle(rail).position, top: getComputedStyle(rail).top, railTop: rail.getBoundingClientRect().top, scrollTop: content ? content.scrollTop : -1 };
  });
  await p.mouse.move(720, 400);
  await p.mouse.wheel(0, 1500);
  await p.waitForTimeout(400);
  const after = await p.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    const content = document.querySelector('.module-workspace-content');
    return { pos: getComputedStyle(rail).position, railTop: rail.getBoundingClientRect().top, scrollTop: content ? content.scrollTop : -1 };
  });
  console.log('1440x600 before:', JSON.stringify(before));
  console.log('1440x600 after wheel:', JSON.stringify(after));
  await p.screenshot({ path: `${OUT}/t2d-sticky-1440x600-scrolled.png` });
  await c.close();
} finally {
  await browser.close();
}
