"""名单接口：班级 CRUD、学生身份与转班、名单上传/校对/幂等确认（TEACHING-LOOP B1 / T30-a）。

取服务：``request.app.state.roster_service``；为 ``None`` 时统一 503 ``SERVICE_UNAVAILABLE``
（可重试），**绝不返回空列表或假成功**。同步的 SQL/文件/表格解析都在有界线程中执行。

上传：multipart（``file`` + 可选 ``mappingJson``/``sheetName``），上限 10 MiB（413
``DOCUMENT_TOO_LARGE``）；表格解析与映射校验在服务层，错误码用 ``app/contracts/roster.py``
常量。施测相关路由（``POST /assessments`` 等）**不在这里注册**：由 B0 通配占位返回
501 ``FEATURE_NOT_IMPLEMENTED``（真实创建 = T30-b）。

| 方法与路径 | 说明 |
| --- | --- |
| GET/POST `/classes`、GET/PATCH `/classes/{id}` | 班级 CRUD（`schoolYear`+`code` 用户内唯一） |
| POST `/classes/{id}/archive`、`/restore` | 归档/恢复（`expectedRevision`；归档仍可读） |
| DELETE `/classes/{id}?expectedRevision=N` | 受引用守卫的彻底删除（归属/施测范围/教案任一引用 → 409 `CLASS_IN_USE` 列出计数） |
| POST `/classes/{id}/students/batch` | 批量添加学生（`submissionId` 幂等；学号已存在跳过并说明） |
| GET `/classes/{id}/students` | 该班活跃成员（含归属历史；默认不含已归档学生，`includeArchived=true` 可带出） |
| GET `/students`（`q` 模糊 / `status` 过滤）、GET/POST `/students` | 学生身份 |
| PATCH `/students/{id}`、POST `/students/{id}/transfer` | 改名/改学号（乐观锁）、转班（归档学生拒绝） |
| POST `/students/{id}/archive`、`/restore` | 归档/恢复学生（`expectedRevision`；归属历史保留） |
| POST `/classes/{id}/roster-imports` | multipart 名单上传 + 预览 |
| GET `/roster-imports`、GET/PATCH `/roster-imports/{id}`、POST `/{id}/confirm`、POST `/{id}/discard` | 批次/预览/校对/确认（幂等）/放弃未确认批次 |
"""

from __future__ import annotations

import functools
import json

import anyio
from fastapi import APIRouter, Query, Request, status

from app.contracts.roster import (
    BatchStudentAddRequest,
    BatchStudentAddResult,
    ClassCreateRequest,
    ClassList,
    ClassRevisionRequest,
    ClassUpdateRequest,
    ClassView,
    MembershipTransferRequest,
    RosterImportConfirmRequest,
    RosterImportConfirmResult,
    RosterImportDiscardRequest,
    RosterImportList,
    RosterImportPatchRequest,
    RosterImportView,
    StudentCreateRequest,
    StudentList,
    StudentRevisionRequest,
    StudentUpdateRequest,
    StudentView,
)
from app.core.exceptions import AppError
from app.services.roster.service import RosterService
from app.services.textbook_ingest.multipart import MultipartPart, parse_multipart_form

router = APIRouter(tags=["roster"])

#: 名单上传上限 10 MiB（任务卡 §4）；multipart 头部/边界开销的宽松上界
MAX_ROSTER_UPLOAD_BYTES = 10 * 1024 * 1024
_MULTIPART_OVERHEAD = 4096

_LABEL_SERVICE = "名单服务"


def _require(service) -> RosterService:
    if service is None:
        raise AppError(
            f"{_LABEL_SERVICE}未装配：后端缺少对应服务，请检查启动日志与依赖。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return service


def _service(request: Request) -> RosterService:
    return _require(getattr(request.app.state, "roster_service", None))


async def _run(fn, /, *args, **kwargs):
    """把同步的 SQL/文件/表格调用放到有界线程里执行，不阻塞事件循环。"""
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


def _too_large() -> AppError:
    return AppError(
        f"单个名单文件不得超过 {MAX_ROSTER_UPLOAD_BYTES // (1024 * 1024)} MiB。",
        code="DOCUMENT_TOO_LARGE",
        status_code=413,
    )


def _mapping_option(form: dict[str, MultipartPart]) -> dict[str, str] | None:
    part = form.get("mappingJson")
    if part is None:
        return None
    try:
        parsed = json.loads(part.text())
    except ValueError as exc:
        raise AppError(
            "mappingJson 不是合法 JSON。", code="INVALID_REQUEST", status_code=422
        ) from exc
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in parsed.items()
    ):
        raise AppError(
            "mappingJson 必须是「字段: 表头」的字符串映射。",
            code="INVALID_REQUEST",
            status_code=422,
        )
    return dict(parsed)


# --------------------------------------------------------------------------- 班级


