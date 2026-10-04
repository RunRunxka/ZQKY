"""G1 correct behavior: lock-time expiry and retry accepted during old cleanup."""
from __future__ import annotations

import asyncio
import os
import tempfile
import threading
from contextlib import contextmanager

if not os.environ.get('ZQKY_DATA_DIR'):
    os.environ['ZQKY_DATA_DIR'] = tempfile.mkdtemp(prefix='zqky-g1-jobs-bootstrap-')
os.environ['ZQKY_ENV'] = 'test'

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1.workflow_jobs import router
from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.services.jobs.engine import JobEngine, JobOutcome
from app.services.jobs.registry import JobExecutorRegistry
from tests.test_jobs_engine import _create_probe, _probe_rows, _teaching_store


@pytest.mark.parametrize('elapsed', [3, 4])
def test_expired_complete_is_zero_write_without_takeover(tmp_path, elapsed):
    catalog, store, clock = _teaching_store(tmp_path, lease_seconds=3)
    _create_probe(catalog)
    job = store.create(kind='export')
    lease = store.claim(job.job_id)
    before = store.get(job.job_id)
    clock.advance(elapsed)
    with pytest.raises(AppError) as failure:
        store.complete(job.job_id, lease, result={'late': True},
                       publish=lambda tx: tx.execute("INSERT INTO publish_probe VALUES ('late')"))
    assert failure.value.code == 'LEASE_LOST'
    assert store.get(job.job_id) == before
    assert _probe_rows(catalog) == []


@pytest.mark.parametrize('operation', ['complete', 'fail', 'cancel', 'heartbeat'])
def test_all_lease_writes_sample_clock_after_real_sqlite_write_lock(tmp_path, monkeypatch, operation):
    catalog, store, clock = _teaching_store(tmp_path, lease_seconds=3)
    _create_probe(catalog)
    job = store.create(kind='export')
    lease = store.claim(job.job_id)
    if operation == 'cancel':
        store.request_cancel(job.job_id)
    before = store.get(job.job_id)
    clock.advance(2)
    admission = threading.Event()
    actual_transaction = catalog.write_transaction

    @contextmanager
    def announce_write_admission():
        admission.set()  # Before BEGIN IMMEDIATE; not a clock read inside the lock.
        with actual_transaction() as tx:
            yield tx

    monkeypatch.setattr(catalog, 'write_transaction', announce_write_admission)
    blocker = connect(catalog.db_path)
    blocker.execute('BEGIN IMMEDIATE')
    result = {}

    def write_after_wait():
        try:
            if operation == 'complete':
                result['record'] = store.complete(job.job_id, lease, result={'late': True},
                    publish=lambda tx: tx.execute("INSERT INTO publish_probe VALUES ('late')"))
            elif operation == 'fail':
                result['record'] = store.fail_if_current_lease(job.job_id, lease, code='LATE', message='late')
            elif operation == 'cancel':
                result['record'] = store.mark_cancelled(job.job_id, lease)
            else:
                result['alive'] = store.heartbeat(lease)
        except BaseException as exc:
            result['error'] = exc

    thread = threading.Thread(target=write_after_wait)
    try:
        thread.start()
        assert admission.wait(3)
        clock.advance(2)
        blocker.execute('COMMIT')
        thread.join(3)
        assert not thread.is_alive()
        if operation == 'complete':
            assert isinstance(result.get('error'), AppError)
            assert result['error'].code == 'LEASE_LOST'
        else:
            assert 'error' not in result, result
        if operation == 'heartbeat':
            assert result['alive'] is False
        assert store.get(job.job_id) == before
        assert _probe_rows(catalog) == []
    finally:
        if blocker.in_transaction:
            blocker.execute('ROLLBACK')
        blocker.close()
        thread.join(3)


def test_engine_final_read_gate_is_not_the_publication_guard(tmp_path, monkeypatch):
    catalog, store, clock = _teaching_store(tmp_path, lease_seconds=3)
    _create_probe(catalog)
    engine = JobEngine({'teaching': store})
    job = store.create(kind='export')
    actual_complete = store.complete

    def cross_expiry_after_read(*args, **kwargs):
        clock.advance(4)
        return actual_complete(*args, **kwargs)

    monkeypatch.setattr(store, 'complete', cross_expiry_after_read)

    async def executor(frozen, context):
        return JobOutcome(result={'late': True}, publish=lambda tx: tx.execute(
            "INSERT INTO publish_probe VALUES ('late')"))

    record = asyncio.run(engine.run_job('teaching', job.job_id, executor))
    assert record.state == 'running'  # No expired worker may write a terminal either.
    assert record.result is None and record.error is None
    assert _probe_rows(catalog) == []


