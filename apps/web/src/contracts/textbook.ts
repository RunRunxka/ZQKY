/**
 * 教材目录与 Embedding 契约（RAG-REBUILD v1.0 · C0）。
 * 与 `apps/api/app/schemas/textbook.py` 一一对应；改任一侧必须同步另一侧。
 */

export type OwnerId = 'system' | 'local-user';
export type LibraryKind = 'base' | 'personal';
export type ImportState =
  | 'uploaded'
  | 'extracting'
  | 'needs_review'
  | 'queued'
  | 'chunking'
  | 'embedding'
  | 'indexing'
  | 'ready'
  | 'failed'
  | 'cancelled'
  /** 草稿已放弃（记录/原始文件/解析产物保留） */
  | 'discarded';
export type JobKind = 'ingest' | 'rebuild' | 'cleanup';
export type JobState = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
export type GenerationState = 'building' | 'ready' | 'aborted';
export type ChunkRegion = 'body' | 'exercise';

export const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;
export const SUPPORTED_SUFFIXES = ['.md', '.pdf', '.docx'] as const;

export interface GradeView {
  id: string;
  label: string;
  stageId: string;
}

export interface SubjectView {
  id: string;
  label: string;
}

export interface EditionView {
  id: string;
  label: string;
}

export interface StageView {
  id: string;
  label: string;
}

export interface TextbookTaxonomy {
  stages: StageView[];
  grades: GradeView[];
  subjects: SubjectView[];
  editions: EditionView[];
}

export interface DocumentMetadataInput {
  title: string;
  stageId: string;
  gradeIds: string[];
  subjectId: string;
  editionId: string;
  publicationLabel: string;
  volumeLabel: string;
}

export interface DocumentMetadataView extends DocumentMetadataInput {
  metadataRevisionId: string;
}

export interface DocumentRevisionSummary {
  revisionId: string;
  originalFileSha256: string;
  normalizedTextSha256: string;
  parserVersion: string;
  charCount: number;
  chunkCount: number;
  createdAt: string;
}

export interface ChunkPreview {
  ordinal: number;
  charStart: number;
  charEnd: number;
  region: ChunkRegion;
  chapterPath: string[];
  text: string;
}

export interface ImportParsedView {
  charCount: number;
  chunkCount: number;
  bodyChunkCount: number;
  exerciseChunkCount: number;
  needsOcr: boolean;
  sourceKind: 'markdown' | 'pdf' | 'docx';
  pageCount: number | null;
  blockCount: number | null;
  warnings: string[];
  preview: ChunkPreview[];
}

export interface ImportDraftView {
  importId: string;
  ownerId: OwnerId;
  state: ImportState;
  revision: number;
  uploadedFileName: string;
  uploadedBytes: number;
  targetDocumentId: string | null;
  expectedCurrentRevisionId: string | null;
  metadata: DocumentMetadataInput | null;
  metadataConfirmed: boolean;
  parsed: ImportParsedView | null;
  warnings: string[];
  errorCode: string | null;
  canCommit: boolean;
  createdAt: string;
}

export interface ImportDraftList {
  imports: ImportDraftView[];
}

export interface ImportCreateResponse {
  draft: ImportDraftView;
}

/**
 * 放弃导入草稿（对应后端 `ImportDiscardRequest`）：
 * 只把状态置 `discarded`；草稿记录、原始文件与解析产物保留。
 */
export interface ImportDiscardRequest {
  expectedRevision: number;
}

export interface DocumentSummary {
  documentId: string;
  ownerId: OwnerId;
  title: string;
  libraryIds: string[];
  gradeIds: string[];
  subjectId: string;
  editionId: string;
  metadataRevisionId: string;
  currentRevision: DocumentRevisionSummary | null;
  pendingRevisionId: string | null;
  deletedAt: string | null;
  revision: number;
}

export interface DocumentDetail extends DocumentSummary {
  metadata: DocumentMetadataView;
  warnings: string[];
}

export interface DocumentList {
  documents: DocumentSummary[];
}

export interface LocatorView {
  kind: 'markdown' | 'pdf' | 'docx';
  lineStart: number | null;
  lineEnd: number | null;
  pageStart: number | null;
  pageEnd: number | null;
  blockStart: number | null;
  blockEnd: number | null;
}