@router.get("/classes")
async def list_classes(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ClassList:
    service = _service(request)
    return await _run(
        service.list_classes, status=status_filter, offset=offset, limit=limit
    )


@router.post("/classes", status_code=status.HTTP_201_CREATED)
async def create_class(request: Request, body: ClassCreateRequest) -> ClassView:
    service = _service(request)
    return await _run(service.create_class, body)


@router.get("/classes/{class_id}")
async def get_class(request: Request, class_id: str) -> ClassView:
    service = _service(request)
    return await _run(service.get_class, class_id)


@router.patch("/classes/{class_id}")
async def update_class(
    request: Request, class_id: str, body: ClassUpdateRequest
) -> ClassView:
    service = _service(request)
    return await _run(service.update_class, class_id, body)


@router.post("/classes/{class_id}/archive")
async def archive_class(
    request: Request, class_id: str, body: ClassRevisionRequest
) -> ClassView:
    service = _service(request)
    return await _run(service.set_archived, class_id, body, archived=True)


@router.post("/classes/{class_id}/restore")
async def restore_class(
    request: Request, class_id: str, body: ClassRevisionRequest
) -> ClassView:
    service = _service(request)
    return await _run(service.set_archived, class_id, body, archived=False)


@router.delete("/classes/{class_id}")
async def delete_class(
    request: Request,
    class_id: str,
    expectedRevision: int = Query(ge=0),
) -> dict:
    """受引用守卫的彻底删除：无下游引用才物理删除；被引用时 409 ``CLASS_IN_USE``。"""
    service = _service(request)
    payload = ClassRevisionRequest(expectedRevision=expectedRevision)
    return await _run(service.delete_class, class_id, payload)


@router.post("/classes/{class_id}/students/batch")
async def batch_add_students(
    request: Request, class_id: str, body: BatchStudentAddRequest
) -> BatchStudentAddResult:
    """批量添加学生：单事务逐行处理；学号已存在跳过并说明；同 submissionId 幂等重放。"""
    service = _service(request)
    return await _run(service.batch_add_students, class_id, body)


@router.get("/classes/{class_id}/students")
async def list_class_students(
    request: Request,
    class_id: str,
    includeArchived: bool = Query(default=False),
) -> StudentList:
    service = _service(request)
    return await _run(
        service.list_class_students, class_id, include_archived=includeArchived
    )


# --------------------------------------------------------------------------- 学生


@router.get("/students")
async def list_students(
    request: Request,
    q: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> StudentList:
    service = _service(request)
    return await _run(
        service.list_students, q=q, status=status_filter, offset=offset, limit=limit
    )


@router.post("/students", status_code=status.HTTP_201_CREATED)
async def create_student(request: Request, body: StudentCreateRequest) -> StudentView:
    service = _service(request)
    return await _run(service.create_student, body)


@router.get("/students/{student_id}")
async def get_student(request: Request, student_id: str) -> StudentView:
    service = _service(request)
    return await _run(service.get_student, student_id)


@router.patch("/students/{student_id}")
async def update_student(
    request: Request, student_id: str, body: StudentUpdateRequest
) -> StudentView:
    service = _service(request)
    return await _run(service.update_student, student_id, body)


@router.post("/students/{student_id}/transfer")
async def transfer_student(
    request: Request, student_id: str, body: MembershipTransferRequest
) -> StudentView:
    service = _service(request)
    return await _run(service.transfer_student, student_id, body)


@router.post("/students/{student_id}/archive")
async def archive_student(
    request: Request, student_id: str, body: StudentRevisionRequest
) -> StudentView:
    service = _service(request)
    return await _run(service.set_student_archived, student_id, body, archived=True)


@router.post("/students/{student_id}/restore")
async def restore_student(
    request: Request, student_id: str, body: StudentRevisionRequest
) -> StudentView:
    service = _service(request)
    return await _run(service.set_student_archived, student_id, body, archived=False)


# --------------------------------------------------------------------------- 名单导入


@router.post(
    "/classes/{class_id}/roster-imports", status_code=status.HTTP_201_CREATED
)
async def create_roster_import(request: Request, class_id: str) -> RosterImportView:
    service = _service(request)
    content_type = request.headers.get("content-type", "")
    declared = request.headers.get("content-length")
    if (
        declared
        and declared.isdigit()
        and int(declared) > MAX_ROSTER_UPLOAD_BYTES + _MULTIPART_OVERHEAD
    ):
        raise _too_large()
    raw = await request.body()
    if len(raw) > MAX_ROSTER_UPLOAD_BYTES + _MULTIPART_OVERHEAD:
        raise _too_large()
    form = await _run(parse_multipart_form, raw, content_type)
    file_part = form.get("file")
    if file_part is None or file_part.filename is None:
        raise AppError(
            "上传请求缺少 file 部件。", code="INVALID_REQUEST", status_code=422
        )
    if len(file_part.data) > MAX_ROSTER_UPLOAD_BYTES:
        raise _too_large()
    mapping = _mapping_option(form)
    sheet_part = form.get("sheetName")
    sheet_name = sheet_part.text().strip() if sheet_part is not None else ""
    return await _run(
        service.create_roster_import,
        class_id=class_id,
        file_name=file_part.filename,
        content=file_part.data,
        media_type=file_part.content_type or "",
        mapping=mapping,
        sheet_name=sheet_name or None,
    )


@router.get("/roster-imports")
async def list_roster_imports(
    request: Request,
    classId: str | None = Query(default=None),
    state: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> RosterImportList:
    service = _service(request)
    return await _run(
        service.list_roster_imports,
        class_id=classId,
        state=state,
        offset=offset,
        limit=limit,
    )


@router.get("/roster-imports/{import_id}")
async def get_roster_import(request: Request, import_id: str) -> RosterImportView:
    service = _service(request)
    return await _run(service.get_roster_import, import_id)


@router.patch("/roster-imports/{import_id}")
async def patch_roster_import(
    request: Request, import_id: str, body: RosterImportPatchRequest
) -> RosterImportView:
    service = _service(request)
    return await _run(service.patch_roster_import, import_id, body)


@router.post("/roster-imports/{import_id}/confirm")
async def confirm_roster_import(
    request: Request, import_id: str, body: RosterImportConfirmRequest
) -> RosterImportConfirmResult:
    service = _service(request)
    return await _run(service.confirm_roster_import, import_id, body)


@router.post("/roster-imports/{import_id}/discard")
async def discard_roster_import(
    request: Request, import_id: str, body: RosterImportDiscardRequest
) -> RosterImportView:
    service = _service(request)
    return await _run(service.discard_roster_import, import_id, body)


__all__ = ["router"]
