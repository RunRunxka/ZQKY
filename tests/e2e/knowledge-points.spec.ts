import { test, expect, type Page, type Route } from '@playwright/test';

/**
 * 知识点页（TEACHING-LOOP B2 · F10-KP）e2e。
 *
 * 后端不可达：全部 `/api/v1/**` 由本文件的确定性替身提供（未声明路由 → 404 并记录），
 * 覆盖：加载与导航、列表筛选、建立→列表出现、表格导入预览→整批确认、AI 候选六态与重试、
 * 409 冲突保留编辑、三视口（1440×900 / 1920×1080 / 390×844）无横向溢出、
 * 键盘可达与对话框 Esc 关闭焦点回落、prefers-reduced-motion 下过渡被压制。
 *
 * 真实后端与真实模型的端到端验收不在这里冒充。
 */

interface PointView {
  id: string;
  subjectId: string;
  code: string;
  name: string;
  description: string;
  parentId: string | null;
  parentCode: string | null;
  sortOrder: number;
  status: 'active' | 'archived';
  revision: number;
  revisionId: string | null;
  version: number;
  aliases: string[];
  createdAt: string;
}

interface ImportRowView {
  rowNo: number;
  name: string;
  code: string;
  parentCode: string | null;
  description: string;
  aliases: string[];
  targetKnowledgePointId: string | null;
  baseRevision: number | null;
  baseVersion: number | null;
  decision: 'create' | 'update' | 'ignore' | null;
  issues: { row?: number; column?: string; field?: string; code: string; message: string }[];
}

interface ImportView {
  importId: string;
  source: 'file' | 'ai';
  subjectId: string;
  state: 'uploaded' | 'reviewing' | 'confirmed' | 'failed' | 'cancelled';
  revision: number;
  fileAsset: {
    assetId: string;
    kind: 'attachment';
    blobKey: string;
    sha256: string;
    mediaType: string;
    byteSize: number;
    originalName: string;
  };
  headers: string[];
  mapping: Record<string, string>;
  warnings: string[];
  issues: { row?: number; column?: string; field?: string; code: string; message: string }[];
  rows: ImportRowView[];
  createdAt: string;
  updatedAt: string;
}

interface JobView {
  jobId: string;
  domain: 'knowledge';
  kind: string;
  attempt: number;
  state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'interrupted';
  result: Record<string, unknown> | null;
  error: { code: string; message: string; retryable?: boolean } | null;
}

interface StubState {
  points: PointView[];
  imports: ImportView[];
  requests: { method: string; path: string; body: string }[];
  /** 下一个 PATCH 知识点请求返回 409（随后恢复正常） */
  conflictOnce: boolean;
  /** GET /workflow-jobs 依次返回的状态（用尽后返回最后一条） */
  pollSequence: JobView[];
  pollIndex: number;
  submissionIds: string[];
  /** 下一次确认请求：服务端已写入但响应在传输中丢失（客户端只看到网络失败） */
  loseNextConfirmResponse: boolean;
  /** 落到未声明路径的请求（应为空；非空即说明有请求走了真实代理） */
  unhandled: string[];
}

const TAXONOMY = {
  stages: [{ id: 'stage-j', label: '初中' }],
  grades: [{ id: 'grade-7', label: '七年级', stageId: 'stage-j' }],
  subjects: [{ id: 'math', label: '数学' }],
  editions: [{ id: 'renjiao', label: '人教版' }],
};

const MODEL_CATALOG = {
  revision: 1,
  defaultChatProfileId: 'p-chat-1',
  connections: [
    {
      id: 'conn-1',
      displayName: '本机 Ollama',
      providerId: 'ollama',
      providerLabel: 'Ollama',
      protocol: 'openai-chat',
      apiFormat: 'auto',
      apiVersion: null,
      baseUrl: '',
      resolvedBaseUrl: 'http://localhost:11434/v1',
      hasCredential: false,
      hasManagedCredential: false,
      callable: true,
      callableReason: null,
      credentialScope: 'process',
      extraHeaderNames: [],
      createdAt: '2026-09-30T00:00:00Z',
      updatedAt: '2026-09-30T00:00:00Z',
    },
  ],
  profiles: [
    {
      id: 'p-chat-1',
      connectionId: 'conn-1',
      displayName: '本机问答',
      modelId: 'qwen2.5:7b',
      purpose: 'chat',
      contextTokens: 8192,
      maxOutputTokens: 2048,
      supportedParams: [],
      reasoningEnabled: null,
      reasoningEffort: null,
      reasoningStyle: null,
      capabilities: {},
      connection: {
        displayName: '本机 Ollama',
        providerId: 'ollama',
        providerLabel: 'Ollama',
        protocol: 'openai-chat',
        apiFormat: 'auto',
        hasCredential: false,
      },
      createdAt: '2026-09-30T00:00:00Z',
      updatedAt: '2026-09-30T00:00:00Z',
    },
  ],
};

