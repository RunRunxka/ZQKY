"""DOCX 富内容解析：段落 / 表格（合并单元格）/ 图片（真实字节）/ OMML 公式 / 可见问题。

与既有教材解析（``app.services.document_parsing.parser``，语义冻结）**互不影响**：本模块是
"题目富内容 v2"的解析器，输出 ``ContentBlock`` 流 + 来源定位 + 抽取的图片资产；它不改动
既有 ``ParsedDocument`` 语义、版本号与任何既有文件。

解析口径（可测、不猜）：

- 只遍历 ``document.element.body`` 的直接子元素；``w:p`` / ``w:tbl`` 计入**块序号**
  （1 基，与既有 ``SourceBlock.block_start`` 同风格）；``w:sectPr`` 等纯属性元素忽略；
  其余未知元素产生 ``RichIssue(code="UNSUPPORTED_OBJECT")`` 并带 ``bodyIndex`` 定位，
  **绝不静默丢弃**；
- 段落可见文本取自 ``w:t`` / ``w:tab`` / ``w:br`` / ``w:cr`` / ``w:noBreakHyphen`` /
  ``w:ptab``（与 python-docx ``Paragraph.text`` 同口径，含超链接内的文本）；删除修订
  （``w:delText``）与域代码（``w:instrText``）不算可见文本；完全没有可见文本、公式、
  图片或对象的空段落不产生块；
- 段落内的公式 / 图片 / 未知对象按**文档顺序**拆分：文本段 → ``ParagraphBlock``，
  OMML → ``FormulaBlock``（``ommlXml`` 是原始 ``m:oMath`` 节点的逐字节序列化，不改写、
  不做 LaTeX 往返）→ 图片 → ``ImageBlock``，未知对象 → ``RichIssue``（挂在段落块 id 上）；
- 表格：处理 ``w:gridSpan`` / ``w:vMerge``；合并单元格**只在起始位置出现一次**——
  起始单元格带 ``rowSpan`` / ``colSpan``，其右方/下方的被覆盖单元格不再产生条目
  （续接单元格若有可见文本，按可见内容追加到起始单元格文本，绝不丢字）；
  ``w:tblHeader`` 或首行 → ``isHeader=True``；每行网格列数与首行不一致时给警告；
  **表格块一律填写 ``columnCount``**（网格宽度 = 首行覆盖列数），它是行优先单元格序列
  精确还原成行的唯一依据（``TableBlock.cells`` 是扁平列表，不含行边界）；
- 图片：从关系（``r:embed`` / ``v:imagedata``）取 image part 的真实字节，
  经 ``AssetStore.store_original`` 落盘（``blobs/<sha256>``）。本层没有数据库：
  ``ImageBlock.assetId`` 用返回的 ``blob_key``，``assets`` 里给出
  ``RichAsset(assetId=blob_key, sha256, mediaType)``；把资产登记成教学库 ``file_assets``
  行由**调用方**（T40/T50 经 ``FileAssetsRepository.create``）在同一事务里完成；
- 图片尺寸：``wp:extent`` 的 EMU 换算像素（96 dpi，``emu / 9525``，四舍五入，与
  python-docx 的 px 换算同口径）；无 extent（如 VML ``v:imagedata``）记 0，渲染时按原图；
- 表格单元格内的公式按可见文本（``m:t`` 拼接）保留并给警告，单元格内的图片给
  ``RichIssue``（``TableBlock`` 只承载文本，不假装保留了结构）。

表格块的 ``locators`` 除 ``blockStart`` / ``blockEnd`` 外附 ``tableColumns`` / ``tableRows``
（与 ``TableBlock.columnCount`` 同值，供调用方做来源核对）。渲染器以 ``columnCount`` 为准；
旧数据缺 ``columnCount`` 时才回退 ``RichOrigin.sourceLocator["tableGrids"]`` 与启发式重建
（重建口径见 ``renderer_docx``）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lxml import etree

from app.contracts.teaching_loop import (
    ContentBlock,
    FormulaBlock,
    ImageBlock,
    ParagraphBlock,
    RichAsset,
    RichOrigin,
    TableBlock,
    TableCell,
)
from app.core.exceptions import AppError
from app.services.assets.store import AssetStore

W_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WP_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/main"
V_NAMESPACE = "urn:schemas-microsoft-com:vml"
C_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/chart"

#: 96 dpi 下 1 像素的 EMU（914400 / 96）
EMU_PER_PIXEL = 9525

UNSUPPORTED_OBJECT = "UNSUPPORTED_OBJECT"


def _q(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def _local_name(tag: Any) -> str:
    text = tag if isinstance(tag, str) else str(tag)
    return text.rsplit("}", 1)[-1]


#: 正文级纯属性/标记元素：不承载可见内容，忽略且不报问题
_BODY_IGNORED_TAGS = frozenset(
    _q(W_NAMESPACE, name)
    for name in (
        "sectPr",
        "bookmarkStart",
        "bookmarkEnd",
        "proofErr",
        "commentRangeStart",
        "commentRangeEnd",
    )
)

#: 段落属性元素：不承载内容，遍历时跳过（不递归）
_INLINE_PROPERTY_TAGS = frozenset(
    _q(W_NAMESPACE, name) for name in ("pPr", "rPr", "rPrChange", "pPrChange")
)


def _failed(message: str, *, code: str, status_code: int) -> AppError:
    return AppError(message, code=code, status_code=status_code)


# --------------------------------------------------------------------------- 结果类型


@dataclass(frozen=True)
class RichIssue:
    """解析过程中的可见问题：未知对象 / 转换失败 / 无法分类，都带来源定位。"""

    code: str
    message: str
    block_id: str | None
    source_locator: dict


@dataclass(frozen=True)
class ParsedRichDocument:
    """一次富内容解析的结果；``blocks`` 顺序 = 原件 body 顺序。"""

    blocks: tuple[ContentBlock, ...]
    #: blockId -> 来源坐标（至少含 blockStart / blockEnd，1 基）
    locators: dict[str, dict]
    #: 抽取并写入 AssetStore 的图片资产（assetId = blob_key）
    assets: tuple[RichAsset, ...]
    issues: tuple[RichIssue, ...]
    warnings: tuple[str, ...]
    #: blockId -> kind（便利字段，等价于 blocks 上的判别字段）
    block_kinds: dict[str, str]


@dataclass(frozen=True)
class _Token:
    """段落内联遍历的原子片段。"""

    kind: str  # text | formula | drawing | pict | unsupported
    text: str = ""
    element: Any = None


@dataclass(frozen=True)
class _ImageRef:
    """一次图片引用（或不可解析的图形对象）。"""

    rid: str | None
    width_px: int
    height_px: int
    kind: str  # image | unsupported
    message: str | None = None


@dataclass(frozen=True)
class _CellParagraphReport:
    text: str
    formulas: int
    images: int
    unsupported: tuple[str, ...]


# --------------------------------------------------------------------------- 内联遍历


def _paragraph_tokens(paragraph_element: Any) -> list[_Token]:
    """按文档顺序展开段落内联内容（含超链接 / 内容控件内部）。"""
    tokens: list[_Token] = []
    _collect_inline(paragraph_element, tokens)
    return tokens


def _collect_inline(element: Any, sink: list[_Token]) -> None:
    for child in element.iterchildren():
        tag = child.tag
        if tag in _INLINE_PROPERTY_TAGS:
            continue
        if tag == _q(W_NAMESPACE, "t"):
            sink.append(_Token("text", child.text or ""))
        elif tag == _q(W_NAMESPACE, "tab"):
            sink.append(_Token("text", "\t"))
        elif tag in (_q(W_NAMESPACE, "br"), _q(W_NAMESPACE, "cr")):
            sink.append(_Token("text", "\n"))
        elif tag == _q(W_NAMESPACE, "noBreakHyphen"):
            sink.append(_Token("text", "-"))
        elif tag == _q(W_NAMESPACE, "ptab"):
            sink.append(_Token("text", "\t"))
        elif tag == _q(W_NAMESPACE, "drawing"):
            sink.append(_Token("drawing", "", child))
        elif tag == _q(W_NAMESPACE, "pict"):
            sink.append(_Token("pict", "", child))
        elif tag in (_q(W_NAMESPACE, "object"), _q(W_NAMESPACE, "altChunk")):
            sink.append(_Token("unsupported", _local_name(tag), child))
        elif tag == _q(M_NAMESPACE, "oMath"):
            sink.append(_Token("formula", "", child))
        else:
            _collect_inline(child, sink)


def _linearize_math(element: Any) -> str:
    """把 OMML 里的可见文本（``m:t``）线性拼接；只用于无法承载公式结构的场合。"""
    return "".join(node.text or "" for node in element.iter(_q(M_NAMESPACE, "t")))


def _serialize_math(element: Any) -> str:
    """原始 ``m:oMath`` 节点的逐字节序列化（不改写、不重排、不转换）。"""
    return etree.tostring(element, encoding="unicode")


def _cell_paragraph_report(paragraph_element: Any) -> _CellParagraphReport:
    pieces: list[str] = []
    formulas = 0
    images = 0
    unsupported: list[str] = []
    for token in _paragraph_tokens(paragraph_element):
        if token.kind == "text":
            pieces.append(token.text)
        elif token.kind == "formula":
            formulas += 1
            pieces.append(_linearize_math(token.element))
        elif token.kind in ("drawing", "pict"):
            images += 1
        else:
            unsupported.append(token.text)
    return _CellParagraphReport("".join(pieces), formulas, images, tuple(unsupported))


# --------------------------------------------------------------------------- 几何 / 表格属性


def _emu_to_px(value: Any) -> int:
    try:
        emu = int(value)
    except (TypeError, ValueError):
        return 0
    if emu <= 0:
        return 0
    return int(round(emu / EMU_PER_PIXEL))


def _positive_int(value: Any, *, default: int = 1) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 1 else default


def _grid_span(tc_pr: Any) -> int:
    if tc_pr is None:
        return 1
    element = tc_pr.find(_q(W_NAMESPACE, "gridSpan"))
    if element is None:
        return 1
    return _positive_int(element.get(_q(W_NAMESPACE, "val")), default=1)


def _vmerge_state(tc_pr: Any) -> str | None:
    """返回 ``restart`` / ``continue`` / None（无纵向合并）。"""
    if tc_pr is None:
        return None
    element = tc_pr.find(_q(W_NAMESPACE, "vMerge"))
    if element is None:
        return None
    value = (element.get(_q(W_NAMESPACE, "val")) or "").strip().lower()
    return "restart" if value == "restart" else "continue"


def _row_grid_skips(tr: Any) -> tuple[int, int]:
    tr_pr = tr.find(_q(W_NAMESPACE, "trPr"))
    if tr_pr is None:
        return 0, 0
    before = tr_pr.find(_q(W_NAMESPACE, "gridBefore"))
    after = tr_pr.find(_q(W_NAMESPACE, "gridAfter"))
    return (
        _positive_int(before.get(_q(W_NAMESPACE, "val")), default=0) if before is not None else 0,
        _positive_int(after.get(_q(W_NAMESPACE, "val")), default=0) if after is not None else 0,
    )


def _row_has_tbl_header(tr: Any) -> bool:
    tr_pr = tr.find(_q(W_NAMESPACE, "trPr"))
    if tr_pr is None:
        return False
    element = tr_pr.find(_q(W_NAMESPACE, "tblHeader"))
    if element is None:
        return False
    value = (element.get(_q(W_NAMESPACE, "val")) or "").strip().lower()
    return value not in ("false", "0", "off")


def _block_id(primary: str, index: int) -> str:
    return primary if index == 0 else f"{primary}-{index}"


def _image_refs(element: Any, kind: str) -> list[_ImageRef]:
    """从 ``w:drawing`` / ``w:pict`` 里取出图片引用（或不可解析的图形对象）。"""
    if kind == "drawing":
        extent = None
        for child in element:
            if child.tag in (_q(WP_NAMESPACE, "inline"), _q(WP_NAMESPACE, "anchor")):
                found = child.find(_q(WP_NAMESPACE, "extent"))
                if found is not None:
                    extent = found
        width = _emu_to_px(extent.get("cx") if extent is not None else None)
        height = _emu_to_px(extent.get("cy") if extent is not None else None)
        refs: list[_ImageRef] = []
        for blip in element.iter(_q(A_NAMESPACE, "blip")):
            rid = blip.get(_q(R_NAMESPACE, "embed")) or blip.get(_q(R_NAMESPACE, "link"))
            refs.append(_ImageRef(rid=rid, width_px=width, height_px=height, kind="image"))
        if refs:
            return refs
        if any(True for _ in element.iter(_q(C_NAMESPACE, "chart"))):
            message = "图表对象（c:chart）未提取。"
        else:
            message = "图形对象里没有可提取的图片（形状/组合图形/SmartArt）。"
        return [_ImageRef(rid=None, width_px=0, height_px=0, kind="unsupported", message=message)]

    refs = []
    for imagedata in element.iter(_q(V_NAMESPACE, "imagedata")):
        rid = imagedata.get(_q(R_NAMESPACE, "id")) or imagedata.get(_q(R_NAMESPACE, "href"))
        refs.append(_ImageRef(rid=rid, width_px=0, height_px=0, kind="image"))
    if refs:
        return refs
    return [
        _ImageRef(
            rid=None,
            width_px=0,
            height_px=0,
            kind="unsupported",
            message="VML 图形对象里没有可提取的图片（文本框/形状）。",
        )
    ]


# --------------------------------------------------------------------------- 解析主体


class _Parser:
    def __init__(self, *, document: Any, assets: AssetStore) -> None:
        self.document = document
        self.assets = assets
        self.issues: list[RichIssue] = []
        self.warnings: list[str] = []
        self.assets_seen: dict[str, RichAsset] = {}

    # -------------------------------------------------------------- 问题与资产

    def add_issue(self, code: str, message: str, *, block_id: str | None, locator: dict | None) -> None:
        self.issues.append(
            RichIssue(
                code=code,
                message=message,
                block_id=block_id,
                source_locator=dict(locator or {}),
            )
        )

    def _relation_part(self, rid: str | None) -> Any | None:
        if not rid:
            return None
        try:
            return self.document.part.related_parts[rid]
        except (KeyError, AttributeError):
            return None

    def store_image(self, ref: _ImageRef, *, block_id: str, locator: dict, label: str) -> ImageBlock | None:
        """把一张图片写入 AssetStore 并返回块；不可解析时记 issue 返回 None。"""
        if ref.kind == "unsupported":
            self.add_issue(
                UNSUPPORTED_OBJECT,
                ref.message or "未支持的图形对象。",
                block_id=block_id,
                locator=locator,
            )
            return None
        if not ref.rid:
            self.add_issue(
                UNSUPPORTED_OBJECT,
                f"{label}的图片缺少关系 id，无法取到字节。",
                block_id=block_id,
                locator=locator,
            )
            return None
        part = self._relation_part(ref.rid)
        if part is None:
            self.add_issue(
                UNSUPPORTED_OBJECT,
                f"{label}的图片关系 {ref.rid} 无法解析，未提取内容。",
                block_id=block_id,
                locator=locator,
            )
            return None
        blob = getattr(part, "blob", None)
        if not isinstance(blob, (bytes, bytearray)) or not blob:
            self.add_issue(
                UNSUPPORTED_OBJECT,
                f"{label}的图片关系 {ref.rid} 不是内嵌图片（外链或非图片部件），未提取内容。",
                block_id=block_id,
                locator=locator,
            )
            return None
        media_type = str(getattr(part, "content_type", "") or "").strip() or "application/octet-stream"
        original_name = Path(str(getattr(part, "partname", "") or "")).name or "image.bin"
        stored = self.assets.store_original(
            bytes(blob), media_type=media_type, original_name=original_name
        )
        if stored.blob_key not in self.assets_seen:
            self.assets_seen[stored.blob_key] = RichAsset(
                asset_id=stored.blob_key,
                sha256=stored.sha256,
                media_type=media_type,
            )
        return ImageBlock(
            id=block_id,
            kind="image",
            asset_id=stored.blob_key,
            width=ref.width_px,
            height=ref.height_px,
        )

    # -------------------------------------------------------------- body

    def parse_body(self, body: Any) -> tuple[list[ContentBlock], dict[str, dict]]:
        blocks: list[ContentBlock] = []
        locators: dict[str, dict] = {}
        ordinal = 0
        for body_index, child in enumerate(body.iterchildren(), start=1):
            tag = child.tag
            if tag == _q(W_NAMESPACE, "p"):
                ordinal += 1
                self._parse_paragraph(child, ordinal, blocks, locators)
            elif tag == _q(W_NAMESPACE, "tbl"):
                ordinal += 1
                self._parse_table(child, ordinal, blocks, locators)
            elif tag in _BODY_IGNORED_TAGS:
                continue
            else:
                self.add_issue(
                    UNSUPPORTED_OBJECT,
                    f"未支持的对象「{_local_name(tag)}」（未提取其内容）。",
                    block_id=None,
                    locator={"bodyIndex": body_index},
                )
        return blocks, locators

    # -------------------------------------------------------------- 段落

    def _parse_paragraph(
        self,
        paragraph_element: Any,
        ordinal: int,
        blocks: list[ContentBlock],
        locators: dict[str, dict],
    ) -> None:
        primary = f"p{ordinal}"
        locator = {"blockStart": ordinal, "blockEnd": ordinal}
        produced: list[ContentBlock] = []
        pending_issues: list[tuple[str, str]] = []
        buffer: list[str] = []

        def flush() -> None:
            text = "".join(buffer)
            del buffer[:]
            if not text.strip():
                return
            produced.append(
                ParagraphBlock(
                    id=_block_id(primary, len(produced)), kind="paragraph", text=text
                )
            )

        for token in _paragraph_tokens(paragraph_element):
            if token.kind == "text":
                buffer.append(token.text)
                continue
            flush()
            if token.kind == "formula":
                produced.append(
                    FormulaBlock(
                        id=_block_id(primary, len(produced)),
                        kind="formula",
                        omml_xml=_serialize_math(token.element),
                    )
                )
                continue
            if token.kind in ("drawing", "pict"):
                label = "段落图片"
                for ref in _image_refs(token.element, token.kind):
                    block = self.store_image(
                        ref,
                        block_id=primary,
                        locator=locator,
                        label=label,
                    )
                    if block is not None:
                        produced.append(
                            block.model_copy(
                                update={"id": _block_id(primary, len(produced))}
                            )
                        )
                continue
            pending_issues.append(
                (
                    UNSUPPORTED_OBJECT,
                    f"未支持的对象「{token.text}」（未提取其内容）。",
                )
            )
        flush()

        if not produced:
            for code, message in pending_issues:
                self.add_issue(code, message, block_id=None, locator=locator)
            return
        for block in produced:
            blocks.append(block)
            locators[block.id] = dict(locator)
        for code, message in pending_issues:
            self.add_issue(code, message, block_id=primary, locator=locator)

    # -------------------------------------------------------------- 表格

    def _parse_table(
        self,
        tbl_element: Any,
        ordinal: int,
        blocks: list[ContentBlock],
        locators: dict[str, dict],
    ) -> None:
        primary = f"t{ordinal}"
        locator = {"blockStart": ordinal, "blockEnd": ordinal}
        rows = [tr for tr in tbl_element.iterchildren() if tr.tag == _q(W_NAMESPACE, "tr")]
        if not rows:
            self.warnings.append(f"第 {ordinal} 个表格没有行，未产出表格块。")
            return

        cells: list[TableCell] = []
        #: 网格列 -> cells 下标：上一行放下的单元格，可被本行的 vMerge 续接
        origins: dict[int, int] = {}
        row_widths: list[int] = []
        formula_count = 0
        image_count = 0
        for row_index, tr in enumerate(rows):
            is_header = row_index == 0 or _row_has_tbl_header(tr)
            before, after = _row_grid_skips(tr)
            if before or after:
                self.warnings.append(
                    f"第 {ordinal} 个表格第 {row_index + 1} 行含 gridBefore/gridAfter"
                    f"（{before}/{after}），对应的空网格列未表示。"
                )
            column = 0
            next_origins: dict[int, int] = {}
            width = 0
            for tc in (child for child in tr.iterchildren() if child.tag == _q(W_NAMESPACE, "tc")):
                tc_pr = tc.find(_q(W_NAMESPACE, "tcPr"))
                grid_span = _grid_span(tc_pr)
                state = _vmerge_state(tc_pr)
                if state == "continue" and column in origins:
                    origin_index = origins[column]
                    origin = cells[origin_index]
                    origin.row_span += 1
                    text = self._cell_text(tc, ordinal, row_index)
                    formula_count += text.formulas
                    image_count += text.images
                    if text.text:
                        origin.text = f"{origin.text}\n{text.text}" if origin.text else text.text
                    next_origins[column] = origin_index
                    width += 1
                    column += 1
                    continue
                if state == "continue":
                    self.warnings.append(
                        f"第 {ordinal} 个表格第 {row_index + 1} 行存在没有起始单元格的"
                        " vMerge 续接，已按普通单元格处理。"
                    )
                text = self._cell_text(tc, ordinal, row_index)
                formula_count += text.formulas
                image_count += text.images
                cells.append(
                    TableCell(
                        text=text.text,
                        is_header=is_header,
                        row_span=1,
                        col_span=grid_span,
                    )
                )
                for covered in range(column, column + grid_span):
                    next_origins[covered] = len(cells) - 1
                width += grid_span
                column += grid_span
            row_widths.append(width)
            origins = next_origins

        if not cells:
            self.warnings.append(f"第 {ordinal} 个表格没有单元格，未产出表格块。")
            return
        if formula_count:
            self.warnings.append(
                f"第 {ordinal} 个表格的单元格含 {formula_count} 处公式，已按可见文本保留"
                "（未保留公式结构）。"
            )
        if image_count:
            self.add_issue(
                UNSUPPORTED_OBJECT,
                f"第 {ordinal} 个表格的单元格含 {image_count} 张图片，表格块只承载文本，未提取。",
                block_id=None,
                locator=locator,
            )
        expected = row_widths[0]
        mismatched = [index + 1 for index, value in enumerate(row_widths) if value != expected]
        if mismatched:
            self.warnings.append(
                f"第 {ordinal} 个表格第 {mismatched[:10]} 行的网格列数与首行（{expected}）不一致，"
                "渲染时可能报表格结构不合法。"
            )
        block = TableBlock(id=primary, kind="table", cells=cells, column_count=expected)
        blocks.append(block)
        locators[block.id] = {
            "blockStart": ordinal,
            "blockEnd": ordinal,
            "tableColumns": expected,
            "tableRows": len(rows),
        }

    def _cell_text(self, tc: Any, ordinal: int, row_index: int) -> _CellParagraphReport:
        pieces: list[str] = []
        formulas = 0
        images = 0
        unsupported: list[str] = []
        locator = {"blockStart": ordinal, "blockEnd": ordinal}
        for child in tc.iterchildren():
            tag = child.tag
            if tag == _q(W_NAMESPACE, "tcPr"):
                continue
            if tag == _q(W_NAMESPACE, "p"):
                report = _cell_paragraph_report(child)
                formulas += report.formulas
                images += report.images
                for name in report.unsupported:
                    unsupported.append(name)
                    self.add_issue(
                        UNSUPPORTED_OBJECT,
                        f"第 {ordinal} 个表格第 {row_index + 1} 行单元格内未支持的对象「{name}」。",
                        block_id=None,
                        locator=locator,
                    )
                pieces.append(report.text)
                continue
            if tag == _q(W_NAMESPACE, "tbl"):
                self.add_issue(
                    UNSUPPORTED_OBJECT,
                    f"第 {ordinal} 个表格单元格内的嵌套表格未提取。",
                    block_id=None,
                    locator=locator,
                )
                continue
            self.add_issue(
                UNSUPPORTED_OBJECT,
                f"第 {ordinal} 个表格单元格内未支持的对象「{_local_name(tag)}」。",
                block_id=None,
                locator=locator,
            )
        return _CellParagraphReport("\n".join(pieces), formulas, images, tuple(unsupported))

    # -------------------------------------------------------------- 原件核验

    def verify_origin(self, origin: RichOrigin, path: Path) -> None:
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        expected = (origin.original_sha256 or "").strip().lower()
        if digest != expected:
            self.warnings.append(
                f"原件散列与 origin.originalSha256 不一致（原件 {digest[:12]}…，"
                f"origin {expected[:12]}…）；已按给定路径的内容解析，请核对来源。"
            )


# --------------------------------------------------------------------------- 公开入口


def parse_docx_rich(
    *,
    path: Path,
    file_name: str,
    assets: AssetStore,
    origin: RichOrigin | None = None,
) -> ParsedRichDocument:
    """解析 DOCX 为富内容块流 + 定位 + 图片资产 + 可见问题（不写数据库、不改原件）。

    - ``assets``：必须是 ``AssetStore`` 形态（``store_original`` / ``read``），图片真实字节
      写进受管资产根；``ImageBlock.assetId`` 即 ``blob_key``；
    - ``origin``：可选。给出时会核对原件 sha256 与 ``origin.originalSha256``，不一致只记
      ``warnings``（可见告警），不因来源元数据缺失而拒绝解析内容 —— 内容是权威。
    """
    target = Path(path)
    if not target.is_file():
        raise _failed(
            f"待解析文件不存在：{target.name}",
            code="DOCUMENT_FILE_MISSING",
            status_code=500,
        )
    suffix = Path((file_name or "").strip() or target.name).suffix.lower()
    if not suffix:
        suffix = target.suffix.lower()
    if suffix != ".docx":
        raise _failed(
            f"富内容解析只支持 .docx，收到「{suffix or file_name}」。",
            code="UNSUPPORTED_DOCUMENT_FORMAT",
            status_code=422,
        )
    if not callable(getattr(assets, "store_original", None)) or not callable(
        getattr(assets, "read", None)
    ):
        raise _failed(
            "assets 必须是 AssetStore（需要 store_original / read）。",
            code="INVALID_REQUEST",
            status_code=422,
        )
    if origin is not None and not isinstance(origin, RichOrigin):
        raise _failed("origin 必须是 RichOrigin。", code="INVALID_REQUEST", status_code=422)

    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - 依赖缺失时明确失败
        raise _failed(
            "DOCX 富内容解析依赖 python-docx 未安装。",
            code="DOCUMENT_PARSER_UNAVAILABLE",
            status_code=500,
        ) from exc
    try:
        document = Document(str(target))
    except Exception as exc:  # noqa: BLE001 - 非 zip/损坏文档统一 422，不伪装成空文
        raise _failed(
            f"DOCX 解析失败：{exc.__class__.__name__}。",
            code="DOCUMENT_PARSE_FAILED",
            status_code=422,
        ) from exc

    parser = _Parser(document=document, assets=assets)
    blocks, locators = parser.parse_body(document.element.body)
    if origin is not None:
        parser.verify_origin(origin, target)

    return ParsedRichDocument(
        blocks=tuple(blocks),
        locators=dict(locators),
        assets=tuple(parser.assets_seen.values()),
        issues=tuple(parser.issues),
        warnings=tuple(parser.warnings),
        block_kinds={block.id: block.kind for block in blocks},
    )


__all__ = [
    "EMU_PER_PIXEL",
    "UNSUPPORTED_OBJECT",
    "ParsedRichDocument",
    "RichIssue",
    "parse_docx_rich",
]
