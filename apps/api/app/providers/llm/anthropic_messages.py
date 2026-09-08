"""Anthropic Messages 协议适配（POST {base}/v1/messages）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx2 as httpx

from app.providers.llm.base import (
    LLMProvider,
    FINISH_LENGTH,
    FINISH_STOP,
    FINISH_UNKNOWN,
    LLMConfig,
    LLMRequest,
    LLMResponse,
    LLMStreamEvent,
    LLMUsage,
    ProviderError,
    empty_response_error,
    iter_sse,
    open_stream,
    post_json,
    require_api_key,
)
from app.schemas.model_config import ModelProtocol

ANTHROPIC_VERSION = "2023-06-01"
# Anthropic 要求 max_tokens 必填；上游未给出预算时使用该安全默认值
DEFAULT_MAX_TOKENS = 256


class AnthropicMessagesProvider(LLMProvider):
    protocol = ModelProtocol.anthropic_messages

    async def _complete(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> LLMResponse:
        api_key = require_api_key(config)
        base = config.baseUrl.rstrip("/")
        url = f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages"

        system_parts = [m.content for m in request.messages if m.role == "system"]
        messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role in ("user", "assistant")
        ]
        if not messages:
            raise ProviderError(
                "INVALID_REQUEST",
                "Anthropic 协议至少需要一条 user 消息。",
                status_code=422,
            )
        body: dict[str, Any] = {
            "model": config.modelId,
            "max_tokens": request.maxOutputTokens or DEFAULT_MAX_TOKENS,
            "messages": messages,
            **request.params,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        headers = {
            "anthropic-version": ANTHROPIC_VERSION,
            **config.extraHeaders,
            # 凭证头由适配器最后写入，附加请求头不能覆盖 x-api-key
            "x-api-key": api_key,
        }
        data = await post_json(config, url, headers, body, transport)

        parts = [
            block.get("text") or ""
            for block in data.get("content") or []
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        stop_reason = data.get("stop_reason")
        if stop_reason == "end_turn":
            finish_reason = FINISH_STOP
        elif stop_reason == "max_tokens":
            finish_reason = FINISH_LENGTH
        else:
            finish_reason = FINISH_UNKNOWN
        usage = data.get("usage") or {}
        return LLMResponse(
            text="".join(parts),
            finishReason=finish_reason,
            usage=LLMUsage(
                inputTokens=usage.get("input_tokens"),
                outputTokens=usage.get("output_tokens"),
            ),
        )

    async def _stream(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> AsyncIterator[LLMStreamEvent]:
        api_key = require_api_key(config)
        base = config.baseUrl.rstrip("/")
        url = f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages"

        system_parts = [m.content for m in request.messages if m.role == "system"]
        messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role in ("user", "assistant")
        ]
        if not messages:
            raise ProviderError(
                "INVALID_REQUEST",
                "Anthropic 协议至少需要一条 user 消息。",
                status_code=422,
            )
        body: dict[str, Any] = {
            "model": config.modelId,
            "max_tokens": request.maxOutputTokens or DEFAULT_MAX_TOKENS,
            "messages": messages,
            "stream": True,
            **request.params,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        headers = {
            "anthropic-version": ANTHROPIC_VERSION,
            **config.extraHeaders,
            # 凭证头由适配器最后写入，附加请求头不能覆盖 x-api-key
            "x-api-key": api_key,
        }

        finish_reason: str | None = None
        usage = LLMUsage()
        saw_text = False
        saw_reasoning = False
        async with open_stream(config, url, headers, body, transport) as (response, sse):
            yield LLMStreamEvent(type="start")
            async for event_name, data in sse:
                try:
                    payload = json.loads(data)
                except ValueError:
                    continue
                if not isinstance(payload, dict):
                    continue
                event_name = event_name or payload.get("type")
                if event_name == "content_block_delta":
                    delta = payload.get("delta") or {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        saw_text = True
                        yield LLMStreamEvent(type="text", text=delta["text"])
                    # 思考型模型的推理增量（thinking 块）
                    elif delta.get("type") == "thinking_delta" and delta.get("thinking"):
                        saw_reasoning = True
                        yield LLMStreamEvent(type="reasoning", text=delta["thinking"])
                elif event_name == "message_start":
                    raw_usage = ((payload.get("message") or {}).get("usage") or {})
                    usage = LLMUsage(inputTokens=raw_usage.get("input_tokens"), outputTokens=usage.outputTokens)
                elif event_name == "message_delta":
                    delta = payload.get("delta") or {}
                    stop_reason = delta.get("stop_reason")
                    if stop_reason == "end_turn":
                        finish_reason = FINISH_STOP
                    elif stop_reason == "max_tokens":
                        finish_reason = FINISH_LENGTH
                    else:
                        finish_reason = FINISH_UNKNOWN
                    raw_usage = payload.get("usage") or {}
                    usage = LLMUsage(inputTokens=usage.inputTokens, outputTokens=raw_usage.get("output_tokens"))
                elif event_name == "error":
                    raise ProviderError(
                        "UPSTREAM_ERROR", "上游流返回错误。"
                    )
            if usage != LLMUsage():
                yield LLMStreamEvent(type="usage", usage=usage)
            if finish_reason is None:
                raise ProviderError("STREAM_INTERRUPTED", "模型未发送结束事件，已保留收到的内容。", retryable=True)
            if not saw_text:
                raise empty_response_error(
                    finish_reason, saw_reasoning=saw_reasoning, max_tokens=request.maxOutputTokens
                )
            yield LLMStreamEvent(type="end", finishReason=finish_reason)
