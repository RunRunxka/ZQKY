"""OpenAI Responses 协议适配（POST {base}/responses）。"""

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
    merge_headers,
    open_stream,
    post_json,
    resolve_api_key,
)
from app.providers.llm.reasoning_params import build_reasoning_kwargs
from app.providers.llm.registry import find_provider, strip_provider_prefix
from app.schemas.model_config import ModelProtocol


class OpenAIResponsesProvider(LLMProvider):
    protocol = ModelProtocol.openai_responses

    def _url(self, config: LLMConfig) -> str:
        """端点构造点；Azure 子类覆盖以归一化地址与附加 api-version。"""
        return f"{config.baseUrl.rstrip('/')}/responses"

    def _headers(self, config: LLMConfig) -> dict[str, str]:
        key = resolve_api_key(config, required=self.requires_api_key)
        auth = {"Authorization": f"Bearer {key}"} if key else {}
        return merge_headers(config.extraHeaders, auth)

    def _body(self, config: LLMConfig, request: LLMRequest, *, stream: bool) -> dict[str, Any]:
        spec = find_provider(config.providerId)
        model = strip_provider_prefix(config.modelId, spec)
        input_items = []
        for message in request.messages:
            text_type = "output_text" if message.role == "assistant" else "input_text"
            input_items.append(
                {"role": message.role, "content": [{"type": text_type, "text": message.content}]}
            )
        body: dict[str, Any] = {"model": model, "input": input_items, **request.params}
        if stream:
            body["stream"] = True
        if request.maxOutputTokens is not None:
            body["max_output_tokens"] = request.maxOutputTokens
        reasoning = build_reasoning_kwargs(
            spec=spec,
            provider_id=config.providerId,
            model=config.modelId,
            reasoning_enabled=config.reasoningEnabled,
            reasoning_effort=config.reasoningEffort,
        )
        effort = reasoning.get("reasoning_effort")
        if effort:
            # Responses 用 reasoning.effort（而非顶层 reasoning_effort）
            body["reasoning"] = {"effort": effort, "summary": "auto"}
        return body

    async def _complete(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> LLMResponse:
        url = self._url(config)
        data = await post_json(config, url, self._headers(config), self._body(config, request, stream=False), transport)

        text = self._extract_text(data)
        status = data.get("status")
        if status == "completed":
            finish_reason = FINISH_STOP
        elif status == "incomplete":
            reason = (data.get("incomplete_details") or {}).get("reason")
            finish_reason = FINISH_LENGTH if reason == "max_output_tokens" else FINISH_UNKNOWN
        else:
            finish_reason = FINISH_UNKNOWN
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            finishReason=finish_reason,
            usage=LLMUsage(
                inputTokens=usage.get("input_tokens"),
                outputTokens=usage.get("output_tokens"),
            ),
        )

    def _extract_text(self, data: dict[str, Any]) -> str:
        parts: list[str] = []
        for item in data.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") == "output_text":
                    parts.append(content.get("text") or "")
        if not parts and isinstance(data.get("output_text"), str):
            # 某些兼容服务器直接返回 output_text 字符串
            parts.append(data["output_text"])
        return "".join(parts)

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
                if event_name == "response.output_text.delta":
                    if payload.get("delta"):
                        saw_text = True
                        yield LLMStreamEvent(type="text", text=payload["delta"])
                elif event_name == "response.reasoning_summary_text.delta":
                    # 推理摘要增量（o 系/推理型模型）
                    if payload.get("delta"):
                        saw_reasoning = True
                        yield LLMStreamEvent(type="reasoning", text=payload["delta"])
                elif event_name == "error":
                    raise ProviderError(
                        "UPSTREAM_ERROR", "模型流返回错误，请检查配置或稍后重试。"
                    )
                elif event_name == "response.failed":
                    error = (payload.get("response") or {}).get("error") or {}
                    raise ProviderError(
                        "UPSTREAM_ERROR", "上游响应失败。"
                    )
                elif event_name in ("response.completed", "response.incomplete"):
                    response_payload = payload.get("response") or {}
                    raw_usage = response_payload.get("usage") or {}
                    usage = LLMUsage(
                        inputTokens=raw_usage.get("input_tokens"),
                        outputTokens=raw_usage.get("output_tokens"),
                    )
                    if event_name == "response.completed":
                        finish_reason = FINISH_STOP
                    elif (response_payload.get("incomplete_details") or {}).get("reason") == "max_output_tokens":
                        finish_reason = FINISH_LENGTH
                    else:
                        finish_reason = FINISH_UNKNOWN
            if usage != LLMUsage():
                yield LLMStreamEvent(type="usage", usage=usage)
            if finish_reason is None:
                raise ProviderError("STREAM_INTERRUPTED", "模型未发送结束事件，已保留收到的内容。", retryable=True)
            if not saw_text:
                raise empty_response_error(
                    finish_reason, saw_reasoning=saw_reasoning, max_tokens=request.maxOutputTokens
                )
            yield LLMStreamEvent(type="end", finishReason=finish_reason)
