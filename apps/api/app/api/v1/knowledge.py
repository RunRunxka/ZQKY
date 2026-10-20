"""知识点接口（TEACHING-LOOP B1 / T20）。

取服务：``request.app.state.knowledge_service``；未装配统一 503 ``SERVICE_UNAVAILABLE``
（可重试），绝不返回空列表或假成功。同步重活（SQL、表格解析、资产落盘）都在
``anyio.to_thread.run_sync`` 的有界线程里执行；``create_suggestion_job`` 是 async
服务方法（内部只在建任务/读证据时用线程池，任务调度留在事件循环线程）。

错误语义：错误信封与 B0 一致；父树/行级问题带 ``details.issues``（``row``/``field``
可定位），乐观锁冲突 409 ``REVISION_CONFLICT`` + ``details.currentRevision``。
"""

from __future__ import annotations

import functools
import json

import anyio
from fastapi import APIRouter, Query, Request, Response, status

from app.contracts.knowledge import (
    KnowledgeExtractionPreview,
    KnowledgeExtractionRequest,
    KnowledgeImportConfirmRequest,
    KnowledgeImportConfirmResult,
    KnowledgeImportDiscardRequest,
    KnowledgeImportList,
    KnowledgeImportPatchRequest,
    KnowledgeImportView,
    KnowledgePointCreateRequest,
    KnowledgePointList,
    KnowledgePointRevisionRequest,
    KnowledgePointUpdateRequest,
    KnowledgePointView,
    KnowledgeSuggestionRequest,
    TextbookLinkCreateRequest,
    TextbookLinkList,
    TextbookLinkView,
)
from app.contracts.teaching_loop import JobView
from app.core.exceptions import AppError
from pydantic import Field
from app.contracts.knowledge import _Strict as _StrictBase
from app.services.knowledge.service import MAX_UPLOAD_BYTES, KnowledgeService
from app.services.textbook_ingest.multipart import MultipartPart, parse_multipart_form

router = APIRouter(tags=["knowledge"])

#: multipart 头部/边界开销的宽松上界（超出此值在解析前直接 413）
_MULTIPART_OVERHEAD = 4096

_LABEL_SERVICE = "知识点服务"


