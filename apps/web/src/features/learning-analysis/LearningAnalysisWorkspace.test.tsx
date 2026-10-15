/**
 * 学情分析工作区（R6-FE）：五图各自的数据源与错误隔离、顶部筛选（班级/试卷/时间粒度）、
 * 报告读取失败不当空目录、未就绪报告不读图表、小题分导入面板入口。
 *
 * 与归档测试的差异（本卡裁定，已在交付说明报告）：
 * - 趋势图由折线改为红色柱状图：这里用 Chart.js 替身捕获真实传给 `new Chart()` 的配置，
 *   直接断言图型、数据与颜色口径（jsdom 无 Canvas 2D context，替身也避免依赖真实画布）；
 * - 归档的创建报告 / 归档 / 彻底删除 / 教师备注页签不在本卡交付范围，测试不覆盖。
 */

import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ApiError } from '@/services/api-client';
import type { AnalysisRunView, ItemStatView } from '@/contracts/learning-analysis';
import { LearningAnalysisWorkspace } from './LearningAnalysisWorkspace';

const mocks = vi.hoisted(() => ({ api: {} as Record<string, unknown> }));

vi.mock('@/services/learning-analysis-api', () => ({
  learningAnalysisApi: mocks.api,
  COLUMN_PATTERN: /^[A-Za-z]{1,3}$/,
}));

/** Chart.js 替身：捕获配置，避免 jsdom 画布依赖；真实浏览器仍走真实 Chart.js。 */
const chartStub = vi.hoisted(() => ({
  configs: [] as Array<Record<string, unknown>>,
  register: vi.fn(),
}));

vi.mock('chart.js', () => ({
  Chart: class {
    static register = chartStub.register;
    constructor(_element: unknown, config: Record<string, unknown>) {
      chartStub.configs.push(config);
    }
    destroy() {}
  },
  CategoryScale: {},
  LinearScale: {},
  BarController: {},
  BarElement: {},
  LineElement: {},
  PointElement: {},
  Filler: {},
  Tooltip: {},
  Legend: {},
  Title: {},
}));

/** 与 globals.css `--danger` 同值；jsdom 不加载样式表，取 token 失败时的兜底色。 */
const DANGER = '#c62d21';
const WEAK_BROWN = '#8a5a2e';

const RUN: AnalysisRunView = {
  runId: 'run-1',
  assessmentId: 'asm-1',
  scoreRevisionId: 'rev-1',
  paperRevisionId: 'paper-1',
  paperTitle: '第一次月考',
  reportReady: true,
  createdAt: '2026-10-05T08:00:00Z',
  participants: [
    {
      participantId: 'p1',
      studentId: 's1',
      studentNo: '001',
      name: '甲',
      classId: 'class-a',
      className: '七一班',
      attemptNo: 1,
      attendance: 'present',
    },
  ],
  knowledgePoints: [],
  selectionSnapshot: {
    selectedParticipantIds: ['p1'],
    uniqueStudentCount: 1,
    participantCount: 1,
    leafCount: 2,
    stateCounts: { recorded: 2, missing: 0, absent: 0, exempt: 0 },
  },
};

const ITEM_STATS: ItemStatView[] = [
  {
    itemId: 'i1',
    itemPath: '1',
    maxScoreUnits: 100,
    recordedCount: 1,
    totalScoreUnits: 80,
    scoreRate: 0.8,
  },
  {
    itemId: 'i2',
    itemPath: '2',
    maxScoreUnits: 100,
    recordedCount: 0,
    totalScoreUnits: 0,
    scoreRate: null,
  },
];

function page<T>(items: T[]) {
  return { items, total: items.length, offset: 0, limit: 20 };
}

