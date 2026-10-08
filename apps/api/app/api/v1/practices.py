"""Real practice workspace; blocking SQL/IO runs in bounded threads."""
import functools
import anyio
from fastapi import APIRouter, Request, Query, Response
from app.contracts import b4
from app.core.exceptions import AppError

router = APIRouter(tags=["practices"])


def service(request):
    value = getattr(request.app.state, "practice_service", None)
    if value is None:
        raise AppError("练习服务未装配。", code="SERVICE_UNAVAILABLE", status_code=503)
    return value


async def run(fn, *args, **kwargs):
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


@router.post("/practice-sets", response_model=b4.PracticeSetView, status_code=201)
async def create(request: Request, body: b4.PracticeCreateRequest):
    return await run(service(request).create_practice, body)


@router.get("/practice-sets", response_model=b4.Page[b4.PracticeSetView])
async def listing(request: Request, analysisRunId: str | None = None, status: str | None = Query(default=None), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return await run(service(request).list_practices, analysis_run_id=analysisRunId, status=status, offset=offset, limit=limit)


@router.get("/practice-sets/{set_id}", response_model=b4.PracticeSetView)
async def detail(request: Request, set_id: str):
    return await run(service(request).get_practice, set_id)


@router.post("/practice-sets/{set_id}/archive", response_model=b4.PracticeSetView)
async def archive(request: Request, set_id: str, body: b4.PracticeSetStatusRequest):
    return await run(service(request).set_archived, set_id, body, archived=True)


@router.delete("/practice-sets/{set_id}", response_model=b4.PracticeSetDeleteReceipt)
async def delete_set(request: Request, set_id: str, expectedRevision: int = Query(ge=0)):
    """受引用守卫的彻底删除：已审核版本/导出/转换任一引用 → 409 列出计数；纯草稿集物理删除。"""
    payload = b4.PracticeSetStatusRequest(expectedRevision=expectedRevision)
    return await run(service(request).delete_practice, set_id, payload)


@router.post("/practice-sets/{set_id}/restore", response_model=b4.PracticeSetView)
async def restore(request: Request, set_id: str, body: b4.PracticeSetStatusRequest):
    return await run(service(request).set_archived, set_id, body, archived=False)


@router.get("/practice-sets/{set_id}/revisions/{revision_id}", response_model=b4.PracticeRevisionView)
async def revision(request: Request, set_id: str, revision_id: str):
    return await run(service(request).get_revision, set_id, revision_id)


@router.post("/practice-sets/{set_id}/suggestions", response_model=b4.PracticeSuggestions)
async def suggestions(request: Request, set_id: str, body: b4.PracticeSuggestionsRequest):
    return await run(service(request).suggestions, set_id, body)


@router.patch("/practice-sets/{set_id}/draft", response_model=b4.PracticeSetView)
async def draft(request: Request, set_id: str, body: b4.PracticeDraftPatch):
    return await run(service(request).save_draft, set_id, body)


@router.post("/practice-sets/{set_id}/review", response_model=b4.PracticeSetView)
async def review(request: Request, set_id: str, body: b4.PracticeReviewRequest):
    return await run(service(request).review, set_id, body)


@router.post("/practice-sets/{set_id}/revisions", response_model=b4.PracticeSetView, status_code=201)
async def new_revision(request: Request, set_id: str, body: b4.PracticeRevisionRequest):
    return await run(service(request).new_revision, set_id, body)


@router.post("/practice-sets/{set_id}/revisions/{revision_id}/exports", response_model=b4.ExportReceipt, status_code=202)
async def export(request: Request, set_id: str, revision_id: str, body: b4.ExportRequest):
    return await service(request).create_export(set_id, revision_id, body)


@router.get("/practice-sets/{set_id}/revisions/{revision_id}/exports", response_model=b4.Page[b4.ExportArtifact])
async def exports(request: Request, set_id: str, revision_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return await run(service(request).list_exports, set_id, revision_id, offset=offset, limit=limit)


@router.get("/practice-sets/{set_id}/revisions/{revision_id}/assets/{sha}")
async def asset(request: Request, set_id: str, revision_id: str, sha: str):
    data, media = await run(service(request).get_asset, set_id, revision_id, sha)
    return Response(data, media_type=media)


@router.post("/practice-sets/{set_id}/revisions/{revision_id}/assessments", response_model=b4.PracticeConversionReceipt, status_code=201)
async def convert(request: Request, set_id: str, revision_id: str, body: b4.PracticeConversionRequest):
    return await run(service(request).convert, set_id, revision_id, body)
