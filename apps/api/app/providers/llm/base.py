"""统一 LLM Provider 接口与协议无关的 HTTP/错误规范化。

接口划分参考 DeepTutor v1.6.4（Apache-2.0，固定提交 93df3d48）的
LLMProvider / LLMResponse / GenerationSettings 设计，实现为本项目自有代码，未复制其源码。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from contextlib import aclosing, asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx2 as httpx

from app.core.exceptions import AppError
from app.schemas.model_config import ModelProtocol

# 规范化结束原因：上游取值一律映射到这一集合，未知值不得伪装成 stop
FINISH_STOP = "stop"
FINISH_LENGTH = "length"
FINISH_ERROR = "error"
FINISH_UNKNOWN = "unknown"

DEFAULT_TIMEOUT_SECONDS = 30.0
STREAM_TIMEOUT_SECONDS = 120.0


class ProviderError(AppError):
    """上游调用失败；message 已脱敏，不包含凭证或完整上游响应。"""

    def __init__(self, code: str, message: str, *, status_code: int = 502, retryable: bool = False) -> None:
        super().__init__(message, code=code, status_code=status_code, retryable=retryable)


@dataclass(frozen=True)
class LLMConfig:
    protocol: ModelProtocol
    baseUrl: str
    modelId: str
    apiKey: str | None = None
    extraHeaders: dict[str, str] = field(default_factory=dict)
    timeoutSeconds: float = DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class LLMMessage:
    role: str  # system | user | assistant
    content: str


@dataclass
class LLMRequest:
    messages: list[LLMMessage]
    maxOutputTokens: int | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMUsage:
    inputTokens: int | None = None
    outputTokens: int | None = None


@dataclass(frozen=True)
class LLMStreamEvent:
    """规范化流事件：start（上游 200 确认）、text（增量文本）、usage、end（结束原因）。"""

    type: str
    text: str | None = None
    finishReason: str | None = None
    usage: LLMUsage | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str
    finishReason: str
    usage: LLMUsage | None = None


def check_params(request: LLMRequest, supported: frozenset[str]) -> None:
    unsupported = sorted(set(request.params) - supported)
    if unsupported:
        raise ProviderError(
            "UNSUPPORTED_PARAMETER",
            f"当前协议不支持参数：{', '.join(unsupported)}。",
            status_code=422,
        )


def require_api_key(config: LLMConfig) -> str:
    if not config.apiKey:
        raise ProviderError(
            "MODEL_NOT_CONFIGURED",
            "该连接未保存凭证，请先在设置中填写 API Key。",
            status_code=400,
        )
    return config.apiKey


def _sanitize_upstream_message(response: httpx.Response, fallback: str) -> str:
    # 上游错误可能回显密钥、请求头或提示词，统一使用本地文案。
    return fallback


def sanitize_error_text(text: str, fallback: str) -> str:
    return fallback


def text_from_content(content: object) -> str:
    """正文形态兼容：字符串直接返回；[{type:'text', text:'...'}] 分块拼接；其余为空。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def empty_response_error(
    finish_reason: str | None, *, saw_reasoning: bool, max_tokens: int | None
) -> "ProviderError":
    """流干净结束但没有正文时的可操作诊断：区分推理耗尽预算、仅推理内容与纯空响应。"""
    budget = f"当前输出上限 {max_tokens} tokens。" if max_tokens else ""
    if finish_reason == FINISH_LENGTH:
        if saw_reasoning:
            message = (
                f"模型已产生推理内容，但输出预算在生成正文前耗尽（{budget}结束原因：length）。"
                "请在设置的模型配置中增大输出上限后重试。"
            )
        else:
            message = (
                f"输出预算内未返回正文（{budget}结束原因：length）。"
                "请在设置的模型配置中增大输出上限后重试。"
            )
    elif saw_reasoning:
        message = "模型仅返回推理内容，未输出正文。请检查模型能力或更换模型。"
    else:
        message = "模型未返回正文，请检查协议、输出预算或模型能力。"
    return ProviderError("EMPTY_RESPONSE", message)


async def raise_for_stream_status(response: httpx.Response) -> None:
    if 200 <= response.status_code < 300:
        return
    if response.status_code in (401, 403):
        raise ProviderError("UPSTREAM_AUTH_FAILED", "上游认证失败，请检查凭证与权限。")
    if response.status_code == 429:
        raise ProviderError("RATE_LIMITED", "上游限流，请稍后重试。", retryable=True)
    raise ProviderError("UPSTREAM_ERROR", f"上游返回错误（HTTP {response.status_code}）。")


