"""教学闭环 v1 跨模块冻结契约（B0）。

本模块是 TEACHING-LOOP B0 冻结的**唯一**跨模块类型来源，对应设计文档
``docs/design/teaching-loop-v1/``：错误详情、修订身份、任务视图、提交幂等、
受管资产与富内容。业务模块（知识点、题库关联、原卷、成绩、学情、练习、教案）
一律从这里导入，**不得各自复制**这些类型。

外部 JSON 使用 camelCase，内部 Python/SQL 使用 snake_case（pydantic 别名负责转换）。

冻结口径（改动需走契约变更，不允许实现方就地改名或改语义）：

- ``RevisionIdentity``：``revision`` 是可变实体的乐观锁整数；``revisionId`` 是固定
  内容修订身份（不可变 UUID）。两者不得混用。
- 任务状态机：``queued → running → succeeded|failed|cancelled|interrupted``；
  ``running`` 只由持有有效租约的 worker 推进；重启遗留 ``running`` 一律转
  ``interrupted``，不自动重新调用模型。
- 提交幂等身份：``(ownerId, operation, submissionId)``；同键同 ``requestHash``
  重放返回原结果，同键不同 hash 报 409 ``SUBMISSION_CONFLICT``。
- 分数一律用整数 ``scoreUnits``（分数 × 100）；空白/缺考/免考与有效 0 分严格区分。
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- 领域枚举

JobDomain = Literal["knowledge", "question", "teaching"]
JOB_DOMAINS: frozenset[str] = frozenset({"knowledge", "question", "teaching"})

JobState = Literal[
    "queued", "running", "succeeded", "failed", "cancelled", "interrupted"
]
JOB_STATES: frozenset[str] = frozenset(
    {"queued", "running", "succeeded", "failed", "cancelled", "interrupted"}
)
#: 终态集合：进入后不再由 worker 推进；只有 retry 能重新排队。
JOB_TERMINAL_STATES: frozenset[str] = frozenset(
    {"succeeded", "failed", "cancelled", "interrupted"}
)

#: 教学库文件资产类别（设计 06：roster/score_sheet/paper/export/attachment）。
AssetKind = Literal["roster", "score_sheet", "paper", "export", "attachment"]
ASSET_KINDS: frozenset[str] = frozenset(
    {"roster", "score_sheet", "paper", "export", "attachment"}
)

#: 成绩单元格状态：有效记录 / 空白 / 缺考 / 免考。绝不把空白、缺考、免考补成 0。
ScoreStatus = Literal["recorded", "missing", "absent", "exempt"]
SCORE_STATUSES: frozenset[str] = frozenset({"recorded", "missing", "absent", "exempt"})

#: 学情观察值（any_loss_v1）：相关小题存在实际失分 → needs_consolidation；
#: 全部满分 → full_credit；有部分有效成绩但未覆盖全部小题 → incomplete；
#: 无任何有效成绩 → no_evidence。不建立掌握概率或自动评分。
Observation = Literal["needs_consolidation", "full_credit", "incomplete", "no_evidence"]
OBSERVATIONS: frozenset[str] = frozenset(
    {"needs_consolidation", "full_credit", "incomplete", "no_evidence"}
)

# --------------------------------------------------------------------------- 错误详情

SUBMISSION_CONFLICT = "SUBMISSION_CONFLICT"
IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
REVISION_CONFLICT = "REVISION_CONFLICT"
JOB_NOT_FOUND = "JOB_NOT_FOUND"
JOB_NOT_RETRYABLE = "JOB_NOT_RETRYABLE"
LEASE_LOST = "LEASE_LOST"
JOB_CANCELLED = "JOB_CANCELLED"
JOB_FAILED = "JOB_FAILED"
SCHEMA_MIGRATION_DRIFT = "SCHEMA_MIGRATION_DRIFT"


class ErrorIssue(BaseModel):
    """422 行列错误中的单条问题：定位到原行/原列，不回显请求内容。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    row: int | None = None
    column: str | None = None
    field: str | None = None
    code: str
    message: str


class ErrorDetails(BaseModel):
    """错误信封 details 的冻结形状。

    - 版本冲突（409）：``current_revision``（camelCase ``currentRevision``）。
    - 行列错误（422）：``issues``；简单字段错误可只用 ``fields``（既有约定）。
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    current_revision: int | None = Field(default=None, alias="currentRevision")
    issues: list[ErrorIssue] | None = None
    fields: list[str] | None = None


class ApiErrorEnvelope(BaseModel):
    """统一错误信封；与 ``app/schemas/errors.py`` 的响应体逐字段一致。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    code: str
    message: str
    request_id: str | None = Field(default=None, alias="requestId")
    retryable: bool = False
    details: ErrorDetails | None = None


