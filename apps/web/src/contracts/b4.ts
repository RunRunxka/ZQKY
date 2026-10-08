/** B4 v1 shared wire contract; mirrored from app/contracts/b4.py. */
import type { JobView, RichContentV2, ScoreStatus, Observation } from './teaching-loop';
import type { AssessmentParticipantInput } from './assessments';

export interface AnalysisCreateRequest {
  submissionId: string;
  scoreRevisionId: string;
  selectedParticipantIds: Array<string>;
  ruleCode: 'any_loss_v1';
}

/**
 * 学情运行归档/恢复请求体：镜像后端 `AnalysisArchiveRequest`，
 * 当前无业务字段（后端 `extra="forbid"`），客户端固定提交 `{}`。
 */
export type AnalysisArchiveRequest = Record<string, never>;

export interface FrozenParticipant {
  participantId: string;
  studentId: string;
  studentNo: string | null;
  name: string;
  classId: string;
  /**
   * 班名走「名称优先」：密封事实只冻结 classId，读路径按同 owner JOIN `classes.name` 实时填充；
   * 班名确实缺失才是 null（界面此时显示短号 + `classNameNote`，不伪造名称）。
   */
  className: string | null;
  /** 班名缺失时的兜底说明；只在 `className` 为 null 时展示，不当作名称。 */
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
  /** 软归档时间；缺省/未带 = 未归档（归档只写该字段，报告内容不动） */
  archivedAt?: string | null;
  createdAt: string;
}

export interface ClassReportRow {
  classId: string;
  /** 结果行只冻结 classId；班名由读路径 JOIN `classes.name` 实时填充，缺失才 null（见 FrozenParticipant）。 */
  className: string | null;
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

/** 练习集归档/恢复（对应后端 `PracticeSetStatusRequest`：只带乐观锁修订号）。 */
export interface PracticeSetStatusRequest {
  expectedRevision: number;
}

/**
 * 彻底删除练习集回执（200）：受引用守卫的物理删除，不可恢复
 * （纯 draft 集合的子行、修订与集合行在同一事务删除）。
 * 有已审核修订/导出/转换引用 → 409 `PRACTICE_IN_USE` + `details.counts`（见 `PracticeSetReferenceCounts`）。
 */
export interface PracticeSetDeleteReceipt {
  deleted: boolean;
  practiceSetId: string;
}

/** `PRACTICE_IN_USE` 的逐项引用计数（键与后端一致；未知键由界面原样列出，不隐藏）。 */
export interface PracticeSetReferenceCounts {
  reviewedRevisions: number;
  exports: number;
  conversions: number;
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
  /**
   * 练习来源的展示名（只读派生，镜像后端同名字段）：来源学情报告的原卷标题；
   * 读路径实时 JOIN，来源卷修订缺失时为 null（界面回落 `analysisRunId` 短号，不伪造名称）。
   */
  sourcePaperTitle?: string | null;
  /** 来源学情报告的创建时间（只读派生）；缺失为 null，界面显示「时间未记录」而不猜造。 */
  sourceCreatedAt?: string | null;
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
  /** 练习来源的展示名（只读派生，与 `currentRevision` 同口径；见 `PracticeRevisionView`）。 */
  sourcePaperTitle?: string | null;
  /** 来源学情报告的创建时间（只读派生，与 `currentRevision` 同口径）。 */
  sourceCreatedAt?: string | null;
  /** 练习集状态；缺省视为 `'active'`（对齐后端对归档功能上线前既有收据的默认值） */
  status?: 'active' | 'archived';
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
