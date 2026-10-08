"""施测接口：创建/列表/详情/更新/补录人次（TEACHING-LOOP B2 / T30-b）。

取服务：``request.app.state.assessment_service``（CTRL 的 ``app.main`` 在 reader 可用时
装配）；为 ``None`` 时统一 503 ``SERVICE_UNAVAILABLE``（可重试），**绝不返回空列表或
假成功**。同步的 SQL 调用放在有界线程里执行，不阻塞事件循环。

| 方法与路径 | 说明 |
| --- | --- |
| ``GET /assessments`` | ``subjectId``/``classId``/``state`` 筛选 + 分页 |
| ``POST /assessments`` | 真实创建（201）：只接受已确认原卷修订；``submissionId`` 幂等 |
| ``GET /assessments/{id}`` | 详情（含参测人次，按班级/人次/姓名排序） |
| ``PATCH /assessments/{id}`` | 标题/类型/日期（``expectedRevision`` 守卫；不改原卷） |
| ``POST /assessments/{id}/participants`` | 补录/补考：新增人次（不覆盖既有记录） |
| ``DELETE /assessments/{id}/participants/{pid}`` | 移除误录人次（守卫式：已有成绩版本/导入引用/学情报告 → 409） |
| ``DELETE /assessments/{id}?expectedRevision=N`` | 受引用守卫的彻底删除（成绩/导入/报告/练习转换任一引用 → 409 ``ASSESSMENT_IN_USE`` 列出计数） |
| ``POST /assessments/{id}/archive``、``/restore`` | 归档/恢复（``expectedRevision``；归档后禁止更新/补录/出勤校正与新成绩导入，历史保留） |

错误码一律用 ``app/contracts/assessments.py`` 的契约常量；这些真实路由注册后，B0 的
``/api/v1/{rest:path}`` 通配占位不再命中本前缀（路由按注册顺序优先匹配）。
"""

from __future__ import annotations

import functools

import anyio
from fastapi import APIRouter, Query, Request, status

from app.contracts.assessments import (
    AssessmentCreateRequest,
    AssessmentCreateResult,
    AssessmentDetailView,
    AssessmentList,
    AssessmentRevisionRequest,
    AssessmentUpdateRequest,
    AssessmentView,
    ParticipantAddRequest,
    ParticipantAttendanceRequest,
    ParticipantMutationResult,
)
from app.core.exceptions import AppError
from app.services.assessments.service import AssessmentService

router = APIRouter(tags=["assessments"])

_LABEL_SERVICE = "施测服务"


def _require(service) -> AssessmentService:
    if service is None:
        raise AppError(
            f"{_LABEL_SERVICE}未装配：后端缺少对应服务，请检查启动日志与依赖。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return service


def _service(request: Request) -> AssessmentService:
    return _require(getattr(request.app.state, "assessment_service", None))


async def _run(fn, /, *args, **kwargs):
    """把同步的 SQL 调用放到有界线程里执行，不阻塞事件循环。"""
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


# --------------------------------------------------------------------------- 施测


@router.get("/assessments")
async def list_assessments(
    request: Request,
    subjectId: str | None = Query(default=None),
    classId: str | None = Query(default=None),
    state: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> AssessmentList:
    service = _service(request)
    return await _run(
        service.list_assessments,
        subject_id=subjectId,
        class_id=classId,
        state=state,
        offset=offset,
        limit=limit,
    )


@router.post("/assessments", status_code=status.HTTP_201_CREATED)
async def create_assessment(
    request: Request, body: AssessmentCreateRequest
) -> AssessmentCreateResult:
    service = _service(request)
    return await _run(service.create_assessment, body)


@router.get("/assessments/{assessment_id}")
async def get_assessment(
    request: Request, assessment_id: str
) -> AssessmentDetailView:
    service = _service(request)
    return await _run(service.get_assessment, assessment_id)


@router.patch("/assessments/{assessment_id}")
async def update_assessment(
    request: Request, assessment_id: str, body: AssessmentUpdateRequest
) -> AssessmentView:
    service = _service(request)
    return await _run(service.update_assessment, assessment_id, body)


@router.post("/assessments/{assessment_id}/participants")
async def add_participants(
    request: Request, assessment_id: str, body: ParticipantAddRequest
) -> ParticipantMutationResult:
    service = _service(request)
    return await _run(service.add_participants, assessment_id, body)


@router.patch("/assessments/{assessment_id}/participants/{participant_id}/attendance")
async def correct_participant_attendance(
    request: Request, assessment_id: str, participant_id: str,
    body: ParticipantAttendanceRequest,
) -> ParticipantMutationResult:
    return await _run(
        _service(request).correct_participant_attendance, assessment_id, participant_id, body
    )


@router.delete("/assessments/{assessment_id}/participants/{participant_id}")
async def remove_participant(
    request: Request, assessment_id: str, participant_id: str,
    expectedRevision: int = Query(ge=0),
) -> ParticipantMutationResult:
    """移除误录人次（守卫式）：已有成绩版本/导入引用/学情报告时 409 拒绝。"""
    service = _service(request)
    payload = AssessmentRevisionRequest(expectedRevision=expectedRevision)
    return await _run(service.remove_participant, assessment_id, participant_id, payload)


@router.delete("/assessments/{assessment_id}")
async def delete_assessment(
    request: Request,
    assessment_id: str,
    expectedRevision: int = Query(ge=0),
) -> dict:
    """受引用守卫的彻底删除：成绩/导入/报告/练习转换任一引用 → 409 ``ASSESSMENT_IN_USE`` 列出计数。"""
    service = _service(request)
    payload = AssessmentRevisionRequest(expectedRevision=expectedRevision)
    return await _run(service.delete_assessment, assessment_id, payload)


@router.post("/assessments/{assessment_id}/archive")
async def archive_assessment(
    request: Request, assessment_id: str, body: AssessmentRevisionRequest
) -> AssessmentView:
    service = _service(request)
    return await _run(service.set_archived, assessment_id, body, archived=True)


@router.post("/assessments/{assessment_id}/restore")
async def restore_assessment(
    request: Request, assessment_id: str, body: AssessmentRevisionRequest
) -> AssessmentView:
    service = _service(request)
    return await _run(service.set_archived, assessment_id, body, archived=False)


__all__ = ["router"]
