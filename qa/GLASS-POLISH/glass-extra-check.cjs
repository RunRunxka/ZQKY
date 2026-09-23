/**
 * 补充验证：浅色玻璃下 (a) 输入区渐隐遮罩是否命中新规则；(b) 窄视口无横向溢出。
 * 用法：node /tmp/zqky-glass-extra.cjs <baseUrl>
 */
const { createRequire } = require('node:module');
const req = createRequire('/Users/wang/.workbuddy/binaries/node/workspace/');
const { chromium } = req('playwright');

const BASE = process.argv[2] ?? 'http://127.0.0.1:5174';
const EXE =
  '/Users/wang/Library/Caches/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-mac-x64/chrome-headless-shell';

const prep = (scheme) =>
  [
    "localStorage.setItem('zqky.glass','on')",
    `localStorage.setItem('zqky.glass-scheme','${scheme}')`,
    "localStorage.setItem('zqky.glass-bg','ambient')",
    "localStorage.setItem('zqky.glass-fluid','true')",
  ].join(';') + ';';

(async () => {
  const browser = await chromium.launch({ executablePath: EXE });
  const out = {};

  for (const [scheme, width] of [['light', 1440], ['light', 390], ['dark', 390]]) {
    const context = await browser.newContext({ viewport: { width, height: 844 } });
    await context.addInitScript(prep(scheme));
    const page = await context.newPage();
    await page.goto(`${BASE}/chat`, { waitUntil: 'load' });
    await page.waitForTimeout(600);
    const key = `${scheme}-${width}`;
    out[key] = await page.evaluate(() => {
      // 会话态才渲染的渐隐条这里没有实例：临时插入一个同名元素，验证新规则确实命中
      const probe = document.createElement('div');
      probe.className = 'chat-fade-top';
      const host = document.querySelector('.chat-main') ?? document.body;
      host.appendChild(probe);
      const fade = getComputedStyle(probe).backgroundImage;
      probe.remove();
      const composer = document.querySelector('.chat-composer');
      return {
        fadeTopBackground: fade.replace(/rgba?\([^)]*\)/g, (m) => m.replace(/\s+/g, '')),
        composerBackground: composer ? getComputedStyle(composer).backgroundColor : null,
        noHorizontalOverflow:
          document.documentElement.scrollWidth <= window.innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
      };
    });
    await context.close();
  }

  await browser.close();
  console.log(JSON.stringify(out, null, 2));
})();
