"""Provider 流式适配测试：SSE 解析、UTF-8 分块、事件规范化、错误与取消。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from httpx2 import MockTransport, Response

import httpx2 as httpx

from app.providers.llm.anthropic_messages import AnthropicMessagesProvider
from app.providers.llm.base import LLMConfig, LLMMessage, LLMRequest, LLMStreamEvent, ProviderError
from app.providers.llm.factory import create_provider
from app.providers.llm.openai_chat import OpenAIChatProvider
from app.providers.llm.openai_responses import OpenAIResponsesProvider
from app.schemas.model_config import ModelProtocol


def make_config(protocol: ModelProtocol) -> LLMConfig:
    return LLMConfig(
        protocol=protocol,
        baseUrl="https://api.example.com/v1",
        modelId="sim-model",
        apiKey="sk-test",
    )


def make_request(**kwargs) -> LLMRequest:
    messages = kwargs.pop("messages", [LLMMessage(role="user", content="你好")])
    return LLMRequest(messages=messages, **kwargs)


def sse_response(chunks: list[bytes]) -> MockTransport:
    """按字节块分片返回 SSE 流，可模拟 UTF-8 字符跨块与增量到达。"""

    async def content() -> AsyncIterator[bytes]:
        for chunk in chunks:
            yield chunk

    def handler(request):
        return Response(200, headers={"content-type": "text/event-stream"}, content=content())

    return MockTransport(handler)


async def collect(provider, protocol: ModelProtocol, transport) -> list[LLMStreamEvent]:
    return [event async for event in provider.stream(make_config(protocol), make_request(), transport=transport)]


class TestOpenAIChatStream:
    async def test_events_and_request_shape(self):
        captured = {}

        def handler(request):
            captured["body"] = json.loads(request.content)
            chunks = [
                b'data: {"choices":[{"delta":{"content":"\xe4\xbd\xa0"}}]}\n\n',
                b'data: {"choices":[{"delta":{"content":"\xe5\xa5\xbd"}}]}\n\n',
                b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
                b'data: {"usage":{"prompt_tokens":9,"completion_tokens":2}}\n\n',
                b"data: [DONE]\n\n",
            ]
            return Response(200, headers={"content-type": "text/event-stream"}, content=iterate(chunks))

        async def iterate(items):
            for item in items:
                yield item

        provider = OpenAIChatProvider()
        events = [
            event
            async for event in provider.stream(
                make_config(ModelProtocol.openai_chat), make_request(), transport=MockTransport(handler)
            )
        ]
        assert captured["body"]["stream"] is True
        assert "stream_options" not in captured["body"]
        assert [e.type for e in events] == ["start", "text", "text", "usage", "end"]
        assert events[1].text == "你" and events[2].text == "好"
        assert events[-1].finishReason == "stop"
        assert events[3].usage.outputTokens == 2

    async def test_utf8_split_across_chunks(self):
        payload = 'data: {"choices":[{"delta":{"content":"你好，世界"}}]}\n\n'.encode("utf-8")
        split = payload.index("，".encode("utf-8")) + 2  # 切在“，”三字节中间
        transport = sse_response([payload[:split], payload[split:], b"data: [DONE]\n\n"])
        events = await collect(OpenAIChatProvider(), ModelProtocol.openai_chat, transport)
        texts = [e.text for e in events if e.type == "text"]
        assert "".join(texts) == "你好，世界"

    async def test_midstream_error_payload_raises(self):
        chunks = [
            'data: {"choices":[{"delta":{"content":"部分"}}]}\n\n'.encode("utf-8"),
            'data: {"error":{"message":"上游内部错误"}}\n\n'.encode("utf-8"),
        ]
        transport = sse_response(chunks)
        provider = OpenAIChatProvider()
        with pytest.raises(Exception) as exc_info:
            [e async for e in provider.stream(make_config(ModelProtocol.openai_chat), make_request(), transport=transport)]
        assert exc_info.value.code == 'UPSTREAM_ERROR'
        assert "上游内部错误" not in str(exc_info.value)


class TestAnthropicStream:
    async def test_events_merged_usage(self):
        chunks = [
            b'event: message_start\ndata: {"message":{"usage":{"input_tokens":7}}}\n\n',
            'event: content_block_delta\ndata: {"delta":{"type":"text_delta","text":"中文"}}\n\n'.encode("utf-8"),
            'event: content_block_delta\ndata: {"delta":{"type":"text_delta","text":"回答"}}\n\n'.encode("utf-8"),
            b'event: message_delta\ndata: {"delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":4}}\n\n',
            b'event: message_stop\ndata: {}\n\n',
        ]
        transport = sse_response(chunks)
        events = await collect(AnthropicMessagesProvider(), ModelProtocol.anthropic_messages, transport)
        assert [e.type for e in events] == ["start", "text", "text", "usage", "end"]
        usage_event = next(e for e in events if e.type == "usage")
        assert usage_event.usage.inputTokens == 7
        assert usage_event.usage.outputTokens == 4
        assert events[-1].finishReason == "stop"

    async def test_max_tokens_stop_reason(self):
        chunks = [
            'event: content_block_delta\ndata: {"delta":{"type":"text_delta","text":"截断"}}\n\n'.encode("utf-8"),
            b'event: message_delta\ndata: {"delta":{"stop_reason":"max_tokens"},"usage":{}}\n\n',
        ]
        events = await collect(AnthropicMessagesProvider(), ModelProtocol.anthropic_messages, sse_response(chunks))
        assert events[-1].finishReason == "length"


class TestResponsesStream:
    async def test_events(self):
        chunks = [
            'event: response.output_text.delta\ndata: {"delta":"回答A"}\n\n'.encode("utf-8"),
            'event: response.output_text.delta\ndata: {"delta":"回答B"}\n\n'.encode("utf-8"),
            b'event: response.completed\ndata: {"response":{"status":"completed","usage":{"input_tokens":6,"output_tokens":5}}}\n\n',
        ]
        events = await collect(OpenAIResponsesProvider(), ModelProtocol.openai_responses, sse_response(chunks))
        assert [e.type for e in events] == ["start", "text", "text", "usage", "end"]
        assert events[-1].finishReason == "stop"
        assert events[3].usage.inputTokens == 6

    async def test_failed_event_raises(self):
        chunks = [
            'event: response.failed\ndata: {"response":{"error":{"message":"生成失败"}}}\n\n'.encode("utf-8"),
        ]
        with pytest.raises(Exception) as exc_info:
            await collect(OpenAIResponsesProvider(), ModelProtocol.openai_responses, sse_response(chunks))
        assert exc_info.value.code == 'UPSTREAM_ERROR'
        assert "生成失败" not in str(exc_info.value)


class TestStreamErrors:
    async def test_pre_stream_401_raises_before_first_event(self):
        def handler(request):
            return Response(401, json={"error": {"message": "无效密钥"}})

        provider = OpenAIChatProvider()
        generator = provider.stream(
            make_config(ModelProtocol.openai_chat), make_request(), transport=MockTransport(handler)
        )
        from app.providers.llm.base import ProviderError

        with pytest.raises(ProviderError) as exc_info:
            await generator.__anext__()
        assert exc_info.value.code == "UPSTREAM_AUTH_FAILED"

    async def test_timeout_exception_maps(self):
        def handler(request):
            raise httpx.ReadTimeout("timed out", request=request)

        provider = OpenAIChatProvider()
        generator = provider.stream(
            make_config(ModelProtocol.openai_chat), make_request(), transport=MockTransport(handler)
        )
        from app.providers.llm.base import ProviderError

        with pytest.raises(ProviderError) as exc_info:
            await generator.__anext__()
        assert exc_info.value.code == "UPSTREAM_TIMEOUT"

    async def test_cancel_propagates_and_closes(self):
        started = asyncio.Event()

        async def slow_content():
            yield 'data: {"choices":[{"delta":{"content":"第一段"}}]}\n\n'.encode("utf-8")
            started.set()
            await asyncio.sleep(30)
            yield 'data: {"choices":[{"delta":{"content":"第二段"}}]}\n\n'.encode("utf-8")

        def handler(request):
            return Response(200, headers={"content-type": "text/event-stream"}, content=slow_content())

        provider = OpenAIChatProvider()
        events: list[LLMStreamEvent] = []

        async def consume():
            async for event in provider.stream(
                make_config(ModelProtocol.openai_chat), make_request(), transport=MockTransport(handler)
            ):
                events.append(event)

        task = asyncio.create_task(consume())
        await started.wait()
        # 保证第一段已被消费
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert [e.type for e in events] == ["start", "text"]


class TestReasoningAndEmptyResponse:
    """推理模型输出形态：reasoning_content / thinking 增量与仅推理时的可操作诊断。"""

    async def test_reasoning_and_text_both_emitted(self):
        reasoning_chunk = (
            'data: {"choices":[{"delta":{"reasoning_content":"\u63a8\u7406"}}]}\n\n'.encode("utf-8")
        )
        text_chunk = 'data: {"choices":[{"delta":{"content":"\u7b54"}}]}\n\n'.encode("utf-8")
        chunks = [
            reasoning_chunk,
            text_chunk,
            b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
            b"data: [DONE]\n\n",
        ]
        events = await collect(OpenAIChatProvider(), ModelProtocol.openai_chat, sse_response(chunks))
        kinds = [e.type for e in events]
        assert "reasoning" in kinds and "text" in kinds
        assert events[-1].finishReason == "stop"

    async def test_reasoning_only_with_length_gives_actionable_error(self):
        reasoning_chunk = (
            'data: {"choices":[{"delta":{"reasoning_content":"\u601d\u8003\u4e2d"}}]}\n\n'.encode("utf-8")
        )
        length_chunk = b'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n'
        done_chunk = b"data: [DONE]\n\n"
        provider = OpenAIChatProvider()
        request = make_request(maxOutputTokens=256)
        with pytest.raises(ProviderError) as exc_info:
            _ = [
                e
                async for e in provider.stream(
                    make_config(ModelProtocol.openai_chat),
                    request,
                    transport=sse_response([reasoning_chunk, length_chunk, done_chunk]),
                )
            ]
        assert exc_info.value.code == "EMPTY_RESPONSE"
        assert "推理" in str(exc_info.value)
        assert "输出上限" in str(exc_info.value)
        assert "256" in str(exc_info.value)

    async def test_content_as_list_parts_extracted(self):
        parts_chunk = (
            'data: {"choices":[{"delta":{"content":[{"type":"text","text":"\u5206\u5757"}]}}]}\n\n'.encode(
                "utf-8"
            )
        )
        events = await collect(
            OpenAIChatProvider(),
            ModelProtocol.openai_chat,
            sse_response([parts_chunk, b"data: [DONE]\n\n"]),
        )
        texts = [e.text for e in events if e.type == "text"]
        assert "".join(texts) == "\u5206\u5757"

    async def test_plain_empty_stop_keeps_generic_message(self):
        chunks = [b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n', b"data: [DONE]\n\n"]
        provider = OpenAIChatProvider()
        with pytest.raises(ProviderError) as exc_info:
            _ = [
                e
                async for e in provider.stream(
                    make_config(ModelProtocol.openai_chat), make_request(), transport=sse_response(chunks)
                )
            ]
        assert exc_info.value.code == "EMPTY_RESPONSE"
        assert "推理" not in str(exc_info.value)

    async def test_anthropic_thinking_delta_reasoning(self):
        chunks = [
            b'event: content_block_delta\ndata: {"delta":{"type":"thinking_delta","thinking":"think"}}\n\n',
            b'event: content_block_delta\ndata: {"delta":{"type":"text_delta","text":"answer"}}\n\n',
            b'event: message_delta\ndata: {"delta":{"stop_reason":"end_turn"},"usage":{}}\n\n',
        ]
        events = await collect(AnthropicMessagesProvider(), ModelProtocol.anthropic_messages, sse_response(chunks))
        assert [e.type for e in events] == ["start", "reasoning", "text", "end"]
