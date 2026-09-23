"""学习问答流式对话的请求模型与基础校验。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.exceptions import AppError

MAX_MESSAGES = 200
MAX_MESSAGE_CHARS = 32_000
MAX_TOTAL_CHARS = 120_000
MAX_SKILLS = 8
MAX_SKILL_NAME_CHARS = 80
MAX_SKILL_CONTENT_CHARS = 8_000
MAX_SKILLS_CHARS = 16_000


class ChatMessageIn(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatSkillIn(BaseModel):
    """本轮启用的技能：名称 + 说明正文。

    只作提示词级系统上下文，不接受凭证、连接地址或执行参数；
    技能要执行工具需另走 MCP 通道（当前未实现）。
    """

    name: str = Field(min_length=1, max_length=MAX_SKILL_NAME_CHARS)
    content: str = Field(min_length=1, max_length=MAX_SKILL_CONTENT_CHARS)


class ChatStreamRequest(BaseModel):
    requestId: str = Field(min_length=8, max_length=64)
    modelProfileId: str
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=MAX_MESSAGES)
    maxOutputTokens: int | None = Field(default=None, ge=1, le=1_000_000)
    params: dict[str, Any] | None = None
    skills: list[ChatSkillIn] | None = Field(default=None, max_length=MAX_SKILLS)


def validate_chat_request(body: ChatStreamRequest) -> None:
    messages_total = sum(len(message.content) for message in body.messages)
    skills_total = sum(len(skill.content) for skill in body.skills or ())
    if skills_total > MAX_SKILLS_CHARS:
        raise AppError(
            "启用的技能说明总长度超出限制，请停用部分技能后重试。",
            code="SKILL_CONTEXT_TOO_LARGE",
            status_code=413,
        )
    if messages_total + skills_total > MAX_TOTAL_CHARS:
        raise AppError(
            "消息总长度超出上下文限制，请精简后重试。",
            code="CONTEXT_TOO_LARGE",
            status_code=413,
        )
