import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { crc32 } from 'node:zlib';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect, type Page, type Route } from '@playwright/test';

/**
 * `/assessments` 施测与成绩工作区 e2e（TEACHING-LOOP B3 · F20-I）。
 *
 * **真实浏览器链**：本文件起一个**隔离的真 FastAPI**（`ZQKY_DATA_DIR` 指临时目录、
 * 迁移自动应用、监听临时空闲端口；绝不使用 8000 端口的本机服务，也绝不读写 `.local-data`），
 * 浏览器在真实页面上完成 建班 → 选人次 → 选已确认原卷 → 建施测 → 上传 XLSX（Playwright
 * `setInputFiles` 生成的字节，不落盘）→ 映射 → 修正一格 → 承认 → 确认 → 历史矩阵读回。
 *
 * 隔离8001构建以 `ZQKY_API_ORIGIN` 固定Next同源代理，浏览器直接发送完整文件给真API。
 * 未配置该构建时保留 `page.route` 动态转发兼容路径；文件用内存字节上传，避免Chromium
 * 请求快照省略磁盘File内容。响应丢失只拦确认响应，实际业务提交仍由真实FastAPI完成。
 * 业务数据全部来自真FastAPI，无任何fixture数据冒充成功。
 *
 * 数据准备：用后端自己的测试台 `tests.scores_support.ScoresHarness`（真库、真迁移、真确认
 * 触发器）在同一个临时数据根里种子一张**已确认原卷**（Q1=2、Q2=3、Q3=5）；班级/学生/施测/
 * 参测人次/成绩全部在浏览器里走真实 API 创建。
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');
const API_DIR = path.join(REPO_ROOT, 'apps', 'api');

interface Backend {
  origin: string;
  dataDir: string;
  tmpRoot: string;
  child: ChildProcess;
  closed: Promise<void>;
  logStream: fs.WriteStream;
  paper: { paperId: string; revisionId: string; title: string };
  scalePaper: { paperId: string; revisionId: string; title: string };
  completePaperFile: string;
}

let backend: Backend | null = null;
let backendPromise: Promise<Backend> | null = null;

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on('error', reject);
    server.listen(8001, '127.0.0.1', () => {
      const address = server.address();
      const port = typeof address === 'object' && address ? address.port : 0;
      server.close(() => (port ? resolve(port) : reject(new Error('无法分配空闲端口'))));
    });
  });
}

function uvArgs(args: string[]): { command: string; args: string[] } {
  if (process.platform === 'win32') {
    return { command: 'cmd.exe', args: ['/d', '/s', '/c', 'uv', ...args] };
  }
  return { command: 'uv', args };
}

function runUvSync(
  args: string[],
  options: { cwd: string; env: NodeJS.ProcessEnv },
): { status: number; stdout: string; stderr: string } {
  const { command, args: commandArgs } = uvArgs(args);
  const result = spawnSync(command, commandArgs, {
    cwd: options.cwd,
    env: options.env,
    encoding: 'utf8',
    windowsHide: true,
  });
  return {
    status: result.status ?? -1,
    stdout: result.stdout ?? '',
    stderr: result.stderr ?? '',
  };
}

async function waitForHealth(origin: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError: unknown = null;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${origin}/api/v1/health`);
      if (response.ok) return;
      lastError = new Error(`health ${response.status}`);
    } catch (cause) {
      lastError = cause;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`隔离后端未在 ${timeoutMs}ms 内就绪：${String(lastError)}`);
}

async function startBackend(): Promise<Backend> {
  const port = await freePort();
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'zqky-f20i-'));
  const dataDir = path.join(tmpRoot, 'data');
  const logFile = path.join(tmpRoot, 'api.log');
  if (process.env.ZQKY_KEEP_TEST_DATA === '1') {
    console.log(`[ZQKY_TEST_DATA_CREATED] ${JSON.stringify({ spec: 'assessments', tmpRoot, dataDir, apiLog: logFile })}`);
  }
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    ZQKY_DATA_DIR: dataDir,
    ZQKY_ENV: 'test',
    ZQKY_API_PORT: String(port),
    ZQKY_ALLOWED_ORIGINS: 'http://127.0.0.1:5174',
    // 教材原件目录指到临时空目录：隔离运行不读正式教材盘
    ZQKY_TEXTBOOK_SOURCE_DIR: path.join(tmpRoot, 'no-textbooks'),
  };

  // 1) 用后端自己的测试台在临时数据根里种子「已确认原卷」（真库 + 真确认触发器）。
  //    规模用例取 200 人次 × 100 叶：`tabular.read_score_sheet` 已由 CTRL 修为
  //    `iter_rows` 一次性物化（修复前逐格 `.cell()` 在 200×100 上不可收敛），
  //    后端 200×100 专项测试约 2s，本 spec 按真实浏览器链复测。
  const seedScript = path.join(tmpRoot, 'seed_paper.py');
  fs.writeFileSync(
    seedScript,
    [
      'import json, sys',
      'from pathlib import Path',
      'REPO, ROOT = Path(sys.argv[1]), Path(sys.argv[2])',
      'sys.path.insert(0, str(REPO / "apps" / "api"))',
      'from tests.scores_support import ScoresHarness',
      'sys.path.insert(0, str(REPO / "tests" / "fixtures"))',
      'from teaching_loop_docx import build_complete_paper',
      '(ROOT / "complete-paper.docx").write_bytes(build_complete_paper())',
      'with ScoresHarness(ROOT) as harness:',
      '    paper = harness.seed_confirmed_paper(',
      '        tag="f20i",',
      '        leaves=(("Q1", 200), ("Q2", 300), ("Q3", 500)),',
      '        title="F20-I 成绩样本卷",',
      '    )',
      '    scale = harness.seed_confirmed_paper(',
      '        tag="scale",',
      '        leaves=tuple((f"Q{i}", 100) for i in range(1, 101)),',
      '        title="F20-I 规模样本卷（100 叶）",',
      '    )',
      '    print(json.dumps({',
      '        "paper": {"paperId": paper.paper_id, "revisionId": paper.revision_id, "title": paper.title},',
      '        "scalePaper": {"paperId": scale.paper_id, "revisionId": scale.revision_id, "title": scale.title},',
      '    }, ensure_ascii=False))',
    ].join('\n'),
    'utf8',
  );
  const seed = runUvSync(
    ['run', 'python', seedScript, REPO_ROOT, tmpRoot],
    { cwd: API_DIR, env },
  );
  if (seed.status !== 0) {
    throw new Error(`种子原卷失败（exit ${seed.status}）：${seed.stderr || seed.stdout}`);
  }
  const paper = JSON.parse(seed.stdout.trim().split(/\r?\n/).pop() ?? '{}') as {
    paper?: Backend['paper'];
    scalePaper?: Backend['scalePaper'];
  };
  if (!paper.paper?.paperId || !paper.scalePaper?.paperId) {
    throw new Error(`种子原卷输出无法解析：${seed.stdout}`);
  }

  // 2) 起隔离 FastAPI（临时端口；迁移在启动时自动应用）
  const { command, args } = uvArgs([
    'run',
    'uvicorn',
    'teaching_loop_backend:app',
    '--app-dir',
    '../../tests/fixtures',
    '--host',
    '127.0.0.1',
    '--port',
    String(port),
    '--log-level',
    'warning',
  ]);
  const logStream = fs.createWriteStream(logFile, { flags: 'a' });
  const child = spawn(command, args, { cwd: API_DIR, env, windowsHide: true });
  const closed = new Promise<void>((resolve) => child.once('close', () => resolve()));
  child.stdout?.pipe(logStream, { end: false });
  child.stderr?.pipe(logStream, { end: false });
  const origin = `http://127.0.0.1:${port}`;
  const current = { origin, dataDir, tmpRoot, child, closed, logStream, paper: paper.paper, scalePaper: paper.scalePaper, completePaperFile: path.join(tmpRoot, 'complete-paper.docx') };
  backend = current;

  try {
    await waitForHealth(origin, 180_000);
  } catch (cause) {
    const startupLog = fs.existsSync(logFile) ? fs.readFileSync(logFile, 'utf8') : '';
    await stopBackend();
    throw new Error(
      `${String(cause)}\n--- api.log ---\n${startupLog}`,
    );
  }
  return current;
}

function ensureBackend(): Promise<Backend> {
  if (!backendPromise) backendPromise = startBackend();
  return backendPromise;
}

/** 等待自有后端和日志关闭；明确 opt-in 保留证据，默认清理本轮临时目录。 */
async function stopBackend(): Promise<void> {
  const current = backend;
  backend = null;
  backendPromise = null;
  if (!current) return;
  try {
    if (current.child.exitCode === null && current.child.signalCode === null) {
      if (process.platform === 'win32' && current.child.pid) {
        spawnSync('taskkill', ['/pid', String(current.child.pid), '/T', '/F'], {
          windowsHide: true,
          encoding: 'utf8',
        });
      } else {
        current.child.kill('SIGTERM');
      }
    }
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Owned backend did not close within 30s')), 30_000);
      current.closed.then(() => {
        clearTimeout(timer);
        resolve();
      }, (cause) => {
        clearTimeout(timer);
        reject(cause);
      });
    });
    await new Promise<void>((resolve, reject) => {
      if (current.logStream.closed) return resolve();
      current.logStream.once('close', () => resolve());
      current.logStream.once('error', reject);
      current.logStream.end();
    });
  } catch (cause) {
    console.warn(`[assessments.spec] 自有后端或日志未完成关闭，保留临时目录：${current.tmpRoot}；${String(cause)}`);
    return;
  }
  const resolved = path.resolve(current.tmpRoot);
  const relative = path.relative(path.resolve(os.tmpdir()), resolved);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative) || !path.basename(resolved).startsWith('zqky-f20i-')) {
    throw new Error('Refusing to clean an unowned temporary directory');
  }
  if (process.env.ZQKY_KEEP_TEST_DATA === '1') {
    console.log(`[ZQKY_TEST_DATA_RETAINED] ${JSON.stringify({ spec: 'assessments', tmpRoot: resolved, dataDir: current.dataDir, apiLog: path.join(resolved, 'api.log'), pid: current.child.pid, childClosed: true, logClosed: current.logStream.closed })}`);
    return;
  }
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    try {
      fs.rmSync(resolved, { recursive: true, force: true });
      return;
    } catch {
      // Windows 上进程句柄释放有延迟：重试
    }
  }
  // 保留临时目录（不静默删不掉还宣称清理完成），只在控制台说明位置
  console.warn(`[assessments.spec] 临时目录未能删除，请手工清理：${current.tmpRoot}`);
}

