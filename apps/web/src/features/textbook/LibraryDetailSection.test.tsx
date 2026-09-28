import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type {
  DocumentDetail,
  DocumentSummary,
  LibraryDetail,
  TextbookTaxonomy,
} from '@/contracts/textbook';
import { LibraryDetailSection } from './LibraryDetailSection';

const TAXONOMY: TextbookTaxonomy = {
  stages: [{ id: 'stage-j', label: '初中' }],
  grades: [{ id: 'g7', label: '七年级', stageId: 'stage-j' }],
  subjects: [{ id: 'math', label: '数学' }],
  editions: [{ id: 'rj', label: '人教版' }],
};

function documentSummary(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    documentId: 'doc-1',
    ownerId: 'system',
    title: '七年级数学上册',
    libraryIds: ['lib-1'],
    gradeIds: ['g7'],
    subjectId: 'math',
    editionId: 'rj',
    metadataRevisionId: 'meta-1',
    currentRevision: {
      revisionId: 'rev-1',
      originalFileSha256: 'orig',
      normalizedTextSha256: 'norm',
      parserVersion: 'p1',
      charCount: 5000,
      chunkCount: 12,
      createdAt: '2026-09-20T00:00:00Z',
    },
    pendingRevisionId: null,
    deletedAt: null,
    revision: 4,
    ...overrides,
  };
}

function libraryDetail(): LibraryDetail {
  return {
    libraryId: 'lib-1',
    kind: 'base',
    ownerId: 'system',
    displayName: '七年级数学基础库',
    gradeId: 'g7',
    subjectId: 'math',
    editionId: 'rj',
    documentCount: 2,
    readyDocumentCount: 1,
    revision: 3,
    deletedAt: null,
    documents: [
      documentSummary(),
      documentSummary({
        documentId: 'doc-2',
        title: '七年级数学下册',
        currentRevision: null,
        pendingRevisionId: 'rev-2',
      }),
    ],
  };
}

function documentDetail(title: string): DocumentDetail {
  return {
    ...documentSummary({ title }),
    metadata: {
      metadataRevisionId: 'meta-1',
      title,
      stageId: 'stage-j',
      gradeIds: ['g7'],
      subjectId: 'math',
      editionId: 'rj',
      publicationLabel: '2024 年版',
      volumeLabel: '上册',
    },
    warnings: [],
  };
}

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response;
const failed = (status: number, body: unknown) =>
  ({ ok: false, status, json: async () => body }) as Response;

function stubApi(handler: (url: string, init: RequestInit) => Response) {
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
});

async function rowFor(title: string): Promise<HTMLElement> {
  const items = await screen.findAllByRole('listitem');
  const row = items.find((item) => item.textContent?.includes(title));
  if (!row) throw new Error(`未找到书册行：${title}`);
  return row;
}

