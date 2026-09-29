import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type {
  DocumentSummary,
  LibrarySummary,
  ScopeCheckView,
  TextbookTaxonomy,
  TeachingSettingsView,
} from '@/contracts/textbook';
import { TeachingScopePanel } from './TeachingScopePanel';
import { TextbookWorkspace } from './TextbookWorkspace';
import { buildTaxonomyIndex } from './taxonomy';

const TAXONOMY: TextbookTaxonomy = {
  stages: [{ id: 'stage-j', label: '初中' }],
  grades: [
    { id: 'g7', label: '七年级', stageId: 'stage-j' },
    { id: 'g8', label: '八年级', stageId: 'stage-j' },
  ],
  subjects: [
    { id: 'math', label: '数学' },
    { id: 'chinese', label: '语文' },
  ],
  editions: [{ id: 'rj', label: '人教版' }],
};
const index = buildTaxonomyIndex(TAXONOMY);

function documentSummary(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    documentId: 'doc-g7-math',
    ownerId: 'system',
    title: '七年级数学上册',
    libraryIds: ['lib-g7-math'],
    gradeIds: ['g7'],
    subjectId: 'math',
    editionId: 'rj',
    metadataRevisionId: 'meta-1',
    currentRevision: {
      revisionId: 'rev-1',
      originalFileSha256: 'orig',
      normalizedTextSha256: 'norm',
      parserVersion: 'p1',
      charCount: 5120,
      chunkCount: 18,
      createdAt: '2026-09-20T00:00:00Z',
    },
    pendingRevisionId: null,
    deletedAt: null,
    revision: 2,
    ...overrides,
  };
}

const MATH_DOC = documentSummary();
const CHINESE_DOC = documentSummary({
  documentId: 'doc-g7-chinese',
  title: '七年级语文上册',
  subjectId: 'chinese',
  libraryIds: ['lib-g7-chinese'],
  metadataRevisionId: 'meta-2',
  currentRevision: {
    revisionId: 'rev-2',
    originalFileSha256: 'orig-2',
    normalizedTextSha256: 'norm-2',
    parserVersion: 'p1',
    charCount: 2200,
    chunkCount: 7,
    createdAt: '2026-09-21T00:00:00Z',
  },
});

function settingsView(overrides: Partial<TeachingSettingsView> = {}): TeachingSettingsView {
  return {
    ownerId: 'local-user',
    selection: {
      gradeId: 'g7',
      subjectId: 'math',
      editionId: 'rj',
      documentIds: [MATH_DOC.documentId],
    },
    revision: 3,
    updatedAt: '2026-09-29T00:00:00Z',
    scopeReady: true,
    scopeReason: null,
    ...overrides,
  };
}

