// B-R05-EXTEND v3 前后对照截图脚本（只写本证据目录，不碰正式数据）
// 用法：node docs/qa/B-R05-EXT3/shoot.mjs before|after
// 前置：5174 上运行本批构建产物（node scripts/run-web.mjs start 5174）
// 种子：写作/阅读文档走页面「载入演示数据」/「新建」按钮路径（store 严格校验，直写风险高）。
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const phase = process.argv[2] ?? 'before';
const outDir = path.join(path.dirname(fileURLToPath(import.meta.url)), phase);
const base = 'http://127.0.0.1:5174';

/** 写作：新建一篇文章（含模板），得到可截图的编辑器页
 *  注意：空态下页头与空态各有一个「新建文稿」按钮，用 .first() 避免 strict mode 冲突。 */
async function seedWriting(page) {
  await page.goto(`${base}/co-writer`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: '新建文稿' }).first().click();
  const dialog = page.getByRole('dialog', { name: '新建文稿' });
  await dialog.getByLabel('标题').fill('分数教学文稿（视觉对照样本）');
  await dialog.getByLabel(/教学设计示例模板/).check();
  await dialog.getByRole('button', { name: '创建' }).click();
  await page.waitForURL(/\/co-writer\/doc-/, { timeout: 15000 });
  await page.waitForTimeout(500);
  return page.url();
}

const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
try {
  const VIEWPORTS = [
    ['1440x900', { width: 1440, height: 900 }],
    ['1920x1080', { width: 1920, height: 1080 }],
    ['390x844', { width: 390, height: 844 }],
  ];

  for (const [name, viewport] of VIEWPORTS) {
    // ===== 写作两页（含种子） =====
    const ctx = await browser.newContext({ viewport, reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    const docUrl = await seedWriting(page);

    // 列表页（已有 1 篇文稿）
    await page.goto(`${base}/co-writer`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outDir, `cowriter-list-${name}.png`), fullPage: true });
    await page.keyboard.press('Tab');
    await page.screenshot({ path: path.join(outDir, `cowriter-list-${name}-focus.png`), fullPage: false });

    // 编辑器
    await page.goto(docUrl, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outDir, `cowriter-editor-${name}.png`), fullPage: true });
    await page.keyboard.press('Tab');
    await page.screenshot({ path: path.join(outDir, `cowriter-editor-${name}-focus.png`), fullPage: false });

    // 版本历史弹窗（编辑器内，需要先造一个版本）
    await page.getByRole('button', { name: '保存版本' }).click();
    await page.getByRole('button', { name: '版本历史' }).click();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(outDir, `cowriter-versions-${name}.png`), fullPage: false });

    if (name === '390x844') {
      const overflow = await page.evaluate(() => {
        const vw = window.innerWidth;
        const offenders = [];
        for (const el of document.querySelectorAll('*')) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.right > vw + 1) offenders.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 40), right: +r.right.toFixed(1) });
        }
        return { scrollWidth: document.documentElement.scrollWidth, innerWidth: vw, offenderCount: offenders.length, offenders: offenders.slice(0, 6) };
      });
      console.log(`${phase} cowriter-versions @390 overflow:`, JSON.stringify(overflow));
    }
    await ctx.close();
    console.log(`shot writing ${name}`);

    // ===== 阅读库两页（含演示数据） =====
    const ctx2 = await browser.newContext({ viewport, reducedMotion: 'reduce' });
    const page2 = await ctx2.newPage();
    await page2.goto(`${base}/reading`, { waitUntil: 'networkidle' });
    await page2.getByRole('button', { name: '载入演示数据' }).click();
    await page2.waitForTimeout(500);
    await page2.screenshot({ path: path.join(outDir, `reading-list-${name}.png`), fullPage: true });
    await page2.keyboard.press('Tab');
    await page2.screenshot({ path: path.join(outDir, `reading-list-${name}-focus.png`), fullPage: false });

    await page2.goto(`${base}/reading/materials`, { waitUntil: 'networkidle' });
    await page2.waitForTimeout(500);
    await page2.screenshot({ path: path.join(outDir, `reading-materials-${name}.png`), fullPage: true });
    await page2.keyboard.press('Tab');
    await page2.screenshot({ path: path.join(outDir, `reading-materials-${name}-focus.png`), fullPage: false });

    if (name === '390x844') {
      const overflow = await page2.evaluate(() => {
        const vw = window.innerWidth;
        const offenders = [];
        for (const el of document.querySelectorAll('*')) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.right > vw + 1) offenders.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 40), right: +r.right.toFixed(1) });
        }
        return { scrollWidth: document.documentElement.scrollWidth, innerWidth: vw, offenderCount: offenders.length, offenders: offenders.slice(0, 6) };
      });
      console.log(`${phase} reading-materials @390 overflow:`, JSON.stringify(overflow));
    }
    await ctx2.close();
    console.log(`shot reading ${name}`);
  }
  console.log(`done: ${phase}`);
} finally {
  await browser.close();
}
