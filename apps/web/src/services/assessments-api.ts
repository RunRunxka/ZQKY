/**
 * `/assessments/**` 施测与成绩模块客户端（TEACHING-LOOP B3 · F20-I；R5-FE 取回最小子集）。
 *
 * 视图/请求体类型全部来自模块契约镜像：
 * - `@/contracts/roster`（班级 / 学生 / 名单导入，对应 `app/contracts/roster.py`）；
 * - `@/contracts/papers`（原卷 / 知识点建议，对应 `app/contracts/papers.py`）；
 * - `@/contracts/assessments`（模块公共最小子集：任务视图）。
 *
 * 本文件只做路径拼接与 JSON/multipart 编码：不复制第二份类型、不改写服务端语义、**不把失败
 * 降级为空列表**。失败统一抛 `ApiError`（`details.currentRevision` / `details.issues` /
 * `details.counts` 原样保留，供 409 保留编辑、422 行列定位、守卫原因清单使用）。
 *
 * R10-FE（2026-10-12，用户裁定「舍弃所有归档功能，只留删除」）：归档/恢复客户端函数
 * （班级/学生/试卷的 `/archive` 与 `/restore`）已从本文件移除；删除改为携带 `expectedRevision`
 * 查询参数的物理删除，学生删除按 `StudentDeleteResult` 的两种模式回执呈现。
 *
 * 重建期范围（R5-FE 2026-10-11）：本模块只做「班级管理」与「试卷管理」两页，因此归档客户端里
 * 的施测（`/assessments*`）与成绩（`/score-*`、`/score-revisions*`）部分不在本文件——
 * 它们属于后续批次，随该批次的页面一并取回，避免出现无人调用的第二套客户端。
 */

import { apiRequest } from '@/services/api-client';
import type {
  ClassCreateRequest,
  ClassDeleteResult,
  ClassList,
  ClassView,
  RosterImportConfirmRequest,
  RosterImportConfirmResult,
  RosterImportDiscardRequest,
  RosterImportList,
  RosterImportPatchRequest,
  RosterImportView,
  StudentCreateRequest,
  StudentDeleteResult,
  StudentList,
  StudentUpdateRequest,
  StudentView,
} from '@/contracts/roster';
import type {
  KnowledgeDistributionBucket,
  PaperConfirmRequest,
  PaperConfirmResult,
  PaperDeleteResult,
  PaperDraftPatchRequest,
  PaperImportView,
  PaperList,
  PaperProposalDecisionRequest,
  PaperProposalJobRequest,
  PaperProposalView,
  PaperRevisionContentView,
  PaperView,
} from '@/contracts/papers';
import type { TeachingJobView } from '@/contracts/assessments';

/* ------------------------------------------------------------------ 查询串与请求辅助 */

/**
 * 拼接查询串：只写有值的键（undefined/null/空串跳过），并做 URL 编码。
 * `boolean` 原样写成 `true`/`false`（false 不跳过：`includeArchived=false` 是真实筛选，
 * 静默丢弃会丢语义）。
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

/* ------------------------------------------------------------------ 班级 */

export interface ClassQuery {
  offset?: number;
  limit?: number;
}

