/**
 * 独立题库契约（RAG-REBUILD v1.0 · C0）。
 * 与 `apps/api/app/schemas/question_bank.py` 一一对应；改任一侧必须同步另一侧。
 */

export type QuestionType =
  | 'single_choice'
  | 'multiple_choice'
  | 'true_false'
  | 'fill_blank'
  | 'short_answer'
  | 'other';
export type Difficulty = 'unspecified' | 'easy' | 'medium' | 'hard';
export type DraftReviewState = 'needs_review' | 'reviewed' | 'excluded';
export type QuestionImportState =
  | 'uploaded'
  | 'extracting'
  | 'needs_review'
  | 'failed'
  | 'cancelled'
  | 'confirmed';
export type SuggestionState = 'pending' | 'applied' | 'rejected';
export type QuestionStatus = 'confirmed' | 'archived';
export type AnswerState = 'provided' | 'not_provided';

export interface QuestionOption {
  key: string;
  textMarkdown: string;
}

export interface QuestionAnswer {
  choiceKeys: string[];
  accepted: boolean | null;
  textMarkdown: string | null;
}

export interface QuestionContent {
  type: QuestionType;
  stemMarkdown: string;
  options: QuestionOption[];
  answer: QuestionAnswer | null;
  explanationMarkdown: string | null;
  assetIds: string[];
}

export interface QuestionMetadata {
  stageId: string;
  gradeId: string;
  subjectId: string;
  editionId: string;
  knowledgeTags: string[];
  difficulty: Difficulty;
}

export interface SourceSpan {
  blockId: string;
  charStart: number;
  charEnd: number;
}

export interface QuestionLocatorView {
  kind: 'markdown' | 'pdf' | 'docx' | 'text';
  lineStart: number | null;
  lineEnd: number | null;
  pageStart: number | null;
  pageEnd: number | null;
  blockStart: number | null;
  blockEnd: number | null;
}

export interface SourceBlockView {
  blockId: string;
  ordinal: number;
  text: string;
  locator: QuestionLocatorView;
}

export interface DraftView {
  draftId: string;
  importId: string;
  revision: number;
  content: QuestionContent;
  metadata: QuestionMetadata;
  sourceSpans: SourceSpan[];
  extractionMethod: 'rule' | 'ai' | 'manual';
  reviewState: DraftReviewState;
  missingAnswerAcknowledged: boolean;
  warnings: string[];
  duplicateOfQuestionId: string | null;
  knowledgeLinks?: DraftKnowledgeLinkView[];
}

export interface SuggestionView {
  suggestionId: string;
  organizationJobId: string;
  targetDraftId: string;
  baseDraftRevision: number;
  proposedContent: QuestionContent;
  proposedMetadata: QuestionMetadata;
  sourceBlockIds: string[];
  state: SuggestionState;
  note: string | null;
}

export interface QuestionImportSummary {
  importId: string;
  ownerId: string;
  state: QuestionImportState;
  revision: number;
  uploadedFileName: string;
  uploadedBytes: number;
  draftCount: number;
  reviewedCount: number;
  unassignedCount: number;
  warnings: string[];
  createdAt: string;
}

export interface QuestionImportDetail extends QuestionImportSummary {
  drafts: DraftView[];
  unassignedBlocks: SourceBlockView[];
}

export interface QuestionImportList {
  imports: QuestionImportSummary[];
}

/** 草稿的正式知识点关联（教师编辑；确认时写入正式题修订关联）。 */
export interface DraftKnowledgeLinkView {
  knowledgePointId: string;
  knowledgeRevisionId: string;
  knowledgeNameSnapshot: string;
  subjectIdSnapshot: string;
  role: 'primary' | 'secondary';
  source: 'human' | 'ai';
}

export interface DraftKnowledgeLinkInput {
  knowledgePointId: string;
  role?: 'primary' | 'secondary';
}

/** 正式题修订的知识点关联（不可变修订上的快照；后端 `QuestionKnowledgeLinkView`，无 source 字段）。 */
export interface QuestionKnowledgeLinkView {
  knowledgePointId: string;
  knowledgeRevisionId: string;
  knowledgeNameSnapshot: string;
  subjectIdSnapshot: string;
  role: 'primary' | 'secondary';
}

