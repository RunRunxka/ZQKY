"""Thin lesson API. Blocking preparation/SQL is delegated to bounded workers."""
import functools

import anyio
from fastapi import APIRouter, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from app.contracts import lesson_plans as lp
from app.contracts.b4 import Page
from app.core.exceptions import AppError


class BoundedLessonRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request):
            if request.method in {"POST", "PATCH"} and len(await request.body()) > lp.MAX_REQUEST_BYTES:
                raise AppError("完整请求超过2 MiB，请保留原稿并减小内容。", code="LESSON_REQUEST_TOO_LARGE", status_code=413)
            try:
                return await handler(request)
            except RequestValidationError as exc:
                issues = [{"field": ".".join(str(part) for part in error["loc"]),
                           "code": error["type"], "message": error["msg"]} for error in exc.errors()]
                # Validation details expose neither the rejected input nor model
                # context/credentials. Other modules retain their own handler.
                raise AppError("教案请求字段不符合契约。", code="VALIDATION_ERROR", status_code=422,
                               details={"issues": issues}) from exc
        return checked


router = APIRouter(tags=["lesson-plans"], route_class=BoundedLessonRoute)


def service(request):
    value = getattr(request.app.state, "lesson_plan_service", None)
    if value is None:
        raise AppError("教案服务未装配。", code="SERVICE_UNAVAILABLE", status_code=503)
    return value


async def run(fn, *args, **kwargs):
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


@router.get("/lesson-plans", response_model=Page[lp.LessonSummary])
async def listing(request: Request, subjectId: str | None = None, classId: str | None = None,
                  archived: bool = Query(default=False),
                  offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return await run(service(request).list_lessons, subject_id=subjectId, class_id=classId,
                     archived=archived, offset=offset, limit=limit)


@router.post("/lesson-plans", response_model=lp.LessonView, status_code=201)
async def create(request: Request, body: lp.LessonCreateRequest):
    return await run(service(request).create_lesson, body)


@router.post("/lesson-plans/import-local", response_model=lp.LessonView, status_code=201)
async def import_local(request: Request, body: lp.LessonImportRequest):
    return await run(service(request).import_local, body)


@router.post("/lesson-plans/evidence/verify", response_model=lp.LessonEvidenceView)
async def verify_evidence(request: Request, body: lp.LessonEvidenceRequest):
    return await run(service(request).verify_evidence, body)


@router.post("/lesson-plans/{lesson_id}/archive", response_model=lp.LessonView)
async def archive(request: Request, lesson_id: str, body: lp.LessonRevisionRequest):
    """归档教案：请求体 ``{"expectedRevision": <int>}``，返回最新 ``LessonView``。"""
    return await run(service(request).set_archived, lesson_id, body, archived=True)


@router.post("/lesson-plans/{lesson_id}/restore", response_model=lp.LessonView)
async def restore(request: Request, lesson_id: str, body: lp.LessonRevisionRequest):
    """恢复教案：清除 ``archived_at``，按原 revision 继续编辑。"""
    return await run(service(request).set_archived, lesson_id, body, archived=False)


@router.get("/lesson-plans/{lesson_id}", response_model=lp.LessonView)
async def detail(request: Request, lesson_id: str):
    return await run(service(request).get_lesson, lesson_id)


@router.patch("/lesson-plans/{lesson_id}/draft", response_model=lp.LessonView)
async def save(request: Request, lesson_id: str, body: lp.LessonSaveRequest):
    return await run(service(request).save_draft, lesson_id, body)


@router.get("/lesson-plans/{lesson_id}/revisions", response_model=Page[lp.LessonRevisionSummary])
async def history(request: Request, lesson_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return await run(service(request).list_revisions, lesson_id, offset=offset, limit=limit)


@router.get("/lesson-plans/{lesson_id}/revisions/{revision_id}", response_model=lp.LessonRevisionView)
async def revision(request: Request, lesson_id: str, revision_id: str):
    return await run(service(request).get_revision, lesson_id, revision_id)


@router.post("/lesson-plans/{lesson_id}/proposals", response_model=lp.LessonGenerationReceipt, status_code=202)
async def generate(request: Request, lesson_id: str, body: lp.LessonGenerateRequest):
    return await service(request).generate_proposal(lesson_id, body)


@router.get("/lesson-plans/{lesson_id}/proposals/{proposal_id}", response_model=lp.LessonProposalView)
async def proposal(request: Request, lesson_id: str, proposal_id: str):
    return await run(service(request).get_proposal, lesson_id, proposal_id)


@router.post("/lesson-plans/{lesson_id}/proposals/{proposal_id}/apply", response_model=lp.LessonView)
async def apply(request: Request, lesson_id: str, proposal_id: str, body: lp.LessonApplyRequest):
    return await service(request).apply_proposal(lesson_id, proposal_id, body)


@router.post("/lesson-plans/{lesson_id}/proposals/{proposal_id}/reject", response_model=lp.LessonProposalView)
async def reject(request: Request, lesson_id: str, proposal_id: str, body: lp.LessonRejectRequest):
    return await run(service(request).reject_proposal, lesson_id, proposal_id, body)
