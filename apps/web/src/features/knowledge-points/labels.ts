/**
 * 知识点模块的可见文案映射：状态、来源、行动作与错误码说明只在这里定义一份，
 * 组件不散写中文常量。
 *
 * 词表来源：
 * - 知识点状态 / 导入批次状态 / 行动作 / 链接来源：冻结契约 `@/contracts/knowledge` 的取值；
 * - 行级 `issues[].code` 的阻断判定：与后端 `app/services/knowledge/imports.py` 的
 *   `BLOCKING_ISSUE_CODES` 一致（**仅用于预览提示与入口禁用，最终以服务端 422 为准**）。
 */

import type { ErrorIssue } from '@/contracts/api';
import type {
  KnowledgeImportSource,
  KnowledgeImportState,
  KnowledgePointReferenceCount,
  KnowledgePointScope,
  KnowledgePointStatus,
  KnowledgeRowAction,
} from '@/contracts/knowledge';
import type { JobState } from '@/contracts/teaching-loop';

export const KNOWLEDGE_STATUS_LABEL: Record<KnowledgePointStatus, string> = {
  active: '在用',
  archived: '已归档',
};

export const KNOWLEDGE_IMPORT_STATE_LABEL: Record<KnowledgeImportState, string> = {
  uploaded: '已上传',
  reviewing: '待校对',
  confirmed: '已确认入库',
  failed: '失败',
  cancelled: '已取消',
};

export const KNOWLEDGE_SOURCE_LABEL: Record<KnowledgeImportSource, string> = {
  file: '表格导入',
  ai: 'AI 候选',
};

export const KNOWLEDGE_ROW_ACTION_LABEL: Record<KnowledgeRowAction, string> = {
  create: '新建',
  update: '更新',
  ignore: '忽略',
};

/** 统一任务六态（与后端 `JobState` 一致）。 */
export const JOB_STATE_LABEL: Record<JobState, string> = {
  queued: '排队中',
  running: '生成中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
  interrupted: '已中断',
};

/** 教材依据服务未就绪的固定文案（绝不能显示成「没有依据」）。 */
export const TEXTBOOK_EVIDENCE_UNAVAILABLE_TEXT = '教材依据暂不可用（服务未就绪）';

/** 教材目录未装配的错误码（后端 503；不降级为「没有依据」）。 */
export const TEXTBOOK_EVIDENCE_UNAVAILABLE_CODE = 'TEXTBOOK_EVIDENCE_UNAVAILABLE';

/** AI 候选任务被中断时的说明（不自动重跑模型，重试需用户显式点击）。 */
export const SUGGESTION_INTERRUPTED_NOTICE = '候选已中断（无执行器在跑）';

/** 行级阻断问题码（与后端 BLOCKING_ISSUE_CODES 一致；用于预览期禁用确认入口）。 */
export const BLOCKING_ISSUE_CODES: readonly string[] = [
  'KNOWLEDGE_ROW_INVALID',
  'KNOWLEDGE_ROW_MISSING_CODE',
  'KNOWLEDGE_ROW_MISSING_NAME',
  'KNOWLEDGE_ROW_DUPLICATE_CODE',
  'KNOWLEDGE_PARENT_INVALID',
  'KNOWLEDGE_CROSS_SUBJECT_PARENT',
  'KNOWLEDGE_CYCLE',
  'KNOWLEDGE_ARCHIVED',
  'KNOWLEDGE_CODE_CONFLICT',
];

/* ------------------------------------------------------------------ 范围 / 年级 / 删除 */

/** 列表范围切档文案（与设计 3.2 一致：默认窄口径在前）。 */
export const KNOWLEDGE_POINT_SCOPE_LABEL: Record<KnowledgePointScope, string> = {
  taught: '任教范围内教材',
  subject: '学科全部教材',
};

/** `scope=taught` 未能就绪（未设置任教范围 / 索引代未发布）：409，绝不静默回退全部。 */
export const KNOWLEDGE_SCOPE_UNAVAILABLE_CODE = 'KNOWLEDGE_SCOPE_UNAVAILABLE';

/** 知识点仍被引用（含仍有子节点）：409 `KNOWLEDGE_POINT_IN_USE`。 */
export const KNOWLEDGE_POINT_IN_USE_CODE = 'KNOWLEDGE_POINT_IN_USE';

/** 教材提取受理时书册未就绪：409 `KNOWLEDGE_EXTRACTION_NOT_READY`（逐册给原因）。 */
export const KNOWLEDGE_EXTRACTION_NOT_READY_CODE = 'KNOWLEDGE_EXTRACTION_NOT_READY';

/** 任教范围设置入口（`/knowledge-bases` 顶部的「任教范围」面板）。 */
export const TAUGHT_SCOPE_SETTINGS_HREF = '/knowledge-bases';

/** 删除守卫 `details.counts` 里的库名 → 可读库名（未知库名原样展示，不猜造）。 */
export const REFERENCE_LIBRARY_LABEL: Record<string, string> = {
  knowledge: '知识点库',
  teaching: '教学库',
  question_bank: '题库',
};

