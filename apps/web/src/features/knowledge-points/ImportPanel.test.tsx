import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { KnowledgeImportSummary, KnowledgeImportView } from '@/contracts/knowledge';
import { ImportPanel } from './ImportPanel';

function importView(overrides: Partial<KnowledgeImportView> = {}): KnowledgeImportView {
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
    headers: ['编码', '名称'],
    mapping: { code: '编码', name: '名称' },
    warnings: [],
    issues: [],
    rows: [
      {
        rowNo: 1,
        name: '数轴',
        code: 'M.7.2',
        parentCode: null,
        description: '',
        aliases: [],
        targetKnowledgePointId: null,
        baseRevision: null,
        baseVersion: null,
        decision: null,
        issues: [],
      },
    ],
    createdAt: '2026-09-30T00:00:00Z',
    updatedAt: '2026-09-30T00:00:00Z',
    ...overrides,
  };
}

function json(ok: boolean, status: number, body: unknown): Response {
  return { ok, status, json: async () => body } as Response;
}

function stubApi(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
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

describe('导入面板：批次列表与选中', () => {
  it('批次卡有稳定 testid；点击后把批次 id 交给调用方', async () => {
    stubApi((url, init) => {
      const method = (init.method ?? 'GET').toUpperCase();
      if (method === 'GET' && url.endsWith('/api/v1/knowledge-imports?limit=100')) {
        return json(true, 200, {
          items: [
            {
              importId: 'imp-file-1',
              source: 'file',
              subjectId: 'math',
              state: 'reviewing',
              revision: 2,
              rowCount: 1,
              blockingIssueCount: 0,
              createdAt: '2026-09-30T00:00:00Z',
              updatedAt: '2026-09-30T00:00:00Z',
            },
          ],
          total: 1,
          offset: 0,
          limit: 100,
        });
      }
      return json(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: `${method} ${url}` });
    });
    const onSelectImport = vi.fn();
    render(
      <ImportPanel
        subjects={[{ id: 'math', label: '数学' }]}
        taxonomyReady
        defaultSubjectId="math"
        selectedImportId={null}
        onSelectImport={onSelectImport}
        refreshToken={0}
      />,
    );

    const card = await screen.findByTestId('kp-import-card-imp-file-1');
    expect(card).toHaveTextContent('表格批次');
    expect(screen.getByText('未选择批次')).toBeInTheDocument();

    fireEvent.click(card);
    expect(onSelectImport).toHaveBeenCalledWith('imp-file-1');
  });

  it('选中批次后渲染校对面板，并显示批次文件名', async () => {
    const view = importView();
    stubApi((url, init) => {
      const method = (init.method ?? 'GET').toUpperCase();
      if (method === 'GET' && url.endsWith('/api/v1/knowledge-imports?limit=100')) {
        return json(true, 200, {
          items: [
            {
              importId: view.importId,
              source: view.source,
              subjectId: view.subjectId,
              state: view.state,
              revision: view.revision,
              rowCount: view.rows.length,
              blockingIssueCount: 0,
              createdAt: view.createdAt,
              updatedAt: view.updatedAt,
            },
          ],
          total: 1,
          offset: 0,
          limit: 100,
        });
      }
      if (method === 'GET' && url.endsWith('/api/v1/knowledge-imports/imp-file-1')) {
        return json(true, 200, view);
      }
      return json(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: `${method} ${url}` });
    });
    render(
      <ImportPanel
        subjects={[{ id: 'math', label: '数学' }]}
        taxonomyReady
        defaultSubjectId="math"
        selectedImportId="imp-file-1"
        onSelectImport={vi.fn()}
        refreshToken={0}
      />,
    );

    await waitFor(() =>
      expect(screen.getByTestId('kp-import-file')).toHaveTextContent('知识点.csv'),
    );
    expect(screen.getByTestId('kp-row-1')).toHaveTextContent('数轴');
  });
});

