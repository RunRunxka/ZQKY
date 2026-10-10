import { describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach } from 'vitest';
import { LoopConveyor } from './LoopConveyor';
import { normalizeFocusStations } from './use-loop-progress';
import {
  deriveLoopProgress,
  type LoopProgressServices,
  type LoopSnapshot,
  type LoopStationId,
} from '@/services/loop-progress';
import type { AssessmentView } from '@/contracts/assessments';
import type { AnalysisRunView, PracticeRevisionView, PracticeSetView } from '@/contracts/b4';
import type { LessonSummary } from '@/contracts/lesson-plans';
import type { PaperView } from '@/contracts/papers';
import type { ScoreRevisionView } from '@/contracts/scores';

/* ------------------------------------------------------------------ 固定数据（只造读接口返回的字段） */

const SUBJECT = 'sub-math';

function paper(overrides: Partial<PaperView> = {}): PaperView {
  return {
    paperId: 'pap-1', subjectId: SUBJECT, title: '函数与导数单元测', status: 'active', revision: 5,
    currentRevisionId: 'pr-3', currentState: 'confirmed', version: 3, totalScoreUnits: 6000,
    totalScore: '60', itemCount: 12, scoredLeafCount: 10, blockingIssueCount: 0,
    createdAt: '2026-10-01T00:00:00Z', ...overrides,
  };
}

function assessment(overrides: Partial<AssessmentView> = {}): AssessmentView {
  return {
    assessmentId: 'asm-1', paperRevisionId: 'pr-3', paperId: 'pap-1', paperTitle: '函数与导数单元测',
    subjectId: SUBJECT, title: '函数与导数单元测 · 第 1 次', assessmentType: 'exam', heldOn: '2026-10-09',
    activeScoreRevisionId: 'sr-2', state: 'open', revision: 4, classIds: ['cls-1'], participantCount: 34,
    createdAt: '2026-10-09T01:00:00Z', ...overrides,
  };
}

function scoreRevision(overrides: Partial<ScoreRevisionView> = {}): ScoreRevisionView {
  return { revisionId: 'sr-2', assessmentId: 'asm-1', version: 2, state: 'confirmed', createdAt: '2026-10-09T02:00:00Z', ...overrides };
}

function analysisRun(overrides: Partial<AnalysisRunView> = {}): AnalysisRunView {
  const base = {
    participantId: 'pt-1', studentNo: '01', name: '甲', className: '高二(3)班',
    classNameNote: '该成绩未记录班名' as const, attemptNo: 1, attendance: 'present' as const,
  };
  return {
    runId: 'run-1', assessmentId: 'asm-1', subjectId: SUBJECT, scoreRevisionId: 'sr-2', paperRevisionId: 'pr-3',
    paperTitle: '函数与导数单元测', inputHash: 'hash', ruleCode: 'any_loss_v1',
    selectionSnapshot: { selectedParticipantIds: [], uniqueStudentCount: 34, participantCount: 34, leafCount: 10, stateCounts: { recorded: 300, missing: 0, absent: 0, exempt: 0 } },
    participants: [
      { ...base, studentId: 'stu-1', classId: 'cls-1' },
      { ...base, participantId: 'pt-2', studentId: 'stu-2', classId: 'cls-2' },
      { ...base, participantId: 'pt-3', studentId: 'stu-3', classId: 'cls-3' },
    ],
    knowledgePoints: [],
    job: { jobId: 'job-1', domain: 'teaching', kind: 'analysis', attempt: 1, state: 'succeeded', result: null, error: null },
    reportReady: true, createdAt: '2026-10-09T03:00:00Z', ...overrides,
  };
}

function practiceRevision(overrides: Partial<PracticeRevisionView> = {}): PracticeRevisionView {
  return {
    practiceSetId: 'ps-1', practiceRevisionId: 'prv-1', version: 1, state: 'reviewed', title: '导数的几何意义',
    subjectId: SUBJECT, analysisRunId: 'run-1', targetKnowledgePoints: [], constraints: { count: 5 },
    inputHash: 'hash', totalScoreUnits: 100, draftItems: [], items: [], reviewedAt: '2026-10-09T04:00:00Z',
    createdAt: '2026-10-09T04:00:00Z', ...overrides,
  };
}

