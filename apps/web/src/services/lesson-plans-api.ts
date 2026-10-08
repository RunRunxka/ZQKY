/** Transport only: owned fixed content, original submissions and shared jobs. */
import { apiRequest } from './api-client';
import { assessmentsQuery } from './assessments-api';
import type {
  Page, LessonSummary, LessonRevisionSummary, LessonView, LessonRevisionView,
  LessonCreateRequest, LessonImportRequest, LessonSaveRequest, LessonEvidenceRequest, LessonEvidenceView,
  LessonGenerateRequest, LessonGenerationReceipt, LessonProposalView, LessonApplyRequest, LessonRejectRequest,
  LessonRevisionRequest,
} from '@/contracts/lesson-plans';

const key = encodeURIComponent;
const write = (method: string, body: unknown, signal?: AbortSignal): RequestInit => ({
  method, headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), signal,
});
export interface LessonListQuery { offset?: number; limit?: number; subjectId?: string; classId?: string; archived?: boolean }
export interface LessonHistoryQuery { offset?: number; limit?: number }

export function listLessons(query: LessonListQuery = {}, signal?: AbortSignal): Promise<Page<LessonSummary>> {
  return apiRequest(`/lesson-plans${assessmentsQuery({ ...query })}`, { signal });
}
export function createLesson(body: LessonCreateRequest, signal?: AbortSignal): Promise<LessonView> {
  return apiRequest('/lesson-plans', write('POST', body, signal));
}
export function importLocalLesson(body: LessonImportRequest, signal?: AbortSignal): Promise<LessonView> {
  return apiRequest('/lesson-plans/import-local', write('POST', body, signal));
}
export function getLesson(id: string, signal?: AbortSignal): Promise<LessonView> {
  return apiRequest(`/lesson-plans/${key(id)}`, { signal });
}
/** 教案归档：`expectedRevision` 守卫；历史修订与来源证据保留。 */
export function archiveLessonPlan(id: string, body: LessonRevisionRequest, signal?: AbortSignal): Promise<LessonView> {
  return apiRequest(`/lesson-plans/${key(id)}/archive`, write('POST', body, signal));
}
export function restoreLessonPlan(id: string, body: LessonRevisionRequest, signal?: AbortSignal): Promise<LessonView> {
  return apiRequest(`/lesson-plans/${key(id)}/restore`, write('POST', body, signal));
}
export function saveLesson(id: string, body: LessonSaveRequest, signal?: AbortSignal): Promise<LessonView> {
  return apiRequest(`/lesson-plans/${key(id)}/draft`, write('PATCH', body, signal));
}
export function listLessonRevisions(id: string, query: LessonHistoryQuery = {}, signal?: AbortSignal): Promise<Page<LessonRevisionSummary>> {
  return apiRequest(`/lesson-plans/${key(id)}/revisions${assessmentsQuery({ ...query })}`, { signal });
}
export function getLessonRevision(id: string, revisionId: string, signal?: AbortSignal): Promise<LessonRevisionView> {
  return apiRequest(`/lesson-plans/${key(id)}/revisions/${key(revisionId)}`, { signal });
}
export function verifyLessonEvidence(body: LessonEvidenceRequest, signal?: AbortSignal): Promise<LessonEvidenceView> {
  return apiRequest('/lesson-plans/evidence/verify', write('POST', body, signal));
}
export function generateLessonProposal(id: string, body: LessonGenerateRequest, signal?: AbortSignal): Promise<LessonGenerationReceipt> {
  return apiRequest(`/lesson-plans/${key(id)}/proposals`, write('POST', body, signal));
}
export function getLessonProposal(id: string, proposalId: string, signal?: AbortSignal): Promise<LessonProposalView> {
  return apiRequest(`/lesson-plans/${key(id)}/proposals/${key(proposalId)}`, { signal });
}
export function applyLessonProposal(id: string, proposalId: string, body: LessonApplyRequest, signal?: AbortSignal): Promise<LessonView> {
  return apiRequest(`/lesson-plans/${key(id)}/proposals/${key(proposalId)}/apply`, write('POST', body, signal));
}
export function rejectLessonProposal(id: string, proposalId: string, body: LessonRejectRequest, signal?: AbortSignal): Promise<LessonProposalView> {
  return apiRequest(`/lesson-plans/${key(id)}/proposals/${key(proposalId)}/reject`, write('POST', body, signal));
}

export const lessonPlanApi = {
  listLessons, createLesson, importLocalLesson, getLesson, saveLesson,
  listLessonRevisions, getLessonRevision, verifyLessonEvidence,
  generateLessonProposal, getLessonProposal, applyLessonProposal, rejectLessonProposal,
  archiveLessonPlan, restoreLessonPlan,
};
