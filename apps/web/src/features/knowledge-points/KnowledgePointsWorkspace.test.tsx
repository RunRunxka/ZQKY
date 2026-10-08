import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { KnowledgePointView } from '@/contracts/knowledge';
import { KnowledgePointsWorkspace } from './KnowledgePointsWorkspace';

const TAXONOMY = {
  stages: [{ id: 'stage-j', label: '初中' }],
  grades: [{ id: 'grade-7', label: '七年级', stageId: 'stage-j' }],
  subjects: [{ id: 'math', label: '数学' }],
  editions: [{ id: 'renjiao', label: '人教版' }],
};

function point(overrides: Partial<KnowledgePointView> = {}): KnowledgePointView {
  return {
    id: 'kp-1',
    subjectId: 'math',
    code: 'M.7.1',
    name: '有理数',
    description: '',
    parentId: null,
    parentCode: null,
    sortOrder: 0,
    status: 'active',
    revision: 1,
    revisionId: 'kr-1',
    version: 1,
    aliases: [],
    createdAt: '2026-09-30T00:00:00Z',
    ...overrides,
  };
}

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function jsonResponse(ok: boolean, status: number, body: unknown): Response {
  return { ok, status, json: async () => body } as Response;
}

function calls(fetchMock: ReturnType<typeof vi.fn>, fragment: string, method?: string) {
  return fetchMock.mock.calls.filter(([url, init]) => {
    const request = init as RequestInit | undefined;
    return String(url).includes(fragment) && (!method || request?.method === method);
  });
}

function router(overrides: Record<string, Handler> = {}) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(
      (() => {
        const url = typeof input === 'string' ? input : input.toString();
        const method = (init?.method ?? 'GET').toUpperCase();
        for (const [key, handler] of Object.entries(overrides)) {
          const prefix = key.slice(method.length + 1);
          if (key.startsWith(`${method} `) && (url === prefix || url.startsWith(`${prefix}?`))) {
            return handler(url, init ?? {});
          }
        }
        if (url.endsWith('/api/v1/textbook-taxonomy')) {
          return jsonResponse(true, 200, TAXONOMY);
        }
        if (url.includes('/api/v1/knowledge-points?') && method === 'GET') {
          return jsonResponse(true, 200, { items: [point()], total: 1, offset: 0, limit: 100 });
        }
        if (
          url.endsWith('/api/v1/knowledge-imports?offset=&limit=100') ||
          url === '/api/v1/knowledge-imports?limit=100'
        ) {
          return jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 100 });
        }
        if (url.endsWith('/api/v1/model-catalog')) {
          return jsonResponse(true, 200, {
            revision: 1,
            defaultChatProfileId: null,
            connections: [],
            profiles: [],
          });
        }
        return jsonResponse(false, 500, {
          code: 'UNEXPECTED_TEST_REQUEST',
          message: `${method} ${url} 未在测试路由中声明`,
        });
      })(),
    ),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
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

