/** B4 transport only. FastAPI owns facts, CAS and fixed submission receipts. */
import { apiRequest, apiRequestBlob } from './api-client';
import { assessmentsQuery } from './assessments-api';
import type {
  AnalysisArchiveRequest, AnalysisCreateRequest, AnalysisReceipt, AnalysisRunView, ClassReportRow,
  StudentReportRow, EvidenceRow, ItemStatView, NoteRequest, NoteView, Page,
  AnalysisRunDeleteResult,
  PracticeCreateRequest, PracticeSetView, PracticeRevisionView,
  PracticeSetStatusRequest, PracticeSetDeleteReceipt,
  PracticeSuggestionsRequest, PracticeSuggestions, PracticeDraftPatch,
  PracticeReviewRequest, PracticeRevisionRequest, ExportRequest, ExportReceipt,
  ExportArtifact, PracticeConversionRequest, PracticeConversionReceipt,
  PracticeConversionDeleteResult,
} from '@/contracts/b4';

const key = encodeURIComponent;
const write = (method: string, body: unknown, signal?: AbortSignal): RequestInit => ({
  method, headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), signal,
});
/** 归档/恢复请求体：后端 `AnalysisArchiveRequest` 当前无字段（`extra="forbid"`），固定空对象。 */
const analysisArchiveBody: AnalysisArchiveRequest = {};
export interface PageQuery { offset?: number; limit?: number }
export interface AnalysisQuery extends PageQuery { assessmentId?: string; scoreRevisionId?: string; archived?: boolean }
export interface ReportQuery extends PageQuery { classId?: string; participantId?: string; knowledgePointId?: string }
export interface PracticeQuery extends PageQuery { analysisRunId?: string; status?: 'active' | 'archived' }

export function createAnalysisRun(assessmentId: string, body: AnalysisCreateRequest, signal?: AbortSignal): Promise<AnalysisReceipt> {
  return apiRequest(`/assessments/${key(assessmentId)}/analysis-runs`, write('POST', body, signal));
}
export function listAnalysisRuns(query: AnalysisQuery = {}, signal?: AbortSignal): Promise<Page<AnalysisRunView>> {
  return apiRequest(`/analysis-runs${assessmentsQuery({ ...query })}`, { signal });
}
export function getAnalysisRun(runId: string, signal?: AbortSignal): Promise<AnalysisRunView> {
  return apiRequest(`/analysis-runs/${key(runId)}`, { signal });
}
/** 软归档学情运行：只写 `archivedAt`，报告内容与子表一概不动；幂等。 */
export function archiveAnalysisRun(runId: string, signal?: AbortSignal): Promise<AnalysisRunView> {
  return apiRequest(`/analysis-runs/${key(runId)}/archive`, write('POST', analysisArchiveBody, signal));
}
export function restoreAnalysisRun(runId: string, signal?: AbortSignal): Promise<AnalysisRunView> {
  return apiRequest(`/analysis-runs/${key(runId)}/restore`, write('POST', analysisArchiveBody, signal));
}
/**
 * 彻底删除学情报告（受引用守卫的物理删除）：物理删除报告与其冻结的班级/学生依据、题证据、教师备注，不可恢复。
 * 仍有针对练习 / 教案引用 → 409 `ANALYSIS_RUN_IN_USE` + `details.counts`；不存在/非本人 → 404。
 */
export function deleteAnalysisRun(runId: string, signal?: AbortSignal): Promise<AnalysisRunDeleteResult> {
  return apiRequest(`/analysis-runs/${key(runId)}`, { method: 'DELETE', signal });
}
export function listAnalysisClasses(runId: string, query: ReportQuery = {}, signal?: AbortSignal): Promise<Page<ClassReportRow>> {
  return apiRequest(`/analysis-runs/${key(runId)}/classes${assessmentsQuery({ ...query })}`, { signal });
}
export function listAnalysisStudents(runId: string, query: ReportQuery = {}, signal?: AbortSignal): Promise<Page<StudentReportRow>> {
  return apiRequest(`/analysis-runs/${key(runId)}/students${assessmentsQuery({ ...query })}`, { signal });
}
export function listAnalysisEvidence(runId: string, query: ReportQuery = {}, signal?: AbortSignal): Promise<Page<EvidenceRow>> {
  return apiRequest(`/analysis-runs/${key(runId)}/evidence${assessmentsQuery({ ...query })}`, { signal });
}