test.afterAll(async () => {
  await stopBackend();
});

/** 把页面发出的 /api/v1/** 逐字节转发给隔离后端（业务数据全部来自它）。 */
async function proxyApi(page: Page, origin: string) {
  // 固定8001验收走真实Next同源代理；保留浏览器的文件上传字节，避免
  // Chromium postDataBuffer 对磁盘File部件的省略。动态端口才使用下方转发。
  if (process.env.ZQKY_API_ORIGIN === origin) return;
  await page.route('**/api/v1/**', async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers: Record<string, string> = { ...request.headers() };
    delete headers.host;
    delete headers['content-length'];
    const body = request.postDataBuffer();
    let response: Response;
    try {
      response = await fetch(`${origin}${url.pathname}${url.search}`, {
        method: request.method(),
        headers,
        body: body ?? undefined,
        redirect: 'manual',
      });
    } catch (cause) {
      await route.fulfill({
        status: 502,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'E2E_PROXY_FAILED',
          message: `隔离后端转发失败：${String(cause)}`,
        }),
      });
      return;
    }
    const buffer = Buffer.from(await response.arrayBuffer());
    const responseHeaders: Record<string, string> = {};
    response.headers.forEach((value, key) => {
      if (key === 'content-encoding' || key === 'content-length' || key === 'transfer-encoding') {
        return;
      }
      responseHeaders[key] = value;
    });
    await route.fulfill({ status: response.status, headers: responseHeaders, body: buffer });
  });
}

interface ApiCall {
  status: number;
  body: unknown;
}

