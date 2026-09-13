"""供应商工厂：按连接快照（providerId + apiFormat）分派适配器。

- 有 providerId：用注册表派生 backend（registry.effective_backend）。
- 无 providerId（未迁移旧调用方）：按 protocol 回退到三传输适配器。
- backend 决定实例化的协议类；OpenAI 兼容供应商在 anthropic 格式下切到 Anthropic Messages。
"""

from __future__ import annotations

from app.providers.llm.base import LLMConfig, LLMProvider, ProviderError
from app.providers.llm.registry import (
    BACKEND_ANTHROPIC,
    BACKEND_AZURE_OPENAI,
    BACKEND_CODEBUDDY,
    BACKEND_GITHUB_COPILOT,
    BACKEND_OPENAI_CODEX,
    BACKEND_OPENAI_COMPAT,
    effective_backend,
    find_provider,
)
from app.schemas.model_config import ApiFormat, ModelProtocol

def _protocol_provider(protocol: ModelProtocol) -> LLMProvider:
    # 延迟导入：避免无 providerId 的旧路径与专用适配器互相牵扯
    if protocol == ModelProtocol.openai_chat:
        from app.providers.llm.openai_chat import OpenAIChatProvider

        return OpenAIChatProvider()
    if protocol == ModelProtocol.openai_responses:
        from app.providers.llm.openai_responses import OpenAIResponsesProvider

        return OpenAIResponsesProvider()
    if protocol == ModelProtocol.anthropic_messages:
        from app.providers.llm.anthropic_messages import AnthropicMessagesProvider

        return AnthropicMessagesProvider()
    raise ProviderError(
        "UNSUPPORTED_PROTOCOL",
        f"不支持的模型协议：{protocol}；当前支持 openai-chat / openai-responses / anthropic-messages。",
        status_code=400,
    )


def create_provider(protocol: ModelProtocol | str, config: LLMConfig | None = None) -> LLMProvider:
    """创建适配器。传入 config 时优先按供应商 backend 分派（contract-v1 路径）。"""
    if config is not None and config.providerId:
        spec = find_provider(config.providerId)
        backend = effective_backend(spec, config.apiFormat)
        if backend == BACKEND_AZURE_OPENAI:
            from app.providers.llm.azure_openai import AzureOpenAIProvider

            return AzureOpenAIProvider()
        if backend == BACKEND_OPENAI_CODEX:
            from app.providers.llm.openai_codex import OpenAICodexProvider

            return OpenAICodexProvider()
        if backend == BACKEND_GITHUB_COPILOT:
            from app.providers.llm.github_copilot import GitHubCopilotProvider

            return GitHubCopilotProvider()
        if backend == BACKEND_CODEBUDDY:
            from app.providers.llm.codebuddy import CodeBuddyProvider

            return CodeBuddyProvider()
        if backend == BACKEND_ANTHROPIC:
            from app.providers.llm.anthropic_messages import AnthropicMessagesProvider

            return AnthropicMessagesProvider()
        if backend == BACKEND_OPENAI_COMPAT:
            from app.providers.llm.openai_chat import OpenAIChatProvider

            return OpenAIChatProvider()

    # 兼容路径：无 providerId 时按 protocol
    try:
        protocol_key = ModelProtocol(protocol)
    except ValueError as exc:
        raise ProviderError(
            "UNSUPPORTED_PROTOCOL",
            f"不支持的模型协议：{protocol}；当前支持 openai-chat / openai-responses / anthropic-messages。",
            status_code=400,
        ) from exc
    return _protocol_provider(protocol_key)


def resolve_api_format_for_request(config: LLMConfig) -> str:
    """请求开始前解析生效格式（D3）；流开始后不得再切换。"""
    spec = find_provider(config.providerId) if config.providerId else None
    if spec is None:
        return config.apiFormat or ApiFormat.auto.value
    from app.providers.llm.registry import api_format_for_provider

    return api_format_for_provider(config.apiFormat, spec)


__all__ = ["create_provider", "resolve_api_format_for_request"]