describe('教材库详情', () => {
  it('加载后展示库信息与各册修订状态', async () => {
    stubApi((url) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('/textbook-libraries/lib-1')) return ok(libraryDetail());
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<LibraryDetailSection libraryId="lib-1" />);

    expect(await screen.findByRole('heading', { name: '七年级数学基础库' })).toBeInTheDocument();
    expect(screen.getByText('可检索')).toBeInTheDocument();
    expect(screen.getByText('尚不可检索')).toBeInTheDocument();
    expect(screen.getByText('有待入库修订')).toBeInTheDocument();
    expect(screen.getByText('字符 5000')).toBeInTheDocument();
    expect(screen.getByText('块 12')).toBeInTheDocument();
    expect(screen.getByText('解析器 p1')).toBeInTheDocument();
    expect(screen.getByText('尚无已发布修订')).toBeInTheDocument();
  });

  it('读取失败显示错误与重试，不显示空库', async () => {
    let attempt = 0;
    stubApi((url) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('/textbook-libraries/lib-1')) {
        attempt += 1;
        if (attempt === 1) {
          return failed(503, {
            code: 'SERVICE_UNAVAILABLE',
            message: '后端服务不可用。',
            retryable: true,
          });
        }
        return ok(libraryDetail());
      }
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<LibraryDetailSection libraryId="lib-1" />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('教材库读取失败');
    expect(screen.queryByText('该库还没有书册')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('字符 5000')).toBeInTheDocument();
  });

  it('编辑分类遇 409 时提示冲突并保留用户输入', async () => {
    let detailLoads = 0;
    let patchBody: Record<string, unknown> | null = null;
    stubApi((url, init) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('/textbook-libraries/lib-1')) return ok(libraryDetail());
      if (url.includes('/textbooks/doc-1')) {
        if (init.method === 'PATCH') {
          patchBody = JSON.parse(String(init.body)) as Record<string, unknown>;
          return failed(409, {
            code: 'REVISION_CONFLICT',
            message: '书册已被其他操作修改。',
            retryable: false,
          });
        }
        detailLoads += 1;
        return ok(documentDetail(detailLoads === 1 ? '七年级数学上册' : '服务端最新标题'));
      }
      throw new Error(`未预期的请求 ${url} ${String(init.method)}`);
    });
    render(<LibraryDetailSection libraryId="lib-1" />);

    const row = await rowFor('七年级数学上册');
    fireEvent.click(within(row).getByRole('button', { name: '编辑分类' }));

    const titleInput = await screen.findByLabelText('标题');
    expect(titleInput).toHaveValue('七年级数学上册');

    fireEvent.change(titleInput, { target: { value: '七年级数学上册（修订）' } });
    fireEvent.click(screen.getByRole('button', { name: '保存分类' }));

    const alert = await screen.findByText(/保存冲突（REVISION_CONFLICT）/);
    expect(alert).toHaveTextContent('你的填写已保留');
    // 用户输入未被覆盖
    expect(screen.getByLabelText('标题')).toHaveValue('七年级数学上册（修订）');
    // 服务端最新分类单独展示，供比较
    expect(screen.getByText(/服务端最新分类：服务端最新标题/)).toBeInTheDocument();
    expect(patchBody).toMatchObject({ expectedRevision: 4 });
  });

  it('删除需二次确认并带 expectedRevision', async () => {
    const deletedCalls: { url: string; body: unknown }[] = [];
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('/textbook-libraries/lib-1')) return ok(libraryDetail());
      if (url.includes('/textbooks/doc-1') && init.method === 'DELETE') {
        deletedCalls.push({ url, body: JSON.parse(String(init.body)) });
        return ok({ ...documentSummary(), deletedAt: '2026-09-28T00:00:00Z' });
      }
      throw new Error(`未预期的请求 ${url} ${String(init.method)}`);
    });
    render(<LibraryDetailSection libraryId="lib-1" />);

    const row = await rowFor('七年级数学上册');
    expect(deletedCalls).toHaveLength(0);
    fireEvent.click(within(row).getByRole('button', { name: '删除' }));
    expect(screen.getByText(/确认删除《七年级数学上册》/)).toBeInTheDocument();

    fireEvent.click(within(row).getByRole('button', { name: '确认删除' }));

    await waitFor(() => expect(deletedCalls).toHaveLength(1));
    expect(deletedCalls[0].url).toBe('/api/v1/textbooks/doc-1');
    expect(deletedCalls[0].body).toEqual({ expectedRevision: 4 });
    expect(await screen.findByText(/已删除《七年级数学上册》/)).toBeInTheDocument();
    // 删除后重新读取库列表（不乐观地本地移除行后又留下脏状态）
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([url]) => String(url).includes('/textbook-libraries/lib-1'))
          .length,
      ).toBeGreaterThan(1),
    );
  });

  it('来源预览读取受控原文并显示定位，失败如实报错', async () => {
    let sourceCalls = 0;
    stubApi((url) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('/textbook-libraries/lib-1')) return ok(libraryDetail());
      if (url.includes('/textbook-revisions/rev-1/source')) {
        sourceCalls += 1;
        if (sourceCalls === 1) {
          return failed(404, {
            code: 'DOCUMENT_REVISION_NOT_FOUND',
            message: '修订不存在。',
            retryable: false,
          });
        }
        return ok({
          documentRevisionId: 'rev-1',
          normalizedTextSha256: 'abcdef0123456789',
          charStart: 0,
          charEnd: 1200,
          text: '第一段原文',
          locator: {
            kind: 'markdown',
            lineStart: 1,
            lineEnd: 10,
            pageStart: null,
            pageEnd: null,
            blockStart: null,
            blockEnd: null,
          },
        });
      }
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<LibraryDetailSection libraryId="lib-1" />);

    const row = await rowFor('七年级数学上册');
    fireEvent.click(within(row).getByRole('button', { name: '来源预览' }));
    fireEvent.click(screen.getByRole('button', { name: '读取原文' }));

    expect(await screen.findByText(/原文读取失败/)).toBeInTheDocument();
    expect(screen.getByText(/修订不存在/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('第一段原文')).toBeInTheDocument();
    expect(screen.getByText('类型 markdown · 行 1–10')).toBeInTheDocument();
  });
});

