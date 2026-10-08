/**
 * 班级 / 学生 / 名单导入 / 施测契约镜像（TEACHING-LOOP B1 / T30-a）。
 *
 * 与后端 `apps/api/app/contracts/roster.py` 逐字段对应（camelCase）；
 * 修改任一侧必须同步另一侧。施测真实创建 = T30-b（本批只冻结形状）。
 */

import type { ErrorIssue } from '@/contracts/api';
import type { AssetRef } from '@/contracts/teaching-loop';

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
export type Attendance = 'present' | 'absent' | 'exempt';
export type AssessmentType = 'exam' | 'quiz' | 'practice';

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

export interface StudentUpdateRequest {
  expectedRevision: number;
  name?: string | null;
  studentNo?: string | null;
}

/** 学生归档/恢复（对应后端 `StudentRevisionRequest`：与班级同形；归属历史保留）。 */
export interface StudentRevisionRequest {
  expectedRevision: number;
}

export interface MembershipTransferRequest {
  expectedStudentRevision: number;
  fromClassId: string;
  toClassId: string;
  movedOn: string;
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

/**
 * 批量添加学生（对应后端 `BatchStudentAddRequest`）：`submissionId` 幂等，1..200 行。
 * `studentNo` 可空（无学号显式建档）；行级非法由服务端 422 + `details.issues[].row` 定位。
 */
export interface BatchStudentItem {
  studentNo?: string | null;
  name: string;
}

export interface BatchStudentAddRequest {
  submissionId: string;
  items: BatchStudentItem[];
  joinedOn?: string | null;
}

/** 被跳过的行：`index` 是请求 `items` 的 0 基下标（学号已存在时附既有学生）。 */
export interface BatchStudentSkippedRow {
  index: number;
  reason: string;
  code: string;
  existingStudentId?: string | null;
  existingName?: string | null;
}

export interface BatchStudentAddResult {
  created: StudentView[];
  skipped: BatchStudentSkippedRow[];
  replayed: boolean;
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

export interface ParticipantSnapshot {
  studentId: string;
  studentNo: string | null;
  name: string;
  classId: string;
  attemptNo: number;
  attendance: Attendance;
}

export interface AssessmentCreateRequest {
  paperRevisionId: string;
  title: string;
  assessmentType: AssessmentType;
  heldOn: string;
  classIds: string[];
  participants: ParticipantSnapshot[];
}

export interface ConfirmedPaperRevisionView {
  paperId: string;
  paperRevisionId: string;
  title: string;
  subjectId: string;
  totalScoreUnits: number;
  scoredLeafCount: number;
}

/** 名单表字段（表头映射只允许这两个） */
export const ROSTER_IMPORT_FIELDS = ['studentNo', 'name'] as const;
