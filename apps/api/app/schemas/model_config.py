"""模型连接与模型配置的数据模型及字段校验。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from app.core.exceptions import InvalidRequestError

MODEL_CONFIG_SCHEMA_VERSION = 1

LOCAL_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})


class ModelProtocol(str, Enum):
    openai_chat = "openai-chat"
    openai_responses = "openai-responses"
    anthropic_messages = "anthropic-messages"


class CapabilityEvidence(str, Enum):
    verified = "verified"
    claimed = "claimed"
    unknown = "unknown"


class KnownParam(str, Enum):
    temperature = "temperature"
    top_p = "top_p"


class ModelConnection(BaseModel):
    id: str
    displayName: str
    protocol: ModelProtocol
    baseUrl: str
    extraHeaders: dict[str, str] = Field(default_factory=dict)
    createdAt: datetime
    updatedAt: datetime


class ModelProfile(BaseModel):
    id: str
    connectionId: str
    displayName: str
    modelId: str
    purpose: str | None = None
    contextTokens: int | None = None
    maxOutputTokens: int | None = None
    supportedParams: list[str] = Field(default_factory=list)
    params: dict[str, float] = Field(default_factory=dict)
    capabilities: dict[str, str] = Field(default_factory=lambda: {"chat": "unknown"})
    createdAt: datetime
    updatedAt: datetime


class ModelConfigDocument(BaseModel):
    schemaVersion: int = MODEL_CONFIG_SCHEMA_VERSION
    revision: int = 1
    connections: list[ModelConnection] = Field(default_factory=list)
    profiles: list[ModelProfile] = Field(default_factory=list)
    defaultChatProfileId: str | None = None


def now_utc() -> datetime:
    return datetime.now(UTC)


def validate_base_url(raw: str) -> str:
    url = raw.strip()
    parts = urlsplit(url)
    if parts.scheme not in {"https", "http"} or not parts.netloc:
        raise InvalidRequestError("Base URL 必须以 http(s):// 开头并包含主机名。")
    if parts.scheme == "http" and parts.hostname not in LOCAL_HOSTNAMES:
        raise InvalidRequestError("非 https 的 Base URL 仅允许本机回环地址（本机模型服务）。")
    if parts.username or parts.password:
        raise InvalidRequestError("Base URL 不允许嵌入凭证。")
    if parts.query or parts.fragment:
        raise InvalidRequestError("Base URL 不允许携带查询参数或锚点。")
    return url.rstrip("/")


def validate_capability_map(capabilities: dict[str, str] | None) -> dict[str, str]:
    if not capabilities:
        return {"chat": CapabilityEvidence.unknown.value}
    for feature, evidence in capabilities.items():
        if feature not in {"chat", "stream"}:
            raise InvalidRequestError(f"暂不支持的能力项：{feature}")
        try:
            CapabilityEvidence(evidence)
        except ValueError as exc:
            raise InvalidRequestError(f"能力证据取值不合法：{evidence}") from exc
    # verified 只由服务端测试产生，不能由表单自称已验证。
    return {key: "claimed" if value == "verified" else value for key, value in capabilities.items()}
