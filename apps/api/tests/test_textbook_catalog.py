"""B0 教材目录权威层：迁移幂等、不可变修订、范围解析、任务幂等与损坏保护。

全部用例使用 pytest ``tmp_path`` 注入临时数据库；不读写正式 .local-data / .env，
不访问网络与 Ollama。
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import ChunkInput, DocumentRecord, GenerationRecord, LibraryRecord
from app.schemas.textbook import TextbookSelection

GRADE = "grade-7"
SUBJECT = "math"
EDITION_A = "renjiao-a"
EDITION_B = "beishida-a"
CHUNK_POLICY = "chunk-policy-1"
MANIFEST = "c" * 64


@pytest.fixture()
def catalog(tmp_path: Path) -> Iterator[TextbookCatalog]:
    instance = TextbookCatalog(tmp_path / "catalog.sqlite3")
    instance.migrate()
    yield instance
    instance.close()


# --------------------------------------------------------------------------- 测试辅助


def raw_execute(db_path: Path, sql: str, params: tuple = ()) -> None:
    connection = connect(db_path)
    try:
        connection.execute(sql, params)
    finally:
        connection.close()


def raw_scalar(db_path: Path, sql: str, params: tuple = ()) -> object:
    connection = connect(db_path)
    try:
        row = connection.execute(sql, params).fetchone()
    finally:
        connection.close()
    return row[0] if row is not None else None


def make_profile(catalog: TextbookCatalog, *, tag: str = "1"):
    return catalog.create_embedding_profile(
        fingerprint=f"fingerprint-{tag}",
        adapter="ollama",
        native_base_url="http://127.0.0.1:11434",
        model_name="bge-m3",
        model_manifest_digest=f"sha256-{tag}",
        dimensions=8,
        distance="cosine",
        query_prefix="",
        document_prefix="",
        normalization="none",
    )


def make_generation(catalog: TextbookCatalog, *, tag: str = "1", state: str = "ready") -> GenerationRecord:
    profile = make_profile(catalog, tag=tag)
    generation = catalog.create_generation(
        profile_id=profile.profile_id,
        collection_name=f"zqky_test_{tag}",
        chunk_policy_json={"target": 800, "overlap": 120},
        state="building",
    )
    if state == "ready":
        catalog.publish_generation(generation.generation_id)
    catalog.set_active_generation(generation.generation_id)
    return catalog.get_generation(generation.generation_id)


def make_library(
    catalog: TextbookCatalog,
    *,
    owner_id: str = "local-user",
    grade_id: str | None = GRADE,
    subject_id: str = SUBJECT,
    edition_id: str = EDITION_A,
    display_name: str = "我的教材",
) -> LibraryRecord:
    kind = "personal" if owner_id == "local-user" else "base"
    return catalog.create_library(
        kind=kind,
        owner_id=owner_id,
        display_name=display_name,
        grade_id=grade_id,
        subject_id=subject_id,
        edition_id=edition_id,
    )


def add_revision(catalog: TextbookCatalog, document: DocumentRecord, *, tag: str = "1"):
    return catalog.create_document_revision(
        document.document_id,
        original_file_sha256="a" * 64,
        normalized_text_sha256="b" * 64,
        parser_version=f"parser-{tag}",
        original_blob_id=f"orig-{tag}",
        normalized_blob_id=f"norm-{tag}",
        source_map_blob_id=f"map-{tag}",
        char_count=100,
    )


def make_scoped_document(
    catalog: TextbookCatalog,
    generation: GenerationRecord,
    *,
    title: str = "数学七年级上册",
    library: LibraryRecord | None = None,
    owner_id: str = "local-user",
    grade_id: str = GRADE,
    subject_id: str = SUBJECT,
    edition_id: str = EDITION_A,
    policy_fingerprint: str = CHUNK_POLICY,
    create_chunk_set: bool = True,
) -> tuple[DocumentRecord, str, str | None]:
    """建库 → 书册 → 修订 → 发布 → 分块 → 挂到索引代；返回 (书册, 修订 id, 分块集 id)。"""
    library = library or make_library(
        catalog,
        owner_id=owner_id,
        grade_id=grade_id,
        subject_id=subject_id,
        edition_id=edition_id,
        display_name=f"库：{title}",
    )
    document = catalog.create_document(
        owner_id=owner_id,
        title=title,
        stage_id="junior",
        grade_ids=[grade_id],
        subject_id=subject_id,
        edition_id=edition_id,
        library_ids=[library.library_id],
    )
    revision = add_revision(catalog, document, tag=document.document_id[:8])
    metadata = catalog.current_metadata_revision(document.document_id)
    published = catalog.publish_document_revision(
        document.document_id,
        revision_id=revision.revision_id,
        metadata_revision_id=metadata.metadata_revision_id,
    )
    if not create_chunk_set:
        return published, revision.revision_id, None
    chunk_set = catalog.create_chunk_set(
        revision.revision_id,
        policy_fingerprint=policy_fingerprint,
        manifest_sha256=MANIFEST,
        chunks=[
            ChunkInput(
                ordinal=0,
                char_start=0,
                char_end=50,
                region="body",
                chapter_path=["第一章"],
                text_sha256="d" * 64,
            )
        ],
    )
    catalog.upsert_generation_revision(
        generation.generation_id,
        revision.revision_id,
        chunk_set.chunk_set_id,
        state="ready",
        expected_chunk_count=1,
        manifest_sha256=MANIFEST,
    )
    return published, revision.revision_id, chunk_set.chunk_set_id


def selection_for(*document_ids: str, grade_id: str = GRADE, subject_id: str = SUBJECT, edition_id: str = EDITION_A):
    return TextbookSelection(
        gradeId=grade_id,
        subjectId=subject_id,
        editionId=edition_id,
        documentIds=list(document_ids),
    )


# --------------------------------------------------------------------------- 迁移


def test_migrate_is_idempotent(catalog: TextbookCatalog, tmp_path: Path) -> None:
    catalog.migrate()
    catalog.migrate()
    assert raw_scalar(catalog.db_path, "SELECT COUNT(*) FROM catalog_state") == 1
    state = catalog.catalog_state()
    assert state.active_generation_id is None
    assert state.rebuild_job_id is None
    assert state.catalog_version == 0

    tables = {
        "catalog_state",
        "embedding_profiles",
        "index_generations",
        "libraries",
        "documents",
        "library_documents",
        "document_metadata_revisions",
        "document_revisions",
        "chunk_sets",
        "chunks",
        "generation_revisions",
        "import_drafts",
        "index_jobs",
        "cleanup_queue",
        "teaching_settings",
    }
    connection = connect(catalog.db_path)
    try:
        existing = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    finally:
        connection.close()
    assert tables <= existing


def test_catalog_lifecycle_guards(tmp_path: Path) -> None:
    instance = TextbookCatalog(tmp_path / "lifecycle.sqlite3")
    with pytest.raises(AppError) as not_migrated:
        instance.catalog_state()
    assert (not_migrated.value.code, not_migrated.value.status_code) == ("CATALOG_NOT_MIGRATED", 500)

    instance.migrate()
    assert instance.catalog_state().catalog_version == 0
    instance.close()
    with pytest.raises(AppError) as closed:
        instance.catalog_state()
    assert (closed.value.code, closed.value.status_code) == ("CATALOG_CLOSED", 500)


# --------------------------------------------------------------------------- 逻辑库


def test_library_crud_and_optimistic_lock(catalog: TextbookCatalog) -> None:
    library = make_library(catalog, display_name="我的数学")
    assert catalog.get_library(library.library_id) == library
    assert [item.library_id for item in catalog.list_libraries(kind="personal")] == [library.library_id]

    updated = catalog.update_library(
        library.library_id, expected_revision=library.revision, display_name="我的数学（修订）"
    )
    assert updated.display_name == "我的数学（修订）"
    assert updated.revision == library.revision + 1

    with pytest.raises(AppError) as stale:
        catalog.update_library(library.library_id, expected_revision=library.revision, display_name="过期写入")
    assert (stale.value.code, stale.value.status_code) == ("REVISION_CONFLICT", 409)

    catalog.delete_library(library.library_id, expected_revision=updated.revision)
    assert catalog.list_libraries() == []
    assert catalog.list_libraries(include_deleted=True)[0].deleted_at is not None
    with pytest.raises(AppError) as gone:
        catalog.update_library(library.library_id, expected_revision=updated.revision + 1, display_name="已删")
    assert gone.value.code == "LIBRARY_NOT_FOUND"


# --------------------------------------------------------------------------- 修订不可变


def test_publish_switches_current_revision_and_keeps_old_metadata(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="publish")
    document, revision_one, _ = make_scoped_document(catalog, generation, title="数学一册")
    metadata_one = catalog.current_metadata_revision(document.document_id)
    assert document.current_revision_id == revision_one
    assert document.current_metadata_revision_id == metadata_one.metadata_revision_id
    assert document.revision == 1

    updated = catalog.update_document_metadata(
        document.document_id,
        expected_revision=document.revision,
        title="数学一册（改名）",
        stage_id="junior",
        grade_ids=[GRADE],
        subject_id=SUBJECT,
        edition_id=EDITION_A,
    )
    metadata_two = catalog.current_metadata_revision(updated.document_id)
    assert metadata_two.metadata_revision_id != metadata_one.metadata_revision_id
    assert metadata_two.title == "数学一册（改名）"
    # 旧元数据修订行必须原样保留，不被 update 改写
    assert catalog.get_metadata_revision(metadata_one.metadata_revision_id) == metadata_one
    assert catalog.get_metadata_revision(metadata_one.metadata_revision_id).title == "数学一册"

    revision_two = add_revision(catalog, document, tag="second")
    published = catalog.publish_document_revision(
        document.document_id,
        revision_id=revision_two.revision_id,
        metadata_revision_id=metadata_two.metadata_revision_id,
        expected_document_revision=updated.revision,
    )
    assert published.current_revision_id == revision_two.revision_id
    assert published.current_metadata_revision_id == metadata_two.metadata_revision_id
    assert published.revision == updated.revision + 1
    assert catalog.get_revision(revision_one) is not None
    assert len(catalog.list_document_revisions(document.document_id)) == 2

    with pytest.raises(AppError) as conflict:
        catalog.publish_document_revision(
            document.document_id,
            revision_id=revision_two.revision_id,
            metadata_revision_id=metadata_two.metadata_revision_id,
            expected_document_revision=updated.revision,
        )
    assert conflict.value.code == "REVISION_CONFLICT"


def test_update_document_metadata_never_touches_old_rows(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="immutable")
    document, _, _ = make_scoped_document(catalog, generation, title="不可变教材")
    metadata_one = catalog.current_metadata_revision(document.document_id)
    snapshot = raw_scalar(
        catalog.db_path,
        "SELECT grade_ids_json FROM document_metadata_revisions WHERE id = ?",
        (metadata_one.metadata_revision_id,),
    )
    catalog.update_document_metadata(
        document.document_id,
        expected_revision=document.revision,
        title="不可变教材（二版）",
        stage_id="junior",
        grade_ids=["grade-8"],
        subject_id=SUBJECT,
        edition_id=EDITION_A,
    )
    assert (
        raw_scalar(
            catalog.db_path,
            "SELECT title FROM document_metadata_revisions WHERE id = ?",
            (metadata_one.metadata_revision_id,),
        )
        == "不可变教材"
    )
    assert (
        raw_scalar(
            catalog.db_path,
            "SELECT grade_ids_json FROM document_metadata_revisions WHERE id = ?",
            (metadata_one.metadata_revision_id,),
        )
        == snapshot
    )


# --------------------------------------------------------------------------- 删除


def test_delete_document_marks_bumps_version_and_enqueues_cleanup(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="delete")
    document, revision_id, _ = make_scoped_document(catalog, generation, title="待删除教材")
    library_id = document.library_ids[0]
    version_before = catalog.catalog_state().catalog_version

    catalog.delete_document(document.document_id, expected_revision=document.revision)

    assert catalog.catalog_state().catalog_version == version_before + 1
    stored = catalog.get_document(document.document_id)
    assert stored.deleted_at is not None
    assert stored.revision == document.revision + 1
    assert stored.current_revision_id == revision_id  # 删除不改写有效修订
    assert catalog.pending_cleanup() == [document.document_id]

    assert catalog.list_documents() == []
    assert catalog.list_documents(library_id=library_id) == []
    assert [item.document_id for item in catalog.list_documents(include_deleted=True)] == [
        document.document_id
    ]
    assert catalog.library_document_ids(library_id) == []

    with pytest.raises(AppError) as unavailable:
        catalog.require_live_document(document.document_id)
    assert (unavailable.value.code, unavailable.value.status_code) == ("DOCUMENT_UNAVAILABLE", 409)

    # 清理队列幂等：重复入队不产生第二行，清理后移除
    catalog.enqueue_cleanup(document.document_id)
    assert catalog.pending_cleanup() == [document.document_id]
    catalog.clear_cleanup(document.document_id)
    assert catalog.pending_cleanup() == []


def test_delete_document_rejects_stale_revision(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="delete-stale")
    document, _, _ = make_scoped_document(catalog, generation, title="并发删除")
    catalog.update_document_metadata(
        document.document_id,
        expected_revision=document.revision,
        title="并发删除（改）",
        stage_id="junior",
        grade_ids=[GRADE],
        subject_id=SUBJECT,
        edition_id=EDITION_A,
    )
    with pytest.raises(AppError) as conflict:
        catalog.delete_document(document.document_id, expected_revision=document.revision)
    assert conflict.value.code == "REVISION_CONFLICT"
    assert catalog.get_document(document.document_id).deleted_at is None


# --------------------------------------------------------------------------- 任务幂等与租约


def test_create_job_is_idempotent_per_key_and_fingerprint(catalog: TextbookCatalog) -> None:
    first = catalog.create_job(
        kind="ingest", idempotency_key="submit-1", request_fingerprint="fp-1"
    )
    replay = catalog.create_job(
        kind="ingest", idempotency_key="submit-1", request_fingerprint="fp-1"
    )
    assert replay.job_id == first.job_id
    assert catalog.find_job_by_key("submit-1").job_id == first.job_id

    with pytest.raises(AppError) as conflict:
        catalog.create_job(kind="ingest", idempotency_key="submit-1", request_fingerprint="fp-2")
    assert (conflict.value.code, conflict.value.status_code) == ("IDEMPOTENCY_CONFLICT", 409)


def test_lease_claim_require_finish_and_recovery(catalog: TextbookCatalog) -> None:
    job = catalog.create_job(kind="ingest", idempotency_key="submit-lease", request_fingerprint="fp")
    assert catalog.has_active_ingest_jobs() is True
    assert catalog.first_recoverable_job().job_id == job.job_id

    claimed = catalog.claim_job(job.job_id, lease_seconds=60)
    assert claimed.state == "running"
    assert claimed.attempt == 1
    assert claimed.lease_token is not None
    assert catalog.require_lease(job.job_id, claimed.lease_token).job_id == job.job_id

    with pytest.raises(AppError) as wrong_token:
        catalog.require_lease(job.job_id, "0" * 32)
    assert (wrong_token.value.code, wrong_token.value.status_code) == ("LEASE_LOST", 409)

    # 租约未过期时不能被第二个执行者抢走
    with pytest.raises(AppError) as busy:
        catalog.claim_job(job.job_id, lease_seconds=60)
    assert busy.value.code == "JOB_BUSY"

    assert catalog.renew_lease(job.job_id, lease_token=claimed.lease_token, lease_seconds=60) is True
    assert catalog.renew_lease(job.job_id, lease_token="bad-token", lease_seconds=60) is False
    catalog.checkpoint_job(job.job_id, lease_token=claimed.lease_token, checkpoint={"documentsDone": 1})
    assert catalog.get_job(job.job_id).checkpoint == {"documentsDone": 1}

    with pytest.raises(AppError) as stale_finish:
        catalog.finish_job(job.job_id, lease_token="bad-token", state="succeeded")
    assert stale_finish.value.code == "LEASE_LOST"

    finished = catalog.finish_job(job.job_id, lease_token=claimed.lease_token, state="succeeded")
    assert finished.state == "succeeded"
    assert finished.lease_token is None and finished.lease_until is None
    assert catalog.has_active_ingest_jobs() is False
    assert catalog.first_recoverable_job() is None

    # 崩溃恢复：running 且租约过期的任务可被重新领取，attempt 递增
    crashed = catalog.create_job(kind="ingest", idempotency_key="submit-crash", request_fingerprint="fp")
    crashed_claim = catalog.claim_job(crashed.job_id, lease_seconds=90)
    raw_execute(
        catalog.db_path,
        "UPDATE index_jobs SET lease_until = ? WHERE id = ?",
        ("2000-01-01T00:00:00Z", crashed.job_id),
    )
    assert catalog.first_recoverable_job().job_id == crashed.job_id
    recovered = catalog.claim_job(crashed.job_id, lease_seconds=90)
    assert recovered.state == "running"
    assert recovered.attempt == 2
    assert recovered.lease_token != crashed_claim.lease_token


def test_job_reference_validation_and_listing(catalog: TextbookCatalog) -> None:
    with pytest.raises(AppError) as missing_revision:
        catalog.create_job(
            kind="ingest",
            idempotency_key="submit-bad",
            request_fingerprint="fp",
            input_revision_id="missing-revision",
        )
    assert missing_revision.value.code == "REVISION_NOT_FOUND"

    catalog.create_job(kind="ingest", idempotency_key="submit-a", request_fingerprint="fp")
    rebuild = catalog.create_job(kind="rebuild", idempotency_key="submit-b", request_fingerprint="fp")
    assert [item.job_id for item in catalog.list_jobs(kinds=["rebuild"])] == [rebuild.job_id]
    assert len(catalog.list_jobs(states=["queued"])) == 2
    assert catalog.list_jobs(states=["succeeded"]) == []
    with pytest.raises(AppError) as bad_kind:
        catalog.list_jobs(kinds=["unknown"])
    assert bad_kind.value.code == "INVALID_REQUEST"


# --------------------------------------------------------------------------- 范围解析


def test_resolve_selection_returns_allowed_documents_in_input_order(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="scope")
    library = make_library(catalog, display_name="七年级数学")
    first, first_revision, first_chunk_set = make_scoped_document(
        catalog, generation, title="数学一册", library=library
    )
    second, second_revision, second_chunk_set = make_scoped_document(
        catalog, generation, title="数学二册", library=library
    )

    resolved = catalog.resolve_selection(selection_for(second.document_id, first.document_id))

    assert [item.document_id for item in resolved] == [second.document_id, first.document_id]
    assert [item.document_revision_id for item in resolved] == [second_revision, first_revision]
    assert [item.chunk_set_id for item in resolved] == [second_chunk_set, first_chunk_set]
    assert resolved[0].library_ids == (library.library_id,)
    assert resolved[0].grade_ids == (GRADE,)
    assert resolved[0].title == "数学二册"
    assert resolved[0].metadata_revision_id == catalog.current_metadata_revision(
        second.document_id
    ).metadata_revision_id

    allowed = catalog.allowed_chunks(
        generation.generation_id, [first_revision, second_revision, first_revision]
    )
    assert allowed.revision_ids == (first_revision, second_revision)
    assert allowed.chunk_set_ids == (first_chunk_set, second_chunk_set)
    assert catalog.generation_chunk_total(generation.generation_id) == 2


def test_resolve_selection_rejects_empty_and_unready_index(catalog: TextbookCatalog) -> None:
    with pytest.raises(AppError) as no_generation:
        catalog.resolve_selection(selection_for("doc-missing"))
    assert (no_generation.value.code, no_generation.value.status_code) == ("INDEX_NOT_READY", 409)

    building = make_generation(catalog, tag="building", state="building")
    library = make_library(catalog, display_name="未发布索引")
    document, _, _ = make_scoped_document(catalog, building, title="未发布教材", library=library)
    with pytest.raises(AppError) as not_ready:
        catalog.resolve_selection(selection_for(document.document_id))
    assert not_ready.value.code == "INDEX_NOT_READY"


def test_resolve_selection_rejects_empty_scope(catalog: TextbookCatalog) -> None:
    make_generation(catalog, tag="empty-scope")
    with pytest.raises(AppError) as empty:
        catalog.resolve_selection(selection_for())
    assert (empty.value.code, empty.value.status_code) == ("RAG_SCOPE_EMPTY", 422)


def test_resolve_selection_rejects_grade_subject_edition_mismatch(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="mismatch")
    document, _, _ = make_scoped_document(catalog, generation, title="数学一册")

    cases = (
        selection_for(document.document_id, grade_id="grade-8"),
        selection_for(document.document_id, subject_id="physics"),
        selection_for(document.document_id, edition_id=EDITION_B),
    )
    for selection in cases:
        with pytest.raises(AppError) as error:
            catalog.resolve_selection(selection)
        assert (error.value.code, error.value.status_code) == ("RAG_SCOPE_CHANGED", 409)


def test_resolve_selection_rejects_library_gaps_deleted_and_unlinked(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="library-gaps")

    # 书册分类正确，但所在逻辑库年级未确认（NULL 不匹配任何任教范围）
    pending_library = make_library(catalog, grade_id=None, display_name="未确认年级库")
    in_pending, _, _ = make_scoped_document(
        catalog, generation, title="未确认库教材", library=pending_library
    )
    with pytest.raises(AppError) as pending:
        catalog.resolve_selection(selection_for(in_pending.document_id))
    assert pending.value.code == "RAG_SCOPE_CHANGED"

    # 未加入任何逻辑库
    unlinked = catalog.create_document(
        owner_id="local-user",
        title="未入库教材",
        stage_id="junior",
        grade_ids=[GRADE],
        subject_id=SUBJECT,
        edition_id=EDITION_A,
    )
    unlinked_revision = add_revision(catalog, unlinked, tag="unlinked")
    unlinked_metadata = catalog.current_metadata_revision(unlinked.document_id)
    catalog.publish_document_revision(
        unlinked.document_id,
        revision_id=unlinked_revision.revision_id,
        metadata_revision_id=unlinked_metadata.metadata_revision_id,
    )
    with pytest.raises(AppError) as no_library:
        catalog.resolve_selection(selection_for(unlinked.document_id))
    assert no_library.value.code == "RAG_SCOPE_CHANGED"

    # 已逻辑删除的书册
    deleted_library = make_library(catalog, display_name="待删书库")
    deleted_doc, _, _ = make_scoped_document(
        catalog, generation, title="待删教材", library=deleted_library
    )
    catalog.delete_document(deleted_doc.document_id, expected_revision=deleted_doc.revision)
    with pytest.raises(AppError) as deleted:
        catalog.resolve_selection(selection_for(deleted_doc.document_id))
    assert deleted.value.code == "RAG_SCOPE_CHANGED"

    # 逻辑库被删除后成员关系失效
    removed_library = make_library(catalog, display_name="待删逻辑库")
    removed_doc, _, _ = make_scoped_document(
        catalog, generation, title="库已删教材", library=removed_library
    )
    catalog.delete_library(removed_library.library_id, expected_revision=removed_library.revision)
    with pytest.raises(AppError) as removed:
        catalog.resolve_selection(selection_for(removed_doc.document_id))
    assert removed.value.code == "RAG_SCOPE_CHANGED"


def test_resolve_selection_rejects_pending_generation_revision(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="pending-revision")
    library = make_library(catalog, display_name="待索引库")
    document, revision_id, _ = make_scoped_document(
        catalog, generation, title="待索引教材", library=library, create_chunk_set=False
    )
    chunk_set = catalog.create_chunk_set(
        revision_id,
        policy_fingerprint=CHUNK_POLICY,
        manifest_sha256=MANIFEST,
        chunks=[ChunkInput(0, 0, 50, "body", ["第一章"], "d" * 64)],
    )
    catalog.upsert_generation_revision(
        generation.generation_id,
        revision_id,
        chunk_set.chunk_set_id,
        state="pending",
        expected_chunk_count=1,
        manifest_sha256=MANIFEST,
    )
    with pytest.raises(AppError) as not_ready:
        catalog.resolve_selection(selection_for(document.document_id))
    assert (not_ready.value.code, not_ready.value.status_code) == ("INDEX_NOT_READY", 409)

    with pytest.raises(AppError) as allowed:
        catalog.allowed_chunks(generation.generation_id, [revision_id])
    assert allowed.value.code == "INDEX_NOT_READY"


def test_resolve_selection_does_not_cross_editions(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="editions")
    library_a = make_library(catalog, edition_id=EDITION_A, display_name="人教A库")
    library_b = make_library(catalog, edition_id=EDITION_B, display_name="北师A库")
    doc_a, revision_a, chunk_a = make_scoped_document(
        catalog, generation, title="同名教材", library=library_a, edition_id=EDITION_A
    )
    doc_b, revision_b, chunk_b = make_scoped_document(
        catalog, generation, title="同名教材", library=library_b, edition_id=EDITION_B
    )

    resolved_a = catalog.resolve_selection(selection_for(doc_a.document_id, edition_id=EDITION_A))
    assert [item.document_id for item in resolved_a] == [doc_a.document_id]
    assert resolved_a[0].document_revision_id == revision_a
    assert resolved_a[0].chunk_set_id == chunk_a
    assert resolved_a[0].library_ids == (library_a.library_id,)

    resolved_b = catalog.resolve_selection(selection_for(doc_b.document_id, edition_id=EDITION_B))
    assert [item.document_id for item in resolved_b] == [doc_b.document_id]
    assert resolved_b[0].document_revision_id == revision_b
    assert resolved_b[0].library_ids == (library_b.library_id,)

    with pytest.raises(AppError) as mixed:
        catalog.resolve_selection(selection_for(doc_a.document_id, doc_b.document_id))
    assert mixed.value.code == "RAG_SCOPE_CHANGED"
    assert chunk_b == catalog.resolve_selection(
        selection_for(doc_b.document_id, edition_id=EDITION_B)
    )[0].chunk_set_id


def test_resolve_selection_uses_injected_schema_selection_type(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="schema-type")
    document, _, _ = make_scoped_document(catalog, generation, title="契约类型教材")
    selection = TextbookSelection.model_validate(
        {
            "gradeId": GRADE,
            "subjectId": SUBJECT,
            "editionId": EDITION_A,
            "documentIds": [document.document_id],
        }
    )
    assert [item.document_id for item in catalog.resolve_selection(selection)] == [document.document_id]


# --------------------------------------------------------------------------- 分块集


def test_chunk_set_replay_is_idempotent_and_chunks_are_ordered(catalog: TextbookCatalog) -> None:
    library = make_library(catalog, display_name="分块库")
    document = catalog.create_document(
        owner_id="local-user",
        title="分块教材",
        stage_id="junior",
        grade_ids=[GRADE],
        subject_id=SUBJECT,
        edition_id=EDITION_A,
        library_ids=[library.library_id],
    )
    revision = add_revision(catalog, document, tag="chunks")
    chunks = [
        ChunkInput(2, 20, 30, "exercise", ["第一章", "习题"], "e" * 64),
        ChunkInput(0, 0, 10, "body", ["第一章"], "d" * 64, legacy_chunk_id="legacy-0"),
        ChunkInput(1, 10, 20, "body", ["第一章"], "f" * 64),
    ]

    first = catalog.create_chunk_set(
        revision.revision_id,
        policy_fingerprint=CHUNK_POLICY,
        manifest_sha256=MANIFEST,
        chunks=chunks,
    )
    # 同修订 + 同策略 + 同内容：重放返回既有分块集（锁定行为）
    replay = catalog.create_chunk_set(
        revision.revision_id,
        policy_fingerprint=CHUNK_POLICY,
        manifest_sha256=MANIFEST,
        chunks=list(reversed(chunks)),
    )
    assert replay.chunk_set_id == first.chunk_set_id
    assert replay.chunk_count == 3
    assert catalog.find_chunk_set(revision.revision_id, CHUNK_POLICY).chunk_set_id == first.chunk_set_id

    ordered = catalog.list_chunks(first.chunk_set_id)
    assert [item.ordinal for item in ordered] == [0, 1, 2]
    assert ordered[0].legacy_chunk_id == "legacy-0"
    assert catalog.get_chunk(first.chunk_set_id, 2).region == "exercise"
    assert catalog.get_chunk(first.chunk_set_id, 9) is None

    # 同键不同内容必须拒绝，不能覆盖既有分块集
    with pytest.raises(AppError) as conflict:
        catalog.create_chunk_set(
            revision.revision_id,
            policy_fingerprint=CHUNK_POLICY,
            manifest_sha256="9" * 64,
            chunks=chunks,
        )
    assert (conflict.value.code, conflict.value.status_code) == ("IDEMPOTENCY_CONFLICT", 409)
    assert catalog.get_chunk_set(first.chunk_set_id).manifest_sha256 == MANIFEST


# --------------------------------------------------------------------------- 损坏保护


def test_corrupt_json_raises_catalog_corrupt_and_is_not_rewritten(catalog: TextbookCatalog) -> None:
    generation = make_generation(catalog, tag="corrupt")
    document, _, _ = make_scoped_document(catalog, generation, title="损坏教材")
    metadata_id = catalog.current_metadata_revision(document.document_id).metadata_revision_id
    raw_execute(
        catalog.db_path,
        "UPDATE document_metadata_revisions SET grade_ids_json = ? WHERE id = ?",
        ("{", metadata_id),
    )

    with pytest.raises(AppError) as corrupted:
        catalog.get_document(document.document_id)
    assert (corrupted.value.code, corrupted.value.status_code) == ("CATALOG_CORRUPT", 500)

    with pytest.raises(AppError) as in_scope:
        catalog.resolve_selection(selection_for(document.document_id))
    assert in_scope.value.code == "CATALOG_CORRUPT"

    # 读失败不得改写原行
    assert (
        raw_scalar(
            catalog.db_path,
            "SELECT grade_ids_json FROM document_metadata_revisions WHERE id = ?",
            (metadata_id,),
        )
        == "{"
    )


# --------------------------------------------------------------------------- Embedding / 索引代 / 导入 / 任教设置


def test_embedding_profile_conflict_validations_and_retirement(catalog: TextbookCatalog) -> None:
    profile = make_profile(catalog, tag="profile")
    assert catalog.find_embedding_profile(profile.fingerprint).profile_id == profile.profile_id
    assert catalog.get_embedding_profile(profile.profile_id) == profile
    assert [item.profile_id for item in catalog.list_embedding_profiles()] == [profile.profile_id]

    with pytest.raises(AppError) as duplicate:
        make_profile(catalog, tag="profile")
    assert (duplicate.value.code, duplicate.value.status_code) == ("PROFILE_CONFLICT", 409)

    with pytest.raises(AppError) as adapter:
        catalog.create_embedding_profile(
            fingerprint="fingerprint-x",
            adapter="openai",
            native_base_url="http://127.0.0.1:11434",
            model_name="text-embedding-3",
            model_manifest_digest="sha256-x",
            dimensions=1536,
            distance="cosine",
            query_prefix="",
            document_prefix="",
            normalization="none",
        )
    assert adapter.value.code == "INVALID_REQUEST"

    with pytest.raises(AppError) as normalization:
        catalog.create_embedding_profile(
            fingerprint="fingerprint-y",
            adapter="ollama",
            native_base_url="http://127.0.0.1:11434",
            model_name="bge-m3",
            model_manifest_digest="sha256-y",
            dimensions=8,
            distance="cosine",
            query_prefix="",
            document_prefix="",
            normalization="l1",
        )
    assert normalization.value.code == "INVALID_REQUEST"

    catalog.retire_embedding_profile(profile.profile_id)
    assert catalog.get_embedding_profile(profile.profile_id).retired_at is not None
    catalog.retire_embedding_profile(profile.profile_id)  # 重复退役是幂等的


def test_generation_state_publish_and_collection_conflict(catalog: TextbookCatalog) -> None:
    profile = make_profile(catalog, tag="generation")
    generation = catalog.create_generation(
        profile_id=profile.profile_id,
        collection_name="zqky_test_generation",
        chunk_policy_json={"target": 800},
    )
    assert generation.state == "building"
    assert generation.published_at is None
    assert generation.chunk_policy == {"target": 800}

    catalog.publish_generation(generation.generation_id)
    published = catalog.get_generation(generation.generation_id)
    assert published.state == "ready"
    assert published.published_at is not None
    catalog.publish_generation(generation.generation_id)
    # 重复发布不刷新 published_at，也不改变状态
    assert catalog.get_generation(generation.generation_id).published_at == published.published_at

    with pytest.raises(AppError) as conflict:
        catalog.create_generation(
            profile_id=profile.profile_id,
            collection_name="zqky_test_generation",
            chunk_policy_json={},
        )
    assert conflict.value.code == "COLLECTION_CONFLICT"

    aborted = catalog.create_generation(
        profile_id=profile.profile_id,
        collection_name="zqky_test_generation_aborted",
        chunk_policy_json={},
    )
    catalog.update_generation_state(aborted.generation_id, "aborted")
    with pytest.raises(AppError) as aborted_publish:
        catalog.publish_generation(aborted.generation_id)
    assert aborted_publish.value.code == "GENERATION_ABORTED"


def test_import_draft_revision_and_optimistic_lock(catalog: TextbookCatalog) -> None:
    draft = catalog.create_import(
        owner_id="local-user",
        uploaded_file_name="book.pdf",
        uploaded_bytes=1024,
        uploaded_blob_id="blob-1",
        warnings=["需要 OCR"],
    )
    assert draft.state == "uploaded"
    assert draft.revision == 0
    assert draft.warnings == ["需要 OCR"]

    updated = catalog.update_import(
        draft.import_id,
        expected_revision=0,
        state="needs_review",
        metadata_json={"title": "数学一册"},
        warnings_json=["已解析"],
    )
    assert updated.revision == 1
    assert updated.state == "needs_review"
    assert updated.metadata == {"title": "数学一册"}
    assert updated.warnings == ["已解析"]

    with pytest.raises(AppError) as conflict:
        catalog.update_import(draft.import_id, expected_revision=0, state="ready")
    assert (conflict.value.code, conflict.value.status_code) == ("REVISION_CONFLICT", 409)

    with pytest.raises(AppError) as unknown_field:
        catalog.update_import(draft.import_id, expected_revision=1, unexpected_field="x")
    assert unknown_field.value.code == "INVALID_REQUEST"

    assert [item.import_id for item in catalog.list_imports()] == [draft.import_id]


def test_teaching_settings_revision_conflict_and_clearing(catalog: TextbookCatalog) -> None:
    initial = catalog.get_teaching_settings()
    assert initial.revision == 0
    assert initial.selection_json is None

    saved = catalog.set_teaching_settings(
        selection_json={
            "gradeId": GRADE,
            "subjectId": SUBJECT,
            "editionId": EDITION_A,
            "documentIds": [],
        },
        expected_revision=0,
    )
    assert saved.revision == 1
    assert saved.selection == {
        "gradeId": GRADE,
        "subjectId": SUBJECT,
        "editionId": EDITION_A,
        "documentIds": [],
    }

    with pytest.raises(AppError) as conflict:
        catalog.set_teaching_settings(selection_json=None, expected_revision=0)
    assert (conflict.value.code, conflict.value.status_code) == ("REVISION_CONFLICT", 409)

    cleared = catalog.set_teaching_settings(selection_json=None, expected_revision=1)
    assert cleared.selection_json is None
    assert cleared.revision == 2
    assert catalog.get_teaching_settings().revision == 2


def test_catalog_is_usable_across_threads(catalog: TextbookCatalog) -> None:
    """FastAPI 同步路由运行在线程池：实例必须能在其他线程读写，不能绑定创建线程。"""
    library = make_library(catalog, display_name="线程库")
    created: list[str] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            document = catalog.create_document(
                owner_id="local-user",
                title="线程教材",
                stage_id="junior",
                grade_ids=[GRADE],
                subject_id=SUBJECT,
                edition_id=EDITION_A,
                library_ids=[library.library_id],
            )
            created.append(catalog.get_document(document.document_id).title)
        except BaseException as exc:  # 断言收集：跨线程访问应成功
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert errors == []
    assert created == ["线程教材"]
    assert catalog.list_libraries()[0].library_id == library.library_id


def test_document_origin_key_is_unique_per_owner(catalog: TextbookCatalog) -> None:
    owner_fields = {
        "title": "系统教材",
        "stage_id": "junior",
        "grade_ids": [GRADE],
        "subject_id": SUBJECT,
        "edition_id": EDITION_A,
    }
    first = catalog.create_document(owner_id="system", origin_key="textbook/a.md", **owner_fields)
    assert catalog.find_document_by_origin_key("system", "textbook/a.md").document_id == first.document_id

    with pytest.raises(AppError) as conflict:
        catalog.create_document(owner_id="system", origin_key="textbook/a.md", **owner_fields)
    assert conflict.value.code == "DOCUMENT_ORIGIN_CONFLICT"

    other = catalog.create_document(owner_id="local-user", origin_key="textbook/a.md", **owner_fields)
    assert other.document_id != first.document_id
    # 逻辑删除后来源键仍然唯一，find 仍能看到已删除书册
    catalog.delete_document(first.document_id, expected_revision=first.revision)
    found = catalog.find_document_by_origin_key("system", "textbook/a.md")
    assert found.document_id == first.document_id
    assert found.deleted_at is not None
