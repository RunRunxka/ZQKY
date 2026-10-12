"""任务引擎与租约（B0 A6）：claim/心跳/失权不发布/取消（含迟到结果）/收敛/重试/并发上限。

全部使用 pytest ``tmp_path`` 临时库（三库真实迁移）与注入的假时钟/短租约（lease=3s →
心跳 1s），不连接任何真实服务、不读写正式 ``.local-data`` 与 ``.env``；全套时长约数秒。
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import pytest

from app.contracts.teaching_loop import canonical_hash
from app.core.exceptions import AppError
from app.core.sqlite import connect, transaction
from app.repositories.jobs.repository import JobLease, JobStore
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.teaching.catalog import TeachingCatalog
from app.services.jobs.engine import FrozenJob, JobContext, JobEngine, JobOutcome


class FakeClock:
    """可注入的任务钟：秒精度 UTC ISO-8601（与 ``now_iso`` 同格式，可排序比较）。"""

    def __init__(self, start: str = "2026-09-30T00:00:00Z") -> None:
        self.moment = datetime.fromisoformat(start)

    def now(self) -> str:
        return (
            self.moment.astimezone(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def advance(self, seconds: int) -> None:
        self.moment += timedelta(seconds=seconds)


def _teaching_store(
    tmp_path: Path,
    *,
    clock: FakeClock | None = None,
    lease_seconds: int = 90,
) -> tuple[TeachingCatalog, JobStore, FakeClock]:
    clock = clock or FakeClock()
    catalog = TeachingCatalog(tmp_path / "teaching.sqlite3")
    catalog.migrate()
    store = JobStore(
        catalog,
        domain="teaching",
        table="workflow_jobs",
        kinds=frozenset({"export", "batch"}),
        lease_seconds=lease_seconds,
        now=clock.now,
    )
    return catalog, store, clock


def _create_probe(catalog: Any) -> None:
    connection = connect(catalog.db_path)
    try:
        with transaction(connection, immediate=True) as tx:
            tx.execute("CREATE TABLE IF NOT EXISTS publish_probe (id TEXT PRIMARY KEY)")
    finally:
        connection.close()


def _probe_rows(catalog: Any) -> list[str]:
    connection = connect(catalog.db_path)
    try:
        return [
            row[0]
            for row in connection.execute(
                "SELECT id FROM publish_probe ORDER BY id"
            ).fetchall()
        ]
    finally:
        connection.close()


def _execute_sql(catalog: Any, sql: str, params: tuple[Any, ...] = ()) -> None:
    connection = connect(catalog.db_path)
    try:
        with transaction(connection, immediate=True) as tx:
            tx.execute(sql, params)
    finally:
        connection.close()


# --------------------------------------------------------------------------- 仓储


def test_create_queued_with_frozen_input_and_camel_view(tmp_path: Path) -> None:
    _catalog, store, _clock = _teaching_store(tmp_path)
    record = store.create(
        kind="export",
        frozen_input={"b": 2, "a": 1},
        model_snapshot={"modelProfileId": "p1", "model": "m1"},
    )
    assert record.state == "queued"
    assert record.attempt == 0
    assert record.input_hash == canonical_hash({"a": 1, "b": 2})
    assert record.frozen_input == {"a": 1, "b": 2}
    assert record.model_snapshot == {"modelProfileId": "p1", "model": "m1"}
    assert record.cancel_requested is False
    payload = record.view().model_dump(by_alias=True)
    assert payload["jobId"] == record.job_id
    assert payload["domain"] == "teaching"
    assert payload["kind"] == "export"
    assert payload["state"] == "queued"
    assert payload["attempt"] == 0
    assert payload["result"] is None
    assert payload["error"] is None
    assert "job_id" not in payload


def test_create_rejects_unknown_kind_and_table(tmp_path: Path) -> None:
    catalog, store, _clock = _teaching_store(tmp_path)
    with pytest.raises(AppError) as err:
        store.create(kind="never-registered")
    assert err.value.code == "INVALID_REQUEST"
    assert err.value.status_code == 422
    with pytest.raises(AppError):
        JobStore(catalog, domain="teaching", table="not_a_job_table", kinds=frozenset({"x"}))
    with pytest.raises(AppError):
        JobStore(catalog, domain="unknown", table="workflow_jobs", kinds=frozenset({"x"}))
    with pytest.raises(AppError):
        JobStore(catalog, domain="teaching", table="workflow_jobs", kinds=frozenset())


def test_claim_increments_attempt_and_busy_while_lease_alive(tmp_path: Path) -> None:
    _catalog, store, clock = _teaching_store(tmp_path)
    job = store.create(kind="export")
    lease = store.claim(job.job_id)
    assert lease.attempt == 1
    assert lease.token
    assert lease.expires_at == "2026-09-30T00:01:30Z"
    record = store.get(job.job_id)
    assert record.state == "running"
    assert record.attempt == 1
    assert record.lease_token == lease.token
    assert record.started_at == clock.now()
    assert store.load_frozen_input(job.job_id).input_hash == job.input_hash

    with pytest.raises(AppError) as err:
        store.claim(job.job_id)
    assert err.value.code == "JOB_BUSY"
    assert err.value.status_code == 409
    assert err.value.retryable is True
    assert store.get(job.job_id).attempt == 1  # 失败的 claim 不落库


def test_claim_after_lease_expiry_takes_over_and_old_lease_is_locked_out(
    tmp_path: Path,
) -> None:
    _catalog, store, clock = _teaching_store(tmp_path)
    job = store.create(kind="export")
    first = store.claim(job.job_id)
    clock.advance(91)
    second = store.claim(job.job_id)
    assert second.attempt == 2
    assert second.token != first.token

    with pytest.raises(AppError) as err:
        store.complete(job.job_id, first, result={"late": True})
    assert err.value.code == "LEASE_LOST"
    assert err.value.status_code == 409
    assert store.get(job.job_id).state == "running"

    done = store.complete(job.job_id, second, result={"ok": True})
    assert done.state == "succeeded"
    assert done.result == {"ok": True}
    assert done.lease_token is None
    assert done.finished_at is not None


def test_heartbeat_renews_current_lease_only(tmp_path: Path) -> None:
    _catalog, store, clock = _teaching_store(tmp_path)
    job = store.create(kind="export")
    lease = store.claim(job.job_id)

    clock.advance(30)
    assert store.heartbeat(lease) is True
    renewed = store.get(job.job_id)
    assert renewed.lease_expires_at == "2026-09-30T00:02:00Z"

    stale = JobLease(
        job_id=job.job_id,
        domain="teaching",
        attempt=lease.attempt,
        token="0" * 32,
        expires_at=lease.expires_at,
    )
    assert store.heartbeat(stale) is False
    assert store.get(job.job_id).lease_expires_at == renewed.lease_expires_at
    assert store.heartbeat(JobLease(job.job_id, "teaching", 0, "", "")) is False

    store.complete(job.job_id, lease, result={"ok": True})
    assert store.heartbeat(lease) is False  # 终态后不再续租


def test_complete_publish_same_transaction_and_rollback(tmp_path: Path) -> None:
    catalog, store, _clock = _teaching_store(tmp_path)
    _create_probe(catalog)
    job = store.create(kind="export")
    lease = store.claim(job.job_id)
    published: list[str] = []

    def publish(tx: sqlite3.Connection) -> None:
        tx.execute("INSERT INTO publish_probe (id) VALUES ('first')")
        published.append("first")

    done = store.complete(job.job_id, lease, result={"answer": 42}, publish=publish)
    assert done.state == "succeeded"
    assert done.result == {"answer": 42}
    assert published == ["first"]
    assert _probe_rows(catalog) == ["first"]

    job2 = store.create(kind="export")
    lease2 = store.claim(job2.job_id)

    def bad_publish(tx: sqlite3.Connection) -> None:
        tx.execute("INSERT INTO publish_probe (id) VALUES ('second')")
        raise RuntimeError("publish exploded")

    with pytest.raises(RuntimeError):
        store.complete(job2.job_id, lease2, result={"answer": 1}, publish=bad_publish)
    after = store.get(job2.job_id)
    assert after.state == "running"
    assert after.result is None
    assert after.finished_at is None
    assert after.lease_token == lease2.token  # 事务回滚后租约仍有效
    assert _probe_rows(catalog) == ["first"]  # 业务写入一并回滚

    done2 = store.complete(job2.job_id, lease2, result={"answer": 1})
    assert done2.state == "succeeded"


def test_complete_after_cancel_request_marks_cancelled_without_publishing(
    tmp_path: Path,
) -> None:
    catalog, store, _clock = _teaching_store(tmp_path)
    _create_probe(catalog)
    job = store.create(kind="export")
    lease = store.claim(job.job_id)

    requested = store.request_cancel(job.job_id)
    assert requested.state == "running"
    assert requested.cancel_requested is True

    def publish(tx: sqlite3.Connection) -> None:
        tx.execute("INSERT INTO publish_probe (id) VALUES ('nope')")

    done = store.complete(job.job_id, lease, result={"late": True}, publish=publish)
    assert done.state == "cancelled"
    assert done.result is None
    assert _probe_rows(catalog) == []


def test_request_cancel_queued_is_immediate_and_terminal_is_noop(tmp_path: Path) -> None:
    _catalog, store, _clock = _teaching_store(tmp_path)
    queued = store.create(kind="export")
    cancelled = store.request_cancel(queued.job_id)
    assert cancelled.state == "cancelled"
    assert cancelled.cancel_requested is True
    assert cancelled.finished_at is not None
    assert store.cancel_requested(queued.job_id) is True
    assert store.request_cancel(queued.job_id).state == "cancelled"  # 幂等

    done_job = store.create(kind="export")
    lease = store.claim(done_job.job_id)
    store.complete(done_job.job_id, lease, result={"ok": True})
    untouched = store.request_cancel(done_job.job_id)
    assert untouched.state == "succeeded"
    assert untouched.cancel_requested is False  # 终态原样返回


def test_mark_cancelled_with_stale_lease_does_not_overwrite_new_holder(
    tmp_path: Path,
) -> None:
    _catalog, store, clock = _teaching_store(tmp_path)
    job = store.create(kind="export")
    first = store.claim(job.job_id)
    clock.advance(91)
    second = store.claim(job.job_id)

    current = store.mark_cancelled(job.job_id, first)
    assert current.state == "running"
    assert current.attempt == 2
    assert current.lease_token == second.token

    updated = store.mark_cancelled(job.job_id, second)
    assert updated.state == "cancelled"
    assert updated.lease_token is None


def test_fail_if_current_lease_writes_error_or_skips_stale_lease(tmp_path: Path) -> None:
    _catalog, store, clock = _teaching_store(tmp_path)
    job = store.create(kind="export")
    lease = store.claim(job.job_id)

    failed = store.fail_if_current_lease(
        job.job_id,
        lease,
        code="MODEL_UNAVAILABLE",
        message="模型服务不可用。",
        retryable=True,
    )
    assert failed.state == "failed"
    assert failed.error_code == "MODEL_UNAVAILABLE"
    assert failed.error == {
        "code": "MODEL_UNAVAILABLE",
        "message": "模型服务不可用。",
        "retryable": True,
    }
    view = failed.view()
    assert view.error is not None
    assert view.error.code == "MODEL_UNAVAILABLE"
    assert view.error.retryable is True
    assert view.result is None

    job2 = store.create(kind="export")
    lease2 = store.claim(job2.job_id)
    clock.advance(91)
    store.claim(job2.job_id)  # 新持有者接管
    skipped = store.fail_if_current_lease(
        job2.job_id, lease2, code="STALE", message="过期失败不得写入。"
    )
    assert skipped.state == "running"
    assert skipped.error_code is None
    assert skipped.attempt == 2


def test_reconcile_interrupted_only_running_and_idempotent(tmp_path: Path) -> None:
    _catalog, store, _clock = _teaching_store(tmp_path)
    running = store.create(kind="export")
    queued = store.create(kind="batch")
    store.claim(running.job_id)

    converged = store.reconcile_interrupted()
    assert converged == [running.job_id]
    record = store.get(running.job_id)
    assert record.state == "interrupted"
    assert record.lease_token is None
    assert record.finished_at is not None
    assert store.get(queued.job_id).state == "queued"
    assert store.reconcile_interrupted() == []


def test_retry_preserves_frozen_input_and_attempt_until_next_claim(tmp_path: Path) -> None:
    _catalog, store, _clock = _teaching_store(tmp_path)
    job = store.create(
        kind="export", frozen_input={"chapter": 3}, model_snapshot={"model": "m1"}
    )
    lease = store.claim(job.job_id)
    store.fail_if_current_lease(job.job_id, lease, code="E", message="失败。")

    retried = store.retry(job.job_id)
    assert retried.state == "queued"
    assert retried.attempt == 1  # 下次 claim 才 +1
    assert retried.frozen_input == {"chapter": 3}
    assert retried.model_snapshot == {"model": "m1"}
    assert retried.input_hash == job.input_hash

    renewed = store.claim(job.job_id)
    assert renewed.attempt == 2


def test_retry_clears_previous_error_so_queued_view_has_no_failure(
    tmp_path: Path,
) -> None:
    """V00 observation：retry 后 ``queued`` 视图不得残留上一轮失败（UI 误读）。"""
    _catalog, store, _clock = _teaching_store(tmp_path)
    job = store.create(
        kind="export", frozen_input={"chapter": 3}, model_snapshot={"model": "m1"}
    )
    lease = store.claim(job.job_id)
    failed = store.fail_if_current_lease(
        job.job_id,
        lease,
        code="MODEL_CONFIG_INVALID",
        message="模型配置已失效。",
        retryable=True,
    )
    assert failed.error_code == "MODEL_CONFIG_INVALID"
    assert failed.error is not None

    retried = store.retry(job.job_id)
    assert retried.state == "queued"
    assert retried.error_code is None
    assert retried.error is None
    assert retried.view().error is None  # 对外视图不携带上一轮失败
    # 原有不变量：冻结输入、模型指纹、input_hash 与 attempt 全部保留
    assert retried.frozen_input == {"chapter": 3}
    assert retried.model_snapshot == {"model": "m1"}
    assert retried.input_hash == job.input_hash
    assert retried.attempt == 1


def test_retry_rejected_for_queued_running_and_succeeded(tmp_path: Path) -> None:
    _catalog, store, _clock = _teaching_store(tmp_path)

    queued = store.create(kind="export")
    with pytest.raises(AppError) as err:
        store.retry(queued.job_id)
    assert err.value.code == "JOB_NOT_RETRYABLE"
    assert err.value.status_code == 409

    running = store.create(kind="export")
    store.claim(running.job_id)
    with pytest.raises(AppError) as err2:
        store.retry(running.job_id)
    assert err2.value.code == "JOB_NOT_RETRYABLE"

    succeeded = store.create(kind="export")
    lease = store.claim(succeeded.job_id)
    store.complete(succeeded.job_id, lease, result={"ok": True})
    with pytest.raises(AppError) as err3:
        store.retry(succeeded.job_id)
    assert err3.value.code == "JOB_NOT_RETRYABLE"


def test_retry_of_cancelled_job_clears_cancel_flag_and_can_run(tmp_path: Path) -> None:
    _catalog, store, _clock = _teaching_store(tmp_path)
    job = store.create(kind="export")
    store.request_cancel(job.job_id)
    retried = store.retry(job.job_id)
    assert retried.state == "queued"
    assert retried.cancel_requested is False

    lease = store.claim(job.job_id)
    assert store.cancel_requested(job.job_id) is False
    done = store.complete(job.job_id, lease, result={"ok": True})
    assert done.state == "succeeded"


def test_get_unknown_job_is_404(tmp_path: Path) -> None:
    _catalog, store, _clock = _teaching_store(tmp_path)
    with pytest.raises(AppError) as err:
        store.get("does-not-exist")
    assert err.value.code == "JOB_NOT_FOUND"
    assert err.value.status_code == 404
    with pytest.raises(AppError) as err2:
        store.cancel_requested("does-not-exist")
    assert err2.value.code == "JOB_NOT_FOUND"


def test_get_corrupt_state_row_is_not_silently_queued(tmp_path: Path) -> None:
    # workflow_jobs 的 state 有 CHECK 约束，用无 CHECK 的 question_jobs 构造坏 state
    catalog = QuestionBankCatalog(tmp_path / "question-bank.sqlite3")
    catalog.migrate()
    store = JobStore(
        catalog, domain="question", table="question_jobs", kinds=frozenset({"organize"})
    )
    job = store.create(kind="organize")
    _execute_sql(
        catalog, "UPDATE question_jobs SET state = 'mystery' WHERE id = ?", (job.job_id,)
    )
    with pytest.raises(AppError) as err:
        store.get(job.job_id)
    assert err.value.code == "CORRUPT_JOB_ROW"
    assert err.value.status_code == 500


def test_get_corrupt_json_column_is_rejected(tmp_path: Path) -> None:
    catalog, store, _clock = _teaching_store(tmp_path)
    job = store.create(kind="export")
    _execute_sql(
        catalog,
        "UPDATE workflow_jobs SET frozen_input_json = 'not-json' WHERE id = ?",
        (job.job_id,),
    )
    with pytest.raises(AppError) as err:
        store.get(job.job_id)
    assert err.value.code == "CORRUPT_JOB_ROW"


def test_job_store_covers_all_three_domains(tmp_path: Path) -> None:
    cases: list[tuple[str, Any, str, str]] = [
        ("knowledge", KnowledgeCatalog, "knowledge_jobs", "ingest"),
        ("teaching", TeachingCatalog, "workflow_jobs", "export"),
        ("question", QuestionBankCatalog, "question_jobs", "organize"),
    ]
    for domain, catalog_cls, table, kind in cases:
        catalog = catalog_cls(tmp_path / f"{domain}.sqlite3")
        catalog.migrate()
        store = JobStore(
            catalog,
            domain=domain,
            table=table,
            kinds=frozenset({kind}),
            lease_seconds=30,
        )
        job = store.create(kind=kind, frozen_input={"domain": domain})
        lease = store.claim(job.job_id)
        assert lease.attempt == 1
        done = store.complete(job.job_id, lease, result={"domain": domain})
        assert done.state == "succeeded"
        assert done.view().job_id == job.job_id


def test_get_reads_legacy_question_job_row(tmp_path: Path) -> None:
    catalog = QuestionBankCatalog(tmp_path / "question-bank.sqlite3")
    catalog.migrate()
    legacy = catalog.create_job(kind="organize")  # 0002 迁移之前的既有写入路径
    store = JobStore(
        catalog, domain="question", table="question_jobs", kinds=frozenset({"organize"})
    )
    record = store.get(legacy.job_id)
    assert record.state == "queued"
    assert record.attempt == 0
    assert record.frozen_input == {}
    assert record.error is None


# --------------------------------------------------------------------------- 引擎


@dataclass
class EngineEnv:
    catalog: TeachingCatalog
    store: JobStore
    engine: JobEngine
    clock: FakeClock


@pytest.fixture()
def engine_env(tmp_path: Path) -> EngineEnv:
    clock = FakeClock()
    catalog = TeachingCatalog(tmp_path / "teaching.sqlite3")
    catalog.migrate()
    store = JobStore(
        catalog,
        domain="teaching",
        table="workflow_jobs",
        kinds=frozenset({"export", "batch"}),
        lease_seconds=3,  # 心跳间隔 = 1s，测试不等待 90s 租约
        now=clock.now,
    )
    engine = JobEngine({"teaching": store}, heavy_limit=2, model_limit=1)
    return EngineEnv(catalog=catalog, store=store, engine=engine, clock=clock)


async def _wait_until(predicate: Callable[[], bool], *, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("等待条件超时。")


async def test_engine_run_job_uses_frozen_input_and_persists_result(
    engine_env: EngineEnv,
) -> None:
    env = engine_env
    job = env.store.create(kind="export", frozen_input={"n": 1})
    seen: list[FrozenJob] = []

    async def executor(frozen: FrozenJob, context: JobContext) -> JobOutcome:
        seen.append(frozen)
        assert await context.cancellation_requested() is False
        return JobOutcome(result={"echo": frozen.input["n"]})

    record = await env.engine.run_job("teaching", job.job_id, executor)
    assert record.state == "succeeded"
    assert record.result == {"echo": 1}
    assert seen[0].job_id == job.job_id
    assert seen[0].attempt == 1
    assert seen[0].input_hash == job.input_hash
    assert seen[0].domain == "teaching"
    assert env.engine.active_jobs == 0


async def test_engine_limits_model_jobs_to_one(engine_env: EngineEnv) -> None:
    env = engine_env
    entered: list[str] = []
    release = asyncio.Event()

    async def executor(frozen: FrozenJob, context: JobContext) -> JobOutcome:
        entered.append(frozen.job_id)
        await release.wait()
        return JobOutcome(result={"jobId": frozen.job_id})

    first = env.store.create(kind="export")
    second = env.store.create(kind="export")
    task_a = env.engine.schedule("teaching", first.job_id, executor, uses_model=True)
    task_b = env.engine.schedule("teaching", second.job_id, executor, uses_model=True)

    await _wait_until(lambda: len(entered) == 1)
    await asyncio.sleep(0.1)  # 给第二个任务进入的机会（模型名额已满，不应进入）
    assert entered == [first.job_id]
    assert env.engine.active_jobs == 1

    release.set()
    await asyncio.gather(task_a, task_b)
    assert entered == [first.job_id, second.job_id]
    assert env.engine.active_jobs == 0


async def test_engine_limits_heavy_jobs_to_two(engine_env: EngineEnv) -> None:
    env = engine_env
    entered: list[str] = []
    release = asyncio.Event()

    async def executor(frozen: FrozenJob, context: JobContext) -> JobOutcome:
        entered.append(frozen.job_id)
        await release.wait()
        return JobOutcome(result={})

    jobs = [env.store.create(kind="batch") for _ in range(3)]
    tasks = [
        env.engine.schedule("teaching", job.job_id, executor) for job in jobs
    ]
    await _wait_until(lambda: len(entered) == 2)
    await asyncio.sleep(0.1)
    assert len(entered) == 2  # 第三个任务排队等待名额
    assert env.engine.active_jobs == 2

    release.set()
    await asyncio.gather(*tasks)
    assert len(entered) == 3
    assert env.engine.active_jobs == 0


async def test_engine_cancellation_probe_discards_late_result(engine_env: EngineEnv) -> None:
    env = engine_env
    job = env.store.create(kind="export")
    started = asyncio.Event()
    gate = asyncio.Event()
    saw: list[bool] = []

    async def executor(frozen: FrozenJob, context: JobContext) -> JobOutcome:
        started.set()
        await gate.wait()
        saw.append(await context.cancellation_requested())
        return JobOutcome(result={"late": True})

    task = env.engine.schedule("teaching", job.job_id, executor)
    await asyncio.wait_for(started.wait(), timeout=3)
    env.store.request_cancel(job.job_id)
    gate.set()

    record = await asyncio.wait_for(task, timeout=3)
    assert saw == [True]
    assert record.state == "cancelled"
    assert record.result is None
    assert env.store.get(job.job_id).state == "cancelled"


async def test_engine_executor_app_error_fails_with_code_and_retryable(
    engine_env: EngineEnv,
) -> None:
    env = engine_env
    job = env.store.create(kind="export")

    async def executor(frozen: FrozenJob, context: JobContext) -> JobOutcome:
        raise AppError(
            "模型连接不可用。", code="MODEL_UNAVAILABLE", status_code=503, retryable=True
        )

    record = await env.engine.run_job("teaching", job.job_id, executor)
    assert record.state == "failed"
    assert record.error_code == "MODEL_UNAVAILABLE"
    assert record.error == {
        "code": "MODEL_UNAVAILABLE",
        "message": "模型连接不可用。",
        "retryable": True,
    }
    assert record.view().error is not None
    assert record.view().error.retryable is True
    assert env.store.retry(job.job_id).state == "queued"


async def test_engine_internal_error_hides_stack_and_raw_message(
    engine_env: EngineEnv,
) -> None:
    env = engine_env
    job = env.store.create(kind="export")
    secret = "sk-live-should-never-appear"

    async def executor(frozen: FrozenJob, context: JobContext) -> JobOutcome:
        raise RuntimeError(f"boom {secret} at C:\\private\\path")

    record = await env.engine.run_job("teaching", job.job_id, executor)
    assert record.state == "failed"
    assert record.error_code == "JOB_FAILED"
    assert record.error is not None
    assert record.error["message"] == "任务执行失败（内部错误）。"
    stored = json.dumps(record.error, ensure_ascii=False)
    assert secret not in stored
    assert "private" not in stored


async def test_engine_heartbeat_loss_cancels_executor_and_publishes_nothing(
    engine_env: EngineEnv,
) -> None:
    env = engine_env
    job = env.store.create(kind="export")
    started = asyncio.Event()
    cancelled = asyncio.Event()
    never = asyncio.Event()
    published: list[int] = []

    async def executor(frozen: FrozenJob, context: JobContext) -> JobOutcome:
        started.set()
        try:
            await never.wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return JobOutcome(
            result={"late": True}, publish=lambda tx: published.append(1)
        )

    task = env.engine.schedule("teaching", job.job_id, executor)
    await asyncio.wait_for(started.wait(), timeout=3)

    env.clock.advance(91)  # 旧租约过期
    takeover = env.store.claim(job.job_id)  # 新持有者接管
    assert takeover.attempt == 2

    record = await asyncio.wait_for(task, timeout=6)
    assert cancelled.is_set()  # 下一次心跳失权后执行器被取消
    assert record.state == "running"
    assert record.attempt == 2
    assert record.result is None
    assert published == []
    assert env.store.get(job.job_id).lease_token == takeover.token  # 新持有者不被覆盖


async def test_engine_second_runner_gets_busy_and_shutdown_converges(
    engine_env: EngineEnv,
) -> None:
    env = engine_env
    job = env.store.create(kind="export")
    started = asyncio.Event()
    never = asyncio.Event()

    async def executor(frozen: FrozenJob, context: JobContext) -> JobOutcome:
        started.set()
        await never.wait()
        return JobOutcome(result={"ok": True})

    task = env.engine.schedule("teaching", job.job_id, executor)
    await asyncio.wait_for(started.wait(), timeout=3)
    assert env.engine.active_jobs == 1

    with pytest.raises(AppError) as err:
        await env.engine.run_job("teaching", job.job_id, executor)
    assert err.value.code == "JOB_BUSY"

    await env.engine.shutdown()
    assert env.engine.active_jobs == 0
    assert task.cancelled()
    # shutdown 不自动重跑：遗留 running 交由重启收敛
    assert env.store.get(job.job_id).state == "running"
    assert env.engine.reconcile_all() == {"teaching": [job.job_id]}
    assert env.store.get(job.job_id).state == "interrupted"
    assert env.engine.reconcile_all() == {"teaching": []}


async def test_engine_unknown_domain_is_422(engine_env: EngineEnv) -> None:
    env = engine_env
    with pytest.raises(AppError) as err:
        env.engine.store("bogus")
    assert err.value.code == "INVALID_REQUEST"
    assert err.value.status_code == 422

    async def executor(frozen: FrozenJob, context: JobContext) -> JobOutcome:
        raise AssertionError("未知域不应执行")

    with pytest.raises(AppError) as err2:
        await env.engine.run_job("bogus", "job-id", executor)
    assert err2.value.code == "INVALID_REQUEST"


async def test_engine_slot_wait_keeps_lease_and_blocks_takeover(tmp_path: Path) -> None:
    """T00-a-01 回归：排队等待并发名额期间，租约必须持续续期，且同一任务不可被接管。

    旧实现（心跳在取到名额之后才启动）中，第二个任务在等待超过 ``lease_seconds`` 后
    租约过期，任何一次 ``claim`` 都会按"过期接管"成功 → 同一 job 出现两个执行者。
    本用例对实现方式不做假设，只断言不变量：等待期租约有效、不能被接管、
    执行器并发度恒为 1。
    """
    clock = FakeClock()
    catalog = TeachingCatalog(tmp_path / "teaching.sqlite3")
    catalog.migrate()
    store = JobStore(
        catalog,
        domain="teaching",
        table="workflow_jobs",
        kinds=frozenset({"export"}),
        lease_seconds=3,
        now=clock.now,
    )
    engine = JobEngine({"teaching": store}, heavy_limit=1, model_limit=1)

    first = store.create(kind="export")
    second = store.create(kind="export")
    entered: list[str] = []
    concurrent = 0
    max_concurrent = 0
    release_first = asyncio.Event()

    async def executor(frozen: FrozenJob, context: JobContext) -> JobOutcome:
        nonlocal concurrent, max_concurrent
        concurrent += 1
        max_concurrent = max(max_concurrent, concurrent)
        entered.append(frozen.job_id)
        try:
            if frozen.job_id == first.job_id:
                await release_first.wait()
            return JobOutcome(result={"jobId": frozen.job_id})
        finally:
            concurrent -= 1

    task_a = engine.schedule("teaching", first.job_id, executor)
    await _wait_until(lambda: entered == [first.job_id])
    task_b = engine.schedule("teaching", second.job_id, executor)

    # 第二个任务已领取（running）、在等待唯一的名额，尚未进入执行器
    await _wait_until(lambda: store.get(second.job_id).state == "running")
    assert store.get(second.job_id).attempt == 1
    assert entered == [first.job_id]

    # 总等待时间超过租约，但每次在到期前续期。一次跳到已过期不应再被心跳复活。
    # 10次×2s的任务钟，真实等待每个心跳周期（1s），核验持续排队仍保留有效租约。
    for _ in range(10):
        expiry_before = [store.get(item.job_id).lease_expires_at for item in (first, second)]
        clock.advance(2)
        await _wait_until(
            lambda: all((current := store.get(item.job_id)).state == "running"
                        and current.attempt == 1 and current.lease_expires_at is not None
                        and current.lease_expires_at > previous and current.lease_expires_at > clock.now()
                        for item, previous in zip((first, second), expiry_before)),
            timeout=4.0,
        )
        assert entered == [first.job_id]
        assert not task_a.done() and not task_b.done()
    waiting = store.get(second.job_id)
    assert waiting.attempt == 1
    assert waiting.lease_expires_at is not None
    assert waiting.lease_expires_at > clock.now()  # 等待期租约持续有效（心跳在工作）

    # 等待期间不能被第二个执行者接管（旧实现这里会成功接管）
    with pytest.raises(AppError) as err:
        store.claim(second.job_id)
    assert err.value.code == "JOB_BUSY"

    release_first.set()
    records = await asyncio.gather(task_a, task_b)
    assert [record.state for record in records] == ["succeeded", "succeeded"]
    assert max_concurrent == 1  # 同一 job 绝不会有两个执行者并发
    assert entered == [first.job_id, second.job_id]
    assert engine.active_jobs == 0
