"""题库测试共用替身（R4 LangChain 改造配套；与 ``tests/papers_support.py`` 同一口径）。

R4-BE 改造：题库 AI（整理/补题）统一走 LangChain（``resolve_agent_chat_model`` +
``services.llm.runner.run_structured``），替身也按 LangChain 形状提供：

- ``FakeLangChainModel``：``with_structured_output`` 形状替身（不触网）；handler/replies
  语义与归档 ``FakeLLMProvider`` 一致（字符串 / 异常 / ``None``）；截断用半截 JSON
  表示（``looks_truncated`` 判为 ``*_OUTPUT_TRUNCATED``，与 R5 papers 的
  ``TRUNCATED_REPLY`` 同一适配口径）；
- ``make_handle``：构造 ``AgentModelHandle``（生产句柄形状）；``provider_id`` 参数
  保留归档云端闸门用例（ollama → 422 ``QUESTION_MODEL_NOT_CLOUD``）；
- ``FakeResolver``：``(profileId) -> 句柄`` 替身（可换映射、可抛错、记录调用与线程）。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from app.core.exceptions import AppError
from app.services.agent.model import AgentModelHandle
from app.services.model_runtime import model_fingerprint

LOCAL_PROFILE = "chat-model-local"
CLOUD_PROFILE = "chat-model-cloud"
FAKE_API_KEY = "sk-test-should-never-be-persisted"


@dataclass
class ProviderCall:
    """一次结构化调用的可断言摘要（含所在线程，用于验证「不在事件循环线程跑 SQL」）。

    归档 ``ProviderCall`` 的字段保留；R4 LangChain 路径下 ``max_output_tokens`` 是
    句柄构造值（不再有按调用下发），``messages`` 是渲染后的 LangChain 消息。
    """

    index: int
    input_text: str
    max_output_tokens: int | None
    model_profile_id: str | None
    model_id: str
    thread_id: int
    messages: list[Any] = field(default_factory=list)


class FakeLLMProvider:
    """模型替身：LangChain ``with_structured_output`` 形状（不触网；R4 题库配套）。

    handler/replies 语义与归档完全一致（字符串 / 异常 / ``None``），但 ``handler(call)``
    收到的仍是 ``ProviderCall``（老用例读 ``call.input_text``/``call.index`` 不断言签名）。
    截断用半截 JSON 表示（``structured.looks_truncated`` 判为 ``*_OUTPUT_TRUNCATED``）。
    """

    def __init__(
        self, replies: Sequence[Any] | None = None, handler: Callable[[ProviderCall], Any] | None = None
    ) -> None:
        self.replies = list(replies or [])
        self.handler = handler
        self.calls: list[ProviderCall] = []

    # ---- LangChain 形状 ---------------------------------------------------

    def with_structured_output(self, schema: Any, *, include_raw: bool = False, **kwargs: Any):  # noqa: ANN001, ANN202
        return _FakeStructuredRunnable(self, schema)

    def bind_tools(self, _tools: Any, **_kwargs: Any) -> "FakeLLMProvider":  # noqa: ANN001, ANN202
        return self

    # ---- 取值（runnable 回调）----------------------------------------------

    def _take(self, call: ProviderCall) -> Any:
        if self.handler is not None:
            return self.handler(call)
        if self.replies:
            return self.replies.pop(0)
        # 默认回复 = 本批块 id 组成的合法整理 JSON（归档 FakeProvider 语义）；
        # organize_reply 定义在 tests.test_question_bank（题库测试公共样本），延迟导入。
        from tests.test_question_bank import block_ids_of, organize_reply

        return organize_reply(block_ids_of(call.input_text))


class _FakeStructuredRunnable:
    def __init__(self, model: Any, schema: Any) -> None:
        self._model = model
        self._schema = schema

    async def ainvoke(self, messages: Any, config: Any = None) -> Any:  # noqa: ANN001, ARG002
        from langchain_core.messages import AIMessage

        prompt_messages = list(messages)
        prompt_text = "\n".join(str(getattr(m, "content", m)) for m in prompt_messages)
        provider = self._model
        call = ProviderCall(
            index=len(provider.calls),
            input_text=prompt_messages[-1].content if prompt_messages else "",
            max_output_tokens=getattr(provider, "max_output_tokens", None),
            model_profile_id=getattr(provider, "model_profile_id", None),
            model_id=getattr(provider, "model_id", None) or "",
            thread_id=threading.get_ident(),
            messages=prompt_messages,
        )
        provider.calls.append(call)
        value = provider._take(call)
        if value is None:
            value = "{}"
        if isinstance(value, BaseException):
            raise value
        # include_raw=True 的真实链路：模型原始输出 → 解析器。真实 LangChain 的
        # 解析失败经 fallback 变成 ``parsing_error``（**不抛异常**、raw 保留），
        # 这里对齐同一行为：parsed=None + parsing_error=异常，由 ``run_structured``
        # 记为「结构化解析失败」（outcome.raw_text 保留原始输出）。
        import json as _json

        parsing_error: BaseException | None = None
        parsed: Any = None
        try:
            parsed = _json.loads(value) if isinstance(value, str) else value
            parsed = self._schema.model_validate(parsed)
        except Exception as exc:  # noqa: BLE001 - 真实链路解析失败也是这样降级的
            parsing_error = exc
            parsed = None
        return {
            "raw": AIMessage(content=value if isinstance(value, str) else str(value)),
            "parsed": parsed,
            "parsing_error": parsing_error,
        }


@dataclass(frozen=True)
class StubAgentHandle(AgentModelHandle):
    """测试句柄：在 ``AgentModelHandle`` 上补 ``provider_id`` / 替身绑定字段。

    仅用于**云端闸门**用例（``provider_id="ollama"`` → 422 ``QUESTION_MODEL_NOT_CLOUD``）
    与调用记录（``model_profile_id``/``model_id`` 供替身断言）；生产路径的闸门判定按
    profileId 回查模型仓储连接（见 ``service._provider_is_local``）。
    """

    provider_id: str | None = None
    provider: Any = None
    model_profile_id: str | None = None


def make_handle(
    profile_id: str = LOCAL_PROFILE,
    *,
    model_id: str = "qwen2.5:7b",
    base_url: str = "http://127.0.0.1:11434/v1",
    max_output_tokens: int = 2048,
    provider: Any | None = None,
    api_key: str | None = FAKE_API_KEY,
    provider_id: str | None = None,
) -> StubAgentHandle:
    """构造测试用 ``AgentModelHandle``（LangChain 形状；``chat_model`` 用替身）。

    ``api_key`` 形参保留归档签名（LangChain 路径凭证只在生产解析器里显式注入，替身
    不消费）；``provider_id`` 保留归档语义：设为 ``ollama`` 等本机供应商时，生产判定
    ``find_provider(providerId).is_local`` 会拒绝该句柄；缺省 ``None`` 模拟
    "未识别供应商"的替身句柄（闸门不假设本机，放行）。
    """
    del api_key
    chat_model = provider if provider is not None else FakeLLMProvider()
    # 替身记录模型身份（ProviderCall 断言用）；生产路径没有这层绑定
    chat_model.model_profile_id = profile_id
    chat_model.model_id = model_id
    chat_model.max_output_tokens = max_output_tokens
    return StubAgentHandle(
        profile_id=profile_id,
        model_id=model_id,
        chat_model=chat_model,
        max_output_tokens=max_output_tokens,
        fingerprint=model_fingerprint(
            model_id=model_id,
            protocol="openai_chat",
            base_url=base_url,
            api_format="openai_chat",
        ),
        provider_id=provider_id,
    )


class FakeClock:
    """可注入的任务钟：秒精度 UTC ISO-8601（与 ``now_iso`` 同格式，可排序比较）。

    归档 ``tests.test_jobs_engine.FakeClock`` 的同构副本（该文件未随骨架回归；
    题库租约/恢复用例需要受控时钟）。
    """

    def __init__(self, start: str = "2026-09-30T00:00:00Z") -> None:
        from datetime import UTC, datetime

        self.moment = datetime.fromisoformat(start).astimezone(UTC)
        self._UTC = UTC

    def now(self) -> str:
        return (
            self.moment.astimezone(self._UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def advance(self, seconds: int) -> None:
        from datetime import timedelta

        self.moment = self.moment + timedelta(seconds=seconds)


class FakeResolver:
    """``(profileId) -> 模型句柄`` 替身：可换映射、可抛错、记录调用参数与线程。"""

    def __init__(
        self,
        profiles: dict[str, Any] | None = None,
        *,
        default: Any = None,
        error: BaseException | None = None,
    ) -> None:
        self.profiles = dict(profiles or {})
        self.default = default
        self.error = error
        self.calls: list[str] = []
        self.thread_ids: list[int] = []

    def __call__(self, profile_id: str) -> Any:
        self.calls.append(profile_id)
        self.thread_ids.append(threading.get_ident())
        if self.error is not None:
            raise self.error
        handle = self.profiles.get(profile_id) or self.default
        if handle is None:
            raise AppError("模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404)
        return handle