async def iter_sse(response: httpx.Response) -> AsyncIterator[tuple[str | None, str]]:
    """按 SSE 规范产出 (event_name, data)；多行 data 以换行合并，event 缺省为 None。"""
    event_name: str | None = None
    data_lines: list[str] = []
    async for line in response.aiter_lines():
        if not line:
            if data_lines:
                yield event_name, "\n".join(data_lines)
            event_name = None
            data_lines = []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event_name = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].strip())
    if data_lines:
        yield event_name, "\n".join(data_lines)


@asynccontextmanager
async def open_stream(
    config: LLMConfig, url: str, headers: dict[str, str], body: dict[str, Any], transport: httpx.AsyncBaseTransport | None
) -> AsyncIterator[tuple[httpx.Response, AsyncIterator[tuple[str | None, str]]]]:
    """建立流式上游连接：仅在确认 HTTP 200 后产出响应与 SSE 行迭代器。

    生成器退出（含取消）时关闭 client 与连接，向上游传播取消。
    """
    timeout = httpx.Timeout(config.timeoutSeconds, read=STREAM_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False) as client:
            async with client.stream("POST", url, headers={**headers, "Accept": "text/event-stream", "Accept-Encoding": "identity"}, json=body) as response:
                await raise_for_stream_status(response)
                if "text/event-stream" not in response.headers.get("content-type", "").lower():
                    raise ProviderError("UPSTREAM_PROTOCOL_ERROR", "模型服务未返回 SSE 流，请检查所选协议与服务的流式支持。")
                async with aclosing(iter_sse(response)) as events:
                    yield response, events
    except httpx.TimeoutException as exc:
        raise ProviderError("UPSTREAM_TIMEOUT", "等待模型响应超时。", retryable=True) from exc
    except httpx.HTTPError as exc:
        raise ProviderError("UPSTREAM_UNREACHABLE", "模型连接中断，请检查服务地址与网络。", retryable=True) from exc


async def post_json(
    config: LLMConfig,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """发送请求并规范化错误；响应体不进入错误信息（只保留上游给用户的一句话摘要）。"""
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeoutSeconds), transport=transport
        ) as client:
            response = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        raise ProviderError(
            "UPSTREAM_TIMEOUT",
            f"上游请求超时（{config.timeoutSeconds:g} 秒）。",
            retryable=True,
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderError("UPSTREAM_UNREACHABLE", "无法连接到模型服务，请检查 Base URL 与网络。") from exc

    if response.status_code in (401, 403):
        raise ProviderError(
            "UPSTREAM_AUTH_FAILED",
            _sanitize_upstream_message(response, "上游返回认证失败，请检查 API Key。"),
            status_code=502,
        )
    if response.status_code == 429:
        raise ProviderError(
            "RATE_LIMITED",
            _sanitize_upstream_message(response, "上游限流，请稍后重试。"),
            retryable=True,
        )
    if response.status_code >= 400:
        raise ProviderError(
            "UPSTREAM_ERROR",
            _sanitize_upstream_message(response, f"上游返回错误（HTTP {response.status_code}）。"),
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise ProviderError("UPSTREAM_ERROR", "上游返回了无法解析的响应。") from exc
    if not isinstance(data, dict):
        raise ProviderError("UPSTREAM_ERROR", "上游返回了无法解析的响应。")
    return data


class LLMProvider(ABC):
    """统一入口：参数能力校验与凭证检查在基类完成，协议细节留在子类。

    transport 仅供测试注入 MockTransport，生产调用不传。
    流式约定：生成器首个产出恒为 start 事件；上游 HTTP 失败在任何产出之前抛 ProviderError，
    供端点转换为流开始前的 HTTP 错误。
    """

    supported_params: frozenset[str] = frozenset({"temperature", "top_p"})

    async def complete(
        self,
        config: LLMConfig,
        request: LLMRequest,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> LLMResponse:
        check_params(request, self.supported_params)
        require_api_key(config)
        return await self._complete(config, request, transport)

    async def stream(
        self,
        config: LLMConfig,
        request: LLMRequest,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> AsyncIterator[LLMStreamEvent]:
        check_params(request, self.supported_params)
        require_api_key(config)
        async with aclosing(self._stream(config, request, transport)) as delegate:
            async for event in delegate:
                yield event

    @abstractmethod
    async def _complete(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> LLMResponse:
        ...

    @abstractmethod
    def _stream(
        self,
        config: LLMConfig,
        request: LLMRequest,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> AsyncIterator[LLMStreamEvent]:
        ...
