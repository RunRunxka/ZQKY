"""协议适配测试：请求/响应、中文、取消、超时、鉴权、限流、不支持参数。

全部使用 httpx2 MockTransport 模拟上游；真实供应商验收在未获凭证时单独标注未执行。
"""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx2 import MockTransport, Response

import httpx2 as httpx

from app.providers.llm.anthropic_messages import AnthropicMessagesProvider
from app.providers.llm.base import LLMConfig, LLMMessage, LLMRequest, ProviderError
from app.providers.llm.factory import create_provider
from app.providers.llm.openai_chat import OpenAIChatProvider
from app.providers.llm.openai_responses import OpenAIResponsesProvider
from app.schemas.model_config import ModelProtocol


def make_config(protocol: ModelProtocol, api_key: str | None = "sk-test") -> LLMConfig:
    return LLMConfig(
        protocol=protocol,
        baseUrl="https://api.example.com/v1",
        modelId="测试模型-id",
        apiKey=api_key,
        extraHeaders={"X-Extra": "1"},
    )


def make_request(**kwargs) -> LLMRequest:
    messages = kwargs.pop("messages", [LLMMessage(role="user", content="你好，请回复连接正常。")])
    return LLMRequest(messages=messages, **kwargs)


def mock_200(payload: dict):
    return MockTransport(lambda request: Response(200, json=payload))


OPENAI_CHAT_PAYLOAD = {
    "choices": [
        {"message": {"role": "assistant", "content": "连接正常，模型已就绪。"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 12, "completion_tokens": 9},
}


class TestOpenAIChat:
    async def test_request_shape_and_chinese_response(self):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["body"] = json.loads(request.content)
            return Response(200, json=OPENAI_CHAT_PAYLOAD)

        provider = OpenAIChatProvider()
        response = await provider.complete(
            make_config(ModelProtocol.openai_chat),
            make_request(maxOutputTokens=64),
            transport=MockTransport(handler),
        )
        assert captured["url"].endswith("/v1/chat/completions")
        assert captured["headers"]["authorization"] == "Bearer sk-test"
        assert captured["headers"]["x-extra"] == "1"
        assert captured["body"]["model"] == "测试模型-id"
        assert captured["body"]["messages"][0]["content"].startswith("你好")
        assert captured["body"]["max_tokens"] == 64
        assert response.text == "连接正常，模型已就绪。"
        assert response.finishReason == "stop"
        assert response.usage.inputTokens == 12
        assert response.usage.outputTokens == 9

    async def test_missing_credential_rejected_before_send(self):
        captured = {}

        def handler(request):
            captured["called"] = True
            return Response(200, json=OPENAI_CHAT_PAYLOAD)

        provider = OpenAIChatProvider()
        with pytest.raises(ProviderError) as exc_info:
            await provider.complete(make_config(ModelProtocol.openai_chat, api_key=None), make_request(), transport=MockTransport(handler))
        assert exc_info.value.code == "MODEL_NOT_CONFIGURED"
        assert "called" not in captured

    async def test_length_finish_reason(self):
        payload = {"choices": [{"message": {"content": "截断"}, "finish_reason": "length"}]}
        provider = OpenAIChatProvider()
        response = await provider.complete(make_config(ModelProtocol.openai_chat), make_request(), transport=mock_200(payload))
        assert response.finishReason == "length"


class TestOpenAIResponses:
    async def test_request_shape_and_output_parsing(self):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            return Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {"content": [{"type": "output_text", "text": "中文回答，一切正常。"}]}
                    ],
                    "usage": {"input_tokens": 8, "output_tokens": 6},
                },
            )

        provider = OpenAIResponsesProvider()
        response = await provider.complete(
            make_config(ModelProtocol.openai_responses),
            make_request(maxOutputTokens=64),
            transport=MockTransport(handler),
        )
        assert captured["url"].endswith("/v1/responses")
        assert captured["body"]["max_output_tokens"] == 64
        assert captured["body"]["input"][0]["content"][0]["type"] == "input_text"
        assert response.text == "中文回答，一切正常。"
        assert response.finishReason == "stop"
        assert response.usage.outputTokens == 6

    async def test_incomplete_maps_to_length(self):
        payload = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "output": []}
        provider = OpenAIResponsesProvider()
        response = await provider.complete(make_config(ModelProtocol.openai_responses), make_request(), transport=mock_200(payload))
        assert response.finishReason == "length"


