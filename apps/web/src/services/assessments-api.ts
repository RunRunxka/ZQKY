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
 */

import { apiRequest } from '@/services/api-client';
import type {
  AssessmentCreateRequest,
  AssessmentCreateResult,
  AssessmentDetailView,
  AssessmentList,
  AssessmentUpdateRequest,
  AssessmentView,
  ParticipantAddRequest,
  ParticipantMutationResult,
} from '@/contracts/assessments';
import type { ClassCreateRequest, ClassList, ClassView, StudentCreateRequest, StudentList, StudentView } from '@/contracts/roster';
import type {
  PaperList,
  PaperRevisionContentView,
  PaperView,
} from '@/contracts/papers';
import type {
  ScoreImportConfirmRequest,
  ScoreImportConfirmResult,
  ScoreImportList,
  ScoreImportRowList,
  ScoreImportPatchRequest,
  ScoreImportView,
  ScoreMatrixPage,
  ScoreRevisionCorrectRequest,
  ScoreRevisionCorrectResult,
  ScoreRevisionList,
  ScoreRevisionView,
} from '@/contracts/scores';

/* ------------------------------------------------------------------ 查询串与请求辅助 */

/** 拼接查询串：只写有值的键（undefined/null/空串跳过），并做 URL 编码。 */
export function assessmentsQuery(
  params: Record<string, string | number | undefined | null>,
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

/** 该班活跃成员（含归属历史）。 */
export function listClassStudents(classId: string, signal?: AbortSignal): Promise<StudentList> {
  return apiRequest<StudentList>(`/classes/${encodeURIComponent(classId)}/students`, { signal });
}

export interface StudentQuery {
  q?: string;
  offset?: number;
  limit?: number;
}

export function listStudents(query: StudentQuery = {}, signal?: AbortSignal): Promise<StudentList> {
  return apiRequest<StudentList>(
    `/students${assessmentsQuery({ q: query.q, offset: query.offset, limit: query.limit })}`,
    { signal },
  );
}

/** 建立学生身份；`classId` 给定时同时建立该班归属（学号按文本保存，保留前导零）。 */
export function createStudent(body: StudentCreateRequest): Promise<StudentView> {
  return apiRequest<StudentView>('/students', jsonInit('POST', body));
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

/* ------------------------------------------------------------------ 成绩导入 */

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
