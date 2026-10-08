import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { KnowledgePointView } from '@/contracts/knowledge';
import { PointBrowser } from './PointBrowser';

const TAXONOMY_SUBJECTS = [{ id: 'math', label: '数学' }];
const TAXONOMY_GRADES = [
  { id: 'grade-7', label: '七年级' },
  { id: 'grade-8', label: '八年级' },
];

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

describe('知识点浏览：范围切档（默认任教范围）与年级筛选', () => {
  it('默认 scope=taught（窄口径）；显式切到「学科全部教材」后发 scope=subject 且按钮态明确', async () => {
    const fetchMock = stubApi((url) => {
      if (url.includes('/knowledge-points')) return listResponse([point()]);
      return jsonResponse(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: url });
    });
    renderBrowser({ grades: TAXONOMY_GRADES });

    await screen.findByText('有理数');
    // 默认口径：任教范围内教材
    expect(calls(fetchMock, 'scope=taught').length).toBe(1);
    const taught = screen.getByTestId('kp-scope-taught');
    const subject = screen.getByTestId('kp-scope-subject');
    expect(taught).toHaveAttribute('aria-pressed', 'true');
    expect(subject).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('kp-scope-hint')).toHaveTextContent('任教范围内教材');

    fireEvent.click(subject);
    await waitFor(() => expect(calls(fetchMock, 'scope=subject').length).toBe(1));
    expect(screen.getByTestId('kp-scope-subject')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('kp-scope-taught')).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('kp-scope-hint')).toHaveTextContent('学科全部教材');
  });

  it('scope=taught 409：显示服务端原因与「去设置任教范围」链接，不静默回退全部', async () => {
    const fetchMock = stubApi((url) => {
      if (url.includes('scope=subject')) return listResponse([point()]);
      if (url.includes('/knowledge-points')) {
        return jsonResponse(false, 409, {
          code: 'KNOWLEDGE_SCOPE_UNAVAILABLE',
          message: '尚未保存任教范围，无法按任教范围筛选知识点。',
          retryable: false,
        });
      }
      return jsonResponse(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: url });
    });
    renderBrowser();

    const banner = await screen.findByTestId('kp-scope-unavailable');
    expect(banner).toHaveTextContent('KNOWLEDGE_SCOPE_UNAVAILABLE');
    expect(banner).toHaveTextContent('尚未保存任教范围，无法按任教范围筛选知识点。');
    expect(within(banner).getByRole('link', { name: '去设置任教范围' })).toHaveAttribute(
      'href',
      '/knowledge-bases',
    );
    // 不是空态、也没有回退成「全部」的第二条请求
    expect(screen.queryByText('没有符合条件的数据')).not.toBeInTheDocument();
    expect(calls(fetchMock, 'scope=subject').length).toBe(0);

    // 显式切换到「学科全部教材」才发 subject 口径的请求
    fireEvent.click(screen.getByTestId('kp-scope-switch-subject'));
    expect(await screen.findByText('有理数')).toBeInTheDocument();
    expect(calls(fetchMock, 'scope=subject').length).toBe(1);
  });

  it('年级筛选用字典选项，并把 gradeId 传给服务端；字典不可用时降级为汇总结果 gradeIds 并说明', async () => {
    const fetchMock = stubApi((url) => {
      if (url.includes('gradeId=grade-8')) return listResponse([point({ name: '一次函数' })]);
      if (url.includes('/knowledge-points')) {
        return listResponse([point({ gradeIds: ['grade-7'] })]);
      }
      return jsonResponse(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: url });
    });
    const { view } = renderBrowser({ grades: TAXONOMY_GRADES });

    await screen.findByText('有理数');
    const gradeSelect = screen.getByLabelText('按年级筛选');
    expect(within(gradeSelect).getByRole('option', { name: '七年级' })).toBeInTheDocument();
    expect(within(gradeSelect).getByRole('option', { name: '八年级' })).toBeInTheDocument();
    expect(screen.getByText('年级 七年级')).toBeInTheDocument();
    expect(screen.queryByTestId('kp-grade-fallback')).not.toBeInTheDocument();

    fireEvent.change(gradeSelect, { target: { value: 'grade-8' } });
    expect(await screen.findByText('一次函数')).toBeInTheDocument();
    expect(calls(fetchMock, 'gradeId=grade-8').length).toBe(1);

    // 字典不可用（grades 为空）→ 只能汇总当前结果里出现过的年级，并如实说明局限
    view.unmount();
    stubApi((url) => {
      if (url.includes('/knowledge-points')) return listResponse([point({ gradeIds: ['grade-7'] })]);
      return jsonResponse(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: url });
    });
    renderBrowser();
    await screen.findByText('有理数');
    expect(screen.getByTestId('kp-grade-fallback')).toHaveTextContent(
      '年级筛选项由本页结果里的 `gradeIds` 汇总而来',
    );
    expect(
      within(screen.getByLabelText('按年级筛选')).getByRole('option', { name: 'grade-7' }),
    ).toBeInTheDocument();
  });
});
