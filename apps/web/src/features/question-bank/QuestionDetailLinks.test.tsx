/**
 * F10-QB：已入库题目的知识点关联「查看 + 更新」端到端路径（组件级）。
 *
 * 断言方向：
 * - 未改动关联保存时不发送 `knowledgeLinks`（服务端沿用旧正式关联，不清空）；
 * - 改动/清空后发送整表替换（空数组 = 清空）；
 * - 跨学科改题而未显式处置关联：后端 422 的字段级错误显示到具体关联行，编辑内容保留，
 *   绝不静默失败；
 * - 服务端未返回 `knowledgeLinks` 字段时按「未提供」呈现（旧数据仍可读）。
 */

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { QuestionDetail, QuestionImportDetail } from '@/contracts/question-bank';
import { QuestionDetailPanel } from './QuestionDetailPanel';
import { buildTaxonomyIndex } from './taxonomy';

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={typeof href === 'string' ? href : '#'} {...rest}>
      {children}
    </a>
  ),
}));

const TAXONOMY = buildTaxonomyIndex({
  stages: [{ id: 'stage-j', label: '初中' }],
  grades: [{ id: 'grade-7', label: '七年级', stageId: 'stage-j' }],
  subjects: [
    { id: 'math', label: '数学' },
    { id: 'physics', label: '物理' },
  ],
  editions: [{ id: 'renjiao', label: '人教版' }],
});

const CONTENT = {
  type: 'single_choice' as const,
  stemMarkdown: '下列说法正确的是？',
  options: [
    { key: 'A', textMarkdown: '甲' },
    { key: 'B', textMarkdown: '乙' },
  ],
  answer: { choiceKeys: ['A'], accepted: null, textMarkdown: null },
  explanationMarkdown: null,
  assetIds: [],
};

const METADATA = {
  stageId: 'stage-j',
  gradeId: 'grade-7',
  subjectId: 'math',
  editionId: 'renjiao',
  knowledgeTags: ['旧标签甲'],
  difficulty: 'easy' as const,
};

const LINKS = [
  {
    knowledgePointId: 'kp-1',
    knowledgeRevisionId: 'kpr-1',
    knowledgeNameSnapshot: '有理数',
    subjectIdSnapshot: 'math',
    role: 'primary' as const,
  },
  {
    knowledgePointId: 'kp-2',
    knowledgeRevisionId: 'kpr-2',
    knowledgeNameSnapshot: '相反数',
    subjectIdSnapshot: 'math',
    role: 'secondary' as const,
  },
];

function detail(extra: Record<string, unknown> = {}): QuestionDetail & Record<string, unknown> {
  return {
    questionId: 'q-1',
    ownerId: 'local-user',
    status: 'confirmed',
    revision: 3,
    type: 'single_choice',
    stemPreview: '下列说法正确的是？',
    subjectId: 'math',
    gradeId: 'grade-7',
    editionId: 'renjiao',
    knowledgeTags: ['旧标签甲'],
    difficulty: 'easy',
    answerState: 'provided',
    confirmedAt: '2026-10-01T00:00:00Z',
    content: CONTENT,
    metadata: METADATA,
    sources: [],
    sourceImportId: null,
    knowledgeLinks: LINKS,
    ...extra,
  };
}

const IMPORT_DETAIL: QuestionImportDetail = {
  importId: 'imp-1',
  ownerId: 'local-user',
  state: 'confirmed',
  revision: 1,
  uploadedFileName: '七年级数学.md',
  uploadedBytes: 100,
  draftCount: 1,
  reviewedCount: 1,
  unassignedCount: 0,
  warnings: [],
  createdAt: '2026-10-01T00:00:00Z',
  drafts: [],
  unassignedBlocks: [],
};

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
    return (
      String(url).includes(fragment) &&
      (!method || (request?.method ?? 'GET').toUpperCase() === method)
    );
  });
}

