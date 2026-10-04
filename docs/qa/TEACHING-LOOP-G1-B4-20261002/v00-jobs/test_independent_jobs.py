"""G1 independent correct-behavior probes, with owned fixtures and raw SQL oracles.

Only temporary databases are created. No app.main or existing test helper is imported.
The publication callback deliberately writes both business and checkpoint data, so
an expired worker must leave the entire job row and domain data byte-for-byte equal.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

assert os.environ.get("ZQKY_ENV") == "test"
assert os.environ.get("ZQKY_DATA_DIR"), "Set a fresh data root before app imports"

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1.workflow_jobs import router
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.repositories.jobs.repository import JobStore
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.teaching.catalog import TeachingCatalog
from app.services.jobs.engine import JobEngine, JobOutcome
from app.services.jobs.registry import JobExecutorRegistry


class Clock:
    def __init__(self):
        self.seconds = 0
        self.reads = []
        self.lock = threading.Lock()

    def now(self):
        with self.lock:
            second = self.seconds
            self.reads.append((threading.current_thread().name, second))
        return (datetime(2026, 10, 2, tzinfo=UTC) + timedelta(seconds=second)).isoformat().replace("+00:00", "Z")

    def set(self, seconds):
        with self.lock:
            self.seconds = seconds


def fixture(path, domain="teaching", ttl=3):
    catalog_class, table, kind = {
        "teaching": (TeachingCatalog, "workflow_jobs", "export"),
        "knowledge": (KnowledgeCatalog, "knowledge_jobs", "extract"),
        "question": (QuestionBankCatalog, "question_jobs", "organize"),
    }[domain]
    catalog = catalog_class(path / (domain + ".sqlite3"))
    catalog.migrate()
    clock = Clock()
    store = JobStore(catalog, domain=domain, table=table, kinds={kind}, lease_seconds=ttl, now=clock.now)
    with catalog.write_transaction() as tx:
        tx.execute("CREATE TABLE independent_business (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    job = store.create(kind=kind, frozen_input={"chosen": ["fixed-1", "fixed-2"], "rule": "unchanged"},
                       model_snapshot={"profile": "fixed-model"})
    with catalog.write_transaction() as tx:
        tx.execute(f"UPDATE {table} SET checkpoint_json=? WHERE id=?", ('{"position":7,"fixed":"old"}', job.job_id))
    return catalog, store, clock, job


def raw_row(catalog, store, job_id):
    conn = connect(catalog.db_path)
    try:
        return dict(conn.execute(f"SELECT * FROM {store.table} WHERE id=?", (job_id,)).fetchone())
    finally:
        conn.close()


def business(catalog):
    conn = connect(catalog.db_path)
    try:
        return [tuple(row) for row in conn.execute("SELECT * FROM independent_business ORDER BY id")]
    finally:
        conn.close()


def publish(catalog, store, job_id, calls):
    def callback(tx):
        calls.append("called")
        tx.execute("INSERT INTO independent_business (value) VALUES ('forbidden-late-publication')")
        tx.execute(f"UPDATE {store.table} SET checkpoint_json=? WHERE id=?", ('{"position":99}', job_id))
    return callback


def receipt(name, **values):
    print("RECEIPT=" + json.dumps({"name": name, **values}, ensure_ascii=False, default=str))


def lease_write(operation, catalog, store, lease, calls):
    if operation == "complete":
        return store.complete(lease.job_id, lease, result={"late": True},
                              publish=publish(catalog, store, lease.job_id, calls))
    if operation == "fail":
        return store.fail_if_current_lease(lease.job_id, lease, code="INDEPENDENT_FAILURE", message="probe")
    if operation == "cancel":
        return store.mark_cancelled(lease.job_id, lease)
    if operation == "heartbeat":
        return store.heartbeat(lease)
    raise AssertionError(operation)


@pytest.mark.parametrize("domain", ["teaching", "question", "knowledge"])
@pytest.mark.parametrize("second", [3, 4])
@pytest.mark.parametrize("cancellation", [False, True])
def test_unclaimed_expired_complete_is_zero_business_checkpoint_and_terminal(tmp_path, domain, second, cancellation):
    catalog, store, clock, job = fixture(tmp_path, domain)
    lease = store.claim(job.job_id)
    assert lease.expires_at == "2026-10-02T00:00:03Z"
    if cancellation:
        store.request_cancel(job.job_id)
    before = raw_row(catalog, store, job.job_id)
    calls = []
    clock.set(second)
    with pytest.raises(AppError) as caught:
        lease_write("complete", catalog, store, lease, calls)
    assert caught.value.code == "LEASE_LOST" and caught.value.status_code == 409
    assert raw_row(catalog, store, job.job_id) == before
    assert business(catalog) == [] and calls == []
    receipt("unclaimed-expiry", domain=domain, second=second, cancel=cancellation,
            state=before["state"], attempt=before["attempt"], checkpoint=before["checkpoint_json"],
            expiry=lease.expires_at, error=caught.value.code, business=[])


@pytest.mark.parametrize("operation", ["complete", "fail", "cancel", "heartbeat"])
@pytest.mark.parametrize("cancellation", [False, True])
def test_true_second_connection_write_lock_crosses_expiry(tmp_path, monkeypatch, operation, cancellation):
    catalog, store, clock, job = fixture(tmp_path)
    lease = store.claim(job.job_id)
    if cancellation:
        store.request_cancel(job.job_id)
    before = raw_row(catalog, store, job.job_id)
    clock.set(2)
    blocker = connect(catalog.db_path)
    blocker.execute("BEGIN IMMEDIATE")
    begin_attempted, finished = threading.Event(), threading.Event()
    opened = catalog._open

    def instrumented_open(*args, **kwargs):
        conn = opened(*args, **kwargs)
        conn.set_trace_callback(lambda sql: begin_attempted.set() if sql == "BEGIN IMMEDIATE" else None)
        return conn

    monkeypatch.setattr(catalog, "_open", instrumented_open)
    outcomes, calls = {}, []

    def waiting_writer():
        try:
            outcomes["result"] = lease_write(operation, catalog, store, lease, calls)
        except BaseException as exc:
            outcomes["error"] = exc
        finally:
            finished.set()

    worker = threading.Thread(target=waiting_writer, name="independent-waiting-writer")
    try:
        worker.start()
        assert begin_attempted.wait(3), "Writer must actually attempt BEGIN IMMEDIATE"
        assert not finished.wait(0.05), "Actual SQLite writer must wait for the other connection"
        assert [r for r in clock.reads if r[0] == worker.name] == [], "No lock-before-clock read is permitted"
        clock.set(4)
        blocker.execute("COMMIT")
        assert finished.wait(3)
        worker.join(3)
        assert not worker.is_alive()
        if operation == "complete":
            assert isinstance(outcomes.get("error"), AppError)
            assert outcomes["error"].code == "LEASE_LOST"
        else:
            assert "error" not in outcomes, outcomes
            if operation == "heartbeat":
                assert outcomes["result"] is False
        assert raw_row(catalog, store, job.job_id) == before
        assert business(catalog) == [] and calls == []
        assert [r[1] for r in clock.reads if r[0] == worker.name] == [4]
        receipt("sqlite-wait-expiry", operation=operation, cancel=cancellation,
                beforeSecond=2, afterSecond=4, expiry=lease.expires_at, rowUnchanged=True,
                callbackCalls=calls, workerClockReads=[r for r in clock.reads if r[0] == worker.name])
    finally:
        if blocker.in_transaction:
            blocker.execute("ROLLBACK")
        blocker.close()
        worker.join(3)


def test_claim_clock_is_after_the_write_lock_and_ttl_stays_three(tmp_path, monkeypatch):
    catalog, store, clock, job = fixture(tmp_path)
    old = store.claim(job.job_id)
    clock.set(2)
    blocker = connect(catalog.db_path)
    blocker.execute("BEGIN IMMEDIATE")
    begin_attempted = threading.Event()
    opened = catalog._open

    def instrumented_open(*args, **kwargs):
        conn = opened(*args, **kwargs)
        conn.set_trace_callback(lambda sql: begin_attempted.set() if sql == "BEGIN IMMEDIATE" else None)
        return conn

    monkeypatch.setattr(catalog, "_open", instrumented_open)
    outcome = {}

    def claim():
        try:
            outcome["lease"] = store.claim(job.job_id)
        except BaseException as exc:
            outcome["error"] = exc

    worker = threading.Thread(target=claim, name="independent-claim")
    try:
        worker.start()
        assert begin_attempted.wait(3)
        clock.set(4)
        blocker.execute("COMMIT")
        worker.join(3)
        assert not worker.is_alive()
        assert "error" not in outcome, outcome
        new = outcome["lease"]
        assert new.attempt == 2 and new.token != old.token
        assert new.expires_at == "2026-10-02T00:00:07Z"
        assert store.lease_seconds == 3
        receipt("claim-after-lock", oldAttempt=1, newAttempt=2, newExpiry=new.expires_at, ttl=store.lease_seconds)
    finally:
        if blocker.in_transaction:
            blocker.execute("ROLLBACK")
        blocker.close()
        worker.join(3)


@pytest.mark.asyncio
async def test_last_engine_read_gate_then_expiry_still_cannot_publish(tmp_path, monkeypatch):
    catalog, store, clock, job = fixture(tmp_path)
    calls = []
    actual = store.complete
    gate_crossed = []

    def expire_just_before_transaction(*args, **kwargs):
        current = raw_row(catalog, store, job.job_id)
        assert current["state"] == "running" and current["lease_expires_at"] == "2026-10-02T00:00:03Z"
        gate_crossed.append(True)
        clock.set(4)
        return actual(*args, **kwargs)

    monkeypatch.setattr(store, "complete", expire_just_before_transaction)
    engine = JobEngine({"teaching": store})

    async def executor(frozen, context):
        return JobOutcome(result={"never": "published"}, publish=publish(catalog, store, job.job_id, calls))

    result = await asyncio.wait_for(engine.run_job("teaching", job.job_id, executor), 3)
    after = raw_row(catalog, store, job.job_id)
    assert gate_crossed == [True]
    assert result.state == "running" and result.result is None and result.error is None
    assert after["checkpoint_json"] == '{"position":7,"fixed":"old"}'
    assert after["finished_at"] is None and after["lease_expires_at"] == "2026-10-02T00:00:03Z"
    assert after["attempt"] == 1 and after["error_code"] is None
    assert business(catalog) == [] and calls == []
    receipt("engine-read-then-expiry", state=result.state, attempt=result.attempt,
            result=result.result, error=result.error, checkpoint=result.checkpoint, business=[])


@pytest.mark.parametrize("operation", ["complete", "fail"])
def test_live_original_lease_honors_cancellation_priority(tmp_path, operation):
    catalog, store, clock, job = fixture(tmp_path)
    lease = store.claim(job.job_id)
    clock.set(2)
    store.request_cancel(job.job_id)
    calls = []
    result = lease_write(operation, catalog, store, lease, calls)
    assert result.state == "cancelled" and result.result is None and result.error is None
    assert result.attempt == 1 and result.checkpoint == {"position": 7, "fixed": "old"}
    assert business(catalog) == [] and calls == [] and result.lease_token is None
    receipt("live-cancel-wins", operation=operation, state=result.state, callbackCalls=calls)


@pytest.mark.parametrize("operation", ["complete", "fail", "cancel", "heartbeat"])
@pytest.mark.parametrize("wrong_identity", ["token", "attempt", "takeover"])
def test_original_identity_cas_prevents_any_old_worker_write(tmp_path, operation, wrong_identity):
    catalog, store, clock, job = fixture(tmp_path)
    old = store.claim(job.job_id)
    if wrong_identity == "token":
        stale = dataclasses.replace(old, token="other-worker")
    elif wrong_identity == "attempt":
        stale = dataclasses.replace(old, attempt=old.attempt + 1)
    else:
        clock.set(4)
        newer = store.claim(job.job_id)
        assert newer.attempt == 2 and newer.token != old.token
        stale = old
    before = raw_row(catalog, store, job.job_id)
    calls = []
    if operation == "complete":
        with pytest.raises(AppError) as caught:
            lease_write(operation, catalog, store, stale, calls)
        assert caught.value.code == "LEASE_LOST"
    else:
        result = lease_write(operation, catalog, store, stale, calls)
        if operation == "heartbeat":
            assert result is False
    assert raw_row(catalog, store, job.job_id) == before
    assert business(catalog) == [] and calls == []
    receipt("identity-cas", operation=operation, identity=wrong_identity, rowUnchanged=True, business=[])


class CleanupEngine(JobEngine):
    """Test-only heartbeat finalizer barrier, outside all production transactions."""
    def __init__(self, stores):
        super().__init__(stores)
        self.cleanup_entered = asyncio.Event()
        self.release_cleanup = asyncio.Event()
        self.barrier_used = False

    async def _heartbeat_loop(self, store, lease, interval):
        try:
            await super()._heartbeat_loop(store, lease, interval)
        finally:
            if lease.attempt == 1 and not self.barrier_used:
                self.barrier_used = True
                self.cleanup_entered.set()
                await self.release_cleanup.wait()


def asgi_app(engine, registry):
    app = FastAPI()
    app.state.settings = Settings(host="127.0.0.1", port=8001, allowed_origins=frozenset(),
                                  env="test", data_dir=Path(os.environ["ZQKY_DATA_DIR"]), credentials_file=None)
    app.state.job_engine, app.state.job_executors = engine, registry
    app.include_router(router, prefix="/api/v1")

    @app.exception_handler(AppError)
    async def error_handler(request, exc):
        return JSONResponse(status_code=exc.status_code,
                            content={"code": exc.code, "message": str(exc), "retryable": exc.retryable})
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("first_end", ["failed", "internal_error", "cancelled", "interrupted"])
@pytest.mark.parametrize("next_end", ["success", "failure", "cancel_before_start", "restart_before_start"])
async def test_real_asgi_retry_accepted_in_old_heartbeat_cleanup_runs_once(tmp_path, first_end, next_end):
    catalog, store, clock, job = fixture(tmp_path, ttl=90)
    engine = CleanupEngine({"teaching": store})
    registry = JobExecutorRegistry()
    second_started, release_second = asyncio.Event(), asyncio.Event()
    attempts = []
    provider_inputs = []

    async def executor(frozen, context):
        attempts.append(frozen.attempt)
        provider_inputs.append((frozen.input, frozen.model_snapshot, frozen.input_hash))
        if frozen.attempt == 1:
            if first_end == "failed":
                raise AppError("first expected error", code="INDEPENDENT_FIRST", status_code=503)
            if first_end == "internal_error":
                raise ValueError("private internal exception must not escape into job data")
            if first_end == "cancelled":
                store.request_cancel(job.job_id)
            else:
                store.reconcile_interrupted()
            return JobOutcome(result={"first": "must-not-publish"})
        second_started.set()
        await release_second.wait()
        if next_end == "failure":
            raise AppError("second expected error", code="INDEPENDENT_SECOND", status_code=503)
        return JobOutcome(result={"done": frozen.attempt}, publish=lambda tx: tx.execute(
            "INSERT INTO independent_business (value) VALUES ('published-attempt-two')"))

    registry.register("teaching", "export", uses_model=False, factory=lambda record: executor)
    app = asgi_app(engine, registry)
    key = ("teaching", job.job_id)
    first = engine.schedule("teaching", job.job_id, executor)
    try:
        await asyncio.wait_for(engine.cleanup_entered.wait(), 3)
        expected_first = "failed" if first_end in ("failed", "internal_error") else first_end
        assert store.get(job.job_id).state == expected_first
        assert not first.done() and engine.is_tracking(*key)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8001") as client:
            responses = await asyncio.gather(*[
                client.post(f"/api/v1/workflow-jobs/{job.job_id}/retry", json={"domain": "teaching"})
                for _ in range(3)
            ])
            assert [r.status_code for r in responses] == [200, 200, 200]
            receipts = [r.json() for r in responses]
            assert all(r["state"] == "queued" and r["attempt"] == 1 for r in receipts)
            accepted = engine._tracked[key]
            assert accepted is not first and not accepted.done()
            assert attempts == [1]
            if next_end == "cancel_before_start":
                response = await client.post(f"/api/v1/workflow-jobs/{job.job_id}/cancel", json={"domain": "teaching"})
                assert response.status_code == 200 and response.json()["state"] == "cancelled"
            if next_end == "restart_before_start":
                await engine.shutdown()
                assert first.done() and accepted.done() and engine.active_jobs == 0
                replacement = JobEngine({"teaching": store})
                assert replacement.reconcile_all() == {"teaching": []}
                assert store.get(job.job_id).state == "queued" and attempts == [1]
                replacement_app = asgi_app(replacement, registry)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=replacement_app), base_url="http://127.0.0.1:8001") as resumed:
                    response = await resumed.post(f"/api/v1/workflow-jobs/{job.job_id}/retry", json={"domain": "teaching"})
                    assert response.status_code == 200
                accepted = replacement._tracked[key]
                release_second.set()
                await asyncio.wait_for(accepted, 3)
                await replacement.shutdown()
            else:
                engine.release_cleanup.set()
                await asyncio.wait_for(first, 3)
                if next_end != "cancel_before_start":
                    await asyncio.wait_for(second_started.wait(), 3)
                    assert engine.is_tracking(*key) and engine._tracked[key] is accepted
                    # Old callback has had an actual scheduling turn while new executor is blocked.
                    await asyncio.sleep(0)
                    assert engine._tracked[key] is accepted
                release_second.set()
                await asyncio.wait_for(accepted, 3)
        final = store.get(job.job_id)
        expected_state = {"success": "succeeded", "failure": "failed", "cancel_before_start": "cancelled", "restart_before_start": "succeeded"}[next_end]
        assert final.state == expected_state
        assert attempts == ([1] if next_end == "cancel_before_start" else [1, 2])
        assert final.attempt == (1 if next_end == "cancel_before_start" else 2)
        assert final.frozen_input == job.frozen_input and final.model_snapshot == job.model_snapshot
        assert final.input_hash == job.input_hash
        assert all(values == provider_inputs[0] for values in provider_inputs)
        assert final.checkpoint == {"position": 7, "fixed": "old"}
        assert len(business(catalog)) == (1 if expected_state == "succeeded" else 0)
        if next_end == "failure":
            assert final.error_code == "INDEPENDENT_SECOND"
        receipt("asgi-retry-cleanup", firstEnd=first_end, nextEnd=next_end,
                httpReceipts=receipts, attempts=attempts, finalState=final.state,
                finalAttempt=final.attempt, business=business(catalog), frozenInputUnchanged=True)
    finally:
        engine.release_cleanup.set()
        release_second.set()
        await engine.shutdown()