function point(overrides: Partial<PointView> = {}): PointView {
  return {
    id: 'kp-1',
    subjectId: 'math',
    code: 'M.7.1',
    name: '有理数',
    description: '整数与分数',
    parentId: null,
    parentCode: null,
    sortOrder: 1,
    status: 'active',
    revision: 3,
    revisionId: 'kr-3',
    version: 2,
    aliases: ['有理数概念'],
    createdAt: '2026-09-30T00:00:00Z',
    ...overrides,
  };
}

function importRow(overrides: Partial<ImportRowView> = {}): ImportRowView {
  return {
    rowNo: 1,
    name: '数轴',
    code: 'M.7.2',
    parentCode: 'M.7',
    description: '',
    aliases: [],
    targetKnowledgePointId: null,
    baseRevision: null,
    baseVersion: null,
    decision: null,
    issues: [],
    ...overrides,
  };
}

function importView(overrides: Partial<ImportView> = {}): ImportView {
  return {
    importId: 'imp-file-1',
    source: 'file',
    subjectId: 'math',
    state: 'reviewing',
    revision: 2,
    fileAsset: {
      assetId: 'asset-1',
      kind: 'attachment',
      blobKey: 'blobs/abc',
      sha256: 'abc',
      mediaType: 'text/csv',
      byteSize: 128,
      originalName: '知识点.csv',
    },
    headers: ['编码', '名称', '父级'],
    mapping: { code: '编码', name: '名称', parentCode: '父级' },
    warnings: [],
    issues: [],
    rows: [importRow(), importRow({ rowNo: 2, code: 'M.7.3', name: '相反数' })],
    createdAt: '2026-09-30T00:00:00Z',
    updatedAt: '2026-09-30T00:00:00Z',
    ...overrides,
  };
}

function jobView(overrides: Partial<JobView> = {}): JobView {
  return {
    jobId: 'job-ai-1',
    domain: 'knowledge',
    kind: 'suggestion',
    attempt: 1,
    state: 'queued',
    result: null,
    error: null,
    ...overrides,
  };
}

function newState(overrides: Partial<StubState> = {}): StubState {
  return {
    points: [point()],
    imports: [importView()],
    requests: [],
    conflictOnce: false,
    pollSequence: [],
    pollIndex: 0,
    submissionIds: [],
    loseNextConfirmResponse: false,
    unhandled: [],
    ...overrides,
  };
}

function statePoints(state: StubState, url: URL): PointView[] {
  const q = url.searchParams.get('q');
  const subjectId = url.searchParams.get('subjectId');
  const status = url.searchParams.get('status');
  return state.points.filter((item) => {
    if (subjectId && item.subjectId !== subjectId) return false;
    if (status && item.status !== status) return false;
    if (q && !`${item.code} ${item.name} ${item.aliases.join(' ')}`.includes(q)) return false;
    return true;
  });
}

/** 替身回复：`abort` 表示「服务端已处理但响应在传输中丢失」（客户端只看到网络失败）。 */
type StubReply = { status: number; body: unknown } | 'abort';

/**
 * 统一替身：本页会发的每个请求都必须在这里声明（未声明的记入 `state.unhandled`
 * 并返回 404），绝不依赖真实代理（127.0.0.1:8000）不存在时的 ECONNREFUSED。
 */
async function stubApi(page: Page, state: StubState) {
  await page.route('**/api/v1/**', async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    state.requests.push({ method, path: `${path}${url.search}`, body: request.postData() ?? '' });

    const reply = dispatch(route, state, url, path, method);
    if (reply === 'abort') {
      await route.abort('failed');
      return;
    }
    await route.fulfill({
      status: reply.status,
      contentType: 'application/json',
      json: reply.body as object,
    });
  });
}

