/**
 * 题库首页（参考图布局，R4-FE 2026-10-11）：
 * 筛选条（选择知识点 / 难度 / 搜索）/ 左「知识点分类」树 + 计数 / 右「题目列表」行 + 分页 /
 * 「编辑」「删除」行操作 / 「批量导入」（含教材课后习题提取）/「添加题目」（手动录入 + AI 补题）。
 *
 * 与归档测试的差异（参考图优先，已在交付说明中报告）：
 * - 归档的「导入批次 / 已入库题目」页签与 `?tab=` 薄路由校验按参考图取消（导入动作收进面板）；
 * - 「查询」按钮改为筛选即请求（关键词 300ms 防抖，回车立即应用）；
 * - 「查看题目」按钮改为行内「编辑」「删除」文字操作。
 */

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { QuestionDetail, QuestionImportSummary, QuestionList } from '@/contracts/question-bank';
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
  warnings: [],
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
    {
      questionId: 'q-2',
      ownerId: 'local-user',
      status: 'confirmed',
      revision: 1,
      type: 'fill_blank',
      stemPreview: '计算 $2^3$ 的值。',
      subjectId: 'math',
      gradeId: 'grade-7',
      editionId: 'renjiao',
      knowledgeTags: [],
      difficulty: 'easy',
      answerState: 'provided',
      confirmedAt: '2026-09-28T09:05:00Z',
    },
  ],
  total: 2,
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
    {
      id: 'kp-m2',
      subjectId: 'math',
      code: 'M1.1',
      name: '相反数',
      description: '',
      parentId: 'kp-m1',
      parentCode: 'M1',
      sortOrder: 1,
      status: 'active',
      revision: 1,
      revisionId: 'kpr-m2',
      version: 1,
      aliases: [],
      createdAt: '2026-09-28T00:00:00Z',
    },
  ],
  total: 2,
  offset: 0,
  limit: 200,
};

const QUESTION_DETAIL_BY_ID: Record<string, QuestionDetail> = { 'q-1': QUESTION_DETAIL };

const defaultRoute = (url: string, init: RequestInit) => {
  const method = (init.method ?? 'GET').toUpperCase();
  if (url.endsWith('/textbook-taxonomy')) return jsonResponse(true, 200, TAXONOMY);
  if (url.includes('/knowledge-points')) return jsonResponse(true, 200, POINTS);
  if (url.endsWith('/question-imports') && method === 'GET') {
    return jsonResponse(true, 200, { imports: [BATCH] });
  }
  if (url.includes('/questions/q-') && method === 'GET') {
    const questionId = url.split('/questions/')[1]?.split('?')[0] ?? 'q-1';
    return jsonResponse(true, 200, QUESTION_DETAIL_BY_ID[questionId] ?? QUESTION_DETAIL);
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

describe('题库首页：题目列表', () => {
  it('加载成功后显示题干、难度徽标、记录数与分页，点击页码请求对应 offset', async () => {
    const fetchMock = router({
      'GET /api/v1/questions': (url) =>
        jsonResponse(true, 200, {
          ...QUESTION_LIST,
          total: 128,
          offset: Number(new URL(url, 'http://localhost').searchParams.get('offset') ?? 0),
        }),
    });
    render(<QuestionBankWorkspace />);

    expect(await screen.findByText(/下列各数中，是负数的有/)).toBeInTheDocument();
    const mediumRow = screen.getByText(/下列各数中，是负数的有/).closest('.qb-question-row') as HTMLElement;
    const easyRow = document.querySelectorAll('.qb-question-row')[1] as HTMLElement;
    expect(within(mediumRow).getByText('中等')).toHaveClass('qb-badge-medium');
    expect(within(easyRow).getByText('基础')).toHaveClass('qb-badge-easy');
    // 题干里的 $2^3$ 由 KaTeX 渲染（沿用项目既有 Markdown + KaTeX 路径）
    expect(easyRow.textContent).toContain('计算');
    expect(easyRow.querySelector('.qb-question-stem .katex')).not.toBeNull();
    expect(screen.getByText('共 128 条记录')).toBeInTheDocument();
    // 128 条 / 每页 20 → 7 页，中间用省略号
    expect(screen.getByRole('button', { name: '1' })).toHaveClass('current');
    expect(screen.getByRole('button', { name: '7' })).toBeInTheDocument();
    expect(screen.getByText('…')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '2' }));
    await waitFor(() => expect(calls(fetchMock, '/questions?offset=20&limit=20')).toHaveLength(1));
  });

  it('读取失败显示错误与重试，不显示空态；重试成功后恢复真实数据', async () => {
    let attempt = 0;
    router({
      'GET /api/v1/questions': (url) => {
        if (url.includes('limit=1')) return jsonResponse(true, 200, QUESTION_LIST);
        attempt += 1;
        if (attempt === 1) {
          return jsonResponse(false, 503, {
            code: 'SERVICE_UNAVAILABLE',
            message: '题库服务未装配。',
            retryable: true,
          });
        }
        return jsonResponse(true, 200, QUESTION_LIST);
      },
    });
    render(<QuestionBankWorkspace />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('题目列表读取失败');
    expect(alert).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(screen.queryByText('没有符合条件的题目')).not.toBeInTheDocument();

    fireEvent.click(within(alert).getByRole('button', { name: '重试' }));
    expect(await screen.findByText(/下列各数中，是负数的有/)).toBeInTheDocument();
  });

  it('没有题目时显示空态而不是错误', async () => {
    router({ 'GET /api/v1/questions': () => jsonResponse(true, 200, { ...QUESTION_LIST, questions: [], total: 0 }) });
    render(<QuestionBankWorkspace />);

    expect(await screen.findByText('没有符合条件的题目')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByText('共 0 条记录')).toBeInTheDocument();
  });

  it('难度下拉与知识点筛选都会带进列表请求', async () => {
    const fetchMock = router();
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);

    fireEvent.change(screen.getByLabelText('难度'), { target: { value: 'hard' } });
    await waitFor(() =>
      expect(calls(fetchMock, '/questions?difficulty=hard&offset=0&limit=20')).toHaveLength(1),
    );

    fireEvent.click(await screen.findByRole('button', { name: '展开知识点 有理数' }));
    fireEvent.click(await screen.findByRole('button', { name: '相反数' }));
    await waitFor(() =>
      expect(
        calls(fetchMock, '/questions?knowledgePointId=kp-m2&difficulty=hard&offset=0&limit=20'),
      ).toHaveLength(1),
    );
  });

  it('题干关键词回车立即应用（不做无筛选的全量重取）', async () => {
    const fetchMock = router();
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);

    const input = screen.getByLabelText('搜索题目');
    fireEvent.change(input, { target: { value: '负数' } });
    fireEvent.submit(input.closest('form') as HTMLFormElement);

    await waitFor(() =>
      expect(calls(fetchMock, '/questions?q=%E8%B4%9F%E6%95%B0&offset=0&limit=20')).toHaveLength(1),
    );
  });
});

