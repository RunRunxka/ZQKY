/**
 * F10-QB：知识点关联区块组件。
 *
 * 覆盖：正式关联与历史标签分区呈现、缺失字段不猜造、添加/移除/清空/恢复（整表替换），
 * 422 字段级错误显示到对应行、学科冲突提前说明、知识点读取失败不当空目录。
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import {
  locateLinkIssues,
  readKnowledgeLinks,
  subjectChangeState,
  type KnowledgeLinkView,
  type LinkIssueLocation,
} from './knowledge-links';
import { KnowledgeLinksPanel } from './KnowledgeLinksPanel';
import { ApiError } from '@/services/api-client';

const NO_ISSUES: LinkIssueLocation = { byIndex: new Map(), general: [] };

function link(overrides: Partial<KnowledgeLinkView> = {}): KnowledgeLinkView {
  return {
    knowledgePointId: 'kp-1',
    knowledgeRevisionId: 'kpr-1',
    knowledgeNameSnapshot: '有理数',
    subjectIdSnapshot: 'math',
    role: 'primary',
    ...overrides,
  };
}

function stubFetch(handler: (url: string, init?: RequestInit) => unknown) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(String(input), init)),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

const POINTS = {
  items: [
    {
      id: 'kp-1',
      subjectId: 'math',
      code: 'M1',
      name: '有理数',
      description: '',
      parentId: null,
      parentCode: null,
      sortOrder: 0,
      status: 'active',
      revision: 1,
      revisionId: 'kpr-1',
      version: 1,
      aliases: [],
      createdAt: '2026-10-01T00:00:00Z',
    },
    {
      id: 'kp-2',
      subjectId: 'math',
      code: 'M2',
      name: '相反数',
      description: '',
      parentId: null,
      parentCode: null,
      sortOrder: 1,
      status: 'active',
      revision: 1,
      revisionId: 'kpr-2',
      version: 1,
      aliases: [],
      createdAt: '2026-10-01T00:00:00Z',
    },
  ],
  total: 2,
  offset: 0,
  limit: 200,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderPanel(options: {
  read?: ReturnType<typeof readKnowledgeLinks>;
  links?: KnowledgeLinkView[];
  touched?: boolean;
  editable?: boolean;
  subjectId?: string;
  originalSubjectId?: string;
  legacyTags?: string[];
  issues?: LinkIssueLocation;
  onAdd?: (link: KnowledgeLinkView) => void;
  onRemove?: (index: number) => void;
  onClear?: () => void;
  onReset?: () => void;
}) {
  const read = options.read ?? { status: 'provided', links: options.links ?? [link()], skipped: 0 };
  const links = options.links ?? [link()];
  const subjectId = options.subjectId ?? 'math';
  const originalSubjectId = options.originalSubjectId ?? 'math';
  return render(
    <KnowledgeLinksPanel
      read={read}
      links={links}
      touched={options.touched ?? false}
      editable={options.editable ?? true}
      subjectId={subjectId}
      originalSubjectId={originalSubjectId}
      subjectChange={subjectChangeState(originalSubjectId, subjectId, links)}
      issues={options.issues ?? NO_ISSUES}
      legacyTags={options.legacyTags ?? ['旧标签甲', '旧标签乙']}
      idPrefix="qb-test-links"
      onAdd={options.onAdd ?? (() => undefined)}
      onRemove={options.onRemove ?? (() => undefined)}
      onRoleChange={() => undefined}
      onClear={options.onClear ?? (() => undefined)}
      onReset={options.onReset ?? (() => undefined)}
    />,
  );
}

describe('知识点关联与历史标签：分区呈现、不合并、不丢弃', () => {
  it('正式关联显示名称/角色/来源/修订，历史标签独立成块', () => {
    renderPanel({
      links: [
        link({ source: 'ai' }),
        link({
          knowledgePointId: 'kp-2',
          role: 'secondary',
          knowledgeNameSnapshot: '相反数',
          knowledgeRevisionId: 'kpr-2',
        }),
      ],
      legacyTags: ['旧标签甲'],
    });
    const panel = screen.getByTestId('qb-knowledge-links');
    expect(within(panel).getByText('有理数')).toBeInTheDocument();
    expect(within(panel).getByText('相反数')).toBeInTheDocument();
    expect(within(panel).getByText('主知识点', { selector: '.space-chip' })).toBeInTheDocument();
    expect(within(panel).getByText('AI 补题关联')).toBeInTheDocument();
    expect(within(panel).getByText('次要知识点', { selector: '.space-chip' })).toBeInTheDocument();
    expect(within(panel).getByText(/修订：kpr-2/)).toBeInTheDocument();

    const legacy = screen.getByTestId('qb-legacy-tags');
    expect(within(legacy).getByText('历史知识点标签（旧字段）')).toBeInTheDocument();
    expect(within(legacy).getByText('旧标签甲')).toBeInTheDocument();
    // 旧标签样式与正式关联区分（虚线 chip）
    expect(within(legacy).getByText('旧标签甲')).toHaveClass('qb-legacy-tag');
    expect(within(panel).getByTestId('qb-knowledge-link-count')).toHaveTextContent('2 条');
  });

  it('服务端未提供 knowledgeLinks 字段：明说未提供，不冒充「无关联」', () => {
    const read = readKnowledgeLinks({});
    renderPanel({ read, links: [] });
    expect(screen.getByTestId('qb-knowledge-links-missing')).toHaveTextContent(
      '不会用旧标签或猜测补齐',
    );
    expect(screen.getByTestId('qb-knowledge-links-empty')).toHaveTextContent('未读取到正式知识点关联');
  });

  it('形状损坏的条目丢弃并显式说明条数', () => {
    const read = readKnowledgeLinks({ knowledgeLinks: [link(), { knowledgePointId: '' }] });
    renderPanel({ read, links: [link()] });
    expect(screen.getByTestId('qb-knowledge-links-skipped')).toHaveTextContent('有 1 条关联的形状无法识别');
  });

  it('未改动关联：说明保存时不发送、服务端沿用旧关联（不制造已重写错觉）', () => {
    renderPanel({ touched: false });
    expect(screen.getByTestId('qb-knowledge-links-untouched')).toHaveTextContent('服务端会沿用旧正式关联');
  });

  it('只读模式（详情查看）不出现添加/清空/恢复入口', () => {
    renderPanel({ editable: false, touched: true, links: [link()] });
    expect(screen.queryByTestId('qb-knowledge-link-add')).not.toBeInTheDocument();
    expect(screen.queryByTestId('qb-knowledge-link-clear')).not.toBeInTheDocument();
    expect(screen.queryByTestId('qb-knowledge-links-reset')).not.toBeInTheDocument();
    // 关联本身仍可查看
    expect(screen.getByText('有理数')).toBeInTheDocument();
  });
});

describe('关联编辑：整表替换的动作与载荷', () => {
  it('从当前学科的在用知识点中添加一条（带当前修订与学科快照）', async () => {
    stubFetch((url) => (url.includes('/knowledge-points') ? jsonResponse(POINTS) : jsonResponse({}, 500)));
    const onAdd = vi.fn();
    renderPanel({ links: [], onAdd, legacyTags: [] });

    const select = await screen.findByLabelText('知识点');
    await waitFor(() => expect((select as HTMLSelectElement).disabled).toBe(false));
    fireEvent.change(select, { target: { value: 'kp-2' } });

    expect(onAdd).toHaveBeenCalledTimes(1);
    expect(onAdd.mock.calls[0][0]).toMatchObject({
      knowledgePointId: 'kp-2',
      knowledgeRevisionId: 'kpr-2',
      knowledgeNameSnapshot: '相反数',
      subjectIdSnapshot: 'math',
      role: 'primary',
    });
  });

  it('移除与清空产生整表替换所需的动作（空数组 = 清空）', () => {
    const onRemove = vi.fn();
    const onClear = vi.fn();
    renderPanel({ links: [link(), link({ knowledgePointId: 'kp-2' })], onRemove, onClear });
    fireEvent.click(screen.getByTestId('qb-knowledge-link-remove-1'));
    expect(onRemove).toHaveBeenCalledWith(1);
    fireEvent.click(screen.getByTestId('qb-knowledge-link-clear'));
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it('已改动时显示「整表替换」标识与恢复入口', () => {
    const onReset = vi.fn();
    renderPanel({ touched: true, onReset });
    expect(screen.getByTestId('qb-knowledge-links-touched')).toHaveTextContent('整表替换');
    fireEvent.click(screen.getByTestId('qb-knowledge-links-reset'));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});

describe('学科变化与字段级错误', () => {
  it('学科变化且有冲突旧关联：提前说明会被 422 拒绝，要求显式替换/清空', () => {
    renderPanel({
      links: [link({ subjectIdSnapshot: 'physics', knowledgeNameSnapshot: '力' })],
      subjectId: 'math',
      originalSubjectId: 'math-x',
    });
    const notice = screen.getByTestId('qb-knowledge-subject-change');
    expect(notice).toHaveTextContent('422');
    expect(notice).toHaveAttribute('role', 'alert');
    expect(screen.getByTestId('qb-knowledge-links-blocked')).toHaveTextContent('与新学科');
  });

  it('服务端 422 的字段级错误显示到对应关联行，其他错误为整体错误', () => {
    const links = [link(), link({ knowledgePointId: 'kp-2', knowledgeNameSnapshot: '力' })];
    const issues = locateLinkIssues(
      new ApiError('KNOWLEDGE_REFERENCE_INVALID', '冲突', 422, false, undefined, {
        issues: [
          {
            field: 'knowledgeLinks[1].knowledgePointId',
            code: 'KNOWLEDGE_REFERENCE_INVALID',
            message: '知识点 kp-2 属于学科 physics，与新学科 math 不一致；请显式替换或清空该关联。',
          },
          { code: 'KNOWLEDGE_ARCHIVED', message: '有知识点已归档，不能作为新引用。' },
        ],
      }),
      links,
    );
    renderPanel({ links, issues });
    expect(screen.getByTestId('qb-knowledge-link-issue-1')).toHaveTextContent('kp-2');
    expect(screen.queryByTestId('qb-knowledge-link-issue-0')).not.toBeInTheDocument();
    expect(screen.getByTestId('qb-knowledge-links-general-issues')).toHaveTextContent(
      '有知识点已归档，不能作为新引用。',
    );
  });

  it('知识点读取失败：显示错误码与重试入口，不把失败当空列表', async () => {
    stubFetch(() =>
      jsonResponse({ code: 'SERVICE_UNAVAILABLE', message: '知识点服务未装配。', retryable: true }, 503),
    );
    renderPanel({ links: [] });
    const error = await screen.findByTestId('qb-knowledge-points-error');
    expect(error).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(within(error).getByRole('button', { name: /重试读取知识点/ })).toBeInTheDocument();
    expect(screen.queryByTestId('qb-knowledge-points-empty')).not.toBeInTheDocument();
  });
});
