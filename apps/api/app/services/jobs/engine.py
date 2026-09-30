"""后台任务执行引擎（TEACHING-LOOP B0 / T00-a 冻结接口）。

固定行为（与 ``app/repositories/jobs/repository.py`` 共同锁定）：

- ``claim`` → 载入冻结输入 → **启动心跳** → 取并发名额（模型任务先占 model 名额再占
  heavy 名额）→ 执行。心跳在名额等待之前启动（T00-a-01）：排队等待期间租约持续续期，
  不会因等待超过 ``lease_seconds`` 而被第二个执行者接管；等待期间心跳失权即取消等待，
  不执行、不发布，返回库中当前记录。
- 同时最多 ``heavy_limit``（默认 2）个后台重任务，其中最多 ``model_limit``（默认 1）
  个模型生成任务；模型任务同时占用两个名额；等待名额不丢任务。
- 心跳间隔 ``max(1, min(20, lease_seconds // 3))`` 秒；心跳失败（失权/接管/查询失败）
  立即取消执行器任务，**绝不发布**结果，返回库中当前记录（新持有者不被覆盖）。
- 执行器正常返回：若 ``cancellation_requested()`` 为真 → ``mark_cancelled``（迟到结果
  不发布）；否则 ``complete``（publish 与状态在同一事务内）。
- 执行器抛 ``AppError`` → ``fail_if_current_lease(code=exc.code, message=str(exc),
  retryable=exc.retryable)``；抛其他异常 → ``JOB_FAILED`` + 固定文案（不落堆栈、
  不落原始异常文本），返回记录且不再向上抛。重复领取（``claim`` 抛 ``JOB_BUSY``）
  仍按冻结契约向上抛给调用方。
- ``shutdown()`` 取消本引擎自建的任务并等待收尾（遗留 ``running`` 由下次启动的
  ``reconcile_all()`` / ``reconcile_interrupted()`` 收敛，不自动重跑模型）。

引擎应在服务事件循环内构造/调度（名额信号量首次使用时绑定当前循环）；测试用
``tmp_path`` 库与注入的假时钟，不联网、不读写正式数据目录。
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
import sqlite3
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import anyio

from app.contracts.teaching_loop import JOB_FAILED
from app.core.exceptions import AppError
from app.repositories.jobs.repository import JobLease, JobRecord, JobStore

logger = logging.getLogger(__name__)

#: 非 AppError 的执行器失败对外的固定文案（堆栈与原始异常文本不落库）。
INTERNAL_FAILURE_MESSAGE = "任务执行失败（内部错误）。"


@dataclass(frozen=True)
class FrozenJob:
    """执行器看到的冻结任务：输入、模型指纹与输入散列在创建时已定死。"""

    job_id: str
    domain: str
    kind: str
    attempt: int
    input: dict[str, Any]
    model_snapshot: dict[str, Any]
    input_hash: str


@dataclass(frozen=True)
class JobOutcome:
    """执行结果；``publish`` 在 ``complete`` 的同一事务内执行（抛错整体回滚）。"""

    result: dict[str, Any]
    publish: Callable[[sqlite3.Connection], None] | None = None


class JobContext:
    """执行器可用的协作式上下文：只暴露只读取消探测。"""

    def __init__(self, store: JobStore, job_id: str) -> None:
        self._store = store
        self._job_id = job_id

    async def cancellation_requested(self) -> bool:
        """是否已请求取消（本机单行读；执行器应周期性探测并尽快收尾）。"""
        return self._store.cancel_requested(self._job_id)


JobExecutor = Callable[[FrozenJob, JobContext], Awaitable[JobOutcome]]


class JobEngine:
    """多域任务执行器：只依赖各域的 ``JobStore``，不感知业务表。"""

    def __init__(
        self,
        stores: Mapping[str, JobStore],
        *,
        heavy_limit: int = 2,
        model_limit: int = 1,
    ) -> None:
        for name, value in (("heavy_limit", heavy_limit), ("model_limit", model_limit)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise AppError(
                    f"{name} 必须是不小于 1 的整数。",
                    code="INVALID_REQUEST",
                    status_code=422,
                )
        self._stores: dict[str, JobStore] = dict(stores)
        self._heavy_limit = heavy_limit
        self._model_limit = model_limit
        self._heavy: asyncio.Semaphore | None = None
        self._model: asyncio.Semaphore | None = None
        self._tasks: set[asyncio.Future[JobRecord]] = set()
        self._active = 0

    # ------------------------------------------------------------ 查询

    def store(self, domain: str) -> JobStore:
        """按域取任务表入口；未知域 → 422 ``INVALID_REQUEST``。"""
        store = self._stores.get(domain)
        if store is None:
            raise AppError(f"未知任务域：{domain!r}。", code="INVALID_REQUEST", status_code=422)
        return store

    @property
    def active_jobs(self) -> int:
        """当前持有并发名额、正在执行（含收尾）的任务数。"""
        return self._active

    def reconcile_all(self) -> dict[str, list[str]]:
        """逐库重启收敛；返回 ``{domain: [被置为 interrupted 的 job id]}``（含空列表）。"""
        return {
            domain: store.reconcile_interrupted()
            for domain, store in self._stores.items()
        }

    # ------------------------------------------------------------ 执行

    async def run_job(
        self,
        domain: str,
        job_id: str,
        executor: JobExecutor,
        *,
        uses_model: bool = False,
    ) -> JobRecord:
        """完整执行一轮任务；并发受限、心跳续租、取消与失败语义见模块 docstring。"""
        store = self.store(domain)
        lease = store.claim(job_id)
        record = store.load_frozen_input(job_id)
        frozen = FrozenJob(
            job_id=record.job_id,
            domain=record.domain,
            kind=record.kind,
            attempt=record.attempt,
            input=dict(record.frozen_input),
            model_snapshot=dict(record.model_snapshot),
            input_hash=record.input_hash,
        )
        # T00-a-01：心跳必须在等待并发名额之前启动，否则排队超过 lease_seconds
        # 的任务会因租约过期而被第二个执行者接管（同一 job 两个执行者）。
        interval = max(1, min(20, store.lease_seconds // 3))
        heartbeat = asyncio.ensure_future(self._heartbeat_loop(store, lease, interval))
        slots_held = False
        try:
            if not await self._acquire_slots_watching(uses_model, heartbeat):
                # 排队等待期间失权（被接管）：不执行、不发布，返回当前持有者记录
                return store.get(frozen.job_id)
            slots_held = True
            self._active += 1
            try:
                return await self._execute_claimed(
                    store, frozen, lease, executor, heartbeat
                )
            finally:
                self._active -= 1
        finally:
            await self._settle(heartbeat)
            if slots_held:
                self._release_slots(uses_model)

    def schedule(
        self,
        domain: str,
        job_id: str,
        executor: JobExecutor,
        *,
        uses_model: bool = False,
    ) -> "asyncio.Task[JobRecord]":
        """后台调度一轮任务；返回值可 await/取消，异常仍可经 ``await`` 取回。"""
        task = asyncio.ensure_future(
            self.run_job(domain, job_id, executor, uses_model=uses_model)
        )
        self._tasks.add(task)
        task.add_done_callback(self._on_done)
        return task

    async def shutdown(self) -> None:
        """取消本引擎自建的任务并等待收尾；之后 ``active_jobs == 0``。"""
        pending = [task for task in self._tasks if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for task in list(self._tasks):
            if task.done():
                self._tasks.discard(task)

    # ------------------------------------------------------------ 内部

    async def _execute_claimed(
        self,
        store: JobStore,
        frozen: FrozenJob,
        lease: JobLease,
        executor: JobExecutor,
        heartbeat: "asyncio.Future[None]",
    ) -> JobRecord:
        context = JobContext(store, frozen.job_id)
        execution: asyncio.Future[JobOutcome] | None = None
        try:
            execution = asyncio.ensure_future(executor(frozen, context))
            done, _pending = await asyncio.wait(
                {heartbeat, execution}, return_when=asyncio.FIRST_COMPLETED
            )
            if heartbeat in done:
                # 心跳失败（失权/被接管/查询失败）：执行器立即停止，绝不发布
                await self._settle(execution)
                return store.get(frozen.job_id)
            try:
                outcome = execution.result()
            except AppError as exc:
                return store.fail_if_current_lease(
                    frozen.job_id,
                    lease,
                    code=exc.code,
                    message=str(exc),
                    retryable=exc.retryable,
                )
            except Exception:
                logger.warning(
                    "任务执行失败（内部错误）：job=%s domain=%s kind=%s attempt=%s",
                    frozen.job_id,
                    frozen.domain,
                    frozen.kind,
                    frozen.attempt,
                )
                return store.fail_if_current_lease(
                    frozen.job_id,
                    lease,
                    code=JOB_FAILED,
                    message=INTERNAL_FAILURE_MESSAGE,
                )
            if await context.cancellation_requested():
                return store.mark_cancelled(frozen.job_id, lease)
            return store.complete(
                frozen.job_id,
                lease,
                result=outcome.result,
                publish=outcome.publish,
            )
        finally:
            if execution is not None:
                await self._settle(execution)

    async def _heartbeat_loop(
        self, store: JobStore, lease: JobLease, interval: int
    ) -> None:
        """按周期续租；失权或查询失败即返回（等待方据此停止执行器且不发布）。"""
        while True:
            await asyncio.sleep(interval)
            try:
                alive = await anyio.to_thread.run_sync(
                    functools.partial(store.heartbeat, lease)
                )
            except Exception:
                alive = False
            if not alive:
                return

    async def _acquire_slots_watching(
        self, uses_model: bool, heartbeat: "asyncio.Future[None]"
    ) -> bool:
        """等待并发名额，同时监视心跳；失权/取消时归还已到手名额并返回 ``False``。

        名额获取顺序：``uses_model=True`` 时先 model 后 heavy（模型任务同时占两个名额），
        否则只占 heavy。等待期间心跳持续续租（T00-a-01），不会出现"无心跳排队"。
        """
        self._ensure_primitives()
        assert self._heavy is not None and self._model is not None
        order: tuple[asyncio.Semaphore, ...] = (
            (self._model, self._heavy) if uses_model else (self._heavy,)
        )
        owned: list[asyncio.Semaphore] = []
        handed_over = False
        try:
            for semaphore in order:
                if not await self._wait_for_semaphore(semaphore, heartbeat):
                    return False
                owned.append(semaphore)
            handed_over = True
            return True
        finally:
            if not handed_over:
                for semaphore in reversed(owned):
                    semaphore.release()

    async def _wait_for_semaphore(
        self, semaphore: asyncio.Semaphore, heartbeat: "asyncio.Future[None]"
    ) -> bool:
        """等待一个名额，同时监视心跳；心跳先完成 → 返回 ``False`` 且不持有名额。"""
        acquire = asyncio.ensure_future(semaphore.acquire())
        try:
            done, _pending = await asyncio.wait(
                {acquire, heartbeat}, return_when=asyncio.FIRST_COMPLETED
            )
        except BaseException:
            await self._release_or_cancel(semaphore, acquire)
            raise
        if heartbeat in done:
            await self._release_or_cancel(semaphore, acquire)
            return False
        await self._settle(acquire)
        acquire.result()
        return True

    @staticmethod
    async def _release_or_cancel(
        semaphore: asyncio.Semaphore, acquire: "asyncio.Future[bool]"
    ) -> None:
        """等待中的 acquire：取消；已成功的 acquire：立即归还名额（不泄漏）。"""
        if acquire.done() and not acquire.cancelled() and acquire.exception() is None:
            semaphore.release()
            return
        await JobEngine._settle(acquire)

    def _release_slots(self, uses_model: bool) -> None:
        assert self._heavy is not None and self._model is not None
        self._heavy.release()
        if uses_model:
            self._model.release()

    def _ensure_primitives(self) -> None:
        if self._heavy is None or self._model is None:
            self._heavy = asyncio.Semaphore(self._heavy_limit)
            self._model = asyncio.Semaphore(self._model_limit)

    @staticmethod
    async def _settle(task: "asyncio.Future[Any]") -> None:
        """取消并等待一个子任务收尾；吞掉其取消/异常，避免悬挂与未检索告警。"""
        if not task.done():
            task.cancel()
        with contextlib.suppress(BaseException):
            await task
        if task.done() and not task.cancelled():
            with contextlib.suppress(BaseException):
                task.exception()

    def _on_done(self, task: "asyncio.Future[JobRecord]") -> None:
        self._tasks.discard(task)
        if not task.cancelled():
            # 取一次异常避免后台任务"未检索"告警；调用方仍可自行 await 取回。
            with contextlib.suppress(BaseException):
                task.exception()


__all__ = [
    "FrozenJob",
    "INTERNAL_FAILURE_MESSAGE",
    "JobContext",
    "JobEngine",
    "JobExecutor",
    "JobOutcome",
]
