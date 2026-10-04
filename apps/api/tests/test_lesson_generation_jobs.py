import asyncio
import copy
import json
from dataclasses import replace
import pytest
from app.core.exceptions import AppError
from app.repositories.jobs.repository import JobStore
from app.services.jobs.engine import JobEngine
from tests.lesson_generation_support import Scene


@pytest.fixture
async def scene(tmp_path):
    value = await Scene.create(tmp_path)
    try: yield value
    finally: await value.close()


async def test_real_job_and_candidate_publish_atomic_immutable_no_lesson_edit(scene):
    before = scene.lesson.current_revision.data.model_dump()
    result = await scene.run()
    assert result.state == "succeeded" and result.attempt == 1 and scene.calls == 1
    assert set(result.result) == {"lessonPlanId","proposalId"}
    assert scene.count("lesson_ai_proposals") == 1 and scene.count("lesson_plan_revisions") == 1
    with scene.catalog.read_connection() as conn:
        row = conn.execute("SELECT * FROM lesson_ai_proposals").fetchone()
        assert row["job_id"] == result.job_id and row["id"] == result.result["proposalId"]
        assert row["input_hash"] == result.input_hash
        assert row["model_fingerprint"] == result.model_snapshot["fingerprint"]
        assert conn.execute("SELECT current_revision_id,revision FROM lesson_plans").fetchone()[:] == ("lesson-r",1)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        payload = json.loads(row["payload_json"])
        assert payload["generationSource"]["analysis"]["scoreRevisionId"] == "score-r"
    with pytest.raises(Exception):
        with scene.catalog.write_transaction() as conn:
            conn.execute("UPDATE lesson_ai_proposals SET payload_json='{}'")
    assert scene.lesson.current_revision.data.model_dump() == before


@pytest.mark.parametrize("response,finish", [("{", "stop"), ('{"patch":{},"patch":{},"budget":{}}',"stop"),
    ('{"patch":{},"budget":NaN}',"stop"), ('[]',"stop"), ("x"*(256*1024+1),"stop"), (None,"length")],
    ids=["incomplete","duplicate-key","nonfinite","array","oversize","length-finish"])
async def test_bad_json_truncated_and_large_outputs_never_publish(scene,response,finish):
    if response is not None: scene.reply = response
    scene.finish = finish
    result = await scene.run()
    assert result.state == "failed" and result.error_code == "LESSON_PROPOSAL_INVALID"
    assert scene.count("lesson_ai_proposals") == 0 and scene.count("lesson_plan_revisions") == 1


async def test_timeout_and_explicit_retry_preserve_frozen_input(scene):
    scene.handle = replace(scene.handle,config=replace(scene.handle.config,timeoutSeconds=0.05))
    scene.delay = 0.2
    job = scene.job()
    failed = await scene.run(job)
    assert failed.state == "failed" and failed.error_code == "UPSTREAM_TIMEOUT"
    assert scene.count("lesson_ai_proposals") == 0
    scene.delay = 0
    queued = scene.store.retry(job.job_id)
    assert queued.frozen_input == job.frozen_input and queued.input_hash == job.input_hash and queued.model_snapshot == job.model_snapshot
    done = await scene.run(queued)
    assert done.state == "succeeded" and done.attempt == 2 and scene.calls == 2


@pytest.mark.parametrize("status,code", [(401,"UPSTREAM_AUTH_FAILED"),(429,"RATE_LIMITED"),(503,"UPSTREAM_ERROR")])
async def test_provider_service_errors_keep_original_code(scene,status,code):
    scene.fail_http = status
    done = await scene.run()
    assert done.state == "failed" and done.error_code == code
    assert "fixture upstream" not in str(done.error)
    assert scene.count("lesson_ai_proposals") == 0


async def test_queued_cancel_and_inflight_cancel_do_not_publish(scene):
    queued = scene.job()
    scene.store.request_cancel(queued.job_id)
    assert scene.store.get(queued.job_id).state == "cancelled" and scene.calls == 0
    scene.delay = 0.3
    job = scene.job()
    task = asyncio.create_task(scene.run(job))
    await asyncio.wait_for(scene.started.wait(),2)
    scene.store.request_cancel(job.job_id)
    done = await task
    assert done.state == "cancelled" and scene.count("lesson_ai_proposals") == 0


async def test_restart_interrupted_only_explicit_retry_calls_provider(scene):
    job = scene.job()
    scene.store.claim(job.job_id)
    assert scene.store.reconcile_interrupted() == [job.job_id]
    assert scene.calls == 0 and scene.store.get(job.job_id).state == "interrupted"
    queued = scene.store.retry(job.job_id)
    done = await scene.run(queued)
    assert done.state == "succeeded" and done.attempt == 2 and scene.calls == 1
    assert done.frozen_input == job.frozen_input and done.model_snapshot == job.model_snapshot


