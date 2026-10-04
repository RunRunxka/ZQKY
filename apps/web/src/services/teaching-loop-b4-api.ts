/** B4 transport only. FastAPI owns facts, CAS and fixed submission receipts. */
import { apiRequest, apiRequestBlob } from './api-client';
import { assessmentsQuery } from './assessments-api';
import type {
  AnalysisCreateRequest, AnalysisReceipt, AnalysisRunView, ClassReportRow,
  StudentReportRow, EvidenceRow, NoteRequest, NoteView, Page,
  PracticeCreateRequest, PracticeSetView, PracticeRevisionView,
  PracticeSuggestionsRequest, PracticeSuggestions, PracticeDraftPatch,
  PracticeReviewRequest, PracticeRevisionRequest, ExportRequest, ExportReceipt,
  ExportArtifact, PracticeConversionRequest, PracticeConversionReceipt,
} from '@/contracts/b4';

const key = encodeURIComponent;
const write = (method: string, body: unknown, signal?: AbortSignal): RequestInit => ({
  method, headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), signal,
});
export interface PageQuery { offset?: number; limit?: number }
export interface AnalysisQuery extends PageQuery { assessmentId?: string; scoreRevisionId?: string }
export interface ReportQuery extends PageQuery { classId?: string; participantId?: string; knowledgePointId?: string }
export interface PracticeQuery extends PageQuery { analysisRunId?: string }

export function createAnalysisRun(assessmentId: string, body: AnalysisCreateRequest, signal?: AbortSignal): Promise<AnalysisReceipt> {
  return apiRequest(`/assessments/${key(assessmentId)}/analysis-runs`, write('POST', body, signal));
}
export function listAnalysisRuns(query: AnalysisQuery = {}, signal?: AbortSignal): Promise<Page<AnalysisRunView>> {
  return apiRequest(`/analysis-runs${assessmentsQuery({ ...query })}`, { signal });
}
export function getAnalysisRun(runId: string, signal?: AbortSignal): Promise<AnalysisRunView> {
  return apiRequest(`/analysis-runs/${key(runId)}`, { signal });
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

export const b4Api = {
  createAnalysisRun, listAnalysisRuns, getAnalysisRun, listAnalysisClasses, listAnalysisStudents,
  listAnalysisEvidence, listAnalysisNotes, createAnalysisNote, createPractice, listPractices,
  getPractice, getPracticeRevision, suggestPractice, patchPracticeDraft, reviewPractice,
  createPracticeRevision, createPracticeExport, listPracticeExports, getExportArtifact,
  downloadExportArtifact, getPracticeAsset, convertPractice,
};
