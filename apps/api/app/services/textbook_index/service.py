"""索引代与重建：闸门、逐修订构建、对账、原子发布，以及 Embedding 配置管理。

不变量：
- 重建期间查询继续使用旧代；``active_generation_id`` 只在全部核验通过后切换；
- 失败/取消把目标代标为 ``aborted`` 并释放闸门，但**不改** ``active_generation_id``；
- 代内清单在开始时冻结：期间被删除的书册标 ``skipped_deleted`` 且不复活，
  发布前用当前存活修订集合与清单对账（``expected ⊆ frozen``）；
- 逐修订对账使用 ``vector_store.count``（范围过滤下推），不取回全库。
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.core.exceptions import AppError
from app.providers.embeddings.fingerprint import (
    canonical_json,
    embedding_fingerprint,
    sha256_hex,
)
from app.providers.embeddings.ollama_embedding import normalize_model_tag
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import (
    GenerationRecord,
    JobRecord,
    ProfileRecord,
)
from app.repositories.vector_store.base import AllowedFilter
from app.schemas.textbook import (
    EmbeddingProfileList,
    EmbeddingProfileView,
    EmbeddingProbeView,
    IndexStatusView,
    JobView,
)
from app.services.document_parsing.chunking import (
    DEFAULT_CHUNK_POLICY,
    chunk_manifest_sha256,
    chunk_policy_fingerprint,
)
from app.services.document_parsing.parser import ParsedDocument, parse_document
from app.services.textbook_ingest.blobs import BlobStore
from app.services.textbook_ingest.generation_doc import (
    ManifestEntry,
    generation_manifest,
    generation_policy,
    generation_policy_document,
    new_collection_name,
)
from app.services.textbook_ingest.indexer import DocumentIndexer, JobCancelled
from app.services.textbook_ingest.jobs import (
    DEFAULT_RENEW_SECONDS,
    recoverable_jobs,
    request_cancel,
    try_fail_lost_lease,
)
from app.services.textbook_ingest.views import generation_view, job_view

logger = logging.getLogger("zhiqikeyuan.api.textbook_index")

DEFAULT_WORKER_ID = "index-worker-1"
DEFAULT_LEASE_SECONDS = 90
FINAL_JOB_STATES = frozenset({"succeeded", "failed", "cancelled"})


def _invalid(message: str, *, code: str = "INVALID_REQUEST") -> AppError:
    return AppError(message, code=code, status_code=422)


def _not_found(message: str, *, code: str) -> AppError:
    return AppError(message, code=code, status_code=404)


def _conflict(message: str, *, code: str, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=409, retryable=retryable)


@dataclass(frozen=True)
class _ProbeOutcome:
    view: EmbeddingProbeView
    fingerprint: str
    base_url: str


class IndexService:
    def __init__(
        self,
        catalog: TextbookCatalog,
        embeddings: Any,
        vectors: Any,
        settings: Any,
        *,
        parser: Callable[..., ParsedDocument] = parse_document,
        chunker: Callable[..., list] | None = None,
        provider_factory: Callable[[str], Any] | None = None,
        batch_size: int = 8,
        worker_id: str = DEFAULT_WORKER_ID,
        sleep: Callable[[float], None] = time.sleep,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        renew_seconds: float = DEFAULT_RENEW_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
        max_attempts: int = 3,
        retry_backoff: tuple[float, ...] = (2.0, 10.0, 30.0),
    ) -> None:
        self.catalog = catalog
        self.embeddings = embeddings
        self.vectors = vectors
        self.settings = settings
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self._provider_factory = provider_factory
        self.blobs = BlobStore(settings.textbooks_root)
        self.indexer = DocumentIndexer(
            catalog,
            embeddings,
            vectors,
            self.blobs,
            batch_size=batch_size,
            sleep=sleep,
            max_attempts=max_attempts,
            retry_backoff=retry_backoff,
            lease_seconds=lease_seconds,
            renew_seconds=renew_seconds,
            monotonic=monotonic,
        )
        self._gate_lock = threading.Lock()
        self._running = threading.Lock()

    def close(self) -> None:
        """无长连接需要关闭；保留方法以便统一生命周期调用。"""
        return None

    # -------------------------------------------------------------------- 状态

    def status(self) -> IndexStatusView:
        state = self.catalog.catalog_state()
        generation = (
            self.catalog.get_generation(state.active_generation_id)
            if state.active_generation_id
            else None
        )
        profile = (
            self.catalog.get_embedding_profile(generation.profile_id)
            if generation is not None
            else None
        )
        rebuild_job = (
            self.catalog.get_job(state.rebuild_job_id) if state.rebuild_job_id else None
        )
        available, reason = self._qdrant_status()
        scope_ready, scope_reason = self._scope_status(generation)
        return IndexStatusView(
            activeGenerationId=state.active_generation_id,
            activeProfileId=profile.profile_id if profile is not None else None,
            activeProfileName=profile.model_name if profile is not None else None,
            activeProfileDimensions=profile.dimensions if profile is not None else None,
            generation=generation_view(self.catalog, generation) if generation is not None else None,
            rebuildJob=job_view(rebuild_job) if rebuild_job is not None else None,
            generationCount=len(self.catalog.list_generations()),
            qdrantAvailable=available,
            qdrantReason=reason,
            scopeReady=scope_ready,
            scopeReason=scope_reason,
        )

    def _qdrant_status(self) -> tuple[bool, str | None]:
        try:
            available = bool(self.vectors.ping())
        except Exception as exc:  # noqa: BLE001 - 探测失败不抛，如实报告
            return False, f"Qdrant 探测失败：{exc.__class__.__name__}"
        if available:
            return True, None
        reason = None
        getter = getattr(self.vectors, "ping_error", None)
        if callable(getter):
            try:
                reason = getter()
            except Exception:  # noqa: BLE001
                reason = None
        return False, reason or "Qdrant 不可达或未启动。"

    def _scope_status(self, generation: GenerationRecord | None) -> tuple[bool, str | None]:
        if generation is None:
            return False, "尚未创建任何索引代。"
        if generation.state != "ready":
            return False, f"当前索引代状态为 {generation.state}，尚不可检索。"
        ready = [
            record
            for record in self.catalog.list_generation_revisions(generation.generation_id)
            if record.state == "ready"
        ]
        if not ready:
            return False, "当前索引代还没有已入库的教材。"
        return True, None

    # -------------------------------------------------------------- Embedding

    def list_profiles(self) -> EmbeddingProfileList:
        state = self.catalog.catalog_state()
        active_generation = (
            self.catalog.get_generation(state.active_generation_id)
            if state.active_generation_id
            else None
        )
        active_profile_id = active_generation.profile_id if active_generation is not None else None
        installed = self._installed_model_names()
        profiles = [
            self._profile_view(
                profile,
                is_active=profile.profile_id == active_profile_id,
                installed=self._is_installed(profile.model_name, installed),
            )
            for profile in self.catalog.list_embedding_profiles()
        ]
        return EmbeddingProfileList(profiles=profiles, activeProfileId=active_profile_id)

    def _installed_model_names(self) -> set[str] | None:
        """本机在场模型名（按 Ollama tag 语义归一：``bge-m3`` 与 ``bge-m3:latest`` 视为同一模型）。

        本地服务不可达时返回 ``None``（无法证明"已安装"，不猜）。
        """
        try:
            return {normalize_model_tag(candidate.name) for candidate in self.embeddings.list_models()}
        except AppError:
            return None

    @staticmethod
    def _is_installed(profile_model_name: str, installed: set[str] | None) -> bool:
        """tag 归一后全等才算在场；不做包含匹配（``bge-m3`` 不得命中 ``bge-m3-large``）。"""
        if installed is None:
            return False
        key = normalize_model_tag(profile_model_name)
        return bool(key) and key in installed

    @staticmethod
    def _profile_view(
        profile: ProfileRecord, *, is_active: bool, installed: bool
    ) -> EmbeddingProfileView:
        return EmbeddingProfileView(
            profileId=profile.profile_id,
            fingerprint=profile.fingerprint,
            adapter="ollama",
            nativeBaseUrl=profile.native_base_url,
            modelName=profile.model_name,
            modelManifestDigest=profile.model_manifest_digest,
            dimensions=profile.dimensions,
            distance="cosine",
            queryPrefix=profile.query_prefix,
            documentPrefix=profile.document_prefix,
            normalization=profile.normalization,
            verifiedAt=profile.verified_at,
            retiredAt=profile.retired_at,
            isActive=is_active,
            installed=installed,
        )

    def _provider_for(self, base_url: str | None):
        target = (base_url or "").strip()
        settings_url = str(self.settings.embedding_base_url)
        if not target or target.rstrip("/") == settings_url.rstrip("/"):
            return self.embeddings
        if self._provider_factory is not None:
            return self._provider_factory(target)
        from app.providers.embeddings.ollama_embedding import OllamaEmbeddingProvider

        return OllamaEmbeddingProvider(target)

    def _probe_internal(
        self,
        *,
        model_name: str,
        base_url: str | None,
        query_prefix: str,
        document_prefix: str,
        normalization: str,
    ) -> _ProbeOutcome:
        provider = self._provider_for(base_url)
        result = provider.verify_embedding_candidate(model_name=model_name)
        fingerprint = embedding_fingerprint(
            model_manifest_digest=result.model_manifest_digest,
            dimensions=result.dimensions,
            query_prefix=query_prefix,
            document_prefix=document_prefix,
            normalization=normalization,
            options={},
        )
        existing = self.catalog.find_embedding_profile(fingerprint)
        native_base_url = str(
            getattr(provider, "base_url", settings_url_normalized(self.settings))
        )
        return _ProbeOutcome(
            view=EmbeddingProbeView(
                modelName=result.model_name,
                modelManifestDigest=result.model_manifest_digest,
                dimensions=result.dimensions,
                distance="cosine",
                sampleCount=result.sample_count,
                nonZero=result.non_zero,
                finite=result.finite,
                stableDigest=result.stable_digest,
                alreadyConfigured=existing is not None,
                existingProfileId=existing.profile_id if existing is not None else None,
            ),
            fingerprint=fingerprint,
            base_url=native_base_url,
        )

    def probe(
        self,
        *,
        model_name: str,
        base_url: str | None = None,
        query_prefix: str = "",
        document_prefix: str = "",
        normalization: str = "none",
    ) -> EmbeddingProbeView:
        outcome = self._probe_internal(
            model_name=model_name,
            base_url=base_url,
            query_prefix=query_prefix,
            document_prefix=document_prefix,
            normalization=normalization,
        )
        return outcome.view

    def create_profile(
        self,
        *,
        model_name: str,
        base_url: str | None = None,
        query_prefix: str = "",
        document_prefix: str = "",
        normalization: str = "none",
    ) -> EmbeddingProfileView:
        outcome = self._probe_internal(
            model_name=model_name,
            base_url=base_url,
            query_prefix=query_prefix,
            document_prefix=document_prefix,
            normalization=normalization,
        )
        if outcome.view.existingProfileId is not None:
            existing = self.catalog.get_embedding_profile(outcome.view.existingProfileId)
            if existing is not None:
                return self._profile_view(existing, is_active=False, installed=True)
        profile = self.catalog.create_embedding_profile(
            fingerprint=outcome.fingerprint,
            adapter="ollama",
            native_base_url=outcome.base_url,
            model_name=outcome.view.modelName,
            model_manifest_digest=outcome.view.modelManifestDigest,
            dimensions=outcome.view.dimensions,
            distance="cosine",
            query_prefix=query_prefix,
            document_prefix=document_prefix,
            normalization=normalization,
            options_json={},
        )
        return self._profile_view(profile, is_active=False, installed=True)

    # ---------------------------------------------------------------- 空库首启

    def ensure_empty_generation(self, profile_id: str) -> GenerationRecord:
        """创建并验证空 collection，事务外建代、随后置为当前；``scopeReady`` 仍为 False。"""
        profile = self.catalog.get_embedding_profile(profile_id)
        if profile is None:
            raise _not_found("Embedding 配置不存在。", code="PROFILE_NOT_FOUND")
        generation = self.catalog.create_generation(
            profile_id=profile.profile_id,
            collection_name=new_collection_name(),
            chunk_policy_json=generation_policy_document(DEFAULT_CHUNK_POLICY, []),
            state="building",
        )
        try:
            self.vectors.ensure_collection(
                name=generation.collection_name,
                dimensions=profile.dimensions,
                distance="Cosine",
            )
            count = self.vectors.count(name=generation.collection_name)
            if count != 0:
                raise _conflict(
                    "新建 collection 不是空集，拒绝发布为当前索引代。",
                    code="COLLECTION_NOT_EMPTY",
                )
        except Exception:
            try:
                self.catalog.update_generation_state(generation.generation_id, "aborted")
            except AppError:  # pragma: no cover - 尽力标记，不覆盖原始错误
                logger.exception("标记空索引代失败")
            raise
        self.catalog.publish_generation(generation.generation_id)
        self.catalog.set_active_generation(generation.generation_id)
        return self.catalog.get_generation(generation.generation_id) or generation

    # ------------------------------------------------------------------ 重建

    def _release_stale_gate(self) -> None:
        """闸门指向已结束任务时释放：崩溃/竞态留下的悬空闸门自愈。"""
        state = self.catalog.catalog_state()
        if state.rebuild_job_id is None:
            return
        job = self.catalog.get_job(state.rebuild_job_id)
        if job is None or job.state in FINAL_JOB_STATES:
            logger.warning("释放悬空重建闸门：%s", state.rebuild_job_id)
            self.catalog.set_rebuild_job(None)

    def _snapshot_manifest(self) -> tuple[ManifestEntry, ...]:
        entries: list[ManifestEntry] = []
        for document in self.catalog.list_documents():
            if document.is_deleted or not document.current_revision_id:
                continue
            entries.append(
                ManifestEntry(
                    document_id=document.document_id,
                    document_revision_id=document.current_revision_id,
                    metadata_revision_id=document.current_metadata_revision_id,
                    title=document.title,
                )
            )
        return tuple(entries)

    def _rebuild_fingerprint(
        self, *, profile_id: str, base_generation_id: str | None, manifest: tuple[ManifestEntry, ...]
    ) -> str:
        return sha256_hex(
            canonical_json(
                {
                    "profileId": profile_id,
                    "baseGenerationId": base_generation_id,
                    "manifest": [entry.to_json() for entry in manifest],
                }
            )
        )

    def begin_rebuild(self, *, profile_id: str, submission_id: str) -> JobView:
        submission = (submission_id or "").strip()
        if len(submission) < 8:
            raise _invalid("submit 幂等键至少 8 个字符。")
        self._release_stale_gate()
        profile = self.catalog.get_embedding_profile(profile_id)
        if profile is None:
            raise _not_found("Embedding 配置不存在。", code="PROFILE_NOT_FOUND")
        self.indexer.require_profile_usable(profile)

        existing = self.catalog.find_job_by_key(submission)
        state = self.catalog.catalog_state()
        manifest = self._snapshot_manifest()
        fingerprint = self._rebuild_fingerprint(
            profile_id=profile.profile_id,
            base_generation_id=state.active_generation_id,
            manifest=manifest,
        )
        if existing is not None:
            if existing.kind != "rebuild":
                raise _conflict(
                    "同一幂等键已用于其他类型任务。", code="IDEMPOTENCY_CONFLICT"
                )
            if existing.request_fingerprint != fingerprint:
                raise _conflict(
                    "同一幂等键已登记不同载荷的重建任务。", code="IDEMPOTENCY_CONFLICT"
                )
            return job_view(existing)

        # 事务外先核模型身份：清单 digest 变化拒绝继续（不换模型）
        digest = self.embeddings.manifest_digest(profile.model_name)
        if digest != profile.model_manifest_digest:
            raise _conflict(
                "模型清单 digest 与配置不一致，禁止使用错误模型空间；请重新检测并保存配置。",
                code="EMBEDDING_MODEL_CHANGED",
            )

        with self._gate_lock:
            state = self.catalog.catalog_state()
            if state.rebuild_job_id is not None:
                raise _conflict(
                    "已有重建任务在进行，请等待其结束。",
                    code="INDEX_MUTATION_BUSY",
                    retryable=True,
                )
            if self.catalog.has_active_ingest_jobs():
                raise _conflict(
                    "仍有入库任务排队或执行中，暂不能开始重建。",
                    code="INDEX_MUTATION_BUSY",
                    retryable=True,
                )
            manifest = self._snapshot_manifest()
            fingerprint = self._rebuild_fingerprint(
                profile_id=profile.profile_id,
                base_generation_id=state.active_generation_id,
                manifest=manifest,
            )
            generation = self.catalog.create_generation(
                profile_id=profile.profile_id,
                collection_name=new_collection_name(),
                chunk_policy_json=generation_policy_document(DEFAULT_CHUNK_POLICY, manifest),
                state="building",
            )
            job = self.catalog.create_job(
                kind="rebuild",
                idempotency_key=submission,
                request_fingerprint=fingerprint,
                target_generation_id=generation.generation_id,
                base_generation_id=state.active_generation_id,
                state="queued",
            )
            guard = self.catalog.catalog_state()
            if guard.rebuild_job_id is not None and guard.rebuild_job_id != job.job_id:
                self.catalog.update_generation_state(generation.generation_id, "aborted")
                raise _conflict(
                    "已有重建任务在进行，请等待其结束。",
                    code="INDEX_MUTATION_BUSY",
                    retryable=True,
                )
            self.catalog.set_rebuild_job(job.job_id)
        return job_view(job)

    def get_job_view(self, job_id: str) -> JobView:
        record = self.catalog.get_job(job_id)
        if record is None:
            raise _not_found("索引任务不存在。", code="JOB_NOT_FOUND")
        return job_view(record)

    def run_rebuild(self, job_id: str, *, lease_seconds: int | None = None) -> JobView:
        record = self.catalog.get_job(job_id)
        if record is None:
            raise _not_found("索引任务不存在。", code="JOB_NOT_FOUND")
        if record.kind != "rebuild":
            raise _conflict("该任务不是重建任务。", code="JOB_KIND_MISMATCH")
        if record.state in FINAL_JOB_STATES:
            return job_view(record)
        try:
            claimed = self.catalog.claim_job(
                job_id, lease_seconds=lease_seconds or self.lease_seconds
            )
        except AppError as exc:
            if exc.code == "JOB_BUSY":
                return job_view(self.catalog.get_job(job_id) or record)
            raise
        return job_view(self._execute_rebuild(claimed))

    def cancel_job(self, job_id: str) -> JobView:
        record = self.catalog.get_job(job_id)
        if record is None:
            raise _not_found("索引任务不存在。", code="JOB_NOT_FOUND")
        updated = request_cancel(self.catalog, job_id, lease_seconds=self.lease_seconds)
        if updated.state == "cancelled":
            # 排队任务取消即终态：同步释放闸门并把目标代标为 aborted（与 terminate 同语义）
            self._abort_target_and_release_gate(record.job_id, record.target_generation_id)
            return job_view(self.catalog.get_job(job_id) or updated)
        return job_view(updated)

    def _abort_target_and_release_gate(
        self, job_id: str, target_generation_id: str | None
    ) -> None:
        if target_generation_id:
            try:
                self.catalog.update_generation_state(target_generation_id, "aborted")
            except AppError:
                logger.exception("标记索引代 %s 为 aborted 失败", target_generation_id)
        if self.catalog.catalog_state().rebuild_job_id == job_id:
            self.catalog.set_rebuild_job(None)

    def _handle_lost_lease(self, job: JobRecord) -> JobRecord:
        """租约失效的安全落点：只有先写定终态（证明记录仍属于本执行者）才动目标代与闸门。

        真失权（记录不可写，例如已被其他 worker 重新领取）时什么都不改，保持 ``running``，
        由 ``recover_pending_jobs`` 在租约过期后接管，绝不误伤他人正在构建的代。
        """
        failed = try_fail_lost_lease(self.catalog, job)
        if failed is None:
            return self.catalog.get_job(job.job_id) or job
        self._abort_target_and_release_gate(job.job_id, job.target_generation_id)
        return failed

    def recover_pending_jobs(self, *, max_jobs: int = 4) -> int:
        if not self._running.acquire(blocking=False):
            return 0
        completed = 0
        try:
            self._release_stale_gate()
            for _ in range(max(1, max_jobs)):
                candidates = recoverable_jobs(self.catalog, kinds=("rebuild",))
                if not candidates:
                    break
                try:
                    self.run_rebuild(candidates[0].job_id)
                except AppError as exc:
                    if exc.code in ("JOB_BUSY", "JOB_NOT_CLAIMABLE"):
                        break
                    raise
                completed += 1
        finally:
            self._running.release()
        return completed

    def terminate_rebuild(
        self,
        job_id: str,
        *,
        state: str,
        error_code: str,
        error_message: str | None = None,
    ) -> JobView:
        if state not in ("failed", "cancelled"):
            raise _invalid("重建终止状态只能是 failed 或 cancelled。")
        record = self.catalog.get_job(job_id)
        if record is None:
            raise _not_found("索引任务不存在。", code="JOB_NOT_FOUND")
        if record.state in FINAL_JOB_STATES:
            return job_view(record)
        lease_token = record.lease_token
        if record.state == "queued":
            # 排队任务没有租约：先领取再终止，保证 finish_job 的租约校验成立
            claimed = self.catalog.claim_job(job_id, lease_seconds=self.lease_seconds)
            lease_token = claimed.lease_token
        if not lease_token:
            raise _conflict(
                "任务租约缺失，无法写入终止状态。", code="LEASE_LOST", retryable=True
            )
        self._abort_target_and_release_gate(job_id, record.target_generation_id)
        try:
            finished = self.catalog.finish_job(
                job_id,
                lease_token=lease_token,
                state=state,
                error_code=error_code,
                error_message=(error_message or "")[:500] or None,
            )
        except AppError as exc:
            if exc.code == "LEASE_LOST":
                logger.warning("重建任务 %s 租约失效，终止未写入。", job_id)
                return job_view(self.catalog.get_job(job_id) or record)
            raise
        return job_view(finished)

    def _execute_rebuild(self, job: JobRecord) -> JobRecord:
        self.indexer.begin_job(job.job_id)
        try:
            return self._execute_rebuild_claimed(job)
        finally:
            self.indexer.forget_job(job.job_id)

    def _execute_rebuild_claimed(self, job: JobRecord) -> JobRecord:
        try:
            generation = self._require_target_generation(job)
            profile = self._require_profile(generation)
            self.indexer.require_profile_usable(profile)
            policy = generation_policy(generation)
            manifest = generation_manifest(generation)
            self.vectors.ensure_collection(
                name=generation.collection_name,
                dimensions=profile.dimensions,
                distance="Cosine",
            )
            documents_total = len(manifest)
            documents_done = 0
            self.indexer.require_lease_and_renew(
                job_id=job.job_id, lease_token=job.lease_token or ""
            )
            self.indexer.checkpoint(
                job_id=job.job_id,
                lease_token=job.lease_token or "",
                state="building",
                chunks_done=0,
                chunks_total=0,
                documents_done=0,
                documents_total=documents_total,
                current_title=None,
            )
            for entry in manifest:
                # 逐册边界：核验并（到期）续租，慢册也不会在下一册被判失权
                self.indexer.require_lease_and_renew(
                    job_id=job.job_id, lease_token=job.lease_token or ""
                )
                self.indexer.raise_if_cancelled(job.job_id)
                document = self.catalog.get_document(entry.document_id)
                if document is None or document.is_deleted:
                    self._mark_skipped_deleted(
                        job, generation=generation, entry=entry, policy=policy
                    )
                    documents_done += 1
                    self.indexer.renew_lease_if_due(
                        job_id=job.job_id, lease_token=job.lease_token or ""
                    )
                    self.indexer.checkpoint(
                        job_id=job.job_id,
                        lease_token=job.lease_token or "",
                        state="building",
                        documents_done=documents_done,
                        documents_total=documents_total,
                        current_title=entry.title,
                    )
                    continue
                if document.current_revision_id != entry.document_revision_id:
                    raise _conflict(
                        "书册有效修订在重建期间发生变化，快照已失效；请重新发起重建。",
                        code="REVISION_CHANGED_DURING_REBUILD",
                    )
                if self._revision_state(generation.generation_id, entry.document_revision_id) == "ready":
                    documents_done += 1
                    continue
                revision = self.catalog.get_revision(entry.document_revision_id)
                if revision is None:
                    raise _not_found("文档修订不存在。", code="REVISION_NOT_FOUND")
                chunk_set, chunks, parsed = self.indexer.ensure_chunk_set(
                    revision=revision, policy=policy
                )
                if not parsed.normalized_text.strip() or not chunks:
                    raise _invalid(
                        f"教材《{document.title}》没有可索引文本（需要 OCR），重建已中止。",
                        code="DOCUMENT_NEEDS_OCR",
                    )
                self.catalog.upsert_generation_revision(
                    generation.generation_id,
                    revision.revision_id,
                    chunk_set.chunk_set_id,
                    state="pending",
                    expected_chunk_count=len(chunks),
                    manifest_sha256=chunk_set.manifest_sha256,
                )
                self.indexer.index_chunks(
                    job=job,
                    lease_token=job.lease_token or "",
                    generation=generation,
                    profile=profile,
                    revision=revision,
                    chunk_set=chunk_set,
                    chunks=chunks,
                    parsed=parsed,
                    document_id=document.document_id,
                    owner_id=document.owner_id,
                    document_title=document.title,
                    state_label="building",
                    documents_done=documents_done,
                    documents_total=documents_total,
                )
                self.indexer.verify_points(
                    generation=generation,
                    revision=revision,
                    chunk_set=chunk_set,
                    expected=len(chunks),
                )
                self.catalog.upsert_generation_revision(
                    generation.generation_id,
                    revision.revision_id,
                    chunk_set.chunk_set_id,
                    state="ready",
                    expected_chunk_count=len(chunks),
                    manifest_sha256=chunk_set.manifest_sha256,
                )
                documents_done += 1
                self.indexer.renew_lease_if_due(
                    job_id=job.job_id, lease_token=job.lease_token or ""
                )
                self.indexer.checkpoint(
                    job_id=job.job_id,
                    lease_token=job.lease_token or "",
                    state="building",
                    documents_done=documents_done,
                    documents_total=documents_total,
                    current_title=document.title,
                )

            self._verify_manifest_and_point_counts(generation=generation, manifest=manifest)
            self._publish_rebuild(job, generation=generation, manifest=manifest)
            return self.catalog.get_job(job.job_id) or job
        except JobCancelled as exc:
            return self.terminate_rebuild_record(
                job, "cancelled", "JOB_CANCELLED", str(exc)
            )
        except AppError as exc:
            if exc.code == "LEASE_LOST":
                # 失权 worker 绝不先改别人的代：先写终态证明记录仍属于本执行者，
                # 写完 succeeded 才 abort 目标代并释放闸门；真失权时保持 running 不动任何指针。
                logger.warning("重建任务 %s 租约失效，停止写入。", job.job_id)
                return self._handle_lost_lease(job)
            if self.indexer.cancel_requested(job.job_id):
                return self.terminate_rebuild_record(
                    job, "cancelled", "JOB_CANCELLED", "任务在执行中被取消。"
                )
            return self.terminate_rebuild_record(job, "failed", exc.code, str(exc))
        except Exception as exc:  # noqa: BLE001 - 未预期异常也要终止并释放闸门
            logger.exception("重建任务 %s 失败", job.job_id)
            return self.terminate_rebuild_record(
                job, "failed", "REBUILD_FAILED", exc.__class__.__name__
            )

    def terminate_rebuild_record(
        self, job: JobRecord, state: str, error_code: str, message: str | None
    ) -> JobRecord:
        """内部终止路径：直接对已领取的任务写状态（不重复查库）。"""
        if not job.lease_token:
            return self.catalog.get_job(job.job_id) or job
        self._abort_target_and_release_gate(job.job_id, job.target_generation_id)
        try:
            finished = self.catalog.finish_job(
                job.job_id,
                lease_token=job.lease_token,
                state=state,
                error_code=error_code,
                error_message=(message or "")[:500] or None,
            )
        except AppError as exc:
            if exc.code == "LEASE_LOST":
                return self.catalog.get_job(job.job_id) or job
            raise
        return finished

    def _require_target_generation(self, job: JobRecord) -> GenerationRecord:
        if not job.target_generation_id:
            raise _not_found("任务缺少目标索引代。", code="GENERATION_NOT_FOUND")
        generation = self.catalog.get_generation(job.target_generation_id)
        if generation is None:
            raise _not_found("索引代不存在。", code="GENERATION_NOT_FOUND")
        if generation.state == "aborted":
            raise _conflict("目标索引代已终止。", code="GENERATION_ABORTED")
        return generation

    def _require_profile(self, generation: GenerationRecord) -> ProfileRecord:
        profile = self.catalog.get_embedding_profile(generation.profile_id)
        if profile is None:
            raise _not_found("Embedding 配置不存在。", code="PROFILE_NOT_FOUND")
        return profile

    def _revision_state(self, generation_id: str, revision_id: str) -> str | None:
        for record in self.catalog.list_generation_revisions(generation_id):
            if record.document_revision_id == revision_id:
                return record.state
        return None

    def _mark_skipped_deleted(
        self,
        job: JobRecord,
        *,
        generation: GenerationRecord,
        entry: ManifestEntry,
        policy,
    ) -> None:
        """已删除书册：写 skipped_deleted 标记（零块分块集），绝不重建其向量。"""
        revision = self.catalog.get_revision(entry.document_revision_id)
        if revision is None:
            return
        fingerprint = chunk_policy_fingerprint(policy)
        chunk_set = self.catalog.find_chunk_set(revision.revision_id, fingerprint)
        if chunk_set is None:
            chunk_set = self.catalog.create_chunk_set(
                revision.revision_id,
                policy_fingerprint=fingerprint,
                manifest_sha256=chunk_manifest_sha256([]),
                chunks=[],
            )
        self.catalog.upsert_generation_revision(
            generation.generation_id,
            revision.revision_id,
            chunk_set.chunk_set_id,
            state="skipped_deleted",
            expected_chunk_count=0,
            manifest_sha256=chunk_set.manifest_sha256,
        )
        logger.info(
            "重建跳过已删除书册：document=%s revision=%s",
            entry.document_id,
            entry.document_revision_id,
        )

    def _verify_manifest_and_point_counts(
        self, *, generation: GenerationRecord, manifest: tuple[ManifestEntry, ...]
    ) -> None:
        """逐条对账：每个 ready 修订的向量条数必须等于登记的 expected_chunk_count。"""
        links = {
            record.document_revision_id: record
            for record in self.catalog.list_generation_revisions(generation.generation_id)
        }
        for entry in manifest:
            link = links.get(entry.document_revision_id)
            if link is None or link.state != "ready":
                continue
            revision = self.catalog.get_revision(entry.document_revision_id)
            chunk_set = self.catalog.get_chunk_set(link.chunk_set_id)
            if revision is None or chunk_set is None:
                raise _conflict(
                    "重建对账缺少修订或分块集记录。",
                    code="REBUILD_INCOMPLETE",
                )
            self.indexer.verify_points(
                generation=generation,
                revision=revision,
                chunk_set=chunk_set,
                expected=link.expected_chunk_count,
            )

    def _publish_rebuild(
        self, job: JobRecord, *, generation: GenerationRecord, manifest: tuple[ManifestEntry, ...]
    ) -> None:
        lease_token = job.lease_token or ""
        # 发布前核验并（到期）续租：长重建的最后阶段也不会失权
        self.indexer.require_lease_and_renew(job_id=job.job_id, lease_token=lease_token)
        self.indexer.raise_if_cancelled(job.job_id)
        state = self.catalog.catalog_state()
        if state.rebuild_job_id != job.job_id:
            raise _conflict("重建闸门已不属于本任务，拒绝发布。", code="REBUILD_GATE_LOST")
        if state.active_generation_id != job.base_generation_id:
            raise _conflict(
                "当前索引代已变化，拒绝用旧快照发布。", code="BASE_GENERATION_CHANGED"
            )
        frozen = {entry.document_revision_id for entry in manifest}
        expected = {entry.document_revision_id for entry in self._snapshot_manifest()}
        if not expected <= frozen:
            raise _conflict(
                "重建期间有教材发布，快照未覆盖当前修订；请重新发起重建。",
                code="REBUILD_INCOMPLETE",
            )
        links = {
            record.document_revision_id: record
            for record in self.catalog.list_generation_revisions(generation.generation_id)
        }
        for revision_id in expected:
            link = links.get(revision_id)
            if link is None or link.state != "ready":
                raise _conflict(
                    "仍有教材未完成构建，拒绝发布。", code="REBUILD_INCOMPLETE"
                )
        self.catalog.publish_generation(generation.generation_id)
        self.catalog.set_active_generation(generation.generation_id)
        self.catalog.finish_job(
            job.job_id, lease_token=lease_token, state="succeeded", error_message=None
        )
        if self.catalog.catalog_state().rebuild_job_id == job.job_id:
            self.catalog.set_rebuild_job(None)

    # ------------------------------------------------------------------ 清理

    def cleanup_document(self, document_id: str) -> int:
        """删除已停用书册在各代中的向量；失败保留队列项（逻辑删除已生效）。"""
        revisions = self.catalog.list_document_revisions(document_id)
        revision_ids = tuple(record.revision_id for record in revisions)
        if not revision_ids:
            self.catalog.clear_cleanup(document_id)
            return 0
        for generation in self.catalog.list_generations():
            try:
                self.vectors.delete_by_filter(
                    name=generation.collection_name,
                    allowed=AllowedFilter(revision_ids=revision_ids),
                )
            except AppError as exc:
                if exc.code in ("QDRANT_COLLECTION_MISSING",):
                    continue
                raise
        self.catalog.clear_cleanup(document_id)
        return len(revision_ids)

    def run_cleanup_queue(self, *, limit: int = 50) -> dict[str, int]:
        """处理清理队列：逐个删除向量，成功出队；失败保留并停止本轮（可重试）。"""
        removed = 0
        cleared = 0
        for document_id in self.catalog.pending_cleanup(limit=limit):
            removed += self.cleanup_document(document_id)
            cleared += 1
        return {"documents": cleared, "revisions": removed}


def settings_url_normalized(settings: Any) -> str:
    return str(settings.embedding_base_url)
