"""可读文本投影：从封存原文派生清洗文本，**不改原文**（RAG-QUALITY v1.1/v1.2 · B0）。

三种文本必须区分（PLAN §2.2）：封存原文不可变；清洗文本按清洗版本派生；简短回答由回答
策略生成。本模块只负责第二种，产出 :class:`TextProjection`：清洗后的文本、清洗码点到
**原文码点**的映射、以及被清除的图片节点数。

清洗规则（PLAN §3.1，逐条对应）：

===================================================== ======================================
输入                                                  处理
===================================================== ======================================
``![](images/hash.jpg)``                              删除整个图片节点
``![加速度与力关系图](…)``                              保留有意义的说明文字，删除地址
引用式图片 ``![说明][fig1]``                            解析引用定义后按同样规则处理
图片引用定义                                          仅被图片使用时删除；文字链接仍使用时保留
``<img>`` / ``<picture>``                             删除图片元素与地址，保留有意义的 alt
包裹图片的外层链接                                     内容只有图片与空白时整体删除
空 alt、文件名、路径、长哈希、泛化占位词                 不作为说明文字保留
图片下方正文图注                                       保留（不是图片语法，原样保留）
公式、表格、正文、普通文字链接                           保留
代码围栏、行内代码中的字面示例                           不误当成真实图片节点
清洗后仅剩空白的片段                                   文本为空串，调用方据此跳过
被分块边界截断的标签残片（v2 起）                        地址不进入清洗文本，残片计入图片数
===================================================== ======================================

**有限归一**：只清除删除后残留的空行与行尾空白（:func:`normalize_blank_lines`），
规则固定为——

1. 每行去掉行尾空白（空格、制表符、``\\r``；CRLF 因此归一为 LF）；
2. 连续空行折叠为一个空行；
3. 文首、文末的空行整段删除（不留尾随换行）。

**不压缩正文空白、不重排内容、不改写任何保留下来的字符。**

**版本与分派**（规则一变必须换版本号：``textProjectionVersion`` 参与分块指纹，
否则会出现「同指纹、不同索引文本」）：

- ``raw-v0``：原样返回，历史指纹与历史引用不变；
- ``rag-readable-v1``：图片节点清洗，**不清洗**被截断的标签残片（历史数据按此解释）；
- ``rag-readable-v2``（``TEXT_PROJECTION_VERSION``，当前默认）：v1 + 标签残片清洗。

坐标口径：所有索引都是 Python ``str`` 下标（Unicode 码点），不是 UTF-8 字节、也不是
前端 UTF-16 码元。``absolute_start`` 把切片坐标平移为全文坐标（:attr:`SourceSegment.raw_start`
等全部加上它），B1/B2 依赖该语义做原文定位。它是非负整数，非法时抛 ``ValueError``
（编程错误，不占业务错误码）。

本模块是纯函数：无 I/O、无网络、无线程、无全局可变状态、无模型调用。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import AppError
from app.services.text_projection.scanner import RemovalPlan, scan_document

TEXT_PROJECTION_VERSION = "rag-readable-v2"
READABLE_V1_TEXT_PROJECTION_VERSION = "rag-readable-v1"
LEGACY_TEXT_PROJECTION_VERSION = "raw-v0"

#: 版本历史（规则一变必须换版本号，否则分块指纹与索引文本会脱钩）：
#: - ``raw-v0``：原样返回（历史指纹与历史引用）；
#: - ``rag-readable-v1``：图片 Markdown / HTML 节点清洗；**不清洗被截断的标签残片**；
#: - ``rag-readable-v2``：在 v1 基础上清洗被分块边界截断的标签残片
#:   （``src="images/….jpg"/>…``、``<img src="…"``），地址同样不进入清洗文本。

SEGMENT_KIND_KEPT = "kept"
SEGMENT_KIND_ALT_KEPT = "alt_kept"
SEGMENT_KIND_REMOVED = "removed"
SEGMENT_KINDS = frozenset({SEGMENT_KIND_KEPT, SEGMENT_KIND_ALT_KEPT, SEGMENT_KIND_REMOVED})

_TRAILING_WHITESPACE = " \t\r"


@dataclass(frozen=True)
class SourceSegment:
    """清洗文本的一段与原文的一段之间的对应关系。

    - ``kind="kept"`` / ``"alt_kept"``：清洗文本逐字来自原文区间（长度相同），
      ``alt_kept`` 表示该文字原本是图片节点的 alt 说明；
    - ``kind="removed"``：原文区间被清除，对应的清洗区间为空。

    整份投影里，``raw_*`` 区间铺满原文、``clean_*`` 区间铺满清洗文本，且两者同序。
    """

    clean_start: int
    clean_end: int
    raw_start: int
    raw_end: int
    kind: str

    def references_original_codepoint_offsets(self) -> bool:
        """本段是否把清洗坐标锚定在原文码点坐标上（可直接用于回原定位）。"""
        if self.kind not in SEGMENT_KINDS:
            return False
        if self.raw_start < 0 or self.raw_end < self.raw_start:
            return False
        if self.clean_start < 0 or self.clean_end < self.clean_start:
            return False
        if self.kind == SEGMENT_KIND_REMOVED:
            return self.clean_start == self.clean_end
        return (self.clean_end - self.clean_start) == (self.raw_end - self.raw_start)


@dataclass(frozen=True)
class TextProjection:
    """一次投影的结果；``text`` 是派生文本，原文本身不在本对象里。"""

    version: str
    text: str
    source_segments: tuple[SourceSegment, ...]
    removed_image_count: int


@dataclass(frozen=True)
class Replacement:
    """一段待替换的原文区间。

    ``replacement`` 为空表示整段删除；非空时必须给出它在原文里的**逐字来源**
    ``source_start``/``source_end``（图片说明文字就属于这种：只删地址、留文字）。
    """

    raw_start: int
    raw_end: int
    replacement: str = ""
    source_start: int | None = None
    source_end: int | None = None


@dataclass(frozen=True)
class MappedText:
    """替换（或归一）之后的文本及其到原文的映射；归一前的中间结果。"""

    text: str
    segments: tuple[SourceSegment, ...]


def known_projection_versions() -> frozenset[str]:
    """本模块认识的清洗版本；未知版本必须显式报错，不得套用新规则。"""
    return frozenset(
        {
            TEXT_PROJECTION_VERSION,
            READABLE_V1_TEXT_PROJECTION_VERSION,
            LEGACY_TEXT_PROJECTION_VERSION,
        }
    )


def project_by_version(raw: str, version: str, *, absolute_start: int = 0) -> TextProjection:
    """按清洗版本投影。

    - ``rag-readable-v2``（当前默认）：v1 规则 + 被截断标签残片清洗；
    - ``rag-readable-v1``：仅图片节点清洗（历史数据按此解释，必须继续可读）；
    - ``raw-v0``：原样返回。

    未知版本抛 ``AppError(code="UNKNOWN_TEXT_PROJECTION_VERSION", status_code=422)``。
    """
    if version == LEGACY_TEXT_PROJECTION_VERSION:
        return _legacy_projection(raw, absolute_start=absolute_start)
    if version == READABLE_V1_TEXT_PROJECTION_VERSION:
        return _project_readable(
            raw, version=version, include_image_fragments=False, absolute_start=absolute_start
        )
    if version == TEXT_PROJECTION_VERSION:
        return _project_readable(
            raw, version=version, include_image_fragments=True, absolute_start=absolute_start
        )
    raise AppError(
        f"未知的文本清洗版本：{version}",
        code="UNKNOWN_TEXT_PROJECTION_VERSION",
        status_code=422,
    )


def project_readable(raw: str, *, absolute_start: int = 0) -> TextProjection:
    """派生可读文本（当前版本 ``rag-readable-v2``）。

    清除图片 Markdown/HTML 与被截断的标签残片，保留公式、表格、正文与图注；
    ``rag-readable-v1`` 的历史文本请走 :func:`project_by_version`。
    """
    return _project_readable(
        raw,
        version=TEXT_PROJECTION_VERSION,
        include_image_fragments=True,
        absolute_start=absolute_start,
    )


def _project_readable(
    raw: str, *, version: str, include_image_fragments: bool, absolute_start: int
) -> TextProjection:
    _require_text(raw, "raw")
    _validate_absolute_start(absolute_start)
    scan = scan_document(raw, include_image_fragments=include_image_fragments)
    mapped = apply_replacements_with_source_mapping(
        raw,
        _replacements_from_plans(raw, scan.plans),
        absolute_start=absolute_start,
    )
    normalized = normalize_blank_lines_only(mapped)
    return TextProjection(
        version=version,
        text=normalized.text,
        source_segments=normalized.segments,
        removed_image_count=sum(plan.image_count for plan in scan.plans),
    )


def _legacy_projection(raw: str, *, absolute_start: int) -> TextProjection:
    """``raw-v0``：原样返回，不做任何归一，保证历史指纹与引用不变。"""
    _require_text(raw, "raw")
    _validate_absolute_start(absolute_start)
    identity = SourceSegment(
        clean_start=0,
        clean_end=len(raw),
        raw_start=absolute_start,
        raw_end=absolute_start + len(raw),
        kind=SEGMENT_KIND_KEPT,
    )
    return TextProjection(
        version=LEGACY_TEXT_PROJECTION_VERSION,
        text=raw,
        source_segments=(identity,),
        removed_image_count=0,
    )


def _replacements_from_plans(raw: str, plans: tuple[RemovalPlan, ...]) -> list[Replacement]:
    """把待清除区间展开成替换：删除区与「保留说明文字」的逐字来源。"""
    replacements: list[Replacement] = []
    for plan in plans:
        cursor = plan.start
        for kept_start, kept_end in plan.kept_spans:
            if kept_start > cursor:
                replacements.append(Replacement(cursor, kept_start, ""))
            replacements.append(
                Replacement(
                    kept_start,
                    kept_end,
                    raw[kept_start:kept_end],
                    source_start=kept_start,
                    source_end=kept_end,
                )
            )
            cursor = kept_end
        if cursor < plan.end:
            replacements.append(Replacement(cursor, plan.end, ""))
    return replacements


def apply_replacements_with_source_mapping(
    raw: str, replacements: list[Replacement] | tuple[Replacement, ...], *, absolute_start: int = 0
) -> MappedText:
    """应用替换并保留原文映射；替换区间必须有序、互不重叠。"""
    _require_text(raw, "raw")
    _validate_absolute_start(absolute_start)
    pieces = _build_pieces(raw, replacements)
    text_parts: list[str] = []
    segments: list[SourceSegment] = []
    clean_cursor = 0
    for raw_start, raw_end, clean_text, kind in pieces:
        if kind == SEGMENT_KIND_REMOVED:
            if raw_end > raw_start:
                segments.append(
                    SourceSegment(
                        clean_start=clean_cursor,
                        clean_end=clean_cursor,
                        raw_start=raw_start + absolute_start,
                        raw_end=raw_end + absolute_start,
                        kind=SEGMENT_KIND_REMOVED,
                    )
                )
            continue
        piece_text = raw[raw_start:raw_end] if clean_text is None else clean_text
        text_parts.append(piece_text)
        segments.append(
            SourceSegment(
                clean_start=clean_cursor,
                clean_end=clean_cursor + len(piece_text),
                raw_start=raw_start + absolute_start,
                raw_end=raw_end + absolute_start,
                kind=kind,
            )
        )
        clean_cursor += len(piece_text)
    return MappedText(text="".join(text_parts), segments=_merge_removed_segments(segments))


def _build_pieces(
    raw: str, replacements: list[Replacement] | tuple[Replacement, ...]
) -> list[tuple[int, int, str | None, str]]:
    """把原文切成有序、铺满、互不重叠的片段；``clean_text=None`` 表示逐字保留。"""
    ordered = sorted(replacements, key=lambda item: (item.raw_start, item.raw_end))
    pieces: list[tuple[int, int, str | None, str]] = []
    previous_end = 0
    for replacement in ordered:
        _validate_replacement(raw, replacement)
        if replacement.raw_start < previous_end:
            raise ValueError("替换区间重叠，拒绝生成可能错位的映射。")
        if replacement.raw_start > previous_end:
            pieces.append((previous_end, replacement.raw_start, None, SEGMENT_KIND_KEPT))
        if replacement.replacement:
            assert replacement.source_start is not None and replacement.source_end is not None
            pieces.append(
                (replacement.raw_start, replacement.source_start, "", SEGMENT_KIND_REMOVED)
            )
            pieces.append(
                (
                    replacement.source_start,
                    replacement.source_end,
                    replacement.replacement,
                    SEGMENT_KIND_ALT_KEPT,
                )
            )
            pieces.append(
                (replacement.source_end, replacement.raw_end, "", SEGMENT_KIND_REMOVED)
            )
        else:
            pieces.append((replacement.raw_start, replacement.raw_end, "", SEGMENT_KIND_REMOVED))
        previous_end = replacement.raw_end
    if previous_end < len(raw):
        pieces.append((previous_end, len(raw), None, SEGMENT_KIND_KEPT))
    if not pieces:
        pieces.append((0, 0, "", SEGMENT_KIND_KEPT))
    return pieces


def _validate_replacement(raw: str, replacement: Replacement) -> None:
    if replacement.raw_start < 0 or replacement.raw_end > len(raw):
        raise ValueError("替换区间越界。")
    if replacement.raw_start >= replacement.raw_end:
        raise ValueError("替换区间必须非空。")
    if not replacement.replacement:
        if replacement.source_start is not None or replacement.source_end is not None:
            raise ValueError("删除型替换不应带来源区间。")
        return
    if replacement.source_start is None or replacement.source_end is None:
        raise ValueError("保留文字必须给出原文来源区间。")
    if not (
        replacement.raw_start <= replacement.source_start <= replacement.source_end <= replacement.raw_end
    ):
        raise ValueError("来源区间必须落在替换区间内。")
    if raw[replacement.source_start : replacement.source_end] != replacement.replacement:
        raise ValueError("保留文字必须与原文逐字一致。")


def normalize_blank_lines(text: str) -> str:
    """有限归一：去行尾空白、折叠连续空行、删文首文末空行；其余字符不动。"""
    _require_text(text, "text")
    keep = _blank_line_keep_mask(text)
    if all(keep):
        return text
    return "".join(char for char, alive in zip(text, keep) if alive)


def normalize_blank_lines_only(mapped: MappedText) -> MappedText:
    """对映射结果做有限归一，并同步收紧每一段到清洗文本的坐标上。"""
    keep = _blank_line_keep_mask(mapped.text)
    if all(keep):
        return mapped
    prefix = [0] * (len(keep) + 1)
    for index, alive in enumerate(keep):
        prefix[index + 1] = prefix[index] + (1 if alive else 0)
    text = "".join(char for char, alive in zip(mapped.text, keep) if alive)
    segments: list[SourceSegment] = []
    for segment in mapped.segments:
        if segment.clean_start == segment.clean_end:
            # 空映射段（删除段）原样保留，只把坐标挪到归一后的位置上
            segments.append(
                SourceSegment(
                    clean_start=prefix[segment.clean_start],
                    clean_end=prefix[segment.clean_start],
                    raw_start=segment.raw_start,
                    raw_end=segment.raw_end,
                    kind=segment.kind,
                )
            )
            continue
        cursor = segment.clean_start
        for run_start, run_end in _kept_runs(keep, segment.clean_start, segment.clean_end):
            if run_start > cursor:
                segments.append(
                    _shifted_segment(segment, cursor, run_start, prefix, SEGMENT_KIND_REMOVED)
                )
            segments.append(
                _shifted_segment(segment, run_start, run_end, prefix, segment.kind)
            )
            cursor = run_end
        if cursor < segment.clean_end:
            segments.append(_shifted_segment(segment, cursor, segment.clean_end, prefix, SEGMENT_KIND_REMOVED))
    return MappedText(text=text, segments=_merge_removed_segments(segments))


def _shifted_segment(
    segment: SourceSegment,
    clean_start: int,
    clean_end: int,
    prefix: list[int],
    kind: str,
) -> SourceSegment:
    """把段内某个子区间映射到归一后的坐标；删除段没有清洗区间。"""
    offset = clean_start - segment.clean_start
    raw_start = segment.raw_start + offset
    raw_end = raw_start + (clean_end - clean_start)
    if kind == SEGMENT_KIND_REMOVED:
        return SourceSegment(
            clean_start=prefix[clean_start],
            clean_end=prefix[clean_start],
            raw_start=raw_start,
            raw_end=raw_end,
            kind=SEGMENT_KIND_REMOVED,
        )
    length = clean_end - clean_start
    return SourceSegment(
        clean_start=prefix[clean_start],
        clean_end=prefix[clean_start] + length,
        raw_start=raw_start,
        raw_end=raw_end,
        kind=kind,
    )


def _kept_runs(keep: list[bool], start: int, end: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        if not keep[cursor]:
            cursor += 1
            continue
        run_end = cursor
        while run_end < end and keep[run_end]:
            run_end += 1
        runs.append((cursor, run_end))
        cursor = run_end
    return runs


def _blank_line_keep_mask(text: str) -> list[bool]:
    """归一保留掩码：``True`` 表示该码点进入清洗文本。"""
    keep = [True] * len(text)
    lines = _iter_line_spans(text)
    for start, end, _ in lines:
        cursor = end
        while cursor > start and text[cursor - 1] in _TRAILING_WHITESPACE:
            cursor -= 1
        for index in range(cursor, end):
            keep[index] = False
    blank = [text[start:end].strip() == "" for start, end, _ in lines]
    content_lines = [index for index, is_blank in enumerate(blank) if not is_blank]
    if not content_lines:
        return [False] * len(text)
    first_content = content_lines[0]
    last_content = content_lines[-1]
    # 文首、文末空行整段删除（含换行，不留尾随换行）
    for index in range(0, lines[first_content][0]):
        keep[index] = False
    for index in range(lines[last_content][1], len(text)):
        keep[index] = False
    # 文内连续空行只保留第一个
    run_started = False
    for index in range(first_content, last_content + 1):
        if not blank[index]:
            run_started = False
            continue
        if not run_started:
            run_started = True
            continue
        start, _, next_start = lines[index]
        _drop(keep, start, next_start, len(text))
    return keep


def _drop(keep: list[bool], start: int, end: int, limit: int) -> None:
    for index in range(start, min(end, limit)):
        keep[index] = False


def _iter_line_spans(text: str) -> list[tuple[int, int, int]]:
    """``(行首, 行尾, 下一行行首)``；行尾不含换行符。"""
    spans: list[tuple[int, int, int]] = []
    cursor = 0
    total = len(text)
    while cursor <= total:
        newline = text.find("\n", cursor)
        if newline == -1:
            spans.append((cursor, total, total + 1))
            break
        spans.append((cursor, newline, newline + 1))
        cursor = newline + 1
        if cursor == total:
            spans.append((cursor, total, total + 1))
            break
    return spans


def _merge_removed_segments(segments: list[SourceSegment]) -> tuple[SourceSegment, ...]:
    """合并相邻删除段，并丢弃空删除段，得到紧凑映射。"""
    merged: list[SourceSegment] = []
    for segment in segments:
        if (
            segment.kind == SEGMENT_KIND_REMOVED
            and segment.raw_start == segment.raw_end
        ):
            continue
        if merged and merged[-1].kind == SEGMENT_KIND_REMOVED and segment.kind == SEGMENT_KIND_REMOVED:
            previous = merged[-1]
            if previous.clean_start == segment.clean_start and previous.raw_end == segment.raw_start:
                merged[-1] = SourceSegment(
                    clean_start=previous.clean_start,
                    clean_end=previous.clean_end,
                    raw_start=previous.raw_start,
                    raw_end=segment.raw_end,
                    kind=SEGMENT_KIND_REMOVED,
                )
                continue
        merged.append(segment)
    return tuple(merged)


def _require_text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} 必须是 str。")


def _validate_absolute_start(absolute_start: int) -> None:
    if isinstance(absolute_start, bool) or not isinstance(absolute_start, int):
        raise ValueError("absolute_start 必须是整数。")
    if absolute_start < 0:
        raise ValueError("absolute_start 不能为负。")


__all__ = [
    "LEGACY_TEXT_PROJECTION_VERSION",
    "READABLE_V1_TEXT_PROJECTION_VERSION",
    "SEGMENT_KIND_ALT_KEPT",
    "SEGMENT_KIND_KEPT",
    "SEGMENT_KIND_REMOVED",
    "SEGMENT_KINDS",
    "TEXT_PROJECTION_VERSION",
    "MappedText",
    "Replacement",
    "SourceSegment",
    "TextProjection",
    "apply_replacements_with_source_mapping",
    "known_projection_versions",
    "normalize_blank_lines",
    "normalize_blank_lines_only",
    "project_by_version",
    "project_readable",
]
