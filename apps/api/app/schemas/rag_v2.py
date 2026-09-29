"""RAG v2 契约：范围快照、结构化证据、知识点结果与详解请求。

`scopeSnapshot` 是服务端在定位时冻结的教材范围事实，客户端只回传、不构造判定；
服务端在每次使用前重新核验归属、修订、分类与删除状态（`scopeHash` 用于检测
意外变化，不是认证凭证）。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.textbook import LocatorView, TextbookSelection


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScopeDocument(_Frozen):
    documentId: str
    documentRevisionId: str
    metadataRevisionId: str


class ScopeSnapshot(_Frozen):
    schemaVersion: Literal[2] = 2
    selection: TextbookSelection
    documents: list[ScopeDocument]
    embeddingGenerationId: str
    scopeHash: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceRef(_Frozen):
    evidenceId: str = Field(min_length=1, max_length=128)
    documentRevisionId: str = Field(min_length=1, max_length=64)
    normalizedTextSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    charStart: int = Field(ge=0)
    charEnd: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> "EvidenceRef":
        if self.charStart >= self.charEnd:
            raise ValueError("charStart 必须小于 charEnd")
        return self


class EvidenceReadable(_Frozen):
    """证据的**可读投影**（RAG-QUALITY v1.1）：已清洗图片 Markdown，保留公式与正文结构。

    与 `TextbookEvidence.text` 的关系：`text` 仍是**可逐字验证的封存原文切片**（引用、
    散列、坐标都绑定它）；`readable.text` 只是派生展示文本，**不得**作为客户端回传的
    可信证据，也不得参与原文散列校验。
    """

    #: 清洗规则版本：规则变化时递增（规则版本进入分块指纹，见 `text_projection`）。
    #: 客户端只需原样读取；新增版本时这里必须同步，否则证据构建会因字面量校验失败。
    version: Literal["rag-readable-v1", "rag-readable-v2"]
    text: str
    removedImageCount: int = Field(ge=0)


class TextbookEvidence(EvidenceRef):
    documentId: str
    title: str
    editionLabel: str
    subjectLabel: str
    chapterPath: list[str]
    text: str
    originalFileSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: LocatorView
    isSuperseded: bool
    #: 新服务端**必须**填充；旧历史消息允许缺失（前端按缺省降级展示）
    readable: EvidenceReadable | None = None


class RagPoint(_Frozen):
    pointId: str
    title: str
    summary: str
    evidenceIds: list[str]


class RagPresentation(_Frozen):
    """首答呈现元数据（RAG-QUALITY v1.1）：告诉前端这是紧凑简短回答。

    `bodyCharCount` 是**知识点正文**（标题+说明）的码点数，不含引用编号与来源；
    供前端与验收核对"首答是否落在预算内"，不作为渲染开关。
    """

    version: Literal["compact-v1"]
    answerStyle: Literal["brief"]
    bodyCharCount: int = Field(ge=0)


class RagResultV2(_Frozen):
    contractVersion: Literal[2] = 2
    resultId: str
    status: Literal["ok", "partial", "uncertain", "no_evidence"]
    scopeSnapshot: ScopeSnapshot
    points: list[RagPoint]
    evidence: list[TextbookEvidence]
    reason: str | None = None
    #: 机器可读的原因码（取值见 `app.core.rag_budget.REASON_CODES`）；`ok` 时为 None
    reasonCode: str | None = None
    #: 紧凑首答标记；旧历史消息允许缺失
    presentation: RagPresentation | None = None


class RagExplainHistoryMessage(_Strict):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=32000)


class RagExplainRequest(_Strict):
    requestId: str = Field(min_length=1, max_length=128)
    sessionId: str = Field(min_length=1, max_length=128)
    turnId: str = Field(min_length=1, max_length=128)
    modelProfileId: str = Field(min_length=1, max_length=128)
    originalQuestion: str = Field(min_length=1, max_length=4000)
    followUp: str = Field(min_length=1, max_length=4000)
    scopeSnapshot: ScopeSnapshot
    evidenceRefs: list[EvidenceRef] = Field(min_length=1, max_length=20)
    history: list[RagExplainHistoryMessage] = Field(default_factory=list, max_length=200)
    maxOutputTokens: int | None = Field(default=None, ge=64, le=32768)


class RagIdentityV2(_Strict):
    """定位请求的 v2 身份字段（沿用既有事件编号与恢复语义）。"""

    requestId: str = Field(min_length=1, max_length=128)
    sessionId: str = Field(min_length=1, max_length=128)
    turnId: str = Field(min_length=1, max_length=128)
