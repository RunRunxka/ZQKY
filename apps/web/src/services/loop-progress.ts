/**
 * 教学闭环「传递带」的只读派生（F2-LOOP · 方向 02 闭环传递带）。
 *
 * 六工位＝原卷 → 成绩 → 学情报告 → 针对练习 → 回流对比 → 教案调整。状态只来自现有前端
 * 服务（FastAPI 读接口）：**不新增后端/契约、不引入定时器、不伪造入库**。每个来源独立成败，
 * 任一读取失败只让对应工位显示「未知」，整条带照常渲染；读取成功但确实没有产出物时，
 * 前置满足显示「可开始」，前置未产出显示「缺前置」。
 *
 * 生产口径（读得到什么就说什么，不做猜测）：
 * - 原卷：存在已确认修订（`currentState === 'confirmed'`）；
 * - 成绩：施测存在当前生效成绩修订（`activeScoreRevisionId`）；版本号另读一次修订列表，
 *   读不到版本时只显示人次，不伪造 v 号；
 * - 学情报告：报告 `reportReady` 且未归档，「N 班」按冻结人次里的班级数；
 * - 针对练习：练习集当前修订 `reviewed`；
 * - 回流对比：**练习类施测**（`assessmentType === 'practice'`，即由练习转换建立）已有生效成绩修订。
 *   前端可见字段里没有 `practice_conversions` 关联，这条按「类型 + 生效成绩」判定，
 *   口径写在工位 title 里，不宣称比这更精确；
 * - 教案调整：后台教案来源为 `ai_applied`（已采用 AI 候选）或 `manual`（人工编辑）。
 */

import type { AssessmentView } from '@/contracts/assessments';
import type { AnalysisRunView, PracticeSetView } from '@/contracts/b4';
import type { LessonSummary } from '@/contracts/lesson-plans';
import type { PaperView } from '@/contracts/papers';
import { listAssessments, listPapers, listScoreRevisions } from '@/services/assessments-api';
import { listLessons } from '@/services/lesson-plans-api';
import { b4Api } from '@/services/teaching-loop-b4-api';

/** 每个来源只取一页；六工位只关心「有没有产出物」，不做全量统计。 */
const LIST_LIMIT = 100;

export type LoopStationId = 'paper' | 'score' | 'report' | 'practice' | 'reflux' | 'lesson';
/** 三态 + 未知：`unknown` 只用于该来源读取失败，不代表「没有产出物」。 */
export type LoopStationState = 'done' | 'ready' | 'blocked' | 'unknown';
/** 渲染期多一个 `pending`（首次读取中），避免把「还没读到」显示成任何结论。 */
export type LoopStationPhase = LoopStationState | 'pending';
export type LoopLinkTone = 'locked' | 'open' | 'broken' | 'unknown';

export interface LoopStationView {
  id: LoopStationId;
  name: string;
  state: LoopStationPhase;
  /** 卡面第二行：done=真实版本与规模；ready=「可开始」；blocked=「缺前置」；unknown=「未知」。 */
  artifact: string;
  /** 该工位可点击时的跳转目标；主按钮也用同一目标。 */
  href: string;
  /** 产出/补齐的动作文案（`去…`），用于主按钮。 */
  action: string;
  /** 缺口/未知工位的一行原因；已完成与可开始工位为 null。 */
  reason: string | null;
  /** 工位右侧连接线段：`null` 只在最后一个工位。 */
  linkAfter: LoopLinkTone | null;
  /** hover 说明（口径、身份或失败原因），不隐藏任何结论。 */
  title: string;
}

export interface LoopActionView {
  kind: 'pending' | 'next' | 'blocked' | 'closed' | 'unknown';
  title: string;
  note: string;
  label: string;
  /** 有 href＝导航到能产出/补齐的模块；没有 href（读取中 / 重新读取）＝就地按钮。 */
  href: string | null;
}

export interface LoopProgress {
  stations: LoopStationView[];
  action: LoopActionView;
}

/** 原始读取结果：`null` 表示该来源读取失败（不是「空数据」）。 */
export interface LoopSnapshot {
  papers: PaperView[] | null;
  assessments: AssessmentView[] | null;
  runs: AnalysisRunView[] | null;
  practices: PracticeSetView[] | null;
  lessons: LessonSummary[] | null;
  /** 成绩工位选中施测的当前生效成绩版本号（尽力而为，读不到就不显示 v）。 */
  scoreVersions: Record<string, number>;
  /** 成绩未产出时，深链到「施测与成绩」的施测 id（有就带上，没有就不猜）。 */
  scoreLinkId: string | null;
  /** 回流对比未产出时，深链到练习派生施测的 id。 */
  refluxLinkId: string | null;
  /** 有学科上下文的页面传入的学科 id；原卷/练习/报告按它过滤（施测与教案由接口过滤）。 */
  subjectId: string | null;
}

