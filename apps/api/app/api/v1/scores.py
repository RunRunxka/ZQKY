"""成绩接口：上传/预览/校对/确认 + 修订/矩阵/修正（TEACHING-LOOP B3 / T60）。

取服务：``request.app.state.score_service``（CTRL 的 ``app.main`` 用
``build_score_service`` 装配）；为 ``None`` 时统一 503 ``SERVICE_UNAVAILABLE``（可重试），
**绝不返回空列表或假成功**。同步的 SQL/文件/表格解析调用都放在有界线程里执行。

| 方法与路径 | 说明 |
| --- | --- |
| ``POST /assessments/{assessmentId}/score-imports`` | multipart（``file`` + 可选 ``workSheet``/``baseScoreRevisionId``）→ 201 |
| ``GET /score-imports`` | ``assessmentId`` 筛选 + 分页 |
| ``GET /score-imports/{importId}`` | 批次详情（含映射/预览摘要/阻断问题） |
| ``GET /score-imports/{importId}/rows`` | 预览行分页（物理坐标 + 两视图文本） |
| ``PATCH /score-imports/{importId}`` | 映射/行定位/单元格校正（``expectedRevision`` CAS） |
| ``POST /score-imports/{importId}/confirm`` | 三版本守卫 + 承认范围 + 幂等确认 |
| ``GET /assessments/{assessmentId}/score-revisions`` | 修订历史（含冻结快照） |
| ``GET /score-revisions/{revisionId}`` | 单个修订 |
| ``GET /score-revisions/{revisionId}/matrix`` | 只读矩阵分页（items 固定叶；rows 分页） |
| ``POST /assessments/{assessmentId}/score-revisions/correct`` | 从不可变 base 生成新完整版本 |

错误码一律用 ``app/contracts/scores.py`` 的契约常量；文件本体走受管资产
（``kind='score_sheet'``），不落临时目录。
"""

from __future__ import annotations

import functools

import anyio
from fastapi import APIRouter, Query, Request, status

from app.contracts.scores import (
    ScoreImportConfirmRequest,
    ScoreImportConfirmResult,
    ScoreImportList,
    ScoreImportRowList,
    ScoreImportView,
    ScoreMatrixPage,
    ScoreRevisionCorrectRequest,
    ScoreRevisionCorrectResult,
    ScoreRevisionList,
    ScoreRevisionView,
)
from app.core.exceptions import AppError
from app.contracts.scores import ScoreImportPatchRequest
from app.services.scores.service import ScoreService
from app.services.textbook_ingest.multipart import MultipartPart, parse_multipart_form

router = APIRouter(tags=["scores"])

#: 成绩上传上限 10 MiB（与名单一致；100 叶 × 200 行的 XLSX 远小于该上限）
MAX_SCORE_UPLOAD_BYTES = 10 * 1024 * 1024
_MULTIPART_OVERHEAD = 4096

_LABEL_SERVICE = "成绩服务"


