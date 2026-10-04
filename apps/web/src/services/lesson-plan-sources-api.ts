/** Actual confirmed revision identities; generation revalidates immutable sources. */
import type { Page } from '@/contracts/b4';
import { apiRequest } from '@/services/api-client';
import { assessmentsQuery } from '@/services/assessments-api';

export interface ConfirmedQuestionRevision {
  questionId: string;
  questionRevisionId: string;
  subjectId: string;
  stemMarkdown: string;
}

export function listConfirmedQuestionRevisions(subjectId: string, query: { offset?: number; limit?: number } = {}, signal?: AbortSignal) {
  return apiRequest<Page<ConfirmedQuestionRevision>>(`/confirmed-question-revisions${assessmentsQuery({ subjectId, ...query })}`, { signal });
}
