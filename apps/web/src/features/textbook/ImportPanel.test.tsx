import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import {
  MAX_UPLOAD_BYTES,
  type DocumentMetadataInput,
  type ImportDraftView,
  type ImportParsedView,
  type LibrarySummary,
  type TextbookTaxonomy,
} from '@/contracts/textbook';
import { ImportPanel } from './ImportPanel';
import { buildTaxonomyIndex } from './taxonomy';

const TAXONOMY: TextbookTaxonomy = {
  stages: [{ id: 'stage-j', label: '初中' }],
  grades: [
    { id: 'g7', label: '七年级', stageId: 'stage-j' },
    { id: 'g8', label: '八年级', stageId: 'stage-j' },
  ],
  subjects: [{ id: 'math', label: '数学' }],
  editions: [{ id: 'rj', label: '人教版' }],
};
const index = buildTaxonomyIndex(TAXONOMY);

const LIBRARY: LibrarySummary = {
  libraryId: 'lib-1',
  kind: 'base',
  ownerId: 'system',
  displayName: '七年级数学基础库',
  gradeId: 'g7',
  subjectId: 'math',
  editionId: 'rj',
  documentCount: 2,
  readyDocumentCount: 1,
  revision: 1,
  deletedAt: null,
};

const METADATA: DocumentMetadataInput = {
  title: '七年级数学上册',
  stageId: 'stage-j',
  gradeIds: ['g7'],
  subjectId: 'math',
  editionId: 'rj',
  publicationLabel: '2024 年版',
  volumeLabel: '上册',
};

const PARSED: ImportParsedView = {
  charCount: 1200,
  chunkCount: 3,
  bodyChunkCount: 2,
  exerciseChunkCount: 1,
  needsOcr: false,
  sourceKind: 'markdown',
  pageCount: null,
  blockCount: 8,
  warnings: [],
  preview: [
    {
      ordinal: 0,
      charStart: 0,
      charEnd: 400,
      region: 'body',
      chapterPath: ['第一章'],
      text: '第一段正文',
    },
  ],
};

function draft(overrides: Partial<ImportDraftView> = {}): ImportDraftView {
  return {
    importId: 'imp-1',
    ownerId: 'local-user',
    state: 'extracting',
    revision: 1,
    uploadedFileName: 'book.md',
    uploadedBytes: 2048,
    targetDocumentId: null,
    expectedCurrentRevisionId: null,
    metadata: null,
    metadataConfirmed: false,
    parsed: null,
    warnings: [],
    errorCode: null,
    canCommit: false,
    createdAt: '2026-09-28T00:00:00Z',
    ...overrides,
  };
}

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response;
const failed = (status: number, body: unknown) =>
  ({ ok: false, status, json: async () => body }) as Response;

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function stubApi(handler: Handler) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

/** 只看阶段 chip（阶段文案同样出现在提示段落里，避免命中多元素）。 */
function stageText(): string {
  const chip = Array.from(document.querySelectorAll('.space-chip')).find((node) =>
    node.textContent?.startsWith('阶段：'),
  );
  return chip?.textContent ?? '';
}

function postCalls(fetchMock: ReturnType<typeof stubApi>, fragment: string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      String(url).includes(fragment) && (init as RequestInit | undefined)?.method === 'POST',
  );
}

