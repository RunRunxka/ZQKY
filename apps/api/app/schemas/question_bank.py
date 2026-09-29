"""独立题库契约：导入、拆题草稿、AI 建议、确认入库与题目管理。

题库与教材向量库完全分离：题库服务没有任何写入教材 collection 的路径。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

QuestionType = Literal[
    "single_choice", "multiple_choice", "true_false", "fill_blank", "short_answer", "other"
]
Difficulty = Literal["unspecified", "easy", "medium", "hard"]
DraftReviewState = Literal["needs_review", "reviewed", "excluded"]
ImportState = Literal[
    "uploaded", "extracting", "needs_review", "failed", "cancelled", "confirmed"
]
SuggestionState = Literal["pending", "applied", "rejected"]
QuestionStatus = Literal["confirmed", "archived"]
AnswerState = Literal["provided", "not_provided"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionOption(_Frozen):
    key: str = Field(min_length=1, max_length=8)
    textMarkdown: str = Field(min_length=1, max_length=4000)


class QuestionAnswer(_Strict):
    choiceKeys: list[str] = Field(default_factory=list, max_length=26)
    accepted: bool | None = None
    textMarkdown: str | None = Field(default=None, max_length=8000)

    @field_validator("choiceKeys")
    @classmethod
    def unique_keys(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("choiceKeys 不允许重复")
        return value


class QuestionContent(_Strict):
    type: QuestionType
    stemMarkdown: str = Field(min_length=1, max_length=20000)
    options: list[QuestionOption] = Field(default_factory=list, max_length=26)
    answer: QuestionAnswer | None = None
    explanationMarkdown: str | None = Field(default=None, max_length=20000)
    assetIds: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("options")
    @classmethod
    def unique_option_keys(cls, value: list[QuestionOption]) -> list[QuestionOption]:
        keys = [item.key for item in value]
        if len(set(keys)) != len(keys):
            raise ValueError("选项 key 不允许重复")
        return value


class QuestionMetadata(_Strict):
    stageId: str = Field(default="", max_length=64)
    gradeId: str = Field(default="", max_length=64)
    subjectId: str = Field(default="", max_length=64)
    editionId: str = Field(default="", max_length=64)
    knowledgeTags: list[str] = Field(default_factory=list, max_length=32)
    difficulty: Difficulty = "unspecified"


class SourceSpan(_Frozen):
    blockId: str
    charStart: int = Field(ge=0)
    charEnd: int = Field(ge=0)


class SourceBlockView(_Frozen):
    blockId: str
    ordinal: int
    text: str
    locator: "QuestionLocatorView"


class QuestionLocatorView(_Frozen):
    kind: Literal["markdown", "pdf", "docx", "text"]
    lineStart: int | None = None
    lineEnd: int | None = None
    pageStart: int | None = None
    pageEnd: int | None = None
    blockStart: int | None = None
    blockEnd: int | None = None


class DraftView(_Frozen):
    draftId: str
    importId: str
    revision: int
    content: QuestionContent
    metadata: QuestionMetadata
    sourceSpans: list[SourceSpan]
    extractionMethod: Literal["rule", "ai", "manual"]
    reviewState: DraftReviewState
    missingAnswerAcknowledged: bool
    warnings: list[str]
    duplicateOfQuestionId: str | None


class SuggestionView(_Frozen):
    suggestionId: str
    organizationJobId: str
    targetDraftId: str
    baseDraftRevision: int
    proposedContent: QuestionContent
    proposedMetadata: QuestionMetadata
    sourceBlockIds: list[str]
    state: SuggestionState
    note: str | None


class QuestionImportSummary(_Frozen):
    importId: str
    ownerId: str
    state: ImportState
    revision: int
    uploadedFileName: str
    uploadedBytes: int
    draftCount: int
    reviewedCount: int
    unassignedCount: int
    warnings: list[str]
    createdAt: str


class QuestionImportDetail(QuestionImportSummary):
    drafts: list[DraftView]
    unassignedBlocks: list[SourceBlockView]


class QuestionImportList(_Frozen):
    imports: list[QuestionImportSummary]


class QuestionImportCreate(_Strict):
    subjectId: str = Field(default="", max_length=64)
    gradeId: str = Field(default="", max_length=64)


class DraftPatchRequest(_Strict):
    expectedRevision: int = Field(ge=0)
    content: QuestionContent
    metadata: QuestionMetadata
    reviewState: DraftReviewState | None = None
    missingAnswerAcknowledged: bool | None = None


class DraftSplitRequest(_Strict):
    expectedRevision: int = Field(ge=0)
    charOffset: int = Field(ge=1)


class DraftMergeRequest(_Strict):
    expectedRevisions: dict[str, int] = Field(min_length=2, max_length=20)


class OrganizeRequest(_Strict):
    draftIds: list[str] = Field(default_factory=list, max_length=50)
    includeUnassigned: bool = False
    #: **当前聊天模型**的 profile id（本地或云端均可）；语义与详解一致，必填。
    #: 后端经 `model_runtime.resolve_chat_model` 解析——不得把 profile id 当模型名用。
    modelProfileId: str = Field(min_length=1, max_length=128)


class OrganizeBatchFailure(_Frozen):
    batchIndex: int
    code: str
    message: str


class OrganizeJobView(_Frozen):
    jobId: str
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    suggestionCount: int
    failedBatches: int
    errorCode: str | None
    # 建议明细与失败批原因：前端据此逐条「应用/忽略」，不用再猜建议 id
    suggestions: list[SuggestionView] = Field(default_factory=list)
    failures: list[OrganizeBatchFailure] = Field(default_factory=list)


class SuggestionApplyRequest(_Strict):
    expectedDraftRevision: int = Field(ge=0)
    accept: bool = True


class DuplicateResolution(_Strict):
    draftId: str
    action: Literal["skip", "link_existing", "edit_as_new", "none"] = "none"
    existingQuestionId: str | None = None


class QuestionConfirmRequest(_Strict):
    submissionId: str = Field(min_length=8, max_length=128)
    importId: str = Field(min_length=1, max_length=64)
    items: list["ConfirmItem"] = Field(min_length=1, max_length=200)
    duplicateResolutions: list[DuplicateResolution] = Field(default_factory=list)


class ConfirmItem(_Strict):
    draftId: str
    expectedDraftRevision: int = Field(ge=0)


class ConfirmResult(_Frozen):
    confirmedQuestionIds: list[str]
    linkedQuestionIds: list[str]
    skippedDraftIds: list[str]
    failures: list["ConfirmFailure"]


class ConfirmFailure(_Frozen):
    draftId: str
    code: str
    message: str


class QuestionSummary(_Frozen):
    questionId: str
    ownerId: str
    status: QuestionStatus
    revision: int
    type: QuestionType
    stemPreview: str
    subjectId: str
    gradeId: str
    editionId: str
    knowledgeTags: list[str]
    difficulty: Difficulty
    answerState: AnswerState
    confirmedAt: str


class QuestionDetail(QuestionSummary):
    content: QuestionContent
    metadata: QuestionMetadata
    sources: list[SourceSpan]
    sourceImportId: str | None


class QuestionList(_Frozen):
    questions: list[QuestionSummary]
    total: int
    offset: int
    limit: int


class QuestionPatchRequest(_Strict):
    expectedRevision: int = Field(ge=0)
    content: QuestionContent
    metadata: QuestionMetadata


QuestionConfirmRequest.model_rebuild()
ConfirmResult.model_rebuild()
QuestionImportDetail.model_rebuild()
SourceBlockView.model_rebuild()
