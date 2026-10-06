"""知识点首答：用**全局默认云端模型**结构化概括，只引用**实际进入提示词**的教材原文。

RAG-QUALITY v1.1 修复（PLAN §3.4）+ 2026-10-06 模型口径调整：

- 概括模型**只取设置里的「全局默认问答模型」**（``defaultChatProfileId``），经
  ``resolve_chat_model`` 冻结成 ``ChatModelHandle`` 后按档案协议调用（openai-chat /
  openai-responses / anthropic-messages 均可）。**本机部署（Ollama/vLLM/LM Studio）
  不参与概括**：默认档案是本机或未配置默认档案时，状态明确不可用并给出原因，不静默回退本地。
- ``PromptPack`` 返回**真实准入集合**：``admitted_evidence_ids`` / ``admitted_evidence`` /
  ``skipped_evidence_ids``。打包按 ``EVIDENCE_PROMPT_MAX_CHARS``（预算唯一事实来源）与档案
  ``contextTokens``/输出上限估算出的字符预算中**较小者**；整条装入、绝不截断单条原文，
  装入文本用清洗后的 ``readable.text``（不把图片地址送进模型）。
- **引用校验只用 admitted 集合**：某个点的 ``evidenceIds`` 不是 admitted 子集 → **整个点拒绝**
  （不删非法 ID 后继续使用可能依赖它的内容）；伪造 ID、空引用、超 2 条引用、单点超 90 码点、
  含图片 Markdown 同样整点拒绝。
- 首答长度约束全部从 ``app.core.rag_budget`` 读：≤3 点 / 单点 ≤90 / 合计 ≤250 码点 / 每点 ≤2 引用。
- 模型输出超长、重复或格式错误 → **最多修正一次**（``SUMMARY_MAX_CORRECTIONS``，模型调用总数 ≤2）；
  修正后仍不合法时保留**完整且能装入预算**的点（不截断单点）→ ``SUMMARY_PARTIAL``；
  连一个完整点都没有 → ``SUMMARY_INVALID``。
- 输出预算取档案 ``maxOutputTokens``（未声明用聊天默认值），并夹在
  ``[OUTPUT_TOKEN_MIN, OUTPUT_TOKEN_MAX]``；``usage`` 计数只作**诊断字段**。
- 失败分类分级：上游不可用（未配置云端默认模型 / 默认档案是本机 / 连接失败 / 非 200）抛
  503 ``RAG_SUMMARY_UNAVAILABLE``；非法 JSON、结构不符、引用校验不过、超时、上游截断一律返回
  ``partial`` 语义并保留证据，措辞彼此可区分。**绝不悄悄降级成 no_evidence、绝不编造讲解。**
- ``status()`` / ``probe()`` 是**配置级检查**（解析默认档案 + 判定云端），不向云端发起真实推理
  调用；因此「探测通过」只表示配置就绪，不代表上游凭证/额度已实测。
- ``reason`` 只含固定措辞、计数与预算数字，不回显题目全文或原文内容。

测试注入替身（含假 handle/假 provider）即可覆盖全部分支；真实模型验收见结果卡「验证」小节。
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Protocol

from app.core.exceptions import AppError
from app.core.rag_budget import (
    EVIDENCE_PROMPT_MAX_CHARS,
    SUMMARY_MAX_CORRECTIONS,
    SUMMARY_MAX_POINT_CHARS,
    SUMMARY_MAX_POINTS,
    SUMMARY_MAX_REFS_PER_POINT,
    SUMMARY_MAX_TOTAL_CHARS,
)
from app.providers.llm.base import FINISH_LENGTH, LLMMessage, LLMRequest, LLMResponse, ProviderError
from app.providers.llm.registry import find_provider
from app.schemas.rag_v2 import RagPoint, TextbookEvidence
from app.services.model_runtime import ChatModelHandle

#: 未声明上下文窗口时的保守估算（与既有实现一致）；实际窗口以档案 contextTokens 为准。
DEFAULT_CONTEXT_TOKENS = 8192
DEFAULT_TIMEOUT_SECONDS = 300.0
#: 输出侧有界（PLAN §3.4 默认 1024）：生成预留同时决定提示词 token 预算。
DEFAULT_OUTPUT_TOKENS = 1024
OUTPUT_TOKEN_MIN = 256
OUTPUT_TOKEN_MAX = 2048
#: 保守字符估算（仓库既有口径）：1 token ≈ 2 字符。**这是估算，不是精确 token 计数。**
CHARS_PER_TOKEN = 2
#: 预算预留：聊天模板与结构开销。
RESERVED_TOKENS = 512
#: 安全余量：中文实际约 1.2–1.7 字符/token，字符口径会低估 token 数，故再打折扣。
PROMPT_SAFETY_MARGIN = 0.7

# ------------------------------------------------------------------ 违规码（内部）
#: 结构不合法（不是 JSON 对象 / 缺 points 数组 / points 为空）
VIOLATION_STRUCTURE = "STRUCTURE"
VIOLATION_POINT_EMPTY = "POINT_EMPTY"
VIOLATION_POINT_TOO_LONG = "POINT_TOO_LONG"
VIOLATION_POINT_LIMIT = "POINT_LIMIT"
VIOLATION_TOTAL_TOO_LONG = "TOTAL_TOO_LONG"
VIOLATION_REF_EMPTY = "REF_EMPTY"
VIOLATION_REF_NOT_ADMITTED = "REF_NOT_ADMITTED"
VIOLATION_REF_LIMIT = "REF_LIMIT"
VIOLATION_DUPLICATE = "DUPLICATE_POINT"
VIOLATION_IMAGE_TEXT = "IMAGE_TEXT"

VIOLATION_LABELS = {
    VIOLATION_STRUCTURE: "输出结构不符合要求",
    VIOLATION_POINT_EMPTY: "标题或说明为空",
    VIOLATION_POINT_TOO_LONG: f"单点超过 {SUMMARY_MAX_POINT_CHARS} 码点",
    VIOLATION_POINT_LIMIT: f"知识点超过 {SUMMARY_MAX_POINTS} 条",
    VIOLATION_TOTAL_TOO_LONG: f"知识点合计超过 {SUMMARY_MAX_TOTAL_CHARS} 码点",
    VIOLATION_REF_EMPTY: "没有引用教材原文",
    VIOLATION_REF_NOT_ADMITTED: "引用了未进入提示词的证据",
    VIOLATION_REF_LIMIT: f"单点引用超过 {SUMMARY_MAX_REFS_PER_POINT} 条",
    VIOLATION_DUPLICATE: "知识点重复",
    VIOLATION_IMAGE_TEXT: "输出包含图片标记",
}

INSTRUCTION = (
    "你是教材知识点整理助手，只做教材原文的知识点概括。\n"
    "只概括与题目有关的教材知识点、适用条件和原文依据；每条知识点必须引用下方提供的 "
    "evidenceId（从上方原文的 [ev-…] 标记里原样复制至少一个，不得自造、不得留空）；"
    f"最多 {SUMMARY_MAX_POINTS} 条，单点标题与说明合计不超过 {SUMMARY_MAX_POINT_CHARS} 字，"
    f"全部知识点合计不超过 {SUMMARY_MAX_TOTAL_CHARS} 字，每条最多引用 {SUMMARY_MAX_REFS_PER_POINT} 个 evidenceId；"
    "不输出图片 Markdown，不提供完整解题推导，不编造教材出处，不引入未提供的教材内容。\n"
    "只输出 JSON（不要任何额外字段、不要解释文字），结构固定为："
    '{"points":[{"title":"知识点标题","summary":"教材原文要点","evidenceIds":["原样复制的 ev-id"]}]}'
)

#: 用户提示头部与尾部（尾部重复一遍输出要求，即使上游截断开头也仍能看到）
PROMPT_HEADER = (
    "题目：{question}\n\n"
    "教材原文（只可引用下列 evidenceId；未列出的内容一律不得引用）："
)
PROMPT_FOOTER = (
    '只输出 JSON（不要额外字段）：{"points":[{"title":"知识点标题","summary":"教材原文要点",'
    '"evidenceIds":["原样复制上面出现过的 ev-id，至少一个"]}]}'
)


class Summarizer(Protocol):
    """会话层依赖的概括端口；测试注入替身，真实实现见 ``KnowledgeSummarizer``。"""

    def summarize(
        self, *, question: str, evidence: Sequence[TextbookEvidence]
    ) -> "SummaryOutcome": ...

    def status(self) -> dict: ...


@dataclass(frozen=True)
class SummaryOutcome:
    """一次概括的结果：``points`` 为空即"概括未完成"，证据由调用方原样保留。

    v1.1 诊断字段（不回显题目或原文内容，只放计数与预算数字）：

    - ``reason_code``：``SUMMARY_INVALID``（无可用知识点）或 ``SUMMARY_PARTIAL``（保留了部分完整知识点）；
      成功时为 ``None``（与 ``RagResultV2.reasonCode`` 的 ``ok`` 语义一致）；
    - ``admitted_evidence_ids`` / ``skipped_evidence_ids``：**真实准入集合**（进入提示词的证据 id
      与被预算排除的 id）；``used_evidence``/``total_evidence``/``skipped_evidence`` 是同一事实的计数；
    - ``corrected`` / ``violation_codes``：修正次数与最后一次的违规码（模型调用总数 ≤ 1+修正次数）；
    - ``prompt_eval_count``/``eval_count``：上游报告的提示词与生成 token 数（**诊断信号**，见模块说明）；
    - ``elapsed_seconds``：本次概括实际耗时（含修正）；
    - ``truncated``：上游窗口把提示词截断时为 True（此时不采用该输出）。
    """

    points: list[RagPoint] = field(default_factory=list)
    reason: str | None = None
    reason_code: str | None = None
    dropped: int = 0
    used_evidence: int = 0
    total_evidence: int = 0
    skipped_evidence: int = 0
    admitted_evidence_ids: frozenset[str] | None = None
    skipped_evidence_ids: tuple[str, ...] = ()
    corrected: int = 0
    violation_codes: tuple[str, ...] = ()
    prompt_eval_count: int | None = None
    eval_count: int | None = None
    elapsed_seconds: float | None = None
    truncated: bool = False


@dataclass(frozen=True)
class PromptPack:
    """按预算整条装配后的提示词与**真实准入集合**。

    ``admitted_evidence`` / ``admitted_evidence_ids`` 是实际出现在 ``prompt`` 里的证据；
    引用校验只能用这个集合（PLAN §3.4）。``skipped_evidence_ids`` 是被预算排除的证据。
    """

    prompt: str
    chars: int
    budget_chars: int
    used_evidence: int
    total_evidence: int
    skipped_evidence: int
    fits: bool
    admitted_evidence_ids: frozenset[str] = frozenset()
    admitted_evidence: tuple[TextbookEvidence, ...] = ()
    skipped_evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckedProposal:
    """引用与长度校验结果：``valid`` 为假时按 ``violation_codes`` 决定是否修正。"""

    points: tuple[RagPoint, ...] = ()
    dropped: int = 0
    violation_codes: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.violation_codes


@dataclass(frozen=True)
class _Proposal:
    """模型返回的可用性：``ok=False`` 表示概括未完成（非法 JSON / 超时）。"""

    ok: bool
    payload: object = None
    reason: str | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None
    truncated: bool = False


def unavailable(message: str) -> AppError:
    return AppError(message, code="RAG_SUMMARY_UNAVAILABLE", status_code=503, retryable=True)


def prompt_token_budget(context_tokens: int = DEFAULT_CONTEXT_TOKENS, output_tokens: int = DEFAULT_OUTPUT_TOKENS) -> int:
    """提示词可用 token 预算（估算）：窗口 − 生成预留 − 模板预留。"""
    return max(0, int(context_tokens) - int(output_tokens) - RESERVED_TOKENS)


def prompt_char_budget(context_tokens: int = DEFAULT_CONTEXT_TOKENS, output_tokens: int = DEFAULT_OUTPUT_TOKENS) -> int:
    """提示词字符硬上限：保守估算（1 token ≈ 2 字符）× 安全余量。

    这是字符口径的上限，用于打包与"发送前自检"；真实 token 数由上游 usage 交叉验证
    （**诊断信号**，不写成"证明绝未截断"）。
    """
    return int(prompt_token_budget(context_tokens, output_tokens) * CHARS_PER_TOKEN * PROMPT_SAFETY_MARGIN)


def evidence_block(item: TextbookEvidence) -> str:
    """一条证据的提示词文本：**用清洗后的可读文本**（不把图片地址送进模型）。"""
    location = " → ".join([item.title, *item.chapterPath]) if item.chapterPath else item.title
    return f"[{item.evidenceId}] {location}\n{readable_text(item)}"


def readable_text(item: TextbookEvidence) -> str:
    """入模/展示用的清洗文本；``readable`` 缺失（历史证据）时退回封存原文切片。"""
    readable = getattr(item, "readable", None)
    text = getattr(readable, "text", None)
    return text if isinstance(text, str) and text else item.text


def pack_evidence(
    *,
    question: str,
    evidence: Sequence[TextbookEvidence],
    budget_chars: int,
) -> PromptPack:
    """按证据顺序整条装入提示词，直到接近预算；装不下的整条丢弃，绝不截断单条原文。

    返回的 ``fits`` 为 False 表示连一条证据都装不下（调用方必须据此跳过请求）。
    """
    header = PROMPT_HEADER.format(question=question)
    fixed_chars = len(header) + len(PROMPT_FOOTER) + 4  # 两处分隔
    if fixed_chars > budget_chars:
        return PromptPack(
            prompt="",
            chars=0,
            budget_chars=budget_chars,
            used_evidence=0,
            total_evidence=len(evidence),
            skipped_evidence=len(evidence),
            fits=False,
            skipped_evidence_ids=tuple(item.evidenceId for item in evidence),
        )
    used: list[str] = []
    admitted: list[TextbookEvidence] = []
    skipped_ids: list[str] = []
    size = fixed_chars
    for item in evidence:
        block = evidence_block(item)
        cost = len(block) + 2
        if size + cost > budget_chars:
            skipped_ids.append(item.evidenceId)
            continue
        used.append(block)
        admitted.append(item)
        size += cost
    if not used:
        return PromptPack(
            prompt="",
            chars=0,
            budget_chars=budget_chars,
            used_evidence=0,
            total_evidence=len(evidence),
            skipped_evidence=len(evidence),
            fits=False,
            skipped_evidence_ids=tuple(item.evidenceId for item in evidence),
        )
    prompt = "\n\n".join([header, *used, PROMPT_FOOTER])
    if len(prompt) > budget_chars:  # pragma: no cover - 防御性：打包逻辑与预算必须自洽
        raise unavailable("知识点概括提示词打包超出预算，已停止概括并保留原文。")
    admitted_ids = frozenset(item.evidenceId for item in admitted)
    return PromptPack(
        prompt=prompt,
        chars=len(prompt),
        budget_chars=budget_chars,
        used_evidence=len(used),
        total_evidence=len(evidence),
        skipped_evidence=len(skipped_ids),
        fits=True,
        admitted_evidence_ids=admitted_ids,
        admitted_evidence=tuple(admitted),
        skipped_evidence_ids=tuple(skipped_ids),
    )


def structure_state(payload: object) -> str:
    """模型输出的结构分级：``ok`` / ``not_object`` / ``no_points`` / ``empty_points``。"""
    if not isinstance(payload, dict):
        return "not_object"
    raw_points = payload.get("points")
    if not isinstance(raw_points, list):
        return "no_points"
    if not raw_points:
        return "empty_points"
    return "ok"


def coverage_note(pack: PromptPack) -> str:
    """本次覆盖条数说明；只在 partial 的 reason 里出现。"""
    if pack.skipped_evidence <= 0:
        return ""
    return f"（本次仅使用 {pack.used_evidence}/{pack.total_evidence} 条证据）"


def _with_coverage(reason: str, pack: PromptPack) -> str:
    return reason + coverage_note(pack)


def _invalid_reason(checked: CheckedProposal, *, structure: str) -> str:
    """不可用输出的可读原因：结构 / 引用 / 长度分类措辞彼此可区分（不回显题目或原文）。"""
    codes = set(checked.violation_codes)
    if VIOLATION_STRUCTURE in codes:
        wording = {
            "not_object": "知识点概括返回结构不符合要求（不是 JSON 对象）",
            "no_points": "知识点概括返回结构不符合要求（缺少 points 数组）",
            "empty_points": "知识点概括未给出知识点（points 为空）",
        }.get(structure, "知识点概括返回结构不符合要求")
        return wording + "，保留教材原文供核对。"
    if codes & {VIOLATION_REF_EMPTY, VIOLATION_REF_NOT_ADMITTED, VIOLATION_REF_LIMIT}:
        return "知识点未通过原文引用校验，保留教材原文供核对。"
    if codes & {VIOLATION_POINT_TOO_LONG, VIOLATION_TOTAL_TOO_LONG, VIOLATION_POINT_LIMIT}:
        return (
            f"知识点超出首答长度预算（单点 {SUMMARY_MAX_POINT_CHARS} 码点 / "
            f"合计 {SUMMARY_MAX_TOTAL_CHARS} 码点 / 最多 {SUMMARY_MAX_POINTS} 条），保留教材原文供核对。"
        )
    if VIOLATION_IMAGE_TEXT in codes:
        return "知识点输出包含图片标记，保留教材原文供核对。"
    return "知识点概括输出不合法，保留教材原文供核对。"


# ------------------------------------------------------------------ 校验

def _normalized_ids(raw_ids: object) -> list[str] | None:
    if not isinstance(raw_ids, list):
        return None
    ids: list[str] = []
    for value in raw_ids:
        if isinstance(value, str) and value and value not in ids:
            ids.append(value)
    return ids


def _check_fields(
    *,
    title: str,
    summary: str,
    ids: Sequence[str],
    allowed_ids: frozenset[str] | None,
    max_point_chars: int,
    max_refs_per_point: int,
) -> str | None:
    """单个知识点的引用与长度校验：返回违规码，``None`` 表示合法。

    **整点拒绝**：只要有一个 ``evidenceIds`` 不在准入集合内，该点整体作废——
    不能只删非法 ID 后继续使用可能依赖它的内容（PLAN §3.4）。
    """
    if not title or not summary:
        return VIOLATION_POINT_EMPTY
    if "![" in title or "![" in summary or "<img" in title.lower() or "<img" in summary.lower():
        return VIOLATION_IMAGE_TEXT
    if len(title) + len(summary) > max_point_chars:
        return VIOLATION_POINT_TOO_LONG
    if not ids:
        return VIOLATION_REF_EMPTY
    if len(ids) > max_refs_per_point:
        return VIOLATION_REF_LIMIT
    if allowed_ids is not None and not set(ids).issubset(allowed_ids):
        return VIOLATION_REF_NOT_ADMITTED
    return None


def validate_points(
    proposal: object,
    *,
    allowed_ids: frozenset[str] | set[str] | None,
    max_points: int = SUMMARY_MAX_POINTS,
    max_point_chars: int = SUMMARY_MAX_POINT_CHARS,
    max_total_chars: int = SUMMARY_MAX_TOTAL_CHARS,
    max_refs_per_point: int = SUMMARY_MAX_REFS_PER_POINT,
) -> CheckedProposal:
    """校验模型输出的结构与引用：只允许引用 ``allowed_ids``（**真实准入集合**）。

    返回值里的 ``points`` 是**逐点合法**的部分（含整个点被拒绝的删除计数），
    ``violation_codes`` 记录数量/总量等"点本身完整但超限"的违规；调用方据此决定修正或部分保留。
    """
    allowed = frozenset(allowed_ids) if allowed_ids is not None else None
    if not isinstance(proposal, dict):
        return CheckedProposal(violation_codes=(VIOLATION_STRUCTURE,))
    raw_points = proposal.get("points")
    if not isinstance(raw_points, list) or not raw_points:
        return CheckedProposal(violation_codes=(VIOLATION_STRUCTURE,))
    points: list[RagPoint] = []
    dropped = 0
    codes: list[str] = []
    seen: set[str] = set()
    for raw in raw_points:
        if not isinstance(raw, dict):
            dropped += 1
            codes.append(VIOLATION_POINT_EMPTY)
            continue
        title = raw.get("title")
        summary = raw.get("summary")
        ids = _normalized_ids(raw.get("evidenceIds"))
        code = _check_fields(
            title=title.strip() if isinstance(title, str) else "",
            summary=summary.strip() if isinstance(summary, str) else "",
            ids=ids or [],
            allowed_ids=allowed,
            max_point_chars=max_point_chars,
            max_refs_per_point=max_refs_per_point,
        )
        if code is not None:
            dropped += 1
            codes.append(code)
            continue
        point = RagPoint(
            pointId="pt-" + _digest(title.strip(), summary.strip(), ids),
            title=title.strip(),
            summary=summary.strip(),
            evidenceIds=list(ids),
        )
        if point.pointId in seen:
            dropped += 1
            codes.append(VIOLATION_DUPLICATE)
            continue
        seen.add(point.pointId)
        points.append(point)
    if len(points) > max_points:
        codes.append(VIOLATION_POINT_LIMIT)
    if sum(len(point.title) + len(point.summary) for point in points) > max_total_chars:
        codes.append(VIOLATION_TOTAL_TOO_LONG)
    return CheckedProposal(
        points=tuple(points), dropped=dropped, violation_codes=tuple(dict.fromkeys(codes))
    )


def choose_complete_valid_points(
    points: Sequence[RagPoint],
    *,
    max_points: int = SUMMARY_MAX_POINTS,
    total_budget: int = SUMMARY_MAX_TOTAL_CHARS,
) -> list[RagPoint]:
    """保留完整且能装入预算的知识点：按顺序取，放不下的**整点丢弃**，绝不截断单点。"""
    kept: list[RagPoint] = []
    used = 0
    for point in points:
        if len(kept) >= max_points:
            break
        cost = len(point.title) + len(point.summary)
        if used + cost > total_budget:
            continue
        kept.append(point)
        used += cost
    return kept


def filter_points(
    points: Sequence[RagPoint],
    evidence: Sequence[TextbookEvidence],
    *,
    allowed_ids: frozenset[str] | set[str] | None = None,
) -> tuple[list[RagPoint], int]:
    """服务端二次校验：任何实现（含替身）产出的知识点都必须只引用**准入集合**。

    ``allowed_ids`` 缺省（替身没有提示词打包信息）时退回"全部已核验证据"，
    这样"引用不存在证据"依然不可能越过会话层进入结果；真实概括走
    ``SummaryOutcome.admitted_evidence_ids``（打包后实际进入提示词的集合）。
    """
    allowed = (
        frozenset(allowed_ids)
        if allowed_ids is not None
        else frozenset(item.evidenceId for item in evidence)
    )
    kept: list[RagPoint] = []
    dropped = 0
    seen: set[str] = set()
    for point in points:
        title = point.title.strip() if isinstance(point.title, str) else ""
        summary = point.summary.strip() if isinstance(point.summary, str) else ""
        ids = _normalized_ids(list(point.evidenceIds)) or []
        code = _check_fields(
            title=title,
            summary=summary,
            ids=ids,
            allowed_ids=allowed,
            max_point_chars=SUMMARY_MAX_POINT_CHARS,
            max_refs_per_point=SUMMARY_MAX_REFS_PER_POINT,
        )
        if code is not None:
            dropped += 1
            continue
        point_id = point.pointId or "pt-" + _digest(title, summary, ids)
        if point_id in seen:
            dropped += 1
            continue
        seen.add(point_id)
        kept.append(
            RagPoint(pointId=point_id, title=title, summary=summary, evidenceIds=list(ids))
        )
    return kept, dropped


def _digest(title: str, summary: str, ids: Sequence[str]) -> str:
    import hashlib

    payload = f"{title}\u0000{summary}\u0000{'|'.join(ids)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def correction_prompt(*, pack: PromptPack, question: str, violation_codes: Sequence[str]) -> str:
    """修正提示词：**同一批证据**（不新增准入内容）+ 上一次的违规说明。"""
    labels = [VIOLATION_LABELS.get(code, code) for code in dict.fromkeys(violation_codes)]
    detail = "；".join(labels) if labels else "输出不合法"
    return (
        f"{pack.prompt}\n\n"
        f"上一次输出不合法（{detail}）。请只依据上面同一批 evidenceId 重新输出："
        f"最多 {SUMMARY_MAX_POINTS} 条知识点，单点标题与说明合计不超过 {SUMMARY_MAX_POINT_CHARS} 字，"
        f"全部合计不超过 {SUMMARY_MAX_TOTAL_CHARS} 字，每条最多引用 {SUMMARY_MAX_REFS_PER_POINT} 个"
        "上面原样出现过的 ev-id，不要图片 Markdown，不要额外说明文字。"
    )


# ------------------------------------------------------------------ 概括实现

class KnowledgeSummarizer:
    """知识点概括：同步实现，由会话层放进有界线程执行；模型是**全局默认云端档案**。

    - 模型身份每次调用时解析（默认档案 → ``ChatModelHandle``）；本机部署档案与"未配置默认
      模型"一律按 503 不可用处理，**不回退本机**。
    - 提示词预算按档案 ``contextTokens``（未声明用 ``DEFAULT_CONTEXT_TOKENS``）与输出上限
      （``maxOutputTokens``，夹到 ``[OUTPUT_TOKEN_MIN, OUTPUT_TOKEN_MAX]``）计算，
      并与 ``EVIDENCE_PROMPT_MAX_CHARS`` 取较小者。
    - ``status()`` / ``probe()`` 均为**配置级检查**：只解析默认档案与判定云端，不发起推理调用。
    """

    def __init__(
        self,
        *,
        resolve_default_profile: Callable[[], str | None],
        resolve_handle: Callable[[str], ChatModelHandle],
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._resolve_default_profile = resolve_default_profile
        self._resolve_handle = resolve_handle
        self.timeout_seconds = float(timeout_seconds)

    # ------------------------------------------------------------------ 状态

    def _resolved(self) -> tuple[str, ChatModelHandle]:
        """解析默认档案并判定云端；不可用时抛 503（调用方转 partial 并保留证据）。"""
        try:
            profile_id = self._resolve_default_profile()
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 - 读取配置失败按不可用报告
            raise unavailable(f"读取默认模型配置失败：{exc.__class__.__name__}。") from exc
        if not profile_id:
            raise unavailable(
                "未配置全局默认问答模型（设置 → 默认模型）；知识点概括只使用云端模型，不使用本机模型。"
            )
        try:
            handle = self._resolve_handle(profile_id)
        except AppError as exc:
            # 档案缺失/连接被删等都属于"概括暂停"，不能把问答本身拖成 500
            raise unavailable(f"默认模型档案不可用（{exc.code}），知识点概括暂停。") from exc
        spec = find_provider(handle.config.providerId) if handle.config.providerId else None
        if spec is not None and spec.is_local:
            raise unavailable("全局默认问答模型是本机部署；知识点概括只使用云端模型，请在设置中改选云端默认模型。")
        return profile_id, handle

    @property
    def prompt_budget_chars(self) -> int:
        """档案窗口估算与首答入模上限的**较小者**（PLAN §3.4）。"""
        _profile_id, handle = self._resolved()
        return min(prompt_char_budget(handle.context_tokens or DEFAULT_CONTEXT_TOKENS, self._output_tokens(handle)),
                   EVIDENCE_PROMPT_MAX_CHARS)

    @staticmethod
    def _output_tokens(handle: ChatModelHandle) -> int:
        return min(max(OUTPUT_TOKEN_MIN, int(handle.max_output_tokens)), OUTPUT_TOKEN_MAX)

    def status(self) -> dict:
        """配置级状态：只解析默认档案 + 判定云端；不发起真实推理调用。"""
        try:
            profile_id, handle = self._resolved()
        except AppError as exc:
            return {"available": False, "reason": str(exc), "model": None, "providerUrl": None,
                    "modelProfileId": None}
        spec = find_provider(handle.config.providerId)
        return {
            "available": True,
            "reason": None,
            "model": handle.model_id,
            "providerUrl": None,
            "providerLabel": spec.label if spec else None,
            "modelProfileId": profile_id,
            "outputTokens": self._output_tokens(handle),
            "contextTokens": handle.context_tokens or DEFAULT_CONTEXT_TOKENS,
            "promptBudgetChars": min(
                prompt_char_budget(handle.context_tokens or DEFAULT_CONTEXT_TOKENS, self._output_tokens(handle)),
                EVIDENCE_PROMPT_MAX_CHARS),
        }

    def probe(self) -> dict:
        """配置级探测：解析默认档案并确认是云端档案。

        不向云端发起真实调用（避免为状态页产生费用），因此"探测通过"只表示**配置就绪**，
        不代表凭证与额度已实测；调用失败仍按 503 原样上报。
        """
        try:
            self._resolved()
        except AppError as exc:
            return {"available": False, "reason": str(exc)}
        except Exception:  # noqa: BLE001 - 探测失败只回报，不影响状态接口
            return {"available": False, "reason": "默认模型配置探测失败。"}
        return {"available": True, "reason": None,
                "detail": "配置级检查：默认云端档案已就绪（未发起真实推理调用）。"}

    # ------------------------------------------------------------------ 概括

    def summarize(self, *, question: str, evidence: Sequence[TextbookEvidence]) -> SummaryOutcome:
        total = len(evidence)
        if not evidence:
            return SummaryOutcome(
                points=[],
                reason="没有可引用的教材原文，未进行知识点概括。",
                reason_code="SUMMARY_INVALID",
            )
        budget = self.prompt_budget_chars
        pack = pack_evidence(question=question, evidence=evidence, budget_chars=budget)
        if not pack.fits:
            # 发送前自检：连一条证据都装不下 → 不调用模型，直接按 partial 返回
            return SummaryOutcome(
                points=[],
                reason=(
                    f"教材证据超出知识点概括输入预算（上限 {budget} 字符；题目与输出要求已占用固定部分），"
                    "未调用知识点概括，保留教材原文供核对。"
                ),
                reason_code="SUMMARY_INVALID",
                total_evidence=total,
                skipped_evidence=total,
                skipped_evidence_ids=pack.skipped_evidence_ids,
            )

        started = time.monotonic()
        proposal = self._request_proposal(pack.prompt)
        attempts = 1
        corrected = 0
        truncated = proposal.truncated
        prompt_eval_count = proposal.prompt_eval_count
        eval_count = proposal.eval_count
        if not proposal.ok:
            return self._failure(
                _with_coverage(proposal.reason or "", pack),
                pack,
                total=total,
                started=started,
                prompt_eval_count=prompt_eval_count,
                eval_count=eval_count,
                truncated=truncated,
                attempts=attempts,
            )
        if truncated:
            return self._failure(
                _with_coverage(
                    "知识点概括提示词超出模型上下文（上游已截断），本次不采用该输出，保留教材原文供核对。",
                    pack,
                ),
                pack,
                total=total,
                started=started,
                prompt_eval_count=prompt_eval_count,
                eval_count=eval_count,
                truncated=True,
                attempts=attempts,
            )
        checked = validate_points(proposal.payload, allowed_ids=pack.admitted_evidence_ids)
        structure = structure_state(proposal.payload)
        while not checked.valid and corrected < SUMMARY_MAX_CORRECTIONS:
            corrected += 1
            proposal = self._request_proposal(
                correction_prompt(
                    pack=pack, question=question, violation_codes=checked.violation_codes
                )
            )
            attempts += 1
            prompt_eval_count = proposal.prompt_eval_count or prompt_eval_count
            eval_count = proposal.eval_count or eval_count
            truncated = proposal.truncated
            if not proposal.ok or truncated:
                break
            checked = validate_points(proposal.payload, allowed_ids=pack.admitted_evidence_ids)
            structure = structure_state(proposal.payload)

        common = {
            "total_evidence": total,
            "used_evidence": pack.used_evidence,
            "skipped_evidence": pack.skipped_evidence,
            "admitted_evidence_ids": pack.admitted_evidence_ids,
            "skipped_evidence_ids": pack.skipped_evidence_ids,
            "corrected": corrected,
            "violation_codes": checked.violation_codes,
            "prompt_eval_count": prompt_eval_count,
            "eval_count": eval_count,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "truncated": truncated,
        }
        if checked.valid:
            # 成功结果保持 reason is None；覆盖条数与上游计数只走诊断字段
            return SummaryOutcome(points=list(checked.points), dropped=checked.dropped, **common)
        if not proposal.ok:
            return SummaryOutcome(
                points=[],
                reason=_with_coverage(proposal.reason or "", pack),
                reason_code="SUMMARY_INVALID",
                dropped=checked.dropped,
                **common,
            )
        if truncated:
            return SummaryOutcome(
                points=[],
                reason=_with_coverage(
                    "知识点概括提示词超出模型上下文（上游已截断），本次不采用该输出，保留教材原文供核对。",
                    pack,
                ),
                reason_code="SUMMARY_INVALID",
                dropped=checked.dropped,
                **common,
            )
        # 修正后仍不合法：保留**完整且能装入预算**的知识点，绝不截断单点
        kept = choose_complete_valid_points(checked.points)
        if not kept:
            return SummaryOutcome(
                points=[],
                reason=_with_coverage(_invalid_reason(checked, structure=structure), pack),
                reason_code="SUMMARY_INVALID",
                dropped=checked.dropped,
                **common,
            )
        labels = "、".join(
            VIOLATION_LABELS.get(code, code) for code in checked.violation_codes
        )
        return SummaryOutcome(
            points=kept,
            reason=_with_coverage(
                f"部分知识点不合法（{labels or '未通过校验'}），已保留 {len(kept)} 个完整知识点"
                f"（不截断单点），保留教材原文供核对。",
                pack,
            ),
            reason_code="SUMMARY_PARTIAL",
            dropped=checked.dropped,
            **common,
        )

    def _failure(
        self,
        reason: str,
        pack: PromptPack,
        *,
        total: int,
        started: float,
        prompt_eval_count: int | None,
        eval_count: int | None,
        truncated: bool,
        attempts: int,
    ) -> SummaryOutcome:
        return SummaryOutcome(
            points=[],
            reason=reason,
            reason_code="SUMMARY_INVALID",
            total_evidence=total,
            used_evidence=pack.used_evidence,
            skipped_evidence=pack.skipped_evidence,
            admitted_evidence_ids=pack.admitted_evidence_ids,
            skipped_evidence_ids=pack.skipped_evidence_ids,
            corrected=attempts - 1,
            prompt_eval_count=prompt_eval_count,
            eval_count=eval_count,
            elapsed_seconds=round(time.monotonic() - started, 3),
            truncated=truncated,
        )

    def _request_proposal(self, prompt: str) -> _Proposal:
        _profile_id, handle = self._resolved()
        request = LLMRequest(
            messages=[LLMMessage("system", INSTRUCTION), LLMMessage("user", prompt)],
            maxOutputTokens=self._output_tokens(handle),
            params={},
        )
        try:
            response = self._complete(handle, request)
        except TimeoutError as exc:
            # 超时后上游可能仍在生成（无法取消已发出的请求）：按"概括未完成"处理，证据由调用方保留。
            return _timeout(exc)
        except ProviderError as exc:
            if exc.code == "UPSTREAM_TIMEOUT":
                return _timeout(exc)
            raise unavailable(f"默认云端模型调用失败（{exc.code}），知识点概括不可用。") from exc
        text = (response.text or "").strip()
        usage = response.usage
        prompt_eval_count = usage.inputTokens if usage is not None else None
        eval_count = usage.outputTokens if usage is not None else None
        truncated = getattr(response, "finishReason", None) == FINISH_LENGTH
        if not text:
            return _invalid_json(prompt_eval_count=prompt_eval_count, eval_count=eval_count, truncated=truncated)
        try:
            parsed = json.loads(text)
        except ValueError:
            return _invalid_json(prompt_eval_count=prompt_eval_count, eval_count=eval_count, truncated=truncated)
        return _Proposal(
            ok=True,
            payload=parsed,
            prompt_eval_count=prompt_eval_count,
            eval_count=eval_count,
            truncated=truncated,
        )

    def _complete(self, handle: ChatModelHandle, request: LLMRequest) -> LLMResponse:
        """同步桥接异步 provider：在独立线程里跑事件循环，避免在事件循环线程调用 asyncio.run。"""
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, handle.provider.complete(handle.config, request)).result(
                timeout=self.timeout_seconds
            )


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _timeout(exc: Exception) -> _Proposal:
    """超时是"概括未完成"：返回 partial 语义，证据由调用方保留。"""
    return _Proposal(
        ok=False,
        reason=f"知识点概括调用超时（{exc.__class__.__name__}），保留教材原文供核对。",
    )


def _invalid_json(
    *,
    prompt_eval_count: int | None = None,
    eval_count: int | None = None,
    truncated: bool = False,
) -> _Proposal:
    return _Proposal(
        ok=False,
        reason="知识概括返回结构不符合要求（不是合法 JSON），保留教材原文供核对。",
        prompt_eval_count=prompt_eval_count,
        eval_count=eval_count,
        truncated=truncated,
    )


__all__ = [
    "CHARS_PER_TOKEN",
    "DEFAULT_CONTEXT_TOKENS",
    "DEFAULT_OUTPUT_TOKENS",
    "DEFAULT_TIMEOUT_SECONDS",
    "INSTRUCTION",
    "KnowledgeSummarizer",
    "OUTPUT_TOKEN_MAX",
    "OUTPUT_TOKEN_MIN",
    "PROMPT_FOOTER",
    "PROMPT_HEADER",
    "PROMPT_SAFETY_MARGIN",
    "CheckedProposal",
    "PromptPack",
    "SummaryOutcome",
    "Summarizer",
    "VIOLATION_LABELS",
    "choose_complete_valid_points",
    "correction_prompt",
    "coverage_note",
    "evidence_block",
    "filter_points",
    "pack_evidence",
    "prompt_char_budget",
    "prompt_token_budget",
    "readable_text",
    "structure_state",
    "validate_points",
]
