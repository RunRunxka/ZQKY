import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect, type Page } from '@playwright/test';

/**
 * Real FastAPI business chain with a controlled model Provider only.
 * Browser requests are forwarded byte-for-byte to the isolated backend; no
 * business API response is mocked. Each run owns one OS temporary data root.
 */
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const API_DIR = path.join(REPO_ROOT, 'apps', 'api');
const API_ORIGIN = 'http://127.0.0.1:8001';
const GENERATED_STEM = '计算有理数 (-2) + 5 的结果。';
const REVIEWED_STEM = '计算有理数 (-2) + 5 的结果，并写出计算过程。';

interface Backend {
  child: ChildProcess;
  logStream: fs.WriteStream;
  tmpRoot: string;
  dataDir: string;
}

interface GenerationStats {
  pointId: string;
  pointCode: string;
  profileId: string;
  providerCalls: number;
  calls: { profileId: string; modelId: string }[];
}

interface CapturedResponse {
  method: string;
  path: string;
  status: number;
  body: Record<string, unknown>;
}

let backend: Backend | null = null;

function uvArgs(args: string[]): { command: string; args: string[] } {
  return process.platform === 'win32'
    ? { command: 'cmd.exe', args: ['/d', '/s', '/c', 'uv', ...args] }
    : { command: 'uv', args };
}

async function requireFreePort(port: number): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const server = net.createServer();
    server.on('error', () => reject(new Error(`测试端口 ${port} 已占用；不连接或终止未知服务。`)));
    server.listen(port, '127.0.0.1', () => server.close(() => resolve()));
  });
}

async function waitForHealth(current: Backend): Promise<void> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (current.child.exitCode !== null) break;
    try {
      if ((await fetch(`${API_ORIGIN}/api/v1/health`)).ok) return;
    } catch {
      // Only poll the freshly spawned owned backend after its port check.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  const logFile = path.join(current.tmpRoot, 'api.log');
  throw new Error(
    `隔离题库后端未启动：${fs.existsSync(logFile) ? fs.readFileSync(logFile, 'utf8') : ''}`,
  );
}

async function startBackend(): Promise<Backend> {
  await requireFreePort(8001);
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'zqky-f10-real-'));
  const dataDir = path.join(tmpRoot, 'data');
  const env = {
    ...process.env,
    ZQKY_ENV: 'test',
    ZQKY_DATA_DIR: dataDir,
    ZQKY_API_HOST: '127.0.0.1',
    ZQKY_API_PORT: '8001',
    ZQKY_TEST_GENERATION: '1',
    ZQKY_ALLOWED_ORIGINS: 'http://127.0.0.1:5174',
    ZQKY_TEXTBOOK_SOURCE_DIR: path.join(tmpRoot, 'no-textbooks'),
  };
  const { command, args } = uvArgs([
    'run',
    'uvicorn',
    'teaching_loop_backend:app',
    '--app-dir',
    '../../tests/fixtures',
    '--host',
    '127.0.0.1',
    '--port',
    '8001',
    '--log-level',
    'warning',
  ]);
  const child = spawn(command, args, { cwd: API_DIR, env, windowsHide: true });
  const logStream = fs.createWriteStream(path.join(tmpRoot, 'api.log'));
  child.stdout?.pipe(logStream);
  child.stderr?.pipe(logStream);
  const current = { child, logStream, tmpRoot, dataDir };
  // Save ownership before waiting: startup failure must still stop this process.
  backend = current;
  await waitForHealth(current);
  return current;
}

