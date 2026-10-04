/** B5 v1 wire contract. Content/envelope remain v1; server identity is v2. */
import type { JobView } from './teaching-loop';
import type { FixedKnowledge, Page } from './b4';
import type { TextbookSelection } from './textbook';
import type { EvidenceRef, ScopeSnapshot, TextbookEvidence } from './rag-v2';
export type { Page, EvidenceRef, ScopeSnapshot, TextbookEvidence };

export type LessonType = 'new' | 'review' | 'exercise' | 'experiment' | 'other';
export interface ProcessItem { id: string; stage: string; design: string; secondary: string }
export interface LessonPlanData {
  title: string; totalLessons: string; currentLessonNo: string; lessonTypes: LessonType[];
  otherTypeText: string; coreCompetencies: string; keyPoints: string; teachingDesign: string;
  process: ProcessItem[]; exercises: string; reflection: string;
}
export interface DraftEnvelope { schemaVersion: 1; revision: number; updatedAt: string; data: LessonPlanData }
export type AllowedLessonField = 'coreCompetencies' | 'keyPoints' | 'teachingDesign' | 'process' | 'exercises';
export const allowedLessonFields: readonly AllowedLessonField[] = [
  'coreCompetencies', 'keyPoints', 'teachingDesign', 'process', 'exercises',
];
export type LessonSource = 'manual' | 'rule' | 'import_local' | 'ai_applied';
export interface AnalysisContextInput { analysisRunId: string; selectedKnowledgePointIds: string[] }
export interface LessonCreateRequest {
  submissionId: string; subjectId: string; classId: string; data: LessonPlanData;
  context: AnalysisContextInput | null; source?: 'manual' | 'rule';
}
export interface LessonImportRequest {
  submissionId: string; subjectId: string; classId: string; draft: DraftEnvelope; context: AnalysisContextInput | null;
}
export interface LessonSaveRequest {
  submissionId: string; expectedRevision: number; data: LessonPlanData;
  context: AnalysisContextInput | null; source?: 'manual' | 'rule';
}
export interface AnalysisContextSnapshot {
  analysisRunId: string; inputHash: string; scoreRevisionId: string; paperRevisionId: string;
  className: string | null; classNameNote: string; knowledgePoints: FixedKnowledge[];
}
export interface LessonContextSnapshot {
  subjectId: string; classId: string; classNameAtSave: string; analysis: AnalysisContextSnapshot | null;
}
export interface LessonStageMetadata {
  processId: string; phase: 'introduction' | 'exploration' | 'practice' | 'conclusion';
  minutes: number; knowledgeAliases: string[]; activity: string; check: string; evidenceAliases: string[];
}
export interface LessonRevisionView {
  protocolVersion: 2; lessonPlanId: string; revisionId: string; version: number; data: LessonPlanData;
  contentHash: string; source: LessonSource; contextSnapshot: LessonContextSnapshot;
  analysisRunId: string | null; acceptedProposalId: string | null; importEnvelope: DraftEnvelope | null;
  selectedFields: AllowedLessonField[]; processMetadata: LessonStageMetadata[];
  reviewState: 'unreviewed' | 'reviewed'; createdAt: string;
}
export interface LessonView {
  protocolVersion: 2; lessonPlanId: string; subjectId: string; classId: string;
  revision: number; currentRevisionId: string; currentRevision: LessonRevisionView; replayed: boolean;
}
export interface LessonSummary {
  lessonPlanId: string; subjectId: string; classId: string; revision: number; currentRevisionId: string;
  title: string; source: LessonSource; analysisRunId: string | null; updatedAt: string;
}
export interface LessonRevisionSummary {
  lessonPlanId: string; revisionId: string; version: number; title: string; contentHash: string;
  source: LessonSource; analysisRunId: string | null; acceptedProposalId: string | null;
  selectedFields: AllowedLessonField[]; reviewState: 'unreviewed' | 'reviewed'; createdAt: string;
}
export interface LessonEvidenceRequest {
  selection: TextbookSelection; slices: { documentRevisionId: string; charStart: number; charEnd: number }[];
}
export interface LessonEvidenceView { scopeSnapshot: ScopeSnapshot; evidenceRefs: EvidenceRef[]; evidence: TextbookEvidence[] }
export interface LessonGenerateRequest {
  submissionId: string; baseRevisionId: string; baseServerRevision: number;
  analysisRunId: string; classId: string; selectedKnowledgePointIds: string[];
  requirements: string; durationMinutes: number; modelProfileId: string;
  scopeSnapshot: ScopeSnapshot; evidenceRefs: EvidenceRef[];
  questionRevisionIds: string[]; practiceRevisionIds: string[];
}
export interface LessonGenerationReceipt { lessonPlanId: string; inputHash: string; job: JobView; replayed: boolean }
export interface LessonPatch {
  coreCompetencies: string | null; keyPoints: string | null; teachingDesign: string | null;
  process: ProcessItem[]; exercises: string | null;
}
export interface LessonProposalEvidence {
  alias: string; kind: 'textbook' | 'question' | 'practice'; referenceId: string;
  title: string; sha256: string; locator: Record<string, unknown>; text: string;
}
export interface LessonBudget { durationMinutes: number; stages: LessonStageMetadata[] }
export interface LessonGenerationSource {
  analysis: AnalysisContextSnapshot; classId: string; selectedKnowledgePoints: FixedKnowledge[];
  modelProfileId: string; scopeSnapshot: ScopeSnapshot; evidenceRefs: EvidenceRef[]; requirements: string;
}
export interface LessonProposalView {
  protocolVersion: 2; lessonPlanId: string; proposalId: string; jobId: string;
  baseRevisionId: string; baseServerRevision: number; inputHash: string; modelFingerprint: string;
  state: 'pending' | 'applied' | 'rejected' | 'stale'; patch: LessonPatch; budget: LessonBudget;
  evidence: LessonProposalEvidence[]; generationSource: LessonGenerationSource;
  selectedFields: AllowedLessonField[]; acceptedRevisionId: string | null;
  createdAt: string; decidedAt: string | null; replayed: boolean;
}
export interface LessonApplyRequest {
  submissionId: string; expectedRevision: number; baseRevisionId: string; selectedFields: AllowedLessonField[];
}
export interface LessonRejectRequest { submissionId: string }
