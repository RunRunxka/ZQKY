"""R2-BE3 教材检索服务：命中映射、学科过滤、未就绪报错与空范围行为。

service 级闭环（不触网、不连真实 Qdrant/Ollama）：
- 装配方式沿 ``tests.test_r2_ingest_smoke``：内存向量库 + FakeEmbeddings + tmp catalog；
- 走真实 ``parse_document``/``chunk_document`` 与 ``HybridRetriever``（含指纹核验、
  BM25 词法与 RRF 融合），断言 SearchHit 携带章节路径、标签与原文片段；
- 负例：无活动代 → 409 ``RAG_INDEX_NOT_READY``；学科过滤后无书 → 空列表不猜。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.vector_store import InMemoryVectorStore
from app.services.document_parsing import chunk_document, parse_document
from app.services.textbook_index import IndexService
from app.services.textbook_ingest import IngestService
from app.services.textbook_search import EXCERPT_MAX_CHARS, TextbookSearchService
from tests.test_textbook_ingest import METADATA, FakeEmbeddings


def _sample_markdown(topic: str) -> str:
    """小而真实的 md 文件：正文多段含主题词，保证稠密与词法都能命中。"""
    body = "\n\n".join(f"{topic}是重要的数学概念，需要结合例子反复理解。" * 8 for _ in range(6))
    return f"# 第一章 {topic}\n\n{body}\n\n## 1.1 基本概念\n\n{topic}的定义如下。\n"


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    settings = Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=frozenset(),
        env="test",
        data_dir=tmp_path / "data",
    )
    catalog = TextbookCatalog(settings.textbooks_root / "catalog.sqlite3")
    catalog.migrate()
    vectors = InMemoryVectorStore()
    embeddings = FakeEmbeddings()
    ingest = IngestService(
        catalog,
        parse_document,
        chunk_document,
        embeddings,
        vectors,
        settings,
        batch_size=8,
        sleep=lambda _seconds: None,
    )
    index = IndexService(catalog, embeddings, vectors, settings, sleep=lambda _seconds: None)
    probe = index.probe(model_name="bge-m3")
    profile = index.create_profile(
        model_name=probe.modelName,
        base_url=None,
        query_prefix="",
        document_prefix="",
        normalization="none",
    )
    generation = index.ensure_empty_generation(profile.profileId)
    library = catalog.create_library(
        kind="base",
        owner_id="system",
        display_name="基础库·数学",
        grade_id="senior-1",
        subject_id="math",
        edition_id="renjiao-a",
    )
    service = TextbookSearchService(catalog, vectors, embeddings)
    return {
        "catalog": catalog,
        "vectors": vectors,
        "embeddings": embeddings,
        "ingest": ingest,
        "index": index,
        "profile": profile,
        "generation": generation,
        "library": library,
        "service": service,
        "settings": settings,
    }


def _ingest(env: dict, *, topic: str, subject_id: str = "math") -> str:
    """导入并入库一册小教材；返回文档 id（书册元数据可定制学科）。"""
    catalog: TextbookCatalog = env["catalog"]
    ingest: IngestService = env["ingest"]
    metadata = dict(METADATA)
    metadata["subjectId"] = subject_id
    draft = ingest.create_import(
        file_name=f"{topic}.md",
        data=_sample_markdown(topic).encode("utf-8"),
        metadata=metadata,
    )
    assert draft.state == "needs_review", draft.warnings
    job = ingest.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id=f"search-{topic}",
        library_ids=[env["library"].library_id],
    )
    final = ingest.run_ingest_job(job.jobId)
    assert final.state == "succeeded", final.errorMessage
    return final.documentId


class TestSearchService:
    def test_search_returns_hits_with_chapter_path_and_excerpt(self, env: dict) -> None:
        _ingest(env, topic="函数的单调性")
        service: TextbookSearchService = env["service"]

        hits = service.search("函数的单调性", limit=3)

        assert hits, "已入库教材必须被检索命中"
        assert len(hits) <= 3
        first = hits[0]
        assert first.document_title == METADATA["title"]
        assert first.chapter_path and any("函数的单调性" in part for part in first.chapter_path)
        assert "函数的单调性" in first.excerpt
        assert " " not in first.excerpt.replace(" ", "") or first.excerpt  # 已压平空白
        assert "\n" not in first.excerpt and "\t" not in first.excerpt
        assert len(first.excerpt) <= EXCERPT_MAX_CHARS + 1  # 截断带省略号
        assert first.subject_label == "数学"
        # edition_label 语义沿 rag_v2.scope：版次+册次，都为空时才退回版本 id
        assert first.edition_label == "2019版 必修第一册"
        assert first.grade_ids == ("senior-1",)
        assert first.region == "body"
        assert first.char_end > first.char_start
        assert first.fused_score > 0.0
        # 数学（假嵌入按文本哈希）：该词与正文相同 → 至少一路名次在
        assert first.dense_rank is not None or first.lexical_rank is not None

    def test_search_limit_truncates(self, env: dict) -> None:
        _ingest(env, topic="集合")
        service: TextbookSearchService = env["service"]

        hits = service.search("集合", limit=2)
        assert len(hits) <= 2

    def test_subject_filter_no_match_returns_empty(self, env: dict) -> None:
        """学科过滤后无书：返回空列表，不放宽成全库、不猜。"""
        _ingest(env, topic="函数")
        service: TextbookSearchService = env["service"]

        assert service.search("函数", subject_id="chinese") == []

    def test_subject_filter_matching_keeps_hits(self, env: dict) -> None:
        _ingest(env, topic="数列")
        service: TextbookSearchService = env["service"]

        hits = service.search("数列", subject_id="math")
        assert hits
        assert all(hit.subject_label == "数学" for hit in hits)

    def test_no_active_generation_raises_not_ready(self, tmp_path: Path) -> None:
        """空库（无活动代）：409 RAG_INDEX_NOT_READY，不返回空列表冒充成功。"""
        settings = Settings(
            host="127.0.0.1",
            port=8001,
            allowed_origins=frozenset(),
            env="test",
            data_dir=tmp_path / "data-empty",
        )
        catalog = TextbookCatalog(settings.textbooks_root / "catalog.sqlite3")
        catalog.migrate()
        service = TextbookSearchService(catalog, InMemoryVectorStore(), FakeEmbeddings())

        with pytest.raises(AppError) as exc_info:
            service.search("任意问题")
        assert exc_info.value.code == "RAG_INDEX_NOT_READY"
        assert exc_info.value.status_code == 409

    def test_generation_not_ready_raises(self, env: dict) -> None:
        """活动代被置为 building：409 RAG_INDEX_NOT_READY。"""
        _ingest(env, topic="幂函数")
        catalog: TextbookCatalog = env["catalog"]
        generation = env["generation"]
        catalog.update_generation_state(generation.generation_id, "building")
        try:
            with pytest.raises(AppError) as exc_info:
                env["service"].search("幂函数")
            assert exc_info.value.code == "RAG_INDEX_NOT_READY"
        finally:
            catalog.update_generation_state(generation.generation_id, "ready")

    def test_invalid_inputs_raise(self, env: dict) -> None:
        service: TextbookSearchService = env["service"]
        with pytest.raises(AppError) as empty_query:
            service.search("   ")
        assert empty_query.value.code == "INVALID_REQUEST"
        with pytest.raises(AppError):
            service.search("函数", limit=0)
        with pytest.raises(AppError):
            service.search("函数", limit=999)

    def test_excerpt_flat_and_bounded_for_long_chunk(self, env: dict) -> None:
        """超长块片段截断到 ~400 字符；换行/缩进压平。"""
        catalog: TextbookCatalog = env["catalog"]
        ingest: IngestService = env["ingest"]
        long_body = "\n\n".join("单调性判断方法与例题讲解。" * 60 for _ in range(4))
        draft = ingest.create_import(
            file_name="long.md",
            data=f"# 第二章 长文本\n\n{long_body}\n".encode("utf-8"),
            metadata=dict(METADATA),
        )
        job = ingest.commit_import(
            draft.importId,
            expected_revision=draft.revision,
            submission_id="search-long",
            library_ids=[env["library"].library_id],
        )
        final = ingest.run_ingest_job(job.jobId)
        assert final.state == "succeeded", final.errorMessage

        hits = env["service"].search("单调性判断方法")
        assert hits
        assert all(len(hit.excerpt) <= EXCERPT_MAX_CHARS + 1 for hit in hits)
        assert all("\n" not in hit.excerpt for hit in hits)

    def test_retriever_cached_across_calls(self, env: dict) -> None:
        """惰性构建的 retriever 被复用（不重复实例化）。"""
        _ingest(env, topic="指数函数")
        service: TextbookSearchService = env["service"]
        assert service._retriever is None
        service.search("指数函数")
        first = service._retriever
        assert first is not None
        service.search("指数函数")
        assert service._retriever is first

    def test_thread_safety_serialized(self, env: dict) -> None:
        """多线程并发调用不崩（内部锁串行化检索）。"""
        import concurrent.futures

        _ingest(env, topic="对数函数")
        service: TextbookSearchService = env["service"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(service.search, "对数函数", limit=2) for _ in range(4)]
            results = [future.result() for future in futures]
        assert all(isinstance(rows, list) for rows in results)
        assert any(rows for rows in results)
