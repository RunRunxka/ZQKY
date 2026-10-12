"""R2-BE2 教材导入管线冒烟：导入 → 解析 → 清洗 → 切块 → 嵌入 → 入库 → 检索可用。

service 级闭环（不触网、不连真实 Qdrant/Ollama）：
- 替身沿归档测试既有模式（``tests.test_textbook_ingest.FakeEmbeddings`` +
  ``InMemoryVectorStore``），SQLite 与 blob 文件都在 pytest ``tmp_path``；
- 走真实 ``parse_document``/``chunk_document``（document_parsing 清洗链路）；
- 断言：草稿 needs_review → commit 产生 queued ingest 任务 → 任务 succeeded →
  修订在当前索引代内 ready、向量点数与块数一致 → ``RevisionScope`` + 内存向量库
  可按登记 payload 检索回该修订（检索可用）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.vector_store import InMemoryVectorStore
from app.services.document_parsing import chunk_document, parse_document
from app.services.textbook_index import IndexService
from app.services.textbook_ingest import IngestService
from tests.test_textbook_ingest import METADATA, FakeEmbeddings, sample_text


def _sample_markdown() -> str:
    """小而真实的 md 文件：标题 + 多段正文 + 小节标题（走完整清洗/分块规则）。"""
    body = "\n\n".join("集合与函数是高中数学的基础内容，需要反复理解与应用。" * 8 for _ in range(6))
    return f"# 第一章 集合与函数\n\n{body}\n\n## 1.1 集合的概念\n\n集合元素具有确定性。\n"


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
    # 空库首启顺序与归档迁移脚本一致：probe → create_profile → ensure_empty_generation
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
    return {
        "catalog": catalog,
        "vectors": vectors,
        "embeddings": embeddings,
        "ingest": ingest,
        "index": index,
        "profile": profile,
        "generation": generation,
        "library": library,
    }


def test_r2_ingest_pipeline_smoke(env: dict) -> None:
    catalog: TextbookCatalog = env["catalog"]
    ingest: IngestService = env["ingest"]
    vectors: InMemoryVectorStore = env["vectors"]
    generation = env["generation"]
    library = env["library"]

    # 1) 导入：小 md 文件 → 草稿（真实解析+清洗，元数据确认后 needs_review）
    draft = ingest.create_import(
        file_name="chapter.md",
        data=_sample_markdown().encode("utf-8"),
        metadata=dict(METADATA),
    )
    assert draft.state == "needs_review", draft.warnings
    assert draft.parsed is not None and draft.parsed.charCount > 0
    assert draft.canCommit is True

    # 2) 提交：封存不可变修订 + 创建 queued 入库任务（幂等键 submissionId）
    job = ingest.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="smoke-submission-1",
        library_ids=[library.library_id],
    )
    assert job.state == "queued"
    assert job.kind == "ingest"

    # 3) 入库执行：分块 → 嵌入（FakeEmbeddings）→ 写内存向量库 → 原子发布
    final = ingest.run_ingest_job(job.jobId)
    assert final.state == "succeeded", final.errorMessage
    assert final.documentId and final.inputRevisionId

    # 4) 权威状态：修订在当前索引代内 ready；向量点数与分块数一致
    revision = catalog.get_revision(final.inputRevisionId)
    assert revision is not None
    in_generation = catalog.list_generation_revisions(generation.generation_id)
    assert any(
        item.document_revision_id == revision.revision_id and item.state == "ready"
        for item in in_generation
    )
    document = catalog.get_document(final.documentId)
    assert document is not None
    assert document.current_revision_id == revision.revision_id
    chunk_set = catalog.find_chunk_set(revision.revision_id, _generation_fingerprint(catalog, generation))
    assert chunk_set is not None, "入库后必须登记分块集"
    chunks = catalog.list_chunks(chunk_set.chunk_set_id)
    assert chunks, "入库后必须存在分块"
    allowed = _allowed_for(revision.revision_id, chunk_set.chunk_set_id)
    point_count = vectors.count(name=generation.collection_name, allowed=allowed)
    assert point_count == len(chunks)

    # 5) 检索可用：RevisionScope 允许集 + 假嵌入向量能召回本修订的点
    from app.repositories.vector_store.base import PAYLOAD_DOCUMENT_ID, PAYLOAD_REVISION_ID
    from app.services.rag_v2.scope import RevisionScope, allowed_filter

    scope = RevisionScope(
        document_id=document.document_id,
        document_revision_id=revision.revision_id,
        metadata_revision_id=document.current_metadata_revision_id,
        chunk_set_id=chunk_set.chunk_set_id,
        owner_id=document.owner_id,
        title=document.title,
        edition_label="人教A版",
        subject_label="数学",
        grade_ids=("senior-1",),
        library_ids=tuple(document.library_ids),
    )
    query_vector = env["embeddings"].embed(model=env["profile"].modelName, texts=["集合与函数"])[0]
    hits = vectors.search(
        name=generation.collection_name,
        vector=query_vector,
        limit=5,
        allowed=allowed_filter([scope]),
    )
    assert hits, "检索必须命中已入库块"
    assert all(
        hit.payload.get(PAYLOAD_REVISION_ID) == revision.revision_id
        and hit.payload.get(PAYLOAD_DOCUMENT_ID) == document.document_id
        for hit in hits
    ), "命中点必须属于刚入库的修订"


def _generation_fingerprint(catalog: TextbookCatalog, generation) -> str:
    """当前代登记策略的指纹：与入库路径同一个 ``generation_policy`` 派生，不另起口径。"""
    from app.services.document_parsing.chunking import chunk_policy_fingerprint
    from app.services.textbook_ingest import generation_policy

    fresh = catalog.get_generation(generation.generation_id)
    assert fresh is not None
    return chunk_policy_fingerprint(generation_policy(fresh))


def _allowed_for(revision_id: str, chunk_set_id: str):
    from app.repositories.vector_store.base import AllowedFilter

    return AllowedFilter(revision_ids=(revision_id,), chunk_set_ids=(chunk_set_id,))
