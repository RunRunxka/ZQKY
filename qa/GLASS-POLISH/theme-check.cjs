/**
 * 玻璃主题改动的前后对比取样：浅色 / 深色 × 流体背景。
 *
 * 取样内容：
 *  1. 流体画布像素统计（均值 / 标准差 / 色调数）—— 判断"流动"是否变明显；
 *  2. 主区与输入区的 computed background —— 判断背景能否透到右侧聊天区；
 *  3. 两张截图，供人眼判断。
 *
 * 用法：node /tmp/zqky-theme-check.cjs <baseUrl> <输出前缀>
 */
const { createRequire } = require('node:module');
const require2 = createRequire('/Users/wang/.workbuddy/binaries/node/workspace/');
const { chromium } = require2('playwright');

const BASE = process.argv[2] ?? 'http://127.0.0.1:5174';
const PREFIX = process.argv[3] ?? '/tmp/zqky-theme';
const EXECUTABLE =
  '/Users/wang/Library/Caches/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-mac-x64/chrome-headless-shell';

const prep = (scheme) => `
  localStorage.setItem('zqky.glass','on');
  localStorage.setItem('zqky.glass-scheme','${scheme}');
  localStorage.setItem('zqky.glass-bg','ambient');
  localStorage.setItem('zqky.glass-fluid','true');
  localStorage.setItem('zqky.glass-fluid-hue','0');
  localStorage.setItem('zqky.glass-fluid-depth','25');
`;

async function probe(page) {
  return page.evaluate(() => {
    const read = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { background: cs.backgroundColor, backdrop: cs.backdropFilter || cs.webkitBackdropFilter };
    };
    const canvas = document.querySelector('canvas[data-glass-fluid-canvas]');
    let fluid = null;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      const d = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      let sum = 0;
      let sumSq = 0;
      let n = 0;
      let rSum = 0;
      let gSum = 0;
      let bSum = 0;
      const colors = new Set();
      for (let i = 0; i < d.length; i += 4) {
        const lum = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
        sum += lum;
        sumSq += lum * lum;
        rSum += d[i];
        gSum += d[i + 1];
        bSum += d[i + 2];
        n += 1;
        if (colors.size < 8192) colors.add(`${d[i]},${d[i + 1]},${d[i + 2]}`);
      }
      const mean = sum / n;
      fluid = {
        size: `${canvas.width}x${canvas.height}`,
        meanLum: +mean.toFixed(2),
        stdDev: +Math.sqrt(Math.max(0, sumSq / n - mean * mean)).toFixed(2),
        meanRgb: [Math.round(rSum / n), Math.round(gSum / n), Math.round(bSum / n)],
        distinctColors: colors.size,
      };
    }
    return {
      fluidOk: document.documentElement.dataset.glassFluidOk ?? null,
      scheme: document.documentElement.dataset.glassScheme ?? null,
      fluid,
      chatMain: read('.chat-main'),
      composer: read('.chat-composer'),
    };
  });
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXECUTABLE });
  const out = {};
  for (const scheme of ['light', 'dark']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await context.addInitScript(prep(scheme));
    const page = await context.newPage();
    await page.goto(`${BASE}/chat`, { waitUntil: 'load' });
    await page.waitForTimeout(1200);
    out[scheme] = await probe(page);
    await page.screenshot({ path: `${PREFIX}-${scheme}.png` });
    await context.close();
  }
  await browser.close();
  console.log(JSON.stringify(out, null, 2));
})();