export interface LoopProgressServices {
  listPapers: typeof listPapers;
  listAssessments: typeof listAssessments;
  listScoreRevisions: typeof listScoreRevisions;
  listAnalysisRuns: typeof b4Api.listAnalysisRuns;
  listPractices: typeof b4Api.listPractices;
  listLessons: typeof listLessons;
}

/**
 * 真实服务装配。每个读接口延迟到**调用时**解析：模块被部分替身注入（单测里的
 * `vi.mock` 只给部分导出）时，导入阶段不会因为一个缺失导出把整页带崩，
 * 缺失的接口只让对应工位降级为「未知」。
 */
export const loopProgressServices: LoopProgressServices = {
  listPapers: (query, signal) => listPapers(query, signal),
  listAssessments: (query, signal) => listAssessments(query, signal),
  listScoreRevisions: (assessmentId, signal) => listScoreRevisions(assessmentId, signal),
  listAnalysisRuns: (query, signal) => b4Api.listAnalysisRuns(query, signal),
  listPractices: (query, signal) => b4Api.listPractices(query, signal),
  listLessons: (query, signal) => listLessons(query, signal),
};

interface LoopStationSpec {
  id: LoopStationId;
  name: string;
  /** 产出物未产生时，为什么还不能开始（也是主按钮文案里的那句话）。 */
  gapReason: string;
  /** 去产出 / 去补齐的动作文案。 */
  action: string;
}

const STATION_SPECS: readonly LoopStationSpec[] = [
  { id: 'paper', name: '原卷', gapReason: '还没有已确认的原卷修订', action: '去确认原卷' },
  { id: 'score', name: '成绩', gapReason: '没有已确认的成绩修订', action: '去导入成绩' },
  { id: 'report', name: '学情报告', gapReason: '没有已准备完成的学情报告', action: '去创建报告' },
  { id: 'practice', name: '针对练习', gapReason: '没有已审核的练习修订', action: '去审核练习' },
  { id: 'reflux', name: '回流对比', gapReason: '练习派生的施测还没有确认成绩', action: '去导入新成绩' },
  { id: 'lesson', name: '教案调整', gapReason: '还没有已采用候选或人工编辑的后台教案', action: '去生成候选' },
];

const ASSESSMENTS_ROUTE = '/assessments';

/** 深链到某一施测的成绩步骤；没有施测 id 时退回页面入口，不猜 id。 */
function scoreRoute(assessmentId: string | null): string {
  return assessmentId ? `${ASSESSMENTS_ROUTE}?assessmentId=${encodeURIComponent(assessmentId)}&step=score` : ASSESSMENTS_ROUTE;
}

interface StationFact {
  /** 该来源是否读成功（false → 工位显示「未知」）。 */
  readable: boolean;
  done: boolean;
  artifact: string | null;
  /** 事实来源说明（title 的一部分）。 */
  basis: string;
}

function matchesSubject(value: string, subjectId: string | null): boolean {
  return !subjectId || value === subjectId;
}

/** 取最近一条（按给定时间戳倒序；时间缺失时保持接口顺序），不按标题/最近访问猜测。 */
function newest<T>(items: readonly T[], stamp: (item: T) => string | null | undefined): T | undefined {
  return items.reduce<T | undefined>(
    (best, item) => (!best || (stamp(item) ?? '') > (stamp(best) ?? '') ? item : best),
    undefined,
  );
}

function paperFact(snapshot: LoopSnapshot, subjectId: string | null): StationFact {
  const papers = snapshot.papers;
  if (!papers) return { readable: false, done: false, artifact: null, basis: '原卷列表读取失败' };
  const confirmed = papers.filter((paper) => paper.currentState === 'confirmed' && matchesSubject(paper.subjectId, subjectId));
  if (confirmed.length === 0) return { readable: true, done: false, artifact: null, basis: '没有已确认修订的原卷' };
  const latest = confirmed.reduce((best, paper) => (paper.version > best.version ? paper : best));
  return { readable: true, done: true, artifact: `v${latest.version} 已确认`, basis: '已确认原卷修订' };
}