describe('题库首页：知识点分类树', () => {
  it('显示全部题目与各节点计数；子节点未展开时父节点显示子树总数', async () => {
    router({
      'GET /api/v1/questions': (url) => {
        const params = new URLSearchParams(url.split('?')[1] ?? '');
        if (params.get('limit') !== '1') return jsonResponse(true, 200, QUESTION_LIST);
        const pointId = params.get('knowledgePointId');
        const total = pointId === 'kp-m1' ? 1 : pointId === 'kp-m2' ? 2 : 3;
        return jsonResponse(true, 200, { ...QUESTION_LIST, questions: [], total });
      },
    });
    render(<QuestionBankWorkspace />);

    expect(await screen.findByText('知识点分类')).toBeInTheDocument();
    // 全部题目 = 3；有理数自身 1 + 子级相反数 2 = 3
    const allRow = screen.getByRole('button', { name: '全部题目' }).closest('.qb-tree-row');
    const parentRow = screen.getByRole('button', { name: '有理数' }).closest('.qb-tree-row');
    await waitFor(() => expect(parentRow?.textContent).toContain('（3）'));
    expect(allRow?.textContent).toContain('（3）');
    // 子节点折叠时父节点仍显示子树总数
    expect(screen.queryByRole('button', { name: '相反数' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '展开知识点 有理数' }));
    expect(await screen.findByRole('button', { name: '相反数' })).toBeInTheDocument();
  });

  it('单节点计数读取失败显示「—」并给出重试，不写成 0', async () => {
    router({
      'GET /api/v1/questions': (url) => {
        const params = new URLSearchParams(url.split('?')[1] ?? '');
        if (params.get('limit') !== '1') return jsonResponse(true, 200, QUESTION_LIST);
        if (params.get('knowledgePointId') === 'kp-m2') {
          return jsonResponse(false, 500, { code: 'INTERNAL_ERROR', message: '统计失败' });
        }
        return jsonResponse(true, 200, { ...QUESTION_LIST, questions: [], total: 4 });
      },
    });
    render(<QuestionBankWorkspace />);

    const alert = await screen.findByTestId('qb-tree-count-error');
    expect(alert).toHaveTextContent('不是 0');
    await waitFor(() =>
      expect(screen.getAllByText('（—）', { selector: '.qb-tree-count' }).length).toBeGreaterThan(0),
    );
    expect(within(alert).getByRole('button', { name: /重试计数/ })).toBeInTheDocument();
  });
});