/** 闭环补齐（2026-10-13）用到的固定数据：已确认原卷、班级学生、新建施测回执、成绩修订。 */
const CLOSED_LOOP = {
  paper: {
    paperId: 'paper-1',
    title: '第一次月考原卷',
    version: 1,
    currentRevisionId: 'paper-1',
    currentState: 'confirmed' as const,
    scoredLeafCount: 16,
  },
  created: {
    assessment: {
      assessmentId: 'asm-9',
      paperId: 'paper-1',
      paperRevisionId: 'paper-1',
      paperTitle: '第一次月考原卷',
      title: '第一次月考',
      heldOn: '2026-10-13',
      revision: 0,
      participantCount: 1,
      classIds: ['class-a'],
    },
    participants: [
      {
        participantId: 'p1',
        studentId: 's1',
        nameSnapshot: '甲',
        classId: 'class-a',
        attemptNo: 1,
        attendance: 'present' as const,
      },
    ],
    replayed: false,
  },
  revision: {
    revisionId: 'rev-1',
    assessmentId: 'asm-1',
    paperRevisionId: 'paper-1',
    version: 1,
    state: 'confirmed' as const,
    confirmedAt: '2026-10-13T09:00:00Z',
    createdAt: '2026-10-13T08:00:00Z',
    participantSnapshot: [
      {
        participantId: 'p1',
        studentId: 's1',
        studentNo: '001',
        name: '甲',
        classId: 'class-a',
        attemptNo: 1,
        attendance: 'present' as const,
      },
    ],
  },
  runReceipt: {
    runId: 'run-9',
    inputHash: 'hash-9',
    scoreRevisionId: 'rev-1',
    paperRevisionId: 'paper-1',
    replayed: false,
    reused: false,
  },
};

function baseApi() {
  return {
    listClasses: vi.fn(async () => page([{ id: 'class-a', name: '七一班' }])),
    listAssessments: vi.fn(async () =>
      page([
        {
          assessmentId: 'asm-1',
          paperId: 'paper-1',
          paperRevisionId: 'paper-1',
          paperTitle: '第一次月考原卷',
          title: '第一次月考',
          heldOn: '2026-09-30',
          revision: 3,
          participantCount: 1,
          classIds: ['class-a'],
        },
      ]),
    ),
    listPapers: vi.fn(async () =>
      page([CLOSED_LOOP.paper, { ...CLOSED_LOOP.paper, paperId: 'paper-2', title: '草稿卷', currentState: 'draft' }]),
    ),
    listClassStudents: vi.fn(async () => ({
      items: [{ id: 's1', name: '甲', studentNo: '001', status: 'active' }],
      total: 1,
    })),
    createAssessment: vi.fn(async () => CLOSED_LOOP.created),
    listScoreRevisions: vi.fn(async () => ({ items: [CLOSED_LOOP.revision], total: 1 })),
    createAnalysisRun: vi.fn(async () => CLOSED_LOOP.runReceipt),
    listAnalysisRuns: vi.fn(async () => page([RUN])),
    getAnalysisRun: vi.fn(async () => RUN),
    getAnalysisItemStats: vi.fn(async () => ITEM_STATS),
    getAnalysisKnowledgeStats: vi.fn(async () => ({
      items: [
        { knowledgePointId: 'kp-1', name: '分式', path: '代数/分式', scoreRate: 0.5, questionCount: 2 },
        { knowledgePointId: 'kp-2', name: '整式', path: null, scoreRate: 0.9, questionCount: 1 },
      ],
    })),
    getAnalysisStudentKnowledge: vi.fn(async () => ({
      knowledgePoints: [{ knowledgePointId: 'kp-1', name: '分式' }],
      students: [
        { label: '学生A', cells: [{ knowledgePointId: 'kp-1', scoreRate: null, questionCount: 1 }] },
        { label: '学生B', cells: [{ knowledgePointId: 'kp-1', scoreRate: 0.25, questionCount: 1 }] },
      ],
    })),
    getAnalysisDistribution: vi.fn(async () => ({
      buckets: [
        { label: '低（<40%）', count: 1 },
        { label: '中（40–70%）', count: 0 },
        { label: '高（≥70%）', count: 1 },
      ],
    })),
    generateAnalysisCommentary: vi.fn(async () => ({
      commentary: '候选评价',
      degraded: false,
      reason: null,
    })),
    createAnalysisNote: vi.fn(),
    createAnalysisReport: vi.fn(),
    downloadExportArtifact: vi.fn(),
    createScoreImport: vi.fn(),
  };
}