async function stopBackend(): Promise<void> {
  const current = backend;
  backend = null;
  if (!current) return;
  if (process.platform === 'win32' && current.child.pid) {
    spawnSync('taskkill', ['/pid', String(current.child.pid), '/T', '/F'], {
      windowsHide: true,
      encoding: 'utf8',
    });
  } else {
    current.child.kill('SIGTERM');
  }
  current.logStream.end();
  const resolved = path.resolve(current.tmpRoot);
  const temporary = path.resolve(os.tmpdir());
  const relative = path.relative(temporary, resolved);
  if (
    !relative ||
    relative.startsWith('..') ||
    path.isAbsolute(relative) ||
    !path.basename(resolved).startsWith('zqky-f10-real-')
  ) {
    throw new Error('Refusing to clean an unowned temporary directory');
  }
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    try {
      fs.rmSync(resolved, { recursive: true, force: true });
      return;
    } catch {
      // Windows process handles can outlive taskkill for a short interval.
    }
  }
  console.warn(`[question-bank-real] 临时目录未能清理：${resolved}`);
}

async function forwardApi(page: Page, captured: CapturedResponse[]): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = { ...request.headers() };
    delete headers.host;
    delete headers['content-length'];
    const response = await fetch(`${API_ORIGIN}${url.pathname}${url.search}`, {
      method: request.method(),
      headers,
      body: request.postDataBuffer() ?? undefined,
      redirect: 'manual',
    });
    const bytes = Buffer.from(await response.arrayBuffer());
    const responseHeaders = Object.fromEntries(response.headers.entries());
    delete responseHeaders['content-length'];
    delete responseHeaders['content-encoding'];
    delete responseHeaders['transfer-encoding'];
    if (responseHeaders['content-type']?.includes('application/json')) {
      captured.push({
        method: request.method(),
        path: `${url.pathname}${url.search}`,
        status: response.status,
        body: JSON.parse(bytes.toString('utf8')),
      });
    }
    await route.fulfill({ status: response.status, headers: responseHeaders, body: bytes });
  });
}

test.afterAll(stopBackend);

