"""原文证据重建：不可变切片、有界邻块窗口、预算取舍与来源定位一致性。

RAG-QUALITY v1.1（PLAN §3.3）后本文件断言的口径：

- 邻块扩展**左右各最多 1 块**（旧实现沿同章无上限扩张，823 码点命中扩成整章 45,577 码点）；
- 单条原文切片 ≤ ``EVIDENCE_SINGLE_RAW_MAX_CHARS``、清洗后文本 ≤
  ``EVIDENCE_SINGLE_CLEANED_MAX_CHARS``；首答 ≤6 条、原文总量 ≤ ``EVIDENCE_TOTAL_RAW_MAX_CHARS``；
- 每条证据带 ``readable``（清洗投影），``text`` 仍是逐字节一致的封存原文切片。
"""

from __future__ import annotations

import pytest

from app.services.text_projection import TEXT_PROJECTION_VERSION
from app.core.exceptions import AppError
from app.core.rag_budget import (
    EVIDENCE_SINGLE_CLEANED_MAX_CHARS,
    EVIDENCE_SINGLE_RAW_MAX_CHARS,
    EVIDENCE_TOTAL_RAW_MAX_CHARS,
    FIRST_ANSWER_EVIDENCE_MAX_ITEMS,
)
from app.providers.embeddings.fingerprint import canonical_json
from app.services.document_parsing import parsed_from_source_map, split_regions
from app.services.rag_v2.evidence import (
    build_evidence,
    evidence_id,
    select_evidence,
    sha256_utf8,
)
from app.services.rag_v2.retrieval import Candidate
from app.services.rag_v2.scope import verify_scope
from app.services.textbook_ingest.source_access import read_source_span
from tests.test_rag_v2_support import RagEnv, multi_chapter_text, textbook_text

#: 含公式、emoji 的正文：验证逐字节一致与码点坐标
BODY_LINE = "集合的 $$A\\cup B$$ 运算与 emoji 🙂 说明，注意区间端点。"
FORMULA_TEXT = "# 第一章 集合\n\n" + BODY_LINE * 90 + "\n\n## 练习 1.1\n\n1. 求并集。\n"

SINGLE_BODY_TEXT = (
    "# 集合\n\n" + "集合的表示方法。" * 120 + "\n\n## 练习 1.1\n\n1. 求并集。\n"
)


def candidate_for(chunk, *, chunk_set_id: str, revision_id: str, score: float = 0.03) -> Candidate:
    return Candidate(
        chunk_set_id=chunk_set_id,
        ordinal=chunk.ordinal,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        region=chunk.region,
        chapter_path=tuple(chunk.chapter_path),
        dense_rank=1,
        lexical_rank=None,
        fused_score=score,
        document_revision_id=revision_id,
    )


