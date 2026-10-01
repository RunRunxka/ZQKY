import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type {
  QuestionDetail,
  QuestionImportSummary,
  QuestionList,
} from '@/contracts/question-bank';
import { QuestionBankWorkspace } from './QuestionBankWorkspace';

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn(), refresh: vi.fn() }),
}));

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
      (method === undefined || (request?.method ?? 'GET').toUpperCase() === method)
    );
  });
}

const TAXONOMY = {
  stages: [{ id: 'stage-j', label: '初中' }],
  grades: [{ id: 'grade-7', label: '七年级', stageId: 'stage-j' }],
  subjects: [{ id: 'math', label: '数学' }],
  editions: [{ id: 'renjiao', label: '人教版' }],
};

const BATCH: QuestionImportSummary = {
  importId: 'imp-1',
  ownerId: 'local-user',
  state: 'needs_review',
  revision: 1,
  uploadedFileName: '七年级数学题库.md',
  uploadedBytes: 3 * 1024 * 1024,
  draftCount: 6,
  reviewedCount: 2,
  unassignedCount: 3,
  warnings: ['第 3 题缺少题干'],
  createdAt: '2026-09-28T08:00:00Z',
};

const QUESTION_DETAIL: QuestionDetail = {
  questionId: 'q-1',
  ownerId: 'local-user',
  status: 'confirmed',
  revision: 2,
  type: 'multiple_choice',
  stemPreview: '下列各数中，是负数的有？',
  subjectId: 'math',
  gradeId: 'grade-7',
  editionId: 'renjiao',
  knowledgeTags: ['有理数'],
  difficulty: 'medium',
  answerState: 'not_provided',
  confirmedAt: '2026-09-28T09:00:00Z',
  content: {
    type: 'multiple_choice',
    stemMarkdown: '下列各数中，是负数的有？',
    options: [
      { key: 'A', textMarkdown: '-2' },
      { key: 'B', textMarkdown: '3' },
    ],
    answer: null,
    explanationMarkdown: null,
    assetIds: [],
  },
  metadata: {
    stageId: 'stage-j',
    gradeId: 'grade-7',
    subjectId: 'math',
    editionId: 'renjiao',
    knowledgeTags: ['有理数'],
    difficulty: 'medium',
  },
  sources: [{ blockId: 'b-2', charStart: 30, charEnd: 66 }],
  sourceImportId: 'imp-1',
};

const QUESTION_LIST: QuestionList = {
  questions: [
    {
      questionId: 'q-1',
      ownerId: 'local-user',
      status: 'confirmed',
      revision: 2,
      type: 'multiple_choice',
      stemPreview: '下列各数中，是负数的有？',
      subjectId: 'math',
      gradeId: 'grade-7',
      editionId: 'renjiao',
      knowledgeTags: ['有理数'],
      difficulty: 'medium',
      answerState: 'not_provided',
      confirmedAt: '2026-09-28T09:00:00Z',
    },
  ],
  total: 1,
  offset: 0,
  limit: 20,
};

const POINTS = {
  items: [
    {
      id: 'kp-m1',
      subjectId: 'math',
      code: 'M1',
      name: '有理数',
      description: '',
      parentId: null,
      parentCode: null,
      sortOrder: 0,
      status: 'active',
      revision: 1,
      revisionId: 'kpr-m1',
      version: 1,
      aliases: [],
      createdAt: '2026-09-28T00:00:00Z',
    },
  ],
  total: 1,
  offset: 0,
  limit: 200,
};

const defaultRoute = (url: string, init: RequestInit) => {
  const method = (init.method ?? 'GET').toUpperCase();
  if (url.endsWith('/textbook-taxonomy')) return jsonResponse(true, 200, TAXONOMY);
  if (url.includes('/knowledge-points')) return jsonResponse(true, 200, POINTS);
  if (url.endsWith('/question-imports') && method === 'GET') {
    return jsonResponse(true, 200, { imports: [BATCH] });
  }
  if (url.includes('/questions/q-1') && method === 'GET') {
    return jsonResponse(true, 200, QUESTION_DETAIL);
  }
  if (url.includes('/questions') && method === 'GET') {
    return jsonResponse(true, 200, QUESTION_LIST);
  }
  return null;
};