function practiceSet(overrides: Partial<PracticeSetView> = {}, revisionOverrides: Partial<PracticeRevisionView> = {}): PracticeSetView {
  const revision = practiceRevision(revisionOverrides);
  return {
    practiceSetId: 'ps-1', title: '导数的几何意义', subjectId: SUBJECT, analysisRunId: 'run-1', status: 'active',
    revision: 2, currentRevision: revision, revisions: [revision], replayed: false, ...overrides,
  };
}

function lessonSummary(overrides: Partial<LessonSummary> = {}): LessonSummary {
  return {
    lessonPlanId: 'lp-1', subjectId: SUBJECT, classId: 'cls-1', revision: 4, currentRevisionId: 'lr-4',
    title: '函数单调性', source: 'ai_applied', analysisRunId: 'run-1', updatedAt: '2026-10-09T05:00:00Z', ...overrides,
  };
}

/** 空快照：五个来源都读成功但都没有产出物。 */
function emptyServices(overrides: Partial<LoopProgressServices> = {}): LoopProgressServices {
  return {
    listPapers: async () => ({ items: [], total: 0, offset: 0, limit: 100 }),
    listAssessments: async () => ({ items: [], total: 0, offset: 0, limit: 100 }),
    listScoreRevisions: async () => ({ items: [], total: 0 }),
    listAnalysisRuns: async () => ({ items: [], total: 0, offset: 0, limit: 100 }),
    listPractices: async () => ({ items: [], total: 0, offset: 0, limit: 100 }),
    listLessons: async () => ({ items: [], total: 0, offset: 0, limit: 100 }),
    ...overrides,
  };
}

function snapshot(overrides: Partial<LoopSnapshot> = {}): LoopSnapshot {
  return {
    papers: [], assessments: [], runs: [], practices: [], lessons: [],
    scoreVersions: {}, scoreLinkId: null, refluxLinkId: null, subjectId: null, ...overrides,
  };
}

afterEach(cleanup);

/* ------------------------------------------------------------------ 派生（纯函数） */

