"""富内容块的分组与组装：共同材料识别、共享材料分组与 ``RichContentV2`` 组装。

本模块是**纯函数**层：不读文件、不碰数据库、不依赖 python-docx，便于 T40/T50 在拿到
块列表（``parse_docx_rich`` 的 ``blocks``）后复用；块类型一律取自冻结契约
``app.contracts.teaching_loop``，不复制第二份定义。

共同材料（shared materials）判定口径 —— 保守、可测、不猜：

1. **首个题号段之前的块**：题号段 = 段落块且文本匹配 ``QUESTION_NUMBER_PATTERN``。
   文档里出现过题号段时，位于首个题号段**之前**的所有块归入共同材料组；没有题号段时
   "首个题号段之前"不成立，不产生前导组（不把整篇当成材料）。
2. **材料段**：段落块文本（去掉前导空白）以 ``材料`` / ``阅读材料`` / ``阅读下面的材料``
   起头的，无论位置都是材料锚点；锚点在**没有打开的组**时起一个新组。
3. 组一旦打开就向后连续吸收块（正文/表格/公式/图片），直到遇到**下一个题号段**；
   **题号段本身留在 ``unassigned_block_ids``**，不吸收、也不起组。
4. 既不落在前导区、也不在打开的组里的块（如题号后的选项行）一律留在
   ``unassigned_block_ids``，不做任何猜测。

组 id 稳定：``material-1``、``material-2``…，按各组首块在文档中的位置排序；组内块顺序
= 文档顺序（按 ``locators.blockStart`` 归一，缺定位时按传入顺序），因此同一原件恒得同一分组。

题号正则口径（对任务卡示例的**收窄**，避免把页码/年份/小数误判成题号）：只识别带分隔符
或"题/问"字样的数字编号 —— ``1.`` / ``1、`` / ``1．`` / ``1)`` / ``1）`` / ``第1题`` /
``(1)`` / ``（1）``；裸数字（``2023``、``2.5``）不算题号。无法判定的一律留在
``unassigned_block_ids``。
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from app.contracts.teaching_loop import (
    ContentBlock,
    FormulaBlock,
    ImageBlock,
    ParagraphBlock,
    RichAsset,
    RichContentV2,
    RichOrigin,
    SharedMaterial,
    TableBlock,
)
from app.core.exceptions import AppError

#: 材料段落前缀（任务卡 §A：``材料`` / ``阅读材料`` / ``阅读下面的材料``）
MATERIAL_PREFIXES: tuple[str, ...] = ("阅读下面的材料", "阅读材料", "材料")

#: 前导空白（不跨行；段落文本可能含软换行）
_LEADING_SPACE = r"[ \t\u3000\f\v]*"

#: 保守题号正则；见模块 docstring 的口径说明
QUESTION_NUMBER_PATTERN = re.compile(
    r"^\s*" + _LEADING_SPACE + r"(?:第\s*)?\d{1,2}\s*(?:题|问|[.、．)）](?!\d))"
    r"|^" + _LEADING_SPACE + r"[（(]" + _LEADING_SPACE + r"\d{1,2}" + _LEADING_SPACE + r"[)）]"
)

#: 契约里的块类型（顺序即判别顺序）
BLOCK_TYPES: tuple[type, ...] = (ParagraphBlock, TableBlock, FormulaBlock, ImageBlock)


def _invalid(message: str) -> AppError:
    return AppError(message, code="INVALID_REQUEST", status_code=422)


def is_question_number_block(block: ContentBlock) -> bool:
    """段落块是否为"题号段"（保守正则；非段落一律 False）。"""
    return (
        isinstance(block, ParagraphBlock)
        and QUESTION_NUMBER_PATTERN.match(block.text) is not None
    )


def is_material_heading_block(block: ContentBlock) -> bool:
    """段落块是否以材料前缀起头（材料锚点）。"""
    if not isinstance(block, ParagraphBlock):
        return False
    text = block.text.lstrip()
    return any(text.startswith(prefix) for prefix in MATERIAL_PREFIXES)


def _position(block_id: str, index: int, locators: Mapping[str, Mapping]) -> tuple[int, int]:
    """块在文档中的位置；缺少定位时退回输入顺序（1 基），保证排序确定性。"""
    locator = locators.get(block_id) if isinstance(locators, Mapping) else None
    start = locator.get("blockStart") if isinstance(locator, Mapping) else None
    if not isinstance(start, int) or isinstance(start, bool):
        start = index + 1
    return (start, index)


def group_shared_materials(
    blocks: Sequence[ContentBlock],
    locators: Mapping[str, Mapping],
) -> tuple[tuple[SharedMaterial, ...], tuple[str, ...]]:
    """把块列表切成共同材料组与未分组块（见模块 docstring 的四条规则）。"""
    if not blocks:
        return (), ()
    positions = {
        block.id: _position(block.id, index, locators)
        for index, block in enumerate(blocks)
    }
    ordered = sorted(blocks, key=lambda block: positions[block.id])
    question_positions = [
        positions[block.id] for block in ordered if is_question_number_block(block)
    ]
    first_question = min(question_positions) if question_positions else None

    materials: list[SharedMaterial] = []
    assigned: set[str] = set()
    current: list[ContentBlock] | None = None

    def close() -> None:
        nonlocal current
        if current:
            materials.append(
                SharedMaterial(id=f"material-{len(materials) + 1}", blocks=list(current))
            )
        current = None

    for block in ordered:
        if is_question_number_block(block):
            close()  # 题号段终止当前组，本身留在 unassigned
            continue
        is_leading = first_question is not None and positions[block.id] < first_question
        if is_leading or is_material_heading_block(block):
            if current is None:
                current = []
            current.append(block)
            assigned.add(block.id)
            continue
        if current is not None:
            current.append(block)  # 锚点与下一个题号之间的块：归属当前材料组
            assigned.add(block.id)
            continue
        # 既不在前导区也没有打开的组：不猜，留在 unassigned
    close()

    unassigned = tuple(block.id for block in ordered if block.id not in assigned)
    return tuple(materials), unassigned


def rich_content_from_blocks(
    *,
    blocks: Sequence[ContentBlock],
    materials: Sequence[SharedMaterial],
    assets: Sequence[RichAsset],
    origin: RichOrigin,
    stem_block_ids: Sequence[str] | None = None,
) -> RichContentV2:
    """组装 ``RichContentV2``：``stem_block_ids`` 决定题干块，其余分组留空待填充。

    - ``stem_block_ids=None``：全部**不属于**共享材料的块按文档顺序作题干；
    - 显式给出时：按文档顺序取这些 id；未出现在 ``blocks`` 里的 id、或已被共享材料占用的
      id 一律 ``INVALID_REQUEST``（同一块不能既是题干又是共享材料，**不静默丢弃**）；
    - 块 id 在 ``blocks`` 与共享材料之间必须唯一且内容一致，否则 ``INVALID_REQUEST``；
    - 块对象按引用透传（``TableBlock.columnCount`` 等字段一律保留，不重建、不丢字段）；
    - ``optionBlocks``/``answerBlocks``/``explanationBlocks`` 由调用方在返回对象上补齐
      （本工具只做"块流 → 富内容"的确定性切分）。
    """
    if not isinstance(origin, RichOrigin):
        raise _invalid("origin 必须是 RichOrigin（原件来源定位）。")
    block_list = list(blocks)
    by_id: dict[str, ContentBlock] = {}
    for block in block_list:
        if not isinstance(block, BLOCK_TYPES):
            raise _invalid(f"不支持的内容块类型：{type(block).__name__}。")
        if block.id in by_id:
            raise _invalid(f"内容块 id 重复：{block.id}。")
        by_id[block.id] = block

    material_ids: set[str] = set()
    for material in materials:
        for block in material.blocks:
            if block.id in material_ids:
                raise _invalid(f"共享材料内块 id 重复：{block.id}。")
            material_ids.add(block.id)
            source = by_id.get(block.id)
            if source is None:
                raise _invalid(f"共享材料引用了不存在的内容块：{block.id}。")
            if source != block:
                raise _invalid(f"共享材料的块与内容块列表不一致：{block.id}。")

    if stem_block_ids is None:
        stem = [block for block in block_list if block.id not in material_ids]
    else:
        selected: set[str] = set()
        for block_id in stem_block_ids:
            if not isinstance(block_id, str) or not block_id.strip():
                raise _invalid("stem_block_ids 必须是非空块 id 列表。")
            if block_id not in by_id:
                raise _invalid(f"stem_block_ids 引用了不存在的内容块：{block_id}。")
            if block_id in material_ids:
                raise _invalid(
                    f"stem_block_ids 与共享材料冲突：{block_id}（同一块不能既是题干又是共享材料）。"
                )
            selected.add(block_id)
        stem = [block for block in block_list if block.id in selected]

    return RichContentV2(
        version=2,
        # 契约的富内容模型只认 camelCase 别名（未开 populate_by_name）
        sharedMaterials=list(materials),
        stemBlocks=stem,
        optionBlocks={},
        answerBlocks=[],
        explanationBlocks=[],
        assets=list(assets),
        origin=origin,
    )
