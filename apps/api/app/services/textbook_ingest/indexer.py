"""文档修订 → 向量库：分块集、批量嵌入、校验、upsert 与 checkpoint。

设计要点：
- 嵌入与 upsert 都在 SQL 事务外执行；每次 checkpoint / 发布前先核验租约与取消请求。
- 批次固定 8；上游报 OOM 或输出非法且批 >1 时缩批 8→4→2→1，**不换模型**。
- 短暂网络错误（EMBEDDING_UNAVAILABLE / QDRANT_UNAVAILABLE）最多重试 3 次，
  退避 2/10/30 秒（sleep 可注入，测试不真实等待）。
- 身份（digest）变化、维度错误、指纹损坏不重试。
- point id 由 (generation, chunk_set, ordinal, text_sha256) 决定：崩溃重做覆盖同一 id，
  不会产生重复向量。
- **送模型的文本是该代登记的清洗版本投影后的索引输入文本**（RAG-QUALITY v1.1 §3.2）：
  ``document_prefix + 上下文头 + projection.text``；payload 里的 ``text_sha256`` 仍是
  **原文切片**散列，另有 ``textProjectionVersion`` / ``indexTextSha256`` 描述索引输入。
  旧代（``raw-v0``）投影是恒等变换，历史行为不变。
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from typing import Any

from app.core.exceptions import AppError
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import (
    ChunkInput,
    ChunkSetRecord,
    GenerationRecord,
    JobRecord,
    ProfileRecord,
    RevisionRecord,
)
from app.repositories.vector_store.base import (
    PAYLOAD_CHUNK_SET_ID,
    PAYLOAD_DOCUMENT_ID,
    PAYLOAD_GENERATION_ID,
    PAYLOAD_ORDINAL,
    PAYLOAD_OWNER_ID,
    PAYLOAD_REGION,
    PAYLOAD_REVISION_ID,
    PAYLOAD_TEXT_SHA256,
    AllowedFilter,
    VectorPoint,
    point_id_for,
)
from app.services.document_parsing.chunking import (
    ChunkPolicy,
    chunk_document,
    chunk_manifest_sha256,
    chunk_policy_fingerprint,
    chunk_projection,
)
from app.services.document_parsing.parser import ParsedDocument, parsed_from_source_map
from app.services.textbook_ingest.blobs import BlobStore, sha256_text
from app.services.textbook_ingest.generation_doc import generation_policy
from app.services.textbook_ingest.jobs import DEFAULT_RENEW_SECONDS, LeaseKeeper

#: 索引输入文本的清洗版本（与 :mod:`app.services.text_projection` 的版本常量同源）
PAYLOAD_TEXT_PROJECTION_VERSION = "textProjectionVersion"
#: 索引输入文本（清洗文本）的 sha256；与原文切片散列 ``text_sha256`` 是两个不同事实
PAYLOAD_INDEX_TEXT_SHA256 = "indexTextSha256"

DEFAULT_BATCH_SIZE = 8
DEFAULT_RETRY_BACKOFF = (2.0, 10.0, 30.0)
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LEASE_SECONDS = 90
_NO_RETRY_CODES = frozenset(
    {
        "EMBEDDING_MODEL_CHANGED",
        "EMBEDDING_DIMENSION_MISMATCH",
        "EMBEDDING_MODEL_MISSING",
        "EMBEDDING_MODEL_NOT_EMBEDDING",
        "EMBEDDING_INVALID_OUTPUT",
        "SOURCE_HASH_MISMATCH",
        "GENERATION_DOC_CORRUPT",
        "CHUNK_POLICY_CORRUPT",
    }
)


class JobCancelled(Exception):
    """worker 在 checkpoint 前发现取消请求；由调用方落为 cancelled 状态。"""


class DocumentIndexer:
    def __init__(
        self,
        catalog: TextbookCatalog,
        embeddings: Any,
        vectors: Any,
        blobs: BlobStore,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        sleep=time.sleep,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_backoff: Sequence[float] = DEFAULT_RETRY_BACKOFF,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        renew_seconds: float = DEFAULT_RENEW_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.catalog = catalog
        self.embeddings = embeddings
        self.vectors = vectors
        self.blobs = blobs
        self.batch_size = max(1, int(batch_size))
        self.sleep = sleep
        self.max_attempts = max(0, int(max_attempts))
        self.retry_backoff = tuple(retry_backoff) or (0.0,)
        self.lease_seconds = int(lease_seconds)
        self.leases = LeaseKeeper(
            catalog,
            renew_seconds=renew_seconds,
            lease_seconds=self.lease_seconds,
            monotonic=monotonic,
        )

    # ------------------------------------------------------------------ 租约

    def begin_job(self, job_id: str) -> None:
        """任务领取后锚定续租计时（服务在开始执行时调用）。"""
        self.leases.begin(job_id)

    def forget_job(self, job_id: str) -> None:
        self.leases.forget(job_id)

    def renew_lease_if_due(
        self, *, job_id: str, lease_token: str, force: bool = False
    ) -> bool:
        """到期续租；失败抛 ``LEASE_LOST``（调用方必须立即停止写入）。"""
        return self.leases.renew_if_due(
            job_id=job_id, lease_token=lease_token, force=force
        )

    def require_lease(self, job_id: str, lease_token: str) -> JobRecord:
        return self.catalog.require_lease(job_id, lease_token)

    def require_lease_and_renew(
        self, *, job_id: str, lease_token: str, force: bool = False
    ) -> JobRecord:
        """先核验租约仍属于本执行者，再按阈值续租（长任务不会中途失权）。"""
        record = self.require_lease(job_id, lease_token)
        self.renew_lease_if_due(job_id=job_id, lease_token=lease_token, force=force)
        return record

    def checkpoint(
        self,
        *,
        job_id: str,
        lease_token: str,
        state: str,
        chunks_done: int | None = None,
        chunks_total: int | None = None,
        documents_done: int | None = None,
        documents_total: int | None = None,
        current_title: str | None = None,
    ) -> None:
        """写 checkpoint；保留取消请求等既有键，避免覆盖控制信号。"""
        record = self.catalog.get_job(job_id)
        payload: dict[str, Any] = dict(record.checkpoint) if record is not None else {}
        payload["state"] = state
        if chunks_done is not None:
            payload["chunksDone"] = chunks_done
        if chunks_total is not None:
            payload["chunksTotal"] = chunks_total
        if documents_done is not None:
            payload["documentsDone"] = documents_done
        if documents_total is not None:
            payload["documentsTotal"] = documents_total
        if current_title is not None:
            payload["currentTitle"] = current_title
        self.catalog.checkpoint_job(job_id, lease_token=lease_token, checkpoint=payload)

    def cancel_requested(self, job_id: str) -> bool:
        record = self.catalog.get_job(job_id)
        return bool(record is not None and record.checkpoint.get("cancelRequested") is True)

    def raise_if_cancelled(self, job_id: str) -> None:
        if self.cancel_requested(job_id):
            raise JobCancelled(f"任务 {job_id} 已请求取消。")

    # -------------------------------------------------------------- 修订内容

    def parse_revision(self, revision: RevisionRecord) -> ParsedDocument:
        text = self.blobs.read_text(area="normalized", blob_id=revision.normalized_blob_id)
        if len(text) != revision.char_count or sha256_text(text) != revision.normalized_text_sha256:
            raise AppError(
                "规范化文本与修订登记不符（长度或指纹不一致）。",
                code="SOURCE_HASH_MISMATCH",
                status_code=409,
            )
        payload = self.blobs.read_json(area="normalized", blob_id=revision.source_map_blob_id)
        parsed = parsed_from_source_map(payload, normalized_text=text)
        if parsed.char_count != revision.char_count:
            raise AppError(
                "来源映射与修订长度不一致。",
                code="SOURCE_MAP_CORRUPT",
                status_code=500,
            )
        return parsed

    def ensure_chunk_set(
        self, *, revision: RevisionRecord, policy: ChunkPolicy
    ) -> tuple[ChunkSetRecord, list[ChunkInput], ParsedDocument]:
        """同修订 + 同策略只存在一个分块集：已存在时直接复用（含崩溃恢复）。"""
        fingerprint = chunk_policy_fingerprint(policy)
        parsed = self.parse_revision(revision)
        existing = self.catalog.find_chunk_set(revision.revision_id, fingerprint)
        if existing is not None:
            records = self.catalog.list_chunks(existing.chunk_set_id)
            if len(records) != existing.chunk_count:
                raise AppError(
                    "分块集与 chunks 行数不一致。",
                    code="SOURCE_MAP_CORRUPT",
                    status_code=500,
                )
            chunks = [
                ChunkInput(
                    ordinal=record.ordinal,
                    char_start=record.char_start,
                    char_end=record.char_end,
                    region=record.region,
                    chapter_path=record.chapter_path,
                    text_sha256=record.text_sha256,
                    legacy_chunk_id=record.legacy_chunk_id,
                )
                for record in records
            ]
            return existing, chunks, parsed
        chunks = chunk_document(parsed, policy=policy)
        manifest = chunk_manifest_sha256(chunks)
        chunk_set = self.catalog.create_chunk_set(
            revision.revision_id,
            policy_fingerprint=fingerprint,
            manifest_sha256=manifest,
            chunks=chunks,
        )
        return chunk_set, chunks, parsed

    # ------------------------------------------------------------------ 嵌入

    def require_profile_usable(self, profile: ProfileRecord) -> None:
        if profile.retired_at is not None:
            raise AppError(
                "该 Embedding 配置已退役，不能用于新的入库或重建。",
                code="PROFILE_RETIRED",
                status_code=409,
            )

    def require_digest(self, profile: ProfileRecord) -> str:
        """核对模型身份；同名 tag 的 digest 变化一律拒绝继续。"""
        digest = self.embeddings.manifest_digest(profile.model_name)
        if digest != profile.model_manifest_digest:
            raise AppError(
                "模型清单 digest 与配置不一致，禁止继续使用错误模型空间。",
                code="EMBEDDING_MODEL_CHANGED",
                status_code=409,
            )
        return digest

    def embed_batch(self, *, profile: ProfileRecord, texts: list[str]) -> tuple[list[list[float]], int]:
        """嵌入一批文本；返回 (向量, 生效批大小)。"""
        size = max(1, len(texts))
        attempt = 0
        pending = list(texts)
        collected: list[list[float]] = []
        while pending:
            window = pending[:size]
            try:
                vectors = self.embeddings.embed(model=profile.model_name, texts=list(window))
            except AppError as exc:
                if exc.code in {"EMBEDDING_OUT_OF_MEMORY", "EMBEDDING_INVALID_OUTPUT"} and len(window) > 1:
                    size = max(1, len(window) // 2)
                    attempt = 0
                    continue
                if exc.code in _NO_RETRY_CODES or not exc.retryable:
                    raise
                if attempt >= self.max_attempts:
                    raise
                self.sleep(self.retry_backoff[min(attempt, len(self.retry_backoff) - 1)])
                attempt += 1
                continue
            self._validate_vectors(profile, vectors, expected=len(window))
            collected.extend(vectors)
            pending = pending[len(window):]
            attempt = 0
        return collected, size

    def _validate_vectors(
        self, profile: ProfileRecord, vectors: object, *, expected: int
    ) -> None:
        if not isinstance(vectors, list) or len(vectors) != expected:
            raise AppError(
                "Embedding 返回条数与输入不一致，拒绝写入向量库。",
                code="EMBEDDING_INVALID_OUTPUT",
                status_code=502,
            )
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != profile.dimensions:
                raise AppError(
                    f"Embedding 维度与配置 {profile.dimensions} 不一致，禁止继续。",
                    code="EMBEDDING_DIMENSION_MISMATCH",
                    status_code=409,
                )
            for value in vector:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    raise AppError(
                        "Embedding 输出包含非有限值。",
                        code="EMBEDDING_INVALID_OUTPUT",
                        status_code=502,
                    )

    def embedding_text(
        self,
        *,
        profile: ProfileRecord,
        document_title: str,
        index_text: str,
        chunk: ChunkInput,
    ) -> str:
        """送模型的文本 = 文档前缀 + 上下文头 + **清洗后的索引输入文本**。

        ``index_text`` 由 :func:`chunk_projection` 按该代登记的清洗版本派生；原文切片
        不再直接送模型（图片 Markdown 不进入向量空间）。
        """
        header = " > ".join(
            part for part in (document_title, *chunk.chapter_path) if part
        )
        if profile.document_prefix or header:
            return f"{profile.document_prefix}{header}\n{index_text}"
        return index_text

    def payload_for(
        self,
        *,
        generation: GenerationRecord,
        revision: RevisionRecord,
        chunk_set: ChunkSetRecord,
        document_id: str,
        owner_id: str,
        chunk: ChunkInput,
        text_projection_version: str,
        index_text_sha256: str,
    ) -> dict:
        """point payload：原有字段含义不变（``text_sha256`` 仍是原文切片散列），新增两个字段。"""
        return {
            PAYLOAD_GENERATION_ID: generation.generation_id,
            PAYLOAD_DOCUMENT_ID: document_id,
            PAYLOAD_REVISION_ID: revision.revision_id,
            PAYLOAD_CHUNK_SET_ID: chunk_set.chunk_set_id,
            PAYLOAD_ORDINAL: chunk.ordinal,
            PAYLOAD_OWNER_ID: owner_id,
            PAYLOAD_REGION: chunk.region,
            PAYLOAD_TEXT_SHA256: chunk.text_sha256,
            PAYLOAD_TEXT_PROJECTION_VERSION: text_projection_version,
            PAYLOAD_INDEX_TEXT_SHA256: index_text_sha256,
        }

    def upsert_points(self, *, collection: str, points: list[VectorPoint]) -> None:
        attempt = 0
        while True:
            try:
                self.vectors.upsert(name=collection, points=points, wait=True)
                return
            except AppError as exc:
                if exc.retryable and attempt < self.max_attempts:
                    self.sleep(self.retry_backoff[min(attempt, len(self.retry_backoff) - 1)])
                    attempt += 1
                    continue
                raise

    # -------------------------------------------------------------- 批次主循环

    def index_chunks(
        self,
        *,
        job: JobRecord,
        lease_token: str,
        generation: GenerationRecord,
        profile: ProfileRecord,
        revision: RevisionRecord,
        chunk_set: ChunkSetRecord,
        chunks: Sequence[ChunkInput],
        parsed: ParsedDocument,
        document_id: str,
        owner_id: str,
        document_title: str,
        state_label: str = "embedding",
        documents_done: int | None = None,
        documents_total: int | None = None,
    ) -> int:
        """分批嵌入并写入向量库，每批 checkpoint；返回已写入块数。

        每个批次的两端都做租约检查与（到期）续租：批次开始前核验+续租，
        upsert 之后、checkpoint 之前再续租一次；任何一次续租失败立即抛
        ``LEASE_LOST`` 停止写入，不再产生新批次。

        索引输入文本按**该索引代登记的清洗版本**投影（旧代 = ``raw-v0`` 恒等投影，
        新代 = ``rag-readable-v1`` 清洗文本）；块清单已排除清洗后为空的块，
        所以点数与 ``expected_chunk_count`` 永远一致。
        """
        self.require_profile_usable(profile)
        policy = generation_policy(generation)
        total = len(chunks)
        batch_size = self.batch_size
        index = 0
        while index < total:
            self.require_lease_and_renew(job_id=job.job_id, lease_token=lease_token)
            self.raise_if_cancelled(job.job_id)
            batch = list(chunks[index:index + batch_size])
            projections = [
                chunk_projection(chunk, parsed.normalized_text, policy) for chunk in batch
            ]
            texts = [
                self.embedding_text(
                    profile=profile,
                    document_title=document_title,
                    index_text=projection.text,
                    chunk=chunk,
                )
                for chunk, projection in zip(batch, projections)
            ]
            self.require_digest(profile)
            vectors, batch_size = self.embed_batch(profile=profile, texts=texts)
            self.require_digest(profile)
            points = [
                VectorPoint(
                    point_id=point_id_for(
                        generation.generation_id,
                        chunk_set.chunk_set_id,
                        chunk.ordinal,
                        chunk.text_sha256,
                    ),
                    vector=vector,
                    payload=self.payload_for(
                        generation=generation,
                        revision=revision,
                        chunk_set=chunk_set,
                        document_id=document_id,
                        owner_id=owner_id,
                        chunk=chunk,
                        text_projection_version=projection.version,
                        index_text_sha256=sha256_text(projection.text),
                    ),
                )
                for chunk, projection, vector in zip(batch, projections, vectors)
            ]
            self.upsert_points(collection=generation.collection_name, points=points)
            index += len(batch)
            # 批次之后、checkpoint 之前续租：慢批次也不会让下一批失权
            self.renew_lease_if_due(job_id=job.job_id, lease_token=lease_token)
            self.checkpoint(
                job_id=job.job_id,
                lease_token=lease_token,
                state=state_label,
                chunks_done=index,
                chunks_total=total,
                documents_done=documents_done,
                documents_total=documents_total,
                current_title=document_title,
            )
        return index

    def verify_points(
        self,
        *,
        generation: GenerationRecord,
        revision: RevisionRecord,
        chunk_set: ChunkSetRecord,
        expected: int,
    ) -> int:
        actual = self.vectors.count(
            name=generation.collection_name,
            allowed=AllowedFilter(
                revision_ids=(revision.revision_id,),
                chunk_set_ids=(chunk_set.chunk_set_id,),
            ),
        )
        if actual != expected:
            raise AppError(
                f"向量库对账失败：期望 {expected} 条，实际 {actual} 条；发布已中止。",
                code="PUBLISH_POINT_COUNT_MISMATCH",
                status_code=409,
                retryable=True,
            )
        return actual
