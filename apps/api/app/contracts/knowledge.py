"""知识点库 v1 冻结契约（TEACHING-LOOP B1 / T20）。

与 ``docs/design/teaching-loop-v1/sql/knowledge.sql``、``06-data-design.md`` 的
知识点节一致；设计未定义、由 B1 任务卡冻结补齐的部分（导入批次、AI 候选复用同一
确认流程）在本模块给出唯一形状。**知识点、名单、富内容类型不复制第二份**：
知识点视图/请求只在这里定义，前端镜像在 ``apps/web/src/contracts/knowledge.ts``。

关键语义（不得改写）：

- ``code`` 是**学科内**身份键（``UNIQUE(subject_id, code)``）；名称或别名相同只提示，不合并。
- 身份（``id``）与内容修订（``revisionId``/``version``）分离：改名 = 追加修订；
  被引用历史修订永久保留（DB 触发器 ``IMMUTABLE_REVISION``）。
- ``revision`` 是可变实体的乐观锁；更新必须核 ``expectedRevision``；
  可选字段空白默认不修改，**明确清空**才写空（``clearFields``）。
- AI 候选只生成 ``source="ai"`` 的导入批次（待确认），不直接写正式表。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.teaching_loop import AssetRef, ErrorIssue

# --------------------------------------------------------------------------- 枚举

KnowledgePointStatus = Literal["active", "archived"]
KNOWLEDGE_POINT_STATUSES: frozenset[str] = frozenset({"active", "archived"})

KnowledgeImportState = Literal["uploaded", "reviewing", "confirmed", "failed", "cancelled"]
KNOWLEDGE_IMPORT_STATES: frozenset[str] = frozenset(
    {"uploaded", "reviewing", "confirmed", "failed", "cancelled"}
)
KnowledgeImportSource = Literal["file", "ai"]
KnowledgeRowAction = Literal["create", "update", "ignore"]
KNOWLEDGE_ROW_ACTIONS: frozenset[str] = frozenset({"create", "update", "ignore"})
KnowledgeLinkSource = Literal["human", "ai_confirmed"]

#: 导入表字段（表头/映射只允许这六个）
KNOWLEDGE_IMPORT_FIELDS: tuple[str, ...] = (
    "subjectCode",
    "code",
    "name",
    "description",
    "parentCode",
    "aliases",
)

# --------------------------------------------------------------------------- 错误码

KNOWLEDGE_CODE_CONFLICT = "KNOWLEDGE_CODE_CONFLICT"
KNOWLEDGE_PARENT_INVALID = "KNOWLEDGE_PARENT_INVALID"
KNOWLEDGE_CROSS_SUBJECT_PARENT = "KNOWLEDGE_CROSS_SUBJECT_PARENT"
KNOWLEDGE_CYCLE = "KNOWLEDGE_CYCLE"
KNOWLEDGE_ARCHIVED = "KNOWLEDGE_ARCHIVED"
KNOWLEDGE_ROW_INVALID = "KNOWLEDGE_ROW_INVALID"
KNOWLEDGE_POINT_IN_USE = "KNOWLEDGE_POINT_IN_USE"
KNOWLEDGE_SCOPE_UNAVAILABLE = "KNOWLEDGE_SCOPE_UNAVAILABLE"
KNOWLEDGE_EXTRACTION_NOT_READY = "KNOWLEDGE_EXTRACTION_NOT_READY"
KNOWLEDGE_IMPORT_BLOCKING_ISSUES = "KNOWLEDGE_IMPORT_BLOCKING_ISSUES"
KNOWLEDGE_IMPORT_CONFIRMED = "KNOWLEDGE_IMPORT_CONFIRMED"
KNOWLEDGE_SUBJECT_UNKNOWN = "KNOWLEDGE_SUBJECT_UNKNOWN"
KNOWLEDGE_LINK_INVALID = "KNOWLEDGE_LINK_INVALID"
KNOWLEDGE_LINK_DUPLICATE = "KNOWLEDGE_LINK_DUPLICATE"
KNOWLEDGE_SUGGESTION_INVALID_JSON = "KNOWLEDGE_SUGGESTION_INVALID_JSON"
KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE = "KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE"
KNOWLEDGE_SUGGESTION_TRUNCATED = "KNOWLEDGE_SUGGESTION_TRUNCATED"
KNOWLEDGE_SUGGESTION_NO_EVIDENCE = "KNOWLEDGE_SUGGESTION_NO_EVIDENCE"
TEXTBOOK_EVIDENCE_INVALID = "TEXTBOOK_EVIDENCE_INVALID"
TEXTBOOK_EVIDENCE_UNAVAILABLE = "TEXTBOOK_EVIDENCE_UNAVAILABLE"

# --------------------------------------------------------------------------- 基类


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------- 知识点视图


class KnowledgePointView(_Frozen):
    """知识点身份 + 当前内容修订 + 别名（列表与详情共用）。"""

    id: str
    subject_id: str = Field(alias="subjectId", min_length=1)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    parent_id: str | None = Field(default=None, alias="parentId")
    parent_code: str | None = Field(default=None, alias="parentCode")
    sort_order: int = Field(default=0, alias="sortOrder")
    status: KnowledgePointStatus = "active"
    #: 乐观锁（可变实体编辑版本）
    revision: int = Field(ge=0)
    #: 固定内容修订身份与版本号（不可变）
    revision_id: str | None = Field(default=None, alias="revisionId")
    version: int = Field(default=0, ge=0)
    aliases: list[str] = Field(default_factory=list)
    #: 教材依据文档的年级去重集合（只读展示字段；无依据或未按需查询为空列表）
    grade_ids: list[str] = Field(default_factory=list, alias="gradeIds")
    created_at: str = Field(alias="createdAt")


class KnowledgePointList(_Frozen):
    items: list[KnowledgePointView]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class KnowledgePointCreateRequest(_Strict):
    subject_id: str = Field(alias="subjectId", min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    parent_id: str | None = Field(default=None, alias="parentId")
    parent_code: str | None = Field(default=None, alias="parentCode")
    sort_order: int = Field(default=0, alias="sortOrder", ge=0, le=1_000_000)
    aliases: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("aliases")
    @classmethod
    def unique_aliases(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("aliases 不允许空字符串")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("aliases 不允许重复")
        return cleaned


class KnowledgePointUpdateRequest(_Strict):
    """更新：空白/缺省 = 不修改；``clearFields`` 明确清空（description/parentId/aliases）。"""

    expected_revision: int = Field(alias="expectedRevision", ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    parent_id: str | None = Field(default=None, alias="parentId")
    parent_code: str | None = Field(default=None, alias="parentCode")
    sort_order: int | None = Field(default=None, alias="sortOrder", ge=0, le=1_000_000)
    aliases: list[str] | None = Field(default=None, max_length=32)
    clear_fields: list[Literal["description", "parentId", "aliases"]] = Field(
        default_factory=list, alias="clearFields"
    )


class KnowledgePointRevisionRequest(_Strict):
    """归档/恢复：核编辑锁。"""

    expected_revision: int = Field(alias="expectedRevision", ge=0)


# --------------------------------------------------------------------------- 导入批次


class KnowledgeImportRowView(_Frozen):
    row_no: int = Field(alias="rowNo", ge=1)
    name: str = ""
    code: str = ""
    parent_code: str | None = Field(default=None, alias="parentCode")
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    #: 已匹配的正式知识点（update 目标）；create 行为空
    target_knowledge_point_id: str | None = Field(default=None, alias="targetKnowledgePointId")
    base_revision: int | None = Field(default=None, alias="baseRevision")
    base_version: int | None = Field(default=None, alias="baseVersion")
    decision: KnowledgeRowAction | None = None
    issues: list[ErrorIssue] = Field(default_factory=list)


class KnowledgeImportView(_Frozen):
    import_id: str = Field(alias="importId")
    source: KnowledgeImportSource
    subject_id: str = Field(alias="subjectId")
    state: KnowledgeImportState
    revision: int = Field(ge=0)
    file_asset: AssetRef = Field(alias="fileAsset")
    #: 原始上传文件名（教学库 file_assets.original_name；读取失败为 None，不伪造）
    uploaded_file_name: str | None = Field(default=None, alias="uploadedFileName")
    headers: list[str] = Field(default_factory=list)
    mapping: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    issues: list[ErrorIssue] = Field(default_factory=list)
    rows: list[KnowledgeImportRowView] = Field(default_factory=list)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class KnowledgeImportSummary(_Frozen):
    import_id: str = Field(alias="importId")
    source: KnowledgeImportSource
    subject_id: str = Field(alias="subjectId")
    state: KnowledgeImportState
    revision: int = Field(ge=0)
    row_count: int = Field(alias="rowCount", ge=0)
    blocking_issue_count: int = Field(alias="blockingIssueCount", ge=0)
    #: 原始上传文件名（教学库 file_assets.original_name；读取失败为 None，不伪造）
    uploaded_file_name: str | None = Field(default=None, alias="uploadedFileName")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class KnowledgeImportList(_Frozen):
    items: list[KnowledgeImportSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class KnowledgeImportRowPatch(_Strict):
    row_no: int = Field(alias="rowNo", ge=1)
    decision: KnowledgeRowAction
    #: update 行的期望编辑锁（缺省 = 使用预览时冻结的 baseRevision）
    expected_revision: int | None = Field(default=None, alias="expectedRevision")


class KnowledgeImportPatchRequest(_Strict):
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    mapping: dict[str, str] | None = None
    rows: list[KnowledgeImportRowPatch] | None = None


class KnowledgeImportDiscardRequest(_Strict):
    """放弃未确认批次：只把状态置 ``cancelled``；批次记录、原始文件与预览行保留。"""

    expected_revision: int = Field(alias="expectedRevision", ge=0)


class KnowledgeImportConfirmRequest(_Strict):
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    #: 缺省时使用各行已有的 decision
    actions: list[KnowledgeImportRowPatch] | None = None


class KnowledgeAppliedRow(_Frozen):
    row_no: int = Field(alias="rowNo", ge=1)
    knowledge_point_id: str = Field(alias="knowledgePointId")
    revision_id: str = Field(alias="revisionId")
    version: int = Field(ge=1)


class KnowledgeImportConfirmResult(_Frozen):
    import_id: str = Field(alias="importId")
    state: KnowledgeImportState
    created: list[KnowledgeAppliedRow] = Field(default_factory=list)
    updated: list[KnowledgeAppliedRow] = Field(default_factory=list)
    ignored: list[int] = Field(default_factory=list)
    #: True = 命中同一 submissionId 的重放（返回原结果，未重复写入）
    replayed: bool = False


# --------------------------------------------------------------------------- 教材依据关联


class TextbookEvidenceInput(_Strict):
    document_revision_id: str = Field(alias="documentRevisionId", min_length=1)
    char_start: int = Field(alias="charStart", ge=0)
    char_end: int = Field(alias="charEnd", ge=1)


class TextbookLinkCreateRequest(_Strict):
    """新增教材依据：核知识点编辑锁；区间由服务端向教材目录核验并冻结标题。"""

    expected_revision: int = Field(alias="expectedRevision", ge=0)
    document_revision_id: str = Field(alias="documentRevisionId", min_length=1)
    char_start: int = Field(alias="charStart", ge=0)
    char_end: int = Field(alias="charEnd", ge=1)
    source: KnowledgeLinkSource = "human"


class TextbookLinkView(_Frozen):
    link_id: str = Field(alias="linkId")
    knowledge_point_id: str = Field(alias="knowledgePointId")
    knowledge_revision_id: str = Field(alias="knowledgeRevisionId")
    document_revision_id: str = Field(alias="documentRevisionId")
    char_start: int = Field(alias="charStart", ge=0)
    char_end: int = Field(alias="charEnd", ge=1)
    title_snapshot: str = Field(alias="titleSnapshot")
    locator_hash: str = Field(alias="locatorHash")
    source: KnowledgeLinkSource
    created_at: str = Field(alias="createdAt")


class TextbookLinkList(_Frozen):
    items: list[TextbookLinkView]


# --------------------------------------------------------------------------- AI 候选


class KnowledgeMaterialInput(_Strict):
    """受管资料块（教师提供或受管资产文本）；用于原卷业务就绪前的候选输入。"""

    id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=20000)


class KnowledgeSuggestionRequest(_Strict):
    model_profile_id: str = Field(alias="modelProfileId", min_length=1, max_length=128)
    subject_id: str = Field(alias="subjectId", min_length=1, max_length=64)
    materials: list[KnowledgeMaterialInput] = Field(default_factory=list, max_length=50)
    textbook_evidence: list[TextbookEvidenceInput] = Field(
        default_factory=list, alias="textbookEvidence", max_length=20
    )
    instructions: str | None = Field(default=None, max_length=2000)

    @field_validator("textbook_evidence")
    @classmethod
    def ordered_ranges(cls, value: list[TextbookEvidenceInput]) -> list[TextbookEvidenceInput]:
        for item in value:
            if item.char_end <= item.char_start:
                raise ValueError("教材证据区间必须满足 charEnd > charStart")
        return value


class KnowledgeSuggestionJobView(_Frozen):
    """AI 候选任务视图：任务 + 生成的待确认批次。"""

    job_id: str = Field(alias="jobId")
    state: str
    attempt: int = Field(ge=0)
    import_id: str | None = Field(default=None, alias="importId")
    candidate_count: int = Field(default=0, alias="candidateCount", ge=0)
    error_code: str | None = Field(default=None, alias="errorCode")


class KnowledgeSuggestionCandidate(_Frozen):
    """模型返回的单条候选（内部校验形状；不直接落正式表）。"""

    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    parent_code: str | None = Field(default=None, alias="parentCode")
    aliases: list[str] = Field(default_factory=list)
    #: 关联的既有知识点 id（可选；必须在允许集合内）
    existing_knowledge_point_id: str | None = Field(
        default=None, alias="existingKnowledgePointId"
    )
    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")


# --------------------------------------------------------------------------- 知识点提取（教材 → 候选）


class KnowledgeExtractionDocument(_Frozen):
    """预览清单里的一本教材：取材范围 + 就绪状态（未就绪书册带 reason，不伪造）。"""

    document_id: str = Field(alias="documentId")
    title: str
    grade_ids: list[str] = Field(alias="gradeIds")
    #: 当前修订 id（无修订为 None → 必然未就绪）
    revision_id: str | None = Field(default=None, alias="revisionId")
    chunk_count: int = Field(alias="chunkCount", ge=0)
    approx_chars: int = Field(alias="approxChars", ge=0)
    #: 当前索引代是否包含该修订（正文分块可作 AI 证据）
    index_ready: bool = Field(alias="indexReady")
    #: 未就绪原因（就绪书册为 None）
    reason: str | None = None


class KnowledgeExtractionPreview(_Frozen):
    """某学科全部已入库教材的提取预览：清单 + 合计（只读，不建任务）。"""

    subject_id: str = Field(alias="subjectId")
    documents: list[KnowledgeExtractionDocument] = Field(default_factory=list)
    total_documents: int = Field(alias="totalDocuments", ge=0)
    ready_documents: int = Field(alias="readyDocuments", ge=0)
    total_chunks: int = Field(alias="totalChunks", ge=0)
    approx_chars: int = Field(alias="approxChars", ge=0)


class KnowledgeExtractionRequest(_Strict):
    """提取任务受理请求：每个书册一个 AI 候选任务；缺省 = 该学科全部就绪书册。"""

    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    model_profile_id: str = Field(alias="modelProfileId", min_length=1, max_length=128)
    subject_id: str = Field(alias="subjectId", min_length=1, max_length=64)
    #: 缺省 = 该学科全部就绪书册；指定时仅这些（含未就绪书册 → 409 逐册列出）
    document_ids: list[str] | None = Field(
        default=None, alias="documentIds", max_length=64
    )

    @field_validator("document_ids")
    @classmethod
    def unique_documents(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("documentIds 不允许空字符串")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("documentIds 不允许重复")
        return cleaned