export interface DraftPatchRequest {
  expectedRevision: number;
  content: QuestionContent;
  metadata: QuestionMetadata;
  reviewState?: DraftReviewState | null;
  missingAnswerAcknowledged?: boolean | null;
  /** 提供即整表替换（空数组 = 清空）；缺省不动 */
  knowledgeLinks?: DraftKnowledgeLinkInput[] | null;
}

export interface DraftSplitRequest {
  expectedRevision: number;
  charOffset: number;
}

export interface OrganizeBatchFailure {
  batchIndex: number;
  code: string;
  message: string;
}

/** 题库任务视图（B2 六态统一；attempt 由统一任务引擎维护）。 */
export interface OrganizeJobView {
  jobId: string;
  state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'interrupted';
  attempt?: number;
  suggestionCount: number;
  failedBatches: number;
  errorCode: string | null;
  suggestions: SuggestionView[];
  failures: OrganizeBatchFailure[];
}

/** AI 补题请求：冻结允许知识点/可选证据/题型/数量与模型指纹。 */
export interface QuestionGenerationRequest {
  modelProfileId: string;
  subjectId?: string;
  knowledgePointIds?: string[];
  questionTypes?: QuestionType[];
  difficulty?: Difficulty;
  count?: number;
  instructions?: string | null;
  materials?: string[];
}

export interface GenerationJobView {
  jobId: string;
  state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'interrupted';
  attempt?: number;
  importId: string | null;
  candidateCount: number;
  errorCode: string | null;
}

export interface DuplicateResolution {
  draftId: string;
  action: 'skip' | 'link_existing' | 'edit_as_new' | 'none';
  existingQuestionId: string | null;
}

export interface ConfirmItem {
  draftId: string;
  expectedDraftRevision: number;
}

export interface QuestionConfirmRequest {
  submissionId: string;
  importId: string;
  items: ConfirmItem[];
  duplicateResolutions: DuplicateResolution[];
}

export interface ConfirmFailure {
  draftId: string;
  code: string;
  message: string;
}

export interface ConfirmResult {
  confirmedQuestionIds: string[];
  linkedQuestionIds: string[];
  skippedDraftIds: string[];
  failures: ConfirmFailure[];
}

export interface QuestionSummary {
  questionId: string;
  ownerId: string;
  status: QuestionStatus;
  revision: number;
  type: QuestionType;
  stemPreview: string;
  subjectId: string;
  gradeId: string;
  editionId: string;
  knowledgeTags: string[];
  difficulty: Difficulty;
  answerState: AnswerState;
  confirmedAt: string;
}

export interface QuestionDetail extends QuestionSummary {
  content: QuestionContent;
  metadata: QuestionMetadata;
  sources: SourceSpan[];
  sourceImportId: string | null;
  /** 正式知识点关联（修订快照；缺省空数组 = 未正式关联） */
  knowledgeLinks?: QuestionKnowledgeLinkView[];
}

export interface QuestionList {
  questions: QuestionSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface QuestionPatchRequest {
  expectedRevision: number;
  content: QuestionContent;
  metadata: QuestionMetadata;
  /** 提供即整表替换正式知识点关联；缺省 = 复制旧正式关联 */
  knowledgeLinks?: DraftKnowledgeLinkInput[] | null;
}

export const QUESTION_TYPE_LABEL: Record<QuestionType, string> = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  true_false: '判断题',
  fill_blank: '填空题',
  short_answer: '简答题',
  other: '其他',
};

export const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  unspecified: '未标注',
  easy: '容易',
  medium: '中等',
  hard: '较难',
};

export const REVIEW_STATE_LABEL: Record<DraftReviewState, string> = {
  needs_review: '待校对',
  reviewed: '已校对',
  excluded: '已排除',
};

export const ORGANIZE_STATE_LABEL: Record<OrganizeJobView['state'], string> = {
  queued: '排队中',
  running: '整理中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
  interrupted: '已中断',
};
