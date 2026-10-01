"""原卷 v1 冻结契约（TEACHING-LOOP B2 / T40）。

与 ``docs/design/teaching-loop-v1/sql/teaching.sql`` 的 papers/paper_revisions/paper_items/
paper_item_knowledge 一致；设计未定义、由 B2 任务卡冻结补齐的部分（原文块、问题处置、草稿 PATCH
形状、AI 建议读取/应用）在这里给出唯一形状。

关键语义（不得改写）：

- 题号是**完整路径**（``16(1)``），同一修订唯一；父子同卷、无环；**只有叶子计分**，父容器不计分。
- 分值一律以 **Decimal 字符串**入出（``"2.5"``），服务端解析为 ``×100`` 的整数 ``maxScoreUnits``；
  禁止浮点运算。
- 草稿 PATCH **整表替换** items/blocks/issues（含知识关联），核 ``expectedRevision``（= ``papers.revision``
  编辑锁）；确认用 ``submissionId`` 幂等且同库原子；确认后修订及其子记录不可增删改（DB 触发器 + 服务）。
- 原文块必须归属题目/共享材料或有明确排除理由；问题清单里的 **blocking** 未解决或仍有未归属块时
  不得确认（影响题意的解析损失必须补录后才可解决）。
- AI 建议只做两件事：关联**已有**知识点、提出待确认新知识点（后者先走 T20 候选确认再单独绑定）；
  应用前复核草稿版本（过期 → stale）。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.teaching_loop import ErrorIssue

# --------------------------------------------------------------------------- 枚举

PaperStatus = Literal["active", "archived"]
PaperRevisionState = Literal["draft", "confirmed"]
PaperKnowledgeRole = Literal["primary", "secondary"]
PaperKnowledgeSource = Literal["human", "ai_confirmed", "bank_confirmed"]
PaperBlockKind = Literal["paragraph", "table", "formula", "image", "unknown"]
PaperBlockDisposition = Literal["item", "shared_material", "excluded", "unassigned"]
PaperIssueSeverity = Literal["info", "warning", "blocking"]
PaperIssueStatus = Literal["open", "resolved", "excluded"]
ProposalState = Literal["pending", "applied", "rejected", "stale"]

PAPER_BLOCK_DISPOSITIONS: frozenset[str] = frozenset(
    {"item", "shared_material", "excluded", "unassigned"}
)
#: 分值字符串：最多两位小数（与成绩「×100 整数单位」一致）
SCORE_TEXT_PATTERN = r"^\d{1,4}(\.\d{1,2})?$"

# --------------------------------------------------------------------------- 错误码

PAPER_NOT_FOUND = "PAPER_NOT_FOUND"
PAPER_REVISION_STALE = "PAPER_REVISION_STALE"
PAPER_NOT_EDITABLE = "PAPER_NOT_EDITABLE"
PAPER_CONFIRM_INVALID = "PAPER_CONFIRM_INVALID"
PAPER_BLOCK_UNASSIGNED = "PAPER_BLOCK_UNASSIGNED"
PAPER_ISSUE_BLOCKING = "PAPER_ISSUE_BLOCKING"
PAPER_ISSUE_NOT_FOUND = "PAPER_ISSUE_NOT_FOUND"
PAPER_TOTAL_MISMATCH = "PAPER_TOTAL_MISMATCH"
NO_SCORED_ITEMS = "NO_SCORED_ITEMS"
ITEM_KNOWLEDGE_MISSING = "ITEM_KNOWLEDGE_MISSING"
SCORED_ITEM_MUST_BE_LEAF = "SCORED_ITEM_MUST_BE_LEAF"
ITEM_CYCLE = "ITEM_CYCLE"
ITEM_PARENT_INVALID = "ITEM_PARENT_INVALID"
ITEM_QUESTION_NO_DUPLICATE = "ITEM_QUESTION_NO_DUPLICATE"
ITEM_SCORE_INVALID = "ITEM_SCORE_INVALID"
PAPER_BLOCK_INVALID = "PAPER_BLOCK_INVALID"
KNOWLEDGE_REFERENCE_INVALID = "KNOWLEDGE_REFERENCE_INVALID"
PAPER_PROPOSAL_NOT_FOUND = "PAPER_PROPOSAL_NOT_FOUND"
PAPER_PROPOSAL_STALE = "PAPER_PROPOSAL_STALE"
PAPER_PROPOSAL_INVALID = "PAPER_PROPOSAL_INVALID"
PAPER_IMPORT_PARSE_FAILED = "PAPER_IMPORT_PARSE_FAILED"
PAPER_IMPORT_ASSET_INVALID = "PAPER_IMPORT_ASSET_INVALID"

# --------------------------------------------------------------------------- 基类


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------- 输入


class PaperItemKnowledgeInput(_Strict):
    knowledge_point_id: str = Field(alias="knowledgePointId", min_length=1)
    role: PaperKnowledgeRole = "primary"


class PaperItemInput(_Strict):
    """草稿题目（大题容器或计分叶子）。``maxScore`` 只在 ``isScored=true`` 时必填。"""

    item_id: str | None = Field(default=None, alias="itemId")
    parent_item_id: str | None = Field(default=None, alias="parentItemId")
    question_no: str = Field(alias="questionNo", min_length=1, max_length=32)
    ordinal: int = Field(ge=1, le=100000)
    is_scored: bool = Field(alias="isScored")
    max_score: str | None = Field(default=None, alias="maxScore", pattern=SCORE_TEXT_PATTERN)
    content: dict = Field(default_factory=dict)
    source_locator: dict = Field(default_factory=dict, alias="sourceLocator")
    knowledge: list[PaperItemKnowledgeInput] = Field(default_factory=list, max_length=32)


class PaperBlockPatch(_Strict):
    block_id: str = Field(alias="blockId", min_length=1)
    disposition: PaperBlockDisposition
    item_id: str | None = Field(default=None, alias="itemId")
    exclude_reason: str | None = Field(default=None, alias="excludeReason", max_length=500)


#: 内容损失类问题（必须"补录"后才能解决，不能仅以排除放行）
CONTENT_LOSS_ISSUE_CODES: frozenset[str] = frozenset(
    {
        "UNSUPPORTED_OBJECT",
        "RICH_IMAGE_UNSUPPORTED",
        "FORMULA_CONVERSION_FAILED",
        "DOCUMENT_PARSE_FAILED",
        "CONTENT_LOSS",
    }
)


class PaperIssueResolution(_Strict):
    """结构化问题处置（B3/G0 · B2-RV02）——不能用任意 JSON 消除 blocking。

    - ``supplement_text``：必须给 ``targetBlockId`` + ``text``；服务把文本补录进该块
      （内容随之变化，可被 F20 审阅）；
    - ``supplement_asset``：必须给 ``targetBlockId`` + ``assetId``（受管资产键
      ``blobs/<64hex>``，服务核验存在且可读）；服务把图片块补录进该块；
    - ``exclude``：必须给 ``reason``；**仅允许非内容损失**的问题码
      （见 ``CONTENT_LOSS_ISSUE_CODES``，内容损失必须补录）。
    """

    kind: Literal["supplement_text", "supplement_asset", "exclude"]
    target_block_id: str | None = Field(default=None, alias="targetBlockId", max_length=128)
    text: str | None = Field(default=None, max_length=20000)
    asset_id: str | None = Field(default=None, alias="assetId", max_length=128)
    reason: str | None = Field(default=None, max_length=500)


class PaperIssuePatch(_Strict):
    issue_id: str = Field(alias="issueId", min_length=1)
    status: PaperIssueStatus
    #: resolved 时的结构化处置；excluded 同样必须给 resolution（kind=exclude 或补录）
    resolution: PaperIssueResolution | None = None


class PaperDraftPatchRequest(_Strict):
    """整表替换草稿内容；``expectedRevision`` = ``papers.revision`` 编辑锁。"""

    expected_revision: int = Field(alias="expectedRevision", ge=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    items: list[PaperItemInput] | None = Field(default=None, max_length=1000)
    blocks: list[PaperBlockPatch] | None = Field(default=None, max_length=5000)
    issues: list[PaperIssuePatch] | None = Field(default=None, max_length=1000)


class PaperConfirmRequest(_Strict):
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)


class PaperProposalJobRequest(_Strict):
    model_profile_id: str = Field(alias="modelProfileId", min_length=1, max_length=128)
    expected_revision: int = Field(alias="expectedRevision", ge=0)


class PaperProposalSelection(_Strict):
    item_id: str = Field(alias="itemId", min_length=1)
    knowledge_point_id: str = Field(alias="knowledgePointId", min_length=1)


class PaperProposalDecisionRequest(_Strict):
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    selections: list[PaperProposalSelection] = Field(default_factory=list, max_length=500)


# --------------------------------------------------------------------------- 视图


class PaperItemKnowledgeView(_Frozen):
    knowledge_point_id: str = Field(alias="knowledgePointId")
    knowledge_revision_id: str = Field(alias="knowledgeRevisionId")
    knowledge_name_snapshot: str = Field(alias="knowledgeNameSnapshot")
    role: PaperKnowledgeRole
    source: PaperKnowledgeSource


class PaperItemView(_Frozen):
    item_id: str = Field(alias="itemId")
    parent_item_id: str | None = Field(default=None, alias="parentItemId")
    question_no: str = Field(alias="questionNo")
    ordinal: int = Field(ge=1)
    is_scored: bool = Field(alias="isScored")
    max_score_units: int | None = Field(default=None, alias="maxScoreUnits")
    max_score: str | None = Field(default=None, alias="maxScore")
    content: dict = Field(default_factory=dict)
    source_locator: dict = Field(default_factory=dict, alias="sourceLocator")
    knowledge: list[PaperItemKnowledgeView] = Field(default_factory=list)


class PaperSourceBlockView(_Frozen):
    block_id: str = Field(alias="blockId")
    ordinal: int = Field(ge=1)
    kind: PaperBlockKind
    locator: dict = Field(default_factory=dict)
    disposition: PaperBlockDisposition
    item_id: str | None = Field(default=None, alias="itemId")
    exclude_reason: str | None = Field(default=None, alias="excludeReason")
    #: 持久化的块内容快照（B3/G0 · B2-RV03）：未归属段落/表格/公式/图片都可审阅；
    #: 图片块内含受管 assetId，字节经 `GET /papers/{id}/revisions/{rid}/assets/{assetId}/content` 受控读取
    content: dict = Field(default_factory=dict)


class PaperIssueView(_Frozen):
    issue_id: str = Field(alias="issueId")
    code: str
    severity: PaperIssueSeverity
    message: str
    block_id: str | None = Field(default=None, alias="blockId")
    locator: dict = Field(default_factory=dict)
    status: PaperIssueStatus = "open"
    resolution: dict | None = None


class PaperRevisionContentView(_Frozen):
    """固定修订内容。``title`` 是**修订级标题快照**（B3/G0 · B2-RV11）：
    固定修订读取自己的标题，不随后续草稿改名而变。"""

    paper_id: str = Field(alias="paperId")
    paper_revision_id: str = Field(alias="paperRevisionId")
    version: int = Field(ge=1)
    state: PaperRevisionState
    subject_id: str = Field(alias="subjectId")
    title: str
    total_score_units: int = Field(alias="totalScoreUnits", ge=0)
    total_score: str = Field(alias="totalScore")
    confirmed_at: str | None = Field(default=None, alias="confirmedAt")
    created_at: str = Field(alias="createdAt")
    items: list[PaperItemView] = Field(default_factory=list)
    blocks: list[PaperSourceBlockView] = Field(default_factory=list)
    issues: list[PaperIssueView] = Field(default_factory=list)


class PaperView(_Frozen):
    paper_id: str = Field(alias="paperId")
    subject_id: str = Field(alias="subjectId")
    title: str
    status: PaperStatus = "active"
    revision: int = Field(ge=0)
    current_revision_id: str | None = Field(default=None, alias="currentRevisionId")
    current_state: PaperRevisionState | None = Field(default=None, alias="currentState")
    version: int = Field(default=0, ge=0)
    total_score_units: int = Field(default=0, alias="totalScoreUnits", ge=0)
    total_score: str = Field(default="0", alias="totalScore")
    item_count: int = Field(default=0, alias="itemCount", ge=0)
    scored_leaf_count: int = Field(default=0, alias="scoredLeafCount", ge=0)
    blocking_issue_count: int = Field(default=0, alias="blockingIssueCount", ge=0)
    created_at: str = Field(alias="createdAt")


class PaperImportView(_Frozen):
    """导入结果：试卷概览 + 草稿修订内容（解析问题在 ``issues``）。"""

    paper: PaperView
    revision: PaperRevisionContentView
    warnings: list[str] = Field(default_factory=list)


class PaperList(_Frozen):
    items: list[PaperView]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class PaperConfirmResult(_Frozen):
    paper_id: str = Field(alias="paperId")
    paper_revision_id: str = Field(alias="paperRevisionId")
    state: PaperRevisionState
    total_score_units: int = Field(alias="totalScoreUnits", ge=1)
    scored_leaf_count: int = Field(alias="scoredLeafCount", ge=1)
    replayed: bool = False


class PaperProposalItemView(_Frozen):
    item_id: str = Field(alias="itemId")
    question_no: str = Field(alias="questionNo")
    knowledge_point_id: str | None = Field(default=None, alias="knowledgePointId")
    proposed_code: str | None = Field(default=None, alias="proposedCode")
    proposed_name: str | None = Field(default=None, alias="proposedName")
    evidence: list[str] = Field(default_factory=list)
    ambiguity: bool = False


class PaperProposalView(_Frozen):
    proposal_id: str = Field(alias="proposalId")
    job_id: str = Field(alias="jobId")
    state: ProposalState
    base_revision: int = Field(alias="baseRevision", ge=0)
    stale: bool = False
    items: list[PaperProposalItemView] = Field(default_factory=list)
    issues: list[ErrorIssue] = Field(default_factory=list)
    created_at: str = Field(alias="createdAt")