def test_live_cancellation_wins_without_publishing(tmp_path):
    catalog, store, clock = _teaching_store(tmp_path, lease_seconds=3)
    _create_probe(catalog)
    job = store.create(kind='export')
    lease = store.claim(job.job_id)
    clock.advance(2)
    store.request_cancel(job.job_id)
    record = store.complete(job.job_id, lease, result={'ignored': True},
        publish=lambda tx: tx.execute("INSERT INTO publish_probe VALUES ('wrong')"))
    assert record.state == 'cancelled'
    assert _probe_rows(catalog) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('old_terminal', ['failed', 'cancelled', 'interrupted'])
@pytest.mark.parametrize('cancel_pending_retry', [False, True])
async def test_real_asgi_retry_during_old_cleanup_is_once_or_explicitly_cancelled(
    tmp_path, monkeypatch, old_terminal, cancel_pending_retry,
):
    _, store, _ = _teaching_store(tmp_path)
    engine = JobEngine({'teaching': store})
    registry = JobExecutorRegistry()
    cleanup_entered, release_cleanup = asyncio.Event(), asyncio.Event()
    second_entered, finish_second = asyncio.Event(), asyncio.Event()
    calls = []
    actual_settle = engine._settle

    async def cleanup_barrier(task):
        coroutine = getattr(task, 'get_coro', lambda: None)()
        heartbeat = getattr(coroutine, '__qualname__', '').endswith('_heartbeat_loop')
        if heartbeat and not task.done() and not release_cleanup.is_set():
            cleanup_entered.set()
            try:
                await release_cleanup.wait()
            finally:
                await actual_settle(task)
        else:
            await actual_settle(task)

    monkeypatch.setattr(engine, '_settle', cleanup_barrier)

    async def executor(frozen, context):
        calls.append(frozen.attempt)
        if frozen.attempt == 1:
            if old_terminal == 'cancelled':
                store.request_cancel(frozen.job_id)
                return JobOutcome(result={'ignored': True})
            if old_terminal == 'interrupted':
                store.reconcile_interrupted()
                return JobOutcome(result={'ignored': True})
            raise AppError('first failure', code='EXPECTED', status_code=503)
        second_entered.set()
        await finish_second.wait()
        return JobOutcome(result={'done': True})

    registry.register('teaching', 'export', uses_model=False, factory=lambda record: executor)
    job = store.create(kind='export', frozen_input={'selection': ['fixed']})
    first = engine.schedule('teaching', job.job_id, executor)
    app = FastAPI()
    app.state.job_engine, app.state.job_executors = engine, registry
    app.include_router(router, prefix='/api/v1')
    try:
        await asyncio.wait_for(cleanup_entered.wait(), 3)
        assert store.get(job.job_id).state == old_terminal
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8001') as client:
            receipts = await asyncio.gather(*[
                client.post(f'/api/v1/workflow-jobs/{job.job_id}/retry', json={'domain': 'teaching'})
                for _ in range(2)
            ])
        assert [response.status_code for response in receipts] == [200, 200]
        assert all(response.json()['state'] == 'queued' and response.json()['attempt'] == 1 for response in receipts)
        second = engine._tracked[('teaching', job.job_id)]
        assert second is not first
        if cancel_pending_retry:
            store.request_cancel(job.job_id)
        release_cleanup.set()
        await asyncio.wait_for(first, 3)
        if not cancel_pending_retry:
            await asyncio.wait_for(second_entered.wait(), 3)
            assert engine.is_tracking('teaching', job.job_id)
            assert engine._tracked[('teaching', job.job_id)] is second
        finish_second.set()
        await asyncio.wait_for(second, 3)
        final = store.get(job.job_id)
        assert calls == ([1] if cancel_pending_retry else [1, 2])
        assert final.state == ('cancelled' if cancel_pending_retry else 'succeeded')
        assert final.attempt == (1 if cancel_pending_retry else 2)
        assert final.frozen_input == job.frozen_input and final.input_hash == job.input_hash
    finally:
        release_cleanup.set()
        finish_second.set()
        await engine.shutdown()
