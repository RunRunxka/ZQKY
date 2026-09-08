"""供应商工厂：只实例化所选协议的适配器；协议细节与依赖不跨协议加载。"""

from __future__ import annotations

from app.providers.llm.anthropic_messages import AnthropicMessagesProvider
from app.providers.llm.base import LLMProvider, ProviderError
from app.providers.llm.openai_chat import OpenAIChatProvider
from app.providers.llm.openai_responses import OpenAIResponsesProvider
from app.schemas.model_config import ModelProtocol

_PROVIDERS: dict[ModelProtocol, type[LLMProvider]] = {
    ModelProtocol.openai_chat: OpenAIChatProvider,
    ModelProtocol.openai_responses: OpenAIResponsesProvider,
    ModelProtocol.anthropic_messages: AnthropicMessagesProvider,
}


def create_provider(protocol: ModelProtocol | str) -> LLMProvider:
    try:
        protocol_key = ModelProtocol(protocol)
    except ValueError as exc:
        raise ProviderError(
            "UNSUPPORTED_PROTOCOL",
            f"不支持的模型协议：{protocol}；当前支持 openai-chat / openai-responses / anthropic-messages。",
            status_code=400,
        ) from exc
    return _PROVIDERS[protocol_key]()