/** 未声明的路径：记录 + 404（供用例末尾 `expectNoUnhandled` 断言）。 */
function unhandled(state: StubState, method: string, path: string): StubReply {
  state.unhandled.push(`${method} ${path}`);
  return {
    status: 404,
    body: {
      code: 'UNHANDLED_E2E_ROUTE',
      message: `${method} ${path} 未在 e2e 替身中声明`,
      retryable: false,
    },
  };
}

/** 断言本用例期间没有任何请求落到未声明路径（也即没有请求走真实代理）。 */
function expectNoUnhandled(state: StubState) {
  expect(state.unhandled).toEqual([]);
}

function dispatch(
  route: Route,
  state: StubState,
  url: URL,
  path: string,
  method: string,
): StubReply {
  const request = route.request();

  const json = (status: number, body: unknown): StubReply => ({ status, body });

  if (method === 'GET' && path === '/api/v1/textbook-taxonomy') return json(200, TAXONOMY);
  if (method === 'GET' && path === '/api/v1/model-catalog') return json(200, MODEL_CATALOG);
  // 教材依据选择器会读书册列表（没有书册时给出空列表，不落到未声明路径）
  if (method === 'GET' && path === '/api/v1/textbooks') return json(200, { documents: [] });
  if (method === 'GET' && path === '/api/v1/knowledge-points') {
    const items = statePoints(state, url);
    return json(200, { items, total: items.length, offset: 0, limit: 100 });
  }
  if (method === 'POST' && path === '/api/v1/knowledge-points') {
    const body = JSON.parse(request.postData() ?? '{}') as Record<string, unknown>;
    const created = point({
      id: `kp-${state.points.length + 1}`,
      code: String(body.code),
      name: String(body.name),
      description: typeof body.description === 'string' ? body.description : '',
      aliases: Array.isArray(body.aliases) ? (body.aliases as string[]) : [],
      revision: 1,
      revisionId: `kr-new-${state.points.length + 1}`,
      version: 1,
    });
    state.points = [...state.points, created];
    return json(201, created);
  }
  if (path.startsWith('/api/v1/knowledge-points/')) {
    const rest = path.slice('/api/v1/knowledge-points/'.length);
    if (rest.endsWith('/textbook-links')) {
      return json(200, { items: [] });
    }
    const id = decodeURIComponent(rest);
    const found = state.points.find((item) => item.id === id);
    if (method === 'GET') {
      return found
        ? json(200, found)
        : json(404, { code: 'KNOWLEDGE_NOT_FOUND', message: '不存在。' });
    }
    if (method === 'PATCH') {
      const body = JSON.parse(request.postData() ?? '{}') as Record<string, unknown>;
      if (state.conflictOnce) {
        state.conflictOnce = false;
        return json(409, {
          code: 'REVISION_CONFLICT',
          message: '知识点已被其他操作更新（当前 revision=7），请刷新后重试。',
          retryable: false,
          details: { currentRevision: 7 },
        });
      }
      const updated: PointView = {
        ...(found ?? point()),
        name: typeof body.name === 'string' ? body.name : (found?.name ?? ''),
        description:
          typeof body.description === 'string'
            ? body.description
            : Array.isArray(body.clearFields) &&
                (body.clearFields as string[]).includes('description')
              ? ''
              : (found?.description ?? ''),
        revision: (found?.revision ?? 3) + 1,
        revisionId: 'kr-updated',
        version: (found?.version ?? 2) + 1,
      };
      state.points = state.points.map((item) => (item.id === updated.id ? updated : item));
      return json(200, updated);
    }
  }
  if (method === 'GET' && path === '/api/v1/knowledge-imports') {
    const items = state.imports.map((item) => ({
      importId: item.importId,
      source: item.source,
      subjectId: item.subjectId,
      state: item.state,
      revision: item.revision,
      rowCount: item.rows.length,
      blockingIssueCount: item.rows.flatMap((row) => row.issues).length,
      createdAt: item.createdAt,
      updatedAt: item.updatedAt,
    }));
    return json(200, { items, total: items.length, offset: 0, limit: 100 });
  }
  if (method === 'POST' && path === '/api/v1/knowledge-imports') {
    const created = importView({ importId: 'imp-file-1' });
    state.imports = [
      created,
      ...state.imports.filter((item) => item.importId !== created.importId),
    ];
    return json(201, created);
  }
  if (path.startsWith('/api/v1/knowledge-imports/')) {
    const rest = path.slice('/api/v1/knowledge-imports/'.length);
    const [id, action] = rest.split('/');
    const view = state.imports.find((item) => item.importId === decodeURIComponent(id));
    if (method === 'GET' && !action) {
      return view
        ? json(200, view)
        : json(404, { code: 'KNOWLEDGE_IMPORT_NOT_FOUND', message: '不存在。' });
    }
    if (method === 'PATCH' && view) {
      const body = JSON.parse(request.postData() ?? '{}') as {
        rows?: { rowNo: number; decision: 'create' | 'update' | 'ignore' }[];
      };
      const updated: ImportView = {
        ...view,
        revision: view.revision + 1,
        rows: view.rows.map((row) => {
          const patch = body.rows?.find((item) => item.rowNo === row.rowNo);
          return patch ? { ...row, decision: patch.decision } : row;
        }),
      };
      state.imports = state.imports.map((item) =>
        item.importId === updated.importId ? updated : item,
      );
      return json(200, updated);
    }
    if (method === 'POST' && action === 'confirm' && view) {
      const body = JSON.parse(request.postData() ?? '{}') as { submissionId: string };
      // 服务端按 (owner, operation, submissionId) 幂等：同 id 的第二次提交必然命中重放
      const attempt = state.submissionIds.length;
      state.submissionIds.push(body.submissionId);
      if (state.loseNextConfirmResponse) {
        // 服务端已写入，但响应在传输中丢失：客户端只看到网络失败（status 0）
        state.loseNextConfirmResponse = false;
        state.imports = state.imports.map((item) =>
          item.importId === view.importId
            ? { ...item, state: 'confirmed', revision: item.revision + 1 }
            : item,
        );
        return 'abort';
      }
      const replayed = attempt > 0;
      state.imports = state.imports.map((item) =>
        item.importId === view.importId
          ? { ...item, state: 'confirmed', revision: item.revision + (replayed ? 0 : 1) }
          : item,
      );
      return json(200, {
        importId: view.importId,
        state: 'confirmed',
        created: replayed
          ? []
          : view.rows.map((row, index) => ({
              rowNo: row.rowNo,
              knowledgePointId: `kp-created-${index}`,
              revisionId: `kr-created-${index}`,
              version: 1,
            })),
        updated: [],
        ignored: replayed ? [] : [],
        replayed,
      });
    }
  }
  if (method === 'POST' && path === '/api/v1/knowledge-suggestion-jobs') {
    return json(202, jobView({ state: 'queued', attempt: 1 }));
  }
  if (path === '/api/v1/workflow-jobs/job-ai-1/retry' && method === 'POST') {
    return json(200, jobView({ state: 'running', attempt: 2 }));
  }
  if (path === '/api/v1/workflow-jobs/job-ai-1' && method === 'GET') {
    const index = Math.min(state.pollIndex, state.pollSequence.length - 1);
    state.pollIndex += 1;
    return json(200, state.pollSequence[index] ?? jobView({ state: 'running' }));
  }
  return unhandled(state, method, path);
}