class TestAnthropicMessages:
    async def test_request_shape_and_chinese_response(self):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["body"] = json.loads(request.content)
            return Response(
                200,
                json={
                    "content": [{"type": "text", "text": "Anthropic 连接正常。"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 7},
                },
            )

        provider = AnthropicMessagesProvider()
        response = await provider.complete(
            make_config(ModelProtocol.anthropic_messages),
            make_request(messages=[LLMMessage(role="system", content="你是助手。"), LLMMessage(role="user", content="你好")], maxOutputTokens=64),
            transport=MockTransport(handler),
        )
        assert captured["url"].endswith("/v1/messages")
        assert captured["headers"]["x-api-key"] == "sk-test"
        assert captured["headers"]["anthropic-version"] == "2023-06-01"
        assert captured["body"]["system"] == "你是助手。"
        assert captured["body"]["max_tokens"] == 64
        assert all(m["role"] in ("user", "assistant") for m in captured["body"]["messages"])
        assert response.text == "Anthropic 连接正常。"
        assert response.finishReason == "stop"

    async def test_max_tokens_limit_maps_to_length(self):
        payload = {"content": [{"type": "text", "text": "部分"}], "stop_reason": "max_tokens", "usage": {}}
        provider = AnthropicMessagesProvider()
        response = await provider.complete(make_config(ModelProtocol.anthropic_messages), make_request(), transport=mock_200(payload))
        assert response.finishReason == "length"

    async def test_user_message_required(self):
        provider = AnthropicMessagesProvider()
        with pytest.raises(ProviderError) as exc_info:
            await provider.complete(
                make_config(ModelProtocol.anthropic_messages),
                make_request(messages=[LLMMessage(role="system", content="只有系统消息")]),
            )
        assert exc_info.value.code == "INVALID_REQUEST"


class TestErrorMapping:
    @pytest.mark.parametrize(
        ("status", "expected_code"),
        [(401, "UPSTREAM_AUTH_FAILED"), (403, "UPSTREAM_AUTH_FAILED"), (429, "RATE_LIMITED"), (500, "UPSTREAM_ERROR")],
    )
    async def test_http_error_mapping(self, status, expected_code):
        def handler(request):
            return Response(status, json={"error": {"message": "上游细节信息"}})

        provider = OpenAIChatProvider()
        with pytest.raises(ProviderError) as exc_info:
            await provider.complete(
                make_config(ModelProtocol.openai_chat), make_request(), transport=MockTransport(handler)
            )
        assert exc_info.value.code == expected_code

    async def test_error_message_sanitized(self):
        def handler(request):
            return Response(401, json={"error": {"message": "无效密钥 " * 100}})

        provider = OpenAIChatProvider()
        with pytest.raises(ProviderError) as exc_info:
            await provider.complete(
                make_config(ModelProtocol.openai_chat), make_request(), transport=MockTransport(handler)
            )
        assert "sk-test" not in str(exc_info.value)
        assert len(str(exc_info.value)) < 300

    async def test_timeout_maps_to_upstream_timeout(self):
        def timeout_handler(request):
            # MockTransport 不经过真实连接池超时；超时由传输层抛出 TimeoutException，
            # 这里模拟该行为以验证适配层的规范化映射
            raise httpx.ReadTimeout("timed out", request=request)

        provider = OpenAIChatProvider()
        with pytest.raises(ProviderError) as exc_info:
            await provider.complete(
                make_config(ModelProtocol.openai_chat),
                make_request(),
                transport=MockTransport(timeout_handler),
            )
        assert exc_info.value.code == "UPSTREAM_TIMEOUT"
        assert exc_info.value.retryable is True

    async def test_cancel_propagates(self):
        started = asyncio.Event()

        async def hanging_handler(request):
            started.set()
            await asyncio.sleep(10)
            return Response(200, json=OPENAI_CHAT_PAYLOAD)

        provider = OpenAIChatProvider()
        task = asyncio.create_task(
            provider.complete(
                make_config(ModelProtocol.openai_chat), make_request(), transport=MockTransport(hanging_handler)
            )
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_unsupported_parameter_rejected_before_send(self):
        def handler(request):
            raise AssertionError("不应发送请求")

        provider = OpenAIChatProvider()
        with pytest.raises(ProviderError) as exc_info:
            await provider.complete(
                make_config(ModelProtocol.openai_chat),
                make_request(params={"logit_bias": {"x": 1}}),
                transport=MockTransport(handler),
            )
        assert exc_info.value.code == "UNSUPPORTED_PARAMETER"


class TestFactory:
    def test_creates_provider_per_protocol(self):
        for protocol in ModelProtocol:
            assert create_provider(protocol.value).protocol == protocol

    def test_unknown_protocol_rejected(self):
        with pytest.raises(ProviderError) as exc_info:
            create_provider("gemini-native")
        assert exc_info.value.code == "UNSUPPORTED_PROTOCOL"
