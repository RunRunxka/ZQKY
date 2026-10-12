/**
 * 学情分析 /api/v1 客户端（R6-FE 2026-10-11）。
 *
 * 视图类型全部来自 `@/contracts/learning-analysis`（与后端契约逐字段镜像）。
 * 一律经 `@/services/api-client` 的相对路径 `/api/v1` 请求：失败统一抛 `ApiError`，
 * 绝不把失败降级为空列表或假成功；后端尚未上线时同样是可见的失败（例如 501），
 * 由卡片的错误态与重试入口呈现，不当空数据。
 *
 * 端点来源：
 * - 归档沿用：`analysis-runs`（列表/详情/item-stats/ai-commentary/notes）、
 *   施测 / 班级 / 原卷修订内容、成绩导入（score-imports）；
 * - 本卡冻结新增：`knowledge-stats` / `student-knowledge` / `distribution` / `report`；
 *   下载沿用受管产物 `GET /export-artifacts/{artifactId}/download`。
 */

import { apiRequest, apiRequestBlob, type BlobDownload } from '@/services/api-client';
import type {
  AnalysisCommentaryView,
  AnalysisReportReceipt,
  AnalysisRunList,
  AnalysisRunView,
  AssessmentDetailView,
  AssessmentList,
  ClassList,
  DistributionResponse,
  ItemStatView,
  KnowledgeStatsResponse,
  NoteRequest,
  NoteView,
  PaperRevisionContentView,
  ScoreColumnMapping,
  ScoreImportConfirmRequest,
  ScoreImportConfirmResult,
  ScoreImportDeleteResult,
  ScoreImportDiscardRequest,
  ScoreImportList,
  ScoreImportPatchRequest,
  ScoreImportRefreshRequest,
  ScoreImportRowList,
  ScoreImportView,
  ScoreRevisionList,
  StudentKnowledgeResponse,
} from '@/contracts/learning-analysis';

const key = encodeURIComponent;

