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
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
    QuestionImportDeleteResult,
    QuestionImportDetail,
    QuestionImportDiscardRequest,
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


class TextbookExerciseImportRequest(BaseModel):
    """教材课后习题 → 题目导入草稿（C4-2）：exercise chunks 拼成 markdown 走既有导入校对链。

    重建适配（R4-BE）：归档实现取自 ``app.contracts.b4.Frozen``；该契约未随本批回归，
    这里按同一配置（``extra=forbid`` + ``frozen`` + ``populate_by_name``）就地声明，
    字段与取值一字不改。``b4`` 契约回归后应改回从那里导入。
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    subject_id: str = Field(default="math", alias="subjectId", max_length=64)
    grade_id: str = Field(default="", alias="gradeId", max_length=64)
    document_ids: list[str] = Field(default_factory=list, alias="documentIds", max_length=50)
    chapter_prefix: str = Field(default="", alias="chapterPrefix", max_length=200)


@router.post("/question-imports/from-textbook", status_code=status.HTTP_201_CREATED)
async def import_from_textbook_exercises(request: Request, body: TextbookExerciseImportRequest) -> QuestionImportDetail:
    """把已入库教材的课后习题区域（region=exercise）提取为题目导入草稿（只产草稿，教师校对确认）。"""
    service = _service(request)
    catalog = getattr(request.app.state, "catalog", None)
    if catalog is None:
        raise AppError("教材目录未装配，无法读取教材习题。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)

    def _work() -> QuestionImportDetail:
        documents = catalog.list_documents(subject_id=body.subject_id, grade_id=body.grade_id or None)
        if body.document_ids:
            wanted = set(body.document_ids)
            documents = [d for d in documents if d.document_id in wanted]
        sections: list[str] = []
        for document in documents:
            if document.current_revision_id is None:
                continue
            evidence = getattr(request.app.state, "textbook_evidence", None)
            revision = catalog.get_revision(document.current_revision_id)
            if revision is None or evidence is None or not hasattr(evidence, "_source"):
                continue
            normalized = evidence._source.read_normalized_text(revision)  # noqa: SLF001 - 提取端点读取封存正文
            for chunk_set in _textbook_chunk_sets(catalog, document.current_revision_id):
                for chunk in catalog.list_chunks(chunk_set.chunk_set_id):
                    if chunk.region != "exercise" or not chunk.text_sha256:
                        continue
                    path = tuple(str(part) for part in chunk.chapter_path)
                    if body.chapter_prefix and (not path or not path[0].startswith(body.chapter_prefix)):
                        continue
                    text = normalized[chunk.char_start:chunk.char_end]
                    if text and text.strip():
                        heading = " / ".join(path) if path else document.title
                        sections.append(f"## {document.title}｜{heading}\n\n{text.strip()}")
        if not sections:
            raise AppError(
                "所选教材没有可提取的课后习题区域；请确认教材已入库并完成索引。",
                code="TEXTBOOK_EXERCISES_EMPTY",
                status_code=422,
            )
        document_text = "\n\n".join(sections)
        if len(document_text.encode("utf-8")) > MAX_UPLOAD_BYTES:
            raise AppError("所选教材习题总量超过单次导入上限，请缩小教材或章节范围。", code="DOCUMENT_TOO_LARGE", status_code=413)
        return service.create_import(
            file_name=f"教材课后习题-{body.subject_id}.md",
            data=document_text.encode("utf-8"),
            subject_id=body.subject_id,
            grade_id=body.grade_id,
        )

    return await _run(_work)


def _textbook_chunk_sets(catalog, document_revision_id: str):
    with catalog._read() as conn:  # noqa: SLF001 - 只读 chunk_sets（提取端点专用）
        rows = conn.execute(
            "SELECT id FROM chunk_sets WHERE document_revision_id = ?", (document_revision_id,)
        ).fetchall()
    for row in rows:
        record = catalog.get_chunk_set(row["id"])
        if record is not None:
            yield record


@router.post("/question-imports/{import_id}/discard")
async def discard_question_import(
    request: Request, import_id: str, body: QuestionImportDiscardRequest
) -> QuestionImportDetail:
    """放弃未确认批次（误上传清理）：状态置 ``cancelled``，批次记录/原文/草稿保留。"""
    service = _service(request)
    return await _run(service.discard_import, import_id, body)


@router.delete("/question-imports/{import_id}")
async def delete_question_import(
    request: Request, import_id: str
) -> QuestionImportDeleteResult:
    """彻底删除导入批次及其解析产物（与放弃互补：放弃保留记录，删除移除记录）。

    R10（2026-10-13 用户裁定「批次只是记录」）：**已确认批次同样可删**，题目一律保留
    （``question_sources.import_id`` 置空、来源跨度保留，回执 ``unlinkedQuestionSources``）；
    单写事务按 FK 顺序删除批次全部库行；**受管原件（blobs）不物理删除**——内容寻址、
    可能被其他批次复用，保留待独立清理策略，本接口不宣称原件已删。
    """
    service = _service(request)
    return await _run(service.delete_import, import_id)


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
    difficulty: str | None = Query(default=None, pattern="^(easy|medium|hard|unspecified)$"),
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
        difficulty=difficulty,
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
