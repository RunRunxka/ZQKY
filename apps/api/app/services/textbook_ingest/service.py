"""教材入库：导入草稿、封存不可变修订、入库任务、取消/重试与崩溃恢复。

不变量：
- 解析、嵌入、向量库调用都在 SQL 事务外执行（目录层只做 SQL）；
- 未完成核验前不发布：``generation_revisions`` 保持 ``pending``，``documents.current_revision_id`` 不动；
- 失败/取消不改 ``active_generation_id``，也不改已发布修订；
- 幂等：同一 ``submissionId`` 返回同一任务；相同键不同载荷返回 409；
- 崩溃重做使用相同 point id（uuid5），重复 upsert 不产生重复向量；
- 任务运行期间按 ≤20 秒阈值续租（见 ``jobs.LeaseKeeper``），失权立即停止写入。

书册身份（``origin_key``）规则（固定、版本化）::

    origin_key = f"{owner_id}:{sha256(原件字节)}"

- ``owner_id`` 由服务端按所选逻辑库推导（只选基础库 → ``system``，其余 → 本机用户）；
- sha256 取上传原件的字节指纹（即内容寻址的 ``uploaded_blob_id``）：**内容相同即同一书册身份**；
- 仅在**新建书册**路径写入；显式 ``targetDocumentId`` 的更新路径沿用目标书册既有 ``origin_key``，不改写；
- 命中未删除的既有书册 → 不新建书册，改为在该书册上追加不可变修订（等价更新），
  并在草稿 ``warnings`` 如实提示「检测到相同内容的既有书册，已作为该书册的新修订」；
- 命中已删除的既有书册 → 409 ``DOCUMENT_ORIGIN_DELETED``：不自动复活，也不另建重复册；
- 同一内容换库（owner 推导结果不同）视为不同 owner 的身份，会产生各自独立的两册（身份按 owner 分区）。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.core.exceptions import AppError
from app.providers.embeddings.fingerprint import canonical_json, sha256_hex
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import (
    ImportRecord,
    JobRecord,
    RevisionRecord,
)
from app.schemas.textbook import (
    MAX_UPLOAD_BYTES,
    SUPPORTED_SUFFIXES,
    DocumentMetadataInput,
    ImportDraftView,
    JobView,
    SourceSpanView,
)
from app.services.document_parsing.chunking import (
    DEFAULT_CHUNK_POLICY,
    chunk_policy_fingerprint,
    chunk_policy_json,
)
from app.services.document_parsing.parser import (
    PARSER_VERSION,
    ParsedDocument,
    source_map_payload,
)
from app.services.document_parsing.regions import split_regions
from app.services.textbook_ingest.blobs import BlobStore, sha256_text
from app.services.textbook_ingest.generation_doc import generation_policy
from app.services.textbook_ingest.indexer import DocumentIndexer, JobCancelled
from app.services.textbook_ingest.jobs import (
    DEFAULT_RENEW_SECONDS,
    recoverable_jobs,
    request_cancel,
    try_fail_lost_lease,
)
from app.services.textbook_ingest.source_access import read_source_span
from app.services.textbook_ingest.views import (
    chunk_preview,
    import_draft_view,
    job_view,
    metadata_input_from_record,
)

logger = logging.getLogger("zhiqikeyuan.api.textbook_ingest")

DEFAULT_WORKER_ID = "ingest-worker-1"
DEFAULT_LEASE_SECONDS = 90
DEFAULT_OWNER_ID = "local-user"
#: 命中同一来源键（内容相同）时的草稿警告文案
ORIGIN_REUSE_WARNING = "检测到相同内容的既有书册，已作为该书册的新修订（不新建重复书册）。"
_ARTIFACT_FIELDS = (
    "normalizedBlobId",
    "normalizedTextSha256",
    "sourceMapBlobId",
    "parserVersion",
    "charCount",
)


def origin_key_for(owner_id: str, original_file_sha256: str) -> str:
    """书册来源键：``{owner_id}:{原件 sha256}``；内容相同即同一书册身份。"""
    owner = (owner_id or "").strip()
    digest = (original_file_sha256 or "").strip()
    if not owner or not digest:
        raise _invalid("书册来源键需要 owner_id 与原件 sha256。")
    return f"{owner}:{digest}"


def _append_warning(values: object, warning: str) -> list[str]:
    items = [item for item in values if isinstance(item, str)] if isinstance(values, list) else []
    if warning not in items:
        items.append(warning)
    return items


def _invalid(message: str, *, code: str = "INVALID_REQUEST") -> AppError:
    return AppError(message, code=code, status_code=422)


def _conflict(message: str, *, code: str, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=409, retryable=retryable)


def _not_found(message: str, *, code: str) -> AppError:
    return AppError(message, code=code, status_code=404)


class IngestService:
    def __init__(
        self,
        catalog: TextbookCatalog,
        parser: Callable[..., ParsedDocument],
        chunker: Callable[..., list],
        embeddings: Any,
        vectors: Any,
        settings: Any,
        *,
        batch_size: int = 8,
        worker_id: str = DEFAULT_WORKER_ID,
        sleep: Callable[[float], None] = time.sleep,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        renew_seconds: float = DEFAULT_RENEW_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
        max_attempts: int = 3,
        retry_backoff: tuple[float, ...] = (2.0, 10.0, 30.0),
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> None:
        self.catalog = catalog
        self.parser = parser
        self.chunker = chunker
        self.embeddings = embeddings
        self.vectors = vectors
        self.settings = settings
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.owner_id = owner_id
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
        self._running = threading.Lock()
        self._commit_lock = threading.Lock()

    # ------------------------------------------------------------------ 生命周期

    def close(self) -> None:
        """无长连接需要关闭；保留方法以便统一生命周期调用。"""
        return None

    # -------------------------------------------------------------------- 导入

    def create_import(
        self,
        *,
        file_name: str,
        data: bytes,
        metadata: dict | None = None,
        target_document_id: str | None = None,
        expected_current_revision_id: str | None = None,
        confirm_metadata: bool | None = None,
        owner_id: str | None = None,
    ) -> ImportDraftView:
        """字节入口（测试与程序内调用）；路由入口使用 ``create_import_from_path``。"""
        self.blobs.ensure_dirs()
        if len(data) > MAX_UPLOAD_BYTES:
            raise AppError(
                f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
                code="DOCUMENT_TOO_LARGE",
                status_code=413,
            )
        staged = self.blobs.stage_temp_path()
        try:
            staged.write_bytes(data)
            return self.create_import_from_path(
                file_name=file_name,
                staged_path=staged,
                metadata=metadata,
                target_document_id=target_document_id,
                expected_current_revision_id=expected_current_revision_id,
                confirm_metadata=confirm_metadata,
                owner_id=owner_id,
            )
        finally:
            staged.unlink(missing_ok=True)

    def create_import_from_path(
        self,
        *,
        file_name: str,
        staged_path: Path,
        metadata: dict | None = None,
        target_document_id: str | None = None,
        expected_current_revision_id: str | None = None,
        confirm_metadata: bool | None = None,
        owner_id: str | None = None,
    ) -> ImportDraftView:
        name = (file_name or "").strip()
        if not name:
            raise _invalid("上传文件名不能为空。")
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise _invalid(
                f"不支持的教材文件类型「{suffix or name}」：仅支持 .md / .txt / .pdf / .docx。",
                code="UNSUPPORTED_DOCUMENT_FORMAT",
            )
        source = Path(staged_path)
        if source.is_file() and source.stat().st_size > MAX_UPLOAD_BYTES:
            raise AppError(
                f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
                code="DOCUMENT_TOO_LARGE",
                status_code=413,
            )
        self.blobs.ensure_dirs()
        blob_id, size = self.blobs.stage_file(source)

        validated_metadata, confirmed = self._prepare_metadata(
            metadata,
            target_document_id=target_document_id,
            confirm_metadata=confirm_metadata,
        )
        expected_revision_id = expected_current_revision_id
        if expected_revision_id is None and target_document_id:
            document = self.catalog.require_live_document(target_document_id)
            expected_revision_id = document.current_revision_id

        state = "needs_review"
        error_code: str | None = None
        warnings: list[str] = []
        artifacts: dict | None = None
        try:
            parsed = self.parser(
                path=self.blobs.path_of("staging", blob_id),
                file_name=name,
                parser_version=PARSER_VERSION,
                allow_empty_text=True,
            )
            policy = DEFAULT_CHUNK_POLICY
            chunks = list(self.chunker(parsed, policy=policy))
            artifacts = self._store_artifacts(parsed, chunks, policy, confirmed=confirmed)
            warnings.extend(parsed.warnings)
        except AppError as exc:
            state = "failed"
            error_code = exc.code
            warnings.append(str(exc))
        except Exception as exc:  # noqa: BLE001 - 解析层未预期异常也要留痕，不伪装成功
            state = "failed"
            error_code = "DOCUMENT_PARSE_FAILED"
            warnings.append(f"解析失败：{exc.__class__.__name__}")

        record = self.catalog.create_import(
            owner_id=owner_id or self.owner_id,
            uploaded_file_name=name,
            uploaded_bytes=size,
            uploaded_blob_id=blob_id,
            target_document_id=target_document_id,
            expected_current_revision_id=expected_revision_id,
            metadata_json=validated_metadata,
            parsed_artifacts_json=artifacts,
            warnings=warnings,
            state=state,
        )
        if error_code is not None:
            record = self.catalog.update_import(
                record.import_id,
                expected_revision=record.revision,
                error_code=error_code,
            )
        return self._build_import_view(record)

    def get_import_view(self, import_id: str) -> ImportDraftView:
        record = self.catalog.get_import(import_id)
        if record is None:
            raise _not_found("导入草稿不存在。", code="IMPORT_NOT_FOUND")
        return self._build_import_view(record)

    def list_import_views(self, *, limit: int = 50) -> list[ImportDraftView]:
        return [
            self._build_import_view(record)
            for record in self.catalog.list_imports(limit=limit)
        ]

    def update_import_metadata(
        self, import_id: str, *, expected_revision: int, metadata: dict
    ) -> ImportDraftView:
        record = self.catalog.get_import(import_id)
        if record is None:
            raise _not_found("导入草稿不存在。", code="IMPORT_NOT_FOUND")
        if record.state not in ("uploaded", "needs_review", "failed"):
            raise _conflict(
                f"草稿当前状态（{record.state}）不允许修改分类。",
                code="IMPORT_NOT_EDITABLE",
            )
        validated = self._validate_metadata(metadata)
        artifacts = dict(record.parsed_artifacts or {})
        artifacts["metadataConfirmed"] = True
        state = "failed" if record.state == "failed" else "needs_review"
        updated = self.catalog.update_import(
            import_id,
            expected_revision=expected_revision,
            metadata_json=validated.model_dump(),
            parsed_artifacts_json=artifacts,
            state=state,
        )
        return self._build_import_view(updated)

    # -------------------------------------------------------------------- 提交

    def commit_import(
        self,
        import_id: str,
        *,
        expected_revision: int,
        submission_id: str,
        library_ids: list[str],
        acknowledge_warnings: bool = False,
    ) -> JobView:
        record = self.catalog.get_import(import_id)
        if record is None:
            raise _not_found("导入草稿不存在。", code="IMPORT_NOT_FOUND")
        submission = (submission_id or "").strip()
        if len(submission) < 8:
            raise _invalid("submit 幂等键至少 8 个字符。")
        libraries = self._validate_libraries(library_ids)

        existing = self.catalog.find_job_by_key(submission)
        if existing is not None:
            if existing.kind != "ingest":
                raise _conflict(
                    "同一幂等键已用于其他类型任务。", code="IDEMPOTENCY_CONFLICT"
                )
            if existing.request_fingerprint != self._request_fingerprint(record, libraries):
                raise _conflict(
                    "同一幂等键已登记不同载荷的入库任务。", code="IDEMPOTENCY_CONFLICT"
                )
            return job_view(existing)

        # 单进程内串行化"校验 → 封存 → 建任务"，避免同一书册并发产生两个发布任务
        with self._commit_lock:
            return self._commit_locked(
                import_id=import_id,
                record=record,
                expected_revision=expected_revision,
                submission=submission,
                libraries=libraries,
                acknowledge_warnings=acknowledge_warnings,
            )

    def _commit_locked(
        self,
        *,
        import_id: str,
        record: ImportRecord,
        expected_revision: int,
        submission: str,
        libraries: list[str],
        acknowledge_warnings: bool,
    ) -> JobView:
        # 锁内重读草稿：并发 PATCH 会推进 revision，必须用最新快照校验与封存
        fresh = self.catalog.get_import(import_id)
        if fresh is not None:
            record = fresh
        if record.revision != expected_revision:
            raise _conflict(
                f"导入草稿已被其他操作更新（当前 revision={record.revision}），请刷新后重试。",
                code="REVISION_CONFLICT",
            )
        if record.state == "failed":
            raise _invalid(
                "该草稿解析失败，不能提交入库；请重新上传或修正文件。",
                code="IMPORT_PARSE_FAILED",
            )
        if record.state != "needs_review":
            raise _conflict(
                f"草稿当前状态（{record.state}）不允许提交。",
                code="IMPORT_NOT_COMMITTABLE",
            )
        artifacts = dict(record.parsed_artifacts or {})
        if artifacts.get("needsOcr"):
            raise _invalid(
                "该文件没有可提取的文本层，无法生成教材索引；请先做 OCR。",
                code="DOCUMENT_NEEDS_OCR",
            )
        if record.metadata is None or not artifacts.get("metadataConfirmed"):
            raise _invalid(
                "提交前必须先确认教材分类信息。",
                code="METADATA_NOT_CONFIRMED",
            )
        warnings = self._draft_warnings(record, artifacts)
        if warnings and not acknowledge_warnings:
            raise _invalid(
                "解析存在警告，提交前需要显式确认。",
                code="WARNINGS_NOT_ACKNOWLEDGED",
            )

        catalog_state = self.catalog.catalog_state()
        if catalog_state.rebuild_job_id is not None:
            raise _conflict(
                "正在重建索引，暂不能发布新入库；草稿已保留，可稍后重试。",
                code="INDEX_REBUILD_IN_PROGRESS",
            )
        generation_id = catalog_state.active_generation_id
        if generation_id is None:
            raise _conflict("当前还没有已发布的教材索引代。", code="INDEX_NOT_READY")
        generation = self.catalog.get_generation(generation_id)
        if generation is None or generation.state != "ready":
            raise _conflict("当前索引代未就绪。", code="INDEX_NOT_READY")
        self.indexer.require_profile_usable(self._require_profile(generation))

        document_id, revision, metadata_revision_id = self._seal_revision(record, libraries)
        if record.expected_current_revision_id is not None:
            current = self.catalog.require_live_document(document_id)
            if current.current_revision_id != record.expected_current_revision_id:
                raise _conflict(
                    "该书册的有效修订已变化，拒绝把新修订接到旧基线上；请刷新后重试。",
                    code="REVISION_CONFLICT",
                )
        self._require_no_active_publish(document_id)

        sealed = self.catalog.get_import(import_id) or record
        job = self.catalog.create_job(
            kind="ingest",
            idempotency_key=submission,
            request_fingerprint=self._request_fingerprint(sealed, libraries),
            input_revision_id=revision.revision_id,
            document_id=document_id,
            metadata_revision_id=metadata_revision_id,
            target_generation_id=generation.generation_id,
            state="queued",
        )
        self._set_import_state(import_id, "queued")
        return job_view(job)

    # -------------------------------------------------------------------- 任务

    def get_job_view(self, job_id: str) -> JobView:
        record = self.catalog.get_job(job_id)
        if record is None:
            raise _not_found("索引任务不存在。", code="JOB_NOT_FOUND")
        return job_view(record)

    def list_job_views(self, *, limit: int = 50) -> list[JobView]:
        return [job_view(record) for record in self.catalog.list_jobs(limit=limit)]

    def run_ingest_job(self, job_id: str, *, lease_seconds: int | None = None) -> JobView:
        record = self.catalog.get_job(job_id)
        if record is None:
            raise _not_found("索引任务不存在。", code="JOB_NOT_FOUND")
        if record.kind != "ingest":
            raise _conflict("该任务不是入库任务。", code="JOB_KIND_MISMATCH")
        if record.state in ("succeeded", "failed", "cancelled"):
            return job_view(record)
        try:
            claimed = self.catalog.claim_job(
                job_id, lease_seconds=lease_seconds or self.lease_seconds
            )
        except AppError as exc:
            if exc.code == "JOB_BUSY":
                # 其他 worker 持有租约：如实返回当前状态，不抢跑
                return job_view(self.catalog.get_job(job_id) or record)
            raise
        final = self._execute(claimed)
        return job_view(final)

    def recover_pending_jobs(self, *, max_jobs: int = 8) -> int:
        """崩溃恢复：重做 queued / 租约过期的 running 入库任务（单 worker 串行）。"""
        if not self._running.acquire(blocking=False):
            return 0
        completed = 0
        try:
            for _ in range(max(1, max_jobs)):
                record = self._next_recoverable_ingest_job()
                if record is None:
                    break
                try:
                    self.run_ingest_job(record.job_id)
                except AppError as exc:
                    if exc.code in ("JOB_BUSY", "JOB_NOT_CLAIMABLE"):
                        break
                    raise
                completed += 1
        finally:
            self._running.release()
        return completed

    def cancel_job(self, job_id: str) -> JobView:
        record = self.catalog.get_job(job_id)
        if record is None:
            raise _not_found("索引任务不存在。", code="JOB_NOT_FOUND")
        updated = request_cancel(self.catalog, job_id, lease_seconds=self.lease_seconds)
        if updated.state == "cancelled":
            self._set_import_state_for_revision(
                updated.input_revision_id, "cancelled", error_code="JOB_CANCELLED"
            )
        return job_view(updated)

    def retry_job(self, job_id: str) -> JobView:
        record = self.catalog.get_job(job_id)
        if record is None:
            raise _not_found("索引任务不存在。", code="JOB_NOT_FOUND")
        if record.kind != "ingest":
            raise _conflict(
                "只有入库任务可以就地重试；重建请重新发起新的索引代。",
                code="RETRY_NOT_SUPPORTED",
            )
        if record.state in ("queued", "running"):
            raise _conflict("任务仍在进行，无需重试。", code="JOB_BUSY")
        if record.state == "succeeded":
            raise _conflict("任务已成功，无需重试。", code="JOB_NOT_RETRYABLE")
        if record.input_revision_id is None or record.target_generation_id is None:
            raise _conflict("任务缺少必要输入，无法重试。", code="JOB_NOT_RETRYABLE")
        attempt = record.attempt
        new_job = self.catalog.create_job(
            kind="ingest",
            idempotency_key=f"retry/{record.job_id}/{attempt + 1}",
            request_fingerprint=record.request_fingerprint,
            input_revision_id=record.input_revision_id,
            document_id=record.document_id,
            metadata_revision_id=record.metadata_revision_id,
            target_generation_id=record.target_generation_id,
            state="queued",
        )
        return job_view(new_job)

    # -------------------------------------------------------------------- 原文

    def source_span(self, revision_id: str, *, char_start: int, char_end: int) -> SourceSpanView:
        return read_source_span(
            catalog=self.catalog,
            blobs=self.blobs,
            revision_id=revision_id,
            char_start=char_start,
            char_end=char_end,
        )

    # ------------------------------------------------------------------ 内部：解析产物

    def _prepare_metadata(
        self,
        metadata: dict | None,
        *,
        target_document_id: str | None,
        confirm_metadata: bool | None,
    ) -> tuple[dict | None, bool]:
        if metadata is None:
            if target_document_id is None:
                return None, False
            document = self.catalog.require_live_document(target_document_id)
            return metadata_input_from_record(document.metadata), (
                True if confirm_metadata is None else bool(confirm_metadata)
            )
        validated = self._validate_metadata(metadata)
        confirmed = True if confirm_metadata is None else bool(confirm_metadata)
        return validated.model_dump(), confirmed

    def _validate_metadata(self, metadata: dict) -> DocumentMetadataInput:
        if not isinstance(metadata, dict):
            raise _invalid("metadata 必须是 JSON 对象。")
        try:
            return DocumentMetadataInput.model_validate(metadata)
        except Exception as exc:  # noqa: BLE001 - pydantic 校验错误统一 422
            raise _invalid(f"教材分类信息不合法：{exc}") from exc

    def _store_artifacts(
        self,
        parsed: ParsedDocument,
        chunks: list,
        policy,
        *,
        confirmed: bool,
    ) -> dict:
        normalized_blob_id = self.blobs.write_staged_text(parsed.normalized_text)
        source_map_blob_id = self.blobs.write_staged_json(source_map_payload(parsed))
        return {
            "parserVersion": PARSER_VERSION,
            "sourceKind": parsed.source_kind,
            "charCount": parsed.char_count,
            "pageCount": parsed.page_count,
            "blockCount": parsed.block_count,
            "needsOcr": parsed.needs_ocr,
            "warnings": list(parsed.warnings),
            "normalizedBlobId": normalized_blob_id,
            "normalizedTextSha256": sha256_text(parsed.normalized_text),
            "sourceMapBlobId": source_map_blob_id,
            "policyFingerprint": chunk_policy_fingerprint(policy),
            "chunkPolicy": chunk_policy_json(policy),
            "chunks": [
                {
                    "ordinal": chunk.ordinal,
                    "charStart": chunk.char_start,
                    "charEnd": chunk.char_end,
                    "region": chunk.region,
                    "chapterPath": list(chunk.chapter_path),
                    "textSha256": chunk.text_sha256,
                }
                for chunk in chunks
            ],
            "regions": [
                {"region": span.region, "charStart": span.char_start, "charEnd": span.char_end}
                for span in split_regions(parsed)
            ],
            "metadataConfirmed": bool(confirmed),
            "sealedDocumentId": None,
            "sealedRevisionId": None,
        }

    def _draft_warnings(self, record: ImportRecord, artifacts: dict) -> list[str]:
        warnings = list(record.warnings)
        extra = artifacts.get("warnings")
        if isinstance(extra, list):
            warnings.extend(item for item in extra if isinstance(item, str))
        return list(dict.fromkeys(warnings))

    def _build_import_view(self, record: ImportRecord) -> ImportDraftView:
        artifacts = record.parsed_artifacts
        parsed_view = None
        if isinstance(artifacts, dict) and artifacts.get("normalizedBlobId"):
            try:
                text = self.blobs.read_text(
                    area="staging", blob_id=str(artifacts["normalizedBlobId"])
                )
            except AppError:
                text = None
            if text is not None:
                parsed_view = self._parsed_view(artifacts, text)
        can_commit = self._can_commit(record, artifacts)
        return import_draft_view(
            record, artifacts=artifacts if isinstance(artifacts, dict) else None,
            parsed=parsed_view, can_commit=can_commit,
        )

    def _parsed_view(self, artifacts: dict, text: str):
        from app.schemas.textbook import ImportParsedView

        chunks = artifacts.get("chunks")
        chunk_list = [item for item in chunks if isinstance(item, dict)] if isinstance(chunks, list) else []
        body = sum(1 for item in chunk_list if item.get("region") == "body")
        warnings = [item for item in artifacts.get("warnings", []) if isinstance(item, str)]
        return ImportParsedView(
            charCount=int(artifacts.get("charCount", len(text)) or 0),
            chunkCount=len(chunk_list),
            bodyChunkCount=body,
            exerciseChunkCount=len(chunk_list) - body,
            needsOcr=bool(artifacts.get("needsOcr")),
            sourceKind=artifacts.get("sourceKind", "markdown"),
            pageCount=artifacts.get("pageCount"),
            blockCount=artifacts.get("blockCount"),
            warnings=warnings,
            preview=chunk_preview(chunk_list, text),
        )

    def _can_commit(self, record: ImportRecord, artifacts: dict | None) -> bool:
        if record.state != "needs_review" or not isinstance(artifacts, dict):
            return False
        if artifacts.get("needsOcr"):
            return False
        if not artifacts.get("metadataConfirmed"):
            return False
        return record.metadata is not None

    # ------------------------------------------------------------------ 内部：封存

    def _validate_libraries(self, library_ids: list[str]) -> list[str]:
        if not library_ids:
            raise _invalid("至少选择一个逻辑库。")
        unique: list[str] = []
        for library_id in library_ids:
            if not isinstance(library_id, str) or not library_id:
                raise _invalid("libraryIds 必须是非空字符串数组。")
            if library_id in unique:
                continue
            library = self.catalog.get_library(library_id)
            if library is None or library.is_deleted:
                raise _not_found("逻辑库不存在或已停用。", code="LIBRARY_NOT_FOUND")
            unique.append(library_id)
        return unique

    def _require_no_active_publish(self, document_id: str) -> None:
        for record in self.catalog.list_jobs(
            kinds=["ingest"], states=["queued", "running"], limit=200
        ):
            if record.document_id == document_id:
                raise _conflict(
                    "该教材已有正在进行的入库任务，请等待其结束。",
                    code="INDEX_MUTATION_BUSY",
                    retryable=True,
                )

    def _owner_for_libraries(self, library_ids: list[str]) -> str:
        """书册归属由服务端按所选逻辑库推导：仅基础库 → system，其余 → 本机用户。

        范围解析要求"书册 owner 与逻辑库 owner 一致"（B0），因此把用户导入放进基础库时
        必须让书册归属同一 owner，否则该教材在任教范围里永远无法解析。
        """
        owners: list[str] = []
        for library_id in library_ids:
            record = self.catalog.get_library(library_id)
            owners.append(record.owner_id if record is not None else self.owner_id)
        if owners and all(owner == "system" for owner in owners):
            return "system"
        return self.owner_id

    def _seal_revision(
        self, record: ImportRecord, library_ids: list[str]
    ) -> tuple[str, RevisionRecord, str]:
        """封存原件/规范化文本/来源映射并落定不可变修订（全部在 SQL 事务外）。

        书册身份（``origin_key``）规则见模块 docstring：内容相同即同一书册；
        命中未删除的既有书册时追加修订（等价更新），不新建书册。
        """
        artifacts = dict(record.parsed_artifacts or {})
        for field in _ARTIFACT_FIELDS:
            if not artifacts.get(field):
                raise _invalid(
                    "草稿缺少解析产物，无法封存修订；请重新上传。",
                    code="IMPORT_ARTIFACT_MISSING",
                )
        metadata = self._validate_metadata(record.metadata or {})
        self.blobs.seal(area="blobs", blob_id=record.uploaded_blob_id)
        self.blobs.seal(area="normalized", blob_id=str(artifacts["normalizedBlobId"]))
        self.blobs.seal(area="normalized", blob_id=str(artifacts["sourceMapBlobId"]))

        document_id = record.target_document_id or artifacts.get("sealedDocumentId")
        if document_id is not None:
            # 显式更新路径（targetDocumentId）或同一草稿的崩溃重做：沿用书册既有 origin_key
            self._prepare_existing_document(
                document_id, metadata=metadata, library_ids=library_ids
            )
        else:
            owner_id = self._owner_for_libraries(library_ids)
            origin_key = origin_key_for(owner_id, record.uploaded_blob_id)
            hit = self._match_document_by_origin(owner_id=owner_id, origin_key=origin_key)
            if hit is not None:
                # 相同内容已入库且未删除：作为该书册的新修订，不新建书册
                document_id = hit
                artifacts["sealedDocumentId"] = document_id
                artifacts["originKey"] = origin_key
                artifacts["warnings"] = _append_warning(
                    artifacts.get("warnings"),
                    ORIGIN_REUSE_WARNING,
                )
                self._patch_artifacts(record, artifacts)
                logger.info(
                    "导入草稿 %s 命中同一来源键（%s），追加到已有书册 %s",
                    record.import_id,
                    origin_key,
                    document_id,
                )
                self._prepare_existing_document(
                    document_id, metadata=metadata, library_ids=library_ids
                )
            else:
                try:
                    created = self.catalog.create_document(
                        owner_id=owner_id,
                        title=metadata.title,
                        stage_id=metadata.stageId,
                        grade_ids=metadata.gradeIds,
                        subject_id=metadata.subjectId,
                        edition_id=metadata.editionId,
                        publication_label=metadata.publicationLabel,
                        volume_label=metadata.volumeLabel,
                        origin_key=origin_key,
                        library_ids=library_ids,
                    )
                    document_id = created.document_id
                except AppError as exc:
                    if exc.code != "DOCUMENT_ORIGIN_CONFLICT":
                        raise
                    # 并发提交抢到同一来源键：复用已落库的书册（幂等，不产生第二册）
                    concurrent = self._match_document_by_origin(
                        owner_id=owner_id, origin_key=origin_key
                    )
                    if concurrent is None:
                        raise
                    document_id = concurrent
                artifacts["sealedDocumentId"] = document_id
                artifacts["originKey"] = origin_key
                self._patch_artifacts(record, artifacts)

        revision = None
        sealed_revision_id = artifacts.get("sealedRevisionId")
        if sealed_revision_id:
            revision = self.catalog.get_revision(str(sealed_revision_id))
        if revision is None:
            revision = self.catalog.create_document_revision(
                document_id,
                original_file_sha256=record.uploaded_blob_id,
                normalized_text_sha256=str(artifacts["normalizedTextSha256"]),
                parser_version=str(artifacts["parserVersion"]),
                original_blob_id=record.uploaded_blob_id,
                normalized_blob_id=str(artifacts["normalizedBlobId"]),
                source_map_blob_id=str(artifacts["sourceMapBlobId"]),
                char_count=int(artifacts["charCount"]),
            )
            artifacts["sealedRevisionId"] = revision.revision_id
            self._patch_artifacts(record, artifacts)
        metadata_revision_id = self.catalog.current_metadata_revision(document_id).metadata_revision_id
        return document_id, revision, metadata_revision_id

    def _prepare_existing_document(
        self, document_id: str, *, metadata: DocumentMetadataInput, library_ids: list[str]
    ) -> None:
        """已有书册：元数据不同才新建元数据修订；逻辑库归属为增量 link（不摘除）。"""
        document = self.catalog.require_live_document(document_id)
        if not self._metadata_matches(document.metadata, metadata):
            self.catalog.update_document_metadata(
                document_id,
                expected_revision=document.revision,
                title=metadata.title,
                stage_id=metadata.stageId,
                grade_ids=metadata.gradeIds,
                subject_id=metadata.subjectId,
                edition_id=metadata.editionId,
                publication_label=metadata.publicationLabel,
                volume_label=metadata.volumeLabel,
            )
        for library_id in library_ids:
            self.catalog.link_document(library_id, document_id)

    def _match_document_by_origin(self, *, owner_id: str, origin_key: str) -> str | None:
        """按来源键查未删除书册；命中已删除书册时明确拒绝，不复活也不另建重复册。"""
        existing = self.catalog.find_document_by_origin_key(owner_id, origin_key)
        if existing is None:
            return None
        if existing.is_deleted:
            raise _conflict(
                "相同内容的教材此前已被停用；不能自动复活，也不新建重复书册。",
                code="DOCUMENT_ORIGIN_DELETED",
            )
        return existing.document_id

    @staticmethod
    def _metadata_matches(existing, metadata: DocumentMetadataInput) -> bool:
        return (
            existing.title == metadata.title
            and existing.stage_id == metadata.stageId
            and tuple(existing.grade_ids) == tuple(metadata.gradeIds)
            and existing.subject_id == metadata.subjectId
            and existing.edition_id == metadata.editionId
            and existing.publication_label == metadata.publicationLabel
            and existing.volume_label == metadata.volumeLabel
        )

    def _patch_artifacts(self, record: ImportRecord, artifacts: dict) -> None:
        current = self.catalog.get_import(record.import_id)
        if current is None:
            return
        self.catalog.update_import(
            record.import_id,
            expected_revision=current.revision,
            parsed_artifacts_json=artifacts,
        )

    def _request_fingerprint(self, record: ImportRecord, library_ids: list[str]) -> str:
        artifacts = record.parsed_artifacts or {}
        payload = {
            "importId": record.import_id,
            "documentId": record.target_document_id or artifacts.get("sealedDocumentId"),
            "revisionId": artifacts.get("sealedRevisionId"),
            "normalizedTextSha256": artifacts.get("normalizedTextSha256"),
            "sourceMapBlobId": artifacts.get("sourceMapBlobId"),
            "metadata": record.metadata,
            "libraryIds": sorted(library_ids),
            "expectedCurrentRevisionId": record.expected_current_revision_id,
            "parserVersion": artifacts.get("parserVersion"),
            "policyFingerprint": artifacts.get("policyFingerprint"),
            "chunkCount": len(artifacts.get("chunks") or []),
        }
        return sha256_hex(canonical_json(payload))

    # ------------------------------------------------------------------ 内部：执行

    def _require_profile(self, generation):
        profile = self.catalog.get_embedding_profile(generation.profile_id)
        if profile is None:
            raise _not_found("Embedding 配置不存在。", code="PROFILE_NOT_FOUND")
        return profile

    def _execute(self, job: JobRecord) -> JobRecord:
        self.indexer.begin_job(job.job_id)
        try:
            return self._execute_claimed(job)
        finally:
            self.indexer.forget_job(job.job_id)

    def _execute_claimed(self, job: JobRecord) -> JobRecord:
        import_id = self._find_import_for_revision(job.input_revision_id)
        try:
            revision = self._require_revision(job.input_revision_id)
            generation = self._require_generation(job.target_generation_id)
            profile = self._require_profile(generation)
            document = self._require_document(job.document_id)
            parsed = self.indexer.parse_revision(revision)
            if not parsed.normalized_text.strip():
                raise _invalid(
                    "该修订没有可索引文本（需要 OCR），已拒绝生成空索引。",
                    code="DOCUMENT_NEEDS_OCR",
                )
            policy = generation_policy(generation)
            chunk_set, chunks, parsed = self.indexer.ensure_chunk_set(
                revision=revision, policy=policy
            )
            if not chunks:
                raise _invalid(
                    "分块结果为空，已拒绝生成空索引。",
                    code="DOCUMENT_NEEDS_OCR",
                )
            # 读大文件/分块可能耗时：进入批次循环前再核验并（到期）续租
            self.indexer.require_lease_and_renew(
                job_id=job.job_id, lease_token=job.lease_token or ""
            )
            if import_id:
                self._set_import_state(import_id, "embedding")
            if self._revision_state(generation.generation_id, revision.revision_id) != "ready":
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
                state_label="embedding",
            )
            if import_id:
                self._set_import_state(import_id, "indexing")
            self.indexer.verify_points(
                generation=generation,
                revision=revision,
                chunk_set=chunk_set,
                expected=len(chunks),
            )
            self._publish(job, generation=generation, revision=revision, chunk_set=chunk_set)
            if import_id:
                self._set_import_state(import_id, "ready")
            return self.catalog.get_job(job.job_id) or job
        except JobCancelled as exc:
            return self._terminate(job, "cancelled", "JOB_CANCELLED", str(exc), import_id)
        except AppError as exc:
            if exc.code == "LEASE_LOST":
                # 租约失效：绝不继续写向量，也不改索引指针；记录可写时落 failed，
                # 真失权（记录不可写）时保持 running，交给恢复流程重新领取。
                logger.warning("任务 %s 租约失效，停止写入。", job.job_id)
                failed = try_fail_lost_lease(self.catalog, job)
                if failed is not None and import_id:
                    self._set_import_state(import_id, "failed", error_code="LEASE_LOST")
                return failed or (self.catalog.get_job(job.job_id) or job)
            if self.indexer.cancel_requested(job.job_id):
                return self._terminate(
                    job, "cancelled", "JOB_CANCELLED", "任务在执行中被取消。", import_id
                )
            return self._terminate(job, "failed", exc.code, str(exc), import_id)
        except Exception as exc:  # noqa: BLE001 - 未预期异常也要落 failed，不悬挂 running
            logger.exception("入库任务 %s 失败", job.job_id)
            return self._terminate(
                job, "failed", "INGEST_FAILED", exc.__class__.__name__, import_id
            )

    def _publish(self, job: JobRecord, *, generation, revision, chunk_set) -> None:
        lease_token = job.lease_token or ""
        # 最终发布前核验并（到期）续租：长任务的最后一批与对账之间也不会失权
        self.indexer.require_lease_and_renew(
            job_id=job.job_id, lease_token=lease_token
        )
        self.indexer.raise_if_cancelled(job.job_id)
        state = self.catalog.catalog_state()
        if state.rebuild_job_id is not None:
            raise _conflict(
                "正在重建索引，暂不能发布入库结果。", code="INDEX_REBUILD_IN_PROGRESS"
            )
        if state.active_generation_id != generation.generation_id:
            raise _conflict("当前索引代已改变，拒绝发布。", code="INDEX_NOT_READY")
        document = self._require_document(job.document_id)
        metadata_revision_id = (
            job.metadata_revision_id
            or self.catalog.current_metadata_revision(document.document_id).metadata_revision_id
        )
        self.catalog.upsert_generation_revision(
            generation.generation_id,
            revision.revision_id,
            chunk_set.chunk_set_id,
            state="ready",
            expected_chunk_count=chunk_set.chunk_count,
            manifest_sha256=chunk_set.manifest_sha256,
        )
        self.catalog.publish_document_revision(
            document.document_id,
            revision_id=revision.revision_id,
            metadata_revision_id=metadata_revision_id,
        )
        self.catalog.finish_job(
            job.job_id,
            lease_token=lease_token,
            state="succeeded",
            error_message=None,
        )

    def _terminate(
        self,
        job: JobRecord,
        state: str,
        error_code: str,
        message: str,
        import_id: str | None,
    ) -> JobRecord:
        try:
            finished = self.catalog.finish_job(
                job.job_id,
                lease_token=job.lease_token or "",
                state=state,
                error_code=error_code,
                error_message=message[:500] if message else None,
            )
        except AppError as exc:
            if exc.code == "LEASE_LOST":
                return self.catalog.get_job(job.job_id) or job
            raise
        if import_id:
            self._set_import_state(import_id, state, error_code=error_code)
        return finished

    def _require_revision(self, revision_id: str | None) -> RevisionRecord:
        if not revision_id:
            raise _not_found("任务缺少输入修订。", code="REVISION_NOT_FOUND")
        revision = self.catalog.get_revision(revision_id)
        if revision is None:
            raise _not_found("文档修订不存在。", code="REVISION_NOT_FOUND")
        return revision

    def _require_generation(self, generation_id: str | None):
        if not generation_id:
            raise _not_found("任务缺少目标索引代。", code="GENERATION_NOT_FOUND")
        generation = self.catalog.get_generation(generation_id)
        if generation is None:
            raise _not_found("索引代不存在。", code="GENERATION_NOT_FOUND")
        return generation

    def _require_document(self, document_id: str | None):
        if not document_id:
            raise _not_found("任务缺少书册。", code="DOCUMENT_UNAVAILABLE")
        document = self.catalog.get_document(document_id)
        if document is None or document.is_deleted:
            raise _conflict(
                "教材已删除，迟到任务不得复活它。", code="DOCUMENT_UNAVAILABLE"
            )
        return document

    def _revision_state(self, generation_id: str, revision_id: str) -> str | None:
        for record in self.catalog.list_generation_revisions(generation_id):
            if record.document_revision_id == revision_id:
                return record.state
        return None

    def _next_recoverable_ingest_job(self) -> JobRecord | None:
        first = self.catalog.first_recoverable_job()
        if first is not None and first.kind == "ingest":
            return first
        candidates = recoverable_jobs(self.catalog, kinds=("ingest",))
        return candidates[0] if candidates else None

    def _find_import_for_revision(self, revision_id: str | None) -> str | None:
        if not revision_id:
            return None
        for record in self.catalog.list_imports(limit=100):
            artifacts = record.parsed_artifacts
            if isinstance(artifacts, dict) and artifacts.get("sealedRevisionId") == revision_id:
                return record.import_id
        return None

    def _set_import_state_for_revision(
        self, revision_id: str | None, state: str, *, error_code: str | None = None
    ) -> None:
        import_id = self._find_import_for_revision(revision_id)
        if import_id:
            self._set_import_state(import_id, state, error_code=error_code)

    def _set_import_state(
        self, import_id: str, state: str, *, error_code: str | None = None
    ) -> None:
        """把草稿状态推进到任务状态；草稿被并发编辑时最多重试 3 次，失败只记日志。"""
        for _ in range(3):
            record = self.catalog.get_import(import_id)
            if record is None or record.state == state:
                return
            try:
                self.catalog.update_import(
                    import_id,
                    expected_revision=record.revision,
                    state=state,
                    error_code=error_code,
                )
                return
            except AppError as exc:
                if exc.code != "REVISION_CONFLICT":
                    logger.warning("更新导入草稿状态失败：%s", exc)
                    return
        logger.warning("导入草稿 %s 状态更新冲突次数过多，任务状态仍以任务记录为准。", import_id)


@dataclass(frozen=True)
class ImportFormOptions:
    """multipart 上传的 metadataJson 解析结果。

    支持两种形态：裸 ``DocumentMetadataInput``（前端 F0 直接发送）与包装对象
    ``{"metadata": ..., "targetDocumentId": ..., "expectedCurrentRevisionId": ..., "confirmMetadata": bool}``；
    两者混用时包装对象的字段优先。未知字段一律 422。
    """

    metadata: dict | None = None
    target_document_id: str | None = None
    expected_current_revision_id: str | None = None
    confirm_metadata: bool | None = None


_WRAPPER_FIELDS = frozenset(
    {"metadata", "targetDocumentId", "expectedCurrentRevisionId", "confirmMetadata"}
)
_METADATA_FIELDS = frozenset(
    {
        "title",
        "stageId",
        "gradeIds",
        "subjectId",
        "editionId",
        "publicationLabel",
        "volumeLabel",
    }
)


def parse_import_form_metadata(raw: str | None) -> ImportFormOptions:
    if raw is None or not raw.strip():
        return ImportFormOptions()
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise _invalid("metadataJson 不是合法 JSON。") from exc
    if not isinstance(payload, dict):
        raise _invalid("metadataJson 必须是 JSON 对象。")
    keys = set(payload)
    if keys & _WRAPPER_FIELDS:
        unknown = sorted(keys - _WRAPPER_FIELDS)
        if unknown:
            raise _invalid(f"metadataJson 包含未知字段：{', '.join(unknown)}。")
        metadata = payload.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise _invalid("metadataJson.metadata 必须是 JSON 对象。")
        target = payload.get("targetDocumentId")
        expected = payload.get("expectedCurrentRevisionId")
        confirm = payload.get("confirmMetadata")
        for value, field in (
            (target, "targetDocumentId"),
            (expected, "expectedCurrentRevisionId"),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise _invalid(f"metadataJson.{field} 必须是非空字符串。")
        if confirm is not None and not isinstance(confirm, bool):
            raise _invalid("metadataJson.confirmMetadata 必须是布尔值。")
        return ImportFormOptions(
            metadata=metadata,
            target_document_id=target.strip() if isinstance(target, str) else None,
            expected_current_revision_id=expected.strip() if isinstance(expected, str) else None,
            confirm_metadata=confirm,
        )
    unknown = sorted(keys - _METADATA_FIELDS)
    if unknown:
        raise _invalid(f"metadataJson 包含未知字段：{', '.join(unknown)}。")
    return ImportFormOptions(metadata=payload)
