"""All lesson routes and byte/strict/owner errors via actual FastAPI middleware."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.contracts import lesson_plans as lp
from tests.lesson_plans_support import LessonScene, changed


@pytest.fixture
async def scene(tmp_path):
    value=await LessonScene.create(tmp_path)
    try:
        yield value
    finally:
        await value.close()


def test_actual_http_create_import_list_save_history_and_errors(scene):
    with scene.client() as (client,_):
        base="/api/v1/lesson-plans"
        body=scene.create_request().model_dump(by_alias=True,mode="json")
        response=client.post(base,json=body)
        assert response.status_code==201,response.text
        created=response.json();lid=created["lessonPlanId"]
        assert client.post(base,json=body).json()=={**created,"replayed":True}
        local=dict(schemaVersion=1,revision=4,updatedAt="2026-10-03T09:00:00Z",data=body["data"])
        imported=client.post(base+"/import-local",json=dict(submissionId="import",subjectId="math",classId="class",draft=local,context=None))
        assert imported.status_code==201 and imported.json()["currentRevision"]["importEnvelope"]==local
        assert client.get(base,params={"subjectId":"math","classId":"class","limit":1}).json()["total"]==3
        request=scene.save_request(created,content=changed(body["data"],title="更新")).model_dump(by_alias=True,mode="json")
        updated=client.patch(base+f"/{lid}/draft",json=request)
        assert updated.status_code==200 and updated.json()["revision"]==2
        assert client.patch(base+f"/{lid}/draft",json=request).json()=={**updated.json(),"replayed":True}
        history=client.get(base+f"/{lid}/revisions").json()
        assert [x["version"] for x in history["items"]]==[2,1]
        assert "data" not in history["items"][0]
        fixed=client.get(base+f"/{lid}/revisions/{created['currentRevisionId']}")
        assert fixed.status_code==200 and fixed.json()==created["currentRevision"]
        assert client.get(base+f"/{lid}").json()==updated.json()
        conflict=client.patch(base+f"/{lid}/draft",json={**request,"submissionId":"old-cas-new-op"})
        assert conflict.status_code==409 and conflict.json()["code"]=="REVISION_CONFLICT"
        assert conflict.json()["details"]["fields"]==["expectedRevision"]
        for path in [base+"/missing",base+f"/{lid}/revisions/missing",base+"/missing/revisions"]:
            result=client.get(path)
            assert result.status_code==404 and result.json()["code"]=="NOT_FOUND"
        invalid=client.post(base,json={**body,"ownerId":"other"})
        assert invalid.status_code==422 and invalid.json()["code"]=="VALIDATION_ERROR"
        assert client.get(base,params={"limit":201}).status_code==422
        assert client.get(base,params={"offset":-1}).status_code==422


def test_create_with_missing_class_returns_class_not_found(scene):
    """本机记忆里的 classId 失效时，后端给出可识别的 CLASS_NOT_FOUND，而不是误导性的教案 404。"""
    with scene.client() as (client, _):
        body = scene.create_request().model_dump(by_alias=True, mode="json")
        body["classId"] = "missing-class"
        response = client.post("/api/v1/lesson-plans", json=body)
        assert response.status_code == 404
        assert response.json()["code"] == "CLASS_NOT_FOUND"
        assert "班级" in response.json()["message"]


def test_actual_http_same_body_parallel_saves_return_one_receipt(scene):
    created=scene.be.create_lesson(scene.create_request())
    body=scene.save_request(created,content=changed(created["currentRevision"]["data"],title="HTTP 并发")).model_dump(by_alias=True,mode="json")
    with scene.client() as (client,_),ThreadPoolExecutor(2) as pool:
        responses=list(pool.map(lambda _:client.patch(f"/api/v1/lesson-plans/{created['lessonPlanId']}/draft",json=copy.deepcopy(body)),range(2)))
    assert [x.status_code for x in responses]==[200,200],[x.text for x in responses]
    values=[x.json() for x in responses]
    assert sorted(x["replayed"] for x in values)==[False,True]
    assert values[0]["currentRevisionId"]==values[1]["currentRevisionId"]


def test_raw_request_cap_invalid_unicode_and_strict_import(scene):
    with scene.client() as (client,_):
        path="/api/v1/lesson-plans"
        body=scene.create_request().model_dump(by_alias=True,mode="json")
        # Even whitespace cannot bypass the complete raw-byte ceiling.
        raw=json.dumps(body).encode()+b" "*(lp.MAX_REQUEST_BYTES+1)
        oversize=client.post(path,content=raw,headers={"Content-Type":"application/json"})
        assert oversize.status_code==413 and oversize.json()["code"]=="LESSON_REQUEST_TOO_LARGE"
        illegal=copy.deepcopy(body);illegal["data"]["title"]="\ud800"
        invalid=client.post(path,content=json.dumps(illegal).encode(),headers={"Content-Type":"application/json"})
        assert invalid.status_code==422
        envelope=dict(schemaVersion=True,revision=3,updatedAt="2026-10-03T09:00:00Z",data=body["data"])
        assert client.post(path+"/import-local",json=dict(submissionId="bad",subjectId="math",classId="class",context=None,draft=envelope)).status_code==422
        assert scene.count("lesson_plans")==1


async def test_actual_http_evidence_generation_get_apply_reject_all_routes(scene):
    with scene.client() as (client,_):
        verified=scene.ai.verified
        ref=verified.evidence_refs[0]
        response=client.post("/api/v1/lesson-plans/evidence/verify",json=dict(selection=verified.scope_snapshot.selection.model_dump(),
            slices=[dict(documentRevisionId=ref.documentRevisionId,charStart=ref.charStart,charEnd=ref.charEnd)]))
        assert response.status_code==200,response.text
        assert response.json()==verified.model_dump(by_alias=True,mode="json")
        body=scene.generate_request().model_dump(by_alias=True,mode="json")
        generated=client.post("/api/v1/lesson-plans/lesson/proposals",json=body)
        assert generated.status_code==202,generated.text
        record=scene.ai.store.get(generated.json()["job"]["jobId"])
        job=await scene.engine.run_job("teaching",record.job_id,scene.ai.service.executor_for(record),uses_model=True)
        assert job.state=="succeeded",job.error
        proposal=client.get(f"/api/v1/lesson-plans/lesson/proposals/{job.result['proposalId']}")
        assert proposal.status_code==200 and proposal.json()["state"]=="pending"
        request=scene.apply_request(proposal.json(),("coreCompetencies",)).model_dump(by_alias=True,mode="json")
        applied=client.post(f"/api/v1/lesson-plans/lesson/proposals/{job.result['proposalId']}/apply",json=request)
        assert applied.status_code==200,applied.text
        assert applied.json()["currentRevision"]["selectedFields"]==["coreCompetencies"]
        second,receipt=await scene.proposal(applied.json(),submission="next")
        rejected=client.post(f"/api/v1/lesson-plans/lesson/proposals/{second['proposalId']}/reject",json={"submissionId":"reject"})
        assert rejected.status_code==200 and rejected.json()["state"]=="rejected"


def test_missing_service_returns_503(scene):
    with scene.client() as (client,app):
        app.state.lesson_plan_service=None
        response=client.get("/api/v1/lesson-plans")
        assert response.status_code==503 and response.json()["code"]=="SERVICE_UNAVAILABLE"


def test_archive_restore_routes_are_gone(scene):
    """B3 归档移除：教案归档/恢复端点 404，数据零变化；archived 过滤参数移除。"""
    with scene.client() as (client,_):
        base="/api/v1/lesson-plans"
        created=client.post(base,json=scene.create_request().model_dump(by_alias=True,mode="json")).json()
        lid=created["lessonPlanId"]
        assert client.post(base+f"/{lid}/archive",json={"expectedRevision":created["revision"]}).status_code==404
        assert client.post(base+f"/{lid}/restore",json={"expectedRevision":created["revision"]}).status_code==404
        # archived 查询参数已移除（传入被忽略，返回全部——场景含预置种子教案）
        ignored=client.get(base,params={"archived":"true"})
        assert ignored.status_code==200 and ignored.json()["total"]==2
        # 数据零变化：详情/列表照常，仍可继续编辑
        assert client.get(base+f"/{lid}").json()["revision"]==created["revision"]
        assert client.get(base).json()["total"]==2
        saved=client.patch(base+f"/{lid}/draft",json=scene.save_request(created,submission="after-routes-gone",
            content=changed(created["currentRevision"]["data"],title="端点移除后写入")).model_dump(by_alias=True,mode="json"))
        assert saved.status_code==200 and saved.json()["revision"]==created["revision"]+1


def test_archived_new_save_is_422_without_revision_receipt_and_old_receipt_replays(scene):
    created=scene.be.create_lesson(scene.create_request())
    original=scene.save_request(created,content=changed(created["currentRevision"]["data"],title="归档前保存"))
    saved=scene.be.save_draft(created["lessonPlanId"],original)
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE lesson_plans SET archived_at='2026-10-03T09:00:00Z' WHERE id=?",(created["lessonPlanId"],))
    before=tuple(scene.count(table) for table in ("lesson_plan_revisions","lesson_revision_reviews","command_submissions"))
    new_request=scene.save_request(saved,submission="new-after-archive",content=changed(saved["currentRevision"]["data"],title="拒绝写入"))
    with scene.client() as (client,_):
        path=f"/api/v1/lesson-plans/{created['lessonPlanId']}/draft"
        response=client.patch(path,json=new_request.model_dump(by_alias=True,mode="json"))
        assert response.status_code==422 and response.json()["code"]=="LESSON_INVALID"
        assert before==tuple(scene.count(table) for table in ("lesson_plan_revisions","lesson_revision_reviews","command_submissions"))
        assert scene.be.get_lesson(created["lessonPlanId"])==saved
        replay=client.patch(path,json=original.model_dump(by_alias=True,mode="json"))
        assert replay.status_code==200 and replay.json()=={**saved,"replayed":True}
    assert before==tuple(scene.count(table) for table in ("lesson_plan_revisions","lesson_revision_reviews","command_submissions"))


def test_http_delete_lesson_route_guard_receipt_and_list_refresh(scene):
    """DELETE /lesson-plans/{id}：查询参数乐观锁、404/409 语义、回执与列表刷新。"""
    with scene.client() as (client,_):
        base="/api/v1/lesson-plans"
        created=client.post(base,json=scene.create_request().model_dump(by_alias=True,mode="json")).json()
        lid=created["lessonPlanId"]
        updated=client.patch(base+f"/{lid}/draft",json=scene.save_request(created,
            content=changed(created["currentRevision"]["data"],title="HTTP 删除前")).model_dump(by_alias=True,mode="json")).json()
        # 乐观锁不符 409；缺失 404。
        stale=client.delete(base+f"/{lid}",params={"expectedRevision":updated["revision"]+1})
        assert stale.status_code==409 and stale.json()["code"]=="REVISION_CONFLICT"
        missing=client.delete(base+"/missing",params={"expectedRevision":0})
        assert missing.status_code==404 and missing.json()["code"]=="NOT_FOUND"
        negative=client.delete(base+f"/{lid}",params={"expectedRevision":-1})
        assert negative.status_code==422 and negative.json()["code"]=="VALIDATION_ERROR"
        # 删除是唯一清理出口：物理删除教案行及其历史。
        receipt=client.delete(base+f"/{lid}",params={"expectedRevision":updated["revision"]})
        assert receipt.status_code==200,receipt.text
        assert receipt.json()=={"deleted":True,"lessonPlanId":lid,"removedRevisions":2,"removedProposals":0,"removedInputs":0}
        assert client.get(base+f"/{lid}").status_code==404
        assert lid not in [x["lessonPlanId"] for x in client.get(base).json()["items"]]
        assert client.get(base+f"/{lid}/revisions").status_code==404
