import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { KnowledgeImportRowView, KnowledgeImportView } from '@/contracts/knowledge';
import { ImportReviewPanel } from './ImportReviewPanel';

function row(overrides: Partial<KnowledgeImportRowView> = {}): KnowledgeImportRowView {
  return {
    rowNo: 1,
    name: '有理数',
    code: 'M.1',
    parentCode: null,
    description: '整数与分数',
    aliases: [],
    targetKnowledgePointId: null,
    baseRevision: null,
    baseVersion: null,
    decision: null,
    issues: [],
    ...overrides,
  };
}

function importView(overrides: Partial<KnowledgeImportView> = {}): KnowledgeImportView {
  return {
    importId: 'imp-1',
    source: 'file',
    subjectId: 'math',
    state: 'reviewing',
    revision: 2,
    fileAsset: {
      assetId: 'asset-1',
      kind: 'attachment',
      blobKey: 'blobs/deadbeef',
      sha256: 'deadbeef',
      mediaType: 'text/csv',
      byteSize: 120,
      originalName: '知识点.csv',
    },
    headers: ['编码', '名称'],
    mapping: { code: '编码', name: '名称' },
    warnings: [],
    issues: [],
    rows: [row()],
    createdAt: '2026-09-30T00:00:00Z',
    updatedAt: '2026-09-30T00:00:00Z',
    ...overrides,
  };
}

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function jsonResponse(ok: boolean, status: number, body: unknown): Response {
  return { ok, status, json: async () => body } as Response;
}

function stubApi(handler: Handler) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function calls(fetchMock: ReturnType<typeof stubApi>, fragment: string, method?: string) {
  return fetchMock.mock.calls.filter(([url, init]) => {
    const request = init as RequestInit | undefined;
    return String(url).includes(fragment) && (!method || request?.method === method);
  });
}

function bodyAt(
  fetchMock: ReturnType<typeof stubApi>,
  fragment: string,
  method: string,
  index = 0,
) {
  const matched = calls(fetchMock, fragment, method);
  return JSON.parse(String((matched[index]?.[1] as RequestInit).body)) as Record<string, unknown>;
}

