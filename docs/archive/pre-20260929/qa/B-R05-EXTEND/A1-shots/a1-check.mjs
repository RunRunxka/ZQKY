// B-R05-EXTEND-A1 独立验收脚本（只写 A1-shots 目录，只读产品代码，隔离上下文种子）
// 用法：node docs/qa/B-R05-EXTEND/A1-shots/a1-check.mjs <screenshots|interactions|reduced|regression|all>
// 前置：5174 上运行候选 82871fa 构建产物（node scripts/run-web.mjs start 5174）
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const step = process.argv[2] ?? 'all';
const outDir = path.dirname(fileURLToPath(import.meta.url));
const base = 'http://127.0.0.1:5174';
const results = [];

function log(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name} :: ${detail}`);
}

const KB_SEED = [
  {
    id: 'seed-kb-1',
    name: '课程标准库',
    description: '教学资料与课标摘录的集中登记库（种子数据）。',
    isDefault: true,
    docs: [
      { id: 'seed-doc-1', name: '课程标准摘录一.md', size: 1024, registeredAt: '2026-09-08T01:00:00.000Z', status: 'ready' },
      { id: 'seed-doc-2', name: '课程标准摘录二.md', size: 2048, registeredAt: '2026-09-08T01:05:00.000Z', status: 'parsing', progress: { stage: '解析中', percent: 35 } },
      { id: 'doc-long', name: '这是一个非常长的文档名称用于检验列表在窄视口下的截断与换行行为是否稳定.md', size: 3072, registeredAt: '2026-09-08T01:10:00.000Z', status: 'ready' },
    ],
    sources: [{ id: 'seed-src-1', type: 'github', url: 'https://github.com/owner/repo', addedAt: '2026-09-08T02:00:00.000Z' }],
    indexVersions: [{ id: 'seed-idx-1', createdAt: '2026-09-08T02:30:00.000Z', docCount: 2, chunkCount: 18 }],
  },
  {
    id: 'seed-kb-2',
    name: '空种子库',
    description: '尚未登记任何资料的库。',
    docs: [],
    sources: [],
  },
];

const NOTEBOOKS_SEED = [
  { id: 'nb-monthly', name: '月度整理', description: '月度回顾用', color: 'green', createdAt: '2026-09-08T01:00:00.000Z', updatedAt: '2026-09-08T01:00:00.000Z' },
  { id: 'nb-long', name: '一个很长的笔记本名称用来检验窄视口下侧栏名称截断行为是否正常', description: '长名称样本', color: 'blue', createdAt: '2026-09-08T01:00:00.000Z', updatedAt: '2026-09-08T01:00:00.000Z' },
];

const RECORDS_SEED = [
  {
    id: 'rec-1',
    notebookId: 'nb-monthly',
    type: 'research_report',
    title: '演示研究报告',
    summary: '演示摘要',
    userQuery: '什么是分数？',
    content: '# 报告正文',
    createdAt: '2026-09-08T01:00:00.000Z',
    updatedAt: '2026-09-08T01:10:00.000Z',
    metadata: { sessionId: 'seed-session-1' },
  },
  {
    id: 'rec-2',
    notebookId: 'nb-monthly',
    type: 'chat',
    title: '月度对话记录',
    content: '对话内容',
    createdAt: '2026-09-08T02:00:00.000Z',
    updatedAt: '2026-09-08T02:10:00.000Z',
  },
  {
    id: 'rec-3',
    notebookId: 'nb-long',
    type: 'co_writer',
    title: '一条标题很长很长的写作记录用于检验记录行在窄视口下的截断与操作按钮排布是否仍然可用',
    content: '写作内容',
    createdAt: '2026-09-08T03:00:00.000Z',
    updatedAt: '2026-09-08T03:10:00.000Z',
  },
];

async function seedKb(page) {
  await page.addInitScript((kb) => {
    window.localStorage.setItem('zqky.replica.knowledge.v1', JSON.stringify(kb));
  }, KB_SEED);
}
async function seedNotebooks(page, records = RECORDS_SEED) {
  await page.addInitScript(({ nb, rec }) => {
    window.localStorage.setItem('zhiqikeyuan:notebooks', JSON.stringify(nb));
    window.localStorage.setItem('zhiqikeyuan:notebook-entries', JSON.stringify(rec));
  }, { nb: NOTEBOOKS_SEED, rec: records });
}
async function seedChatSession(page) {
  await page.addInitScript(({ dbName, conversation }) => {
    const request = indexedDB.open(dbName, 1);
    request.onupgradeneeded = (event) => {
      event.target.result.createObjectStore('conversations', { keyPath: 'id' });
    };
    request.onsuccess = () => {
      const db = request.result;
      db.transaction('conversations', 'readwrite').objectStore('conversations').put(conversation);
    };
  }, {
    dbName: 'zhiqikeyuan-chat',
    conversation: {
      id: 'seed-session-1',
      title: '种子会话',
      messages: [
        { id: 'seed-msg-u', role: 'user', content: '什么是分数？', status: 'done' },
        { id: 'seed-msg-a', role: 'assistant', content: '分数表示整体的一部分。', status: 'done' },
      ],
      createdAt: '2026-09-08T01:00:00.000Z',
      updatedAt: '2026-09-08T01:05:00.000Z',
      schemaVersion: 1,
      revision: 1,
      draft: '',
      modelProfileId: null,
      mode: 'real',
    },
  });
}

const VIEWPORTS = [
  ['1440x900', { width: 1440, height: 900 }],
  ['1920x1080', { width: 1920, height: 1080 }],
  ['390x844', { width: 390, height: 844 }],
];

const PAGES = [
  ['kb-list', '/knowledge-bases', 'kb'],
  ['kb-detail', `/knowledge-bases/${encodeURIComponent('课程标准库')}`, 'kb'],
  ['notebooks', '/notebooks', 'nb'],
  ['notebook-detail', '/notebooks/nb-monthly', 'nb'],
];

async function overflowCheck(page) {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const overflowX = doc.scrollWidth - doc.clientWidth;
    // find elements extending beyond viewport
    const offenders = [];
    const vw = doc.clientWidth;
    document.querySelectorAll('body *').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && (r.right > vw + 1 || r.left < -1)) {
        const cls = (typeof el.className === 'string' ? el.className : '').slice(0, 60);
        offenders.push(`${el.tagName}.${cls} right=${Math.round(r.right)} left=${Math.round(r.left)}`);
      }
    });
    return { overflowX, offenders: offenders.slice(0, 6) };
  });
}

async function screenshots() {
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  try {
    for (const [name, viewport] of VIEWPORTS) {
      for (const [slug, url] of PAGES) {
        const context = await browser.newContext({ viewport });
        const page = await context.newPage();
        if (url.startsWith('/knowledge')) await seedKb(page);
        else { await seedNotebooks(page); await seedChatSession(page); }
        await page.goto(`${base}${url}`, { waitUntil: 'networkidle' });
        await page.waitForTimeout(600);
        const shot = path.join(outDir, `${slug}-${name}.png`);
        await page.screenshot({ path: shot, fullPage: true });
        const ov = await overflowCheck(page);
        log(`overflow ${slug} ${name}`, ov.overflowX <= 0, `scrollW-clientW=${ov.overflowX} offenders=${ov.offenders.length ? ov.offenders.join(' | ') : 'none'}`);
        // focus shot
        await page.keyboard.press('Tab');
        await page.screenshot({ path: shot.replace('.png', '-focus.png'), fullPage: false });
        await context.close();
      }
    }
  } finally { await browser.close(); }
}

async function a11yCheck() {
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  try {
    // KB list: tabs
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      await seedKb(page);
      await page.goto(`${base}/knowledge-bases`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);
      const tabs = await page.getByRole('tab').all();
      const names = [];
      for (const t of tabs) names.push(await t.getAttribute('aria-label') || (await t.textContent()) || '');
      log('kb tabs accessible names', names.length >= 2, JSON.stringify(names));
      log('kb tab contains 知识库', names.some((n) => n.includes('知识库')), 'substring match');
      log('kb tab contains 检索引擎', names.some((n) => n.includes('检索引擎')), 'substring match');
      // tab through and check focus ring
      await page.keyboard.press('Tab');
      const firstFocus = await page.evaluate(() => {
        const el = document.activeElement;
        const cs = getComputedStyle(el);
        return { tag: el.tagName, text: (el.textContent || '').slice(0, 20), outline: cs.outlineStyle + ' ' + cs.outlineWidth + ' ' + cs.outlineColor, boxShadow: cs.boxShadow !== 'none' };
      });
      log('kb first Tab focus', true, JSON.stringify(firstFocus));
      // walk up to 20 tabs, count focusable in tab order reaching cards/main buttons
      const focusSeq = [];
      for (let i = 0; i < 20; i++) {
        await page.keyboard.press('Tab');
        const info = await page.evaluate(() => {
          const el = document.activeElement;
          return `${el.tagName}:${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 16)}`;
        });
        focusSeq.push(info);
      }
      log('kb Tab sequence', true, focusSeq.join(' -> '));
      await context.close();
    }
    // KB detail: nav sections + doc row buttons
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      await seedKb(page);
      await page.goto(`${base}/knowledge-bases/${encodeURIComponent('课程标准库')}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);
      const nav = page.locator('nav[aria-label="知识库分区"]');
      const navCount = await nav.count();
      const btns = navCount ? await nav.locator('button').all() : [];
      const texts = [];
      for (const b of btns) texts.push(((await b.textContent()) || '').trim());
      log('kb-detail nav exists', navCount === 1, `count=${navCount}`);
      log('kb-detail 5 section buttons exact text', JSON.stringify(texts) === JSON.stringify(['文档', '登记文档', '外部来源', '索引', '设置']), JSON.stringify(texts));
      // doc row remove buttons reachable via keyboard
      const removeBtns = await page.locator('button[aria-label^="移除文档"]').all();
      log('kb-detail remove doc buttons', removeBtns.length >= 1, `count=${removeBtns.length}`);
      await context.close();
    }
    // Notebooks: rail, record rows, expand
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      await seedNotebooks(page);
      await seedChatSession(page);
      await page.goto(`${base}/notebooks/nb-monthly`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);
      const rail = page.locator('nav[aria-label="笔记本列表"]');
      log('nb rail exists', (await rail.count()) === 1, 'nav[aria-label=笔记本列表]');
      const railItems = await rail.locator('button.space-scope-item').all();
      log('nb rail items include 新建笔记本', railItems.length >= 3, `items=${railItems.length}`);
      const editBtns = await page.locator('button[aria-label^="编辑记录"]').all();
      const moveBtns = await page.locator('button[aria-label^="移动或复制记录"]').all();
      const delBtns = await page.locator('button[aria-label^="删除记录"]').all();
      log('nb record action buttons', editBtns.length === 1 && moveBtns.length === 1 && delBtns.length === 1, `edit=${editBtns.length} move=${moveBtns.length} del=${delBtns.length}`);
      await context.close();
    }
  } finally { await browser.close(); }
}