function scoreFact(snapshot: LoopSnapshot, subjectId: string | null): StationFact {
  const assessments = snapshot.assessments;
  if (!assessments) return { readable: false, done: false, artifact: null, basis: '施测列表读取失败' };
  const withScore = assessments.filter((item) => item.state !== 'archived' && item.activeScoreRevisionId && matchesSubject(item.subjectId, subjectId));
  if (withScore.length === 0) return { readable: true, done: false, artifact: null, basis: '没有带生效成绩修订的施测' };
  const latest = newest(withScore, (item) => item.createdAt) as AssessmentView;
  const version = snapshot.scoreVersions[latest.assessmentId];
  return {
    readable: true,
    done: true,
    artifact: version ? `v${version} · ${latest.participantCount} 人次` : `${latest.participantCount} 人次 · 已确认`,
    basis: version ? '当前生效成绩修订' : '当前生效成绩修订（版本号未读到）',
  };
}

function reportFact(snapshot: LoopSnapshot, subjectId: string | null): StationFact {
  const runs = snapshot.runs;
  if (!runs) return { readable: false, done: false, artifact: null, basis: '学情报告列表读取失败' };
  const ready = runs.filter((run) => run.reportReady && !run.archivedAt && matchesSubject(run.subjectId, subjectId));
  if (ready.length === 0) return { readable: true, done: false, artifact: null, basis: '没有已准备完成的学情报告' };
  const latest = newest(ready, (item) => item.createdAt) as AnalysisRunView;
  const classes = new Set(latest.participants.map((participant) => participant.classId)).size;
  return { readable: true, done: true, artifact: classes > 0 ? `ready · ${classes} 班` : 'ready', basis: '固定学情报告已准备' };
}

function practiceFact(snapshot: LoopSnapshot, subjectId: string | null): StationFact {
  const practices = snapshot.practices;
  if (!practices) return { readable: false, done: false, artifact: null, basis: '练习列表读取失败' };
  const reviewed = practices.filter((item) => item.status !== 'archived' && item.currentRevision?.state === 'reviewed' && matchesSubject(item.subjectId, subjectId));
  if (reviewed.length === 0) return { readable: true, done: false, artifact: null, basis: '没有已审核的练习修订' };
  const latest = reviewed.reduce((best, item) => (item.currentRevision.version > best.currentRevision.version ? item : best));
  return { readable: true, done: true, artifact: `v${latest.currentRevision.version} 已审核`, basis: '练习修订已审核' };
}

/**
 * 回流对比＝练习派生的施测已有确认成绩修订。
 * 前端读接口看不到 `practice_conversions`，按「练习类施测 + 生效成绩修订」判定；
 * 这条判定口径在 title 里明说，不把近似当精确。
 */
function refluxFact(snapshot: LoopSnapshot, subjectId: string | null): StationFact {
  const assessments = snapshot.assessments;
  if (!assessments) return { readable: false, done: false, artifact: null, basis: '施测列表读取失败' };
  const derived = assessments.filter((item) => item.state !== 'archived' && item.assessmentType === 'practice' && matchesSubject(item.subjectId, subjectId));
  const withScore = derived.filter((item) => item.activeScoreRevisionId);
  if (withScore.length === 0) return { readable: true, done: false, artifact: null, basis: derived.length > 0 ? '练习派生的施测还没有生效成绩修订' : '还没有练习派生的施测' };
  const latest = newest(withScore, (item) => item.createdAt) as AssessmentView;
  const version = snapshot.scoreVersions[latest.assessmentId];
  return {
    readable: true,
    done: true,
    artifact: version ? `新成绩 v${version}` : '新成绩已确认',
    basis: '练习类施测的生效成绩修订（未读到转换映射，按类型判定）',
  };
}

function lessonFact(snapshot: LoopSnapshot, subjectId: string | null): StationFact {
  const lessons = snapshot.lessons;
  if (!lessons) return { readable: false, done: false, artifact: null, basis: '后台教案列表读取失败' };
  const adopted = lessons.filter((item) => (item.source === 'ai_applied' || item.source === 'manual') && matchesSubject(item.subjectId, subjectId));
  if (adopted.length === 0) return { readable: true, done: false, artifact: null, basis: '没有已采用候选或人工编辑的后台教案' };
  const latest = newest(adopted, (item) => item.updatedAt) as LessonSummary;
  return {
    readable: true,
    done: true,
    artifact: `v${latest.revision} · ${latest.source === 'ai_applied' ? '已采用候选' : '人工编辑'}`,
    basis: '后台教案已存在',
  };
}

