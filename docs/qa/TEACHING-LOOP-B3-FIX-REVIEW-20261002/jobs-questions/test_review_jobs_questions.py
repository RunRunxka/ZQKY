"""Independent review probes; expected product behavior, only isolated databases."""
from __future__ import annotations

import asyncio
import copy
import json
import os
import tempfile
import threading
from pathlib import Path

# Must precede any indirect app.main import. No production credentials/lifespan.
os.environ["ZQKY_DATA_DIR"] = tempfile.mkdtemp(prefix="zqky-b3fix-review-jq-bootstrap-")
os.environ["ZQKY_ENV"] = "test"
os.environ["PYTHONUTF8"] = "1"

import pytest
import httpx
from fastapi import FastAPI

from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.services.jobs.engine import JobEngine, JobOutcome
from app.services.jobs.registry import JobExecutorRegistry
from app.api.v1.workflow_jobs import router as workflow_router
from tests.test_jobs_engine import _teaching_store, _create_probe, _probe_rows
from tests.test_question_bank import open_harness
from tests.test_question_bank_confirm import confirm, set_content_and_review
from tests.test_question_rich_content import upload_one, rich_content


def output(label, value):
    print(label + "=" + json.dumps(value, ensure_ascii=False, default=str))


def test_expired_lease_cannot_publish_even_without_a_takeover(tmp_path):
    catalog, store, clock = _teaching_store(tmp_path, lease_seconds=3)
    _create_probe(catalog)
    job = store.create(kind="export")
    lease = store.claim(job.job_id)
    clock.advance(4)
    assert store.execution_allowed(lease) is False
    try:
        result = store.complete(job.job_id, lease, result={"late": True},
                                publish=lambda tx: tx.execute("INSERT INTO publish_probe VALUES ('late')"))
    except AppError as exc:
        output("expired_complete", {"code": exc.code, "rows": _probe_rows(catalog)})
        assert exc.code == "LEASE_LOST"
    else:
        output("expired_complete", {"state": result.state, "rows": _probe_rows(catalog),
                                     "expiresAt": lease.expires_at, "now": clock.now()})
        assert result.state != "succeeded", "Expired worker published with matching token/attempt"
    assert _probe_rows(catalog) == []


def test_engine_last_read_gate_does_not_replace_publication_expiry_cas(tmp_path, monkeypatch):
    catalog, store, clock = _teaching_store(tmp_path, lease_seconds=3)
    _create_probe(catalog)
    engine = JobEngine({"teaching": store})
    job = store.create(kind="export")
    actual = store.complete

    def expire_after_last_read(*args, **kwargs):
        clock.advance(4)
        return actual(*args, **kwargs)

    monkeypatch.setattr(store, "complete", expire_after_last_read)

    async def executor(frozen, ctx):
        return JobOutcome(result={"late": True}, publish=lambda tx: tx.execute(
            "INSERT INTO publish_probe VALUES ('engine-late')"))

    result = asyncio.run(engine.run_job("teaching", job.job_id, executor))
    output("engine_boundary", {"state": result.state, "rows": _probe_rows(catalog), "now": clock.now()})
    assert result.state != "succeeded", "Lease expiry after read gate must be caught in commit transaction"
    assert _probe_rows(catalog) == []


def test_failure_cas_rechecks_time_after_real_sqlite_lock_wait(tmp_path):
    catalog, store, clock = _teaching_store(tmp_path, lease_seconds=3)
    job = store.create(kind="export")
    lease = store.claim(job.job_id)
    clock.advance(2)
    entered = threading.Event()
    actual_now = clock.now
    outcomes = {}

    def captured_now():
        value = actual_now()
        entered.set()
        return value

    store._now = captured_now
    blocker = connect(catalog.db_path)
    blocker.execute("BEGIN IMMEDIATE")

    def late_failure():
        try:
            outcomes["result"] = store.fail_if_current_lease(job.job_id, lease, code="PROBE", message="late failure")
        except BaseException as exc:
            outcomes["error"] = exc

    thread = threading.Thread(target=late_failure)
    try:
        thread.start()
        assert entered.wait(3)
        clock.advance(2)
        blocker.execute("COMMIT")
        thread.join(3)
        assert not thread.is_alive()
        assert "error" not in outcomes, outcomes
        result = outcomes["result"]
        output("late_failure_lock_wait", {"state": result.state, "finishedAt": result.finished_at,
                                            "expiresAt": lease.expires_at, "now": clock.now()})
        assert result.state == "running", "Failure CAS used timestamp captured before SQLite lock wait"
        assert store.get(job.job_id).lease_token == lease.token
    finally:
        if blocker.in_transaction:
            blocker.execute("ROLLBACK")
        blocker.close()
        thread.join(3)


