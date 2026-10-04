"""Actual B5 generation/publication/apply/reject with isolated provider replies."""
import copy
import sqlite3

import pytest

from app.contracts import lesson_plans as lp
from app.core.exceptions import AppError
from app.services.jobs.registry import JobExecutorRegistry
from tests.lesson_plans_support import LessonScene, changed


@pytest.fixture
async def scene(tmp_path):
    value = await LessonScene.create(tmp_path)
    try:
        yield value
    finally:
        await value.close()


async def test_generation_job_input_receipt_atomic_and_original_replay(scene,monkeypatch):
    base = scene.be.get_lesson("lesson")
    body = scene.generate_request(base)
    receipt = await scene.be.generate_proposal("lesson",body)
    assert receipt["job"]["state"]=="queued" and receipt["job"]["kind"]=="lesson_generation"
    with scene.catalog.read_connection() as conn:
        row = conn.execute("SELECT * FROM lesson_generation_inputs WHERE job_id=?",(receipt["job"]["jobId"],)).fetchone()
        assert row["input_hash"]==receipt["inputHash"] and row["base_revision_id"]==base["currentRevisionId"]
    def broken(*args,**kwargs):
        raise AssertionError("replay must not resolve changed models or prepare invalidated references")
    monkeypatch.setattr(scene.ai.service,"prepare",broken)
    scene.be.save_draft("lesson",scene.save_request(base,content=changed(base["currentRevision"]["data"],reflection="later")))
    assert await scene.be.generate_proposal("lesson",body)=={**receipt,"replayed":True}
    assert scene.count("lesson_generation_inputs")==1 and len(scene.engine.accepted)==1
    altered = body.model_copy(update={"requirements":"不同要求"})
    with pytest.raises(AppError) as conflict:
        await scene.be.generate_proposal("lesson",altered)
    assert conflict.value.code=="SUBMISSION_CONFLICT"
    registry=JobExecutorRegistry();scene.be.register_job_executors(registry)
    spec=registry.spec_for("teaching","lesson_generation")
    assert spec.uses_model and callable(spec.factory(scene.ai.store.get(receipt["job"]["jobId"])))


async def test_generation_input_failure_rolls_back_job_and_receipt(scene,monkeypatch):
    before=scene.count("workflow_jobs"),scene.count("command_submissions")
    original=scene.ai.service.insert_input_in
    def fault(conn,**kwargs):
        original(conn,**kwargs)
        raise RuntimeError("after real input INSERT")
    monkeypatch.setattr(scene.ai.service,"insert_input_in",fault)
    with pytest.raises(RuntimeError,match="after real input"):
        await scene.be.generate_proposal("lesson",scene.generate_request())
    assert scene.count("lesson_generation_inputs")==0
    assert before==(scene.count("workflow_jobs"),scene.count("command_submissions"))
    assert scene.engine.accepted==[]


async def test_generation_prepare_failure_rechecks_competing_success_receipt(scene,monkeypatch):
    import asyncio
    original=scene.ai.service.prepare
    body=scene.generate_request()
    saved=[]
    def race(*args,**kwargs):
        monkeypatch.setattr(scene.ai.service,"prepare",original)
        saved.append(asyncio.run(scene.be.generate_proposal("lesson",body)))
        raise AppError("准备期间材料失效",code="ORIGINAL_PREPARE",status_code=422)
    monkeypatch.setattr(scene.ai.service,"prepare",race)
    result=await scene.be.generate_proposal("lesson",body)
    assert result=={**saved[0],"replayed":True}
    assert scene.count("lesson_generation_inputs")==1 and len(scene.engine.accepted)==1


