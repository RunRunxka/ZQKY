"""contract-v1 供应商行为：分派、专有参数、Azure/Codex 适配与推理控制。

全部使用 MockTransport/内存对象，不发真实上游请求。
"""

from __future__ import annotations

import json

import pytest
from httpx2 import MockTransport, Response

from app.providers.llm.azure_openai import AzureOpenAIProvider, normalize_azure_base_url
from app.providers.llm.base import LLMConfig, LLMMessage, LLMRequest, ProviderError
from app.providers.llm.codebuddy import CodeBuddyProvider
from app.providers.llm.factory import create_provider
from app.providers.llm.github_copilot import GitHubCopilotProvider
from app.providers.llm.openai_chat import build_chat_body
from app.providers.llm.openai_codex import OpenAICodexProvider
from app.providers.llm.reasoning_params import build_reasoning_kwargs
from app.providers.llm.registry import find_provider
from app.schemas.model_config import ApiFormat, ModelProtocol


def _config(**overrides) -> LLMConfig:
    base = dict(
        protocol=ModelProtocol.openai_chat,
        baseUrl="https://api.example.com/v1",
        modelId="test-model",
        apiKey="sk-test",
    )
    base.update(overrides)
    return LLMConfig(**base)


def _request(**overrides) -> LLMRequest:
    base = dict(messages=[LLMMessage(role="user", content="你好")])
    base.update(overrides)
    return LLMRequest(**base)


def _ok_response() -> Response:
    return Response(
        200,
        json={
            "choices": [{"message": {"content": "好的"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        },
    )


# --- 分派 -----------------------------------------------------------------


def test_factory_dispatches_by_backend():
    assert isinstance(create_provider(ModelProtocol.openai_chat, _config(providerId="deepseek")), type(create_provider(ModelProtocol.openai_chat)))
    assert isinstance(
        create_provider(ModelProtocol.openai_chat, _config(providerId="azure_openai")),
        AzureOpenAIProvider,
    )
    assert isinstance(
        create_provider(ModelProtocol.openai_chat, _config(providerId="openai_codex")),
        OpenAICodexProvider,
    )
    assert isinstance(
        create_provider(ModelProtocol.openai_chat, _config(providerId="github_copilot")),
        GitHubCopilotProvider,
    )
    assert isinstance(
        create_provider(ModelProtocol.openai_chat, _config(providerId="codebuddy")),
        CodeBuddyProvider,
    )


def test_factory_dispatches_anthropic_format_on_openai_compat_vendor():
    provider = create_provider(
        ModelProtocol.openai_chat,
        _config(providerId="minimax", apiFormat=ApiFormat.anthropic.value),
    )
    assert provider.protocol == ModelProtocol.anthropic_messages


def test_factory_falls_back_to_protocol_without_provider_id():
    provider = create_provider(ModelProtocol.openai_responses)
    assert provider.protocol == ModelProtocol.openai_responses


# --- max_tokens 线型 -------------------------------------------------------


def test_max_completion_tokens_only_for_openai_and_copilot():
    openai_body = build_chat_body(
        _config(providerId="openai", modelId="gpt-4o"), _request(maxOutputTokens=128), stream=False
    )
    assert openai_body["max_completion_tokens"] == 128
    assert "max_tokens" not in openai_body

    deepseek_body = build_chat_body(
        _config(providerId="deepseek"), _request(maxOutputTokens=128), stream=False
    )
    assert deepseek_body["max_tokens"] == 128
    assert "max_completion_tokens" not in deepseek_body


def test_stream_options_only_when_declared():
    nvidia_body = build_chat_body(
        _config(providerId="nvidia_nim"), _request(), stream=True
    )
    assert "stream_options" not in nvidia_body
    deepseek_body = build_chat_body(
        _config(providerId="deepseek"), _request(), stream=True
    )
    assert deepseek_body["stream_options"] == {"include_usage": True}


def test_legacy_config_without_provider_keeps_original_bytes():
    # 无 providerId：不新增 stream_options、不换 max_tokens 线型（D3 兼容）
    body = build_chat_body(_config(), _request(maxOutputTokens=64), stream=True)
    assert body["max_tokens"] == 64
    assert "stream_options" not in body
    assert "max_completion_tokens" not in body


# --- 推理控制 -------------------------------------------------------------


def test_thinking_type_style_injects_extra_body():
    kwargs = build_reasoning_kwargs(
        spec=find_provider("deepseek"),
        provider_id="deepseek",
        model="deepseek-reasoner",
        reasoning_enabled=None,
        reasoning_effort=None,
    )
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}


def test_enable_thinking_suppresses_top_level_effort():
    kwargs = build_reasoning_kwargs(
        spec=find_provider("dashscope"),
        provider_id="dashscope",
        model="qwen3-max",
        reasoning_enabled=True,
        reasoning_effort="medium",
    )
    assert "reasoning_effort" not in kwargs
    assert kwargs["extra_body"] == {"enable_thinking": True}


def test_reasoning_split_style_for_minimax():
    kwargs = build_reasoning_kwargs(
        spec=find_provider("minimax"),
        provider_id="minimax",
        model="minimax-m2",
        reasoning_enabled=True,
        reasoning_effort="high",
    )
    assert kwargs["extra_body"] == {"reasoning_split": True}


def test_explicit_disable_turns_thinking_off():
    kwargs = build_reasoning_kwargs(
        spec=find_provider("deepseek"),
        provider_id="deepseek",
        model="deepseek-reasoner",
        reasoning_enabled=False,
        reasoning_effort=None,
    )
    assert "reasoning_effort" not in kwargs
    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_gemini_default_off_family_maps_to_none_or_minimal():
    kwargs = build_reasoning_kwargs(
        spec=find_provider("gemini"),
        provider_id="gemini",
        model="gemini-2.5-flash",
        reasoning_enabled=None,
        reasoning_effort=None,
    )
    assert kwargs.get("reasoning_effort") in ("none", "minimal")


def test_custom_endpoint_infers_thinking_style_from_model_family():
    kwargs = build_reasoning_kwargs(
        spec=find_provider("custom"),
        provider_id="custom",
        model="qwen3-235b",
        reasoning_enabled=None,
        reasoning_effort=None,
    )
    assert kwargs.get("extra_body") == {"enable_thinking": True}


def test_kimi_temperature_removed_from_body():
    body = build_chat_body(
        _config(providerId="moonshot", modelId="kimi-k3"),
        _request(params={"temperature": 0.7}),
        stream=False,
    )
    assert "temperature" not in body


# --- Azure ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://x.openai.azure.com", "https://x.openai.azure.com/openai/v1"),
        ("https://x.openai.azure.com/", "https://x.openai.azure.com/openai/v1"),
        ("https://x.openai.azure.com/openai/v1", "https://x.openai.azure.com/openai/v1"),
        (
            "https://x.openai.azure.com/openai/deployments/my-dep/chat/completions",
            "https://x.openai.azure.com/openai/v1",
        ),
        ("https://x.openai.azure.com/openai", "https://x.openai.azure.com/openai/v1"),
    ],
)
def test_azure_base_url_normalization(raw, expected):
    assert normalize_azure_base_url(raw) == expected


