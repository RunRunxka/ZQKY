"""模型运行时装配：把连接/模型快照变成一次调用的 Provider + LLMConfig。

这里是"连接 A 的认证与参数不得污染 B"的实现点：所有凭证与专有状态都通过
显式对象传递，不写进程环境、不跨连接共享（D9）。
"""

from __future__ import annotations

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


__all__ = ["build_llm_config", "build_provider", "supports_provider"]
