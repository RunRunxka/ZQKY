"""共享 HTTP 视图构造：把 B0 记录与任务状态映射为冻结契约的响应模型。

所有视图只读目录与任务记录；不在这里做任何写入，也不把失败包装成空列表。
"""

from __future__ import annotations

import functools
from typing import Any, TypeVar

import anyio

from app.core.exceptions import AppError
from app.core.sqlite import connect as sqlite_connect
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import (
    DocumentRecord,
    GenerationRecord,
    ImportRecord,
    JobRecord,
    LibraryRecord,
    MetadataRevisionRecord,
    RevisionRecord,
)
from app.schemas.textbook import (
    ChunkPreview,
    DocumentDetail,
    DocumentMetadataView,
    DocumentRevisionSummary,
    DocumentSummary,
    GenerationView,
    ImportDraftView,
    ImportParsedView,
    JobProgress,
    JobView,
    LibraryDetail,
    LibrarySummary,
    ScopeCheckView,
    TeachingSettingsView,
    TextbookSelection,
)

#: 失败后仍可重试的错误：其余错误重试也会再次失败（身份/维度/指纹/数据缺失）。
RETRYABLE_JOB_ERRORS = frozenset(
    {
        "EMBEDDING_UNAVAILABLE",
        "EMBEDDING_OUT_OF_MEMORY",
        "QDRANT_UNAVAILABLE",
        "JOB_LEASE_EXPIRED",
        "PUBLISH_POINT_COUNT_MISMATCH",
    }
)
#: 明确不可重试的错误（即使来自网络层也不应自动重试）
NON_RETRYABLE_JOB_ERRORS = frozenset(
    {
        "EMBEDDING_MODEL_CHANGED",
        "EMBEDDING_DIMENSION_MISMATCH",
        "EMBEDDING_INVALID_OUTPUT",
        "EMBEDDING_MODEL_MISSING",
        "DOCUMENT_NEEDS_OCR",
        "REVISION_NOT_FOUND",
        "DOCUMENT_UNAVAILABLE",
        "IDEMPOTENCY_CONFLICT",
        "GENERATION_DOC_CORRUPT",
        "CHUNK_POLICY_CORRUPT",
    }
)


_T = TypeVar("_T")


