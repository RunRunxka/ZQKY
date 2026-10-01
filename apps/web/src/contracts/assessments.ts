/**
 * 施测 v1 契约镜像（TEACHING-LOOP B2 / T30-b）。
 *
 * 与后端 `apps/api/app/contracts/assessments.py` 逐字段对应（camelCase）；
 * 姓名/学号快照一律由服务端按 studentId 读取后冻结，客户端不提供快照字段。
 */

import type { Attendance } from '@/contracts/roster';

export type AssessmentType = 'exam' | 'quiz' | 'practice';
export type AssessmentState = 'open' | 'closed' | 'archived';

export interface AssessmentParticipantInput {
  studentId: string;
  classId: string;
  attendance?: Attendance;
  attemptNo?: number | null;
  /** 历史归属未覆盖 heldOn 时的显式确认（服务端仍校验 classId 在 classIds 内） */
  classConfirmed?: boolean;
  classConfirmationNote?: string | null;
}

export interface AssessmentCreateRequest {
  submissionId: string;
  paperRevisionId: string;
  title: string;
  assessmentType?: AssessmentType;
  heldOn: string;
  classIds: string[];
  participants: AssessmentParticipantInput[];
}

export interface ParticipantAddRequest {
  submissionId: string;
  expectedRevision: number;
  participants: AssessmentParticipantInput[];
}

export interface AssessmentUpdateRequest {
  expectedRevision: number;
  title?: string | null;
  assessmentType?: AssessmentType | null;
  heldOn?: string | null;
}

export interface AssessmentParticipantView {
  participantId: string;
  studentId: string;
  studentNoSnapshot: string | null;
  nameSnapshot: string;
  classId: string;
  attemptNo: number;
  attendance: Attendance;
  classConfirmed: boolean;
  classConfirmationNote: string | null;
  classConfirmationAt: string | null;
}

export interface AssessmentView {
  assessmentId: string;
  paperRevisionId: string;
  paperId: string;
  paperTitle: string;
  subjectId: string;
  title: string;
  assessmentType: AssessmentType;
  heldOn: string;
  /** 当前生效成绩修订（B3/T60 起可写；null = 尚无正式成绩版本） */
  activeScoreRevisionId?: string | null;
  state: AssessmentState;
  revision: number;
  classIds: string[];
  participantCount: number;
  createdAt: string;
}

export interface AssessmentDetailView {
  assessment: AssessmentView;
  participants: AssessmentParticipantView[];
}

export interface AssessmentList {
  items: AssessmentView[];
  total: number;
  offset: number;
  limit: number;
}

export interface AssessmentCreateResult {
  assessment: AssessmentView;
  participants: AssessmentParticipantView[];
  replayed: boolean;
}

export interface ParticipantMutationResult {
  assessment: AssessmentView;
  participants: AssessmentParticipantView[];
  replayed: boolean;
}