def _require(service, *, label: str):
    if service is None:
        raise AppError(
            f"{label}未装配：后端缺少对应服务，请检查启动日志与依赖。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return service


def _service(request: Request) -> KnowledgeService:
    return _require(getattr(request.app.state, "knowledge_service", None), label=_LABEL_SERVICE)


async def _run(fn, /, *args, **kwargs):
    """把同步的 SQL/文件调用放到有界线程执行（事件循环里不跑同步数据库调用）。"""
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


def _too_large() -> AppError:
    return AppError(
        f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
        code="DOCUMENT_TOO_LARGE",
        status_code=413,
    )


def _json_object(part: MultipartPart | None, *, field: str) -> dict | None:
    if part is None:
        return None
    try:
        parsed = json.loads(part.text())
    except ValueError as exc:
        raise AppError(
            f"{field} 不是合法 JSON。", code="INVALID_REQUEST", status_code=422
        ) from exc
    if not isinstance(parsed, dict):
        raise AppError(
            f"{field} 必须是 JSON 对象。", code="INVALID_REQUEST", status_code=422
        )
    return parsed


# --------------------------------------------------------------------------- 知识点


@router.get("/knowledge-points")
async def list_knowledge_points(
    request: Request,
    subjectId: str | None = None,
    parentId: str | None = None,
    q: str | None = None,
    scope: str | None = None,
    gradeId: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> KnowledgePointList:
    service = _service(request)
    return await _run(
        service.list_points,
        subject_id=subjectId,
        parent_id=parentId,
        q=q,
        scope=scope,
        grade_id=gradeId,
        offset=offset,
        limit=limit,
    )


@router.post("/knowledge-points", status_code=status.HTTP_201_CREATED)
async def create_knowledge_point(
    request: Request, body: KnowledgePointCreateRequest
) -> KnowledgePointView:
    service = _service(request)
    return await _run(service.create_point, body)


class TreeFromTextbookRequest(_StrictBase):
    """教材目录 → 知识点树（C4-1）：subject 默认数学；documentIds 可选限定教材。"""

    subject_id: str = Field(default="math", alias="subjectId", max_length=64)
    document_ids: list[str] = Field(default_factory=list, alias="documentIds", max_length=50)


@router.post("/knowledge-points/tree-from-textbook")
async def generate_tree_from_textbook(request: Request, body: TreeFromTextbookRequest) -> dict:
    """从已入库教材的**正文标题**（Markdown 标题路径）反向生成知识点树（幂等；章节为容器节点）。

    R11 口径：按封存原文的标题读目录，不按分块起点采样 ``chapter_path``（短章节会漏、
    习题标题会被重叠尾巴带进来）；习题/练习类标题段由 ``tree_gen`` 过滤，不作为知识点。
    教师可在生成后的任何节点下继续自定义增删改（走既有 create/update/delete）。
    """
    service = _service(request)
    catalog = getattr(request.app.state, "catalog", None)
    if catalog is None:
        raise AppError("教材目录未装配，无法读取教材目录。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)
    evidence = getattr(request.app.state, "textbook_evidence", None)
    if evidence is None or not hasattr(evidence, "_source"):
        raise AppError(
            "教材原文读取器未装配，无法读取教材目录。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )

    def _work() -> dict:
        from app.services.document_parsing.chunking import heading_paths
        from app.services.knowledge.tree_gen import TextbookInput, plan_tree

        documents = catalog.list_documents(subject_id=body.subject_id)
        if body.document_ids:
            wanted = set(body.document_ids)
            documents = [d for d in documents if d.document_id in wanted]
        books: list[TextbookInput] = []
        for document in documents:
            if document.current_revision_id is None:
                continue
            revision = catalog.get_revision(document.current_revision_id)
            if revision is None:
                raise AppError(
                    f"教材《{document.title}》的当前修订记录缺失，无法读取目录。",
                    code="SERVICE_UNAVAILABLE",
                    status_code=503,
                    retryable=True,
                )
            try:
                normalized = evidence._source.read_normalized_text(revision)  # noqa: SLF001 - 只读封存正文（生成端点专用）
            except AppError as exc:
                # 原文不可读绝不静默跳过：漏一本书的目录等于给出一棵不完整的树
                raise AppError(
                    f"教材《{document.title}》的原文当前不可读，无法读取目录：{exc}",
                    code="SERVICE_UNAVAILABLE",
                    status_code=503,
                    retryable=True,
                ) from exc
            except Exception as exc:  # noqa: BLE001 - 读取实现未知异常一律按不可用处理
                raise AppError(
                    f"教材《{document.title}》的原文当前不可读，无法读取目录。",
                    code="SERVICE_UNAVAILABLE",
                    status_code=503,
                    retryable=True,
                ) from exc
            if not isinstance(normalized, str):
                raise AppError(
                    f"教材《{document.title}》的规范化原文读取结果非法，无法读取目录。",
                    code="SERVICE_UNAVAILABLE",
                    status_code=503,
                    retryable=True,
                )
            books.append(
                TextbookInput(
                    title=document.title,
                    document_id=document.document_id,
                    chapter_paths=heading_paths(normalized),
                )
            )
        plan = plan_tree(body.subject_id, books)
        created, skipped = 0, 0
        for node in plan.nodes:
            try:
                service.create_point(KnowledgePointCreateRequest(
                    subjectId=body.subject_id, code=node.code, name=node.name,
                    parentCode=node.parent_code, sortOrder=node.sort_order,
                    description=f"教材目录节点（文档 {node.document_id}）",
                ))
                created += 1
            except AppError as exc:
                if exc.code in ("KNOWLEDGE_CODE_CONFLICT",):
                    skipped += 1
                else:
                    raise
        return {"created": created, "skipped": skipped, "total": len(plan.nodes), "books": len(books)}

    return await _run(_work)


@router.get("/knowledge-points/{point_id}")
async def get_knowledge_point(request: Request, point_id: str) -> KnowledgePointView:
    service = _service(request)
    return await _run(service.get_point, point_id)


@router.patch("/knowledge-points/{point_id}")
async def update_knowledge_point(
    request: Request, point_id: str, body: KnowledgePointUpdateRequest
) -> KnowledgePointView:
    service = _service(request)
    return await _run(service.update_point, point_id, body)


@router.delete("/knowledge-points/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_point(
    request: Request,
    point_id: str,
    expectedRevision: int = Query(ge=0),
) -> Response:
    """彻底删除知识点**及其整棵子树**（物理删除，不可恢复）。

    子树内任一节点有教材依据、原卷题目或题库引用 → 409 ``KNOWLEDGE_POINT_IN_USE``，
    ``details.points`` 逐节点给出引用计数；引用检查端口缺失 → 503。根节点
    ``expectedRevision`` 不符 → 409 ``REVISION_CONFLICT``。
    """
    service = _service(request)
    await _run(
        service.delete_point,
        point_id,
        KnowledgePointRevisionRequest(expected_revision=expectedRevision),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- 教材依据


@router.get("/knowledge-points/{point_id}/textbook-links")
async def list_textbook_links(request: Request, point_id: str) -> TextbookLinkList:
    service = _service(request)
    return await _run(service.list_textbook_links, point_id)


@router.post("/knowledge-points/{point_id}/textbook-links", status_code=status.HTTP_201_CREATED)
async def create_textbook_link(
    request: Request, point_id: str, body: TextbookLinkCreateRequest
) -> TextbookLinkView:
    service = _service(request)
    return await _run(service.add_textbook_link, point_id, body)


@router.delete(
    "/knowledge-points/{point_id}/textbook-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_textbook_link(
    request: Request,
    point_id: str,
    link_id: str,
    expectedRevision: int = Query(ge=0),
) -> Response:
    service = _service(request)
    await _run(
        service.delete_textbook_link, point_id, link_id, expected_revision=expectedRevision
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- 表格导入


@router.post("/knowledge-imports", status_code=status.HTTP_201_CREATED)
async def create_knowledge_import(request: Request) -> KnowledgeImportView:
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
    subject_part = form.get("subjectId")
    if subject_part is None or not subject_part.text().strip():
        raise AppError(
            "上传请求缺少 subjectId 字段。", code="INVALID_REQUEST", status_code=422
        )
    mapping = _json_object(form.get("mappingJson"), field="mappingJson")
    sheet_part = form.get("sheetName")
    sheet_name = sheet_part.text().strip() if sheet_part is not None else None
    return await _run(
        service.create_file_import,
        file_name=file_part.filename,
        content=file_part.data,
        media_type=file_part.content_type or "",
        subject_id=subject_part.text().strip(),
        mapping=mapping,
        sheet_name=sheet_name or None,
    )


@router.get("/knowledge-imports")
async def list_knowledge_imports(
    request: Request,
    state: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> KnowledgeImportList:
    service = _service(request)
    return await _run(service.list_imports, state=state, offset=offset, limit=limit)


@router.get("/knowledge-imports/{import_id}")
async def get_knowledge_import(request: Request, import_id: str) -> KnowledgeImportView:
    service = _service(request)
    return await _run(service.get_import, import_id)


@router.patch("/knowledge-imports/{import_id}")
async def patch_knowledge_import(
    request: Request, import_id: str, body: KnowledgeImportPatchRequest
) -> KnowledgeImportView:
    service = _service(request)
    return await _run(service.patch_import, import_id, body)


@router.post("/knowledge-imports/{import_id}/confirm")
async def confirm_knowledge_import(
    request: Request, import_id: str, body: KnowledgeImportConfirmRequest
) -> KnowledgeImportConfirmResult:
    service = _service(request)
    return await _run(service.confirm_import, import_id, body)


@router.delete("/knowledge-imports/{import_id}")
async def delete_import(request: Request, import_id: str) -> dict:
    """彻底删除导入批次（R10：任何状态都可删，含已确认；已入库的知识点保留）。

    只清批次行与预览行（知识点与教材依据不引用导入表）；不存在 → 404。
    回执 ``{deleted, importId, removedRows}``。
    """
    service = _service(request)
    return await _run(service.delete_import, import_id)


@router.post("/knowledge-imports/{import_id}/discard")
async def discard_knowledge_import(
    request: Request, import_id: str, body: KnowledgeImportDiscardRequest
) -> KnowledgeImportView:
    """放弃未确认批次（误上传清理）：``state=cancelled``；记录/文件/预览行保留。"""
    service = _service(request)
    return await _run(service.discard_import, import_id, body)


# --------------------------------------------------------------------------- AI 候选


@router.post(
    "/knowledge-suggestion-jobs",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_knowledge_suggestion_job(
    request: Request, body: KnowledgeSuggestionRequest
) -> JobView:
    """AI 候选：202 只代表任务被接受；候选落在 ``source="ai"`` 的待确认批次里。"""
    service = _service(request)
    return await service.create_suggestion_job(body)


# --------------------------------------------------------------------------- 教材提取（任务③）


@router.get("/knowledge-extraction/preview")
async def knowledge_extraction_preview(
    request: Request, subjectId: str = Query(min_length=1, max_length=64)
) -> KnowledgeExtractionPreview:
    """预览某学科全部已入库教材的提取清单（只读；未就绪书册带 reason）。"""
    service = _service(request)
    return await _run(service.extraction_preview, subjectId)


@router.post(
    "/knowledge-extraction-jobs",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_knowledge_extraction_jobs(
    request: Request, body: KnowledgeExtractionRequest
) -> list[JobView]:
    """提取任务受理：**每个书册一个** AI 候选任务（202 只代表任务被接受）。

    ``documentIds`` 缺省 = 该学科全部就绪书册；指定时含未就绪书册 → 409
    ``KNOWLEDGE_EXTRACTION_NOT_READY`` 逐册列出，不静默跳过、不部分受理。
    候选仍只进 ``source="ai"`` 的待确认批次，确认后自动建教材依据。
    """
    service = _service(request)
    return await service.create_extraction_jobs(body)


__all__ = ["router"]