export interface SourceSpanView {
  documentRevisionId: string;
  normalizedTextSha256: string;
  charStart: number;
  charEnd: number;
  text: string;
  locator: LocatorView;
}

export interface LibrarySummary {
  libraryId: string;
  kind: LibraryKind;
  ownerId: OwnerId;
  displayName: string;
  gradeId: string | null;
  subjectId: string;
  editionId: string;
  documentCount: number;
  readyDocumentCount: number;
  revision: number;
  deletedAt: string | null;
}

export interface LibraryDetail extends LibrarySummary {
  documents: DocumentSummary[];
}

export interface LibraryList {
  libraries: LibrarySummary[];
}

export interface JobProgress {
  documentsDone: number;
  documentsTotal: number;
  chunksDone: number;
  chunksTotal: number;
  currentTitle: string | null;
}

export interface JobView {
  jobId: string;
  kind: JobKind;
  state: JobState;
  targetGenerationId: string | null;
  baseGenerationId: string | null;
  documentId: string | null;
  inputRevisionId: string | null;
  attempt: number;
  progress: JobProgress;
  errorCode: string | null;
  errorMessage: string | null;
  retryable: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface JobList {
  jobs: JobView[];
}

export interface TextbookSelection {
  gradeId: string;
  subjectId: string;
  editionId: string;
  documentIds: string[];
}

export interface TeachingSettingsView {
  ownerId: OwnerId;
  selection: TextbookSelection | null;
  revision: number;
  updatedAt: string | null;
  scopeReady: boolean;
  scopeReason: string | null;
}

export interface EmbeddingModelCandidate {
  name: string;
  digest: string;
  sizeBytes: number;
  family: string;
  parameterSize: string;
  isEmbeddingCapable: boolean;
}

export interface EmbeddingModelList {
  baseUrl: string;
  available: boolean;
  reason: string | null;
  models: EmbeddingModelCandidate[];
}

export interface EmbeddingProbeRequest {
  modelName: string;
  baseUrl?: string | null;
  queryPrefix?: string;
  documentPrefix?: string;
  normalization?: 'none' | 'l2';
}

export interface EmbeddingProbeView {
  modelName: string;
  modelManifestDigest: string;
  dimensions: number;
  distance: 'cosine';
  sampleCount: number;
  nonZero: boolean;
  finite: boolean;
  stableDigest: boolean;
  alreadyConfigured: boolean;
  existingProfileId: string | null;
}

export interface EmbeddingProfileView {
  profileId: string;
  fingerprint: string;
  adapter: 'ollama';
  nativeBaseUrl: string;
  modelName: string;
  modelManifestDigest: string;
  dimensions: number;
  distance: 'cosine';
  queryPrefix: string;
  documentPrefix: string;
  normalization: string;
  verifiedAt: string;
  retiredAt: string | null;
  isActive: boolean;
  installed: boolean;
}

export interface EmbeddingProfileList {
  profiles: EmbeddingProfileView[];
  activeProfileId: string | null;
}

export interface GenerationView {
  generationId: string;
  collectionName: string;
  profileId: string;
  state: GenerationState;
  chunkTotal: number;
  documentTotal: number;
  createdAt: string;
  publishedAt: string | null;
}

export interface IndexStatusView {
  activeGenerationId: string | null;
  activeProfileId: string | null;
  activeProfileName: string | null;
  activeProfileDimensions: number | null;
  generation: GenerationView | null;
  rebuildJob: JobView | null;
  generationCount: number;
  qdrantAvailable: boolean;
  qdrantReason: string | null;
  scopeReady: boolean;
  scopeReason: string | null;
}

export interface ScopeCheckView {
  scopeReady: boolean;
  reason: string | null;
  documents: DocumentSummary[];
  missingDocumentIds: string[];
}

/** 导入任务的用户可见阶段文案；未列出的状态按原样显示。 */
export const IMPORT_STATE_LABEL: Record<ImportState, string> = {
  uploaded: '已上传',
  extracting: '解析中',
  needs_review: '待确认',
  queued: '排队中',
  chunking: '分块中',
  embedding: '向量化中',
  indexing: '写入索引中',
  ready: '已入库',
  failed: '失败',
  cancelled: '已取消',
  discarded: '已放弃',
};
