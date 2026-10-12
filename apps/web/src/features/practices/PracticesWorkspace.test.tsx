/**
 * 练习工作台（R8-FE）集成测试：全部经真实服务层（fetch 桩）验证接线与纪律。
 *
 * 覆盖：来源一（报告 → 薄弱知识点 → 目标自动勾选 → 创建）、来源二（教师描述 → AI 出题任务
 * 只进候选题库）、题库选拔建议的显式采用与增删排序、保存草稿 CAS、审核门槛（未审核不可导出）、
 * 审核后 A4 导出预览两页签与产物下载身份、本机恢复稿的损坏保护。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { PracticeRevisionView, PracticeSetView } from '@/contracts/b4';
import type { RichContentV2 } from '@/contracts/question-bank';
import { PracticesWorkspace } from './PracticesWorkspace';
import { initialPracticeSession, recoveryKey } from './session';

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

const rich: RichContentV2 = {
  version: 2,
  sharedMaterials: [],
  stemBlocks: [{ id: 'b1', kind: 'paragraph', text: '下列说法正确的是' }],
  optionBlocks: {
    A: [{ id: 'o-a', kind: 'paragraph', text: '选项甲' }],
    B: [{ id: 'o-b', kind: 'paragraph', text: '选项乙' }],
  },
  answerBlocks: [{ id: 'a1', kind: 'paragraph', text: 'A' }],
  explanationBlocks: [{ id: 'e1', kind: 'paragraph', text: '因为甲正确。' }],
  assets: [],
  origin: { originalAssetId: 'q-source', originalSha256: 'sha', sourceLocator: {} },
};

const point = { knowledgePointId: 'kp-1', knowledgeRevisionId: 'kr-1', name: '通感的表达效果', role: 'primary' as const };
const point2 = { knowledgePointId: 'kp-2', knowledgeRevisionId: 'kr-2', name: '叠词的表达效果', role: 'secondary' as const };

const RUN = {
  runId: 'run-1',
  assessmentId: 'assessment-1',
  subjectId: 'chinese',
  scoreRevisionId: 'score-rev-1',
  paperRevisionId: 'paper-rev-1',
  paperTitle: '第一次月考',
  inputHash: 'hash-1',
  ruleCode: 'any_loss_v1' as const,
  selectionSnapshot: { selectedParticipantIds: ['p1'], uniqueStudentCount: 1, participantCount: 1, leafCount: 2, stateCounts: { recorded: 1, missing: 0, absent: 0, exempt: 0 } },
  participants: [],
  knowledgePoints: [point, point2],
  job: { jobId: 'job-analysis', domain: 'teaching' as const, kind: 'analysis', attempt: 1, state: 'succeeded' as const, result: { runId: 'run-1' }, error: null },
  reportReady: true,
  archivedAt: null,
  createdAt: '2026-10-05T08:00:00Z',
};

const DRAFT_ITEM = {
  itemKey: 'key-1',
  questionRevisionId: 'qrev-1',
  ordinal: 1,
  itemStructure: {
    nodes: [
      {
        nodeKey: 'node-1',
        parentNodeKey: null,
        questionNo: '1',
        ordinal: 1,
        isScored: true,
        maxScore: '1',
        knowledgePointIds: ['kp-1'],
        sourceBlockIds: ['b1'],
      },
    ],
  },
  maxScore: '1',
  selectedKnowledgePointIds: ['kp-1'],
};

const MATERIALIZED_ITEM = {
  practiceItemId: 'item-1',
  selectionId: 'sel-1',
  itemKey: 'key-1',
  nodeKey: 'node-1',
  parentItemId: null,
  questionNo: '1',
  ordinal: 1,
  isScored: true,
  maxScoreUnits: 100,
  questionId: 'question-1',
  questionRevisionId: 'qrev-1',
  content: rich,
  knowledgePoints: [point],
  sourceLocator: {},
  reason: '符合教师约束',
  answerState: 'provided',
};

function draftRevision(overrides: Partial<PracticeRevisionView> = {}): PracticeRevisionView {
  return {
    practiceSetId: 'ps-1',
    practiceRevisionId: 'prev-draft-1',
    version: 1,
    state: 'draft',
    title: '第一次月考 针对性练习',
    subjectId: 'chinese',
    analysisRunId: 'run-1',
    sourcePaperTitle: '第一次月考',
    sourceCreatedAt: '2026-10-05T08:00:00Z',
    targetKnowledgePoints: [point],
    constraints: { count: 1, questionTypes: [], difficulties: [], includeUnknownDifficulty: false, excludeOriginal: true, deduplicate: true },
    inputHash: '',
    totalScoreUnits: 0,
    draftItems: [],
    items: [],
    convertedAssessmentId: null,
    reviewedAt: null,
    createdAt: '2026-10-12T09:00:00Z',
    ...overrides,
  };
}

function setView(revision: PracticeRevisionView, revision_no = 1): PracticeSetView {
  return {
    practiceSetId: revision.practiceSetId,
    title: revision.title,
    subjectId: revision.subjectId,
    analysisRunId: revision.analysisRunId,
    sourcePaperTitle: revision.sourcePaperTitle,
    sourceCreatedAt: revision.sourceCreatedAt,
    status: 'active',
    revision: revision_no,
    currentRevision: revision,
    revisions: [revision],
    replayed: false,
  };
}

const DRAFT_SET = setView(draftRevision(), 3);
const REVIEWED_REVISION = draftRevision({
  practiceSetId: 'ps-2',
  practiceRevisionId: 'prev-reviewed-1',
  state: 'reviewed',
  inputHash: 'hash-reviewed',
  draftItems: [DRAFT_ITEM],
  items: [MATERIALIZED_ITEM],
  totalScoreUnits: 100,
  reviewedAt: '2026-10-12T10:00:00Z',
});
const REVIEWED_SET = setView(REVIEWED_REVISION, 4);

const CATALOG = { revision: 1, defaultChatProfileId: 'p-chat-1', connections: [], profiles: [] };

interface RouterOptions {
  setById?: Record<string, PracticeSetView>;
  onCreate?: (body: Record<string, unknown>) => PracticeSetView;
  onDraft?: (body: Record<string, unknown>) => PracticeSetView;
  onReview?: () => PracticeSetView;
  suggestions?: { items: unknown[]; requestedCount: number; selectedCount: number; coverage: Record<string, number>; gaps: string[] };
  artifacts?: unknown[];
}

function router(options: RouterOptions = {}) {
  return (url: string, init: RequestInit): Response => {
    const path = url.replace(/^https?:\/\/[^/]+/, '').split('?')[0];
    const method = (init.method ?? 'GET').toUpperCase();
    const body = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
    const json = (value: unknown, status = 200) => jsonResponse(true, status, value);

    if (path === '/api/v1/analysis-runs' && method === 'GET') {
      return json({ items: [RUN], total: 1, offset: 0, limit: 50 });
    }
    if (path === '/api/v1/analysis-runs/run-1/knowledge-stats' && method === 'GET') {
      return json({ items: [
        { knowledgePointId: 'kp-1', name: '通感的表达效果', path: null, scoreRate: 0.25, questionCount: 2 },
        { knowledgePointId: 'kp-2', name: '叠词的表达效果', path: null, scoreRate: 0.8, questionCount: 1 },
      ] });
    }
    if (path === '/api/v1/model-catalog' && method === 'GET') return json(CATALOG);
    if (path === '/api/v1/practice-sets' && method === 'GET') {
      return json({ items: [DRAFT_SET, REVIEWED_SET], total: 2, offset: 0, limit: 20 });
    }
    if (path === '/api/v1/practice-sets' && method === 'POST') {
      const created = options.onCreate?.(body) ?? DRAFT_SET;
      return json(created, 201);
    }
    if (path === '/api/v1/question-generation-jobs' && method === 'POST') {
      return json({ jobId: 'gen-job-1', state: 'succeeded', attempt: 1, importId: 'imp-1', candidateCount: 3, errorCode: null }, 202);
    }
    if (/^\/api\/v1\/practice-sets\/[^/]+$/.test(path) && method === 'GET') {
      const id = path.split('/').pop() as string;
      const view = options.setById?.[id];
      if (!view) return jsonResponse(false, 404, { code: 'NOT_FOUND', message: '练习不存在', retryable: false });
      return json(view);
    }
    if (/^\/api\/v1\/practice-sets\/[^/]+\/suggestions$/.test(path) && method === 'POST') {
      return json(options.suggestions ?? {
        items: [
          {
            questionId: 'question-1',
            questionRevisionId: 'qrev-1',
            content: rich,
            knowledgePoints: [point],
            questionType: 'single_choice',
            difficulty: 'easy',
            reason: '符合教师约束；覆盖目标知识点：通感的表达效果',
            answerState: 'provided',
          },
        ],
        requestedCount: 1,
        selectedCount: 1,
        coverage: { 'kp-1': 1 },
        gaps: [],
      });
    }
    if (/^\/api\/v1\/practice-sets\/[^/]+\/draft$/.test(path) && method === 'PATCH') {
      const next = options.onDraft?.(body) ?? DRAFT_SET;
      return json(next);
    }
    if (/^\/api\/v1\/practice-sets\/[^/]+\/review$/.test(path) && method === 'POST') {
      const next = options.onReview?.() ?? REVIEWED_SET;
      return json(next);
    }
    if (/^\/api\/v1\/practice-sets\/[^/]+\/revisions$/.test(path) && method === 'POST') {
      return json(DRAFT_SET, 201);
    }
    if (/^\/api\/v1\/practice-sets\/[^/]+\/revisions\/[^/]+\/exports$/.test(path)) {
      if (method === 'GET') return json({ items: options.artifacts ?? [], total: (options.artifacts ?? []).length, offset: 0, limit: 50 });
      return json({ exportId: 'exp-1', practiceRevisionId: 'prev-reviewed-1', inputHash: 'h', job: { jobId: 'job-export-1', domain: 'teaching', kind: 'export', attempt: 0, state: 'queued', result: null, error: null }, replayed: false, reused: false }, 202);
    }
    if (path === '/api/v1/export-artifacts/art-1/download' && method === 'GET') {
      return {
        ok: true,
        status: 200,
        blob: async () => new Blob([new Uint8Array([1, 2, 3, 4])]),
        headers: { get: (name: string) => (name === 'content-disposition' ? "attachment; filename*=UTF-8''%E5%AD%A6%E7%94%9F%E5%8D%B7.docx" : null) },
      } as unknown as Response;
    }
    if (path.startsWith('/api/v1/')) {
      return jsonResponse(false, 501, { code: 'NOT_MOCKED', message: `测试未覆盖 ${method} ${path}`, retryable: false });
    }
    return jsonResponse(false, 404, { code: 'NOT_FOUND', message: '未找到', retryable: false });
  };
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('新建练习（来源一 + 来源二）', () => {
  it('选择报告后显示得分率并自动勾选目标知识点，创建提交镜像后端契约', async () => {
    const fetchMock = stubApi(router({ setById: { 'ps-new': DRAFT_SET } }));
    render(<PracticesWorkspace />);

    await screen.findByTestId('practices-run-run-1');
    fireEvent.click(screen.getByTestId('practices-run-run-1'));

    await waitFor(() => expect(screen.getByTestId('practices-target-kp-1')).toBeChecked());
    expect(screen.getByTestId('practices-target-kp-2')).toBeChecked();
    // 薄弱在前（得分率升序）：kp-1 0.25 在 kp-2 0.80 之前。
    const stats = screen.getByTestId('practices-run-stats');
    const rows = within(stats).getAllByRole('listitem');
    expect(rows[0].textContent).toContain('通感的表达效果');
    expect(rows[0].textContent).toContain('25%');

    const create = await screen.findByTestId('practices-create-submit');
    expect(create).toBeEnabled();
    fireEvent.click(create);

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => String(url).includes('/practice-sets') && (init as RequestInit)?.method === 'POST');
      expect(call).toBeTruthy();
      const payload = JSON.parse(String((call?.[1] as RequestInit).body));
      expect(payload.analysisRunId).toBe('run-1');
      expect(payload.targetKnowledgePointIds).toEqual(['kp-1', 'kp-2']);
      expect(payload.title).toContain('第一次月考');
      expect(payload.submissionId).toMatch(/[0-9a-f-]{8,}/);
      expect(payload.constraints.count).toBe(3);
    });
  });

  it('来源二：教师描述触发 AI 出题，任务接受只进候选题库（不落入练习）', async () => {
    const fetchMock = stubApi(router({ setById: { 'ps-1': DRAFT_SET } }));
    render(<PracticesWorkspace />);

    fireEvent.click(await screen.findByTestId('practices-source-description'));
    fireEvent.click(await screen.findByTestId('practices-run-run-1'));
    await waitFor(() => expect(screen.getByTestId('practices-ai-point-kp-1')).toBeChecked().valueOf());

    fireEvent.change(screen.getByTestId('practices-ai-note'), { target: { value: '贴近课本例题，基础巩固' } });
    fireEvent.change(screen.getByTestId('practices-ai-count'), { target: { value: '5' } });
    fireEvent.change(screen.getByTestId('practices-ai-difficulty'), { target: { value: 'easy' } });
    fireEvent.click(screen.getByTestId('practices-ai-generate'));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url]) => String(url).includes('/question-generation-jobs'));
      expect(call).toBeTruthy();
      const payload = JSON.parse(String((call?.[1] as RequestInit).body));
      expect(payload.modelProfileId).toBe('p-chat-1');
      expect(payload.knowledgePointIds).toEqual(['kp-1', 'kp-2']);
      expect(payload.count).toBe(5);
      expect(payload.difficulty).toBe('easy');
      expect(payload.instructions).toBe('贴近课本例题，基础巩固');
    });
    const status = await screen.findByTestId('practices-ai-status');
    expect(status.textContent).toContain('3 道候选题');
    expect(status.textContent).toContain('题库');
    expect(status.textContent).toContain('校对确认');
    // 出题任务不写练习：没有 practice-sets 的写入请求。
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).includes('/practice-sets') && (init as RequestInit)?.method === 'POST')).toBe(false);
  });
});

describe('生成后微调与审核门槛', () => {
  it('建议必须显式采用；采用后可上移/下移/移除；保存提交 CAS 版本', async () => {
    const saved = setView(draftRevision({ draftItems: [DRAFT_ITEM], items: [MATERIALIZED_ITEM], totalScoreUnits: 100 }), 4);
    stubApi(router({ setById: { 'ps-1': DRAFT_SET }, onDraft: () => saved }));
    render(<PracticesWorkspace />);

    fireEvent.click(await screen.findByTestId('practices-list-item-ps-1'));
    const suggest = await screen.findByTestId('practices-suggest');
    await waitFor(() => expect(suggest).toBeEnabled());
    fireEvent.click(suggest);

    const adopt = await screen.findByTestId('practices-adopt-qrev-1');
    await waitFor(() => expect(adopt).toBeEnabled());
    // 采用前草稿为空：建议只显示为候选。
    expect(screen.getByTestId('practices-empty-items')).toBeInTheDocument();
    fireEvent.click(adopt);

    await waitFor(() => expect(screen.getByTestId('practices-item-0')).toBeInTheDocument());
    const item = screen.getByTestId('practices-item-0');
    expect(within(item).getByLabelText('第1题上移')).toBeDisabled();
    expect(within(item).getByLabelText('第1题下移')).toBeDisabled();
    expect(item.textContent).toContain('基础');

    fireEvent.click(within(item).getByLabelText('移除第1题'));
    await waitFor(() => expect(screen.queryByTestId('practices-item-0')).not.toBeInTheDocument());
    expect(screen.getByTestId('practices-empty-items')).toBeInTheDocument();
  });

  it('保存草稿提交 CAS 版本与冻结提交标识；成功后回到「草稿已保存」', async () => {
    const saved = setView(draftRevision({ draftItems: [DRAFT_ITEM], items: [MATERIALIZED_ITEM], totalScoreUnits: 100 }), 4);
    const fetchMock = stubApi(router({ setById: { 'ps-1': DRAFT_SET }, onDraft: () => saved }));
    render(<PracticesWorkspace />);

    fireEvent.click(await screen.findByTestId('practices-list-item-ps-1'));
    const suggest = await screen.findByTestId('practices-suggest');
    await waitFor(() => expect(suggest).toBeEnabled());
    fireEvent.click(suggest);
    const adopt = await screen.findByTestId('practices-adopt-qrev-1');
    await waitFor(() => expect(adopt).toBeEnabled());
    fireEvent.click(adopt);

    const save = await screen.findByTestId('practices-save');
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => /\/practice-sets\/ps-1\/draft$/.test(String(url)) && (init as RequestInit)?.method === 'PATCH');
      expect(call).toBeTruthy();
      const payload = JSON.parse(String((call?.[1] as RequestInit).body));
      expect(payload.expectedRevision).toBe(3);
      expect(payload.submissionId).toMatch(/[0-9a-f-]{8,}/);
      expect(payload.items).toHaveLength(1);
      expect(payload.items[0].questionRevisionId).toBe('qrev-1');
      expect(payload.constraints.count).toBe(1);
    });
    expect((await screen.findByTestId('practices-editor-notice')).textContent).toContain('草稿已保存');
    // 保存不等于审核：审核仍需另行确认。
    expect(screen.getByTestId('practices-review')).toBeInTheDocument();
  });

  it('审核门槛：题量/覆盖/未保存三态显式展示，未满足时审核不可用', async () => {
    const draftWithItem = setView(draftRevision({ draftItems: [DRAFT_ITEM], items: [MATERIALIZED_ITEM] }), 3);
    stubApi(router({ setById: { 'ps-1': draftWithItem } }));
    render(<PracticesWorkspace />);

    fireEvent.click(await screen.findByTestId('practices-list-item-ps-1'));
    const gate = await screen.findByTestId('practices-review-gate');
    await waitFor(() => expect(gate.textContent).toContain('已选题目 1 题'));
    expect(gate.textContent).toContain('题量约束 1 / 1：满足');
    expect(gate.textContent).toContain('目标知识点覆盖 1 / 1');
    expect(screen.getByTestId('practices-review')).toBeEnabled();
    fireEvent.click(screen.getByTestId('practices-review'));
    expect(await screen.findByTestId('practices-review-confirm')).toBeInTheDocument();
  });

  it('未审核的草稿不能进入导出区', async () => {
    stubApi(router({ setById: { 'ps-1': DRAFT_SET } }));
    render(<PracticesWorkspace />);

    fireEvent.click(await screen.findByTestId('practices-list-item-ps-1'));
    fireEvent.click(await screen.findByTestId('practices-view-export'));

    const gate = await screen.findByTestId('practices-export-gate');
    expect(gate.textContent).toContain('未审核（review）的草稿不能进入导出区');
    expect(screen.queryByTestId('practices-paper-1')).not.toBeInTheDocument();
  });
});

describe('导出预览（已审核修订）', () => {
  it('学生卷/教师卷两页签、教师卷含答案页、A4 分页标记', async () => {
    stubApi(router({ setById: { 'ps-2': REVIEWED_SET } }));
    render(<PracticesWorkspace />);

    fireEvent.click(await screen.findByTestId('practices-list-item-ps-2'));
    fireEvent.click(await screen.findByTestId('practices-view-export'));

    const paper = await screen.findByTestId('practices-paper-1');
    expect(paper).toBeInTheDocument();
    expect(screen.getByTestId('practices-page-end-1').textContent).toContain('第 1 页结束');
    expect(screen.getByTestId('practices-answer-space-item-1')).toBeInTheDocument();
    expect(screen.queryByTestId('practices-answer-sheet')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('practices-tab-teacher'));
    expect(await screen.findByTestId('practices-answer-sheet')).toBeInTheDocument();
    expect(screen.queryByTestId('practices-answer-space-item-1')).not.toBeInTheDocument();
    // 成绩模板在没有回流转换前不可生成。
    expect(screen.getByTestId('practices-export-score_template')).toBeDisabled();
    expect(screen.getByTestId('practices-score-template-hint')).toBeInTheDocument();
  });

  it('下载固定产物：字节数一致才触发浏览器下载', async () => {
    const artifact = {
      artifactId: 'art-1',
      exportId: 'exp-1',
      practiceRevisionId: 'prev-reviewed-1',
      variant: 'student',
      assessmentId: null,
      fileAssetId: 'file-1',
      filename: '学生卷.docx',
      mediaType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      sha256: 'sha-1',
      byteSize: 4,
      downloadUrl: '/api/v1/export-artifacts/art-1/download',
      createdAt: '2026-10-12T11:00:00Z',
    };
    const createObjectURL = vi.fn(() => 'blob:test');
    const revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL }));
    stubApi(router({ setById: { 'ps-2': REVIEWED_SET }, artifacts: [artifact] }));
    render(<PracticesWorkspace />);

    fireEvent.click(await screen.findByTestId('practices-list-item-ps-2'));
    fireEvent.click(await screen.findByTestId('practices-view-export'));

    const download = await screen.findByText('下载学生卷 DOCX');
    fireEvent.click(download);
    await waitFor(() => expect(createObjectURL).toHaveBeenCalled());
    expect(click).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalled();
  });
});

describe('本机恢复稿', () => {
  it('未保存的编辑留在本机，重新打开时恢复且提示不会自动保存', async () => {
    stubApi(router({ setById: { 'ps-1': DRAFT_SET } }));
    const first = render(<PracticesWorkspace />);
    fireEvent.click(await screen.findByTestId('practices-list-item-ps-1'));
    const suggest = await screen.findByTestId('practices-suggest');
    await waitFor(() => expect(suggest).toBeEnabled());
    fireEvent.click(suggest);
    const adopt = await screen.findByTestId('practices-adopt-qrev-1');
    await waitFor(() => expect(adopt).toBeEnabled());
    fireEvent.click(adopt);
    await screen.findByTestId('practices-item-0');
    expect(window.localStorage.getItem('zhiqikeyuan:practice-session:v1:ps-1')).toContain('"dirty":true');
    first.unmount();

    render(<PracticesWorkspace />);
    fireEvent.click(await screen.findByTestId('practices-list-item-ps-1'));
    expect(await screen.findByTestId('practices-item-0')).toBeInTheDocument();
    expect((await screen.findByTestId('practices-editor-notice')).textContent).toContain('已恢复此练习的独立本机稿');
  });

  it('刷新前未确认结果的保存包：重试沿用同一 submissionId 与原样载荷', async () => {
    const fetchMock = stubApi(router({ setById: { 'ps-1': DRAFT_SET } }));
    const restored = initialPracticeSession(DRAFT_SET);
    restored.dirty = true;
    restored.saveOperation = {
      operationId: 'sub-restored-1',
      submissionId: 'sub-restored-1',
      payloadKey: '{"items":[]}',
      payload: {
        expectedRevision: 3,
        items: [DRAFT_ITEM],
        constraints: { count: 1, questionTypes: [], difficulties: [], includeUnknownDifficulty: false, excludeOriginal: true, deduplicate: true },
      },
    };
    window.localStorage.setItem(recoveryKey('ps-1'), JSON.stringify(restored));
    render(<PracticesWorkspace />);

    fireEvent.click(await screen.findByTestId('practices-list-item-ps-1'));
    const replay = await screen.findByTestId('practices-replay-restored');
    await waitFor(() => expect(replay).toBeEnabled());
    fireEvent.click(replay);

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => String(url).includes('/practice-sets/ps-1/draft') && (init as RequestInit)?.method === 'PATCH');
      expect(call).toBeTruthy();
      const payload = JSON.parse(String((call?.[1] as RequestInit).body));
      expect(payload.submissionId).toBe('sub-restored-1');
      expect(payload.expectedRevision).toBe(3);
      expect(payload.items).toHaveLength(1);
    });
  });

  it('保存失败/损坏的恢复稿原字节保留且暂停保存', async () => {
    stubApi(router({ setById: { 'ps-1': DRAFT_SET } }));
    window.localStorage.setItem('zhiqikeyuan:practice-session:v1:ps-1', '{broken');
    render(<PracticesWorkspace />);

    fireEvent.click(await screen.findByTestId('practices-list-item-ps-1'));
    const error = await screen.findByTestId('practices-cache-error');
    expect(error.textContent).toContain('原字节未覆盖');
    expect(window.localStorage.getItem('zhiqikeyuan:practice-session:v1:ps-1')).toBe('{broken');
  });
});
