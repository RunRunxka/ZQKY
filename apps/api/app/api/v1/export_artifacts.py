"""B4 fixed managed export metadata/download routes."""
from functools import partial
from urllib.parse import quote
import anyio
from fastapi import APIRouter, Request, Response
from app.contracts.b4 import ExportArtifact
from app.core.exceptions import AppError

router = APIRouter(tags=['export-artifacts'])


def service(request: Request):
    value = getattr(request.app.state, 'export_artifacts_service', None)
    if value is None:
        raise AppError('导出下载服务未装配。', code='SERVICE_UNAVAILABLE', status_code=503, retryable=True)
    return value


@router.get('/export-artifacts/{artifact_id}', response_model=ExportArtifact)
async def artifact(artifact_id: str, request: Request):
    return await anyio.to_thread.run_sync(partial(service(request).get, artifact_id))


@router.get('/export-artifacts/{artifact_id}/download')
async def download(artifact_id: str, request: Request):
    view, data = await anyio.to_thread.run_sync(partial(service(request).download, artifact_id))
    return Response(data, media_type=view.media_type, headers={
        'Content-Disposition': "attachment; filename*=UTF-8''" + quote(view.filename, safe=''),
        'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store',
    })
