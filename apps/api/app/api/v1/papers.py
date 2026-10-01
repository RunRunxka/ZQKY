"""原卷接口：DOCX 导入拆题、草稿校对、确认入库、AI 知识点建议与修订内容读取。

取服务：业务服务来自 ``request.app.state.paper_service``（CTRL 装配）；为 ``None`` 时统一
503 ``SERVICE_UNAVAILABLE``（可重试），绝不返回空列表或假成功。同步重活（SQL、解析、
文件）都在有界线程中执行；``knowledge-proposals`` 是 async 服务方法（任务调度必须在事件
循环线程上），路由直接 ``await``。

multipart 解析沿用题库/知识库同一实现（``app/services/textbook_ingest/multipart.py``），
字段固定为 ``file``（.docx）、``subjectId`` 与可选 ``title``。
"""

from __future__ import annotations

import functools

import anyio
from fastapi import APIRouter, Query, Request, Response, status

from app.contracts.papers import (
    PaperConfirmRequest,
    PaperConfirmResult,
    PaperDraftPatchRequest,
    PaperImportView,
    PaperList,
    PaperProposalDecisionRequest,
    PaperProposalJobRequest,
    PaperProposalView,
    PaperRevisionContentView,
    PaperView,
)
from app.contracts.teaching_loop import JobView
from app.core.exceptions import AppError
from app.schemas.textbook import MAX_UPLOAD_BYTES
from app.services.papers.service import PaperService
from app.services.textbook_ingest.multipart import parse_multipart_form

router = APIRouter(tags=["papers"])

#: multipart 头部/边界开销的宽松上界（超出此值在解析前直接 413）
_MULTIPART_OVERHEAD = 4096

_LABEL_SERVICE = "原卷服务"


def _require(service, *, label: str):
    if service is None:
        raise AppError(
            f"{label}未装配：后端缺少对应服务，请检查启动日志与依赖。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return service


def _service(request: Request) -> PaperService:
    return _require(getattr(request.app.state, "paper_service", None), label=_LABEL_SERVICE)


async def _run(fn, /, *args, **kwargs):
    """把同步的 SQL/文件/解析调用放到有界线程里执行，不阻塞事件循环。"""
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


def _too_large() -> AppError:
    return AppError(
        f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
        code="DOCUMENT_TOO_LARGE",
        status_code=413,
    )


# --------------------------------------------------------------------------- 导入


@router.post("/paper-imports", status_code=status.HTTP_201_CREATED)
async def create_paper_import(request: Request) -> PaperImportView:
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
    title_part = form.get("title")
    title = title_part.text().strip() if title_part is not None else None
    return await _run(
        service.create_import,
        file_name=file_part.filename,
        content=file_part.data,
        media_type=file_part.content_type or "application/octet-stream",
        subject_id=subject_part.text().strip(),
        title=title or None,
    )


# --------------------------------------------------------------------------- 原卷


@router.get("/papers")
async def list_papers(
    request: Request,
    subjectId: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> PaperList:
    service = _service(request)
    return await _run(
        service.list_papers,
        subject_id=subjectId,
        status=status_filter,
        q=q,
        offset=offset,
        limit=limit,
    )


@router.get("/papers/{paper_id}")
async def get_paper(request: Request, paper_id: str) -> PaperView:
    service = _service(request)
    return await _run(service.get_paper, paper_id)


@router.get("/papers/{paper_id}/revisions/{revision_id}/content")
async def get_paper_revision_content(
    request: Request, paper_id: str, revision_id: str
) -> PaperRevisionContentView:
    service = _service(request)
    return await _run(service.get_revision_content, paper_id, revision_id)


@router.get("/papers/{paper_id}/revisions/{revision_id}/assets/{asset_id:path}/content")
async def get_paper_revision_asset_content(
    request: Request, paper_id: str, revision_id: str, asset_id: str
) -> Response:
    """受控读取该修订图片块引用过的受管资产（``blobs/<64hex>``）。

    只放行**本修订**引用过的键（否则 404），非法键 422；返回真实字节与 media type。
    不接受任意路径读取，也不跨修订/跨卷放行。
    """
    service = _service(request)
    data, media_type = await _run(
        service.get_revision_asset_content, paper_id, revision_id, asset_id
    )
    return Response(content=data, media_type=media_type)


@router.patch("/papers/{paper_id}/draft")
async def patch_paper_draft(
    request: Request, paper_id: str, body: PaperDraftPatchRequest
) -> PaperRevisionContentView:
    service = _service(request)
    return await _run(service.patch_draft, paper_id, body)


@router.post("/papers/{paper_id}/confirm")
async def confirm_paper(
    request: Request, paper_id: str, body: PaperConfirmRequest
) -> PaperConfirmResult:
    service = _service(request)
    return await _run(service.confirm, paper_id, body)


# --------------------------------------------------------------------------- AI 建议


@router.post(
    "/papers/{paper_id}/knowledge-proposals", status_code=status.HTTP_202_ACCEPTED
)
async def create_paper_knowledge_proposals(
    request: Request, paper_id: str, body: PaperProposalJobRequest
) -> JobView:
    """建知识点建议任务（queued）并调度执行；202 只代表接受任务，不代表建议已生成。"""
    service = _service(request)
    return await service.create_proposal_job(paper_id, body)


@router.get("/paper-proposals/{proposal_id}")
async def get_paper_proposal(request: Request, proposal_id: str) -> PaperProposalView:
    service = _service(request)
    return await _run(service.get_proposal, proposal_id)


@router.post("/paper-proposals/{proposal_id}/apply")
async def apply_paper_proposal(
    request: Request, proposal_id: str, body: PaperProposalDecisionRequest
) -> PaperRevisionContentView:
    service = _service(request)
    return await _run(service.apply_proposal, proposal_id, body)


@router.post("/paper-proposals/{proposal_id}/reject")
async def reject_paper_proposal(
    request: Request, proposal_id: str, body: PaperProposalDecisionRequest
) -> PaperProposalView:
    service = _service(request)
    return await _run(service.reject_proposal, proposal_id, body)
