"""OpenAI Codex 适配：登录后走 ChatGPT 后端 Responses 端点（D11/D16）。

参考 `provider_core/openai_codex_provider.py`：
- 令牌来自受管的 OAuth 服务（本实现为智启课源自有的 `CodexOAuthService`）。
- 请求头：`Authorization: Bearer`、`chatgpt-account-id`（有账号时）、`OpenAI-Beta: responses=experimental`。
- 不接受 `max_tokens`/`temperature`（参考显式删除）。
- 未登录时返回可操作错误，绝不自称可用。

不硬编码参考的 client_id/originator（那属于冒充 Codex CLI 身份），
也不读取任何第三方登录文件。
"""

from __future__ import annotations

import hashlib
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
    merge_headers,
)
from app.providers.llm.codex_oauth import CODEX_DEFAULT_MODEL, CodexOAuthService
from app.providers.llm.registry import find_provider, strip_provider_prefix
from app.schemas.model_config import ModelProtocol

CODEX_RESPONSES_PATH = "/codex/responses"
DEFAULT_CODEX_BASE = "https://chatgpt.com/backend-api"
STREAM_TIMEOUT_SECONDS = 120.0


class OpenAICodexProvider(LLMProvider):
    protocol = ModelProtocol.openai_responses
    requires_api_key = False

    def __init__(self, oauth_service: CodexOAuthService | None = None) -> None:
        self._oauth = oauth_service

    def bind_oauth(self, service: CodexOAuthService) -> None:
        self._oauth = service

    def _require_service(self) -> CodexOAuthService:
        if self._oauth is None:
            raise ProviderError(
                "AUTH_REQUIRED",
                "Codex 认证服务未初始化。",
                status_code=400,
            )
        return self._oauth

    async def _ensure_token(self, config: LLMConfig) -> tuple[str, str | None]:
        """取可用令牌：过期先续期，续不了就明确要求重新登录（MR-11）。"""
        service = self._require_service()
        if not config.connectionId:
            raise ProviderError("AUTH_REQUIRED", "缺少连接标识，无法读取 Codex 登录状态。", status_code=400)
        stored = service.load_tokens(config.connectionId)
        if stored is None or not stored.access_token:
            raise ProviderError(
                "AUTH_REQUIRED",
                "尚未完成 Codex 登录，请先在设置中开始授权流程。",
                status_code=400,
            )
        token = await service.get_access_token(config.connectionId)
        if not token:
            raise ProviderError(
                "AUTH_EXPIRED",
                "Codex 登录已过期且无法自动续期，请重新授权。",
                status_code=401,
            )
        # 续期可能刷新 account_id，取最新快照
        latest = service.load_tokens(config.connectionId) or stored
        return token, latest.account_id

    def _url(self, config: LLMConfig) -> str:
        base = (config.baseUrl or DEFAULT_CODEX_BASE).rstrip("/")
        if base.endswith("/codex"):
            return f"{base}/responses"
        return f"{base}{CODEX_RESPONSES_PATH}"

    async def _build_headers(self, config: LLMConfig) -> dict[str, str]:
        token, account_id = await self._ensure_token(config)
        auth: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "OpenAI-Beta": "responses=experimental",
            "Accept": "text/event-stream",
            "originator": "zhiqikeyuan",
            "User-Agent": "zhiqikeyuan/1",
        }
        if account_id:
            auth["chatgpt-account-id"] = account_id
        return merge_headers(config.extraHeaders, auth)

    def _body(self, config: LLMConfig, request: LLMRequest) -> dict[str, Any]:
        model = strip_provider_prefix(config.modelId, find_provider(config.providerId)) or CODEX_DEFAULT_MODEL
        input_items = []
        for message in request.messages:
            text_type = "output_text" if message.role == "assistant" else "input_text"
            input_items.append(
                {"role": message.role, "content": [{"type": text_type, "text": message.content}]}
            )
        return {
            "model": model,
            "input": input_items,
            "store": False,
            "stream": True,
            "instructions": "",
            "text": {"verbosity": "medium"},
            "parallel_tool_calls": True,
        }

    async def _complete(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> LLMResponse:
        response = await self._collect(config, request, transport)
        return response

    async def _collect(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> LLMResponse:
        text_parts: list[str] = []
        finish_reason = FINISH_UNKNOWN
        usage: LLMUsage | None = None
        async for event in self._stream(config, request, transport):
            if event.type == "text" and event.text:
                text_parts.append(event.text)
            elif event.type == "usage":
                usage = event.usage
            elif event.type == "end":
                finish_reason = event.finishReason or FINISH_UNKNOWN
        return LLMResponse(text="".join(text_parts), finishReason=finish_reason, usage=usage)

    async def _stream(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> AsyncIterator[LLMStreamEvent]:
        url = self._url(config)
        headers = await self._build_headers(config)
        body = self._body(config, request)
        timeout = httpx.Timeout(config.timeoutSeconds, read=STREAM_TIMEOUT_SECONDS)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False) as client:
                async with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code == 401:
                        raise ProviderError("AUTH_EXPIRED", "Codex 登录已过期，请重新授权。", status_code=401)
                    if response.status_code >= 400:
                        raise ProviderError("UPSTREAM_ERROR", f"Codex 上游返回错误（HTTP {response.status_code}）。")
                    yield LLMStreamEvent(type="start")
                    finish_reason: str | None = None
                    usage = LLMUsage()
                    saw_text = False
                    saw_reasoning = False
                    async for event_name, data in iter_sse(response):
                        try:
                            payload = json.loads(data)
                        except ValueError:
                            continue
                        if not isinstance(payload, dict):
                            continue
                        name = event_name or payload.get("type")
                        if name == "response.output_text.delta":
                            if payload.get("delta"):
                                saw_text = True
                                yield LLMStreamEvent(type="text", text=payload["delta"])
                        elif name in ("response.reasoning_summary_text.delta", "response.reasoning_text.delta"):
                            if payload.get("delta"):
                                saw_reasoning = True
                                yield LLMStreamEvent(type="reasoning", text=payload["delta"])
                        elif name == "error":
                            raise ProviderError("UPSTREAM_ERROR", "Codex 流返回错误。")
                        elif name in ("response.completed", "response.incomplete"):
                            inner = payload.get("response") or {}
                            raw_usage = inner.get("usage") or {}
                            usage = LLMUsage(
                                inputTokens=raw_usage.get("input_tokens"),
                                outputTokens=raw_usage.get("output_tokens"),
                            )
                            if name == "response.completed":
                                finish_reason = FINISH_STOP
                            elif (inner.get("incomplete_details") or {}).get("reason") == "max_output_tokens":
                                finish_reason = FINISH_LENGTH
                            else:
                                finish_reason = FINISH_UNKNOWN
                    if usage != LLMUsage():
                        yield LLMStreamEvent(type="usage", usage=usage)
                    if finish_reason is None:
                        raise ProviderError("STREAM_INTERRUPTED", "Codex 未发送结束事件，已保留收到的内容。", retryable=True)
                    if not saw_text:
                        raise empty_response_error(
                            finish_reason, saw_reasoning=saw_reasoning, max_tokens=request.maxOutputTokens
                        )
                    yield LLMStreamEvent(type="end", finishReason=finish_reason)
        except httpx.TimeoutException as exc:
            raise ProviderError("UPSTREAM_TIMEOUT", "等待 Codex 响应超时。", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("UPSTREAM_UNREACHABLE", "无法连接 Codex 后端。", retryable=True) from exc

    @staticmethod
    def prompt_cache_key(messages: list) -> str:
        serialized = json.dumps(
            [{"role": m.role, "content": m.content} for m in messages],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


__all__ = ["DEFAULT_CODEX_BASE", "OpenAICodexProvider"]
