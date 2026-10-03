"""题库接口：导入拆题、草稿校对、拆分/合并、AI 整理建议、幂等确认与题目管理。

取服务：目录来自 ``request.app.state.question_bank``，业务服务来自
``request.app.state.question_bank_service``；服务为 ``None`` 时统一 503
``SERVICE_UNAVAILABLE``（可重试），绝不返回空列表或假成功。
``organize`` 是 async 服务方法（模型经注入的 ``model_resolver`` 解析、调用在 SQL 写事务外），
路由直接 ``await``；其余同步重活（SQL、文件、解析）都在有界线程中执行。
"""

from __future__ import annotations

import functools
import json

import anyio
from fastapi import APIRouter, Query, Request, Response, status
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.schemas.question_bank import (
    ConfirmResult,
    DraftMergeRequest,
    DraftPatchRequest,
    DraftSplitRequest,
    DraftView,
    GenerationJobView,
    OrganizeJobView,
    OrganizeRequest,
    QuestionConfirmRequest,
    QuestionDetail,
    QuestionGenerationRequest,
    QuestionImportCreate,
    QuestionImportDetail,
    QuestionImportList,
    QuestionList,
    QuestionPatchRequest,
    SuggestionApplyRequest,
)
from app.schemas.textbook import MAX_UPLOAD_BYTES
from app.services.question_bank.service import QuestionBankService
from app.services.textbook_ingest.multipart import MultipartPart, parse_multipart_form

router = APIRouter(tags=["question-bank"])


@router.get('/question-drafts/{draft_id}/assets/{asset_id:path}/content')
async def get_draft_asset(request: Request, draft_id: str, asset_id: str) -> Response:
    service = _service(request)
    data, media_type = await _run(service.get_content_asset, 'draft', draft_id, asset_id)
    return Response(content=data, media_type=media_type)


@router.get('/questions/{question_id}/assets/{asset_id:path}/content')
async def get_question_asset(request: Request, question_id: str, asset_id: str) -> Response:
    service = _service(request)
    data, media_type = await _run(service.get_content_asset, 'question', question_id, asset_id)
    return Response(content=data, media_type=media_type)

#: multipart 头部/边界开销的宽松上界（超出此值在解析前直接 413）
_MULTIPART_OVERHEAD = 4096

_LABEL_CATALOG = "题库目录"
_LABEL_SERVICE = "题库服务"


