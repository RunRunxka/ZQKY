"""V3 任务协议独立探针（V00 / TEACHING-LOOP B0）。

仓库层（可控时钟）：
  3① claim 递增 attempt、换新 token
  3② 未过期租约重复 claim → 409 JOB_BUSY（retryable）
  3③ 租约过期后可接管
  3④ 心跳失权返回 False；旧 lease complete → LEASE_LOST，库内结果为空
  3⑤ 取消：queued 立即 cancelled；running 置标志后 complete 不发布（publish 未调用、结果不落库）
  3⑥ reconcile_interrupted 只收敛 running 且幂等
  3⑦ retry 保留 frozen_input/model_snapshot/input_hash，attempt 不变；queued/running/succeeded 409

引擎层（真实 asyncio，短租约）：
  3⑧ 并发上限（heavy=2 / model=1）：同时进入 executor 的重任务 ≤2、模型任务 ≤1；
      排队等待期间租约持续续租（lease_expires_at 变化），不会被第二个执行者接管，
      等待者的 attempt 不变（同一 job 只有一个执行者）
  3⑧ 变体：heavy_limit=1 + model_limit=1 重跑同一探针
  3⑧ 附加：执行中失权（租约被夺）→ 执行器被停止、结果不发布
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _probe_common import EVIDENCE_DIR, check, cleanup, record, run_main, temp_root

from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.repositories.jobs.repository import JobStore
from app.repositories.teaching.catalog import TeachingCatalog
from app.services.jobs.engine import JobEngine, JobOutcome

PROBE = "v3_jobs_engine_probe"
KINDS = frozenset({"probe_kind"})
SIDE_EFFECT_TABLE = "probe_side_effect"


class Clock:
    """可控时钟：返回候选契约要求的 UTC ISO（秒精度、Z 结尾）。"""

    def __init__(self) -> None:
        self.now = datetime(2026, 9, 30, 0, 0, 0, tzinfo=UTC)

    def __call__(self) -> str:
        return self.now.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _make_store(root: Path, *, lease_seconds: int = 30, clock: Clock | None = None) -> tuple[JobStore, TeachingCatalog]:
    catalog = TeachingCatalog(root / "teaching" / "teaching.sqlite3")
    catalog.migrate()
    raw = connect(catalog.db_path)
    try:
        raw.execute(f"CREATE TABLE IF NOT EXISTS {SIDE_EFFECT_TABLE} (id TEXT PRIMARY KEY)")
    finally:
        raw.close()
    store = JobStore(
        catalog,
        domain="teaching",
        table="workflow_jobs",
        kinds=KINDS,
        lease_seconds=lease_seconds,
        now=clock,
    )
    return store, catalog


def _side_effects(catalog: TeachingCatalog) -> list[str]:
    raw = sqlite3.connect(str(catalog.db_path))
    try:
        return sorted(row[0] for row in raw.execute(f"SELECT id FROM {SIDE_EFFECT_TABLE}"))
    finally:
        raw.close()


def _raw_row(catalog: TeachingCatalog, job_id: str) -> dict:
    raw = sqlite3.connect(str(catalog.db_path))
    raw.row_factory = sqlite3.Row
    try:
        row = raw.execute("SELECT * FROM workflow_jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row is not None else {}
    finally:
        raw.close()


# --------------------------------------------------------------------------- 仓库层


def repo_lease_cycle(root: Path) -> None:
    clock = Clock()
    store, catalog = _make_store(root / "repo-lease", clock=clock)
    job = store.create(kind="probe_kind", frozen_input={"a": 1}, model_snapshot={"m": "x"})
    check("v3.0 create -> queued", job.state == "queued" and job.attempt == 0, f"state={job.state} attempt={job.attempt}")

    lease1 = store.claim(job.job_id)
    check(
        "v3.1a claim increments attempt to 1 and issues token",
        lease1.attempt == 1 and bool(lease1.token),
        f"attempt={lease1.attempt} token={lease1.token[:8]}... expires={lease1.expires_at}",
    )
    check(
        "v3.1b lease expiry = now + lease_seconds",
        lease1.expires_at == "2026-09-30T00:00:30Z",
        lease1.expires_at,
    )

    try:
        store.claim(job.job_id)
        record("v3.2 unexpired lease re-claim -> 409 JOB_BUSY", False, "no exception")
    except AppError as exc:
        check(
            "v3.2 unexpired lease re-claim -> 409 JOB_BUSY",
            exc.code == "JOB_BUSY" and exc.status_code == 409 and exc.retryable is True,
            f"code={exc.code} status={exc.status_code} retryable={exc.retryable}",
        )

    clock.advance(31)
    lease2 = store.claim(job.job_id)
    check(
        "v3.3a expired lease can be taken over (attempt+1, new token)",
        lease2.attempt == 2 and lease2.token != lease1.token,
        f"attempt={lease2.attempt} token_changed={lease2.token != lease1.token}",
    )
    check("v3.3b old holder heartbeat -> False", store.heartbeat(lease1) is False, "")
    check("v3.3c new holder heartbeat -> True", store.heartbeat(lease2) is True, "")
    try:
        store.complete(job.job_id, lease1, result={"late": True})
        record("v3.4a late complete with lost lease -> LEASE_LOST", False, "no exception")
    except AppError as exc:
        check(
            "v3.4a late complete with lost lease -> LEASE_LOST",
            exc.code == "LEASE_LOST" and exc.status_code == 409,
            f"code={exc.code} status={exc.status_code}",
        )
    row = _raw_row(catalog, job.job_id)
    check("v3.4b lost-lease publish left no result row", row.get("result_json") is None, str(row.get("result_json")))
    check("v3.4c row still owned by new holder", row.get("lease_token") == lease2.token, str(row.get("lease_token"))[:8])
    catalog.close()


def repo_cancel(root: Path) -> None:
    clock = Clock()
    store, catalog = _make_store(root / "repo-cancel", clock=clock)

    queued = store.create(kind="probe_kind", frozen_input={})
    cancelled = store.request_cancel(queued.job_id)
    check(
        "v3.5a queued cancel -> cancelled immediately",
        cancelled.state == "cancelled"
        and cancelled.cancel_requested
        and cancelled.finished_at is not None
        and cancelled.lease_token is None,
        f"state={cancelled.state} flag={cancelled.cancel_requested} finished={cancelled.finished_at}",
    )

    running = store.create(kind="probe_kind", frozen_input={"b": 2})
    lease = store.claim(running.job_id)
    flagged = store.request_cancel(running.job_id)
    check(
        "v3.5b running cancel -> only sets flag, stays running",
        flagged.state == "running" and flagged.cancel_requested is True and flagged.lease_token == lease.token,
        f"state={flagged.state} flag={flagged.cancel_requested}",
    )

    published: list[str] = []

    def publish(conn: sqlite3.Connection) -> None:
        published.append("called")
        conn.execute(f"INSERT INTO {SIDE_EFFECT_TABLE} (id) VALUES ('cancelled-late')")

    result = store.complete(running.job_id, lease, result={"late": "result"}, publish=publish)
    check(
        "v3.5c cancelled job: complete publishes nothing and lands cancelled",
        result.state == "cancelled" and result.result is None and published == [],
        f"state={result.state} result={result.result} publish_called={published}",
    )
    check("v3.5d cancelled publish wrote no business row", _side_effects(catalog) == [], str(_side_effects(catalog)))

    # 终态取消幂等
    terminal = store.create(kind="probe_kind", frozen_input={})
    terminal_lease = store.claim(terminal.job_id)
    store.complete(terminal.job_id, terminal_lease, result={"ok": True})
    after_success = store.get(terminal.job_id)
    repeat = store.request_cancel(terminal.job_id)
    check(
        "v3.5e cancel on terminal state is an idempotent no-op",
        repeat.state == "succeeded" and repeat.updated_at == after_success.updated_at and repeat.result == {"ok": True},
        f"state={repeat.state} updated_at={repeat.updated_at}",
    )
    catalog.close()


def repo_reconcile(root: Path) -> None:
    clock = Clock()
    store, catalog = _make_store(root / "repo-reconcile", clock=clock)
    running = store.create(kind="probe_kind", frozen_input={})
    store.claim(running.job_id)
    queued = store.create(kind="probe_kind", frozen_input={})
    succeeded = store.create(kind="probe_kind", frozen_input={})
    store.complete(succeeded.job_id, store.claim(succeeded.job_id), result={"done": True})

    first = store.reconcile_interrupted()
    check("v3.6a reconcile only touches running jobs", first == [running.job_id], str(first))
    check("v3.6b running -> interrupted + lease cleared",
          store.get(running.job_id).state == "interrupted" and store.get(running.job_id).lease_token is None,
          store.get(running.job_id).state)
    check("v3.6c queued untouched", store.get(queued.job_id).state == "queued", store.get(queued.job_id).state)
    check("v3.6d succeeded untouched", store.get(succeeded.job_id).state == "succeeded", store.get(succeeded.job_id).state)
    second = store.reconcile_interrupted()
    check("v3.6e reconcile is idempotent (second call = [])", second == [], str(second))
    catalog.close()


def repo_retry(root: Path) -> None:
    clock = Clock()
    store, catalog = _make_store(root / "repo-retry", clock=clock)
    frozen = {"payload": {"x": [1, 2, 3]}}
    snapshot = {"modelProfileId": "p-1", "fingerprint": "abc"}
    job = store.create(kind="probe_kind", frozen_input=frozen, model_snapshot=snapshot)
    lease = store.claim(job.job_id)
    failed = store.fail_if_current_lease(job.job_id, lease, code="PROBE_FAIL", message="探针失败", retryable=True)
    before = dict(
        frozen=failed.frozen_input,
        snapshot=failed.model_snapshot,
        input_hash=failed.input_hash,
        attempt=failed.attempt,
    )
    check("v3.7a failed state + error recorded", failed.state == "failed" and failed.error_code == "PROBE_FAIL", failed.state)

    try:
        store.create(kind="probe_kind", frozen_input={}, job_id=job.job_id)
        record("v3.7b duplicate job id rejected", False, "no exception")
    except AppError as exc:
        check("v3.7b duplicate job id rejected", exc.code == "JOB_ALREADY_EXISTS" and exc.status_code == 409, exc.code)

    queued = store.create(kind="probe_kind", frozen_input={})
    for state_name, target in (("queued", queued),):
        try:
            store.retry(target.job_id)
            record(f"v3.7c retry on {state_name} -> 409 JOB_NOT_RETRYABLE", False, "no exception")
        except AppError as exc:
            check(
                f"v3.7c retry on {state_name} -> 409 JOB_NOT_RETRYABLE",
                exc.code == "JOB_NOT_RETRYABLE" and exc.status_code == 409,
                f"code={exc.code} status={exc.status_code}",
            )

    succeeded_job = store.create(kind="probe_kind", frozen_input={})
    store.complete(succeeded_job.job_id, store.claim(succeeded_job.job_id), result={"done": True})
    for label, job_id in (("succeeded", succeeded_job.job_id),):
        try:
            store.retry(job_id)
            record(f"v3.7c retry on {label} -> 409 JOB_NOT_RETRYABLE", False, "no exception")
        except AppError as exc:
            check(
                f"v3.7c retry on {label} -> 409 JOB_NOT_RETRYABLE",
                exc.code == "JOB_NOT_RETRYABLE",
                exc.code,
            )

    running_job = store.create(kind="probe_kind", frozen_input={})
    store.claim(running_job.job_id)
    try:
        store.retry(running_job.job_id)
        record("v3.7c retry on running -> 409 JOB_NOT_RETRYABLE", False, "no exception")
    except AppError as exc:
        check("v3.7c retry on running -> 409 JOB_NOT_RETRYABLE", exc.code == "JOB_NOT_RETRYABLE", exc.code)

    requeued = store.retry(job.job_id)
    check(
        "v3.7d retry keeps frozen input / model snapshot / input hash",
        requeued.frozen_input == before["frozen"]
        and requeued.model_snapshot == before["snapshot"]
        and requeued.input_hash == before["input_hash"],
        f"frozen_ok={requeued.frozen_input == before['frozen']} snapshot_ok={requeued.model_snapshot == before['snapshot']}",
    )
    check(
        "v3.7e retry keeps attempt, clears lease/cancel flag",
        requeued.state == "queued"
        and requeued.attempt == before["attempt"]
        and requeued.lease_token is None
        and requeued.cancel_requested is False,
        f"state={requeued.state} attempt={requeued.attempt}",
    )
    reclaimed = store.claim(job.job_id)
    check("v3.7f next claim increments attempt", reclaimed.attempt == before["attempt"] + 1, str(reclaimed.attempt))
    catalog.close()


def repo_failure_paths(root: Path) -> None:
    clock = Clock()
    store, catalog = _make_store(root / "repo-fail", clock=clock)
    job = store.create(kind="probe_kind", frozen_input={})
    lease = store.claim(job.job_id)

    def exploding_publish(conn: sqlite3.Connection) -> None:
        conn.execute(f"INSERT INTO {SIDE_EFFECT_TABLE} (id) VALUES ('rolled-back')")
        raise RuntimeError("publish 探针失败")

    try:
        store.complete(job.job_id, lease, result={"should": "rollback"}, publish=exploding_publish)
        record("v3.9a publish failure rolls back result+status", False, "no exception")
    except RuntimeError as exc:
        record("v3.9a publish failure rolls back result+status", True, f"{exc!r}")
    row = _raw_row(catalog, job.job_id)
    check(
        "v3.9b after publish failure: state running, no result, no business row",
        row.get("state") == "running" and row.get("result_json") is None and _side_effects(catalog) == [],
        f"state={row.get('state')} result={row.get('result_json')} side_effects={_side_effects(catalog)}",
    )
    try:
        store.get("no-such-job")
        record("v3.9c unknown job -> 404 JOB_NOT_FOUND", False, "no exception")
    except AppError as exc:
        check("v3.9c unknown job -> 404 JOB_NOT_FOUND", exc.code == "JOB_NOT_FOUND" and exc.status_code == 404, exc.code)
    try:
        JobStore(catalog, domain="teaching", table="not_a_job_table", kinds=KINDS)
        record("v3.9d unknown table rejected", False, "no exception")
    except AppError as exc:
        check("v3.9d unknown table rejected", exc.code == "INVALID_REQUEST" and exc.status_code == 422, exc.code)
    catalog.close()


# --------------------------------------------------------------------------- 引擎层


class Timeline:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.t0 = time.monotonic()

    def add(self, kind: str, job: str) -> None:
        self.events.append({"t": round(time.monotonic() - self.t0, 3), "event": kind, "job": job})

    def max_concurrency(self, kind: str) -> int:
        current = 0
        peak = 0
        for event in self.events:
            if event["event"] == f"{kind}-start":
                current += 1
                peak = max(peak, current)
            elif event["event"] == f"{kind}-end":
                current -= 1
        return peak

    def starts_after(self, job: str, other: str) -> bool:
        start_job = next((e["t"] for e in self.events if e["event"] == "heavy-start" and e["job"] == job), None)
        end_other = next((e["t"] for e in self.events if e["event"] == "heavy-end" and e["job"] == other), None)
        return start_job is not None and end_other is not None and start_job >= end_other


async def _concurrency_scenario(
    root: Path,
    *,
    heavy_limit: int,
    model_limit: int,
    heavy_jobs: int,
    model_jobs: int,
    heavy_seconds: float,
    model_seconds: float,
) -> dict:
    """跑一组任务，返回并发/续租证据；重任务与模型任务分别计时。"""
    store, catalog = _make_store(root, lease_seconds=2)
    engine = JobEngine({"teaching": store}, heavy_limit=heavy_limit, model_limit=model_limit)
    timeline = Timeline()
    started: dict[str, float] = {}
    finished: dict[str, float] = {}
    executor_finished: dict[str, bool] = {}

    def make_executor(tag: str, seconds: float):
        async def executor(frozen, context):
            started[frozen.job_id] = time.monotonic()
            timeline.add(f"{tag}-start", frozen.job_id)
            try:
                await asyncio.sleep(seconds)
                executor_finished[frozen.job_id] = True
                return JobOutcome(result={"job": frozen.job_id, "tag": tag})
            finally:
                timeline.add(f"{tag}-end", frozen.job_id)
                finished[frozen.job_id] = time.monotonic()

        return executor

    heavy_ids = [
        store.create(kind="probe_kind", frozen_input={"i": i}).job_id for i in range(heavy_jobs)
    ]
    model_ids = [
        store.create(kind="probe_kind", frozen_input={"m": i}).job_id for i in range(model_jobs)
    ]
    tasks = [
        asyncio.ensure_future(engine.run_job("teaching", jid, make_executor("heavy", heavy_seconds)))
        for jid in heavy_ids
    ]
    tasks += [
        asyncio.ensure_future(
            engine.run_job("teaching", jid, make_executor("model", model_seconds), uses_model=True)
        )
        for jid in model_ids
    ]

    # 在第一个任务进入执行器后，观察排队任务的租约与接管情况
    wait_observations: dict[str, list[str]] = {}
    takeover_attempts: dict[str, list[str]] = {}
    await asyncio.sleep(0.3)
    deadline = time.monotonic() + 2.6
    while time.monotonic() < deadline:
        for jid in heavy_ids + model_ids:
            record_view = store.get(jid)
            if record_view.state == "running" and jid not in started:
                wait_observations.setdefault(jid, []).append(record_view.lease_expires_at or "")
                try:
                    store.claim(jid)
                    takeover_attempts.setdefault(jid, []).append("CLAIMED")
                except AppError as exc:
                    takeover_attempts.setdefault(jid, []).append(exc.code)
        await asyncio.sleep(0.4)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    summary = {
        "heavy_peak": timeline.max_concurrency("heavy"),
        "model_peak": timeline.max_concurrency("model"),
        "timeline": timeline.events,
        "wait_observations": wait_observations,
        "takeover_attempts": takeover_attempts,
        "results": [
            r.state if hasattr(r, "state") else f"{type(r).__name__}: {r}" for r in results
        ],
        "attempts_after": {jid: store.get(jid).attempt for jid in heavy_ids + model_ids},
        "executor_finished": executor_finished,
        "third_started_after_first_end": (
            timeline.starts_after(heavy_ids[-1], heavy_ids[0])
            or timeline.starts_after(heavy_ids[-1], heavy_ids[1])
        )
        if heavy_jobs >= 3
        else None,
        "engine_active_after": engine.active_jobs,
    }
    catalog.close()
    return summary


def engine_concurrency(root: Path) -> None:
    # 场景 1：heavy=2 / model=1，三个重任务（两个 3.4s + 一个 0.1s）
    summary = asyncio.run(
        _concurrency_scenario(
            root / "engine-heavy",
            heavy_limit=2,
            model_limit=1,
            heavy_jobs=3,
            model_jobs=0,
            heavy_seconds=3.4,
            model_seconds=0.0,
        )
    )
    (EVIDENCE_DIR / "v3_engine_heavy.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    check("v3.8a heavy peak <= 2", summary["heavy_peak"] <= 2, f"peak={summary['heavy_peak']}")
    check("v3.8b heavy peak == 2 (two slots actually used)", summary["heavy_peak"] == 2, f"peak={summary['heavy_peak']}")
    check(
        "v3.8c third heavy task waits for a free slot",
        summary["third_started_after_first_end"] is True,
        f"started_after_first_end={summary['third_started_after_first_end']}",
    )
    queued_id = None
    for jid, samples in summary["wait_observations"].items():
        if len(samples) >= 3:
            queued_id = jid
            distinct = len(set(samples))
            check(
                f"v3.8d waiting task {jid[:8]} keeps renewing lease while queued",
                distinct >= 2,
                f"samples={samples}",
            )
            check(
                f"v3.8e waiting task {jid[:8]} cannot be taken over (all claims JOB_BUSY)",
                all(code == "JOB_BUSY" for code in summary["takeover_attempts"].get(jid, [])),
                str(summary["takeover_attempts"].get(jid)),
            )
    check("v3.8f a queued task was observed waiting", queued_id is not None, f"observed={list(summary['wait_observations'])}")
    check(
        "v3.8g every heavy job succeeded with attempt=1 (single executor per job)",
        all(state == "succeeded" for state in summary["results"]) and all(a == 1 for a in summary["attempts_after"].values()),
        f"results={summary['results']} attempts={summary['attempts_after']}",
    )
    check("v3.8h engine slots released after run", summary["engine_active_after"] == 0, str(summary["engine_active_after"]))

    # 场景 2：模型任务上限 1（heavy=2 不构成限制）
    model_summary = asyncio.run(
        _concurrency_scenario(
            root / "engine-model",
            heavy_limit=2,
            model_limit=1,
            heavy_jobs=0,
            model_jobs=2,
            heavy_seconds=0.0,
            model_seconds=2.2,
        )
    )
    (EVIDENCE_DIR / "v3_engine_model.json").write_text(
        json.dumps(model_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    check("v3.8i model peak <= 1", model_summary["model_peak"] <= 1, f"peak={model_summary['model_peak']}")
    check("v3.8j model peak == 1", model_summary["model_peak"] == 1, f"peak={model_summary['model_peak']}")
    check(
        "v3.8k second model task renews lease while waiting for the model slot",
        any(len(set(samples)) >= 2 for samples in model_summary["wait_observations"].values()),
        str(model_summary["wait_observations"]),
    )
    check(
        "v3.8l waiting model task never taken over",
        all(
            all(code == "JOB_BUSY" for code in codes)
            for codes in model_summary["takeover_attempts"].values()
        ),
        str(model_summary["takeover_attempts"]),
    )
    check(
        "v3.8m both model jobs succeeded with attempt=1",
        all(state == "succeeded" for state in model_summary["results"])
        and all(a == 1 for a in model_summary["attempts_after"].values()),
        f"results={model_summary['results']} attempts={model_summary['attempts_after']}",
    )

    # 场景 3（变体）：heavy_limit=1 + model_limit=1 重跑
    variant = asyncio.run(
        _concurrency_scenario(
            root / "engine-variant",
            heavy_limit=1,
            model_limit=1,
            heavy_jobs=2,
            model_jobs=2,
            heavy_seconds=2.0,
            model_seconds=1.2,
        )
    )
    (EVIDENCE_DIR / "v3_engine_variant.json").write_text(
        json.dumps(variant, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    check("v3.8n variant heavy_limit=1 -> heavy peak == 1", variant["heavy_peak"] == 1, f"peak={variant['heavy_peak']}")
    check("v3.8o variant model_limit=1 -> model peak == 1", variant["model_peak"] == 1, f"peak={variant['model_peak']}")
    check(
        "v3.8p variant: all four jobs succeeded",
        all(state == "succeeded" for state in variant["results"]),
        str(variant["results"]),
    )


def engine_lease_lost(root: Path) -> None:
    """执行中租约被夺 → 心跳失败 → 执行器停止且不发布。"""
    store, catalog = _make_store(root / "engine-lost", lease_seconds=2)
    engine = JobEngine({"teaching": store}, heavy_limit=2, model_limit=1)
    state = {"executor_completed": False}

    async def executor(frozen, context):
        await asyncio.sleep(3.0)
        state["executor_completed"] = True
        return JobOutcome(result={"published": True})

    job = store.create(kind="probe_kind", frozen_input={})

    async def scenario():
        task = asyncio.ensure_future(engine.run_job("teaching", job.job_id, executor))
        for _ in range(60):
            await asyncio.sleep(0.1)
            if store.get(job.job_id).state == "running":
                break
        # 模拟"第二个执行者在租约过期后接管"：直接改库内租约 token
        raw = sqlite3.connect(str(catalog.db_path))
        try:
            raw.execute("UPDATE workflow_jobs SET lease_token = 'stolen-by-probe' WHERE id = ?", (job.job_id,))
            raw.commit()
        finally:
            raw.close()
        returned = await task
        return returned

    returned = asyncio.run(scenario())
    row = _raw_row(catalog, job.job_id)
    check(
        "v3.8q lease lost mid-execution: executor stopped, nothing published",
        state["executor_completed"] is False
        and row.get("result_json") is None
        and row.get("state") == "running"
        and returned.state == "running",
        f"executor_completed={state['executor_completed']} state={row.get('state')} result={row.get('result_json')}",
    )
    check("v3.8r engine slots released", engine.active_jobs == 0, str(engine.active_jobs))
    catalog.close()


def main() -> None:
    root = temp_root("v3")
    try:
        repo_lease_cycle(root)
        repo_cancel(root)
        repo_reconcile(root)
        repo_retry(root)
        repo_failure_paths(root)
        engine_concurrency(root)
        engine_lease_lost(root)
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