/** 图表聚合（C2）：按题号的全班得分率（匿名；趋势图/热力图共用）。 */
export function getAnalysisItemStats(runId: string, signal?: AbortSignal): Promise<ItemStatView[]> {
  return apiRequest(`/analysis-runs/${key(runId)}/item-stats`, { signal });
}

/** AI 学情评价（C2-3）：即席生成 Markdown 评价（候选文本不落库；学生匿名进模型）。 */
export function generateAnalysisCommentary(runId: string, modelProfileId: string, signal?: AbortSignal): Promise<string> {
  return apiRequest(`/analysis-runs/${key(runId)}/ai-commentary`, write('POST', { modelProfileId }, signal));
}
export function listAnalysisNotes(runId: string, query: PageQuery = {}, signal?: AbortSignal): Promise<Page<NoteView>> {
  return apiRequest(`/analysis-runs/${key(runId)}/notes${assessmentsQuery({ ...query })}`, { signal });
}
export function createAnalysisNote(runId: string, body: NoteRequest, signal?: AbortSignal): Promise<NoteView> {
  return apiRequest(`/analysis-runs/${key(runId)}/notes`, write('POST', body, signal));
}
export function createPractice(body: PracticeCreateRequest, signal?: AbortSignal): Promise<PracticeSetView> {
  return apiRequest('/practice-sets', write('POST', body, signal));
}
export function listPractices(query: PracticeQuery = {}, signal?: AbortSignal): Promise<Page<PracticeSetView>> {
  return apiRequest(`/practice-sets${assessmentsQuery({ ...query })}`, { signal });
}
export function getPractice(setId: string, signal?: AbortSignal): Promise<PracticeSetView> {
  return apiRequest(`/practice-sets/${key(setId)}`, { signal });
}
/** 练习集归档：`expectedRevision` 守卫；历史修订与导出产物保留。 */
export function archivePracticeSet(setId: string, body: PracticeSetStatusRequest, signal?: AbortSignal): Promise<PracticeSetView> {
  return apiRequest(`/practice-sets/${key(setId)}/archive`, write('POST', body, signal));
}
export function restorePracticeSet(setId: string, body: PracticeSetStatusRequest, signal?: AbortSignal): Promise<PracticeSetView> {
  return apiRequest(`/practice-sets/${key(setId)}/restore`, write('POST', body, signal));
}
/**
 * 练习集彻底删除（受引用守卫的物理删除）：`expectedRevision` 走查询参数。
 * 有已审核修订/导出/转换引用 → 409 `PRACTICE_IN_USE` + `details.counts`（见 `PracticeSetReferenceCounts`）；
 * 乐观锁不符 → 409 `REVISION_CONFLICT`；不存在/非本人 → 404。已归档练习同样受守卫（不会因归档而可删）。
 * `includeHistory=true`（界面明确确认「连同全部历史」后）一并彻底删除已审核修订/导出产物/回流转换，
 * 查询串追加 `&includeHistory=true`，成功回执带四类删除计数；不传时保持原两参调用语义（回执计数为 0）。
 */
