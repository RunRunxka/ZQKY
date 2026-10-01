import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { KnowledgeImportView } from '@/contracts/knowledge';
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
