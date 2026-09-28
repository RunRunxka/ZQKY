"""知识点首答：本机 Ollama 结构化概括，只引用已核验的教材原文。

- 只调本机回环地址的 Ollama 原生 ``/api/chat``（``httpx``，``trust_env=False``，
  不跟随重定向）；地址非回环一律拒绝。
- 指令固定为「只概括与题目有关的教材知识点、适用条件和原文依据；每条必须引用提供的
  evidenceId；不提供完整解题推导、不编造出处」；输出要求同时写在系统指令与用户提示尾部
  （尾部那句在截断场景下仍会被模型看到）。
- **上下文与输出预算显式下发**（``options.num_ctx`` / ``options.num_predict``），并把
  ``num_ctx`` 作为提示词硬上限的依据：按保守字符估算（仓库既有口径 1 token ≈ 2 字符）
  再乘安全余量得到字符预算；**字符数是估算口径，不是精确 token 计数**。
- **整条打包，绝不截断单条原文**：按证据顺序装入直到接近预算，装不下的整条丢弃；若连一条
  都装不下，**不发送请求**，直接按 partial 返回并说明原因。本次覆盖条数写入
  ``SummaryOutcome`` 的 ``used_evidence/total_evidence/skipped_evidence`` 字段
  （成功结果保持 ``reason is None``，覆盖信息不放 reason，避免把成功结果说成部分结果）。
- ``validate_points`` 丢弃引用不存在 evidenceId 的点、丢弃空标题/空摘要，输出模式固定为
  「教材原文摘录 + 知识点标题」，本模块不做任何独立推导；``reason`` 只含固定措辞、计数与
  预算数字，不回显题目全文或原文内容。
- 失败分类分级：上游不可用（非 200 / 连接失败 / 地址非法）抛 503 ``RAG_SUMMARY_UNAVAILABLE``；
  非法 JSON、"缺少 points 数组"、"points 为空"、"知识点未通过引用校验"、超时、上游截断
  一律返回 ``partial`` 语义并保留证据，且措辞彼此可区分。**绝不悄悄降级成 no_evidence、绝不编造讲解。**
- 测试注入替身即可覆盖全部分支；真实模型验收见结果卡「v1.1 修复」小节。
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.exceptions import AppError
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
#: 输出侧有界：生成预留同时决定提示词 token 预算。
DEFAULT_NUM_PREDICT = 1536
OUTPUT_TOKEN_MIN = 256
OUTPUT_TOKEN_MAX = 2048
#: 保守字符估算（仓库既有口径）：1 token ≈ 2 字符。**这是估算，不是精确 token 计数。**
CHARS_PER_TOKEN = 2
#: 预算预留：聊天模板与结构开销。
RESERVED_TOKENS = 512
#: 安全余量：中文实际约 1.2–1.7 字符/token，字符口径会低估 token 数，故再打折扣。
PROMPT_SAFETY_MARGIN = 0.7
#: 上游截断判定余量：prompt_eval_count 逼近窗口即视为提示词被截断。
TRUNCATION_MARGIN_TOKENS = 64
MAX_TITLE_CHARS = 200
MAX_SUMMARY_CHARS = 4000
MAX_POINT_EVIDENCE_IDS = 20

INSTRUCTION = (
    "你是教材知识点整理助手，只做教材原文的知识点概括。\n"
    "只概括与题目有关的教材知识点、适用条件和原文依据；每条知识点必须引用下方提供的 "
    "evidenceId（从上方原文的 [ev-…] 标记里原样复制至少一个，不得自造、不得留空）；"
    "不提供完整解题推导，不编造教材出处，不引入未提供的教材内容。\n"
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

    - ``used_evidence/total_evidence/skipped_evidence``：本次打包进提示词的证据条数与丢弃条数
      （成功的概括保持 ``reason is None``，覆盖信息只在这些字段里）；
    - ``prompt_eval_count/eval_count``：上游报告的提示词与生成 token 数（截断自检依据）；
    - ``elapsed_seconds``：本次概括实际耗时；
    - ``truncated``：上游窗口把提示词截断时为 True（此时不采用该输出）。
    """

    points: list[RagPoint] = field(default_factory=list)
    reason: str | None = None
    dropped: int = 0
    used_evidence: int = 0
    total_evidence: int = 0
    skipped_evidence: int = 0
    prompt_eval_count: int | None = None
    eval_count: int | None = None
    elapsed_seconds: float | None = None
    truncated: bool = False