beforeAll(() => {
  // jsdom 未实现 <dialog> 的方法；补最小实现以驱动 Modal
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

describe('导入面板', () => {
  it('拒绝不支持的文件类型并给出明确提示，且不发起上传', async () => {
    const fetchMock = stubApi((url) => {
      if (url.includes('/textbook-libraries')) return ok({ libraries: [LIBRARY] });
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<ImportPanel taxonomy={index} onClose={() => {}} />);

    fireEvent.change(screen.getByLabelText('教材文件'), {
      target: { files: [new File(['x'], '教材.txt', { type: 'text/plain' })] },
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('不支持的文件类型');
    expect(postCalls(fetchMock, '/textbook-imports')).toHaveLength(0);
  });

  it('超过 100 MiB 时前端先拒绝，不发起上传', async () => {
    const fetchMock = stubApi((url) => {
      if (url.includes('/textbook-libraries')) return ok({ libraries: [LIBRARY] });
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<ImportPanel taxonomy={index} onClose={() => {}} />);

    const big = new File(['x'], 'big.pdf', { type: 'application/pdf' });
    Object.defineProperty(big, 'size', { value: MAX_UPLOAD_BYTES + 1 });

    fireEvent.change(screen.getByLabelText('教材文件'), { target: { files: [big] } });

    expect(await screen.findByRole('alert')).toHaveTextContent('文件过大');
    expect(postCalls(fetchMock, '/textbook-imports')).toHaveLength(0);
  });

  it('按 IMPORT_STATE_LABEL 轮询阶段直到终态，并展示解析预览', async () => {
    let polls = 0;
    // 用闸门控制第一次轮询返回时机，保证中间阶段可观测（不依赖真实计时竞速）
    let releaseFirstPoll: () => void = () => {};
    const firstPollGate = new Promise<void>((resolve) => {
      releaseFirstPoll = resolve;
    });
    stubApi((url) => {
      if (url.includes('/textbook-libraries')) return ok({ libraries: [LIBRARY] });
      if (url.endsWith('/textbook-imports')) return ok({ draft: draft({ state: 'extracting' }) });
      if (url.includes('/textbook-imports/imp-1')) {
        polls += 1;
        if (polls === 1) return firstPollGate.then(() => ok(draft({ state: 'chunking' })));
        return ok(draft({ state: 'ready', parsed: PARSED, canCommit: true, revision: 3 }));
      }
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<ImportPanel taxonomy={index} onClose={() => {}} pollIntervalMs={60} />);

    fireEvent.change(screen.getByLabelText('教材文件'), {
      target: { files: [new File(['# 标题'], 'book.md', { type: 'text/markdown' })] },
    });
    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }));

    await waitFor(() => expect(stageText()).toBe('阶段：解析中'));

    // 放行第一次轮询：阶段来自服务端返回，不是前端推断
    await waitFor(() => expect(polls).toBe(1));
    releaseFirstPoll();
    await waitFor(() => expect(stageText()).toBe('阶段：分块中'));
    await waitFor(() => expect(stageText()).toBe('阶段：已入库'));

    // 预览字段来自服务端解析结果
    expect(screen.getByText('来源：Markdown 文本')).toBeInTheDocument();
    expect(screen.getByText('字符 1200')).toBeInTheDocument();
    expect(screen.getByText('正文块 2')).toBeInTheDocument();
    expect(screen.getByText('习题块 1')).toBeInTheDocument();
    expect(screen.getByText('第一段正文')).toBeInTheDocument();

    // 到达终态后停止轮询
    const settled = polls;
    await new Promise((resolve) => setTimeout(resolve, 200));
    expect(polls).toBe(settled);
  });

  it('needsOcr 时明确提示需要文本层，且不显示成功', async () => {
    stubApi((url) => {
      if (url.includes('/textbook-libraries')) return ok({ libraries: [LIBRARY] });
      return ok({
        draft: draft({
          state: 'needs_review',
          parsed: { ...PARSED, needsOcr: true, chunkCount: 0, preview: [] },
          canCommit: false,
        }),
      });
    });
    render(<ImportPanel taxonomy={index} onClose={() => {}} />);

    fireEvent.change(screen.getByLabelText('教材文件'), {
      target: { files: [new File(['x'], 'scan.pdf', { type: 'application/pdf' })] },
    });
    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }));

    expect(await screen.findByText(/需要文本层或人工处理/)).toBeInTheDocument();
    expect(screen.queryByText(/已提交入库任务/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '提交入库' })).toBeDisabled();
    // 禁用按钮必须给出具体原因，而不是笼统禁用
    expect(screen.getByText(/没有可用文本层/)).toBeInTheDocument();
  });

  it('警告需人工确认；提交带同一幂等键与服务端 revision，失败可重试复用', async () => {
    let commitCalls = 0;
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/textbook-libraries')) return ok({ libraries: [LIBRARY] });
      if (url.endsWith('/textbook-imports')) {
        return ok({
          draft: draft({
            state: 'needs_review',
            revision: 2,
            parsed: PARSED,
            warnings: ['存在重复标题'],
            canCommit: true,
          }),
        });
      }
      if (url.includes('/commit')) {
        commitCalls += 1;
        if (commitCalls === 1) {
          return failed(409, {
            code: 'REVISION_CONFLICT',
            message: '草稿已被其他操作修改。',
            retryable: false,
          });
        }
        // v1.1 冻结：commit 直接返回 JobView
        return ok({
          jobId: 'job-1',
          kind: 'ingest',
          state: 'queued',
          attempt: 1,
          progress: {
            documentsDone: 0,
            documentsTotal: 1,
            chunksDone: 0,
            chunksTotal: 3,
            currentTitle: null,
          },
          errorCode: null,
          errorMessage: null,
          retryable: false,
        });
      }
      if (url.includes('/textbook-imports/imp-1')) {
        return ok(draft({ state: 'queued', revision: 3, canCommit: false }));
      }
      throw new Error(`未预期的请求 ${url} ${String(init.method)}`);
    });

    render(<ImportPanel taxonomy={index} onClose={() => {}} />);
    fireEvent.change(screen.getByLabelText('教材文件'), {
      target: { files: [new File(['# 标题'], 'book.md', { type: 'text/markdown' })] },
    });
    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }));

    const libraryBox = await screen.findByRole('checkbox', { name: /七年级数学基础库/ });
    const commitButton = screen.getByRole('button', { name: '提交入库' });
    expect(commitButton).toBeDisabled();

    fireEvent.click(libraryBox);
    expect(commitButton).toBeDisabled(); // 警告未确认

    fireEvent.click(screen.getByRole('checkbox', { name: /我已核对以上警告/ }));
    expect(commitButton).toBeEnabled();

    fireEvent.click(commitButton);
    expect(await screen.findByText(/REVISION_CONFLICT/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重试提交' })).toBeInTheDocument();
    // 失败时保留用户选择
    expect(libraryBox).toBeChecked();

    fireEvent.click(screen.getByRole('button', { name: '重试提交' }));
    expect(await screen.findByText(/已提交入库任务（任务 job-1）/)).toBeInTheDocument();

    const commits = postCalls(fetchMock, '/commit');
    expect(commits).toHaveLength(2);
    const first = JSON.parse(String((commits[0][1] as RequestInit).body));
    const second = JSON.parse(String((commits[1][1] as RequestInit).body));
    expect(first).toEqual({
      expectedRevision: 2,
      submissionId: expect.any(String),
      libraryIds: ['lib-1'],
      acknowledgeWarnings: true,
    });
    expect(first.submissionId).toHaveLength(36); // crypto.randomUUID
    expect(second.submissionId).toBe(first.submissionId);
  });

  it('更新模式在 metadataJson 中携带目标书册与期望修订，并预填分类', async () => {
    const fetchMock = stubApi((url) => {
      if (url.includes('/textbook-libraries')) return ok({ libraries: [LIBRARY] });
      if (url.endsWith('/textbook-imports')) {
        return ok({
          draft: draft({
            state: 'needs_review',
            parsed: PARSED,
            metadata: METADATA,
            metadataConfirmed: true,
            canCommit: true,
            targetDocumentId: 'doc-1',
          }),
        });
      }
      throw new Error(`未预期的请求 ${url}`);
    });
    render(
      <ImportPanel
        taxonomy={index}
        onClose={() => {}}
        updateTarget={{
          documentId: 'doc-1',
          title: '七年级数学上册',
          expectedCurrentRevisionId: 'rev-1',
        }}
        initialMetadata={METADATA}
      />,
    );

    // 目标信息与预填（来自 GET /textbooks/{id}）
    expect(screen.getByText(/期望修订 rev-1/)).toBeInTheDocument();
    expect(screen.getByLabelText('标题')).toHaveValue('七年级数学上册');

    fireEvent.change(screen.getByLabelText('教材文件'), {
      target: { files: [new File(['# 标题'], 'book.md', { type: 'text/markdown' })] },
    });
    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }));

    await waitFor(() => expect(postCalls(fetchMock, '/textbook-imports')).toHaveLength(1));
    const form = (postCalls(fetchMock, '/textbook-imports')[0][1] as RequestInit).body as FormData;
    expect(JSON.parse(String(form.get('metadataJson')))).toEqual({
      metadata: METADATA,
      confirmMetadata: true,
      targetDocumentId: 'doc-1',
      expectedCurrentRevisionId: 'rev-1',
    });
    expect(await screen.findByText(/草稿已绑定目标书册 doc-1/)).toBeInTheDocument();
  });

  it('期望修订过期（409）时保留填写、提示刷新并通知父级', async () => {
    const stale = vi.fn();
    stubApi((url) => {
      if (url.includes('/textbook-libraries')) return ok({ libraries: [LIBRARY] });
      if (url.endsWith('/textbook-imports')) {
        return failed(409, {
          code: 'REVISION_CONFLICT',
          message: '该书册当前修订已变化。',
          retryable: false,
        });
      }
      throw new Error(`未预期的请求 ${url}`);
    });
    render(
      <ImportPanel
        taxonomy={index}
        onClose={() => {}}
        onTargetStale={stale}
        updateTarget={{
          documentId: 'doc-1',
          title: '七年级数学上册',
          expectedCurrentRevisionId: 'rev-old',
        }}
        initialMetadata={METADATA}
      />,
    );

    fireEvent.change(screen.getByLabelText('教材文件'), {
      target: { files: [new File(['# 标题'], 'book.md', { type: 'text/markdown' })] },
    });
    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }));

    expect(
      await screen.findByText(/该书册已被更新，请刷新后重试（REVISION_CONFLICT）/),
    ).toBeInTheDocument();
    // 用户填写未被清空
    expect(screen.getByLabelText('标题')).toHaveValue('七年级数学上册');
    expect(stale).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '刷新书册信息' })).toBeInTheDocument();
  });

  it('逻辑库列表失败显示错误与重试，而不是空的可选项', async () => {
    stubApi((url) => {
      if (url.includes('/textbook-libraries')) {
        return failed(503, {
          code: 'SERVICE_UNAVAILABLE',
          message: '后端服务不可用。',
          retryable: true,
        });
      }
      return ok({ draft: draft({ state: 'needs_review', parsed: PARSED, canCommit: true }) });
    });
    render(<ImportPanel taxonomy={index} onClose={() => {}} />);

    fireEvent.change(screen.getByLabelText('教材文件'), {
      target: { files: [new File(['# 标题'], 'book.md', { type: 'text/markdown' })] },
    });
    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }));

    await waitFor(() => expect(screen.getByText(/逻辑库列表读取失败/)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '提交入库' })).toBeDisabled();
  });
});