function bodyAt(fetchMock: ReturnType<typeof stubApi>, fragment: string, method: string, index = 0) {
  const matched = calls(fetchMock, fragment, method);
  return JSON.parse(String((matched[index]?.[1] as RequestInit).body)) as Record<string, unknown>;
}

const POINTS = {
  items: [
    {
      id: 'kp-3',
      subjectId: 'math',
      code: 'M3',
      name: '数轴',
      description: '',
      parentId: null,
      parentCode: null,
      sortOrder: 0,
      status: 'active',
      revision: 1,
      revisionId: 'kpr-3',
      version: 1,
      aliases: [],
      createdAt: '2026-10-01T00:00:00Z',
    },
  ],
  total: 1,
  offset: 0,
  limit: 200,
};

function router(overrides: Record<string, Handler> = {}) {
  return stubApi((url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    for (const [key, handler] of Object.entries(overrides)) {
      if (key.startsWith(`${method} `) && url.startsWith(key.slice(method.length + 1))) {
        return handler(url, init);
      }
    }
    if (url.endsWith('/api/v1/questions/q-1') && method === 'GET') {
      return jsonResponse(true, 200, detail());
    }
    if (url.includes('/api/v1/knowledge-points')) return jsonResponse(true, 200, POINTS);
    if (url.includes('/api/v1/question-imports/imp-1')) return jsonResponse(true, 200, IMPORT_DETAIL);
    return jsonResponse(false, 500, {
      code: 'UNEXPECTED_TEST_REQUEST',
      message: `${method} ${url} 未在测试路由中声明`,
      retryable: false,
    });
  });
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

function renderDetail(onClose = () => undefined, onChanged = () => undefined) {
  return render(
    <QuestionDetailPanel
      questionId="q-1"
      taxonomy={TAXONOMY}
      onClose={onClose}
      onChanged={onChanged}
    />,
  );
}

async function openEdit() {
  fireEvent.click(await screen.findByRole('button', { name: '编辑题目' }));
  return screen.getByRole('dialog', { name: '编辑题目' });
}

describe('题目详情：关联查看与历史标签分区', () => {
  it('查看态显示正式关联与旧标签，且不出现编辑入口', async () => {
    router();
    renderDetail();

    const dialog = await screen.findByRole('dialog', { name: '题目详情' });
    const panel = await within(dialog).findByTestId('qb-knowledge-links');
    expect(within(panel).getByText('有理数')).toBeInTheDocument();
    expect(within(panel).getByText('相反数')).toBeInTheDocument();
    expect(within(panel).getByText('旧标签甲')).toHaveClass('qb-legacy-tag');
    expect(within(panel).queryByTestId('qb-knowledge-link-add')).not.toBeInTheDocument();
  });

  it('服务端未返回 knowledgeLinks 字段（旧数据）：按「未提供」呈现，不用旧标签补齐', async () => {
    router({
      'GET /api/v1/questions/q-1': () => {
        const payload = detail();
        delete (payload as Record<string, unknown>).knowledgeLinks;
        return jsonResponse(true, 200, payload);
      },
    });
    renderDetail();

    const dialog = await screen.findByRole('dialog', { name: '题目详情' });
    expect(await within(dialog).findByTestId('qb-knowledge-links-missing')).toHaveTextContent(
      '不会用旧标签或猜测补齐',
    );
    expect(within(dialog).getByText('旧标签甲')).toBeInTheDocument();
  });
});

describe('题目编辑：关联整表替换与 422 字段级错误', () => {
  it('未改动关联保存：请求体不发送 knowledgeLinks（服务端沿用旧关联）', async () => {
    const fetchMock = router({
      'PATCH /api/v1/questions/q-1': () => jsonResponse(true, 200, detail({ revision: 4 })),
    });
    renderDetail();
    const dialog = await openEdit();

    fireEvent.click(within(dialog).getByRole('button', { name: '保存修改' }));

    await waitFor(() => expect(calls(fetchMock, '/questions/q-1', 'PATCH')).toHaveLength(1));
    const body = bodyAt(fetchMock, '/questions/q-1', 'PATCH');
    expect(body.expectedRevision).toBe(3);
    expect(body).not.toHaveProperty('knowledgeLinks');
  });

  it('移除一条关联后保存：发送剩余关联的整表替换载荷', async () => {
    const fetchMock = router({
      'PATCH /api/v1/questions/q-1': () =>
        jsonResponse(true, 200, detail({ revision: 4, knowledgeLinks: [LINKS[0]] })),
    });
    renderDetail();
    const dialog = await openEdit();

    fireEvent.click(await within(dialog).findByTestId('qb-knowledge-link-remove-1'));
    fireEvent.click(within(dialog).getByRole('button', { name: '保存修改' }));

    await waitFor(() => expect(calls(fetchMock, '/questions/q-1', 'PATCH')).toHaveLength(1));
    expect(bodyAt(fetchMock, '/questions/q-1', 'PATCH').knowledgeLinks).toEqual([
      { knowledgePointId: 'kp-1', role: 'primary' },
    ]);
    // 保存成功后以服务端权威关联为准，恢复「未改动」状态
    await waitFor(() =>
      expect(within(dialog).queryByTestId('qb-knowledge-links-touched')).not.toBeInTheDocument(),
    );
  });

  it('新增关联：载荷带新知识点（当前修订由服务端重新解析）', async () => {
    const fetchMock = router({
      'PATCH /api/v1/questions/q-1': () =>
        jsonResponse(true, 200, detail({ revision: 4, knowledgeLinks: [...LINKS] })),
    });
    renderDetail();
    const dialog = await openEdit();

    const select = await within(dialog).findByLabelText('知识点');
    await waitFor(() => expect((select as HTMLSelectElement).disabled).toBe(false));
    fireEvent.change(select, { target: { value: 'kp-3' } });
    fireEvent.click(within(dialog).getByRole('button', { name: '保存修改' }));

    await waitFor(() => expect(calls(fetchMock, '/questions/q-1', 'PATCH')).toHaveLength(1));
    expect(bodyAt(fetchMock, '/questions/q-1', 'PATCH').knowledgeLinks).toEqual([
      { knowledgePointId: 'kp-1', role: 'primary' },
      { knowledgePointId: 'kp-2', role: 'secondary' },
      { knowledgePointId: 'kp-3', role: 'primary' },
    ]);
  });

  it('跨学科改题未处置旧关联：422 字段级错误显示到关联行，编辑内容保留', async () => {
    const conflictMessage =
      '知识点 kp-1（有理数）属于学科 math，与新学科 physics 不一致；请显式替换或清空该关联。';
    const fetchMock = router({
      'PATCH /api/v1/questions/q-1': () =>
        jsonResponse(false, 422, {
          code: 'KNOWLEDGE_REFERENCE_INVALID',
          message: '改题目学科后不能继承与新学科不一致的旧知识点关联；请显式提供 knowledgeLinks。',
          retryable: false,
          details: {
            issues: [
              {
                field: 'knowledgeLinks[0].knowledgePointId',
                code: 'KNOWLEDGE_REFERENCE_INVALID',
                message: conflictMessage,
              },
              {
                field: 'knowledgeLinks[1].knowledgePointId',
                code: 'KNOWLEDGE_REFERENCE_INVALID',
                message: '知识点 kp-2（相反数）属于学科 math，与新学科 physics 不一致。',
              },
            ],
          },
        }),
    });
    renderDetail();
    const dialog = await openEdit();

    // 先把学科改成物理：界面在保存前就提示会被 422 拒绝
    fireEvent.change(within(dialog).getByLabelText('学科'), { target: { value: 'physics' } });
    expect(await within(dialog).findByTestId('qb-knowledge-subject-change')).toHaveTextContent(
      '422',
    );
    expect(within(dialog).getByTestId('qb-knowledge-links-blocked')).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: '保存修改' }));

    // 字段级错误显示到对应行；用户填的学科没有被回滚
    const rowIssue = await within(dialog).findByTestId('qb-knowledge-link-issue-0');
    expect(rowIssue).toHaveTextContent(conflictMessage);
    expect(within(dialog).getByTestId('qb-knowledge-link-issue-1')).toHaveTextContent('kp-2');
    expect((within(dialog).getByLabelText('学科') as HTMLSelectElement).value).toBe('physics');
    expect(within(dialog).getByText(/知识点关联校验失败（KNOWLEDGE_REFERENCE_INVALID）/)).toBeInTheDocument();
    // 未改动关联：请求体不能偷偷带 knowledgeLinks（那会变成静默清空/改写）
    expect(bodyAt(fetchMock, '/questions/q-1', 'PATCH')).not.toHaveProperty('knowledgeLinks');
  });

  it('显式清空关联后保存：发送空数组（明确清空）', async () => {
    const fetchMock = router({
      'PATCH /api/v1/questions/q-1': () =>
        jsonResponse(true, 200, detail({ revision: 4, knowledgeLinks: [] })),
    });
    renderDetail();
    const dialog = await openEdit();

    fireEvent.click(await within(dialog).findByTestId('qb-knowledge-link-clear'));
    fireEvent.click(within(dialog).getByRole('button', { name: '保存修改' }));

    await waitFor(() => expect(calls(fetchMock, '/questions/q-1', 'PATCH')).toHaveLength(1));
    expect(bodyAt(fetchMock, '/questions/q-1', 'PATCH').knowledgeLinks).toEqual([]);
  });
});