function router(overrides: Record<string, Handler> = {}) {
  return stubApi((url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    for (const [key, handler] of Object.entries(overrides)) {
      if (key.startsWith(`${method} `) && url.startsWith(key.slice(method.length + 1))) {
        return handler(url, init);
      }
    }
    const base = defaultRoute(url, init);
    if (base) return base;
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
  pushMock.mockReset();
});

describe('题库首页：导入批次', () => {
  it('加载完成后显示批次的文件名、状态、计数、警告与校对页链接', async () => {
    router();
    render(<QuestionBankWorkspace />);

    expect(screen.getByLabelText('正在读取导入批次')).toBeInTheDocument();
    expect(await screen.findByText('七年级数学题库.md')).toBeInTheDocument();
    expect(screen.getByText('待校对')).toBeInTheDocument();
    expect(screen.getByText('草稿 6')).toBeInTheDocument();
    expect(screen.getByText('已校对 2')).toBeInTheDocument();
    expect(screen.getByText('未归属原文 3')).toBeInTheDocument();
    expect(screen.getByText(/警告 1 条：第 3 题缺少题干/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /七年级数学题库.md/ })).toHaveAttribute(
      'href',
      '/question-bank/imports/imp-1',
    );
  });

  it('读取失败时显示错误与重试，不显示空态；重试成功后恢复真实数据', async () => {
    let attempt = 0;
    router({
      'GET /api/v1/question-imports': () => {
        attempt += 1;
        if (attempt === 1) {
          return jsonResponse(false, 503, {
            code: 'SERVICE_UNAVAILABLE',
            message: '题库服务未装配。',
            retryable: true,
          });
        }
        return jsonResponse(true, 200, { imports: [BATCH] });
      },
    });
    render(<QuestionBankWorkspace />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('导入批次读取失败');
    expect(alert).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(screen.queryByText('还没有导入批次')).not.toBeInTheDocument();

    fireEvent.click(within(alert).getByRole('button', { name: '重试' }));
    expect(await screen.findByText('七年级数学题库.md')).toBeInTheDocument();
  });

  it('没有批次时显示空态而不是错误', async () => {
    router({ 'GET /api/v1/question-imports': () => jsonResponse(true, 200, { imports: [] }) });
    render(<QuestionBankWorkspace />);

    expect(await screen.findByText('还没有导入批次')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('题库首页：已入库题目', () => {
  it('切换页签后显示题目列表（缺失答案照实显示）并按筛选请求', async () => {
    const fetchMock = router();
    render(<QuestionBankWorkspace />);
    await screen.findByText('七年级数学题库.md');

    fireEvent.click(screen.getByRole('tab', { name: '已入库题目' }));

    expect(await screen.findByText('下列各数中，是负数的有？')).toBeInTheDocument();
    expect(screen.getByText('多选题')).toBeInTheDocument();
    expect(screen.getByText('答案缺失')).toBeInTheDocument();
    expect(screen.getByText('难度：中等')).toBeInTheDocument();
    expect(screen.getByText('有理数')).toBeInTheDocument();
    expect(calls(fetchMock, '/questions?offset=0&limit=20')).toHaveLength(1);

    fireEvent.change(screen.getByLabelText('学科'), { target: { value: 'math' } });
    fireEvent.click(screen.getByRole('button', { name: /查询/ }));
    await waitFor(() =>
      expect(calls(fetchMock, '/questions?subjectId=math&offset=0&limit=20')).toHaveLength(1),
    );
  });

  it('题目详情展示答案缺失、来源与分类，归档删除带 expectedRevision 且需二次确认', async () => {
    const fetchMock = router({
      'DELETE /api/v1/questions/q-1': () => jsonResponse(true, 204, null),
    });
    render(<QuestionBankWorkspace />);
    await screen.findByText('七年级数学题库.md');
    fireEvent.click(screen.getByRole('tab', { name: '已入库题目' }));
    fireEvent.click(await screen.findByRole('button', { name: '查看题目' }));

    const dialog = await screen.findByRole('dialog', { name: '题目详情' });
    expect(within(dialog).getByText('下列各数中，是负数的有？')).toBeInTheDocument();
    expect(within(dialog).getByText('答案缺失', { selector: '.space-chip' })).toBeInTheDocument();
    expect(within(dialog).getByText('有理数')).toBeInTheDocument();
    expect(within(dialog).getByText(/b-2（字符 30–66）/)).toBeInTheDocument();
    expect(within(dialog).getByRole('link', { name: 'imp-1' })).toHaveAttribute(
      'href',
      '/question-bank/imports/imp-1',
    );

    fireEvent.click(within(dialog).getByRole('button', { name: '归档删除…' }));
    expect(within(dialog).getByText(/归档删除会让题目不再出现在列表中/)).toBeInTheDocument();
    expect(calls(fetchMock, '/questions/q-1', 'DELETE')).toHaveLength(0);

    fireEvent.click(within(dialog).getByRole('button', { name: '确认归档删除' }));
    await waitFor(() => {
      expect(calls(fetchMock, '/questions/q-1').length).toBeGreaterThan(0);
    });
    const deleteCall = fetchMock.mock.calls.find(
      ([, init]) => (init as RequestInit | undefined)?.method === 'DELETE',
    );
    expect(String(deleteCall?.[0])).toBe('/api/v1/questions/q-1?expectedRevision=2');
  });

  it('题目编辑 409 冲突保留输入并给出两个动作', async () => {
    const fetchMock = router({
      'PATCH /api/v1/questions/q-1': () =>
        jsonResponse(false, 409, {
          code: 'REVISION_CONFLICT',
          message: '题目已被其他操作更新。',
          retryable: false,
        }),
    });
    render(<QuestionBankWorkspace />);
    await screen.findByText('七年级数学题库.md');
    fireEvent.click(screen.getByRole('tab', { name: '已入库题目' }));
    fireEvent.click(await screen.findByRole('button', { name: '查看题目' }));

    const dialog = await screen.findByRole('dialog', { name: '题目详情' });
    fireEvent.click(within(dialog).getByRole('button', { name: '编辑题目' }));

    const editDialog = screen.getByRole('dialog', { name: '编辑题目' });
    const stem = within(editDialog).getByLabelText('题干') as HTMLTextAreaElement;
    fireEvent.change(stem, { target: { value: '我的题目修改' } });
    fireEvent.click(within(editDialog).getByRole('button', { name: '保存修改' }));

    await waitFor(() => expect(screen.getByText(/内容已在别处被修改/)).toBeInTheDocument());
    expect((within(editDialog).getByLabelText('题干') as HTMLTextAreaElement).value).toBe(
      '我的题目修改',
    );
    expect(screen.getByRole('button', { name: '用我的修改重试' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '放弃我的修改' })).toBeInTheDocument();
    expect(calls(fetchMock, '/questions/q-1', 'PATCH')).toHaveLength(1);
  });

  it('抽屉 Escape 关闭后焦点回到触发按钮', async () => {
    router();
    render(<QuestionBankWorkspace />);
    await screen.findByText('七年级数学题库.md');
    fireEvent.click(screen.getByRole('tab', { name: '已入库题目' }));

    const trigger = await screen.findByRole('button', { name: '查看题目' });
    trigger.focus();
    expect(document.activeElement).toBe(trigger);
    fireEvent.click(trigger);

    const dialog = await screen.findByRole('dialog', { name: '题目详情' });
    // 浏览器原生 Escape 行为：对 <dialog> 派发 cancel 事件
    fireEvent(dialog, new Event('cancel', { bubbles: false, cancelable: true }));

    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: '题目详情' })).not.toBeInTheDocument(),
    );
    expect(document.activeElement).toBe(trigger);
  });

  it('按知识点筛选：选项来自知识点库在用列表，查询请求带 knowledgePointId', async () => {
    const fetchMock = router();
    render(<QuestionBankWorkspace />);
    await screen.findByText('七年级数学题库.md');
    fireEvent.click(screen.getByRole('tab', { name: '已入库题目' }));

    const filter = await screen.findByLabelText('知识点');
    await waitFor(() => expect((filter as HTMLSelectElement).disabled).toBe(false));
    fireEvent.change(filter, { target: { value: 'kp-m1' } });
    fireEvent.click(screen.getByRole('button', { name: /查询/ }));

    await waitFor(() =>
      expect(calls(fetchMock, '/questions?knowledgePointId=kp-m1')).toHaveLength(1),
    );
    // 旧标签仍照实显示，并标注为历史字段（与正式关联分开）
    expect(screen.getByText('历史标签（旧字段）')).toBeInTheDocument();
    expect(screen.getByText('有理数')).toHaveClass('qb-legacy-tag');
  });

  it('AI 补题入口打开补题面板（不在页面加载时调用模型）', async () => {
    const fetchMock = router();
    render(<QuestionBankWorkspace />);
    await screen.findByText('七年级数学题库.md');
    fireEvent.click(screen.getByRole('tab', { name: '已入库题目' }));

    fireEvent.click(await screen.findByTestId('qb-generation-open'));

    expect(await screen.findByTestId('qb-generation-panel')).toBeInTheDocument();
    expect(
      screen.getByText(/AI 补题只生成待校对草稿/),
    ).toBeInTheDocument();
    expect(calls(fetchMock, '/question-generation-jobs', 'POST')).toHaveLength(0);
  });
});
