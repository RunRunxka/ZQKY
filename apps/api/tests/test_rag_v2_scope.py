"""范围解析与使用前核验：快照稳定性、范围不串库、三类漂移必须 409。"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest

from app.core.exceptions import AppError
from app.repositories.vector_store.base import AllowedFilter
from app.schemas.rag_v2 import ScopeDocument
from app.services.rag_v2.scope import allowed_filter, canonical_json, resolve_scope, verify_scope
from app.services.textbook_ingest.generation_doc import generation_policy_document
from tests.test_rag_v2_support import RagEnv, sample_text


def test_snapshot_fields_and_scope_hash_stability_and_sensitivity(tmp_path):
    env = RagEnv(tmp_path)
    doc = env.add_document(title="高中数学必修第一册", text=sample_text())
    selection = env.selection(doc)

    first = resolve_scope(env.catalog, selection)
    second = resolve_scope(env.catalog, selection)
    assert first.model_dump() == second.model_dump()
    assert first.scopeHash == second.scopeHash
    assert len(first.scopeHash) == 64
    assert first.schemaVersion == 2
    assert first.embeddingGenerationId == env.generation.generation_id
    assert [item.documentId for item in first.documents] == [doc.document_id]
    assert first.documents[0].documentRevisionId == doc.revision_id
    assert first.documents[0].metadataRevisionId == doc.metadata_revision_id

    # 独立复算：canonical json 的字段集合与排序逐字节固定（契约冻结，不靠实现自证）
    payload = {
        "schemaVersion": 2,
        "selection": selection.model_dump(),
        "documents": [
            {
                "documentId": doc.document_id,
                "documentRevisionId": doc.revision_id,
                "metadataRevisionId": doc.metadata_revision_id,
            }
        ],
        "embeddingGenerationId": env.generation.generation_id,
    }
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert first.scopeHash == expected
    assert canonical_json(payload) == json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )

    # 改一个 documentId（加入第二册）→ 散列必须变化
    other = env.add_document(title="高中数学必修第二册", text=sample_text(title="函数"))
    changed = resolve_scope(env.catalog, env.selection(doc, other))
    assert changed.scopeHash != first.scopeHash
    assert len(changed.documents) == 2
    # selection（含 documentIds 顺序）是散列的一部分；documents 条目按 documentId 排序
    reordered_selection = resolve_scope(env.catalog, env.selection(other, doc))
    assert reordered_selection.scopeHash != changed.scopeHash
    assert [item.documentId for item in reordered_selection.documents] == sorted(
        [doc.document_id, other.document_id]
    )
    # 只翻转快照里的 documents 数组顺序（selection 不变）不影响核验：按 documentId 排序比较
    reversed_documents = changed.model_copy(update={"documents": list(reversed(changed.documents))})
    baseline = {(item.document_id, item.document_revision_id) for item in verify_scope(env.catalog, changed)}
    flipped = {
        (item.document_id, item.document_revision_id)
        for item in verify_scope(env.catalog, reversed_documents)
    }
    assert flipped == baseline


def test_verify_scope_rejects_tampered_snapshot(tmp_path):
    env = RagEnv(tmp_path)
    doc = env.add_document(title="高中数学必修第一册", text=sample_text())
    snapshot = env.snapshot(doc)
    assert [item.document_revision_id for item in verify_scope(env.catalog, snapshot)] == [doc.revision_id]

    forged_hash = snapshot.model_copy(update={"scopeHash": "0" * 64})
    with pytest.raises(AppError) as bad_hash:
        verify_scope(env.catalog, forged_hash)
    assert bad_hash.value.code == "RAG_SCOPE_CHANGED" and bad_hash.value.status_code == 409

    forged_documents = snapshot.model_copy(
        update={
            "documents": [
                ScopeDocument(
                    documentId=doc.document_id,
                    documentRevisionId=uuid.uuid4().hex,
                    metadataRevisionId=doc.metadata_revision_id,
                )
            ]
        }
    )
    with pytest.raises(AppError) as bad_documents:
        verify_scope(env.catalog, forged_documents)
    assert bad_documents.value.code == "RAG_SCOPE_CHANGED"


def test_allowed_filter_and_retrieval_stay_inside_one_edition(tmp_path):
    """数学 A/B 同名册：只检索命中的那一册，filter 里不出现另一册。"""
    env = RagEnv(tmp_path)
    doc_a = env.add_document(title="高中数学 必修一", text=sample_text(title="集合"))
    library_b = env.new_library(
        grade_id="senior-1", subject_id="math", edition_id="renjiao-b", display_name="B版数学"
    )
    doc_b = env.add_document(
        title="高中数学 必修一",
        text=sample_text(title="集合的补集"),
        edition_id="renjiao-b",
        library_ids=[library_b],
    )

    snapshot = resolve_scope(env.catalog, env.selection(doc_a, edition_id="renjiao-a"))
    assert [item.documentId for item in snapshot.documents] == [doc_a.document_id]
    scope = verify_scope(env.catalog, snapshot)
    assert [item.document_revision_id for item in scope] == [doc_a.revision_id]

    pushed = allowed_filter(scope)
    assert isinstance(pushed, AllowedFilter)
    assert pushed.revision_ids == (doc_a.revision_id,)
    assert pushed.chunk_set_ids == (doc_a.chunk_set_id,)
    assert pushed.owners == ("system", "local-user")
    assert pushed.region == "body"
    assert doc_b.revision_id not in pushed.revision_ids
    assert doc_b.chunk_set_id not in pushed.chunk_set_ids

    candidates = env.retriever.retrieve(
        question="集合的表示方法",
        scope=scope,
        profile=env.profile,
        generation=env.generation,
    )
    assert candidates, "本册内应能检索到候选"
    assert {item.chunk_set_id for item in candidates} == {doc_a.chunk_set_id}
    assert {item.document_revision_id for item in candidates} == {doc_a.revision_id}
    assert env.vectors.calls, "向量检索必须发生"
    last = env.vectors.calls[-1]
    assert last["allowed"] is not None, "向量检索必须带范围过滤（禁止全库取回再过滤）"
    assert last["allowed"].revision_ids == (doc_a.revision_id,)
    assert last["allowed"].chunk_set_ids == (doc_a.chunk_set_id,)
    assert last["allowed"].region == "body"

    # 把 B 版册塞进 A 版范围：必须整体拒绝，不给"尽力而为"的部分结果
    with pytest.raises(AppError) as mixed:
        resolve_scope(env.catalog, env.selection(doc_a, doc_b, edition_id="renjiao-a"))
    assert mixed.value.code == "RAG_SCOPE_CHANGED"


def test_senior_two_math_and_physics_never_appear_together(tmp_path):
    env = RagEnv(tmp_path)
    library_math = env.new_library(grade_id="senior-2", subject_id="math", display_name="高二数学")
    library_physics = env.new_library(
        grade_id="senior-2", subject_id="physics", display_name="高二物理"
    )
    math = env.add_document(
        title="高二数学选择性必修",
        text=sample_text(title="数列"),
        grade_ids=("senior-2",),
        library_ids=[library_math],
    )
    physics = env.add_document(
        title="高二物理选择性必修",
        text=sample_text(title="电场"),
        subject_id="physics",
        grade_ids=("senior-2",),
        library_ids=[library_physics],
    )

    selection = env.selection(math, grade_id="senior-2", subject_id="math")
    scope = verify_scope(env.catalog, resolve_scope(env.catalog, selection))
    assert [item.document_revision_id for item in scope] == [math.revision_id]
    assert physics.revision_id not in {item.document_revision_id for item in scope}

    candidates = env.retriever.retrieve(
        question="数列的通项公式",
        scope=scope,
        profile=env.profile,
        generation=env.generation,
    )
    assert candidates
    assert physics.chunk_set_id not in {item.chunk_set_id for item in candidates}
    assert all(item.document_revision_id == math.revision_id for item in candidates)

    # 物理册不属于数学学科范围：混选必须拒绝，且不回退全库
    with pytest.raises(AppError) as cross_subject:
        resolve_scope(
            env.catalog,
            env.selection(math, physics, grade_id="senior-2", subject_id="math"),
        )
    assert cross_subject.value.code == "RAG_SCOPE_CHANGED"

    # 空范围：显式拒绝，不回退全库
    with pytest.raises(AppError) as empty:
        resolve_scope(env.catalog, env.selection(document_ids=[]))
    assert empty.value.code == "RAG_SCOPE_EMPTY"
    assert empty.value.status_code == 422


def test_verify_scope_reports_deleted_metadata_changed_and_generation_switched(tmp_path):
    env = RagEnv(tmp_path)

    deleted = env.add_document(title="将被删除的册", text=sample_text(title="集合"))
    deleted_snapshot = env.snapshot(deleted)
    record = env.catalog.get_document(deleted.document_id)
    env.catalog.delete_document(deleted.document_id, expected_revision=record.revision)
    with pytest.raises(AppError) as gone:
        verify_scope(env.catalog, deleted_snapshot)
    assert gone.value.code == "RAG_SCOPE_CHANGED" and gone.value.status_code == 409

    edited = env.add_document(title="将被改分类的册", text=sample_text(title="函数"))
    edited_snapshot = env.snapshot(edited)
    record = env.catalog.get_document(edited.document_id)
    env.catalog.update_document_metadata(
        edited.document_id,
        expected_revision=record.revision,
        title="改过的标题",
        stage_id="senior",
        grade_ids=["senior-1"],
        subject_id="math",
        edition_id="renjiao-a",
        library_ids=[env.library.library_id],
    )
    with pytest.raises(AppError) as changed:
        verify_scope(env.catalog, edited_snapshot)
    assert changed.value.code == "RAG_SCOPE_CHANGED"

    switched = env.add_document(title="将被换代的册", text=sample_text(title="统计"))
    switched_snapshot = env.snapshot(switched)
    link = next(
        item
        for item in env.catalog.list_generation_revisions(env.generation.generation_id)
        if item.document_revision_id == switched.revision_id
    )
    second = env.catalog.create_generation(
        profile_id=env.profile.profile_id,
        collection_name=f"textbooks_{uuid.uuid4().hex}",
        chunk_policy_json=generation_policy_document(),
        state="building",
    )
    env.vectors.ensure_collection(
        name=second.collection_name, dimensions=env.dimensions, distance="Cosine"
    )
    env.catalog.upsert_generation_revision(
        second.generation_id,
        switched.revision_id,
        link.chunk_set_id,
        state="ready",
        expected_chunk_count=link.expected_chunk_count,
        manifest_sha256=link.manifest_sha256,
    )
    env.catalog.publish_generation(second.generation_id)
    env.catalog.set_active_generation(second.generation_id)
    with pytest.raises(AppError) as switched_error:
        verify_scope(env.catalog, switched_snapshot)
    assert switched_error.value.code == "RAG_SCOPE_CHANGED"
    # 新代自身可用：用新快照重解析仍能通过（换的是指针，不是把一切判死）
    fresh = resolve_scope(env.catalog, env.selection(switched))
    assert fresh.embeddingGenerationId == second.generation_id
    assert [item.document_revision_id for item in verify_scope(env.catalog, fresh)] == [
        switched.revision_id
    ]


def test_scope_empty_and_index_not_ready_on_missing_generation(tmp_path):
    env = RagEnv(tmp_path)
    doc = env.add_document(title="暂时没有索引代的册", text=sample_text())
    env.catalog.set_active_generation(None)
    with pytest.raises(AppError) as not_ready:
        resolve_scope(env.catalog, env.selection(doc))
    assert not_ready.value.code == "INDEX_NOT_READY" and not_ready.value.status_code == 409
