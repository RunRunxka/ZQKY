"""P12 拒答线：**证据定向性门禁** `p12-directedness-v1`（版本化、**默认关闭**、未采用候选）。

为什么需要新机制（而不是调 `min_overlap`）
------------------------------------------
P11 的因素 B（`p8h-suff-v1`）用的是「题面内容词 ∩ 被引区间内容词」的**原始计数 ≥ 1**。
实测在 23 条反例上**零效果**：`OOC-1` 覆盖信号 0.43、`F-QA-2` 0.75 都判 `sufficient`，
因为「…的」「时间」「分析」这类**高文档频次泛化词**在任何教材区间里都会出现，
计数 ≥1 恒真。**改变阈值仍是同一机制**，不构成新机制。

本模块换的是机制：**证据对本题的区分度**。做法是把题面内容词按**文档频次**分成
「特有词」（DF ≤ `df_max_ratio` × 正文块数）与「泛化词」，只统计**特有词**在被引区间里
出现了多少 —— 即「本题真正在问的东西，被引区间里有没有讲」。

* 这是**比率**判据（`|shared_distinctive| / |distinctive|`），不是计数；
* 泛化词**不参与**判定（计数 ≥1 的机制恰恰是被泛化词骗了）；
* 无任何特有词（题面全是泛化词）时**不降级**（`undecided`，保守方向：避免误拒）。

产物口径
--------
判定结果把「为什么该拒」分成四类，**分开记录、互斥、不合并成单一计数**：
  `no_evidence` / `invalid_source` / `irrelevant_evidence` / `unsupported_by_evidence`。

**默认关闭**：`enabled=False` 时本模块不被任何现役路径调用，A0 行为逐字节不变；
本批**不**据此切换默认，也不宣布拒答已修复。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

GATE_VERSION = "p12-directedness-v1"
DF_TABLE_VERSION = "p12-df-active-p8d-v3-body-v1"

_STOP = frozenset(("的", "了", "是", "在", "和", "与", "或", "为", "有", "这", "那",
                   "什么", "多少", "哪些", "如何", "怎么", "请问", "下列", "以上",
                   "正确", "说法", "关于"))
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")
_ASCII_WORD = re.compile(r"[A-Za-z]{2,}")


def content_terms(text: str) -> set[str]:
    """题面/区间的**内容词**：中文二元组 + 英文词（去停用词）。

    与 `src/llm/sufficiency.py` 同口径（同一份 bigram 定义），但**用途不同**：
    这里只用来算 DF，不作为计数阈值。
    """
    body = str(text or "")
    out: set[str] = {w.lower() for w in _ASCII_WORD.findall(body)}
    for run in _CJK_RUN.findall(body):
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg not in _STOP:
                out.add(bg)
    return out


@dataclass
class DirectednessConfig:
    """机制配置。**默认关闭**；阈值在 `P12-PREREG/refusal_mechanism.json` 登记后不得事后调整。"""

    enabled: bool = False
    version: str = GATE_VERSION
    #: 「特有词」的 DF 上限 = `df_max_ratio` × 正文块数（本批：0.0005 × 11,608 ≈ 5）
    df_max_ratio: float = 0.0005
    #: 特有词覆盖率下限：`|shared| / |distinctive| >= required_share`
    required_share: float = 0.5
    #: 至少要有这么多特有词被命中（避免 1/1 = 1.0 的样本过少假通过）
    min_shared: int = 1
    #: DF 表（`{term: df}`）与正文块数；由调用方注入（服务路径不自己读盘）
    df_table: dict | None = None
    n_body_chunks: int = 0
    df_table_version: str = DF_TABLE_VERSION
    adopted: bool = False
    evidence: str = ("P11 §6·11·1：`min_overlap=1` 在 23 条反例上零效果；"
                     "本候选改用特有词覆盖率（不同机制），默认关闭")

    @property
    def df_max(self) -> int:
        return max(1, int(self.df_max_ratio * max(0, self.n_body_chunks)))


@dataclass
class DirectednessDecision:
    status: str                       # noop | sufficient | insufficient | undecided
    reason: str
    distinctive_terms: list[str] = field(default_factory=list)
    shared_terms: list[str] = field(default_factory=list)
    coverage: float | None = None
    df_max: int | None = None
    n_evidence_considered: int = 0
    version: str = GATE_VERSION
    cause: str = ""                   # 四类之一（no_evidence/invalid_source/
                                      # irrelevant_evidence/unsupported_by_evidence）


def build_df_table(chunks_path: str | Path, *, out_path: str | Path | None = None) -> dict:
    """从**正文索引**构建词项文档频次表（只读；可落盘缓存）。"""
    from app.services.rag_engine.contracts import read_jsonl
    df: dict[str, int] = {}
    n = 0
    for r in read_jsonl(chunks_path):
        n += 1
        for t in content_terms(r.get("text") or ""):
            df[t] = df.get(t, 0) + 1
    payload = {"version": DF_TABLE_VERSION, "n_body_chunks": n,
               "source": str(chunks_path).replace("\\", "/"), "df": df}
    if out_path:
        Path(out_path).write_text(json.dumps(payload, ensure_ascii=False) + "\n",
                                  encoding="utf-8", newline="\n")
    return payload


def evaluate_directedness(question: str, evidence_texts: list[str], *,
                          cfg: DirectednessConfig | None = None) -> DirectednessDecision:
    """按**特有词覆盖率**判定证据是否对题。

    `evidence_texts`：进包候选区间的原文（**已通过来源过滤的**）。
    """
    cfg = cfg or DirectednessConfig()
    if not cfg.enabled:
        return DirectednessDecision(status="noop", reason="门禁默认关闭（未采用候选）")
    if not evidence_texts:
        return DirectednessDecision(status="insufficient", cause="no_evidence",
                                    reason="证据为空：结构化降级，不硬答")
    if not cfg.df_table:
        return DirectednessDecision(status="undecided",
                                    reason="缺 DF 表 → 不判定（保守，避免误拒）")
    df_max = cfg.df_max
    q_terms = content_terms(question)
    distinctive = sorted(t for t in q_terms if cfg.df_table.get(t, 0) <= df_max)
    ev_terms: set[str] = set()
    for t in evidence_texts:
        ev_terms |= content_terms(t)
    shared = sorted(t for t in distinctive if t in ev_terms)
    if not distinctive:
        return DirectednessDecision(
            status="undecided", df_max=df_max, n_evidence_considered=len(evidence_texts),
            reason=("题面无特有词（全部为高文档频次泛化词）→ 无区分度可判，"
                    "保守不降级（避免误拒）"))
    coverage = len(shared) / len(distinctive)
    ok = coverage >= cfg.required_share and len(shared) >= cfg.min_shared
    return DirectednessDecision(
        status="sufficient" if ok else "insufficient",
        cause="" if ok else "unsupported_by_evidence",
        distinctive_terms=distinctive[:40], shared_terms=shared[:40],
        coverage=coverage, df_max=df_max, n_evidence_considered=len(evidence_texts),
        reason=(f"特有词（DF≤{df_max}，共 {len(distinctive)} 个）覆盖率 "
                f"{coverage:.3f} vs 下限 {cfg.required_share}"
                + ("；命中 " + "、".join(shared[:8]) if shared else "；一个都没命中")
                + ("→ 证据对题" if ok else "→ 证据不对题，结构化降级")))


def classify_cause(*, n_citations: int, n_non_body: int, n_distinctive: int,
                   n_shared_distinctive: int) -> str:
    """四类互斥的失败归因（**分开记录**，不合并）。"""
    if n_citations == 0:
        return "no_evidence"
    if n_non_body >= n_citations:
        return "invalid_source"
    if n_distinctive and n_shared_distinctive == 0:
        return "unsupported_by_evidence"
    if n_distinctive == 0:
        return "unsupported_by_evidence"
    return "irrelevant_evidence"


# ---------------------------------------------------------------------------
# P12 候选 E：**语料覆盖**（识别语料外问题；与 D 机制不同，不看被引区间）
# ---------------------------------------------------------------------------

CORPUS_COVERAGE_VERSION = "p12-corpus-coverage-v1"


@dataclass
class CorpusCoverageConfig:
    """候选 E 配置。**默认关闭**；阈值在 `P12-PREREG/refusal_mechanism_E.json` 登记后不得事后调整。"""

    enabled: bool = False
    version: str = CORPUS_COVERAGE_VERSION
    df_max_ratio: float = 0.0005
    required_share: float = 0.5
    min_distinctive: int = 3
    df_table: dict | None = None
    n_body_chunks: int = 0
    df_table_version: str = DF_TABLE_VERSION
    adopted: bool = False
    evidence: str = ("候选 D 已 FAIL（见 P12-REFUSAL/pairing.json）；本候选改看**全库存在性**，"
                     "默认关闭")

    @property
    def df_max(self) -> int:
        return max(1, int(self.df_max_ratio * max(0, self.n_body_chunks)))


def evaluate_corpus_coverage(question: str, *,
                             cfg: CorpusCoverageConfig | None = None) -> DirectednessDecision:
    """题面的**特有词**在**全库正文索引**中的存在比例。

    与 `evaluate_directedness` 的关键差别：**完全不使用被引区间**——问的是
    「这道题问的东西，整本教材里有没有」，因此不会因为检索段选偏而误杀。
    """
    cfg = cfg or CorpusCoverageConfig()
    if not cfg.enabled:
        return DirectednessDecision(status="noop", reason="门禁默认关闭（未采用候选）",
                                    version=cfg.version)
    if not cfg.df_table:
        return DirectednessDecision(status="undecided", version=cfg.version,
                                    reason="缺 DF 表 → 不判定（保守，避免误拒）")
    df_max = cfg.df_max
    distinctive = sorted(t for t in content_terms(question)
                         if cfg.df_table.get(t, 0) <= df_max)
    if len(distinctive) < cfg.min_distinctive:
        return DirectednessDecision(
            status="undecided", df_max=df_max, version=cfg.version,
            distinctive_terms=distinctive[:40],
            reason=(f"题面特有词仅 {len(distinctive)} 个（< {cfg.min_distinctive}）"
                    "→ 无区分度可判，保守不降级（避免误拒）"))
    present = [t for t in distinctive if cfg.df_table.get(t, 0) > 0]
    coverage = len(present) / len(distinctive)
    ok = coverage >= cfg.required_share
    return DirectednessDecision(
        status="sufficient" if ok else "insufficient",
        cause="" if ok else "unsupported_by_evidence",
        distinctive_terms=distinctive[:40], shared_terms=present[:40],
        coverage=coverage, df_max=df_max, version=cfg.version,
        reason=(f"特有词（DF≤{df_max}，共 {len(distinctive)} 个）中 {len(present)} 个"
                f"在**全库正文**里出现过（{coverage:.3f} vs 下限 {cfg.required_share}）"
                + ("→ 语料内有依据" if ok else "→ 题面特有概念在语料里基本不存在："
                                              "判为语料外/证据不足，结构化降级")))