test('真实 AI 补题 queued@0→attempt 1→人工校对确认→知识点检索', async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(180_000);
  const current = await startBackend();
  const captured: CapturedResponse[] = [];
  await forwardApi(page, captured);
  const statsResponse = await request.get(`${API_ORIGIN}/__test/generation`);
  expect(statsResponse.status()).toBe(200);
  const initialStats = (await statsResponse.json()) as GenerationStats;
  expect(initialStats.providerCalls).toBe(0);
  const catalogResponse = await request.get(`${API_ORIGIN}/api/v1/model-catalog`);
  const catalog = await catalogResponse.json();
  expect(catalog.defaultChatProfileId).toBe(initialStats.profileId);
  expect(catalog.connections[0].callable).toBe(true);
  expect((await request.get(`${API_ORIGIN}/api/v1/questions`)).status()).toBe(200);

  await page.goto('/question-bank#library');
  await expect(page.getByRole('tab', { name: '已入库题目' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page.getByTestId('qb-generation-open').click();
  const panel = page.getByTestId('qb-generation-panel');
  await panel.getByRole('combobox', { name: '学科', exact: true }).selectOption('math');
  await panel.getByLabel(`有理数（${initialStats.pointCode}）`, { exact: true }).check();
  await panel.getByLabel('题数（1–10）').fill('1');
  const receiptPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/question-generation-jobs') &&
      response.request().method() === 'POST',
  );
  await page.getByTestId('qb-generation-submit').click();
  const receiptResponse = await receiptPromise;
  expect(receiptResponse.status()).toBe(202);
  const receipt = await receiptResponse.json();
  expect(receipt).toMatchObject({ state: 'queued', attempt: 0, importId: null, candidateCount: 0 });
  await expect(page.getByTestId('qb-generation-attempt')).toHaveText('第 1 次尝试');
  await expect(page.getByTestId('qb-generation-state')).toHaveText('整理中');
  await expect(page.getByTestId('qb-generation-observe-notice')).toHaveCount(0);
  await expect(page.getByTestId('qb-generation-import')).toHaveCount(0);
  const beforePublish = await (await request.get(`${API_ORIGIN}/api/v1/questions`)).json();
  expect(beforePublish.total).toBe(0);
  expect((await request.post(`${API_ORIGIN}/__test/generation/release`)).status()).toBe(200);

  await expect(page.getByTestId('qb-generation-succeeded')).toContainText(
    '生成 1 道待校对候选草稿',
  );
  await expect(page.getByTestId('qb-generation-observe-notice')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('generation-succeeded.png'), fullPage: true });
  const terminalResponse = await request.get(
    `${API_ORIGIN}/api/v1/workflow-jobs/${receipt.jobId}?domain=question`,
  );
  const terminal = await terminalResponse.json();
  expect(terminal).toMatchObject({ state: 'succeeded', attempt: 1 });
  expect(terminal.result.candidateCount).toBe(1);
  const importId = terminal.result.importId as string;
  const candidate = await (
    await request.get(`${API_ORIGIN}/api/v1/question-imports/${importId}`)
  ).json();
  expect(candidate.drafts).toHaveLength(1);
  expect(candidate.drafts[0]).toMatchObject({
    extractionMethod: 'ai',
    reviewState: 'needs_review',
  });
  expect(candidate.drafts[0].content.stemMarkdown).toBe(GENERATED_STEM);
  expect(candidate.drafts[0].knowledgeLinks[0].knowledgePointId).toBe(initialStats.pointId);
  expect((await (await request.get(`${API_ORIGIN}/api/v1/questions`)).json()).total).toBe(0);

  await page.getByTestId('qb-generation-import').click();
  await expect(page).toHaveURL(new RegExp(`/question-bank/imports/${importId}$`));
  await expect(page.getByRole('heading', { name: '试题校对', exact: true })).toBeVisible();
  await expect(page.getByTestId('qb-draft-ai-source')).toBeVisible();
  await expect(page.getByRole('textbox', { name: '题干', exact: true })).toHaveValue(GENERATED_STEM);
  await page.getByRole('textbox', { name: '题干', exact: true }).fill(REVIEWED_STEM);
  // 内容实际变化必须回到needs_review；先保存新内容，再审核该服务端修订。
  const savedPromise = page.waitForResponse((response) =>
    response.url().includes(`/question-drafts/${candidate.drafts[0].draftId}`) &&
    response.request().method() === 'PATCH');
  await page.getByRole('button', { name: '保存修改', exact: true }).click();
  const savedResponse = await savedPromise;
  expect(savedResponse.status()).toBe(200);
  const savedDraft = await savedResponse.json();
  expect(savedDraft.content.stemMarkdown).toBe(REVIEWED_STEM);
  expect(savedDraft.reviewState).toBe('needs_review');
  await expect(page.getByRole('button', { name: '标记已校对', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: '标记已校对', exact: true }).click();
  await expect(page.getByTestId('qb-review-state')).toHaveText('已校对');
  await page.screenshot({ path: testInfo.outputPath('candidate-reviewed.png'), fullPage: true });
  const confirmationPromise = page.waitForResponse(
    (response) =>
      response.url().includes(`/question-imports/${importId}/confirm`) &&
      response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: '确认入库（1 道）', exact: true }).click();
  const confirmationResponse = await confirmationPromise;
  expect(confirmationResponse.status()).toBe(200);
  const confirmation = await confirmationResponse.json();
  expect(confirmation.failures).toEqual([]);
  expect(confirmation.confirmedQuestionIds).toHaveLength(1);
  await expect(page.getByText('本次已入库 1 道题', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: '查看已入库题目', exact: true }).click();
  await expect(page.getByRole('tab', { name: '已入库题目' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page.locator('#qb-filter-subject').selectOption('math');
  await page
    .getByTestId('qb-library-knowledge-filter')
    .getByRole('combobox')
    .selectOption(initialStats.pointId);
  const filteredPromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/v1/questions?') &&
      response.url().includes(`knowledgePointId=${initialStats.pointId}`),
  );
  await page.getByRole('button', { name: '查询', exact: true }).click();
  const filtered = await (await filteredPromise).json();
  expect(filtered.total).toBe(1);
  expect(filtered.questions[0].questionId).toBe(confirmation.confirmedQuestionIds[0]);
  await expect(page.locator('.qb-question-card')).toHaveCount(1);
  await expect(page.locator('.qb-question-card')).toContainText(REVIEWED_STEM);
  await page.screenshot({ path: testInfo.outputPath('knowledge-filter.png'), fullPage: true });
  const detail = await (
    await request.get(`${API_ORIGIN}/api/v1/questions/${confirmation.confirmedQuestionIds[0]}`)
  ).json();
  expect(detail.content.stemMarkdown).toBe(REVIEWED_STEM);
  expect(detail.knowledgeLinks[0].knowledgePointId).toBe(initialStats.pointId);
  const finalStats = (await (
    await request.get(`${API_ORIGIN}/__test/generation`)
  ).json()) as GenerationStats;
  expect(finalStats.providerCalls).toBe(1);
  expect(finalStats.calls[0].profileId).toBe(initialStats.profileId);
  await testInfo.attach('real-generation-chain', {
    contentType: 'application/json',
    body: Buffer.from(
      JSON.stringify({ receipt, terminal, confirmation, finalStats, captured }, null, 2),
    ),
  });
  await testInfo.attach('isolated-api-log', {
    path: path.join(current.tmpRoot, 'api.log'),
    contentType: 'text/plain',
  });
});

test('真实公共 retry：首次失败可见，queued(N)→succeeded(N+1)只调用一次', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  const current = backend ?? await startBackend();
  const captured: CapturedResponse[] = [];
  await forwardApi(page, captured);
  const initial = await (await request.get(`${API_ORIGIN}/__test/generation`)).json() as GenerationStats;
  await request.post(`${API_ORIGIN}/__test/generation/fail-next`);
  await request.post(`${API_ORIGIN}/__test/generation/release`);
  await page.goto('/question-bank#library');
  await page.getByTestId('qb-generation-open').click();
  const panel = page.getByTestId('qb-generation-panel');
  await panel.getByRole('combobox', { name: '学科', exact:true }).selectOption('math');
  await panel.getByLabel(`有理数（${initial.pointCode}）`, { exact:true }).check();
  await panel.getByLabel('题数（1–10）').fill('1');
  const created = page.waitForResponse((response) => response.url().endsWith('/api/v1/question-generation-jobs') && response.request().method() === 'POST');
  await page.getByTestId('qb-generation-submit').click();
  const receipt = await (await created).json();
  expect(receipt.attempt).toBe(0);
  await expect(page.getByTestId('qb-generation-state')).toHaveText('失败');
  await expect(page.getByTestId('qb-generation-import')).toHaveCount(0);
  const retryResponse = page.waitForResponse((response) => response.url().includes(`/workflow-jobs/${receipt.jobId}/retry`) && response.request().method() === 'POST');
  await page.getByTestId('qb-generation-retry').click();
  const retry = await (await retryResponse).json();
  expect(retry).toMatchObject({jobId:receipt.jobId, state:'queued', attempt:1});
  await expect(page.getByTestId('qb-generation-succeeded')).toContainText('生成 1 道待校对候选草稿');
  const terminal = await (await request.get(`${API_ORIGIN}/api/v1/workflow-jobs/${receipt.jobId}?domain=question`)).json();
  expect(terminal).toMatchObject({jobId:receipt.jobId,state:'succeeded',attempt:2});
  expect(terminal.result.candidateCount).toBe(1);
  const stats = await (await request.get(`${API_ORIGIN}/__test/generation`)).json() as GenerationStats;
  expect(stats.providerCalls - initial.providerCalls).toBe(2);
  await testInfo.attach('real-public-retry.json', {contentType:'application/json',body:Buffer.from(JSON.stringify({receipt,retry,terminal,stats,captured},null,2))});
  await page.screenshot({path:testInfo.outputPath('public-retry-succeeded.png'),fullPage:true});
  await testInfo.attach('isolated-api-log', {path:path.join(current.tmpRoot,'api.log'),contentType:'text/plain'});
});

