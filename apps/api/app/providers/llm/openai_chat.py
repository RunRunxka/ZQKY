"""OpenAI-compatible Chat Completions 协议适配（POST {base}/chat/completions）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx2 as httpx

from app.providers.llm.base import (
    FINISH_LENGTH,
    FINISH_STOP,
    FINISH_UNKNOWN,
    LLMConfig,
    LLMProvider,
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
    text_from_content,
)
from app.schemas.model_config import ModelProtocol


def _map_finish_reason(raw: Any) -> str:
    if raw == "stop":
        return FINISH_STOP
    if raw == "length":
        return FINISH_LENGTH
    return FINISH_UNKNOWN


class OpenAIChatProvider(LLMProvider):
    protocol = ModelProtocol.openai_chat

    async def _complete(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> LLMResponse:
        api_key = require_api_key(config)
        url = f"{config.baseUrl}/chat/completions"
        messages = [
            {"role": message.role, "content": message.content} for message in request.messages
        ]
        body: dict[str, Any] = {"model": config.modelId, "messages": messages, **request.params}
        if request.maxOutputTokens is not None:
            # 兼容服务器以 max_tokens 为准；正式 OpenAI 端点的参数适配随流式一起复核
            body["max_tokens"] = request.maxOutputTokens
        # 凭证头由适配器最后写入，附加请求头不能覆盖 Authorization
        headers = {**config.extraHeaders, "Authorization": f"Bearer {api_key}"}
        data = await post_json(config, url, headers, body, transport)
        try:
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
            finish_reason = _map_finish_reason(choice.get("finish_reason"))
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ProviderError("UPSTREAM_ERROR", "上游响应缺少预期字段（choices）。") from exc
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            finishReason=finish_reason,
            usage=LLMUsage(
                inputTokens=usage.get("prompt_tokens"),
                outputTokens=usage.get("completion_tokens"),
            ),
        )

    async def _stream(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> AsyncIterator[LLMStreamEvent]:
        api_key = require_api_key(config)
        url = f"{config.baseUrl}/chat/completions"
        messages = [
            {"role": message.role, "content": message.content} for message in request.messages
        ]
        body: dict[str, Any] = {
            "model": config.modelId,
            "messages": messages,
            "stream": True,
            # OpenAI 官方约定；不支持该字段的服务器会忽略它，用量按“未知”展示
            **request.params,
        }
        if request.maxOutputTokens is not None:
            body["max_tokens"] = request.maxOutputTokens
        headers = {**config.extraHeaders, "Authorization": f"Bearer {api_key}"}

        finish_reason: str | None = None
        saw_text = False
        saw_reasoning = False
        async with open_stream(config, url, headers, body, transport) as (response, sse):
            yield LLMStreamEvent(type="start")
            async for _event_name, data in sse:
                if data.strip() == "[DONE]":
                    finish_reason = finish_reason or FINISH_UNKNOWN
                    break
                try:
                    payload = json.loads(data)
                except ValueError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if payload.get("error"):
                    raise ProviderError(
                        "UPSTREAM_ERROR",
                        "模型流返回错误，请检查配置或稍后重试。",
                    )
                choices = payload.get("choices") or []
                if choices:
                    choice = choices[0] or {}
                    delta = choice.get("delta") or {}
                    # 正文兼容两种形态：字符串与 [{type:'text', text:'...'}] 分块
                    content = text_from_content(delta.get("content"))
                    if content:
                        saw_text = True
                        yield LLMStreamEvent(type="text", text=content)
                    # 推理模型（如 DeepSeek reasoner 系列）把思考过程放在 reasoning_content
                    reasoning = delta.get("reasoning_content")
                    if isinstance(reasoning, str) and reasoning:
                        saw_reasoning = True
                        yield LLMStreamEvent(type="reasoning", text=reasoning)
                    if choice.get("finish_reason"):
                        finish_reason = _map_finish_reason(choice["finish_reason"])
                usage = payload.get("usage")
                if usage:
                    yield LLMStreamEvent(
                        type="usage",
                        usage=LLMUsage(
                            inputTokens=usage.get("prompt_tokens"),
                            outputTokens=usage.get("completion_tokens"),
                        ),
                    )
            if finish_reason is None:
                raise ProviderError("STREAM_INTERRUPTED", "模型未发送结束事件，已保留收到的内容。", retryable=True)
            if not saw_text:
                raise empty_response_error(
                    finish_reason, saw_reasoning=saw_reasoning, max_tokens=request.maxOutputTokens
                )
            yield LLMStreamEvent(type="end", finishReason=finish_reason)
