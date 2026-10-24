import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
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

/** jsdom 未实现 dialog 的 showModal/close（公共 Modal 依赖），这里只补最小实现。 */
beforeAll(() => {
  if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.setAttribute('open', '');
    };
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.removeAttribute('open');
    };
  }
});

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
    expect(card).toHaveAttribute('href', '/textbooks/libraries/lib-base');
    expect(within(card).getByText('书册 2')).toBeInTheDocument();
    expect(within(card).getByText('已就绪 1')).toBeInTheDocument();
    expect(within(card).getByText('学科：数学')).toBeInTheDocument();

    // 重建后不再提供书籍/课程入口（这两个顶级模块尚未回归，避免死链）
    expect(container.querySelector('.kb-library-links')).toBeNull();
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

  it('切换到我的教材展示个人库，两个页签互斥选中', async () => {
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
      '/textbooks/libraries/lib-personal',
    );

    // 重建后不再提供「历史登记」页签（旧产品 localStorage 残留，无写入方）
    expect(screen.queryByRole('tab', { name: '历史登记' })).toBeNull();
    expect(screen.getByRole('tab', { name: '基础库' })).toHaveAttribute('aria-selected', 'false');
  });
});

describe('教材管理页 · 新建逻辑库（R10-FE 2026-10-13）', () => {
  it('填齐必填项后提交：POST 带 kind/displayName/subjectId/editionId/gradeId，成功后切页签、刷新列表并给提示', async () => {
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('/textbook-libraries') && (init.method ?? 'GET') === 'POST') {
        return ok(
          library({
            libraryId: 'lib-new',
            kind: 'personal',
            displayName: '我的教材',
            gradeId: null,
            revision: 0,
            documentCount: 0,
            readyDocumentCount: 0,
          }),
        );
      }
      if (url.includes('kind=base')) return ok({ libraries: [] });
      if (url.includes('kind=personal')) {
        return ok({ libraries: [library({ libraryId: 'lib-new', kind: 'personal', displayName: '我的教材' })] });
      }
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<TextbookWorkspace />);

    fireEvent.click(await screen.findByTestId('textbook-library-create-open'));
    const form = await screen.findByTestId('textbook-library-create');
    // 必填未齐：提交键禁用
    expect(within(form).getByTestId('textbook-library-create-submit')).toBeDisabled();

    fireEvent.change(within(form).getByLabelText('库显示名'), { target: { value: '我的教材' } });
    fireEvent.change(within(form).getByLabelText('库学科'), { target: { value: 'math' } });
    fireEvent.change(within(form).getByLabelText('库版本'), { target: { value: 'rj' } });
    expect(within(form).getByTestId('textbook-library-create-submit')).not.toBeDisabled();

    fireEvent.click(within(form).getByTestId('textbook-library-create-submit'));
    await waitFor(() => {
      const posted = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes('/textbook-libraries') && (init as RequestInit)?.method === 'POST',
      );
      expect(posted).toBeTruthy();
      expect(JSON.parse(String((posted?.[1] as RequestInit).body))).toEqual({
        kind: 'personal',
        displayName: '我的教材',
        subjectId: 'math',
        editionId: 'rj',
        gradeId: null,
      });
    });
    // 成功提示 + 自动切到该库所在页签 + 列表刷新（再次读取 personal 列表）
    expect(await screen.findByTestId('textbook-notice')).toHaveTextContent('已新建逻辑库「我的教材」');
    expect(screen.getByRole('tab', { name: '我的教材' })).toHaveAttribute('aria-selected', 'true');
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([url]) => String(url).includes('kind=personal')).length,
      ).toBeGreaterThan(1),
    );
    expect(screen.queryByTestId('textbook-library-create')).toBeNull();
  });

  it('失败（409）：原样显示服务端 code 与 message，保留输入、不给成功提示', async () => {
    stubApi((url, init) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('/textbook-libraries') && (init.method ?? 'GET') === 'POST') {
        return failed(409, { code: 'LIBRARY_CONFLICT', message: '同一范围（学科/版本/年级）的逻辑库已存在。' });
      }
      if (url.includes('/textbook-libraries')) return ok({ libraries: [] });
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<TextbookWorkspace />);

    fireEvent.click(await screen.findByTestId('textbook-library-create-open'));
    const form = await screen.findByTestId('textbook-library-create');
    fireEvent.change(within(form).getByLabelText('库显示名'), { target: { value: '我的教材' } });
    fireEvent.change(within(form).getByLabelText('库学科'), { target: { value: 'math' } });
    fireEvent.change(within(form).getByLabelText('库版本'), { target: { value: 'rj' } });
    fireEvent.click(within(form).getByTestId('textbook-library-create-submit'));

    const error = await screen.findByTestId('textbook-library-create-error');
    expect(error).toHaveTextContent('新建逻辑库失败（LIBRARY_CONFLICT）');
    expect(error).toHaveTextContent('同一范围（学科/版本/年级）的逻辑库已存在。');
    // 输入保留、对话框仍在、没有成功提示
    expect((within(form).getByLabelText('库显示名') as HTMLInputElement).value).toBe('我的教材');
    expect(screen.queryByTestId('textbook-notice')).toBeNull();
  });

  it('分类字典不可用时不让提交并说明原因', async () => {
    stubApi((url) => {
      if (url.includes('/textbook-taxonomy')) return failed(500, { code: 'DICT_DOWN', message: '字典不可用' });
      if (url.includes('/textbook-libraries')) return ok({ libraries: [] });
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<TextbookWorkspace />);

    fireEvent.click(await screen.findByTestId('textbook-library-create-open'));
    const form = await screen.findByTestId('textbook-library-create');
    expect(within(form).getByTestId('textbook-library-create-dict-error')).toBeInTheDocument();
    fireEvent.change(within(form).getByLabelText('库显示名'), { target: { value: '我的教材' } });
    expect(within(form).getByTestId('textbook-library-create-submit')).toBeDisabled();
  });
});

