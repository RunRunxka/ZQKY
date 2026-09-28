/**
 * 教材模块的可见文案映射：状态/类别只在这里定义一份，组件不散写中文常量。
 * 导入阶段文案直接使用冻结契约的 `IMPORT_STATE_LABEL`（缺项按原样显示，不猜造）。
 */

import {
  IMPORT_STATE_LABEL,
  type ChunkRegion,
  type ImportDraftView,
  type ImportState,
  type JobKind,
  type JobState,
  type LibraryKind,
} from '@/contracts/textbook';

/** 终态：到达后不再轮询（`ready` 已入库 / `failed` / `cancelled`）。 */
export const TERMINAL_IMPORT_STATES: readonly ImportState[] = ['ready', 'failed', 'cancelled'];

export function isImportTerminal(state: ImportState): boolean {
  return TERMINAL_IMPORT_STATES.includes(state);
}

/** 解析进行中：需要按阶段轮询 `getImport`。 */
export const ACTIVE_IMPORT_STATES: readonly ImportState[] = [
  'uploaded',
  'extracting',
  'queued',
  'chunking',
  'embedding',
  'indexing',
];

export function isImportActive(state: ImportState): boolean {
  return ACTIVE_IMPORT_STATES.includes(state);
}

/** 未在契约表中列出的状态按原样显示，不虚构阶段名。 */
export function importStateLabel(state: ImportState): string {
  return IMPORT_STATE_LABEL[state] ?? String(state);
}

export const JOB_STATE_LABEL: Record<JobState, string> = {
  queued: '排队中',
  running: '执行中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

export const JOB_KIND_LABEL: Record<JobKind, string> = {
  ingest: '入库',
  rebuild: '索引重建',
  cleanup: '清理',
};

export const REGION_LABEL: Record<ChunkRegion, string> = {
  body: '正文',
  exercise: '习题',
};

/** 解析来源类型（与契约 `ImportParsedView.sourceKind` 一致）。 */
export const SOURCE_KIND_LABEL: Record<'markdown' | 'pdf' | 'docx', string> = {
  markdown: 'Markdown 文本',
  pdf: 'PDF',
  docx: 'Word（.docx）',
};

export const LIBRARY_KIND_LABEL: Record<LibraryKind, string> = {
  base: '基础库',
  personal: '我的教材',
};

export function jobStateLabel(state: JobState): string {
  return JOB_STATE_LABEL[state] ?? String(state);
}

export function jobKindLabel(kind: JobKind): string {
  return JOB_KIND_LABEL[kind] ?? String(kind);
}

/** 进行中（可取消）的任务状态。 */
export function isJobActive(state: JobState): boolean {
  return state === 'queued' || state === 'running';
}

/** 进度百分比（0–100 整数）；总量为 0 时返回 0，不除以零。 */
export function progressPercent(done: number, total: number): number {
  if (!Number.isFinite(done) || !Number.isFinite(total) || total <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((done / total) * 100)));
}

export interface CommitGateInput {
  draft: ImportDraftView | null;
  /** 已勾选的目标逻辑库数量 */
  libraryCount: number;
  hasWarnings: boolean;
  warningsAcknowledged: boolean;
  committed: boolean;
}

/**
 * 为什么现在不能提交入库（null = 可以提交）。
 *
 * 顺序：服务端 `canCommit` 是唯一权威；只有它为假时才按草稿状态解释具体原因
 * （需要 OCR / 状态不对 / 未确认元数据），避免笼统地禁用按钮。服务端允许后再检查
 * 客户端前置条件（目标逻辑库、警告确认）。
 */
export function commitBlockReason(input: CommitGateInput): string | null {
  const { draft, libraryCount, hasWarnings, warningsAcknowledged, committed } = input;
  if (!draft || committed) return null;

  if (draft.canCommit) {
    if (draft.parsed?.needsOcr)
      return '该文件没有可用文本层（需要 OCR 或人工处理），无法提交入库。';
    if (libraryCount === 0) return '请选择至少一个目标逻辑库。';
    if (hasWarnings && !warningsAcknowledged) return '请先勾选「我已核对以上警告，确认继续入库」。';
    return null;
  }

  if (draft.parsed?.needsOcr) {
    return '该文件没有可用文本层（需要 OCR 或人工处理），服务端不会为此生成索引。';
  }
  if (draft.state === 'failed') return '解析失败：请重新上传文件后再提交。';
  if (draft.state === 'cancelled') return '该草稿已取消：请重新上传文件后再提交。';
  if (draft.state !== 'needs_review') {
    return `当前阶段「${importStateLabel(draft.state)}」不可提交：请等服务端处理到「待确认」。`;
  }
  if (!draft.metadata || !draft.metadataConfirmed) {
    return '尚未确认分类元数据：请填写分类并「保存分类」（保存即确认），再提交入库。';
  }
  return '服务端当前不允许提交（可提交性以草稿状态为准）。';
}
