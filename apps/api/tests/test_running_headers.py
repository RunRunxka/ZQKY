"""页眉/页脚与页码行清洗（C4-5）：strip_running_headers 回归。

- 跨 ≥3 个 chunk 重复出现的首/尾短行（页眉/页脚）被剔除；
- 页码行（纯数字等）位于 chunk 首尾时剔除；
- 正文中间行绝不触碰；剔除后坐标正确映射回原文。
"""

from __future__ import annotations

from app.services.document_parsing.chunking import ChunkInput, strip_running_headers

LINES = [
    "第一章 有理数",   # 页眉（每 chunk 重复）
    "1.1 正数与负数",
    "正文甲第一段内容。",
    "1",               # 页码
    "第一章 有理数",
    "1.2 数轴",
    "正文乙第一段内容。",
    "2",
    "第一章 有理数",
    "1.3 相反数",
    "正文丙第一段内容。",
    "3",
    "第一章 有理数",
    "1.4 绝对值",
    "正文丁第一段内容。",
]
NORMALIZED = "\n".join(LINES)
#: 每行起始字符偏移
OFFSETS = []
pos = 0
for line in LINES:
    OFFSETS.append(pos)
    pos += len(line) + 1

#: 5 个 chunk，每个 3 行（首行=页眉、末行=页码 或正文行序依 CHUNK_LINES）
CHUNK_LINES = [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11), (12, 13, 14)]


def _chunks() -> list[ChunkInput]:
    chunks = []
    for i, group in enumerate(CHUNK_LINES):
        start = OFFSETS[group[0]]
        end = OFFSETS[group[-1]] + len(LINES[group[-1]])
        chunks.append(ChunkInput(ordinal=i, char_start=start, char_end=end, region="body",
                                 chapter_path=("第一章 有理数",), text_sha256=""))
    return chunks


def test_repeated_header_and_page_numbers_removed() -> None:
    kept = strip_running_headers(_chunks(), NORMALIZED)
    assert len(kept) == len(CHUNK_LINES)
    for chunk in kept:
        text = NORMALIZED[chunk.char_start:chunk.char_end]
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        assert lines[0] != "第一章 有理数", text
        assert lines[-1] not in {"1", "2", "3"}, text


def test_body_lines_never_touched() -> None:
    kept = strip_running_headers(_chunks(), NORMALIZED)
    all_text = "\n".join(NORMALIZED[c.char_start:c.char_end] for c in kept)
    for line in ("正文甲第一段内容。", "正文乙第一段内容。", "正文丙第一段内容。", "正文丁第一段内容。"):
        assert line in all_text


def test_trimmed_range_hash_rebound_and_ordinals_contiguous() -> None:
    """修复回归：修剪首尾后 char_* 与 text_sha256 必须绑定同一段原文切片。

    上游缺陷（C4-5 曾把坐标移了但没重算哈希）会让检索侧「块指纹一致性」校验
    对真实入库数据报 RAG_EVIDENCE_UNAVAILABLE；本用例用真实切片哈希构造块，
    断言修剪后不变量成立（ordinal 连续 + 哈希=新切片）。
    """
    from app.providers.embeddings.fingerprint import sha256_hex

    real = [
        ChunkInput(
            ordinal=c.ordinal,
            char_start=c.char_start,
            char_end=c.char_end,
            region=c.region,
            chapter_path=c.chapter_path,
            text_sha256=sha256_hex(NORMALIZED[c.char_start:c.char_end]),
        )
        for c in _chunks()
    ]
    kept = strip_running_headers(real, NORMALIZED)
    assert [c.ordinal for c in kept] == list(range(len(kept)))
    for chunk in kept:
        assert sha256_hex(NORMALIZED[chunk.char_start:chunk.char_end]) == chunk.text_sha256
    # 覆盖力：至少有一块确实发生了区间修剪
    assert any(
        (k.char_start, k.char_end) != (r.char_start, r.char_end) for k, r in zip(kept, real)
    )
