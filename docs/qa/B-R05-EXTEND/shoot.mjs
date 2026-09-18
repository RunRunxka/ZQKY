// B-R05-EXTEND v1 前后对照截图脚本（只写本证据目录，不碰正式数据）
// 用法：node docs/qa/B-R05-EXTEND/shoot.mjs before|after
// 前置：5174 上运行本批构建产物（node scripts/run-web.mjs start 5174）
// 种子方式复用 tests/e2e/knowledge-notebooks.spec.ts（隔离上下文，不读真实用户数据）。
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const phase = process.argv[2] ?? 'before';
const outDir = path.join(path.dirname(fileURLToPath(import.meta.url)), phase);
const base = 'http://127.0.0.1:5174';

const KB_SEED = [
  {
    id: 'seed-kb-1',
    name: '课程标准库',
    description: '教学资料与课标摘录的集中登记库（种子数据）。',
    isDefault: true,
    docs: [
      { id: 'seed-doc-1', name: '课程标准摘录一.md', size: 1024, registeredAt: '2026-09-08T01:00:00.000Z', status: 'ready' },
      { id: 'seed-doc-2', name: '课程标准摘录二.md', size: 2048, registeredAt: '2026-09-08T01:05:00.000Z', status: 'parsing', progress: { stage: '解析中', percent: 35 } },
      { id: 'seed-doc-3', name: '这是一个非常长的文档名称用于检验列表在窄视口下的截断与换行行为是否稳定.md', size: 3072, registeredAt: '2026-09-08T01:10:00.000Z', status: 'ready' },
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
  {
    id: 'nb-monthly',
    name: '月度整理',
    description: '月度回顾用',
    color: 'green',
    createdAt: '2026-09-08T01:00:00.000Z',
    updatedAt: '2026-09-08T01:00:00.000Z',
  },
  {
    id: 'nb-long',
    name: '一个很长的笔记本名称用来检验窄视口下侧栏名称截断行为是否正常',
    description: '长名称样本',
    color: 'blue',
    createdAt: '2026-09-08T01:00:00.000Z',
    updatedAt: '2026-09-08T01:00:00.000Z',
  },
];

const RECORDS_SEED = [
  {
    id: 'rec-1',
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

async function seed(page) {
  await page.addInitScript(
    ({ kb, notebooks, records }) => {
      window.localStorage.setItem('zqky.replica.knowledge.v1', JSON.stringify(kb));
      window.localStorage.setItem('zhiqikeyuan:notebooks', JSON.stringify(notebooks));
      window.localStorage.setItem('zhiqikeyuan:notebook-entries', JSON.stringify(records));
    },
    { kb: KB_SEED, notebooks: NOTEBOOKS_SEED, records: RECORDS_SEED },
  );
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
  ['kb-list', '/knowledge-bases'],
  ['kb-detail', `/knowledge-bases/${encodeURIComponent('课程标准库')}`],
  ['notebooks', '/notebooks'],
  ['notebook-detail', '/notebooks/nb-monthly'],
];

const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
try {
  for (const [name, viewport] of VIEWPORTS) {
    for (const [slug, url] of PAGES) {
      const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
      const page = await context.newPage();
      await seed(page);
      await page.goto(`${base}${url}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(outDir, `${slug}-${name}.png`), fullPage: true });
      await page.keyboard.press('Tab');
      await page.screenshot({ path: path.join(outDir, `${slug}-${name}-focus.png`), fullPage: false });
      await context.close();
      console.log(`shot ${slug} ${name}`);
    }
  }
  console.log(`done: ${phase}`);
} finally {
  await browser.close();
}