/** 拼接查询串：只写有值的键（undefined/null/空串跳过），并做 URL 编码。 */
export function learningAnalysisQuery(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.set(name, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

function jsonInit(method: string, body: unknown, signal?: AbortSignal): RequestInit {
  return {
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  };
}

/* ---------------------------------------------------------------- 学情报告 */

export interface AnalysisRunQuery {
  assessmentId?: string;
  scoreRevisionId?: string;
  offset?: number;
  limit?: number;
}

export function listAnalysisRuns(
  query: AnalysisRunQuery = {},
  signal?: AbortSignal,
): Promise<AnalysisRunList> {
  return apiRequest<AnalysisRunList>(`/analysis-runs${learningAnalysisQuery({ ...query })}`, {
    signal,
  });
}

export function getAnalysisRun(runId: string, signal?: AbortSignal): Promise<AnalysisRunView> {
  return apiRequest<AnalysisRunView>(`/analysis-runs/${key(runId)}`, { signal });
}

/** 小题得分聚合（题号 × 全班得分率；趋势图与热力图共用同一来源）。 */
export function getAnalysisItemStats(
  runId: string,
  signal?: AbortSignal,
): Promise<ItemStatView[]> {
  return apiRequest<ItemStatView[]>(`/analysis-runs/${key(runId)}/item-stats`, { signal });
}

/** 知识点得分率（冻结形状：`items` 已按 scoreRate 降序）。 */
export function getAnalysisKnowledgeStats(
  runId: string,
  signal?: AbortSignal,
): Promise<KnowledgeStatsResponse> {
  return apiRequest<KnowledgeStatsResponse>(`/analysis-runs/${key(runId)}/knowledge-stats`, {
    signal,
  });
}

/** 学生 × 知识点矩阵（冻结形状：`label` 一律展示后端给的值）。 */
export function getAnalysisStudentKnowledge(
  runId: string,
  signal?: AbortSignal,
): Promise<StudentKnowledgeResponse> {
  return apiRequest<StudentKnowledgeResponse>(`/analysis-runs/${key(runId)}/student-knowledge`, {
    signal,
  });
}

/** 得分率分数段分布（冻结形状：低/中/高分档计数）。 */
export function getAnalysisDistribution(
  runId: string,
  signal?: AbortSignal,
): Promise<DistributionResponse> {
  return apiRequest<DistributionResponse>(`/analysis-runs/${key(runId)}/distribution`, { signal });
}

/**
 * AI 学情评价：候选 Markdown 文本（即席生成、不落库；学生由后端脱敏为代称）。
 *
 * 返回 `{commentary, degraded, reason}`：模型未返回/不可用时服务端**不**抛错，
 * 以 `degraded=true` + 空文本 + 原因码表达（教师可重试）。
 */
export function generateAnalysisCommentary(
  runId: string,
  modelProfileId: string,
  signal?: AbortSignal,
): Promise<AnalysisCommentaryView> {
  return apiRequest<AnalysisCommentaryView>(
    `/analysis-runs/${key(runId)}/ai-commentary`,
    jsonInit('POST', { modelProfileId }, signal),
  );
}

/** 追加教师备注（逻辑确认：`submissionId` 幂等）。 */
export function createAnalysisNote(
  runId: string,
  body: NoteRequest,
  signal?: AbortSignal,
): Promise<NoteView> {
  return apiRequest<NoteView>(
    `/analysis-runs/${key(runId)}/notes`,
    jsonInit('POST', body, signal),
  );
}

/** 生成分析报告导出产物（201）：返回受管产物标识，随后经下载端点取文件。 */
export function createAnalysisReport(
  runId: string,
  signal?: AbortSignal,
): Promise<AnalysisReportReceipt> {
  return apiRequest<AnalysisReportReceipt>(
    `/analysis-runs/${key(runId)}/report`,
    jsonInit('POST', {}, signal),
  );
}

export function downloadExportArtifact(
  artifactId: string,
  signal?: AbortSignal,
): Promise<BlobDownload> {
  return apiRequestBlob(`/export-artifacts/${key(artifactId)}/download`, { signal });
}

/* ---------------------------------------------------------------- 施测 / 班级 / 原卷 */

export interface AssessmentQuery {
  classId?: string;
  state?: 'open' | 'closed' | 'archived';
  offset?: number;
  limit?: number;
}

export function listAssessments(
  query: AssessmentQuery = {},
  signal?: AbortSignal,
): Promise<AssessmentList> {
  return apiRequest<AssessmentList>(`/assessments${learningAnalysisQuery({ ...query })}`, { signal });
}

export function getAssessment(
  assessmentId: string,
  signal?: AbortSignal,
): Promise<AssessmentDetailView> {
  return apiRequest<AssessmentDetailView>(`/assessments/${key(assessmentId)}`, { signal });
}

export function listClasses(
  query: { status?: 'active' | 'archived'; offset?: number; limit?: number } = {},
  signal?: AbortSignal,
): Promise<ClassList> {
  return apiRequest<ClassList>(`/classes${learningAnalysisQuery({ ...query })}`, { signal });
}

/** 固定原卷修订内容：列映射的计分叶集合来自它的 `items`。 */
export function getPaperRevisionContent(
  paperId: string,
  revisionId: string,
  signal?: AbortSignal,
): Promise<PaperRevisionContentView> {
  return apiRequest<PaperRevisionContentView>(
    `/papers/${key(paperId)}/revisions/${key(revisionId)}/content`,
    { signal },
  );
}

/* ---------------------------------------------------------------- 小题分成绩单导入 */

export interface ScoreImportCreateMeta {
  /** 多工作表 XLSX 指定工作表名；缺省由服务端选用。 */
  workSheet?: string | null;
  /** 本次导入所基于的正式成绩版本；首个版本为 null（不提供）。 */
  baseScoreRevisionId?: string | null;
}

/** 上传小题分成绩单（.xlsx/.csv）创建待校对批次（multipart；不手写 content-type）。 */
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
    `/assessments/${key(assessmentId)}/score-imports`,
    { method: 'POST', body: form, signal },
  );
}

export function listScoreImports(
  query: { assessmentId?: string; offset?: number; limit?: number } = {},
  signal?: AbortSignal,
): Promise<ScoreImportList> {
  return apiRequest<ScoreImportList>(`/score-imports${learningAnalysisQuery({ ...query })}`, {
    signal,
  });
}

