"""公共任务路由：查询、协作式取消与重试（TEACHING-LOOP B0）。

| 方法与路径 | 说明 |
| --- | --- |
| GET `/api/v1/workflow-jobs/{jobId}?domain=…`（domain ∈ knowledge/question/teaching） | `JobView` |
| POST `/api/v1/workflow-jobs/{jobId}/cancel` | 协作式取消（幂等）；`queued` 立即取消 |
| POST `/api/v1/workflow-jobs/{jobId}/retry` | 终态可重试（保留冻结输入与模型指纹）；重排后**经执行器注册表调度**；`queued` 且本进程未在跑（重启/调度异常遗留）时再次调用会补调度；`running` 仍 409 |

任务结果与终态由各域在**所属业务库的同一事务**提交（见 `app/services/jobs`）；
本路由只读视图、置取消标志与重新排队，不做任何生成工作。

域未装配时返回 503（不返回空视图或假成功）；域参数非法返回 422。
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.contracts.teaching_loop import JOB_DOMAINS, JobView
from app.core.exceptions import AppError
from app.schemas.teaching_loop import JobDomainRequest

router = APIRouter(tags=["workflow-jobs"])


def _engine(request: Request):
    engine = getattr(request.app.state, "job_engine", None)
    if engine is None:
        raise AppError(
            "任务引擎未装配（本地数据库运行时未启动）。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return engine


def _store(request: Request, domain: str):
    engine = _engine(request)
    if domain not in JOB_DOMAINS:
        raise AppError(
            f"未知任务域：{domain}。",
            code="INVALID_REQUEST",
            status_code=422,
            details={"fields": ["domain"]},
        )
    try:
        return engine.store(domain)
    except AppError as exc:
        # 引擎对"已知域但没有对应仓储"按非法域报错；这里如实转为未装配 503，
        # 不把"服务缺失"伪装成"参数错误"。
        if exc.code == "INVALID_REQUEST":
            raise AppError(
                f"任务域 {domain} 的服务未装配。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            ) from exc
        raise


@router.get("/workflow-jobs/{job_id}", response_model=JobView)
async def get_workflow_job(
    request: Request,
    job_id: str,
    domain: str = Query(..., description="knowledge | question | teaching"),
) -> JobView:
    return _store(request, domain).get(job_id).view()


@router.post("/workflow-jobs/{job_id}/cancel", response_model=JobView)
async def cancel_workflow_job(
    request: Request, job_id: str, payload: JobDomainRequest
) -> JobView:
    return _store(request, payload.domain).request_cancel(job_id).view()


@router.post("/workflow-jobs/{job_id}/retry", response_model=JobView)
async def retry_workflow_job(
    request: Request, job_id: str, payload: JobDomainRequest
) -> JobView:
    """协作式重试：终态 → 重排队并经注册表调度；queued 且未调度 → 补调度（B3/G0）。

    - 重复点击/并发重试：已在本引擎调度中的任务不重复入队（幂等返回当前视图）；
    - 入队后调度异常或进程重启遗留的 `queued`：再次调用即补调度（显式动作，
      **不**在启动时自动重放模型任务）；
    - `running` 仍 409 `JOB_NOT_RETRYABLE`（由乐观锁与任务状态共同保证）。
    """
    domain = payload.domain
    store = _store(request, domain)
    registry, engine = _executors(request)
    try:
        record = store.retry(job_id)
    except AppError as exc:
        if exc.code != "JOB_NOT_RETRYABLE":
            raise
        current = store.get(job_id)
        if current.state != "queued":
            raise
        # queued 且本进程未在跑：补调度（幂等），否则按原契约 409
        if registry is None or not registry.has(domain, current.kind):
            raise
        if registry.schedule(engine, current):
            return store.get(job_id).view()
        raise
    if registry is not None:
        registry.schedule(engine, record)
    return store.get(job_id).view()


def _executors(request: Request):
    """取执行器注册表与引擎；未装配（隔离测试）返回 (None, None)。"""
    return (
        getattr(request.app.state, "job_executors", None),
        getattr(request.app.state, "job_engine", None),
    )
