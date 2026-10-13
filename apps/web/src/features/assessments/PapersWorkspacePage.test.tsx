/**
 * 试卷管理页（`/assessments/papers`，参考图布局，R5-FE 2026-10-11；R10-FE 2026-10-12 去归档）。
 *
 * 覆盖参考图要求的版面与不可回退的行为：
 * 操作行（导入试卷 / 删除试卷）/ 表格列（试卷名称 / 科目 / 操作：浏览、编辑、删除）/
 * 表格下方「AI 试题知识点分类」环状图卡（含百分比图例）与拆题结构；
 * 列表读取失败显示错误码与重试而**不是**空列表；物理删除被守卫拒绝时逐项列出引用原因
 * （R10-FE：不再提供「改为归档」兜底）；页面没有归档/恢复入口，也不请求 archive/restore 端点；
 * 拆题结构只给题号/分值/知识点，不显示试卷正文。
 */

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { PaperRevisionContentView, PaperView } from '@/contracts/papers';
import { PapersWorkspacePage } from './PapersWorkspacePage';

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

const PAPER: PaperView = {
  paperId: 'paper-1',
  subjectId: 'math',
  title: '七年级数学期中试卷',
  status: 'active',
  revision: 4,
  currentRevisionId: 'rev-1',
  currentState: 'confirmed',
  version: 1,
  totalScoreUnits: 10000,
  totalScore: '100',
  itemCount: 3,
  scoredLeafCount: 2,
  blockingIssueCount: 0,
  createdAt: '2026-10-01T00:00:00Z',
};

const REVISION: PaperRevisionContentView = {
  paperId: 'paper-1',
  paperRevisionId: 'rev-1',
  version: 1,
  state: 'confirmed',
  subjectId: 'math',
  title: '七年级数学期中试卷',
  totalScoreUnits: 10000,
  totalScore: '100',
  confirmedAt: '2026-10-02T00:00:00Z',
  createdAt: '2026-10-01T00:00:00Z',
  items: [
    {
      itemId: 'item-1',
      parentItemId: null,
      questionNo: '1',
      ordinal: 1,
      isScored: true,
      maxScoreUnits: 500,
      maxScore: '5',
      content: { version: 2, stemBlocks: [{ id: 'b1', kind: 'paragraph', text: '这是不该显示的题面正文' }] },
      sourceLocator: { paragraph: 3 },
      knowledge: [
        {
          knowledgePointId: 'kp-1',
          knowledgeRevisionId: 'kr-1',
          knowledgeNameSnapshot: '有理数',
          role: 'primary',
          source: 'ai_confirmed',
        },
      ],
    },
    {
      itemId: 'item-2',
      parentItemId: null,
      questionNo: '2',
      ordinal: 2,
      isScored: true,
      maxScoreUnits: 500,
      maxScore: '5',
      content: { version: 2, stemBlocks: [] },
      sourceLocator: {},
      knowledge: [],
    },
  ],
  blocks: [
    {
      blockId: 'blk-1',
      ordinal: 1,
      kind: 'paragraph',
      locator: { paragraph: 3 },
      disposition: 'item',
      itemId: 'item-1',
      excludeReason: null,
      content: { id: 'b1', kind: 'paragraph', text: '这是不该显示的题面正文' },
    },
  ],
  issues: [],
};

const DISTRIBUTION = [
  { knowledgePointId: 'kp-1', name: '有理数', itemCount: 1, totalScoreUnits: 500, scoreRatio: 0.5 },
  { knowledgePointId: 'unclassified', name: '未分类', itemCount: 1, totalScoreUnits: 500, scoreRatio: 0.5 },
];

