"""Read-only G1 review probes; temporary SQLite, ASGI without listener."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

assert os.environ.get("ZQKY_ENV") == "test"
assert os.environ.get("ZQKY_DATA_DIR")

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1.workflow_jobs import router
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.repositories.jobs.repository import JobStore
from app.repositories.teaching.catalog import TeachingCatalog
from app.services.jobs.engine import JobEngine, JobOutcome
from app.services.jobs.registry import JobExecutorRegistry


class CleanupEngine(JobEngine):
    def __init__(self, stores):
        super().__init__(stores)
        self.entered = {i: asyncio.Event() for i in (1, 2)}
        self.release = {i: asyncio.Event() for i in (1, 2)}

    async def _heartbeat_loop(self, store, lease, interval):
        try:
            await super()._heartbeat_loop(store, lease, interval)
        finally:
            if lease.attempt in self.entered:
                self.entered[lease.attempt].set()
                await self.release[lease.attempt].wait()


def fixture(path):
    catalog = TeachingCatalog(path / "teaching.sqlite3")
    catalog.migrate()
    store = JobStore(catalog, domain="teaching", table="workflow_jobs", kinds={"export"})
    with catalog.write_transaction() as tx:
        tx.execute("CREATE TABLE review_publish (attempt INTEGER PRIMARY KEY)")
    engine = CleanupEngine({"teaching": store})
    registry = JobExecutorRegistry()
    app = FastAPI()
    app.state.settings = Settings(host="127.0.0.1", port=8001, env="test", allowed_origins=frozenset(),
        data_dir=Path(os.environ["ZQKY_DATA_DIR"]), credentials_file=None)
    app.state.job_engine, app.state.job_executors = engine, registry
    app.include_router(router, prefix="/api/v1")

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code})

    job = store.create(kind="export", frozen_input={"selected": ["frozen"]},
        model_snapshot={"model": "frozen-v1"})
    return catalog, store, engine, registry, app, job


def publishes(catalog):
    conn = connect(catalog.db_path)
    try:
        return [row[0] for row in conn.execute("SELECT attempt FROM review_publish ORDER BY attempt")]
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_cancel_pending_then_retry_again_runs_the_accepted_attempt_once(tmp_path):
    catalog, store, engine, registry, app, job = fixture(tmp_path)
    attempts = []

    async def executor(frozen, context):
        attempts.append(frozen.attempt)
        assert frozen.input == {"selected": ["frozen"]}
        if frozen.attempt == 1:
            raise AppError("expected", code="FIRST", status_code=503)
        return JobOutcome(result={"attempt": frozen.attempt}, publish=lambda tx:
            tx.execute("INSERT INTO review_publish VALUES (?)", (frozen.attempt,)))

    registry.register("teaching", "export", uses_model=False, factory=lambda record: executor)
    first = engine.schedule("teaching", job.job_id, executor)
    retry_url = f"/api/v1/workflow-jobs/{job.job_id}/retry"
    try:
        await asyncio.wait_for(engine.entered[1].wait(), 3)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8001") as client:
            first_retry = await client.post(retry_url, json={"domain": "teaching"})
            assert first_retry.status_code == 200
            pending = engine._tracked[("teaching", job.job_id)]
            cancellation = await client.post(f"/api/v1/workflow-jobs/{job.job_id}/cancel", json={"domain": "teaching"})
            assert cancellation.status_code == 200 and cancellation.json()["state"] == "cancelled"
            responses = await asyncio.gather(*[client.post(retry_url, json={"domain": "teaching"}) for _ in range(3)])
            assert all(r.status_code == 200 and r.json()["state"] == "queued" for r in responses)
            assert engine._tracked[("teaching", job.job_id)] is pending
        engine.release[1].set()
        engine.release[2].set()
        await asyncio.wait_for(first, 3)
        await asyncio.wait_for(pending, 3)
        final = store.get(job.job_id)
        assert final.state == "succeeded" and final.attempt == 2
        assert attempts == [1, 2] and publishes(catalog) == [2]
        assert final.input_hash == job.input_hash and final.model_snapshot == job.model_snapshot
    finally:
        for barrier in engine.release.values():
            barrier.set()
        await engine.shutdown()


@pytest.mark.asyncio
async def test_two_consecutive_terminal_cleanup_retries_keep_tracking_and_publish_once(tmp_path):
    catalog, store, engine, registry, app, job = fixture(tmp_path)
    attempts = []
    third_started, finish_third = asyncio.Event(), asyncio.Event()

    async def executor(frozen, context):
        attempts.append(frozen.attempt)
        if frozen.attempt < 3:
            raise AppError("expected", code=f"FAIL_{frozen.attempt}", status_code=503)
        third_started.set()
        await finish_third.wait()
        return JobOutcome(result={"attempt": frozen.attempt}, publish=lambda tx:
            tx.execute("INSERT INTO review_publish VALUES (?)", (frozen.attempt,)))

    registry.register("teaching", "export", uses_model=False, factory=lambda record: executor)
    first = engine.schedule("teaching", job.job_id, executor)
    key = ("teaching", job.job_id)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8001") as client:
            await asyncio.wait_for(engine.entered[1].wait(), 3)
            response = await client.post(f"/api/v1/workflow-jobs/{job.job_id}/retry", json={"domain": "teaching"})
            assert response.status_code == 200 and response.json()["attempt"] == 1
            second = engine._tracked[key]
            engine.release[1].set()
            await asyncio.wait_for(first, 3)
            await asyncio.wait_for(engine.entered[2].wait(), 3)
            assert store.get(job.job_id).state == "failed" and store.get(job.job_id).attempt == 2
            responses = await asyncio.gather(*[client.post(f"/api/v1/workflow-jobs/{job.job_id}/retry", json={"domain": "teaching"}) for _ in range(3)])
            assert all(r.status_code == 200 and r.json()["attempt"] == 2 for r in responses)
            third = engine._tracked[key]
            assert third is not second
            engine.release[2].set()
            await asyncio.wait_for(second, 3)
            await asyncio.wait_for(third_started.wait(), 3)
            await asyncio.sleep(0)
            assert engine._tracked[key] is third and engine.is_tracking(*key)
            finish_third.set()
            await asyncio.wait_for(third, 3)
        final = store.get(job.job_id)
        assert final.state == "succeeded" and final.attempt == 3
        assert attempts == [1, 2, 3] and publishes(catalog) == [3]
        assert final.input_hash == job.input_hash and final.model_snapshot == job.model_snapshot
    finally:
        for barrier in engine.release.values():
            barrier.set()
        finish_third.set()
        await engine.shutdown()
