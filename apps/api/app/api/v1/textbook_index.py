"""教材索引代接口：状态与重建发起。

- ``GET /textbook-index/status``：当前模型、索引代、重建任务与 Qdrant 可达性；
  Qdrant 不可达时 ``qdrantAvailable=false`` 并给出原因，不抛错也不冒充空库。
- ``POST /textbook-index/rebuilds``：全套闸门（幂等键、无进行中重建、无排队/执行中入库），
  响应先返回 queued 任务，重建在后台线程执行。
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request, status

from app.schemas.textbook import IndexStatusView, JobView, RebuildCreateRequest
from app.services.textbook_ingest.views import require_state, run_in_thread

router = APIRouter(tags=["textbook-index"])


def _index(request: Request):
    return require_state(request.app.state.index_service, label="教材索引服务")


@router.get("/textbook-index/status")
async def get_textbook_index_status(request: Request) -> IndexStatusView:
    index = _index(request)
    return await run_in_thread(index.status)


@router.post("/textbook-index/rebuilds", status_code=status.HTTP_201_CREATED)
async def create_textbook_rebuild(
    request: Request, body: RebuildCreateRequest, background_tasks: BackgroundTasks
) -> JobView:
    index = _index(request)
    job = await run_in_thread(
        index.begin_rebuild,
        profile_id=body.profileId,
        submission_id=body.submissionId,
    )
    background_tasks.add_task(index.recover_pending_jobs)
    return job
