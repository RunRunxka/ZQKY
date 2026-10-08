"""索引代：状态、配置探测、重建闸门与发布、失败回退、删除跳过与清理。

复用入库测试的替身（内存向量库 + 假 Embedding + tmp_path 目录），不连接真实 Qdrant/Ollama。
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.services.text_projection import TEXT_PROJECTION_VERSION
from app.core.exceptions import AppError
from app.repositories.vector_store import AllowedFilter, InMemoryVectorStore
from app.services.textbook_ingest import (
    DEFAULT_RENEW_SECONDS,
    generation_manifest,
    generation_policy,
    new_collection_name,
)
from app.services.textbook_index import IndexService
from tests.test_textbook_ingest import (
    CountingVectorStore,
    FakeClock,
    FakeEmbeddings,
    Harness,
    _install_lease_spy,
    long_text,
    sample_text,
)


class BrokenVectorStore(InMemoryVectorStore):
    """只破坏健康探测：用于断言 status 如实报告不可用而不抛错。"""

    def ping(self) -> bool:
        return False

    def ping_error(self) -> str | None:
        return "连接被拒绝（测试替身）"


class FailingDeleteStore(InMemoryVectorStore):
    def delete_by_filter(self, *, name: str, allowed: AllowedFilter) -> None:
        raise AppError("Qdrant 不可达", code="QDRANT_UNAVAILABLE", status_code=503, retryable=True)


class IndexHarness:
    def __init__(
        self,
        tmp_path: Path,
        *,
        vectors=None,
        embeddings=None,
        bootstrap=True,
        monotonic=None,
        renew_seconds: float = DEFAULT_RENEW_SECONDS,
        batch_size: int = 8,
        model_name: str = "bge-m3",
    ) -> None:
        self.base = Harness(
            tmp_path,
            vectors=vectors,
            embeddings=embeddings,
            bootstrap=bootstrap,
            batch_size=batch_size,
            monotonic=monotonic,
            renew_seconds=renew_seconds,
            model_name=model_name,
        )
        self.catalog = self.base.catalog
        self.vectors = self.base.vectors
        self.embeddings = self.base.embeddings
        self.settings = self.base.settings
        self.service = IndexService(
            self.catalog,
            self.embeddings,
            self.vectors,
            self.settings,
            sleep=lambda _seconds: None,
            batch_size=batch_size,
            renew_seconds=renew_seconds,
            monotonic=monotonic or time.monotonic,
        )

    def publish_document(self, text: str = "集合", *, submission_id: str = "submission-index-1"):
        draft = self.base.import_with_metadata(sample_text(text))
        return self.base.commit_and_run(draft, submission_id=submission_id)

    def publish_long_document(self, *, submission_id: str = "submission-index-long"):
        """约 10 个块的长册：用于观察多批次边界上的租约续租。"""
        draft = self.base.import_with_metadata(long_text(), file_name="long.md")
        return self.base.commit_and_run(draft, submission_id=submission_id)


@pytest.fixture()
def env(tmp_path: Path) -> IndexHarness:
    return IndexHarness(tmp_path)


# ------------------------------------------------------------------------ 状态


def test_status_reports_qdrant_failure_without_raising(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, vectors=BrokenVectorStore())
    status = env.service.status()
    assert status.qdrantAvailable is False
    assert status.qdrantReason
    assert "测试替身" in status.qdrantReason
    assert status.scopeReady is False


def test_status_after_empty_generation_is_not_scope_ready(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, bootstrap=False)
    generation = env.service.ensure_empty_generation(env.base.profile.profile_id)
    assert env.catalog.catalog_state().active_generation_id == generation.generation_id
    status = env.service.status()
    assert status.qdrantAvailable is True
    assert status.scopeReady is False
    assert status.scopeReason
    assert status.activeProfileName == "bge-m3"
    assert status.activeProfileDimensions == 4
    assert status.generation is not None and status.generation.state == "ready"
    assert status.generationCount == 1


def test_status_after_publish_is_scope_ready(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    env.publish_document()
    status = env.service.status()
    assert status.scopeReady is True
    assert status.scopeReason is None
    assert status.generation is not None
    assert status.generation.chunkTotal > 0
    assert status.generation.documentTotal == 1
    assert status.rebuildJob is None


# ------------------------------------------------------------------ Embedding 配置


def test_probe_and_create_profile_is_idempotent_by_fingerprint(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, bootstrap=False)
    probe = env.service.probe(model_name="bge-m3")
    assert probe.dimensions == 4
    assert probe.alreadyConfigured is True  # Harness 已登记同指纹配置
    assert probe.existingProfileId is not None

    created = env.service.create_profile(model_name="bge-m3")
    assert created.profileId == probe.existingProfileId
    listed = env.service.list_profiles()
    assert listed.activeProfileId is None
    assert len(listed.profiles) == 1
    assert listed.profiles[0].installed is True


def test_list_profiles_marks_uninstalled_when_local_service_unavailable(tmp_path: Path) -> None:
    class UnreachableEmbeddings(FakeEmbeddings):
        def list_models(self):
            raise AppError("不可达", code="EMBEDDING_UNAVAILABLE", status_code=503, retryable=True)

    env = IndexHarness(tmp_path, embeddings=UnreachableEmbeddings(), bootstrap=False)
    listed = env.service.list_profiles()
    assert listed.profiles[0].installed is False  # 无法证明已安装，不猜


def test_probe_rejects_unknown_model(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, bootstrap=False)
    with pytest.raises(AppError) as exc_info:
        env.service.probe(model_name="not-installed")
    assert exc_info.value.code == "EMBEDDING_MODEL_MISSING"


def test_retire_profile_is_idempotent_and_reports_retired_at(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, bootstrap=False)
    retired = env.service.retire_profile(env.base.profile.profile_id)
    assert retired.retiredAt is not None
    assert retired.isActive is False

    again = env.service.retire_profile(env.base.profile.profile_id)
    assert again.retiredAt == retired.retiredAt  # 已停用再调不报错，且时间戳不变

    # 重建选择已停用配置应被既有守卫拒绝（语义不改，这里只确认守卫存在）
    profile = env.catalog.get_embedding_profile(env.base.profile.profile_id)
    with pytest.raises(AppError) as guard:
        env.service.indexer.require_profile_usable(profile)
    assert guard.value.code == "PROFILE_RETIRED"


def test_retire_profile_missing_returns_404(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, bootstrap=False)
    with pytest.raises(AppError) as exc_info:
        env.service.retire_profile("nope")
    assert exc_info.value.code == "PROFILE_NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_delete_profile_hard_deletes_when_unreferenced(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, bootstrap=False)
    spare = env.catalog.create_embedding_profile(
        fingerprint="fingerprint-spare",
        adapter="ollama",
        native_base_url="http://127.0.0.1:11434",
        model_name="bge-m3",
        model_manifest_digest="digest-1",
        dimensions=4,
        distance="cosine",
        query_prefix="",
        document_prefix="",
        normalization="none",
    )
    env.service.delete_profile(spare.profile_id)
    assert env.catalog.get_embedding_profile(spare.profile_id) is None
    assert env.catalog.get_embedding_profile(env.base.profile.profile_id) is not None


def test_delete_profile_rejects_generation_referenced_profile(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)  # bootstrap=True：base 配置已有一个索引代引用
    with pytest.raises(AppError) as exc_info:
        env.service.delete_profile(env.base.profile.profile_id)
    assert exc_info.value.code == "EMBEDDING_PROFILE_IN_USE"
    assert exc_info.value.status_code == 409
    assert "请改用停用" in str(exc_info.value)
    # 守卫删除失败后配置仍在，可改走停用路径
    assert env.catalog.get_embedding_profile(env.base.profile.profile_id) is not None
    retired = env.service.retire_profile(env.base.profile.profile_id)
    assert retired.retiredAt is not None


def test_delete_profile_missing_returns_404(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, bootstrap=False)
    with pytest.raises(AppError) as exc_info:
        env.service.delete_profile("nope")
    assert exc_info.value.code == "PROFILE_NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_retired_profile_cannot_begin_rebuild(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, bootstrap=False)
    env.service.ensure_empty_generation(env.base.profile.profile_id)
    env.service.retire_profile(env.base.profile.profile_id)
    with pytest.raises(AppError) as exc_info:
        env.service.begin_rebuild(
            profile_id=env.base.profile.profile_id, submission_id="submission-retire-1"
        )
    assert exc_info.value.code == "PROFILE_RETIRED"


# ---------------------------------------------------------------------- 重建闸门


def test_begin_rebuild_gates(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    with pytest.raises(AppError) as missing:
        env.service.begin_rebuild(profile_id="nope", submission_id="submission-rebuild-x")
    assert (missing.value.code, missing.value.status_code) == ("PROFILE_NOT_FOUND", 404)

    env.embeddings.digest = "digest-changed"
    with pytest.raises(AppError) as changed:
        env.service.begin_rebuild(
            profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-y"
        )
    assert (changed.value.code, changed.value.status_code) == ("EMBEDDING_MODEL_CHANGED", 409)
    env.embeddings.digest = "digest-1"

    first = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-1"
    )
    assert first.state == "queued"
    assert env.catalog.catalog_state().rebuild_job_id == first.jobId

    with pytest.raises(AppError) as busy:
        env.service.begin_rebuild(
            profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-2"
        )
    assert (busy.value.code, busy.value.status_code) == ("INDEX_MUTATION_BUSY", 409)

    # 幂等重放返回同一任务
    replay = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-1"
    )
    assert replay.jobId == first.jobId


def test_begin_rebuild_blocked_by_active_ingest_job(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    draft = env.base.import_with_metadata(sample_text())
    env.base.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-ingest-busy",
        library_ids=[env.base.library.library_id],
    )
    with pytest.raises(AppError) as exc_info:
        env.service.begin_rebuild(
            profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-3"
        )
    assert (exc_info.value.code, exc_info.value.status_code) == ("INDEX_MUTATION_BUSY", 409)


# ------------------------------------------------------------------------ 发布


def test_rebuild_switches_active_generation_and_keeps_old(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    published = env.publish_document()
    old_generation = env.base.generation
    old_collection = env.base.collection

    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-ok"
    )
    generation = env.catalog.get_generation(job.targetGenerationId)
    manifest = generation_manifest(generation)
    assert len(manifest) == 1  # 冻结清单包含开始时的当前修订

    final = env.service.run_rebuild(job.jobId)
    assert final.state == "succeeded", final.errorMessage
    state = env.catalog.catalog_state()
    assert state.active_generation_id == generation.generation_id
    assert state.rebuild_job_id is None

    links = env.catalog.list_generation_revisions(generation.generation_id)
    assert links[0].state == "ready"
    assert env.vectors.count(name=generation.collection_name) == links[0].expected_chunk_count
    # 旧代与其向量保留（未过期定位轮继续可用）
    assert env.catalog.get_generation(old_generation.generation_id).state == "ready"
    assert env.vectors.count(name=old_collection) > 0

    status = env.service.status()
    assert status.scopeReady is True
    assert status.activeGenerationId == generation.generation_id
    documents = env.catalog.list_documents()
    assert documents[0].current_revision_id == published.inputRevisionId


def test_rebuild_failure_keeps_active_generation_and_aborts_target(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    env.publish_document()
    active_before = env.catalog.catalog_state().active_generation_id
    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-fail"
    )
    env.embeddings.fail_next = 100
    final = env.service.run_rebuild(job.jobId)
    assert final.state == "failed"
    assert final.errorCode == "EMBEDDING_UNAVAILABLE"
    state = env.catalog.catalog_state()
    assert state.active_generation_id == active_before  # 旧代继续可用
    assert state.rebuild_job_id is None  # 闸门释放
    assert env.catalog.get_generation(job.targetGenerationId).state == "aborted"
    assert env.service.status().scopeReady is True


def test_rebuild_cancel_aborts_target_and_releases_gate(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    env.publish_document()
    active_before = env.catalog.catalog_state().active_generation_id
    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-cancel"
    )
    cancelled = env.service.cancel_job(job.jobId)
    assert cancelled.state == "cancelled"
    assert env.catalog.catalog_state().rebuild_job_id is None
    assert env.catalog.get_generation(job.targetGenerationId).state == "aborted"
    assert env.catalog.catalog_state().active_generation_id == active_before


def test_rebuild_deleted_document_is_marked_skipped_and_not_revived(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    env.publish_document()
    document = env.catalog.list_documents()[0]
    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-delete"
    )
    # 重建开始后删除书册
    env.catalog.delete_document(document.document_id, expected_revision=document.revision)
    final = env.service.run_rebuild(job.jobId)
    assert final.state == "succeeded", final.errorMessage

    links = env.catalog.list_generation_revisions(job.targetGenerationId)
    assert [(link.state) for link in links] == ["skipped_deleted"]
    assert links[0].expected_chunk_count == 0
    generation = env.catalog.get_generation(job.targetGenerationId)
    assert env.vectors.count(name=generation.collection_name) == 0
    # 不复活：逻辑删除与当前修订都不被重建改写
    after = env.catalog.get_document(document.document_id)
    assert after.deleted_at is not None
    assert after.current_revision_id == document.current_revision_id


def test_rebuild_without_gate_fails_loudly(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    env.publish_document()
    active_before = env.catalog.catalog_state().active_generation_id
    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-lost"
    )
    env.catalog.set_rebuild_job(None)  # 闸门被其他路径释放
    final = env.service.run_rebuild(job.jobId)
    assert final.state == "failed"
    assert final.errorCode == "REBUILD_GATE_LOST"
    assert env.catalog.get_generation(job.targetGenerationId).state == "aborted"
    assert env.catalog.catalog_state().active_generation_id == active_before


def test_terminate_rebuild_is_idempotent_and_keeps_active(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    env.publish_document()
    active_before = env.catalog.catalog_state().active_generation_id
    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-term"
    )
    terminated = env.service.terminate_rebuild(
        job.jobId, state="failed", error_code="EMBEDDING_UNAVAILABLE", error_message="测试"
    )
    assert terminated.state == "failed"
    assert env.catalog.catalog_state().rebuild_job_id is None
    assert env.catalog.get_generation(job.targetGenerationId).state == "aborted"
    assert env.catalog.catalog_state().active_generation_id == active_before
    again = env.service.terminate_rebuild(
        job.jobId, state="failed", error_code="EMBEDDING_UNAVAILABLE"
    )
    assert again.state == "failed"


def test_rebuild_resume_after_crash_skips_ready_revisions(tmp_path: Path) -> None:
    """硬崩溃（未写终态、租约过期）后恢复：已 ready 的修订不重做，向量不重复。"""
    import time

    env = IndexHarness(tmp_path)
    env.publish_document("集合", submission_id="submission-a")
    second = env.base.import_with_metadata(sample_text("集合的运算"), file_name="b.md")
    env.base.commit_and_run(second, submission_id="submission-b")
    assert len(env.catalog.list_documents()) == 2

    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-crash"
    )
    original_checkpoint = env.service.indexer.checkpoint
    calls = {"count": 0}

    def flaky_checkpoint(**kwargs):
        calls["count"] += 1
        if calls["count"] >= 3:  # 第一册完成后进程中断
            raise RuntimeError("simulated crash")
        return original_checkpoint(**kwargs)

    env.service.indexer.checkpoint = flaky_checkpoint
    env.service.terminate_rebuild_record = lambda job, state, code, message: env.catalog.get_job(job.job_id)  # type: ignore[assignment]
    env.service.run_rebuild(job.jobId, lease_seconds=1)
    env.service.indexer.checkpoint = original_checkpoint
    assert env.catalog.get_job(job.jobId).state == "running"  # 崩溃留下 running 与过期租约

    time.sleep(1.05)
    recovered = IndexService(
        env.catalog, env.embeddings, env.vectors, env.settings, sleep=lambda _s: None
    )
    assert recovered.recover_pending_jobs() == 1
    assert env.catalog.get_job(job.jobId).state == "succeeded"

    links = env.catalog.list_generation_revisions(job.targetGenerationId)
    assert {link.state for link in links} == {"ready"}
    generation = env.catalog.get_generation(job.targetGenerationId)
    assert env.vectors.count(name=generation.collection_name) == sum(
        link.expected_chunk_count for link in links
    )


def test_recover_releases_stale_gate(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    env.publish_document()
    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-stale"
    )
    # 手工把任务写成终态（模拟崩溃后残留闸门）
    claimed = env.catalog.claim_job(job.jobId)
    env.catalog.finish_job(
        claimed.job_id, lease_token=claimed.lease_token or "", state="failed", error_code="X"
    )
    assert env.catalog.catalog_state().rebuild_job_id == job.jobId
    assert env.service.recover_pending_jobs() == 0
    assert env.catalog.catalog_state().rebuild_job_id is None


# ------------------------------------------------------------------------ 清理


def test_cleanup_document_deletes_vectors_and_clears_queue(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    env.publish_document()
    document = env.catalog.list_documents()[0]
    env.catalog.delete_document(document.document_id, expected_revision=document.revision)
    assert document.document_id in env.catalog.pending_cleanup()
    removed = env.service.cleanup_document(document.document_id)
    assert removed == 1
    assert env.vectors.count(name=env.base.collection) == 0
    assert env.catalog.pending_cleanup() == []
    # 逻辑删除不受清理影响
    assert env.catalog.get_document(document.document_id).deleted_at is not None


def test_cleanup_failure_keeps_queue_item(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, vectors=FailingDeleteStore())
    env.publish_document()
    document = env.catalog.list_documents()[0]
    env.catalog.delete_document(document.document_id, expected_revision=document.revision)
    with pytest.raises(AppError) as exc_info:
        env.service.cleanup_document(document.document_id)
    assert exc_info.value.code == "QDRANT_UNAVAILABLE"
    assert document.document_id in env.catalog.pending_cleanup()  # 保留队列项，可重试


def test_cleanup_queue_processes_pending_items(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path)
    env.publish_document()
    document = env.catalog.list_documents()[0]
    env.catalog.delete_document(document.document_id, expected_revision=document.revision)
    summary = env.service.run_cleanup_queue()
    assert summary == {"documents": 1, "revisions": 1}
    assert env.catalog.pending_cleanup() == []
    assert env.vectors.count(name=env.base.collection) == 0


def test_ensure_empty_generation_refuses_non_empty_collection(tmp_path: Path) -> None:
    env = IndexHarness(tmp_path, bootstrap=False)
    generation = env.service.ensure_empty_generation(env.base.profile.profile_id)
    assert env.catalog.catalog_state().active_generation_id == generation.generation_id

    # 让"新建 collection 非空"可复现：替换 count 探测，覆盖拒绝分支
    env.vectors.count = lambda **kwargs: 1  # type: ignore[assignment]
    with pytest.raises(AppError) as exc_info:
        env.service.ensure_empty_generation(env.base.profile.profile_id)
    assert exc_info.value.code == "COLLECTION_NOT_EMPTY"
    assert env.catalog.get_generation(generation.generation_id).state == "ready"
    # 失败的空代数不占用当前指针
    assert env.catalog.catalog_state().active_generation_id == generation.generation_id


def test_rebuild_reuses_identical_chunk_set_and_point_ids(tmp_path: Path) -> None:
    from app.services.document_parsing import chunk_policy_fingerprint

    env = IndexHarness(tmp_path)
    env.publish_document()
    revision_id = env.catalog.list_documents()[0].current_revision_id
    chunk_set_before = env.catalog.find_chunk_set(revision_id, chunk_policy_fingerprint())
    assert chunk_set_before is not None

    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-ids"
    )
    assert env.service.run_rebuild(job.jobId).state == "succeeded"
    generation = env.catalog.get_generation(job.targetGenerationId)
    links = env.catalog.list_generation_revisions(generation.generation_id)
    # 同一修订 + 同一策略复用同一不可变分块集（不重写原文、不产生第二套块）
    assert env.catalog.find_chunk_set(revision_id, chunk_policy_fingerprint()).chunk_set_id == (
        chunk_set_before.chunk_set_id
    )
    # 新代内 point id 由 (代, 分块集, ordinal, 文本指纹) 决定：条数与期望一致，可重放
    assert env.vectors.count(name=generation.collection_name) == links[0].expected_chunk_count
    assert len(env.vectors.point_ids(generation.collection_name)) == links[0].expected_chunk_count


# ------------------------------------------------------- v1.1 重建的租约续租


def test_rebuild_renews_lease_at_document_and_batch_boundaries(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock()
    embeddings = FakeEmbeddings()
    embeddings.on_embed = lambda _fake: clock.advance(10.0)
    store = CountingVectorStore()
    env = IndexHarness(tmp_path, vectors=store, embeddings=embeddings, monotonic=clock, batch_size=1)
    published = env.publish_long_document()
    assert published.state == "succeeded"
    assert published.progress.chunksTotal >= 5

    records = _install_lease_spy(monkeypatch, clock=clock)
    started_at = clock.now
    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-lease"
    )
    final = env.service.run_rebuild(job.jobId)
    assert final.state == "succeeded", final.errorMessage

    assert env.service.indexer.leases.renew_seconds <= 20.0
    assert records["renewals"], "长重建没有发生任何续租"
    assert records["renewals"][0] - started_at >= DEFAULT_RENEW_SECONDS
    deltas = [
        round(records["renewals"][index + 1] - records["renewals"][index], 3)
        for index in range(len(records["renewals"]) - 1)
    ]
    assert all(delta <= DEFAULT_RENEW_SECONDS for delta in deltas), deltas
    kinds = [kind for kind, _moment in records["events"]]
    assert kinds[-1] == "checkpoint"
    for index, kind in enumerate(kinds):
        if kind == "renew":
            assert "checkpoint" in kinds[index + 1:], records["events"]


def test_rebuild_lease_renewal_refusal_does_not_touch_target_generation(
    tmp_path: Path, monkeypatch
) -> None:
    """失权（续租被拒）→ 立即停止写入；未完成对账前绝不切换 active_generation_id。"""
    clock = FakeClock()
    embeddings = FakeEmbeddings()
    embeddings.on_embed = lambda _fake: clock.advance(10.0)
    store = CountingVectorStore()
    env = IndexHarness(tmp_path, vectors=store, embeddings=embeddings, monotonic=clock, batch_size=1)
    env.publish_long_document()
    active_before = env.catalog.catalog_state().active_generation_id

    observed: dict = {}
    records = _install_lease_spy(
        monkeypatch,
        clock=clock,
        renew_result=False,
        on_renew=lambda: observed.setdefault("batches", store.upsert_batches),
    )
    job = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-lost-lease"
    )
    final = env.service.run_rebuild(job.jobId)

    assert records["renewals"]
    assert store.upsert_batches == observed["batches"]  # 失权后没有新写入
    assert final.state == "failed"
    assert final.errorCode == "LEASE_LOST"
    state = env.catalog.catalog_state()
    assert state.active_generation_id == active_before  # 旧代继续可用
    assert state.rebuild_job_id is None  # 证明记录仍可写后才释放闸门
    assert env.catalog.get_generation(job.targetGenerationId).state == "aborted"


# ------------------------------------------------- v1.3 模型在场判定（tag 语义）


@pytest.mark.parametrize(
    "profile_name,local_names,expected",
    [
        # 配置 bge-m3 + 本机 bge-m3:latest → 在场（真实浏览器实测的误报场景）
        ("bge-m3", ["bge-m3:latest"], True),
        # 反向：配置 bge-m3:latest + 本机 bge-m3 → 在场
        ("bge-m3:latest", ["bge-m3"], True),
        # 本机只有 bge-m3-large：不得被包含匹配命中
        ("bge-m3", ["bge-m3-large:latest"], False),
        ("bge-m3:latest", ["bge-m3-large"], False),
        # 同 tag 精确命中
        ("bge-m3:latest", ["bge-m3:latest"], True),
        ("bge-m3", ["bge-m3"], True),
        # 不同 tag 不是同一模型
        ("bge-m3:v2", ["bge-m3:latest"], False),
        ("bge-m3:latest", ["bge-m3:v2"], False),
        # 本机完全没有
        ("bge-m3", [], False),
        ("bge-m3:latest", [], False),
        # 多模型在场时只认全等
        ("bge-m3", ["qwen2.5:7b", "bge-m3:latest", "bge-reranker-large"], True),
    ],
)
def test_installed_flag_is_tag_aware(
    tmp_path: Path, profile_name: str, local_names: list[str], expected: bool
) -> None:
    embeddings = FakeEmbeddings(model=profile_name, installed_models=local_names)
    env = IndexHarness(
        tmp_path, embeddings=embeddings, bootstrap=False, model_name=profile_name
    )
    listed = env.service.list_profiles()
    assert len(listed.profiles) == 1
    assert listed.profiles[0].modelName == profile_name
    assert listed.profiles[0].installed is expected


def test_installed_flag_is_false_when_local_service_unreachable(tmp_path: Path) -> None:
    class UnreachableEmbeddings(FakeEmbeddings):
        def list_models(self):
            raise AppError("不可达", code="EMBEDDING_UNAVAILABLE", status_code=503, retryable=True)

    env = IndexHarness(tmp_path, embeddings=UnreachableEmbeddings(), bootstrap=False)
    listed = env.service.list_profiles()
    assert listed.profiles[0].installed is False  # 无法证明在场，不猜


# ------------------------ v1.1 清洗版本：分代词法文本、缓存键与新策略产生新分块集

#: 逼出"整块只有一张图"的文档（图片行前后都是超长段落，块边界落在图片行上）
IMAGE_ONLY_TEXT = (
    "# 第一章 力\n\n"
    + "开头段落。" * 170
    + "\n\n![](images/only.jpg)\n\n"
    + "长段落说明。" * 220
    + "\n\n## 练习 1.1\n\n1. 求并集。\n"
)


def _scope_for(revision, chunk_set_id: str, document) -> "object":
    from app.services.rag_v2.scope import RevisionScope

    return RevisionScope(
        document_id=document.document_id,
        document_revision_id=revision.revision_id,
        metadata_revision_id=document.current_metadata_revision_id,
        chunk_set_id=chunk_set_id,
        owner_id=document.owner_id,
        title=document.title,
        edition_label="人教版 必修一",
        subject_label="数学",
        grade_ids=("senior-1",),
        library_ids=tuple(document.library_ids),
    )


def test_bm25_text_follows_generation_projection_version_and_cache_key(
    tmp_path: Path, monkeypatch
) -> None:
    """BM25 文档文本按**该代登记**的清洗版本投影；缓存键含清洗版本，跨版本不命中。"""
    from app.services.document_parsing import (
        LEGACY_TEXT_PROJECTION_VERSION,
        ChunkPolicy,
        chunk_document,
        chunk_manifest_sha256,
        chunk_policy_fingerprint,
    )
    from app.services.rag_v2 import retrieval as retrieval_module
    from app.services.rag_v2.retrieval import HybridRetriever
    from app.services.textbook_ingest import generation_policy_document

    env = IndexHarness(tmp_path)
    draft = env.base.import_with_metadata(IMAGE_ONLY_TEXT)
    job = env.base.commit_and_run(draft, submission_id="submission-bm25-1")
    assert job.state == "succeeded", job.errorMessage
    revision = env.catalog.get_revision(job.inputRevisionId)
    assert revision is not None
    document = env.catalog.list_documents()[0]
    parsed = env.base.service.indexer.parse_revision(revision)

    new_policy = generation_policy(env.base.generation)
    legacy_policy = ChunkPolicy(text_projection_version=LEGACY_TEXT_PROJECTION_VERSION)
    assert new_policy.text_projection_version == TEXT_PROJECTION_VERSION
    assert legacy_policy.text_projection_version == "raw-v0"
    assert chunk_policy_fingerprint(legacy_policy) != chunk_policy_fingerprint(new_policy)

    # 旧口径分块集：同一修订、同一几何，但多一个"图片独占块"（清洗后为空的那个）
    legacy_chunks = chunk_document(parsed, policy=legacy_policy)
    legacy_set = env.catalog.create_chunk_set(
        revision.revision_id,
        policy_fingerprint=chunk_policy_fingerprint(legacy_policy),
        manifest_sha256=chunk_manifest_sha256(legacy_chunks),
        chunks=legacy_chunks,
    )
    new_link = env.catalog.list_generation_revisions(env.base.generation.generation_id)[0]
    new_chunks = env.catalog.list_chunks(new_link.chunk_set_id)
    assert len(legacy_chunks) == len(new_chunks) + 1  # 新策略不复用旧划分

    # 旧代：一个登记 raw-v0 策略的索引代（模拟 v1.1 之前已发布的代）
    legacy_generation = env.catalog.create_generation(
        profile_id=env.base.profile.profile_id,
        collection_name=new_collection_name(),
        chunk_policy_json=generation_policy_document(legacy_policy, []),
        state="building",
    )
    env.catalog.upsert_generation_revision(
        legacy_generation.generation_id,
        revision.revision_id,
        legacy_set.chunk_set_id,
        state="ready",
        expected_chunk_count=len(legacy_chunks),
        manifest_sha256=legacy_set.manifest_sha256,
    )

    retriever = HybridRetriever(env.catalog, env.vectors, env.embeddings)
    scope_new = (_scope_for(revision, new_link.chunk_set_id, document),)
    scope_legacy = (_scope_for(revision, legacy_set.chunk_set_id, document),)

    index_new = retriever._lexical_index(env.base.generation, scope_new)
    index_legacy = retriever._lexical_index(legacy_generation, scope_legacy)
    assert (retriever.cache_misses, retriever.cache_hits) == (2, 0)
    new_texts = [entry.text for entry in index_new.entries]
    legacy_texts = [entry.text for entry in index_legacy.entries]
    # 新代：图片地址不进入词法文本；旧代：保持登记策略（原样含图片地址）
    assert new_texts and all("images/" not in text for text in new_texts)
    assert any("images/only.jpg" in text for text in legacy_texts)
    assert len(legacy_texts) == len(new_texts) + 1

    # 缓存键含清洗版本：同一代 + 同一范围，只换清洗版本也必须重建（不命中同一缓存）
    # 用旧口径分块集作为范围：它含"清洗后为空"的图片独占块，差异最直观
    monkeypatch.setattr(
        retrieval_module,
        "generation_policy",
        lambda generation: legacy_policy,
    )
    swapped = retriever._lexical_index(env.base.generation, scope_legacy)
    monkeypatch.undo()
    assert retriever.cache_misses == 3 and retriever.cache_hits == 0
    assert any("images/only.jpg" in entry.text for entry in swapped.entries)
    # 同一批块在登记策略（rag-readable-v1）下投影：图片独占块清洗后为空 → 正是被清单排除的原因
    image_chunk = next(
        chunk
        for chunk in env.catalog.list_chunks(legacy_set.chunk_set_id)
        if "images/only.jpg" in parsed.normalized_text[chunk.char_start:chunk.char_end]
    )
    from app.services.document_parsing import chunk_projection

    assert chunk_projection(image_chunk, parsed.normalized_text, new_policy).text.strip() == ""
    assert new_chunks and not any(
        "images/only.jpg" in parsed.normalized_text[chunk.char_start:chunk.char_end]
        for chunk in new_chunks
    )

    # 恢复原策略后，原键仍命中缓存（同输入同索引）
    again = retriever._lexical_index(env.base.generation, scope_new)
    assert again is index_new and retriever.cache_hits == 1


def test_new_projection_policy_rebuild_keeps_old_generation_untouched(tmp_path: Path) -> None:
    """旧代按 raw-v0 建（含图片块），新策略重建后：新代新分块集，旧代与其 collection 不改写。"""
    from app.services.document_parsing import (
        LEGACY_TEXT_PROJECTION_VERSION,
        ChunkPolicy,
    )
    from app.services.rag_v2.retrieval import HybridRetriever
    from app.services.textbook_ingest import generation_policy_document

    env = IndexHarness(tmp_path, bootstrap=False)
    legacy_policy = ChunkPolicy(text_projection_version=LEGACY_TEXT_PROJECTION_VERSION)
    old_generation = env.catalog.create_generation(
        profile_id=env.base.profile.profile_id,
        collection_name=new_collection_name(),
        chunk_policy_json=generation_policy_document(legacy_policy, []),
        state="building",
    )
    env.vectors.ensure_collection(
        name=old_generation.collection_name, dimensions=4, distance="Cosine"
    )
    env.catalog.publish_generation(old_generation.generation_id)
    env.catalog.set_active_generation(old_generation.generation_id)
    env.base.generation = old_generation
    env.base.collection = old_generation.collection_name

    # 入库走旧代登记策略（raw-v0）：图片独占块保留在清单与向量里
    draft = env.base.import_with_metadata(IMAGE_ONLY_TEXT)
    job = env.base.commit_and_run(draft, submission_id="submission-legacy-1")
    assert job.state == "succeeded", job.errorMessage
    revision = env.catalog.get_revision(job.inputRevisionId)
    assert revision is not None
    parsed = env.base.service.indexer.parse_revision(revision)
    old_link = env.catalog.list_generation_revisions(old_generation.generation_id)[0]
    old_chunks = env.catalog.list_chunks(old_link.chunk_set_id)
    old_points = env.vectors.point_ids(old_generation.collection_name)
    # 旧口径保留图片独占块：清单与向量里都有它
    assert any(
        "images/only.jpg" in parsed.normalized_text[chunk.char_start:chunk.char_end]
        for chunk in old_chunks
    )
    old_payloads = env.vectors.payloads(old_generation.collection_name)
    assert old_payloads and all(
        payload["textProjectionVersion"] == LEGACY_TEXT_PROJECTION_VERSION
        for payload in old_payloads
    )

    # 同模型、新清洗策略重建：新代必须产生新分块集与自己的 collection
    rebuild = env.service.begin_rebuild(
        profile_id=env.base.profile.profile_id, submission_id="submission-rebuild-clean"
    )
    generation = env.catalog.get_generation(rebuild.targetGenerationId)
    assert generation_policy(generation).text_projection_version == TEXT_PROJECTION_VERSION
    assert env.service.run_rebuild(rebuild.jobId).state == "succeeded"
    assert env.catalog.catalog_state().active_generation_id == generation.generation_id

    new_link = env.catalog.list_generation_revisions(generation.generation_id)[0]
    assert new_link.state == "ready"
    new_chunk_set = env.catalog.get_chunk_set(new_link.chunk_set_id)
    assert new_chunk_set is not None
    assert new_chunk_set.chunk_set_id != old_link.chunk_set_id  # 不复用旧划分
    assert new_chunk_set.manifest_sha256 == new_link.manifest_sha256
    new_chunks = env.catalog.list_chunks(new_link.chunk_set_id)
    assert new_chunk_set.chunk_count == new_link.expected_chunk_count == len(new_chunks)
    assert len(new_chunks) == len(old_chunks) - 1  # 图片独占块在新代被排除
    assert env.vectors.count(name=generation.collection_name) == new_link.expected_chunk_count
    new_payloads = env.vectors.payloads(generation.collection_name)
    assert new_payloads and all(
        payload["textProjectionVersion"] == TEXT_PROJECTION_VERSION for payload in new_payloads
    )
    for payload in new_payloads:
        assert isinstance(payload["indexTextSha256"], str)
        assert len(payload["indexTextSha256"]) == 64
        assert payload["text_sha256"]  # 原文切片散列仍在，含义不变

    # 旧代：状态、分块集、collection 与点集一字不改（不就地改写旧 collection）
    assert env.catalog.get_generation(old_generation.generation_id).state == "ready"
    assert (
        env.catalog.list_generation_revisions(old_generation.generation_id)[0].chunk_set_id
        == old_link.chunk_set_id
    )
    assert env.vectors.point_ids(old_generation.collection_name) == old_points
    assert env.vectors.payloads(old_generation.collection_name) == old_payloads

    # 两个代各自按登记策略产出词法文本：新代不含图片地址，旧代保留
    document = env.catalog.list_documents()[0]
    retriever = HybridRetriever(env.catalog, env.vectors, env.embeddings)
    index_old = retriever._lexical_index(
        old_generation, (_scope_for(revision, old_link.chunk_set_id, document),)
    )
    index_new = retriever._lexical_index(
        generation, (_scope_for(revision, new_link.chunk_set_id, document),)
    )
    assert any("images/only.jpg" in entry.text for entry in index_old.entries)
    assert all("images/" not in entry.text for entry in index_new.entries)
    assert len(index_old.entries) == len(index_new.entries) + 1
    assert parsed.normalized_text  # 原文一字未改，仍可读


# ---------------- B2 修复 v1.1（1）：分词全空语料不得让检索直接崩

def _activate_generation_with_policy(env: IndexHarness, policy):
    """把自定义分块策略的代设为活动代（用于精确控制"分词为空"的块）。"""
    from app.services.textbook_ingest import generation_policy_document

    generation = env.catalog.create_generation(
        profile_id=env.base.profile.profile_id,
        collection_name=new_collection_name(),
        chunk_policy_json=generation_policy_document(policy, []),
        state="building",
    )
    env.vectors.ensure_collection(
        name=generation.collection_name, dimensions=4, distance="Cosine"
    )
    env.catalog.publish_generation(generation.generation_id)
    env.catalog.set_active_generation(generation.generation_id)
    env.base.generation = generation
    env.base.collection = generation.collection_name
    return generation


def test_all_empty_token_corpus_does_not_crash_retrieval(tmp_path: Path) -> None:
    """单块纯符号语料（分词为空）：不构造 BM25、不抛异常，向量侧结果照常融合返回。"""
    from app.services.document_parsing import ChunkPolicy
    from app.services.rag_v2.retrieval import HybridRetriever, tokenize

    env = IndexHarness(tmp_path)
    policy = ChunkPolicy(target_chars=12, max_chars=24, overlap_chars=0)
    generation = _activate_generation_with_policy(env, policy)
    draft = env.base.import_with_metadata("…" * 40, file_name="symbols.md")
    job = env.base.commit_and_run(draft, submission_id="submission-empty-token-1")
    assert job.state == "succeeded", job.errorMessage
    revision = env.catalog.get_revision(job.inputRevisionId)
    assert revision is not None
    parsed = env.base.service.indexer.parse_revision(revision)
    document = env.catalog.list_documents()[0]
    link = env.catalog.list_generation_revisions(generation.generation_id)[0]
    chunks = env.catalog.list_chunks(link.chunk_set_id)
    assert chunks  # 有块（不是"没有文本"）：只是每块分词都为空
    assert all(
        tokenize(parsed.normalized_text[chunk.char_start:chunk.char_end]) == []
        for chunk in chunks
    )

    retriever = HybridRetriever(env.catalog, env.vectors, env.embeddings)
    scope = (_scope_for(revision, link.chunk_set_id, document),)
    # 构造期不崩：可索引条目为空 → 不构造 BM25
    index = retriever._lexical_index(generation, scope)
    assert index.entries == [] and index.bm25 is None
    assert retriever._lexical(generation, scope, "集合的表示方法") == []

    candidates = retriever.retrieve(
        question="集合的表示方法",
        scope=scope,
        profile=env.base.profile,
        generation=generation,
    )
    # 词法为空不影响向量侧与 RRF：稠密结果照常返回，不判定为整体不可用
    assert candidates
    assert all(item.dense_rank is not None and item.lexical_rank is None for item in candidates)
    assert candidates[0].dense_rank == 1
    assert candidates[0].fused_score == pytest.approx(1.0 / (retriever.rrf_k + 1))


def test_mixed_empty_token_corpus_keeps_lexical_mapping_aligned(tmp_path: Path) -> None:
    """混合语料（一块分词为空 + 若干正常块）：正常块仍可命中，且序号映射不错位。"""
    from rank_bm25 import BM25Okapi

    from app.services.document_parsing import ChunkPolicy
    from app.services.rag_v2.retrieval import HybridRetriever, tokenize

    env = IndexHarness(tmp_path)
    policy = ChunkPolicy(target_chars=12, max_chars=24, overlap_chars=0)
    generation = _activate_generation_with_policy(env, policy)
    text = (
        "# 第一章 集合与常用逻辑用语\n\n"
        + "…" * 20
        + "\n\n"
        + "集合的表示方法。" * 3
        + "\n\n"
        + "集合的表示。\n"
    )
    draft = env.base.import_with_metadata(text, file_name="mixed.md")
    job = env.base.commit_and_run(draft, submission_id="submission-empty-token-2")
    assert job.state == "succeeded", job.errorMessage
    revision = env.catalog.get_revision(job.inputRevisionId)
    assert revision is not None
    parsed = env.base.service.indexer.parse_revision(revision)
    document = env.catalog.list_documents()[0]
    link = env.catalog.list_generation_revisions(generation.generation_id)[0]
    chunks = env.catalog.list_chunks(link.chunk_set_id)
    empty_ordinals = [
        chunk.ordinal
        for chunk in chunks
        if tokenize(parsed.normalized_text[chunk.char_start:chunk.char_end]) == []
    ]
    assert empty_ordinals == [1]  # 样本里恰好一个"分词为空"的块

    retriever = HybridRetriever(env.catalog, env.vectors, env.embeddings)
    scope = (_scope_for(revision, link.chunk_set_id, document),)
    index = retriever._lexical_index(generation, scope)
    # 过滤后序号与 _LexicalEntry 重新对齐：条目 = 块表去掉空词元块，顺序不变
    assert [(entry.chunk_set_id, entry.ordinal) for entry in index.entries] == [
        (link.chunk_set_id, chunk.ordinal)
        for chunk in chunks
        if chunk.ordinal not in set(empty_ordinals)
    ]
    assert index.bm25 is not None and index.bm25.corpus_size == len(index.entries)

    question = "集合的表示方法"
    query_tokens = set(tokenize(question))
    # 独立 BM25（同一份已过滤语料）给出期望命中与名次：与检索器逐一比对，错位必然暴露
    independent = BM25Okapi([tokenize(entry.text) for entry in index.entries])
    independent_scores = independent.get_scores(tokenize(question))
    expected_hits = [
        (entry.chunk_set_id, entry.ordinal)
        for entry, score in sorted(
            zip(index.entries, independent_scores),
            key=lambda pair: (-float(pair[1]), pair[0].chunk_set_id, pair[0].ordinal),
        )
        if entry.tokens & query_tokens
    ][: retriever.lexical_limit]
    hits = retriever._lexical(generation, scope, question)
    assert hits == expected_hits
    assert hits  # 正常块仍可被词法命中
    assert empty_ordinals[0] not in [ordinal for _chunk_set, ordinal in hits]


# ---------------- B2 修复 v1.1（2）：chunk_count 兜底必须找得到旧口径分块集

def test_chunk_count_falls_back_to_latest_sealed_chunk_set(tmp_path: Path) -> None:
    """无代链接的修订：块数取该修订下最新已封存分块集，不再按指纹猜成 0。"""
    from app.services.document_parsing import (
        LEGACY_TEXT_PROJECTION_VERSION,
        ChunkPolicy,
        chunk_document,
        chunk_manifest_sha256,
        chunk_policy_fingerprint,
    )
    from app.services.textbook_ingest.views import ViewContext, latest_sealed_chunk_count

    env = IndexHarness(tmp_path)
    draft = env.base.import_with_metadata(sample_text())
    job = env.base.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-chunk-count-1",
        library_ids=[env.base.library.library_id],
    )
    revision = env.catalog.get_revision(job.inputRevisionId)
    assert revision is not None
    parsed = env.base.service.indexer.parse_revision(revision)
    # 该修订只有旧口径分块集，且没有任何索引代链接（模拟历史/中断产物）
    legacy = ChunkPolicy(text_projection_version=LEGACY_TEXT_PROJECTION_VERSION)
    legacy_chunks = chunk_document(parsed, policy=legacy)
    legacy_set = env.catalog.create_chunk_set(
        revision.revision_id,
        policy_fingerprint=chunk_policy_fingerprint(legacy),
        manifest_sha256=chunk_manifest_sha256(legacy_chunks),
        chunks=legacy_chunks,
    )
    assert env.catalog.list_generation_revisions(env.base.generation.generation_id) == []
    assert legacy_set.policy_fingerprint != chunk_policy_fingerprint()

    views = ViewContext(env.catalog)
    assert views.chunk_count(revision.revision_id) == legacy_set.chunk_count == len(legacy_chunks) > 0
    assert latest_sealed_chunk_count(env.catalog, revision.revision_id) == len(legacy_chunks)
    # 更晚写入的分块集（新策略）优先：兜底取"最新"
    new_chunks = chunk_document(parsed, policy=ChunkPolicy())
    new_set = env.catalog.create_chunk_set(
        revision.revision_id,
        policy_fingerprint=chunk_policy_fingerprint(ChunkPolicy()),
        manifest_sha256=chunk_manifest_sha256(new_chunks),
        chunks=new_chunks,
    )
    assert views.chunk_count(revision.revision_id) == new_set.chunk_count
    # 完全没有分块集的修订才显示 0
    assert views.chunk_count("no-such-revision") == 0
