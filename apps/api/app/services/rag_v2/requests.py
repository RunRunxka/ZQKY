"""RAG v2 定位与澄清的 HTTP 请求模型（v2 协议；未知字段一律 422）。

契约边界：``app/schemas/rag_v2.py``（总控冻结）提供范围快照、证据与结果模型；
本模块只放本任务新增的定位/澄清请求包装，身份字段直接复用 ``RagIdentityV2``，
澄清答案沿用既有 ``RagReplyAnswer`` 形状，避免出现第二套答案契约。
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.rag import RagReplyAnswer
from app.schemas.rag_v2 import RagIdentityV2, ScopeSnapshot
from app.schemas.textbook import TextbookSelection


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScopeSelectionInput(_Strict):
    """按任教范围选择：服务端重新解析并冻结快照（每次使用前重算）。"""

    kind: Literal["selection"]
    selection: TextbookSelection


class ScopeFrozenInput(_Strict):
    """按已冻结快照继续（澄清重定位、详解引用）：服务端每次使用前重核验。"""

    kind: Literal["frozen"]
    snapshot: ScopeSnapshot


RagScopeInput = Annotated[ScopeSelectionInput | ScopeFrozenInput, Field(discriminator="kind")]


class RagStreamRequestV2(RagIdentityV2):
    question: str = Field(min_length=1, max_length=4000)
    scope: RagScopeInput
    afterEventId: int = Field(default=0, ge=0)

    @field_validator("question")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question 不能为空白。")
        return value


class RagReplyRequestV2(RagIdentityV2):
    interactionId: str = Field(min_length=1, max_length=128)
    submissionId: str = Field(min_length=1, max_length=128)
    answers: list[RagReplyAnswer] = Field(min_length=1, max_length=4)


class RagCancelRequestV2(_Strict):
    sessionId: str = Field(min_length=1, max_length=128)
    turnId: str = Field(min_length=1, max_length=128)


__all__ = [
    "RagCancelRequestV2",
    "RagReplyRequestV2",
    "RagScopeInput",
    "RagStreamRequestV2",
    "ScopeFrozenInput",
    "ScopeSelectionInput",
]
