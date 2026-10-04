"""B3 R09/R10 正确行为回归；真实临时库/JobEngine，模型仅为替身。"""
from __future__ import annotations


def test_expired_heartbeat_cannot_reauthorize_old_batch(tmp_path):
    from tests.test_question_lease_batches import LeaseFixture

    fixture = LeaseFixture(tmp_path)
    job = fixture.job()
    lease = fixture.store.claim(job.job_id)
    fixture.clock.advance(31)
    before = fixture.store.get(job.job_id)
    assert fixture.store.heartbeat(lease) is False
    assert fixture.store.get(job.job_id) == before
    _current, created, _notice = fixture.batch(job.job_id, lease=fixture.lease_of(lease))
    assert created is None
    fixture.assert_zero_write(job.job_id)

import asyncio

import pytest

from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.services.jobs.engine import JobOutcome
from app.services.model_runtime import fingerprint_of_handle
from tests.test_model_drift_guards import _organize_contract
from tests.test_question_bank import LOCAL_PROFILE, FakeLLMProvider
from tests.test_question_generation import GenerationHarness, _generation_request, generation_reply


def expire(harness, job_id):
    conn = connect(harness.catalog.db_path)
    try:
        conn.execute(
            "UPDATE question_jobs SET lease_expires_at='2000-01-01T00:00:00Z' WHERE id=?",
            (job_id,),
        )
    finally:
        conn.close()


def test_late_failure_preserves_new_attempt_checkpoint(tmp_path, monkeypatch):
    harness = GenerationHarness(tmp_path)
    try:
        detail = harness.sample_detail()
        draft = harness.catalog.get_draft(detail['drafts'][0]['draftId'])
        provider = FakeLLMProvider(replies=[AppError(
            'upstream unavailable', code='UPSTREAM_UNAVAILABLE', status_code=503
        )])
        handle = harness.handle(LOCAL_PROFILE, provider=provider)
        store = harness.service.job_engine.store('question')
        job = store.create(
            kind='organize',
            frozen_input=_organize_contract(draft, fingerprint=fingerprint_of_handle(handle)),
            model_snapshot={'profileId': LOCAL_PROFILE, 'fingerprint': fingerprint_of_handle(handle)},
        )
        real_record = harness.catalog.record_organize_failure
        takeover = {}

        def before_old_failure_write(job_id, **kwargs):
            expire(harness, job_id)
            fresh = store.claim(job_id)
            current, created, failure = harness.catalog.record_organize_batch(
                job_id, batch_index=0, next_batch_index=1,
                draft_id=draft.draft_id, base_draft_revision=draft.revision,
                proposed_content=dict(draft.content),
                lease_attempt=fresh.attempt, lease_token=fresh.token,
            )
            assert created is not None and failure is None
            takeover.update(token=fresh.token, checkpoint=current.checkpoint)
            return real_record(job_id, **kwargs)

        monkeypatch.setattr(harness.catalog, 'record_organize_failure', before_old_failure_write)
        result = asyncio.run(harness.service.job_engine.run_job(
            'question', job.job_id,
            harness.service._organize_executor_factory(model=handle), uses_model=True,
        ))
        live = store.get(job.job_id)
        assert result.state == live.state == 'running'
        assert live.attempt == 2 and live.lease_token == takeover['token']
        assert live.checkpoint == takeover['checkpoint']
        assert live.checkpoint['nextBatchIndex'] == 1
        assert len(live.checkpoint['suggestionIds']) == 1
        assert 'jobError' not in live.checkpoint
        assert len(harness.catalog.list_suggestions(organization_job_id=job.job_id)) == 1
    finally:
        harness.close()