def require_state(service: _T | None, *, label: str) -> _T:
    """从 ``request.app.state`` 取服务；未装配时抛 503，绝不返回空列表或假成功。"""
    if service is None:
        raise AppError(
            f"{label}未装配：后端缺少对应服务，请检查启动日志与依赖。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return service


async def run_in_thread(fn, /, *args, **kwargs):
    """把同步的 SQL/文件/网络重活放到有界线程里执行，不阻塞事件循环。"""
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


def job_retryable(record: JobRecord) -> bool:
    if record.state not in ("failed", "cancelled"):
        return False
    code = record.error_code
    if code in NON_RETRYABLE_JOB_ERRORS:
        return False
    return True


def job_view(record: JobRecord) -> JobView:
    checkpoint = record.checkpoint
    progress = JobProgress(
        documentsDone=_int(checkpoint.get("documentsDone")),
        documentsTotal=_int(checkpoint.get("documentsTotal")),
        chunksDone=_int(checkpoint.get("chunksDone")),
        chunksTotal=_int(checkpoint.get("chunksTotal")),
        currentTitle=checkpoint.get("currentTitle") if isinstance(checkpoint.get("currentTitle"), str) else None,
    )
    return JobView(
        jobId=record.job_id,
        kind=record.kind,
        state=record.state,
        targetGenerationId=record.target_generation_id,
        baseGenerationId=record.base_generation_id,
        documentId=record.document_id,
        inputRevisionId=record.input_revision_id,
        attempt=record.attempt,
        progress=progress,
        errorCode=record.error_code,
        errorMessage=record.error_message,
        retryable=job_retryable(record),
        createdAt=record.created_at,
        updatedAt=record.updated_at,
    )


def generation_view(catalog: TextbookCatalog, record: GenerationRecord) -> GenerationView:
    revisions = catalog.list_generation_revisions(record.generation_id)
    return GenerationView(
        generationId=record.generation_id,
        collectionName=record.collection_name,
        profileId=record.profile_id,
        state=record.state,
        chunkTotal=catalog.generation_chunk_total(record.generation_id),
        documentTotal=len(revisions),
        createdAt=record.created_at,
        publishedAt=record.published_at,
    )


def metadata_input_from_record(metadata: MetadataRevisionRecord) -> dict:
    return {
        "title": metadata.title,
        "stageId": metadata.stage_id,
        "gradeIds": list(metadata.grade_ids),
        "subjectId": metadata.subject_id,
        "editionId": metadata.edition_id,
        "publicationLabel": metadata.publication_label,
        "volumeLabel": metadata.volume_label,
    }


def metadata_view(metadata: MetadataRevisionRecord) -> DocumentMetadataView:
    return DocumentMetadataView(
        metadataRevisionId=metadata.metadata_revision_id,
        title=metadata.title,
        stageId=metadata.stage_id,
        gradeIds=list(metadata.grade_ids),
        subjectId=metadata.subject_id,
        editionId=metadata.edition_id,
        publicationLabel=metadata.publication_label,
        volumeLabel=metadata.volume_label,
    )


class ViewContext:
    """一次请求内共享读取缓存，避免列表接口对每个书册重复查询。"""

    def __init__(self, catalog: TextbookCatalog) -> None:
        self.catalog = catalog
        self._generation_links: tuple[str, dict[str, int]] | None = None
        self._pending_revisions: dict[str, str] | None = None

    # ------------------------------------------------------------------ 任务

    def pending_revision_map(self) -> dict[str, str]:
        if self._pending_revisions is None:
            mapping: dict[str, str] = {}
            for record in self.catalog.list_jobs(
                kinds=["ingest"], states=["queued", "running"], limit=200
            ):
                if record.document_id and record.input_revision_id:
                    mapping.setdefault(record.document_id, record.input_revision_id)
            self._pending_revisions = mapping
        return self._pending_revisions

    # ------------------------------------------------------------------ 书册

    def revision_summary(self, revision: RevisionRecord) -> DocumentRevisionSummary:
        return DocumentRevisionSummary(
            revisionId=revision.revision_id,
            originalFileSha256=revision.original_file_sha256,
            normalizedTextSha256=revision.normalized_text_sha256,
            parserVersion=revision.parser_version,
            charCount=revision.char_count,
            chunkCount=self.chunk_count(revision.revision_id),
            createdAt=revision.created_at,
        )

    def chunk_count(self, revision_id: str) -> int:
        state = self.catalog.catalog_state()
        generation_id = state.active_generation_id
        if generation_id:
            if self._generation_links is None or self._generation_links[0] != generation_id:
                self._generation_links = (
                    generation_id,
                    {
                        record.document_revision_id: record.expected_chunk_count
                        for record in self.catalog.list_generation_revisions(generation_id)
                    },
                )
            count = self._generation_links[1].get(revision_id)
            if count is not None:
                return count
        return latest_sealed_chunk_count(self.catalog, revision_id)

    def document_summary(self, record: DocumentRecord) -> DocumentSummary:
        revision = (
            self.catalog.get_revision(record.current_revision_id)
            if record.current_revision_id
            else None
        )
        return DocumentSummary(
            documentId=record.document_id,
            ownerId=record.owner_id,
            title=record.title,
            libraryIds=list(record.library_ids),
            gradeIds=list(record.grade_ids),
            subjectId=record.subject_id,
            editionId=record.edition_id,
            metadataRevisionId=record.current_metadata_revision_id,
            currentRevision=self.revision_summary(revision) if revision is not None else None,
            pendingRevisionId=self.pending_revision_map().get(record.document_id),
            deletedAt=record.deleted_at,
            revision=record.revision,
        )

    def document_detail(self, record: DocumentRecord) -> DocumentDetail:
        summary = self.document_summary(record)
        revision = (
            self.catalog.get_revision(record.current_revision_id)
            if record.current_revision_id
            else None
        )
        warnings: list[str] = []
        if revision is None:
            warnings.append("该书册尚未发布有效修订。")
        if summary.pendingRevisionId is not None:
            warnings.append("该教材有正在构建的新修订，构建完成后才对外生效。")
        return DocumentDetail(
            **summary.model_dump(),
            metadata=metadata_view(record.metadata),
            warnings=warnings,
        )

    # ------------------------------------------------------------------ 逻辑库

    def library_summary(self, record: LibraryRecord) -> LibrarySummary:
        documents = [
            item
            for item in self.catalog.list_documents(library_id=record.library_id)
            if item.deleted_at is None
        ]
        return LibrarySummary(
            libraryId=record.library_id,
            kind=record.kind,
            ownerId=record.owner_id,
            displayName=record.display_name,
            gradeId=record.grade_id,
            subjectId=record.subject_id,
            editionId=record.edition_id,
            documentCount=len(documents),
            readyDocumentCount=sum(1 for item in documents if item.current_revision_id is not None),
            revision=record.revision,
            deletedAt=record.deleted_at,
        )

    def library_detail(self, record: LibraryRecord) -> LibraryDetail:
        summary = self.library_summary(record)
        documents = [
            self.document_summary(item)
            for item in self.catalog.list_documents(library_id=record.library_id)
            if item.deleted_at is None
        ]
        return LibraryDetail(**summary.model_dump(), documents=documents)

    # ---------------------------------------------------------------- 任教设置

    def teaching_settings(self) -> TeachingSettingsView:
        record = self.catalog.get_teaching_settings()
        selection = _selection_from_json(record.selection)
        ready, reason = scope_status(self.catalog, selection)
        return TeachingSettingsView(
            ownerId=record.owner_id,
            selection=selection,
            revision=record.revision,
            updatedAt=record.updated_at,
            scopeReady=ready,
            scopeReason=reason,
        )


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def latest_sealed_chunk_count(catalog: TextbookCatalog, revision_id: str) -> int:
    """该修订下**最新已封存分块集**的块数；真的没有任何分块集才返回 0。

    兜底不再按某个策略指纹猜（新清洗策略会让旧口径分块集查不到，显示成 0 块）；
    按 ``sealed_at`` 倒序取第一个，得到该修订当前实际存在的块数。

    接口缺口（已上报总控）：仓库层只有 ``find_chunk_set(修订, 指纹)``，没有"按修订列出分块集"的
    公开方法，所以这里用统一连接入口 ``app.core.sqlite.connect`` 做一次只读查询。
    若 B0 补上 ``TextbookCatalog.list_chunk_sets(document_revision_id)``，本函数应改为调用它。
    """
    connection = sqlite_connect(catalog.db_path)
    try:
        row = connection.execute(
            "SELECT chunk_count FROM chunk_sets WHERE document_revision_id = ? "
            # 秒级时间戳相同时按插入顺序取最后写入的那一个（"最新"的确定口径）
            "ORDER BY sealed_at DESC, rowid DESC LIMIT 1",
            (revision_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return 0
    return _int(row["chunk_count"])


def _selection_from_json(raw: object) -> TextbookSelection | None:
    if raw is None:
        return None
    try:
        return TextbookSelection.model_validate(raw)
    except Exception:  # noqa: BLE001 - 损坏设置不伪装成"已就绪"
        return None


def scope_status(
    catalog: TextbookCatalog, selection: TextbookSelection | None
) -> tuple[bool, str | None]:
    """任教范围是否可检索：逐条核验通过才为 ready，失败返回原因（不抛）。"""
    if selection is None:
        return False, "尚未保存任教范围。"
    try:
        catalog.resolve_selection(selection)
    except AppError as exc:
        return False, str(exc)
    return True, None


def scope_check_view(
    catalog: TextbookCatalog, selection: TextbookSelection
) -> ScopeCheckView:
    context = ViewContext(catalog)
    missing = [
        document_id
        for document_id in selection.documentIds
        if not _document_is_live(catalog, document_id)
    ]
    try:
        resolved = catalog.resolve_selection(selection)
    except AppError as exc:
        return ScopeCheckView(
            scopeReady=False,
            reason=str(exc),
            documents=[],
            missingDocumentIds=missing or list(selection.documentIds),
        )
    documents = [
        context.document_summary(catalog.require_live_document(item.document_id))
        for item in resolved
    ]
    return ScopeCheckView(
        scopeReady=True,
        reason=None,
        documents=documents,
        missingDocumentIds=[],
    )


def _document_is_live(catalog: TextbookCatalog, document_id: str) -> bool:
    try:
        record = catalog.get_document(document_id)
    except AppError:
        return False
    return record is not None and record.deleted_at is None


def import_draft_view(
    record: ImportRecord,
    *,
    artifacts: dict[str, Any] | None,
    parsed: ImportParsedView | None,
    can_commit: bool,
) -> ImportDraftView:
    metadata_payload = record.metadata
    metadata = None
    if isinstance(metadata_payload, dict):
        try:
            from app.schemas.textbook import DocumentMetadataInput

            metadata = DocumentMetadataInput.model_validate(metadata_payload)
        except Exception:  # noqa: BLE001 - 非法元数据不伪装成已确认
            metadata = None
    warnings = list(record.warnings)
    if artifacts is not None:
        extra = artifacts.get("warnings")
        if isinstance(extra, list):
            warnings.extend(item for item in extra if isinstance(item, str) and item not in warnings)
    confirmed = bool(artifacts.get("metadataConfirmed")) if artifacts else False
    return ImportDraftView(
        importId=record.import_id,
        ownerId=record.owner_id,
        state=record.state,
        revision=record.revision,
        uploadedFileName=record.uploaded_file_name,
        uploadedBytes=record.uploaded_bytes,
        targetDocumentId=record.target_document_id,
        expectedCurrentRevisionId=record.expected_current_revision_id,
        metadata=metadata,
        metadataConfirmed=confirmed,
        parsed=parsed,
        warnings=warnings,
        errorCode=record.error_code,
        canCommit=can_commit,
        createdAt=record.created_at,
    )


def chunk_preview(chunks: list[dict], text: str, limit: int = 8) -> list[ChunkPreview]:
    previews: list[ChunkPreview] = []
    for chunk in chunks[:limit]:
        try:
            previews.append(
                ChunkPreview(
                    ordinal=int(chunk["ordinal"]),
                    charStart=int(chunk["charStart"]),
                    charEnd=int(chunk["charEnd"]),
                    region=chunk["region"],
                    chapterPath=[str(item) for item in chunk.get("chapterPath", [])],
                    text=text[int(chunk["charStart"]): int(chunk["charEnd"])],
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return previews
