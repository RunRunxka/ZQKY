"""模型设置相关的请求体模型（contract-v1）。"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.exceptions import InvalidRequestError
from app.schemas.model_config import (
    ApiFormat,
    ModelProtocol,
    ReasoningEffort,
    validate_base_url,
)

HEADER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")
# 认证头由适配器写入，用户附加头不得包含
_FORBIDDEN_HEADERS = {
    "authorization",
    "x-api-key",
    "api-key",
    "anthropic-version",
    "x-session-affinity",
    "chatgpt-account-id",
    "cookie",
}

CredentialAction = Literal["keep", "replace", "clear"]


def validate_extra_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    cleaned: dict[str, str] = {}
    for name, value in headers.items():
        lowered = name.lower()
        if lowered in _FORBIDDEN_HEADERS:
            raise InvalidRequestError("认证请求头由服务端管理，不能手动设置。")
        if lowered not in {"x-title", "http-referer", "openai-organization", "openai-project", "anthropic-beta"}:
            raise InvalidRequestError("附加请求头不在允许列表中，认证头由服务端管理。")
        if not HEADER_NAME_PATTERN.match(name):
            raise InvalidRequestError(f"请求头名称不合法：{name}")
        if "\n" in value or "\r" in value or len(value) > 512:
            raise InvalidRequestError(f"请求头 {name} 的值不合法。")
        cleaned[name] = value
    return cleaned


class ConnectionCreate(BaseModel):
    displayName: str = Field(min_length=1, max_length=64)
    providerId: str | None = Field(default=None, max_length=64)
    protocol: ModelProtocol | None = None
    apiFormat: ApiFormat = ApiFormat.auto
    baseUrl: str = ""
    apiVersion: str | None = Field(default=None, max_length=64)
    apiKey: str | None = Field(default=None, max_length=4096)
    extraHeaders: dict[str, str] | None = None


class ConnectionUpdate(BaseModel):
    displayName: str | None = Field(default=None, min_length=1, max_length=64)
    providerId: str | None = Field(default=None, max_length=64)
    protocol: ModelProtocol | None = None
    apiFormat: ApiFormat | None = None
    baseUrl: str | None = None
    apiVersion: str | None = Field(default=None, max_length=64)
    apiKey: str | None = Field(default=None, max_length=4096)
    credentialAction: CredentialAction | None = None
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
    reasoningEnabled: bool | None = None
    reasoningEffort: ReasoningEffort | None = None


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
    reasoningEnabled: bool | None = None
    reasoningEffort: ReasoningEffort | None = None
    expectedRevision: int | None = None


class ProfileTestRequest(BaseModel):
    stream: bool = False
    prompt: str | None = Field(default=None, max_length=2000)
    maxOutputTokens: int | None = Field(default=None, ge=1, le=1024)
    params: dict[str, Any] | None = None


__all__ = [
    "ConnectionCreate",
    "ConnectionUpdate",
    "CredentialAction",
    "ProfileCreate",
    "ProfileTestRequest",
    "ProfileUpdate",
    "validate_base_url",
    "validate_extra_headers",
]