def test_evidence_text_is_byte_identical_to_immutable_normalized_text(tmp_path):
    env = RagEnv(tmp_path)
    path = tmp_path / "formula.md"
    path.write_bytes(FORMULA_TEXT.replace("\n", "\r\n").encode("utf-8"))
    document = env.add_document(title="含公式与 emoji 的册", text=path.read_text(encoding="utf-8"))
    scope = verify_scope(env.catalog, env.snapshot(document))
    body_chunks = document.body_chunks()
    assert len(body_chunks) >= 3, "正文应被切成多个块，才能验证跨块合并"
    candidates = [
        candidate_for(
            chunk,
            chunk_set_id=document.chunk_set_id,
            revision_id=document.revision_id,
            score=0.5 - index * 0.01,
        )
        for index, chunk in enumerate(body_chunks)
    ]

    evidence = build_evidence(catalog=env.catalog, scope=scope, candidates=candidates)
    assert evidence, "同一章节的连续正文块至少要产出一条证据，绝不能因超预算整段丢弃"
    assert len(evidence) <= FIRST_ANSWER_EVIDENCE_MAX_ITEMS
    assert sum(len(item.text) for item in evidence) <= EVIDENCE_TOTAL_RAW_MAX_CHARS
    normalized = document.normalized_text
    assert "\r" not in normalized, "规范化文本必须统一 LF"
    revision = env.catalog.get_revision(document.revision_id)
    assert sha256_utf8(normalized) == revision.normalized_text_sha256
    assert len(normalized) == revision.char_count

    # 正文区边界：块的区间可能带跨界重叠尾巴（B1 v1.4「块不跨区」），证据必须裁到正文区内
    parsed = parsed_from_source_map(
        env.blobs.read_json(area="normalized", blob_id=revision.source_map_blob_id),
        normalized_text=normalized,
    )
    regions = split_regions(parsed)
    exercise_start = next(span.char_start for span in regions if span.region == "exercise")
    body_span = next(span for span in regions if span.region == "body")

    for item in evidence:
        assert item.text == normalized[item.charStart : item.charEnd]
        assert len(item.text) <= EVIDENCE_SINGLE_RAW_MAX_CHARS
        assert item.evidenceId == evidence_id(document.revision_id, item.charStart, item.charEnd)
        assert item.normalizedTextSha256 == revision.normalized_text_sha256
        assert item.documentId == document.document_id
        assert item.isSuperseded is False
        assert item.chapterPath == ["第一章 集合"]
        assert item.originalFileSha256 == revision.original_file_sha256
        assert item.locator.kind == "markdown"
        assert item.locator.lineStart is not None and item.locator.lineStart >= 1
        # 清洗只产生派生展示文本：readable 必须存在，且不得改变封存原文切片
        assert item.readable is not None and item.readable.version == TEXT_PROJECTION_VERSION
        assert item.readable.text.strip(), "有文本命中时清洗后不得为空"
        assert len(item.readable.text) <= EVIDENCE_SINGLE_CLEANED_MAX_CHARS
        # 证据必须整段落在正文区：习题区文本永不作为知识点依据
        assert item.charStart >= body_span.char_start and item.charEnd <= body_span.char_end
        assert item.charEnd <= exercise_start
        assert "练习" not in item.text

        # 定位与 source_access 的受控读取逐字段一致（同一套来源映射语义）
        expected = read_source_span(
            catalog=env.catalog,
            blobs=env.blobs,
            revision_id=document.revision_id,
            char_start=item.charStart,
            char_end=item.charEnd,
        )
        assert item.locator == expected.locator
        assert item.text == expected.text

    assert any("$$A\\cup B$$" in item.text and "🙂" in item.text for item in evidence), (
        "公式与 emoji 必须逐字保留在证据里"
    )

    # 排名第一的命中块必须被第一条证据覆盖；有序块之间不得重复/重叠地拼出两遍内容
    first_seed = body_chunks[0]
    assert evidence[0].charStart <= first_seed.char_start
    assert evidence[0].charEnd >= first_seed.char_end
    merged = merge_intervals([(item.charStart, item.charEnd) for item in evidence])
    assert len(merged) == 1, "同一章节的连续正文块应被合并成一条连续覆盖，不得重复同一段内容"
    assert merged[0][0] <= body_span.char_start
    assert merged[0][1] >= body_span.char_end - 2, "正文区应被完整覆盖（只允许边界换行缝）"
    for item in evidence:
        assert item.charEnd <= exercise_start