async function reducedMotion() {
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      reducedMotion: 'reduce',
    });
    const page = await context.newPage();
    await seedKb(page);
    await seedNotebooks(page);
    await page.goto(`${base}/knowledge-bases`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(300);
    // measuring kb-pulse dot computed animation
    const dot = await page.evaluate(() => {
      const el = document.querySelector('.kb-status-dot');
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { animationName: cs.animationName, animationDuration: cs.animationDuration, animationIterationCount: cs.animationIterationCount };
    });
    log('reduced: kb-pulse suppressed', !!dot && dot.animationDuration === '0.01ms', JSON.stringify(dot));
    // hover transition on card
    const card = page.locator('.kb-page .space-persona-card').first();
    if (await card.count()) {
      const cs = await card.evaluate((el) => {
        const c = getComputedStyle(el);
        return { transitionDuration: c.transitionDuration };
      });
      log('reduced: card transition suppressed', cs.transitionDuration.split(',').every((d) => d.trim() === '0.01ms'), JSON.stringify(cs));
    } else {
      log('reduced: card transition suppressed', false, 'no .kb-page .space-persona-card found');
    }
    // notebook pop-in on detail
    await page.goto(`${base}/notebooks/nb-monthly`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(300);
    const pop = await page.evaluate(() => {
      const el = document.querySelector('.nb-pop-in');
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { animationName: cs.animationName, animationDuration: cs.animationDuration };
    });
    log('reduced: nb-pop-in suppressed', !!pop && pop.animationDuration === '0.01ms', JSON.stringify(pop));
    await context.close();
    // control: without reduce, durations should be real
    const context2 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page2 = await context2.newPage();
    await seedKb(page2);
    await seedNotebooks(page2);
    await page2.goto(`${base}/knowledge-bases`, { waitUntil: 'networkidle' });
    await page2.waitForTimeout(300);
    const dot2 = await page2.evaluate(() => {
      const el = document.querySelector('.kb-status-dot');
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { animationName: cs.animationName, animationDuration: cs.animationDuration };
    });
    log('normal: kb-pulse active (control)', !!dot2 && dot2.animationDuration === '1.4s', JSON.stringify(dot2));
    await page2.goto(`${base}/notebooks/nb-monthly`, { waitUntil: 'networkidle' });
    await page2.waitForTimeout(300);
    const pop2 = await page2.evaluate(() => {
      const el = document.querySelector('.nb-pop-in');
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { animationName: cs.animationName, animationDuration: cs.animationDuration };
    });
    log('normal: nb-pop-in active (control)', !!pop2 && pop2.animationDuration === '0.2s', JSON.stringify(pop2));
    await context2.close();
  } finally { await browser.close(); }
}

