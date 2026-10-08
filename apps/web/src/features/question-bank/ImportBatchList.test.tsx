/**
 * 导入批次列表：放弃 / 彻底删除的三态（可删 / 已确认只保留 / 被引用 409 给计数与放弃入口）。
 *
 * 断言方向（设计 2.3 + 任务卡）：
 * - 未确认批次同时有「放弃」与「彻底删除」；已确认批次两者都没有，并有保留原因；
 * - 「彻底删除」二次确认文案必须说明「删除批次与解析产物…原件保留」；
 * - DELETE 走 `/question-imports/{id}`；成功刷新列表；
 * - 409 `IMPORT_IN_USE` 渲染来源登记数与并入草稿数，并保留「改为放弃」快捷入口。
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { QuestionImportSummary } from '@/contracts/question-bank';
import { ImportBatchList } from './ImportBatchList';

function summary(overrides: Partial<QuestionImportSummary> = {}): QuestionImportSummary {
  return {
    importId: 'imp-1',
    ownerId: 'local-user',
    state: 'needs_review',
    revision: 2,
    uploadedFileName: '七年级数学题库.md',
    uploadedBytes: 2048,
    draftCount: 6,
    reviewedCount: 6,
    unassignedCount: 2,
    warnings: [],
    createdAt: '2026-10-07T12:30:00Z',
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
    return String(url).includes(fragment) && (!method || (request?.method ?? 'GET') === method);
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('导入批次：放弃与彻底删除入口', () => {
  it('未确认批次同时有放弃与彻底删除；已确认批次两者都没有且给出保留原因', async () => {
    stubApi(() =>
      jsonResponse(true, 200, {
        imports: [
          summary(),
          summary({
            importId: 'imp-done',
            state: 'confirmed',
            uploadedFileName: '闭环测试_针对练习题库.docx',
            draftCount: 6,
          }),
          // 已取消（放弃过）的批次：放弃入口按既有规则不再显示，但必须有彻底删除出口
          summary({ importId: 'imp-cancelled', state: 'cancelled', uploadedFileName: '误上传.docx' }),
        ],
      }),
    );
    render(<ImportBatchList refreshToken={0} />);

    expect(await screen.findByRole('button', { name: '放弃批次 七年级数学题库.md' })).toBeInTheDocument();
    expect(screen.getByTestId('qb-import-delete-imp-1')).toHaveTextContent('彻底删除');
    expect(screen.getByTestId('qb-import-delete-imp-cancelled')).toHaveTextContent('彻底删除');
    expect(
      screen.queryByRole('button', { name: '放弃批次 误上传.docx' }),
    ).not.toBeInTheDocument();
    // 已确认批次：不提供任何删除入口（服务端也会 409）
    expect(
      screen.queryByRole('button', { name: '放弃批次 闭环测试_针对练习题库.docx' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId('qb-import-delete-imp-done')).not.toBeInTheDocument();
    expect(screen.getByTestId('qb-import-retained-imp-done')).toHaveTextContent(
      '来源追溯必须保留',
    );
  });

  it('彻底删除二次确认说明「删除批次与解析产物…原件保留」，成功后刷新列表', async () => {
    let listCalls = 0;
    const prompts: string[] = [];
    const confirmSpy = vi.fn((message?: string) => {
      prompts.push(String(message ?? ''));
      return true;
    });
    vi.stubGlobal('confirm', confirmSpy);
    const fetchMock = stubApi((url, init) => {
      const method = (init.method ?? 'GET').toUpperCase();
      if (method === 'DELETE' && url.endsWith('/api/v1/question-imports/imp-1')) {
        return jsonResponse(true, 200, { deleted: true, importId: 'imp-1' });
      }
      if (method === 'GET' && url.endsWith('/api/v1/question-imports')) {
        listCalls += 1;
        return jsonResponse(true, 200, {
          imports: listCalls === 1 ? [summary()] : [],
        });
      }
      return jsonResponse(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: `${method} ${url}` });
    });
    render(<ImportBatchList refreshToken={0} />);

    fireEvent.click(await screen.findByTestId('qb-import-delete-imp-1'));
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    const prompt = prompts[0] ?? '';
    expect(prompt).toContain('删除批次与解析产物');
    expect(prompt).toContain('原件保留');
    expect(prompt).toContain('不可恢复');

    await waitFor(() =>
      expect(calls(fetchMock, '/question-imports/imp-1', 'DELETE')).toHaveLength(1),
    );
    await waitFor(() => expect(listCalls).toBe(2));
    expect(await screen.findByText('还没有导入批次')).toBeInTheDocument();
  });

  it('被引用 409：逐项渲染来源登记与并入草稿计数，并保留「改为放弃」入口', async () => {
    const fetchMock = stubApi((url, init) => {
      const method = (init.method ?? 'GET').toUpperCase();
      if (method === 'DELETE' && url.endsWith('/api/v1/question-imports/imp-1')) {
        return jsonResponse(false, 409, {
          code: 'IMPORT_IN_USE',
          message: '该批次的草稿被正式题引用（来源追溯或并入记录存在），不能彻底删除。',
          retryable: false,
          details: { sourceRefCount: 2, mergedDraftCount: 1 },
        });
      }
      if (method === 'GET' && url.endsWith('/api/v1/question-imports')) {
        return jsonResponse(true, 200, { imports: [summary()] });
      }
      return jsonResponse(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: `${method} ${url}` });
    });
    vi.stubGlobal('confirm', vi.fn(() => true));
    render(<ImportBatchList refreshToken={0} />);

    fireEvent.click(await screen.findByTestId('qb-import-delete-imp-1'));

    const blocked = await screen.findByTestId('qb-import-delete-blocked-imp-1');
    expect(blocked).toHaveTextContent('IMPORT_IN_USE');
    const counts = within(blocked).getByTestId('qb-import-delete-counts-imp-1');
    expect(counts).toHaveTextContent('正式题来源登记：2 处');
    expect(counts).toHaveTextContent('已并入正式题的草稿：1 道');
    // 保留「改为放弃」快捷入口（放弃只收起，不删记录）
    expect(within(blocked).getByRole('button', { name: /改为放弃/ })).toBeInTheDocument();
    // 失败没有产生第二次删除请求，也没有把批次从列表里去掉
    expect(calls(fetchMock, '/question-imports/imp-1', 'DELETE')).toHaveLength(1);
    expect(screen.getByText('七年级数学题库.md')).toBeInTheDocument();
  });

  it('已确认批次 409 守卫（服务端权威）：原因如实渲染，不假装删除成功', async () => {
    const fetchMock = stubApi((url, init) => {
      const method = (init.method ?? 'GET').toUpperCase();
      if (method === 'DELETE' && url.endsWith('/api/v1/question-imports/imp-1')) {
        return jsonResponse(false, 409, {
          code: 'IMPORT_ALREADY_CONFIRMED',
          message: '该导入已确认入库，正式题源自它，来源追溯必须保留；不能彻底删除。',
          retryable: false,
        });
      }
      if (method === 'GET' && url.endsWith('/api/v1/question-imports')) {
        // 列表里该批次仍是未确认状态（并发确认的场景），入口可见但服务端拒绝
        return jsonResponse(true, 200, { imports: [summary()] });
      }
      return jsonResponse(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: `${method} ${url}` });
    });
    vi.stubGlobal('confirm', vi.fn(() => true));
    render(<ImportBatchList refreshToken={0} />);

    fireEvent.click(await screen.findByTestId('qb-import-delete-imp-1'));

    const blocked = await screen.findByTestId('qb-import-delete-blocked-imp-1');
    expect(blocked).toHaveTextContent('IMPORT_ALREADY_CONFIRMED');
    expect(blocked).toHaveTextContent('来源追溯必须保留');
    // 没有 counts 就不编造计数
    expect(blocked).toHaveTextContent('服务端没有给出逐项计数');
    expect(calls(fetchMock, '/question-imports/imp-1', 'DELETE')).toHaveLength(1);
  });
});
