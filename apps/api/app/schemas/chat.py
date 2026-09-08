"""学习问答流式对话的请求模型与基础校验。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.exceptions import AppError

MAX_MESSAGES = 200
MAX_MESSAGE_CHARS = 32_000
MAX_TOTAL_CHARS = 120_000


class ChatMessageIn(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatStreamRequest(BaseModel):
    requestId: str = Field(min_length=8, max_length=64)
    modelProfileId: str
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=MAX_MESSAGES)
    maxOutputTokens: int | None = Field(default=None, ge=1, le=1_000_000)
    params: dict[str, Any] | None = None


def validate_chat_request(body: ChatStreamRequest) -> None:
    total = sum(len(message.content) for message in body.messages)
    if total > MAX_TOTAL_CHARS:
        raise AppError(
            "消息总长度超出上下文限制，请精简后重试。",
            code="CONTEXT_TOO_LARGE",
            status_code=413,
        )