/** 删除守卫 `details.counts` 里的引用键 → 可读原因（未知键原样展示）。 */
export const REFERENCE_KEY_LABEL: Record<string, string> = {
  textbookKnowledgeLinks: '教材依据',
  paperItemKnowledge: '原卷题目关联',
  questionKnowledgeLinks: '题库正式题关联',
  questionDraftKnowledgeLinks: '题库草稿关联',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/**
 * 解析 409 `KNOWLEDGE_POINT_IN_USE` 的 `details.counts`。
 * 形状不认识、缺 `counts` 或全部计数为 0 时返回 null（**不伪造原因清单**）；
 * `count` 非有限数字的项直接丢弃（宁可少一行，也不显示假计数）。
 */
export function parseKnowledgeReferenceCounts(
  details: unknown,
): KnowledgePointReferenceCount[] | null {
  if (!isRecord(details) || !Array.isArray(details.counts)) return null;
  const counts: KnowledgePointReferenceCount[] = [];
  for (const item of details.counts) {
    if (!isRecord(item)) continue;
    const library = typeof item.library === 'string' ? item.library : '';
    const key = typeof item.key === 'string' ? item.key : '';
    const count = item.count;
    if (typeof count !== 'number' || !Number.isFinite(count)) continue;
    counts.push({ library, key, count });
  }
  const hits = counts.filter((item) => item.count > 0);
  return counts.length > 0 ? hits : null;
}

/** 单条引用计数的可读文案（库名 · 引用键：N 处）。 */
export function referenceCountLabel(item: KnowledgePointReferenceCount): string {
  const library = REFERENCE_LIBRARY_LABEL[item.library] ?? item.library;
  const key = REFERENCE_KEY_LABEL[item.key] ?? item.key;
  return library && key ? `${library} · ${key}：${item.count} 处` : `${key || library}：${item.count} 处`;
}

/** 未就绪书册（409 `KNOWLEDGE_EXTRACTION_NOT_READY` 的 `details.documents`）。 */
export interface ExtractionNotReadyDocument {
  documentId: string;
  title: string;
  reason: string;
}

/** 解析未就绪书册清单；形状不认识时返回 null（不猜造书名与原因）。 */
export function parseExtractionNotReadyDocuments(
  details: unknown,
): ExtractionNotReadyDocument[] | null {
  if (!isRecord(details) || !Array.isArray(details.documents)) return null;
  const documents: ExtractionNotReadyDocument[] = [];
  for (const item of details.documents) {
    if (!isRecord(item)) continue;
    documents.push({
      documentId: typeof item.documentId === 'string' ? item.documentId : '',
      title: typeof item.title === 'string' ? item.title : '',
      reason: typeof item.reason === 'string' ? item.reason : '',
    });
  }
  return documents.length > 0 ? documents : null;
}

/**
 * 当前结果里出现过的年级 id（去重、保持出现顺序）。
 * 教材字典的年级定义不可用时的降级来源；只汇总服务端确实返回的 `gradeIds`。
 */
export function collectResultGradeIds(items: readonly { gradeIds?: string[] }[]): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const item of items) {
    for (const gradeId of item.gradeIds ?? []) {
      if (!gradeId || seen.has(gradeId)) continue;
      seen.add(gradeId);
      ordered.push(gradeId);
    }
  }
  return ordered;
}

export function knowledgeStatusLabel(status: KnowledgePointStatus): string {
  return KNOWLEDGE_STATUS_LABEL[status] ?? String(status);
}

export function importStateLabel(state: KnowledgeImportState): string {
  return KNOWLEDGE_IMPORT_STATE_LABEL[state] ?? String(state);
}

export function importSourceLabel(source: KnowledgeImportSource): string {
  return KNOWLEDGE_SOURCE_LABEL[source] ?? String(source);
}

export function rowActionLabel(action: KnowledgeRowAction): string {
  return KNOWLEDGE_ROW_ACTION_LABEL[action] ?? String(action);
}

export function jobStateLabel(state: JobState): string {
  return JOB_STATE_LABEL[state] ?? String(state);
}

/** 批次状态对应的既有 chip 修饰类（不新增颜色）。 */
export function importStateChipClass(state: KnowledgeImportState): string {
  switch (state) {
    case 'confirmed':
      return 'space-chip green';
    case 'reviewing':
      return 'space-chip blue';
    case 'failed':
      return 'space-chip amber';
    default:
      return 'space-chip';
  }
}

/** 是否属于阻断确认的行级问题（预览期提示；确认仍以服务端为准）。 */
export function isBlockingIssue(issue: ErrorIssue): boolean {
  return BLOCKING_ISSUE_CODES.includes(issue.code);
}

export function blockingIssues(issues: readonly ErrorIssue[]): ErrorIssue[] {
  return issues.filter(isBlockingIssue);
}

/** 可读的行/列定位：有行号写行号，有列名写列名；都没有时只给错误码。 */
export function issueLocationLabel(issue: ErrorIssue): string {
  const parts: string[] = [];
  if (typeof issue.row === 'number') parts.push(`第 ${issue.row} 行`);
  if (issue.column) parts.push(`列「${issue.column}」`);
  else if (issue.field) parts.push(`字段 ${issue.field}`);
  return parts.length > 0 ? `${parts.join(' · ')}：` : '';
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