describe('闭环传递带派生', () => {
  it('六工位按顺序派生三态：已完成带真实产出物，下一站可开始，后面是缺前置', () => {
    const { stations } = deriveLoopProgress(snapshot({
      papers: [paper()],
      assessments: [assessment()],
      runs: [],
      practices: [],
      lessons: [],
      scoreVersions: { 'asm-1': 2 },
    }));
    expect(stations.map((station) => station.id)).toEqual(['paper', 'score', 'report', 'practice', 'reflux', 'lesson']);
    expect(stations.map((station) => station.state)).toEqual(['done', 'done', 'ready', 'blocked', 'blocked', 'blocked']);
    expect(stations[0].artifact).toBe('v3 已确认');
    expect(stations[1].artifact).toBe('v2 · 34 人次');
    expect(stations[2].artifact).toBe('可开始');
    expect(stations[3].artifact).toBe('缺前置');
    expect(stations[3].reason).toBe('缺「学情报告」');
  });

  it('成绩版本读不到时只说人次，不伪造 v 号', () => {
    const { stations } = deriveLoopProgress(snapshot({
      papers: [paper()],
      assessments: [assessment()],
      scoreVersions: {},
    }));
    expect(stations[1].artifact).toBe('34 人次 · 已确认');
  });

  it('缺口断在没接上的那一段：第一个没有产出物的工位之后断开，之前是实线蓝', () => {
    const { stations } = deriveLoopProgress(snapshot({
      papers: [paper()],
      assessments: [assessment()],
      scoreVersions: { 'asm-1': 2 },
    }));
    expect(stations.map((station) => station.linkAfter)).toEqual(['locked', 'locked', 'broken', 'open', 'open', null]);
  });

  it('六站齐备＝整条带实线蓝，主按钮是「开始下一轮」', () => {
    const progress = deriveLoopProgress(snapshot({
      papers: [paper()],
      assessments: [assessment(), assessment({ assessmentId: 'asm-2', assessmentType: 'practice', activeScoreRevisionId: 'sr-9', title: '练习转换施测', createdAt: '2026-10-09T06:00:00Z' })],
      runs: [analysisRun()],
      practices: [practiceSet()],
      lessons: [lessonSummary()],
      scoreVersions: { 'asm-1': 2, 'asm-2': 1 },
    }));
    expect(progress.stations.every((station) => station.state === 'done')).toBe(true);
    expect(progress.stations.map((station) => station.linkAfter)).toEqual(['locked', 'locked', 'locked', 'locked', 'locked', null]);
    expect(progress.stations[4].artifact).toBe('新成绩 v1');
    expect(progress.stations[5].artifact).toBe('v4 · 已采用候选');
    expect(progress.action).toMatchObject({ kind: 'closed', title: '本轮闭环已完成', label: '开始下一轮' });
  });

  it('来源读取失败＝未知，不判缺失也不假装完成；产出物仍在的工位照常显示已完成', () => {
    const { stations, action } = deriveLoopProgress(snapshot({
      papers: null,
      assessments: [assessment()],
      scoreVersions: { 'asm-1': 2 },
    }));
    expect(stations[0]).toMatchObject({ state: 'unknown', artifact: '未知', reason: '读取失败，无法确认是否已产出' });
    expect(stations[1]).toMatchObject({ state: 'done', artifact: 'v2 · 34 人次' });
    expect(stations[2].state).toBe('ready');
    expect(stations[3].state).toBe('blocked');
    expect(stations.map((station) => station.linkAfter)).toEqual(['open', 'locked', 'broken', 'open', 'open', null]);
    expect(action).toMatchObject({ kind: 'unknown', title: '未知「原卷」', label: '重新读取', href: null });
  });

  it('真实数据不线性时只在真接不上的那一段断口，不误报整条带断裂', () => {
    // 成绩缺失（可开始），但报告/练习早已产出（上一轮或历史数据）：断口落在「针对练习 → 回流对比」
    const { stations } = deriveLoopProgress(snapshot({
      papers: [paper()],
      assessments: [assessment({ activeScoreRevisionId: null })],
      runs: [analysisRun()],
      practices: [practiceSet()],
      scoreVersions: {},
    }));
    expect(stations.map((station) => station.state)).toEqual(['done', 'ready', 'done', 'done', 'ready', 'blocked']);
    expect(stations.map((station) => station.linkAfter)).toEqual(['locked', 'open', 'locked', 'locked', 'broken', null]);
  });

  it('有学科上下文时其他学科的原卷不算已完成', () => {
    const { stations } = deriveLoopProgress(snapshot({ papers: [paper({ subjectId: 'sub-physics' })], subjectId: SUBJECT }));
    expect(stations[0].state).toBe('ready');
    expect(stations[0].artifact).toBe('可开始');
  });

  it('归档原卷不算已产出，只有在用原卷才算完成（真机复走发现）', () => {
    const archivedOnly = deriveLoopProgress(snapshot({ papers: [paper({ status: 'archived', currentState: 'confirmed', version: 9 })] }));
    expect(archivedOnly.stations[0].state).toBe('ready');
    expect(archivedOnly.stations[0].artifact).toBe('可开始');

    const mixed = deriveLoopProgress(snapshot({ papers: [paper({ status: 'archived', currentState: 'confirmed', version: 9 }), paper({ version: 2 })] }));
    expect(mixed.stations[0].state).toBe('done');
    expect(mixed.stations[0].artifact).toBe('v2 已确认');
  });
});

/* ------------------------------------------------------------------ 组件（DOM 契约） */

