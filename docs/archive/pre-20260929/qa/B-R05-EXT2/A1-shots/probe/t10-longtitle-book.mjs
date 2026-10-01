// T10: 书籍长标题卡片截断抽查（新建长书名）——390 视口
import { chromium } from 'playwright';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
try {
  const c = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p = await c.newPage();
  await p.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  // 640 以下搜索隐藏——390 视口走卡片直查。用 1440 建长名书后回 390 看。
  await p.setViewportSize({ width: 1440, height: 900 });
  await p.getByRole('button', { name: '新建书籍' }).click();
  await p.waitForTimeout(300);
  await p.locator('.space-form input').first().fill('超长书籍标题用于验收卡片标题在窄视口下应当截断显示省略号而不是撑破卡片布局ABCD');
  await p.locator('.space-form input').nth(1).fill('长标题截断抽查');
  await p.getByRole('button', { name: /创建（生成模拟提案）/ }).click();
  await p.waitForTimeout(900);
  await p.setViewportSize({ width: 390, height: 844 });
  await p.goto(base + '/books', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(500);
  const chk = await p.evaluate(() => {
    const vw = window.innerWidth;
    const overflows = [];
    document.querySelectorAll('body *').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.right > vw + 1) overflows.push((typeof el.className === 'string' ? el.className : el.tagName).slice(0, 50));
    });
    const title = Array.from(document.querySelectorAll('.space-card-title')).find((t) => t.textContent.includes('超长书籍标题'));
    const cs = title ? getComputedStyle(title) : null;
    return { overflowCount: overflows.length, sample: overflows.slice(0, 4), titleFound: !!title, titleOverflowX: cs ? cs.overflowX : null, clientW: title ? title.clientWidth : null, scrollW: title ? title.scrollWidth : null };
  });
  console.log('390 long book title:', JSON.stringify(chk));
  await p.screenshot({ path: `${OUT}/t10-longtitle-book-390.png` });
  await c.close();
} finally {
  await browser.close();
}