def test_distinct_shared_material_is_not_silently_skipped_as_a_duplicate(tmp_path):
    harness = open_harness(tmp_path)
    try:
        first_import, first_draft = upload_one(harness)
        first_content = rich_content(harness, first_import, first_draft)
        first_content["richContent"]["sharedMaterials"][0]["blocks"][0]["text"] = "共同材料：实验溶液浓度为 1 mol/L。"
        first_draft = set_content_and_review(harness, first_import, 0, first_content)
        first = confirm(harness, first_import, [{"draftId": first_draft["draftId"], "expectedDraftRevision": first_draft["revision"]}], submission_id="jq-first")
        assert first.status_code == 200 and len(first.json()["confirmedQuestionIds"]) == 1

        second_import, second_draft = upload_one(harness)
        second_content = rich_content(harness, second_import, second_draft)
        second_content["richContent"]["sharedMaterials"][0]["blocks"][0]["text"] = "共同材料：实验溶液浓度为 2 mol/L。"
        second_draft = set_content_and_review(harness, second_import, 0, second_content)
        assert first_content["stemMarkdown"] == second_content["stemMarkdown"]
        assert harness.service._derived_fingerprint(first_content) != harness.service._derived_fingerprint(second_content)
        request_items = [{"draftId": second_draft["draftId"], "expectedDraftRevision": second_draft["revision"]}]
        response = confirm(harness, second_import, request_items, submission_id="jq-second")
        explicit = confirm(harness, second_import, request_items, submission_id="jq-explicit", resolutions=[{
            "draftId": second_draft["draftId"], "action": "edit_as_new",
        }])
        output("shared_material_duplicate", {"default": response.json(), "editAsNew": explicit.json(),
                                              "questionCount": harness.service.list_questions().total})
        assert response.status_code == 200
        assert len(response.json()["confirmedQuestionIds"]) == 1, "Different authoritative material was silently discarded by legacy fingerprint"
        assert response.json()["skippedDraftIds"] == []
    finally:
        harness.close()


@pytest.mark.asyncio
async def test_retry_while_previous_attempt_settles_is_actually_scheduled(tmp_path, monkeypatch):
    catalog, store, clock = _teaching_store(tmp_path)
    engine = JobEngine({"teaching": store})
    registry = JobExecutorRegistry()
    calls = []
    entered, release = asyncio.Event(), asyncio.Event()
    actual_settle = engine._settle

    async def delayed_heartbeat_cleanup(task):
        if not task.done():
            entered.set()
            await release.wait()
        await actual_settle(task)

    monkeypatch.setattr(engine, "_settle", delayed_heartbeat_cleanup)

    async def executor(frozen, ctx):
        calls.append(frozen.attempt)
        if frozen.attempt == 1:
            raise AppError("first attempt failed", code="PROBE_FAILURE", status_code=503)
        return JobOutcome(result={"retryExecuted": True})

    registry.register("teaching", "export", uses_model=False, factory=lambda record: executor)
    job = store.create(kind="export")
    task = engine.schedule("teaching", job.job_id, executor)
    try:
        await asyncio.wait_for(entered.wait(), timeout=3)
        assert store.get(job.job_id).state == "failed"
        assert engine.is_tracking("teaching", job.job_id)
        app = FastAPI()
        app.state.job_engine, app.state.job_executors = engine, registry
        app.include_router(workflow_router, prefix="/api/v1")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8001") as client:
            response = await client.post(f"/api/v1/workflow-jobs/{job.job_id}/retry", json={"domain": "teaching"})
        assert response.status_code == 200, response.text
        receipt = response.json()
        assert receipt["state"] == "queued"
        release.set()
        await asyncio.wait_for(task, timeout=3)
        await asyncio.sleep(0)
        final = store.get(job.job_id)
        output("retry_during_cleanup", {"httpStatus": response.status_code, "receipt": receipt,
                                         "finalState": final.state, "attempt": final.attempt,
                                         "calls": calls, "tracking": engine.is_tracking("teaching", job.job_id)})
        assert final.state == "succeeded", "Retry was acknowledged queued but old cleanup consumed its scheduling"
        assert calls == [1, 2]
    finally:
        release.set()
        await engine.shutdown()