describe('闭环传递带组件', () => {
  const mixed = () => emptyServices({
    listPapers: async () => ({ items: [paper()], total: 1, offset: 0, limit: 100 }),
    listAssessments: async () => ({ items: [assessment()], total: 1, offset: 0, limit: 100 }),
    listScoreRevisions: async () => ({ items: [scoreRevision()], total: 1 }),
  });

  it('渲染六个工位：已完成实心+产出物、可开始空心+「可开始」、缺前置虚线+「缺前置」与原因', async () => {
    render(<LoopConveyor services={mixed()} />);
    const belt = await screen.findByTestId('loop-belt');
    const slots = within(belt).getAllByTestId(/^loop-slot-/);
    expect(slots).toHaveLength(6);
    expect(slots.map((slot) => slot.getAttribute('data-station'))).toEqual(['paper', 'score', 'report', 'practice', 'reflux', 'lesson']);
    expect(slots[0]).toHaveAttribute('data-state', 'done');
    expect(screen.getByTestId('loop-artifact-paper')).toHaveTextContent('v3 已确认');
    expect(screen.getByTestId('loop-artifact-score')).toHaveTextContent('v2 · 34 人次');
    expect(slots[2]).toHaveAttribute('data-state', 'ready');
    expect(screen.getByTestId('loop-artifact-report')).toHaveTextContent('可开始');
    expect(slots[3]).toHaveAttribute('data-state', 'blocked');
    expect(screen.getByTestId('loop-artifact-practice')).toHaveTextContent('缺前置');
    expect(screen.getByTestId('loop-why-practice')).toHaveTextContent('缺「学情报告」');
    expect(screen.getByTestId('loop-why-reflux')).toHaveTextContent('缺「针对练习」');
  });

  it('缺口断线只断一段，并挂出「缺」标记；已流过的段是实线蓝', async () => {
    render(<LoopConveyor services={mixed()} />);
    await screen.findByTestId('loop-belt');
    expect(screen.getByTestId('loop-link-paper')).toHaveAttribute('data-tone', 'locked');
    expect(screen.getByTestId('loop-link-score')).toHaveAttribute('data-tone', 'locked');
    const broken = screen.getByTestId('loop-link-report');
    expect(broken).toHaveAttribute('data-tone', 'broken');
    expect(broken).toHaveAttribute('data-broken', 'true');
    expect(screen.getByTestId('loop-gap-badge-report')).toHaveTextContent('缺');
    expect(screen.getByTestId('loop-link-practice')).toHaveAttribute('data-tone', 'open');
    expect(screen.getByTestId('loop-link-reflux')).toHaveAttribute('data-tone', 'open');
    // 最后一个工位后面没有连接段
    expect(screen.queryByTestId('loop-link-lesson')).not.toBeInTheDocument();
  });

  it('全带只有一个主按钮，可推进时是「下一步 · 下一站」并导航到能产出的模块', async () => {
    const { container } = render(<LoopConveyor services={mixed()} />);
    await screen.findByTestId('loop-belt');
    expect(container.querySelectorAll('.loop-primary')).toHaveLength(1);
    const action = screen.getByTestId('loop-next');
    expect(within(action).getByTestId('loop-next-title')).toHaveTextContent('下一步 · 学情报告');
    expect(within(action).getByTestId('loop-next-note')).toHaveTextContent('成绩 v2 · 34 人次，可以开始');
    const primary = within(action).getByRole('link', { name: '去创建报告' });
    expect(primary).toHaveAttribute('href', '/learning-analysis');
  });

  it('缺前置与未知工位不跳转、只显示原因；已完成/可开始工位可跳到对应模块', async () => {
    const hostile = emptyServices({
      listPapers: async () => ({ items: [paper()], total: 1, offset: 0, limit: 100 }),
      listAssessments: async () => ({ items: [assessment()], total: 1, offset: 0, limit: 100 }),
      listScoreRevisions: async () => ({ items: [scoreRevision()], total: 1 }),
      listLessons: async () => { throw new Error('教案列表读取失败'); },
    });
    render(<LoopConveyor services={hostile} />);
    await screen.findByTestId('loop-belt');
    const slots = within(screen.getByTestId('loop-belt')).getAllByTestId(/^loop-slot-/);
    expect(within(slots[0]).getByRole('link', { name: /原卷/ })).toHaveAttribute('href', '/assessments');
    expect(within(slots[2]).getByRole('link', { name: /学情报告/ })).toHaveAttribute('href', '/learning-analysis');
    expect(within(slots[3]).queryByRole('link')).not.toBeInTheDocument();
    expect(within(slots[4]).queryByRole('link')).not.toBeInTheDocument();
    const blockedCard = within(slots[3]).getByText('针对练习').closest('.loop-card');
    expect(blockedCard).toHaveAttribute('title', expect.stringContaining('缺「学情报告」'));
    // 教案来源读取失败＝未知，不跳转、不假装完成
    expect(slots[5]).toHaveAttribute('data-state', 'unknown');
    expect(screen.getByTestId('loop-artifact-lesson')).toHaveTextContent('未知');
    expect(within(slots[5]).queryByRole('link')).not.toBeInTheDocument();
  });

  it('成绩未产出时深链到该施测的成绩步骤；没有施测就退回施测与成绩入口', async () => {
    const withAssessment = emptyServices({
      listPapers: async () => ({ items: [paper()], total: 1, offset: 0, limit: 100 }),
      listAssessments: async () => ({ items: [assessment({ activeScoreRevisionId: null })], total: 1, offset: 0, limit: 100 }),
    });
    const first = render(<LoopConveyor services={withAssessment} />);
    await waitFor(() => expect(screen.getByTestId('loop-next-title')).toHaveTextContent('下一步 · 成绩'));
    expect(screen.getByRole('link', { name: '去导入成绩' })).toHaveAttribute('href', '/assessments?assessmentId=asm-1&step=score');
    first.unmount();
    const without = emptyServices({
      listPapers: async () => ({ items: [paper()], total: 1, offset: 0, limit: 100 }),
    });
    render(<LoopConveyor services={without} />);
    await waitFor(() => expect(screen.getByRole('link', { name: '去导入成绩' })).toHaveAttribute('href', '/assessments'));
  });

  it('任一来源读取失败不影响整条带：该工位未知，其余照常渲染，主按钮就地重新读取', async () => {
    const flaky = vi.fn()
      .mockRejectedValueOnce(new Error('读取失败'))
      .mockResolvedValue({ items: [paper()], total: 1, offset: 0, limit: 100 });
    const services = emptyServices({
      listPapers: flaky,
      listAssessments: async () => ({ items: [assessment()], total: 1, offset: 0, limit: 100 }),
      listScoreRevisions: async () => ({ items: [scoreRevision()], total: 1 }),
    });
    render(<LoopConveyor services={services} />);
    await waitFor(() => expect(screen.getByTestId('loop-slot-paper')).toHaveAttribute('data-state', 'unknown'));
    expect(screen.getByTestId('loop-slot-score')).toHaveAttribute('data-state', 'done');
    expect(screen.getByTestId('loop-artifact-paper')).toHaveTextContent('未知');
    expect(screen.getByTestId('loop-next-title')).toHaveTextContent('未知「原卷」');
    const retry = screen.getByRole('button', { name: '重新读取' });
    expect(screen.getByTestId('loop-conveyor').querySelectorAll('.loop-primary')).toHaveLength(1);
    fireEvent.click(retry);
    await waitFor(() => expect(screen.getByTestId('loop-slot-paper')).toHaveAttribute('data-state', 'done'));
    expect(screen.getByTestId('loop-artifact-paper')).toHaveTextContent('v3 已确认');
  });

  it('首次读取显示「读取中…」，不给任何结论也不假装完成', async () => {
    render(<LoopConveyor services={emptyServices()} />);
    const conveyor = screen.getByTestId('loop-conveyor');
    expect(conveyor).toHaveAttribute('data-loading', 'true');
    expect(screen.getAllByText('读取中…')).toHaveLength(6);
    expect(screen.getByRole('button', { name: '正在读取…' })).toBeDisabled();
    await waitFor(() => expect(screen.getByTestId('loop-conveyor')).toHaveAttribute('data-loading', 'false'));
  });

  it('空数据也从原卷开始：可开始＝空心工位＋「可开始」，主按钮指向原卷模块', async () => {
    render(<LoopConveyor services={emptyServices()} />);
    await waitFor(() => expect(screen.getByTestId('loop-slot-paper')).toHaveAttribute('data-state', 'ready'));
    expect(screen.getByTestId('loop-artifact-paper')).toHaveTextContent('可开始');
    expect(screen.getByTestId('loop-next-title')).toHaveTextContent('下一步 · 原卷');
    expect(screen.getByRole('link', { name: '去确认原卷' })).toHaveAttribute('href', '/assessments');
    expect(screen.getByTestId('loop-slot-score')).toHaveAttribute('data-state', 'blocked');
  });

  it('读取被取消（卸载）后迟到的结果不写状态、不报错', async () => {
    let release = () => {};
    const pending = new Promise<void>((resolve) => { release = resolve; });
    const slow = emptyServices({
      listPapers: () => pending.then(() => ({ items: [paper()], total: 1, offset: 0, limit: 100 })),
    });
    const view = render(<LoopConveyor services={slow} />);
    view.unmount();
    release();
    await waitFor(() => expect(screen.queryByTestId('loop-conveyor')).not.toBeInTheDocument());
  });
});

