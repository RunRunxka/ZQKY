"""原卷 DOCX 的规则拆题与块归属推断（TEACHING-LOOP B2 / T40）。

本模块是**纯函数**层：输入 T10 ``parse_docx_rich`` 的解析结果与 ``RichOrigin``，输出
候选题目、块处置、解析问题与计分叶子合计；不碰数据库、不调模型、不读文件。

口径（保守、可测、不猜，与 ``services/rich_content/blocks.py`` 的分组口径协同）：

- **完整题号**：只识别带分隔符/"题""问"字样或括号子题号的编号 —— ``16.`` / ``16、`` /
  ``第16题`` / ``16(1)`` / ``17（2）`` / 独立成段的 ``(1)``；裸数字（``2023``、``2.5``）
  一律不算题号。识别到父号（``16.``）与子号（``16(1)`` 或独立 ``(1)``）时，父为容器
  （不计分），子为计分候选；**只有子号而没有父号时补一个空容器**（题号路径必须完整）。
- **题号重复**（同一路径出现两次）：不新建重复行（DB 唯一约束就是权威），把后段并入
  该题并在问题清单里记 ``ITEM_QUESTION_NO_DUPLICATE``（blocking），由教师人工拆分。
- **满分**：从题号段与其自有块文本里找 ``（N 分）`` / ``（N分）`` / ``满分 N 分`` /
  ``共 N 分`` 标记，取**首个**匹配，输出十进制字符串（≤2 位小数）；找不到则留空，
  并且该叶子**不计分**（``is_scored=0``）——不能把"不知道多少分"伪造成 0 分或假分数。
- **块归属**：每个块恰好一种处置 —— ``item``（题号段与其题目范围内的块）、
  ``shared_material``（首个题号之前的前导区，或同段内出现材料锚点之后的部分）、
  ``unassigned``（没有题号可归属时的兜底；本层不产出 ``excluded``）。
  材料的判定同时要求"T10 ``group_shared_materials`` 判为材料"且"本层分段口径也认为
  是材料"：T10 的题号正则不认识 ``16(1)`` 这类完整路径，材料组会越过这种分界继续吸收，
  该修正把被误吸收的题干块交还给题目。
- **分节边界**：``一、``/``（二）``/``第三部分`` 这类分节标题只作结构边界——关闭上一题的
  归属、自己归 ``unassigned``（由教师指定归属或排除）。否则节标题里的「共 N 分」会被
  当成上一题的满分，节标题本身也会混进上一题题干。
- **题干内容**：每个题目用 ``rich_content_from_blocks`` 组装 ``RichContentV2``（含 origin）：
  题干块 = 该题自有块；共享材料 = 在该题结束位置之前开始的材料组（前导材料对所有题可见，
  题目内部开的材料留给后续小题）；补出的空容器不含内容（``{}``）。独立成段的子号
  （``(1)``）与它后面的自有内容归**完整子题路径**（``15(1)``），不留在父容器上。
- **问题清单**：T10 的解析问题（未知对象等）按 ``blocking`` 落库（影响题意的解析损失
  必须补录或显式排除才可确认）；T10 告警按 ``info``；未归属块按 ``warning`` 逐块登记
  （确认闸门另有实时检查）；分值缺失与题号重复按 ``blocking``。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from app.contracts.papers import SCORE_TEXT_PATTERN
from app.contracts.teaching_loop import (
    ImageBlock,
    ParagraphBlock,
    RichAsset,
    RichContentV2,
    RichOrigin,
    SharedMaterial,
)
from app.services.rich_content import (
    ParsedRichDocument,
    group_shared_materials,
    is_material_heading_block,
    rich_content_from_blocks,
)

#: 计分叶子缺满分（blocking：教师必须补分或显式排除）
ITEM_SCORE_MISSING = "ITEM_SCORE_MISSING"
#: 题号重复（blocking）
ITEM_QUESTION_NO_DUPLICATE = "ITEM_QUESTION_NO_DUPLICATE"
#: 整篇没有可用题号（blocking）
NO_ITEMS_DETECTED = "NO_ITEMS_DETECTED"
#: T10 解析告警（info）
PARSER_WARNING = "PARSER_WARNING"
#: 未归属块（warning；确认闸门另有实时 PAPER_BLOCK_UNASSIGNED 检查）
BLOCK_UNASSIGNED = "PAPER_BLOCK_UNASSIGNED"

#: 块类型 → ``paper_source_blocks.kind``（契约枚举；解析器只产出四种，余下归 unknown）
BLOCK_KINDS = frozenset({"paragraph", "table", "formula", "image", "unknown"})

#: 顶层题号：``16.`` / ``16、`` / ``16．`` / ``16)`` / ``16）`` / ``第16题`` / ``16问``
_ROOT_NUMBER = re.compile(r"^\s*(?:第\s*)?(\d{1,2})\s*(?:题|问|[.、．)）](?!\d))")
#: 完整路径子号：``16(1)`` / ``17（2）``
_COMPOSITE_NUMBER = re.compile(r"^\s*(?:第\s*)?(\d{1,2})\s*[（(]\s*(\d{1,2})\s*[)）]")
#: 独立成段的子号：``(1)`` / ``（2）``（只在已有顶层题号时才有意义）
_CHILD_NUMBER = re.compile(r"^\s*[（(]\s*(\d{1,2})\s*[)）](?!\d)")

#: 分节标题：``一、``/``（二）``/``第三部分``。它是**结构边界**：既不属于任何题目的内容，
#: 也不能把「（本题共3小题，每小题6分，共18分）」这类节合计当作上一题的满分。
_SECTION_HEADING = re.compile(
    r"^\s*(?:[（(]\s*[一二三四五六七八九十]{1,3}\s*[)）]"
    r"|[一二三四五六七八九十]{1,3}\s*[、.．]"
    r"|第\s*[一二三四五六七八九十\d]{1,3}\s*(?:部分|章|节|大题))"
)

#: 「（N 分）」标记（首选）
_SCORE_PAREN = re.compile(r"[（(]\s*(\d{1,3}(?:\.\d{1,2})?)\s*分\s*[)）]")
#: 「满分 N 分」/「共 N 分」标记（次选）
_SCORE_TOTAL = re.compile(r"(?:满分|共)\s*(?:为)?\s*(\d{1,3}(?:\.\d{1,2})?)\s*分")


# --------------------------------------------------------------------------- 结构


@dataclass(frozen=True)
class CandidateItem:
    """一条规则拆出的题目（容器或叶子）；``item_id`` 由服务层生成。"""

    question_no: str
    parent_question_no: str | None
    ordinal: int
    is_scored: bool
    max_score: str | None
    locator: dict[str, Any]
    content: dict[str, Any]
    #: 归属该题的块 id（文档顺序，不含共享材料块）
    own_block_ids: tuple[str, ...] = ()
    #: 题号所在的段落块 id（补出的空容器为 None）
    number_block_id: str | None = None


@dataclass(frozen=True)
class CandidateBlock:
    """一个原文块的持久化候选：快照 + 处置（``item`` 用题号引用，服务层再换成 id）。"""

    block_id: str
    ordinal: int
    kind: str
    locator: dict[str, Any]
    payload: dict[str, Any]
    disposition: str
    item_question_no: str | None = None
    exclude_reason: str | None = None


@dataclass(frozen=True)
class CandidateIssue:
    code: str
    severity: str
    message: str
    block_id: str | None
    locator: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportAnalysis:
    items: tuple[CandidateItem, ...]
    blocks: tuple[CandidateBlock, ...]
    issues: tuple[CandidateIssue, ...]
    total_score_units: int


# --------------------------------------------------------------------------- 小工具


def _score_text_from_marker(raw: str) -> str | None:
    """把标记里的十进制文本归一成契约允许的 ``maxScore`` 字符串（>0、≤2 位小数）。"""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0:
        return None
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -2:
        return None
    units = value * 100
    if units != units.to_integral_value():
        return None
    normalized = format(value.normalize(), "f")
    return normalized if re.fullmatch(SCORE_TEXT_PATTERN, normalized) else None


def extract_score_marker(text: str) -> str | None:
    """从一段文本里取首个「（N 分）」/「满分 N 分」标记，返回十进制字符串或 None。"""
    if not isinstance(text, str):
        return None
    for pattern in (_SCORE_PAREN, _SCORE_TOTAL):
        match = pattern.search(text)
        if match is not None:
            normalized = _score_text_from_marker(match.group(1))
            if normalized is not None:
                return normalized
    return None


@dataclass(frozen=True)
class _NumberMatch:
    kind: str  # root | composite | child
    root: str
    child: str | None


def classify_question_number(text: str) -> _NumberMatch | None:
    """判定段落文本是否为题号段；返回归一化题号或 ``None``。"""
    if not isinstance(text, str) or not text.strip():
        return None
    composite = _COMPOSITE_NUMBER.match(text)
    if composite is not None:
        return _NumberMatch("composite", composite.group(1), composite.group(2))
    root = _ROOT_NUMBER.match(text)
    if root is not None:
        return _NumberMatch("root", root.group(1), None)
    child = _CHILD_NUMBER.match(text)
    if child is not None:
        return _NumberMatch("child", "", child.group(1))
    return None


def question_no_for(root: str, child: str | None) -> str:
    return f"{root}({child})" if child else root


def is_section_heading_block(block: Any) -> bool:
    """段落是否为分节标题（只作结构边界：不进任何题目的自有块，也不贡献分值标记）。"""
    if not isinstance(block, ParagraphBlock):
        return False
    text = block.text
    return isinstance(text, str) and _SECTION_HEADING.match(text) is not None


def block_kind(block: Any) -> str:
    kind = getattr(block, "kind", None)
    return kind if kind in BLOCK_KINDS else "unknown"


def _block_positions(parsed: ParsedRichDocument) -> dict[str, tuple[int, int]]:
    """块 → ``(blockStart, 输入顺序)``；缺定位时退回输入顺序，保证排序确定。"""
    positions: dict[str, tuple[int, int]] = {}
    for index, block in enumerate(parsed.blocks):
        locator = parsed.locators.get(block.id) or {}
        start = locator.get("blockStart")
        if not isinstance(start, int) or isinstance(start, bool):
            start = index + 1
        positions[block.id] = (start, index)
    return positions


def _ordered_blocks(parsed: ParsedRichDocument) -> list[Any]:
    positions = _block_positions(parsed)
    return sorted(parsed.blocks, key=lambda block: positions[block.id])


def _block_payload(block: Any) -> dict[str, Any]:
    return block.model_dump(by_alias=True)


# --------------------------------------------------------------------------- 拆题


@dataclass
class _Spec:
    """拆题过程中的可变题目状态。"""

    question_no: str
    root: str
    child: str | None
    parent: str | None
    number_block_id: str | None
    locator: dict[str, Any]
    score_text: str | None = None
    own_blocks: list[str] = field(default_factory=list)
    duplicate: bool = False


def _locator_of(positions: Mapping[str, tuple[int, int]], block_id: str) -> dict[str, Any]:
    start, index = positions.get(block_id, (0, 0))
    return {"blockStart": start, "blockIndex": index}


def _detect_specs(
    ordered: Sequence[Any], positions: dict[str, tuple[int, int]]
) -> tuple[list[_Spec], dict[str, str]]:
    """按文档顺序扫描题号段，返回 ``(题目状态, 题号块 -> 题号)``（含重复题号块）。"""
    specs: list[_Spec] = []
    by_number: dict[str, _Spec] = {}
    number_blocks: dict[str, str] = {}
    current_root: _Spec | None = None

    def ensure_root(root: str, *, number_block_id: str | None, locator: dict[str, Any]) -> _Spec:
        existing = by_number.get(root)
        if existing is not None:
            return existing
        spec = _Spec(
            question_no=root,
            root=root,
            child=None,
            parent=None,
            number_block_id=number_block_id,
            locator=dict(locator),
        )
        by_number[root] = spec
        specs.append(spec)
        return spec

    for block in ordered:
        if not isinstance(block, ParagraphBlock):
            continue
        match = classify_question_number(block.text)
        if match is None:
            continue
        locator = _locator_of(positions, block.id)
        if match.kind == "root":
            spec = ensure_root(
                match.root, number_block_id=block.id, locator=locator
            )
            current_root = spec
            number_blocks[block.id] = spec.question_no
            if spec.number_block_id == block.id:
                spec.score_text = extract_score_marker(block.text) or spec.score_text
                continue
            # 重复题号：并入已有题目，登记 blocking 问题（不新建重复行）
            spec.duplicate = True
            continue
        if match.kind == "composite":
            parent = ensure_root(
                match.root, number_block_id=None, locator={}
            )
            current_root = parent
            full = question_no_for(match.root, match.child)
            number_blocks[block.id] = full
            existing = by_number.get(full)
            if existing is not None:
                existing.duplicate = True
                continue
            spec = _Spec(
                question_no=full,
                root=match.root,
                child=match.child,
                parent=parent.question_no,
                number_block_id=block.id,
                locator=locator,
                score_text=extract_score_marker(block.text),
            )
            by_number[full] = spec
            specs.append(spec)
            continue
        # child：``(1)`` 必须挂在最近的顶层题号下（父子路径完整）；没有顶层题号时不算题号（不猜）
        if current_root is None:
            continue
        full = question_no_for(current_root.root, match.child)
        # 子题号块与它后面的自有内容都归**完整子题路径**，不能留在父容器上
        # （否则子题有分值没有题干，父容器反而吸收全部内容）
        number_blocks[block.id] = full
        existing = by_number.get(full)
        if existing is not None:
            existing.duplicate = True
            continue
        spec = _Spec(
            question_no=full,
            root=current_root.root,
            child=match.child,
            parent=current_root.question_no,
            number_block_id=block.id,
            locator=locator,
            score_text=extract_score_marker(block.text),
        )
        by_number[full] = spec
        specs.append(spec)
    return specs, number_blocks


def _material_sets(parsed: ParsedRichDocument, ordered: Sequence[Any]) -> set[str]:
    """T10 判为共同材料的块 id 集合。"""
    materials, _unassigned = group_shared_materials(ordered, parsed.locators)
    return {block.id for material in materials for block in material.blocks}


def _segment_material_ids(
    ordered: Sequence[Any], boundary_ids: set[str]
) -> tuple[set[str], set[str]]:
    """按本层题号分界分段，返回 ``(前导区块, 段内材料锚点之后的块)``。

    段 = 一个题号段到下一个题号段之前；段内第一个材料锚点（含自身）之后的块是材料。
    题号段自身不吸收、也不起材料组。
    """
    leading: set[str] = set()
    in_segment_material: set[str] = set()
    seen_boundary = False
    anchor_open = False
    for block in ordered:
        if block.id in boundary_ids:
            seen_boundary = True
            anchor_open = False
            continue
        if not seen_boundary:
            leading.add(block.id)
            continue
        if anchor_open:
            in_segment_material.add(block.id)
            continue
        if is_material_heading_block(block):
            anchor_open = True
            in_segment_material.add(block.id)
    return leading, in_segment_material


def _assign_blocks(
    parsed: ParsedRichDocument,
    ordered: Sequence[Any],
    specs: Sequence[_Spec],
    number_blocks: dict[str, str],
) -> tuple[dict[str, str], dict[str, str | None], set[str]]:
    """返回 ``(block_id -> disposition, block_id -> item_question_no, unassigned ids)``。"""
    boundary_ids = set(number_blocks)
    t10_material = _material_sets(parsed, ordered)
    leading, in_segment_material = _segment_material_ids(ordered, boundary_ids)
    material_ids = (leading | in_segment_material) & t10_material

    dispositions: dict[str, str] = {}
    owners: dict[str, str | None] = {}
    unassigned: set[str] = set()
    current: str | None = None
    for block in ordered:
        if block.id in boundary_ids:
            current = number_blocks[block.id]
            dispositions[block.id] = "item"
            owners[block.id] = current
            continue
        if block.id in material_ids:
            dispositions[block.id] = "shared_material"
            owners[block.id] = None
            continue
        if is_section_heading_block(block):
            # 分节标题是结构边界：关闭上一题的归属，自己不归任何题目
            # （否则节标题里的「共 N 分」会被当成上一题的满分）。由教师指定归属或排除。
            current = None
            dispositions[block.id] = "unassigned"
            owners[block.id] = None
            unassigned.add(block.id)
            continue
        if current is not None:
            dispositions[block.id] = "item"
            owners[block.id] = current
            continue
        dispositions[block.id] = "unassigned"
        owners[block.id] = None
        unassigned.add(block.id)

    # 回填每题的 own_block_ids（文档顺序；材料块与题号块已按处置排除在外）
    own: dict[str, list[str]] = {spec.question_no: [] for spec in specs}
    for block in ordered:
        if dispositions[block.id] != "item":
            continue
        item_no = owners.get(block.id)
        if item_no is None:
            continue
        own.setdefault(item_no, []).append(block.id)
    for spec in specs:
        spec.own_blocks = own.get(spec.question_no, [])
    return dispositions, owners, unassigned


def _children_map(specs: Sequence[_Spec]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for spec in specs:
        if spec.child is not None:
            counts[spec.root] = counts.get(spec.root, 0) + 1
    return counts


def _material_groups(ordered: Sequence[Any], material_ids: set[str]) -> list[SharedMaterial]:
    """把共同的材料块按文档顺序切成连续组（``material-1``、``material-2``…）。"""
    groups: list[SharedMaterial] = []
    current: list[Any] = []
    for block in ordered:
        if block.id in material_ids:
            current.append(block)
            continue
        if current:
            groups.append(
                SharedMaterial(id=f"material-{len(groups) + 1}", blocks=list(current))
            )
            current = []
    if current:
        groups.append(SharedMaterial(id=f"material-{len(groups) + 1}", blocks=list(current)))
    return groups


def _fill_leaf_scores(
    ordered: Sequence[Any], specs: Sequence[_Spec], children: dict[str, int]
) -> None:
    """叶子的满分标记也可写在题干里（题号段之外）；取该题自有块里的首个标记。"""
    by_id = {block.id: block for block in ordered}
    for spec in specs:
        if children.get(spec.question_no):
            continue  # 容器：分值由子题表达，不在容器上记分
        if spec.score_text is not None:
            continue
        for block_id in spec.own_blocks:
            candidate = by_id.get(block_id)
            if isinstance(candidate, ParagraphBlock):
                found = extract_score_marker(candidate.text)
                if found is not None:
                    spec.score_text = found
                    break


def _units_of(score_text: str) -> int:
    try:
        return int(Decimal(score_text) * 100)
    except (InvalidOperation, ValueError):  # pragma: no cover - 上游已校验
        return 0


# --------------------------------------------------------------------------- 入口


def analyze_paper(*, parsed: ParsedRichDocument, origin: RichOrigin) -> ImportAnalysis:
    """把解析结果规则化为候选题目/块处置/问题清单（不写数据库、不猜内容）。"""
    ordered = _ordered_blocks(parsed)
    positions = _block_positions(parsed)
    specs, number_blocks = _detect_specs(ordered, positions)
    dispositions, owners, unassigned = _assign_blocks(parsed, ordered, specs, number_blocks)
    material_ids = {
        block_id
        for block_id, disposition in dispositions.items()
        if disposition == "shared_material"
    }
    materials = _material_groups(ordered, material_ids)
    block_by_id = {block.id: block for block in ordered}
    assets_by_id = {asset.asset_id: asset for asset in parsed.assets}
    children = _children_map(specs)
    _fill_leaf_scores(ordered, specs, children)

    issues: list[CandidateIssue] = []
    issues.extend(
        CandidateIssue(
            code=issue.code,
            severity="blocking",
            message=issue.message,
            block_id=issue.block_id if issue.block_id in block_by_id else None,
            locator=dict(issue.source_locator or {}),
        )
        for issue in parsed.issues
    )
    issues.extend(
        CandidateIssue(
            code=PARSER_WARNING,
            severity="info",
            message=str(warning),
            block_id=None,
            locator={},
        )
        for warning in parsed.warnings
    )

    items: list[CandidateItem] = []
    total_score_units = 0
    for spec in specs:
        is_container = bool(children.get(spec.question_no))
        is_scored = False
        max_score: str | None = None
        if not is_container:
            if spec.score_text is None:
                issues.append(
                    CandidateIssue(
                        code=ITEM_SCORE_MISSING,
                        severity="blocking",
                        message=(
                            f"题 {spec.question_no} 未识别到满分标记（如「（6 分）」）；"
                            "该题暂不计分，请补充分值或显式排除该问题。"
                        ),
                        block_id=spec.number_block_id,
                        locator=_item_locator(spec, positions),
                    )
                )
            else:
                is_scored = True
                max_score = spec.score_text
                total_score_units += _units_of(spec.score_text)
        if spec.duplicate:
            issues.append(
                CandidateIssue(
                    code=ITEM_QUESTION_NO_DUPLICATE,
                    severity="blocking",
                    message=(
                        f"题号 {spec.question_no} 在原件中重复出现，已并入同一题；"
                        "请人工拆分后调整题号。"
                    ),
                    block_id=spec.number_block_id,
                    locator=_item_locator(spec, positions),
                )
            )

        item_end = max(
            (positions.get(block_id, (0, 0)) for block_id in spec.own_blocks),
            default=None,
        )
        if spec.number_block_id is not None:
            number_position = positions.get(spec.number_block_id, (0, 0))
            item_end = number_position if item_end is None else max(item_end, number_position)
        has_content = spec.number_block_id is not None or bool(spec.own_blocks)
        included_materials = [
            material
            for material in materials
            if has_content and positions.get(material.blocks[0].id, (0, 0)) < item_end
        ]
        referenced_assets: list[RichAsset] = []
        seen_assets: set[str] = set()
        for block_id in spec.own_blocks:
            block = block_by_id[block_id]
            asset_id = getattr(block, "asset_id", None)
            if isinstance(block, ImageBlock) and isinstance(asset_id, str):
                if asset_id not in seen_assets and asset_id in assets_by_id:
                    seen_assets.add(asset_id)
                    referenced_assets.append(assets_by_id[asset_id])
        if has_content:
            content: dict[str, Any] = rich_content_from_blocks(
                blocks=list(block_by_id.values()),
                materials=list(included_materials),
                assets=list(referenced_assets),
                origin=origin,
                stem_block_ids=list(spec.own_blocks),
            ).model_dump(by_alias=True)
        else:
            content = {}
        items.append(
            CandidateItem(
                question_no=spec.question_no,
                parent_question_no=spec.parent,
                ordinal=len(items) + 1,
                is_scored=is_scored,
                max_score=max_score,
                locator=_item_locator(spec, positions),
                content=content,
                own_block_ids=tuple(spec.own_blocks),
                number_block_id=spec.number_block_id,
            )
        )

    if not items:
        issues.append(
            CandidateIssue(
                code=NO_ITEMS_DETECTED,
                severity="blocking",
                message=(
                    "整个文件没有识别到题号（如「16.」「16(1)」）；"
                    "请先在草稿里补建题目并归属原文块，再确认。"
                ),
                block_id=None,
                locator={},
            )
        )
    for block in ordered:
        if dispositions.get(block.id) == "unassigned":
            issues.append(
                CandidateIssue(
                    code=BLOCK_UNASSIGNED,
                    severity="warning",
                    message=(
                        f"第 {positions.get(block.id, (0, 0))[0]} 个原文块未归属到题目或共享材料；"
                        "确认前请在草稿里指定归属或填写排除理由。"
                    ),
                    block_id=block.id,
                    locator=dict(parsed.locators.get(block.id) or {}),
                )
            )

    blocks = [
        CandidateBlock(
            block_id=block.id,
            ordinal=index + 1,
            kind=block_kind(block),
            locator=dict(parsed.locators.get(block.id) or {}),
            payload=_block_payload(block),
            disposition=dispositions[block.id],
            item_question_no=owners.get(block.id) if dispositions[block.id] == "item" else None,
        )
        for index, block in enumerate(ordered)
    ]
    return ImportAnalysis(
        items=tuple(items),
        blocks=tuple(blocks),
        issues=tuple(issues),
        total_score_units=total_score_units,
    )


# --------------------------------------------------------------------------- 内部


def _item_locator(spec: _Spec, positions: dict[str, tuple[int, int]]) -> dict[str, Any]:
    if spec.number_block_id is not None:
        return _locator_of(positions, spec.number_block_id)
    first_child = next(
        (positions.get(block_id) for block_id in spec.own_blocks), None
    )
    if first_child is not None:
        return {"blockStart": first_child[0], "blockIndex": first_child[1]}
    return {}


__all__ = [
    "BLOCK_KINDS",
    "BLOCK_UNASSIGNED",
    "CandidateBlock",
    "CandidateIssue",
    "CandidateItem",
    "ITEM_QUESTION_NO_DUPLICATE",
    "ITEM_SCORE_MISSING",
    "ImportAnalysis",
    "NO_ITEMS_DETECTED",
    "PARSER_WARNING",
    "analyze_paper",
    "block_kind",
    "classify_question_number",
    "extract_score_marker",
    "question_no_for",
]
