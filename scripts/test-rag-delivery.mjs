/**
 * RAG-BROWSER-v1: real local end-to-end browser acceptance, no mocked API/model.
 * Run from the host repository after starting web :5174 and API :8001:
 *   node scripts/test-rag-delivery.mjs
 * Uses a new non-persistent browser context. Existing browsers/data are untouched.
 * Fixed budget: 2 initial questions + 1 non-empty follow-up; refresh/skip/cancel
 * must not create new inference jobs. No automated retries of failed questions.
 */
import { chromium } from '@playwright/test';
import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const webUrl = process.env.ZQKY_RAG_WEB_URL ?? 'http://127.0.0.1:5174';
const parsedUrl = new URL(webUrl);
if (!['127.0.0.1', 'localhost', '[::1]'].includes(parsedUrl.hostname) || parsedUrl.port !== '5174') {
  throw new Error('This acceptance script only permits an isolated loopback web server on port 5174.');
}
const runId = new Date().toISOString().replace(/[:.]/g, '-');
const evidenceDir = path.join(repoRoot, '_work', 'rag-delivery', runId);
await mkdir(evidenceDir, { recursive: true });
const fixtures = {
  math: { id: 'NEW-MATH', question: '用列举法表示集合 A={x|x²-3x+2=0}，说明列举法是什么。' },
  ooc: { id: 'OOC-1', question: '快速排序算法的平均时间复杂度是多少？' },
  supplement: '请只给出教材关于列举法的定义与原文，不需要解方程。',
};
const sha = (value) => createHash('sha256').update(value).digest('hex');
const report = {
  task: 'RAG-BROWSER-v1', startedAt: new Date().toISOString(), webUrl,
  claim: '真实本地教材服务工程验收；不是人工教学质量验收，也不认证自由解题推导。',
  expectedAnswerMode: 'textbook_excerpt', humanQuality: 'not_run',
  budget: { maxInitialQuestions: 2, maxNonemptyReplies: 1, maxLocateJobs: 3, cloudRequestsAllowed: 0 },
  fixtures: { ...fixtures, mathSha256: sha(fixtures.math.question), oocSha256: sha(fixtures.ooc.question) },
  checks: [], screenshots: [], cases: {}, console: [], pageErrors: [], requests: [], responses: [], requestFailures: [], externalRequestsBlocked: [],
};
// details 只允许追加证据字段；name/status 固定写在最后，避免 details 里的同名键
// 把 PASS/FAIL 悄悄覆盖成别的值（2026-09-26 实测：{status: ...} 曾让一项检查既不
// 计入 PASS 也不计入 FAIL，摘要因此少报一项——真实结果不得被吞掉）。
const check = (name, pass, details = {}) => {
  const item = { ...details, name, status: pass ? 'PASS' : 'FAIL' };
  report.checks.push(item);
  console.log(`${item.status} ${name}`);
  return pass;
};
const save = async (name, value) => writeFile(path.join(evidenceDir, name), JSON.stringify(value, null, 2), 'utf8');
// 宿主既有浏览器自动化用系统 Edge（playwright.config.ts 同款），不下载额外浏览器。
const browser = await chromium.launch({
  channel: process.env.PLAYWRIGHT_CHANNEL ?? (process.platform === 'win32' ? 'msedge' : undefined),
  headless: true,
});
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce', locale: 'zh-CN' });
const page = await context.newPage();
page.setDefaultTimeout(15000);
page.setDefaultNavigationTimeout(45000);
const ownTurns = new Map();
let completed = false;