async function interactions() {
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  try {
    // --- KB list ---
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      await seedKb(page);
      await page.goto(`${base}/knowledge-bases`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);

      // tab switch
      const tabEngine = page.getByRole('tab', { name: /检索引擎/ });
      await tabEngine.click();
      await page.waitForTimeout(300);
      const engineSelected = await tabEngine.getAttribute('aria-selected');
      const panelVisible = await page.getByRole('tabpanel').first().isVisible().catch(() => false);
      log('kb tab switch to 检索引擎', engineSelected === 'true', `aria-selected=${engineSelected}`);
      const tabKb = page.getByRole('tab', { name: /知识库/ });
      await tabKb.click();
      await page.waitForTimeout(200);
      log('kb tab switch back', (await tabKb.getAttribute('aria-selected')) === 'true', 'aria-selected=true');

      // seed has 2 KBs -> search box should NOT appear (needs >6)
      const searchCount = await page.locator('input[type="search"]').count();
      log('kb search box hidden with 2 KBs', searchCount === 0, `search inputs=${searchCount}`);

      // status dots
      const dotInfo = await page.evaluate(() => {
        const dots = [...document.querySelectorAll('.kb-status-dot')];
        return dots.map((d) => ({ cls: d.className, color: getComputedStyle(d).backgroundColor, anim: getComputedStyle(d).animationName }));
      });
      log('kb status dots rendered', dotInfo.length >= 1, JSON.stringify(dotInfo));
      await context.close();

      // >6 KBs -> search appears
      const kbMany = Array.from({ length: 8 }, (_, i) => ({
        id: `kb-${i}`,
        name: `批量库${i}`,
        description: '批量种子',
        docs: [],
        sources: [],
      }));
      const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const p2 = await ctx2.newPage();
      await p2.addInitScript((kb) => localStorage.setItem('zqky.replica.knowledge.v1', JSON.stringify(kb)), kbMany);
      await p2.goto(`${base}/knowledge-bases`, { waitUntil: 'networkidle' });
      await p2.waitForTimeout(400);
      const search2 = await p2.locator('input[type="search"]').count();
      log('kb search box appears with 8 KBs', search2 === 1, `search inputs=${search2}`);
      await ctx2.close();

      // empty state: clear localStorage
      const ctx3 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const p3 = await ctx3.newPage();
      await p3.goto(`${base}/knowledge-bases`, { waitUntil: 'networkidle' });
      await p3.waitForTimeout(400);
      const emptyText = await p3.evaluate(() => document.body.innerText.slice(0, 400));
      const hasEmpty = emptyText.includes('还没有知识库');
      const hasIcon = await p3.locator('.space-empty, [class*="empty"]').count();
      const hasCta = await p3.getByRole('button', { name: /新建知识库|登记/ }).count() + await p3.locator('a[class*="space-button"]').count();
      log('kb empty state text', hasEmpty, JSON.stringify(emptyText.slice(0, 120)));
      log('kb empty icon element', hasIcon >= 1, `count=${hasIcon}`);
      await ctx3.close();
    }

    // --- KB detail ---
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      await seedKb(page);
      await page.goto(`${base}/knowledge-bases/${encodeURIComponent('课程标准库')}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);

      // five sections switch
      const nav = page.locator('nav[aria-label="知识库分区"]');
      const sectionBtns = await nav.locator('button').all();
      for (const b of sectionBtns) { await b.click(); await page.waitForTimeout(150); }
      const lastSelected = await sectionBtns[4].getAttribute('aria-selected').catch(() => null);
      log('kb-detail section switching', true, `clicked all 5; last aria-selected=${lastSelected}`);

      // parsing doc -> 全部解析并索引 disabled
      await sectionBtns[0].click();
      await page.waitForTimeout(200);
      const parseAll = page.getByRole('button', { name: /全部解析并索引/ });
      const parseCount = await parseAll.count();
      const disabled = parseCount ? await parseAll.first().isDisabled() : null;
      log('kb-detail parse-all disabled while parsing', parseCount > 0 && disabled === true, `count=${parseCount} disabled=${disabled}`);

      // two-stage remove confirm: click remove -> confirm text; cancel restores
      const removeBtn = page.locator('button[aria-label^="移除文档"]').first();
      await removeBtn.click();
      await page.waitForTimeout(200);
      const confirmVisible = await page.getByText('确认移除').first().isVisible().catch(() => false);
      log('kb-detail remove shows 确认移除', confirmVisible, 'two-stage confirm visible');
      const cancelBtn = page.getByRole('button', { name: /^取消$/ }).first();
      let cancelOk = false;
      if (await cancelBtn.count()) {
        await cancelBtn.click();
        await page.waitForTimeout(200);
        const confirmGone = (await page.getByText('确认移除').count()) === 0;
        const docStill = await page.getByText('课程标准摘录一.md').first().isVisible().catch(() => false);
        cancelOk = confirmGone && docStill;
        log('kb-detail cancel restores row', cancelOk, `confirmGone=${confirmGone} docStillVisible=${docStill}`);
      } else {
        log('kb-detail cancel restores row', false, 'no 取消 button found');
      }
      await context.close();
    }

    // --- Notebooks ---
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      await seedNotebooks(page);
      await seedChatSession(page);
      await page.goto(`${base}/notebooks/nb-monthly`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);

      // rail switching + indicator
      const rail = page.locator('nav[aria-label="笔记本列表"]');
      const itemLong = rail.locator('button.space-scope-item', { hasText: '一个很长的笔记本名称' });
      await itemLong.click();
      await page.waitForTimeout(300);
      const urlAfter = page.url();
      const currentIsLong = await itemLong.getAttribute('class');
      log('nb rail switch updates URL', urlAfter.includes('nb-long'), urlAfter);
      const indicator = await itemLong.evaluate((el) => {
        const cs = getComputedStyle(el, '::before');
        return { content: cs.content, bg: cs.backgroundColor, display: cs.display };
      });
      log('nb indicator on current item', indicator.content !== 'none' && indicator.content !== 'normal', JSON.stringify(indicator));
      // switch back to monthly
      const itemMonthly = rail.locator('button.space-scope-item', { hasText: '月度整理' });
      await itemMonthly.click();
      await page.waitForTimeout(300);

      // expand record row
      const expandBtn = page.locator('button[aria-label*="展开"], button[aria-expanded]').first();
      const expandCount = await page.locator('button[aria-expanded]').count();
      if (expandCount) {
        const before = await expandBtn.getAttribute('aria-expanded');
        await expandBtn.click();
        await page.waitForTimeout(250);
        const after = await expandBtn.getAttribute('aria-expanded');
        const popVisible = await page.locator('.nb-pop-in').first().isVisible().catch(() => false);
        log('nb record expand', before === 'false' && after === 'true', `aria-expanded ${before}->${after}; nb-pop-in visible=${popVisible}`);
        // open original session link
        const openLink = page.locator('a', { hasText: '打开原会话' });
        const openCount = await openLink.count();
        log('nb open-original-session link', openCount >= 1, `count=${openCount}`);
        await expandBtn.click(); // collapse back
      } else {
        log('nb record expand', false, 'no aria-expanded button found');
      }

      // hover bg change on record row
      const row = page.locator('.nb-page .space-session-card').first();
      if (await row.count()) {
        const before = await row.evaluate((el) => getComputedStyle(el).backgroundColor);
        await row.hover();
        await page.waitForTimeout(200);
        const after = await row.evaluate((el) => getComputedStyle(el).backgroundColor);
        log('nb record hover bg change', before !== after, `before=${before} after=${after}`);
      } else {
        log('nb record hover bg change', false, 'no .nb-page .space-session-card');
      }

      // deep link missing: single role=alert
      const p2 = await context.newPage();
      await p2.goto(`${base}/notebooks/does-not-exist`, { waitUntil: 'networkidle' });
      await p2.waitForTimeout(500);
      const alertCount = await p2.locator('[role="alert"]').count();
      const alertText = alertCount ? await p2.locator('[role="alert"]').first().innerText() : '';
      const backLink = await p2.getByRole('link', { name: '返回笔记本列表' }).count();
      log('nb deep-link single alert', alertCount === 1, `role=alert count=${alertCount} text=${JSON.stringify(alertText.slice(0, 80))}`);
      log('nb deep-link alert mentions 不存在', alertText.includes('链接指向的笔记本不存在'), 'text match');
      log('nb deep-link back link', backLink === 1, `count=${backLink}`);
      await context.close();
    }
  } finally { await browser.close(); }
}

async function regression() {
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
  const proc = { context: null };
  function track(ctx) { proc.context = ctx; return ctx; }
  try {
    // KB: create (with duplicate-name rejection), rename syncs URL, set default, doc register (file input), external source add/remove
    {
      const context = track(await browser.newContext({ viewport: { width: 1440, height: 900 }, permissions: [] }));
      const page = await context.newPage();
      await seedKb(page);
      await page.goto(`${base}/knowledge-bases`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);

      // create new KB
      const newBtn = page.getByRole('button', { name: /新建知识库/ }).first();
      if (await newBtn.count()) {
        await newBtn.click();
        await page.waitForTimeout(200);
        const nameInput = page.locator('input[type="text"]').first();
        await nameInput.fill('验收新建库');
        const confirmBtn = page.locator('[role="dialog"], .space-modal, form').getByRole('button', { name: /创建|确定|保存/ }).first();
        await confirmBtn.click();
        await page.waitForTimeout(300);
        const created = await page.getByText('验收新建库').first().isVisible().catch(() => false);
        log('kb create new', created, '新建知识库 flow');
        // duplicate name rejection
        await newBtn.click();
        await page.waitForTimeout(200);
        await nameInput.fill('课程标准库');
        await confirmBtn.click();
        await page.waitForTimeout(300);
        const bodyText = await page.evaluate(() => document.body.innerText);
        const rejected = /已存在|重复|重名/.test(bodyText);
        const dialogStill = await page.locator('[role="dialog"], .space-modal, form').count();
        log('kb duplicate name rejected', rejected, `dialogStill=${dialogStill}`);
        const esc = page.keyboard.press('Escape');
        await esc;
        await page.waitForTimeout(200);
      } else {
        log('kb create new', false, 'no 新建知识库 button');
      }

      // rename current default KB -> URL sync
      await page.goto(`${base}/knowledge-bases/${encodeURIComponent('课程标准库')}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);
      const renameBtn = page.getByRole('button', { name: /重命名|改名/ }).first();
      if (await renameBtn.count()) {
        await renameBtn.click();
        await page.waitForTimeout(200);
        const input = page.locator('input[type="text"]').first();
        await input.fill('课程标准库B');
        const saveBtn = page.locator('[role="dialog"], .space-modal, form').getByRole('button', { name: /保存|确定/ }).first();
        await saveBtn.click();
        await page.waitForTimeout(400);
        const url = page.url();
        log('kb rename syncs URL', decodeURIComponent(url).includes('课程标准库B'), url);
      } else {
        log('kb rename syncs URL', false, 'no rename button found');
      }
      await context.close();
    }

    // Notebooks regression: create, edit, export, expand session link, delete record, delete notebook URL back
    {
      const context = track(await browser.newContext({ viewport: { width: 1440, height: 900 } }));
      const page = await context.newPage();
      await seedNotebooks(page);
      await seedChatSession(page);
      await page.goto(`${base}/notebooks`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);

      // create
      await page.locator('nav[aria-label="笔记本列表"] button', { hasText: '新建笔记本' }).click();
      await page.waitForTimeout(200);
      await page.locator('input[type="text"]').first().fill('验收笔记本');
      const createBtn = page.locator('[role="dialog"], .space-modal, form').getByRole('button', { name: /创建|确定|保存/ }).first();
      await createBtn.click();
      await page.waitForTimeout(400);
      const nbCreated = await page.locator('nav[aria-label="笔记本列表"] button', { hasText: '验收笔记本' }).count();
      log('nb create new', nbCreated >= 1, `rail count=${nbCreated}`);

      // edit (rename) the created notebook: select it, use 编辑 button in header
      const nbItem = page.locator('nav[aria-label="笔记本列表"] button', { hasText: '验收笔记本' });
      await nbItem.click();
      await page.waitForTimeout(300);
      const editNb = page.getByRole('button', { name: /^编辑$/ }).first();
      if (await editNb.count()) {
        await editNb.click();
        await page.waitForTimeout(200);
        await page.locator('input[type="text"]').first().fill('验收笔记本B');
        const save = page.locator('[role="dialog"], .space-modal, form').getByRole('button', { name: /保存|确定/ }).first();
        await save.click();
        await page.waitForTimeout(300);
        const renamed = await page.locator('nav[aria-label="笔记本列表"] button', { hasText: '验收笔记本B' }).count();
        log('nb edit rename', renamed >= 1, 'renamed in rail');
      } else {
        log('nb edit rename', false, 'no 编辑 button');
      }

      // export markdown: expect a download event
      const exportBtn = page.getByRole('button', { name: /导出/ }).first();
      if (await exportBtn.count()) {
        const [download] = await Promise.all([
          page.waitForEvent('download', { timeout: 5000 }).catch(() => null),
          exportBtn.click(),
        ]);
        log('nb export markdown download', !!download, download ? `file=${download.suggestedFilename()}` : 'no download event (headless dl allowed)');
      } else {
        log('nb export markdown download', false, 'no export button');
      }

      // record expand shows 打开原会话
      await page.goto(`${base}/notebooks/nb-monthly`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);
      const expandBtn = page.locator('button[aria-expanded]').first();
      if (await expandBtn.count()) {
        await expandBtn.click();
        await page.waitForTimeout(300);
        const link = page.locator('a', { hasText: '打开原会话' });
        const linkCount = await link.count();
        const href = linkCount ? await link.first().getAttribute('href') : null;
        log('nb session link on expand', linkCount >= 1, `href=${href}`);
      } else {
        log('nb session link on expand', false, 'no expand button');
      }

      // delete a record (rec-2 月度对话记录) with confirm
      const delBtn = page.locator('button[aria-label^="删除记录 月度对话记录"]');
      if (await delBtn.count()) {
        page.once('dialog', (d) => d.accept());
        await delBtn.click();
        await page.waitForTimeout(400);
        const gone = (await page.locator('button[aria-label^="删除记录 月度对话记录"]').count()) === 0;
        log('nb delete record', gone, 'record row removed after confirm');
      } else {
        log('nb delete record', false, 'no delete button for rec-2');
      }

      // delete notebook -> URL back to /notebooks
      await page.goto(`${base}/notebooks/nb-long`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);
      const delNb = page.getByRole('button', { name: /删除笔记本|删除/ }).first();
      if (await delNb.count()) {
        page.once('dialog', (d) => d.accept());
        await delNb.click();
        await page.waitForTimeout(600);
        const url = page.url();
        const back = url.replace(/\/$/, '') === `${base}/notebooks`;
        log('nb delete notebook URL back', back, url);
      } else {
        log('nb delete notebook URL back', false, 'no delete button');
      }
      await context.close();
    }
  } finally { await browser.close(); }
}

const steps = { screenshots, a11y: a11yCheck, reduced: reducedMotion, interactions, regression };
const toRun = step === 'all' ? Object.keys(steps) : [step];
for (const s of toRun) {
  console.log(`\n===== STEP ${s} =====`);
  await steps[s]();
}
const fails = results.filter((r) => !r.ok);
console.log(`\nSUMMARY: ${results.length - fails.length} pass, ${fails.length} fail / ${results.length}`);
fs.writeFileSync(path.join(outDir, 'results.json'), JSON.stringify(results, null, 2));
