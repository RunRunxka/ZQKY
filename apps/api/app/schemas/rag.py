"""Local textbook stream input; identities are scoped to a browser session and turn."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RagIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sessionId: str = Field(min_length=1, max_length=128)
    turnId: str = Field(min_length=1, max_length=128)


class RagStreamRequest(RagIdentity):
    requestId: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=4000)
    subject: Literal["数学", "物理", "化学", "生物"] | None = None
    afterEventId: int = Field(default=0, ge=0)

    @field_validator("question")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


class RagReplyAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    questionId: str = Field(min_length=1, max_length=128)
    labels: list[str] = Field(default_factory=list, max_length=4)
    freeText: str = Field(default="", max_length=2000)
    skipped: bool = False


class RagReplyRequest(RagIdentity):
    interactionId: str = Field(min_length=1, max_length=128)
    submissionId: str = Field(min_length=1, max_length=128)
    answers: list[RagReplyAnswer] = Field(min_length=1, max_length=4)
