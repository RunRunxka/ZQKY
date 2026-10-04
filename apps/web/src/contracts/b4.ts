/** B4 v1 shared wire contract; mirrored from app/contracts/b4.py. */
import type { JobView, RichContentV2, ScoreStatus, Observation } from './teaching-loop';
import type { AssessmentParticipantInput } from './assessments';

export interface AnalysisCreateRequest {
  submissionId: string;
  scoreRevisionId: string;
  selectedParticipantIds: Array<string>;
  ruleCode: 'any_loss_v1';
}

export interface FrozenParticipant {
  participantId: string;
  studentId: string;
  studentNo: string | null;
  name: string;
  classId: string;
  className: null;
  classNameNote: '该成绩未记录班名';
  attemptNo: number;
  attendance: 'present' | 'absent' | 'exempt';
}

export interface FixedKnowledge {
  knowledgePointId: string;
  knowledgeRevisionId: string;
  name: string;
  role: 'primary' | 'secondary';
}

export interface SelectionSnapshot {
  selectedParticipantIds: Array<string>;
  uniqueStudentCount: number;
  participantCount: number;
  leafCount: number;
  stateCounts: Record<ScoreStatus, number>;
}

export interface AnalysisReceipt {
  runId: string;
  inputHash: string;
  scoreRevisionId: string;
  paperRevisionId: string;
  job: JobView;
  replayed: boolean;
  reused: boolean;
}

export interface AnalysisRunView {
  runId: string;
  assessmentId: string;
  subjectId: string;
  scoreRevisionId: string;
  paperRevisionId: string;
  paperTitle: string;
  inputHash: string;
  ruleCode: 'any_loss_v1';
  selectionSnapshot: SelectionSnapshot;
  participants: Array<FrozenParticipant>;
  knowledgePoints: Array<FixedKnowledge>;
  job: JobView;
  reportReady: boolean;
  createdAt: string;
}

export interface ClassReportRow {
  classId: string;
  className: null;
  classNameNote: string;
  knowledgePoint: FixedKnowledge;
  selectedCount: number;
  validCount: number;
  needsCount: number;
  incompleteCount: number;
  noEvidenceCount: number;
  fullCreditCount: number;
  numerator: number;
  denominator: number;
  ratio: number | null;
}

export interface StudentReportRow {
  participant: FrozenParticipant;
  knowledgePoint: FixedKnowledge;
  observation: Observation;
  informationIncomplete: boolean;
  expectedCount: number;
  validCount: number;
  stateCounts: Record<ScoreStatus, number>;
  totalScoreUnits: number | null;
  totalMaxScoreUnits: number;
}

export interface EvidenceRow {
  evidenceId: string;
  runId: string;
  scoreRevisionId: string;
  paperRevisionId: string;
  participant: FrozenParticipant;
  itemId: string;
  itemPath: string;
  maxScoreUnits: number;
  scoreUnits: number | null;
  status: ScoreStatus;
  knowledgePoints: Array<FixedKnowledge>;
  content: Record<string, unknown>;
  sharedMaterials: Array<Record<string, unknown>>;
  sourceLocator: Record<string, unknown>;
  assets: Array<Record<string, unknown>>;
  practiceRevisionId: string | null;
  practiceItemId: string | null;
  associationNote: string;
}

export interface NoteRequest {
  submissionId: string;
  participantId?: string | null;
  knowledgePointId?: string | null;
  note: string;
}

export interface NoteView {
  noteId: string;
  runId: string;
  participantId: string | null;
  knowledgePointId: string | null;
  note: string;
  createdAt: string;
  replayed: boolean;
}

export interface Page<T> {
  items: Array<T>;
  total: number;
  offset: number;
  limit: number;
}

export interface PracticeConstraints {
  count: number;
  questionTypes?: Array<string>;
  difficulties?: Array<string>;
  includeUnknownDifficulty?: boolean;
  excludeOriginal?: boolean;
  deduplicate?: boolean;
}

