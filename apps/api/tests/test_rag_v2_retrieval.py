"""混合检索：范围下推、RRF 融合与并列确定性、BM25 只用允许块与有界缓存。"""

from __future__ import annotations

import pytest

from app.core.exceptions import AppError
from app.services.rag_v2 import retrieval as retrieval_module
from app.services.rag_v2.retrieval import RRF_K, HybridRetriever
from app.services.rag_v2.scope import allowed_filter, resolve_scope, verify_scope
from tests.test_rag_v2_support import (
    FakeEmbeddings,
    RagEnv,
    ScriptedVectorStore,
    textbook_text,
)

#: 一个正文块 + 一个习题块（习题区不进入检索），便于精确控制名次与并列
SINGLE_BODY_TEXT = (
    "# 集合\n\n" + "集合的表示方法。" * 120 + "\n\n## 练习 1.1\n\n1. 求并集。\n"
)


class CatalogSpy:
    """只读代理：记录 list_chunks 被读了哪些分块集，用于证明"不读全库"。"""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.chunk_sets_read: list[str] = []

    def __getattr__(self, name):
        attribute = getattr(self.inner, name)
        if name != "list_chunks":
            return attribute

        def wrapper(chunk_set_id: str, *args, **kwargs):
            self.chunk_sets_read.append(chunk_set_id)
            return attribute(chunk_set_id, *args, **kwargs)

        return wrapper


class WrongDimensionEmbeddings(FakeEmbeddings):
    """只让查询向量维度错误（教材向量仍正确），验证维度闸门。"""

    def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        return [[0.5, 0.5] for _ in texts]


def test_dense_search_pushes_scope_filter_and_bm25_reads_only_allowed_chunk_sets(tmp_path):
    env = RagEnv(tmp_path)
    inside = env.add_document(title="范围内的册", text=textbook_text("集合"))
    library = env.new_library(grade_id="senior-2", subject_id="math", display_name="高二数学")
    outside = env.add_document(
        title="范围外的册",
        text=textbook_text("向量"),
        grade_ids=("senior-2",),
        library_ids=[library],
    )
    snapshot = resolve_scope(env.catalog, env.selection(inside))
    scope = verify_scope(env.catalog, snapshot)
    spy = CatalogSpy(env.catalog)
    retriever = HybridRetriever(spy, env.vectors, env.embeddings)

    candidates = retriever.retrieve(
        question="集合的表示方法",
        scope=scope,
        profile=env.profile,
        generation=env.generation,
    )
    assert candidates
    assert all(item.document_revision_id == inside.revision_id for item in candidates)
    assert all(item.chunk_set_id == inside.chunk_set_id for item in candidates)

    pushed = env.vectors.calls[-1]["allowed"]
    assert pushed == allowed_filter(scope)
    assert pushed.revision_ids == (inside.revision_id,)
    assert pushed.chunk_set_ids == (inside.chunk_set_id,)
    assert pushed.region == "body"
    assert env.vectors.calls[-1]["limit"] == retriever.dense_limit

    # BM25 只读允许范围内的分块集：范围外的册一次都没被读
    assert set(spy.chunk_sets_read) == {inside.chunk_set_id}
    assert outside.chunk_set_id not in spy.chunk_sets_read


def test_empty_scope_never_touches_vector_store_or_catalog(tmp_path):
    env = RagEnv(tmp_path)
    env.add_document(title="不参与本轮检索的册", text=textbook_text("集合"))
    spy = CatalogSpy(env.catalog)
    retriever = HybridRetriever(spy, env.vectors, env.embeddings)
    assert (
        retriever.retrieve(
            question="任意问题",
            scope=(),
            profile=env.profile,
            generation=env.generation,
        )
        == []
    )
    assert env.vectors.calls == [] and spy.chunk_sets_read == []


def test_rrf_formula_merges_both_paths_and_ties_follow_stable_identity(tmp_path):
    store = ScriptedVectorStore([])
    env = RagEnv(tmp_path, vectors=store)
    doc_a = env.add_document(title="数学 A 册", text=SINGLE_BODY_TEXT)
    doc_b = env.add_document(title="数学 B 册", text=SINGLE_BODY_TEXT)
    scope = verify_scope(env.catalog, env.snapshot(doc_a, doc_b))

    def retrieve():
        return env.retriever.retrieve(
            question="集合的表示方法",
            scope=scope,
            profile=env.profile,
            generation=env.generation,
        )

    def dense_order(first: tuple[str, int], second: tuple[str, int]) -> None:
        store.hits = [
            (first[0], first[1], "", "p-first"),
            (second[0], second[1], "", "p-second"),
        ]

    # 先只看词法（脚本化稠密为空）：取词法第 1、2 名作为并列实验的一对
    first_pass = retrieve()
    lexical_ranked = [item for item in first_pass if item.lexical_rank]
    assert len(lexical_ranked) >= 2
    first, second = lexical_ranked[0], lexical_ranked[1]
    assert {first.lexical_rank, second.lexical_rank} == {1, 2}
    # 两册文本逐字相同 → BM25 分数并列，词法名次由稳定块身份决定
    assert first.document_revision_id in {doc_a.revision_id, doc_b.revision_id}

    # 让稠密名次与词法名次相反 → 融合分并列，必须按 (chunk_set_id, ordinal) 稳定排序
    dense_order(second.identity, first.identity)
    tied = retrieve()
    by_identity = {item.identity: item for item in tied}
    tied_first, tied_second = by_identity[first.identity], by_identity[second.identity]
    assert tied_first.dense_rank == 2 and tied_first.lexical_rank == 1
    assert tied_second.dense_rank == 1 and tied_second.lexical_rank == 2
    for candidate in tied:
        assert candidate.fused_score == pytest.approx(
            1.0 / (RRF_K + candidate.dense_rank) + 1.0 / (RRF_K + candidate.lexical_rank)
        )
    assert tied_first.fused_score == pytest.approx(tied_second.fused_score)
    assert [item.identity for item in tied[:2]] == sorted(
        [tied_first.identity, tied_second.identity], key=lambda identity: (identity[0], identity[1])
    )
    assert tied == sorted(
        tied, key=lambda item: (-item.fused_score, item.chunk_set_id, item.ordinal)
    )
    assert [item.dense_rank == item.lexical_rank for item in tied[:2]] == [False, False]
    # 同输入重复检索 → 逐项一致（确定性）
    assert [(item.identity, item.fused_score) for item in tied] == [
        (item.identity, item.fused_score) for item in retrieve()
    ]
    # 稠密与词法命中不同项时，两路都要出现在融合结果里
    assert {item.dense_rank is not None for item in tied} == {True}
    assert any(item.lexical_rank is not None for item in tied)