function defaultHandler(options: { papers?: PaperView[]; papersStatus?: number } = {}): Handler {
  const list = options.papers ?? [PAPER];
  return (url, init) => {
    if (url.includes('/textbook-taxonomy')) {
      return jsonResponse(true, 200, {
        stages: [{ id: 'stage-j', label: '初中' }],
        grades: [{ id: 'g7', label: '七年级', stageId: 'stage-j' }],
        subjects: [{ id: 'math', label: '数学' }],
        editions: [{ id: 'rj', label: '人教版' }],
      });
    }
    if (url.includes('/knowledge-distribution')) {
      return jsonResponse(true, 200, DISTRIBUTION);
    }
    if (url.includes('/revisions/rev-1/content')) {
      return jsonResponse(true, 200, REVISION);
    }
    if (url.includes('/papers/paper-1') && (init.method ?? 'GET') === 'DELETE') {
      return jsonResponse(true, 200, { deleted: true, paperId: 'paper-1' });
    }
    if (url.includes('/papers')) {
      if (options.papersStatus && options.papersStatus >= 400) {
        return jsonResponse(false, options.papersStatus, {
          code: 'SERVICE_UNAVAILABLE',
          message: '后端服务不可用。',
          retryable: true,
        });
      }
      return jsonResponse(true, 200, { items: list, total: list.length, offset: 0, limit: 200 });
    }
    return jsonResponse(false, 404, { code: 'NOT_FOUND', message: `未 mock：${url}` });
  };
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

describe('试卷管理页：列表版面（参考图）', () => {
  it('渲染标题、操作行、表头列与行操作', async () => {
    stubApi(defaultHandler());
    render(<PapersWorkspacePage />);
    expect(screen.getByRole('heading', { level: 1, name: '试卷管理' })).toBeInTheDocument();
    expect(screen.getByTestId('assessments-paper-import')).toHaveTextContent('导入试卷');
    expect(screen.getByTestId('assessments-paper-delete-selected')).toHaveTextContent('删除试卷');

    const table = await screen.findByRole('table');
    expect(within(table).getByText('七年级数学期中试卷')).toBeInTheDocument();
    for (const column of ['试卷名称', '科目', '操作']) {
      expect(within(table).getByRole('columnheader', { name: column })).toBeInTheDocument();
    }
    expect(within(table).getByText('数学')).toBeInTheDocument();
    expect(screen.getByTestId('assessments-paper-browse-paper-1')).toHaveTextContent('浏览');
    expect(screen.getByTestId('assessments-paper-edit-paper-1')).toHaveTextContent('编辑');
    expect(screen.getByTestId('assessments-paper-delete-paper-1')).toHaveTextContent('删除');
  });

  it('表格下方是「AI 试题知识点分类」卡：环状图 + 含百分比图例', async () => {
    stubApi(defaultHandler());
    render(<PapersWorkspacePage />);
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'AI 试题知识点分类' })).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.getByTestId('paper-knowledge-donut')).toBeInTheDocument(),
    );
    const legend = screen.getByRole('list', { name: '知识点占比图例' });
    expect(within(legend).getByText('有理数')).toBeInTheDocument();
    expect(within(legend).getByText('未分类')).toBeInTheDocument();
    expect(within(legend).getAllByText(/50%/)).toHaveLength(2);
    expect(within(legend).getAllByText(/1 题 · 5 分/)).toHaveLength(2);
    expect(screen.getByRole('img', { name: '试卷知识点占比环状图' })).toBeInTheDocument();
  });

  it('拆题结构只给题号/分值/知识点，不渲染试卷正文', async () => {
    stubApi(defaultHandler());
    render(<PapersWorkspacePage />);
    await waitFor(() =>
      expect(screen.getByTestId('paper-structure-panel')).toBeInTheDocument(),
    );
    const panel = screen.getByTestId('paper-structure-panel');
    await waitFor(() => expect(within(panel).getByText(/题 1/)).toBeInTheDocument());
    expect(within(panel).getByText('有理数 · primary · ai_confirmed')).toBeInTheDocument();
    expect(within(panel).getByText('未关联知识点')).toBeInTheDocument();
    // 内容只给结构摘要（块数量），不显示正文
    expect(within(panel).getByText('题面 1 块 · 选项 0 组 · 答案 0 块 · 解析 0 块')).toBeInTheDocument();
    expect(within(panel).queryByText(/这是不该显示的题面正文/)).not.toBeInTheDocument();
  });

  it('列表为空显示空态；读取失败显示错误码与重试而不是空列表', async () => {
    stubApi(defaultHandler({ papers: [] }));
    render(<PapersWorkspacePage />);
    await waitFor(() =>
      expect(screen.getByTestId('assessments-papers-empty')).toHaveTextContent('还没有试卷'),
    );
    expect(screen.queryByTestId('assessments-papers-error')).not.toBeInTheDocument();

    cleanup();
    stubApi(defaultHandler({ papersStatus: 503 }));
    render(<PapersWorkspacePage />);
    await waitFor(() =>
      expect(screen.getByTestId('assessments-papers-error')).toHaveTextContent(
        'SERVICE_UNAVAILABLE',
      ),
    );
    expect(screen.getByTestId('assessments-papers-error')).toHaveTextContent('这不是空列表');
    expect(screen.queryByTestId('assessments-papers-empty')).not.toBeInTheDocument();
  });
});

