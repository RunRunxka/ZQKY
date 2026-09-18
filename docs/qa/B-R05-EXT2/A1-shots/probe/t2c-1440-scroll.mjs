// T2c: 1440 rail sticky —— 定位正确滚动容器重测
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
const results = [];
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await p.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  await p.goto(base + '/books/demo-book-fractions', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(600);
  const probe = await p.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    // 枚举所有可滚动祖先
    const scrollers = [];
    let node = rail.parentElement;
    while (node && node !== document.documentElement) {
      const cs = getComputedStyle(node);
      if (cs.overflowY === 'auto' || cs.overflowY === 'scroll') {
        scrollers.push({ cls: (typeof node.className === 'string' ? node.className : node.tagName).slice(0, 60), clientH: node.clientHeight, scrollH: node.scrollHeight });
      }
      node = node.parentElement;
    }
    const docScroll = { scrollH: document.documentElement.scrollHeight, clientH: document.documentElement.clientHeight, scEl: document.scrollingElement ? document.scrollingElement.tagName : null };
    return { scrollers, docScroll };
  });
  console.log('1440 scroll ancestry:', JSON.stringify(probe, null, 2));
  results.push(probe);
  // 使用键盘 End 或大量 mouse wheel 触发滚动
  await p.mouse.move(720, 500);
  await p.mouse.wheel(0, 2000);
  await p.waitForTimeout(400);
  const after = await p.evaluate(() => {
    const rail = document.querySelector('.books-rail');
    const content = document.querySelector('.module-workspace-content');
    return { railTop: rail.getBoundingClientRect().top, pos: getComputedStyle(rail).position, contentScrollTop: content ? content.scrollTop : null, winScrollY: window.scrollY };
  });
  console.log('1440 after wheel:', JSON.stringify(after));
  results.push(after);
  await p.screenshot({ path: `${OUT}/t2c-rail-1440-scrolled.png` });
  await c.close();
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t2c-1440-scroll.json`, JSON.stringify(results, null, 2));
}