@pytest.mark.parametrize("protocol",["openai_chat","openai_responses","anthropic_messages"])
async def test_real_generation_then_process_apply_preserves_teacher_fields(tmp_path,protocol):
    scene=await LessonScene.create(tmp_path,protocol)
    try:
        base=scene.be.get_lesson("lesson")
        proposal,receipt=await scene.proposal()
        assert proposal["state"]=="pending" and scene.ai.calls==1
        assert scene.be.get_lesson("lesson")==base  # Publishing is not applying.
        result=await scene.be.apply_proposal("lesson",proposal["proposalId"],scene.apply_request(proposal))
        revision=result["currentRevision"]
        assert result["revision"]==2 and revision["source"]=="ai_applied" and revision["reviewState"]=="unreviewed"
        assert revision["acceptedProposalId"]==proposal["proposalId"] and revision["selectedFields"]==["process"]
        assert revision["data"]["process"]==proposal["patch"]["process"]
        assert revision["processMetadata"]==proposal["budget"]["stages"]
        assert sum(stage["minutes"] for stage in revision["processMetadata"])==40
        for field,value in base["currentRevision"]["data"].items():
            if field!="process":
                assert revision["data"][field]==value
        assert revision["contextSnapshot"]["analysis"]["analysisRunId"]==scene.body.analysis_run_id
        decision=scene.be.get_proposal("lesson",proposal["proposalId"])
        assert decision["state"]=="applied" and decision["acceptedRevisionId"]==result["currentRevisionId"]
        with scene.catalog.read_connection() as conn:
            assert conn.execute("PRAGMA foreign_key_check").fetchall()==[]
    finally:
        await scene.close()


async def test_partial_apply_terminal_replay_original_receipt_after_undo_save(scene,monkeypatch):
    base=scene.be.get_lesson("lesson")
    proposal,_=await scene.proposal()
    body=scene.apply_request(proposal,("keyPoints","exercises"))
    result=await scene.be.apply_proposal("lesson",proposal["proposalId"],body)
    assert result["currentRevision"]["data"]["process"]==base["currentRevision"]["data"]["process"]
    assert result["currentRevision"]["processMetadata"]==[]
    for field in ["title","totalLessons","currentLessonNo","lessonTypes","otherTypeText","reflection","coreCompetencies","teachingDesign"]:
        assert result["currentRevision"]["data"][field]==base["currentRevision"]["data"][field]
    with pytest.raises(AppError) as terminal:
        await scene.be.apply_proposal("lesson",proposal["proposalId"],scene.apply_request(proposal,("process",),submission="second-part"))
    assert terminal.value.code=="LESSON_PROPOSAL_TERMINATED"
    later=scene.be.save_draft("lesson",scene.save_request(result,submission="undo-save",content=base["currentRevision"]["data"]))
    assert later["revision"]==3
    def fail(*args,**kwargs):
        raise AssertionError("old apply replay must bypass candidate and byte verification")
    monkeypatch.setattr(scene.ai.service,"validate_for_apply",fail)
    monkeypatch.setattr(scene.ai.rag,"verify_selected_evidence",fail)
    assert await scene.be.apply_proposal("lesson",proposal["proposalId"],body)=={**result,"replayed":True}
    assert scene.be.get_lesson("lesson")["revision"]==3
    assert scene.be.get_revision("lesson",result["currentRevisionId"])==result["currentRevision"]


async def test_absent_candidate_fields_rejected_without_writes(scene):
    scene.ai.reply["patch"].pop("exercises")
    proposal,_=await scene.proposal()
    assert proposal["patch"]["exercises"] is None
    before=scene.count("lesson_plan_revisions"),scene.count("command_submissions")
    with pytest.raises(AppError) as invalid:
        await scene.be.apply_proposal("lesson",proposal["proposalId"],scene.apply_request(proposal,("exercises",)))
    assert invalid.value.code=="LESSON_PROPOSAL_INVALID"
    assert before==(scene.count("lesson_plan_revisions"),scene.count("command_submissions"))


async def test_new_save_stales_proposal_explicit_reject_does_not_change_doc(scene):
    base=scene.be.get_lesson("lesson")
    proposal,_=await scene.proposal()
    later=scene.be.save_draft("lesson",scene.save_request(base,content=changed(base["currentRevision"]["data"],title="later")))
    assert scene.be.get_proposal("lesson",proposal["proposalId"])["state"]=="stale"
    with pytest.raises(AppError) as stale:
        await scene.be.apply_proposal("lesson",proposal["proposalId"],scene.apply_request(proposal))
    assert stale.value.code=="LESSON_PROPOSAL_STALE"
    body=lp.LessonRejectRequest(submissionId="reject")
    result=scene.be.reject_proposal("lesson",proposal["proposalId"],body)
    assert result["state"]=="rejected" and result["selectedFields"]==[]
    assert scene.be.reject_proposal("lesson",proposal["proposalId"],body)=={**result,"replayed":True}
    assert scene.be.get_lesson("lesson")==later
    with pytest.raises(AppError) as terminal:
        scene.be.reject_proposal("lesson",proposal["proposalId"],lp.LessonRejectRequest(submissionId="second"))
    assert terminal.value.code=="LESSON_PROPOSAL_TERMINATED"


