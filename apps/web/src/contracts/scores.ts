/**
 * 成绩 v1 契约镜像（TEACHING-LOOP B3 / T60）。
 *
 * 与后端 `apps/api/app/contracts/scores.py` 逐字段对应（camelCase）；
 * 修改任一侧必须同步另一侧。分数一律十进制字符串（服务端转 ×100 整数单位）。
 *
 * 三个版本语义互不替代：`expectedImportRevision`（导入草稿乐观锁）、
 * `expectedAssessmentRevision`（施测乐观锁）、`baseScoreRevisionId`（所基于的正式成绩版本；
 * 首个版本为 null，修正时必须等于当前 active）。任一不符 → 409，保留前端编辑。
 */

import type { AssetRef, ErrorIssue, ScoreStatus } from '@/contracts/teaching-loop';

export type ScoreImportState =
  | 'uploaded'
  | 'reviewing'
  | 'confirmed'
  | 'failed'
  | 'cancelled';
export type ScoreRevisionState = 'draft' | 'confirmed';

export interface ScoreItemColumn {
  itemId: string;
  /** 原表列字母，如 "D" */
  column: string;
}

export interface ScoreColumnMapping {
  workSheet: string;
  /** 仅用于原表表头定位展示；0 = 无表头 */
  headerRow?: number;
  studentNoColumn?: string | null;
  nameColumn?: string | null;
  itemColumns: ScoreItemColumn[];
}

export interface ScoreRawCellView {
  row: number;
  column: string;
  /** 公式视图文本（公式单元格为公式文本） */
  text?: string;
  /** data_only 缓存值文本 */
  cachedText?: string;
  isFormula?: boolean;
}

export interface ScoreImportRowView {
  rowNo: number;
  participantId?: string | null;
  participantName?: string | null;
  /** 歧义/未匹配行的可选取人次（供教师显式消歧） */
  candidates?: string[];
  cells?: ScoreRawCellView[];
  issues?: ErrorIssue[];
}

export interface ScoreCellPatch {
  /** 原表物理坐标（与题目映射无关） */
  row: number;
  column: string;
  text?: string;
}

export interface ScoreImportRowPatch {
  rowNo: number;
  participantId?: string | null;
  cells?: ScoreCellPatch[];
}

export interface ScoreImportView {
  importId: string;
  assessmentId: string;
  assessmentTitle: string;
  state: ScoreImportState;
  revision: number;
  previewVersion: number;
  fileAsset: AssetRef;
  mapping?: ScoreColumnMapping | null;
  baseScoreRevisionId?: string | null;
  warnings?: string[];
  issues?: ErrorIssue[];
  rowCount: number;
  resolvedRowCount: number;
  missingCellCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ScoreImportRowList {
  items: ScoreImportRowView[];
  total: number;
  offset: number;
  limit: number;
}

export interface ScoreImportSummary {
  importId: string;
  assessmentId: string;
  state: ScoreImportState;
  revision: number;
  rowCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ScoreImportList {
  items: ScoreImportSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface ScoreAbsenceAcknowledgement {
  classId: string;
  participantIds: string[];
}

export interface ScoreMissingAcknowledgement {
  participantIds: string[];
  cellCount: number;
}

/**
 * 一次生效的导入校对补丁；`mapping`/`rows` 至少提供一项。
 * `expectedRevision` 是导入批次自己的乐观锁（CAS）：不符 409 + `currentRevision`，前端保留编辑。
 */
export interface ScoreImportPatchRequest {
  expectedRevision: number;
  mapping?: ScoreColumnMapping | null;
  rows?: ScoreImportRowPatch[];
}

export interface ScoreImportConfirmRequest {
  expectedImportRevision: number;
  expectedAssessmentRevision: number;
  baseScoreRevisionId?: string | null;
  previewVersion: number;
  submissionId: string;
  absences?: ScoreAbsenceAcknowledgement[];
  missing?: ScoreMissingAcknowledgement | null;
}

export interface ScoreImportConfirmResult {
  importId: string;
  state: ScoreImportState;
  revisionId: string;
  assessmentRevision: number;
  activeScoreRevisionId: string;
  replayed?: boolean;
}

export interface ScoreParticipantSnapshot {
  participantId: string;
  studentId: string;
  studentNo?: string | null;
  name: string;
  classId: string;
  attemptNo: number;
  attendance: 'present' | 'absent' | 'exempt';
}

export interface ScoreItemSnapshot {
  itemId: string;
  itemPath: string;
  maxScoreUnits: number;
}

export interface ScoreRevisionView {
  revisionId: string;
  assessmentId: string;
  version: number;
  state: ScoreRevisionState;
  sourceImportId?: string | null;
  baseRevisionId?: string | null;
  participantSnapshot?: ScoreParticipantSnapshot[];
  itemSnapshot?: ScoreItemSnapshot[];
  confirmedAt?: string | null;
  createdAt: string;
}

export interface ScoreRevisionList {
  items: ScoreRevisionView[];
  total: number;
}

export interface ScoreCellValue {
  itemId: string;
  status: ScoreStatus;
  scoreUnits?: number | null;
}

export interface ScoreMatrixParticipant {
  participantId: string;
  studentId: string;
  studentNo?: string | null;
  name: string;
  classId: string;
  attemptNo: number;
  attendance: 'present' | 'absent' | 'exempt';
  /** 只在全员 recorded 时非空；否则 null */
  totalUnits?: number | null;
  totalMaxUnits: number;
}

export interface ScoreMatrixRow {
  participant: ScoreMatrixParticipant;
  /** 与 items 顺序一一对应 */
  cells: ScoreCellValue[];
}

export interface ScoreMatrixPage {
  revision: ScoreRevisionView;
  items: ScoreItemSnapshot[];
  rows: ScoreMatrixRow[];
  total: number;
  offset: number;
  limit: number;
  missingParticipantIds?: string[];
  missingCellCount: number;
  absentClassIds?: string[];
}

export interface ScoreCorrectionEntry {
  participantId: string;
  itemId: string;
  status: ScoreStatus;
  /** recorded 时必填；其余状态不得提供 */
  scoreText?: string | null;
}

export interface ScoreRevisionCorrectRequest {
  baseScoreRevisionId: string;
  expectedAssessmentRevision: number;
  submissionId: string;
  reason: string;
  corrections: ScoreCorrectionEntry[];
}

export interface ScoreRevisionCorrectResult {
  revisionId: string;
  baseRevisionId: string;
  version: number;
  assessmentRevision: number;
  activeScoreRevisionId: string;
  replayed?: boolean;
}