describe('导入面板：放弃未确认批次', () => {
  const summary = (state: KnowledgeImportSummary['state'], revision: number) => ({
    importId: 'imp-file-1',
    source: 'file' as const,
    subjectId: 'math',
    state,
    revision,
    rowCount: 1,
    blockingIssueCount: 0,
    // 真实批次都有上传文件名：主标题用文件名，短号进次行小字
    uploadedFileName: '知识点-导入.csv',
    createdAt: '2026-09-30T00:00:00Z',
    updatedAt: '2026-09-30T00:00:00Z',
  });

  function renderPanel(onSelectImport = vi.fn()) {
    render(
      <ImportPanel
        subjects={[{ id: 'math', label: '数学' }]}
        taxonomyReady
        defaultSubjectId="math"
        selectedImportId={null}
        onSelectImport={onSelectImport}
        refreshToken={0}
      />,
    );
    return onSelectImport;
  }

  it('只对未确认批次显示放弃按钮；放弃带 expectedRevision，成功后刷新为已取消', async () => {
    let listCalls = 0;
    stubApi((url, init) => {
      const method = (init.method ?? 'GET').toUpperCase();
      if (method === 'POST' && url.endsWith('/api/v1/knowledge-imports/imp-file-1/discard')) {
        expect(JSON.parse(String(init.body))).toEqual({ expectedRevision: 3 });
        return json(true, 200, importView({ state: 'cancelled', revision: 4 }));
      }
      if (method === 'GET' && url.endsWith('/api/v1/knowledge-imports?limit=100')) {
        listCalls += 1;
        return json(true, 200, {
          items: [
            summary(listCalls === 1 ? 'reviewing' : 'cancelled', listCalls === 1 ? 3 : 4),
            {
              ...summary('confirmed', 2),
              importId: 'imp-file-done',
              uploadedFileName: '已确认批次.csv',
            },
          ],
          total: 2,
          offset: 0,
          limit: 100,
        });
      }
      return json(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: `${method} ${url}` });
    });
    vi.stubGlobal('confirm', vi.fn(() => true));
    renderPanel();

    // 主标题是真实上传文件名，短号与来源进次行小字（不再把短号当标题）
    const card = await screen.findByText('知识点-导入.csv');
    expect(card.closest('button')).toHaveTextContent('批次 imp-file');
    // 未确认批次（reviewing）有入口；已确认批次没有
    const discard = await screen.findByRole('button', { name: '放弃批次 知识点-导入.csv' });
    expect(
      screen.queryByRole('button', { name: '放弃批次 已确认批次.csv' }),
    ).not.toBeInTheDocument();
    expect(screen.getByText('已确认入库')).toBeInTheDocument();

    fireEvent.click(discard);

    expect(await screen.findByText('已取消')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '放弃批次 知识点-导入.csv' }),
    ).not.toBeInTheDocument();
    expect(listCalls).toBe(2);
  });

  it('放弃失败如实显示错误码与原因；409 时刷新列表取最新 revision', async () => {
    let listCalls = 0;
    stubApi((url, init) => {
      const method = (init.method ?? 'GET').toUpperCase();
      if (method === 'POST' && url.endsWith('/api/v1/knowledge-imports/imp-file-1/discard')) {
        return json(false, 409, {
          code: 'REVISION_CONFLICT',
          message: '批次已被其他操作更新（当前 revision=4），请刷新后重试。',
          retryable: false,
        });
      }
      if (method === 'GET' && url.endsWith('/api/v1/knowledge-imports?limit=100')) {
        listCalls += 1;
        return json(true, 200, { items: [summary('reviewing', 4)], total: 1, offset: 0, limit: 100 });
      }
      return json(false, 500, { code: 'UNEXPECTED_TEST_REQUEST', message: `${method} ${url}` });
    });
    vi.stubGlobal('confirm', vi.fn(() => true));
    renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: '放弃批次 知识点-导入.csv' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('REVISION_CONFLICT');
    expect(alert).toHaveTextContent('批次已被其他操作更新（当前 revision=4），请刷新后重试。');
    expect(screen.queryByText('已取消')).not.toBeInTheDocument();
    // 冲突后刷新取最新 revision，入口仍在（用户可再次确认）
    await waitFor(() => expect(listCalls).toBe(2));
    expect(
      await screen.findByRole('button', { name: '放弃批次 知识点-导入.csv' }),
    ).toBeEnabled();
  });
});
