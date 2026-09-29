"""知识点首答：本机 Ollama 结构化概括，只引用**实际进入提示词**的教材原文。

RAG-QUALITY v1.1 修复（PLAN §3.4）：

- 只调本机回环地址的 Ollama 原生 ``/api/chat``（``httpx``，``trust_env=False``，
  不跟随重定向）；地址非回环一律拒绝。
- ``PromptPack`` 返回**真实准入集合**：``admitted_evidence_ids`` / ``admitted_evidence`` /
  ``skipped_evidence_ids``。打包按 ``EVIDENCE_PROMPT_MAX_CHARS``（预算唯一事实来源）与模型
  ``num_ctx``/``num_predict`` 估算出的字符预算中**较小者**；整条装入、绝不截断单条原文，
  装入文本用清洗后的 ``readable.text``（不把图片地址送进模型）。
- **引用校验只用 admitted 集合**：某个点的 ``evidenceIds`` 不是 admitted 子集 → **整个点拒绝**
  （不删非法 ID 后继续使用可能依赖它的内容）；伪造 ID、空引用、超 2 条引用、单点超 90 码点、
  含图片 Markdown 同样整点拒绝。
- 首答长度约束全部从 ``app.core.rag_budget`` 读：≤3 点 / 单点 ≤90 / 合计 ≤250 码点 / 每点 ≤2 引用。
- 模型输出超长、重复或格式错误 → **最多修正一次**（``SUMMARY_MAX_CORRECTIONS``，模型调用总数 ≤2）；
  修正后仍不合法时保留**完整且能装入预算**的点（不截断单点）→ ``SUMMARY_PARTIAL``；
  连一个完整点都没有 → ``SUMMARY_INVALID``。
- ``num_ctx`` / ``num_predict`` 保持显式下发（既有实现），提示词预算统一由这两个参数计算；
  ``prompt_eval_count`` 只作**诊断字段**（"样本未观察到窗口饱和"，不代表"绝未截断"）。
- 失败分类分级：上游不可用（非 200 / 连接失败 / 地址非法）抛 503 ``RAG_SUMMARY_UNAVAILABLE``；
  非法 JSON、结构不符、引用校验不过、超时、上游截断一律返回 ``partial`` 语义并保留证据，
  措辞彼此可区分。**绝不悄悄降级成 no_evidence、绝不编造讲解。**
- ``reason`` 只含固定措辞、计数与预算数字，不回显题目全文或原文内容。

测试注入替身即可覆盖全部分支；真实模型验收见结果卡「验证」小节。
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.exceptions import AppError
from app.core.rag_budget import (
    EVIDENCE_PROMPT_MAX_CHARS,
    SUMMARY_MAX_CORRECTIONS,
    SUMMARY_MAX_POINT_CHARS,
    SUMMARY_MAX_POINTS,
    SUMMARY_MAX_REFS_PER_POINT,
    SUMMARY_MAX_TOTAL_CHARS,
)
from app.providers.embeddings.ollama_embedding import (
    model_names_match,
    normalize_loopback_base_url,
)
from app.schemas.rag_v2 import RagPoint, TextbookEvidence

DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_TIMEOUT_SECONDS = 300.0
#: 状态探测的短超时：绝不把 /rag/status 拖慢（探测失败只影响 available/reason）。
PROBE_TIMEOUT_SECONDS = 3.0
#: 显式上下文窗口：不显式下发时 Ollama 按默认（常见 2048）截断提示词，
#: 模型看不到"必须返回 points 数组并引用 evidenceId"的指令 → 真实规模证据必然概括失败。
DEFAULT_NUM_CTX = 8192
#: 输出侧有界（PLAN §3.4 默认 1024）：生成预留同时决定提示词 token 预算。
DEFAULT_NUM_PREDICT = 1024
OUTPUT_TOKEN_MIN = 256
OUTPUT_TOKEN_MAX = 2048
#: 保守字符估算（仓库既有口径）：1 token ≈ 2 字符。**这是估算，不是精确 token 计数。**
CHARS_PER_TOKEN = 2
#: 预算预留：聊天模板与结构开销。
RESERVED_TOKENS = 512
#: 安全余量：中文实际约 1.2–1.7 字符/token，字符口径会低估 token 数，故再打折扣。
PROMPT_SAFETY_MARGIN = 0.7
#: 上游截断判定余量：prompt_eval_count 逼近窗口即视为提示词被截断（**诊断信号**）。
TRUNCATION_MARGIN_TOKENS = 64

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


def prompt_token_budget(num_ctx: int = DEFAULT_NUM_CTX, num_predict: int = DEFAULT_NUM_PREDICT) -> int:
    """提示词可用 token 预算（估算）：窗口 − 生成预留 − 模板预留。"""
    return max(0, int(num_ctx) - int(num_predict) - RESERVED_TOKENS)


def prompt_char_budget(num_ctx: int = DEFAULT_NUM_CTX, num_predict: int = DEFAULT_NUM_PREDICT) -> int:
    """提示词字符硬上限：保守估算（1 token ≈ 2 字符）× 安全余量。

    这是字符口径的上限，用于打包与"发送前自检"；真实 token 数由上游 ``prompt_eval_count``
    交叉验证（**诊断信号**，不写成"证明绝未截断"）。
    """
    return int(prompt_token_budget(num_ctx, num_predict) * CHARS_PER_TOKEN * PROMPT_SAFETY_MARGIN)


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
        raise unavailable("本地概括提示词打包超出预算，已停止概括并保留原文。")
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
            "not_object": "本地概括返回结构不符合要求（不是 JSON 对象）",
            "no_points": "本地概括返回结构不符合要求（缺少 points 数组）",
            "empty_points": "本地概括未给出知识点（points 为空）",
        }.get(structure, "本地概括返回结构不符合要求")
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
    """本机 Ollama 知识点概括；同步实现，由会话层放进有界线程执行。

    ``num_ctx`` / ``num_predict`` 显式下发到 ``options``；两者一旦变化，提示词预算随之变化
    （``prompt_char_budget``）。``num_predict`` 会被夹到 ``[OUTPUT_TOKEN_MIN, OUTPUT_TOKEN_MAX]``，
    ``num_ctx`` 下限 1024，避免调用方给出会立刻截断的窗口。
    """

    def __init__(
        self,
        provider_url: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        *,
        num_ctx: int = DEFAULT_NUM_CTX,
        num_predict: int = DEFAULT_NUM_PREDICT,
        client_factory=None,
    ) -> None:
        self.provider_url = provider_url
        self.model = model
        self.timeout_seconds = float(timeout_seconds)
        self.num_ctx = max(1024, int(num_ctx))
        self.num_predict = min(max(OUTPUT_TOKEN_MIN, int(num_predict)), OUTPUT_TOKEN_MAX)
        self._client_factory = client_factory

    # ------------------------------------------------------------------ 状态

    @property
    def prompt_budget_chars(self) -> int:
        """模型窗口估算与首答入模上限的**较小者**（PLAN §3.4）。"""
        return min(prompt_char_budget(self.num_ctx, self.num_predict), EVIDENCE_PROMPT_MAX_CHARS)

    def _base_url(self) -> str:
        if not self.provider_url:
            raise unavailable("本地概括服务地址未配置，知识点概括不可用。")
        try:
            return normalize_loopback_base_url(self.provider_url)
        except AppError as exc:
            raise unavailable(f"本地概括服务地址不合法：{exc}") from exc

    def status(self) -> dict:
        try:
            base_url = self._base_url()
        except AppError as exc:
            return {"available": False, "reason": str(exc), "model": self.model, "providerUrl": None}
        return {
            "available": True,
            "reason": None,
            "model": self.model,
            "providerUrl": base_url,
            "numCtx": self.num_ctx,
            "numPredict": self.num_predict,
            "promptBudgetChars": self.prompt_budget_chars,
        }

    def probe(self) -> dict:
        """轻量真实探测：Ollama ``/api/tags`` 可达 + 配置的概括模型已安装（tag 归一）。

        只回报不抛错（``/rag/status`` 不得因上游不可达而失败或变慢）；使用短超时客户端。
        """
        try:
            base_url = self._base_url()
        except AppError as exc:
            return {"available": False, "reason": str(exc)}
        try:
            with self._client(base_url, timeout_seconds=PROBE_TIMEOUT_SECONDS) as client:
                response = client.get("/api/tags")
        except httpx.TimeoutException:
            return {"available": False, "reason": "本地概括服务探测超时（Ollama 未在 3 秒内响应）。"}
        except httpx.HTTPError:
            return {"available": False, "reason": "本地概括服务不可达（Ollama 未响应）。"}
        except Exception:  # noqa: BLE001 - 探测失败只回报，不影响状态接口
            return {"available": False, "reason": "本地概括服务探测失败。"}
        if response.status_code != 200:
            return {"available": False, "reason": f"本地概括服务返回 {response.status_code}。"}
        try:
            body = response.json()
        except ValueError:
            return {"available": False, "reason": "本地概括服务探测响应不是合法 JSON。"}
        entries = body.get("models") if isinstance(body, dict) else None
        if not isinstance(entries, list):
            return {"available": False, "reason": "本地概括服务探测响应缺少 models 数组。"}
        names = [
            entry.get("name") or entry.get("model")
            for entry in entries
            if isinstance(entry, dict)
        ]
        if not any(isinstance(name, str) and name.strip() for name in names):
            return {"available": False, "reason": "本机 Ollama 没有可用模型。"}
        if not any(
            isinstance(name, str) and model_names_match(name, self.model) for name in names
        ):
            return {"available": False, "reason": f"本机未安装概括模型 {self.model}。"}
        return {"available": True, "reason": None}

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
                    f"教材证据超出本地概括输入预算（上限 {budget} 字符；题目与输出要求已占用固定部分），"
                    "未调用本地概括，保留教材原文供核对。"
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
                    "本地概括提示词超出模型上下文（上游已截断），本次不采用该输出，保留教材原文供核对。",
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
                    "本地概括提示词超出模型上下文（上游已截断），本次不采用该输出，保留教材原文供核对。",
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
        base_url = self._base_url()
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            "options": {
                "temperature": 0,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }
        try:
            with self._client(base_url) as client:
                response = client.post("/api/chat", json=payload)
        except httpx.TimeoutException as exc:
            return _timeout(exc)
        except httpx.HTTPError as exc:
            raise unavailable("本地概括服务不可用，请检查本机 Ollama 后重试。") from exc
        if response.status_code != 200:
            raise unavailable(f"本地概括服务返回 {response.status_code}，知识点概括不可用。")
        try:
            body = response.json()
        except ValueError:
            return _invalid_json()
        if not isinstance(body, dict):
            return _invalid_json()
        prompt_eval_count = _as_int(body.get("prompt_eval_count"))
        eval_count = _as_int(body.get("eval_count"))
        truncated = (
            prompt_eval_count is not None
            and prompt_eval_count >= self.num_ctx - TRUNCATION_MARGIN_TOKENS
        )
        message = body.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            return _invalid_json(prompt_eval_count=prompt_eval_count, eval_count=eval_count, truncated=truncated)
        try:
            parsed = json.loads(content)
        except ValueError:
            return _invalid_json(prompt_eval_count=prompt_eval_count, eval_count=eval_count, truncated=truncated)
        return _Proposal(
            ok=True,
            payload=parsed,
            prompt_eval_count=prompt_eval_count,
            eval_count=eval_count,
            truncated=truncated,
        )

    def _client(self, base_url: str, *, timeout_seconds: float | None = None) -> httpx.Client:
        timeout = self.timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        if self._client_factory is not None:
            return self._client_factory(base_url=base_url, timeout=timeout)
        return httpx.Client(
            base_url=base_url,
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        )


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _timeout(exc: Exception) -> _Proposal:
    """超时是"概括未完成"：返回 partial 语义，证据由调用方保留。"""
    return _Proposal(
        ok=False,
        reason=f"本地知识点概括超时（{exc.__class__.__name__}），保留教材原文供核对。",
    )


def _invalid_json(
    *,
    prompt_eval_count: int | None = None,
    eval_count: int | None = None,
    truncated: bool = False,
) -> _Proposal:
    return _Proposal(
        ok=False,
        reason="本地概括返回结构不符合要求（不是合法 JSON），保留教材原文供核对。",
        prompt_eval_count=prompt_eval_count,
        eval_count=eval_count,
        truncated=truncated,
    )


__all__ = [
    "CHARS_PER_TOKEN",
    "DEFAULT_MODEL",
    "DEFAULT_NUM_CTX",
    "DEFAULT_NUM_PREDICT",
    "DEFAULT_TIMEOUT_SECONDS",
    "INSTRUCTION",
    "KnowledgeSummarizer",
    "OUTPUT_TOKEN_MAX",
    "OUTPUT_TOKEN_MIN",
    "PROMPT_FOOTER",
    "PROMPT_HEADER",
    "PROMPT_SAFETY_MARGIN",
    "PROBE_TIMEOUT_SECONDS",
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
