"""原文证据重建：不可变切片、邻块扩展边界、预算取舍与来源定位一致性。"""

from __future__ import annotations

import pytest

from app.core.exceptions import AppError
from app.providers.embeddings.fingerprint import canonical_json
from app.services.document_parsing import parsed_from_source_map, split_regions
from app.services.rag_v2.evidence import build_evidence, evidence_id, sha256_utf8
from app.services.rag_v2.retrieval import Candidate
from app.services.rag_v2.scope import verify_scope
from app.services.textbook_ingest.source_access import read_source_span
from tests.test_rag_v2_support import RagEnv, multi_chapter_text

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
    assert len(evidence) == 1, "同一章节的连续正文块应合并成一个完整 span"
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

    # 合并从正文区起点开始，并覆盖到正文区末尾附近；边界允许极小的换行/尾块缝
    # （分块器在正文/习题边界处的切点由 B1 决定，这里只断言"覆盖正文、不含习题"）
    covered = min(chunk.char_start for chunk in body_chunks)
    item = evidence[0]
    assert (item.charStart, item.charStart) == (covered, body_span.char_start)
    assert item.charStart < item.charEnd, "半开区间 [start, end)"
    assert item.charEnd <= exercise_start
    assert item.charEnd >= exercise_start - 8, "正文区应被覆盖到边界附近"
    assert item.text == normalized[item.charStart : item.charEnd]
    assert item.evidenceId == evidence_id(document.revision_id, item.charStart, item.charEnd)
    assert item.normalizedTextSha256 == revision.normalized_text_sha256
    assert item.documentId == document.document_id
    assert item.isSuperseded is False
    assert item.chapterPath == ["第一章 集合"]
    assert "$$A\\cup B$$" in item.text and "🙂" in item.text
    assert item.originalFileSha256 == revision.original_file_sha256
    assert item.locator.kind == "markdown"
    assert item.locator.lineStart is not None and item.locator.lineStart >= 1

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

    # 证据必须整段落在正文区：习题区文本永不作为知识点依据
    assert item.charEnd <= exercise_start
    assert body_span.char_start <= item.charStart and body_span.char_end >= item.charEnd
    assert item.charEnd >= body_span.char_end - 2, "正文区应被完整覆盖（只允许边界换行缝）"
    assert "练习" not in item.text


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