describe('教材管理页 · 逻辑库删除', () => {
  it('卡片二次确认后彻底删除，DELETE 带 expectedRevision，列表刷新后卡片消失', async () => {
    let deleted = false;
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('/textbook-libraries/lib-base') && init.method === 'DELETE') {
        deleted = true;
        return { ok: true, status: 204, json: async () => null } as Response;
      }
      if (url.includes('kind=base')) return ok({ libraries: deleted ? [] : [library()] });
      return ok({ libraries: [] });
    });
    render(<TextbookWorkspace />);

    await screen.findByRole('link', { name: /七年级数学基础库/ });
    fireEvent.click(screen.getByTestId('textbook-library-delete-lib-base'));
    expect(screen.getByTestId('textbook-library-confirm-lib-base')).toBeTruthy();
    expect(screen.getByText(/彻底删除逻辑库「七年级数学基础库」/)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('textbook-library-confirm-lib-base'));
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes('/textbook-libraries/lib-base') &&
          (init as RequestInit)?.method === 'DELETE',
      );
      expect(call).toBeTruthy();
      expect(JSON.parse(String((call?.[1] as RequestInit).body))).toEqual({ expectedRevision: 5 });
    });
    await waitFor(() => expect(screen.queryByTestId('textbook-library-card-lib-base')).toBeNull());
    expect(screen.getByTestId('textbook-library-notice')).toHaveTextContent('已彻底删除逻辑库');
  });

  it('409 冲突：显示服务端 code 并刷新列表', async () => {
    let listCalls = 0;
    stubApi((url, init) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('/textbook-libraries/lib-base') && init.method === 'DELETE') {
        return failed(409, { code: 'REVISION_CONFLICT', message: '逻辑库已被修改。' });
      }
      if (url.includes('kind=base')) {
        listCalls += 1;
        return ok({ libraries: [library()] });
      }
      return ok({ libraries: [] });
    });
    render(<TextbookWorkspace />);

    await screen.findByRole('link', { name: /七年级数学基础库/ });
    fireEvent.click(screen.getByTestId('textbook-library-delete-lib-base'));
    fireEvent.click(screen.getByTestId('textbook-library-confirm-lib-base'));

    const error = await screen.findByTestId('textbook-library-delete-error');
    expect(error).toHaveTextContent('删除冲突（REVISION_CONFLICT）');
    expect(error).toHaveTextContent('逻辑库已被修改。');
    await waitFor(() => expect(listCalls).toBeGreaterThan(1));
  });
});
