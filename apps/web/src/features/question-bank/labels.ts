/**
 * 题库模块的可见文案映射：状态与来源类型只在这里定义一份，组件不散写中文常量。
 * 题目类型 / 难度 / 校对状态 / 整理状态直接使用冻结契约里的映射（不重复定义）。
 */

import {
  DIFFICULTY_LABEL,
  QUESTION_TYPE_LABEL,
  REVIEW_STATE_LABEL,
  ORGANIZE_STATE_LABEL,
  type AnswerState,
  type Difficulty,
  type DraftReviewState,
  type OrganizeJobView,
  type QuestionImportState,
  type QuestionLocatorView,
  type QuestionType,
  type SuggestionState,
} from '@/contracts/question-bank';

export const QUESTION_IMPORT_STATE_LABEL: Record<QuestionImportState, string> = {
  uploaded: '已上传',
  extracting: '解析中',
  needs_review: '待校对',
  failed: '解析失败',
  cancelled: '已取消',
  confirmed: '已确认入库',
};

export const ANSWER_STATE_LABEL: Record<AnswerState, string> = {
  provided: '答案已提供',
  not_provided: '答案缺失',
};

export const EXTRACTION_METHOD_LABEL: Record<'rule' | 'ai' | 'manual', string> = {
  rule: '规则拆题',
  ai: 'AI 候选（整理/补题）',
  manual: '人工拆分',
};

/** AI 候选的显式标识：来源是 AI（整理或补题），且必然还要人工校对。 */
export const AI_CANDIDATE_CHIP = 'AI 候选（需人工校对）';

/** 旧字段 knowledgeTags 的区块标题与边界说明（与正式关联分开呈现，不合并、不丢弃）。 */
export const LEGACY_TAGS_TITLE = '历史知识点标签（旧字段）';
export const LEGACY_TAGS_HINT =
  '旧字段 knowledgeTags 与正式知识点关联分开保留：不合并、不丢弃，也不参与知识点筛选。';

/** 200 + failures 的统一说法：整批未确认（不是部分成功）。 */
export const CONFIRM_UNCONFIRMED_TITLE = '整批未确认';


export const SUGGESTION_STATE_LABEL: Record<SuggestionState, string> = {
  pending: '待处理',
  applied: '已应用',
  rejected: '已忽略',
};

export const LOCATOR_KIND_LABEL: Record<QuestionLocatorView['kind'], string> = {
  markdown: 'Markdown',
  pdf: 'PDF',
  docx: 'Word',
  text: '纯文本',
};

/** 未在契约表中列出的取值按原样显示，不虚构阶段名。 */
export function importStateLabel(state: QuestionImportState): string {
  return QUESTION_IMPORT_STATE_LABEL[state] ?? String(state);
}

/** 批次状态对应的既有 chip 修饰类（不新增颜色）。 */
export function importStateChipClass(state: QuestionImportState): string {
  switch (state) {
    case 'confirmed':
      return 'space-chip green';
    case 'needs_review':
      return 'space-chip blue';
    case 'failed':
      return 'space-chip amber';
    default:
      return 'space-chip';
  }
}

export function reviewStateLabel(state: DraftReviewState): string {
  return REVIEW_STATE_LABEL[state] ?? String(state);
}

export function questionTypeLabel(type: QuestionType): string {
  return QUESTION_TYPE_LABEL[type] ?? String(type);
}

export function difficultyLabel(difficulty: Difficulty): string {
  return DIFFICULTY_LABEL[difficulty] ?? String(difficulty);
}

export function organizeStateLabel(state: keyof typeof ORGANIZE_STATE_LABEL): string {
  return ORGANIZE_STATE_LABEL[state] ?? String(state);
}

/** 整理任务状态对应的既有 chip 修饰类（不新增颜色）：中断/失败用 amber，进行中用 blue。 */
export function organizeStateChipClass(state: OrganizeJobView['state']): string {
  switch (state) {
    case 'succeeded':
      return 'space-chip green';
    case 'failed':
    case 'interrupted':
      return 'space-chip amber';
    case 'running':
      return 'space-chip blue';
    default:
      return 'space-chip';
  }
}

function range(start: number | null, end: number | null, unit: string): string | null {
  if (start === null && end === null) return null;
  const from = start ?? end;
  const to = end ?? start;
  if (from === null || to === null) return null;
  return from === to ? `第 ${from} ${unit}` : `第 ${from}–${to} ${unit}`;
}

/**
 * 可读定位文案：按来源类型选择行号 / 页码 / 段落序号。
 * 契约中四种 kind 的可用字段不同，取不到时返回空串（不编造位置）。
 */
export function locatorLabel(locator: QuestionLocatorView): string {
  switch (locator.kind) {
    case 'markdown':
      return range(locator.lineStart, locator.lineEnd, '行') ?? '';
    case 'pdf':
      return range(locator.pageStart, locator.pageEnd, '页') ?? '';
    case 'docx':
    case 'text':
      return range(locator.blockStart, locator.blockEnd, '段') ?? '';
    default:
      return '';
  }
}

/** 文件大小（MiB，一位小数）；0 字节显示 0 MiB。 */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 MiB';
  return `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
}

/** 时间展示：解析失败时原样返回，不显示假时间。 */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