def _require(service) -> ScoreService:
    if service is None:
        raise AppError(
            f"{_LABEL_SERVICE}未装配：后端缺少对应服务，请检查启动日志与依赖。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return service


def _service(request: Request) -> ScoreService:
    return _require(getattr(request.app.state, "score_service", None))


async def _run(fn, /, *args, **kwargs):
    """把同步的 SQL/文件/表格调用放到有界线程里执行，不阻塞事件循环。"""
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


def _too_large() -> AppError:
    return AppError(
        f"单个成绩文件不得超过 {MAX_SCORE_UPLOAD_BYTES // (1024 * 1024)} MiB。",
        code="DOCUMENT_TOO_LARGE",
        status_code=413,
    )


def _option(form: dict[str, MultipartPart], name: str) -> str | None:
    part = form.get(name)
    if part is None:
        return None
    text = part.text().strip()
    return text or None


@router.post(
    "/assessments/{assessment_id}/score-imports",
    status_code=status.HTTP_201_CREATED,
    response_model=ScoreImportView,
)
async def create_score_import(request: Request, assessment_id: str) -> ScoreImportView:
    service = _service(request)
    content_type = request.headers.get("content-type", "")
    declared = request.headers.get("content-length")
    if (
        declared
        and declared.isdigit()
        and int(declared) > MAX_SCORE_UPLOAD_BYTES + _MULTIPART_OVERHEAD
    ):
        raise _too_large()
    raw = await request.body()
    if len(raw) > MAX_SCORE_UPLOAD_BYTES + _MULTIPART_OVERHEAD:
        raise _too_large()
    form = await _run(parse_multipart_form, raw, content_type)
    file_part = form.get("file")
    if file_part is None or file_part.filename is None:
        raise AppError(
            "上传请求缺少 file 部件。", code="INVALID_REQUEST", status_code=422
        )
    if len(file_part.data) > MAX_SCORE_UPLOAD_BYTES:
        raise _too_large()
    return await _run(
        service.create_score_import,
        assessment_id,
        file_name=file_part.filename,
        content=file_part.data,
        media_type=file_part.content_type or "",
        work_sheet=_option(form, "workSheet"),
        base_score_revision_id=_option(form, "baseScoreRevisionId"),
    )


@router.get("/score-imports", response_model=ScoreImportList)
async def list_score_imports(
    request: Request,
    assessmentId: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ScoreImportList:
    service = _service(request)
    return await _run(
        service.list_score_imports,
        assessment_id=assessmentId,
        offset=offset,
        limit=limit,
    )


@router.get("/score-imports/{import_id}", response_model=ScoreImportView)
async def get_score_import(request: Request, import_id: str) -> ScoreImportView:
    service = _service(request)
    return await _run(service.get_score_import, import_id)


@router.get("/score-imports/{import_id}/rows", response_model=ScoreImportRowList)
async def list_score_import_rows(
    request: Request,
    import_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ScoreImportRowList:
    service = _service(request)
    return await _run(
        service.list_score_import_rows, import_id, offset=offset, limit=limit
    )


@router.patch("/score-imports/{import_id}", response_model=ScoreImportView)
async def patch_score_import(
    request: Request, import_id: str, body: ScoreImportPatchRequest
) -> ScoreImportView:
    service = _service(request)
    return await _run(service.patch_score_import, import_id, body)


@router.post(
    "/score-imports/{import_id}/confirm", response_model=ScoreImportConfirmResult
)
async def confirm_score_import(
    request: Request, import_id: str, body: ScoreImportConfirmRequest
) -> ScoreImportConfirmResult:
    service = _service(request)
    return await _run(service.confirm_score_import, import_id, body)


@router.get(
    "/assessments/{assessment_id}/score-revisions", response_model=ScoreRevisionList
)
async def list_score_revisions(
    request: Request, assessment_id: str
) -> ScoreRevisionList:
    service = _service(request)
    return await _run(service.list_score_revisions, assessment_id)


@router.get("/score-revisions/{revision_id}", response_model=ScoreRevisionView)
async def get_score_revision(request: Request, revision_id: str) -> ScoreRevisionView:
    service = _service(request)
    return await _run(service.get_score_revision, revision_id)


@router.get("/score-revisions/{revision_id}/matrix", response_model=ScoreMatrixPage)
async def get_score_matrix(
    request: Request,
    revision_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ScoreMatrixPage:
    service = _service(request)
    return await _run(service.get_score_matrix, revision_id, offset=offset, limit=limit)


@router.post(
    "/assessments/{assessment_id}/score-revisions/correct",
    response_model=ScoreRevisionCorrectResult,
)
async def correct_scores(
    request: Request, assessment_id: str, body: ScoreRevisionCorrectRequest
) -> ScoreRevisionCorrectResult:
    service = _service(request)
    return await _run(service.correct_scores, assessment_id, body)


__all__ = ["router"]
