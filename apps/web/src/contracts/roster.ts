/**
 * 班级 / 学生 / 名单导入契约镜像（TEACHING-LOOP B1 / T30-a；R5-FE 取回最小子集）。
 *
 * 与后端 `apps/api/app/contracts/roster.py` 逐字段对应（camelCase）；修改任一侧必须同步另一侧。
 *
 * 重建期取回说明（R5-FE 2026-10-11）：本模块只做「班级管理」页（班级选择 + 学生名单增删改 +
 * xlsx/csv 名单导入校对）。归档契约里的施测相关形状（`ParticipantSnapshot` /
 * `AssessmentCreateRequest` / `ConfirmedPaperRevisionView` / `Attendance` / `AssessmentType`）
 * 属于后续「施测与成绩」批次，本文件不持有；`AssetRef` 来自模块公共最小契约
 * `@/contracts/assessments`（待 `@/contracts/teaching-loop` 回归后改回）。
 */

import type { ErrorIssue } from '@/contracts/api';
import type { AssetRef } from '@/contracts/assessments';

export type ClassStatus = 'active' | 'archived';
export type StudentStatus = 'active' | 'archived';
export type RosterImportState = 'uploaded' | 'reviewing' | 'confirmed' | 'failed' | 'cancelled';
export type RosterDecision = 'link' | 'create' | 'ignore';
export type RosterRowSuggestion =
  | 'link'
  | 'create'
  | 'name_mismatch'
  | 'no_student_no'
  | 'duplicate'
  | 'conflict';

export interface ClassView {
  id: string;
  code: string;
  name: string;
  schoolYear: string;
  gradeId: string;
  status: ClassStatus;
  revision: number;
  studentCount: number;
  createdAt: string;
}

export interface ClassList {
  items: ClassView[];
  total: number;
  offset: number;
  limit: number;
}

export interface ClassCreateRequest {
  code: string;
  name: string;
  schoolYear: string;
  gradeId: string;
}

export interface ClassUpdateRequest {
  expectedRevision: number;
  name?: string | null;
  schoolYear?: string | null;
  gradeId?: string | null;
}

/** 班级归档/恢复（对应后端 `ClassRevisionRequest`：只带乐观锁修订号，不携带内容）。 */
export interface ClassRevisionRequest {
  expectedRevision: number;
}

export interface StudentMembershipView {
  membershipId: string;
  classId: string;
  className: string;
  joinedOn: string;
  leftOn: string | null;
}

export interface StudentView {
  id: string;
  studentNo: string | null;
  name: string;
  status: StudentStatus;
  revision: number;
  memberships: StudentMembershipView[];
  createdAt: string;
  /**
   * 性别（R5-FE 参考图列）。
   *
   * **后端归档契约（`roster.py` 的 `StudentView`）没有这个字段**，本模块不做任何猜测：
   * 缺省一律显示「未记录」，`null`/`''` 同样显示「未记录」；只有服务端真的返回了值才展示原文。
   * 后端若在后续批次补上该字段，本行类型无需改动即可生效；若始终不补，该列恒为「未记录」。
   * 交付说明中列为未决问题（列保留 vs 后端补字段）。
   */
  gender?: string | null;
}

export interface StudentList {
  items: StudentView[];
  total: number;
  offset: number;
  limit: number;
}

export interface StudentCreateRequest {
  name: string;
  studentNo?: string | null;
  classId?: string | null;
  joinedOn?: string | null;
}

/** 编辑学生身份（姓名/学号）；`expectedRevision` 乐观锁，409 时保留本地编辑。 */
export interface StudentUpdateRequest {
  expectedRevision: number;
  name?: string | null;
  studentNo?: string | null;
}

/** 学生归档/恢复（对应后端 `StudentRevisionRequest`：与班级同形；归属历史保留）。 */
export interface StudentRevisionRequest {
  expectedRevision: number;
}

