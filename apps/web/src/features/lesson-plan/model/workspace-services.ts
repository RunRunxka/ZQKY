import * as assessments from '@/services/assessments-api';
import * as textbooks from '@/services/textbook-api';
import * as questions from '@/services/question-bank-api';
import * as models from '@/services/model-settings-api';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { listConfirmedQuestionRevisions } from '@/services/lesson-plan-sources-api';
import type { LessonPlanServices } from './types';

export const defaultSourceApi = {
  listClasses: assessments.listClasses, taxonomy: textbooks.fetchTextbookTaxonomy,
  listRuns: b4Api.listAnalysisRuns, getRun: b4Api.getAnalysisRun, listClassesReport: b4Api.listAnalysisClasses,
  listDocuments: textbooks.listDocuments, getDocumentSource: textbooks.getDocumentSource,
  listQuestions: questions.listQuestions, listPractices: b4Api.listPractices,
  getPractice: b4Api.getPractice, getPracticeRevision: b4Api.getPracticeRevision,
  listProfiles: models.listProfiles,
  listConfirmedQuestionRevisions,
};
export interface LessonWorkspaceServices extends LessonPlanServices {
  lessonApi?: typeof lessonPlanApi;
  sourceApi?: typeof defaultSourceApi;
  recoveryStorage?: Storage;
}
