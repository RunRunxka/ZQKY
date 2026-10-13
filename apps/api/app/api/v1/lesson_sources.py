"""Real owner-scoped confirmed revision selector; no model or write operations.

2026-10-13 追加：``POST /lesson-plans/source-uploads``（教师上传学情材料 → ``assetRef``）。
该端点此前只有前端调用、后端未实现（501 ``FEATURE_NOT_IMPLEMENTED``）；现在按
「只收可提取文本的文档、表格类给学情分析指引」的口径做实（见 ``services.lesson_sources``）。
"""
import functools
import anyio
from fastapi import APIRouter, Query, Request
from app.contracts.b4 import Page
from app.contracts.lesson_sources import ConfirmedQuestionRevision, LessonSourceUploadView
from app.core.exceptions import AppError
from app.schemas.textbook import MAX_UPLOAD_BYTES
from app.services.lesson_sources import MAX_SOURCE_BYTES
from app.services.textbook_ingest.multipart import parse_multipart_form

router = APIRouter(tags=["lesson-sources"])

#: multipart 头部/边界开销的宽松上界（超出此值在解析前直接 413）
_MULTIPART_OVERHEAD = 4096


@router.get("/confirmed-question-revisions", response_model=Page[ConfirmedQuestionRevision])
async def confirmed_question_revisions(request: Request, subjectId: str = Query(min_length=1, max_length=64),
                                       offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    reader = getattr(request.app.state, "fixed_question_reader", None)
    questions = getattr(request.app.state, "question_bank_service", None)
    if reader is None or questions is None:
        raise AppError("固定题库来源未装配。", code="SERVICE_UNAVAILABLE", status_code=503)
    # R4 题库服务重建后未挂 owner 属性（归档服务有 owner_id）；owner 语义是"题库域
    # 自留的本地归属"，读 path 兜底用默认归属，不发明第二套归属来源。
    owner_id = getattr(questions, "owner_id", "local")
    snapshots, total = await anyio.to_thread.run_sync(functools.partial(
        reader.list_confirmed_page, subject_id=subjectId, owner_id=owner_id, offset=offset, limit=limit))
    items = []
    for item in snapshots:
        stem = item.content.get("stemMarkdown")
        if not isinstance(stem, str):
            raise AppError("固定题目内容损坏。", code="QUESTION_ROW_CORRUPT", status_code=500)
        items.append(ConfirmedQuestionRevision(question_id=item.question_id,
            question_revision_id=item.question_revision_id, subject_id=item.subject_id, stem_markdown=stem))
    return Page(items=items, total=total, offset=offset, limit=limit)


@router.post("/lesson-plans/source-uploads", response_model=LessonSourceUploadView, status_code=201)
async def upload_lesson_source(request: Request) -> LessonSourceUploadView:
    """上传学情材料（multipart ``file``）→ 受管资产 ``assetRef``。

    只接受可提取文本的文档（.docx/.pdf/.txt/.md）；成绩表类（.xlsx/.xls/.csv）返回 422
    并给出「先在学情分析生成报告、再用『分析报告』来源」的指引——不把含学号/姓名的原始
    表格送进模型（见 ``services/lesson_sources`` 的红线口径）。空文件/超限如实 422/413。
    """
    service = getattr(request.app.state, "lesson_source_service", None)
    if service is None:
        raise AppError(
            "学情材料服务未装配：后端缺少对应服务，请检查启动日志与依赖。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    content_type = request.headers.get("content-type", "")
    declared = request.headers.get("content-length")
    limit = min(MAX_UPLOAD_BYTES, MAX_SOURCE_BYTES) + _MULTIPART_OVERHEAD
    if declared and declared.isdigit() and int(declared) > limit:
        raise AppError(
            f"上传文件超过 {MAX_SOURCE_BYTES // (1024 * 1024)} MiB 上限。",
            code="UPLOAD_TOO_LARGE",
            status_code=413,
        )
    raw = await request.body()
    if len(raw) > limit:
        raise AppError(
            f"上传文件超过 {MAX_SOURCE_BYTES // (1024 * 1024)} MiB 上限。",
            code="UPLOAD_TOO_LARGE",
            status_code=413,
        )
    form = await anyio.to_thread.run_sync(functools.partial(parse_multipart_form, raw, content_type))
    file_part = form.get("file")
    if file_part is None or file_part.filename is None:
        raise AppError("上传请求缺少 file 部件。", code="INVALID_REQUEST", status_code=422)
    if len(file_part.data) > MAX_SOURCE_BYTES:
        raise AppError(
            f"上传文件超过 {MAX_SOURCE_BYTES // (1024 * 1024)} MiB 上限。",
            code="UPLOAD_TOO_LARGE",
            status_code=413,
        )
    stored = await anyio.to_thread.run_sync(
        functools.partial(
            service.upload,
            data=file_part.data,
            file_name=file_part.filename,
            media_type=file_part.content_type or "application/octet-stream",
        )
    )
    return LessonSourceUploadView(
        assetRef=stored.asset_ref,
        fileName=stored.file_name,
        mediaType=stored.media_type,
        byteSize=stored.byte_size,
        sha256=stored.sha256,
    )
