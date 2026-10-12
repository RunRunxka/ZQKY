'use client';

/**
 * 小题分成绩单导入的纯展示口径（取回自归档 `features/assessments/labels.ts`，R6-FE）。
 *
 * 保留归档语义：四态显著区分（0 是有效记录、空白绝不补 0、缺考/免考不计 0）、
 * 422 定位原表物理坐标、名称缺失只回落短号（不伪造名称）、引用守卫计数逐项列出。
 * 与归档的差异：只保留本 feature 用到的纯函数，类型改从 `@/contracts/learning-analysis` 导入。
 */

import type { ErrorIssue } from '@/contracts/api';
import type {
  PaperItemView,
  ScoreImportState,
  ScoreStatus,
} from '@/contracts/learning-analysis';

export const SCORE_TEXT_PATTERN = /^\d{1,4}(\.\d{1,2})?$/;

/** 服务端分数为 ×100 整数单位；展示为十进制文本，不四舍五入丢精度。 */
export function formatScoreUnits(units: number | null | undefined): string {
  if (units === null || units === undefined) return '—';
  const sign = units < 0 ? '-' : '';
  const abs = Math.abs(units);
  const whole = Math.floor(abs / 100);
  const rest = abs % 100;
  if (rest === 0) return `${sign}${whole}`;
  return `${sign}${whole}.${String(rest).padStart(2, '0')}`;
}

/** 矩阵/单元格上的分数展示（`scoreUnits/100` 文本）。 */
export function scoreUnitsText(units: number | null | undefined): string {
  return units === null || units === undefined ? '（无分数）' : `${formatScoreUnits(units)} 分`;
}

/* ------------------------------------------------------------------ 四态呈现 */

/** 原表单元格的本地读法；未识别文本标 `unparsed`，不猜。 */
export type RawCellKind = ScoreStatus | 'unparsed';

/** 缺考/免考在表格里的写法：与成绩导入服务端口径逐字一致（去空白 + casefold）。 */
export const ABSENT_TOKENS: readonly string[] = ['缺考', 'absent'];
export const EXEMPT_TOKENS: readonly string[] = ['免考', 'exempt'];

export interface RawCellReading {
  kind: RawCellKind;
  /** 显示用文本（公式单元格显示缓存值视图）。 */
  displayText: string;
  /** 补充说明（公式 / 空白 / 未识别）。 */
  note: string | null;
}

/**
 * 服务端有效状态优先；纯原件展示使用本地只读读法：
 * 空白 → missing；数值（含 0）→ recorded；缺考/免考标记 → absent/exempt；其余 → unparsed。
 * 正式四态由服务端确认后的矩阵给出，这里绝不把未知文本当 0。
 */
export function rawCellReading(input: {
  text?: string;
  cachedText?: string;
  isFormula?: boolean;
  effectiveStatus?: ScoreStatus | null;
  scoreUnits?: number | null;
}): RawCellReading {
  if (input.effectiveStatus) {
    return {
      kind: input.effectiveStatus,
      displayText:
        input.effectiveStatus === 'recorded'
          ? input.scoreUnits === null || input.scoreUnits === undefined
            ? '有效分数（未给分值）'
            : formatScoreUnits(input.scoreUnits)
          : scoreStatusShort(input.effectiveStatus),
      note: '服务端有效状态（已应用出勤与保存的校正）',
    };
  }
  const text = (input.text ?? '').trim();
  const cached = (input.cachedText ?? '').trim();
  if (input.isFormula) {
    return {
      kind: cached === '' ? 'unparsed' : rawCellReading({ text: cached }).kind,
      displayText: cached === '' ? '（公式无缓存值）' : cached,
      note: text ? `公式视图：${text}` : '公式单元格（按缓存值预览）',
    };
  }
  if (text === '') {
    return { kind: 'missing', displayText: '（空白）', note: '空白单元格按 missing 处理，不补 0' };
  }
  const token = text.trim().toLowerCase();
  if (ABSENT_TOKENS.includes(token)) return { kind: 'absent', displayText: text, note: null };
  if (EXEMPT_TOKENS.includes(token)) return { kind: 'exempt', displayText: text, note: null };
  if (SCORE_TEXT_PATTERN.test(text)) {
    return { kind: 'recorded', displayText: text, note: text === '0' ? '显式 0 分（有效记录）' : null };
  }
  return { kind: 'unparsed', displayText: text, note: '无法本地判读，以服务端为准' };
}

const STATUS_LABELS: Record<ScoreStatus, string> = {
  recorded: '有效分数（recorded）',
  missing: '空白（missing）',
  absent: '缺考（absent）',
  exempt: '免考（exempt）',
};

const STATUS_SHORT: Record<ScoreStatus, string> = {
  recorded: '有效',
  missing: '空白',
  absent: '缺考',
  exempt: '免考',
};

const STATUS_GLYPHS: Record<ScoreStatus, string> = {
  recorded: '●',
  missing: '▢',
  absent: '✕',
  exempt: '◇',
};

