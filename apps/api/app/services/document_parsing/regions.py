"""正文 / 习题区划分：交替产出 ``body`` / ``exercise`` 区间，其余为 ``body``。

判定规则（固定、可测试、版本化；改动必须同时更新本说明与测试）：

1. 逐行扫描规范化文本；代码围栏（``` / ~~~）内部的文本不参与判定。
2. **标记必须是"标题行"**（不是正文里出现过该词）：
   - 该行要么是 Markdown 标题（``#``–``######`` 开头），要么是**短行**（去首尾空白后 ≤30 码点）；
   - 去掉 ``#`` 前缀与列表编号（``1.`` / ``（1）`` / ``一、`` / ``第N节``）后，**以**触发词**开头**才算命中；
   - **目录行不得触发**：含 ``……`` / ``....`` / ``···`` 的行，或"标题 + 空格 + 页码数字"的行（如
     ``第一章 运动的描述 10``、``练习与应用 12``）一律排除；``习题1.1``、``复习参考题 10`` 这类
     "触发词 + 题号"仍算正文标记。
   - 触发词集合（固定）：练习 / 习题 / 复习参考题 / 复习巩固 / 综合运用 / 拓广探索 /
     A组 / B组 / 章末 / 单元小结 / 课后练习 / 总复习。
3. **交替回切**：命中标记 → ``exercise``；之后遇到"正常章节标题"（``1.2 …``、``1.1.1 …``、
   ``第X章/节/单元/篇``、或目录/导引/探究/思考/阅读与思考/小结 等正文标题）→ 回到 ``body``。
   连续命中的标记（如 ``习题1.1`` → ``复习巩固`` → ``综合运用`` → ``拓广探索``）合并成同一段习题区。
4. **健全性守卫**：若习题区占全文 >90%（或存在习题段但正文 <10%），说明规则在该版式上失效：
   在 ``ParsedDocument.warnings`` 如实记一条可读警告，并把结果**降级为整篇 body**，
   绝不用错误的划分去索引（警告随草稿 ``ImportDraftView.warnings`` 展示）。
   v1.4 起再加一条：**正文占比 <50%** 时（检索只取 body 块，正文太少意味着大面积检索不到）
   同样写警告（不降级，保留真实划分），提示人工核对版式。
5. 分块的区语义：**块不跨区**——分块在正文/习题边界处断开，块的 ``region`` 取该块的"自然区"
   （不含为上下文补的重叠尾巴）；``region_for_span`` 的"有重叠即 exercise"仍用于判断原子所属区域。
   这条与规则 4 一起受 ``REGION_RULES_VERSION`` 管理：规则一变指纹就变，必然重新分块，
   不会复用按旧语义算出的 region 标签（v1.4 → ``zqky-region-v3``）。

根因记录：
- v1.0 是"一次性切换 + 标记过宽（目录行 ``复习参考题 1 …… 47`` 也算）"，在真实教材上把整本书标成习题
  （实测 A 版选择性必修第一册 body 仅 0.75%），RAG 实质上只索引了封面。
- v1.2 修正了区间交替，但块级仍用"有重叠即 exercise"，短习题区会把后面的正文吞进 exercise 块：
  块级 body 占比 43.5%–50.2%（A1 冻结候选实测 3 册低于 50% 门槛），被吞的正文检索不到。
  v1.4 用"块不跨区 + 自然区标签"修复覆盖面（修后 58 册全部 ≥50%，见结果卡 v1.4 实测表）。

规则版本（``REGION_RULES_VERSION``）：任何影响区间或块级区域归属的改动都必须递增该常量；它进入
``ChunkPolicy.region_rules_version`` 与分块策略指纹，保证规则变化后必然产生新的 ``chunk_set``，
不会静默复用按旧划分算出的分块集。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

#: 正文/习题划分规则版本；改规则必须递增
#: （v1 = 一次性切换；v2 = 交替划分 + 标题行/TOC 规则；v3 = 块不跨区 + 自然区标签 + 正文占比守卫）
REGION_RULES_VERSION = "zqky-region-v3"
#: 旧（v1.0/v1.1）规则版本，仅用于读取历史 JSON 时补齐字段
LEGACY_REGION_RULES_VERSION = "zqky-region-v1"

EXERCISE_MARKERS: tuple[str, ...] = (
    "练习",
    "习题",
    "复习参考题",
    "复习巩固",
    "综合运用",
    "拓广探索",
    "A组",
    "B组",
    "章末",
    "单元小结",
    "课后练习",
    "总复习",
)

REGION_BODY = "body"
REGION_EXERCISE = "exercise"

#: 判定为"标题行"的短行上限（非 Markdown 标题的候选行）
MAX_MARKER_LINE_CHARS = 30
MAX_SECTION_LINE_CHARS = 30
#: 健全性守卫阈值：习题区占比上限 / 正文占比下限（划分降级）
EXERCISE_RATIO_LIMIT = 0.90
BODY_RATIO_FLOOR = 0.10
#: 正文占比警戒线（v1.4）：低于此值只告警不降级——检索只取 body 块，正文太少等于大面积检索不到
BODY_SHARE_FLOOR = 0.50
#: 降级警告前缀（上层据此识别；文案含实际占比）
DEGRADED_WARNING_PREFIX = "正文/习题划分结果异常"
#: 正文占比偏低警告前缀
LOW_BODY_SHARE_WARNING_PREFIX = "正文占比偏低"

_HEADING_PATTERN = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.*)$")
_FENCE_PREFIXES = ("```", "~~~")
_LIST_PREFIX = re.compile(
    r"^\s*(?:\d+[.．、)]|（\d+）|\(\d+\)|第\s*[一二三四五六七八九十百零〇\d]{1,4}\s*[章节单元篇])\s*"
)
#: 目录行：省略号/点线/中圆点线
_TOC_DOTS = re.compile(r"……|\.{3,}|·{3,}|⋯{2,}")
#: 目录行：标题与页码之间只隔空白（如 ``第一章 运动的描述 10``）
_TRAILING_PAGE = re.compile(r"\s(\d{1,4})$")
#: 正文小节标题形态：1.2 / 1.1.1 / "1 质点 参考系" / 第一章·节·单元·篇
_SECTION_PATTERNS = (
    re.compile(r"^\d{1,3}(?:[.．]\d{1,3})+(?:[.．、]|\s)\S"),
    re.compile(r"^\d{1,3}\s+\S"),
    re.compile(r"^第\s*[一二三四五六七八九十百零〇\d]{1,4}\s*[章节单元篇]"),
)
#: 正文类标题关键词（命中即回到 body；不得与 EXERCISE_MARKERS 重叠或近义冲突）
_SECTION_KEYWORDS: tuple[str, ...] = (
    "目录",
    "本册导引",
    "导引",
    "序言",
    "致同学们",
    "科学家访谈",
    "阅读与思考",
    "科学漫步",
    "探究",
    "思考",
    "问题",
    "实验",
    "课题研究",
    "小结",
    "本章小结",
    "附录",
    "后记",
    "参考文献",
    "索引",
    "结语",
)
_NUMBERING_CHARS = frozenset("0123456789.．、()（） \t")


@dataclass(frozen=True)
class RegionSpan:
    region: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class RegionReport:
    """划分结果与自查信息；``degraded`` 为 True 时 ``spans`` 已降级为整篇 body。"""

    spans: list[RegionSpan]
    warnings: list[str]
    exercise_ratio: float
    body_ratio: float
    exercise_span_count: int
    marker_hits: int
    degraded: bool
    #: v1.4：正文占比低于警戒线（已告警，未降级）
    low_body_share: bool = False


def iter_lines(text: str):
    """按行产出 ``(start, end, line)``；end 不含换行符。"""
    start = 0
    length = len(text)
    while start <= length:
        newline = text.find("\n", start)
        if newline == -1:
            end = length
        else:
            end = newline
        yield start, end, text[start:end]
        if newline == -1:
            return
        start = newline + 1


def _title_of(stripped: str) -> tuple[str, bool]:
    """返回 ``(标题文本, 是否 Markdown 标题)``。"""
    heading = _HEADING_PATTERN.match(stripped)
    if heading is not None:
        return heading.group("title").strip(), True
    return stripped, False


def _trigger_match(text: str) -> str | None:
    normalized = _LIST_PREFIX.sub("", text).strip()
    if not normalized:
        return None
    for trigger in EXERCISE_MARKERS:
        if normalized.startswith(trigger):
            return trigger
    return None


def _is_marker_with_numbering(text: str) -> bool:
    """``复习参考题 10`` / ``习题 1.1`` 这类"触发词 + 纯题号"（不是目录条目）。"""
    normalized = _LIST_PREFIX.sub("", text).strip()
    if not normalized:
        return False
    for trigger in EXERCISE_MARKERS:
        if normalized == trigger:
            return True
        if normalized.startswith(trigger):
            rest = normalized[len(trigger):]
            if rest and all(character in _NUMBERING_CHARS for character in rest):
                return True
    return False


def looks_like_toc_line(title: str) -> bool:
    """目录行：省略号/点线，或"标题 + 页码"（排除 触发词+题号 的正文标记行）。"""
    if _TOC_DOTS.search(title):
        return True
    match = _TRAILING_PAGE.search(title)
    if match is None:
        return False
    head = title[: match.start()].strip()
    if not head:
        return True
    return not _is_marker_with_numbering(head)


def is_exercise_marker_line(line: str) -> bool:
    """该行是否为习题区起始标题（Markdown 标题，或 ≤30 码点的短行）。"""
    stripped = line.strip()
    if not stripped:
        return False
    title, is_heading = _title_of(stripped)
    if not title:
        return False
    if not is_heading and len(stripped) > MAX_MARKER_LINE_CHARS:
        return False
    if looks_like_toc_line(title):
        return False
    return _trigger_match(title) is not None


def is_section_heading_line(line: str) -> bool:
    """该行是否为"正常章节标题"（命中即从习题区回到正文）。"""
    stripped = line.strip()
    if not stripped:
        return False
    title, is_heading = _title_of(stripped)
    if not title:
        return False
    if not is_heading and len(stripped) > MAX_SECTION_LINE_CHARS:
        return False
    if looks_like_toc_line(title):
        return False
    if any(pattern.match(title) for pattern in _SECTION_PATTERNS):
        return True
    return any(title.startswith(keyword) for keyword in _SECTION_KEYWORDS)


def _scan_regions(text: str) -> tuple[list[RegionSpan], int]:
    """按行状态机产出交替区间；返回 (spans, 标记命中次数)。"""
    spans: list[RegionSpan] = []
    current = REGION_BODY
    run_start = 0
    marker_hits = 0
    in_fence = False
    fence_token: str | None = None
    for start, _end, line in iter_lines(text):
        stripped = line.strip()
        if stripped.startswith(_FENCE_PREFIXES):
            token = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_token = token
            elif token == fence_token:
                in_fence = False
                fence_token = None
            continue
        if in_fence:
            continue
        if is_exercise_marker_line(line):
            marker_hits += 1
            next_region = REGION_EXERCISE
        elif is_section_heading_line(line):
            next_region = REGION_BODY
        else:
            next_region = None
        if next_region is not None and next_region != current:
            if start > run_start:
                spans.append(RegionSpan(region=current, char_start=run_start, char_end=start))
            run_start = start
            current = next_region
    if run_start < len(text):
        spans.append(RegionSpan(region=current, char_start=run_start, char_end=len(text)))
    elif not spans:
        spans.append(RegionSpan(region=current, char_start=0, char_end=len(text)))
    return spans, marker_hits


def _degraded_warning(exercise_ratio: float, body_ratio: float) -> str:
    return (
        f"{DEGRADED_WARNING_PREFIX}：习题区占 {exercise_ratio:.0%}（正文 {body_ratio:.0%}），"
        "已按正文处理以便检索；请人工核对教材版式后重新导入。"
    )


def _low_body_share_warning(body_ratio: float, exercise_ratio: float) -> str:
    return (
        f"{LOW_BODY_SHARE_WARNING_PREFIX}：正文仅 {body_ratio:.0%}（习题区 {exercise_ratio:.0%}，"
        f"低于 {BODY_SHARE_FLOOR:.0%} 门槛），检索只取正文块，可能有正文检索不到；"
        "请人工核对教材版式（本次保留实际划分）。"
    )


def analyze_regions(text: str) -> RegionReport:
    """划分正文/习题区并做健全性自查；空文本返回空区间与无警告。"""
    if not text:
        return RegionReport(
            spans=[],
            warnings=[],
            exercise_ratio=0.0,
            body_ratio=1.0,
            exercise_span_count=0,
            marker_hits=0,
            degraded=False,
            low_body_share=False,
        )
    spans, marker_hits = _scan_regions(text)
    total = len(text)
    exercise_chars = sum(
        span.char_end - span.char_start for span in spans if span.region == REGION_EXERCISE
    )
    exercise_spans = [span for span in spans if span.region == REGION_EXERCISE]
    exercise_ratio = exercise_chars / total
    body_ratio = 1.0 - exercise_ratio
    degraded = exercise_ratio > EXERCISE_RATIO_LIMIT or (
        bool(exercise_spans) and body_ratio < BODY_RATIO_FLOOR
    )
    warnings: list[str] = []
    low_body_share = False
    if degraded:
        warnings.append(_degraded_warning(exercise_ratio, body_ratio))
        spans = [RegionSpan(region=REGION_BODY, char_start=0, char_end=total)]
    elif body_ratio < BODY_SHARE_FLOOR:
        # 划分本身可用，但正文太少：如实告警（不降级，保留真实习题区）
        low_body_share = True
        warnings.append(_low_body_share_warning(body_ratio, exercise_ratio))
    return RegionReport(
        spans=spans,
        warnings=warnings,
        exercise_ratio=exercise_ratio,
        body_ratio=body_ratio,
        exercise_span_count=len(exercise_spans),
        marker_hits=marker_hits,
        degraded=degraded,
        low_body_share=low_body_share,
    )


def split_regions(parsed: Any) -> list[RegionSpan]:
    """``parsed`` 需有 ``normalized_text``；返回已过健全性守卫的区间表。"""
    return analyze_regions(parsed.normalized_text).spans


def region_at(regions: Sequence[RegionSpan], position: int) -> str:
    """取该字符位置所在的区；落在区间缝隙（区间之间的换行）时取前一个区间。"""
    previous = REGION_BODY
    for span in regions:
        if position < span.char_start:
            break
        previous = span.region
    return previous


def region_for_span(regions: Sequence[RegionSpan], char_start: int, char_end: int) -> str:
    """块的区：与习题区有任何重叠即判为 ``exercise``（保守方向）。

    宁可把跨界块整体排除出正文检索，也不让习题文本以 ``body`` 进入知识点检索；
    只与正文重叠的块一律 ``body``。
    """
    for span in regions:
        if span.region != REGION_EXERCISE:
            continue
        if span.char_start < char_end and span.char_end > char_start:
            return REGION_EXERCISE
    return REGION_BODY