def merge_intervals(intervals: list[tuple[int, int]], *, gap: int = 2) -> list[tuple[int, int]]:
    """把证据区间并成连续覆盖段（允许 ≤2 码点的换行缝）。"""
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1] + gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def test_neighbor_expansion_never_crosses_document_section_or_exercise_gap(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="多章教材", text=multi_chapter_text(("集合", "函数")))
    other = env.add_document(title="另一册", text=SINGLE_BODY_TEXT)
    scope = verify_scope(env.catalog, env.snapshot(document, other))

    body = [chunk for chunk in document.chunks if chunk.region == "body"]
    exercise = [chunk for chunk in document.chunks if chunk.region == "exercise"]
    assert len(exercise) == 1, "末尾习题区应只有一个习题块"
    chapter_one = [chunk for chunk in body if chunk.chapter_path[:1] == ("第1章 集合",)]
    chapter_two = [chunk for chunk in body if chunk.chapter_path[:1] == ("第2章 函数",)]
    assert len(chapter_one) >= 2 and chapter_two

    last_of_one = chapter_one[-1]
    first_of_two = chapter_two[0]
    seeded = [
        candidate_for(
            last_of_one, chunk_set_id=document.chunk_set_id, revision_id=document.revision_id, score=0.9
        ),
        candidate_for(
            first_of_two, chunk_set_id=document.chunk_set_id, revision_id=document.revision_id, score=0.8
        ),
        candidate_for(
            other.body_chunks()[0],
            chunk_set_id=other.chunk_set_id,
            revision_id=other.revision_id,
            score=0.7,
        ),
        candidate_for(
            exercise[0], chunk_set_id=document.chunk_set_id, revision_id=document.revision_id, score=0.6
        ),
    ]
    evidence = build_evidence(catalog=env.catalog, scope=scope, candidates=seeded)
    assert len(evidence) == 3, "两章的正文块各自成段；习题块不产出证据"

    own = [item for item in evidence if item.documentId == document.document_id]
    assert len(own) == 2
    assert [item.documentId for item in evidence if item.documentId == other.document_id] == [
        other.document_id
    ]
    assert sorted(tuple(item.chapterPath) for item in own) == [
        ("第1章 集合",),
        ("第2章 函数",),
    ], "邻块扩展不得跨章节合并"

    normalized = document.normalized_text
    for item in own:
        assert item.charEnd <= exercise[0].char_start, "邻块扩展不得跨越习题区间隙"
        assert item.text == normalized[item.charStart : item.charEnd]
        assert "练习" not in item.text
    for item in evidence:
        assert item.charEnd - item.charStart == len(item.text)


def test_over_long_protected_unit_reports_partial_with_locator_not_no_evidence(tmp_path):
    """单个受保护单元超预算：整条不采用、给出可解释状态与 locator，绝不报"没有找到依据"。"""
    env = RagEnv(tmp_path)
    formula = "$$\n" + "x_{1}+y_{2}=z_{3};" * 400 + "\n$$"  # ≈7,600 码点的单个显示公式
    assert len(formula) > EVIDENCE_SINGLE_RAW_MAX_CHARS
    document = env.add_document(
        title="公式超长册",
        text=f"# 第一章 向量\n\n向量公式：\n\n{formula}\n\n## 练习 1.1\n\n1. 求并集。\n",
    )
    scope = verify_scope(env.catalog, env.snapshot(document))
    body = document.body_chunks()
    hit = max(body, key=lambda chunk: chunk.char_end - chunk.char_start)
    assert hit.char_end - hit.char_start > EVIDENCE_SINGLE_RAW_MAX_CHARS, (
        "本用例依赖不可拆单元超过单条原文上限"
    )

    selection = select_evidence(
        catalog=env.catalog,
        scope=scope,
        candidates=[
            candidate_for(hit, chunk_set_id=document.chunk_set_id, revision_id=document.revision_id)
        ],
    )
    assert selection.status == "partial"
    assert selection.reason_code == "EVIDENCE_UNIT_TOO_LARGE"
    assert selection.evidence == ()
    assert selection.saw_text_hit is True
    assert selection.oversized_locators, "必须附可展示定位"
    locator = selection.oversized_locators[0]
    assert locator.kind == "markdown" and locator.lineStart is not None
    assert "超长公式" in selection.reason and "没有找到" not in selection.reason
    # 兼容入口同样不得把"有命中但装不下"伪装成空结果无解释
    assert build_evidence(catalog=env.catalog, scope=scope, candidates=[]) == []