function installApi(overrides: Record<string, unknown> = {}) {
  const api = baseApi();
  Object.assign(mocks.api, api, overrides);
  return mocks.api as unknown as Record<string, ReturnType<typeof vi.fn>>;
}

/** 取某张图的配置（按数据集 label 或坐标轴特征定位）。 */
function configOf(predicate: (config: Record<string, unknown>) => boolean) {
  return chartStub.configs.find(predicate);
}

function datasetOf(config: Record<string, unknown> | undefined) {
  return (config?.data as { datasets: Array<Record<string, unknown>>; labels: unknown[] })
    ?.datasets?.[0];
}

/**
 * 柱体底色：主题把纯色换成了自上而下的同色渐变（scriptable 函数）。图表区未布局时渐变函数
 * 退回基色，这里按此口径逐柱解析出基色，断言颜色仍取自 token（红柱=--danger、薄弱=褐）。
 */
function barColorsOf(config: Record<string, unknown> | undefined) {
  const dataset = datasetOf(config);
  const background = dataset?.backgroundColor;
  const count = (dataset?.data as unknown[] | undefined)?.length ?? 0;
  if (typeof background !== 'function') return background;
  return Array.from({ length: count }, (_, dataIndex) =>
    (background as (context: unknown) => unknown)({ chart: { chartArea: undefined }, dataIndex }),
  );
}

function labelsOf(config: Record<string, unknown> | undefined) {
  return (config?.data as { labels: unknown[] })?.labels;
}

beforeAll(() => {
  // 「新建施测」用 Modal（原生 <dialog>.showModal）；jsdom 不实现，这里按既有先例补桩。
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close() {
    this.open = false;
  };
});

