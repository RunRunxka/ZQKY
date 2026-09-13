"""Anthropic Messages 协议适配（POST {base}/v1/messages）。

同时服务两类供应商：backend=anthropic 的原生供应商，以及声明了 anthropic 格式的
OpenAI 兼容供应商（如 MiniMax `/anthropic`）。

推理控制（D6）：受控 effort → `thinking` 参数；关闭时不发送。Anthropic 要求
thinking 开启时温度固定为 1 且 max_tokens 必须大于预算。
"""

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
    merge_headers,
    open_stream,
    post_json,
    resolve_api_key,
)
from app.providers.llm.registry import find_provider, strip_provider_prefix
from app.schemas.model_config import ModelProtocol

ANTHROPIC_VERSION = "2023-06-01"
# Anthropic 要求 max_tokens 必填；上游未给出预算时使用该安全默认值
DEFAULT_MAX_TOKENS = 256
# effort → thinking 预算（参考 anthropic_provider.py:429-437 的取值口径）
_THINKING_BUDGETS = {
    "minimal": 1024,
    "low": 1024,
    "medium": 4096,
    "high": 8192,
    "xhigh": 16384,
    "max": 32768,
}


def _thinking_budget(config: LLMConfig) -> int | None:
    if config.reasoningEnabled is False:
        return None
    effort = (config.reasoningEffort or "").lower()
    if effort in {"none", ""}:
        return None
    return _THINKING_BUDGETS.get(effort)


class AnthropicMessagesProvider(LLMProvider):
    protocol = ModelProtocol.anthropic_messages
    requires_api_key = True

    def _url(self, config: LLMConfig) -> str:
        base = config.baseUrl.rstrip("/")
        return f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages"

    def _headers(self, config: LLMConfig) -> dict[str, str]:
        key = resolve_api_key(config, required=self.requires_api_key)
        auth: dict[str, str] = {"anthropic-version": ANTHROPIC_VERSION}
        if key:
            auth["x-api-key"] = key
        return merge_headers(config.extraHeaders, auth)

    def _body(self, config: LLMConfig, request: LLMRequest, *, stream: bool) -> dict[str, Any]:
        model = strip_provider_prefix(config.modelId, find_provider(config.providerId))
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
        max_tokens = request.maxOutputTokens or DEFAULT_MAX_TOKENS

        budget = _thinking_budget(config)
        if budget is not None:
            # Anthropic 要求 max_tokens > budget_tokens，且 thinking 开启时温度固定 1.0
            max_tokens = max(max_tokens, budget + 4096)

        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        body.update(request.params)
        if budget is not None:
            body["thinking"] = {"type": "enabled", "budget_tokens": budget}
            body["temperature"] = 1.0
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        if stream:
            body["stream"] = True
        return body

    async def _complete(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> LLMResponse:
        data = await post_json(
            config,
            self._url(config),
            self._headers(config),
            self._body(config, request, stream=False),
            transport,
        )

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
        url = self._url(config)
        headers = self._headers(config)
        body = self._body(config, request, stream=True)

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
