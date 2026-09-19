// B-R05-EXTEND v5 前后对照截图脚本（只写本证据目录，不碰正式数据）
// 用法：node docs/qa/B-R05-EXT5/shoot.mjs before|after
// 前置：5174 上运行本批构建产物（node scripts/run-web.mjs start 5174）
// 种子：阅读工作区走「载入演示数据」按钮路径；space 子页用 localStorage 注入（与 space-pages.spec.ts 同源）。
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const phase = process.argv[2] ?? 'before';
const outDir = path.join(path.dirname(fileURLToPath(import.meta.url)), phase);
const base = 'http://127.0.0.1:5174';

const QUIZ_SEED = [
  { id: 'm-seed:q-1', messageId: 'm-seed', questionId: 'q-1', topic: '分数的大小比较', question: '比较 1/3 与 1/4 的大小。', questionType: '选择题', options: { A: '1/3 更大', B: '1/4 更大' }, correctAnswer: 'A', explanation: '分母越大分数越小。', difficulty: '基础', savedAt: '2026-09-08T01:00:00.000Z', source: 'deep_question', lastAnswer: { answer: 'B', correct: false, at: '2026-09-08T01:01:00.000Z' } },
  { id: 'm-seed:q-2', messageId: 'm-seed', questionId: 'q-2', topic: '修辞', question: '"小草钻出泥土"用了什么修辞？', questionType: '填空题', correctAnswer: '拟人', explanation: '赋予物人的动作。', difficulty: '基础', savedAt: '2026-09-08T02:00:00.000Z', source: 'deep_question' },
];
const PERSONA_SEED = [
  { id: 'demo-persona-patient', name: '耐心的小学老师', description: '生活化举例（演示数据）。', source: 'demo' },
  { id: 'demo-persona-rigorous', name: '严谨的高中老师', description: '强调推理步骤（演示数据）。', source: 'demo' },
  { id: 'demo-persona-socratic', name: '启发式助教', description: '先反问再引导（演示数据）。', source: 'demo' },
];
/** 会话历史：IndexedDB（与 chat-repository 一致），供 /space/chat-history 显示 */
function conversation(id, title, updatedAt) {
  return {
    id, title,
    messages: [
      { id: `${id}-u`, role: 'user', content: `问题-${id}`, status: 'done' },
      { id: `${id}-a`, role: 'assistant', content: `回答-${id}`, status: 'done' },
    ],
    createdAt: updatedAt, updatedAt, schemaVersion: 1, revision: 1,
    draft: '', modelProfileId: null, mode: 'real',
  };
}

async function seed(page) {
  await page.addInitScript(({ quiz, personas }) => {
    window.localStorage.setItem('zhiqikeyuan:quiz-bank', JSON.stringify(quiz));
    window.localStorage.setItem('zqky.replica.personas.v1', JSON.stringify(personas));
  }, { quiz: QUIZ_SEED, personas: PERSONA_SEED });
  await page.addInitScript(({ dbName, convs }) => {
    const request = indexedDB.open(dbName, 1);
    request.onupgradeneeded = (event) => {
      event.target.result.createObjectStore('conversations', { keyPath: 'id' });
    };
    request.onsuccess = () => {
      const db = request.result;
      const tx = db.transaction('conversations', 'readwrite');
      for (const c of convs) tx.objectStore('conversations').put(c);
    };
  }, { dbName: 'zhiqikeyuan-chat', convs: [conversation('seed-real-1', '真实会话一', '2026-09-08T03:00:00.000Z'), conversation('seed-real-2', '真实会话二', '2026-09-08T04:00:00.000Z')] });
}

const VIEWPORTS = [
  ['1440x900', { width: 1440, height: 900 }],
  ['1920x1080', { width: 1920, height: 1080 }],
  ['390x844', { width: 390, height: 844 }],
];

const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
try {
  for (const [name, viewport] of VIEWPORTS) {
    // ===== 组 A：阅读工作区（演示数据） =====
    const ctxA = await browser.newContext({ viewport, reducedMotion: 'reduce' });
    const pageA = await ctxA.newPage();
    await pageA.goto(`${base}/reading`, { waitUntil: 'networkidle' });
    await pageA.getByRole('button', { name: '载入演示数据' }).click();
    await pageA.waitForTimeout(500);
    await pageA.getByRole('link', { name: '打开阅读集合 分数阅读（演示集合）' }).click();
    await pageA.waitForURL(/\/reading\/demo-reading-ws/, { timeout: 15000 });
    await pageA.waitForTimeout(700);
    await pageA.screenshot({ path: path.join(outDir, `reading-workspace-${name}.png`), fullPage: true });
    await pageA.keyboard.press('Tab');
    await pageA.screenshot({ path: path.join(outDir, `reading-workspace-${name}-focus.png`), fullPage: false });
    if (name === '390x844') {
      const overflow = await pageA.evaluate(() => {
        const vw = window.innerWidth;
        const offenders = [];
        for (const el of document.querySelectorAll('*')) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.right > vw + 1) offenders.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 44), right: +r.right.toFixed(1) });
        }
        return { scrollWidth: document.documentElement.scrollWidth, innerWidth: vw, offenderCount: offenders.length, offenders: offenders.slice(0, 6) };
      });
      console.log(`${phase} reading-workspace @390 overflow:`, JSON.stringify(overflow));
    }
    await ctxA.close();
    console.log(`shot reading-workspace ${name}`);

    // ===== 组 B：space 四子页 =====
    for (const [slug, url] of [
      ['space-chat-history', '/space/chat-history'],
      ['space-questions', '/space/questions'],
      ['space-personas', '/space/personas'],
      ['space-cli-apps', '/space/cli-apps'],
    ]) {
      const ctxB = await browser.newContext({ viewport, reducedMotion: 'reduce' });
      const pageB = await ctxB.newPage();
      await seed(pageB);
      await pageB.goto(`${base}${url}`, { waitUntil: 'networkidle' });
      await pageB.waitForTimeout(700);
      await pageB.screenshot({ path: path.join(outDir, `${slug}-${name}.png`), fullPage: true });
      await pageB.keyboard.press('Tab');
      await pageB.screenshot({ path: path.join(outDir, `${slug}-${name}-focus.png`), fullPage: false });
      if (name === '390x844') {
        const overflow = await pageB.evaluate(() => {
          const vw = window.innerWidth;
          const offenders = [];
          for (const el of document.querySelectorAll('*')) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.right > vw + 1) offenders.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 44), right: +r.right.toFixed(1) });
          }
          return { scrollWidth: document.documentElement.scrollWidth, innerWidth: vw, offenderCount: offenders.length, offenders: offenders.slice(0, 6) };
        });
        console.log(`${phase} ${slug} @390 overflow:`, JSON.stringify(overflow));
      }
      await ctxB.close();
      console.log(`shot ${slug} ${name}`);
    }
  }
  console.log(`done: ${phase}`);
} finally {
  await browser.close();
}
