"""Receipt wins for same-command generation, apply and rejection races."""
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.contracts import lesson_plans as lp
from app.core.exceptions import AppError
from tests.lesson_plans_support import LessonScene, changed


@pytest.fixture
async def scene(tmp_path):
    value=await LessonScene.create(tmp_path)
    try:
        yield value
    finally:
        await value.close()


async def test_concurrent_generation_same_package_creates_one_job_input_schedule(scene):
    body=scene.generate_request()
    before=scene.count("workflow_jobs"),scene.count("command_submissions")
    values=await asyncio.gather(scene.be.generate_proposal("lesson",body),scene.be.generate_proposal("lesson",body))
    assert sorted(item["replayed"] for item in values)==[False,True]
    assert values[0]["job"]["jobId"]==values[1]["job"]["jobId"]
    assert scene.count("workflow_jobs")==before[0]+1 and scene.count("command_submissions")==before[1]+1
    assert scene.count("lesson_generation_inputs")==1 and len(scene.engine.accepted)==1


async def test_concurrent_apply_same_package_one_revision_decision_receipt(scene):
    proposal,_=await scene.proposal()
    body=scene.apply_request(proposal,("process","keyPoints"))
    before=scene.count("lesson_plan_revisions"),scene.count("command_submissions")
    values=await asyncio.gather(*(scene.be.apply_proposal("lesson",proposal["proposalId"],body) for _ in range(2)))
    assert sorted(item["replayed"] for item in values)==[False,True]
    assert values[0]["currentRevisionId"]==values[1]["currentRevisionId"]
    assert scene.count("lesson_plan_revisions")==before[0]+1 and scene.count("command_submissions")==before[1]+1
    assert scene.count("lesson_proposal_decisions")==1 and scene.be.get_lesson("lesson")["revision"]==2
    # Ordered selectedFields belongs to original command identity.
    with pytest.raises(AppError) as changed_package:
        await scene.be.apply_proposal("lesson",proposal["proposalId"],body.model_copy(update={"selected_fields":["keyPoints","process"]}))
    assert changed_package.value.code=="SUBMISSION_CONFLICT"


async def test_concurrent_reject_same_package_only_one_terminal_row(scene):
    proposal,_=await scene.proposal()
    body=lp.LessonRejectRequest(submissionId="reject")
    before=scene.count("command_submissions")
    with ThreadPoolExecutor(2) as pool:
        values=list(pool.map(lambda _:scene.be.reject_proposal("lesson",proposal["proposalId"],body),range(2)))
    assert sorted(item["replayed"] for item in values)==[False,True]
    assert all(item["state"]=="rejected" for item in values)
    assert scene.count("lesson_proposal_decisions")==1 and scene.count("command_submissions")==before+1
    assert scene.be.get_lesson("lesson")["revision"]==1


def test_original_nested_body_frozen_before_external_preparation(scene,monkeypatch):
    from app.services.lesson_plans import service as module
    base=scene.be.create_lesson(scene.create_request())
    request=scene.save_request(base,content=changed(base["currentRevision"]["data"],keyPoints="frozen"))
    original_data=request.data.model_dump(by_alias=True,mode="json")
    original=module.freeze_context
    def mutation(*args):
        request.data.lesson_types.append("experiment")
        request.data.process.clear()
        return original(*args)
    monkeypatch.setattr(module,"freeze_context",mutation)
    result=scene.be.save_draft(base["lessonPlanId"],request)
    assert result["currentRevision"]["data"]==original_data
    # Rebuild the original wire packet, rather than acknowledging the mutated one.
    original_request=lp.LessonSaveRequest(submissionId=request.submission_id,expectedRevision=base["revision"],data=original_data,context=None)
    assert scene.be.save_draft(base["lessonPlanId"],original_request)=={**result,"replayed":True}
