// B-R05-SPACE-VISUAL v1 前后对照截图脚本（只写本证据目录，不碰正式数据）
// 用法：node qa/space-r05-20260918/shoot.mjs before|after
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
const NOTEBOOK_SEED = [
  { id: 'm-seed:report-1', messageId: 'm-seed', title: '种子研究报告', content: '种子内容', savedAt: '2026-09-08T03:00:00.000Z' },
];

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
  await page.addInitScript(({ quiz, personas, notebook }) => {
    window.localStorage.setItem('zhiqikeyuan:quiz-bank', JSON.stringify(quiz));
    window.localStorage.setItem('zqky.replica.personas.v1', JSON.stringify(personas));
    window.localStorage.setItem('zhiqikeyuan:notebook-entries', JSON.stringify(notebook));
  }, { quiz: QUIZ_SEED, personas: PERSONA_SEED, notebook: NOTEBOOK_SEED });
  await page.addInitScript(({ dbName, conversation }) => {
    const request = indexedDB.open(dbName, 1);
    request.onupgradeneeded = (event) => {
      event.target.result.createObjectStore('conversations', { keyPath: 'id' });
    };
    request.onsuccess = () => {
      const db = request.result;
      db.transaction('conversations', 'readwrite').objectStore('conversations').put(conversation);
    };
  }, { dbName: 'zhiqikeyuan-chat', conversation: conversation('seed-real-1', '真实会话一', '2026-09-08T03:00:00.000Z') });
}

const VIEWPORTS = [
  ['1440x900', { width: 1440, height: 900 }],
  ['1920x1080', { width: 1920, height: 1080 }],
  ['390x844', { width: 390, height: 844 }],
];

const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
try {
  for (const [name, viewport] of VIEWPORTS) {
    const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
    const page = await context.newPage();
    await seed(page);
    await page.goto(`${base}/space`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(outDir, `space-${name}.png`), fullPage: true });
    // 键盘焦点图：Tab 后补一张（焦点环可见性核验）
    await page.keyboard.press('Tab');
    await page.screenshot({ path: path.join(outDir, `space-${name}-focus.png`), fullPage: false });
    await context.close();
  }
  console.log(`done: ${phase}`);
} finally {
  await browser.close();
}