/** 按「方法 + 精确路径」路由；未声明的请求显式失败。 */
function router(view: KnowledgeImportView, overrides: Record<string, Handler> = {}) {
  return stubApi((url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    for (const [key, handler] of Object.entries(overrides)) {
      const prefix = key.slice(method.length + 1);
      if (key.startsWith(`${method} `) && url === prefix) return handler(url, init);
    }
    if (method === 'GET' && url === '/api/v1/knowledge-imports/imp-1') {
      return jsonResponse(true, 200, view);
    }
    return jsonResponse(false, 500, {
      code: 'UNEXPECTED_TEST_REQUEST',
      message: `${method} ${url} 未在测试路由中声明`,
    });
  });
}

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close() {
    this.open = false;
  };
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('导入预览：行校对与整批确认', () => {
  it('行问题按行列定位；存在未选择动作/阻断问题时确认入口不可用', async () => {
    router(
      importView({
        rows: [
          row({ rowNo: 1 }),
          row({
            rowNo: 2,
            code: 'M.2',
            name: '',
            decision: 'create',
            issues: [
              {
                row: 2,
                column: '名称',
                field: 'name',
                code: 'KNOWLEDGE_ROW_MISSING_NAME',
                message: '缺少知识点名称（name）。',
              },
            ],
          }),
        ],
      }),
    );
    render(<ImportReviewPanel importId="imp-1" />);

    expect(await screen.findByTestId('kp-row-2')).toBeInTheDocument();
    expect(
      screen.getByText(/第 2 行 · 列「名称」：KNOWLEDGE_ROW_MISSING_NAME：缺少知识点名称/),
    ).toBeInTheDocument();
    expect(screen.getByTestId('kp-import-blocking')).toHaveTextContent('阻断问题 1');
    expect(screen.getByRole('button', { name: '整批确认入库' })).toBeDisabled();
    expect(screen.getByText(/还有 1 行没有选定动作/)).toBeInTheDocument();
  });

  it('选动作保存只提交已选择的行（不把未选择行静默改成 ignore）', async () => {
    const fetchMock = router(
      importView({
        rows: [row({ rowNo: 1 }), row({ rowNo: 2, code: 'M.2' })],
      }),
      {
        'PATCH /api/v1/knowledge-imports/imp-1': () =>
          jsonResponse(true, 200, importView({ revision: 3 })),
      },
    );
    render(<ImportReviewPanel importId="imp-1" />);

    fireEvent.change(await screen.findByLabelText('第 1 行处理动作'), {
      target: { value: 'create' },
    });
    fireEvent.click(screen.getByRole('button', { name: /保存校对（1 行）/ }));

    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-imports/imp-1', 'PATCH')).toHaveLength(1),
    );
    expect(bodyAt(fetchMock, '/knowledge-imports/imp-1', 'PATCH')).toEqual({
      expectedRevision: 2,
      rows: [{ rowNo: 1, decision: 'create', expectedRevision: null }],
    });
  });

  it('整批确认提交 actions + 幂等 submissionId；重放显示「已确认（重放）」', async () => {
    const fakeUuid = vi
      .spyOn(crypto, 'randomUUID')
      .mockImplementation(() => 'sub-fixed' as `${string}-${string}-${string}-${string}-${string}`);
    const fetchMock = router(
      importView({
        rows: [
          row({ rowNo: 1, decision: 'create' }),
          row({
            rowNo: 2,
            code: 'M.old',
            decision: 'update',
            targetKnowledgePointId: 'kp-9',
            baseRevision: 5,
            baseVersion: 2,
          }),
          row({ rowNo: 3, code: 'M.3', decision: 'ignore' }),
        ],
      }),
      {
        'POST /api/v1/knowledge-imports/imp-1/confirm': () =>
          jsonResponse(true, 200, {
            importId: 'imp-1',
            state: 'confirmed',
            created: [{ rowNo: 1, knowledgePointId: 'kp-1', revisionId: 'kr-1', version: 1 }],
            updated: [{ rowNo: 2, knowledgePointId: 'kp-9', revisionId: 'kr-9', version: 3 }],
            ignored: [3],
            replayed: false,
          }),
      },
    );
    render(<ImportReviewPanel importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: '整批确认入库' }));
    expect(await screen.findByText(/提交标识：sub-fixed/)).toBeInTheDocument();

    // 弹窗内按钮与页面级入口的可访问名称必须不同（否则 e2e 的 name 子串匹配会命中两个）
    const dialog = screen.getByRole('dialog', { name: '整批确认入库' });
    const confirmInDialog = within(dialog).getByRole('button', { name: '确认入库' });
    expect(confirmInDialog).toHaveAccessibleName('确认入库');
    expect(screen.getByRole('button', { name: '整批确认入库' })).toHaveAccessibleName(
      '整批确认入库',
    );

    fireEvent.click(confirmInDialog);

    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-imports/imp-1/confirm', 'POST')).toHaveLength(1),
    );
    expect(bodyAt(fetchMock, '/knowledge-imports/imp-1/confirm', 'POST')).toEqual({
      expectedRevision: 2,
      submissionId: 'sub-fixed',
      actions: [
        { rowNo: 1, decision: 'create', expectedRevision: null },
        { rowNo: 2, decision: 'update', expectedRevision: 5 },
        { rowNo: 3, decision: 'ignore', expectedRevision: null },
      ],
    });
    expect(await screen.findByTestId('kp-confirm-result')).toHaveTextContent(
      '已确认入库：新建 1 条、更新 1 条、忽略 1 行。',
    );

    expect(fakeUuid).toHaveBeenCalledTimes(1);
  });

  it('重放结果如实显示「已确认（重放）」，不说成新写入', async () => {
    vi.spyOn(crypto, 'randomUUID').mockImplementation(
      () => 'sub-replay' as `${string}-${string}-${string}-${string}-${string}`,
    );
    router(importView({ rows: [row({ rowNo: 1, decision: 'create' })] }), {
      'POST /api/v1/knowledge-imports/imp-1/confirm': () =>
        jsonResponse(true, 200, {
          importId: 'imp-1',
          state: 'confirmed',
          created: [],
          updated: [],
          ignored: [],
          replayed: true,
        }),
    });
    render(<ImportReviewPanel importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: '整批确认入库' }));
    fireEvent.click(await screen.findByRole('button', { name: '确认入库' }));

    expect(await screen.findByTestId('kp-confirm-result')).toHaveTextContent('已确认（重放）');
    expect(screen.getByTestId('kp-confirm-result')).toHaveTextContent('未重复写入');
  });

  it('422 阻断问题逐行显示并禁止确认；重试复用同一 submissionId', async () => {
    vi.spyOn(crypto, 'randomUUID').mockImplementation(
      () => 'sub-blocked' as `${string}-${string}-${string}-${string}-${string}`,
    );
    const fetchMock = router(importView({ rows: [row({ rowNo: 1, decision: 'create' })] }), {
      'POST /api/v1/knowledge-imports/imp-1/confirm': () =>
        jsonResponse(false, 422, {
          code: 'KNOWLEDGE_IMPORT_BLOCKING_ISSUES',
          message: '批次存在阻断问题。',
          retryable: false,
          details: {
            issues: [
              {
                row: 1,
                column: '父级',
                field: 'parentCode',
                code: 'KNOWLEDGE_PARENT_INVALID',
                message: '父级编码在批内与既有知识点中都不存在。',
              },
            ],
          },
        }),
    });
    render(<ImportReviewPanel importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: '整批确认入库' }));
    fireEvent.click(await screen.findByRole('button', { name: '确认入库' }));

    const issues = await screen.findByTestId('kp-confirm-issues');
    expect(issues).toHaveTextContent('第 1 行 · 列「父级」：KNOWLEDGE_PARENT_INVALID');
    expect(screen.getByText(/批次未确认（KNOWLEDGE_IMPORT_BLOCKING_ISSUES）/)).toBeInTheDocument();

    // 修正后重试：复用同一提交标识（幂等）
    fireEvent.click(screen.getByRole('button', { name: '确认入库' }));
    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-imports/imp-1/confirm', 'POST')).toHaveLength(2),
    );
    expect(bodyAt(fetchMock, '/knowledge-imports/imp-1/confirm', 'POST', 0).submissionId).toBe(
      'sub-blocked',
    );
    expect(bodyAt(fetchMock, '/knowledge-imports/imp-1/confirm', 'POST', 1).submissionId).toBe(
      'sub-blocked',
    );
  });

  it('已确认批次（本页没有回执）也渲染稳定结果元素，只陈述服务端状态', async () => {
    router(importView({ state: 'confirmed', rows: [row({ rowNo: 1, decision: 'create' })] }));
    render(<ImportReviewPanel importId="imp-1" />);

    const result = await screen.findByTestId('kp-confirm-result');
    expect(result).toHaveTextContent('该批次已确认入库');
    expect(result).toHaveTextContent('本页没有本次会话的提交回执');
    expect(screen.getByTestId('kp-import-state')).toHaveTextContent('已确认入库');
    // 已确认批次不能再确认
    expect(screen.getByRole('button', { name: '整批确认入库' })).toBeDisabled();
  });

  it('确认成功后的刷新不会卸载结果条（已确认入库计数保留）', async () => {
    vi.spyOn(crypto, 'randomUUID').mockImplementation(
      () => 'sub-sticky' as `${string}-${string}-${string}-${string}-${string}`,
    );
    let server = importView({ rows: [row({ rowNo: 1, decision: 'create' })] });
    const fetchMock = stubApi(async (url, init) => {
      const method = (init.method ?? 'GET').toUpperCase();
      if (method === 'GET' && url === '/api/v1/knowledge-imports/imp-1') {
        return jsonResponse(true, 200, server);
      }
      if (method === 'POST' && url === '/api/v1/knowledge-imports/imp-1/confirm') {
        // 服务端确认成功：批次变为已确认（刷新后 GET 返回该状态）
        server = { ...server, state: 'confirmed', revision: server.revision + 1 };
        return jsonResponse(true, 200, {
          importId: 'imp-1',
          state: 'confirmed',
          created: [{ rowNo: 1, knowledgePointId: 'kp-1', revisionId: 'kr-1', version: 1 }],
          updated: [],
          ignored: [],
          replayed: false,
        });
      }
      return jsonResponse(false, 500, {
        code: 'UNEXPECTED_TEST_REQUEST',
        message: `${method} ${url}`,
      });
    });
    render(<ImportReviewPanel importId="imp-1" />);

    fireEvent.click(await screen.findByRole('button', { name: '整批确认入库' }));
    fireEvent.click(screen.getByRole('button', { name: '确认入库' }));

    const result = await screen.findByTestId('kp-confirm-result');
    expect(result).toHaveTextContent('已确认入库：新建 1 条、更新 0 条、忽略 0 行。');
    // 刷新完成（批次进入已确认）后结果条仍在，不被骨架替换；状态 chip 同步更新
    await waitFor(() =>
      expect(screen.getByTestId('kp-import-state')).toHaveTextContent('已确认入库'),
    );
    expect(screen.getByTestId('kp-confirm-result')).toHaveTextContent('已确认入库：新建 1 条');
    expect(calls(fetchMock, '/knowledge-imports/imp-1/confirm', 'POST')).toHaveLength(1);
  });

  it('刷新失败时保留已显示数据并给出提示，不清空校对', async () => {
    let reads = 0;
    stubApi((url, init) => {
      const method = (init.method ?? 'GET').toUpperCase();
      if (method === 'GET' && url === '/api/v1/knowledge-imports/imp-1') {
        reads += 1;
        if (reads === 1) return jsonResponse(true, 200, importView());
        return jsonResponse(false, 503, {
          code: 'SERVICE_UNAVAILABLE',
          message: '导入服务未装配。',
          retryable: true,
        });
      }
      return jsonResponse(false, 500, {
        code: 'UNEXPECTED_TEST_REQUEST',
        message: `${method} ${url}`,
      });
    });
    render(<ImportReviewPanel importId="imp-1" />);

    await expect(screen.findByTestId('kp-import-file')).resolves.toHaveTextContent('知识点.csv');
    fireEvent.click(screen.getByRole('button', { name: '重新读取批次' }));

    const failure = await screen.findByTestId('kp-import-refresh-failed');
    expect(failure).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(failure).toHaveTextContent('页面仍显示上一次成功读取的数据');
    // 上一次成功读取的正文仍在（不清空、不显示骨架）
    expect(screen.getByTestId('kp-import-file')).toHaveTextContent('知识点.csv');
    expect(screen.getByTestId('kp-row-1')).toHaveTextContent('M.1');
  });

  it('AI 候选批次用独立样式与说明，强调候选尚未入库', async () => {
    router(importView({ source: 'ai', rows: [row({ rowNo: 1, decision: 'create' })] }));
    render(<ImportReviewPanel importId="imp-1" />);

    const banner = await screen.findByTestId('kp-ai-banner');
    expect(banner).toHaveTextContent('候选尚未入库（不是正式知识点）');
    expect(screen.getByTestId('kp-import-source')).toHaveTextContent('AI 候选');
    expect(screen.getByTestId('kp-import-review')).toHaveClass('ai');
    // 文件名有稳定 testid（e2e 用它在选中批次后断言预览态）
    expect(screen.getByTestId('kp-import-file')).toHaveTextContent('知识点.csv');
  });
});
