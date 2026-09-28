/**
 * 量化流体运动强度：采样两次画布，算平均像素变化与"变化明显"的像素占比。
 * 用法：node /tmp/zqky-motion.cjs <baseUrl> [间隔毫秒]
 */
const { createRequire } = require('node:module');
const req = createRequire('/Users/wang/.workbuddy/binaries/node/workspace/');
const { chromium } = req('playwright');

const BASE = process.argv[2] ?? 'http://127.0.0.1:5174';
const GAP = Number(process.argv[3] ?? 2500);
const EXE =
  '/Users/wang/Library/Caches/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-mac-x64/chrome-headless-shell';

const prep = (scheme) =>
  [
    "localStorage.setItem('zqky.glass','on')",
    `localStorage.setItem('zqky.glass-scheme','${scheme}')`,
    "localStorage.setItem('zqky.glass-bg','ambient')",
    "localStorage.setItem('zqky.glass-fluid','true')",
    "localStorage.setItem('zqky.glass-fluid-hue','0')",
    "localStorage.setItem('zqky.glass-fluid-depth','25')",
  ].join(';') + ';';

const snap = (page) =>
  page.evaluate(() => {
    const canvas = document.querySelector('canvas[data-glass-fluid-canvas]');
    if (!canvas) return null;
    return Array.from(canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data);
  });

(async () => {
  const browser = await chromium.launch({ executablePath: EXE });
  const out = {};
  for (const scheme of ['light', 'dark']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await context.addInitScript(prep(scheme));
    const page = await context.newPage();
    await page.goto(`${BASE}/chat`, { waitUntil: 'load' });
    await page.waitForTimeout(1000);
    const a = await snap(page);
    await page.waitForTimeout(GAP);
    const b = await snap(page);
    if (!a || !b) {
      out[scheme] = { error: 'canvas not found' };
      await context.close();
      continue;
    }
    let sum = 0;
    let n = 0;
    let moved = 0;
    let max = 0;
    for (let i = 0; i < a.length; i += 4) {
      const d =
        (Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2])) / 3;
      sum += d;
      n += 1;
      if (d > 2) moved += 1;
      if (d > max) max = d;
    }
    out[scheme] = {
      gapSeconds: GAP / 1000,
      meanPixelDelta: +(sum / n).toFixed(2),
      movedPixelShare: +(moved / n * 100).toFixed(1),
      maxPixelDelta: +max.toFixed(1),
    };
    await context.close();
  }
  await browser.close();
  console.log(JSON.stringify(out, null, 2));
})();