describe('题库首页：题目行操作', () => {
  it('「编辑」直接打开编辑题目抽屉', async () => {
    router();
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);

    const row = screen.getByText(/下列各数中，是负数的有/).closest('.qb-question-row') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: '编辑' }));

    const dialog = await screen.findByRole('dialog', { name: '编辑题目' });
    expect(within(dialog).getByLabelText('题干')).toHaveValue('下列各数中，是负数的有？');
  });

  it('「删除」二次确认后带 expectedRevision 彻底删除，并刷新列表', async () => {
    const fetchMock = router({ 'DELETE /api/v1/questions/q-1': () => jsonResponse(true, 204, null) });
    const confirmSpy = vi.fn(() => true);
    vi.stubGlobal('confirm', confirmSpy);
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);

    fireEvent.click(screen.getByRole('button', { name: '删除题目 下列各数中，是负数的有？' }));

    // 二次确认文案写明物理删除、不可恢复
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('物理删除'));
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('不可恢复'));
    await waitFor(() => expect(calls(fetchMock, '/questions/q-1', 'DELETE')).toHaveLength(1));
    expect(String(calls(fetchMock, '/questions/q-1', 'DELETE')[0][0])).toBe(
      '/api/v1/questions/q-1?expectedRevision=2',
    );
    // 删除成功后重取列表（服务端权威）
    await waitFor(() =>
      expect(calls(fetchMock, '/questions?offset=0&limit=20', 'GET').length).toBeGreaterThan(1),
    );
  });

  it('409 QUESTION_IN_USE：展示练习/教案引用计数与解锁路径，不当作已删除', async () => {
    const fetchMock = router({
      'DELETE /api/v1/questions/q-1': () =>
        jsonResponse(false, 409, {
          code: 'QUESTION_IN_USE',
          message: '题目仍被教学链引用，不能删除。',
          retryable: false,
          details: { counts: { practices: 2, lessonFixedQuestions: 1 } },
        }),
    });
    vi.stubGlobal('confirm', vi.fn(() => true));
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);

    fireEvent.click(screen.getByRole('button', { name: '删除题目 下列各数中，是负数的有？' }));

    const blocked = await screen.findByTestId('qb-question-delete-blocked');
    expect(blocked).toHaveTextContent('审核练习固定题：2 条');
    expect(blocked).toHaveTextContent('教案生成冻结输入：1 条');
    expect(blocked).toHaveTextContent('先删除引用它的练习/教案');
    expect(calls(fetchMock, '/questions/q-1', 'DELETE')).toHaveLength(1);
    expect(screen.getByText(/下列各数中，是负数的有/)).toBeInTheDocument();
  });

  it('删除取消时不发请求；删除失败原样显示原因且列表保留', async () => {
    const fetchMock = router({
      'DELETE /api/v1/questions/q-1': () =>
        jsonResponse(false, 409, {
          code: 'REVISION_CONFLICT',
          message: '题目已被其他操作更新。',
          retryable: false,
        }),
    });
    vi.stubGlobal('confirm', vi.fn(() => false));
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);
    fireEvent.click(screen.getByRole('button', { name: '删除题目 下列各数中，是负数的有？' }));
    expect(calls(fetchMock, '/questions/q-1', 'DELETE')).toHaveLength(0);
    cleanup();

    vi.stubGlobal('confirm', vi.fn(() => true));
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);
    fireEvent.click(screen.getByRole('button', { name: '删除题目 下列各数中，是负数的有？' }));

    const alert = await screen.findByTestId('qb-question-delete-error');
    expect(alert).toHaveTextContent('REVISION_CONFLICT');
    expect(alert).toHaveTextContent('题目已被其他操作更新。');
    expect(screen.getByText(/下列各数中，是负数的有/)).toBeInTheDocument();
  });
});

