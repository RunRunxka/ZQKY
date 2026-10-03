/**
 * `/assessments` 工作区的呈现判定与文案（纯函数，可单测）。
 *
 * 四态严格区分（TEACHING-LOOP B3 · F20-I）：
 * - `recorded`（有效分数，**显式 0 也是有效 0**）/ `missing`（空白，绝不显示成 0）/
 *   `absent`（缺考）/ `exempt`（免考）；
 * - 颜色只是辅助：每个徽章同时带**文案 + 字形**，图例同样给出文字说明；
 * - 原表单元格的本地读法（`rawCellReading`）只是**校对预览**，正式状态以服务端矩阵为准，
 *   文案里必须说清楚，不冒充服务端结论。
 *
 * 分数一律按整数单位 `scoreUnits`（= 分数 × 100）做**字符串运算**格式化，不做浮点累加。
 */

import type { ErrorIssue } from '@/contracts/api';
import type { Attendance } from '@/contracts/roster';
import type { ScoreStatus } from '@/contracts/teaching-loop';
import type { PaperItemView, PaperRevisionState, PaperStatus } from '@/contracts/papers';
import type {
  AssessmentState,
  AssessmentType,
} from '@/contracts/assessments';
import type {
  ScoreImportState,
  ScoreRevisionState,
} from '@/contracts/scores';

/* ------------------------------------------------------------------ 分数文本 */

/** 与后端 `SCORE_TEXT_PATTERN` 同口径：0–9999，最多两位小数。 */
export const SCORE_TEXT_PATTERN = /^\d{1,4}(\.\d{1,2})?$/;

export type ScoreTextParse =
  | { ok: true; units: number }
  | { ok: false; message: string };

/**
 * `scoreText` 十进制字符串 → 整数单位（字符串分段计算，不经过浮点）。
 * 空串不是合法分数（空 = missing，必须在单元格层面表达）。
 */
export function parseScoreText(text: string): ScoreTextParse {
  const value = text.trim();
  if (!SCORE_TEXT_PATTERN.test(value)) {
    return { ok: false, message: '分数必须是 0–9999 且最多两位小数的十进制文本。' };
  }
  const [whole, fraction = ''] = value.split('.');
  const units = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  return { ok: true, units };
}

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

/** 矩阵/单元格上的分数展示（`scoreUnits/100` 文本）。 */
export function scoreUnitsText(units: number | null | undefined): string {
  return units === null || units === undefined ? '（无分数）' : `${formatScoreUnits(units)} 分`;
}

/* ------------------------------------------------------------------ 四态呈现 */

/** 原表单元格的本地读法；未识别文本标 `unparsed`，不猜。 */
export type RawCellKind = ScoreStatus | 'unparsed';

/** 缺考/免考在表格里的写法：与 T60 服务端口径逐字一致（NFKC + 去空白 + casefold）。 */
export const ABSENT_TOKENS: readonly string[] = ['缺考', 'absent'];
export const EXEMPT_TOKENS: readonly string[] = ['免考', 'exempt'];

function normalizedToken(text: string): string {
  return text.trim().toLowerCase();
}

export interface RawCellReading {
  kind: RawCellKind;
  /** 显示用文本（公式单元格显示缓存值视图）。 */
  displayText: string;
  /** 补充说明（公式 / 空白 / 未识别）。 */
  note: string | null;
}

/**
 * 服务端有效状态优先；旧字段或纯原件展示使用本地只读读法：
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
      displayText: input.effectiveStatus === 'recorded'
        ? input.scoreUnits === null || input.scoreUnits === undefined
          ? '有效分数（未给分值）' : formatScoreUnits(input.scoreUnits)
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
  const token = normalizedToken(text);
  if (ABSENT_TOKENS.includes(token)) {
    return { kind: 'absent', displayText: text, note: null };
  }
  if (EXEMPT_TOKENS.includes(token)) {
    return { kind: 'exempt', displayText: text, note: null };
  }
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

/** 单元格值展示：recorded 给分数；其余状态给状态名，绝不给 0。 */
export function cellValueText(cell: { status: ScoreStatus; scoreUnits?: number | null }): string {
  if (cell.status === 'recorded') {
    return cell.scoreUnits === null || cell.scoreUnits === undefined
      ? '有效分数（服务端未给分值）'
      : `${formatScoreUnits(cell.scoreUnits)} 分`;
  }
  return scoreStatusShort(cell.status);
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

export function scoreRevisionStateLabel(state: ScoreRevisionState): string {
  return state === 'confirmed' ? '已确认（不可变）' : '草稿';
}

const ASSESSMENT_TYPE_LABELS: Record<AssessmentType, string> = {
  exam: '考试',
  quiz: '测验',
  practice: '练习',
};

export function assessmentTypeLabel(type: AssessmentType): string {
  return ASSESSMENT_TYPE_LABELS[type] ?? type;
}

const ASSESSMENT_STATE_LABELS: Record<AssessmentState, string> = {
  open: '进行中',
  closed: '已结束',
  archived: '已归档',
};

export function assessmentStateLabel(state: AssessmentState): string {
  return ASSESSMENT_STATE_LABELS[state] ?? state;
}

const ATTENDANCE_LABELS: Record<Attendance, string> = {
  present: '出勤',
  absent: '缺考',
  exempt: '免考',
};

export function attendanceLabel(attendance: Attendance): string {
  return ATTENDANCE_LABELS[attendance] ?? attendance;
}

const PAPER_STATUS_LABELS: Record<PaperStatus, string> = {
  active: '启用',
  archived: '已归档',
};

export function paperStatusLabel(status: PaperStatus): string {
  return PAPER_STATUS_LABELS[status] ?? status;
}

const PAPER_REVISION_STATE_LABELS: Record<PaperRevisionState, string> = {
  draft: '草稿（不可用于施测）',
  confirmed: '已确认',
};

export function paperRevisionStateLabel(state: PaperRevisionState): string {
  return PAPER_REVISION_STATE_LABELS[state] ?? state;
}

/* ------------------------------------------------------------------ 定位与承认 */

/** 错误/问题的原表物理定位：`原表第 3 行 · 列 E`（不把段落号当页码）。 */
export function issueLocationLabel(issue: ErrorIssue): string {
  const parts: string[] = [];
  if (typeof issue.row === 'number') parts.push(`原表第 ${issue.row} 行`);
  if (issue.column) parts.push(`列 ${issue.column}`);
  if (issue.field) parts.push(`字段 ${issue.field}`);
  return parts.length > 0 ? `[${parts.join(' · ')}] ` : '';
}

export interface ParticipantLite {
  participantId: string;
  classId: string;
  name: string;
  attendance: Attendance;
}

/** 只读矩阵一行的总分展示口径（只在全员 recorded 时展示，否则明确说明原因）。 */
export function matrixRowTotalText(participant: {
  totalUnits?: number | null;
  totalMaxUnits: number;
}): string {
  if (participant.totalUnits === null || participant.totalUnits === undefined) {
    return `不展示总分（共 ${formatScoreUnits(participant.totalMaxUnits)} 分；该人次含空白/缺考/免考）`;
  }
  return `${formatScoreUnits(participant.totalUnits)} / ${formatScoreUnits(participant.totalMaxUnits)} 分`;
}

/**
 * 固定计分叶：`isScored` 且没有计分子项（有计分子项的容器不直接计分）。
 * 矩阵列集合与列映射的题目下拉都来自它。
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
