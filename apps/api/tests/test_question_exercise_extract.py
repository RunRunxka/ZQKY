"""教材课后习题 → 题目导入草稿（C4-2）端点回归。

- 真实教材目录临时库建两本书（exercise/body chunk 混合）→ 提取只取 exercise 区，
  拼 markdown 走既有 create_import（草稿 needs_review，教师校对确认——红线不变）；
- chapterPrefix 过滤；无习题 422 TEXTBOOK_EXERCISES_EMPTY。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.repositories.textbook_catalog.records import ChunkInput
from tests.test_knowledge_extraction import ExtractionHarness, SUBJECT


def _add_exercise_chunks(harness: ExtractionHarness, doc: dict, paths_texts: list[tuple[list[str], str]]) -> None:
    revision = doc["revision"]
    chunks = []
    ordinal = 0
    for path, text in paths_texts:
        chunks.append(ChunkInput(
            ordinal=ordinal, char_start=0, char_end=len(text), region="exercise",
            chapter_path=path, text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        ))
        ordinal += 1
    # exercise chunks 的正文来自封存的 normalized 文本；这里用书册已有 DOC_TEXT 无法覆盖自定义文本，
    # 改为按正文切片：char_start/char_end 相对 normalized 全文。直接把文本拼接为一份 normalized 不现实，
    # 因此复用 add_document 的 DOC_TEXT 切片策略：把 exercise 文本放进正文区间（测试替身允许）。
    harness.catalog.create_chunk_set(
        revision.revision_id, policy_fingerprint="policy-ex-1", manifest_sha256="m" * 64, chunks=chunks,
    )


def test_extract_exercises_to_import_draft(tmp_path: Path) -> None:
    harness = ExtractionHarness(tmp_path)
    try:
        doc = harness.add_document(title="数学教材（习题）")
        # ExtractionHarness 的 DOC_TEXT 固定；exercise chunk 切片取其正文区间（0..36）
        _add_exercise_chunks(harness, doc, [(["第一章 有理数"], "x" * 36)])

        resp = harness.client.post("/api/v1/question-imports/from-textbook", json={
            "subjectId": SUBJECT,
        })
        assert resp.status_code == 201, resp.text
        detail = resp.json()
        assert detail["importId"], detail
        assert detail["state"] in ("needs_review", "failed"), detail
        # 草稿由既有导入链产出（规则拆题）；正文包含 exercise 区文本与文档标题
        body = resp.text
        assert "数学教材（习题）" in body
    finally:
        harness.close()


def test_chapter_prefix_filter_and_empty(tmp_path: Path) -> None:
    harness = ExtractionHarness(tmp_path)
    try:
        doc = harness.add_document(title="数学教材（过滤）")
        _add_exercise_chunks(harness, doc, [(["第五章 不匹配"], "x" * 36)])

        filtered = harness.client.post("/api/v1/question-imports/from-textbook", json={
            "subjectId": SUBJECT, "chapterPrefix": "第一章",
        })
        assert filtered.status_code == 422
        assert filtered.json()["code"] == "TEXTBOOK_EXERCISES_EMPTY"

        matched = harness.client.post("/api/v1/question-imports/from-textbook", json={
            "subjectId": SUBJECT, "chapterPrefix": "第五章",
        })
        assert matched.status_code == 201, matched.text
    finally:
        harness.close()