def error_details(
    *,
    current_revision: int | None = None,
    issues: list[ErrorIssue] | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """构造 ``details`` 的 camelCase dict（供 ``error_response(details=...)``）。"""
    payload = ErrorDetails(
        current_revision=current_revision, issues=issues, fields=fields
    ).model_dump(by_alias=True, exclude_none=True)
    return payload


# --------------------------------------------------------------------------- 修订身份


class RevisionIdentity(BaseModel):
    """稳定业务身份 + 乐观锁 + 固定内容修订身份。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    revision_id: str = Field(alias="revisionId", min_length=1)


# --------------------------------------------------------------------------- 成绩


class ScoreCell(BaseModel):
    """一个（学生，计分小题）单元格。``scoreUnits`` = 分数 × 100 的整数。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    participant_id: str = Field(alias="participantId", min_length=1)
    item_id: str = Field(alias="itemId", min_length=1)
    status: ScoreStatus
    score_units: int | None = Field(default=None, alias="scoreUnits", ge=0)


# --------------------------------------------------------------------------- 任务视图


class JobView(BaseModel):
    """任务对外视图；``202`` 只代表接受任务，不代表生成完成。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    job_id: str = Field(alias="jobId", min_length=1)
    domain: JobDomain
    kind: str = Field(min_length=1)
    attempt: int = Field(ge=0)
    state: JobState
    result: dict[str, Any] | None = None
    error: ApiErrorEnvelope | None = None


# --------------------------------------------------------------------------- 受管资产


class AssetRef(BaseModel):
    """受管文件资产的对外引用（对应教学库 ``file_assets`` 一行）。

    ``blobKey`` 只能是 ``blobs/<sha256>`` 形式的受管相对键；原件不覆盖。
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    asset_id: str = Field(alias="assetId", min_length=1)
    kind: AssetKind
    blob_key: str = Field(alias="blobKey", min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    media_type: str = Field(alias="mediaType", min_length=1)
    byte_size: int = Field(alias="byteSize", ge=0)
    original_name: str = Field(alias="originalName", min_length=1)


# --------------------------------------------------------------------------- 富内容 v2


class TableCell(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    text: str = ""
    is_header: bool = Field(default=False, alias="isHeader")
    row_span: int = Field(default=1, alias="rowSpan", ge=1)
    col_span: int = Field(default=1, alias="colSpan", ge=1)


class ParagraphBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    kind: Literal["paragraph"]
    text: str


class TableBlock(BaseModel):
    """表格块。``cells`` 按**行优先**顺序排列，``rowSpan``/``colSpan`` 占位（与 HTML 网格一致）。

    ``columnCount`` 给出网格宽度，用于把扁平单元格序列精确还原成行；缺省（None）时调用方
    只能按表头/前缀和启发式重建，**可能与原表不一致**——因此 DOCX 解析器必须填写它，
    富内容消费方（前端/导出）应优先使用它。
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    kind: Literal["table"]
    cells: list[TableCell]
    column_count: int | None = Field(default=None, alias="columnCount", ge=1)


class FormulaBlock(BaseModel):
    """公式块：``latex`` 与 ``ommlXml`` 至少有一个不为空（服务层校验）。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    kind: Literal["formula"]
    latex: str | None = None
    omml_xml: str | None = Field(default=None, alias="ommlXml")


class ImageBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    kind: Literal["image"]
    asset_id: str = Field(alias="assetId", min_length=1)
    width: int = Field(ge=0)
    height: int = Field(ge=0)


ContentBlock = Annotated[
    ParagraphBlock | TableBlock | FormulaBlock | ImageBlock,
    Field(discriminator="kind"),
]


class SharedMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    blocks: list[ContentBlock]


class RichAsset(BaseModel):
    """富内容引用的受管资产（字节散列随内容冻结）。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    asset_id: str = Field(alias="assetId", min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    media_type: str = Field(alias="mediaType", min_length=1)


class RichOrigin(BaseModel):
    """来源定位：原始资产 + 原件散列 + 源定位（脱敏、可展示）。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    original_asset_id: str = Field(alias="originalAssetId", min_length=1)
    original_sha256: str = Field(alias="originalSha256", min_length=64, max_length=64)
    source_locator: dict[str, Any] = Field(default_factory=dict, alias="sourceLocator")


class RichContentV2(BaseModel):
    """结构化题干（v2）。存在时它是内容权威，Markdown 是派生展示。

    兼容规则：``richContent`` 可选；旧 Markdown 题保持有效。服务层校验两者一致，
    不允许"保留旧富内容却只改 Markdown"。
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    version: Literal[2]
    shared_materials: list[SharedMaterial] = Field(
        default_factory=list, alias="sharedMaterials"
    )
    stem_blocks: list[ContentBlock] = Field(default_factory=list, alias="stemBlocks")
    option_blocks: dict[str, list[ContentBlock]] = Field(
        default_factory=dict, alias="optionBlocks"
    )
    answer_blocks: list[ContentBlock] = Field(default_factory=list, alias="answerBlocks")
    explanation_blocks: list[ContentBlock] = Field(
        default_factory=list, alias="explanationBlocks"
    )
    assets: list[RichAsset] = Field(default_factory=list)
    origin: RichOrigin


# --------------------------------------------------------------------------- 提交幂等


def canonical_hash(payload: Any) -> str:
    """规范化 JSON（sorted keys、UTF-8、紧凑分隔符）的 sha256。

    提交幂等与冻结输入一律使用本函数；同载荷必须得到同一散列，键顺序不影响结果。
    """
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
