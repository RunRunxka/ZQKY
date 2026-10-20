/**
 * `/assessments/**` 的呈现判定与文案（纯函数，可单测）。
 *
 * 分数一律按整数单位 `scoreUnits`（= 分数 × 100）做**字符串运算**格式化，不做浮点累加。
 * 名称类文本缺失时按 `nameOrShortId` 回落短号；**绝不伪造名称**。
 *
 * 重建期取回说明（R5-FE 2026-10-11）：归档 labels 里的成绩四态（recorded/missing/absent/
 * exempt 徽章与图例）、施测状态与出勤文案属于成绩分析批次，本模块不持有。
 */

import type { ErrorIssue } from '@/contracts/api';
import type { PaperItemView, PaperRevisionState } from '@/contracts/papers';
import type { StudentView } from '@/contracts/roster';

/* ------------------------------------------------------------------ 分数文本 */

/** 整数单位 → 分数文本（最多两位小数；不使用浮点除法）。 */
export function formatScoreUnits(units: number | null | undefined): string {
  if (units === null || units === undefined) return '—';
  const negative = units < 0;
  const abs = Math.abs(Math.trunc(units));
  const whole = Math.floor(abs / 100);
  const fraction = abs % 100;
  if (fraction === 0) return `${negative ? '-' : ''}${whole}`;
  const fractionText = String(fraction).padStart(2, '0').replace(/0$/, '');
  return `${negative ? '-' : ''}${whole}.${fractionText}`;
}

/* ------------------------------------------------------------------ 状态文案 */

const PAPER_REVISION_STATE_LABELS: Record<PaperRevisionState, string> = {
  draft: '草稿（不可用于施测）',
  confirmed: '已确认',
};

export function paperRevisionStateLabel(state: PaperRevisionState): string {
  return PAPER_REVISION_STATE_LABELS[state] ?? state;
}

/** 状态徽标用的 space-chip 色调类（颜色只是辅助，文案始终自洽）。 */
export function paperStateChipClass(state: PaperRevisionState | null): string {
  if (state === 'confirmed') return 'space-chip green';
  if (state === 'draft') return 'space-chip amber';
  return 'space-chip';
}

/* ------------------------------------------------------------------ 定位 */

/** 错误/问题的物理定位：`[原文第 3 段 · 字段 X] `（不把段落号当页码）。 */
export function issueLocationLabel(issue: ErrorIssue): string {
  const parts: string[] = [];
  if (typeof issue.row === 'number') parts.push(`原表第 ${issue.row} 行`);
  if (issue.column) parts.push(`列 ${issue.column}`);
  if (issue.field) parts.push(`字段 ${issue.field}`);
  return parts.length > 0 ? `[${parts.join(' · ')}] ` : '';
}

/* ------------------------------------------------------------------ 计分叶 */

/**
 * 固定计分叶：`isScored` 且没有计分子项（有计分子项的容器不直接计分）。
 */
export function scoredLeafItems(items: readonly PaperItemView[]): PaperItemView[] {
  const parentWithScoredChild = new Set(
    items.filter((item) => item.isScored && item.parentItemId).map((item) => item.parentItemId),
  );
  return items
    .filter((item) => item.isScored && !parentWithScoredChild.has(item.itemId))
    .sort((a, b) => a.ordinal - b.ordinal);
}

/** 计分叶显示名：`题号（满分 X）`（满分来自原卷固定修订）。 */
export function leafLabel(item: PaperItemView): string {
  const max = item.maxScoreUnits === null ? '' : `（满分 ${formatScoreUnits(item.maxScoreUnits)}）`;
  return `${item.questionNo}${max}`;
}

/* ------------------------------------------------------------------ 名称优先与守卫原因 */

/**
 * 短号：长 ID 只显示前 `length` 位（名称缺失时的兜底显示，不是主文本）。
 * 空值给 `—`（"没有"与"有但太长"必须能区分开）。
 */
export function shortId(id: string | null | undefined, length = 8): string {
  if (!id) return '—';
  return id.length <= length ? id : `${id.slice(0, length)}…`;
}

/** 名称缺失时的回落：名称在就用名称，否则给 ID 短号（绝不伪造名称）。 */
export function nameOrShortId(
  name: string | null | undefined,
  id: string | null | undefined,
): string {
  const trimmed = typeof name === 'string' ? name.trim() : '';
  return trimmed !== '' ? trimmed : shortId(id);
}

/** 受引用守卫 409 的一条计数：`键 → 标签 + 计数`。 */
export interface ReferenceCount {
  key: string;
  label: string;
  count: number;
}

/**
 * 班级删除 409 的计数标签（R10-BE 语义）：阻断项是「成绩链证据」（参测人次）与
 * 「教案」（独立成果）；其余键（归属/名单批次/参测范围）只作如实呈现（它们随班级联），
 * 服务端给出非零值时仍逐项列出，不隐藏任何一条引用。
 */
export const CLASS_REFERENCE_LABELS: Record<string, string> = {
  assessmentParticipants: '施测参测人次（成绩链证据；先在学情分析删除相关施测）',
  lessonPlans: '班级教案（到教案工作台删除该教案后重试）',
  lessonGenerationInputs: '教案生成输入（随教案删除）',
  memberships: '班级归属记录',
  rosterImports: '名单导入批次',
  assessments: '参测范围引用',
};

