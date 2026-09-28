"""入库流水线：草稿、封存、提交、批次写入、发布、失败/取消/重试与崩溃恢复。

全部使用内存向量库与假 Embedding；SQLite 与文件都在 pytest ``tmp_path`` 内，不触碰正式 .local-data。
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.sqlite import connect as sqlite_connect
from app.providers.embeddings.fingerprint import embedding_fingerprint
from app.providers.embeddings.ollama_embedding import model_names_match
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import ImportRecord
from app.repositories.vector_store import AllowedFilter, InMemoryVectorStore, VectorPoint
from app.schemas.textbook import ChunkPreview, EmbeddingModelCandidate
from app.services.document_parsing import (
    DEFAULT_CHUNK_POLICY,
    DEGRADED_WARNING_PREFIX,
    LEGACY_REGION_RULES_VERSION,
    chunk_document,
    chunk_manifest_sha256,
    chunk_policy_fingerprint,
    chunk_policy_from_json,
    parse_document,
)
from app.services.textbook_ingest import (
    DEFAULT_RENEW_SECONDS,
    ORIGIN_REUSE_WARNING,
    IngestService,
    generation_policy_document,
    new_collection_name,
    origin_key_for,
)

DIMENSIONS = 4
MODEL = "bge-m3"
DIGEST = "digest-1"
METADATA = {
    "title": "高中数学必修第一册",
    "stageId": "senior",
    "gradeIds": ["senior-1"],
    "subjectId": "math",
    "editionId": "renjiao-a",
    "publicationLabel": "2019版",
    "volumeLabel": "必修第一册",
}


class FakeClock:
    """单调时钟替身：测试只推进它，不做真实等待。"""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class CountingVectorStore(InMemoryVectorStore):
    """记录 upsert 调用次数与写入点数，用于断言"失权后不再写向量"。"""

    def __init__(self) -> None:
        super().__init__()
        self.upsert_batches = 0
        self.upsert_points = 0

    def upsert(self, *, name: str, points: list[VectorPoint], wait: bool = True) -> None:
        self.upsert_batches += 1
        self.upsert_points += len(points)
        super().upsert(name=name, points=points, wait=wait)


def long_text(*, paragraphs: int = 12, repeats: int = 175) -> str:
    """构造约 10 个块的正文：每段 ~500 码点，便于观察到多次批次边界。"""
    body = "\n\n".join("正文说明。" * repeats for _ in range(paragraphs))
    return f"# 第一章 集合\n\n{body}\n\n## 练习 1.1\n\n1. 求并集。\n"


class FakeEmbeddings:
    def __init__(
        self,
        *,
        dimensions: int = DIMENSIONS,
        digest: str = DIGEST,
        model: str = MODEL,
        installed_models: list[str] | None = None,
    ):
        self.dimensions = dimensions
        self.digest = digest
        self.model_name = model
        #: ``None`` = 只暴露自身 model_name；列表 = 覆盖本机在场模型名（测试 tag 归一）
        self.installed_models = installed_models
        self.embed_calls = 0
        self.fail_next = 0
        self.fail_code = "EMBEDDING_UNAVAILABLE"
        self.on_embed = None

    def manifest_digest(self, model: str) -> str:
        # 与真实 Provider 同语义：tag 归一后比较（bge-m3 == bge-m3:latest）
        if not model_names_match(model, self.model_name):
            raise AppError("模型不存在。", code="EMBEDDING_MODEL_MISSING", status_code=404)
        return self.digest

    def list_models(self):
        names = (
            self.installed_models
            if self.installed_models is not None
            else [self.model_name]
        )
        return [
            EmbeddingModelCandidate(
                name=name,
                digest=self.digest,
                sizeBytes=1,
                family="bert",
                parameterSize="567M",
                isEmbeddingCapable=True,
            )
            for name in names
        ]

    def verify_embedding_candidate(self, *, model_name: str, sample_texts=None):
        from app.providers.embeddings.ollama_embedding import EmbeddingProbeResult

        if not model_names_match(model_name, self.model_name):
            raise AppError("模型不存在。", code="EMBEDDING_MODEL_MISSING", status_code=404)
        return EmbeddingProbeResult(
            model_name=model_name,
            model_manifest_digest=self.digest,
            dimensions=self.dimensions,
            sample_count=2,
            non_zero=True,
            finite=True,
            stable_digest=True,
            family="bert",
            parameter_size="567M",
        )

    def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        if self.on_embed is not None:
            self.on_embed(self)
        if self.fail_next > 0:
            self.fail_next -= 1
            raise AppError(
                "本地 Embedding 服务暂不可用。",
                code=self.fail_code,
                status_code=503,
                retryable=True,
            )
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([1.0 + digest[index] / 255.0 for index in range(self.dimensions)])
        return vectors


def _parser(*, path, file_name, parser_version, allow_empty_text=False):
    return parse_document(
        path=path,
        file_name=file_name,
        parser_version=parser_version,
        allow_empty_text=allow_empty_text,
    )


class Harness:
    def __init__(
        self,
        tmp_path: Path,
        *,
        chunker=chunk_document,
        batch_size: int = 8,
        vectors=None,
        embeddings=None,
        bootstrap: bool = True,
        monotonic=None,
        renew_seconds: float = DEFAULT_RENEW_SECONDS,
        lease_seconds: int = 90,
        model_name: str = MODEL,
    ) -> None:
        self.settings = Settings(
            host="127.0.0.1",
            port=8001,
            allowed_origins=frozenset(),
            env="test",
            data_dir=tmp_path / "data",
        )
        self.catalog = TextbookCatalog(self.settings.textbooks_root / "catalog.sqlite3")
        self.catalog.migrate()
        self.vectors = vectors if vectors is not None else InMemoryVectorStore()
        self.embeddings = embeddings if embeddings is not None else FakeEmbeddings()
        self.monotonic = monotonic
        self.renew_seconds = renew_seconds
        self.lease_seconds = lease_seconds
        self.service = IngestService(
            self.catalog,
            _parser,
            chunker,
            self.embeddings,
            self.vectors,
            self.settings,
            batch_size=batch_size,
            sleep=lambda _seconds: None,
            lease_seconds=lease_seconds,
            renew_seconds=renew_seconds,
            monotonic=monotonic or time.monotonic,
        )
        self.profile = self.catalog.create_embedding_profile(
            fingerprint=embedding_fingerprint(
                model_manifest_digest=DIGEST,
                dimensions=DIMENSIONS,
                query_prefix="",
                document_prefix="",
                normalization="none",
            ),
            adapter="ollama",
            native_base_url="http://127.0.0.1:11434",
            model_name=model_name,
            model_manifest_digest=DIGEST,
            dimensions=DIMENSIONS,
            distance="cosine",
            query_prefix="",
            document_prefix="",
            normalization="none",
        )
        self.collection = new_collection_name()
        self.generation = None
        if bootstrap:
            self.generation = self.catalog.create_generation(
                profile_id=self.profile.profile_id,
                collection_name=self.collection,
                chunk_policy_json=generation_policy_document(DEFAULT_CHUNK_POLICY, []),
                state="building",
            )
            self.vectors.ensure_collection(
                name=self.collection, dimensions=DIMENSIONS, distance="Cosine"
            )
            self.catalog.publish_generation(self.generation.generation_id)
            self.catalog.set_active_generation(self.generation.generation_id)
        self.library = self.catalog.create_library(
            kind="base",
            owner_id="system",
            display_name="基础库·数学",
            grade_id="senior-1",
            subject_id="math",
            edition_id="renjiao-a",
        )

    # ------------------------------------------------------------------ 便捷方法

    def draft(self, text: str, *, file_name: str = "chapter.md", metadata=None, **kwargs):
        payload = text.encode("utf-8")
        return self.service.create_import(
            file_name=file_name, data=payload, metadata=metadata, **kwargs
        )

    def import_with_metadata(self, text: str, *, file_name: str = "chapter.md", metadata=None):
        draft = self.draft(text, file_name=file_name)
        draft = self.service.update_import_metadata(
            draft.importId, expected_revision=draft.revision, metadata=metadata or METADATA
        )
        return draft

    def commit_and_run(self, draft, *, submission_id: str = "submission-0001"):
        job = self.service.commit_import(
            draft.importId,
            expected_revision=draft.revision,
            submission_id=submission_id,
            library_ids=[self.library.library_id],
        )
        return self.service.run_ingest_job(job.jobId)


def sample_text(title: str = "集合", sentences: int = 40) -> str:
    body = "".join(f"第{index}句说明文字。{title}的表示方法如下。" for index in range(sentences))
    return f"# 第一章 {title}\n\n{body}\n\n## 练习 1.1\n\n1. 求并集。\n"


@pytest.fixture()
def env(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


# ------------------------------------------------------------------------ 草稿


def test_import_draft_preview_and_can_commit(env: Harness) -> None:
    draft = env.draft(sample_text(), metadata=METADATA)
    assert draft.state == "needs_review"
    assert draft.metadata is not None and draft.metadata.title == METADATA["title"]
    assert draft.metadataConfirmed is True
    assert draft.canCommit is True
    assert draft.parsed is not None
    assert draft.parsed.chunkCount == len(draft.parsed.preview) or draft.parsed.chunkCount >= 1
    assert draft.parsed.charCount > 0
    assert draft.parsed.needsOcr is False
    assert draft.parsed.sourceKind == "markdown"
    assert all(item.region in ("body", "exercise") for item in draft.parsed.preview)
    assert draft.parsed.bodyChunkCount + draft.parsed.exerciseChunkCount == draft.parsed.chunkCount
    # 预览文本与规范化文本区间一致
    preview: ChunkPreview = draft.parsed.preview[0]
    assert preview.text
    assert preview.charEnd > preview.charStart


def test_import_without_metadata_needs_review(env: Harness) -> None:
    draft = env.draft(sample_text())
    assert draft.canCommit is False
    assert draft.metadata is None
    assert draft.warnings == []
    with pytest.raises(AppError) as exc_info:
        env.service.commit_import(
            draft.importId,
            expected_revision=draft.revision,
            submission_id="submission-0002",
            library_ids=[env.library.library_id],
        )
    assert exc_info.value.code == "METADATA_NOT_CONFIRMED"


def test_patch_import_metadata_and_revision_conflict(env: Harness) -> None:
    draft = env.draft(sample_text())
    updated = env.service.update_import_metadata(
        draft.importId, expected_revision=draft.revision, metadata=METADATA
    )
    assert updated.revision == draft.revision + 1
    assert updated.canCommit is True
    with pytest.raises(AppError) as exc_info:
        env.service.update_import_metadata(
            draft.importId, expected_revision=draft.revision, metadata=METADATA
        )
    assert (exc_info.value.code, exc_info.value.status_code) == ("REVISION_CONFLICT", 409)


def test_unsupported_suffix_and_oversize_are_rejected(env: Harness) -> None:
    with pytest.raises(AppError) as suffix_error:
        env.service.create_import(file_name="book.epub", data=b"x")
    assert suffix_error.value.code == "UNSUPPORTED_DOCUMENT_FORMAT"
    # 上传暂存区不残留被拒绝的文件
    assert list((env.settings.textbooks_root / "staging").glob("*")) == []


def test_needs_ocr_draft_is_marked_and_commit_rejected(env: Harness, tmp_path: Path) -> None:
    from tests.test_document_parsing import _build_pdf

    pdf = _build_pdf([""], with_text_stream=False)
    draft = env.service.create_import(file_name="scan.pdf", data=pdf)
    assert draft.state == "needs_review"
    assert draft.parsed is not None and draft.parsed.needsOcr is True
    assert draft.parsed.charCount == 0
    assert draft.canCommit is False
    assert any("OCR" in warning or "文本层" in warning for warning in draft.warnings)
    draft = env.service.update_import_metadata(
        draft.importId, expected_revision=draft.revision, metadata=METADATA
    )
    with pytest.raises(AppError) as exc_info:
        env.service.commit_import(
            draft.importId,
            expected_revision=draft.revision,
            submission_id="submission-ocr1",
            library_ids=[env.library.library_id],
        )
    assert (exc_info.value.code, exc_info.value.status_code) == ("DOCUMENT_NEEDS_OCR", 422)
    # 不生成空索引：没有任何 job 与索引代修订
    assert env.catalog.list_jobs() == []
    assert env.catalog.list_generation_revisions(env.generation.generation_id) == []


def test_warnings_require_acknowledgement(env: Harness) -> None:
    from tests.test_document_parsing import _build_pdf

    # 两页中一页没有文本层 → 解析警告（不是 needs_ocr）
    pdf = _build_pdf(["Page with text", ""])
    draft = env.service.create_import(file_name="mixed.pdf", data=pdf, metadata=METADATA)
    assert draft.parsed is not None and draft.parsed.needsOcr is False
    assert draft.warnings
    assert draft.canCommit is True
    with pytest.raises(AppError) as exc_info:
        env.service.commit_import(
            draft.importId,
            expected_revision=draft.revision,
            submission_id="submission-warn1",
            library_ids=[env.library.library_id],
        )
    assert exc_info.value.code == "WARNINGS_NOT_ACKNOWLEDGED"
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-warn1",
        library_ids=[env.library.library_id],
        acknowledge_warnings=True,
    )
    assert job.state == "queued"


# --------------------------------------------------------------------- 正常发布


def test_publish_pipeline_marks_ready_and_publishes_document(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text())
    job = env.commit_and_run(draft)
    assert job.state == "succeeded", job.errorMessage
    assert job.progress.chunksDone == job.progress.chunksTotal

    documents = env.catalog.list_documents()
    assert len(documents) == 1
    document = documents[0]
    assert document.current_revision_id == job.inputRevisionId
    # 只有基础库（owner=system）：书册归属由服务端推导为 system，范围解析才能匹配
    assert document.owner_id == "system"
    assert document.library_ids == (env.library.library_id,)

    revision = env.catalog.get_revision(document.current_revision_id)
    assert revision is not None
    assert revision.normalized_text_sha256 == revision.normalized_blob_id
    assert revision.parser_version == "zqky-parse-v1"
    assert revision.char_count > 0

    links = env.catalog.list_generation_revisions(env.generation.generation_id)
    assert len(links) == 1
    assert links[0].state == "ready"
    assert links[0].expected_chunk_count > 0

    count = env.vectors.count(
        name=env.collection,
        allowed=AllowedFilter(
            revision_ids=(revision.revision_id,), chunk_set_ids=(links[0].chunk_set_id,)
        ),
    )
    assert count == links[0].expected_chunk_count

    payload = env.vectors.payloads(env.collection)[0]
    assert payload["generation_id"] == env.generation.generation_id
    assert payload["chunk_set_id"] == links[0].chunk_set_id
    assert payload["document_revision_id"] == revision.revision_id
    assert payload["owner_id"] == "system"
    assert payload["region"] in ("body", "exercise")

    # 草稿状态推进到 ready；blobs 与 normalized 均封存
    assert env.service.get_import_view(draft.importId).state == "ready"
    assert (env.settings.textbooks_root / "blobs" / revision.original_blob_id).is_file()
    assert (env.settings.textbooks_root / "normalized" / revision.normalized_blob_id).is_file()


def test_document_owner_follows_selected_library_kind(env: Harness) -> None:
    personal = env.catalog.create_library(
        kind="personal",
        owner_id="local-user",
        display_name="我的教材",
        grade_id="senior-1",
        subject_id="math",
        edition_id="renjiao-a",
    )
    draft = env.import_with_metadata(sample_text())
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-owner-1",
        library_ids=[personal.library_id],
    )
    assert env.service.run_ingest_job(job.jobId).state == "succeeded"
    document = env.catalog.list_documents()[0]
    assert document.owner_id == "local-user"  # 个人库 → 本机用户
    # 范围解析可用（书册 owner 与逻辑库 owner 一致）
    from app.schemas.textbook import TextbookSelection

    resolved = env.catalog.resolve_selection(
        TextbookSelection(
            gradeId="senior-1",
            subjectId="math",
            editionId="renjiao-a",
            documentIds=[document.document_id],
        )
    )
    assert resolved[0].document_revision_id == job.inputRevisionId


def test_commit_is_idempotent_per_submission_id(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text())
    first = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-same-1",
        library_ids=[env.library.library_id],
    )
    replay = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-same-1",
        library_ids=[env.library.library_id],
    )
    assert replay.jobId == first.jobId

    with pytest.raises(AppError) as exc_info:
        env.service.commit_import(
            draft.importId,
            expected_revision=draft.revision,
            submission_id="submission-same-1",
            library_ids=[],
        )
    assert exc_info.value.code == "INVALID_REQUEST"  # 空库列表在更早的校验里失败

    other = env.catalog.create_library(
        kind="personal",
        owner_id="local-user",
        display_name="我的教材",
        grade_id="senior-1",
        subject_id="math",
        edition_id="renjiao-a",
    )
    with pytest.raises(AppError) as conflict:
        env.service.commit_import(
            draft.importId,
            expected_revision=draft.revision,
            submission_id="submission-same-1",
            library_ids=[other.library_id],
        )
    assert (conflict.value.code, conflict.value.status_code) == ("IDEMPOTENCY_CONFLICT", 409)


def test_update_mode_publishes_new_revision_and_keeps_old(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text("集合"))
    job = env.commit_and_run(draft, submission_id="submission-v1")
    document = env.catalog.list_documents()[0]
    old_revision_id = document.current_revision_id
    old_count = env.vectors.count(name=env.collection, allowed=AllowedFilter(revision_ids=(old_revision_id,)))

    update = env.service.create_import(
        file_name="chapter-v2.md",
        data=sample_text("集合的运算").encode("utf-8"),
        target_document_id=document.document_id,
        expected_current_revision_id=old_revision_id,
    )
    assert update.targetDocumentId == document.document_id
    assert update.metadata is not None  # 目标书册元数据预填并确认
    assert update.metadataConfirmed is True
    job2 = env.commit_and_run(update, submission_id="submission-v2")
    assert job2.state == "succeeded", job2.errorMessage

    updated = env.catalog.get_document(document.document_id)
    assert updated.current_revision_id != old_revision_id
    assert env.catalog.get_revision(old_revision_id) is not None  # 旧修订保留可读
    assert old_count > 0
    assert env.vectors.count(
        name=env.collection, allowed=AllowedFilter(revision_ids=(updated.current_revision_id,))
    ) > 0
    # 旧修订在新代内仍是 ready（历史引用可解释），但文档当前修订已切换
    links = {
        link.document_revision_id: link.state
        for link in env.catalog.list_generation_revisions(env.generation.generation_id)
    }
    assert links[old_revision_id] == "ready"
    assert links[updated.current_revision_id] == "ready"
    assert updated.current_revision_id in links


# --------------------------------------------------------------- 失败 / 取消 / 重试


def test_embedding_failure_keeps_old_revision_unpublished(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text("集合"))
    env.commit_and_run(draft, submission_id="submission-ok1")
    document = env.catalog.list_documents()[0]
    published_revision = document.current_revision_id

    env.embeddings.fail_next = 100
    update = env.service.create_import(
        file_name="chapter-bad.md",
        data=sample_text("集合的运算").encode("utf-8"),
        target_document_id=document.document_id,
        expected_current_revision_id=published_revision,
    )
    job = env.commit_and_run(update, submission_id="submission-bad1")
    assert job.state == "failed"
    assert job.errorCode == "EMBEDDING_UNAVAILABLE"
    assert job.retryable is True

    after = env.catalog.get_document(document.document_id)
    assert after.current_revision_id == published_revision  # 旧修订不变
    links = {
        link.document_revision_id: link.state
        for link in env.catalog.list_generation_revisions(env.generation.generation_id)
    }
    assert links[published_revision] == "ready"
    assert links[job.inputRevisionId] == "pending"  # 新修订停在 pending，不可检索
    assert env.service.get_import_view(update.importId).state == "failed"


def test_model_digest_change_is_not_retried(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text())
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-digest-1",
        library_ids=[env.library.library_id],
    )
    env.embeddings.digest = "digest-2"  # 同名 tag 的清单变化 = 换模型
    failed = env.service.run_ingest_job(job.jobId)
    assert failed.state == "failed"
    assert failed.errorCode == "EMBEDDING_MODEL_CHANGED"
    assert env.catalog.get_document(env.catalog.list_documents()[0].document_id).current_revision_id is None


def test_cancel_queued_job_is_immediate(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text())
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-cancel-1",
        library_ids=[env.library.library_id],
    )
    cancelled = env.service.cancel_job(job.jobId)
    assert cancelled.state == "cancelled"
    assert env.vectors.count(name=env.collection) == 0
    assert env.service.get_import_view(draft.importId).state == "cancelled"
    # 再运行时不会复活
    again = env.service.run_ingest_job(job.jobId)
    assert again.state == "cancelled"


def test_cancel_running_job_is_honoured_at_next_checkpoint(env: Harness, tmp_path: Path) -> None:
    temp = Harness(tmp_path / "slow", batch_size=1)
    draft = temp.import_with_metadata(sample_text(sentences=30))
    job = temp.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-cancel-2",
        library_ids=[temp.library.library_id],
    )
    state = {"requested": False}

    def on_embed(_fake) -> None:
        if not state["requested"]:
            state["requested"] = True
            temp.service.cancel_job(job.jobId)

    temp.embeddings.on_embed = on_embed
    final = temp.service.run_ingest_job(job.jobId)
    assert final.state == "cancelled"
    assert final.errorCode == "JOB_CANCELLED"
    documents = temp.catalog.list_documents()
    assert documents and documents[0].current_revision_id is None  # 旧索引仍可用：从未发布新修订
    assert temp.service.get_import_view(draft.importId).state == "cancelled"
    links = temp.catalog.list_generation_revisions(temp.generation.generation_id)
    assert all(link.state != "ready" for link in links)


def test_retry_after_failure_creates_new_job_and_succeeds(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text())
    env.embeddings.fail_next = 100
    job = env.commit_and_run(draft, submission_id="submission-retry-1")
    assert job.state == "failed"
    env.embeddings.fail_next = 0
    retried = env.service.retry_job(job.jobId)
    assert retried.jobId != job.jobId
    assert retried.state == "queued"
    final = env.service.run_ingest_job(retried.jobId)
    assert final.state == "succeeded", final.errorMessage
    assert env.catalog.list_documents()[0].current_revision_id == final.inputRevisionId


def test_crash_before_checkpoint_does_not_duplicate_vectors(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text())
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-crash-1",
        library_ids=[env.library.library_id],
    )
    original_checkpoint = env.service.indexer.checkpoint

    def crash(**_kwargs):
        raise RuntimeError("模拟 checkpoint 前进程中断")

    env.service.indexer.checkpoint = crash
    crashed = env.service.run_ingest_job(job.jobId)
    assert crashed.state == "failed"
    assert crashed.errorCode == "INGEST_FAILED"
    after_crash_ids = env.vectors.point_ids(env.collection)
    assert after_crash_ids  # 向量已写入，但修订未发布

    env.service.indexer.checkpoint = original_checkpoint
    retried = env.service.retry_job(crashed.jobId)
    final = env.service.run_ingest_job(retried.jobId)
    assert final.state == "succeeded", final.errorMessage
    assert env.vectors.point_ids(env.collection) == after_crash_ids  # 相同 point id，无重复
    assert env.vectors.count(name=env.collection) == len(after_crash_ids)


def test_recover_pending_jobs_runs_queued_job(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text())
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-recover-1",
        library_ids=[env.library.library_id],
    )
    assert job.state == "queued"
    completed = env.service.recover_pending_jobs()
    assert completed == 1
    assert env.service.get_job_view(job.jobId).state == "succeeded"
    assert env.catalog.list_documents()[0].current_revision_id == job.inputRevisionId


# ---------------------------------------------------------------------- 提交闸门


def test_commit_blocked_while_rebuild_in_progress(env: Harness) -> None:
    rebuild = env.catalog.create_job(
        kind="rebuild",
        idempotency_key="rebuild-key-1",
        request_fingerprint="fp",
        target_generation_id=env.generation.generation_id,
        base_generation_id=env.generation.generation_id,
        state="queued",
    )
    env.catalog.set_rebuild_job(rebuild.job_id)
    draft = env.import_with_metadata(sample_text())
    with pytest.raises(AppError) as exc_info:
        env.service.commit_import(
            draft.importId,
            expected_revision=draft.revision,
            submission_id="submission-gate-1",
            library_ids=[env.library.library_id],
        )
    assert (exc_info.value.code, exc_info.value.status_code) == ("INDEX_REBUILD_IN_PROGRESS", 409)
    # 草稿保留，可稍后重试
    assert env.service.get_import_view(draft.importId).state == "needs_review"


def test_commit_requires_active_generation(tmp_path: Path) -> None:
    temp = Harness(tmp_path, bootstrap=False)
    draft = temp.import_with_metadata(sample_text())
    with pytest.raises(AppError) as exc_info:
        temp.service.commit_import(
            draft.importId,
            expected_revision=draft.revision,
            submission_id="submission-gate-2",
            library_ids=[temp.library.library_id],
        )
    assert (exc_info.value.code, exc_info.value.status_code) == ("INDEX_NOT_READY", 409)


def test_commit_rejects_second_publish_job_for_same_document(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text("集合"))
    job = env.commit_and_run(draft, submission_id="submission-busy-1")
    document = env.catalog.list_documents()[0]
    # 手工造一个仍在排队的入库任务，模拟另一个发布任务未结束
    env.catalog.create_job(
        kind="ingest",
        idempotency_key="other-publish-job",
        request_fingerprint="fp",
        input_revision_id=job.inputRevisionId,
        document_id=document.document_id,
        target_generation_id=env.generation.generation_id,
        state="queued",
    )
    update = env.service.create_import(
        file_name="chapter-v3.md",
        data=sample_text("集合的运算").encode("utf-8"),
        target_document_id=document.document_id,
        expected_current_revision_id=document.current_revision_id,
    )
    with pytest.raises(AppError) as exc_info:
        env.service.commit_import(
            update.importId,
            expected_revision=update.revision,
            submission_id="submission-busy-2",
            library_ids=[env.library.library_id],
        )
    assert (exc_info.value.code, exc_info.value.status_code) == ("INDEX_MUTATION_BUSY", 409)


def test_commit_rejects_stale_expected_current_revision(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text("集合"))
    env.commit_and_run(draft, submission_id="submission-stale-1")
    document = env.catalog.list_documents()[0]

    update = env.service.create_import(
        file_name="chapter-v4.md",
        data=sample_text("集合的运算").encode("utf-8"),
        target_document_id=document.document_id,
        expected_current_revision_id=document.current_revision_id,
    )
    # 直接发布一个更新的修订，模拟其他来源的改动
    newer = env.catalog.create_document_revision(
        document.document_id,
        original_file_sha256="f" * 64,
        normalized_text_sha256="e" * 64,
        parser_version="zqky-parse-v1",
        original_blob_id="f" * 64,
        normalized_blob_id="e" * 64,
        source_map_blob_id="d" * 64,
        char_count=1,
    )
    env.catalog.publish_document_revision(
        document.document_id,
        revision_id=newer.revision_id,
        metadata_revision_id=document.current_metadata_revision_id,
    )
    with pytest.raises(AppError) as exc_info:
        env.service.commit_import(
            update.importId,
            expected_revision=update.revision,
            submission_id="submission-stale-2",
            library_ids=[env.library.library_id],
        )
    assert (exc_info.value.code, exc_info.value.status_code) == ("REVISION_CONFLICT", 409)


def test_deleted_target_document_is_rejected(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text("集合"))
    env.commit_and_run(draft, submission_id="submission-deleted-1")
    document = env.catalog.list_documents()[0]
    env.catalog.delete_document(document.document_id, expected_revision=document.revision)
    with pytest.raises(AppError) as exc_info:
        env.service.create_import(
            file_name="chapter-v5.md",
            data=sample_text("集合的运算").encode("utf-8"),
            target_document_id=document.document_id,
        )
    assert exc_info.value.code == "DOCUMENT_UNAVAILABLE"


# ---------------------------------------------------------------------- 原文读取


def test_source_span_reads_published_revision(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text())
    job = env.commit_and_run(draft)
    revision_id = job.inputRevisionId
    span = env.service.source_span(revision_id, char_start=0, char_end=5)
    assert span.text == "# 第一章"
    assert span.documentRevisionId == revision_id
    assert span.locator.kind == "markdown"
    assert span.locator.lineStart == 1 and span.locator.lineEnd == 1

    with pytest.raises(AppError) as out_of_range:
        env.service.source_span(revision_id, char_start=0, char_end=10_000)
    assert (out_of_range.value.code, out_of_range.value.status_code) == ("INVALID_REQUEST", 422)

    with pytest.raises(AppError) as empty_range:
        env.service.source_span(revision_id, char_start=3, char_end=3)
    assert empty_range.value.code == "INVALID_REQUEST"


def test_source_span_hash_mismatch_is_409(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text())
    job = env.commit_and_run(draft)
    revision = env.catalog.get_revision(job.inputRevisionId)
    # 伪造登记指纹：指向真实 blob 但指纹不符
    mismatched = env.catalog.create_document_revision(
        env.catalog.list_documents()[0].document_id,
        original_file_sha256=revision.original_file_sha256,
        normalized_text_sha256="0" * 64,
        parser_version=revision.parser_version,
        original_blob_id=revision.original_blob_id,
        normalized_blob_id=revision.normalized_blob_id,
        source_map_blob_id=revision.source_map_blob_id,
        char_count=revision.char_count,
    )
    with pytest.raises(AppError) as exc_info:
        env.service.source_span(mismatched.revision_id, char_start=0, char_end=4)
    assert (exc_info.value.code, exc_info.value.status_code) == ("SOURCE_HASH_MISMATCH", 409)


def test_missing_blob_is_explicit_not_empty_success(env: Harness) -> None:
    draft = env.import_with_metadata(sample_text())
    job = env.commit_and_run(draft)
    revision = env.catalog.get_revision(job.inputRevisionId)
    (env.settings.textbooks_root / "normalized" / revision.normalized_blob_id).unlink()
    with pytest.raises(AppError) as exc_info:
        env.service.source_span(revision.revision_id, char_start=0, char_end=4)
    assert exc_info.value.code == "IMPORT_ARTIFACT_MISSING"


# --------------------------------------------------------------------- 解析失败


def test_parse_failure_stores_failed_draft_and_keeps_original(env: Harness) -> None:
    from tests.test_document_parsing import _build_pdf

    draft = env.service.create_import(file_name="broken.pdf", data=b"%PDF-1.4 junk")
    assert draft.state == "failed"
    assert draft.errorCode == "DOCUMENT_PARSE_FAILED"
    record: ImportRecord = env.catalog.get_import(draft.importId)
    assert record is not None
    assert record.uploaded_blob_id
    assert (env.settings.textbooks_root / "staging" / record.uploaded_blob_id).is_file()
    assert draft.canCommit is False
    with pytest.raises(AppError) as exc_info:
        env.service.commit_import(
            draft.importId,
            expected_revision=draft.revision,
            submission_id="submission-failed-1",
            library_ids=[env.library.library_id],
        )
    assert exc_info.value.code == "IMPORT_PARSE_FAILED"


# ------------------------------------------------------------- v1.1 租约续租


def _install_lease_spy(
    monkeypatch: pytest.MonkeyPatch,
    *,
    clock: FakeClock,
    renew_result: bool | None = None,
    on_renew=None,
) -> dict:
    """类级替身：记录 renew_lease / checkpoint_job 的调用时刻与顺序。"""
    records: dict = {"renewals": [], "events": [], "lease_seconds": []}
    original_renew = TextbookCatalog.renew_lease
    original_checkpoint = TextbookCatalog.checkpoint_job

    def renew(self, job_id: str, *, lease_token: str, lease_seconds: int = 90) -> bool:
        if on_renew is not None:
            on_renew()
        records["renewals"].append(clock.now)
        records["events"].append(("renew", clock.now))
        records["lease_seconds"].append(lease_seconds)
        if renew_result is not None:
            return renew_result
        return original_renew(self, job_id, lease_token=lease_token, lease_seconds=lease_seconds)

    def checkpoint(self, job_id: str, *, lease_token: str, checkpoint: dict) -> None:
        records["events"].append(("checkpoint", clock.now))
        return original_checkpoint(self, job_id, lease_token=lease_token, checkpoint=checkpoint)

    monkeypatch.setattr(TextbookCatalog, "renew_lease", renew)
    monkeypatch.setattr(TextbookCatalog, "checkpoint_job", checkpoint)
    return records


def _long_harness(tmp_path: Path, *, seconds_per_batch: float = 10.0):
    clock = FakeClock()
    embeddings = FakeEmbeddings()
    embeddings.on_embed = lambda _fake: clock.advance(seconds_per_batch)
    store = CountingVectorStore()
    env = Harness(
        tmp_path,
        batch_size=1,
        vectors=store,
        embeddings=embeddings,
        monotonic=clock,
        renew_seconds=DEFAULT_RENEW_SECONDS,
    )
    return env, clock, store


def test_lease_renewed_at_batch_boundaries(tmp_path: Path, monkeypatch) -> None:
    env, clock, _store = _long_harness(tmp_path)
    records = _install_lease_spy(monkeypatch, clock=clock)
    started_at = clock.now
    draft = env.import_with_metadata(long_text())
    job = env.commit_and_run(draft, submission_id="submission-lease-1")

    assert job.state == "succeeded", job.errorMessage
    assert job.progress.chunksTotal >= 5  # 足够跨过多个续租阈值
    assert env.service.indexer.leases.renew_seconds <= 20.0  # 契约：阈值 ≤20 秒
    assert records["renewals"], "长任务没有发生任何续租"

    # 首次续租发生在距上次续租（锚点=领取时刻）达到阈值之后
    assert records["renewals"][0] - started_at >= DEFAULT_RENEW_SECONDS
    # 相邻两次续租间隔不超过阈值（每批 10 秒，边界粒度 10 秒）
    deltas = [
        round(records["renewals"][index + 1] - records["renewals"][index], 3)
        for index in range(len(records["renewals"]) - 1)
    ]
    assert all(delta <= DEFAULT_RENEW_SECONDS for delta in deltas), deltas
    # 续租沿用任务租约长度
    assert set(records["lease_seconds"]) == {env.service.lease_seconds}
    # 每次续租之后都有 checkpoint：续租发生在批次之后、checkpoint 之前
    kinds = [kind for kind, _moment in records["events"]]
    assert kinds[-1] == "checkpoint"
    for index, kind in enumerate(kinds):
        if kind == "renew":
            assert "checkpoint" in kinds[index + 1:], records["events"]


def test_lease_renewal_refusal_stops_writes_immediately(tmp_path: Path, monkeypatch) -> None:
    env, clock, store = _long_harness(tmp_path)
    observed: dict = {}
    records = _install_lease_spy(
        monkeypatch,
        clock=clock,
        renew_result=False,  # 续租被拒：模拟记录已不属于本执行者
        on_renew=lambda: observed.setdefault("batches", store.upsert_batches),
    )
    draft = env.import_with_metadata(long_text())
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-lease-lost",
        library_ids=[env.library.library_id],
    )
    final = env.service.run_ingest_job(job.jobId)

    assert records["renewals"], "失权路径没有触发续租检查"
    assert observed["batches"] >= 1
    assert store.upsert_batches == observed["batches"]  # 失权后一次都没有再写向量
    assert store.upsert_points == observed["batches"]  # batch=1，点数等于批次数
    assert final.progress.chunksTotal >= 5
    assert store.upsert_batches < final.progress.chunksTotal  # 远少于全部批次
    assert final.state == "failed"
    assert final.errorCode == "LEASE_LOST"
    # 未发布：文档没有有效修订，代内修订保持 pending
    assert env.catalog.list_documents()[0].current_revision_id is None
    links = env.catalog.list_generation_revisions(env.generation.generation_id)
    assert [link.state for link in links] == ["pending"]
    assert env.service.get_import_view(draft.importId).state == "failed"


def test_expired_lease_stops_writes_and_is_recoverable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """确定性模拟"记录已不属于本执行者"：所有租约校验失败 → 立即停止且不改记录，租约过期后可恢复。

    不依赖真实 sleep 与负载做"失权"判定（避免满载时抖动）；只在最后让 1 秒租约真实过期以便恢复。
    """
    clock = FakeClock()
    embeddings = FakeEmbeddings()
    state = {"patched": False}

    def on_embed(_fake) -> None:
        clock.advance(10.0)
        if not state["patched"]:
            state["patched"] = True
            # 第一批已写入之后失权：此后 require/checkpoint/finish/renew 的租约校验一律失败
            monkeypatch.setattr(
                TextbookCatalog, "_lease_matches", staticmethod(lambda row, token, now: False)
            )

    embeddings.on_embed = on_embed
    store = CountingVectorStore()
    env = Harness(
        tmp_path,
        batch_size=1,
        vectors=store,
        embeddings=embeddings,
        monotonic=clock,
        renew_seconds=DEFAULT_RENEW_SECONDS,
    )
    draft = env.import_with_metadata(long_text())
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-lease-expired",
        library_ids=[env.library.library_id],
    )
    final = env.service.run_ingest_job(job.jobId)
    written = store.upsert_batches

    assert written >= 1  # 失权发生在第一批之后
    # 真失权：记录不可写 → 保持 running（不得改任务/修订/索引指针），由恢复流程接管
    assert final.state == "running"
    assert final.errorCode is None
    assert store.upsert_batches == written  # 停止后没有任何新写入
    assert env.catalog.list_documents()[0].current_revision_id is None

    # 恢复租约校验，并把 lease_until 直接写到过去（确定性制造"租约过期"，不依赖真实等待；
    # 准备阶段耗时波动曾让 1 秒租约在第一批之前就过期，这里用默认租约避免时间敏感）
    monkeypatch.undo()
    connection = sqlite_connect(env.catalog.db_path)
    try:
        connection.execute(
            "UPDATE index_jobs SET lease_until = ? WHERE id = ?",
            ("1970-01-01T00:00:00Z", job.jobId),
        )
    finally:
        connection.close()
    recovery = IngestService(
        env.catalog,
        _parser,
        chunk_document,
        env.embeddings,
        store,
        env.settings,
        batch_size=1,
        sleep=lambda _seconds: None,
        lease_seconds=90,
        renew_seconds=DEFAULT_RENEW_SECONDS,
        monotonic=clock,
    )
    assert recovery.recover_pending_jobs() == 1
    recovered = recovery.get_job_view(job.jobId)
    assert recovered.state == "succeeded", recovered.errorMessage
    link = env.catalog.list_generation_revisions(env.generation.generation_id)[0]
    assert link.state == "ready"
    assert store.count(name=env.collection) == link.expected_chunk_count


def test_lease_keeper_renews_when_forced_and_anchors_on_begin(tmp_path: Path) -> None:
    """LeaseKeeper 单元语义：未到期不续租，到期/强制续租，失权抛 LEASE_LOST。"""
    from app.services.textbook_ingest.jobs import LeaseKeeper

    catalog = TextbookCatalog(tmp_path / "keeper.sqlite3")
    catalog.migrate()
    clock = FakeClock()
    keeper = LeaseKeeper(catalog, renew_seconds=20.0, lease_seconds=60, monotonic=clock)
    keeper.begin("job-1")
    assert keeper.renew_if_due(job_id="job-1", lease_token="token") is False  # 未到期，不调用
    assert keeper.renewals == 0
    clock.advance(21.0)
    # 到期且没有真实 running 任务：续租返回 False → 抛 LEASE_LOST（立即停止）
    with pytest.raises(AppError) as exc_info:
        keeper.renew_if_due(job_id="job-1", lease_token="token")
    assert exc_info.value.code == "LEASE_LOST"
    assert keeper.renewals == 0
    keeper.forget("job-1")
    assert keeper.revise_seconds_elapsed("job-1") is None

    # 首次调用自动锚定：阈值内不再续租；force=True 跳过阈值检查立即续租（同样失权抛错）
    assert keeper.renew_if_due(job_id="job-2", lease_token="token") is False
    clock.advance(19.0)
    assert keeper.renew_if_due(job_id="job-2", lease_token="token") is False
    with pytest.raises(AppError) as forced:
        keeper.renew_if_due(job_id="job-2", lease_token="token", force=True)
    assert forced.value.code == "LEASE_LOST"

    # 成功续租会记录下来（构造一个真实的 running 任务）
    library = catalog.create_library(
        kind="base",
        owner_id="system",
        display_name="库",
        grade_id="senior-1",
        subject_id="math",
        edition_id="renjiao-a",
    )
    profile = catalog.create_embedding_profile(
        fingerprint="fp-keeper",
        adapter="ollama",
        native_base_url="http://127.0.0.1:11434",
        model_name="bge-m3",
        model_manifest_digest="digest",
        dimensions=4,
        distance="cosine",
        query_prefix="",
        document_prefix="",
        normalization="none",
    )
    generation = catalog.create_generation(
        profile_id=profile.profile_id,
        collection_name="textbooks_keeper",
        chunk_policy_json={"policy": {}, "manifest": []},
    )
    job = catalog.create_job(
        kind="ingest",
        idempotency_key="keeper-job",
        request_fingerprint="fp",
        target_generation_id=generation.generation_id,
        state="queued",
    )
    claimed = catalog.claim_job(job.job_id, lease_seconds=60)
    deadline_before = catalog.get_job(claimed.job_id).lease_until
    # 用更长的租约续租：租约到期时间必须被真正延长（长任务不会中途失权）
    keeper3 = LeaseKeeper(catalog, renew_seconds=20.0, lease_seconds=120, monotonic=clock)
    keeper3.begin(claimed.job_id)
    clock.advance(20.0)
    assert keeper3.renew_if_due(job_id=claimed.job_id, lease_token=claimed.lease_token or "") is True
    assert keeper3.renewals == 1
    deadline_after = catalog.get_job(claimed.job_id).lease_until
    assert deadline_before is not None and deadline_after is not None
    assert deadline_after > deadline_before
    assert catalog.require_lease(claimed.job_id, claimed.lease_token or "") is not None
    assert library.library_id


# ------------------------------------------------------------ v1.1 origin_key


def test_same_content_reimport_reuses_document(tmp_path: Path) -> None:
    env = Harness(tmp_path)
    payload = sample_text("集合")
    first = env.import_with_metadata(payload)
    first_job = env.commit_and_run(first, submission_id="submission-origin-1")
    assert first_job.state == "succeeded"

    documents = env.catalog.list_documents()
    assert len(documents) == 1
    document = documents[0]
    record = env.catalog.get_import(first.importId)
    assert document.origin_key == origin_key_for("system", record.uploaded_blob_id)

    second = env.import_with_metadata(payload)
    second_job = env.commit_and_run(second, submission_id="submission-origin-2")
    assert second_job.state == "succeeded", second_job.errorMessage

    documents = env.catalog.list_documents()
    assert len(documents) == 1  # 相同内容不产生第二册
    document = documents[0]
    assert len(env.catalog.list_document_revisions(document.document_id)) == 2  # 追加为第二个修订
    assert document.current_revision_id == second_job.inputRevisionId
    assert env.catalog.get_revision(first_job.inputRevisionId) is not None  # 旧修订保留可读

    draft_view = env.service.get_import_view(second.importId)
    assert ORIGIN_REUSE_WARNING in draft_view.warnings
    assert draft_view.state == "ready"
    # 第二次提交落在同一书册上（不是新建）
    assert env.catalog.get_import(second.importId).parsed_artifacts["sealedDocumentId"] == document.document_id


def test_different_content_creates_two_documents(tmp_path: Path) -> None:
    env = Harness(tmp_path)
    first = env.import_with_metadata(sample_text("集合"))
    second = env.import_with_metadata(sample_text("函数"), file_name="b.md")
    assert env.commit_and_run(first, submission_id="submission-two-1").state == "succeeded"
    assert env.commit_and_run(second, submission_id="submission-two-2").state == "succeeded"
    documents = env.catalog.list_documents()
    assert len(documents) == 2
    keys = {document.origin_key for document in documents}
    assert len(keys) == 2
    assert all(key is not None and key.startswith("system:") for key in keys)
    assert all(document.current_revision_id is not None for document in documents)


def test_explicit_update_keeps_origin_key(tmp_path: Path) -> None:
    env = Harness(tmp_path)
    first = env.import_with_metadata(sample_text("集合"))
    assert env.commit_and_run(first, submission_id="submission-update-1").state == "succeeded"
    document = env.catalog.list_documents()[0]
    original_key = document.origin_key

    update = env.service.create_import(
        file_name="v2.md",
        data=sample_text("集合的运算").encode("utf-8"),
        target_document_id=document.document_id,
        expected_current_revision_id=document.current_revision_id,
    )
    assert update.metadataConfirmed is True  # 目标书册元数据预填
    job = env.commit_and_run(update, submission_id="submission-update-2")
    assert job.state == "succeeded", job.errorMessage

    documents = env.catalog.list_documents()
    assert len(documents) == 1  # 更新路径不新建书册
    assert documents[0].origin_key == original_key  # 不改写来源键
    assert documents[0].current_revision_id == job.inputRevisionId
    assert len(env.catalog.list_document_revisions(documents[0].document_id)) == 2
    # 更新路径不带"同一内容复用"提示
    assert ORIGIN_REUSE_WARNING not in env.service.get_import_view(update.importId).warnings


def test_reimport_after_delete_is_refused_without_new_document(tmp_path: Path) -> None:
    env = Harness(tmp_path)
    payload = sample_text("集合")
    first = env.import_with_metadata(payload)
    assert env.commit_and_run(first, submission_id="submission-deleted-1").state == "succeeded"
    document = env.catalog.list_documents()[0]
    env.catalog.delete_document(document.document_id, expected_revision=document.revision)

    again = env.import_with_metadata(payload)
    with pytest.raises(AppError) as exc_info:
        env.service.commit_import(
            again.importId,
            expected_revision=again.revision,
            submission_id="submission-deleted-2",
            library_ids=[env.library.library_id],
        )
    assert (exc_info.value.code, exc_info.value.status_code) == ("DOCUMENT_ORIGIN_DELETED", 409)
    # 不复活也不新建：仍是那一册（逻辑删除保留）
    documents = env.catalog.list_documents(include_deleted=True)
    assert len(documents) == 1
    assert documents[0].deleted_at is not None
    assert documents[0].current_revision_id == document.current_revision_id


def test_origin_key_is_partitioned_by_owner(tmp_path: Path) -> None:
    """身份按 owner 分区：同一内容进入基础库与个人库是两册（B0 唯一键为 owner+origin_key）。"""
    env = Harness(tmp_path)
    personal = env.catalog.create_library(
        kind="personal",
        owner_id="local-user",
        display_name="我的教材",
        grade_id="senior-1",
        subject_id="math",
        edition_id="renjiao-a",
    )
    payload = sample_text("集合")
    draft = env.import_with_metadata(payload)
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-owner-1",
        library_ids=[env.library.library_id],
    )
    assert env.service.run_ingest_job(job.jobId).state == "succeeded"

    second = env.import_with_metadata(payload, file_name="same.md")
    job2 = env.service.commit_import(
        second.importId,
        expected_revision=second.revision,
        submission_id="submission-owner-2",
        library_ids=[personal.library_id],
    )
    assert env.service.run_ingest_job(job2.jobId).state == "succeeded"
    documents = env.catalog.list_documents()
    assert len(documents) == 2
    assert {document.owner_id for document in documents} == {"system", "local-user"}
    assert {document.origin_key.split(":")[0] for document in documents} == {"system", "local-user"}


# ------------------------------------------ v1.2 划分规则版本与降级警告贯通


def test_degraded_region_warning_reaches_import_draft_view(tmp_path: Path) -> None:
    """划分异常必须在草稿 warnings 里如实展示（不静默用错误划分索引）。"""
    env = Harness(tmp_path)
    body = "\n\n".join(f"{index}. 第{index}道练习题，计算并说明。" for index in range(1, 80))
    all_exercises = f"# 习题 1.1\n\n{body}\n"
    draft = env.draft(all_exercises, metadata=METADATA)
    assert draft.state == "needs_review"
    assert any(
        warning.startswith(DEGRADED_WARNING_PREFIX) for warning in draft.warnings
    ), draft.warnings
    # 降级后全部按正文处理：分块区只有 body
    assert draft.parsed is not None
    assert draft.parsed.bodyChunkCount == draft.parsed.chunkCount > 0
    assert draft.parsed.exerciseChunkCount == 0
    assert all(chunk.region == "body" for chunk in draft.parsed.preview)


def test_changed_region_rules_version_creates_new_chunk_set(tmp_path: Path) -> None:
    """旧口径（无 regionRulesVersion）的分块集不会被新版静默复用。"""
    env = Harness(tmp_path)
    draft = env.import_with_metadata(sample_text())
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-regionrules-1",
        library_ids=[env.library.library_id],
    )
    revision = env.catalog.get_revision(job.inputRevisionId)
    # 先造一个 v1 口径的分块集（模拟 v1.0/v1.1 已入库的产物）
    legacy_policy = chunk_policy_from_json(
        {"targetChars": 800, "maxChars": 1200, "overlapChars": 120, "version": "zqky-chunk-v1"}
    )
    assert legacy_policy.region_rules_version == LEGACY_REGION_RULES_VERSION
    legacy_fingerprint = chunk_policy_fingerprint(legacy_policy)
    assert legacy_fingerprint != chunk_policy_fingerprint()
    legacy_chunk_set = env.catalog.create_chunk_set(
        revision.revision_id,
        policy_fingerprint=legacy_fingerprint,
        manifest_sha256=chunk_manifest_sha256([]),
        chunks=[],
    )
    assert env.catalog.find_chunk_set(revision.revision_id, chunk_policy_fingerprint()) is None

    final = env.service.run_ingest_job(job.jobId)
    assert final.state == "succeeded", final.errorMessage
    link = env.catalog.list_generation_revisions(env.generation.generation_id)[0]
    new_chunk_set = env.catalog.get_chunk_set(link.chunk_set_id)
    assert new_chunk_set is not None
    assert new_chunk_set.chunk_set_id != legacy_chunk_set.chunk_set_id  # 不复用旧划分
    assert new_chunk_set.policy_fingerprint == chunk_policy_fingerprint()
    assert new_chunk_set.chunk_count == link.expected_chunk_count > 0
    # 旧分块集保留可读（不可变），但当前代挂的是新分块集
    assert env.catalog.get_chunk_set(legacy_chunk_set.chunk_set_id) is not None