describe('知识点工作台：页签与建立', () => {
  it('四个页签都存在；切换页签不会卸载其他页签的任务状态', async () => {
    router();
    const { container } = render(<KnowledgePointsWorkspace />);
    const panel = (id: string) => container.querySelector(`#kp-panel-${id}`);

    // 默认在「知识点」：列表加载完成后可见；其他面板隐藏但仍挂载（保留任务状态）
    expect(await screen.findByRole('heading', { name: '知识点', level: 1 })).toBeInTheDocument();
    expect(await screen.findByText('有理数')).toBeInTheDocument();
    expect(panel('points')).not.toHaveAttribute('hidden');
    expect(panel('imports')).toHaveAttribute('hidden');
    expect(panel('suggestion')).toHaveAttribute('hidden');
    expect(panel('extract')).toHaveAttribute('hidden');

    fireEvent.click(screen.getByRole('tab', { name: '表格导入' }));
    expect(panel('imports')).not.toHaveAttribute('hidden');
    expect(panel('points')).toHaveAttribute('hidden');
    expect(await screen.findByText('还没有导入批次')).toBeInTheDocument();
    // 切走后「知识点」面板没有卸载：选中/列表状态仍在
    expect(panel('points')).not.toBeNull();

    fireEvent.click(screen.getByRole('tab', { name: 'AI 候选' }));
    expect(panel('suggestion')).not.toHaveAttribute('hidden');
    expect(
      await screen.findByRole('heading', { name: /AI 候选（待确认，不直接入库）/ }),
    ).toBeInTheDocument();
    expect(container.querySelector('#kp-panel-imports')).not.toBeNull();

    // 第四个页签「教材提取」：面板挂载、未读预览时入口禁用
    fireEvent.click(screen.getByRole('tab', { name: '教材提取' }));
    expect(panel('extract')).not.toHaveAttribute('hidden');
    expect(screen.getByTestId('kp-extract-start')).toBeDisabled();
    expect(
      await screen.findByRole('heading', { name: /从教材提取知识点（AI 候选 · 需人工确认）/ }),
    ).toBeInTheDocument();
  });

  it('新建知识点成功后关闭对话框、选中新对象并刷新列表', async () => {
    const created = point({ id: 'kp-2', code: 'M.7.2', name: '数轴', revision: 0, version: 0 });
    let createdFlag = false;
    const fetchMock = router({
      'POST /api/v1/knowledge-points': () => {
        createdFlag = true;
        return jsonResponse(true, 201, created);
      },
      'GET /api/v1/knowledge-points/kp-2': () => jsonResponse(true, 200, created),
      'GET /api/v1/knowledge-points?subjectId=math&status=active&limit=200': () =>
        jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 200 }),
    });
    render(<KnowledgePointsWorkspace />);

    fireEvent.click(await screen.findByRole('button', { name: /新建知识点/ }));
    const dialog = await screen.findByRole('dialog', { name: '新建知识点' });
    fireEvent.change(within(dialog).getByLabelText('学科'), { target: { value: 'math' } });
    fireEvent.change(within(dialog).getByLabelText('编码'), { target: { value: 'M.7.2' } });
    fireEvent.change(within(dialog).getByLabelText('名称'), { target: { value: '数轴' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /建立知识点/ }));

    await waitFor(() =>
      expect(calls(fetchMock, '/api/v1/knowledge-points', 'POST')).toHaveLength(1),
    );
    const body = JSON.parse(
      String((calls(fetchMock, '/api/v1/knowledge-points', 'POST')[0]?.[1] as RequestInit).body),
    ) as Record<string, unknown>;
    expect(body).toEqual({ subjectId: 'math', code: 'M.7.2', name: '数轴' });

    expect(createdFlag).toBe(true);
    // 新对象被选中并读取详情
    expect(await screen.findByTestId('kp-revision-id')).toHaveTextContent('kr-1');
    expect(screen.getByLabelText('名称')).toHaveValue('数轴');
    // 列表刷新（父级用 refreshToken 触发）
    await waitFor(() =>
      expect(calls(fetchMock, '/api/v1/knowledge-points?').length).toBeGreaterThan(1),
    );
  });

  it('学科字典读取失败时如实显示错误并允许手动填写，不当空字典', async () => {
    router({
      'GET /api/v1/textbook-taxonomy': () =>
        jsonResponse(false, 503, {
          code: 'SERVICE_UNAVAILABLE',
          message: '教材目录服务未装配。',
          retryable: true,
        }),
    });
    render(<KnowledgePointsWorkspace />);

    const alert = await screen.findByText(/学科字典读取失败（SERVICE_UNAVAILABLE）/);
    expect(alert).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /新建知识点/ }));
    const dialog = await screen.findByRole('dialog', { name: '新建知识点' });
    // 字典不可用时退回手填学科 id，而不是把「全部学科」当唯一选项
    expect(within(dialog).getByLabelText('学科')).toHaveAttribute(
      'placeholder',
      '学科 id（如 math）',
    );
  });
});
