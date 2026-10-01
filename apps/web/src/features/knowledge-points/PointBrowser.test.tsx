import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import type { KnowledgePointView } from '@/contracts/knowledge';
import { PointBrowser } from './PointBrowser';

const TAXONOMY_SUBJECTS = [{ id: 'math', label: '数学' }];

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
    aliases: ['有理数概念'],
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

function listResponse(items: KnowledgePointView[], total = items.length): Response {
  return jsonResponse(true, 200, { items, total, offset: 0, limit: 100 });
}

function calls(fetchMock: ReturnType<typeof stubApi>, fragment: string, method?: string) {
  return fetchMock.mock.calls.filter(([url, init]) => {
    const request = init as RequestInit | undefined;
    return String(url).includes(fragment) && (!method || request?.method === method);
  });
}

function renderBrowser(overrides: Partial<Parameters<typeof PointBrowser>[0]> = {}) {
  const props = {
    subjects: TAXONOMY_SUBJECTS,
    taxonomyReady: true,
    subjectId: '',
    status: '' as const,
    selectedPointId: null,
    onSubjectChange: vi.fn(),
    onStatusChange: vi.fn(),
    onSelect: vi.fn(),
    onCreate: vi.fn(),
    refreshToken: 0,
    ...overrides,
  };
  return { props, view: render(<PointBrowser {...props} />) };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('知识点浏览：列表 / 筛选 / 空态 / 失败重试', () => {
  it('读取失败显示错误码与重试，不显示空态；重试成功后恢复真实列表', async () => {
    let attempt = 0;
    const fetchMock = stubApi((url) => {
      if (url.includes('/knowledge-points')) {
        attempt += 1;
        if (attempt === 1) {
          return jsonResponse(false, 503, {
            code: 'SERVICE_UNAVAILABLE',
            message: '知识点服务未装配。',
            retryable: true,
          });
        }
        return listResponse([point()]);
      }
      return jsonResponse(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: url });
    });
    renderBrowser();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('SERVICE_UNAVAILABLE');
    // 错误横幅有稳定 testid（e2e 不能按全页 alert 数量断言：Next RouteAnnouncer 常驻一个空 alert）
    expect(screen.getByTestId('kp-list-error')).toBe(alert);
    expect(screen.queryByText('没有符合条件的数据')).not.toBeInTheDocument();
    expect(screen.queryByText('有理数')).not.toBeInTheDocument();

    fireEvent.click(within(alert).getByRole('button', { name: '重试' }));
    expect(await screen.findByText('有理数')).toBeInTheDocument();
    expect(screen.queryByTestId('kp-list-error')).not.toBeInTheDocument();
    expect(calls(fetchMock, '/knowledge-points').length).toBe(2);
  });

  it('成功但 0 条时才显示空态；按关键字搜索走 q 查询参数', async () => {
    const fetchMock = stubApi((url) => {
      if (url.includes('q=%E5%87%BD%E6%95%B0')) return listResponse([]);
      if (url.includes('/knowledge-points')) return listResponse([point()]);
      return jsonResponse(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: url });
    });
    renderBrowser();

    expect(await screen.findByText('有理数')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('按关键字搜索知识点'), {
      target: { value: '函数' },
    });
    fireEvent.click(screen.getByRole('button', { name: /搜索/ }));

    expect(await screen.findByText('没有符合条件的数据')).toBeInTheDocument();
    // 空态不是错误态：页面自己的错误横幅不存在
    expect(screen.queryByTestId('kp-list-error')).not.toBeInTheDocument();
    expect(calls(fetchMock, 'q=%E5%87%BD%E6%95%B0').length).toBe(1);
  });

  it('父树视图把父级不在当前结果的节点单独列出，不伪造层级', async () => {
    stubApi((url) => {
      if (url.includes('/knowledge-points')) {
        return listResponse([
          point({ id: 'kp-parent', code: 'M.7', name: '数与式' }),
          point({ id: 'kp-child', parentId: 'kp-parent', parentCode: 'M.7', name: '有理数' }),
          point({ id: 'kp-orphan', parentId: 'kp-missing', parentCode: 'M.9', name: '孤立知识点' }),
        ]);
      }
      return jsonResponse(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: url });
    });
    renderBrowser();

    fireEvent.click(await screen.findByRole('button', { name: /父树/ }));
    const tree = await screen.findByRole('tree', { name: '知识点父树' });

    // 正常父子的层级：父节点与子节点都在树里
    expect(within(tree).getByText('数与式')).toBeInTheDocument();
    expect(within(tree).getByText('有理数')).toBeInTheDocument();
    // 父级不在当前结果的节点：单独成组并原样显示 parentCode
    expect(within(tree).getByText(/父级不在当前结果里/)).toBeInTheDocument();
    expect(within(tree).getByText(/父级 M\.9（不在当前结果）/)).toBeInTheDocument();
  });
});
