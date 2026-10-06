"""知识点概括测试台：**真实 provider + MockTransport 替身**，不发真实网络请求。

替换 2026-10-06 之前的"本机 Ollama 假 client"：概括现在走「全局默认云端档案」，
测试用与生产同一条 ``resolve_chat_model → provider.complete`` 路径，只把 HTTP 传输换掉。

用法::

    wire = SummaryWire(reply={"points": [...]})
    summarizer = wire.summarizer()
    outcome = summarizer.summarize(question="…", evidence=evidence)
    assert wire.requests[0][0].endswith("/chat/completions")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx2 as httpx

from app.providers.llm.anthropic_messages import AnthropicMessagesProvider
from app.providers.llm.base import LLMConfig
from app.providers.llm.openai_chat import OpenAIChatProvider
from app.providers.llm.openai_responses import OpenAIResponsesProvider
from app.schemas.model_config import ModelProtocol
from app.services.model_runtime import ChatModelHandle
from app.services.rag_v2.summary import KnowledgeSummarizer

DEFAULT_PROFILE_ID = "cloud-profile"
DEFAULT_MODEL_ID = "cloud-model"
#: 云端默认供应商（非 is_local），保证概括允许调用
DEFAULT_PROVIDER_ID = "deepseek"


@dataclass
class SummaryWire:
    """可脚本化的概括上游：记录每次请求，按配置返回。"""

    reply: object = None
    text: str | None = None
    #: 脚本化输出：按顺序消费（首次调用 + 一次修正各一条）；给出时忽略 ``reply`` / ``text``
    replies: list[object] | None = None
    finish: str = "stop"
    status_code: int = 200
    fail: Exception | None = None
    profile_id: str | None = DEFAULT_PROFILE_ID
    provider_id: str | None = DEFAULT_PROVIDER_ID
    model_id: str = DEFAULT_MODEL_ID
    #: 档案协议：概括按档案协议调用（openai_chat / openai_responses / anthropic_messages）
    protocol: str = "openai_chat"
    context_tokens: int | None = None
    max_output_tokens: int | None = 1024
    resolve_error: Exception | None = None
    #: 解析档案本身失败（档案被删/连接不可用）：概括必须转 503，而不是把问答拖成 500
    handle_error: Exception | None = None
    requests: list[tuple[str, dict]] = field(default_factory=list)

    # ------------------------------------------------------------------ 上游

    async def handler(self, request: httpx.Request) -> httpx.Response:
        """异步替身：AsyncClient 要求响应流是异步流（与生产同路径）。"""
        self.requests.append((request.url.path, json.loads(request.content)))
        if self.fail is not None:
            raise self.fail
        if self.status_code != 200:
            return httpx.Response(self.status_code, json={"error": "fixture upstream failure"})
        content = self.text
        if self.replies is not None:
            content = json.dumps(self.replies.pop(0), ensure_ascii=False)
        elif content is None:
            content = json.dumps(self.reply if self.reply is not None else {}, ensure_ascii=False)
        if self.protocol == "anthropic_messages":
            stop_reason = "max_tokens" if self.finish == "length" else "end_turn"
            return httpx.Response(200, json={
                "content": [{"type": "text", "text": content}],
                "stop_reason": stop_reason,
                "usage": {"input_tokens": 321, "output_tokens": 123},
            })
        if self.protocol == "openai_responses":
            return httpx.Response(200, json={
                "status": "incomplete" if self.finish == "length" else "completed",
                "incomplete_details": {"reason": "max_output_tokens"} if self.finish == "length" else None,
                "output_text": content,
                "usage": {"input_tokens": 321, "output_tokens": 123},
            })
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": self.finish}],
                                         "usage": {"prompt_tokens": 321, "completion_tokens": 123}})

    # ------------------------------------------------------------------ 装配

    def handle(self) -> ChatModelHandle:
        if self.handle_error is not None:
            raise self.handle_error
        provider = {
            "openai_chat": OpenAIChatProvider,
            "openai_responses": OpenAIResponsesProvider,
            "anthropic_messages": AnthropicMessagesProvider,
        }[self.protocol]()
        original = provider.complete

        async def complete(config, request):  # noqa: ANN001 - 与 provider 签名一致
            return await original(config, request, transport=httpx.MockTransport(self.handler))

        provider.complete = complete  # type: ignore[method-assign]
        return ChatModelHandle(
            self.profile_id or DEFAULT_PROFILE_ID,
            self.model_id,
            provider,
            LLMConfig(protocol=ModelProtocol[self.protocol], baseUrl="http://127.0.0.1:9",
                      modelId=self.model_id, apiKey="fixture-key", providerId=self.provider_id),
            self.max_output_tokens if self.max_output_tokens is not None else 1024,
            self.context_tokens,
        )

    def summarizer(self, **kwargs) -> KnowledgeSummarizer:
        def default_profile() -> str | None:
            if self.resolve_error is not None:
                raise self.resolve_error
            return self.profile_id

        return KnowledgeSummarizer(resolve_default_profile=default_profile,
                                   resolve_handle=lambda _profile_id: self.handle(), **kwargs)


def make_summarizer(reply: object = None, **kwargs) -> tuple[KnowledgeSummarizer, SummaryWire]:
    """兼容旧测试的入口：返回 ``(summarizer, wire)``；``wire.requests`` 仍是 ``(path, body)``。"""
    wire = SummaryWire(reply=reply, **kwargs)
    return wire.summarizer(), wire