beforeEach(() => {
  chartStub.configs.length = 0;
  for (const key of Object.keys(mocks.api)) delete mocks.api[key];
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('学情分析工作区', () => {
  it('五图各自渲染：红柱趋势、热力图、知识点排行、分数段分布、学生×知识点矩阵（尚无≠0）', async () => {
    installApi();
    render(<LearningAnalysisWorkspace initialAssessmentId="asm-1" />);

    expect(await screen.findByTestId('la-trend-card')).toBeInTheDocument();
    expect(await screen.findByTestId('la-heatmap-card')).toBeInTheDocument();
    expect(await screen.findByTestId('la-knowledge-card')).toBeInTheDocument();
    expect(await screen.findByTestId('la-student-card')).toBeInTheDocument();
    expect(await screen.findByTestId('la-distribution-card')).toBeInTheDocument();

    // 小题得分率趋势：红色「柱状图」，横轴题号、纵轴得分率；无有效作答的题留空（null，不补 0）
    // 趋势 / 排行 / 分布三张 Canvas 图（热力图与矩阵为 DOM 色阶）
    await waitFor(() => expect(chartStub.configs.length).toBe(3));
    const trend = configOf((config) => datasetOf(config)?.label === '得分率 %');
    expect(trend?.type).toBe('bar');
    expect(labelsOf(trend)).toEqual(['1', '2']);
    expect(datasetOf(trend)?.data).toEqual([80, null]);
    expect(barColorsOf(trend)).toEqual([DANGER, DANGER]);
    expect(datasetOf(trend)?.hoverBackgroundColor).toBe(DANGER);
    expect(screen.getByRole('img', { name: /小题得分率趋势/ })).toBeInTheDocument();

    // 小题得分热力图：80 与「无有效作答」（—）区分显示，不补 0
    const heatmap = screen.getByTestId('analysis-heatmap');
    expect(within(heatmap).getByText('80')).toBeInTheDocument();
    expect(within(heatmap).getByText('—')).toBeInTheDocument();

    // 知识点排行：横向条形（indexAxis=y），按得分率从低到高，≤60% 用褐色
    const ranking = chartStub.configs.find(
      (config) => (config.options as { indexAxis?: string } | undefined)?.indexAxis === 'y',
    );
    expect(ranking).toBeTruthy();
    expect(labelsOf(ranking)).toEqual(['分式（代数/分式）', '整式']);
    expect(datasetOf(ranking)?.data).toEqual([50, 90]);
    expect(barColorsOf(ranking)).toEqual([WEAK_BROWN, '#2563eb']);

    // 学生 × 知识点：null 显示「尚无」，不显示 0
    const matrix = screen.getByTestId('la-student-matrix');
    expect(within(matrix).getByText('尚无')).toBeInTheDocument();
    expect(within(matrix).queryByText('0%')).not.toBeInTheDocument();
    expect(within(matrix).getByText('25%')).toBeInTheDocument();
    expect(within(matrix).getByText('学生A')).toBeInTheDocument();

    // 分数段分布：低/中/高分档计数
    const distribution = configOf((config) => datasetOf(config)?.label === '小题数');
    expect(labelsOf(distribution)).toEqual(['低（<40%）', '中（40–70%）', '高（≥70%）']);
    expect(datasetOf(distribution)?.data).toEqual([1, 0, 1]);
  });

  it('单一数据源失败只影响该卡：显示原因与重试，其他卡照常渲染', async () => {
    const distribution = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('SERVICE_UNAVAILABLE', '后端未上线', 501, true))
      .mockResolvedValue({ buckets: [{ label: '高（≥70%）', count: 2 }] });
    installApi({ getAnalysisDistribution: distribution });
    render(<LearningAnalysisWorkspace initialAssessmentId="asm-1" />);

    const failed = await screen.findByTestId('la-distribution-card-error');
    expect(failed).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(screen.getByTestId('la-trend-card')).toBeInTheDocument();
    expect(screen.getByTestId('la-knowledge-card')).toBeInTheDocument();
    expect(screen.getByTestId('la-student-card')).toBeInTheDocument();
    expect(
      configOf((config) => datasetOf(config)?.label === '小题数'),
    ).toBeUndefined();

    fireEvent.click(within(failed).getByRole('button', { name: '重试' }));
    await waitFor(() => expect(distribution).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      const distribution2 = configOf((config) => datasetOf(config)?.label === '小题数');
      expect(distribution2).toBeTruthy();
      expect(datasetOf(distribution2)?.data).toEqual([2]);
    });
  });

  it('筛选：班级经服务端收窄试卷、试卷驱动报告列表、时间粒度显式过滤并说明口径', async () => {
    const oldRun: AnalysisRunView = { ...RUN, runId: 'run-old', createdAt: '2026-01-01T00:00:00Z' };
    const listAssessments = vi.fn(async () => page([]));
    installApi({ listAssessments, listAnalysisRuns: vi.fn(async () => page([oldRun])) });
    render(<LearningAnalysisWorkspace />);

    // 班级 → 服务端查询参数（不是把失败当空名单、也不做本地姓名推断）
    await screen.findByLabelText('班级筛选');
    fireEvent.change(screen.getByLabelText('班级筛选'), { target: { value: 'class-a' } });
    await waitFor(() =>
      expect(listAssessments).toHaveBeenCalledWith(
        expect.objectContaining({ classId: 'class-a' }),
        expect.anything(),
      ),
    );

    // 时间粒度：远期报告被过滤，并给出可解释的空态与口径说明
    const listRuns = mocks.api.listAnalysisRuns as ReturnType<typeof vi.fn>;
    await waitFor(() => expect(listRuns).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('时间粒度筛选'), { target: { value: '7d' } });
    expect(await screen.findByTestId('la-runs-time-empty')).toHaveTextContent(
      '当前时间粒度下没有报告',
    );
    expect(screen.getByText(/时间粒度按报告创建时间在已读取的报告页内过滤/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('时间粒度筛选'), { target: { value: 'all' } });
    expect(await screen.findByTestId('la-run-run-old')).toBeInTheDocument();
  });

  it('报告读取失败显示原因与重试，不当空目录；未就绪报告不读图表', async () => {
    const getAnalysisRun = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('DB_BROKEN', '读取损坏', 500, false))
      .mockResolvedValue({ ...RUN, reportReady: false });
    installApi({ getAnalysisRun });
    render(<LearningAnalysisWorkspace initialAssessmentId="asm-1" />);

    const failed = await screen.findByTestId('la-run-error');
    expect(failed).toHaveTextContent('DB_BROKEN');
    expect(screen.queryByTestId('la-trend-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('la-runs-empty')).not.toBeInTheDocument();

    fireEvent.click(within(failed).getByRole('button', { name: '重试' }));
    expect(await screen.findByTestId('la-run-not-ready')).toHaveTextContent('该报告尚未准备好');
    expect(screen.queryByTestId('la-trend-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('analysis-ai-commentary')).not.toBeInTheDocument();
    expect(chartStub.configs).toHaveLength(0);
  });

  it('报告列表读取失败显示原因，不写成空报告', async () => {
    installApi({
      listAnalysisRuns: vi.fn(async () => {
        throw new ApiError('SERVICE_UNAVAILABLE', '后端未运行', 0, true);
      }),
    });
    render(<LearningAnalysisWorkspace initialAssessmentId="asm-1" />);
    const error = await screen.findByTestId('la-runs-error');
    expect(error).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(screen.queryByTestId('la-runs-empty')).not.toBeInTheDocument();
  });

  it('「导入小题分」打开面板；未选试卷时提示先选试卷且不发任何导入请求', async () => {
    const api = installApi();
    render(<LearningAnalysisWorkspace />);
    fireEvent.click(await screen.findByRole('button', { name: /导入小题分/ }));
    expect(await screen.findByTestId('score-import-panel')).toBeInTheDocument();
    expect(screen.getByTestId('score-import-no-assessment')).toHaveTextContent('先在上方选择试卷');
    expect(api.createScoreImport).not.toHaveBeenCalled();
  });

  it('报告就绪时出现 AI 评价与导出入口', async () => {
    installApi();
    render(<LearningAnalysisWorkspace initialAssessmentId="asm-1" />);
    expect(await screen.findByTestId('analysis-ai-commentary')).toBeInTheDocument();
    expect(screen.getByTestId('analysis-export-report')).toBeInTheDocument();
    expect(screen.getByText(/学生以代称进模型，不传姓名\/学号/)).toBeInTheDocument();
  });
});

describe('学情分析：删除施测（R10-BE 施测=成绩链所有者）', () => {
  it('删除成功：二次确认点名后果 → DELETE 带 expectedRevision → 回执逐项列出级联计数并清空筛选', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const deleteAssessment = vi.fn(async () => ({
      deleted: true,
      assessmentId: 'asm-1',
      participants: 3,
      scoreImports: 1,
      scoreRevisions: 1,
      itemScores: 6,
      analysisRuns: 1,
      practiceSets: 0,
      practiceConversions: 0,
      exports: 0,
      unlinkedLessonRevisions: 0,
    }));
    const listAssessments = vi.fn(async () =>
      page([
        {
          assessmentId: 'asm-1',
          paperId: 'paper-1',
          paperRevisionId: 'paper-1',
          paperTitle: '第一次月考原卷',
          title: '第一次月考',
          heldOn: '2026-09-30',
          revision: 3,
          participantCount: 1,
          classIds: ['class-a'],
        },
      ]),
    );
    installApi({ deleteAssessment, listAssessments });
    render(<LearningAnalysisWorkspace initialAssessmentId="asm-1" />);
    await screen.findByTestId('la-trend-card');

    fireEvent.click(screen.getByTestId('la-assessment-delete'));
    await waitFor(() => expect(deleteAssessment).toHaveBeenCalledWith('asm-1', 3));
    // 确认文案按类别点名会被一起删掉的数据（不可恢复）
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('不可恢复'));
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('学情报告'));

    const receipt = await screen.findByTestId('la-assessment-delete-receipt');
    expect(receipt).toHaveTextContent('已彻底删除施测「第一次月考」');
    expect(receipt).toHaveTextContent('参测人次 3');
    expect(receipt).toHaveTextContent('成绩导入批次 1');
    expect(receipt).toHaveTextContent('小题分 6');
    expect(receipt).toHaveTextContent('学情报告 1');
    // 计数为 0 的项不列（不把"没删到"说成删了）
    expect(receipt).not.toHaveTextContent('派生练习');
    expect(receipt).not.toHaveTextContent('教案修订来源指针置空');
    // 删除后清空筛选并重新读取施测列表（报告链已随之消失）
    await waitFor(() => expect(screen.getByLabelText('试卷筛选')).toHaveValue(''));
    expect(listAssessments.mock.calls.length).toBeGreaterThan(1);
    expect(screen.queryByTestId('la-assessment-delete-guard')).not.toBeInTheDocument();
  });

  it('409 ASSESSMENT_IN_USE：逐项列出教案冻结血缘，不显示成功回执', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    installApi({
      deleteAssessment: vi.fn(async () => {
        throw new ApiError(
          'ASSESSMENT_IN_USE',
          '施测链仍被教案的冻结生成血缘引用，不能删除（教案生成输入 1 条）；这些行的来源指针是 NOT NULL 的不可变历史。',
          409,
          false,
          undefined,
          { counts: { lessonGenerationInputs: 1, lessonProposals: 0, scoreRevisions: 1 } },
        );
      }),
    });
    render(<LearningAnalysisWorkspace initialAssessmentId="asm-1" />);
    await screen.findByTestId('la-trend-card');

    fireEvent.click(screen.getByTestId('la-assessment-delete'));
    const guard = await screen.findByTestId('la-assessment-delete-guard');
    expect(guard).toHaveTextContent('ASSESSMENT_IN_USE');
    expect(guard).toHaveTextContent('教案生成输入（冻结血缘，需先在教案端处置） 1 条');
    expect(guard).toHaveTextContent('成绩修订 1 条');
    // 计数为 0 的引用不列；被拒绝时不显示成功回执
    expect(guard).not.toHaveTextContent('教案 AI 候选');
    expect(screen.queryByTestId('la-assessment-delete-receipt')).not.toBeInTheDocument();
  });

  it('乐观锁 409 走普通错误区（不伪装成引用问题）', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    installApi({
      deleteAssessment: vi.fn(async () => {
        throw new ApiError(
          'ASSESSMENT_REVISION_STALE',
          '数据已被其他操作更新，请刷新后重试。',
          409,
          false,
          undefined,
          { currentRevision: 5 },
        );
      }),
    });
    render(<LearningAnalysisWorkspace initialAssessmentId="asm-1" />);
    await screen.findByTestId('la-trend-card');

    fireEvent.click(screen.getByTestId('la-assessment-delete'));
    const error = await screen.findByTestId('la-assessment-delete-error');
    expect(error).toHaveTextContent('删除施测失败（ASSESSMENT_REVISION_STALE）');
    expect(screen.queryByTestId('la-assessment-delete-guard')).not.toBeInTheDocument();
  });

  it('未选择施测时删除键禁用，点击不发起请求', async () => {
    const api = installApi({ deleteAssessment: vi.fn() });
    render(<LearningAnalysisWorkspace />);
    const button = await screen.findByTestId('la-assessment-delete');
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(api.deleteAssessment).not.toHaveBeenCalled();
  });
});