/**
 * 班级删除里**真正挡住删除**的计数键（其余键随删除一并清掉，只是如实告知）：
 * 参测人次是成绩链证据、教案与教案生成输入是独立教学成果——都不随班级删除销毁。
 */
export const CLASS_BLOCKING_KEYS: readonly string[] = [
  'assessmentParticipants',
  'lessonPlans',
  'lessonGenerationInputs',
];

export const PAPER_REFERENCE_LABELS: Record<string, string> = {
  assessments: '引用施测（先在学情分析删除该施测，再删原卷）',
  confirmedRevisions: '已确认修订',
};

/** 试卷删除里真正挡住删除的键：施测是成绩链的锚点；修订链（含已确认）随原卷级联。 */
export const PAPER_BLOCKING_KEYS: readonly string[] = ['assessments'];

/**
 * 从 409 的 `details` 里读 `counts` 并逐项列成原因清单：
 * 只保留计数 >0 的键，未知键用原始键名兜底（不隐藏任何一条引用），形状不符返回空数组。
 */
export function referenceCounts(
  details: unknown,
  labels: Record<string, string>,
): ReferenceCount[] {
  if (!details || typeof details !== 'object') return [];
  const counts = (details as { counts?: unknown }).counts;
  if (!counts || typeof counts !== 'object') return [];
  return Object.entries(counts as Record<string, unknown>)
    .filter(([, value]) => typeof value === 'number' && value > 0)
    .map(([key, value]) => ({ key, label: labels[key] ?? key, count: value as number }));
}

/* ------------------------------------------------------------------ 学生列表（纯函数） */

/**
 * 性别列的显示文本（R5-FE 参考图列）。
 *
 * 后端归档契约没有性别字段，因此这里**只显示服务端真的给出的值**：缺失、`null`、空串、
 * 纯空白一律显示「未记录」，不做任何推断（不从姓名猜、不用「其他」顶替）。后端补上该字段时
 * 自动显示原文，无需改这里。
 */
export function genderText(gender: string | null | undefined): string {
  const text = typeof gender === 'string' ? gender.trim() : '';
  return text === '' ? '未记录' : text;
}

/**
 * 按姓名筛选本班学生（大小写不敏感、去首尾空白；空查询返回原列表）。
 *
 * 服务端 `GET /classes/{id}/students` 没有姓名查询参数，因此搜索是**视图层**对真实全集的
 * 筛选：`items` 始终是本班成员全集（可能含已归档），不把本地筛选结果冒充服务端分页。
 */
export function filterStudentsByName(
  students: readonly StudentView[],
  query: string,
): StudentView[] {
  const keyword = query.trim().toLowerCase();
  if (keyword === '') return [...students];
  return students.filter((student) => student.name.toLowerCase().includes(keyword));
}

/** 分页页数（至少 1 页：空列表也显示「第 1 / 1 页」，不显示 0 页）。 */
export function pageCount(total: number, pageSize: number): number {
  if (!Number.isFinite(total) || total <= 0 || pageSize <= 0) return 1;
  return Math.ceil(total / pageSize);
}

/** 把页码夹到合法范围（筛选后行数变少时不会停留在空页）。 */
export function clampPage(page: number, pages: number): number {
  if (!Number.isFinite(page) || page < 0) return 0;
  return Math.min(Math.trunc(page), Math.max(0, pages - 1));
}

/* ------------------------------------------------------------------ 学科显示 */

/**
 * 学科显示文本（试卷列表的「科目」列）。
 *
 * 学科字典来自 `GET /textbook-taxonomy`：命中就用字典标签；字典读到了但没收录该 id，
 * 说明服务端给了字典外的学科（不隐藏、不猜标签，显示短号并注明未收录）；
 * 字典**读取失败**时明确说「字典不可用」而不是谎称「未收录」，两者必须能区分。
 */
export function subjectText(
  subjectId: string,
  subjects: readonly { id: string; label: string }[] | null,
  dictionaryFailed: boolean,
): string {
  const hit = subjects?.find((subject) => subject.id === subjectId);
  if (hit) return hit.label;
  if (dictionaryFailed) return `学科字典不可用（${shortId(subjectId)}）`;
  if (subjects) return `字典未收录（${shortId(subjectId)}）`;
  return shortId(subjectId);
}

/* ------------------------------------------------------------------ 知识点占比图例 */

/**
 * 占比文本：只用服务端给的 `scoreRatio`（0..1），**不在前端自己算比例**。
 * `null`（服务端未给出）显示「占比未知」，不冒充 0%。
 */
export function ratioPercentText(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return '占比未知';
  return `${Math.round(ratio * 100)}%`;
}

/** 环状图调色板：沿用项目蓝色主题与既有取值（与归档 KnowledgeDonut 同一组颜色）。 */
export const KNOWLEDGE_DONUT_PALETTE: readonly string[] = [
  '#2563eb',
  '#38bdf8',
  '#34d399',
  '#fbbf24',
  '#f87171',
  '#a78bfa',
  '#94a3b8',
];