async def test_azure_uses_api_key_header_and_only_forwards_preview_version():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return Response(200, json={"output": [], "status": "completed", "usage": {}})

    provider = AzureOpenAIProvider()
    config = _config(
        providerId="azure_openai",
        protocol=ModelProtocol.openai_responses,
        baseUrl="https://x.openai.azure.com/openai/deployments/dep/chat/completions",
        apiVersion="preview",
    )
    await provider.complete(config, _request(), transport=MockTransport(handler))
    assert captured["url"].startswith("https://x.openai.azure.com/openai/v1/responses")
    assert "api-version=preview" in captured["url"]
    assert captured["headers"].get("api-key") == "sk-test"
    assert "authorization" not in {k.lower(): v for k, v in captured["headers"].items()}


async def test_azure_does_not_forward_non_preview_version():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return Response(200, json={"output": [], "status": "completed", "usage": {}})

    provider = AzureOpenAIProvider()
    config = _config(
        providerId="azure_openai",
        protocol=ModelProtocol.openai_responses,
        baseUrl="https://x.openai.azure.com",
        apiVersion="2024-10-21",
    )
    await provider.complete(config, _request(), transport=MockTransport(handler))
    assert "api-version" not in captured["url"]


# --- Codex ----------------------------------------------------------------


async def test_codex_without_login_reports_auth_required():
    from app.providers.llm.codex_oauth import CodexOAuthService
    from app.core.secrets import SecretStore

    provider = OpenAICodexProvider(CodexOAuthService(SecretStore()))
    config = _config(
        providerId="openai_codex",
        protocol=ModelProtocol.openai_responses,
        baseUrl="https://chatgpt.com/backend-api",
        apiKey=None,
        connectionId="conn-codex",
    )
    with pytest.raises(ProviderError) as exc_info:
        await provider.complete(config, _request())
    assert exc_info.value.code == "AUTH_REQUIRED"


# --- Copilot --------------------------------------------------------------


async def test_copilot_without_github_token_reports_actionable_error():
    from app.core.secrets import SecretStore

    provider = GitHubCopilotProvider(SecretStore())
    config = _config(
        providerId="github_copilot",
        baseUrl="https://api.githubcopilot.com",
        apiKey=None,
        connectionId="conn-copilot",
    )
    with pytest.raises(ProviderError) as exc_info:
        await provider.complete(config, _request())
    assert exc_info.value.code == "AUTH_REQUIRED"
    assert "GitHub" in str(exc_info.value)


# --- CodeBuddy ------------------------------------------------------------


async def test_codebuddy_uses_x_api_key_header():
    captured = {}

    def handler(request):
        captured["headers"] = dict(request.headers)
        return _ok_response()

    provider = CodeBuddyProvider()
    config = _config(providerId="codebuddy", baseUrl="", apiKey="cb-secret")
    await provider.complete(config, _request(), transport=MockTransport(handler))
    assert captured["headers"].get("x-api-key") == "cb-secret"
    assert "authorization" not in {k.lower(): v for k, v in captured["headers"].items()}


async def test_codebuddy_without_key_is_rejected():
    provider = CodeBuddyProvider()
    config = _config(providerId="codebuddy", baseUrl="", apiKey=None)
    with pytest.raises(ProviderError) as exc_info:
        await provider.complete(config, _request())
    assert exc_info.value.code == "MODEL_NOT_CONFIGURED"


# --- 本地免 Key -----------------------------------------------------------


async def test_local_provider_can_call_without_key():
    captured = {}

    def handler(request):
        captured["headers"] = dict(request.headers)
        return _ok_response()

    from app.providers.llm.openai_chat import OpenAIChatProvider

    provider = OpenAIChatProvider()
    provider.requires_api_key = False
    config = _config(providerId="ollama", baseUrl="http://127.0.0.1:11434/v1", apiKey=None)
    response = await provider.complete(config, _request(), transport=MockTransport(handler))
    assert response.text == "好的"
    assert "authorization" not in {k.lower(): v for k, v in captured["headers"].items()}


def test_user_extra_headers_cannot_override_auth():
    from app.providers.llm.base import merge_headers

    merged = merge_headers({"Authorization": "Bearer injected", "X-Title": "app"}, {"Authorization": "Bearer real"})
    assert merged["Authorization"] == "Bearer real"
    assert merged["X-Title"] == "app"
