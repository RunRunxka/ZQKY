import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { KnowledgePointView } from '@/contracts/knowledge';
import { PointDetailPanel } from './PointDetailPanel';

function point(overrides: Partial<KnowledgePointView> = {}): KnowledgePointView {
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
    aliases: ['有理数概念', '有理数定义'],
    createdAt: '2026-09-30T00:00:00Z',
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

/** 默认路由：未声明的请求一律显式失败，避免测试把意外路径当成功。 */
function router(overrides: Record<string, Handler> = {}, current: KnowledgePointView = point()) {
  return stubApi((url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    for (const [key, handler] of Object.entries(overrides)) {
      const prefix = key.slice(method.length + 1);
      // 精确匹配路径（允许查询串），避免 `/kp-1` 误吃 `/kp-1/textbook-links`
      if (key.startsWith(`${method} `) && (url === prefix || url.startsWith(`${prefix}?`))) {
        return handler(url, init);
      }
    }
    if (url.endsWith('/knowledge-points/kp-1') && method === 'GET') {
      return jsonResponse(true, 200, current);
    }
    if (url.includes('/knowledge-points?') && method === 'GET') {
      return jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 200 });
    }
    if (url.endsWith('/knowledge-points/kp-1/textbook-links') && method === 'GET') {
      return jsonResponse(true, 200, { items: [] });
    }
    if (url.includes('/textbooks') && !url.includes('textbook-links')) {
      return jsonResponse(true, 200, { documents: [] });
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

describe('知识点详情与编辑', () => {
  it('显示版本 / 修订 id / 编辑锁；改名保存后显示服务端返回的新版本', async () => {
    // 有状态替身：PATCH 成功后 GET 返回更新后的权威对象（与真实后端一致）
    let server = point();
    const fetchMock = router({
      'GET /api/v1/knowledge-points/kp-1': () => jsonResponse(true, 200, server),
      'PATCH /api/v1/knowledge-points/kp-1': () => {
        server = point({ name: '有理数与无理数', revision: 4, revisionId: 'kr-4', version: 3 });
        return jsonResponse(true, 200, server);
      },
    });
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);

    expect(await screen.findByTestId('kp-revision-id')).toHaveTextContent('修订 kr-3');
    const name = screen.getByLabelText('名称') as HTMLInputElement;
    fireEvent.change(name, { target: { value: '有理数与无理数' } });
    fireEvent.click(screen.getByRole('button', { name: /保存修改/ }));

    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-points/kp-1', 'PATCH')).toHaveLength(1),
    );
    expect(bodyAt(fetchMock, '/knowledge-points/kp-1', 'PATCH')).toEqual({
      expectedRevision: 3,
      name: '有理数与无理数',
    });
    await waitFor(() => expect(screen.getByTestId('kp-detail-notice')).toHaveTextContent('v3'));
    await waitFor(() => expect(screen.getByTestId('kp-revision-id')).toHaveTextContent('kr-4'));
  });

  it('清空说明必须显式勾选：留空只提示，勾选后按 clearFields 提交', async () => {
    const fetchMock = router({
      'PATCH /api/v1/knowledge-points/kp-1': () =>
        jsonResponse(true, 200, point({ description: '', revision: 4, version: 3 })),
    });
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);

    const description = (await screen.findByLabelText('说明')) as HTMLTextAreaElement;
    fireEvent.change(description, { target: { value: '' } });

    // 只清空输入框：提示「留空 = 不修改」，保存按钮不可用（没有可提交的修改）
    expect(screen.getByText(/说明留空表示不修改/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /保存修改/ })).toBeDisabled();

    // 显式勾选清空：提交 clearFields
    fireEvent.click(screen.getByLabelText('清空说明'));
    fireEvent.click(screen.getByRole('button', { name: /保存修改/ }));
    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-points/kp-1', 'PATCH')).toHaveLength(1),
    );
    expect(bodyAt(fetchMock, '/knowledge-points/kp-1', 'PATCH')).toEqual({
      expectedRevision: 3,
      clearFields: ['description'],
    });
  });

  it('409 冲突保留用户输入、显示当前版本与服务端最新值，可按新版本重试', async () => {
    let patchAttempt = 0;
    const serverPoint = point({ revision: 7, version: 5, name: '服务端最新名称' });
    const fetchMock = router({
      'GET /api/v1/knowledge-points/kp-1': () =>
        jsonResponse(true, 200, patchAttempt === 0 ? point() : serverPoint),
      'PATCH /api/v1/knowledge-points/kp-1': () => {
        patchAttempt += 1;
        if (patchAttempt === 1) {
          return jsonResponse(false, 409, {
            code: 'REVISION_CONFLICT',
            message: '知识点已被其他操作更新（当前 revision=7），请刷新后重试。',
            retryable: false,
            details: { currentRevision: 7 },
          });
        }
        return jsonResponse(true, 200, point({ name: '我的修改', revision: 8, version: 6 }));
      },
    });
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);

    const name = (await screen.findByLabelText('名称')) as HTMLInputElement;
    fireEvent.change(name, { target: { value: '我的修改' } });
    fireEvent.click(screen.getByRole('button', { name: /保存修改/ }));

    const conflict = await screen.findByTestId('kp-conflict');
    expect(conflict).toHaveTextContent('当前版本 7，已刷新为最新，请重试。');
    // 服务端最新值随刷新到位；用户输入不被覆盖
    await waitFor(() => expect(conflict).toHaveTextContent('服务端最新：名称「服务端最新名称」'));
    expect((screen.getByLabelText('名称') as HTMLInputElement).value).toBe('我的修改');

    fireEvent.click(screen.getByRole('button', { name: '保留我的修改并重试' }));
    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-points/kp-1', 'PATCH')).toHaveLength(2),
    );
    expect(bodyAt(fetchMock, '/knowledge-points/kp-1', 'PATCH', 1)).toEqual({
      expectedRevision: 7,
      name: '我的修改',
    });
  });

  it('422 用 details.issues 定位字段并逐条显示', async () => {
    router({
      'PATCH /api/v1/knowledge-points/kp-1': () =>
        jsonResponse(false, 422, {
          code: 'KNOWLEDGE_CYCLE',
          message: '父级选择会形成环。',
          retryable: false,
          details: {
            issues: [
              {
                field: 'parentId',
                code: 'KNOWLEDGE_CYCLE',
                message: '父级关系形成环：M.7.1 → M.7.2 → M.7.1。',
              },
            ],
          },
        }),
    });
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText('名称'), { target: { value: '改名' } });
    fireEvent.click(screen.getByRole('button', { name: /保存修改/ }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('KNOWLEDGE_CYCLE');
    expect(screen.getByText(/字段 parentId：KNOWLEDGE_CYCLE：父级关系形成环/)).toBeInTheDocument();
  });
});

