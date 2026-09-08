"""模型设置相关的请求体模型。"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.exceptions import InvalidRequestError
from app.schemas.model_config import (
    ModelProtocol,
    validate_base_url,
)

HEADER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def validate_extra_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    cleaned: dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() not in {"x-title", "http-referer", "openai-organization", "openai-project", "anthropic-beta"}:
            raise InvalidRequestError("附加请求头不在允许列表中，认证头由服务端管理。")
        if not HEADER_NAME_PATTERN.match(name):
            raise InvalidRequestError(f"请求头名称不合法：{name}")
        if "\n" in value or "\r" in value or len(value) > 512:
            raise InvalidRequestError(f"请求头 {name} 的值不合法。")
        cleaned[name] = value
    return cleaned


class ConnectionCreate(BaseModel):
    displayName: str = Field(min_length=1, max_length=64)
    protocol: ModelProtocol
    baseUrl: str
    apiKey: str | None = Field(default=None, max_length=4096)
    extraHeaders: dict[str, str] | None = None


class ConnectionUpdate(BaseModel):
    displayName: str | None = Field(default=None, min_length=1, max_length=64)
    protocol: ModelProtocol | None = None
    baseUrl: str | None = None
    apiKey: str | None = Field(default=None, max_length=4096)
    extraHeaders: dict[str, str] | None = None
    expectedRevision: int | None = None


class ProfileCreate(BaseModel):
    connectionId: str
    displayName: str = Field(min_length=1, max_length=64)
    modelId: str = Field(min_length=1, max_length=128)
    purpose: str | None = "chat"
    contextTokens: int | None = Field(default=None, ge=1, le=100_000_000)
    maxOutputTokens: int | None = Field(default=None, ge=1, le=1_000_000)
    supportedParams: list[str] | None = None
    params: dict[str, float] = Field(default_factory=dict)
    capabilities: dict[str, str] | None = None


class ProfileUpdate(BaseModel):
    connectionId: str | None = None
    displayName: str | None = Field(default=None, min_length=1, max_length=64)
    modelId: str | None = Field(default=None, min_length=1, max_length=128)
    purpose: str | None = None
    contextTokens: int | None = Field(default=None, ge=1, le=100_000_000)
    maxOutputTokens: int | None = Field(default=None, ge=1, le=1_000_000)
    supportedParams: list[str] | None = None
    params: dict[str, float] | None = None
    capabilities: dict[str, str] | None = None
    expectedRevision: int | None = None


class ProfileTestRequest(BaseModel):
    stream: bool = False
    prompt: str | None = Field(default=None, max_length=2000)
    maxOutputTokens: int | None = Field(default=None, ge=1, le=1024)
    params: dict[str, Any] | None = None


__all__ = [
    "ConnectionCreate",
    "ConnectionUpdate",
    "ProfileCreate",
    "ProfileTestRequest",
    "ProfileUpdate",
    "validate_base_url",
    "validate_extra_headers",
]
