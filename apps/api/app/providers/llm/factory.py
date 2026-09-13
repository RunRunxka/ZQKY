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
    FORMAT_ANTHROPIC,
    FORMAT_AUTO,
    FORMAT_OPENAI_CHAT,
    FORMAT_OPENAI_RESPONSES,
    api_format_for_provider,
    effective_backend,
    find_provider,
    normalize_api_format,
)
from app.schemas.model_config import ModelProtocol

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


def resolve_effective_format(protocol: ModelProtocol | str, config: LLMConfig | None) -> str:
    """请求开始前解析生效格式（D3）。解析结果同时决定 adapter 与 URL 线（MR-01）。

    - 有 providerId：`auto` 与显式值都按注册表钳制；
    - 无 providerId（旧调用方）：由 protocol 回退，`openai-responses` 必须保留为
      Responses，不能被静默改成 Chat Completions。
    """
    if config is not None and config.providerId:
        spec = find_provider(config.providerId)
        if spec is not None:
            return api_format_for_provider(config.apiFormat, spec)
        return normalize_api_format(config.apiFormat)
    try:
        protocol_key = ModelProtocol(protocol)
    except ValueError:
        return FORMAT_AUTO
    if protocol_key == ModelProtocol.openai_responses:
        return FORMAT_OPENAI_RESPONSES
    if protocol_key == ModelProtocol.anthropic_messages:
        return FORMAT_ANTHROPIC
    return FORMAT_OPENAI_CHAT


def create_provider(protocol: ModelProtocol | str, config: LLMConfig | None = None) -> LLMProvider:
    """创建适配器。传入 config 时按供应商 backend + 生效格式分派（contract-v1 路径）。

    MR-01：openai_compat 供应商选择 `openai_responses` 时必须创建 Responses 适配器；
    迁移后的旧 Responses 连接（providerId=custom + apiFormat=openai_responses）同样如此。
    """
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
            # OpenAI 兼容供应商的两种线格式由生效 apiFormat 决定，而非固定 Chat
            if resolve_effective_format(protocol, config) == FORMAT_OPENAI_RESPONSES:
                from app.providers.llm.openai_responses import OpenAIResponsesProvider

                return OpenAIResponsesProvider()
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
    """兼容入口：按连接快照解析生效格式（D3）；流开始后不得再切换。"""
    return resolve_effective_format(config.protocol, config)


__all__ = ["create_provider", "resolve_api_format_for_request", "resolve_effective_format"]