@pytest.mark.parametrize("fault_point",["revision","pointer","decision","receipt"])
async def test_apply_fault_atomic_rollback_each_boundary(scene,monkeypatch,fault_point):
    base=scene.be.get_lesson("lesson")
    proposal,_=await scene.proposal()
    before=tuple(scene.count(t) for t in ("lesson_plan_revisions","lesson_revision_reviews","lesson_proposal_decisions","command_submissions"))
    target={"revision":"append_revision","pointer":"advance","decision":"insert_decision"}.get(fault_point)
    if target:
        original=getattr(scene.be.repo,target)
        def broken(*args,**kwargs):
            original(*args,**kwargs)
            raise RuntimeError("fault after "+fault_point)
        monkeypatch.setattr(scene.be.repo,target,broken)
    else:
        with scene.catalog.write_transaction() as conn:
            conn.execute("""CREATE TRIGGER be_apply_receipt_fault BEFORE INSERT ON command_submissions
                WHEN NEW.operation LIKE 'lesson.apply:%' BEGIN SELECT RAISE(ABORT,'apply receipt fault'); END""")
    with pytest.raises((RuntimeError,sqlite3.IntegrityError)):
        await scene.be.apply_proposal("lesson",proposal["proposalId"],scene.apply_request(proposal))
    assert scene.be.get_lesson("lesson")==base
    assert scene.be.get_proposal("lesson",proposal["proposalId"])["state"]=="pending"
    assert before==tuple(scene.count(t) for t in ("lesson_plan_revisions","lesson_revision_reviews","lesson_proposal_decisions","command_submissions"))


async def test_apply_preparation_failure_returns_competing_success_receipt(scene,monkeypatch):
    import asyncio
    proposal,_=await scene.proposal()
    body=scene.apply_request(proposal)
    original=scene.ai.rag.verify_selected_evidence
    committed=[]
    def race(*args,**kwargs):
        monkeypatch.setattr(scene.ai.rag,"verify_selected_evidence",original)
        committed.append(asyncio.run(scene.be.apply_proposal("lesson",proposal["proposalId"],body)))
        raise AppError("准备期间原文失效",code="ORIGINAL_PREPARE",status_code=422)
    monkeypatch.setattr(scene.ai.rag,"verify_selected_evidence",race)
    result=await scene.be.apply_proposal("lesson",proposal["proposalId"],body)
    assert result=={**committed[0],"replayed":True}
    assert scene.count("lesson_proposal_decisions")==1


async def test_cross_document_and_owner_proposals_uniform404(scene):
    from app.services.lesson_plans import LessonPlanService
    proposal,_=await scene.proposal()
    second=scene.be.create_lesson(scene.create_request())
    other=LessonPlanService(scene.catalog,analysis_reader=scene.ai.analysis.service,knowledge_catalog=scene.ai.practice_scene.knowledge,
        coordinator=scene.be.coordinator,job_engine=scene.engine,generation_service=scene.ai.service,evidence_reader=scene.ai.rag,owner_id="other")
    for owner,lid in [(scene.be,second["lessonPlanId"]),(other,"lesson")]:
        with pytest.raises(AppError) as absent:
            owner.get_proposal(lid,proposal["proposalId"])
        assert absent.value.code=="NOT_FOUND"
        with pytest.raises(AppError) as absent:
            await owner.apply_proposal(lid,proposal["proposalId"],scene.apply_request(proposal))
        assert absent.value.code=="NOT_FOUND"
        with pytest.raises(AppError) as absent:
            owner.reject_proposal(lid,proposal["proposalId"],lp.LessonRejectRequest(submissionId="reject"))
        assert absent.value.code=="NOT_FOUND"


async def test_apply_new_attempt_rechecks_active_references_but_keeps_candidate(scene):
    proposal,_=await scene.proposal()
    with scene.ai.practice_scene.knowledge.write_transaction() as conn:
        conn.execute("UPDATE knowledge_points SET status='archived' WHERE id='k1'")
    with pytest.raises(AppError):
        await scene.be.apply_proposal("lesson",proposal["proposalId"],scene.apply_request(proposal))
    assert scene.be.get_lesson("lesson")["revision"]==1
    assert scene.be.get_proposal("lesson",proposal["proposalId"])["state"]=="pending"