describe('教材库详情 · 更新入口', () => {
  it('更新时预取分类预填，并在 metadataJson 中带上目标书册与期望修订', async () => {
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('/textbook-libraries/lib-1')) return ok(libraryDetail());
      if (url.includes('/textbook-imports') && init.method === 'POST') {
        return ok({
          draft: {
            importId: 'imp-9',
            ownerId: 'system',
            state: 'needs_review',
            revision: 1,
            uploadedFileName: 'book.md',
            uploadedBytes: 10,
            targetDocumentId: 'doc-1',
            expectedCurrentRevisionId: 'rev-1',
            metadata: null,
            metadataConfirmed: true,
            parsed: null,
            warnings: [],
            errorCode: null,
            canCommit: false,
            createdAt: '2026-09-28T00:00:00Z',
          },
        });
      }
      if (url.includes('/textbooks/doc-1')) return ok(documentDetail('七年级数学上册'));
      throw new Error(`未预期的请求 ${url} ${String(init.method)}`);
    });
    render(<LibraryDetailSection libraryId="lib-1" />);

    const row = await rowFor('七年级数学上册');
    fireEvent.click(within(row).getByRole('button', { name: '更新' }));

    // 目标信息来自当前列表的已发布修订；分类预填来自 GET /textbooks/{id}
    expect(await screen.findByText(/期望修订 rev-1/)).toBeInTheDocument();
    const titleInput = await screen.findByLabelText('标题');
    await waitFor(() => expect(titleInput).toHaveValue('七年级数学上册'));
    expect(screen.getByLabelText('册次')).toHaveValue('上册');

    fireEvent.change(screen.getByLabelText('教材文件'), {
      target: { files: [new File(['# 标题'], 'book.md', { type: 'text/markdown' })] },
    });
    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith('/textbook-imports') &&
            (init as RequestInit | undefined)?.method === 'POST',
        ),
      ).toBe(true);
    });
    const createCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith('/textbook-imports') &&
        (init as RequestInit | undefined)?.method === 'POST',
    );
    const form = (createCall?.[1] as RequestInit).body as FormData;
    expect(JSON.parse(String(form.get('metadataJson')))).toEqual({
      metadata: {
        title: '七年级数学上册',
        stageId: 'stage-j',
        gradeIds: ['g7'],
        subjectId: 'math',
        editionId: 'rj',
        publicationLabel: '2024 年版',
        volumeLabel: '上册',
      },
      confirmMetadata: true,
      targetDocumentId: 'doc-1',
      expectedCurrentRevisionId: 'rev-1',
    });
  });
});