@dataclass(frozen=True)
class PromptPack:
    """按预算整条装配后的提示词与覆盖计数。"""

    prompt: str
    chars: int
    budget_chars: int
    used_evidence: int
    total_evidence: int
    skipped_evidence: int
    fits: bool


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
    交叉验证（见 ``SummaryOutcome.prompt_eval_count``）。
    """
    return int(prompt_token_budget(num_ctx, num_predict) * CHARS_PER_TOKEN * PROMPT_SAFETY_MARGIN)


def evidence_block(item: TextbookEvidence) -> str:
    location = " → ".join([item.title, *item.chapterPath]) if item.chapterPath else item.title
    return f"[{item.evidenceId}] {location}\n{item.text}"


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
        )
    used: list[str] = []
    size = fixed_chars
    skipped = 0
    for item in evidence:
        block = evidence_block(item)
        cost = len(block) + 2
        if size + cost > budget_chars:
            skipped += 1
            continue
        used.append(block)
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
        )
    prompt = "\n\n".join([header, *used, PROMPT_FOOTER])
    if len(prompt) > budget_chars:  # pragma: no cover - 防御性：打包逻辑与预算必须自洽
        raise unavailable("本地概括提示词打包超出预算，已停止概括并保留原文。")
    return PromptPack(
        prompt=prompt,
        chars=len(prompt),
        budget_chars=budget_chars,
        used_evidence=len(used),
        total_evidence=len(evidence),
        skipped_evidence=skipped,
        fits=True,
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


def validate_points(proposal: object, evidence: Sequence[TextbookEvidence]) -> tuple[list[RagPoint], int]:
    """过滤模型输出：只保留引用已核验 evidenceId 且标题/摘要非空的点。"""
    known = {item.evidenceId for item in evidence}
    if not isinstance(proposal, dict):
        return [], 0
    raw_points = proposal.get("points")
    if not isinstance(raw_points, list):
        return [], 0
    points: list[RagPoint] = []
    dropped = 0
    seen: set[str] = set()
    for raw in raw_points:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        title = raw.get("title")
        summary = raw.get("summary")
        raw_ids = raw.get("evidenceIds")
        title = title.strip() if isinstance(title, str) else ""
        summary = summary.strip() if isinstance(summary, str) else ""
        ids: list[str] = []
        if isinstance(raw_ids, list):
            for value in raw_ids:
                if isinstance(value, str) and value in known and value not in ids:
                    ids.append(value)
        if not title or not summary or not ids:
            dropped += 1
            continue
        if len(title) > MAX_TITLE_CHARS or len(summary) > MAX_SUMMARY_CHARS:
            dropped += 1
            continue
        if len(ids) > MAX_POINT_EVIDENCE_IDS:
            dropped += 1
            continue
        point_id = "pt-" + _digest(title, summary, ids)
        if point_id in seen:
            dropped += 1
            continue
        seen.add(point_id)
        points.append(
            RagPoint(pointId=point_id, title=title, summary=summary, evidenceIds=ids)
        )
    return points, dropped


def _digest(title: str, summary: str, ids: Sequence[str]) -> str:
    import hashlib

    payload = f"{title}\u0000{summary}\u0000{'|'.join(ids)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def filter_points(points: Sequence[RagPoint], evidence: Sequence[TextbookEvidence]) -> tuple[list[RagPoint], int]:
    """服务端二次校验：任何实现（含替身）产出的知识点都必须只引用已核验证据。

    与 ``validate_points`` 同一组规则，作用在已解析的 ``RagPoint`` 上，
    因此"引用不存在证据"不可能越过会话层进入结果。
    """
    known = {item.evidenceId for item in evidence}
    kept: list[RagPoint] = []
    dropped = 0
    for point in points:
        title = point.title.strip() if isinstance(point.title, str) else ""
        summary = point.summary.strip() if isinstance(point.summary, str) else ""
        ids = [value for value in point.evidenceIds if value in known]
        keep_ids: list[str] = []
        for value in ids:
            if value not in keep_ids:
                keep_ids.append(value)
        if (
            not title
            or not summary
            or not keep_ids
            or len(title) > MAX_TITLE_CHARS
            or len(summary) > MAX_SUMMARY_CHARS
            or len(keep_ids) > MAX_POINT_EVIDENCE_IDS
        ):
            dropped += 1
            continue
        kept.append(
            RagPoint(
                pointId=point.pointId,
                title=title,
                summary=summary,
                evidenceIds=keep_ids,
            )
        )
    return kept, dropped


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
        return prompt_char_budget(self.num_ctx, self.num_predict)

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
            return SummaryOutcome(points=[], reason="没有可引用的教材原文，未进行知识点概括。")
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
                total_evidence=total,
                skipped_evidence=total,
            )

        started = time.monotonic()
        proposal = self._request_proposal(pack.prompt)
        elapsed = round(time.monotonic() - started, 3)
        common = {
            "total_evidence": total,
            "used_evidence": pack.used_evidence,
            "skipped_evidence": pack.skipped_evidence,
            "prompt_eval_count": proposal.prompt_eval_count,
            "eval_count": proposal.eval_count,
            "elapsed_seconds": elapsed,
        }
        if not proposal.ok:
            return SummaryOutcome(points=[], reason=_with_coverage(proposal.reason or "", pack), **common)
        if proposal.truncated:
            return SummaryOutcome(
                points=[],
                reason=_with_coverage(
                    "本地概括提示词超出模型上下文（上游已截断），本次不采用该输出，保留教材原文供核对。",
                    pack,
                ),
                truncated=True,
                **common,
            )
        state = structure_state(proposal.payload)
        if state != "ok":
            wording = {
                "not_object": "本地概括返回结构不符合要求（不是 JSON 对象）",
                "no_points": "本地概括返回结构不符合要求（缺少 points 数组）",
                "empty_points": "本地概括未给出知识点（points 为空）",
            }[state]
            return SummaryOutcome(
                points=[], reason=_with_coverage(wording + "，保留教材原文供核对。", pack), **common
            )
        points, dropped = validate_points(proposal.payload, evidence)
        if not points:
            return SummaryOutcome(
                points=[],
                reason=_with_coverage("知识点未通过原文引用校验，保留教材原文供核对。", pack),
                dropped=dropped,
                **common,
            )
        # 成功结果保持 reason is None；覆盖条数与上游计数只走诊断字段
        return SummaryOutcome(points=points, dropped=dropped, **common)

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
    "PromptPack",
    "SummaryOutcome",
    "Summarizer",
    "coverage_note",
    "evidence_block",
    "filter_points",
    "pack_evidence",
    "prompt_char_budget",
    "prompt_token_budget",
    "structure_state",
    "validate_points",
]
