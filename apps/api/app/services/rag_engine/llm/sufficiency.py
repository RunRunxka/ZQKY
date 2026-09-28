"""P8H 修复批 ⑥：**证据充分性/支持性门禁**（版本化、**默认关闭**、未采用候选）。

问题（已由本批反例证明，见 `data/derived/qa/P8H-STEP45/refusal_cases.jsonl`）：
现役 A0 在**语料外问题**与**证据不足**场景一律返回 `ok`，并输出**与题面无关的教材引用**
（例：`快速排序算法的平均时间复杂度是多少？` → 数学「第四章/03 复习题」区间）。

本模块给出**保守、机械、可核验**的门禁（不做黑名单、不用同源 silver 选通用阈值）：
  1. 证据为空 → `uncertain`（与现役服务一致，显式化）；
  2. 证据存在但**题面实词与被引区间零重叠** → `insufficient`（不发布任何引用）；
  3. 引用落在**非正文区**（习题/作答区）→ 该引用被丢弃；全被丢弃 → `uncertain`；
  4. 门槛（`min_overlap`）是**版本化参数**，必须在冻结 dev + 反例上配对检查后才允许启用。

**默认关闭**：`enabled=False` 时 `evaluate()` 返回 `noop`，服务行为与现役完全一致。
本批**不**切换 A0，也**不**宣布拒答已修复（拒答维度仍为 **FAIL**）。

P11 第二步新增（**影子候选，默认不注入**）
-----------------------------------------
同一模块承担 P11 候选的**证据来源过滤**（因素 A）与**两因素串联**（A→B）：

  - `RegionFilterConfig` + `build_region_verifier()`：因素 A。对候选区间做**机械正文归属
    复核**（复用 `src/evaluation/annotation_v2.py::RegionIndex`——P8B v2 契约的既有单一
    定义点，作用在**教材原文区间**上：chunk 标签层 + 标题层 + 条目形态层）。`region`
    缺失／无法核验（区间不在任何 chunk 内、文件不在 chunk 产物中）／非 `body`
    （`exercise_intersecting` / `practice_conflict`）→ **丢弃并逐条记台账**。
    **不含任何题目关键词黑白名单**。
  - `run_candidate_gate()`：把 A（来源过滤）与 B（`p8h-suff-v1` 充分性判定）串起来，
    返回「保留哪些区间 / 丢弃哪些 / 结构化降级与否」的**单一决策对象**，供服务层在
    证据包装配之前调用；全部丢弃时服务层**不发布任何引用**。

两者都只在**显式注入**时执行；未注入时本模块一行也不参与服务路径（默认 A0 不变）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

GATE_VERSION = "p8h-suff-v1"
STOPWORDS = frozenset(("的", "了", "是", "在", "和", "与", "或", "为", "有", "这", "那", "什么",
                       "多少", "哪些", "如何", "怎么", "请问", "算法", "问题", "方法"))
CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")
ASCII_WORD = re.compile(r"[A-Za-z]{3,}")


def content_terms(text: str) -> set[str]:
    """题面/区间的**内容词**：中文取二元组（bigram）+ 英文词，去停用词。

    为什么用 bigram：中文没有空格，整段切分会让「重叠」退化成 0/1 两个值，无法做门禁；
    bigram 是**机械、可复现**的做法（不引分词器、不做语义扩展、不含黑名单）。
    """
    body = str(text or "")
    out: set[str] = {w.lower() for w in ASCII_WORD.findall(body)}
    for run in CJK_RUN.findall(body):
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg in STOPWORDS:
                continue
            out.add(bg)
    return out


@dataclass
class SufficiencyConfig:
    enabled: bool = False                 # **默认关闭**（未通过配对检查前不得启用）
    min_overlap: int = 1                  # 题面内容词 ∩ 被引区间内容词的**最小**个数
    drop_non_body: bool = True            # 丢弃落在非正文区的引用
    version: str = GATE_VERSION
    evidence: str = ("反例：data/derived/qa/P8H-STEP45/refusal_cases.jsonl（OOC/C17/F-QA-2）；"
                     "未通过配对检查，故默认关闭")
    adopted: bool = False
    #: P12 拒答线候选 D：**证据定向性**（特有词覆盖率）。给定时**替代** `min_overlap`
    #: 判据（不同机制：比率而非计数；泛化词不参与）。`None` = 走 P11 原语义，逐字节不变。
    directedness: Any | None = None


@dataclass
class GateDecision:
    status: str                            # noop | sufficient | insufficient | uncertain
    keep_citation_ids: list[str] = field(default_factory=list)
    dropped_citation_ids: list[str] = field(default_factory=list)
    reason: str = ""
    version: str = GATE_VERSION


def evaluate(question: str, evidence: list[dict], *,
             cfg: SufficiencyConfig | None = None) -> GateDecision:
    """对一次生成前的**证据包**做充分性判定。

    `evidence`：`[{citation_id, text, region}]`（`region` 缺省视为 body）。
    返回 `noop` 表示门禁关闭、不改变现役行为。
    """
    cfg = cfg or SufficiencyConfig()
    if not cfg.enabled:
        return GateDecision(status="noop", keep_citation_ids=[e.get("citation_id") for e in evidence],
                            reason="门禁默认关闭（未采用候选）")
    if not evidence:
        return GateDecision(status="uncertain", reason="证据为空：结构化降级，不硬答")
    keep, dropped = [], []
    for e in evidence:
        cid = str(e.get("citation_id"))
        if cfg.drop_non_body and str(e.get("region") or "body") != "body":
            dropped.append(cid)
            continue
        if getattr(cfg, "directedness", None) is None:
            # P11 原语义（`min_overlap` 计数）——**逐字节不变**
            overlap = content_terms(question) & content_terms(str(e.get("text") or ""))
            if len(overlap) < cfg.min_overlap:
                dropped.append(cid)
                continue
        keep.append(cid)
    if not keep:
        return GateDecision(status="insufficient",
                            dropped_citation_ids=dropped,
                            reason=(f"与题面零重叠/非正文的引用全部丢弃（{len(dropped)} 条）→ "
                                    "结构化降级，不发布无关引用"))
    if getattr(cfg, "directedness", None) is not None:
        # P12 候选 D：**特有词覆盖率**（比率判据，泛化词不参与）
        from app.services.rag_engine.llm.evidence_directedness import evaluate_directedness
        texts = [str(e.get("text") or "") for e in evidence
                 if str(e.get("citation_id")) in set(keep)]
        dec = evaluate_directedness(question, texts, cfg=cfg.directedness)
        if dec.status == "insufficient":
            return GateDecision(status="insufficient", dropped_citation_ids=keep,
                                reason=dec.reason, version=dec.version)
        if dec.status == "undecided":
            return GateDecision(status="sufficient", keep_citation_ids=keep,
                                reason=dec.reason, version=dec.version)
        return GateDecision(status="sufficient", keep_citation_ids=keep,
                            dropped_citation_ids=dropped, reason=dec.reason,
                            version=dec.version)
    return GateDecision(status="sufficient", keep_citation_ids=keep,
                        dropped_citation_ids=dropped,
                        reason=f"保留 {len(keep)} 条与题面有重叠的正文引用")


# ---------------------------------------------------------------------------
# P11 因素 A：证据来源过滤（机械正文归属复核；**默认不注入**）
# ---------------------------------------------------------------------------

#: 因素 A 的版本号（参与候选身份与报表字段）
REGION_FILTER_VERSION = "p11-region-filter-v1"

#: RegionIndex 的判定词表（`src/evaluation/annotation_v2.py` 同一份枚举）
_REGION_KEEP_VERDICT = "body"
_REGION_DROP_VERDICTS = ("exercise_intersecting", "unassigned", "practice_conflict")


@dataclass
class RegionFilterConfig:
    """因素 A 配置。**默认关闭**；未通过配对检查前不得作为现役行为。"""

    enabled: bool = False
    version: str = REGION_FILTER_VERSION
    chunks_path: str | None = None      # v3 **全量** chunk 表（正文 + 习题），只读
    corpus_root: str | None = None      # 教材根（只读；缺省由调用方给）
    adopted: bool = False
    evidence: str = ("P8B v2 机械正文归属复核（RegionIndex）；"
                     "P11 第二步只在影子候选里显式注入，默认路径不调用")


@dataclass
class SourceFilterDecision:
    """一次来源过滤的结果（含逐条台账）。"""

    status: str                          # noop | pass | uncertain
    keep_ids: list[str] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    version: str = REGION_FILTER_VERSION


def build_region_verifier(chunks_path: str, corpus_root: str | None = None):
    """构造 `(file_rel, start, end) -> {verdict, ok, problems, ...}` 判定器。

    只读：`chunks_path`（切分产物）+ 语料（经 `RegionIndex` 的文本层，只读）。
    惰性 import —— `src/llm/*` 不因本模块而在导入期依赖评测侧模块。
    """
    from app.services.rag_engine.evaluation.annotation_v2 import RegionIndex

    index = RegionIndex(chunks_path=chunks_path, corpus_root=corpus_root)

    def _verify(file_rel: str, start: int, end: int) -> dict:
        out = index.classify(file_rel, int(start), int(end))
        return {
            "verdict": str(out.get("verdict")),
            "ok": bool(out.get("ok")),
            "problems": list(out.get("problems") or []),
            "regions": dict(out.get("regions") or {}),
            "practice_conflict_chars": int(out.get("practice_conflict_chars") or 0),
            "unassigned_chars": int(out.get("unassigned_chars") or 0),
            "exercise_chars": int(out.get("exercise_chars") or 0),
            "text_layer_checked": bool(out.get("text_layer_checked")),
        }

    return _verify


def evaluate_sources(spans: list[dict], verifier, *,
                     cfg: RegionFilterConfig | None = None) -> SourceFilterDecision:
    """因素 A：逐区间复核正文归属，丢弃不可核验/非正文者（**只保留 body**）。

    `spans`：[{citation_id, file, char_span}]（服务层的 EvidenceSpan 投影）。
    判定器抛错/缺 file/坐标非法 → 视为**无法核验**并丢弃（保守方向：不放行）。
    """
    cfg = cfg or RegionFilterConfig()
    if not cfg.enabled or verifier is None:
        return SourceFilterDecision(status="noop",
                                    keep_ids=[str(s.get("citation_id")) for s in spans],
                                    reasons=["来源过滤未启用（默认路径不调用）"])
    keep: list[str] = []
    dropped: list[dict] = []
    for s in spans:
        cid = str(s.get("citation_id"))
        file_rel = s.get("file")
        try:
            span = list(s.get("char_span") or [])
            if len(span) != 2 or not file_rel:
                raise ValueError("缺少 file 或 char_span")
            verdict = verifier(str(file_rel), int(span[0]), int(span[1]))
        except Exception as e:                                  # noqa: BLE001
            dropped.append({"citation_id": cid, "file": file_rel,
                            "char_span": list(s.get("char_span") or []),
                            "verdict": "unverifiable",
                            "reasons": [f"正文归属无法核验：{type(e).__name__}: {e}"]})
            continue
        if verdict.get("verdict") == _REGION_KEEP_VERDICT:
            keep.append(cid)
        else:
            dropped.append({
                "citation_id": cid, "file": file_rel,
                "char_span": list(s.get("char_span") or []),
                "verdict": verdict.get("verdict"),
                "reasons": list(verdict.get("problems") or
                                [f"正文归属 verdict={verdict.get('verdict')}（非 body）"]),
            })
    if not keep:
        return SourceFilterDecision(
            status="uncertain", keep_ids=[], dropped=dropped,
            reasons=[f"全部 {len(dropped)} 条候选区间都无法核验为正文 → 结构化降级，"
                     f"不发布任何引用"])
    return SourceFilterDecision(
        status="pass", keep_ids=keep, dropped=dropped,
        reasons=[f"保留 {len(keep)} 条可核验正文区间；丢弃 {len(dropped)} 条"
                 f"（非正文/无法核验）"])


# ---------------------------------------------------------------------------
# P11 候选门禁的**单一决策点**（A → B；服务层只调用这一个函数）
# ---------------------------------------------------------------------------

@dataclass
class CandidateGateResult:
    """一次候选门禁的完整结果（供服务层与报表共用；无判定逻辑）。"""

    status: str                       # noop | pass | insufficient | uncertain
    keep_ids: list[str] = field(default_factory=list)
    source: SourceFilterDecision | None = None
    sufficiency: GateDecision | None = None
    reason: str = ""


def run_candidate_gate(question: str, spans: list[dict], verifier, *,
                       source_cfg: RegionFilterConfig | None = None,
                       suff_cfg: SufficiencyConfig | None = None,
                       ) -> CandidateGateResult:
    """串联因素 A（来源过滤）与因素 B（p8h-suff-v1 充分性判定）。

    顺序固定：**先**来源过滤（不可核验/非正文直接出局，连"相关性"都不再谈），
    **再**对存活区间做题面内容词重叠判定。任一环节全灭 → 结构化降级。
    未注入任何配置 → `noop`（现役路径，不改变任何东西）。
    """
    src_on = bool(source_cfg and source_cfg.enabled)
    suff_on = bool(suff_cfg and suff_cfg.enabled)
    if not src_on and not suff_on:
        return CandidateGateResult(
            status="noop", keep_ids=[str(s.get("citation_id")) for s in spans],
            reason="候选门禁未注入（默认路径）")

    src = evaluate_sources(spans, verifier, cfg=source_cfg) if src_on \
        else SourceFilterDecision(status="noop",
                                  keep_ids=[str(s.get("citation_id")) for s in spans],
                                  reasons=["因素 A 未启用"])
    if src.status == "uncertain":
        return CandidateGateResult(status="uncertain", keep_ids=[], source=src,
                                   reason="；".join(src.reasons))
    kept = [s for s in spans if str(s.get("citation_id")) in set(src.keep_ids)]
    if not suff_on:
        return CandidateGateResult(status="pass", keep_ids=list(src.keep_ids),
                                   source=src, reason="；".join(src.reasons))
    evidence = [{"citation_id": str(s.get("citation_id")),
                 "text": str(s.get("text") or ""),
                 "region": _REGION_KEEP_VERDICT if src_on else
                 str(s.get("region") or _REGION_KEEP_VERDICT)} for s in kept]
    dec = evaluate(question, evidence, cfg=suff_cfg)
    if dec.status == "insufficient":
        return CandidateGateResult(status="insufficient", keep_ids=[], source=src,
                                   sufficiency=dec,
                                   reason=f"{dec.reason}（来源过滤后 {len(kept)} 条全部丢弃）")
    if dec.status == "uncertain":
        return CandidateGateResult(status="uncertain", keep_ids=[], source=src,
                                   sufficiency=dec, reason=dec.reason)
    keep_ids = [cid for cid in [str(s.get("citation_id")) for s in kept]
                if cid in set(dec.keep_citation_ids)]
    return CandidateGateResult(status="pass", keep_ids=keep_ids, source=src,
                               sufficiency=dec,
                               reason="；".join([*src.reasons, dec.reason]))
