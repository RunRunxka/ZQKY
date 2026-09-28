"""解析、来源映射、正文/习题区与分块不变式。

三种格式的样本都在程序内构造（PDF 手工生成 xref 正确的文本层文件，DOCX 用 python-docx 生成），
不读正式教材目录、不写正式 .local-data。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.services.document_parsing import (
    BODY_SHARE_FLOOR,
    DEFAULT_CHUNK_POLICY,
    DEGRADED_WARNING_PREFIX,
    LEGACY_REGION_RULES_VERSION,
    LOW_BODY_SHARE_WARNING_PREFIX,
    PARSER_VERSION,
    REGION_RULES_VERSION,
    ChunkPolicy,
    analyze_regions,
    chunk_document,
    chunk_manifest_sha256,
    chunk_policy_fingerprint,
    chunk_policy_from_json,
    chunk_policy_json,
    chunk_region_share,
    is_exercise_marker_line,
    is_section_heading_line,
    parse_document,
    parsed_from_source_map,
    source_map_payload,
    split_regions,
)
from app.services.document_parsing.regions import region_for_span

# ------------------------------------------------------------------ PDF 构造


def _build_pdf(page_texts: list[str], *, with_text_stream: bool = True) -> bytes:
    """手工生成最小合法 PDF：文本层用 Tj 写入，xref 偏移按实际字节计算。"""
    objects: dict[int, bytes] = {}
    kids: list[int] = []
    next_id = 4
    for text in page_texts:
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        kids.append(page_id)
        escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        stream = (
            f"BT /F1 14 Tf 20 150 Td ({escaped}) Tj ET".encode("latin-1")
            if with_text_stream
            else b""
        )
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        objects[content_id] = (
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = (
        "<< /Type /Pages /Kids ["
        + " ".join(f"{kid} 0 R" for kid in kids)
        + f"] /Count {len(kids)} >>"
    ).encode("ascii")
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for oid in sorted(objects):
        offsets[oid] = len(out)
        out += f"{oid} 0 obj\n".encode("ascii") + objects[oid] + b"\nendobj\n"
    xref_offset = len(out)
    count = max(objects) + 1
    out += f"xref\n0 {count}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for oid in range(1, count):
        out += f"{offsets.get(oid, 0):010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)


def _build_docx(path: Path) -> None:
    from docx import Document as DocxDocument

    document = DocxDocument()
    document.add_paragraph("第一章 集合")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "组别"
    table.cell(0, 1).text = "含义"
    table.cell(1, 0).text = "A组"
    table.cell(1, 1).text = "基础题"
    document.add_paragraph("正文段落：集合的表示方法。")
    document.save(str(path))


# ------------------------------------------------------------------ Markdown


def test_markdown_normalization_and_source_map(tmp_path: Path) -> None:
    path = tmp_path / "chapter.md"
    path.write_bytes("# 标题  \r\n\r\n正文一。\r\n正文二。   \n".encode("utf-8"))
    parsed = parse_document(path=path, file_name="chapter.md", parser_version=PARSER_VERSION)

    assert parsed.source_kind == "markdown"
    assert parsed.normalized_text == "# 标题\n\n正文一。\n正文二。\n"
    assert parsed.char_count == len(parsed.normalized_text)
    assert parsed.needs_ocr is False
    assert parsed.page_count is None
    assert parsed.block_count == 5  # 包含末尾空行
    assert len(parsed.source_map) == 5

    # 1 基闭区间行号，且每个区间都是合法子区间
    assert parsed.source_map[0].line_start == 1 and parsed.source_map[0].line_end == 1
    assert parsed.source_map[3].line_start == 4
    for block in parsed.source_map:
        assert 0 <= block.char_start <= block.char_end <= parsed.char_count
        assert parsed.normalized_text[block.char_start:block.char_end] in {
            "# 标题", "", "正文一。", "正文二。"
        }
    # 行尾空格被去掉、正文内容未压缩
    assert parsed.normalized_text.split("\n")[3] == "正文二。"


def test_txt_suffix_uses_markdown_reader(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("第一行\n第二行\n", encoding="utf-8")
    parsed = parse_document(path=path, file_name="notes.txt", parser_version=PARSER_VERSION)
    assert parsed.source_kind == "markdown"
    assert parsed.normalized_text == "第一行\n第二行\n"


def test_unsupported_suffix_is_422(tmp_path: Path) -> None:
    path = tmp_path / "book.epub"
    path.write_bytes(b"nope")
    with pytest.raises(AppError) as exc_info:
        parse_document(path=path, file_name="book.epub", parser_version=PARSER_VERSION)
    assert (exc_info.value.code, exc_info.value.status_code) == (
        "UNSUPPORTED_DOCUMENT_FORMAT",
        422,
    )


def test_unknown_parser_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(AppError) as exc_info:
        parse_document(path=path, file_name="a.md", parser_version="zqky-parse-v0")
    assert exc_info.value.code == "UNSUPPORTED_PARSER_VERSION"


# ----------------------------------------------------------------------- PDF


def test_pdf_extracts_text_with_page_source_map(tmp_path: Path) -> None:
    path = tmp_path / "book.pdf"
    path.write_bytes(_build_pdf(["First page content", "Second page content"]))
    parsed = parse_document(path=path, file_name="book.pdf", parser_version=PARSER_VERSION)

    assert parsed.source_kind == "pdf"
    assert parsed.page_count == 2
    assert parsed.needs_ocr is False
    assert "First page content" in parsed.normalized_text
    assert "Second page content" in parsed.normalized_text
    assert parsed.normalized_text == "First page content\n\nSecond page content"
    assert len(parsed.source_map) == 2
    first, second = parsed.source_map
    assert (first.page_start, first.page_end) == (1, 1)
    assert (second.page_start, second.page_end) == (2, 2)
    assert second.char_start > first.char_end  # 页间 "\n\n" 落在区间之外
    assert parsed.normalized_text[first.char_start:first.char_end] == "First page content"
    assert "blockCount" in source_map_payload(parsed)


def test_pdf_without_text_layer_needs_ocr(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    path.write_bytes(_build_pdf([""], with_text_stream=False))

    with pytest.raises(AppError) as exc_info:
        parse_document(path=path, file_name="scan.pdf", parser_version=PARSER_VERSION)
    assert (exc_info.value.code, exc_info.value.status_code) == ("DOCUMENT_NEEDS_OCR", 422)

    parsed = parse_document(
        path=path,
        file_name="scan.pdf",
        parser_version=PARSER_VERSION,
        allow_empty_text=True,
    )
    assert parsed.needs_ocr is True
    assert parsed.normalized_text == ""
    assert parsed.char_count == 0
    assert parsed.source_map == []
    assert any("OCR" in warning or "文本层" in warning for warning in parsed.warnings)


def test_source_map_round_trip_rebuilds_parsed_document(tmp_path: Path) -> None:
    path = tmp_path / "chapter.md"
    path.write_text("# 一\n\n正文。\n", encoding="utf-8")
    parsed = parse_document(path=path, file_name="chapter.md", parser_version=PARSER_VERSION)
    payload = source_map_payload(parsed)
    rebuilt = parsed_from_source_map(payload, normalized_text=parsed.normalized_text)
    assert rebuilt.normalized_text == parsed.normalized_text
    assert rebuilt.char_count == parsed.char_count
    assert [block.to_json() for block in rebuilt.source_map] == [
        block.to_json() for block in parsed.source_map
    ]


def test_source_map_corruption_is_explicit() -> None:
    with pytest.raises(AppError) as exc_info:
        parsed_from_source_map({"sourceKind": "markdown", "blocks": [{"kind": "markdown"}]}, normalized_text="x")
    assert exc_info.value.code == "SOURCE_MAP_CORRUPT"


# ---------------------------------------------------------------------- DOCX


def test_docx_paragraphs_tables_and_block_numbers(tmp_path: Path) -> None:
    path = tmp_path / "book.docx"
    _build_docx(path)
    parsed = parse_document(path=path, file_name="book.docx", parser_version=PARSER_VERSION)

    assert parsed.source_kind == "docx"
    assert parsed.block_count == 3
    assert len(parsed.source_map) == 3
    assert [block.block_start for block in parsed.source_map] == [1, 2, 3]
    assert parsed.normalized_text.split("\n")[0] == "第一章 集合"
    assert "[表格]" in parsed.normalized_text
    assert "组别 | 含义" in parsed.normalized_text
    assert "A组 | 基础题" in parsed.normalized_text
    assert parsed.normalized_text.endswith("正文段落：集合的表示方法。")
    assert parsed.char_count == len(parsed.normalized_text)
    assert parsed.needs_ocr is False
    # 表格文本挂在第 2 块的区间里
    table_block = parsed.source_map[1]
    assert "A组" in parsed.normalized_text[table_block.char_start:table_block.char_end]


def test_corrupt_docx_is_parse_failure_not_empty_success(tmp_path: Path) -> None:
    path = tmp_path / "broken.docx"
    path.write_bytes(b"this is not a zip")
    with pytest.raises(AppError) as exc_info:
        parse_document(path=path, file_name="broken.docx", parser_version=PARSER_VERSION)
    assert (exc_info.value.code, exc_info.value.status_code) == ("DOCUMENT_PARSE_FAILED", 422)


# -------------------------------------------------------------------- 区域划分


def test_split_regions_switches_on_exercise_heading(tmp_path: Path) -> None:
    path = tmp_path / "chapter.md"
    path.write_text(
        "# 第一章 集合\n\n正文内容。\n\n## 练习 1.1\n\n1. 求并集。\n", encoding="utf-8"
    )
    parsed = parse_document(path=path, file_name="chapter.md", parser_version=PARSER_VERSION)
    regions = split_regions(parsed)
    assert [span.region for span in regions] == ["body", "exercise"]
    body, exercise = regions
    assert parsed.normalized_text[body.char_start:body.char_end].endswith("正文内容。\n\n")
    assert exercise.char_start == parsed.normalized_text.index("## 练习 1.1")
    assert "求并集" in parsed.normalized_text[exercise.char_start:exercise.char_end]


def test_region_does_not_flip_back_inside_exercise(tmp_path: Path) -> None:
    """习题区内部的编号题行不会把它切回正文（切回只认"正常章节标题"）。"""
    path = tmp_path / "q.md"
    path.write_text(
        "# 第一章 集合\n\n" + "第一节正文说明。" * 40 + "\n\n"
        "## 习题 1.1\n\n1. 判断。\n\n2. 计算。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="q.md", parser_version=PARSER_VERSION)
    regions = split_regions(parsed)
    assert [span.region for span in regions] == ["body", "exercise"]
    exercise_text = parsed.normalized_text[regions[1].char_start:regions[1].char_end]
    assert "1. 判断。" in exercise_text and "2. 计算。" in exercise_text


def test_body_line_mentioning_exercise_stays_body(tmp_path: Path) -> None:
    path = tmp_path / "body.md"
    path.write_text(
        "# 第一章\n\n本节我们完成练习册上的内容，并讨论更多细节与例题。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="body.md", parser_version=PARSER_VERSION)
    regions = split_regions(parsed)
    assert [span.region for span in regions] == ["body"]


def test_short_marker_line_without_heading_is_exercise(tmp_path: Path) -> None:
    path = tmp_path / "scan.txt"
    path.write_text("第一章 集合\n正文。\n\n练习 1.1\n1. 求并集\n", encoding="utf-8")
    parsed = parse_document(path=path, file_name="scan.txt", parser_version=PARSER_VERSION)
    regions = split_regions(parsed)
    assert [span.region for span in regions] == ["body", "exercise"]


def test_region_for_span_prefers_exercise_on_overlap() -> None:
    from app.services.document_parsing.regions import RegionSpan

    regions = (
        RegionSpan(region="body", char_start=0, char_end=100),
        RegionSpan(region="exercise", char_start=100, char_end=200),
    )
    assert region_for_span(regions, 0, 100) == "body"
    assert region_for_span(regions, 0, 101) == "exercise"
    assert region_for_span(regions, 120, 160) == "exercise"


# ----------------------------------------------------------------------- 分块


def _chunk_sample(tmp_path: Path) -> tuple[Path, object]:
    path = tmp_path / "long.md"
    body = "。".join(f"第{i}段正文说明文字" for i in range(120)) + "。"
    section = "。".join(f"概念说明{i}的展开文字" for i in range(90)) + "。"
    path.write_text(
        "# 第一章 集合\n\n"
        + body
        + "\n\n## 1.1 集合的概念\n\n"
        + section
        + "\n\n集合的表示方法如下：\n\n```python\nprint('fence')\n```\n\n"
        + "设 $x$ 满足 $$x^2 + 1 = 0$$ 的条件，则有结论。\n\n"
        + "| 组别 | 含义 |\n| --- | --- |\n| A组 | 基础 |\n\n"
        + "## 练习 1.1\n\n1. 求并集。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="long.md", parser_version=PARSER_VERSION)
    return path, parsed


def test_chunk_invariants(tmp_path: Path) -> None:
    _path, parsed = _chunk_sample(tmp_path)
    chunks = chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY)
    assert chunks
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))

    previous_start = -1
    for chunk in chunks:
        assert chunk.char_start >= previous_start  # 按 ordinal 单调不减
        assert 0 <= chunk.char_start < chunk.char_end <= parsed.char_count  # 不越界
        assert chunk.region in ("body", "exercise")
        text = parsed.normalized_text[chunk.char_start:chunk.char_end]
        assert text
        # 文本指纹是该块文本的 UTF-8 sha256
        import hashlib

        assert chunk.text_sha256 == hashlib.sha256(text.encode("utf-8")).hexdigest()
        previous_start = chunk.char_start

    # 重叠 ≤ 120，且只在相邻块之间
    for previous, current in zip(chunks, chunks[1:]):
        if current.char_start < previous.char_end:
            assert previous.char_end - current.char_start <= DEFAULT_CHUNK_POLICY.overlap_chars

    # 章节路径取自块起点所在的最近 Markdown 标题（块内出现的标题由后续块承接）
    assert chunks[0].chapter_path == ("第一章 集合",)
    assert any(chunk.chapter_path == ("第一章 集合", "1.1 集合的概念") for chunk in chunks)
    # 习题区所在的块被判为 exercise（保守方向：不把习题当正文）
    assert any(chunk.region == "exercise" for chunk in chunks)


def test_chunk_boundaries_never_split_math_pairs(tmp_path: Path) -> None:
    _path, parsed = _chunk_sample(tmp_path)
    text = parsed.normalized_text
    chunks = chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY)
    # 每个块的 $$ 数量必须是偶数 → 没有块以半个公式结尾
    for chunk in chunks:
        assert text[chunk.char_start:chunk.char_end].count("$$") % 2 == 0
    # 全文里每个 $$ 对都必须完整落在某个块内
    pairs: list[tuple[int, int]] = []
    cursor = 0
    while True:
        opening = text.find("$$", cursor)
        if opening == -1:
            break
        closing = text.find("$$", opening + 2)
        assert closing != -1
        pairs.append((opening, closing + 2))
        cursor = closing + 2
    assert pairs
    for opening, closing in pairs:
        assert any(
            chunk.char_start <= opening and chunk.char_end >= closing for chunk in chunks
        ), (opening, closing)


def test_chunk_oversized_paragraph_is_split_at_safe_points() -> None:
    from app.services.document_parsing import ParsedDocument

    sentence = "这是一句完整的说明文字。"
    text = sentence * 300  # 单行 3600 码点，远超上限
    parsed = ParsedDocument(
        normalized_text=text,
        char_count=len(text),
        source_kind="markdown",
        source_map=(),
        page_count=None,
        block_count=1,
        warnings=(),
        needs_ocr=False,
    )
    chunks = chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY)
    assert len(chunks) > 1
    for chunk in chunks:
        piece = text[chunk.char_start:chunk.char_end]
        assert piece.startswith("这")  # 切点落在句号之后
        assert piece.endswith("。")


def test_oversized_indivisible_block_is_kept_whole() -> None:
    from app.services.document_parsing import ParsedDocument

    formula = "$$" + "x" * 1500 + "$$"
    parsed = ParsedDocument(
        normalized_text=formula,
        char_count=len(formula),
        source_kind="markdown",
        source_map=(),
        page_count=None,
        block_count=1,
        warnings=(),
        needs_ocr=False,
    )
    chunks = chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY)
    assert len(chunks) == 1
    assert parsed.normalized_text[chunks[0].char_start:chunks[0].char_end] == formula


def test_chunk_policy_fingerprint_and_manifest() -> None:
    from app.services.document_parsing import ParsedDocument

    text = "第一段。" * 300 + "\n" + "第二段。" * 300
    parsed = ParsedDocument(
        normalized_text=text,
        char_count=len(text),
        source_kind="markdown",
        source_map=(),
        page_count=None,
        block_count=2,
        warnings=(),
        needs_ocr=False,
    )
    chunks = chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY)
    assert len(chunks) > 1
    assert chunk_policy_fingerprint() == chunk_policy_fingerprint(DEFAULT_CHUNK_POLICY)
    assert chunk_policy_json(DEFAULT_CHUNK_POLICY)["targetChars"] == 800
    other = ChunkPolicy(target_chars=400, max_chars=600, overlap_chars=60)
    assert chunk_policy_fingerprint(other) != chunk_policy_fingerprint(DEFAULT_CHUNK_POLICY)
    assert chunk_manifest_sha256(chunks) == chunk_manifest_sha256(chunks)
    import dataclasses

    altered = list(chunks)
    altered[0] = dataclasses.replace(altered[0], text_sha256="f" * 64)
    assert chunk_manifest_sha256(altered) != chunk_manifest_sha256(chunks)


def test_empty_text_produces_no_chunks() -> None:
    from app.services.document_parsing import ParsedDocument

    parsed = ParsedDocument(
        normalized_text="",
        char_count=0,
        source_kind="pdf",
        source_map=(),
        page_count=1,
        block_count=None,
        warnings=("需要 OCR",),
        needs_ocr=True,
    )
    assert chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY) == []


def test_chunk_policy_validation() -> None:
    with pytest.raises(ValueError):
        ChunkPolicy(target_chars=0)
    with pytest.raises(ValueError):
        ChunkPolicy(target_chars=800, max_chars=400)
    with pytest.raises(ValueError):
        ChunkPolicy(overlap_chars=200)


# --------------------------------------------- v1.2 正文/习题区（真实教材版式）


def test_toc_lines_do_not_trigger_exercise(tmp_path: Path) -> None:
    """目录行（省略号+页码 / 标题+页码）不得把全书切成习题区。"""
    path = tmp_path / "with-toc.md"
    path.write_text(
        "# 数学\n\n"
        "## 目录\n\n"
        "第一章 空间向量与立体几何 …… 1\n"
        "1.1 空间向量及其运算…… 2\n"
        "小结…… 45\n"
        "复习参考题 1 …… 47\n"
        "第一章 运动的描述 10\n"
        "练习与应用 12\n\n"
        "## 1.1 空间向量及其运算\n\n"
        "正文第一段说明。\n\n"
        "## 1.2 空间向量基本定理\n\n"
        "正文第二段说明。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="with-toc.md", parser_version=PARSER_VERSION)
    for line in (
        "复习参考题 1 …… 47",
        "小结…… 45",
        "第一章 运动的描述 10",
        "练习与应用 12",
    ):
        assert is_exercise_marker_line(line) is False, line
    regions = split_regions(parsed)
    assert [span.region for span in regions] == ["body"]
    assert regions[0].char_end == parsed.char_count


def test_regions_alternate_body_exercise_body_exercise_body(tmp_path: Path) -> None:
    """body→练习→body→练习→body：必须交替产出多个 span，且两区都非空。"""
    path = tmp_path / "alternating.md"
    path.write_text(
        "# 第一章 集合\n\n"
        "第一节正文内容。\n\n"
        "## 练习 1.1\n\n1. 第一组练习题。\n\n"
        "## 1.2 集合间的基本关系\n\n"
        "第二节正文内容。\n\n"
        "## 习题 1.2\n\n2. 第二组练习题。\n\n"
        "## 1.3 集合的基本运算\n\n"
        "第三节正文内容。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="alternating.md", parser_version=PARSER_VERSION)
    regions = split_regions(parsed)
    assert [span.region for span in regions] == [
        "body",
        "exercise",
        "body",
        "exercise",
        "body",
    ]
    texts = [
        parsed.normalized_text[span.char_start:span.char_end] for span in regions
    ]
    assert "第一节正文内容。" in texts[0]
    assert "第一组练习题。" in texts[1]
    assert "第二节正文内容。" in texts[2]
    assert "第二组练习题。" in texts[3]
    assert "第三节正文内容。" in texts[4]
    # 覆盖全文且无缝隙
    assert regions[0].char_start == 0 and regions[-1].char_end == parsed.char_count
    for previous, current in zip(regions, regions[1:]):
        assert previous.char_end == current.char_start


def test_exercise_dominated_document_is_degraded_with_warning(tmp_path: Path) -> None:
    """整本几乎都是习题 → 健全性守卫：记录可读警告并降级为整篇正文。"""
    path = tmp_path / "all-exercises.md"
    body = "\n\n".join(f"{index}. 第{index}道练习题，计算并说明。 " for index in range(1, 80))
    path.write_text(f"# 习题 1.1\n\n{body}\n", encoding="utf-8")
    parsed = parse_document(path=path, file_name="all-exercises.md", parser_version=PARSER_VERSION)

    assert parsed.warnings, "划分异常必须留下警告"
    warning = parsed.warnings[0]
    assert warning.startswith(DEGRADED_WARNING_PREFIX)
    assert "习题区占" in warning and "已按正文处理" in warning
    regions = split_regions(parsed)
    assert len(regions) == 1  # 降级为整篇 body
    assert regions[0].region == "body"
    assert (regions[0].char_start, regions[0].char_end) == (0, parsed.char_count)
    # 分块的区也随降级结果（不会用错误划分去索引）
    chunks = chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY)
    assert chunks and {chunk.region for chunk in chunks} == {"body"}


def test_normal_document_has_no_region_warning(tmp_path: Path) -> None:
    path = tmp_path / "normal.md"
    path.write_text(
        "# 第一章 集合\n\n" + "正文说明。" * 60 + "\n\n## 练习 1.1\n\n1. 求并集。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="normal.md", parser_version=PARSER_VERSION)
    assert parsed.warnings == []


def test_inline_exercise_mention_does_not_switch(tmp_path: Path) -> None:
    """正文里内联提到习题（不在标题行/不在行首）不触发切换。"""
    path = tmp_path / "inline.md"
    path.write_text(
        "# 第一章 集合\n\n"
        "本节我们完成练习册上的内容，并讨论更多细节与例题。\n\n"
        "## 关于练习题的说明\n\n"
        "正文继续。\n\n"
        "参考习题 1.1 的结论可以得到更一般的性质。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="inline.md", parser_version=PARSER_VERSION)
    assert [span.region for span in regions_of(parsed)] == ["body"]
    assert is_exercise_marker_line("本节我们完成练习册上的内容，并讨论更多细节与例题。") is False
    assert is_exercise_marker_line("## 关于练习题的说明") is False
    assert is_exercise_marker_line("参考习题 1.1 的结论可以得到更一般的性质。") is False


def test_marker_variants_and_section_returns(tmp_path: Path) -> None:
    """真实教材的标记形态：命中列表内、目录形态排除、小节标题回切正文。"""
    for line in (
        "练习",
        "## 练习",
        "## 练习 1.1",
        "## 习题1.1",
        "## 习题 1.3",
        "## 复习参考题 10",
        "## 复习巩固",
        "## 综合运用",
        "## 拓广探索",
        "## A组",
        "B组",
        "## 章末",
        "## 单元小结",
        "练习与应用",
    ):
        assert is_exercise_marker_line(line) is True, line
    for line in (
        "复习参考题 1 …… 47",
        "第一章 运动的描述 10",
        "## 练习与应用 12",
        "练习与应用 针对每节内容所设计的练习题，用于巩固所学的概念、规律和方法。",
    ):
        assert is_exercise_marker_line(line) is False, line
    for line in ("## 1.1.2 空间向量的数量积运算", "## 1.2 空间向量基本定理", "## 第一章 空间向量与立体几何",
                 "## 第2节细胞的多样性和统一性", "## 2 时间 位移", "## 阅读与思考", "## 本章小结", "## 小结"):
        assert is_section_heading_line(line) is True, line
    # 习题区内部的小标题（生物学版式）不把习题区切回正文
    for line in ("## 一、概念检测", "## 二、拓展应用", "1. 举出一些实例.", "（1）判断下列说法。"):
        assert is_section_heading_line(line) is False, line
        assert is_exercise_marker_line(line) is False, line


def test_biology_style_exercise_block_stays_exercise(tmp_path: Path) -> None:
    """习题块内部的小标题（概念检测）不得让习题内容漏回正文。"""
    path = tmp_path / "biology-style.md"
    path.write_text(
        "## 第1节细胞是生命活动的基本单位\n\n"
        "正文：细胞是生命活动的基本单位。\n\n"
        "## 练习与应用\n\n"
        "## 一、概念检测\n\n"
        "1．判断下列事实或证据是否支持细胞是生命活动的基本单位。\n\n"
        "## 二、拓展应用\n\n"
        "2．以草履虫为例说明。\n\n"
        "## 第2节细胞的多样性和统一性\n\n"
        "正文继续。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="biology-style.md", parser_version=PARSER_VERSION)
    regions = split_regions(parsed)
    assert [span.region for span in regions] == ["body", "exercise", "body"]
    exercise_text = parsed.normalized_text[regions[1].char_start:regions[1].char_end]
    assert "概念检测" in exercise_text and "拓展应用" in exercise_text
    body_text = parsed.normalized_text[regions[2].char_start:regions[2].char_end]
    assert body_text.startswith("## 第2节细胞的多样性和统一性")


def test_fenced_code_does_not_trigger_regions(tmp_path: Path) -> None:
    path = tmp_path / "fenced.md"
    path.write_text(
        "# 第一章\n\n```\n## 练习\n## 习题 1.1\n```\n\n正文内容。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="fenced.md", parser_version=PARSER_VERSION)
    assert [span.region for span in split_regions(parsed)] == ["body"]


def regions_of(parsed):
    from app.services.document_parsing.regions import split_regions as _split

    return _split(parsed)


# ------------------------------------------- v1.2 划分规则版本进入分块指纹


#: v1.0/v1.1（4 键 JSON、无 regionRulesVersion）的固定指纹，作为"旧口径"基准
LEGACY_POLICY_FINGERPRINT = "5aace341dcba72254ffce8cb60b798bae30e3a28cdc60959d4ea805930e26df0"
LEGACY_POLICY_JSON = {
    "targetChars": 800,
    "maxChars": 1200,
    "overlapChars": 120,
    "version": "zqky-chunk-v1",
}


def test_region_rules_version_is_exported_and_in_policy() -> None:
    # 版本号本身不写死：只要求"有固定前缀 + 默认策略携带当前版本"
    assert REGION_RULES_VERSION.startswith("zqky-region-v")
    assert REGION_RULES_VERSION != LEGACY_REGION_RULES_VERSION
    assert DEFAULT_CHUNK_POLICY.region_rules_version == REGION_RULES_VERSION
    assert (
        chunk_policy_json(DEFAULT_CHUNK_POLICY)["regionRulesVersion"] == REGION_RULES_VERSION
    )


def test_different_region_rules_version_changes_fingerprint() -> None:
    base = ChunkPolicy()
    same = ChunkPolicy(region_rules_version=REGION_RULES_VERSION)
    other = ChunkPolicy(region_rules_version="zqky-region-v99")
    legacy = ChunkPolicy(region_rules_version=LEGACY_REGION_RULES_VERSION)
    assert chunk_policy_fingerprint(base) == chunk_policy_fingerprint(same)
    assert chunk_policy_fingerprint(other) != chunk_policy_fingerprint(base)
    assert chunk_policy_fingerprint(legacy) != chunk_policy_fingerprint(base)
    # 其他参数一致时，差异必须只来自划分规则版本
    assert chunk_policy_json(other)["regionRulesVersion"] == "zqky-region-v99"


def test_legacy_policy_json_reads_and_keeps_old_fingerprint() -> None:
    """历史 JSON（缺 regionRulesVersion）可读、序列化回到旧口径、指纹与 v1.1 完全一致。"""
    policy = chunk_policy_from_json(LEGACY_POLICY_JSON)
    assert policy.region_rules_version == LEGACY_REGION_RULES_VERSION
    assert chunk_policy_json(policy) == LEGACY_POLICY_JSON  # 4 键，不写入新字段
    assert chunk_policy_fingerprint(policy) == LEGACY_POLICY_FINGERPRINT
    # 新版默认策略的指纹必须与旧口径不同：改规则后必然重建分块集
    assert chunk_policy_fingerprint(DEFAULT_CHUNK_POLICY) != LEGACY_POLICY_FINGERPRINT
    # 新口径往返一致
    assert chunk_policy_fingerprint(
        chunk_policy_from_json(chunk_policy_json(DEFAULT_CHUNK_POLICY))
    ) == chunk_policy_fingerprint(DEFAULT_CHUNK_POLICY)


def test_corrupt_policy_json_still_raises() -> None:
    with pytest.raises(AppError) as exc_info:
        chunk_policy_from_json({"targetChars": 0, "maxChars": 10, "overlapChars": 0})
    assert exc_info.value.code == "CHUNK_POLICY_CORRUPT"
    with pytest.raises(AppError) as not_object:
        chunk_policy_from_json("nope")
    assert not_object.value.code == "CHUNK_POLICY_CORRUPT"


# ------------------------------ v1.4 块级区域归属（A1 D3）、正文占比守卫与真实标题形态


def _region_chars(text_regions, chunk, region: str) -> int:
    total = 0
    for span in text_regions:
        if span.region != region:
            continue
        total += max(
            0, min(chunk.char_end, span.char_end) - max(chunk.char_start, span.char_start)
        )
    return total


def test_three_level_section_heading_after_exercise_returns_to_body(tmp_path: Path) -> None:
    """A1 实测形态：`## 1.1.2 …` 这类三级编号标题出现在习题区之后必须回切正文。"""
    path = tmp_path / "a1-shape.md"
    path.write_text(
        "## 1.1.1 空间向量及其线性运算\n\n"
        "正文：向量的线性运算满足交换律与结合律。\n\n"
        "## 练习\n\n1. 化简下列表达式。\n\n2. 作出图示。\n\n"
        "## 1.1.2 空间向量的数量积运算\n\n"
        "定理：两个向量的数量积满足交换律。证明如下：设 a、b 为任意向量，则……\n\n"
        "## 探究与发现\n\n请思考数量积的几何意义。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="a1-shape.md", parser_version=PARSER_VERSION)
    regions = split_regions(parsed)
    assert [span.region for span in regions] == ["body", "exercise", "body"]
    body_after = parsed.normalized_text[regions[2].char_start:regions[2].char_end]
    assert body_after.startswith("## 1.1.2 空间向量的数量积运算")
    assert "定理：两个向量的数量积满足交换律" in body_after

    chunks = chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY)
    heading_chunk = next(
        chunk for chunk in chunks if chunk.char_start <= regions[2].char_start < chunk.char_end
    )
    # 含三级标题与定理证明的块必须是 body，否则这段正文永远检索不到
    assert heading_chunk.region == "body"
    # 去掉重叠尾巴（≤120 码点上下文）后，块主体只属于正文区
    assert _region_chars(regions, heading_chunk, "body") >= (
        heading_chunk.char_end - heading_chunk.char_start - DEFAULT_CHUNK_POLICY.overlap_chars
    )


def test_chunks_do_not_swallow_other_region_beyond_overlap(tmp_path: Path) -> None:
    """每块主体只属于一个区：正文不再被并进 exercise 块（块级 body 占比 ≈ 区间占比）。"""
    path = tmp_path / "alternating-long.md"
    body = "正文说明文字。" * 70      # ~490 码点
    items = "练习题。" * 40           # ~200 码点
    path.write_text(
        "\n\n".join(
            f"## 1.{index} 小节标题\n\n{body}\n\n## 练习 1.{index}\n\n{items}"
            for index in range(1, 6)
        )
        + "\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="alternating-long.md", parser_version=PARSER_VERSION)
    regions = split_regions(parsed)
    assert any(span.region == "exercise" for span in regions)
    chunks = chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY)
    overlap = DEFAULT_CHUNK_POLICY.overlap_chars

    for chunk in chunks:
        length = chunk.char_end - chunk.char_start
        if length <= overlap:
            continue  # 全部由重叠尾巴构成的小块：不约束
        own = _region_chars(regions, chunk, chunk.region)
        assert own >= length - overlap, (chunk.ordinal, chunk.region, own, length)

    share, body_chunks, total_chunks = chunk_region_share(chunks)
    span_body_share = sum(
        span.char_end - span.char_start for span in regions if span.region == "body"
    ) / len(parsed.normalized_text)
    assert share >= span_body_share - 0.05, (share, span_body_share)
    assert share >= 0.50
    assert body_chunks < total_chunks  # 习题区确实被排除


def test_chunk_region_share_helper() -> None:
    from app.repositories.textbook_catalog.records import ChunkInput

    chunks = [
        ChunkInput(ordinal=0, char_start=0, char_end=100, region="body", chapter_path=(), text_sha256="a"),
        ChunkInput(ordinal=1, char_start=100, char_end=200, region="body", chapter_path=(), text_sha256="b"),
        ChunkInput(ordinal=2, char_start=200, char_end=300, region="exercise", chapter_path=(), text_sha256="c"),
    ]
    share, body_chunks, total = chunk_region_share(chunks)
    assert (body_chunks, total) == (2, 3)
    assert abs(share - 2 / 3) < 1e-9
    assert chunk_region_share([]) == (0.0, 0, 0)


def test_low_body_share_warns_without_degrading(tmp_path: Path) -> None:
    """正文 <50% 必须告警（不降级，保留真实划分）——v1.4 新增守卫。"""
    path = tmp_path / "exercise-heavy.md"
    body = "正文内容。" * 25           # ~125 码点
    items = "练习题内容。" * 60        # ~360 码点
    path.write_text(
        "\n\n".join(
            f"## 1.{index} 小节\n\n{body}\n\n## 练习 1.{index}\n\n{items}"
            for index in range(1, 5)
        )
        + "\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="exercise-heavy.md", parser_version=PARSER_VERSION)
    report = analyze_regions(parsed.normalized_text)
    assert report.body_ratio < BODY_SHARE_FLOOR
    assert report.low_body_share is True
    assert report.degraded is False          # 只告警，不降级
    assert len(report.spans) > 1             # 保留真实划分
    assert any(warning.startswith(LOW_BODY_SHARE_WARNING_PREFIX) for warning in parsed.warnings)
    warning = next(
        item for item in parsed.warnings if item.startswith(LOW_BODY_SHARE_WARNING_PREFIX)
    )
    assert "正文" in warning and "50%" in warning

    # 正常教材版式不触发该守卫
    ok_path = tmp_path / "normal.md"
    ok_path.write_text(
        "# 第一章 集合\n\n" + "正文说明。" * 200 + "\n\n## 练习 1.1\n\n1. 求并集。\n",
        encoding="utf-8",
    )
    ok_parsed = parse_document(path=ok_path, file_name="normal.md", parser_version=PARSER_VERSION)
    ok_report = analyze_regions(ok_parsed.normalized_text)
    assert ok_report.low_body_share is False
    assert ok_report.body_ratio >= BODY_SHARE_FLOOR
    assert ok_parsed.warnings == []


def test_trailing_exercise_block_has_no_phantom_body_chunk(tmp_path: Path) -> None:
    """文末习题块（含末尾空行）不得生成"整段落在习题区、标签却是 body"的伪块。

    v1.4 回归：末尾零长度原子曾与重叠尾巴拼出跨区的 body 块（B2 的原文证据用例先发现）。
    """
    path = tmp_path / "tail.md"
    path.write_text(
        "# 第一章 集合\n\n"
        + "集合的表示方法。" * 120
        + "\n\n## 练习 1.1\n\n1. 求并集。\n",
        encoding="utf-8",
    )
    parsed = parse_document(path=path, file_name="tail.md", parser_version=PARSER_VERSION)
    regions = split_regions(parsed)
    exercise_spans = [span for span in regions if span.region == "exercise"]
    assert exercise_spans
    chunks = chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY)
    assert chunks
    for chunk in chunks:
        # body 块：不得整体落在习题区内，习题字符不得超过重叠上限
        if chunk.region == "body":
            inside = any(
                span.char_start <= chunk.char_start and chunk.char_end <= span.char_end
                for span in exercise_spans
            )
            assert not inside, (chunk.ordinal, chunk.char_start, chunk.char_end)
            assert _region_chars(regions, chunk, "exercise") <= DEFAULT_CHUNK_POLICY.overlap_chars
        else:
            assert _region_chars(regions, chunk, "body") <= DEFAULT_CHUNK_POLICY.overlap_chars
    # 习题文本只出现在 exercise 块里（不允许被 body 块完整复刻）
    exercise_text = parsed.normalized_text[exercise_spans[0].char_start:exercise_spans[0].char_end].strip()
    body_text = "".join(
        parsed.normalized_text[chunk.char_start:chunk.char_end]
        for chunk in chunks
        if chunk.region == "body"
    )
    assert exercise_text not in body_text