export interface PracticeCreateRequest {
  submissionId: string;
  analysisRunId: string;
  title: string;
  targetKnowledgePointIds: Array<string>;
  constraints: PracticeConstraints;
}

export interface PracticeNode {
  nodeKey: string;
  parentNodeKey?: string | null;
  questionNo: string;
  ordinal: number;
  isScored: boolean;
  maxScore?: string | null;
  knowledgePointIds?: Array<string>;
  sourceBlockIds?: Array<string>;
}

export interface PracticeStructure {
  nodes: Array<PracticeNode>;
}

export interface PracticeDraftItem {
  itemKey: string;
  questionRevisionId: string;
  ordinal: number;
  itemStructure: PracticeStructure;
  maxScore: string;
  selectedKnowledgePointIds: Array<string>;
}

export interface PracticeDraftPatch {
  submissionId: string;
  expectedRevision: number;
  items: Array<PracticeDraftItem>;
  constraints: PracticeConstraints;
}

export interface PracticeSuggestionsRequest {
  expectedRevision: number;
  constraints: PracticeConstraints;
}

export interface PracticeReviewRequest {
  submissionId: string;
  expectedRevision: number;
}

export interface PracticeRevisionRequest {
  submissionId: string;
  sourceRevisionId: string;
}

export interface PracticeSuggestion {
  questionId: string;
  questionRevisionId: string;
  content: RichContentV2;
  knowledgePoints: Array<FixedKnowledge>;
  questionType: string | null;
  difficulty: string | null;
  reason: string;
  answerState: string;
}

export interface PracticeSuggestions {
  items: Array<PracticeSuggestion>;
  requestedCount: number;
  selectedCount: number;
  coverage: Record<string, number>;
  gaps: Array<string>;
}

export interface PracticeItemView {
  practiceItemId: string;
  selectionId: string;
  itemKey: string;
  nodeKey: string;
  parentItemId: string | null;
  questionNo: string;
  ordinal: number;
  isScored: boolean;
  maxScoreUnits: number | null;
  questionId: string;
  questionRevisionId: string;
  content: RichContentV2;
  knowledgePoints: Array<FixedKnowledge>;
  sourceLocator: Record<string, unknown>;
  reason: string;
  answerState: string;
}

export interface PracticeRevisionView {
  practiceSetId: string;
  practiceRevisionId: string;
  version: number;
  state: 'draft' | 'reviewed';
  title: string;
  subjectId: string;
  analysisRunId: string;
  targetKnowledgePoints: Array<FixedKnowledge>;
  constraints: PracticeConstraints;
  inputHash: string;
  totalScoreUnits: number;
  draftItems: Array<PracticeDraftItem>;
  items: Array<PracticeItemView>;
  reviewedAt: string | null;
  createdAt: string;
}

export interface PracticeSetView {
  practiceSetId: string;
  title: string;
  subjectId: string;
  analysisRunId: string;
  revision: number;
  currentRevision: PracticeRevisionView;
  revisions: Array<PracticeRevisionView>;
  replayed: boolean;
}

export interface ExportRequest {
  submissionId: string;
  variant: 'student' | 'teacher' | 'score_template';
  assessmentId?: string | null;
}

export interface ExportReceipt {
  exportId: string;
  practiceRevisionId: string;
  inputHash: string;
  job: JobView;
  replayed: boolean;
  reused: boolean;
}

export interface ExportArtifact {
  artifactId: string;
  exportId: string;
  practiceRevisionId: string;
  variant: 'student' | 'teacher' | 'score_template';
  assessmentId: string | null;
  fileAssetId: string;
  filename: string;
  mediaType: string;
  sha256: string;
  byteSize: number;
  downloadUrl: string;
  createdAt: string;
}

export interface PracticeConversionRequest {
  submissionId: string;
  title: string;
  heldOn: string;
  classIds: Array<string>;
  participants: Array<AssessmentParticipantInput>;
}

export interface PracticeConversionReceipt {
  conversionId: string;
  paperId: string;
  paperRevisionId: string;
  assessmentId: string;
  practiceRevisionId: string;
  replayed: boolean;
}
