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


@router.post("/practice-sets/{set_id}/archive", include_in_schema=False)
@router.post("/practice-sets/{set_id}/restore", include_in_schema=False)
async def practice_archive_removed(set_id: str):
    """归档/恢复端点已移除（B3，2026-10-20 用户裁定「删除即删除」）：显式 404。"""
    raise AppError(
        f"练习集 {set_id} 的归档/恢复端点已移除；删除请用 DELETE /practice-sets/{{id}}。",
        code="ARCHIVE_ENDPOINT_REMOVED",
        status_code=404,
    )


@router.delete("/practice-sets/{set_id}", response_model=b4.PracticeSetDeleteReceipt)
async def delete_set(request: Request, set_id: str, expectedRevision: int = Query(ge=0),
                     includeHistory: bool = Query(False)):
    """受引用守卫的彻底删除：已审核版本/导出/转换任一引用 → 409 列出计数；纯草稿集物理删除。

    ``includeHistory=true``（界面明确确认后）跳过守卫，连同全部历史（含已审核修订、
    导出、转换与导出工件）彻底删除该练习；转换生成的原卷修订只摘除来源指针，
    施测/原卷/成绩/报告行本身保留。
    """
    payload = b4.PracticeSetStatusRequest(expectedRevision=expectedRevision)
    return await run(service(request).delete_practice, set_id, payload, include_history=includeHistory)


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


@router.delete("/practice-sets/{set_id}/revisions/{revision_id}/conversion", response_model=b4.PracticeConversionDeleteReceipt)
async def delete_conversion(request: Request, set_id: str, revision_id: str):
    """删除练习转换记录（解除回流关联，无引用守卫）：只删关联行与映射子行；施测/原卷/成绩保留。"""
    return await run(service(request).delete_conversion, set_id, revision_id)
