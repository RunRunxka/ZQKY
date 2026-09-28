/**
 * AGPL-OUT v1 真实浏览器验证：原创流体实现是否真的在画。
 *
 * 关键判据：
 *  1. data-glass-fluid-ok 必须是 'on'（说明没被预检挡掉、也没走 catch 回落）；
 *  2. 画布像素必须有非平凡方差（真的画出了光斑，而不是一片纯色/空白）；
 *  3. 连续两帧像素应发生变化（动了）；减少动画下两帧应完全一致（不动）。
 *
 * 用法：node /tmp/zqky-fluid-check.cjs http://127.0.0.1:5174
 */
const { createRequire } = require('node:module');
const require2 = createRequire('/Users/wang/.workbuddy/binaries/node/workspace/');
const { chromium } = require2('playwright');

const BASE = process.argv[2] ?? 'http://127.0.0.1:5174';
const EXECUTABLE =
  '/Users/wang/Library/Caches/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-mac-x64/chrome-headless-shell';

const PREP = `
  localStorage.setItem('zqky.glass','on');
  localStorage.setItem('zqky.glass-scheme','dark');
  localStorage.setItem('zqky.glass-bg','ambient');
  localStorage.setItem('zqky.glass-fluid','true');
  localStorage.setItem('zqky.glass-fluid-hue','0');
  localStorage.setItem('zqky.glass-fluid-depth','25');
`;

async function sample(page, waitMs) {
  await page.waitForTimeout(waitMs);
  return page.evaluate(() => {
    const canvas = document.querySelector('canvas[data-glass-fluid-canvas]');
    const root = document.documentElement;
    if (!canvas) {
      return { fluidOk: root.dataset.glassFluidOk ?? null, canvas: false };
    }
    const ctx = canvas.getContext('2d');
    const { width, height } = canvas;
    const data = ctx.getImageData(0, 0, width, height).data;
    let sum = 0;
    let sumSq = 0;
    let n = 0;
    const hist = new Set();
    for (let i = 0; i < data.length; i += 4) {
      const lum = 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
      sum += lum;
      sumSq += lum * lum;
      n += 1;
      if (hist.size < 4096) hist.add(`${data[i]},${data[i + 1]},${data[i + 2]}`);
    }
    const mean = sum / n;
    const variance = sumSq / n - mean * mean;
    return {
      fluidOk: root.dataset.glassFluidOk ?? null,
      canvas: true,
      width,
      height,
      meanLum: Number(mean.toFixed(2)),
      stdDev: Number(Math.sqrt(Math.max(0, variance)).toFixed(2)),
      distinctColors: hist.size,
      signature: Array.from(hist).slice(0, 400).join('|'),
      ambientHidden: getComputedStyle(document.body, '::before').display === 'none',
    };
  });
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXECUTABLE });
  const results = {};

  for (const reduced of [false, true]) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await (reduced
      ? context.addInitScript(
          `${PREP} localStorage.setItem('zqky.motion','reduced');`,
        )
      : context.addInitScript(PREP));
    const page = await context.newPage();
    await page.goto(`${BASE}/chat`, { waitUntil: 'load' });
    const a = await sample(page, 900);
    const b = await sample(page, 700);
    results[reduced ? 'reduced' : 'normal'] = {
      first: { ...a, signature: undefined },
      changedBetweenFrames: a.signature !== b.signature,
    };
    await page.screenshot({
      path: `/tmp/zqky-fluid-${reduced ? 'reduced' : 'normal'}.png`,
    });
    await context.close();
  }

  await browser.close();
  console.log(JSON.stringify(results, null, 2));
})();
