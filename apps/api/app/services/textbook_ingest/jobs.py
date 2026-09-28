"""任务控制共享逻辑：租约续租、取消请求与可恢复任务筛选。

租约（计划 §5.6「每 20 秒续租」）：
- 每次 checkpoint 之前与每个批次/逐册循环边界调用续租检查；
- 判定条件是「距上次续租已超过阈值」，用可注入的**单调时钟**，不 sleep 阻塞；
- ``renew_lease`` 返回 False（记录已不属于本执行者/租约过期）→ 抛 ``LEASE_LOST`` 并立即停止，
  不再写向量、不再 checkpoint；记录不可写时任务保持 ``running``，交给恢复流程重新领取
  （失权 worker 不得修改有效修订或索引指针）。

取消语义：
- ``queued``：领取后立即结束为 ``cancelled``；
- ``running``：在 checkpoint 写 ``cancelRequested=true``，worker 在下一个 checkpoint 前检查；
- 已结束任务：原样返回，取消幂等。
"""

from __future__ import annotations

import time
from collections.abc import Callable

from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import JobRecord

FINAL_JOB_STATES = frozenset({"succeeded", "failed", "cancelled"})
#: 续租阈值（秒）：与计划 §5.6 的「每 20 秒续租」一致；真实批量嵌入再慢也在批次边界续租。
DEFAULT_RENEW_SECONDS = 20.0


def _lost_lease(message: str) -> AppError:
    return AppError(message, code="LEASE_LOST", status_code=409, retryable=True)


class LeaseKeeper:
    """按阈值续租的记账器；时钟可注入，测试不真实等待。"""

    def __init__(
        self,
        catalog: TextbookCatalog,
        *,
        renew_seconds: float = DEFAULT_RENEW_SECONDS,
        lease_seconds: int = 90,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if renew_seconds <= 0:
            raise ValueError("续租阈值必须是正数。")
        self.catalog = catalog
        self.renew_seconds = float(renew_seconds)
        self.lease_seconds = int(lease_seconds)
        self.monotonic = monotonic
        self._last: dict[str, float] = {}
        #: 实际成功续租次数（便于测试与运维观测）
        self.renewals = 0

    def begin(self, job_id: str) -> None:
        """任务领取后调用：把"上次续租"锚定在开始时刻。"""
        self._last[job_id] = self.monotonic()

    def forget(self, job_id: str) -> None:
        self._last.pop(job_id, None)

    def revise_seconds_elapsed(self, job_id: str) -> float | None:
        last = self._last.get(job_id)
        return None if last is None else self.monotonic() - last

    def renew_if_due(
        self, *, job_id: str, lease_token: str, force: bool = False
    ) -> bool:
        """到期（或 ``force``）时续租；失败抛 ``LEASE_LOST``，绝不静默继续。"""
        now = self.monotonic()
        last = self._last.get(job_id)
        if last is None:
            self._last[job_id] = now
            if not force:
                return False
        elif not force and (now - last) < self.renew_seconds:
            return False
        if not self.catalog.renew_lease(
            job_id, lease_token=lease_token, lease_seconds=self.lease_seconds
        ):
            raise _lost_lease(
                "任务租约已失效（续租被拒绝），worker 已停止写入；稍后由恢复流程重新领取。"
            )
        self._last[job_id] = now
        self.renewals += 1
        return True


def try_fail_lost_lease(catalog: TextbookCatalog, job: JobRecord) -> JobRecord | None:
    """尽力把失权任务落为 ``failed``/``LEASE_LOST``。

    记录已不可写（真实失权）时返回 ``None``：此时绝不能改任务、修订或索引指针，
    保持 ``running`` 由 ``recover_pending_jobs`` 在租约过期后重新领取。
    """
    if not job.lease_token:
        return None
    try:
        return catalog.finish_job(
            job.job_id,
            lease_token=job.lease_token,
            state="failed",
            error_code="LEASE_LOST",
            error_message="任务租约已失效，worker 已停止写入。",
        )
    except AppError as exc:
        if exc.code == "LEASE_LOST":
            return None
        raise


def request_cancel(
    catalog: TextbookCatalog, job_id: str, *, lease_seconds: int = 90
) -> JobRecord:
    record = catalog.get_job(job_id)
    if record is None:
        raise AppError("索引任务不存在。", code="JOB_NOT_FOUND", status_code=404)
    if record.state in FINAL_JOB_STATES:
        return record
    if record.state == "queued":
        claimed = catalog.claim_job(job_id, lease_seconds=lease_seconds)
        return catalog.finish_job(
            claimed.job_id,
            lease_token=claimed.lease_token or "",
            state="cancelled",
            error_code="JOB_CANCELLED",
            error_message="任务在开始前被取消。",
        )
    token = record.lease_token
    if not token:
        raise AppError(
            "任务租约缺失，无法写入取消请求。",
            code="LEASE_LOST",
            status_code=409,
            retryable=True,
        )
    payload = dict(record.checkpoint)
    payload["cancelRequested"] = True
    try:
        catalog.checkpoint_job(job_id, lease_token=token, checkpoint=payload)
    except AppError as exc:
        if exc.code == "LEASE_LOST":
            raise AppError(
                "任务租约已过期，取消请求未写入；稍后重试或等待自动恢复。",
                code="LEASE_LOST",
                status_code=409,
                retryable=True,
            ) from exc
        raise
    return catalog.get_job(job_id) or record


def recoverable_jobs(
    catalog: TextbookCatalog, *, kinds: tuple[str, ...], limit: int = 50
) -> list[JobRecord]:
    """queued 或租约已过期的 running 任务，按创建顺序返回。"""
    current = now_iso()
    found: list[JobRecord] = []
    for record in catalog.list_jobs(kinds=list(kinds), states=["queued", "running"], limit=limit):
        if record.state == "queued":
            found.append(record)
            continue
        if record.lease_until is None or record.lease_until <= current:
            found.append(record)
    return found
