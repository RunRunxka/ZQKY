"""教材目录、导入、任教范围、Embedding 配置与索引代的共享请求/响应模型。

本模块是前后端唯一契约来源（RAG-REBUILD v1.0 · C0）。请求模型 `extra="forbid"`：
未知字段一律 422，避免客户端字段名漂移被静默忽略。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OwnerId = Literal["system", "local-user"]
LibraryKind = Literal["base", "personal"]
ImportState = Literal[
    "uploaded", "extracting", "needs_review", "queued", "chunking",
    "embedding", "indexing", "ready", "failed", "cancelled", "discarded",
]
JobKind = Literal["ingest", "rebuild", "cleanup"]
JobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]
GenerationState = Literal["building", "ready", "aborted"]
ChunkRegion = Literal["body", "exercise"]

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
SUPPORTED_SUFFIXES = (".md", ".pdf", ".docx")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _ReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- 字典


class GradeView(_ReadModel):
    id: str
    label: str
    stageId: str


class SubjectView(_ReadModel):
    id: str
    label: str


class EditionView(_ReadModel):
    id: str
    label: str


class StageView(_ReadModel):
    id: str
    label: str


class TextbookTaxonomy(_ReadModel):
    stages: list[StageView]
    grades: list[GradeView]
    subjects: list[SubjectView]
    editions: list[EditionView]


# ----------------------------------------------------------------------- 教材元数据


class DocumentMetadataInput(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    stageId: str = Field(min_length=1, max_length=64)
    gradeIds: list[str] = Field(min_length=1, max_length=3)
    subjectId: str = Field(min_length=1, max_length=64)
    editionId: str = Field(min_length=1, max_length=64)
    publicationLabel: str = Field(default="", max_length=120)
    volumeLabel: str = Field(default="", max_length=120)

    @field_validator("gradeIds")
    @classmethod
    def unique_grades(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("gradeIds 不允许重复")
        return value


class DocumentMetadataView(_ReadModel):
    metadataRevisionId: str
    title: str
    stageId: str
    gradeIds: list[str]
    subjectId: str
    editionId: str
    publicationLabel: str
    volumeLabel: str


# ------------------------------------------------------------------------- 数据修订


class DocumentRevisionSummary(_ReadModel):
    revisionId: str
    originalFileSha256: str
    normalizedTextSha256: str
    parserVersion: str
    charCount: int
    chunkCount: int
    createdAt: str


class ChunkPreview(_ReadModel):
    ordinal: int
    charStart: int
    charEnd: int
    region: ChunkRegion
    chapterPath: list[str]
    text: str


class ImportParsedView(_ReadModel):
    charCount: int
    chunkCount: int
    bodyChunkCount: int
    exerciseChunkCount: int
    needsOcr: bool
    sourceKind: Literal["markdown", "pdf", "docx"]
    pageCount: int | None
    blockCount: int | None
    warnings: list[str]
    preview: list[ChunkPreview]


class ImportDraftView(_ReadModel):
    importId: str
    ownerId: OwnerId
    state: ImportState
    revision: int
    uploadedFileName: str
    uploadedBytes: int
    targetDocumentId: str | None
    expectedCurrentRevisionId: str | None
    metadata: DocumentMetadataInput | None
    metadataConfirmed: bool
    parsed: ImportParsedView | None
    warnings: list[str]
    errorCode: str | None
    canCommit: bool
    createdAt: str


class ImportDraftList(_ReadModel):
    imports: list[ImportDraftView]


class ImportCreateResponse(_ReadModel):
    draft: ImportDraftView


class ImportPatchRequest(StrictModel):
    expectedRevision: int = Field(ge=0)
    metadata: DocumentMetadataInput


class ImportCommitRequest(StrictModel):
    expectedRevision: int = Field(ge=0)
    submissionId: str = Field(min_length=8, max_length=128)
    libraryIds: list[str] = Field(min_length=1, max_length=32)
    acknowledgeWarnings: bool = False


class ImportDiscardRequest(StrictModel):
    """放弃导入草稿：只把状态置 ``discarded``；草稿记录、原始文件与解析产物保留。"""

    expectedRevision: int = Field(ge=0)


# --------------------------------------------------------------------------- 书册


class DocumentSummary(_ReadModel):
    documentId: str
    ownerId: OwnerId
    title: str
    libraryIds: list[str]
    gradeIds: list[str]
    subjectId: str
    editionId: str
    metadataRevisionId: str
    currentRevision: DocumentRevisionSummary | None
    pendingRevisionId: str | None
    deletedAt: str | None
    revision: int


class DocumentDetail(DocumentSummary):
    metadata: DocumentMetadataView
    warnings: list[str]


class DocumentList(_ReadModel):
    documents: list[DocumentSummary]


class DocumentPatchRequest(StrictModel):
    expectedRevision: int = Field(ge=0)
    metadata: DocumentMetadataInput
    libraryIds: list[str] = Field(min_length=1, max_length=32)


class DocumentDeleteRequest(StrictModel):
    expectedRevision: int = Field(ge=0)


class SourceSpanView(_ReadModel):
    documentRevisionId: str
    normalizedTextSha256: str
    charStart: int
    charEnd: int
    text: str
    locator: "LocatorView"


class LocatorView(_ReadModel):
    kind: Literal["markdown", "pdf", "docx"]
    lineStart: int | None = None
    lineEnd: int | None = None
    pageStart: int | None = None
    pageEnd: int | None = None
    blockStart: int | None = None
    blockEnd: int | None = None


# --------------------------------------------------------------------------- 逻辑库


class LibraryCreateRequest(StrictModel):
    kind: LibraryKind
    displayName: str = Field(min_length=1, max_length=120)
    gradeId: str | None = Field(default=None, max_length=64)
    subjectId: str = Field(min_length=1, max_length=64)
    editionId: str = Field(min_length=1, max_length=64)


class LibraryPatchRequest(StrictModel):
    expectedRevision: int = Field(ge=0)
    displayName: str | None = Field(default=None, min_length=1, max_length=120)
    gradeId: str | None = Field(default=None, max_length=64)
    editionId: str | None = Field(default=None, max_length=64)


class LibrarySummary(_ReadModel):
    libraryId: str
    kind: LibraryKind
    ownerId: OwnerId
    displayName: str
    gradeId: str | None
    subjectId: str
    editionId: str
    documentCount: int
    readyDocumentCount: int
    revision: int
    deletedAt: str | None


class LibraryDetail(LibrarySummary):
    documents: list[DocumentSummary]


class LibraryList(_ReadModel):
    libraries: list[LibrarySummary]


# --------------------------------------------------------------------------- 任务


class JobProgress(_ReadModel):
    documentsDone: int
    documentsTotal: int
    chunksDone: int
    chunksTotal: int
    currentTitle: str | None


class JobView(_ReadModel):
    jobId: str
    kind: JobKind
    state: JobState
    targetGenerationId: str | None
    baseGenerationId: str | None
    documentId: str | None
    inputRevisionId: str | None
    attempt: int
    progress: JobProgress
    errorCode: str | None
    errorMessage: str | None
    retryable: bool
    createdAt: str
    updatedAt: str


class JobList(_ReadModel):
    jobs: list[JobView]


# --------------------------------------------------------------------- 任教设置


class TextbookSelection(StrictModel):
    gradeId: str = Field(min_length=1, max_length=64)
    subjectId: str = Field(min_length=1, max_length=64)
    editionId: str = Field(min_length=1, max_length=64)
    documentIds: list[str] = Field(max_length=64)

    @field_validator("documentIds")
    @classmethod
    def unique_documents(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("documentIds 不允许重复")
        return value


class TeachingSettingsView(_ReadModel):
    ownerId: OwnerId
    selection: TextbookSelection | None
    revision: int
    updatedAt: str | None
    scopeReady: bool
    scopeReason: str | None


class TeachingSettingsUpdate(StrictModel):
    expectedRevision: int = Field(ge=0)
    selection: TextbookSelection | None


# ------------------------------------------------------------------ Embedding 配置


class EmbeddingModelCandidate(_ReadModel):
    name: str
    digest: str
    sizeBytes: int
    family: str
    parameterSize: str
    isEmbeddingCapable: bool


class EmbeddingModelList(_ReadModel):
    baseUrl: str
    available: bool
    reason: str | None
    models: list[EmbeddingModelCandidate]


class EmbeddingProbeRequest(StrictModel):
    modelName: str = Field(min_length=1, max_length=200)
    baseUrl: str | None = Field(default=None, max_length=200)
    queryPrefix: str = Field(default="", max_length=200)
    documentPrefix: str = Field(default="", max_length=200)
    normalization: Literal["none", "l2"] = "none"


class EmbeddingProbeView(_ReadModel):
    modelName: str
    modelManifestDigest: str
    dimensions: int
    distance: Literal["cosine"]
    sampleCount: int
    nonZero: bool
    finite: bool
    stableDigest: bool
    alreadyConfigured: bool
    existingProfileId: str | None


class EmbeddingProfileCreate(StrictModel):
    modelName: str = Field(min_length=1, max_length=200)
    baseUrl: str | None = Field(default=None, max_length=200)
    queryPrefix: str = Field(default="", max_length=200)
    documentPrefix: str = Field(default="", max_length=200)
    normalization: Literal["none", "l2"] = "none"


class EmbeddingProfileView(_ReadModel):
    profileId: str
    fingerprint: str
    adapter: Literal["ollama"]
    nativeBaseUrl: str
    modelName: str
    modelManifestDigest: str
    dimensions: int
    distance: Literal["cosine"]
    queryPrefix: str
    documentPrefix: str
    normalization: str
    verifiedAt: str
    retiredAt: str | None
    isActive: bool
    installed: bool


class EmbeddingProfileList(_ReadModel):
    profiles: list[EmbeddingProfileView]
    activeProfileId: str | None


# ------------------------------------------------------------------------ 索引代


class GenerationView(_ReadModel):
    generationId: str
    collectionName: str
    profileId: str
    state: GenerationState
    chunkTotal: int
    documentTotal: int
    createdAt: str
    publishedAt: str | None


class IndexStatusView(_ReadModel):
    activeGenerationId: str | None
    activeProfileId: str | None
    activeProfileName: str | None
    activeProfileDimensions: int | None
    generation: GenerationView | None
    rebuildJob: JobView | None
    generationCount: int
    qdrantAvailable: bool
    qdrantReason: str | None
    scopeReady: bool
    scopeReason: str | None


class RebuildCreateRequest(StrictModel):
    submissionId: str = Field(min_length=8, max_length=128)
    profileId: str = Field(min_length=1, max_length=64)


# ------------------------------------------------------------------ 查询参数模型


class LibraryQuery(StrictModel):
    kind: LibraryKind | None = None
    gradeId: str | None = None
    subjectId: str | None = None
    editionId: str | None = None
    includeDeleted: bool = False


class DocumentQuery(StrictModel):
    libraryId: str | None = None
    gradeId: str | None = None
    subjectId: str | None = None
    editionId: str | None = None
    includeDeleted: bool = False


SourceSpanView.model_rebuild()
DocumentDetail.model_rebuild()


class ScopeCheckRequest(StrictModel):
    selection: TextbookSelection


class ScopeCheckView(_ReadModel):
    scopeReady: bool
    reason: str | None
    documents: list[DocumentSummary]
    missingDocumentIds: list[str]