export function listClasses(query: ClassQuery = {}, signal?: AbortSignal): Promise<ClassList> {
  return apiRequest<ClassList>(
    `/classes${assessmentsQuery({
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

/**
 * 彻底删除班级（受引用守卫的物理删除）：`expectedRevision` 走查询参数。
 * 任一引用 >0 → 409 `CLASS_IN_USE` + `details.counts.{memberships,rosterImports,assessments,lessonPlans}`；
 * 乐观锁不符 → 409；不存在 → 404。**不做归档**：归档能力已从界面与客户端移除（R10-FE）。
 */
export function deleteClass(classId: string, expectedRevision: number): Promise<ClassDeleteResult> {
  return apiRequest<ClassDeleteResult>(
    `/classes/${encodeURIComponent(classId)}${assessmentsQuery({ expectedRevision })}`,
    { method: 'DELETE' },
  );
}

/**
 * 该班成员（含归属历史）。
 * 服务端 `GET /classes/{id}/students` 只有 `includeArchived` 一个筛选参数、**没有分页参数**：
 * 返回的是本班成员全集（`StudentList.total` 即全班人数）。页面的搜索与翻页因此是**视图层**
 * 对真实全集的筛选，不改变服务端口径，也不把「本页」当成「全部」。
 */
export function listClassStudents(
  classId: string,
  options: { includeArchived?: boolean } = {},
  signal?: AbortSignal,
): Promise<StudentList> {
  return apiRequest<StudentList>(
    `/classes/${encodeURIComponent(classId)}/students${assessmentsQuery({
      includeArchived: options.includeArchived ? true : undefined,
    })}`,
    { signal },
  );
}

/* ------------------------------------------------------------------ 学生 */

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

/** 编辑学生身份（姓名/学号）；409 版本冲突时调用方保留本地编辑并提示刷新对照。 */
export function updateStudent(
  studentId: string,
  body: StudentUpdateRequest,
): Promise<StudentView> {
  return apiRequest<StudentView>(`/students/${encodeURIComponent(studentId)}`, jsonInit('PATCH', body));
}

/**
 * 彻底删除学生（R10-FE 冻结契约）：`expectedRevision` 走查询参数。
 *
 * 200 回执 `{mode, message}` 两种模式都要原样呈现：
 * - `deleted`：无参测引用，连同归属记录物理删除；
 * - `removed_with_history`：有历史成绩引用，移除身份/归属但保留历史数据。
 * 乐观锁不符 → 409（R10-BE：有历史成绩不再 409）；调用方对任何 409 原样展示。
 * **不做归档**：归档/恢复能力已从界面与客户端移除。
 */
export function deleteStudent(
  studentId: string,
  expectedRevision: number,
): Promise<StudentDeleteResult> {
  return apiRequest<StudentDeleteResult>(
    `/students/${encodeURIComponent(studentId)}${assessmentsQuery({ expectedRevision })}`,
    { method: 'DELETE' },
  );
}

/* ------------------------------------------------------------------ 名单导入 */

export function createRosterImport(
  classId: string,
  file: File,
  meta: { sheetName?: string; mapping?: Record<string, string> } = {},
  signal?: AbortSignal,
): Promise<RosterImportView> {
  const form = new FormData();
  form.append('file', file);
  if (meta.sheetName) form.append('sheetName', meta.sheetName);
  if (meta.mapping) form.append('mappingJson', JSON.stringify(meta.mapping));
  return apiRequest<RosterImportView>(`/classes/${encodeURIComponent(classId)}/roster-imports`, {
    method: 'POST',
    body: form,
    signal,
  });
}

export function listRosterImports(
  query: { classId?: string; state?: string; offset?: number; limit?: number } = {},
  signal?: AbortSignal,
): Promise<RosterImportList> {
  return apiRequest<RosterImportList>(`/roster-imports${assessmentsQuery(query)}`, { signal });
}

export function getRosterImport(importId: string, signal?: AbortSignal): Promise<RosterImportView> {
  return apiRequest<RosterImportView>(`/roster-imports/${encodeURIComponent(importId)}`, { signal });
}

export function patchRosterImport(
  importId: string,
  body: RosterImportPatchRequest,
): Promise<RosterImportView> {
  return apiRequest<RosterImportView>(`/roster-imports/${encodeURIComponent(importId)}`, jsonInit('PATCH', body));
}

export function confirmRosterImport(
  importId: string,
  body: RosterImportConfirmRequest,
): Promise<RosterImportConfirmResult> {
  return apiRequest<RosterImportConfirmResult>(
    `/roster-imports/${encodeURIComponent(importId)}/confirm`,
    jsonInit('POST', body),
  );
}

/** 放弃未确认批次：只置 `state=cancelled`；记录/原始文件/预览行保留（可读，不删除）。 */
export function discardRosterImport(
  importId: string,
  body: RosterImportDiscardRequest,
): Promise<RosterImportView> {
  return apiRequest<RosterImportView>(
    `/roster-imports/${encodeURIComponent(importId)}/discard`,
    jsonInit('POST', body),
  );
}

/* ------------------------------------------------------------------ 试卷 */

export interface PaperQuery {
  offset?: number;
  limit?: number;
}

export function listPapers(query: PaperQuery = {}, signal?: AbortSignal): Promise<PaperList> {
  return apiRequest<PaperList>(
    `/papers${assessmentsQuery({
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

export function getPaper(paperId: string, signal?: AbortSignal): Promise<PaperView> {
  return apiRequest<PaperView>(`/papers/${encodeURIComponent(paperId)}`, { signal });
}

/** 固定修订内容（含小题与原文块）。本模块只用它的**结构**（题号/分值/知识点/块处置），不渲染原文。 */
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

/**
 * 彻底删除试卷（R10-BE 拆开交叉引用）：`expectedRevision` 走查询参数。
 * 被施测引用 → 409 `PAPER_IN_USE` + `details.counts.assessments`（先删施测，再删原卷）；
 * 已确认修订不再阻断（随原卷级联删除）；
 * 乐观锁不符 → 409；不存在 → 404。**不做归档**：归档能力已从界面与客户端移除（R10-FE）。
 */
export function deletePaper(paperId: string, expectedRevision: number): Promise<PaperDeleteResult> {
  return apiRequest<PaperDeleteResult>(
    `/papers/${encodeURIComponent(paperId)}${assessmentsQuery({ expectedRevision })}`,
    { method: 'DELETE' },
  );
}

/** 上传原卷（DOCX/PDF 文本层）创建校对草稿（multipart，不手写 content-type）。 */
export function createPaperImport(
  file: File,
  meta: { subjectId: string; title?: string },
  signal?: AbortSignal,
): Promise<PaperImportView> {
  const form = new FormData();
  form.append('file', file);
  form.append('subjectId', meta.subjectId);
  if (meta.title) form.append('title', meta.title);
  return apiRequest<PaperImportView>('/paper-imports', { method: 'POST', body: form, signal });
}

/** 保存校对草稿（`expectedRevision` 守卫；409 时调用方保留编辑）。 */
export function patchPaperDraft(
  paperId: string,
  body: PaperDraftPatchRequest,
): Promise<PaperRevisionContentView> {
  return apiRequest<PaperRevisionContentView>(`/papers/${encodeURIComponent(paperId)}/draft`, jsonInit('PATCH', body));
}

/** 确认原卷入库（幂等 `submissionId`）：同标识同载荷重放返回原结果（`replayed=true`）。 */
export function confirmPaper(paperId: string, body: PaperConfirmRequest): Promise<PaperConfirmResult> {
  return apiRequest<PaperConfirmResult>(`/papers/${encodeURIComponent(paperId)}/confirm`, jsonInit('POST', body));
}

/** 试卷知识点占比（C4-3）：按当前修订 primary 知识点聚合；未关联计入「未分类」。 */
export function paperKnowledgeDistribution(
  paperId: string,
  signal?: AbortSignal,
): Promise<KnowledgeDistributionBucket[]> {
  return apiRequest<KnowledgeDistributionBucket[]>(
    `/papers/${encodeURIComponent(paperId)}/knowledge-distribution`,
    { signal },
  );
}

/* ------------------------------------------------------------------ AI 知识点建议（只进候选） */

/** 生成知识点关联建议（202 接受任务）：返回待观察的 `teaching` 域任务收据，不直接改原卷。 */
export function createPaperProposal(
  paperId: string,
  body: PaperProposalJobRequest,
): Promise<TeachingJobView> {
  return apiRequest<TeachingJobView>(
    `/papers/${encodeURIComponent(paperId)}/knowledge-proposals`,
    jsonInit('POST', body),
  );
}

export function getPaperProposal(proposalId: string, signal?: AbortSignal): Promise<PaperProposalView> {
  return apiRequest<PaperProposalView>(`/paper-proposals/${encodeURIComponent(proposalId)}`, { signal });
}

/** 教师审核后应用所选建议（仍属草稿：必须再走一次「确认原卷入库」）。 */
export function applyPaperProposal(
  proposalId: string,
  body: PaperProposalDecisionRequest,
): Promise<PaperRevisionContentView> {
  return apiRequest<PaperRevisionContentView>(
    `/paper-proposals/${encodeURIComponent(proposalId)}/apply`,
    jsonInit('POST', body),
  );
}

export function rejectPaperProposal(
  proposalId: string,
  body: PaperProposalDecisionRequest,
): Promise<PaperProposalView> {
  return apiRequest<PaperProposalView>(
    `/paper-proposals/${encodeURIComponent(proposalId)}/reject`,
    jsonInit('POST', body),
  );
}
