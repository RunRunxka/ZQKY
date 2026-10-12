import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
import pytest
from app.services.jobs.engine import FrozenJob, JobContext
from app.services.jobs.registry import JobExecutorRegistry
from app.core.exceptions import AppError
from tests.analysis_support import AnalysisScene


async def test_publish_fault_rolls_back_all_results_and_public_retry(tmp_path, monkeypatch):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    original = scene.service.repo.publish_in
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected after ready transition")
    monkeypatch.setattr(scene.service.repo, "publish_in", fail)
    job = await scene.engine.run_job("teaching", receipt.job.job_id, scene.service.execute_job)
    assert job.state == "failed" and job.error["code"] == "JOB_FAILED"
    assert not scene.service.get_run(receipt.run_id).report_ready
    for table in ("analysis_participants", "analysis_item_snapshots", "analysis_student_results", "analysis_class_results", "analysis_evidence"):
        assert scene.count(table) == 0
    monkeypatch.undo()
    registry = JobExecutorRegistry()
    scene.service.register_job_executors(registry)
    spec = registry.spec_for("teaching", "analysis")
    assert spec is not None and not spec.uses_model
    retried = scene.store.retry(job.job_id)
    assert registry.schedule(scene.engine, retried)
    current = await scene.engine.run_job("teaching", job.job_id, scene.service.execute_job)
    assert current.state == "succeeded" and current.attempt == 2
    assert scene.count("analysis_runs") == 1 and scene.count("analysis_evidence") == 12


async def test_cancel_running_never_publishes_late_executor(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    entered, release = asyncio.Event(), asyncio.Event()
    async def delayed(frozen, context):
        outcome = await scene.service.execute_job(frozen, context)
        entered.set()
        await release.wait()
        return outcome
    task = asyncio.create_task(scene.engine.run_job("teaching", receipt.job.job_id, delayed))
    await entered.wait()
    scene.store.request_cancel(receipt.job.job_id)
    release.set()
    job = await task
    assert job.state == "cancelled" and not scene.service.get_run(receipt.run_id).report_ready
    assert scene.count("analysis_evidence") == scene.count("analysis_participants") == 0
    scene.store.retry(job.job_id)
    job = await scene.engine.run_job("teaching", job.job_id, scene.service.execute_job)
    assert job.state == "succeeded" and job.attempt == 2


async def test_old_lease_and_expired_lease_cannot_write_ready(tmp_path):
    clock = [datetime(2026, 10, 2, tzinfo=UTC)]
    scene = AnalysisScene(tmp_path, now=lambda: clock[0].isoformat().replace("+00:00", "Z"))
    receipt = await scene.accept()
    lease1 = scene.store.claim(receipt.job.job_id)
    record = scene.store.get(receipt.job.job_id)
    frozen = FrozenJob(record.job_id, record.domain, record.kind, record.attempt, record.frozen_input, record.model_snapshot, record.input_hash)
    outcome = await scene.service.execute_job(frozen, JobContext(scene.store, record.job_id, lease1))
    clock[0] += timedelta(seconds=91)
    with pytest.raises(AppError) as expired:
        scene.store.complete(record.job_id, lease1, result=outcome.result, publish=outcome.publish)
    assert expired.value.code == "LEASE_LOST" and not scene.service.get_run(receipt.run_id).report_ready
    scene.store.reconcile_interrupted()
    scene.store.retry(record.job_id)
    lease2 = scene.store.claim(record.job_id)
    assert lease2.attempt == 2
    with pytest.raises(AppError) as stale:
        scene.store.complete(record.job_id, lease1, result=outcome.result, publish=outcome.publish)
    assert stale.value.code == "LEASE_LOST" and scene.store.get(record.job_id).attempt == 2 and scene.count("analysis_evidence") == 0
    scene.store.complete(record.job_id, lease2, result=outcome.result, publish=outcome.publish)
    assert scene.service.get_run(receipt.run_id).report_ready and scene.store.get(record.job_id).state == "succeeded"


async def test_pending_inputs_and_incomplete_ready_transition_rejected(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    for sql in ("UPDATE analysis_runs SET input_json='{}'", "UPDATE analysis_runs SET job_id='else'", "UPDATE analysis_runs SET selected_count=5"):
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
            with scene.catalog.write_transaction() as conn:
                conn.execute(sql)
    with pytest.raises(sqlite3.IntegrityError, match="ANALYSIS_PARTICIPANTS_INCOMPLETE"):
        with scene.catalog.write_transaction() as conn:
            conn.execute("UPDATE analysis_runs SET report_ready=1,ready_at='2026-10-02' WHERE id=?", (receipt.run_id,))
    assert not scene.service.get_run(receipt.run_id).report_ready
