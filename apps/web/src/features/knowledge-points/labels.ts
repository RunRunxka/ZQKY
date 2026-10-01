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