describe('学情分析：新建施测 → 生成报告（闭环补齐 2026-10-13）', () => {
  it('「新建施测」：已确认原卷 + 班级 → 创建成功选中新施测并给出下一步指引', async () => {
    const createAssessment = vi.fn(async () => CLOSED_LOOP.created);
    // 创建后刷新列表：新施测出现在「试卷」下拉里（这是「导入的试卷看不到」的修复点）
    const listAssessments = vi.fn(async () =>
      page([
        {
          assessmentId: 'asm-1',
          paperId: 'paper-1',
          paperRevisionId: 'paper-1',
          paperTitle: '第一次月考原卷',
          title: '第一次月考',
          heldOn: '2026-09-30',
          revision: 3,
          participantCount: 1,
          classIds: ['class-a'],
        },
        CLOSED_LOOP.created.assessment,
      ]),
    );
    installApi({ createAssessment, listAssessments });
    render(<LearningAnalysisWorkspace />);

    fireEvent.click(await screen.findByTestId('la-create-assessment-open'));
    expect(await screen.findByTestId('la-create-assessment')).toBeInTheDocument();
    // 草稿卷不进候选（后端 422，界面不提前放行）
    await waitFor(() =>
      expect(screen.getByLabelText('新建施测原卷')).toHaveValue('paper-1'),
    );
    expect(screen.queryByRole('option', { name: /草稿卷/ })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('新建施测班级'), { target: { value: 'class-a' } });
    await screen.findByTestId('la-create-participant-count');
    fireEvent.click(screen.getByTestId('la-create-submit'));

    await waitFor(() => expect(createAssessment).toHaveBeenCalledTimes(1));
    // 创建成功后：面板关闭、新施测被选中、列表重新读取、并给出「下一步导入小题分」的指引
    await waitFor(() => expect(screen.queryByTestId('la-create-assessment')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByLabelText('试卷筛选')).toHaveValue('asm-9'));
    const notice = await screen.findByTestId('la-flow-notice');
    expect(notice).toHaveTextContent('已新建施测「第一次月考」');
    expect(notice).toHaveTextContent('参测 1 人次');
    expect(notice).toHaveTextContent('导入小题分');
    expect(listAssessments.mock.calls.length).toBeGreaterThan(1);
  });

  it('「生成学情报告」：未选施测时禁用；选中后生成按回执如实提示（复用不重复建）', async () => {
    const createAnalysisRun = vi.fn(
      async (
        assessmentId: string,
        body: { scoreRevisionId: string; selectedParticipantIds: string[]; ruleCode: string },
      ) => ({
        ...CLOSED_LOOP.runReceipt,
        // 回执按请求回显：runId 带上施测与成绩版本，便于断言「选中的是本次生成的报告」
        runId: `run-${assessmentId}-${body.scoreRevisionId}`,
        scoreRevisionId: body.scoreRevisionId,
        reused: true,
      }),
    );
    installApi({ createAnalysisRun });
    render(<LearningAnalysisWorkspace initialAssessmentId="asm-1" />);
    await screen.findByTestId('la-trend-card');

    fireEvent.click(screen.getByTestId('la-create-run-open'));
    const panel = await screen.findByTestId('la-create-run-panel');
    await waitFor(() =>
      expect(within(panel).getByLabelText('生成报告的成绩修订')).toHaveValue('rev-1'),
    );
    expect(within(panel).getByTestId('la-create-run-participant-count')).toHaveTextContent(
      '将对该版本的 1 个人次生成',
    );

    fireEvent.click(screen.getByTestId('la-create-run-submit'));
    await waitFor(() => expect(createAnalysisRun).toHaveBeenCalledTimes(1));
    const [assessmentId, body] = createAnalysisRun.mock.calls[0];
    expect(assessmentId).toBe('asm-1');
    expect(body.scoreRevisionId).toBe('rev-1');
    expect(body.selectedParticipantIds).toEqual(['p1']);
    expect(body.ruleCode).toBe('any_loss_v1');

    // 复用回执：如实用「直接复用」表述，不谎称新建；新报告被选中读取
    const notice = await screen.findByTestId('la-flow-notice');
    expect(notice).toHaveTextContent('直接复用');
    expect(notice).toHaveTextContent('未重复创建');
    await waitFor(() => expect(screen.queryByTestId('la-create-run-panel')).not.toBeInTheDocument());
    await waitFor(() =>
      expect(mocks.api.getAnalysisRun).toHaveBeenCalledWith('run-asm-1-rev-1', expect.anything()),
    );
  });

  it('未选择施测时「生成学情报告」禁用（报告必须挂在明确的施测上）', async () => {
    const api = installApi();
    render(<LearningAnalysisWorkspace />);
    const button = await screen.findByTestId('la-create-run-open');
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(screen.queryByTestId('la-create-run-panel')).not.toBeInTheDocument();
    expect(api.createAnalysisRun).not.toHaveBeenCalled();
  });
});
