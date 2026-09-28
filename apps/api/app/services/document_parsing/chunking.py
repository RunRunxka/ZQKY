"""分块：目标 800 码点 / 上限 1200 / 重叠 ≤120，按完整边界回退。

不可从中间截断的单元（Markdown 代码围栏、表格行块、``$$…$$`` 公式块）先整块成原子，
再按行贪心成块；行内 ``$$…$$`` 作为保护区，切点绝不落在公式内部。
策略参数进入 ``chunk_policy_fingerprint``，不同策略产生不同 ``policy_fingerprint`` 与
``manifest_sha256``，因此可以并存多个分块集而不改写旧修订的原文。

约定：
- ``chapter_path`` 取块**起点**所在的最近 Markdown 标题路径；块内出现的标题由后续块承接
  （块跨标题时不会把两个章节的路径混在一起）；
- 与习题区有任何重叠的块一律标记为 ``exercise``（见 ``regions.region_for_span``）；
- 单个不可切分单元超过上限时整块保留，宁可超过上限也不从公式/表格/围栏中间截断。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from app.core.exceptions import AppError
from app.providers.embeddings.fingerprint import canonical_json, sha256_hex
from app.repositories.textbook_catalog.records import ChunkInput
from app.services.document_parsing.parser import ParsedDocument
from app.services.document_parsing.regions import (
    LEGACY_REGION_RULES_VERSION,
    REGION_RULES_VERSION,
    RegionSpan,
    iter_lines,
    region_for_span,
    split_regions,
)

CHUNK_POLICY_VERSION = "zqky-chunk-v1"
DEFAULT_TARGET_CHARS = 800
DEFAULT_MAX_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 120

_HEADING_PATTERN = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.*)$")
_FENCE_PREFIXES = ("```", "~~~")
_BREAK_AFTER_PRIMARY = ("。", "！", "？", "；", "\n")
_BREAK_AFTER_SECONDARY = ("，", "、", " ", "\t", ")", "）", "]", "】")

_FENCE_KIND = "fence"
_MATH_KIND = "math"
_TABLE_KIND = "table"
_LINE_KIND = "line"


@dataclass(frozen=True)
class ChunkPolicy:
    target_chars: int = DEFAULT_TARGET_CHARS
    max_chars: int = DEFAULT_MAX_CHARS
    overlap_chars: int = DEFAULT_OVERLAP_CHARS
    version: str = CHUNK_POLICY_VERSION
    #: 正文/习题划分规则版本（来自 regions.REGION_RULES_VERSION）；进入指纹：
    #: 规则一变指纹就变，必然产生新的 chunk_set，不会复用按旧划分算出的分块集。
    region_rules_version: str = REGION_RULES_VERSION

    def __post_init__(self) -> None:
        if self.target_chars <= 0:
            raise ValueError("目标块长必须为正整数。")
        if self.max_chars < self.target_chars:
            raise ValueError("最大块长不能小于目标块长。")
        if self.overlap_chars < 0 or self.overlap_chars > DEFAULT_OVERLAP_CHARS:
            raise ValueError(f"重叠不得超过 {DEFAULT_OVERLAP_CHARS} 个码点。")
        if not self.version:
            raise ValueError("分块策略版本不能为空。")
        if not self.region_rules_version:
            raise ValueError("正文/习题划分规则版本不能为空。")


DEFAULT_CHUNK_POLICY = ChunkPolicy()


def chunk_policy_json(policy: ChunkPolicy = DEFAULT_CHUNK_POLICY) -> dict:
    """策略的规范化 JSON；``regionRulesVersion`` 仅在新版规则下写入。

    历史（v1）JSON 没有该字段，读取时按 ``zqky-region-v1`` 补齐，序列化仍回到 4 键形态，
    因此旧口径的指纹保持可复现（旧 chunk_set 仍可被找到），而新规则必然产生新指纹。
    """
    payload: dict = {
        "targetChars": policy.target_chars,
        "maxChars": policy.max_chars,
        "overlapChars": policy.overlap_chars,
        "version": policy.version,
    }
    if policy.region_rules_version != LEGACY_REGION_RULES_VERSION:
        payload["regionRulesVersion"] = policy.region_rules_version
    return payload


def chunk_policy_fingerprint(policy: ChunkPolicy = DEFAULT_CHUNK_POLICY) -> str:
    """对策略参数（含正文/习题划分规则版本）做 canonical JSON sha256。"""
    return sha256_hex(canonical_json(chunk_policy_json(policy)))


def chunk_policy_from_json(payload: object) -> ChunkPolicy:
    """从已存 JSON 还原策略；历史数据缺 ``regionRulesVersion`` 时按旧规则版本补齐。

    只有结构真正损坏（类型不符/阈值非法）才抛 ``CHUNK_POLICY_CORRUPT``，
    旧数据永远可读——指纹与新版不同，所以会重建而不是复用错误划分。
    """
    if not isinstance(payload, dict):
        raise AppError(
            "分块策略数据损坏：不是 JSON 对象。",
            code="CHUNK_POLICY_CORRUPT",
            status_code=500,
        )
    raw_version = payload.get("regionRulesVersion", LEGACY_REGION_RULES_VERSION)
    try:
        policy = ChunkPolicy(
            target_chars=int(payload.get("targetChars", DEFAULT_TARGET_CHARS)),
            max_chars=int(payload.get("maxChars", DEFAULT_MAX_CHARS)),
            overlap_chars=int(payload.get("overlapChars", DEFAULT_OVERLAP_CHARS)),
            version=str(payload.get("version", CHUNK_POLICY_VERSION)),
            region_rules_version=str(raw_version),
        )
    except (TypeError, ValueError) as exc:
        raise AppError(
            f"分块策略数据损坏：{exc}",
            code="CHUNK_POLICY_CORRUPT",
            status_code=500,
        ) from exc
    return policy


@dataclass(frozen=True)
class _Atom:
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class _Emitted:
    start: int
    end: int
    first_atom: int
    last_atom: int


def chunk_manifest_sha256(chunks: Sequence[ChunkInput]) -> str:
    """分块集清单指纹：区间、区、章节路径与文本指纹的 canonical JSON sha256。"""
    return sha256_hex(
        canonical_json(
            [
                {
                    "ordinal": chunk.ordinal,
                    "charStart": chunk.char_start,
                    "charEnd": chunk.char_end,
                    "region": chunk.region,
                    "chapterPath": list(chunk.chapter_path),
                    "textSha256": chunk.text_sha256,
                }
                for chunk in chunks
            ]
        )
    )


def chunk_text(parsed: ParsedDocument, chunk: ChunkInput) -> str:
    return parsed.normalized_text[chunk.char_start:chunk.char_end]


def chunk_document(
    parsed: ParsedDocument,
    *,
    policy: ChunkPolicy = DEFAULT_CHUNK_POLICY,
    regions: Sequence[RegionSpan] | None = None,
) -> list[ChunkInput]:
    """把规范化文本切成有序块；空文本返回空列表（由调用方决定是否拒绝）。"""
    try:
        policy = ChunkPolicy(
            target_chars=policy.target_chars,
            max_chars=policy.max_chars,
            overlap_chars=policy.overlap_chars,
            version=policy.version,
            region_rules_version=policy.region_rules_version,
        )
    except (TypeError, ValueError) as exc:
        raise AppError(
            f"分块策略不合法：{exc}",
            code="CHUNK_POLICY_INVALID",
            status_code=422,
        ) from exc

    text = parsed.normalized_text
    if not text:
        return []
    region_spans = tuple(regions) if regions is not None else split_regions(parsed)
    atoms = _tokenize(text)
    atom_regions = [
        region_for_span(region_spans, atom.start, atom.end) for atom in atoms
    ]
    headings = _heading_entries(text)

    chunks: list[ChunkInput] = []
    emitted: list[_Emitted] = []

    def build(start: int, end: int, *, region: str) -> None:
        if end <= start:
            return
        if not text[start:end].strip():
            # 纯空白块没有可检索内容；若与重叠尾巴拼在一起还可能伪造出跨区的"伪正文块"
            return
        chunks.append(
            ChunkInput(
                ordinal=len(chunks),
                char_start=start,
                char_end=end,
                region=region,
                chapter_path=_path_at(headings, start),
                text_sha256=sha256_hex(text[start:end]),
            )
        )
        emitted.append(
            _Emitted(start=start, end=end, first_atom=len(atoms), last_atom=-1)
        )

    index = 0
    while index < len(atoms):
        atom = atoms[index]
        if atom.end <= atom.start:
            # 空行原子不单独成块：否则末尾空行会与重叠尾巴拼成一个跨区小块
            index += 1
            continue
        atom_length = atom.end - atom.start
        if atom_length > policy.max_chars:
            # 先看是否是可切分的普通行：在安全切点（句末/逗号）内部分段
            if atom.kind == _LINE_KIND:
                for piece_start, piece_end in _split_span(text, atom.start, atom.end, policy):
                    build(
                        piece_start,
                        piece_end,
                        region=region_for_span(region_spans, piece_start, piece_end),
                    )
            else:
                # 围栏 / 表格 / 跨行公式：整块保留，宁可超过上限也不从中间截断
                build(atom.start, atom.end, region=atom_regions[index])
            index += 1
            continue

        natural_region = atom_regions[index]
        last = index
        span_end = atom.end
        while last + 1 < len(atoms):
            if span_end - atom.start >= policy.target_chars:
                break
            # 不跨正文/习题边界成块：每块只覆盖一个区，避免正文被并入 exercise 块后检索不到
            if atom_regions[last + 1] != natural_region:
                break
            candidate_end = atoms[last + 1].end
            if candidate_end - atom.start > policy.max_chars:
                break
            last += 1
            span_end = candidate_end

        start = atom.start
        overlap_floor = _overlap_floor(atoms, emitted, policy.overlap_chars)
        if overlap_floor is not None and overlap_floor < start:
            start = overlap_floor
        # 块标签取"自然区"（不含为上下文补的重叠尾巴），重叠尾巴不改变块的归属
        build(start, span_end, region=natural_region)
        # 记录本次成块覆盖的原子范围，供下一块计算重叠
        emitted[-1] = _Emitted(
            start=start, end=span_end, first_atom=index, last_atom=last
        )
        index = last + 1
    return chunks


def chunk_region_share(chunks: Sequence[ChunkInput]) -> tuple[float, int, int]:
    """块级 body 占比（A1 t12 口径）：body 块字符数 / 全部块字符数；返回 (占比, body 块数, 块数)。

    检索只取 ``region='body'`` 的块，所以这个比值就是"正文可被检索到的字符覆盖率"。
    """
    total = sum(chunk.char_end - chunk.char_start for chunk in chunks)
    body = sum(
        chunk.char_end - chunk.char_start for chunk in chunks if chunk.region == "body"
    )
    return (body / total if total else 0.0, sum(1 for chunk in chunks if chunk.region == "body"), len(chunks))


def _overlap_floor(
    atoms: Sequence[_Atom], emitted: Sequence[_Emitted], limit: int
) -> int | None:
    """从上一块的整原子末尾向前回退，总长不超过 ``limit`` 的起始位置。"""
    if limit <= 0 or not emitted:
        return None
    previous = emitted[-1]
    if previous.first_atom > previous.last_atom:
        return None
    floor = previous.end
    for position in range(previous.last_atom, previous.first_atom - 1, -1):
        if previous.end - atoms[position].start > limit:
            break
        floor = atoms[position].start
    if floor >= previous.end:
        return None
    return floor


def _tokenize(text: str) -> list[_Atom]:
    """把文本切成不可内部截断的原子块（围栏 / 跨行公式 / 表格行块 / 单行）。"""
    lines = list(iter_lines(text))
    atoms: list[_Atom] = []
    index = 0
    total = len(lines)
    while index < total:
        start, end, line = lines[index]
        stripped = line.strip()
        fence = _fence_prefix(stripped)
        if fence is not None:
            if stripped.count(fence) >= 2:
                atoms.append(_Atom(start, end, _FENCE_KIND))
                index += 1
                continue
            close = index + 1
            while close < total and not lines[close][2].strip().startswith(fence):
                close += 1
            last = min(close, total - 1)
            atoms.append(_Atom(start, lines[last][1], _FENCE_KIND))
            index = last + 1
            continue
        if line.count("$$") % 2 == 1:
            close = index + 1
            while close < total:
                candidate = lines[close][2]
                if "$$" in candidate or not candidate.strip():
                    break
                close += 1
            if close < total and "$$" in lines[close][2]:
                atoms.append(_Atom(start, lines[close][1], _MATH_KIND))
                index = close + 1
                continue
            # 未闭合（且后面是空行/文末）：按普通行处理，避免吞掉整篇正文
            atoms.append(_Atom(start, end, _LINE_KIND))
            index += 1
            continue
        if stripped.startswith("|"):
            close = index + 1
            while close < total and lines[close][2].strip().startswith("|"):
                close += 1
            atoms.append(_Atom(start, lines[close - 1][1], _TABLE_KIND))
            index = close
            continue
        atoms.append(_Atom(start, end, _LINE_KIND))
        index += 1
    return atoms


def _fence_prefix(stripped: str) -> str | None:
    for prefix in _FENCE_PREFIXES:
        if stripped.startswith(prefix):
            return prefix
    return None


def _protected_ranges(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """行内 ``$$…$$`` 对的区间（含定界符），切点不得落入其中。"""
    ranges: list[tuple[int, int]] = []
    cursor = start
    while True:
        opening = text.find("$$", cursor, end)
        if opening == -1:
            break
        closing = text.find("$$", opening + 2, end)
        if closing == -1:
            break
        ranges.append((opening, closing + 2))
        cursor = closing + 2
    return ranges


def _inside_protected(position: int, ranges: Sequence[tuple[int, int]]) -> bool:
    return any(start < position < end for start, end in ranges)


def _split_span(text: str, start: int, end: int, policy: ChunkPolicy) -> list[tuple[int, int]]:
    """把一个超长普通行按安全切点分段；任何切点都不落在 ``$$…$$`` 内部。"""
    protected = _protected_ranges(text, start, end)
    primary: list[int] = []
    secondary: list[int] = []
    for position in range(start, end):
        boundary = position + 1
        if _inside_protected(boundary, protected):
            continue
        character = text[position]
        if character in _BREAK_AFTER_PRIMARY:
            primary.append(boundary)
        elif character in _BREAK_AFTER_SECONDARY:
            secondary.append(boundary)

    pieces: list[tuple[int, int]] = []
    cursor = start
    while end - cursor > policy.max_chars:
        limit = cursor + policy.max_chars
        candidates = [point for point in primary if cursor < point <= limit]
        if not candidates:
            candidates = [point for point in secondary if cursor < point <= limit]
        if candidates:
            cut = candidates[-1]
        else:
            # 没有安全切点：把切点推到保护区之后（宁可超过上限也不切进公式）
            cut = limit
            for range_start, range_end in protected:
                if range_start < cut < range_end:
                    cut = range_end
        for range_start, _range_end in protected:
            if range_start < cut < _range_end:
                cut = range_start
        if cut <= cursor or cut > end:
            break
        pieces.append((cursor, cut))
        cursor = cut
    if cursor < end:
        pieces.append((cursor, end))
    return pieces


@dataclass(frozen=True)
class _Heading:
    start: int
    path: tuple[str, ...]


def _heading_entries(text: str) -> list[_Heading]:
    entries: list[_Heading] = []
    stack: list[tuple[int, str]] = []
    in_fence = False
    fence_token: str | None = None
    for start, _end, line in iter_lines(text):
        stripped = line.strip()
        prefix = _fence_prefix(stripped)
        if prefix is not None:
            if not in_fence:
                in_fence = True
                fence_token = prefix
            elif prefix == fence_token:
                in_fence = False
                fence_token = None
            continue
        if in_fence:
            continue
        match = _HEADING_PATTERN.match(stripped)
        if match is None:
            continue
        title = match.group("title").strip()
        if not title:
            continue
        level = len(match.group("hashes"))
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        entries.append(_Heading(start=start, path=tuple(item[1] for item in stack)))
    return entries


def _path_at(entries: Sequence[_Heading], position: int) -> tuple[str, ...]:
    path: tuple[str, ...] = ()
    for entry in entries:
        if entry.start <= position:
            path = entry.path
        else:
            break
    return path
