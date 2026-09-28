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


class RagPoint(_Frozen):
    pointId: str
    title: str
    summary: str
    evidenceIds: list[str]


class RagResultV2(_Frozen):
    contractVersion: Literal[2] = 2
    resultId: str
    status: Literal["ok", "partial", "uncertain", "no_evidence"]
    scopeSnapshot: ScopeSnapshot
    points: list[RagPoint]
    evidence: list[TextbookEvidence]
    reason: str | None = None


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