def test_neighbour_window_covers_at_most_one_block_each_side(tmp_path):
    """邻块扩展左右各最多 1 块：放宽单条预算后仍不得越过相邻的第二块。"""
    env = RagEnv(tmp_path)
    document = env.add_document(title="长章节册", text=textbook_text("集合", paragraphs=120))
    scope = verify_scope(env.catalog, env.snapshot(document))
    body = document.body_chunks()
    assert len(body) >= 6, "本用例需要同章多个可合并块"
    index = len(body) // 2
    selection = select_evidence(
        catalog=env.catalog,
        scope=scope,
        candidates=[
            candidate_for(
                body[index], chunk_set_id=document.chunk_set_id, revision_id=document.revision_id
            )
        ],
        # 放宽单条预算以单独验证"窗口几何"，默认预算下的有界性由 Q3 回归用例覆盖
        max_single_raw_chars=40_000,
        max_single_cleaned_chars=40_000,
        max_total_raw_chars=40_000,
    )
    assert selection.status == "ok" and len(selection.evidence) == 1
    item = selection.evidence[0]
    assert item.charStart <= body[index - 1].char_start, "左侧应补齐相邻块"
    assert item.charStart >= body[index - 2].char_start, "左侧最多补 1 块"
    assert item.charEnd >= body[index + 1].char_end, "右侧应补齐相邻块"
    assert item.charEnd <= body[index + 2].char_end, "右侧最多补 1 块"
    assert item.charEnd - item.charStart <= 40_000
    assert item.text == document.normalized_text[item.charStart : item.charEnd]


def test_evidence_budget_keeps_whole_spans_and_never_truncates(tmp_path):
    env = RagEnv(tmp_path)
    first = env.add_document(title="册一", text=SINGLE_BODY_TEXT)
    second = env.add_document(title="册二", text=SINGLE_BODY_TEXT)
    scope = verify_scope(env.catalog, env.snapshot(first, second))
    candidates = [
        candidate_for(
            first.body_chunks()[0],
            chunk_set_id=first.chunk_set_id,
            revision_id=first.revision_id,
            score=0.9,
        ),
        candidate_for(
            second.body_chunks()[0],
            chunk_set_id=second.chunk_set_id,
            revision_id=second.revision_id,
            score=0.8,
        ),
    ]

    full = build_evidence(catalog=env.catalog, scope=scope, candidates=candidates)
    assert len(full) == 2
    first_span, second_span = full
    assert first_span.documentId == first.document_id

    limited = build_evidence(
        catalog=env.catalog,
        scope=scope,
        candidates=candidates,
        max_chars=len(first_span.text),
    )
    assert len(limited) == 1, "第二条整条放不下就不取"
    assert limited[0].text == first_span.text, "证据不得被截断"

    assert (
        build_evidence(
            catalog=env.catalog,
            scope=scope,
            candidates=candidates,
            max_chars=len(first_span.text) - 1,
        )
        == []
    )
    assert (
        len(
            build_evidence(
                catalog=env.catalog,
                scope=scope,
                candidates=candidates,
                max_items=1,
            )
        )
        == 1
    )
    assert second_span.text


def test_evidence_rejects_tampered_source_and_reports_superseded_revision(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="将被替换的册", text=SINGLE_BODY_TEXT)
    scope = verify_scope(env.catalog, env.snapshot(document))
    candidate = candidate_for(
        document.body_chunks()[0],
        chunk_set_id=document.chunk_set_id,
        revision_id=document.revision_id,
    )
    item = build_evidence(catalog=env.catalog, scope=scope, candidates=[candidate])[0]
    assert item.isSuperseded is False

    class TamperedSource:
        """替身：返回与修订登记不符的文本，验证散列闸门。"""

        def __init__(self, text: str) -> None:
            self.text = text

        def read_normalized_text(self, revision):
            return self.text

    with pytest.raises(AppError) as tampered:
        build_evidence(
            catalog=env.catalog,
            scope=scope,
            candidates=[candidate],
            texts=TamperedSource("被替换过的原文"),
        )
    assert tampered.value.code == "RAG_EVIDENCE_UNAVAILABLE"
    assert tampered.value.status_code == 409

    # 同区间同 id：重复重建得到同一引用标识与同一逐字节文本
    again = build_evidence(catalog=env.catalog, scope=scope, candidates=[candidate])[0]
    assert again.evidenceId == item.evidenceId
    assert again.text == item.text


