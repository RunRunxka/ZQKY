/**
 * `/assessments` 施测与成绩工作区客户端（TEACHING-LOOP B3 · F20-I）。
 *
 * 视图/请求体类型全部来自冻结契约：
 * - `@/contracts/scores`（CTRL 冻结的 TS 镜像，与 `app/contracts/scores.py` 逐字段对应）；
 * - `@/contracts/assessments`（施测）、`@/contracts/papers`（原卷）、`@/contracts/roster`（名单）。
 *
 * 本文件只做路径拼接与 JSON/multipart 编码：不复制第二份类型、不改写服务端语义、不把失败
 * 降级为空列表。失败统一抛 `ApiError`（`details.currentRevision` / `details.issues` 原样保留，
 * 供 409 保留编辑、422 行列定位使用）。
 *
 * `ScoreImportPatchRequest` 已由 CTRL 并入冻结契约 `@/contracts/scores`（B3 r2），本模块只再导出，
 * 不再持有第二份形状。
 *
 * 本批新增三个受引用守卫的 `DELETE`（班级/原卷/施测，`expectedRevision` 走查询参数）与
 * 批量添加学生 `POST /classes/{id}/students/batch`（`submissionId` 幂等）；
 * 409 的 `details.counts` 由调用方按契约逐项渲染，这里只做路径与编码。
 */

import { apiRequest, apiRequestBlob } from '@/services/api-client';
import type {
  AssessmentCreateRequest,
  AssessmentCreateResult,
  AssessmentDetailView,
  AssessmentList,
  AssessmentRevisionRequest,
  AssessmentUpdateRequest,
  AssessmentView,
  ParticipantAddRequest,
  ParticipantAttendanceRequest,
  ParticipantMutationResult,
} from '@/contracts/assessments';
import type {
  ClassCreateRequest, ClassDeleteResult, ClassList, ClassRevisionRequest, ClassView,
  BatchStudentAddRequest, BatchStudentAddResult,
  StudentCreateRequest, StudentList, StudentRevisionRequest, StudentView,
  MembershipTransferRequest, RosterImportView, RosterImportList, RosterImportPatchRequest,
  RosterImportConfirmRequest, RosterImportConfirmResult, RosterImportDiscardRequest,
} from '@/contracts/roster';
import type {
  PaperList,
  PaperDeleteResult,
  PaperRevisionContentView,
  PaperRevisionRequest,
  PaperView,
  PaperImportView, PaperDraftPatchRequest, PaperConfirmRequest, PaperConfirmResult,
  PaperProposalJobRequest, PaperProposalView, PaperProposalDecisionRequest,
} from '@/contracts/papers';
import type {
  AssessmentDeleteResult,
} from '@/contracts/assessments';
import type { JobView } from '@/contracts/teaching-loop';
import type {
  ScoreImportConfirmRequest,
  ScoreImportConfirmResult,
  ScoreImportDiscardRequest,
  ScoreImportList,
  ScoreImportRowList,
  ScoreImportPatchRequest,
  ScoreImportRefreshRequest,
  ScoreImportView,
  ScoreMatrixPage,
  ScoreRevisionCorrectRequest,
  ScoreRevisionCorrectResult,
  ScoreRevisionList,
  ScoreRevisionView,
} from '@/contracts/scores';

/* ------------------------------------------------------------------ 查询串与请求辅助 */

/**
 * 拼接查询串：只写有值的键（undefined/null/空串跳过），并做 URL 编码。
 * `boolean` 原样写成 `true`/`false`（false 不跳过：`archived=false` 是真实筛选，静默丢弃会丢语义）。
 */
export function assessmentsQuery(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  };
}

/* ------------------------------------------------------------------ 名单（班级 / 学生） */

export interface ClassQuery {
  status?: 'active' | 'archived';
  offset?: number;
  limit?: number;
}

