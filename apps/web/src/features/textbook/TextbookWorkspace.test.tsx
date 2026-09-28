import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { LibrarySummary, TextbookTaxonomy } from '@/contracts/textbook';
import { TextbookWorkspace } from './TextbookWorkspace';

const TAXONOMY: TextbookTaxonomy = {
  stages: [{ id: 'stage-j', label: '初中' }],
  grades: [
    { id: 'g7', label: '七年级', stageId: 'stage-j' },
    { id: 'g8', label: '八年级', stageId: 'stage-j' },
  ],
  subjects: [{ id: 'math', label: '数学' }],
  editions: [{ id: 'rj', label: '人教版' }],
};

function library(overrides: Partial<LibrarySummary> = {}): LibrarySummary {
  return {
    libraryId: 'lib-base',
    kind: 'base',
    ownerId: 'system',
    displayName: '七年级数学基础库',
    gradeId: 'g7',
    subjectId: 'math',
    editionId: 'rj',
    documentCount: 2,
    readyDocumentCount: 1,
    revision: 5,
    deletedAt: null,
    ...overrides,
  };
}

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response;
const failed = (status: number, body: unknown) =>
  ({ ok: false, status, json: async () => body }) as Response;

function stubApi(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('教材管理页', () => {
  it('先显示加载态，就绪后列出真实库并保留书籍/课程入口', async () => {
    // 闸门推迟首屏库列表响应，保证「加载态」可被稳定观测
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    stubApi((url) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('kind=base')) return gate.then(() => ok({ libraries: [library()] }));
      if (url.includes('kind=personal')) {
        return ok({
          libraries: [
            library({ libraryId: 'lib-personal', kind: 'personal', displayName: '我的七年级教材' }),
          ],
        });
      }
      throw new Error(`未预期的请求 ${url}`);
    });
    const { container } = render(<TextbookWorkspace />);

    await waitFor(() =>
      expect(container.querySelectorAll('.space-skeleton').length).toBeGreaterThan(0),
    );
    release();

    const card = await screen.findByRole('link', { name: /七年级数学基础库/ });
    expect(card).toHaveAttribute('href', '/knowledge-bases/libraries/lib-base');
    expect(within(card).getByText('书册 2')).toBeInTheDocument();
    expect(within(card).getByText('已就绪 1')).toBeInTheDocument();
    expect(within(card).getByText('学科：数学')).toBeInTheDocument();

    // 书籍/课程直达入口保留（既有 e2e 依赖 .kb-library-links 与这两个 href）
    expect(container.querySelector('.kb-library-links a[href="/books"]')).not.toBeNull();
    expect(container.querySelector('.kb-library-links a[href="/courses"]')).not.toBeNull();
    // 两个面板入口
    expect(screen.getByRole('button', { name: /导入教材/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /入库任务/ })).toBeInTheDocument();
  });

  it('请求失败显示错误与重试，而不是空目录', async () => {
    let attempt = 0;
    stubApi((url) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('kind=base')) {
        attempt += 1;
        if (attempt === 1) {
          return failed(503, {
            code: 'SERVICE_UNAVAILABLE',
            message: '后端服务不可用。',
            retryable: true,
          });
        }
        return ok({ libraries: [library()] });
      }
      return ok({ libraries: [] });
    });
    render(<TextbookWorkspace />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('教材库读取失败');
    expect(alert).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(screen.queryByText('还没有基础库')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('link', { name: /七年级数学基础库/ })).toBeInTheDocument();
  });

  it('字典读取失败只影响筛选条，列表仍可读', async () => {
    stubApi((url) => {
      if (url.includes('/textbook-taxonomy')) {
        return failed(500, { code: 'INTERNAL_ERROR', message: '字典读取失败。', retryable: true });
      }
      if (url.includes('kind=base')) return ok({ libraries: [library()] });
      return ok({ libraries: [] });
    });
    render(<TextbookWorkspace />);

    expect(await screen.findByText(/教材字典读取失败/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /七年级数学基础库/ })).toBeInTheDocument();
    const gradeSelect = document.querySelector<HTMLSelectElement>('#textbook-filter-grade-base');
    expect(gradeSelect).not.toBeNull();
    expect(gradeSelect).toBeDisabled();
  });

  it('年级筛选按服务端查询参数重新请求', async () => {
    const fetchMock = stubApi((url) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('kind=base')) return ok({ libraries: [library()] });
      return ok({ libraries: [] });
    });
    render(<TextbookWorkspace />);
    await screen.findByRole('link', { name: /七年级数学基础库/ });

    const gradeSelect = document.querySelector<HTMLSelectElement>('#textbook-filter-grade-base');
    expect(gradeSelect).not.toBeNull();
    fireEvent.change(gradeSelect as HTMLSelectElement, { target: { value: 'g7' } });

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes('kind=base&gradeId=g7')),
      ).toBe(true);
    });
  });

  it('切换到我的教材展示个人库，历史登记为只读页签', async () => {
    stubApi((url) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('kind=personal')) {
        return ok({
          libraries: [
            library({ libraryId: 'lib-personal', kind: 'personal', displayName: '我的七年级教材' }),
          ],
        });
      }
      return ok({ libraries: [library()] });
    });
    render(<TextbookWorkspace />);
    await screen.findByRole('link', { name: /七年级数学基础库/ });

    fireEvent.click(screen.getByRole('tab', { name: '我的教材' }));
    expect(screen.getByRole('link', { name: /我的七年级教材/ })).toHaveAttribute(
      'href',
      '/knowledge-bases/libraries/lib-personal',
    );

    expect(screen.getByRole('tab', { name: '历史登记' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '基础库' })).toHaveAttribute('aria-selected', 'false');
  });
});