/**
 * 学生删除回执模式（R10-FE 冻结契约，`DELETE /students/{id}?expectedRevision=N` 的 200 体）。
 *
 * - `deleted`：该生没有被任何施测参测快照引用，连同归属记录物理删除；
 * - `removed_with_history`：该生有历史成绩引用，身份与归属从名单中移除，但历史成绩数据保留。
 */
export type StudentDeleteMode = 'deleted' | 'removed_with_history';

/**
 * 学生删除回执（200）：`message` 为服务端可读中文**原样展示**（不二次翻译）；
 * 失败（乐观锁 409 / 404）由调用方按既有错误区原样呈现。
 *
 * R10-BE（2026-10-13）：有历史成绩的学生不再返回 409（按 `removed_with_history`
 * 移除身份并保留历史）；`STUDENT_IN_USE` 已不是任何删除路径的响应，错误区仍防御性原样渲染。
 */
export interface StudentDeleteResult {
  mode: StudentDeleteMode;
  message: string;
}

export interface RosterImportRowView {
  rowNo: number;
  name: string;
  studentNo: string | null;
  matchedStudentId: string | null;
  matchedStudentName: string | null;
  suggestion: RosterRowSuggestion | null;
  decision: RosterDecision | null;
  issues: ErrorIssue[];
}

export interface RosterImportView {
  importId: string;
  classId: string;
  className: string;
  state: RosterImportState;
  revision: number;
  fileAsset: AssetRef;
  headers: string[];
  mapping: Record<string, string>;
  warnings: string[];
  issues: ErrorIssue[];
  rows: RosterImportRowView[];
  createdAt: string;
  updatedAt: string;
}

export interface RosterImportSummary {
  importId: string;
  classId: string;
  /** 只读派生：班名与上传原文件名；关联缺失时服务端给 null（不伪造名称）。 */
  className: string | null;
  uploadedFileName: string | null;
  state: RosterImportState;
  revision: number;
  rowCount: number;
  blockingIssueCount: number;
  createdAt: string;
  updatedAt: string;
}

/**
 * 彻底删除班级回执（200）：物理删除不可恢复；被引用时服务端 409 拒绝。
 * 引用计数形状见 `ClassReferenceCounts`（409 `CLASS_IN_USE` 的 `details.counts`）。
 */
export interface ClassDeleteResult {
  deleted: boolean;
  classId: string;
}

/** `CLASS_IN_USE` 的逐项引用计数（键与后端一致；未知键由界面原样列出，不隐藏）。 */
export interface ClassReferenceCounts {
  memberships: number;
  rosterImports: number;
  assessments: number;
  lessonPlans: number;
}

export interface RosterImportList {
  items: RosterImportSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface RosterImportRowPatch {
  rowNo: number;
  decision: RosterDecision;
  studentId?: string | null;
}

export interface RosterImportPatchRequest {
  expectedRevision: number;
  mapping?: Record<string, string> | null;
  rows?: RosterImportRowPatch[] | null;
}

/**
 * 放弃未确认名单批次（对应后端 `RosterImportDiscardRequest`）：
 * 只把状态置 `cancelled`；批次记录、原始文件与预览行保留。
 */
export interface RosterImportDiscardRequest {
  expectedRevision: number;
}

export interface RosterIdentityMatch {
  rowNo: number;
  action: RosterDecision;
  studentId?: string | null;
}

export interface RosterImportConfirmRequest {
  expectedRevision: number;
  submissionId: string;
  identityMatches?: RosterIdentityMatch[];
}

export interface RosterAppliedRow {
  rowNo: number;
  studentId: string;
  membershipId: string | null;
  createdStudent: boolean;
  createdMembership: boolean;
}

export interface RosterImportConfirmResult {
  importId: string;
  state: RosterImportState;
  applied: RosterAppliedRow[];
  ignored: number[];
  replayed: boolean;
}

/** 名单表字段（表头映射只允许这两个） */
export const ROSTER_IMPORT_FIELDS = ['studentNo', 'name'] as const;