/* -------------------------- F10-QB：已保存题目的 AI 候选来源追溯 */

const AI_DRAFT = {
  draftId: 'd-1',
  importId: 'imp-1',
  revision: 1,
  content: CONTENT,
  metadata: { ...METADATA, knowledgeTags: [] },
  sourceSpans: [],
  extractionMethod: 'ai' as const,
  reviewState: 'needs_review' as const,
  missingAnswerAcknowledged: false,
  warnings: [],
  duplicateOfQuestionId: null,
  knowledgeLinks: [],
};

describe('来源追溯：AI 候选确认路径', () => {
  it('来源批次含 AI 草稿：如实说明候选经人工校对确认后才入库', async () => {
    router({
      'GET /api/v1/questions/q-1': () =>
        jsonResponse(true, 200, detail({ sourceImportId: 'imp-1' })),
      'GET /api/v1/question-imports/imp-1': () =>
        jsonResponse(true, 200, {
          ...IMPORT_DETAIL,
          state: 'needs_review',
          draftCount: 1,
          drafts: [AI_DRAFT],
        }),
    });
    renderDetail();

    const trace = await screen.findByTestId('qb-source-ai-trace');
    await waitFor(() => expect(trace).toHaveTextContent('1/1 道 AI 候选草稿'));
    expect(trace).toHaveTextContent('extractionMethod=ai');
    expect(trace).toHaveTextContent('必须人工校对并确认后才成为题目');
    expect(trace).toHaveTextContent('批次还未确认入库');
  });

  it('来源批次读取失败：明确「无法核对」，不当作「没有 AI 候选」', async () => {
    router({
      'GET /api/v1/questions/q-1': () =>
        jsonResponse(true, 200, detail({ sourceImportId: 'imp-1' })),
      'GET /api/v1/question-imports/imp-1': () =>
        jsonResponse(false, 503, {
          code: 'SERVICE_UNAVAILABLE',
          message: '题库服务未装配。',
          retryable: true,
        }),
    });
    renderDetail();

    const trace = await screen.findByTestId('qb-source-ai-trace');
    await waitFor(() => expect(trace).toHaveTextContent('SERVICE_UNAVAILABLE'));
    expect(trace).toHaveTextContent('无法核对');
    expect(trace).not.toHaveTextContent('没有 AI 来源草稿');
  });
});