@pytest.mark.parametrize('loss', ['expired', 'cancelled', 'interrupted', 'failed', 'succeeded', 'cancel_requested'])
def test_failure_checkpoint_is_zero_write_after_loss(tmp_path, loss):
    harness = GenerationHarness(tmp_path)
    try:
        store = harness.service.job_engine.store('question')
        job = store.create(kind='organize', frozen_input={'original': True})
        lease = store.claim(job.job_id)
        if loss == 'expired':
            expire(harness, job.job_id)
        elif loss == 'cancel_requested':
            store.request_cancel(job.job_id)
        else:
            conn = connect(harness.catalog.db_path)
            try:
                conn.execute('UPDATE question_jobs SET state=? WHERE id=?', (loss, job.job_id))
            finally:
                conn.close()
        before = store.get(job.job_id)
        harness.catalog.record_organize_failure(
            job.job_id, code='UPSTREAM_UNAVAILABLE', message='late error',
            lease_attempt=lease.attempt, lease_token=lease.token,
        )
        assert store.get(job.job_id) == before
    finally:
        harness.close()


def test_current_model_failure_keeps_readable_reason(tmp_path):
    harness = GenerationHarness(tmp_path)
    try:
        detail = harness.sample_detail()
        draft = harness.catalog.get_draft(detail['drafts'][0]['draftId'])
        provider = FakeLLMProvider(replies=[AppError(
            'upstream unavailable', code='UPSTREAM_UNAVAILABLE', status_code=503
        )])
        handle = harness.handle(LOCAL_PROFILE, provider=provider)
        store = harness.service.job_engine.store('question')
        job = store.create(kind='organize', frozen_input=_organize_contract(
            draft, fingerprint=fingerprint_of_handle(handle)
        ))
        result = asyncio.run(harness.service.job_engine.run_job(
            'question', job.job_id, harness.service._organize_executor_factory(model=handle), uses_model=True
        ))
        assert result.state == 'failed'
        assert result.error_code == result.checkpoint['jobError']['code'] == 'UPSTREAM_UNAVAILABLE'
        assert result.checkpoint['jobError']['message']
    finally:
        harness.close()


@pytest.mark.asyncio
async def test_cancel_while_waiting_has_no_provider_call_and_releases_slots(tmp_path):
    provider = FakeLLMProvider(replies=[generation_reply()])
    harness = GenerationHarness(tmp_path, provider=provider, with_client=False)
    engine = harness.service.job_engine
    engine._ensure_primitives()
    await engine._model.acquire()
    try:
        job = await harness.service.create_generation_job(_generation_request([]))
        store = engine.store('question')
        for _ in range(200):
            if store.get(job.jobId).state == 'running':
                break
            await asyncio.sleep(0.005)
        assert store.get(job.jobId).state == 'running'
        store.request_cancel(job.jobId)
        assert provider.calls == []
        task = engine._tracked[('question', job.jobId)]
        engine._model.release()
        result = await asyncio.wait_for(task, timeout=5)
        assert result.state == 'cancelled'
        assert provider.calls == []
        assert harness.row_count('question_imports') == 0
        assert engine.active_jobs == 0
        next_job = store.create(kind='generate')
        async def probe(frozen, ctx):
            return JobOutcome(result={'slotReleased': True})
        next_result = await asyncio.wait_for(engine.run_job(
            'question', next_job.job_id, probe, uses_model=True
        ), timeout=2)
        assert next_result.state == 'succeeded'
    finally:
        await engine.shutdown()
        harness.close()


@pytest.mark.asyncio
async def test_cancel_during_model_resolution_has_no_provider_call(tmp_path, monkeypatch):
    provider = FakeLLMProvider(replies=[generation_reply()])
    harness = GenerationHarness(tmp_path, provider=provider, with_client=False)
    entered, release = asyncio.Event(), asyncio.Event()
    original = harness.service._resolve_frozen_handle
    async def delayed(snapshot):
        entered.set()
        await release.wait()
        return await original(snapshot)
    monkeypatch.setattr(harness.service, '_resolve_frozen_handle', delayed)
    try:
        job = await harness.service.create_generation_job(_generation_request([]))
        await asyncio.wait_for(entered.wait(), timeout=3)
        harness.service.job_engine.store('question').request_cancel(job.jobId)
        release.set()
        task = harness.service.job_engine._tracked[('question', job.jobId)]
        result = await asyncio.wait_for(task, timeout=3)
        assert result.state == 'cancelled'
        assert provider.calls == []
        assert harness.row_count('question_imports') == 0
    finally:
        await harness.service.job_engine.shutdown()
        harness.close()