export function listClasses(query: ClassQuery = {}, signal?: AbortSignal): Promise<ClassList> {
  return apiRequest<ClassList>(
    `/classes${assessmentsQuery({
      status: query.status,
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

/** 新建班级（201）；同学年下 code 冲突由服务端 409 拒绝。 */
export function createClass(body: ClassCreateRequest): Promise<ClassView> {
  return apiRequest<ClassView>('/classes', jsonInit('POST', body));
}

/** 归档班级：`expectedRevision` 守卫；归档仍可读，归属历史保留。 */
export function archiveClass(classId: string, body: ClassRevisionRequest): Promise<ClassView> {
  return apiRequest<ClassView>(
    `/classes/${encodeURIComponent(classId)}/archive`,
    jsonInit('POST', body),
  );
}

export function restoreClass(classId: string, body: ClassRevisionRequest): Promise<ClassView> {
  return apiRequest<ClassView>(
    `/classes/${encodeURIComponent(classId)}/restore`,
    jsonInit('POST', body),
  );
}

/**
 * 彻底删除班级（受引用守卫的物理删除）：`expectedRevision` 走查询参数。
 * 任一引用 >0 → 409 `CLASS_IN_USE` + `details.counts.{memberships,rosterImports,assessments,lessonPlans}`；
 * 乐观锁不符 → 409；不存在 → 404。归档班级同样受守卫（不会因归档而可删）。
 */
export function deleteClass(classId: string, expectedRevision: number): Promise<ClassDeleteResult> {
  return apiRequest<ClassDeleteResult>(
    `/classes/${encodeURIComponent(classId)}${assessmentsQuery({ expectedRevision })}`,
    { method: 'DELETE' },
  );
}

/**
 * 批量添加学生（`submissionId` 幂等：同标识同载荷重放返回原结果）：
 * 单事务逐行处理；学号已存在跳过并说明；行非法 422 + `details.issues[].row`（0 基）整批回滚。
 */
export function batchAddStudents(
  classId: string,
  body: BatchStudentAddRequest,
): Promise<BatchStudentAddResult> {
  return apiRequest<BatchStudentAddResult>(
    `/classes/${encodeURIComponent(classId)}/students/batch`,
    jsonInit('POST', body),
  );
}

/**
 * 该班成员（含归属历史）。
 * - 旧签名 `listClassStudents(classId, signal)` 保留；
 * - `options.includeArchived === true` 才带 `includeArchived=true`（缺省不传，服务端默认只看活跃）。
 */
export function listClassStudents(classId: string, signal?: AbortSignal): Promise<StudentList>;
export function listClassStudents(
  classId: string,
  options?: { includeArchived?: boolean },
  signal?: AbortSignal,
): Promise<StudentList>;
export function listClassStudents(
  classId: string,
  optionsOrSignal: { includeArchived?: boolean } | AbortSignal = {},
  signal?: AbortSignal,
): Promise<StudentList> {
  const [options, actualSignal] = splitClassStudentsArgs(optionsOrSignal, signal);
  return apiRequest<StudentList>(
    `/classes/${encodeURIComponent(classId)}/students${assessmentsQuery({
      includeArchived: options.includeArchived ? true : undefined,
    })}`,
    { signal: actualSignal },
  );
}

/** 拆分第二参数：AbortSignal（旧调用）与 options（新调用）语义分开，互不混淆。 */
function splitClassStudentsArgs(
  optionsOrSignal: { includeArchived?: boolean } | AbortSignal,
  signal?: AbortSignal,
): [{ includeArchived?: boolean }, AbortSignal | undefined] {
  if (isAbortSignal(optionsOrSignal)) return [{}, optionsOrSignal];
  return [optionsOrSignal, signal];
}

function isAbortSignal(value: unknown): value is AbortSignal {
  return (
    typeof value === 'object' &&
    value !== null &&
    'aborted' in value &&
    'addEventListener' in value
  );
}

export interface StudentQuery {
  q?: string;
  /** 学生状态筛选（缺省不传 = 服务端默认口径） */
  status?: 'active' | 'archived';
  offset?: number;
  limit?: number;
}

export function listStudents(query: StudentQuery = {}, signal?: AbortSignal): Promise<StudentList> {
  return apiRequest<StudentList>(
    `/students${assessmentsQuery({
      q: query.q,
      status: query.status,
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

/** 建立学生身份；`classId` 给定时同时建立该班归属（学号按文本保存，保留前导零）。 */
export function createStudent(body: StudentCreateRequest): Promise<StudentView> {
  return apiRequest<StudentView>('/students', jsonInit('POST', body));
}

export function transferStudent(studentId: string, body: MembershipTransferRequest): Promise<StudentView> {
  return apiRequest<StudentView>(`/students/${encodeURIComponent(studentId)}/transfer`, jsonInit('POST', body));
}

/** 归档学生：`expectedRevision` 守卫；归属历史保留。 */
export function archiveStudent(studentId: string, body: StudentRevisionRequest): Promise<StudentView> {
  return apiRequest<StudentView>(
    `/students/${encodeURIComponent(studentId)}/archive`,
    jsonInit('POST', body),
  );
}

export function restoreStudent(studentId: string, body: StudentRevisionRequest): Promise<StudentView> {
  return apiRequest<StudentView>(
    `/students/${encodeURIComponent(studentId)}/restore`,
    jsonInit('POST', body),
  );
}

export function createRosterImport(classId: string, file: File, meta: { sheetName?: string; mapping?: Record<string, string> } = {}, signal?: AbortSignal): Promise<RosterImportView> {
  const form = new FormData();
  form.append('file', file);
  if (meta.sheetName) form.append('sheetName', meta.sheetName);
  if (meta.mapping) form.append('mappingJson', JSON.stringify(meta.mapping));
  return apiRequest<RosterImportView>(`/classes/${encodeURIComponent(classId)}/roster-imports`, { method: 'POST', body: form, signal });
}

export function listRosterImports(query: { classId?: string; state?: string; offset?: number; limit?: number } = {}, signal?: AbortSignal): Promise<RosterImportList> {
  return apiRequest<RosterImportList>(`/roster-imports${assessmentsQuery(query)}`, { signal });
}

export function getRosterImport(importId: string, signal?: AbortSignal): Promise<RosterImportView> {
  return apiRequest<RosterImportView>(`/roster-imports/${encodeURIComponent(importId)}`, { signal });
}

export function patchRosterImport(importId: string, body: RosterImportPatchRequest): Promise<RosterImportView> {
  return apiRequest<RosterImportView>(`/roster-imports/${encodeURIComponent(importId)}`, jsonInit('PATCH', body));
}

export function confirmRosterImport(importId: string, body: RosterImportConfirmRequest): Promise<RosterImportConfirmResult> {
  return apiRequest<RosterImportConfirmResult>(`/roster-imports/${encodeURIComponent(importId)}/confirm`, jsonInit('POST', body));
}

/** 放弃未确认批次：只置 `state=cancelled`；记录/原始文件/预览行保留（可读，不删除）。 */
export function discardRosterImport(importId: string, body: RosterImportDiscardRequest): Promise<RosterImportView> {
  return apiRequest<RosterImportView>(`/roster-imports/${encodeURIComponent(importId)}/discard`, jsonInit('POST', body));
}

/* ------------------------------------------------------------------ 原卷（只读选用） */

export interface PaperQuery {
  status?: 'active' | 'archived';
  offset?: number;
  limit?: number;
}

export function listPapers(query: PaperQuery = {}, signal?: AbortSignal): Promise<PaperList> {
  return apiRequest<PaperList>(
    `/papers${assessmentsQuery({
      status: query.status,
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

export function getPaper(paperId: string, signal?: AbortSignal): Promise<PaperView> {
  return apiRequest<PaperView>(`/papers/${encodeURIComponent(paperId)}`, { signal });
}

/**
 * 固定修订内容（含计分叶与共享材料块）。
 * 成绩列映射用它的 `items` 计算计分叶集合（`isScored` 且无计分子项）。
 */
export function getPaperRevisionContent(
  paperId: string,
  revisionId: string,
  signal?: AbortSignal,
): Promise<PaperRevisionContentView> {
  return apiRequest<PaperRevisionContentView>(
    `/papers/${encodeURIComponent(paperId)}/revisions/${encodeURIComponent(revisionId)}/content`,
    { signal },
  );
}

/** 归档原卷：`expectedRevision` 守卫；历史引用（施测/成绩）保留。 */
export function archivePaper(paperId: string, body: PaperRevisionRequest): Promise<PaperView> {
  return apiRequest<PaperView>(
    `/papers/${encodeURIComponent(paperId)}/archive`,
    jsonInit('POST', body),
  );
}

export function restorePaper(paperId: string, body: PaperRevisionRequest): Promise<PaperView> {
  return apiRequest<PaperView>(
    `/papers/${encodeURIComponent(paperId)}/restore`,
    jsonInit('POST', body),
  );
}

/**
 * 彻底删除原卷（受引用守卫的物理删除）：`expectedRevision` 走查询参数。
 * 被施测引用 → 409 `PAPER_IN_USE` + `details.counts.assessments`；
 * 有已确认修订 → 409 `PAPER_HAS_CONFIRMED_REVISION` + `details.counts.confirmedRevisions`（只能归档）；
 * 乐观锁不符 → 409；不存在 → 404。
 */
export function deletePaper(paperId: string, expectedRevision: number): Promise<PaperDeleteResult> {
  return apiRequest<PaperDeleteResult>(
    `/papers/${encodeURIComponent(paperId)}${assessmentsQuery({ expectedRevision })}`,
    { method: 'DELETE' },
  );
}

/* ------------------------------------------------------------------ 施测 */

export interface AssessmentQuery {
  subjectId?: string;
  classId?: string;
  state?: 'open' | 'closed' | 'archived';
  offset?: number;
  limit?: number;
}

export function listAssessments(
  query: AssessmentQuery = {},
  signal?: AbortSignal,
): Promise<AssessmentList> {
  return apiRequest<AssessmentList>(
    `/assessments${assessmentsQuery({
      subjectId: query.subjectId,
      classId: query.classId,
      state: query.state,
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

/** 真实创建施测（201）；只接受已确认原卷修订，`submissionId` 幂等。 */
export function createAssessment(body: AssessmentCreateRequest): Promise<AssessmentCreateResult> {
  return apiRequest<AssessmentCreateResult>('/assessments', jsonInit('POST', body));
}

export function getAssessment(
  assessmentId: string,
  signal?: AbortSignal,
): Promise<AssessmentDetailView> {
  return apiRequest<AssessmentDetailView>(`/assessments/${encodeURIComponent(assessmentId)}`, {
    signal,
  });
}

/** 标题/类型/日期（`expectedRevision` 守卫；日期变更由服务端逐人次重核归属）。 */
export function updateAssessment(
  assessmentId: string,
  body: AssessmentUpdateRequest,
): Promise<AssessmentView> {
  return apiRequest<AssessmentView>(
    `/assessments/${encodeURIComponent(assessmentId)}`,
    jsonInit('PATCH', body),
  );
}

/** 补录/补考人次（不覆盖既有记录）。 */
export function addAssessmentParticipants(
  assessmentId: string,
  body: ParticipantAddRequest,
): Promise<ParticipantMutationResult> {
  return apiRequest<ParticipantMutationResult>(
    `/assessments/${encodeURIComponent(assessmentId)}/participants`,
    jsonInit('POST', body),
  );
}

/**
 * 移除误录人次（守卫式）：`expectedRevision` 走查询参数；
 * 已有成绩版本/导入引用/学情报告时服务端 409 拒绝，不静默删除。
 */
export function removeAssessmentParticipant(
  assessmentId: string,
  participantId: string,
  expectedRevision: number,
): Promise<ParticipantMutationResult> {
  return apiRequest<ParticipantMutationResult>(
    `/assessments/${encodeURIComponent(assessmentId)}/participants/${encodeURIComponent(
      participantId,
    )}${assessmentsQuery({ expectedRevision })}`,
    { method: 'DELETE' },
  );
}

/** 归档施测：`expectedRevision` 守卫；已封存成绩与报告保留，归档仍可读。 */
export function archiveAssessment(
  assessmentId: string,
  body: AssessmentRevisionRequest,
): Promise<AssessmentView> {
  return apiRequest<AssessmentView>(
    `/assessments/${encodeURIComponent(assessmentId)}/archive`,
    jsonInit('POST', body),
  );
}

export function restoreAssessment(
  assessmentId: string,
  body: AssessmentRevisionRequest,
): Promise<AssessmentView> {
  return apiRequest<AssessmentView>(
    `/assessments/${encodeURIComponent(assessmentId)}/restore`,
    jsonInit('POST', body),
  );
}

/**
 * 彻底删除施测（受引用守卫的物理删除）：`expectedRevision` 走查询参数。
 * 任一引用 >0 → 409 `ASSESSMENT_IN_USE` +
 * `details.counts.{scoreRevisions,scoreImports,analysisRuns,practiceConversions}`；
 * 乐观锁不符 → 409；不存在 → 404。归档施测同样受守卫（不会因归档而可删）。
 */
export function deleteAssessment(
  assessmentId: string,
  expectedRevision: number,
): Promise<AssessmentDeleteResult> {
  return apiRequest<AssessmentDeleteResult>(
    `/assessments/${encodeURIComponent(assessmentId)}${assessmentsQuery({ expectedRevision })}`,
    { method: 'DELETE' },
  );
}

/* ------------------------------------------------------------------ 成绩导入 */

export function correctParticipantAttendance(
  assessmentId: string,
  participantId: string,
  body: ParticipantAttendanceRequest,
): Promise<ParticipantMutationResult> {
  return apiRequest<ParticipantMutationResult>(
    `/assessments/${encodeURIComponent(assessmentId)}/participants/${encodeURIComponent(participantId)}/attendance`,
    jsonInit('PATCH', body),
  );
}

export function createPaperImport(file: File, meta: { subjectId: string; title?: string }, signal?: AbortSignal): Promise<PaperImportView> {
  const form = new FormData();
  form.append('file', file);
  form.append('subjectId', meta.subjectId);
  if (meta.title) form.append('title', meta.title);
  return apiRequest<PaperImportView>('/paper-imports', { method: 'POST', body: form, signal });
}

export function patchPaperDraft(paperId: string, body: PaperDraftPatchRequest): Promise<PaperRevisionContentView> {
  return apiRequest<PaperRevisionContentView>(`/papers/${encodeURIComponent(paperId)}/draft`, jsonInit('PATCH', body));
}

export function confirmPaper(paperId: string, body: PaperConfirmRequest): Promise<PaperConfirmResult> {
  return apiRequest<PaperConfirmResult>(`/papers/${encodeURIComponent(paperId)}/confirm`, jsonInit('POST', body));
}

export function getPaperAsset(paperId: string, revisionId: string, assetId: string, signal?: AbortSignal) {
  return apiRequestBlob(`/papers/${encodeURIComponent(paperId)}/revisions/${encodeURIComponent(revisionId)}/assets/${encodeURIComponent(assetId)}/content`, { signal });
}

export function createPaperProposal(paperId: string, body: PaperProposalJobRequest): Promise<JobView> {
  return apiRequest<JobView>(`/papers/${encodeURIComponent(paperId)}/knowledge-proposals`, jsonInit('POST', body));
}

export function getPaperProposal(proposalId: string, signal?: AbortSignal): Promise<PaperProposalView> {
  return apiRequest<PaperProposalView>(`/paper-proposals/${encodeURIComponent(proposalId)}`, { signal });
}

export function applyPaperProposal(proposalId: string, body: PaperProposalDecisionRequest): Promise<PaperRevisionContentView> {
  return apiRequest<PaperRevisionContentView>(`/paper-proposals/${encodeURIComponent(proposalId)}/apply`, jsonInit('POST', body));
}

export function rejectPaperProposal(proposalId: string, body: PaperProposalDecisionRequest): Promise<PaperProposalView> {
  return apiRequest<PaperProposalView>(`/paper-proposals/${encodeURIComponent(proposalId)}/reject`, jsonInit('POST', body));
}

export function refreshScoreImport(
  importId: string,
  body: ScoreImportRefreshRequest,
): Promise<ScoreImportView> {
  return apiRequest<ScoreImportView>(
    `/score-imports/${encodeURIComponent(importId)}/refresh`,
    jsonInit('POST', body),
  );
}

export interface ScoreImportCreateMeta {
  /** 多工作表 XLSX 指定工作表名；缺省由服务端选用。 */
  workSheet?: string | null;
  /** 本次导入所基于的正式成绩版本；首个版本为 null（不提供）。 */
  baseScoreRevisionId?: string | null;
}

/**
 * 上传成绩表（.xlsx/.csv）创建待校对批次（multipart）。
 * 不手写 content-type，交给 fetch 生成 multipart boundary。
 */
export function createScoreImport(
  assessmentId: string,
  file: File,
  meta: ScoreImportCreateMeta = {},
  signal?: AbortSignal,
): Promise<ScoreImportView> {
  const form = new FormData();
  form.append('file', file);
  if (meta.workSheet) form.append('workSheet', meta.workSheet);
  if (meta.baseScoreRevisionId) form.append('baseScoreRevisionId', meta.baseScoreRevisionId);
  return apiRequest<ScoreImportView>(
    `/assessments/${encodeURIComponent(assessmentId)}/score-imports`,
    { method: 'POST', body: form, signal },
  );
}

export interface ScoreImportQuery {
  assessmentId?: string;
  offset?: number;
  limit?: number;
}

export function listScoreImports(
  query: ScoreImportQuery = {},
  signal?: AbortSignal,
): Promise<ScoreImportList> {
  return apiRequest<ScoreImportList>(
    `/score-imports${assessmentsQuery({
      assessmentId: query.assessmentId,
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

export function getScoreImport(importId: string, signal?: AbortSignal): Promise<ScoreImportView> {
  return apiRequest<ScoreImportView>(`/score-imports/${encodeURIComponent(importId)}`, { signal });
}

/** 原表行分页；`cells` 带物理坐标（行号 + 列字母）。 */
export function listScoreImportRows(
  importId: string,
  query: { offset?: number; limit?: number } = {},
  signal?: AbortSignal,
): Promise<ScoreImportRowList> {
  return apiRequest<ScoreImportRowList>(
    `/score-imports/${encodeURIComponent(importId)}/rows${assessmentsQuery({
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

export type { ScoreImportPatchRequest } from '@/contracts/scores';

/** 改映射 / 行定位 / 单元格校正；返回重算后的权威批次视图（revision 与 previewVersion 递增）。 */
export function patchScoreImport(
  importId: string,
  body: ScoreImportPatchRequest,
): Promise<ScoreImportView> {
  return apiRequest<ScoreImportView>(
    `/score-imports/${encodeURIComponent(importId)}`,
    jsonInit('PATCH', body),
  );
}

/**
 * 整批确认（幂等 `submissionId`）：同标识同载荷重放返回原结果（`replayed=true`）。
 * 三个版本字段互不替代，任一不符 409；承认内容必须与预览一致，否则 422。
 */
export function confirmScoreImport(
  importId: string,
  body: ScoreImportConfirmRequest,
): Promise<ScoreImportConfirmResult> {
  return apiRequest<ScoreImportConfirmResult>(
    `/score-imports/${encodeURIComponent(importId)}/confirm`,
    jsonInit('POST', body),
  );
}

/** 放弃未确认成绩批次：只置 `state=cancelled`；批次记录/原始文件/预览行保留。 */
export function discardScoreImport(
  importId: string,
  body: ScoreImportDiscardRequest,
): Promise<ScoreImportView> {
  return apiRequest<ScoreImportView>(
    `/score-imports/${encodeURIComponent(importId)}/discard`,
    jsonInit('POST', body),
  );
}

/* ------------------------------------------------------------------ 成绩修订与矩阵 */

export function listScoreRevisions(
  assessmentId: string,
  signal?: AbortSignal,
): Promise<ScoreRevisionList> {
  return apiRequest<ScoreRevisionList>(
    `/assessments/${encodeURIComponent(assessmentId)}/score-revisions`,
    { signal },
  );
}

export function getScoreRevision(
  revisionId: string,
  signal?: AbortSignal,
): Promise<ScoreRevisionView> {
  return apiRequest<ScoreRevisionView>(
    `/score-revisions/${encodeURIComponent(revisionId)}`,
    { signal },
  );
}

/** 只读矩阵：`items` 不分页（固定计分叶），`rows` 分页。 */
export function getScoreMatrix(
  revisionId: string,
  query: { offset?: number; limit?: number } = {},
  signal?: AbortSignal,
): Promise<ScoreMatrixPage> {
  return apiRequest<ScoreMatrixPage>(
    `/score-revisions/${encodeURIComponent(revisionId)}/matrix${assessmentsQuery({
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

/** 修正 = 从不可变 base 复制全矩阵 + 当时快照生成新完整版本；`submissionId` 幂等。 */
export function correctScoreRevision(
  assessmentId: string,
  body: ScoreRevisionCorrectRequest,
): Promise<ScoreRevisionCorrectResult> {
  return apiRequest<ScoreRevisionCorrectResult>(
    `/assessments/${encodeURIComponent(assessmentId)}/score-revisions/correct`,
    jsonInit('POST', body),
  );
}
