// B-R05-EXTEND-A1 v2 聚焦复验脚本（候选 19b514c）
// 用法：node docs/qa/B-R05-EXTEND/A1-shots/a1-v2.mjs
// 前置：5174 运行候选 19b514c 构建产物
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const outDir = path.dirname(fileURLToPath(import.meta.url));
const base = 'http://127.0.0.1:5174';
const results = [];
function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name} :: ${detail}`);
}

const NOTEBOOKS_SEED = [
  { id: 'nb-monthly', name: '月度整理', description: '月度回顾用', color: 'green', createdAt: '2026-09-08T01:00:00.000Z', updatedAt: '2026-09-08T01:00:00.000Z' },
  { id: 'nb-long', name: '一个很长的笔记本名称用来检验窄视口下侧栏名称截断行为是否正常', description: '长名称样本', color: 'blue', createdAt: '2026-09-08T01:00:00.000Z', updatedAt: '2026-09-08T01:00:00.000Z' },
];
const RECORDS_SEED = [
  { id: 'rec-3', notebookId: 'nb-monthly', type: 'co_writer', title: '一条标题很长很长的写作记录用于检验记录行在窄视口下的截断与操作按钮排布是否仍然可用', content: '写作内容', createdAt: '2026-09-08T03:00:00.000Z', updatedAt: '2026-09-08T03:10:00.000Z' },
  { id: 'rec-2', notebookId: 'nb-monthly', type: 'chat', title: '月度对话记录', content: '对话内容', createdAt: '2026-09-08T02:00:00.000Z', updatedAt: '2026-09-08T02:10:00.000Z' },
];

async function seedNotebooks(page) {
  await page.addInitScript(({ nb, rec }) => {
    localStorage.setItem('zhiqikeyuan:notebooks', JSON.stringify(nb));
    localStorage.setItem('zhiqikeyuan:notebook-entries', JSON.stringify(rec));
  }, { nb: NOTEBOOKS_SEED, rec: RECORDS_SEED });
}

async function overflowScan(page) {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const pageOverflow = doc.scrollWidth - doc.clientWidth;
    const vw = doc.clientWidth;
    const offenders = [];
    document.querySelectorAll('body *').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && (r.right > vw + 1 || r.left < -1)) {
        const cls = (typeof el.className === 'string' ? el.className : '').slice(0, 50);
        offenders.push(`${el.tagName}.${cls} right=${Math.round(r.right)}`);
      }
    });
    return { pageOverflow, offenderCount: offenders.length, offenders: offenders.slice(0, 5) };
  });
}

const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
try {
  // ============ 390x844 ============
  {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    await seedNotebooks(page);

    // ---- F1: /notebooks rail ----
    await page.goto(`${base}/notebooks`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    const f1 = await page.evaluate(() => {
      const vw = document.documentElement.clientWidth;
      const item = [...document.querySelectorAll('.space-scope-item')].find((b) => b.textContent.includes('一个很长'));
      const name = item?.querySelector('.space-scope-item-name');
      const count = item?.querySelector('.count');
      const itemR = item?.getBoundingClientRect();
      const countR = count?.getBoundingClientRect();
      const ncs = name ? getComputedStyle(name) : null;
      return {
        itemRight: itemR ? Math.round(itemR.right) : null,
        itemWidth: itemR ? Math.round(itemR.width) : null,
        countVisible: countR ? countR.right <= vw && countR.left >= 0 && countR.width > 0 : null,
        countRight: countR ? Math.round(countR.right) : null,
        nameEllipsis: ncs ? { textOverflow: ncs.textOverflow, whiteSpace: ncs.whiteSpace, overflow: ncs.overflow } : null,
        nameWidth: name ? Math.round(name.getBoundingClientRect().width) : null,
        // actual ellipsis: name's scrollWidth exceeds clientWidth and clientWidth < item
        nameTruncated: name ? name.scrollWidth > name.clientWidth : null,
      };
    });
    log('F1 rail item no overflow', f1.itemRight <= 390, `itemRight=${f1.itemRight} itemWidth=${f1.itemWidth} (vw=390)`);
    log('F1 count badge visible', f1.countVisible === true, `countRight=${f1.countRight}`);
    log('F1 name ellipsis truncation', f1.nameEllipsis.textOverflow === 'ellipsis' && f1.nameTruncated === true, JSON.stringify({ ...f1.nameEllipsis, nameWidth: f1.nameWidth, truncated: f1.nameTruncated }));
    await page.screenshot({ path: path.join(outDir, 'v2-notebooks-390x844.png'), fullPage: true });
    const ov1 = await overflowScan(page);
    log('v2 390 /notebooks overflow scan', ov1.pageOverflow <= 0 && ov1.offenderCount === 0, `pageOverflow=${ov1.pageOverflow} offenderCount=${ov1.offenderCount} ${ov1.offenders.join(' | ')}`);

    // ---- F2: /notebooks/nb-monthly record row ----
    await page.goto(`${base}/notebooks/nb-monthly`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    const f2 = await page.evaluate(() => {
      const row = document.querySelector('.nb-page .space-session-card');
      const top = row?.querySelector('.space-session-top');
      const title = row?.querySelector('.space-session-title');
      const badge = row?.querySelector('.nb-badge');
      const time = row?.querySelector('.nb-row-time');
      const tcs = top ? getComputedStyle(top) : null;
      const titleR = title?.getBoundingClientRect();
      const badgeR = badge?.getBoundingClientRect();
      const timeR = time?.getBoundingClientRect();
      return {
        topWrap: tcs?.flexWrap,
        titleWidth: titleR ? Math.round(titleR.width) : null,
        titleRight: titleR ? Math.round(titleR.right) : null,
        titleVisible: titleR ? titleR.width > 0 : null,
        badgeWidth: badgeR ? Math.round(badgeR.width) : null,
        badgeSingleLine: badgeR ? badgeR.height < 30 : null,
        badgeHeight: badgeR ? Math.round(badgeR.height) : null,
        timeWidth: timeR ? Math.round(timeR.width) : null,
        timeTop: timeR ? Math.round(timeR.top) : null,
        titleTop: titleR ? Math.round(titleR.top) : null,
        timeOnSecondLine: titleR && timeR ? timeR.top >= titleR.bottom - 2 : null,
      };
    });
    log('F2 session-top wraps at 390', f2.topWrap === 'wrap', `flexWrap=${f2.topWrap}`);
    log('F2 title visible (non-zero)', f2.titleVisible === true && f2.titleWidth > 30, `titleWidth=${f2.titleWidth}`);
    log('F2 badge single line', f2.badgeSingleLine === true, `badgeWidth=${f2.badgeWidth} badgeHeight=${f2.badgeHeight}`);
    log('F2 time on second line', f2.timeOnSecondLine === true, `titleTop=${f2.titleTop} timeTop=${f2.timeTop} timeWidth=${f2.timeWidth}`);
    await page.screenshot({ path: path.join(outDir, 'v2-notebook-detail-390x844.png'), fullPage: true });
    const ov2 = await overflowScan(page);
    log('v2 390 /notebooks/nb-monthly overflow scan', ov2.pageOverflow <= 0 && ov2.offenderCount === 0, `pageOverflow=${ov2.pageOverflow} offenderCount=${ov2.offenderCount} ${ov2.offenders.join(' | ')}`);
    await context.close();
  }

  // ============ 1440x900 no-regression ============
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await seedNotebooks(page);

    await page.goto(`${base}/notebooks`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    const w1 = await page.evaluate(() => {
      const item = [...document.querySelectorAll('.space-scope-item')].find((b) => b.textContent.includes('一个很长'));
      const name = item?.querySelector('.space-scope-item-name');
      const desc = item?.querySelector('.space-scope-item-desc');
      return {
        itemWidth: item ? Math.round(item.getBoundingClientRect().width) : null,
        nameEllipsis: name ? name.scrollWidth > name.clientWidth : null,
        descEllipsis: desc ? desc.scrollWidth > desc.clientWidth : null,
      };
    });
    log('1440 /notebooks rail layout kept', w1.itemWidth >= 200 && w1.itemWidth <= 300, `itemWidth=${w1.itemWidth} nameTruncated=${w1.nameEllipsis} descTruncated=${w1.descEllipsis}`);
    await page.screenshot({ path: path.join(outDir, 'v2-notebooks-1440x900.png'), fullPage: true });
    const ovw1 = await overflowScan(page);
    log('v2 1440 /notebooks overflow scan', ovw1.pageOverflow <= 0 && ovw1.offenderCount === 0, `pageOverflow=${ovw1.pageOverflow} offenderCount=${ovw1.offenderCount}`);

    await page.goto(`${base}/notebooks/nb-monthly`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    const w2 = await page.evaluate(() => {
      const row = document.querySelector('.nb-page .space-session-card');
      const top = row?.querySelector('.space-session-top');
      const title = row?.querySelector('.space-session-title');
      const time = row?.querySelector('.nb-row-time');
      const tcs = top ? getComputedStyle(top) : null;
      const titleR = title?.getBoundingClientRect();
      const timeR = time?.getBoundingClientRect();
      return {
        topWrap: tcs?.flexWrap,
        titleWidth: titleR ? Math.round(titleR.width) : null,
        timeTop: timeR ? Math.round(timeR.top) : null,
        titleTop: titleR ? Math.round(titleR.top) : null,
        timeSameLine: titleR && timeR ? Math.abs(timeR.top - titleR.top) < 5 : null,
      };
    });
    log('1440 session-top nowrap (time on header line)', w2.topWrap === 'nowrap' && w2.timeSameLine === true, `flexWrap=${w2.topWrap} titleTop=${w2.titleTop} timeTop=${w2.timeTop} titleWidth=${w2.titleWidth}`);
    await page.screenshot({ path: path.join(outDir, 'v2-notebook-detail-1440x900.png'), fullPage: true });
    const ovw2 = await overflowScan(page);
    log('v2 1440 /notebooks/nb-monthly overflow scan', ovw2.pageOverflow <= 0 && ovw2.offenderCount === 0, `pageOverflow=${ovw2.pageOverflow} offenderCount=${ovw2.offenderCount}`);

    // rail switch + indicator still fine at 1440
    const rail = page.locator('nav[aria-label="笔记本列表"]');
    const itemLong = rail.locator('button.space-scope-item', { hasText: '一个很长' });
    await itemLong.click();
    await page.waitForTimeout(300);
    log('1440 rail switch URL', page.url().includes('nb-long'), page.url());
    const ind = await itemLong.evaluate((el) => {
      const cs = getComputedStyle(el, '::before');
      return { content: cs.content, width: cs.width, bg: cs.backgroundColor };
    });
    log('1440 indicator on current', ind.content !== 'none' && ind.width === '2.5px', JSON.stringify(ind));

    // expand + record buttons still present
    const editBtns = await page.locator('button[aria-label^="编辑记录"]').count();
    const expandBtn = page.locator('button[aria-label^="展开记录"]').first();
    const expBefore = await expandBtn.getAttribute('aria-expanded');
    await expandBtn.click();
    await page.waitForTimeout(250);
    const pop = await page.evaluate(() => { const el = document.querySelector('.nb-pop-in'); return el ? getComputedStyle(el).animationName : null; });
    log('1440 expand + pop-in + action buttons', expBefore === 'false' && pop === 'nb-pop-in' && editBtns >= 1, `expanded ${expBefore}->true, pop-in=${pop}, editBtns=${editBtns}`);
    await context.close();
  }

  // ============ assertion preconditions ============
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await seedNotebooks(page);
    await page.goto(`${base}/notebooks/does-not-exist`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    const appAlerts = await page.evaluate(() => [...document.querySelectorAll('[role="alert"]')].filter((el) => !el.closest('next-route-announcer')).length);
    const strictCount = await page.getByRole('alert').filter({ hasText: '链接指向的笔记本不存在' }).count();
    const backLink = await page.getByRole('link', { name: '返回笔记本列表' }).count();
    log('deep-link app-level alert count=1', appAlerts === 1, `appAlerts=${appAlerts}`);
    log('deep-link spec:531 strict locator=1', strictCount === 1, `strictCount=${strictCount}`);
    log('deep-link back link present', backLink === 1, `count=${backLink}`);

    // 新建笔记本 in rail still locatable
    await page.goto(`${base}/notebooks`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);
    const railNew = page.locator('nav[aria-label="笔记本列表"] button.space-scope-item', { hasText: '新建笔记本' });
    log('rail 新建笔记本 locatable', (await railNew.count()) === 1, `count=${await railNew.count()}`);
    await context.close();
  }

  // ============ KB spot-check at 390 (unchanged module) ============
  {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    await page.addInitScript(() => {
      localStorage.setItem('zqky.replica.knowledge.v1', JSON.stringify([
        { id: 'seed-kb-1', name: '课程标准库', description: '教学资料与课标摘录的集中登记库（种子数据）。', isDefault: true,
          docs: [
            { id: 'seed-doc-1', name: '课程标准摘录一.md', size: 1024, registeredAt: '2026-09-08T01:00:00.000Z', status: 'ready' },
            { id: 'doc-long', name: '这是一个非常长的文档名称用于检验列表在窄视口下的截断与换行行为是否稳定.md', size: 3072, registeredAt: '2026-09-08T01:10:00.000Z', status: 'ready' },
          ],
          sources: [], indexVersions: [] },
        { id: 'seed-kb-2', name: '空种子库', description: '尚未登记任何资料的库。', docs: [], sources: [] },
      ]));
    });
    await page.goto(`${base}/knowledge-bases`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    const ovk1 = await overflowScan(page);
    log('390 /knowledge-bases spot-check overflow', ovk1.pageOverflow <= 0 && ovk1.offenderCount === 0, `pageOverflow=${ovk1.pageOverflow} offenderCount=${ovk1.offenderCount}`);
    await page.goto(`${base}/knowledge-bases/${encodeURIComponent('课程标准库')}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    const ovk2 = await overflowScan(page);
    log('390 /knowledge-bases/[kbName] spot-check overflow', ovk2.pageOverflow <= 0 && ovk2.offenderCount === 0, `pageOverflow=${ovk2.pageOverflow} offenderCount=${ovk2.offenderCount} ${ovk2.offenders.join(' | ')}`);
    await context.close();
  }
} finally {
  await browser.close();
}
const fails = results.filter((r) => !r.ok);
console.log(`\nV2 SUMMARY: ${results.length - fails.length} pass, ${fails.length} fail / ${results.length}`);
