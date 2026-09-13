"""模型连接与模型配置的数据模型及字段校验（contract-v1 / schemaVersion 2）。

contract-v1 增量（2026-09-13，依据 PROJECT_GUIDE 的 D1–D16 裁决）：
- 供应商身份（providerId）与 API 格式（apiFormat）分层，连接级保存；protocol 继续作为兼容字段。
- 推理控制独立于 generation params：reasoningEnabled 三态 + reasoningEffort 受控枚举；
  reasoningStyle 只读派生（见 model_views），不落库。
- 旧 v1 文档读取时在内存中补齐新字段，不自动改写文件；首次写 v2 前保留可恢复副本。
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from app.core.exceptions import InvalidRequestError

MODEL_CONFIG_SCHEMA_VERSION = 2

LOCAL_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})


class ModelProtocol(str, Enum):
    openai_chat = "openai-chat"
    openai_responses = "openai-responses"
    anthropic_messages = "anthropic-messages"


class ApiFormat(str, Enum):
    """连接声明的 API 格式；auto 由服务端在请求开始前按供应商/模型解析（D3）。"""

    auto = "auto"
    openai_chat = "openai_chat"
    openai_responses = "openai_responses"
    anthropic = "anthropic"


class ReasoningEffort(str, Enum):
    """受控推理深度全集（含参考的 xhigh/max）；实际可用子集按供应商/模型限制（D6）。"""

    none = "none"
    minimal = "minimal"
    low = "low"
    medium = "medium"
    high = "high"
    xhigh = "xhigh"
    max = "max"


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
    # contract-v1 增量；旧文件缺省时由迁移按 protocol 映射为 custom（D1）
    providerId: str | None = None
    apiFormat: ApiFormat = ApiFormat.auto
    apiVersion: str | None = None
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
    # 推理控制（D6）；reasoningStyle 是派生值，不在此持久化
    reasoningEnabled: bool | None = None
    reasoningEffort: ReasoningEffort | None = None
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
    # D5：继续禁止 query/fragment；版本走 apiVersion 字段
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


def protocol_for(provider_id: str | None, api_format: ApiFormat | str | None) -> ModelProtocol:
    """由供应商身份与 API 格式派生兼容字段 protocol。

    规则与参考 effective_backend 一致：anthropic 格式走 Messages；Azure/Codex 固定 Responses；
    其余 OpenAI 兼容走 Chat Completions（显式 openai_responses 时走 Responses）。
    """
    from app.providers.llm.registry import effective_backend, find_provider  # 延迟导入避免环

    spec = find_provider(provider_id) if provider_id else None
    normalized = api_format.value if isinstance(api_format, ApiFormat) else (api_format or "auto")
    backend = effective_backend(spec, normalized)
    if backend == "anthropic":
        return ModelProtocol.anthropic_messages
    if backend in {"azure_openai", "openai_codex"}:
        return ModelProtocol.openai_responses
    if backend in {"github_copilot", "codebuddy"}:
        return ModelProtocol.openai_chat
    if normalized == ApiFormat.openai_responses.value:
        return ModelProtocol.openai_responses
    if normalized == ApiFormat.anthropic.value:
        return ModelProtocol.anthropic_messages
    return ModelProtocol.openai_chat


__all__ = [
    "ApiFormat",
    "CapabilityEvidence",
    "KnownParam",
    "ModelConfigDocument",
    "ModelConnection",
    "ModelProfile",
    "ModelProtocol",
    "ReasoningEffort",
    "MODEL_CONFIG_SCHEMA_VERSION",
    "now_utc",
    "protocol_for",
    "validate_base_url",
    "validate_capability_map",
]