def test_lexical_cache_is_bounded_and_keyed_by_generation_revisions_and_tokenizer(tmp_path):
    env = RagEnv(tmp_path)
    docs = [
        env.add_document(title=f"册{index}", text=textbook_text(topic))
        for index, topic in enumerate(("集合", "函数", "向量"))
    ]
    scopes = [verify_scope(env.catalog, env.snapshot(doc)) for doc in docs]
    retriever = HybridRetriever(env.catalog, env.vectors, env.embeddings, cache_entries=2)

    def search(scope):
        return retriever.retrieve(
            question="集合", scope=scope, profile=env.profile, generation=env.generation
        )

    search(scopes[0])
    assert (retriever.cache_misses, retriever.cache_hits) == (1, 0)
    search(scopes[0])
    assert (retriever.cache_misses, retriever.cache_hits) == (1, 1)
    # 不同修订集合 → 不同缓存键（不串 scope）
    search(scopes[1])
    assert retriever.cache_misses == 2
    search(scopes[2])
    assert retriever.cache_misses == 3
    # 容量 2：最早的键被淘汰，再问它必须重建
    search(scopes[0])
    assert retriever.cache_misses == 4
    retriever.clear_cache()
    search(scopes[0])
    assert retriever.cache_misses == 5

    # 分词版本进入缓存键：改版本必须重建，不得复用旧词法索引
    misses_before = retriever.cache_misses
    original = retrieval_module.TOKENIZER_VERSION
    try:
        retrieval_module.TOKENIZER_VERSION = "tokenizer-test-v2"
        search(scopes[0])
        assert retriever.cache_misses == misses_before + 1
    finally:
        retrieval_module.TOKENIZER_VERSION = original


def test_dense_scores_must_be_positive_and_stale_points_are_counted(tmp_path):
    store = ScriptedVectorStore([])
    env = RagEnv(tmp_path, vectors=store)
    doc = env.add_document(title="册", text=SINGLE_BODY_TEXT)
    scope = verify_scope(env.catalog, env.snapshot(doc))
    chunk = doc.body_chunks()[0]
    store.hits = [
        (doc.chunk_set_id, chunk.ordinal, doc.revision_id, "p-ok"),
        (doc.chunk_set_id, 9999, doc.revision_id, "p-stale"),  # 白名单内但块表没有：陈旧 point
    ]
    candidates = env.retriever.retrieve(
        question="集合的表示方法",
        scope=scope,
        profile=env.profile,
        generation=env.generation,
    )
    assert [item.ordinal for item in candidates if item.dense_rank is not None] == [chunk.ordinal]
    assert env.retriever.inconsistent_hits == 1

    store.score = -0.5  # 全负相似度：不构成命中，不伪造名次
    assert all(
        item.dense_rank is None
        for item in env.retriever.retrieve(
            question="集合的表示方法",
            scope=scope,
            profile=env.profile,
            generation=env.generation,
        )
    )


def test_query_embedding_uses_profile_prefix_and_rejects_wrong_dimensions(tmp_path):
    env = RagEnv(tmp_path, query_prefix="query: ")
    doc = env.add_document(title="册", text=SINGLE_BODY_TEXT)
    scope = verify_scope(env.catalog, env.snapshot(doc))
    env.retriever.retrieve(
        question="集合的表示方法",
        scope=scope,
        profile=env.profile,
        generation=env.generation,
    )
    model, texts = env.embeddings.calls[-1]
    assert model == env.profile.model_name
    assert texts == ["query: 集合的表示方法"]

    bad_env = RagEnv(tmp_path / "bad", embeddings=WrongDimensionEmbeddings())
    bad_doc = bad_env.add_document(title="册", text=SINGLE_BODY_TEXT)
    bad_scope = verify_scope(bad_env.catalog, bad_env.snapshot(bad_doc))
    with pytest.raises(AppError) as mismatch:
        bad_env.retriever.retrieve(
            question="集合",
            scope=bad_scope,
            profile=bad_env.profile,
            generation=bad_env.generation,
        )
    assert mismatch.value.code == "EMBEDDING_DIMENSION_MISMATCH"