export function scoreStatusLabel(status: ScoreStatus): string {
  return STATUS_LABELS[status];
}

export function scoreStatusShort(status: ScoreStatus): string {
  return STATUS_SHORT[status];
}

export function scoreStatusGlyph(status: RawCellKind): string {
  return status === 'unparsed' ? '?' : STATUS_GLYPHS[status];
}

export function scoreStatusChipClass(status: RawCellKind): string {
  return `score-status score-status-${status}`;
}

/** 图例（颜色 + 文案 + 字形三重说明；页面与测试共用同一份口径）。 */
export const SCORE_STATUS_LEGEND: readonly { status: ScoreStatus; note: string }[] = [
  { status: 'recorded', note: '表格里的 0 是有效 0 分，不等于空白' },
  { status: 'missing', note: '空白单元格：不补 0，需逐类承认后确认' },
  { status: 'absent', note: '缺考：按人次出勤状态登记，不计 0' },
  { status: 'exempt', note: '免考：不计 0，不参与总分核对' },
];

/* ------------------------------------------------------------------ 各类状态文案 */

const IMPORT_STATE_LABELS: Record<ScoreImportState, string> = {
  uploaded: '已上传（待映射）',
  reviewing: '校对中',
  confirmed: '已确认入库',
  failed: '已失败',
  cancelled: '已取消',
};

export function scoreImportStateLabel(state: ScoreImportState): string {
  return IMPORT_STATE_LABELS[state];
}

export function scoreImportStateChipClass(state: ScoreImportState): string {
  if (state === 'confirmed') return 'space-chip green';
  if (state === 'failed' || state === 'cancelled') return 'space-chip score-chip-danger';
  if (state === 'reviewing') return 'space-chip blue';
  return 'space-chip';
}

/** 422/409 的行列定位文本（原表物理坐标；字段级错误退化为字段名）。 */
export function issueLocationLabel(issue: ErrorIssue): string {
  const parts: string[] = [];
  if (typeof issue.row === 'number') parts.push(`第 ${issue.row} 行`);
  if (issue.column) parts.push(`列 ${issue.column}`);
  if (parts.length === 0 && issue.field) parts.push(`字段 ${issue.field}`);
  return parts.length > 0 ? `${parts.join(' ')}：` : '';
}

export interface ParticipantLite {
  participantId: string;
  classId: string;
  name: string;
  attendance: 'present' | 'absent' | 'exempt';
  attemptNo: number;
}

/**
 * 固定计分叶：`isScored` 且没有计分子项（有计分子项的容器不直接计分）。
 * 列映射的题目下拉与校对视图的叶集合都来自它。
 */
export function scoredLeafItems(items: readonly PaperItemView[]): PaperItemView[] {
  const parentWithScoredChild = new Set(
    items.filter((item) => item.isScored && item.parentItemId).map((item) => item.parentItemId),
  );
  return items
    .filter((item) => item.isScored && !parentWithScoredChild.has(item.itemId))
    .sort((a, b) => a.ordinal - b.ordinal);
}

/** 计分叶显示名：`题号 · 满分`（满分来自原卷固定修订）。 */
export function leafLabel(item: PaperItemView): string {
  const max = item.maxScoreUnits === null ? '' : `（满分 ${formatScoreUnits(item.maxScoreUnits)}）`;
  return `${item.questionNo}${max}`;
}

/**
 * 短号：长 ID 只显示前 `length` 位（名称缺失时的兜底显示，不是主文本）。
 * 空值给 `—`（「没有」与「有但太长」必须能区分开）。
 */
export function shortId(id: string | null | undefined, length = 8): string {
  if (!id) return '—';
  return id.length <= length ? id : `${id.slice(0, length)}…`;
}

/** 受引用守卫 409 的一条计数：`键 → 标签 + 计数`。 */
export interface ReferenceCount {
  key: string;
  label: string;
  count: number;
}

/** 彻底删除成绩导入批次被拒（`SCORE_IMPORT_IN_USE`）的 `details.counts` 逐项标签。 */
export const SCORE_IMPORT_REFERENCE_LABELS: Record<string, string> = {
  scoreRevisions: '已生成的成绩版本',
};

/**
 * 从 409 的 `details` 里读 `counts` 并逐项列成原因清单：
 * 只保留计数 >0 的键，未知键用原始键名兜底（不隐藏任何一条引用），形状不符返回空数组。
 */
export function referenceCounts(details: unknown, labels: Record<string, string>): ReferenceCount[] {
  if (!details || typeof details !== 'object') return [];
  const counts = (details as { counts?: unknown }).counts;
  if (!counts || typeof counts !== 'object') return [];
  return Object.entries(counts as Record<string, unknown>)
    .filter(([, value]) => typeof value === 'number' && value > 0)
    .map(([key, value]) => ({ key, label: labels[key] ?? key, count: value as number }));
}
