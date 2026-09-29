"""详解：用用户所选聊天模型讲解，上下文预算与原文引用绑定。

对应 docs/PLAN.md §6.6/§6.7/§6.8：

- 详解走**普通聊天 SSE 语义**（message.start / text.delta / message.end / error），
  没有定位事件游标；断开或停止即关闭上游。
- 不复用定位的 600 秒缓存，不要求 Qdrant 在线，不要求旧 Embedding 模型仍安装：
  本模块只处理"已重建的证据 + 已冻结的模型句柄"。
- **证据送模型前先用同一清洗器**（B0 ``project_readable`` 的 ``readable.text``）：
  图片 Markdown 与图片地址不进模型，只保留正文、公式与表格；
  讲解也不整段复述教材原文（PLAN §3.5）。
- 预算顺序：① 超硬上限直接 ``CONTEXT_TOO_LARGE``（413）；② 从最旧开始整条丢弃历史；
  ③ 仍超限返回 ``CONTEXT_TOO_LARGE``。原题、当前追问与用户已选证据**不截断**。
- 上限沿用后端既有常量（``app.schemas.chat`` 的 200 条 / 单条 32,000 / 总 120,000 字符），
  不在这里硬编码第二套；字符估算与精确 token 计数分开，不假装是 token 计数。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

from app.core.exceptions import AppError
from app.providers.llm.base import (
    FINISH_STOP,
    FINISH_UNKNOWN,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMStreamEvent,
)
from app.schemas.chat import MAX_MESSAGE_CHARS, MAX_MESSAGES, MAX_TOTAL_CHARS
from app.services.model_runtime import (  # noqa: F401  (ChatModelHandle 由共享层定义)
    DEFAULT_CHAT_MAX_OUTPUT_TOKENS,
    ChatModelHandle,
)
from app.schemas.rag_v2 import RagExplainRequest, TextbookEvidence
from app.services.rag_v2.summary import readable_text

DEFAULT_CHAT_MAX_OUTPUT_TOKENS = 2048
#: 证据块按整条拆成多条 user 消息，单条不超过既有单条上限（不截断任何一条原文）。
EVIDENCE_MESSAGE_BUDGET = MAX_MESSAGE_CHARS

SYSTEM_INSTRUCTION = (
    "你是教材详解助手。只依据下方提供的教材原文证据讲解当前题目与追问，"
    "引用时标出对应的 evidenceId；原文没有依据的部分必须明说「证据不足」，不得编造教材出处，"
    "不得引入未提供的教材内容。不给出与教材依据无关的独立解题推导，"
    "也不要把教材原文整段复述成回答（保留必要公式与教学步骤即可）。"
    "如果问题依赖图片中的信息而文本证据无法提供，明确指出缺少图中条件，不要依据图片文件名猜测内容。"
)

FINISH_REASONS = frozenset({FINISH_STOP, "length", FINISH_UNKNOWN})


def _too_large(message: str) -> AppError:
    return AppError(message, code="CONTEXT_TOO_LARGE", status_code=413)


# `ChatModelHandle` 与「按 profileId 解析聊天模型」的唯一实现在共享的 model_runtime
# （RAG-QUALITY v1.1 · C0）：详解与题库 AI 整理共用，任何模块不得再定义第二份。


@dataclass(frozen=True)
class ExplainDelta:
    """上游增量：文字增量或结束原因；服务层据此产出 text.delta / message.end。"""

    type: str
    text: str = ""
    finishReason: str | None = None


@dataclass(frozen=True)
class ExplainBudget:
    """本轮的字符预算明细（字符，不是 token）。"""

    max_messages: int
    max_message_chars: int
    max_total_chars: int
    total_chars: int
    dropped_history: int
    message_count: int


class Explainer:
    """所选聊天模型的详解执行器；模型句柄由 ``model_provider_factory`` 在点击时冻结。"""

    def __init__(self, model_provider_factory=None, *, default_max_output_tokens: int = DEFAULT_CHAT_MAX_OUTPUT_TOKENS) -> None:
        self._factory = model_provider_factory
        self.default_max_output_tokens = int(default_max_output_tokens)

    # ------------------------------------------------------------------ 状态

    @property
    def configured(self) -> bool:
        return self._factory is not None

    def status(self) -> dict:
        return {
            "available": self.configured,
            "reason": None if self.configured else "详解模型工厂未装配，所选模型详解不可用。",
        }

    # ------------------------------------------------------------ 模型冻结

    def freeze_model(self, model_profile_id: str) -> ChatModelHandle:
        """在用户点击时解析并冻结模型；失败即失败，不偷偷换模型。"""
        if self._factory is None:
            raise AppError(
                "所选模型详解未装配，无法调用聊天模型。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        handle = self._factory(model_profile_id)
        if not isinstance(handle, ChatModelHandle):
            raise AppError(
                "详解模型句柄不合法，已停止详解。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
            )
        return handle

    # ------------------------------------------------------------------ 详解

    async def explain(
        self,
        body: RagExplainRequest,
        *,
        evidence: Sequence[TextbookEvidence],
        model: ChatModelHandle,
    ) -> AsyncIterator[ExplainDelta]:
        messages, _budget = build_explanation_request(body=body, evidence=evidence, model=model)
        request = LLMRequest(
            messages=messages,
            maxOutputTokens=body.maxOutputTokens or model.max_output_tokens,
            params={},
        )
        stream = model.provider.stream(model.config, request)
        try:
            async for event in stream:
                yield _delta(event)
        finally:
            # 断开 / 停止 / 异常都必须关闭上游连接（取消传播）。
            await stream.aclose()


def _delta(event: LLMStreamEvent) -> ExplainDelta:
    if event.type == "text" and event.text is not None:
        return ExplainDelta(type="text", text=event.text)
    if event.type == "end":
        return ExplainDelta(type="end", finishReason=normalize_finish(event.finishReason))
    return ExplainDelta(type="other")


def normalize_finish(reason: str | None) -> str:
    """上游结束原因只映射到 stop / length / unknown，未知值不伪装成 stop。"""
    return reason if reason in FINISH_REASONS else FINISH_UNKNOWN


def _message(role: str, content: str, *, label: str) -> LLMMessage:
    if len(content) > MAX_MESSAGE_CHARS:
        raise _too_large(
            f"{label}超过单条上下文上限 {MAX_MESSAGE_CHARS} 字符，"
            "请减少所选证据或改用更大上下文的模型。"
        )
    return LLMMessage(role=role, content=content)


def evidence_messages(evidence: Sequence[TextbookEvidence]) -> list[LLMMessage]:
    """把证据按整条装进多条 user 消息；任何一条都不被截断，且只用清洗文本。

    送模型的是 ``readable.text``（B0 清洗结果，无图片 Markdown/地址）；``readable`` 缺失的
    历史证据退回封存原文切片，绝不在这里再写一套清洗规则。
    """
    blocks = [
        f"[{item.evidenceId}] {item.title}"
        + (" → " + " → ".join(item.chapterPath) if item.chapterPath else "")
        + f"（第 {item.charStart}–{item.charEnd} 字符）\n{readable_text(item)}"
        for item in evidence
    ]
    messages: list[LLMMessage] = []
    current: list[str] = []
    size = 0
    for block in blocks:
        if len(block) > EVIDENCE_MESSAGE_BUDGET:
            raise _too_large(
                f"单条教材证据超过 {EVIDENCE_MESSAGE_BUDGET} 字符，"
                "请减少所选证据或改用更大上下文的模型。"
            )
        if current and size + len(block) + 2 > EVIDENCE_MESSAGE_BUDGET:
            messages.append(
                _message("user", "教材原文证据：\n\n" + "\n\n".join(current), label="教材原文证据")
            )
            current, size = [], 0
        current.append(block)
        size += len(block) + 2
    if current:
        messages.append(_message("user", "教材原文证据：\n\n" + "\n\n".join(current), label="教材原文证据"))
    return messages


def build_explanation_request(
    *,
    body: RagExplainRequest,
    evidence: Sequence[TextbookEvidence],
    model: ChatModelHandle,
) -> tuple[list[LLMMessage], ExplainBudget]:
    """组装详解请求：服务端规则 + 原题 + 当前追问 + 完整证据 + 可用历史。

    ① 固定部分（规则、原题、追问、证据）本身违反硬上限 → 直接 413；
    ② 从最旧开始整条丢弃历史消息，直到符合总字符上限；
    ③ 仍超限 → 413。原题、当前追问与证据不截断。
    """
    fixed = [
        _message("system", SYSTEM_INSTRUCTION, label="服务端规则"),
        _message("user", f"原题：\n{body.originalQuestion}", label="原题"),
        _message("user", f"当前追问：\n{body.followUp}", label="当前追问"),
        *evidence_messages(evidence),
    ]
    fixed_chars = sum(len(message.content) for message in fixed)
    if fixed_chars > MAX_TOTAL_CHARS:
        raise _too_large(
            "原题、当前追问与所选教材证据合计超出上下文上限，"
            "请减少所选证据或改用更大上下文的模型。"
        )
    history = [
        _message(item.role, item.content, label="历史消息") for item in body.history
    ]
    dropped = 0
    remaining = list(history)
    total = fixed_chars + sum(len(message.content) for message in remaining)
    while remaining and (total > MAX_TOTAL_CHARS or len(fixed) + len(remaining) > MAX_MESSAGES):
        removed = remaining.pop(0)
        total -= len(removed.content)
        dropped += 1
    if total > MAX_TOTAL_CHARS or len(fixed) + len(remaining) > MAX_MESSAGES:
        raise _too_large(
            "上下文超出限制且历史已全部丢弃，请减少所选证据或改用更大上下文的模型。"
        )
    messages = [*fixed, *remaining]
    budget = ExplainBudget(
        max_messages=MAX_MESSAGES,
        max_message_chars=MAX_MESSAGE_CHARS,
        max_total_chars=MAX_TOTAL_CHARS,
        total_chars=total,
        dropped_history=dropped,
        message_count=len(messages),
    )
    return messages, budget


__all__ = [
    "ChatModelHandle",
    "ExplainBudget",
    "ExplainDelta",
    "Explainer",
    "build_explanation_request",
    "evidence_messages",
    "normalize_finish",
]