@pytest.mark.parametrize("retry", [False,True])
async def test_frozen_model_drift_blocks_first_and_retry_before_network(scene,retry):
    job = scene.job()
    if retry:
        scene.store.claim(job.job_id)
        scene.store.reconcile_interrupted()
        job = scene.store.retry(job.job_id)
    scene.handle = replace(scene.handle,model_id="different",config=replace(scene.handle.config,modelId="different"))
    done = await scene.run(job)
    assert done.state == "failed" and done.error_code == "MODEL_CONFIG_DRIFT" and scene.calls == 0


async def test_publication_fault_rolls_back_candidate_and_success(scene):
    job = scene.job()
    with scene.catalog.write_transaction() as conn:
        conn.execute("CREATE TRIGGER fixture_fail_candidate AFTER INSERT ON lesson_ai_proposals BEGIN SELECT RAISE(ABORT,'fixture publication fault'); END")
    failed = await scene.run(job)
    assert failed.state == "failed" and failed.error_code == "JOB_FAILED"
    assert scene.count("lesson_ai_proposals") == 0
    with scene.catalog.write_transaction() as conn: conn.execute("DROP TRIGGER fixture_fail_candidate")
    done = await scene.run(scene.store.retry(job.job_id))
    assert done.state == "succeeded" and scene.count("lesson_ai_proposals") == 1


async def test_original_lease_lost_cannot_publish_or_fail_new_holder(scene):
    scene.delay = 0.15
    job = scene.job()
    task = asyncio.create_task(scene.run(job))
    await asyncio.wait_for(scene.started.wait(),2)
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE workflow_jobs SET lease_token='new-holder' WHERE id=?",(job.job_id,))
    done = await task
    assert done.state == "running" and done.lease_token == "new-holder"
    assert scene.count("lesson_ai_proposals") == 0


async def test_model_delay_heartbeat_renews_original_lease(scene):
    scene.store = JobStore(scene.catalog,domain="teaching",table="workflow_jobs",kinds=frozenset({"lesson_generation"}),lease_seconds=3)
    scene.engine = JobEngine({"teaching":scene.store})
    scene.delay = 2.2
    job = scene.job()
    heartbeat_calls = []
    original = scene.store.heartbeat
    def heartbeat(lease):
        result = original(lease)
        heartbeat_calls.append((lease.token,result))
        return result
    scene.store.heartbeat = heartbeat
    done = await scene.run(job)
    assert done.state == "succeeded", done.error
    assert len(heartbeat_calls) >= 2 and all(ok for _,ok in heartbeat_calls)
    assert len({token for token,_ in heartbeat_calls}) == 1


def test_refs_recheck_performs_no_blob_model_or_network(scene,monkeypatch):
    frozen = scene.prepare().frozen_input
    def forbidden(*args,**kwargs): raise AssertionError("external IO in SQL-only recheck")
    monkeypatch.setattr(scene.rag.texts,"read_normalized_text",forbidden)
    monkeypatch.setattr(scene.rag,"verify_selected_evidence",forbidden)
    monkeypatch.setattr(scene.service,"model_resolver",forbidden)
    monkeypatch.setattr(scene.service,"frozen_model_resolver",forbidden)
    scene.service.revalidate_prepared_refs(frozen)


async def test_archived_knowledge_stops_new_generation(scene):
    job = scene.job()
    with scene.practice_scene.knowledge.write_transaction() as conn: conn.execute("UPDATE knowledge_points SET status='archived' WHERE id='k1'")
    done = await scene.run(job)
    assert done.state == "failed" and done.error_code == "KNOWLEDGE_ARCHIVED" and scene.calls == 0


async def test_missing_fingerprint_never_resolves_or_calls_model(scene):
    job = scene.job()
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE workflow_jobs SET model_snapshot_json='{}' WHERE id=?",(job.job_id,))
    def forbidden(_): raise AssertionError("missing snapshot must not resolve current/default model")
    scene.service.frozen_model_resolver = forbidden
    done = await scene.run(scene.store.get(job.job_id))
    assert done.state == "failed" and done.error_code == "MODEL_FINGERPRINT_MISSING" and scene.calls == 0


def test_input_insert_requires_exact_job_hash_owner_and_model_snapshot(scene):
    prepared = scene.prepare()
    with scene.catalog.write_transaction() as conn:
        job = scene.store.create_in(conn,kind="lesson_generation",frozen_input=prepared.frozen_input,
                                  model_snapshot=prepared.model_snapshot,owner_id="local")
        with pytest.raises(AppError):
            scene.service.insert_input_in(conn,job=replace(job,input_hash="ab"*32),prepared=prepared,owner_id="local")
        with pytest.raises(AppError):
            scene.service.insert_input_in(conn,job=job,prepared=prepared,owner_id="foreign")
        with pytest.raises(AppError):
            scene.service.insert_input_in(conn,job=replace(job,model_snapshot={}),prepared=prepared,owner_id="local")
    assert scene.count("lesson_generation_inputs") == 0
