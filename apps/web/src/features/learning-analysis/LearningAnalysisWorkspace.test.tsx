/**
 * 学情分析工作区（R6-FE）：五图各自的数据源与错误隔离、顶部筛选（班级/试卷/时间粒度）、
 * 报告读取失败不当空目录、未就绪报告不读图表、小题分导入面板入口。
 *
 * 与归档测试的差异（本卡裁定，已在交付说明报告）：
 * - 趋势图由折线改为红色柱状图：这里用 Chart.js 替身捕获真实传给 `new Chart()` 的配置，
 *   直接断言图型、数据与颜色口径（jsdom 无 Canvas 2D context，替身也避免依赖真实画布）；
 * - 归档的创建报告 / 归档 / 彻底删除 / 教师备注页签不在本卡交付范围，测试不覆盖。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
    generateAnalysisCommentary: vi.fn(async () => '候选评价'),
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

function labelsOf(config: Record<string, unknown> | undefined) {
  return (config?.data as { labels: unknown[] })?.labels;
}

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
    expect(datasetOf(trend)?.backgroundColor).toBe(DANGER);
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
    expect(datasetOf(ranking)?.backgroundColor).toEqual([WEAK_BROWN, '#2563eb']);

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