// This is a network boundary, never a mock/fulfil handler: all loopback traffic
// goes to the actual servers. Unexpected non-local requests are denied/reported.
await context.route('**/*', (route) => {
  const url = new URL(route.request().url());
  if (['http:', 'https:'].includes(url.protocol) && !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) {
    report.externalRequestsBlocked.push({ origin: url.origin, path: url.pathname });
    return route.abort('blockedbyclient');
  }
  return route.continue();
});
page.on('console', (message) => report.console.push({ type: message.type(), text: message.text(), location: message.location(), time: new Date().toISOString() }));
page.on('pageerror', (error) => report.pageErrors.push({ message: error.message, stack: error.stack }));
page.on('request', (request) => {
  const url = new URL(request.url());
  if (!url.pathname.startsWith('/api/v1/')) return;
  const item = { path: url.pathname, method: request.method(), time: new Date().toISOString() };
  // Only these fixed test fixtures are recorded. Never record headers or model
  // catalog/profile bodies, which are unrelated to this acceptance task.
  if (url.pathname.startsWith('/api/v1/rag/') && request.method() === 'POST') {
    try { item.body = request.postDataJSON(); } catch { item.bodyParseFailed = true; }
    if (url.pathname.endsWith('/stream') && item.body?.sessionId && item.body?.turnId) {
      ownTurns.set(item.body.turnId, { sessionId: item.body.sessionId, turnId: item.body.turnId });
    }
  }
  report.requests.push(item);
});
page.on('response', (response) => {
  const url = new URL(response.url());
  if (url.pathname.startsWith('/api/v1/')) report.responses.push({ path: url.pathname, status: response.status(), time: new Date().toISOString() });
});
page.on('requestfailed', (request) => {
  const url = new URL(request.url());
  report.requestFailures.push({ path: url.pathname, method: request.method(), error: request.failure()?.errorText, time: new Date().toISOString() });
});

function streamRequests() { return report.requests.filter((r) => r.path === '/api/v1/rag/stream'); }
function activeCard() { return page.locator('.chat-ask-card.active').last(); }
function assistant(doc) { return doc?.messages?.filter((m) => m.role === 'assistant').at(-1); }
async function poll(read, predicate, label, timeout = 240000) {
  const deadline = Date.now() + timeout;
  let last;
  while (Date.now() < deadline) {
    last = await read();
    if (predicate(last)) return last;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`Timed out: ${label}; last=${JSON.stringify(last).slice(0, 500)}`);
}
async function readConversation(sessionId) {
  // Read only, and only inside this script's fresh browser context. Opening an
  // absent database aborts rather than creating/migrating any persistent schema.
  return page.evaluate((id) => new Promise((resolve, reject) => {
    const opening = indexedDB.open('zhiqikeyuan-chat');
    opening.onupgradeneeded = () => { opening.transaction?.abort(); };
    opening.onerror = () => reject(opening.error);
    opening.onsuccess = () => {
      const db = opening.result;
      if (!db.objectStoreNames.contains('conversations')) { db.close(); reject(new Error('Missing conversations store')); return; }
      const tx = db.transaction('conversations', 'readonly');
      const request = tx.objectStore('conversations').get(id);
      tx.oncomplete = () => { const value = request.result ?? null; db.close(); resolve(value); };
      tx.onerror = () => { db.close(); reject(tx.error); };
    };
  }), sessionId);
}
async function snapshot(sessionId, name) {
  const doc = await readConversation(sessionId);
  await save(`${name}.json`, doc);
  return doc;
}
async function waitSettled(sessionId, minAsks = 1) {
  return poll(() => readConversation(sessionId), (doc) => {
    const message = assistant(doc);
    return message && (['done', 'error', 'stopped'].includes(message.status) || message.asks?.at(-1)?.status === 'failed' ||
      ((message.asks?.length ?? 0) >= minAsks && message.asks?.at(-1)?.status === 'waiting'));
  }, `turn waiting or terminal, ${sessionId}`);
}
async function sendQuestion(question) {
  const before = streamRequests().length;
  await page.getByRole('textbox', { name: '输入问题', exact: true }).fill(question);
  await page.getByRole('button', { name: '发送', exact: true }).click();
  const item = await poll(async () => streamRequests().slice(before).at(-1), Boolean, 'real RAG request dispatched', 30000);
  return item.body;
}
async function submitCard() {
  await activeCard().getByRole('button', { name: /^(提交|提交回答)$/ }).click();
}
async function layouts(label, anchor = 'card') {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    if (anchor === 'card' && await activeCard().count()) await activeCard().scrollIntoViewIfNeeded();
    else if (await page.locator('.chat-row.assistant').count()) await page.locator('.chat-row.assistant').last().scrollIntoViewIfNeeded();
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const dimensions = await page.evaluate(() => ({
      width: innerWidth, rootScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      main: (() => { const rect = document.querySelector('.chat-main')?.getBoundingClientRect(); return rect ? { left: rect.left, right: rect.right, width: rect.width } : null; })(),
      reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      focus: document.activeElement?.getAttribute('aria-label') ?? document.activeElement?.tagName,
    }));
    const filename = `${label}-${viewport.width}x${viewport.height}.png`;
    await page.screenshot({ path: path.join(evidenceDir, filename), fullPage: true });
    report.screenshots.push({ file: filename, viewport, dimensions });
    check(`${label} ${viewport.width} 无页面横向溢出`, dimensions.rootScrollWidth <= viewport.width + 1 && dimensions.bodyScrollWidth <= viewport.width + 1, dimensions);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}
