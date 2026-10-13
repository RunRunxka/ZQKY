"""LangChain 结构化输出 / 文本生成运行器（R0-C）。

硬性纪律（用户裁定：全部教学闭环 LLM 能力必须经 LangChain + LangGraph 实现）：

- 业务代码**不直连供应商 SDK**（openai/anthropic 等）；模型统一由
  ``model_runtime`` 解析出 LangChain 模型后传入本层（门禁测试见
  ``tests/test_no_raw_sdk_imports.py``）。
- 抽取/分类/生成一律 ``with_structured_output`` + Pydantic 严格校验；解析失败自动
  重试（默认共 2 次尝试，第二次附带纠正提示），仍失败**不抛异常**，返回带错误说明的
  outcome —— 由调用方按「候选 + 标注」进入待确认（红线：AI 输出只进候选）。
- 传输/超时类错误同样降级为 outcome；调用方若需要区分可检查 ``error`` 文本。
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from app.services.llm.prompts import PromptSpec

__all__ = [
    "StructuredMethod",
    "StructuredOutcome",
    "TextOutcome",
    "run_structured",
    "run_text",
]

TModel = TypeVar("TModel", bound=BaseModel)

#: LangChain ``with_structured_output`` 的方法透传（None = 供应商默认）。
StructuredMethod = Literal["function_calling", "json_mode", "json_schema"]

_RETRY_NOTE = (
    "上一次输出无法解析为所需结构。请仅输出符合约定 schema 的内容，"
    "不要附加解释、前后缀或 Markdown 代码围栏。"
)


@dataclass(frozen=True)
class StructuredOutcome(Generic[TModel]):
    """结构化调用结果；``parsed`` 为 None 表示失败（携带原因与最后原文）。

    ``structured_method`` 记录实际生效的结构化输出模式（``None`` = 供应商默认；
    ``"json_mode"`` 表示按下面的降级路径把 ``response_format`` 换成了 ``json_object``）。
    """

    parsed: TModel | None
    raw_text: str
    attempts: int
    error: str | None = None
    structured_method: StructuredMethod | None = None

    @property
    def ok(self) -> bool:
        return self.parsed is not None


@dataclass(frozen=True)
class TextOutcome:
    """文本调用结果；``ok`` 为 False 时 ``error`` 说明原因。"""

    text: str
    attempts: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text)


def _raw_preview(raw: Any) -> str:
    if raw is None:
        return ""
    content = getattr(raw, "content", raw)
    if isinstance(content, str):
        return content
    return str(content)


async def _invoke(runnable: Any, messages: list[BaseMessage], *, timeout_s: float | None, config: RunnableConfig | None) -> Any:
    if timeout_s is not None:
        return await asyncio.wait_for(runnable.ainvoke(messages, config=config), timeout=timeout_s)
    return await runnable.ainvoke(messages, config=config)


#: 供应商"不接受这种结构化输出模式"的特征（DeepSeek 对 ``json_schema`` 返回
#: 400 ``This response_format type is unavailable now``）。只在**未显式指定 method** 时
#: 触发一次降级，避免把内容类错误误判成兼容性问题。
_MODE_REJECTION_MARKERS = ("response_format", "json_schema")
_MODE_REJECTION_TOKENS = (
    "unavailable",
    "unsupported",
    "not support",
    "does not support",
    "invalid_request_error",
    "invalid request",
)


def _structured_mode_rejected(error: str | None) -> bool:
    """判断调用失败是不是"供应商不支持该结构化输出模式"（可安全降级重发）。"""
    lowered = (error or "").lower()
    if not any(marker in lowered for marker in _MODE_REJECTION_MARKERS):
        return False
    return any(token in lowered for token in _MODE_REJECTION_TOKENS)


async def run_structured(
    chat_model: BaseChatModel,
    *,
    prompt: PromptSpec,
    schema: type[TModel],
    variables: Mapping[str, object] | None = None,
    max_attempts: int = 2,
    timeout_s: float | None = None,
    method: StructuredMethod | None = None,
    config: RunnableConfig | None = None,
) -> StructuredOutcome[TModel]:
    """按提示词调用模型并解析为 ``schema``；失败重试后优雅降级，不抛解析异常。

    ``max_attempts`` 含首次尝试（默认 2 = 首次 + 1 次重试）；重试时在消息尾部追加
    一条简短纠正提示（不改动原提示词内容）。

    **结构化模式降级（2026-10-13）**：LangChain 对 OpenAI 兼容端点默认走
    ``json_schema``（``response_format={"type":"json_schema"}``），但部分供应商
    （如 DeepSeek）会直接回 400 ``This response_format type is unavailable now``；
    此前该 400 被当作未知异常落到任务级 ``JOB_FAILED``（题库 AI 整理/知识点候选等
    全部不可用）。现在：未显式指定 ``method`` 且识别到该拒绝时，**同一次尝试内**
    退到 ``json_mode``（``response_format={"type":"json_object"}``）重发一次
    （只降级一次，不做无限换模式；提示词本就要求"只输出 JSON"，故兼容）。
    """
    if max_attempts < 1:
        raise ValueError("max_attempts 至少为 1")
    messages = prompt.messages(variables)
    kwargs: dict[str, Any] = {"include_raw": True}
    if method is not None:
        kwargs["method"] = method
    method_used: StructuredMethod | None = method
    structured = chat_model.with_structured_output(schema, **kwargs)
    mode_fallback_done = False

    async def _call_once(current: list[BaseMessage]) -> tuple[Any, str | None]:
        """一次结构化调用；供应商拒绝该模式时同次尝试内降级重发一次。"""
        nonlocal structured, method_used, mode_fallback_done
        try:
            return await _invoke(structured, current, timeout_s=timeout_s, config=config), None
        except Exception as exc:  # noqa: BLE001 - 统一降级为 outcome，不抛解析异常
            error = f"{type(exc).__name__}: {exc}"
            if method is None and not mode_fallback_done and _structured_mode_rejected(error):
                mode_fallback_done = True
                method_used = "json_mode"
                kwargs["method"] = "json_mode"
                structured = chat_model.with_structured_output(schema, **kwargs)
                try:
                    return (
                        await _invoke(structured, current, timeout_s=timeout_s, config=config),
                        None,
                    )
                except Exception as fallback_exc:  # noqa: BLE001
                    return None, f"{type(fallback_exc).__name__}: {fallback_exc}"
            return None, error

    last_raw = ""
    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        current = messages if attempt == 1 else [*messages, HumanMessage(content=_RETRY_NOTE)]
        result, error = await _call_once(current)
        if error is not None:
            last_error = error
            continue
        parsed = result.get("parsed") if isinstance(result, dict) else result
        raw = result.get("raw") if isinstance(result, dict) else None
        parsing_error = result.get("parsing_error") if isinstance(result, dict) else None
        last_raw = _raw_preview(raw)
        if isinstance(parsed, schema):
            return StructuredOutcome(
                parsed=parsed,
                raw_text=last_raw,
                attempts=attempt,
                structured_method=method_used,
            )
        last_error = (
            f"结构化解析失败：{parsing_error}"
            if parsing_error is not None
            else "结构化解析失败：模型未返回可解析结构"
        )
    return StructuredOutcome(
        parsed=None,
        raw_text=last_raw,
        attempts=max_attempts,
        error=last_error,
        structured_method=method_used,
    )


async def run_text(
    chat_model: BaseChatModel,
    *,
    prompt: PromptSpec,
    variables: Mapping[str, object] | None = None,
    max_attempts: int = 2,
    timeout_s: float | None = None,
    config: RunnableConfig | None = None,
) -> TextOutcome:
    """纯文本生成；空文本视作失败，重试后优雅降级。"""
    if max_attempts < 1:
        raise ValueError("max_attempts 至少为 1")
    messages = prompt.messages(variables)

    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        current = messages if attempt == 1 else [*messages, HumanMessage(content=_RETRY_NOTE)]
        try:
            result = await _invoke(chat_model, current, timeout_s=timeout_s, config=config)
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            continue
        text = _raw_preview(result).strip()
        if text:
            return TextOutcome(text=text, attempts=attempt)
        last_error = "模型返回空文本"
    return TextOutcome(text="", attempts=max_attempts, error=last_error)
