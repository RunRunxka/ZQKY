"""索引代：状态、配置探测、重建闸门与发布、失败回退、删除跳过与清理。

复用入库测试的替身（内存向量库 + 假 Embedding + tmp_path 目录），不连接真实 Qdrant/Ollama。
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.repositories.vector_store import AllowedFilter, InMemoryVectorStore
from app.services.textbook_ingest import DEFAULT_RENEW_SECONDS, generation_manifest
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