describe('题库首页：批量导入面板', () => {
  it('面板内提供教材课后习题提取与文件上传，不改变顶部按钮布局', async () => {
    router({
      'POST /api/v1/question-imports/from-textbook': () =>
        jsonResponse(true, 201, { ...BATCH, importId: 'imp-9', draftCount: 4 }),
    });
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);

    fireEvent.click(screen.getByRole('button', { name: '批量导入' }));
    const dialog = await screen.findByRole('dialog', { name: '批量导入' });
    expect(within(dialog).getByRole('button', { name: /从教材课后习题提取/ })).toBeInTheDocument();
    expect(within(dialog).getByLabelText('试题文件')).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: /从教材课后习题提取/ }));
    expect(await within(dialog).findByText(/草稿 4 道/)).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: '打开校对页' })).toBeInTheDocument();
    // 批次列表刷新后显示服务端返回的批次
    expect(await within(dialog).findByText('七年级数学题库.md')).toBeInTheDocument();
  });

  it('教材未就绪时原样展示服务端错误，不显示成功文案', async () => {
    router({
      'POST /api/v1/question-imports/from-textbook': () =>
        jsonResponse(false, 503, {
          code: 'SERVICE_UNAVAILABLE',
          message: '教材目录未装配，无法读取教材习题。',
          retryable: true,
        }),
    });
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);
    fireEvent.click(screen.getByRole('button', { name: '批量导入' }));

    const dialog = await screen.findByRole('dialog', { name: '批量导入' });
    fireEvent.click(within(dialog).getByRole('button', { name: /从教材课后习题提取/ }));

    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(alert).toHaveTextContent('教材目录未装配，无法读取教材习题。');
    expect(within(dialog).queryByRole('button', { name: '打开校对页' })).not.toBeInTheDocument();
  });

  it('上传合法文件后跳到校对页；上传失败保留已选文件', async () => {
    let attempt = 0;
    const fetchMock = router({
      'POST /api/v1/question-imports': () => {
        attempt += 1;
        if (attempt === 1) {
          return jsonResponse(false, 422, {
            code: 'DOCUMENT_NEEDS_OCR',
            message: '扫描件缺少文本层。',
            retryable: false,
          });
        }
        return jsonResponse(true, 201, { ...BATCH, importId: 'imp-10' });
      },
    });
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);
    fireEvent.click(screen.getByRole('button', { name: '批量导入' }));

    const dialog = await screen.findByRole('dialog', { name: '批量导入' });
    fireEvent.change(within(dialog).getByLabelText('试题文件'), {
      target: { files: [new File(['题干'], '七年级数学.md', { type: 'text/markdown' })] },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /上传并解析/ }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('DOCUMENT_NEEDS_OCR');
    expect(within(dialog).getByText(/已选择：七年级数学.md/)).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: /上传并解析/ }));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/question-bank/imports/imp-10'));
    const [, init] = calls(fetchMock, '/question-imports', 'POST')[1] as [string, RequestInit];
    expect((init.body as FormData).get('file')).toBeInstanceOf(File);
  });
});

describe('题库首页：添加题目面板', () => {
  it('手动录入提交为导入草稿并跳到校对页（失败保留已填内容）', async () => {
    const fetchMock = router({
      'POST /api/v1/question-imports': () => jsonResponse(true, 201, { ...BATCH, importId: 'imp-11' }),
    });
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);

    fireEvent.click(screen.getByRole('button', { name: '添加题目' }));
    const dialog = await screen.findByRole('dialog', { name: '添加题目' });
    fireEvent.change(within(dialog).getByLabelText('题干'), { target: { value: '计算 $1+1$ 的值。' } });
    fireEvent.change(within(dialog).getByLabelText('答案'), { target: { value: '2' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /提交为导入草稿/ }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/question-bank/imports/imp-11'));
    const [, init] = calls(fetchMock, '/question-imports', 'POST')[0] as [string, RequestInit];
    const file = (init.body as FormData).get('file') as File;
    expect(file).toBeInstanceOf(File);
    expect(file.name).toBe('手动录入-题目.md');
    expect(file.type).toBe('text/markdown');
  });

  it('提交失败保留输入并显示错误码，不跳转', async () => {
    router({
      'POST /api/v1/question-imports': () =>
        jsonResponse(false, 500, { code: 'INTERNAL_ERROR', message: '解析服务异常。', retryable: true }),
    });
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);
    fireEvent.click(screen.getByRole('button', { name: '添加题目' }));

    const dialog = await screen.findByRole('dialog', { name: '添加题目' });
    fireEvent.change(within(dialog).getByLabelText('题干'), { target: { value: '保留我的题干' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /提交为导入草稿/ }));

    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent('INTERNAL_ERROR');
    expect(within(dialog).getByLabelText('题干')).toHaveValue('保留我的题干');
    expect(pushMock).not.toHaveBeenCalled();
  });

  it('AI 补题页签打开补题面板，且不在页面加载时调用模型', async () => {
    const fetchMock = router();
    render(<QuestionBankWorkspace />);
    await screen.findByText(/下列各数中，是负数的有/);
    fireEvent.click(screen.getByRole('button', { name: '添加题目' }));

    const dialog = await screen.findByRole('dialog', { name: '添加题目' });
    fireEvent.click(within(dialog).getByTestId('qb-generation-open'));

    expect(await within(dialog).findByTestId('qb-generation-panel')).toBeInTheDocument();
    expect(calls(fetchMock, '/question-generation-jobs', 'POST')).toHaveLength(0);
  });
});
