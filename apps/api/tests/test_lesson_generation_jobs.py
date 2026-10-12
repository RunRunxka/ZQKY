"""R7 教案生成任务生命周期（LangChain 改造适配）：候选发布原子性、取消、重试、冻结。

与归档差异：模型替身是假 LangChain 模型（``with_structured_output``），
无 provider transport——超时/HTTP 状态码路径由 runner 的异常降级与假模型的
抛错结果覆盖；其余（冻结输入/指纹核对/租约/取消/发布事务）语义逐条保留。
"""
import asyncio
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


@pytest.mark.parametrize("reply_value", ["{", '{"patch":{},"patch":{},"budget":{}}', "[]", None],
    ids=["incomplete","duplicate-key","array","none"])
async def test_bad_model_outputs_never_publish(scene,reply_value):
    """坏输出（含结构化解析失败/异常）不发布候选；runner 重试仍坏则优雅降级为失败任务。"""
    if reply_value is None:
        scene.model.default_reply = RuntimeError("fixture upstream failure")
    else:
        scene.model.default_reply = reply_value
    result = await scene.run()
    assert result.state == "failed" and result.error_code == "LESSON_PROPOSAL_INVALID"
    assert scene.count("lesson_ai_proposals") == 0 and scene.count("lesson_plan_revisions") == 1


async def test_explicit_retry_preserves_frozen_input(scene):
    scene.model.default_reply = "{"
    job = scene.job()
    failed = await scene.run(job)
    assert failed.state == "failed" and failed.error_code == "LESSON_PROPOSAL_INVALID"
    assert scene.count("lesson_ai_proposals") == 0
    from tests.lesson_generation_support import reply as valid_reply
    scene.model.default_reply = valid_reply()  # 恢复有效默认输出
    queued = scene.store.retry(job.job_id)
    assert queued.frozen_input == job.frozen_input and queued.input_hash == job.input_hash and queued.model_snapshot == job.model_snapshot
    done = await scene.run(queued)
    assert done.state == "succeeded" and done.attempt == 2 and scene.calls == 2


def test_timeout_budget_widened_for_lesson_generation():
    """教案生成按调用放宽非流式等待（300s > 传输默认 30s），语义移到 runner 后仍保留。"""
    from app.providers.llm.base import DEFAULT_TIMEOUT_SECONDS
    from app.services.lesson_generation.service import LESSON_TIMEOUT_SECONDS
    assert LESSON_TIMEOUT_SECONDS > DEFAULT_TIMEOUT_SECONDS


async def test_model_exception_degrades_to_failed_job_not_crash(scene):
    scene.model.default_reply = RuntimeError("connection reset")
    done = await scene.run()
    assert done.state == "failed"
    assert scene.count("lesson_ai_proposals") == 0


async def test_queued_cancel_and_inflight_cancel_do_not_publish(scene):
    import asyncio as _asyncio
    queued = scene.job()
    scene.store.request_cancel(queued.job_id)
    assert scene.store.get(queued.job_id).state == "cancelled" and scene.calls == 0
    scene.model.delay = 0.3
    scene.model.started = _asyncio.Event()
    job = scene.job()
    task = _asyncio.create_task(scene.run(job))
    await _asyncio.wait_for(scene.model.started.wait(), 2)
    scene.store.request_cancel(job.job_id)
    done = await task
    assert done.state == "cancelled" and scene.count("lesson_ai_proposals") == 0


async def test_restart_interrupted_only_explicit_retry_calls_model(scene):
    job = scene.job()
    scene.store.claim(job.job_id)
    assert scene.store.reconcile_interrupted() == [job.job_id]
    assert scene.calls == 0 and scene.store.get(job.job_id).state == "interrupted"
    queued = scene.store.retry(job.job_id)
    done = await scene.run(queued)
    assert done.state == "succeeded" and done.attempt == 2 and scene.calls == 1
    assert done.frozen_input == job.frozen_input and done.model_snapshot == job.model_snapshot


@pytest.mark.parametrize("retry", [False,True])
async def test_frozen_model_drift_blocks_first_and_retry_before_model_call(scene,retry):
    job = scene.job()
    if retry:
        scene.store.claim(job.job_id)
        scene.store.reconcile_interrupted()
        job = scene.store.retry(job.job_id)
    scene.handle.fingerprint = "drifted-fingerprint"
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
    import asyncio as _asyncio
    scene.model.delay = 0.15
    scene.model.started = _asyncio.Event()
    job = scene.job()
    task = _asyncio.create_task(scene.run(job))
    await _asyncio.wait_for(scene.model.started.wait(), 2)
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE workflow_jobs SET lease_token='new-holder' WHERE id=?",(job.job_id,))
    done = await task
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE workflow_jobs SET lease_token='new-holder' WHERE id=?",(job.job_id,))
    done = await task
    assert done.state == "running" and done.lease_token == "new-holder"
    assert scene.count("lesson_ai_proposals") == 0


async def test_model_delay_heartbeat_renews_original_lease(scene):
    scene.store = JobStore(scene.catalog,domain="teaching",table="workflow_jobs",kinds=frozenset({"lesson_generation"}),lease_seconds=3)
    scene.engine = JobEngine({"teaching":scene.store})
    scene.model.delay = 2.2
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
    assert len({token for token,_ in heartbeat_calls}) == 1


def test_refs_recheck_performs_no_blob_model_or_network(scene,monkeypatch):
    frozen = scene.prepare().frozen_input
    def forbidden(*args,**kwargs): raise AssertionError("external IO in SQL-only recheck")
    monkeypatch.setattr(scene.rag,"_require_source",forbidden)
    monkeypatch.setattr(scene.rag,"verify_selected_evidence",forbidden)
    monkeypatch.setattr(scene.service,"model_resolver",forbidden)
    monkeypatch.setattr(scene.service,"frozen_model_resolver",forbidden)
    scene.service.revalidate_prepared_refs(frozen)


async def test_archived_knowledge_stops_new_generation(scene):
    job = scene.job()
    with scene.knowledge.write_transaction() as conn: conn.execute("UPDATE knowledge_points SET status='archived' WHERE id='k1'")
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