/** 首次读取（还没有任何结果）时的占位：六工位都是「读取中」，不给任何结论。 */
export function pendingLoopProgress(): LoopProgress {
  return {
    stations: STATION_SPECS.map((spec, index) => ({
      id: spec.id,
      name: spec.name,
      state: 'pending',
      artifact: '读取中…',
      href: '',
      action: spec.action,
      reason: null,
      linkAfter: index === STATION_SPECS.length - 1 ? null : 'open',
      title: `${spec.name}：正在读取真实状态`,
    })),
    action: { kind: 'pending', title: '正在读取闭环状态', note: '原卷 / 成绩 / 学情报告 / 针对练习 / 回流对比 / 教案', label: '正在读取…', href: null },
  };
}

/**
 * 六工位状态派生（纯函数，单测直接喂快照）。
 *
 * 链上每个工位的前置就是前一个工位：产出物存在＝`done`；没有产出物且前置已完成＝`ready`（可开始）；
 * 前置没完成＝`blocked`（缺前置）；自身来源读取失败＝`unknown`（不假装完成，也不判缺失）。
 * 连接线段：缺什么就断在哪里——**进入第一个 `blocked` 工位的那一段**断开（虚线＋「缺」），
 * 进入第一个 `unknown` 工位的那一段是虚线待核，左侧已有产出物的一段是实线蓝，其余未到达段是细灰实线。
 * 真实数据不一定线性（例如成绩缺失但报告早已产出）：只在真的接不上时画断口，不误报整条带断裂。
 */
export function deriveLoopProgress(snapshot: LoopSnapshot | null): LoopProgress {
  if (!snapshot) return pendingLoopProgress();
  const subjectId = snapshot.subjectId;
  const facts: StationFact[] = [
    paperFact(snapshot, subjectId),
    scoreFact(snapshot, subjectId),
    reportFact(snapshot, subjectId),
    practiceFact(snapshot, subjectId),
    refluxFact(snapshot, subjectId),
    lessonFact(snapshot, subjectId),
  ];
  const states: LoopStationPhase[] = facts.map((fact, index) => {
    if (!fact.readable) return 'unknown';
    if (fact.done) return 'done';
    // 前置＝链上前一个工位：产出物不存在但前一站已完成＝可开始；前一站没完成＝缺前置。
    const previous = index > 0 ? facts[index - 1] : null;
    return previous === null || (previous.readable && previous.done) ? 'ready' : 'blocked';
  });
  const firstUndone = states.findIndex((state) => state !== 'done');
  const firstBlocked = states.findIndex((state) => state === 'blocked');
  const hrefs: Record<LoopStationId, string> = {
    paper: ASSESSMENTS_ROUTE,
    score: scoreRoute(snapshot.scoreLinkId),
    report: '/learning-analysis',
    practice: '/practices',
    reflux: scoreRoute(snapshot.refluxLinkId),
    lesson: '/lesson-plans',
  };
  const stations: LoopStationView[] = STATION_SPECS.map((spec, index) => {
    const state = states[index];
    const fact = facts[index];
    const previousName = index > 0 ? STATION_SPECS[index - 1].name : null;
    const artifact = state === 'done' ? fact.artifact ?? '已产出'
      : state === 'ready' ? '可开始'
        : state === 'blocked' ? '缺前置'
          : '未知';
    let reason: string | null = null;
    if (state === 'unknown') reason = '读取失败，无法确认是否已产出';
    else if (state === 'blocked' && previousName) reason = `缺「${previousName}」`;
    const linkAfter: LoopLinkTone | null = index === STATION_SPECS.length - 1 ? null
      : index === firstBlocked - 1 ? 'broken'
        : states[index + 1] === 'unknown' ? 'unknown'
          : state === 'done' ? 'locked' : 'open';
    const basis = state === 'done' ? `${artifact} · ${fact.basis}`
      : state === 'ready' ? `可开始 · ${spec.gapReason}`
        : state === 'blocked' ? `${reason} · ${spec.gapReason}`
          : state === 'unknown' ? `${reason}（${fact.basis}）`
            : '正在读取真实状态';
    return {
      id: spec.id,
      name: spec.name,
      state,
      artifact,
      href: hrefs[spec.id],
      action: spec.action,
      reason,
      linkAfter,
      title: `${spec.name}：${basis}`,
    };
  });
  return { stations, action: deriveAction(stations, firstUndone) };
}