/* ------------------------------------------------------------------ 本页工位（focusStation） */

describe('闭环传递带·本页工位', () => {
  /** 原卷、成绩已完成，报告尚未产出：本页视角最典型的「更早的缺口」。 */
  const papersAndScores = () => emptyServices({
    listPapers: async () => ({ items: [paper()], total: 1, offset: 0, limit: 100 }),
    listAssessments: async () => ({ items: [assessment()], total: 1, offset: 0, limit: 100 }),
    listScoreRevisions: async () => ({ items: [scoreRevision()], total: 1 }),
  });

  /** 原卷、成绩、报告都已完成，练习尚未产出。 */
  const upToReport = () => emptyServices({
    listPapers: async () => ({ items: [paper()], total: 1, offset: 0, limit: 100 }),
    listAssessments: async () => ({ items: [assessment()], total: 1, offset: 0, limit: 100 }),
    listScoreRevisions: async () => ({ items: [scoreRevision()], total: 1 }),
    listAnalysisRuns: async () => ({ items: [analysisRun()], total: 1, offset: 0, limit: 100 }),
  });

  it('本页工位归一化：单个与一组都收、去重、缺省为空', () => {
    expect(normalizeFocusStations('report')).toEqual(['report']);
    expect(normalizeFocusStations(['score', 'score', 'paper'])).toEqual(['score', 'paper']);
    expect(normalizeFocusStations(null)).toEqual([]);
    expect(normalizeFocusStations(undefined)).toEqual([]);
  });

  it('不传本页工位：没有工位高亮、没有 aria-current，主按钮与既有行为一致', async () => {
    render(<LoopConveyor services={papersAndScores()} />);
    await screen.findByTestId('loop-belt');
    const slots = within(screen.getByTestId('loop-belt')).getAllByTestId(/^loop-slot-/);
    expect(slots.every((slot) => slot.getAttribute('data-focus') === 'false')).toBe(true);
    expect(slots.some((slot) => slot.hasAttribute('aria-current'))).toBe(false);
    expect(screen.queryAllByTestId(/^loop-focus-tag-/)).toHaveLength(0);
    expect(screen.getByTestId('loop-next-title')).toHaveTextContent('下一步 · 学情报告');
  });

  it('本页工位加 data-focus 与 aria-current="step" 与「本页」小标，其余工位不受影响', async () => {
    const single = render(<LoopConveyor services={papersAndScores()} focusStation="score" />);
    await screen.findByTestId('loop-belt');
    expect(screen.getByTestId('loop-slot-score')).toHaveAttribute('data-focus', 'true');
    expect(screen.getByTestId('loop-slot-score')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByTestId('loop-focus-tag-score')).toHaveTextContent('本页');
    // 本页身份不只在颜色/小标上：tooltip（无障碍名）也说明「本页工位」
    expect(within(screen.getByTestId('loop-slot-score')).getByRole('link')).toHaveAttribute('title', expect.stringContaining('本页工位 · 成绩：'));
    expect(within(screen.getByTestId('loop-slot-paper')).getByRole('link')).toHaveAttribute('title', expect.not.stringContaining('本页工位'));
    expect(screen.getByTestId('loop-slot-paper')).toHaveAttribute('data-focus', 'false');
    expect(screen.getByTestId('loop-slot-paper')).not.toHaveAttribute('aria-current');
    single.unmount();
    render(<LoopConveyor services={papersAndScores()} focusStation={['paper', 'score']} />);
    await screen.findByTestId('loop-belt');
    expect(screen.getByTestId('loop-slot-paper')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByTestId('loop-slot-score')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByTestId('loop-focus-tag-paper')).toHaveTextContent('本页');
    expect(within(screen.getByTestId('loop-slot-report')).queryByTestId(/^loop-focus-tag-/)).not.toBeInTheDocument();
  });

  it('本页工位缺前置：主按钮改为「缺「缺口工位」：一句话」＋「去补齐」，链接到能补齐该缺口的模块', async () => {
    render(<LoopConveyor services={papersAndScores()} focusStation="practice" />);
    await screen.findByTestId('loop-belt');
    expect(screen.getByTestId('loop-slot-practice')).toHaveAttribute('data-state', 'blocked');
    expect(screen.getByTestId('loop-next')).toHaveAttribute('data-kind', 'blocked');
    expect(screen.getByTestId('loop-next-title')).toHaveTextContent('缺「学情报告」：没有已准备完成的学情报告');
    expect(screen.getByTestId('loop-next-note')).toHaveTextContent('补齐后本页「针对练习」才能继续');
    expect(screen.getByRole('link', { name: '去补齐' })).toHaveAttribute('href', '/learning-analysis');
  });

  it('本页工位自己可开始（缺口就是本页工位）时维持「下一步 · X」，不改成缺口文案', async () => {
    render(<LoopConveyor services={upToReport()} focusStation="practice" />);
    await waitFor(() => expect(screen.getByTestId('loop-slot-practice')).toHaveAttribute('data-state', 'ready'));
    expect(screen.getByTestId('loop-next-title')).toHaveTextContent('下一步 · 针对练习');
    expect(screen.getByRole('link', { name: '去审核练习' })).toHaveAttribute('href', '/practices');
  });

  it('成绩页视角（原卷＋成绩都算本页可达）：本页工位可开始时维持「下一步 · X」', async () => {
    render(<LoopConveyor services={emptyServices()} focusStation={['paper', 'score']} />);
    await waitFor(() => expect(screen.getByTestId('loop-slot-paper')).toHaveAttribute('data-state', 'ready'));
    expect(screen.getByTestId('loop-slot-score')).toHaveAttribute('data-focus', 'true');
    expect(screen.getByTestId('loop-next-title')).toHaveTextContent('下一步 · 原卷');
    expect(screen.getByRole('link', { name: '去确认原卷' })).toHaveAttribute('href', '/assessments');
  });

  it('本页工位已完成、缺口在下游时维持「下一步 · X」', async () => {
    render(<LoopConveyor services={upToReport()} focusStation="report" />);
    await waitFor(() => expect(screen.getByTestId('loop-slot-report')).toHaveAttribute('data-state', 'done'));
    expect(screen.getByTestId('loop-next-title')).toHaveTextContent('下一步 · 针对练习');
    expect(screen.getByRole('link', { name: '去审核练习' })).toHaveAttribute('href', '/practices');
  });

  it('读取失败不当缺口：本页视角下仍就地「重新读取」，工位仍标本页', async () => {
    const unreadable = emptyServices({
      listPapers: async () => { throw new Error('原卷列表读取失败'); },
      listAssessments: async () => ({ items: [assessment()], total: 1, offset: 0, limit: 100 }),
      listScoreRevisions: async () => ({ items: [scoreRevision()], total: 1 }),
    });
    render(<LoopConveyor services={unreadable} focusStation="practice" />);
    await waitFor(() => expect(screen.getByTestId('loop-slot-paper')).toHaveAttribute('data-state', 'unknown'));
    expect(screen.getByTestId('loop-next-title')).toHaveTextContent('未知「原卷」');
    expect(screen.getByRole('button', { name: '重新读取' })).toBeInTheDocument();
    expect(screen.getByTestId('loop-slot-practice')).toHaveAttribute('aria-current', 'step');
  });

  it('本页工位到缺口之间有一段读取失败时不断言「缺」：保留既有主按钮，失败仍留在带子上', async () => {
    const partiallyRead = emptyServices({
      listAssessments: async () => { throw new Error('施测列表读取失败'); },
    });
    render(<LoopConveyor services={partiallyRead} focusStation="report" />);
    await waitFor(() => expect(screen.getByTestId('loop-slot-score')).toHaveAttribute('data-state', 'unknown'));
    expect(screen.getByTestId('loop-slot-report')).toHaveAttribute('data-state', 'blocked');
    expect(screen.getByTestId('loop-artifact-score')).toHaveTextContent('未知');
    expect(screen.getByTestId('loop-next-title')).toHaveTextContent('下一步 · 原卷');
    expect(screen.getByRole('link', { name: '去确认原卷' })).toHaveAttribute('href', '/assessments');
  });

  it('未知的工位 id 不猜：没有高亮，主按钮维持既有行为', async () => {
    render(<LoopConveyor services={papersAndScores()} focusStation={'nope' as LoopStationId} />);
    await screen.findByTestId('loop-belt');
    expect(screen.queryAllByTestId(/^loop-focus-tag-/)).toHaveLength(0);
    expect(screen.getByTestId('loop-conveyor').querySelectorAll('[data-focus="true"]')).toHaveLength(0);
    expect(screen.getByTestId('loop-next-title')).toHaveTextContent('下一步 · 学情报告');
  });
});