export function getScoreImport(importId: string, signal?: AbortSignal): Promise<ScoreImportView> {
  return apiRequest<ScoreImportView>(`/score-imports/${key(importId)}`, { signal });
}

/** 原表行分页；`cells` 带物理坐标（行号 + 列字母）。 */
export function listScoreImportRows(
  importId: string,
  query: { offset?: number; limit?: number } = {},
  signal?: AbortSignal,
): Promise<ScoreImportRowList> {
  return apiRequest<ScoreImportRowList>(
    `/score-imports/${key(importId)}/rows${learningAnalysisQuery({ ...query })}`,
    { signal },
  );
}

/** 改映射 / 行定位 / 单元格校正；返回重算后的权威批次视图（revision 与 previewVersion 递增）。 */
export function patchScoreImport(
  importId: string,
  body: ScoreImportPatchRequest,
  signal?: AbortSignal,
): Promise<ScoreImportView> {
  return apiRequest<ScoreImportView>(
    `/score-imports/${key(importId)}`,
    jsonInit('PATCH', body, signal),
  );
}

/** 明确刷新预览（出勤/人次校正后）：乐观锁 + 基准版本原样送服务端。 */
export function refreshScoreImport(
  importId: string,
  body: ScoreImportRefreshRequest,
  signal?: AbortSignal,
): Promise<ScoreImportView> {
  return apiRequest<ScoreImportView>(
    `/score-imports/${key(importId)}/refresh`,
    jsonInit('POST', body, signal),
  );
}

/** 整批确认（幂等 `submissionId`）：同标识同载荷重放返回原结果（`replayed=true`）。 */
export function confirmScoreImport(
  importId: string,
  body: ScoreImportConfirmRequest,
  signal?: AbortSignal,
): Promise<ScoreImportConfirmResult> {
  return apiRequest<ScoreImportConfirmResult>(
    `/score-imports/${key(importId)}/confirm`,
    jsonInit('POST', body, signal),
  );
}

/** 放弃未确认成绩批次：只置 `state=cancelled`；批次记录/原始文件/预览行保留。 */
export function discardScoreImport(
  importId: string,
  body: ScoreImportDiscardRequest,
  signal?: AbortSignal,
): Promise<ScoreImportView> {
  return apiRequest<ScoreImportView>(
    `/score-imports/${key(importId)}/discard`,
    jsonInit('POST', body, signal),
  );
}

/** 彻底删除导入批次（受引用守卫）：批次记录与预览行一并删除；被引用 → 409。 */
export function deleteScoreImport(
  importId: string,
  signal?: AbortSignal,
): Promise<ScoreImportDeleteResult> {
  return apiRequest<ScoreImportDeleteResult>(`/score-imports/${key(importId)}`, {
    method: 'DELETE',
    signal,
  });
}

export function listScoreRevisions(
  assessmentId: string,
  signal?: AbortSignal,
): Promise<ScoreRevisionList> {
  return apiRequest<ScoreRevisionList>(
    `/assessments/${key(assessmentId)}/score-revisions`,
    { signal },
  );
}

/** 导出为对象，便于页面注入测试替身（`services` prop）。 */
export const learningAnalysisApi = {
  listAnalysisRuns,
  getAnalysisRun,
  getAnalysisItemStats,
  getAnalysisKnowledgeStats,
  getAnalysisStudentKnowledge,
  getAnalysisDistribution,
  generateAnalysisCommentary,
  createAnalysisNote,
  createAnalysisReport,
  downloadExportArtifact,
  listAssessments,
  getAssessment,
  listClasses,
  getPaperRevisionContent,
  createScoreImport,
  listScoreImports,
  getScoreImport,
  listScoreImportRows,
  patchScoreImport,
  refreshScoreImport,
  confirmScoreImport,
  discardScoreImport,
  deleteScoreImport,
  listScoreRevisions,
};

export type LearningAnalysisApi = typeof learningAnalysisApi;

/** 列映射保存时的列字母校验（与后端口径一致：最多 3 个字母）。 */
export const COLUMN_PATTERN = /^[A-Za-z]{1,3}$/;

export type { ScoreColumnMapping };