describe('教材依据', () => {
  it('503 TEXTBOOK_EVIDENCE_UNAVAILABLE 显示「暂不可用（服务未就绪）」，绝不当「没有依据」', async () => {
    router({
      'GET /api/v1/knowledge-points/kp-1/textbook-links': () =>
        jsonResponse(false, 503, {
          code: 'TEXTBOOK_EVIDENCE_UNAVAILABLE',
          message: '教材目录未装配。',
          retryable: true,
        }),
    });
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);

    const alert = await screen.findByTestId('kp-evidence-unavailable');
    expect(alert).toHaveTextContent('教材依据暂不可用（服务未就绪）');
    expect(screen.queryByTestId('kp-evidence-empty')).not.toBeInTheDocument();
    expect(screen.queryByText('没有教材依据')).not.toBeInTheDocument();
  });

  it('成功读取且 0 条时才显示「没有教材依据」', async () => {
    router();
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);

    expect(await screen.findByTestId('kp-evidence-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('kp-evidence-unavailable')).not.toBeInTheDocument();
  });

  it('新增依据提交 documentRevisionId 与字符区间（expectedRevision 来自知识点）', async () => {
    const fetchMock = router({
      'POST /api/v1/knowledge-points/kp-1/textbook-links': () =>
        jsonResponse(true, 201, {
          linkId: 'ln-1',
          knowledgePointId: 'kp-1',
          knowledgeRevisionId: 'kr-3',
          documentRevisionId: 'rev-9',
          charStart: 10,
          charEnd: 40,
          titleSnapshot: '第一章 有理数',
          locatorHash: 'h-1',
          source: 'human',
          createdAt: '2026-09-30T00:00:00Z',
        }),
    });
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText('教材修订 id'), {
      target: { value: 'rev-9' },
    });
    fireEvent.change(screen.getByLabelText('起始字符'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('结束字符'), { target: { value: '40' } });
    fireEvent.click(screen.getByRole('button', { name: '新增教材依据' }));

    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-points/kp-1/textbook-links', 'POST')).toHaveLength(1),
    );
    expect(bodyAt(fetchMock, '/knowledge-points/kp-1/textbook-links', 'POST')).toEqual({
      expectedRevision: 3,
      documentRevisionId: 'rev-9',
      charStart: 10,
      charEnd: 40,
      source: 'human',
    });
    expect(await screen.findByText(/已新增教材依据：第一章 有理数/)).toBeInTheDocument();
  });
});