export function deletePracticeSet(setId: string, expectedRevision: number, includeHistory = false): Promise<PracticeSetDeleteReceipt> {
  return apiRequest(`/practice-sets/${key(setId)}${assessmentsQuery({ expectedRevision, ...(includeHistory ? { includeHistory: true } : {}) })}`, { method: 'DELETE' });
}
export function getPracticeRevision(setId: string, revisionId: string, signal?: AbortSignal): Promise<PracticeRevisionView> {
  return apiRequest(`/practice-sets/${key(setId)}/revisions/${key(revisionId)}`, { signal });
}
export function suggestPractice(setId: string, body: PracticeSuggestionsRequest, signal?: AbortSignal): Promise<PracticeSuggestions> {
  return apiRequest(`/practice-sets/${key(setId)}/suggestions`, write('POST', body, signal));
}
export function patchPracticeDraft(setId: string, body: PracticeDraftPatch, signal?: AbortSignal): Promise<PracticeSetView> {
  return apiRequest(`/practice-sets/${key(setId)}/draft`, write('PATCH', body, signal));
}
export function reviewPractice(setId: string, body: PracticeReviewRequest, signal?: AbortSignal): Promise<PracticeSetView> {
  return apiRequest(`/practice-sets/${key(setId)}/review`, write('POST', body, signal));
}
export function createPracticeRevision(setId: string, body: PracticeRevisionRequest, signal?: AbortSignal): Promise<PracticeSetView> {
  return apiRequest(`/practice-sets/${key(setId)}/revisions`, write('POST', body, signal));
}
export function createPracticeExport(setId: string, revisionId: string, body: ExportRequest, signal?: AbortSignal): Promise<ExportReceipt> {
  return apiRequest(`/practice-sets/${key(setId)}/revisions/${key(revisionId)}/exports`, write('POST', body, signal));
}
export function listPracticeExports(setId: string, revisionId: string, query: PageQuery = {}, signal?: AbortSignal): Promise<Page<ExportArtifact>> {
  return apiRequest(`/practice-sets/${key(setId)}/revisions/${key(revisionId)}/exports${assessmentsQuery({ ...query })}`, { signal });
}
export function getExportArtifact(artifactId: string, signal?: AbortSignal): Promise<ExportArtifact> {
  return apiRequest(`/export-artifacts/${key(artifactId)}`, { signal });
}
export function downloadExportArtifact(artifactId: string, signal?: AbortSignal) {
  return apiRequestBlob(`/export-artifacts/${key(artifactId)}/download`, { signal });
}
export function getPracticeAsset(setId: string, revisionId: string, sha: string, signal?: AbortSignal) {
  return apiRequestBlob(`/practice-sets/${key(setId)}/revisions/${key(revisionId)}/assets/${key(sha)}`, { signal });
}
export function convertPractice(setId: string, revisionId: string, body: PracticeConversionRequest, signal?: AbortSignal): Promise<PracticeConversionReceipt> {
  return apiRequest(`/practice-sets/${key(setId)}/revisions/${key(revisionId)}/assessments`, write('POST', body, signal));
}
/**
 * 删除练习转换记录（只解除回流关联，无引用守卫）：施测、原卷与成绩数据保留；
 * 该审核修订没有转换记录 → 404。回执带被解除的 `conversionId` 与 `assessmentId`。
 */
export function deletePracticeConversion(setId: string, revisionId: string, signal?: AbortSignal): Promise<PracticeConversionDeleteResult> {
  return apiRequest(`/practice-sets/${key(setId)}/revisions/${key(revisionId)}/conversion`, { method: 'DELETE', signal });
}

export const b4Api = {
  createAnalysisRun, listAnalysisRuns, getAnalysisRun, listAnalysisClasses, listAnalysisStudents,
  listAnalysisEvidence, getAnalysisItemStats, generateAnalysisCommentary, listAnalysisNotes, createAnalysisNote, createPractice, listPractices,
  getPractice, getPracticeRevision, suggestPractice, patchPracticeDraft, reviewPractice,
  createPracticeRevision, createPracticeExport, listPracticeExports, getExportArtifact,
  downloadExportArtifact, getPracticeAsset, convertPractice, deletePracticeConversion,
  archiveAnalysisRun, restoreAnalysisRun, deleteAnalysisRun, archivePracticeSet, restorePracticeSet,
  deletePracticeSet,
};