def test_evidence_marks_superseded_revision_when_scope_is_stale(tmp_path):
    """旧快照（历史消息）重建证据时如实标记 isSuperseded，且不偷偷换成新修订。"""
    env = RagEnv(tmp_path)
    document = env.add_document(title="将被替换的册", text=SINGLE_BODY_TEXT)
    scope = verify_scope(env.catalog, env.snapshot(document))
    candidate = candidate_for(
        document.body_chunks()[0],
        chunk_set_id=document.chunk_set_id,
        revision_id=document.revision_id,
    )
    live = build_evidence(catalog=env.catalog, scope=scope, candidates=[candidate])[0]
    assert live.isSuperseded is False

    new_revision = publish_new_revision(env, document, SINGLE_BODY_TEXT + "\n补充修订说明。\n")
    stale = build_evidence(catalog=env.catalog, scope=scope, candidates=[candidate])[0]
    assert stale.isSuperseded is True, "修订不再是当前修订时必须标记为已替换"
    assert stale.documentRevisionId == document.revision_id
    assert stale.text == live.text, "不得偷偷替换成新修订的原文"
    assert new_revision.revision_id != document.revision_id


def publish_new_revision(env: RagEnv, document, text: str):
    """为既有书册追加并发布一个新修订（含真实 blob 封存）。"""
    from app.services.document_parsing import (
        PARSER_VERSION,
        parse_document,
        source_map_payload,
    )
    from app.services.textbook_ingest.blobs import sha256_text

    path = env.tmp_path / "replacement.md"
    path.write_text(text, encoding="utf-8")
    parsed = parse_document(path=path, file_name="replacement.md")
    normalized_blob_id = env.blobs.write_staged_bytes(parsed.normalized_text.encode("utf-8"))
    env.blobs.seal(area="normalized", blob_id=normalized_blob_id)
    source_map_blob_id = env.blobs.write_staged_bytes(
        canonical_json(source_map_payload(parsed)).encode("utf-8")
    )
    env.blobs.seal(area="normalized", blob_id=source_map_blob_id)
    original_blob_id = env.blobs.write_staged_bytes(path.read_bytes())
    env.blobs.seal(area="blobs", blob_id=original_blob_id)
    revision = env.catalog.create_document_revision(
        document.document_id,
        original_file_sha256=original_blob_id,
        normalized_text_sha256=sha256_text(parsed.normalized_text),
        parser_version=PARSER_VERSION,
        original_blob_id=original_blob_id,
        normalized_blob_id=normalized_blob_id,
        source_map_blob_id=source_map_blob_id,
        char_count=len(parsed.normalized_text),
    )
    env.catalog.publish_document_revision(
        document.document_id,
        revision_id=revision.revision_id,
        metadata_revision_id=document.metadata_revision_id,
    )
    return revision


def test_candidate_outside_scope_is_rejected_not_silently_dropped(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="在范围内的册", text=SINGLE_BODY_TEXT)
    outside = env.add_document(title="不在范围内的册", text=SINGLE_BODY_TEXT)
    scope = verify_scope(env.catalog, env.snapshot(document))
    stray = candidate_for(
        outside.body_chunks()[0],
        chunk_set_id=outside.chunk_set_id,
        revision_id=outside.revision_id,
    )
    with pytest.raises(AppError) as rejected:
        build_evidence(catalog=env.catalog, scope=scope, candidates=[stray])
    assert rejected.value.code == "RAG_EVIDENCE_UNAVAILABLE"