async function api(origin: string, pathname: string, init: RequestInit = {}): Promise<ApiCall> {
  const response = await fetch(`${origin}${pathname}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init.headers ?? {}) },
  });
  const text = await response.text();
  return { status: response.status, body: text ? JSON.parse(text) : null };
}

/* ------------------------------------------------------------------ 最小 XLSX 生成 */

interface ZipEntry {
  name: string;
  data: Buffer;
}

/** 只写「存储（不压缩）」条目：openpyxl 可读，零依赖。 */
function zipStore(entries: ZipEntry[]): Buffer {
  const localParts: Buffer[] = [];
  const centralParts: Buffer[] = [];
  let offset = 0;
  for (const entry of entries) {
    const name = Buffer.from(entry.name, 'utf8');
    const checksum = crc32(entry.data) >>> 0;
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0x0800, 6); // UTF-8 文件名
    local.writeUInt16LE(0, 8); // 存储
    local.writeUInt16LE(0, 10);
    local.writeUInt16LE(0x21, 12);
    local.writeUInt32LE(checksum, 14);
    local.writeUInt32LE(entry.data.length, 18);
    local.writeUInt32LE(entry.data.length, 22);
    local.writeUInt16LE(name.length, 26);
    local.writeUInt16LE(0, 28);
    localParts.push(local, name, entry.data);

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0x0800, 8);
    central.writeUInt16LE(0, 10);
    central.writeUInt16LE(0, 12);
    central.writeUInt16LE(0x21, 14);
    central.writeUInt32LE(checksum, 16);
    central.writeUInt32LE(entry.data.length, 20);
    central.writeUInt32LE(entry.data.length, 24);
    central.writeUInt16LE(name.length, 28);
    central.writeUInt16LE(0, 30);
    central.writeUInt16LE(0, 32);
    central.writeUInt16LE(0, 34);
    central.writeUInt16LE(0, 36);
    central.writeUInt32LE(0, 38);
    central.writeUInt32LE(offset, 42);
    centralParts.push(central, name);
    offset += local.length + name.length + entry.data.length;
  }
  const centralBuffer = Buffer.concat(centralParts);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(centralBuffer.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...localParts, centralBuffer, end]);
}

function escapeXml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

type CellValue = string | number | null;

function columnLetter(index: number): string {
  let value = index + 1;
  let letters = '';
  while (value > 0) {
    const remainder = (value - 1) % 26;
    letters = String.fromCharCode(65 + remainder) + letters;
    value = Math.floor((value - 1) / 26);
  }
  return letters;
}

/** 生成单表 XLSX（inlineStr，无共享字符串表）；不落盘，直接交给 setInputFiles。 */
function buildXlsx(sheetName: string, rows: CellValue[][]): Buffer {
  const sheetRows = rows
    .map((row, rowIndex) => {
      const cells = row
        .map((value, columnIndex) => {
          if (value === null || value === '') return '';
          const reference = `${columnLetter(columnIndex)}${rowIndex + 1}`;
          if (typeof value === 'number') {
            return `<c r="${reference}"><v>${value}</v></c>`;
          }
          return `<c r="${reference}" t="inlineStr"><is><t xml:space="preserve">${escapeXml(value)}</t></is></c>`;
        })
        .join('');
      return `<row r="${rowIndex + 1}">${cells}</row>`;
    })
    .join('');
  const dimension = `A1:${columnLetter(Math.max(...rows.map((row) => row.length)) - 1)}${rows.length}`;
  const worksheet =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">` +
    `<dimension ref="${dimension}"/><sheetData>${sheetRows}</sheetData></worksheet>`;

  return zipStore([
    {
      name: '[Content_Types].xml',
      data: Buffer.from(
        `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
          `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
          `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` +
          `<Default Extension="xml" ContentType="application/xml"/>` +
          `<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>` +
          `<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>` +
          `</Types>`,
        'utf8',
      ),
    },
    {
      name: '_rels/.rels',
      data: Buffer.from(
        `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
          `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
          `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>` +
          `</Relationships>`,
        'utf8',
      ),
    },
    {
      name: 'xl/workbook.xml',
      data: Buffer.from(
        `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
          `<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ` +
          `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">` +
          `<sheets><sheet name="${escapeXml(sheetName)}" sheetId="1" r:id="rId1"/></sheets></workbook>`,
        'utf8',
      ),
    },
    {
      name: 'xl/_rels/workbook.xml.rels',
      data: Buffer.from(
        `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
          `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
          `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>` +
          `</Relationships>`,
        'utf8',
      ),
    },
    { name: 'xl/worksheets/sheet1.xml', data: Buffer.from(worksheet, 'utf8') },
  ]);
}

const SHEET_NAME = '成绩';
const SAMPLE_HEADER: CellValue[] = ['学号', '姓名', 'Q1', 'Q2', 'Q3'];
/** 甲=(2,2,5)、乙=(2,3,空白)、丁=(0,3,5)；丙缺考（没有行）。 */
const SAMPLE_ROWS: CellValue[][] = [
  ['0001', '甲学生', 2, 2, 5],
  ['0002', '乙学生', 2, 3, null],
  ['0004', '丁学生', 0, 3, 5],
];

async function gotoAssessments(page: Page, backendOrigin: string) {
  await proxyApi(page, backendOrigin);
  await page.goto('/assessments');
  await expect(page.getByRole('heading', { name: '施测与成绩', level: 1 })).toBeVisible();
}

function todayIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

test.describe('施测与成绩工作区（真隔离 FastAPI + 真实浏览器）', () => {
  test.describe.configure({ mode: 'serial' });

  test('空态/错误恢复/键盘/减少动画与 390px：真实后端，无横向溢出', async ({ page }, testInfo) => {
    test.setTimeout(180_000);
    const current = await ensureBackend();
    backend = current;

    // 首屏就让班级列表这一次请求失败：错误态必须显示可读原因与重试入口（不是空列表）
    await proxyApi(page, current.origin);
    await page.route('**/api/v1/classes**', (route) => route.abort('failed'), { times: 1 });
    await page.goto('/assessments');
    await expect(page.getByRole('heading', { name: '施测与成绩', level: 1 })).toBeVisible();
    await expect(page.getByTestId('assessments-classes-error')).toContainText('班级列表读取失败');
    await expect(page.getByTestId('assessments-classes-empty')).toHaveCount(0);

    // 重试后恢复真实数据：空态是「真的没有班级」，不是读取失败
    await page.getByTestId('assessments-classes-error').getByRole('button', { name: '重试' }).click();
    await expect(page.getByTestId('assessments-classes-error')).toHaveCount(0);
    await expect(page.getByTestId('assessments-classes-empty')).toContainText('还没有班级');

    // 原卷步骤：读的是种子出来的**已确认**修订（真实数据，不是空表）
    const paperTab = page.getByRole('tab', { name: '2 原卷' });
    await paperTab.focus();
    await expect(paperTab).toBeFocused();
    await paperTab.press('Enter');
    await expect(paperTab).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('assessments-papers-panel')).toBeVisible();
    await expect(page.getByTestId(`assessments-paper-${current.paper.paperId}`)).toContainText(
      'F20-I 成绩样本卷',
    );
    await expect(page.getByTestId(`assessments-paper-${current.paper.paperId}`)).toContainText(
      '已确认',
    );

    // 成绩步骤：未选择施测时是明确空态（不是错误也不是假数据）
    await page.getByRole('tab', { name: '4 成绩' }).click();
    await expect(page.getByTestId('assessments-score-need-assessment')).toContainText('未选择施测');

    // 减少动画：全局 motion.css 机制对本模块元素同样生效
    await page.getByRole('tab', { name: '2 原卷' }).click();
    const card = page.getByTestId(`assessments-paper-${current.paper.paperId}`);
    const normal = await card.evaluate((el) => getComputedStyle(el).transitionDuration);
    expect(Number.parseFloat(normal)).toBeGreaterThan(0);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const reduced = await card.evaluate((el) => getComputedStyle(el).transitionDuration);
    expect(Number.parseFloat(reduced)).toBeLessThan(0.001);
    await page.emulateMedia({ reducedMotion: 'no-preference' });

    // 390px：页面级无横向溢出（矩阵/长文本容器自身可滚动，不撑破页面）
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(150);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth - innerWidth),
    ).toBeLessThanOrEqual(1);
    await page.screenshot({ path: testInfo.outputPath('assessments-390.png'), fullPage: true });
  });

  test('五步真实链：建班/选人次 → 选原卷 → 建施测 → 上传/映射/校对 → 承认 → 确认 → 历史矩阵', async ({
    page,
  }, testInfo) => {
    test.setTimeout(300_000);
    const current = await ensureBackend();
    backend = current;
    await gotoAssessments(page, current.origin);

    /* ---------- 步骤 1：名单（真实建班 + 4 名学生） ---------- */
    await page.getByRole('button', { name: '新建班级' }).click();
    await page.getByLabel('班级编码').fill('C-F20I');
    await page.getByLabel('班级名称').fill('F20-I 班级');
    await page.getByLabel('学年').fill('2026');
    await page.getByLabel('年级').fill('grade-1');
    await page.getByRole('button', { name: '建立班级', exact: true }).click();
    await expect(page.getByTestId('assessments-classes-empty')).toHaveCount(0);

    for (const [name, studentNo] of [
      ['甲学生', '0001'],
      ['乙学生', '0002'],
      ['丙学生', '0003'],
      ['丁学生', '0004'],
    ] as const) {
      await page.getByLabel('学生姓名').fill(name);
      await page.getByLabel('学生学号').fill(studentNo);
      await page.getByRole('button', { name: '添加学生' }).click();
      await expect(page.getByLabel('学生姓名')).toHaveValue('');
    }
    await expect(page.getByText('学号 0001')).toBeVisible();

    /* ---------- 步骤 2：原卷（只读选用已确认修订） ---------- */
    await page.getByRole('tab', { name: '2 原卷' }).click();
    await expect(page.getByTestId(`assessments-paper-${current.paper.paperId}`)).toBeVisible();
    await page.getByTestId(`assessments-select-paper-${current.paper.paperId}`).click();
    await expect(page.getByTestId('assessments-paper-selected')).toContainText('F20-I 成绩样本卷');

    /* ---------- 步骤 3：施测（建施测 + 丙学生缺考） ---------- */
    await page.getByRole('tab', { name: '3 施测' }).click();
    await page.getByLabel('施测标题').fill('F20-I 第一次月考');
    await page.getByLabel('施测日期').fill(todayIso());
    for (const name of ['甲学生', '乙学生', '丙学生', '丁学生']) {
      await expect(page.getByLabel(`参测 ${name}`)).toBeChecked();
    }
    await page.getByLabel('丙学生 出勤').selectOption('absent');
    await page.getByRole('button', { name: '创建施测' }).click();
    const createResult = page.getByTestId('assessments-create-result');
    await expect(createResult).toContainText('已创建施测');
    await expect(createResult).toContainText('4 人次');

    /* ---------- 步骤 4：成绩（上传 → 映射 → 校对 → 承认 → 确认） ---------- */
    await page.getByRole('tab', { name: '4 成绩' }).click();
    const xlsx = buildXlsx(SHEET_NAME, [SAMPLE_HEADER, ...SAMPLE_ROWS]);
    await page.getByLabel('成绩表格文件').setInputFiles({
      name: 'F20-I 成绩.xlsx',
      mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      buffer: xlsx,
    });
    await page.getByLabel('工作表名', { exact: true }).fill(SHEET_NAME);
    await page.getByRole('button', { name: /上传并创建待校对批次/ }).click();

    // 映射：显式写原表列字母（不依赖自动映射），保存后服务端重算预览
    await expect(page.getByLabel('映射工作表名')).toHaveValue(SHEET_NAME, { timeout: 30_000 });
    await page.getByLabel('学号列', { exact: true }).fill('A');
    await page.getByLabel('姓名列', { exact: true }).fill('B');
    await page.getByLabel('Q1 列字母').fill('C');
    await page.getByLabel('Q2 列字母').fill('D');
    await page.getByLabel('Q3 列字母').fill('E');
    await page.getByRole('button', { name: '保存映射并重算' }).click();
    await expect(page.getByTestId('assessments-mapping-notice')).toContainText('已保存映射并重算');

    // 校对：0 / 空白 必须显著区分（记录值 0 ≠ 空白）
    await expect(page.getByTestId('score-row-2')).toContainText('甲学生');
    await expect(page.getByTestId('score-cell-status-4-C')).toContainText('0');
    await expect(page.getByTestId('score-cell-status-4-C')).toHaveAttribute('data-status', 'recorded');
    await expect(page.getByTestId('score-cell-status-3-E')).toHaveAttribute('data-status', 'missing');
    await expect(page.getByTestId('score-cell-status-3-E')).toContainText('空白');
    // 每个单元格显示原表物理地址（行号 + 列字母）
    await expect(page.getByTestId('score-cell-3-E')).toContainText('第 3 行 · 列 E');

    // 422：把甲学生 Q1 改成 99（超过满分 2）→ 定位到该行该列且保留校对状态
    await page.getByLabel('第 2 行 列 C 校正').fill('99');
    await page.getByTestId('score-save-drafts').click();
    await expect(page.getByTestId('score-issue-list')).toContainText('原表第 2 行');
    await expect(page.getByTestId('score-issue-list')).toContainText('列 C');
    await expect(page.getByTestId('score-cell-2-C')).toHaveAttribute('data-issue', 'true');
    await expect(page.getByLabel('第 2 行 列 C 校正')).toHaveValue('99');

    // 修回合法值 + 「修正一格」：乙学生 Q2 由 3 改成 2.5
    await page.getByLabel('第 2 行 列 C 校正').fill('2');
    await page.getByLabel('第 3 行 列 D 校正').fill('2.5');

    // 409：另一处（例如另一位老师）先把批次改了一版 → 本页保存必须保留输入并提示刷新对照
    const assessmentId = await currentAssessmentId(page);
    const imports = await api(
      current.origin,
      `/api/v1/score-imports?assessmentId=${encodeURIComponent(assessmentId)}`,
    );
    const importId = (imports.body as { items: { importId: string }[] }).items[0].importId;
    const before = await api(current.origin, `/api/v1/score-imports/${importId}`);
    const revision = (before.body as { revision: number }).revision;
    const concurrent = await api(current.origin, `/api/v1/score-imports/${importId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        expectedRevision: revision,
        rows: [{ rowNo: 4, cells: [{ row: 4, column: 'D', text: '2.5' }] }],
      }),
    });
    expect(concurrent.status).toBe(200);

    await page.getByTestId('score-save-drafts').click();
    await expect(page.getByTestId('score-conflict')).toContainText('数据已变化，请刷新对照');
    await expect(page.getByLabel('第 3 行 列 D 校正')).toHaveValue('2.5'); // 用户输入原样保留

    await page.getByTestId('score-refresh-compare').click();
    await expect(page.getByLabel('第 3 行 列 D 校正')).toHaveValue('2.5'); // 显式刷新不覆盖输入
    // 另一位老师的修改（丁学生 Q2=2.5）在刷新后可见，绝不被本页草稿静默抹掉
    await expect(page.getByTestId('score-cell-status-4-D')).toContainText('2.5');
    await page.getByTestId('score-save-drafts').click();
    await expect(page.getByTestId('score-draft-notice')).toContainText('已保存校对');

    // 承认：逐班列举缺考人次 + 空白单元范围，勾选后才能提交
    await page.getByTestId('score-goto-acknowledge').click();
    await expect(page.getByTestId('score-ack-absences')).toContainText('丙学生');
    await expect(page.getByTestId('score-ack-absences')).toContainText('1 名缺考人次');
    await expect(page.getByTestId('score-ack-missing')).toContainText('1 个空白单元');
    await expect(page.getByTestId('score-ack-missing')).toContainText('乙学生');
    const openConfirm = page.getByTestId('score-open-confirm');
    await expect(openConfirm).toBeDisabled();
    await expect(page.getByTestId('score-ack-blocker')).toBeVisible();
    await page.getByLabel(/承认 .* 缺考 1 人次/).check();
    await page.getByLabel(/承认空白 1 个单元覆盖 1 人次/).check();
    await expect(openConfirm).toBeEnabled();

    await openConfirm.click();
    const dialog = page.getByRole('dialog', { name: '确认成绩入库' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByTestId('score-submission-id')).toBeVisible();
    const confirmRequest = page.waitForRequest(
      (request) => request.url().includes('/score-imports/') && request.url().endsWith('/confirm'),
    );
    await dialog.getByTestId('score-confirm-submit').click();
    const confirmBody = JSON.parse((await confirmRequest).postData() ?? '{}') as {
      submissionId: string;
      expectedImportRevision: number;
      expectedAssessmentRevision: number;
      previewVersion: number;
      absences: { classId: string; participantIds: string[] }[];
      missing: { participantIds: string[]; cellCount: number } | null;
    };
    // 逻辑确认：提交标识是 UUID，三个版本字段与承认范围都随请求发出
    expect(confirmBody.submissionId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
    expect(confirmBody.absences).toHaveLength(1);
    expect(confirmBody.absences[0].participantIds).toHaveLength(1);
    expect(confirmBody.missing).toMatchObject({ cellCount: 1 });
    expect(confirmBody.missing?.participantIds).toHaveLength(1);
    await expect(page.getByTestId('score-confirm-result')).toContainText('已确认入库', {
      timeout: 30_000,
    });
    await expect(page.getByTestId('score-import-state')).toContainText('已确认入库');

    /* ---------- 步骤 5：历史（修订列表 + 只读矩阵） ---------- */
    await page.getByRole('tab', { name: '5 历史' }).click();
    const revisionButton = page.locator('[data-testid^="assessments-revision-"]').first();
    await expect(revisionButton).toContainText('已确认（不可变）');
    await expect(page.getByTestId('assessments-matrix')).toBeVisible();

    const rowOf = (name: string) =>
      page.locator('[data-testid^="assessments-matrix-row-"]').filter({ hasText: name });
    await expect(rowOf('甲学生')).toContainText('9 / 10 分');
    await expect(rowOf('丁学生')).toContainText('7.5 / 10 分');
    // 只有当人次所有叶都 recorded 才有总分：乙（空白）与丙（缺考）不展示总分
    await expect(rowOf('乙学生')).toContainText('不展示总分');
    await expect(rowOf('乙学生')).not.toContainText('/ 10 分');
    await expect(rowOf('丙学生')).toContainText('不展示总分');
    // 四态在矩阵里仍显著区分：乙 1 个空白；丙 3 个缺考
    await expect(rowOf('乙学生').locator('[data-status="missing"]')).toHaveCount(1);
    await expect(rowOf('乙学生').locator('[data-status="recorded"]')).toHaveCount(2);
    await expect(rowOf('丙学生').locator('[data-status="absent"]')).toHaveCount(3);
    await expect(rowOf('丁学生').locator('[data-status="recorded"]')).toHaveCount(3);
    await expect(rowOf('丁学生').locator('[data-status="recorded"]').first()).toContainText('0');

    // 服务端事实核对：真实 API 返回的矩阵与页面一致（不是页面自说自话）
    const revisions = await api(
      current.origin,
      `/api/v1/assessments/${encodeURIComponent(await currentAssessmentId(page))}/score-revisions`,
    );
    const revisionList = (revisions.body as { items: { revisionId: string; version: number }[] }).items;
    expect(revisionList).toHaveLength(1);
    expect(revisionList[0].version).toBe(1);
    const matrix = await api(
      current.origin,
      `/api/v1/score-revisions/${revisionList[0].revisionId}/matrix?offset=0&limit=50`,
    );
    const matrixBody = matrix.body as {
      total: number;
      missingCellCount: number;
      missingParticipantIds: string[];
      absentClassIds: string[];
      rows: { participant: { name: string; totalUnits: number | null }; cells: { status: string }[] }[];
    };
    expect(matrixBody.total).toBe(4);
    expect(matrixBody.missingCellCount).toBe(1);
    expect(matrixBody.absentClassIds).toHaveLength(1);
    const byName = (name: string) => matrixBody.rows.find((row) => row.participant.name === name);
    expect(byName('甲学生')?.participant.totalUnits).toBe(900);
    expect(byName('丁学生')?.participant.totalUnits).toBe(750);
    expect(byName('乙学生')?.participant.totalUnits).toBeNull();
    expect(byName('丙学生')?.cells.every((cell) => cell.status === 'absent')).toBe(true);

    await page.screenshot({ path: testInfo.outputPath('assessments-history-1440.png'), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });

  test('完整真实链：名单导入→富原卷校对确认→施测→成绩响应丢失重放→修正历史', async ({ page }, testInfo) => {
    test.setTimeout(240_000);
    const current = await ensureBackend(); backend = current;
    const point = await api(current.origin, '/api/v1/knowledge-points', {
      method: 'POST', body: JSON.stringify({ subjectId: 'math', code: 'COMPLETE-CHAIN', name: '完整链有理数' }),
    });
    expect(point.status).toBe(201);
    const pointId = (point.body as {id: string}).id;
    await gotoAssessments(page, current.origin);
    await page.getByRole('button', { name: '新建班级', exact: true }).click();
    await page.getByLabel('班级编码').fill('COMPLETE');
    await page.getByLabel('班级名称').fill('完整导入班');
    await page.getByLabel('学年').fill('2026');
    await page.getByLabel('年级').fill('grade-1');
    await page.getByRole('button', { name: '建立班级', exact: true }).click();
    await page.getByLabel('名单文件').setInputFiles({ name: '完整名单.csv', mimeType: 'text/csv',
      buffer: Buffer.from('\ufeff学号,姓名\n01001,全链甲\n01002,全链乙\n01003,全链丙\n01004,全链丁\n') });
    await page.getByRole('button', { name: '上传名单', exact: true }).click();
    // 名单沿用 T30-a 的数据行序号（不含表头）；成绩仍用原表物理坐标。
    for (let row = 1; row <= 4; row += 1) await page.getByLabel(`第 ${row} 行处理`).selectOption('create');
    await page.getByRole('button', { name: '保存映射与行决策', exact: true }).click();
    await page.getByRole('button', { name: '确认名单', exact: true }).click();
    await expect(page.getByTestId('roster-import-result')).toContainText('名单已确认');
    await expect(page.getByText('学号 01001', { exact: true })).toBeVisible();

    await page.getByRole('tab', { name: '2 原卷' }).click();
    await page.getByLabel('原卷学科', { exact: true }).selectOption('math');
    const paperBytes = fs.readFileSync(current.completePaperFile);
    expect(paperBytes.length).toBeGreaterThan(0);
    await page.getByLabel('原卷DOCX文件').setInputFiles({ name: '完整原卷.docx',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      buffer: paperBytes });
    await page.getByRole('button', { name: '上传原卷并校对', exact: true }).click();
    await expect(page.getByLabel('原卷修订标题')).toBeVisible();
    await page.getByLabel('原卷修订标题').fill('完整链固定原卷');
    const source = page.getByRole('region', { name: '完整原文块' });
    await expect(source).toContainText('原文合并表头');
    await expect(source.locator('math[aria-label="原始公式"]').first()).toBeVisible();
    await expect(source.getByRole('img').first()).toBeVisible();
    for (const no of ['1','2','3']) await page.getByLabel(`题 ${no} 知识点`, {exact:true}).selectOption([pointId]);
    await page.getByRole('button', { name: '保存原卷草稿', exact: true }).click();
    await page.getByRole('button', { name: '确认原卷入库', exact: true }).click();
    await expect(page.getByTestId('paper-confirm-result')).toContainText('已确认');
    const selectedPaperText = await page.getByTestId('assessments-paper-selected').innerText();
    expect(selectedPaperText).toContain('完整链固定原卷');
    await page.screenshot({ path: testInfo.outputPath('complete-paper-1440.png'), fullPage: true });

    await page.getByRole('tab', { name: '3 施测' }).click();
    await page.getByLabel('施测标题').fill('完整链施测');
    await page.getByLabel('施测日期').fill(todayIso());
    await page.getByLabel('全链丙 出勤').selectOption('absent');
    await page.getByRole('button', { name: '创建施测', exact: true }).click();
    await expect(page.getByTestId('assessments-create-result')).toContainText('4 人次');
    const assessmentId = await currentAssessmentId(page);

    await page.getByRole('tab', { name: '4 成绩' }).click();
    await page.getByLabel('成绩表格文件').setInputFiles({ name: '全链成绩.csv', mimeType: 'text/csv',
      buffer: Buffer.from('\ufeff学号,姓名,1,2,3\n01001,全链甲,2,2,5\n01002,全链乙,2,3,\n01003,全链丙,缺考,,\n01004,全链丁,0,3,5\n') });
    await page.getByRole('button', { name: /上传并创建待校对批次/ }).click();
    await expect(page.getByTestId('score-cell-status-5-C')).toHaveAttribute('data-status', 'recorded');
    await expect(page.getByTestId('score-cell-status-4-D')).toHaveAttribute('data-status', 'absent');
    await page.getByTestId('score-goto-acknowledge').click();
    await expect(page.getByTestId('score-ack-missing')).toContainText('1 个空白单元');
    await page.getByLabel(/承认 .* 缺考 1 人次/).check();
    await page.getByLabel(/承认空白 1 个单元覆盖 1 人次/).check();
    await page.getByTestId('score-open-confirm').click();
    const confirms: { input: unknown; result: { revisionId: string; replayed: boolean } }[] = [];
    await page.route('**/api/v1/score-imports/*/confirm', async (route) => {
      const request = route.request(); const url = new URL(request.url());
      const response = await fetch(`${current.origin}${url.pathname}`, { method: 'POST',
        headers: { 'content-type': 'application/json' }, body: request.postData() });
      const text = await response.text();
      expect(response.status).toBe(200);
      confirms.push({ input: JSON.parse(request.postData() ?? '{}'), result: JSON.parse(text) });
      if (confirms.length === 1) await route.abort('failed');
      else await route.fulfill({ status: response.status, contentType: 'application/json', body: text });
    });
    const dialog = page.getByRole('dialog', { name: '确认成绩入库' });
    await dialog.getByTestId('score-confirm-submit').click();
    await expect(page.getByTestId('score-confirm-unknown')).toBeVisible();
    await dialog.getByTestId('score-confirm-submit').click();
    await expect(page.getByTestId('score-confirm-result')).toContainText('已确认（重放）');
    await expect(page.getByTestId('score-confirm-result')).toContainText('本次未重复写入');
    expect(confirms).toHaveLength(2); expect(confirms[1].input).toEqual(confirms[0].input);
    expect(confirms[1].result).toMatchObject({ revisionId: confirms[0].result.revisionId, replayed: true });
    const revisionId = confirms[0].result.revisionId;
    const oldRevision = await api(current.origin, `/api/v1/score-revisions/${revisionId}`);
    const oldMatrix = await api(current.origin, `/api/v1/score-revisions/${revisionId}/matrix`);
    expect((oldRevision.body as { paperRevisionId: string }).paperRevisionId).toBeTruthy();
    const assessment = await api(current.origin, `/api/v1/assessments/${assessmentId}`);
    expect((oldRevision.body as { paperRevisionId: string }).paperRevisionId)
      .toBe((assessment.body as {assessment:{paperRevisionId:string}}).assessment.paperRevisionId);
    await page.getByRole('tab', { name: '5 历史' }).click();
    await expect(page.getByTestId('assessments-matrix')).toBeVisible();
    // 人次和叶子身份从权威矩阵获取，再通过页面控件修正。
    const data = oldMatrix.body as {rows:{participant:{name:string;participantId:string}}[];items:{itemId:string;itemPath:string}[]};
    await page.getByLabel('修正人次').selectOption(data.rows.find((row) => row.participant.name === '全链甲')!.participant.participantId);
    await page.getByLabel('修正计分叶').selectOption(data.items.find((item) => item.itemPath === '1')!.itemId);
    await page.getByLabel('修正分数').fill('1.5');
    await page.getByRole('button', { name: '加入修正列表', exact: true }).click();
    await page.getByLabel('修正理由').fill('教师复核原表，第一小题实际为1.5分');
    await page.getByTestId('assessments-correct-submit').click();
    await expect(page.getByTestId('assessments-correct-result')).toContainText('已生成新版本 v2');
    expect((await api(current.origin, `/api/v1/score-revisions/${revisionId}`)).body).toEqual(oldRevision.body);
    expect((await api(current.origin, `/api/v1/score-revisions/${revisionId}/matrix`)).body).toEqual(oldMatrix.body);
    const history = await api(current.origin, `/api/v1/assessments/${assessmentId}/score-revisions`);
    expect((history.body as {items:unknown[]}).items).toHaveLength(2);
    await testInfo.attach('complete-chain-replay.json', { body: Buffer.from(JSON.stringify({ confirms, oldRevision:oldRevision.body, history:history.body }, null, 2)), contentType: 'application/json' });
    for (const size of [{width:1440,height:900},{width:1920,height:1080},{width:390,height:844}]) {
      await page.setViewportSize(size); await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.screenshot({ path:testInfo.outputPath(`complete-history-${size.width}.png`), fullPage:true });
      const layout = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
        offenders: Array.from(document.querySelectorAll<HTMLElement>('.assessments-page *'))
          .filter((el) => el.getBoundingClientRect().right > innerWidth + 1)
          .map((el) => ({ tag:el.tagName, className:el.className, width:el.getBoundingClientRect().width,
            right:el.getBoundingClientRect().right, text:el.textContent?.slice(0,80) })).slice(0,20) }));
      console.log(`[complete-layout] ${JSON.stringify(layout)}`);
      await testInfo.attach(`complete-layout-${size.width}.json`, {
        contentType:'application/json',body:Buffer.from(JSON.stringify(layout,null,2)) });
      expect(layout.scrollWidth <= layout.width).toBe(true);
    }
  });

  test('规模实测：200 人次 × 100 叶（分页 50/页，记录首屏与翻页耗时）', async ({ page }, testInfo) => {
    test.setTimeout(600_000);
    const current = await ensureBackend();
    backend = current;

    /* ---------- 直接 HTTP 准备 200 人次 × 100 叶，并完成一次真实确认 ---------- */
    const scene = await prepareScaleScene(current.origin, current.scalePaper, 200, 100);
    console.log(
      `[scale] 准备完成：assessment=${scene.assessmentId} import=${scene.importId} 人次=${scene.participantCount} 叶=${scene.leafCount}`,
    );

    /* ---------- 真实浏览器读回：只读矩阵首屏与翻页 ---------- */
    await gotoAssessments(page, current.origin);
    await page.getByRole('tab', { name: '3 施测' }).click();
    await page.getByTestId(`assessments-assessment-${scene.assessmentId}`).click();
    await page.getByRole('tab', { name: '5 历史' }).click();

    const startedAt = Date.now();
    await expect(page.locator('[data-testid^="assessments-revision-"]').first()).toContainText(
      '已确认（不可变）',
    );
    await expect(page.getByTestId('assessments-matrix')).toBeVisible();
    const matrixRows = page.locator('[data-testid^="assessments-matrix-row-"]');
    await expect(matrixRows).toHaveCount(50);
    const firstPaintMs = Date.now() - startedAt;
    await expect(page.getByTestId('assessments-matrix-page')).toContainText('共 200 人次');
    await expect(page.getByTestId('assessments-matrix-page')).toContainText('第 1 页');

    const turnStartedAt = Date.now();
    await page
      .getByTestId('assessments-history-panel')
      .getByRole('button', { name: '下一页' })
      .click();
    await expect(page.getByTestId('assessments-matrix-page')).toContainText('第 2 页');
    await expect(matrixRows).toHaveCount(50);
    const pageTurnMs = Date.now() - turnStartedAt;

    console.log(
      `[scale] ${scene.participantCount} 人次 × ${scene.leafCount} 叶：矩阵首屏（第 1 页 50 行）${firstPaintMs}ms；翻页 ${pageTurnMs}ms`,
    );
    testInfo.annotations.push({
      type: 'scale',
      description: `${scene.participantCount} 人次 × ${scene.leafCount} 叶：矩阵首屏 ${firstPaintMs}ms，翻页 ${pageTurnMs}ms（选择：服务端分页 50/页；100 叶经 iter_rows 修复后全链可用）`,
    });
    // 宽松上界：只拦"病理性卡顿"，不作为性能验收
    expect(firstPaintMs).toBeLessThan(20_000);
    expect(pageTurnMs).toBeLessThan(10_000);

    await page.screenshot({ path: testInfo.outputPath('assessments-scale-1440.png'), fullPage: false });
    const overflow = await page.evaluate(() => {
      const offenders: string[] = [];
      document.querySelectorAll<HTMLElement>('*').forEach((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.right > innerWidth + 1) {
          offenders.push(
            `${el.tagName}.${el.className || '-'} right=${Math.round(rect.right)} w=${Math.round(rect.width)}`,
          );
        }
      });
      const chain: string[] = [];
      let node: HTMLElement | null = document.querySelector<HTMLElement>('table.score-matrix');
      while (node) {
        const style = getComputedStyle(node);
        chain.push(
          `${node.tagName}.${String(node.className || '-')} w=${Math.round(node.getBoundingClientRect().width)} `
          + `scrollW=${node.scrollWidth} display=${style.display} overflowX=${style.overflowX} minW=${style.minWidth}`,
        );
        node = node.parentElement;
      }
      const positioned: string[] = [];
      document
        .querySelectorAll<HTMLElement>('.assessments-page *')
        .forEach((el) => {
          const style = getComputedStyle(el);
          if (style.position !== 'static') {
            positioned.push(
              `${el.tagName}.${String(el.className || '-')} position=${style.position} `
              + `w=${Math.round(el.getBoundingClientRect().width)} `
              + `left=${Math.round(el.getBoundingClientRect().left)}`,
            );
          }
        });
      const htmlWithTable = document.documentElement.scrollWidth;
      const table = document.querySelector<HTMLElement>('table.score-matrix');
      let htmlWithoutTable = htmlWithTable;
      if (table) {
        const display = table.style.display;
        table.style.display = 'none';
        htmlWithoutTable = document.documentElement.scrollWidth;
        table.style.display = display;
      }
      return {
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth,
        offenders: offenders.slice(0, 6),
        chain,
        positioned: positioned.slice(0, 12),
        htmlWithTable,
        htmlWithoutTable,
      };
    });
    console.log(`[scale] 溢出诊断 ${JSON.stringify(overflow)}`);
    expect(overflow.scrollWidth <= overflow.innerWidth).toBe(true);
  });
});

/* ------------------------------------------------------------------ 规模场景准备 */

async function prepareScaleScene(
  origin: string,
  paper: { paperId: string; revisionId: string; title: string },
  participantCount = 200,
  leafCount = 100,
): Promise<{ assessmentId: string; importId: string; participantCount: number; leafCount: number }> {
  const started = Date.now();
  const klass = await api(origin, '/api/v1/classes', {
    method: 'POST',
    body: JSON.stringify({ code: 'C-SCALE', name: '规模班', schoolYear: '2026', gradeId: 'grade-1' }),
  });
  expect(klass.status).toBe(201);
  const classId = (klass.body as { id: string }).id;

  const studentIds: string[] = [];
  for (let index = 1; index <= participantCount; index += 1) {
    // 学号全局唯一（上一用例已占用 0001…）：规模班用独立前缀，仍保持前导零文本
    const studentNo = `S${String(index).padStart(4, '0')}`;
    const created = await api(origin, '/api/v1/students', {
      method: 'POST',
      body: JSON.stringify({ name: `规模学生${studentNo}`, studentNo, classId }),
    });
    expect(created.status).toBe(201);
    studentIds.push((created.body as { id: string }).id);
  }

  console.log(`[scale] 班级 + ${participantCount} 名学生耗时 ${Date.now() - started}ms`);
  const assessmentCall = await api(origin, '/api/v1/assessments', {
    method: 'POST',
    body: JSON.stringify({
      submissionId: crypto.randomUUID(),
      paperRevisionId: paper.revisionId,
      title: '规模施测（200×10）',
      assessmentType: 'exam',
      heldOn: todayIso(),
      classIds: [classId],
      participants: studentIds.map((studentId) => ({
        studentId,
        classId,
        attendance: 'present',
        attemptNo: 1,
      })),
    }),
  });
  expect(assessmentCall.status).toBe(201);
  console.log(`[scale] 建施测耗时累计 ${Date.now() - started}ms`);
  const assessment = assessmentCall.body as {
    assessment: { assessmentId: string; revision: number };
  };

  // 计分叶（100 个）取自原卷固定修订内容，不硬编码 id
  const content = await api(
    origin,
    `/api/v1/papers/${paper.paperId}/revisions/${paper.revisionId}/content`,
  );
  expect(content.status).toBe(200);
  const leaves = (content.body as { items: { itemId: string; questionNo: string; isScored: boolean }[] })
    .items.filter((item) => item.isScored);
  expect(leaves.length).toBe(leafCount);

  const header: CellValue[] = ['学号', '姓名', ...leaves.map((leaf) => leaf.questionNo)];
  const rows: CellValue[][] = studentIds.map((_, index) => {
    const studentNo = `S${String(index + 1).padStart(4, '0')}`;
    return [studentNo, `规模学生${studentNo}`, ...leaves.map(() => 1)];
  });
  const xlsx = buildXlsx(SHEET_NAME, [header, ...rows]);

  const form = new FormData();
  form.append(
    'file',
    new Blob([new Uint8Array(xlsx)], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }),
    '规模成绩.xlsx',
  );
  form.append('workSheet', SHEET_NAME);
  const upload = await fetch(
    `${origin}/api/v1/assessments/${assessment.assessment.assessmentId}/score-imports`,
    { method: 'POST', body: form },
  );
  console.log(`[scale] 上传（${xlsx.length} 字节）返回，累计 ${Date.now() - started}ms`);
  const uploadText = await upload.text();
  expect(upload.status, `上传失败响应：${uploadText.slice(0, 400)}`).toBe(201);
  const importView = JSON.parse(uploadText) as {
    importId: string;
    revision: number;
    previewVersion: number;
    missingCellCount: number;
  };
  expect(importView.importId).toBeTruthy();

  console.log(`[scale] 上传解析完成，累计 ${Date.now() - started}ms`);
  const mapping = {
    expectedRevision: importView.revision,
    mapping: {
      workSheet: SHEET_NAME,
      headerRow: 1,
      studentNoColumn: 'A',
      nameColumn: 'B',
      itemColumns: leaves.map((leaf, index) => ({
        itemId: leaf.itemId,
        column: columnLetter(2 + index),
      })),
    },
  };
  const patched = await api(origin, `/api/v1/score-imports/${importView.importId}`, {
    method: 'PATCH',
    body: JSON.stringify(mapping),
  });
  expect(patched.status).toBe(200);
  const recalculated = patched.body as {
    revision: number;
    previewVersion: number;
    missingCellCount: number;
    resolvedRowCount: number;
    mapping: unknown;
  };
  expect(recalculated.mapping).toBeTruthy();
  console.log(`[scale] 映射重算完成，累计 ${Date.now() - started}ms（missing=${recalculated.missingCellCount} resolved=${recalculated.resolvedRowCount}）`);
  expect(recalculated.missingCellCount).toBe(0);
  expect(recalculated.resolvedRowCount).toBe(participantCount);

  const confirm = await api(origin, `/api/v1/score-imports/${importView.importId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({
      expectedImportRevision: recalculated.revision,
      expectedAssessmentRevision: assessment.assessment.revision,
      baseScoreRevisionId: null,
      previewVersion: recalculated.previewVersion,
      submissionId: crypto.randomUUID(),
      absences: [],
      missing: null,
    }),
  });
  console.log(`[scale] 确认返回 ${confirm.status}，累计 ${Date.now() - started}ms`);
  expect(confirm.status).toBe(200);
  expect((confirm.body as { state: string }).state).toBe('confirmed');

  return {
    assessmentId: assessment.assessment.assessmentId,
    importId: importView.importId,
    participantCount,
    leafCount,
  };
}

/** 从页面 URL/状态里取当前选中的施测 id（真实 API 断言用）。 */
async function currentAssessmentId(page: Page): Promise<string> {
  const chip = page.locator('.assessments-context .space-chip', { hasText: '施测：' });
  const text = await chip.innerText();
  const value = text.replace('施测：', '').trim();
  if (!value || value === '未选择') {
    throw new Error(`页面上没有选中的施测：${text}`);
  }
  return value;
}
