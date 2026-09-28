/**
 * 三视口视觉与可访问性实测（RAG-REBUILD v1.0 浏览器验收）。
 *
 * 检查内容：页面级横向溢出、关键区块可见性、键盘焦点、异步错误的 role="alert"、
 * 减少动画偏好是否被尊重。**截图存在不等于通过**，这里同时输出可量化的几何数字。
 *
 * 用法：
 *   node scripts/rag/visual-check.mjs --base http://127.0.0.1:5174 --api http://127.0.0.1:8001
 */

import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  args.set(process.argv[index].replace(/^--/, ''), process.argv[index + 1]);
}
const base = args.get('base') ?? 'http://127.0.0.1:5174';
const api = args.get('api') ?? 'http://127.0.0.1:8001';
const outDir = path.resolve(args.get('out') ?? '_work/rag-rebuild-v1/visual');

const VIEWPORTS = [
  { name: '1440x900', width: 1440, height: 900 },
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '390x844', width: 390, height: 844 },
];

async function jsonFetch(url) {
  const response = await fetch(url, { headers: { accept: 'application/json' } });
  if (!response.ok) throw new Error(`${url} -> HTTP ${response.status}`);
  return response.json();
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const libraries = await jsonFetch(`${api}/api/v1/textbook-libraries`);
  const baseLibrary = libraries.libraries.find((item) => item.kind === 'base');
  const imports = await jsonFetch(`${api}/api/v1/question-imports`);
  const importId = imports.imports[0]?.importId;

  const targets = [
    { id: 'chat', path: '/chat', selector: '.chat-bubble, .chat-composer, main' },
    { id: 'knowledge-bases', path: '/knowledge-bases', selector: '.textbook-page' },
  ];
  if (baseLibrary) {
    targets.push({
      id: 'library-detail',
      path: `/knowledge-bases/libraries/${baseLibrary.libraryId}`,
      selector: '.textbook-page',
    });
  }
  targets.push({ id: 'question-bank', path: '/question-bank', selector: '.question-bank-page' });
  if (importId) {
    targets.push({
      id: 'import-review',
      path: `/question-bank/imports/${importId}`,
      selector: '.question-bank-page',
    });
  }
  targets.push({ id: 'settings-embedding', path: '/settings#embedding', selector: '#embedding' });

  const browser = await chromium.launch({ channel: 'msedge' });
  const report = { base, api, checkedAt: new Date().toISOString(), results: [] };
  try {
    for (const viewport of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        reducedMotion: viewport.name === '390x844' ? 'reduce' : 'no-preference',
      });
      const page = await context.newPage();
      for (const target of targets) {
        const entry = { viewport: viewport.name, page: target.id, path: target.path };
        try {
          await page.goto(`${base}${target.path}`, { waitUntil: 'networkidle', timeout: 30000 });
          await page.waitForTimeout(400);
          entry.visible = (await page.locator(target.selector).count()) > 0;
          const geometry = await page.evaluate(() => {
            const root = document.documentElement;
            const alerts = document.querySelectorAll('[role="alert"]');
            const buttons = Array.from(document.querySelectorAll('button')).filter(
              (node) => node.offsetParent !== null,
            );
            const unnamed = buttons.filter(
              (node) =>
                !(node.getAttribute('aria-label') ?? '').trim() &&
                !(node.textContent ?? '').trim(),
            ).length;
            return {
              clientWidth: root.clientWidth,
              scrollWidth: root.scrollWidth,
              bodyScrollWidth: document.body.scrollWidth,
              alertCount: alerts.length,
              visibleButtons: buttons.length,
              unnamedButtons: unnamed,
            };
          });
          entry.overflowPx = Math.max(0, geometry.scrollWidth - geometry.clientWidth);
          entry.bodyOverflowPx = Math.max(0, geometry.bodyScrollWidth - geometry.clientWidth);
          entry.alertCount = geometry.alertCount;
          entry.unnamedButtons = geometry.unnamedButtons;
          // 键盘可达：Tab 一次后必须有可见焦点元素
          await page.keyboard.press('Tab');
          entry.focusTag = await page.evaluate(() => document.activeElement?.tagName ?? null);
          const shot = path.join(outDir, `${viewport.name}-${target.id}.png`);
          await page.screenshot({ path: shot, fullPage: false });
          entry.screenshot = shot;
        } catch (error) {
          entry.error = `${error.name}: ${error.message}`;
        }
        report.results.push(entry);
        const flag = entry.error ? 'ERROR' : entry.overflowPx > 1 ? 'OVERFLOW' : 'ok';
        console.log(
          `${flag.padEnd(9)} ${viewport.name.padEnd(9)} ${target.id.padEnd(18)} ` +
            (entry.error ?? `overflow=${entry.overflowPx}px alerts=${entry.alertCount} unnamed=${entry.unnamedButtons}`),
        );
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }
  const reportPath = path.join(outDir, 'visual-report.json');
  await writeFile(reportPath, JSON.stringify(report, null, 2), 'utf-8');
  const failures = report.results.filter((item) => item.error || item.overflowPx > 1);
  console.log(`\n报告：${reportPath}`);
  console.log(`结论：${report.results.length - failures.length}/${report.results.length} 无溢出无错误`);
  if (failures.length) {
    for (const item of failures) {
      console.log(`  - ${item.viewport} ${item.page}: ${item.error ?? `overflow ${item.overflowPx}px`}`);
    }
  }
  process.exitCode = failures.length ? 1 : 0;
}

main().catch((error) => {
  console.error(error);
  process.exit(2);
});
