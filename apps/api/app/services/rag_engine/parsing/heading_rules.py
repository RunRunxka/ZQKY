"""标题分类规则：configs/heading_rules.yaml 的加载与 classify()。

规则表是结构解析的核心，禁止把正则硬编码进模块（PROJECT_GUIDE D3）。
本模块的行为与 prototype/section_index.py 的 classify() 逐行为一致，
等价性由 src/verify.py --prototype-equivalence 在全语料上验证。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.services.rag_engine.contracts import REGION_BODY, REGION_EXERCISE

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = _ROOT / "configs" / "heading_rules.yaml"


@dataclass
class HeadingRules:
    chapter: list[re.Pattern]
    section: list[re.Pattern]
    dot_section: re.Pattern
    bare_section: re.Pattern
    bare_section_guard: re.Pattern
    practice: tuple[str, ...]
    columns: tuple[str, ...]
    noise_chars: frozenset[str]
    sub_max_chars: int
    sentence_end: re.Pattern

    chunk: dict = field(default_factory=dict)
    subjects: list[dict] = field(default_factory=list)
    eval_groups: dict[str, str] = field(default_factory=dict)
    corpus_root: str = ""
    #: 配置版本（1 = 历史/原型等价；2 = P8D 泄漏治理；3 = +参考选题；4 = +章末复习区窄规则）
    version: int = 1
    #: 剥离编号/题号前缀的正则（v2）；None 表示走 v1 行为
    numbering_strip: re.Pattern | None = None
    #: 练习类「裸标题」正则与前缀词（v2）
    practice_patterns: tuple[re.Pattern, ...] = ()
    practice_words: tuple[str, ...] = ()
    #: 章末复习区锚点（v4；空 = 规则不生效）。见 src/parsing/region_rules.py
    chapter_review_anchors: tuple[str, ...] = ()


def load_rules(path: str | Path | None = None) -> HeadingRules:
    cfg = yaml.safe_load(Path(path or DEFAULT_CONFIG).read_text(encoding="utf-8"))
    hr = cfg["heading_rules"]
    ns = hr.get("numbering_strip")
    return HeadingRules(
        chapter=[re.compile(p) for p in hr["chapter"]],
        section=[re.compile(p) for p in hr["section"]],
        dot_section=re.compile(hr["dot_section"]),
        bare_section=re.compile(hr["bare_section"]),
        bare_section_guard=re.compile(hr["bare_section_guard"]),
        practice=tuple(hr["practice"]),
        columns=tuple(hr["columns"]),
        chapter_review_anchors=tuple(cfg.get("chapter_review_anchors") or ()),
        noise_chars=frozenset(hr["noise_chars"]),
        sub_max_chars=int(hr["sub_max_chars"]),
        sentence_end=re.compile(hr["sentence_end"]),
        chunk=dict(cfg["chunk"]),
        subjects=list(cfg["subjects"]),
        eval_groups=dict(cfg["eval_groups"]),
        corpus_root=cfg["corpus_root"],
        version=int(cfg.get("version", 1)),
        numbering_strip=re.compile(ns) if ns else None,
        practice_patterns=tuple(re.compile(p) for p in hr.get("practice_patterns", ())),
        practice_words=tuple(hr.get("practice_words", ())),
    )


def bare_heading(text: str, rules: HeadingRules) -> str:
    """剥离编号/题号前缀后的**裸标题**（v2）。

    `1 选择题` → `选择题`；`03 复习题` → `复习题`；`一、选择题` → `选择题`；
    `13. 填空题` → `填空题`；`1.1 集合的概念` → `集合的概念`（判定不受影响）。
    v1 配置（无 `numbering_strip`）直接返回原文——保持历史行为。
    """
    t = text.strip()
    if rules.numbering_strip is None:
        return t
    return rules.numbering_strip.sub("", t).strip() or t


def is_practice_title(text: str, rules: HeadingRules) -> bool:
    """练习类标题判定（**v2 的核心**）。

    三层并集，任一命中即 practice：
      ① v1 的 `practice` 前缀表（保留兼容）；
      ② v2 的 `practice_patterns` 正则（裸标题，如 `A组` / `复习题 5-1`）；
      ③ v2 的 `practice_words` 裸标题前缀（选择题/填空题/…）。
    ②③ 只对**裸标题**匹配，因此 `1 选择题`、`03 复习题`、`一、选择题` 都能命中，
    而 `1 曲线运动`（物理节标题）不会。
    """
    t = text.strip()
    bare = bare_heading(t, rules)
    if any(t.startswith(p) or bare.startswith(p) for p in rules.practice):
        return True
    if any(pat.match(bare) for pat in rules.practice_patterns):
        return True
    return any(bare.startswith(w) for w in rules.practice_words)


def classify(text: str, rules: HeadingRules) -> tuple[int | None, str]:
    """返回 (层级, 类型)。层级 None 表示它不是结构节点。

    类型：chapter / section / practice / column / noise / sub。

    **v2 顺序**：noise → practice → chapter → section → dot_section → bare_section
    → columns → sub。练习类判定先行是 v2 的关键修复：v1 里 `1 选择题` 被
    `bare_section` 抢先判成 level=2/section，整节因此标成 region=body 进入正文索引。
    """
    t = text.strip()
    if not t or set(t) <= rules.noise_chars:
        return None, "noise"
    if is_practice_title(t, rules):
        return None, "practice"
    for pat in rules.chapter:
        if pat.match(t):
            return 1, "chapter"
    for pat in rules.section:
        if pat.match(t):
            return 2, "section"
    m = rules.dot_section.match(t)
    if m:
        return 1 + m.group(1).count("."), "section"
    if rules.bare_section.match(t) and not rules.bare_section_guard.match(t):
        return 2, "section"
    for c in rules.columns:
        if t.startswith(c):
            return None, "column"
    if len(t) > rules.sub_max_chars or rules.sentence_end.search(t):
        return None, "noise"        # 误判成标题的正文
    return None, "sub"              # 无编号子标题（列举法、交集…）


def is_practice(text: str, kind: str, rules: HeadingRules) -> bool:
    return kind == "practice" or is_practice_title(text, rules)


def region_of(text: str, kind: str, rules: HeadingRules) -> str:
    return REGION_EXERCISE if is_practice(text, kind, rules) else REGION_BODY
