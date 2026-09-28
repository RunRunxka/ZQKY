"""教材原文解析：`.md` / `.txt`、文本层 `.pdf`、`.docx` → 规范化文本 + 来源映射。

规范化规则固定并版本化（``PARSER_VERSION``）：
- 换行统一为 ``\\n``（CRLF / CR → LF）；
- 去掉每行行尾空格与制表符；
- 其余字符（含空行、缩进、公式与表格原文）原样保留，不压缩空白。

扫描件（无文本层）不得产生"空索引成功"：默认抛 ``DOCUMENT_NEEDS_OCR``（422）；
草稿预览路径显式传 ``allow_empty_text=True`` 时才返回 ``needs_ocr=True`` 的空文结果。

解析成功后按 ``regions.analyze_regions`` 做一次正文/习题划分自查；划分结果异常（习题区占比
超过阈值）时把可读警告并入 ``ParsedDocument.warnings``，供 ``ImportDraftView.warnings`` 展示。

版本审计（v1.2）：本次只改了正文/习题划分规则与警告，**没有**改变 ``normalized_text`` 的产生方式
（换行归一/行尾去空白/保留空行与公式原文均未动），所以 ``PARSER_VERSION`` 保持 ``zqky-parse-v1``；
同一份原件在 v1.2 前后得到相同的 ``normalized_text_sha256``。规则变化由
``regions.REGION_RULES_VERSION`` → ``ChunkPolicy.region_rules_version`` → 分块策略指纹承担，
变化后必然生成新的 ``chunk_set``，不会复用旧划分。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path

from app.core.exceptions import AppError
from app.services.document_parsing.regions import analyze_regions

#: 解析规范版本；进入 document_revisions.parser_version，规则变更必须改版本。
PARSER_VERSION = "zqky-parse-v1"

MARKDOWN_KIND = "markdown"
PDF_KIND = "pdf"
DOCX_KIND = "docx"
SOURCE_KINDS = (MARKDOWN_KIND, PDF_KIND, DOCX_KIND)
SUPPORTED_SUFFIXES = (".md", ".txt", ".pdf", ".docx")

_EMPTY_PAGE_WARNING_LIMIT = 10
_REPLACEMENT_CHARACTER = "\ufffd"


@dataclass(frozen=True)
class SourceBlock:
    """规范化文本中一段可定位来源；markdown 用行号、pdf 用页码、docx 用块序号。"""

    kind: str
    char_start: int
    char_end: int
    line_start: int | None = None
    line_end: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    block_start: int | None = None
    block_end: int | None = None

    def to_json(self) -> dict:
        payload: dict[str, object] = {
            "kind": self.kind,
            "charStart": self.char_start,
            "charEnd": self.char_end,
        }
        for key, value in (
            ("lineStart", self.line_start),
            ("lineEnd", self.line_end),
            ("pageStart", self.page_start),
            ("pageEnd", self.page_end),
            ("blockStart", self.block_start),
            ("blockEnd", self.block_end),
        ):
            if value is not None:
                payload[key] = value
        return payload


@dataclass(frozen=True)
class ParsedDocument:
    normalized_text: str
    char_count: int
    source_kind: str
    source_map: list[SourceBlock]
    page_count: int | None
    block_count: int | None
    warnings: list[str]
    needs_ocr: bool

    def locate(self, char_start: int, char_end: int) -> SourceBlock | None:
        """返回与 ``[char_start, char_end)`` 有交叠的首个来源块（无交叠返回 None）。"""
        for block in self.source_map:
            if block.char_start == block.char_end:
                continue
            if block.char_start < char_end and block.char_end > char_start:
                return block
        return None

    def blocks_in(self, char_start: int, char_end: int) -> list[SourceBlock]:
        return [
            block
            for block in self.source_map
            if block.char_start < char_end and block.char_end > char_start
        ]


def source_map_payload(parsed: ParsedDocument) -> dict:
    """来源映射 blob 的规范化 JSON：可重建正文划分与定位所需的全部信息。"""
    return {
        "parserVersion": PARSER_VERSION,
        "sourceKind": parsed.source_kind,
        "charCount": parsed.char_count,
        "pageCount": parsed.page_count,
        "blockCount": parsed.block_count,
        "warnings": list(parsed.warnings),
        "needsOcr": parsed.needs_ocr,
        "blocks": [block.to_json() for block in parsed.source_map],
    }


def parsed_from_source_map(payload: object, *, normalized_text: str) -> ParsedDocument:
    """从已封存来源映射重建 ``ParsedDocument``；结构不符抛 ``SOURCE_MAP_CORRUPT``。"""
    if not isinstance(payload, dict):
        raise _corrupt("来源映射不是 JSON 对象。")
    source_kind = payload.get("sourceKind")
    if source_kind not in SOURCE_KINDS:
        raise _corrupt("来源映射的 sourceKind 非法。")
    raw_blocks = payload.get("blocks")
    if not isinstance(raw_blocks, list):
        raise _corrupt("来源映射缺少 blocks 数组。")
    blocks: list[SourceBlock] = []
    for raw in raw_blocks:
        if not isinstance(raw, dict):
            raise _corrupt("来源映射的 block 不是对象。")
        try:
            block = SourceBlock(
                kind=str(raw["kind"]),
                char_start=int(raw["charStart"]),
                char_end=int(raw["charEnd"]),
                line_start=_optional_int(raw.get("lineStart")),
                line_end=_optional_int(raw.get("lineEnd")),
                page_start=_optional_int(raw.get("pageStart")),
                page_end=_optional_int(raw.get("pageEnd")),
                block_start=_optional_int(raw.get("blockStart")),
                block_end=_optional_int(raw.get("blockEnd")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise _corrupt("来源映射的 block 字段不合法。") from exc
        if block.char_start < 0 or block.char_end < block.char_start:
            raise _corrupt("来源映射的 block 区间非法。")
        blocks.append(block)
    page_count = _optional_int(payload.get("pageCount"))
    block_count = _optional_int(payload.get("blockCount"))
    warnings = payload.get("warnings")
    if warnings is None:
        warnings = []
    if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
        raise _corrupt("来源映射的 warnings 非法。")
    return ParsedDocument(
        normalized_text=normalized_text,
        char_count=len(normalized_text),
        source_kind=source_kind,
        source_map=list(blocks),
        page_count=page_count,
        block_count=block_count,
        warnings=list(warnings),
        needs_ocr=bool(payload.get("needsOcr")),
    )


def normalize_text(raw: str) -> str:
    """换行归一 + 去掉行尾空白；其余原样。"""
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip(" \t") for line in lines)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _corrupt("来源映射包含非整数定位字段。")
    return value


def _corrupt(message: str) -> AppError:
    return AppError(
        f"来源映射数据损坏：{message}",
        code="SOURCE_MAP_CORRUPT",
        status_code=500,
    )


def _suffix_of(file_name: str, path: Path) -> str:
    name = (file_name or "").strip() or path.name
    suffix = Path(name).suffix.lower()
    return suffix or path.suffix.lower()


def _normalized_lines(raw: str) -> tuple[str, list[tuple[int, int]]]:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[str] = []
    spans: list[tuple[int, int]] = []
    cursor = 0
    for line in lines:
        trimmed = line.rstrip(" \t")
        output.append(trimmed)
        spans.append((cursor, cursor + len(trimmed)))
        cursor += len(trimmed) + 1
    return "\n".join(output), spans


def parse_document(
    *,
    path: Path,
    file_name: str,
    parser_version: str = PARSER_VERSION,
    allow_empty_text: bool = False,
) -> ParsedDocument:
    """按扩展名解析；``allow_empty_text=True`` 时无文本层 PDF 返回空文 + ``needs_ocr``。"""
    target = Path(path)
    if not target.is_file():
        raise AppError(
            f"待解析文件不存在：{target.name}",
            code="DOCUMENT_FILE_MISSING",
            status_code=500,
        )
    suffix = _suffix_of(file_name, target)
    if suffix not in SUPPORTED_SUFFIXES:
        raise AppError(
            f"不支持的教材文件类型「{suffix or file_name}」：仅支持 .md / .txt / .pdf / .docx。",
            code="UNSUPPORTED_DOCUMENT_FORMAT",
            status_code=422,
        )
    if parser_version != PARSER_VERSION:
        # 版本由调用方显式传入；不认识的版本一律拒绝，避免用旧规则解释新文本
        raise AppError(
            f"未知的解析规范版本：{parser_version}",
            code="UNSUPPORTED_PARSER_VERSION",
            status_code=422,
        )
    if suffix in (".md", ".txt"):
        parsed = _parse_markdown(target)
    elif suffix == ".pdf":
        parsed = _parse_pdf(target, allow_empty_text=allow_empty_text)
    else:
        parsed = _parse_docx(target)
    return with_region_warnings(parsed)


def with_region_warnings(parsed: ParsedDocument) -> ParsedDocument:
    """并入正文/习题划分的自查警告；不改文本、来源映射与其余字段。"""
    report = analyze_regions(parsed.normalized_text)
    if not report.warnings:
        return parsed
    return replace(parsed, warnings=[*parsed.warnings, *report.warnings])


def _parse_markdown(path: Path) -> ParsedDocument:
    raw = path.read_text(encoding="utf-8", errors="replace")
    text, spans = _normalized_lines(raw)
    blocks = [
        SourceBlock(
            kind=MARKDOWN_KIND,
            char_start=start,
            char_end=end,
            line_start=index + 1,
            line_end=index + 1,
        )
        for index, (start, end) in enumerate(spans)
    ]
    warnings: list[str] = []
    if _REPLACEMENT_CHARACTER in raw:
        warnings.append("文件包含无法按 UTF-8 解码的字节，已用替换字符保留位置。")
    return ParsedDocument(
        normalized_text=text,
        char_count=len(text),
        source_kind=MARKDOWN_KIND,
        source_map=list(blocks),
        page_count=None,
        block_count=len(blocks),
        warnings=list(warnings),
        needs_ocr=False,
    )


def _parse_pdf(path: Path, *, allow_empty_text: bool) -> ParsedDocument:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:  # pragma: no cover - 依赖缺失时明确失败
        raise AppError(
            "PDF 解析依赖 pypdf 未安装，无法解析该文件。",
            code="DOCUMENT_PARSER_UNAVAILABLE",
            status_code=500,
        ) from exc
    try:
        reader = PdfReader(str(path))
        pages = list(reader.pages)
    except (PdfReadError, OSError, ValueError) as exc:
        raise AppError(
            f"PDF 解析失败：{exc.__class__.__name__}。",
            code="DOCUMENT_PARSE_FAILED",
            status_code=422,
        ) from exc

    page_texts: list[str] = []
    empty_pages: list[int] = []
    failed_pages: list[int] = []
    for index, page in enumerate(pages):
        try:
            extracted = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - 单页损坏不应让整册无法入库，但必须记警告
            failed_pages.append(index + 1)
            extracted = ""
        normalized = normalize_text(extracted)
        if not normalized.strip():
            empty_pages.append(index + 1)
        page_texts.append(normalized)

    text = "\n\n".join(page_texts)
    blocks: list[SourceBlock] = []
    cursor = 0
    for index, page_text in enumerate(page_texts):
        blocks.append(
            SourceBlock(
                kind=PDF_KIND,
                char_start=cursor,
                char_end=cursor + len(page_text),
                page_start=index + 1,
                page_end=index + 1,
            )
        )
        cursor += len(page_text) + 2  # 页间固定 "\n\n"

    warnings: list[str] = []
    if failed_pages:
        warnings.append(f"第 {failed_pages[:10]} 页文本层提取失败，未包含其内容。")
    if empty_pages:
        shown = empty_pages[:_EMPTY_PAGE_WARNING_LIMIT]
        more = "" if len(empty_pages) <= _EMPTY_PAGE_WARNING_LIMIT else " 等"
        warnings.append(f"第 {shown}{more} 页没有可提取的文本层。")

    needs_ocr = not text.strip()
    if needs_ocr:
        warnings.append("该 PDF 没有文本层（疑似扫描件），需要 OCR 后才能入库。")
        if not allow_empty_text:
            raise AppError(
                "该 PDF 没有可提取的文本层，无法生成教材索引；请先做 OCR 或改传文本版。",
                code="DOCUMENT_NEEDS_OCR",
                status_code=422,
            )
        return ParsedDocument(
            normalized_text="",
            char_count=0,
            source_kind=PDF_KIND,
            source_map=[],
            page_count=len(pages),
            block_count=None,
            warnings=list(warnings),
            needs_ocr=True,
        )
    return ParsedDocument(
        normalized_text=text,
        char_count=len(text),
        source_kind=PDF_KIND,
        source_map=list(blocks),
        page_count=len(pages),
        block_count=None,
        warnings=list(warnings),
        needs_ocr=False,
    )


def _parse_docx(path: Path) -> ParsedDocument:
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:  # pragma: no cover - 依赖缺失时明确失败
        raise AppError(
            "DOCX 解析依赖 python-docx 未安装，无法解析该文件。",
            code="DOCUMENT_PARSER_UNAVAILABLE",
            status_code=500,
        ) from exc

    try:
        document = Document(str(path))
    except Exception as exc:  # noqa: BLE001 - 非 zip/损坏文档统一 422，不伪装成空文
        raise AppError(
            f"DOCX 解析失败：{exc.__class__.__name__}。",
            code="DOCUMENT_PARSE_FAILED",
            status_code=422,
        ) from exc

    body = document.element.body
    block_texts: list[str] = []
    failed_blocks: list[int] = []
    ordinal = 0
    for child in body.iterchildren():
        tag = child.tag
        if tag == qn("w:p"):
            ordinal += 1
            try:
                text = normalize_text(Paragraph(child, document).text)
            except Exception:  # noqa: BLE001 - 单个段落异常不影响整册
                failed_blocks.append(ordinal)
                text = ""
            block_texts.append(text)
        elif tag == qn("w:tbl"):
            ordinal += 1
            try:
                table = Table(child, document)
                rows: list[str] = []
                for row in table.rows:
                    cells = [normalize_text(cell.text).replace("\n", " ").strip() for cell in row.cells]
                    rows.append(" | ".join(cells))
                text = normalize_text("[表格]\n" + "\n".join(rows)) if rows else "[表格]"
            except Exception:  # noqa: BLE001 - 单个表格异常不影响整册
                failed_blocks.append(ordinal)
                text = ""
            block_texts.append(text)

    text = "\n".join(block_texts)
    blocks: list[SourceBlock] = []
    cursor = 0
    for index, block_text in enumerate(block_texts):
        blocks.append(
            SourceBlock(
                kind=DOCX_KIND,
                char_start=cursor,
                char_end=cursor + len(block_text),
                block_start=index + 1,
                block_end=index + 1,
            )
        )
        cursor += len(block_text) + 1

    warnings: list[str] = []
    if failed_blocks:
        warnings.append(f"第 {failed_blocks[:10]} 个段落/表格提取失败，未包含其内容。")
    try:
        drawing_count = sum(1 for _ in body.iter(qn("w:drawing")))
        math_count = sum(1 for _ in body.iter(qn("m:oMath")))
    except Exception:  # noqa: BLE001 - 统计失败不影响正文
        drawing_count = 0
        math_count = 0
    if drawing_count:
        warnings.append(f"文档包含 {drawing_count} 处图片/图形，未提取其内容。")
    if math_count:
        warnings.append(f"文档包含 {math_count} 处公式对象，仅保留其可见文本。")
    return ParsedDocument(
        normalized_text=text,
        char_count=len(text),
        source_kind=DOCX_KIND,
        source_map=list(blocks),
        page_count=None,
        block_count=len(block_texts),
        warnings=list(warnings),
        needs_ocr=False,
    )


def text_sha256(text: str) -> str:
    """规范化文本指纹：UTF-8 字节的 sha256。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