async function safeCase(name, run) {
  try { await run(); }
  catch (error) {
    report.cases[name] = { ...report.cases[name], error: error.message, stack: error.stack };
    check(`${name} 浏览器流程完成`, false, { error: error.message });
    await page.screenshot({ path: path.join(evidenceDir, `${name}-failure.png`), fullPage: true }).catch(() => undefined);
    // Cancel only this isolated run's own turn before the next case; never stop
    // an unknown process, browser, or user's task.
    for (const turn of ownTurns.values()) {
      await context.request.post(`${webUrl}/api/v1/rag/cancel`, { data: turn, timeout: 10000 }).catch(() => undefined);
    }
  }
}

try {
  const health = await context.request.get(`${webUrl}/api/v1/rag/status`, { timeout: 30000 });
  report.serviceStatus = await health.json();
  if (!check('真实本地教材服务可用', health.ok() && report.serviceStatus.available === true && report.serviceStatus.localOnly === true, { serviceStatus: report.serviceStatus })) {
    throw new Error('RAG service unavailable; no inference questions were sent.');
  }
  await page.goto(`${webUrl}/chat`);
  await page.getByRole('textbox', { name: '输入问题', exact: true }).waitFor();
  await page.getByRole('button', { name: /^选择业务能力，当前：/ }).click();
  const ragEntry = page.getByRole('button', { name: /^RAG 模式/ });
  check('RAG 入口无需先选择云模型即可使用', await ragEntry.isEnabled());
  await ragEntry.click();

  await safeCase('math', async () => {
    const request = await sendQuestion(fixtures.math.question);
    let doc = await waitSettled(request.sessionId);
    const first = assistant(doc);
    report.cases.math = { sessionId: request.sessionId, turnId: request.turnId, initialStatus: first?.status };
    check('数学正向题返回教材原文与行号', !!first && /教材定位与原文讲解/.test(first.content) && /第\s*\d+[–—-]\d+\s*行/.test(first.content) && /^> /m.test(first.content) && /列举法/.test(first.content), { contentSha256: sha(first?.content ?? ''), observedText: first?.content ?? '' });
    check('默认交付如实标注原文讲解边界', first?.content.includes('本轮未提供独立解题推导。') === true);
    check('真实教材引擎身份与追问卡', !!first?.rag && first.modelProfileId === 'local-textbook-rag' && first.asks?.at(-1)?.status === 'waiting' && !(await page.locator('.chat-messages').innerText()).includes('追问（本地模拟）'));
    if (first?.asks?.at(-1)?.status !== 'waiting') throw new Error('No live clarification card; cannot certify reply/reconnect path.');

    const cardDraft = '请保留这条未提交的教材追问草稿。';
    const composerDraft = '刷新期间保留的主输入草稿。';
    await activeCard().getByRole('textbox').fill(cardDraft);
    await page.getByRole('textbox', { name: '输入问题', exact: true }).fill(composerDraft);
    await poll(() => readConversation(request.sessionId), (value) => value?.draft === composerDraft && assistant(value)?.asks?.at(-1)?.drafts?.['textbook-follow-up']?.freeText === cardDraft, 'drafts persisted', 15000);
    await layouts('math-waiting');
    const before = await snapshot(request.sessionId, 'math-before-refresh');
    const beforeMessage = assistant(before);
    const streamCount = streamRequests().length;
    await page.reload();
    await page.getByRole('button', { name: '继续本轮', exact: true }).waitFor({ timeout: 30000 });
    check('刷新保留主输入草稿', await page.getByRole('textbox', { name: '输入问题', exact: true }).inputValue() === composerDraft);
    await page.getByRole('button', { name: '继续本轮', exact: true }).click();
    const resumedRequest = await poll(async () => streamRequests().slice(streamCount).at(-1), Boolean, 'same-turn reconnect dispatched', 15000);
    await activeCard().getByRole('textbox').waitFor({ timeout: 15000 });
    check('刷新重连原轮与原游标，不新建推理轮', resumedRequest.body.turnId === request.turnId && resumedRequest.body.sessionId === request.sessionId && resumedRequest.body.question === fixtures.math.question && resumedRequest.body.afterEventId === beforeMessage.rag.lastEventId && resumedRequest.body.afterEventId > 0, { request: resumedRequest.body, savedCursor: beforeMessage.rag.lastEventId });
    check('刷新保留追问卡草稿', await activeCard().getByRole('textbox').inputValue() === cardDraft);
    doc = await snapshot(request.sessionId, 'math-after-reconnect');
    check('重连不重复正文、卡片或助手消息', assistant(doc)?.content === beforeMessage.content && assistant(doc)?.asks?.length === beforeMessage.asks?.length && doc.messages.filter((m) => m.role === 'assistant').length === 1 && await page.locator('.chat-row.assistant').count() === 1);

    await activeCard().getByRole('textbox').fill(fixtures.supplement);
    const repliesBefore = report.requests.filter((r) => r.path === '/api/v1/rag/reply').length;
    await submitCard();
    await poll(async () => report.requests.filter((r) => r.path === '/api/v1/rag/reply').length, (n) => n > repliesBefore, 'real reply submitted', 15000);
    doc = await waitSettled(request.sessionId, 2);
    const afterReply = assistant(doc);
    await save('math-after-follow-up.json', doc);
    check('回答经专用接口在同轮继续', afterReply?.rag?.turnId === request.turnId && afterReply?.asks?.[0]?.status === 'answered' && !!afterReply.asks[0].followUp && doc.messages.filter((m) => m.role === 'assistant').length === 1, { followUp: afterReply?.asks?.[0]?.followUp ?? '', status: afterReply?.status });
    check('数学补充仍能返回教材原文', /教材定位与原文讲解/.test(afterReply?.asks?.[0]?.followUp ?? '') && /第\s*\d+[–—-]\d+\s*行/.test(afterReply?.asks?.[0]?.followUp ?? ''), { note: '真实候选若拒答，此项保持 FAIL；不会改用预置文本。' });
    if (afterReply?.asks?.at(-1)?.status === 'waiting') {
      await activeCard().getByRole('textbox').fill('');
      await submitCard();
      doc = await poll(() => readConversation(request.sessionId), (value) => assistant(value)?.status === 'done', 'skip reaches terminal', 15000);
    }
    check('跳过不追加推理并正常结束', assistant(doc)?.status === 'done' && assistant(doc)?.rag?.status === 'terminal');
    check('卡片提交未清空未消费的主输入草稿', doc.draft === composerDraft);
    await snapshot(request.sessionId, 'math-final');
    await layouts('math-final', 'answer');
  });

  await safeCase('ooc', async () => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole('button', { name: '新建对话', exact: true }).click();
    const request = await sendQuestion(fixtures.ooc.question);
    const doc = await waitSettled(request.sessionId);
    const message = assistant(doc);
    report.cases.ooc = { sessionId: request.sessionId, turnId: request.turnId, status: message?.status };
    await save('ooc-before-cancel.json', doc);
    check('OOC-1 如实拒答，不展示无关教材引用或硬答', !!message && /证据不足|无法.*(?:教材|定位)|未找到|不足以|无法.*回答/.test(message.content) && !/教材定位与原文讲解|第\s*\d+[–—-]\d+\s*行|^> /m.test(message.content) && !/O\s*\(\s*n\s*log\s*n\s*\)/i.test(message.content), { actualText: message?.content ?? '' });
    check('OOC-1 提供补充题目入口', message?.asks?.at(-1)?.status === 'waiting');
    if (message?.asks?.at(-1)?.status !== 'waiting') throw new Error('No active wait to exercise real cancellation.');
    await layouts('ooc-waiting');
    await page.getByRole('textbox', { name: '输入问题', exact: true }).fill('');
    const cancellation = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/v1/rag/cancel', { timeout: 15000 });
    await page.getByRole('button', { name: '停止', exact: true }).click();
    const cancelResponse = await cancellation;
    const stopped = await poll(() => readConversation(request.sessionId), (value) => assistant(value)?.rag?.status === 'terminal' && assistant(value)?.status === 'stopped', 'cancel persisted', 15000);
    check('取消调用真实后端并立即关闭本地轮次', cancelResponse.ok() && assistant(stopped).asks?.at(-1)?.status === 'interrupted', { httpStatus: cancelResponse.status() });
    await save('ooc-cancelled.json', stopped);
    await page.reload();
    await page.getByRole('textbox', { name: '输入问题', exact: true }).waitFor();
    check('取消后刷新不复活轮次或恢复入口', await page.getByRole('button', { name: '继续本轮', exact: true }).count() === 0 && await page.locator('.chat-ask-card.active').count() === 0);
    await layouts('ooc-cancelled', 'answer');
  });
  completed = true;
} catch (error) {
  report.fatal = { message: error.message, stack: error.stack };
  check('浏览器验收前置或总流程', false, { error: error.message });
} finally {
  const uniqueTurns = new Set(streamRequests().map((r) => r.body?.turnId));
  const replyRequests = report.requests.filter((r) => r.path === '/api/v1/rag/reply');
  const nonemptyReplies = replyRequests.filter((r) => r.body?.answers?.some((a) => !a.skipped && (a.labels?.length || a.freeText?.trim())));
  report.observedBudget = { uniqueInitialTurns: uniqueTurns.size, nonemptyReplies: nonemptyReplies.length, streamConnections: streamRequests().length, maximumEnqueuedLocatesFromObservedRequests: uniqueTurns.size + nonemptyReplies.length, note: 'HTTP 发起任务上限，不冒充模型台账实测次数；实际生成/复核/缓存用量由root核对后端台账。' };
  check('固定调用预算未超出', uniqueTurns.size <= 2 && nonemptyReplies.length <= 1 && uniqueTurns.size + nonemptyReplies.length <= 3, report.observedBudget);
  check('未调用普通聊天或云模型配置写入', !report.requests.some((r) => r.path === '/api/v1/chat/stream' || (!r.path.startsWith('/api/v1/rag/') && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(r.method))));
  check('未出现非本地网络请求', report.externalRequestsBlocked.length === 0);
  check('页面无未捕获异常', report.pageErrors.length === 0, { count: report.pageErrors.length });
  check('浏览器无 console.error', report.console.every((entry) => entry.type !== 'error'), { errors: report.console.filter((entry) => entry.type === 'error') });
  // Clean up only turns created by this isolated script. No process termination,
  // storage clearing, browser-profile writes, or user-session operations.
  report.cleanup = [];
  for (const turn of ownTurns.values()) {
    try {
      const response = await context.request.post(`${webUrl}/api/v1/rag/cancel`, { data: turn, timeout: 10000 });
      report.cleanup.push({ ...turn, status: response.status() });
    } catch (error) { report.cleanup.push({ ...turn, error: error.message }); }
  }
  report.finishedAt = new Date().toISOString();
  report.completed = completed;
  report.summary = { pass: report.checks.filter((c) => c.status === 'PASS').length, fail: report.checks.filter((c) => c.status === 'FAIL').length, humanQuality: 'not_run' };
  await save('report.json', report);
  await save('console.json', { console: report.console, pageErrors: report.pageErrors, requestFailures: report.requestFailures });
  await save('network.json', { requests: report.requests, responses: report.responses, externalRequestsBlocked: report.externalRequestsBlocked });
  await writeFile(path.join(evidenceDir, 'README.md'), `# RAG-BROWSER-v1\n\n真实本地浏览器验收：${report.summary.pass} PASS / ${report.summary.fail} FAIL。\n\n人工教学质量：not_run。默认验证教材原文摘录与同轮追问工程链路，不认证自由解题推导。\n\n完整逐项结果见 report.json；实际生成 ${report.screenshots.length} 张布局截图，请按 report.json 核对成功覆盖的视口与步骤。计划视口为 1440×900、1920×1080、390×844。未通过项保留真实结果，不自动重试或替换题目。\n`, 'utf8');
  await context.close();
  await browser.close();
  console.log(`Evidence: ${evidenceDir}`);
  console.log(JSON.stringify(report.summary));
  process.exitCode = report.summary.fail || !completed ? 1 : 0;
}