function library(overrides: Partial<LibrarySummary> = {}): LibrarySummary {
  return {
    libraryId: 'lib-g7-math',
    kind: 'base',
    ownerId: 'system',
    displayName: '七年级数学基础库',
    gradeId: 'g7',
    subjectId: 'math',
    editionId: 'rj',
    documentCount: 1,
    readyDocumentCount: 1,
    revision: 1,
    deletedAt: null,
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

type FetchMock = ReturnType<typeof stubApi>;

function callsWithMethod(fetchMock: FetchMock, method: string) {
  return fetchMock.mock.calls.filter(
    ([, init]) => String((init as RequestInit | undefined)?.method ?? 'GET') === method,
  );
}

function requestedUrls(fetchMock: FetchMock, method: string): string[] {
  return callsWithMethod(fetchMock, method).map(([url]) => String(url));
}

function bodyOf(call: unknown[]): Record<string, unknown> {
  return JSON.parse(String((call[1] as RequestInit | undefined)?.body ?? '{}')) as Record<
    string,
    unknown
  >;
}

interface StubConfig {
  settings?: TeachingSettingsView;
  /** 候选书册：函数形式便于「切换组合后返回不同书册」的用例。 */
  documents?: DocumentSummary[] | (() => DocumentSummary[]);
  check?: ScopeCheckView;
  put?: (body: Record<string, unknown>) => Response;
}

/** GET 范围 + GET 候选；scope-check 与 PUT 由各用例覆盖。 */
function scopeStub(config: StubConfig = {}) {
  const documents = (): DocumentSummary[] =>
    typeof config.documents === 'function' ? config.documents() : (config.documents ?? [MATH_DOC]);
  return stubApi((url, init) => {
    const method = init.method ?? 'GET';
    if (url.includes('/teaching-settings/scope-check')) {
      return ok(
        config.check ?? {
          scopeReady: true,
          reason: null,
          documents: documents(),
          missingDocumentIds: [],
        },
      );
    }
    if (url.includes('/teaching-settings')) {
      if (method === 'PUT') {
        return config.put ? config.put(bodyOf([url, init])) : ok(config.settings ?? settingsView());
      }
      return ok(config.settings ?? settingsView());
    }
    if (url.includes('/textbooks')) return ok({ documents: documents() });
    return ok({});
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('任教范围面板', () => {
  it('显示当前范围用可读标签（不是内部 id），并给出已确认册数与范围边界说明', async () => {
    scopeStub({
      settings: settingsView({
        selection: {
          gradeId: 'g7',
          subjectId: 'math',
          editionId: 'rj',
          documentIds: [MATH_DOC.documentId, CHINESE_DOC.documentId],
        },
      }),
    });
    render(<TeachingScopePanel taxonomy={index} />);

    expect(await screen.findByText('年级：七年级')).toBeInTheDocument();
    expect(screen.getByText('学科：数学')).toBeInTheDocument();
    expect(screen.getByText('版本：人教版')).toBeInTheDocument();
    expect(screen.getByText('已确认 2 册进入检索')).toBeInTheDocument();
    expect(screen.getByText('已就绪')).toBeInTheDocument();

    // 内部 id 不落到可见文本
    expect(screen.queryByText('g7')).not.toBeInTheDocument();
    expect(screen.queryByText('math')).not.toBeInTheDocument();
    expect(screen.queryByText('rj')).not.toBeInTheDocument();

    expect(
      screen.getByText(/只有这里确认过的书册才会进入检索范围；未确认的书册不会被检索到/),
    ).toBeInTheDocument();
    expect(screen.getByText(/不会改写已有历史消息里的引用/)).toBeInTheDocument();
  });

  it('切换学科清空已选书册并重新请求候选（断言请求参数与 DOM）', async () => {
    let documents = [MATH_DOC];
    const fetchMock = scopeStub({ documents: () => documents });
    render(<TeachingScopePanel taxonomy={index} />);
    await screen.findByText('已确认 1 册进入检索');

    fireEvent.click(screen.getByRole('button', { name: '修改范围' }));
    const mathCheckbox = await screen.findByRole('checkbox', { name: /七年级数学上册/ });
    expect(mathCheckbox).toBeChecked();
    expect(requestedUrls(fetchMock, 'GET')).toContain(
      '/api/v1/textbooks?gradeId=g7&subjectId=math&editionId=rj',
    );

    documents = [CHINESE_DOC];
    fireEvent.change(document.querySelector('#textbook-scope-subject') as HTMLSelectElement, {
      target: { value: 'chinese' },
    });

    expect(await screen.findByRole('checkbox', { name: /七年级语文上册/ })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole('checkbox', { name: /七年级数学上册/ })).not.toBeInTheDocument();
    });
    // 旧组合的选择没有被带过来
    expect(screen.getByText(/已选 0 册/)).toBeInTheDocument();
    expect(screen.queryAllByRole('checkbox').every((box) => !(box as HTMLInputElement).checked)).toBe(
      true,
    );
    await waitFor(() => {
      expect(requestedUrls(fetchMock, 'GET')).toContain(
        '/api/v1/textbooks?gradeId=g7&subjectId=chinese&editionId=rj',
      );
    });
  });

  it('未选书册点保存：不发任何写请求，显示可读提示', async () => {
    const fetchMock = scopeStub({ documents: [MATH_DOC] });
    render(<TeachingScopePanel taxonomy={index} />);
    await screen.findByText('已确认 1 册进入检索');

    fireEvent.click(screen.getByRole('button', { name: '修改范围' }));
    fireEvent.click(await screen.findByRole('checkbox', { name: /七年级数学上册/ }));
    fireEvent.click(screen.getByRole('button', { name: '保存任教范围' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('至少要确认一册书册');
    expect(callsWithMethod(fetchMock, 'PUT')).toHaveLength(0);
    expect(callsWithMethod(fetchMock, 'POST')).toHaveLength(0);
  });

  it('预检 scopeReady=false 时显示原因且不发 PUT', async () => {
    const fetchMock = scopeStub({
      documents: [MATH_DOC],
      check: {
        scopeReady: false,
        reason: '所选教材尚未进入当前索引代。',
        documents: [],
        missingDocumentIds: [MATH_DOC.documentId],
      },
    });
    render(<TeachingScopePanel taxonomy={index} />);
    await screen.findByText('已确认 1 册进入检索');

    fireEvent.click(screen.getByRole('button', { name: '修改范围' }));
    await screen.findByRole('checkbox', { name: /七年级数学上册/ });
    fireEvent.click(screen.getByRole('button', { name: '保存任教范围' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('预检未通过：所选教材尚未进入当前索引代。');
    expect(alert).toHaveTextContent('七年级数学上册');
    expect(alert).toHaveTextContent('未保存任何修改。');
    await waitFor(() => {
      expect(callsWithMethod(fetchMock, 'POST')).toHaveLength(1);
    });
    expect(callsWithMethod(fetchMock, 'PUT')).toHaveLength(0);
  });

  it('PUT 409 REVISION_CONFLICT：保留用户选择、提示已在别处更新并提供刷新后重试', async () => {
    const fetchMock = scopeStub({
      documents: [MATH_DOC],
      put: () =>
        failed(409, {
          code: 'REVISION_CONFLICT',
          message: '任教设置已被其他操作更新（当前 revision=4），请刷新后重试。',
          retryable: false,
        }),
    });
    render(<TeachingScopePanel taxonomy={index} />);
    await screen.findByText('已确认 1 册进入检索');

    fireEvent.click(screen.getByRole('button', { name: '修改范围' }));
    await screen.findByRole('checkbox', { name: /七年级数学上册/ });
    fireEvent.click(screen.getByRole('button', { name: '保存任教范围' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('范围已在别处更新');
    expect(alert).toHaveTextContent('当前 revision=4');
    expect(alert).toHaveTextContent('你的选择已保留，尚未写入。');
    expect(screen.getByRole('checkbox', { name: /七年级数学上册/ })).toBeChecked();
    expect(callsWithMethod(fetchMock, 'PUT')).toHaveLength(1);

    fireEvent.click(screen.getByRole('button', { name: /刷新后重试/ }));
    await screen.findByText(/已重新读取服务端任教范围/);
    expect(screen.getByRole('checkbox', { name: /七年级数学上册/ })).toBeChecked();
    // 刷新只重新读取，不重放提交
    expect(callsWithMethod(fetchMock, 'PUT')).toHaveLength(1);
    expect(callsWithMethod(fetchMock, 'POST')).toHaveLength(1);
    expect(callsWithMethod(fetchMock, 'GET').length).toBeGreaterThanOrEqual(3);
  });

  it('保存成功后显示服务端返回的更新后范围', async () => {
    let documents = [MATH_DOC];
    const updated = settingsView({
      revision: 4,
      selection: {
        gradeId: 'g7',
        subjectId: 'chinese',
        editionId: 'rj',
        documentIds: [CHINESE_DOC.documentId],
      },
    });
    const fetchMock = scopeStub({
      documents: () => documents,
      put: () => ok(updated),
    });
    render(<TeachingScopePanel taxonomy={index} />);
    await screen.findByText('已确认 1 册进入检索');

    fireEvent.click(screen.getByRole('button', { name: '修改范围' }));
    await screen.findByRole('checkbox', { name: /七年级数学上册/ });
    documents = [CHINESE_DOC];
    fireEvent.change(document.querySelector('#textbook-scope-subject') as HTMLSelectElement, {
      target: { value: 'chinese' },
    });
    fireEvent.click(await screen.findByRole('checkbox', { name: /七年级语文上册/ }));
    fireEvent.click(screen.getByRole('button', { name: '保存任教范围' }));

    expect(await screen.findByText('学科：语文')).toBeInTheDocument();
    expect(screen.getByText('已确认 1 册进入检索')).toBeInTheDocument();
    expect(screen.getByText(/任教范围已保存：只有确认过的书册会进入之后的检索/)).toBeInTheDocument();
    expect(screen.getByText('版本：人教版')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '保存任教范围' })).not.toBeInTheDocument();

    const puts = callsWithMethod(fetchMock, 'PUT');
    expect(puts).toHaveLength(1);
    const body = bodyOf(puts[0] as unknown[]);
    expect(body.expectedRevision).toBe(3);
    expect(body.selection).toEqual({
      gradeId: 'g7',
      subjectId: 'chinese',
      editionId: 'rj',
      documentIds: [CHINESE_DOC.documentId],
    });
  });

  it('scopeReady=false 时如实显示服务端原因；未设置时给出可点的修改入口', async () => {
    scopeStub({
      settings: settingsView({
        scopeReady: false,
        scopeReason: '所选教材尚未进入当前索引代。',
      }),
    });
    const first = render(<TeachingScopePanel taxonomy={index} />);
    expect(await screen.findByText('范围未就绪：所选教材尚未进入当前索引代。')).toBeInTheDocument();
    expect(screen.getByText('未就绪')).toBeInTheDocument();
    first.unmount();

    // 新装状态（selection=null）：这是用户实测时「没法换教材」的那一格
    scopeStub({
      settings: settingsView({ selection: null, revision: 0, scopeReady: false, scopeReason: '尚未保存任教范围。' }),
    });
    render(<TeachingScopePanel taxonomy={index} />);
    expect(await screen.findByText('尚未设置')).toBeInTheDocument();
    expect(screen.getByText(/尚未设置任教范围/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '修改范围' })).toBeInTheDocument();
  });

  it('教材资料库页面打开时只发 GET，不写任何数据', async () => {
    const fetchMock = stubApi((url) => {
      if (url.includes('/teaching-settings')) return ok(settingsView());
      if (url.includes('/textbook-taxonomy')) return ok(TAXONOMY);
      if (url.includes('kind=base')) return ok({ libraries: [library()] });
      if (url.includes('/textbook-libraries')) return ok({ libraries: [] });
      return ok({});
    });
    render(<TextbookWorkspace />);

    expect(await screen.findByText('已确认 1 册进入检索')).toBeInTheDocument();
    // 库卡片同样显示「年级：七年级」，这里只看任教范围面板内的标签
    const scope = document.querySelector('.textbook-scope');
    expect(scope).not.toBeNull();
    expect(within(scope as HTMLElement).getByText('年级：七年级')).toBeInTheDocument();
    await screen.findByRole('link', { name: /七年级数学基础库/ });

    const writeCalls = fetchMock.mock.calls.filter(([, init]) => {
      const method = (init as RequestInit | undefined)?.method;
      return Boolean(method) && method !== 'GET';
    });
    expect(writeCalls).toEqual([]);
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes('/teaching-settings')),
    ).toBe(true);
  });
});
