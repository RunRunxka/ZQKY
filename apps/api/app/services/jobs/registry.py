"""任务执行器注册表（TEACHING-LOOP B3 / G0 · B2-RV01 公共修复）。

背景：B0 的公共 `POST /workflow-jobs/{id}/retry` 只把任务置回 `queued`，没有任何
调度路径，用户点击重试后任务永远排队。本模块提供**唯一**的域/类型执行器注册表：
域服务在装配时注册自己的执行器工厂，公共 retry 经它调度，不引入第二套无租约执行器。

约定：

- ``factory(record) -> JobExecutor``：域服务按任务行（frozen_input/kind/attempt）构造执行器；
  执行器仍是 ``JobExecutor``（``FrozenJob, JobContext -> JobOutcome``），租约/心跳/取消/发布
  语义全部由 ``JobEngine`` 负责。
- 调度幂等：同一 (domain, jobId) 已在引擎内调度时不再重复入队（重复点击/并发 retry 只执行一次）。
- 未注册的 (domain, kind)：``schedule`` 返回 False，任务保持 `queued` 并可由用户再次 retry
  （不报错、不伪造成功）；显式 retry 是唯一调度入口，重启后不自动重放。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.core.exceptions import AppError
from app.repositories.jobs.repository import JobRecord
from app.services.jobs.engine import JobExecutor


@dataclass(frozen=True)
class ExecutorSpec:
    """一个 (domain, kind) 的执行方式。"""

    domain: str
    kind: str
    uses_model: bool
    factory: Callable[[JobRecord], JobExecutor]


class JobExecutorRegistry:
    """域/类型 → 执行器工厂；进程内注册，装配期完成。"""

    def __init__(self) -> None:
        self._specs: dict[tuple[str, str], ExecutorSpec] = {}

    def register(
        self,
        domain: str,
        kind: str,
        *,
        uses_model: bool,
        factory: Callable[[JobRecord], JobExecutor],
    ) -> None:
        if not domain or not kind:
            raise AppError("注册执行器需要非空 domain/kind。", code="INVALID_REQUEST", status_code=422)
        if not callable(factory):
            raise AppError("执行器 factory 必须可调用。", code="INVALID_REQUEST", status_code=422)
        key = (domain, kind)
        if key in self._specs:
            raise AppError(
                f"执行器重复注册：{domain}:{kind}。",
                code="INVALID_REQUEST",
                status_code=422,
            )
        self._specs[key] = ExecutorSpec(
            domain=domain, kind=kind, uses_model=bool(uses_model), factory=factory
        )

    def spec_for(self, domain: str, kind: str) -> ExecutorSpec | None:
        return self._specs.get((domain, kind))

    def has(self, domain: str, kind: str) -> bool:
        return (domain, kind) in self._specs

    def schedule(self, engine: object, record: JobRecord) -> bool:
        """把已重排队的任务交给引擎执行；返回是否已（或已在）调度。

        - 引擎已有同任务在跑（含本次点击重复）→ True（幂等，不重复执行）；
        - 无注册执行器 → False（任务保持 queued，用户可再次 retry）；
        - 引擎装配缺失 → 抛 503（不静默排队）。
        """
        spec = self.spec_for(record.domain, record.kind)
        if spec is None:
            return False
        engine_schedule = getattr(engine, "schedule", None)
        is_tracking = getattr(engine, "is_tracking", None)
        if not callable(engine_schedule) or not callable(is_tracking):
            raise AppError(
                "任务引擎未装配完整，无法调度重试任务。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        if is_tracking(record.domain, record.job_id):
            return True
        engine_schedule(
            record.domain,
            record.job_id,
            spec.factory(record),
            uses_model=spec.uses_model,
        )
        return True

    def kinds(self) -> list[tuple[str, str]]:
        return sorted(self._specs)
