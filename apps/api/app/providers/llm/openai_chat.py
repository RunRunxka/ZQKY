"""OpenAI-compatible Chat Completions 协议适配（POST {base}/chat/completions）。

按供应商元数据（registry）决定：
- 模型名前缀剥离（strip_model_prefix）
- `max_tokens` / `max_completion_tokens` 线型（supports_max_completion_tokens）
- 推理参数注入（reasoning_params，受控 effort）
- 模型级参数覆盖（moonshot kimi 删除 temperature 等）
- `stream_options.include_usage`（supports_stream_options）
- 请求头由适配器写入，用户附加头不得覆盖认证头

不使用参考的进程全局 env 注入；连接快照在每次调用显式传入（D9）。
"""

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
    text_from_content,
)
from app.providers.llm.reasoning_params import build_reasoning_kwargs
from app.providers.llm.registry import (
    find_provider,
    model_overrides_for,
    strip_provider_prefix,
)
from app.schemas.model_config import ModelProtocol


def _map_finish_reason(raw: Any) -> str:
    if raw == "stop":
        return FINISH_STOP
    if raw == "length":
        return FINISH_LENGTH
    return FINISH_UNKNOWN


def build_chat_body(config: LLMConfig, request: LLMRequest, *, stream: bool) -> dict[str, Any]:
    """按供应商元数据构建 Chat Completions 请求体（普通与流式共用）。"""
    spec = find_provider(config.providerId)
    model = strip_provider_prefix(config.modelId, spec)

    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
    }
    if stream:
        body["stream"] = True
        # 仅当注册表明确声明支持时才发送；无 providerId 的旧配置保持原请求字节（D3）
        if spec is not None and spec.supportsStreamOptions:
            body["stream_options"] = {"include_usage": True}

    params = dict(request.params)
    # 模型级参数覆盖（None=删除）；覆盖后仍以用户显式参数为准
    for key, value in model_overrides_for(config.modelId, spec).items():
        if value is None:
            params.pop(key, None)
        else:
            params.setdefault(key, value)
    body.update(params)

    if request.maxOutputTokens is not None:
        if spec is not None and spec.supportsMaxCompletionTokens:
            body["max_completion_tokens"] = request.maxOutputTokens
        else:
            body["max_tokens"] = request.maxOutputTokens

    reasoning = build_reasoning_kwargs(
        spec=spec,
        provider_id=config.providerId,
        model=config.modelId,
        reasoning_enabled=config.reasoningEnabled,
        reasoning_effort=config.reasoningEffort,
    )
    extra_body = reasoning.pop("extra_body", None)
    body.update(reasoning)
    if extra_body:
        # 供应商专有字段（thinking/enable_thinking/reasoning_split）平铺进请求体，
        # 与参考把 extra_body 合并进 payload 的行为等价。
        body.update(extra_body)
    return body


def build_auth_headers(config: LLMConfig, *, required: bool) -> dict[str, str]:
    key = resolve_api_key(config, required=required)
    if key:
        return merge_headers(config.extraHeaders, {"Authorization": f"Bearer {key}"})
    return merge_headers(config.extraHeaders, {})


class OpenAIChatProvider(LLMProvider):
    protocol = ModelProtocol.openai_chat
    requires_api_key = True

    def _base_url(self, config: LLMConfig) -> str:
        """允许子类（Copilot/CodeBuddy）用注册表默认地址填补空 baseUrl。"""
        return config.baseUrl.rstrip("/")

    def _headers(self, config: LLMConfig) -> dict[str, str]:
        """认证头在此统一写入；子类可覆盖以实现专有认证。"""
        return build_auth_headers(config, required=self.requires_api_key)

    async def _complete(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> LLMResponse:
        url = f"{self._base_url(config)}/chat/completions"
        headers = self._headers(config)
        data = await post_json(config, url, headers, build_chat_body(config, request, stream=False), transport)
        try:
            choice = data["choices"][0]
            text = text_from_content(choice["message"].get("content"))
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
        url = f"{self._base_url(config)}/chat/completions"
        headers = self._headers(config)
        body = build_chat_body(config, request, stream=True)

        finish_reason: str | None = None
        saw_text = False
        saw_reasoning = False
        async with open_stream(config, url, headers, body, transport) as (_response, sse):
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
                    raise ProviderError("UPSTREAM_ERROR", "模型流返回错误，请检查配置或稍后重试。")
                choices = payload.get("choices") or []
                if choices:
                    choice = choices[0] or {}
                    delta = choice.get("delta") or {}
                    content = text_from_content(delta.get("content"))
                    if content:
                        saw_text = True
                        yield LLMStreamEvent(type="text", text=content)
                    # 推理/正文分离：DeepSeek 用 reasoning_content，部分网关用 reasoning
                    reasoning = delta.get("reasoning_content")
                    if not isinstance(reasoning, str) or not reasoning:
                        reasoning = delta.get("reasoning")
                    if isinstance(reasoning, str) and reasoning:
                        saw_reasoning = True
                        yield LLMStreamEvent(type="reasoning", text=reasoning)
                    if choice.get("finish_reason"):
                        finish_reason = _map_finish_reason(choice["finish_reason"])
                usage = payload.get("usage")
                if usage:
                    # 只接受非零上报，避免部分网关逐帧发送零值把已知用量清空
                    input_tokens = usage.get("prompt_tokens")
                    output_tokens = usage.get("completion_tokens")
                    if input_tokens or output_tokens:
                        yield LLMStreamEvent(
                            type="usage",
                            usage=LLMUsage(inputTokens=input_tokens, outputTokens=output_tokens),
                        )
            if finish_reason is None:
                raise ProviderError("STREAM_INTERRUPTED", "模型未发送结束事件，已保留收到的内容。", retryable=True)
            if not saw_text:
                raise empty_response_error(
                    finish_reason, saw_reasoning=saw_reasoning, max_tokens=request.maxOutputTokens
                )
            yield LLMStreamEvent(type="end", finishReason=finish_reason)
