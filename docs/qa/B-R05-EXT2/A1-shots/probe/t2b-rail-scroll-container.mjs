// T2b: 找到真实滚动容器，重测 390 static / 1440 sticky 行为
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const results = [];
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
const findScroller = () => {
  const els = [document.scrollingElement, ...document.querySelectorAll('body *')].filter(Boolean);
  for (const el of els) {
    const cs = getComputedStyle(el);
    if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 10) {
      return { tag: el.tagName, cls: (typeof el.className === 'string' ? el.className : el.id || '').slice(0, 60), clientH: el.clientHeight, scrollH: el.scrollHeight };
    }
  }
  return { tag: document.scrollingElement?.tagName, scrollH: document.documentElement.scrollHeight, clientH: document.documentElement.clientHeight };
};
try {
  // 390 详情页
  const c1 = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p1 = await c1.newPage();
  await p1.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p1.getByRole('button', { name: '载入演示数据' }).click();
  await p1.waitForTimeout(400);
  await p1.goto(base + '/books/demo-book-fractions', { waitUntil: 'domcontentloaded' });
  await p1.waitForTimeout(600);
  const scroller390 = await p1.evaluate(findScroller);
  results.push({ test: '390 scroller', scroller390 });
  console.log('390 scroller:', JSON.stringify(scroller390));
  const railFlow = await p1.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    // 滚动真实滚动容器
    let node = document.scrollingElement;
    const els = [document.scrollingElement, ...document.querySelectorAll('body *')].filter(Boolean);
    for (const el of els) {
      const cs = getComputedStyle(el);
      if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 10) { node = el; break; }
    }
    const before = { railTop: rail.getBoundingClientRect().top, scrollTop: node.scrollTop };
    node.scrollTop = 400;
    return new Promise((resolve) => setTimeout(() => {
      const r = document.querySelector('.books-rail');
      resolve({ before, after: { railTop: r.getBoundingClientRect().top, scrollTop: node.scrollTop, pos: getComputedStyle(r).position } });
    }, 250));
  });
  results.push({ test: '390 rail flows with document', railFlow });
  console.log('390 rail flow:', JSON.stringify(railFlow));
  await p1.screenshot({ path: `${OUT}/t2b-rail-390-scrolled.png` });
  await c1.close();

  // 1440 详情页 sticky
  const c2 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p2 = await c2.newPage();
  await p2.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p2.getByRole('button', { name: '载入演示数据' }).click();
  await p2.waitForTimeout(400);
  await p2.goto(base + '/books/demo-book-fractions', { waitUntil: 'domcontentloaded' });
  await p2.waitForTimeout(600);
  const railSticky = await p2.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    const els = [document.scrollingElement, ...document.querySelectorAll('body *')].filter(Boolean);
    let node = document.scrollingElement;
    for (const el of els) {
      const cs = getComputedStyle(el);
      if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 10) { node = el; break; }
    }
    const before = { railTop: rail.getBoundingClientRect().top, scrollTop: node.scrollTop, pos: getComputedStyle(rail).position, top: getComputedStyle(rail).top };
    node.scrollTop = 500;
    return new Promise((resolve) => setTimeout(() => {
      const r = document.querySelector('.books-rail');
      resolve({ before, after: { railTop: r.getBoundingClientRect().top, scrollTop: node.scrollTop, pos: getComputedStyle(r).position } });
    }, 250));
  });
  results.push({ test: '1440 rail sticky', railSticky });
  console.log('1440 rail sticky:', JSON.stringify(railSticky));
  await c2.close();
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t2b-rail-scroll.json`, JSON.stringify(results, null, 2));
}