async function gotoPage(page: Page, state: StubState) {
  await stubApi(page, state);
  await page.goto('/knowledge-points');
  await expect(page.getByRole('heading', { name: '知识点', level: 1 })).toBeVisible();
}

test.describe('知识点页', () => {
  test('页面加载、页签与列表；侧栏当前项唯一高亮为「知识点」', async ({ page }, testInfo) => {
    const state = newState();
    await gotoPage(page, state);

    await expect(page.getByRole('tab', { name: '知识点' })).toBeVisible();
    await expect(page.getByRole('tab', { name: '表格导入' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'AI 候选' })).toBeVisible();
    await expect(page.getByText('有理数')).toBeVisible();

    // 总控已登记 /knowledge-points：桌面侧栏必须恰好一个当前项且是「知识点」（R-04）
    const nav = page.locator('nav[aria-label="项目功能导航"]');
    await expect(nav.locator('[aria-current="page"]')).toHaveCount(1);
    await expect(nav.locator('[aria-current="page"]')).toHaveAttribute('aria-label', /^知识点/);

    await page.screenshot({
      path: testInfo.outputPath('knowledge-points-1440.png'),
      fullPage: true,
    });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    expectNoUnhandled(state);
  });

  test('列表筛选：关键字与状态过滤走服务端参数，空结果给空态而非错误', async ({ page }) => {
    const state = newState({
      points: [point(), point({ id: 'kp-2', code: 'M.7.9', name: '近似数' })],
    });
    await gotoPage(page, state);

    await page.getByLabel('按关键字搜索知识点').fill('近似');
    await page.getByRole('button', { name: '搜索' }).click();

    await expect(page.getByText('近似数')).toBeVisible();
    await expect(page.getByText('有理数')).toHaveCount(0);
    expect(
      state.requests.some(
        (item) => item.method === 'GET' && item.path.includes('q=%E8%BF%91%E4%BC%BC'),
      ),
    ).toBe(true);

    // 无结果的筛选：成功 + 0 条 → 空态（不是失败，也不是伪造数据）。
    // 注意：Next RouteAnnouncer 全站常驻一个空的 role=alert，不能按全页 alert 数量断言；
    // 这里按页面自己的错误横幅 testid 断言「没有错误态」。
    await page.getByLabel('按关键字搜索知识点').fill('不存在的知识点');
    await page.getByRole('button', { name: '搜索' }).click();
    await expect(page.getByText('没有符合条件的数据')).toBeVisible();
    await expect(page.getByTestId('kp-list-error')).toHaveCount(0);
    expectNoUnhandled(state);
  });

  test('建立知识点 → 对话框关闭、列表出现新条目并选中详情', async ({ page }) => {
    const state = newState();
    await gotoPage(page, state);

    await page.getByRole('button', { name: /新建知识点/ }).click();
    const dialog = page.getByRole('dialog', { name: '新建知识点' });
    await expect(dialog).toBeVisible();
    // exact：避免「编码」被「父级编码」子串命中（Playwright name 默认子串匹配）
    await dialog.getByLabel('学科', { exact: true }).selectOption('math');
    await dialog.getByLabel('编码', { exact: true }).fill('M.7.5');
    await dialog.getByLabel('名称', { exact: true }).fill('绝对值');
    await dialog.getByRole('button', { name: /建立知识点/ }).click();

    await expect(dialog).toHaveCount(0);
    // 列表出现新条目，且新对象被选中（详情标题与列表条目同时存在，分别断言）
    await expect(page.locator('.kp-card').filter({ hasText: '绝对值' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '绝对值', level: 2 })).toBeVisible();
    await expect(page.getByTestId('kp-revision-id')).toBeVisible();
    const created = state.requests.find(
      (item) => item.method === 'POST' && item.path === '/api/v1/knowledge-points',
    );
    expect(created?.body).toContain('"code":"M.7.5"');
    expectNoUnhandled(state);
  });

  test('表格导入：上传 → 预览行校对 → 整批确认；响应丢失后同标识重试命中「已确认（重放）」', async ({
    page,
  }) => {
    const state = newState({ imports: [], loseNextConfirmResponse: true });
    await gotoPage(page, state);

    await page.getByRole('tab', { name: '表格导入' }).click();
    await expect(page.getByText('还没有导入批次')).toBeVisible();

    await page.getByRole('button', { name: /上传表格/ }).click();
    const dialog = page.getByRole('dialog', { name: '上传知识点表格' });
    await dialog.getByLabel('表格文件').setInputFiles({
      name: '知识点.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('编码,名称,父级\nM.7.2,数轴,M.7\nM.7.3,相反数,M.7', 'utf8'),
    });
    await dialog.getByLabel('批次学科').selectOption('math');
    await dialog.getByRole('button', { name: /上传并解析/ }).click();

    // 文件名只在选中批次的校对面板里出现：先点批次卡，再按稳定 testid 断言
    await page.getByTestId('kp-import-card-imp-file-1').click();
    await expect(page.getByTestId('kp-import-file')).toHaveText('知识点.csv');

    // 预览：表头映射、行与定位
    await expect(page.getByRole('region', { name: '表头映射' })).toBeVisible();
    await expect(page.getByTestId('kp-row-1')).toContainText('数轴');
    await expect(page.getByTestId('kp-row-2')).toContainText('相反数');

    // 确认入口在未选择动作前不可用
    const confirmButton = page.getByRole('button', { name: '整批确认入库' });
    await expect(confirmButton).toBeDisabled();
    await page.getByLabel('第 1 行处理动作').selectOption('create');
    await page.getByLabel('第 2 行处理动作').selectOption('ignore');
    await expect(confirmButton).toBeEnabled();

    await confirmButton.click();
    const confirmDialog = page.getByRole('dialog', { name: '整批确认入库' });
    await expect(confirmDialog).toBeVisible();
    // 限定在弹窗内并 exact：页面上的「整批确认入库」含相同子串，不能用 first() 掩盖
    const confirmInDialog = confirmDialog.getByRole('button', { name: '确认入库', exact: true });

    // 第一次提交：服务端已写入但响应丢失 → 页面只看到网络失败，如实说「结果未知」，
    // 不谎称「没有写入」，也不冒充成功（没有 kp-confirm-result）。
    await confirmInDialog.click();
    await expect(page.getByText(/确认结果未知（SERVICE_UNAVAILABLE）/)).toBeVisible();
    await expect(page.getByText(/同一个提交标识会按幂等处理/)).toBeVisible();
    await expect(page.getByTestId('kp-confirm-result')).toHaveCount(0);
    await expect(confirmDialog).toBeVisible();

    // 第二次提交（用户重试）：同一提交标识 → 服务端命中重放
    await confirmInDialog.click();
    await expect(confirmDialog).toHaveCount(0);
    const result = page.getByTestId('kp-confirm-result');
    await expect(result).toContainText('已确认（重放）');
    await expect(result).toContainText('未重复写入');
    await expect(page.getByTestId('kp-import-state')).toHaveText('已确认入库');
    await expect(page.getByRole('button', { name: '整批确认入库' })).toBeDisabled();

    // 幂等标识：两次提交必须是同一个 id，且形状是 UUID
    expect(state.submissionIds).toHaveLength(2);
    expect(state.submissionIds[1]).toBe(state.submissionIds[0]);
    expect(state.submissionIds[0]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
    expectNoUnhandled(state);
  });

  test('AI 候选：进行中/中断/重试/成功四态展示 → 成功后切到候选批次', async ({ page }) => {
    const state = newState({
      imports: [],
      pollSequence: [
        jobView({ state: 'running', attempt: 1 }),
        jobView({ state: 'interrupted', attempt: 1 }),
        // 重试后的新尝试先保持 running（可观察到「生成中」），再收敛到 succeeded
        jobView({ state: 'running', attempt: 2 }),
        jobView({
          state: 'succeeded',
          attempt: 2,
          result: { importId: 'imp-ai-1', candidateCount: 3 },
        }),
      ],
    });
    // AI 批次在候选成功后才会出现
    state.imports = [
      importView({
        importId: 'imp-ai-1',
        source: 'ai',
        rows: [importRow({ code: 'M.7.9', name: '近似数' })],
      }),
    ];
    await gotoPage(page, state);

    // 学科：工具栏筛选联动到 AI 候选表单（同一条真实字典；未选择时后端必填，页面如实报错）
    await page.getByLabel('按学科筛选').selectOption('math');

    await page.getByRole('tab', { name: 'AI 候选' }).click();
    await expect(page.getByTestId('kp-suggestion-model')).toContainText('使用');
    await page.getByLabel('新增资料文本').fill('有理数与数轴的定义');
    await page.getByRole('button', { name: '添加资料块' }).click();
    const subjectSelect = page.getByLabel('批次学科');
    await expect(subjectSelect).toHaveValue('math');
    await page.getByRole('button', { name: /发起 AI 候选/ }).click();

    // 进行中：任务提交后按钮让位给「取消任务」，页面持续观察（离页只停止观察，不取消任务）
    await expect(page.getByTestId('kp-suggestion-state')).toHaveText('生成中');
    await expect(page.getByText(/任务在后台执行（生成中）/)).toBeVisible();
    await expect(page.getByRole('button', { name: '取消任务' })).toBeVisible();

    // 中断：显式横幅 + 重试入口，且提示不自动重跑
    await expect(page.getByTestId('kp-interrupted')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('kp-interrupted')).toContainText('候选已中断（无执行器在跑）');
    await expect(page.getByTestId('kp-suggestion-state')).toHaveText('已中断');
    await expect(page.getByText('观察中…')).toHaveCount(0);

    await page.getByRole('button', { name: /重试（沿用冻结模型）/ }).click();
    // 重试后的新尝试仍在进行（按新 attempt 继续观察，不沿用旧尝试结果）
    await expect(page.getByText(/任务在后台执行（生成中）/)).toBeVisible();
    await expect(page.getByRole('button', { name: '取消任务' })).toBeVisible();

    // 成功后自动切到「表格导入」的候选批次
    await expect(page.getByRole('tab', { name: '表格导入' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(page.getByTestId('kp-ai-banner')).toContainText('候选尚未入库');
    await expect(page.getByTestId('kp-import-review')).toHaveClass(/ai/);
    expect(
      state.requests.some((item) => item.method === 'POST' && item.path.endsWith('/retry')),
    ).toBe(true);
    expectNoUnhandled(state);
  });

  test('409 冲突：提示当前版本并刷新，用户输入保留', async ({ page }) => {
    const state = newState();
    await gotoPage(page, state);
    state.conflictOnce = true;

    await page.getByText('有理数').click();
    const nameInput = page.getByLabel('名称');
    await expect(nameInput).toHaveValue('有理数');
    await nameInput.fill('我改的名字');
    await page.getByRole('button', { name: /保存修改/ }).click();

    const conflict = page.getByTestId('kp-conflict');
    await expect(conflict).toBeVisible();
    await expect(conflict).toContainText('当前版本 7，已刷新为最新，请重试。');
    await expect(nameInput).toHaveValue('我改的名字');

    // 按服务端最新版本重试成功
    await page.getByRole('button', { name: '保留我的修改并重试' }).click();
    await expect(page.getByTestId('kp-detail-notice')).toContainText('已保存');
    await expect(page.getByTestId('kp-revision-id')).toContainText('kr-updated');
    expectNoUnhandled(state);
  });

  test('键盘可达与对话框 Esc：Tab 到主要控件，Esc 关闭并回落到打开按钮', async ({ page }) => {
    const state = newState();
    await gotoPage(page, state);

    const createButton = page.getByRole('button', { name: /新建知识点/ });
    await createButton.focus();
    await expect(createButton).toBeFocused();
    await createButton.press('Enter');
    const dialog = page.getByRole('dialog', { name: '新建知识点' });
    await expect(dialog).toBeVisible();

    // Esc 关闭（原生 dialog cancel）并把焦点还给打开它的按钮
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(createButton).toBeFocused();

    // 主要控件都可通过键盘聚焦
    for (const label of ['按学科筛选', '按关键字搜索知识点']) {
      await page.getByLabel(label).focus();
      await expect(page.getByLabel(label)).toBeFocused();
    }
    expectNoUnhandled(state);
  });

  test('三视口无横向溢出；390px 页面级溢出 ≤1px', async ({ page }, testInfo) => {
    const state = newState();
    await gotoPage(page, state);
    await page.getByText('有理数').click();
    await expect(page.getByTestId('kp-revision-id')).toBeVisible();

    for (const viewport of [
      { width: 1440, height: 900 },
      { width: 1920, height: 1080 },
    ]) {
      await page.setViewportSize(viewport);
      await page.waitForTimeout(120);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
    }

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(120);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth - innerWidth),
    ).toBeLessThanOrEqual(1);
    await page.screenshot({
      path: testInfo.outputPath('knowledge-points-390.png'),
      fullPage: true,
    });

    // 移动端可继续操作：切页签 → 选中批次 → 预览可见 → 回到知识点
    await page.getByRole('tab', { name: '表格导入' }).click();
    await page.getByTestId('kp-import-card-imp-file-1').click();
    await expect(page.getByTestId('kp-import-file')).toHaveText('知识点.csv');
    await page.getByRole('tab', { name: '知识点' }).click();
    await expect(page.getByTestId('kp-revision-id')).toBeVisible();
    expectNoUnhandled(state);
  });

  test('prefers-reduced-motion 下过渡被压制（全局 motion.css 生效）', async ({ page }) => {
    const state = newState();
    await gotoPage(page, state);
    const card = page.locator('.kp-card').first();
    await expect(card).toBeVisible();

    const normal = await card.evaluate((el) => getComputedStyle(el).transitionDuration);
    expect(Number.parseFloat(normal)).toBeGreaterThan(0);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const reduced = await card.evaluate((el) => getComputedStyle(el).transitionDuration);
    expect(Number.parseFloat(reduced)).toBeLessThan(0.001);
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    expectNoUnhandled(state);
  });
});