def _require(service, *, label: str):
    if service is None:
        raise AppError(
            f"{label}未装配：后端缺少对应服务，请检查启动日志与依赖。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return service


def _catalog(request: Request) -> QuestionBankCatalog:
    return _require(getattr(request.app.state, "question_bank", None), label=_LABEL_CATALOG)


def _service(request: Request) -> QuestionBankService:
    # 目录与服务必须同时装配：缺任一项都返回 503，而不是空结果
    _catalog(request)
    return _require(
        getattr(request.app.state, "question_bank_service", None), label=_LABEL_SERVICE
    )


async def _run(fn, /, *args, **kwargs):
    """把同步的 SQL/文件/模型调用放到有界线程里执行，不阻塞事件循环。"""
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


def _import_options(form: dict[str, MultipartPart]) -> QuestionImportCreate:
    payload: dict[str, object] = {}
    metadata_part = form.get("metadataJson")
    if metadata_part is not None:
        raw = metadata_part.text()
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise AppError(
                "metadataJson 不是合法 JSON。", code="INVALID_REQUEST", status_code=422
            ) from exc
        if not isinstance(parsed, dict):
            raise AppError(
                "metadataJson 必须是 JSON 对象。", code="INVALID_REQUEST", status_code=422
            )
        payload.update(parsed)
    for key in ("subjectId", "gradeId"):
        part = form.get(key)
        if part is not None:
            payload[key] = part.text().strip()
    try:
        return QuestionImportCreate.model_validate(payload)
    except ValidationError as exc:
        raise AppError(
            "题目导入的分类字段不合法。", code="INVALID_REQUEST", status_code=422
        ) from exc


def _too_large() -> AppError:
    return AppError(
        f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
        code="DOCUMENT_TOO_LARGE",
        status_code=413,
    )


# --------------------------------------------------------------------------- 导入


@router.post("/question-imports", status_code=status.HTTP_201_CREATED)
async def create_question_import(request: Request) -> QuestionImportDetail:
    service = _service(request)
    content_type = request.headers.get("content-type", "")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD:
        raise _too_large()
    raw = await request.body()
    if len(raw) > MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD:
        raise _too_large()
    form = await _run(parse_multipart_form, raw, content_type)
    file_part = form.get("file")
    if file_part is None or file_part.filename is None:
        raise AppError("上传请求缺少 file 部件。", code="INVALID_REQUEST", status_code=422)
    if len(file_part.data) > MAX_UPLOAD_BYTES:
        raise _too_large()
    options = _import_options(form)
    return await _run(
        service.create_import,
        file_name=file_part.filename,
        data=file_part.data,
        subject_id=options.subjectId,
        grade_id=options.gradeId,
    )


@router.get("/question-imports")
async def list_question_imports(
    request: Request, limit: int = Query(default=50, ge=1, le=200)
) -> QuestionImportList:
    service = _service(request)
    return await _run(service.list_imports, limit=limit)


@router.get("/question-imports/{import_id}")
async def get_question_import(request: Request, import_id: str) -> QuestionImportDetail:
    service = _service(request)
    return await _run(service.get_import_detail, import_id)


# --------------------------------------------------------------------------- 草稿


@router.patch("/question-drafts/{draft_id}")
async def patch_question_draft(
    request: Request, draft_id: str, body: DraftPatchRequest
) -> DraftView:
    service = _service(request)
    return await _run(service.patch_draft, draft_id, body)


@router.post("/question-imports/{import_id}/split")
async def split_question_draft(
    request: Request,
    import_id: str,
    body: DraftSplitRequest,
    draftId: str | None = Query(default=None),
) -> QuestionImportDetail:
    service = _service(request)
    return await _run(service.split_draft, import_id, body, draft_id=draftId)


@router.post("/question-imports/{import_id}/merge")
async def merge_question_drafts(
    request: Request, import_id: str, body: DraftMergeRequest
) -> QuestionImportDetail:
    service = _service(request)
    return await _run(service.merge_drafts, import_id, body)


# ------------------------------------------------------------------------- AI 整理


@router.post("/question-imports/{import_id}/organize")
async def organize_question_import(
    request: Request, import_id: str, body: OrganizeRequest
) -> OrganizeJobView:
    """AI 整理：模型 = 点击时的当前聊天模型（``modelProfileId``），服务层自身是 async。"""
    service = _service(request)
    return await service.organize(import_id, body)


@router.post("/question-suggestions/{suggestion_id}/apply")
async def apply_question_suggestion(
    request: Request, suggestion_id: str, body: SuggestionApplyRequest
) -> DraftView:
    service = _service(request)
    return await _run(service.apply_suggestion, suggestion_id, body)


# --------------------------------------------------------------------------- AI 补题


@router.post(
    "/question-generation-jobs", status_code=status.HTTP_202_ACCEPTED
)
async def create_question_generation_job(
    request: Request, body: QuestionGenerationRequest
) -> GenerationJobView:
    """AI 补题：202 只代表任务被接受；候选落在 ``needs_review`` 草稿批次里，
    结果经 ``GET /workflow-jobs/{jobId}?domain=question`` 观察（六态 + attempt）。"""
    service = _service(request)
    return await service.create_generation_job(body)


# ------------------------------------------------------------------------- 确认入库


@router.post("/question-imports/{import_id}/confirm")
async def confirm_question_import(
    request: Request, import_id: str, body: QuestionConfirmRequest
) -> ConfirmResult:
    service = _service(request)
    if body.importId != import_id:
        raise AppError(
            "请求体 importId 与路径不一致。", code="INVALID_REQUEST", status_code=422
        )
    return await _run(service.confirm, body)


# --------------------------------------------------------------------------- 题目


@router.get("/questions")
async def list_questions(
    request: Request,
    subjectId: str | None = None,
    gradeId: str | None = None,
    editionId: str | None = None,
    status: str | None = None,
    q: str | None = None,
    knowledgePointId: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
) -> QuestionList:
    service = _service(request)
    return await _run(
        service.list_questions,
        subject_id=subjectId,
        grade_id=gradeId,
        edition_id=editionId,
        status=status,
        query=q,
        knowledge_point_id=knowledgePointId,
        offset=offset,
        limit=limit,
    )


@router.get("/questions/{question_id}")
async def get_question(request: Request, question_id: str) -> QuestionDetail:
    service = _service(request)
    return await _run(service.get_question, question_id)


@router.patch("/questions/{question_id}")
async def patch_question(
    request: Request, question_id: str, body: QuestionPatchRequest
) -> QuestionDetail:
    """改题 = 追加新修订；``knowledgeLinks`` 提供即整表替换（`[]` 清空），缺省复制旧正式关联。"""
    service = _service(request)
    return await _run(
        service.patch_question, question_id, body, knowledge_links=body.knowledgeLinks
    )


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    request: Request,
    question_id: str,
    expectedRevision: int | None = Query(default=None, ge=0),
) -> Response:
    service = _service(request)
    await _run(service.delete_question, question_id, expected_revision=expectedRevision)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
