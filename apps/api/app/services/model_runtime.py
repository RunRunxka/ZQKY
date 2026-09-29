"""模型运行时装配：把连接/模型快照变成一次调用的 Provider + LLMConfig。

这里是"连接 A 的认证与参数不得污染 B"的实现点：所有凭证与专有状态都通过
显式对象传递，不写进程环境、不跨连接共享（D9）。

RAG-QUALITY v1.1 起，**「按 profileId 解析出可调用的聊天模型」只有这一个实现**
（``resolve_chat_model``）：详解（`rag_v2/explain.py`）与题库 AI 整理（`question_bank`）
共用它，任何模块都不得自行把 profileId 解释成别的含义（例如 Ollama 模型名）。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import AppError
from app.core.secrets import SecretStore
from app.providers.llm.base import LLMConfig, LLMProvider, ProviderError
from app.providers.llm.factory import create_provider
from app.providers.llm.registry import (
    BACKEND_CODEBUDDY,
    BACKEND_GITHUB_COPILOT,
    BACKEND_OPENAI_CODEX,
    effective_backend,
    find_provider,
)
from app.schemas.model_config import ModelConnection, ModelProfile

#: 未显式声明输出上限时的聊天默认值（与 `api/v1/chat.py` 的默认保持一致）
DEFAULT_CHAT_MAX_OUTPUT_TOKENS = 2048


@dataclass(frozen=True)
class ChatModelHandle:
    """一次调用冻结的聊天模型句柄：Provider + 连接快照 + 生效输出上限。

    冻结语义：句柄由 profileId 解析一次，重试沿用同一个句柄，
    **不因为"默认模型"后来变化而换模型**。
    """

    profile_id: str
    model_id: str
    provider: LLMProvider
    config: LLMConfig
    max_output_tokens: int = DEFAULT_CHAT_MAX_OUTPUT_TOKENS


def build_llm_config(
    connection: ModelConnection,
    profile: ModelProfile,
    secrets: SecretStore,
    *,
    max_output_tokens: int | None = None,
) -> LLMConfig:
    spec = find_provider(connection.providerId) if connection.providerId else None
    # 无显式 baseUrl 时用注册表默认/按格式默认（运行期解析，不落库）
    base_url = connection.baseUrl or (spec.defaultApiBaseFor(connection.apiFormat.value) if spec else "")
    if not base_url:
        raise ProviderError("MODEL_NOT_CONFIGURED", "该连接缺少 Base URL，请在设置中补全。", status_code=400)
    return LLMConfig(
        protocol=connection.protocol,
        baseUrl=base_url.rstrip("/"),
        modelId=profile.modelId,
        apiKey=secrets.resolve(connection.id),
        extraHeaders=dict(connection.extraHeaders),
        providerId=connection.providerId,
        apiFormat=connection.apiFormat.value,
        apiVersion=connection.apiVersion,
        connectionId=connection.id,
        modelProfileId=profile.id,
        reasoningEnabled=profile.reasoningEnabled,
        reasoningEffort=profile.reasoningEffort.value if profile.reasoningEffort else None,
    )


def build_provider(connection: ModelConnection, config: LLMConfig, *, auth_service=None) -> LLMProvider:  # noqa: ANN001
    """按 backend 创建适配器，并为专用认证注入所需服务。"""
    spec = find_provider(connection.providerId) if connection.providerId else None
    backend = effective_backend(spec, connection.apiFormat.value) if connection.providerId else None
    provider = create_provider(connection.protocol, config)

    if backend == BACKEND_OPENAI_CODEX:
        if auth_service is None:
            raise ProviderError("AUTH_REQUIRED", "Codex 认证服务不可用。", status_code=400)
        provider.bind_oauth(auth_service.codex)  # type: ignore[attr-defined]
    elif backend == BACKEND_GITHUB_COPILOT:
        secrets = getattr(auth_service, "secrets", None) if auth_service is not None else None
        provider.bind_secrets(secrets)  # type: ignore[attr-defined]
    elif backend == BACKEND_CODEBUDDY:
        pass  # API Key 通道由 config.apiKey 提供
    return provider


def supports_provider(connection: ModelConnection) -> bool:
    return connection.providerId is None or find_provider(connection.providerId) is not None


def resolve_chat_model(
    repo,
    secrets: SecretStore,
    profile_id: str,
    *,
    auth_service=None,
    purpose: str | None = "chat",
) -> ChatModelHandle:
    """按 profileId 解析出可调用的聊天模型句柄（本地或云端一视同仁）。

    - `purpose` 非空时校验模型配置的用途（默认只接受 `chat`），避免把 embedding 等
      专用配置当聊天模型用；调用方需要放宽时显式传 `purpose=None`。
    - 连接不可调用时抛 400 `MODEL_NOT_CONFIGURED`，原因是可读文本，不含凭证。
    - **不读进程环境**：凭证只经 `SecretStore`；也不发起任何网络请求。
    """
    from app.services.model_readiness import callable_state

    # 仓储在"配置不存在"时自己抛 404 NOT_FOUND；这里归一成稳定码，
    # 让调用方（前端错误映射）只依赖一个码，不必分辨是仓储还是运行时的 404。
    try:
        profile = repo.get_profile(profile_id)
    except AppError as exc:
        if exc.status_code == 404:
            raise AppError(
                "模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404
            ) from exc
        raise
    if profile is None:
        raise AppError("模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404)
    if purpose is not None and profile.purpose not in (None, purpose):
        raise AppError(
            f"该模型配置用途为 {profile.purpose}，不能用于{purpose}。",
            code="MODEL_PURPOSE_MISMATCH",
            status_code=422,
        )
    connection = repo.get_connection(profile.connectionId)
    state = callable_state(connection, secrets)
    if not state.ready:
        raise AppError(
            state.reason or "该模型连接当前不可调用。",
            code="MODEL_NOT_CONFIGURED",
            status_code=400,
        )
    config = build_llm_config(connection, profile, secrets)
    provider = build_provider(connection, config, auth_service=auth_service)
    return ChatModelHandle(
        profile_id=profile.id,
        model_id=profile.modelId,
        provider=provider,
        config=config,
        max_output_tokens=profile.maxOutputTokens or DEFAULT_CHAT_MAX_OUTPUT_TOKENS,
    )


__all__ = [
    "ChatModelHandle",
    "DEFAULT_CHAT_MAX_OUTPUT_TOKENS",
    "build_llm_config",
    "build_provider",
    "resolve_chat_model",
    "supports_provider",
]