function deriveAction(stations: LoopStationView[], firstUndone: number): LoopActionView {
  if (firstUndone === -1) {
    const reflux = stations[stations.length - 2];
    const lesson = stations[stations.length - 1];
    return {
      kind: 'closed',
      title: '本轮闭环已完成',
      note: `${reflux.name} ${reflux.artifact} · ${lesson.name} ${lesson.artifact}`,
      label: '开始下一轮',
      href: ASSESSMENTS_ROUTE,
    };
  }
  const first = stations[firstUndone];
  if (first.state === 'ready') {
    const previous = firstUndone > 0 ? stations[firstUndone - 1] : null;
    return {
      kind: 'next',
      title: `下一步 · ${first.name}`,
      note: previous ? `${previous.name} ${previous.artifact}，可以开始` : '从第一步开始',
      label: first.action,
      href: first.href,
    };
  }
  if (first.state === 'unknown') {
    return {
      kind: 'unknown',
      title: `未知「${first.name}」`,
      note: `${first.name}状态读取失败，无法确认是否已产出；不影响本页其他内容`,
      label: '重新读取',
      href: null,
    };
  }
  // 前置未产出（链在这里断掉）：给出缺的那一环与补齐入口。
  const missing = stations.slice(0, firstUndone).reverse().find((station) => station.state !== 'done') ?? first;
  return {
    kind: 'blocked',
    title: `缺「${missing.name}」`,
    note: missing.reason ?? missing.title,
    label: missing.action,
    href: missing.href,
  };
}

/** 单个来源失败不向外抛：`null` 就是「未知」，调用方照常渲染整条带。 */
async function settle<T>(load: () => Promise<T>): Promise<T | null> {
  try {
    return await load();
  } catch {
    return null;
  }
}

/**
 * 读取六工位的真实状态：五个列表接口并行、各自独立成败，最多再为「成绩 / 回流」各读一次
 * 成绩修订列表（拿真实版本号）。任何一步失败都只降级为对应工位「未知」。
 */
export async function loadLoopSnapshot(options: {
  subjectId?: string | null;
  services?: LoopProgressServices;
  signal?: AbortSignal;
} = {}): Promise<LoopSnapshot> {
  const services = options.services ?? loopProgressServices;
  const subjectId = options.subjectId && options.subjectId.trim() ? options.subjectId : null;
  const signal = options.signal;
  const [paperList, assessmentList, runPage, practicePage, lessonPage] = await Promise.all([
    settle(() => services.listPapers({ limit: LIST_LIMIT }, signal)),
    settle(() => services.listAssessments(subjectId ? { subjectId, limit: LIST_LIMIT } : { limit: LIST_LIMIT }, signal)),
    settle(() => services.listAnalysisRuns({ archived: false, limit: LIST_LIMIT }, signal)),
    settle(() => services.listPractices({ limit: LIST_LIMIT }, signal)),
    settle(() => services.listLessons(subjectId ? { subjectId, limit: LIST_LIMIT } : { limit: LIST_LIMIT }, signal)),
  ]);
  const assessments = assessmentList?.items ?? null;
  const active = (assessments ?? []).filter((item) => item.state !== 'archived' && matchesSubject(item.subjectId, subjectId));
  const scoreCandidate = newest(active.filter((item) => item.activeScoreRevisionId), (item) => item.createdAt);
  const refluxCandidate = newest(active.filter((item) => item.assessmentType === 'practice' && item.activeScoreRevisionId), (item) => item.createdAt);
  const scoreLinkId = scoreCandidate?.assessmentId ?? newest(active, (item) => item.createdAt)?.assessmentId ?? null;
  const refluxLinkId = refluxCandidate?.assessmentId
    ?? newest(active.filter((item) => item.assessmentType === 'practice'), (item) => item.createdAt)?.assessmentId
    ?? null;
  const targets = [...new Set([scoreCandidate?.assessmentId, refluxCandidate?.assessmentId].filter((value): value is string => !!value))];
  const scoreVersions: Record<string, number> = {};
  await Promise.all(targets.map(async (assessmentId) => {
    const revisions = await settle(() => services.listScoreRevisions(assessmentId, signal));
    if (!revisions) return;
    const activeId = assessments?.find((item) => item.assessmentId === assessmentId)?.activeScoreRevisionId ?? null;
    const match = revisions.items.find((revision) => revision.revisionId === activeId)
      ?? revisions.items.filter((revision) => revision.state === 'confirmed').reduce<typeof revisions.items[number] | undefined>(
        (best, revision) => (!best || revision.version > best.version ? revision : best), undefined);
    if (match) scoreVersions[assessmentId] = match.version;
  }));
  return {
    papers: paperList?.items ?? null,
    assessments,
    runs: runPage?.items ?? null,
    practices: practicePage?.items ?? null,
    lessons: lessonPage?.items ?? null,
    scoreVersions,
    scoreLinkId,
    refluxLinkId,
    subjectId,
  };
}