describe('彻底删除（三态：成功 / 被引用 / 版本冲突）', () => {
  it('成功：二次确认后按 expectedRevision 删除，通知父级并切到已删除态', async () => {
    const onDeleted = vi.fn();
    const fetchMock = router({
      'DELETE /api/v1/knowledge-points/kp-1': () =>
        ({ ok: true, status: 204, json: async () => null }) as Response,
    });
    render(
      <PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} onDeleted={onDeleted} />,
    );

    fireEvent.click(await screen.findByTestId('kp-delete-open'));
    const dialog = await screen.findByRole('dialog', { name: '彻底删除知识点' });
    expect(dialog).toHaveTextContent('物理删除');
    expect(dialog).toHaveTextContent('不可恢复');
    expect(dialog).toHaveTextContent('仍被引用时服务端会拒绝');
    // 第一步确认不含删除请求
    expect(calls(fetchMock, '/knowledge-points/kp-1', 'DELETE')).toHaveLength(0);

    fireEvent.click(within(dialog).getByTestId('kp-delete-confirm'));
    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-points/kp-1', 'DELETE')).toHaveLength(1),
    );
    expect(calls(fetchMock, '/knowledge-points/kp-1?expectedRevision=3', 'DELETE')).toHaveLength(1);
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith('kp-1'));
    expect(await screen.findByTestId('kp-deleted')).toHaveTextContent('该知识点已彻底删除');
  });

  it('被引用 409：逐项渲染 count>0 的原因清单，并给出「改为归档」出口', async () => {
    const fetchMock = router({
      'DELETE /api/v1/knowledge-points/kp-1': () =>
        jsonResponse(false, 409, {
          code: 'KNOWLEDGE_POINT_IN_USE',
          message: '知识点仍在使用中：存在教材依据、原卷题目或题库引用，先解除引用或改用归档。',
          retryable: false,
          details: {
            counts: [
              { library: 'knowledge', key: 'textbookKnowledgeLinks', count: 1 },
              { library: 'teaching', key: 'paperItemKnowledge', count: 0 },
              { library: 'question_bank', key: 'questionKnowledgeLinks', count: 6 },
              { library: 'question_bank', key: 'questionDraftKnowledgeLinks', count: 2 },
            ],
          },
        }),
    });
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);

    fireEvent.click(await screen.findByTestId('kp-delete-open'));
    fireEvent.click(await screen.findByTestId('kp-delete-confirm'));

    const blocked = await screen.findByTestId('kp-delete-blocked');
    expect(blocked).toHaveTextContent('不能彻底删除');
    const counts = within(blocked).getByTestId('kp-delete-counts');
    expect(counts).toHaveTextContent('知识点库 · 教材依据：1 处');
    expect(counts).toHaveTextContent('题库 · 题库正式题关联：6 处');
    expect(counts).toHaveTextContent('题库 · 题库草稿关联：2 处');
    // count=0 的项不渲染（不把「没引用」当原因）
    expect(counts).not.toHaveTextContent('原卷题目关联');
    // 失败不删除、不刷新成空详情
    expect(calls(fetchMock, '/knowledge-points/kp-1', 'DELETE')).toHaveLength(1);
    expect(screen.queryByTestId('kp-deleted')).not.toBeInTheDocument();

    fireEvent.click(within(blocked).getByTestId('kp-delete-to-archive'));
    expect(await screen.findByRole('dialog', { name: '归档知识点' })).toBeInTheDocument();
  });

  it('仍有子节点（同码 409 但无 counts）如实说明不编造计数；版本冲突走冲突横幅并重读', async () => {
    const fetchMock = router({
      'DELETE /api/v1/knowledge-points/kp-1': () =>
        jsonResponse(false, 409, {
          code: 'KNOWLEDGE_POINT_IN_USE',
          message: '该知识点还有 2 个子节点；先删除或移动子节点。',
          retryable: false,
        }),
    });
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);

    fireEvent.click(await screen.findByTestId('kp-delete-open'));
    fireEvent.click(await screen.findByTestId('kp-delete-confirm'));
    const blocked = await screen.findByTestId('kp-delete-blocked');
    expect(blocked).toHaveTextContent('该知识点还有 2 个子节点');
    expect(blocked).toHaveTextContent('服务端没有给出逐项引用计数');
    expect(within(blocked).queryByTestId('kp-delete-counts')).not.toBeInTheDocument();

    // 版本冲突（REVISION_CONFLICT）：按服务端 currentRevision 刷新并给重试出口
    fetchMock.mockClear();
    router({
      'DELETE /api/v1/knowledge-points/kp-1': () =>
        jsonResponse(false, 409, {
          code: 'REVISION_CONFLICT',
          message: '知识点已被其他操作更新（当前 revision=5），请刷新后重试。',
          retryable: false,
          details: { currentRevision: 5 },
        }),
    });
    cleanup();
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);
    fireEvent.click(await screen.findByTestId('kp-delete-open'));
    fireEvent.click(await screen.findByTestId('kp-delete-confirm'));
    const conflict = await screen.findByTestId('kp-conflict');
    expect(conflict).toHaveTextContent('当前版本 5，已刷新为最新，请重试。');
    expect(screen.queryByTestId('kp-deleted')).not.toBeInTheDocument();
  });
});

describe('别名增删', () => {
  it('逐条移除别名后按剩余别名提交', async () => {
    const fetchMock = router({
      'PATCH /api/v1/knowledge-points/kp-1': () =>
        jsonResponse(true, 200, point({ aliases: ['有理数定义'], revision: 4, version: 3 })),
    });
    render(<PointDetailPanel pointId="kp-1" onPointPatched={vi.fn()} />);

    const row = await screen.findByLabelText('别名（可逐条移除）');
    fireEvent.click(within(row).getByRole('button', { name: '移除别名 有理数概念' }));
    fireEvent.click(screen.getByRole('button', { name: /保存修改/ }));

    await waitFor(() =>
      expect(calls(fetchMock, '/knowledge-points/kp-1', 'PATCH')).toHaveLength(1),
    );
    expect(bodyAt(fetchMock, '/knowledge-points/kp-1', 'PATCH')).toEqual({
      expectedRevision: 3,
      aliases: ['有理数定义'],
    });
  });
});