describe('试卷管理页：物理删除受引用守卫（无归档兜底）', () => {
  it('409 PAPER_IN_USE：逐项列出引用计数，且不再提供「改为归档」', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/papers/paper-1') && (init.method ?? 'GET') === 'DELETE') {
        return jsonResponse(false, 409, {
          code: 'PAPER_IN_USE',
          message: '该原卷已被施测引用，不能删除；请先删除引用它的施测。',
          details: { counts: { assessments: 1 } },
        });
      }
      return defaultHandler()(url, init);
    });
    render(<PapersWorkspacePage />);
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('assessments-paper-delete-selected'));
    await waitFor(() =>
      expect(screen.getByTestId('assessments-paper-delete-guard')).toHaveTextContent(
        'PAPER_IN_USE',
      ),
    );
    const guard = screen.getByTestId('assessments-paper-delete-guard');
    // R10-FE：引用清单分组后，阻断项写明去处（到学情分析删该施测）
    expect(guard).toHaveTextContent('必须先处置（它们挡住删除，且不随删除清掉）：');
    expect(guard).toHaveTextContent('引用施测（先在学情分析删除该施测，再删原卷） 1 条');
    expect(within(guard).queryByText('改为归档（不删除历史）')).not.toBeInTheDocument();
    // 只发了删除，没有后续归档请求
    expect(calls(fetchMock, '/papers/paper-1', 'DELETE')).toHaveLength(1);
    expect(
      fetchMock.mock.calls.every(([url]) => {
        const text = String(url);
        return !text.includes('/archive') && !text.includes('/restore');
      }),
    ).toBe(true);
  });

  it('删除成功后清空选中并重新读取列表', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchMock = stubApi(defaultHandler());
    render(<PapersWorkspacePage />);
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('assessments-paper-delete-paper-1'));
    await waitFor(() => expect(calls(fetchMock, '/papers/paper-1', 'DELETE')).toHaveLength(1));
    await waitFor(() =>
      expect(screen.getByTestId('assessments-paper-notice')).toHaveTextContent('已彻底删除试卷'),
    );
  });

  it('没有归档/恢复入口：无「显示已归档」开关、无归档按钮', async () => {
    stubApi(defaultHandler());
    render(<PapersWorkspacePage />);
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());

    expect(screen.queryByLabelText('显示已归档试卷')).not.toBeInTheDocument();
    expect(screen.queryByText('显示已归档')).not.toBeInTheDocument();
    expect(screen.queryByTestId('assessments-paper-archive-paper-1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('assessments-paper-restore-paper-1')).not.toBeInTheDocument();
    expect(screen.queryByText('归档')).not.toBeInTheDocument();
    expect(screen.queryByText('恢复')).not.toBeInTheDocument();
  });
});
