import pytest
from tests.analysis_support import AnalysisScene


async def test_real_create_app_analysis_http_full_shapes_and_faults(tmp_path):
    scene = AnalysisScene(tmp_path)
    with scene.http_client() as client:
        request = scene.request().model_dump(by_alias=True)
        first = client.post("/api/v1/assessments/assessment/analysis-runs", json=request)
        assert first.status_code == 202, first.text
        receipt = first.json()
        assert set(receipt) == {"runId", "inputHash", "scoreRevisionId", "paperRevisionId", "job", "replayed", "reused"}
        assert receipt["job"]["state"] == "queued" and receipt["job"]["result"] is None and receipt["job"]["error"] is None
        url = f"/api/v1/analysis-runs/{receipt['runId']}"
        assert client.get(url + "/evidence").status_code == 409
        assert client.get(url).json()["reportReady"] is False
        replay = client.post("/api/v1/assessments/assessment/analysis-runs", json=request)
        assert replay.status_code == 202 and replay.json()["replayed"]
        await scene.engine.run_job("teaching", receipt["job"]["jobId"], scene.service.execute_job)
        report = client.get(url).json()
        assert report["reportReady"] and report["job"]["state"] == "succeeded"
        assert report["participants"][0]["className"] is None
        assert client.get("/api/v1/analysis-runs?assessmentId=assessment").json()["total"] == 1
        assert client.get(url + "/classes").json()["total"] == 2
        assert client.get(url + "/students?participantId=p000&knowledgePointId=k1").json()["items"][0]["observation"] == "needs_consolidation"
        first_page = client.get(url + "/evidence?limit=5").json()
        next_page = client.get(url + "/evidence?limit=5&offset=5").json()
        assert first_page["total"] == 12 and len(first_page["items"]) == 5
        assert not {r["evidenceId"] for r in first_page["items"]} & {r["evidenceId"] for r in next_page["items"]}
        assert client.get(url + "/evidence?knowledgePointId=k1").json()["total"] == 8
        invalid = client.get(url + "/evidence?participantId=other")
        assert invalid.status_code == 422 and invalid.json()["details"]["issues"][0]["field"] == "participantId"
        assert client.get(url + "/evidence?limit=201").status_code == 422
        note = client.post(url + "/notes", json={"submissionId": "note", "note": "教师备注"})
        assert note.status_code == 201 and note.json()["participantId"] is None and note.json()["knowledgePointId"] is None
        assert client.get(url + "/notes").json()["total"] == 1
        assert client.get("/api/v1/analysis-runs/unknown").status_code == 404
        client.app.state.analysis_service = None
        missing = client.get(url)
        assert missing.status_code == 503 and missing.json()["retryable"] is True


async def test_http_selection_and_submission_conflict_locate_fields(tmp_path):
    scene = AnalysisScene(tmp_path)
    with scene.http_client() as client:
        body = scene.request(ids=["p000", "p000"]).model_dump(by_alias=True)
        invalid = client.post("/api/v1/assessments/assessment/analysis-runs", json=body)
        assert invalid.status_code == 422 and invalid.json()["details"]["issues"][0]["field"] == "selectedParticipantIds[1]"
        assert scene.count("workflow_jobs") == 0
        accepted = scene.request().model_dump(by_alias=True)
        assert client.post("/api/v1/assessments/assessment/analysis-runs", json=accepted).status_code == 202
        conflict = client.post("/api/v1/assessments/assessment/analysis-runs", json={**accepted, "selectedParticipantIds": ["p000"]})
        assert conflict.status_code == 409 and conflict.json()["code"] == "SUBMISSION_CONFLICT"
        assert set(conflict.json()) >= {"code", "message", "requestId", "retryable", "details"}
