"""教材目录接口：字典、逻辑库、导入草稿、任务、书册、受控原文与任教设置。

取服务：全部经 ``request.app.state``（catalog / ingest_service / index_service …）；
服务为 ``None`` 时统一 503 ``SERVICE_UNAVAILABLE``（可重试），绝不返回空列表或假成功。
所有同步重活（SQL、解析、文件、Qdrant/Ollama 调用）都在有界线程中执行。
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response, status

from app.core.exceptions import AppError
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.schemas.textbook import (
    MAX_UPLOAD_BYTES,
    DocumentDeleteRequest,
    DocumentDetail,
    DocumentList,
    DocumentPatchRequest,
    DocumentQuery,
    ImportCommitRequest,
    ImportCreateResponse,
    ImportDiscardRequest,
    ImportDraftList,
    ImportDraftView,
    ImportPatchRequest,
    JobList,
    JobView,
    LibraryCreateRequest,
    LibraryDetail,
    LibraryList,
    LibraryPatchRequest,
    LibraryQuery,
    LibrarySummary,
    ScopeCheckRequest,
    ScopeCheckView,
    SourceSpanView,
    TeachingSettingsUpdate,
    TeachingSettingsView,
    TextbookTaxonomy,
)
from app.services.textbook_ingest.multipart import parse_multipart_form
from app.services.textbook_ingest.service import parse_import_form_metadata
from app.services.textbook_ingest.taxonomy import TAXONOMY
from app.services.textbook_ingest.views import (
    ViewContext,
    job_view,
    require_state,
    run_in_thread,
    scope_check_view,
)

router = APIRouter(tags=["textbooks"])

#: multipart 头部/边界开销的宽松上界（超出此值在解析前直接 413）
_MULTIPART_OVERHEAD = 4096


def _catalog(request: Request) -> TextbookCatalog:
    return require_state(request.app.state.catalog, label="教材目录")


def _ingest(request: Request):
    return require_state(request.app.state.ingest_service, label="教材入库服务")


def _index(request: Request):
    return require_state(request.app.state.index_service, label="教材索引服务")


def _metadata_dict(payload) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)


# --------------------------------------------------------------------------- 字典


@router.get("/textbook-taxonomy")
async def get_textbook_taxonomy() -> TextbookTaxonomy:
    return TAXONOMY


# ------------------------------------------------------------------------- 逻辑库


@router.get("/textbook-libraries")
async def list_textbook_libraries(
    request: Request,
    kind: str | None = None,
    gradeId: str | None = None,
    subjectId: str | None = None,
    editionId: str | None = None,
    includeDeleted: bool = False,
) -> LibraryList:
    catalog = _catalog(request)
    query = LibraryQuery(
        kind=kind,
        gradeId=gradeId,
        subjectId=subjectId,
        editionId=editionId,
        includeDeleted=includeDeleted,
    )

    def load() -> LibraryList:
        context = ViewContext(catalog)
        records = catalog.list_libraries(
            kind=query.kind,
            grade_id=query.gradeId,
            subject_id=query.subjectId,
            edition_id=query.editionId,
            include_deleted=query.includeDeleted,
        )
        return LibraryList(libraries=[context.library_summary(record) for record in records])

    return await run_in_thread(load)


@router.post("/textbook-libraries", status_code=status.HTTP_201_CREATED)
async def create_textbook_library(request: Request, body: LibraryCreateRequest) -> LibrarySummary:
    catalog = _catalog(request)

    def create() -> LibrarySummary:
        context = ViewContext(catalog)
        record = catalog.create_library(
            kind=body.kind,
            owner_id="local-user" if body.kind == "personal" else "system",
            display_name=body.displayName,
            grade_id=body.gradeId,
            subject_id=body.subjectId,
            edition_id=body.editionId,
        )
        return context.library_summary(record)

    return await run_in_thread(create)


@router.get("/textbook-libraries/{library_id}")
async def get_textbook_library(request: Request, library_id: str) -> LibraryDetail:
    catalog = _catalog(request)

    def load() -> LibraryDetail:
        record = catalog.get_library(library_id)
        if record is None or record.deleted_at is not None:
            raise AppError("逻辑库不存在或已停用。", code="LIBRARY_NOT_FOUND", status_code=404)
        return ViewContext(catalog).library_detail(record)

    return await run_in_thread(load)


@router.patch("/textbook-libraries/{library_id}")
async def patch_textbook_library(
    request: Request, library_id: str, body: LibraryPatchRequest
) -> LibrarySummary:
    catalog = _catalog(request)

    def update() -> LibrarySummary:
        record = catalog.update_library(
            library_id,
            expected_revision=body.expectedRevision,
            display_name=body.displayName,
            grade_id=body.gradeId,
            edition_id=body.editionId,
        )
        return ViewContext(catalog).library_summary(record)

    return await run_in_thread(update)


@router.delete("/textbook-libraries/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_textbook_library(
    request: Request, library_id: str, body: DocumentDeleteRequest
) -> Response:
    catalog = _catalog(request)

    def remove() -> None:
        catalog.delete_library(library_id, expected_revision=body.expectedRevision)

    await run_in_thread(remove)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- 书册


@router.get("/textbooks")
async def list_textbooks(
    request: Request,
    libraryId: str | None = None,
    gradeId: str | None = None,
    subjectId: str | None = None,
    editionId: str | None = None,
    includeDeleted: bool = False,
) -> DocumentList:
    catalog = _catalog(request)
    query = DocumentQuery(
        libraryId=libraryId,
        gradeId=gradeId,
        subjectId=subjectId,
        editionId=editionId,
        includeDeleted=includeDeleted,
    )

    def load() -> DocumentList:
        context = ViewContext(catalog)
        records = catalog.list_documents(
            library_id=query.libraryId,
            grade_id=query.gradeId,
            subject_id=query.subjectId,
            edition_id=query.editionId,
            include_deleted=query.includeDeleted,
        )
        return DocumentList(documents=[context.document_summary(record) for record in records])

    return await run_in_thread(load)


@router.get("/textbooks/{document_id}")
async def get_textbook(request: Request, document_id: str) -> DocumentDetail:
    catalog = _catalog(request)

    def load() -> DocumentDetail:
        record = catalog.get_document(document_id)
        if record is None or record.deleted_at is not None:
            raise AppError("教材不存在或已停用。", code="DOCUMENT_UNAVAILABLE", status_code=404)
        return ViewContext(catalog).document_detail(record)

    return await run_in_thread(load)


@router.patch("/textbooks/{document_id}")
async def patch_textbook(
    request: Request, document_id: str, body: DocumentPatchRequest
) -> DocumentDetail:
    catalog = _catalog(request)

    def update() -> DocumentDetail:
        record = catalog.update_document_metadata(
            document_id,
            expected_revision=body.expectedRevision,
            title=body.metadata.title,
            stage_id=body.metadata.stageId,
            grade_ids=body.metadata.gradeIds,
            subject_id=body.metadata.subjectId,
            edition_id=body.metadata.editionId,
            publication_label=body.metadata.publicationLabel,
            volume_label=body.metadata.volumeLabel,
            library_ids=body.libraryIds,
        )
        return ViewContext(catalog).document_detail(record)

    return await run_in_thread(update)


@router.delete("/textbooks/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_textbook(
    request: Request, document_id: str, body: DocumentDeleteRequest
) -> Response:
    catalog = _catalog(request)

    def remove() -> None:
        catalog.delete_document(document_id, expected_revision=body.expectedRevision)

    await run_in_thread(remove)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------------ 导入草稿


@router.post("/textbook-imports", status_code=status.HTTP_201_CREATED)
async def create_textbook_import(request: Request) -> ImportCreateResponse:
    ingest = _ingest(request)
    content_type = request.headers.get("content-type", "")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD:
        raise AppError(
            f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
            code="DOCUMENT_TOO_LARGE",
            status_code=413,
        )
    raw = await request.body()
    if len(raw) > MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD:
        raise AppError(
            f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
            code="DOCUMENT_TOO_LARGE",
            status_code=413,
        )
    form = await run_in_thread(parse_multipart_form, raw, content_type)
    file_part = form.get("file")
    if file_part is None or file_part.filename is None:
        raise AppError(
            "上传请求缺少 file 部件。",
            code="INVALID_REQUEST",
            status_code=422,
        )
    if len(file_part.data) > MAX_UPLOAD_BYTES:
        raise AppError(
            f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
            code="DOCUMENT_TOO_LARGE",
            status_code=413,
        )
    metadata_part = form.get("metadataJson")
    options = parse_import_form_metadata(metadata_part.text() if metadata_part else None)
    draft = await run_in_thread(
        ingest.create_import,
        file_name=file_part.filename,
        data=file_part.data,
        metadata=options.metadata,
        target_document_id=options.target_document_id,
        expected_current_revision_id=options.expected_current_revision_id,
        confirm_metadata=options.confirm_metadata,
    )
    return ImportCreateResponse(draft=draft)


@router.get("/textbook-imports")
async def list_textbook_imports(
    request: Request, limit: int = Query(default=50, ge=1, le=200)
) -> ImportDraftList:
    ingest = _ingest(request)
    drafts = await run_in_thread(ingest.list_import_views, limit=limit)
    return ImportDraftList(imports=drafts)


@router.get("/textbook-imports/{import_id}")
async def get_textbook_import(request: Request, import_id: str) -> ImportDraftView:
    ingest = _ingest(request)
    return await run_in_thread(ingest.get_import_view, import_id)


@router.patch("/textbook-imports/{import_id}")
async def patch_textbook_import(
    request: Request, import_id: str, body: ImportPatchRequest
) -> ImportDraftView:
    ingest = _ingest(request)
    return await run_in_thread(
        ingest.update_import_metadata,
        import_id,
        expected_revision=body.expectedRevision,
        metadata=_metadata_dict(body.metadata),
    )


@router.post("/textbook-imports/{import_id}/commit")
async def commit_textbook_import(
    request: Request,
    import_id: str,
    body: ImportCommitRequest,
    background_tasks: BackgroundTasks,
) -> JobView:
    ingest = _ingest(request)
    job = await run_in_thread(
        ingest.commit_import,
        import_id,
        expected_revision=body.expectedRevision,
        submission_id=body.submissionId,
        library_ids=body.libraryIds,
        acknowledge_warnings=body.acknowledgeWarnings,
    )
    # 入库在后台线程执行；响应先返回 queued 任务，轮询 /textbook-jobs 获取真实进度
    background_tasks.add_task(ingest.recover_pending_jobs)
    return job


@router.post("/textbook-imports/{import_id}/discard")
async def discard_textbook_import(
    request: Request, import_id: str, body: ImportDiscardRequest
) -> ImportDraftView:
    ingest = _ingest(request)
    return await run_in_thread(
        ingest.discard_import, import_id, expected_revision=body.expectedRevision
    )


# --------------------------------------------------------------------------- 任务


@router.get("/textbook-jobs")
async def list_textbook_jobs(
    request: Request, limit: int = Query(default=50, ge=1, le=200)
) -> JobList:
    catalog = _catalog(request)
    records = await run_in_thread(catalog.list_jobs, limit=limit)
    return JobList(jobs=[job_view(record) for record in records])


@router.get("/textbook-jobs/{job_id}")
async def get_textbook_job(request: Request, job_id: str) -> JobView:
    catalog = _catalog(request)
    record = await run_in_thread(catalog.get_job, job_id)
    if record is None:
        raise AppError("索引任务不存在。", code="JOB_NOT_FOUND", status_code=404)
    return job_view(record)


@router.post("/textbook-jobs/{job_id}/cancel")
async def cancel_textbook_job(request: Request, job_id: str) -> JobView:
    catalog = _catalog(request)
    record = await run_in_thread(catalog.get_job, job_id)
    if record is None:
        raise AppError("索引任务不存在。", code="JOB_NOT_FOUND", status_code=404)
    if record.kind == "ingest":
        return await run_in_thread(_ingest(request).cancel_job, job_id)
    return await run_in_thread(_index(request).cancel_job, job_id)


@router.post("/textbook-jobs/{job_id}/retry")
async def retry_textbook_job(
    request: Request, job_id: str, background_tasks: BackgroundTasks
) -> JobView:
    catalog = _catalog(request)
    record = await run_in_thread(catalog.get_job, job_id)
    if record is None:
        raise AppError("索引任务不存在。", code="JOB_NOT_FOUND", status_code=404)
    if record.kind != "ingest":
        raise AppError(
            "重建请重新发起新的索引代；本接口只重试入库任务。",
            code="RETRY_NOT_SUPPORTED",
            status_code=409,
        )
    ingest = _ingest(request)
    job = await run_in_thread(ingest.retry_job, job_id)
    background_tasks.add_task(ingest.recover_pending_jobs)
    return job


# ------------------------------------------------------------------------ 受控原文


@router.get("/textbook-revisions/{revision_id}/source")
async def get_textbook_revision_source(
    request: Request,
    revision_id: str,
    charStart: int = Query(ge=0),
    charEnd: int = Query(gt=0),
) -> SourceSpanView:
    ingest = _ingest(request)
    return await run_in_thread(
        ingest.source_span, revision_id, char_start=charStart, char_end=charEnd
    )


# ------------------------------------------------------------------------ 任教设置


@router.get("/teaching-settings")
async def get_teaching_settings(request: Request) -> TeachingSettingsView:
    catalog = _catalog(request)
    return await run_in_thread(ViewContext(catalog).teaching_settings)


@router.put("/teaching-settings")
async def put_teaching_settings(
    request: Request, body: TeachingSettingsUpdate
) -> TeachingSettingsView:
    catalog = _catalog(request)

    def update() -> TeachingSettingsView:
        selection = body.selection
        catalog.set_teaching_settings(
            selection_json=selection.model_dump() if selection is not None else None,
            expected_revision=body.expectedRevision,
        )
        return ViewContext(catalog).teaching_settings()

    return await run_in_thread(update)


@router.post("/teaching-settings/scope-check")
async def check_teaching_scope(request: Request, body: ScopeCheckRequest) -> ScopeCheckView:
    catalog = _catalog(request)
    return await run_in_thread(scope_check_view, catalog, body.selection)
