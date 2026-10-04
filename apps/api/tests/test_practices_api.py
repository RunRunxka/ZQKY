from pathlib import Path
from tests.practices_support import open_api_scene, seed_api_loop, package_parts


def test_full_actual_api_loop_three_export_downloads_and_lineage(tmp_path):
    with open_api_scene(tmp_path) as (app,client,settings):
        result=seed_api_loop(app,client)
        question=client.get("/api/v1/questions/"+result["questionId"])
        assert question.status_code==200,question.text
        assert question.json()["ownerId"]==app.state.question_bank_service.owner_id
        assert app.state.practice_service.owner_id=="local"
        assert len(result["exports"])==3
        for artifact in result["exports"]:
            response=client.get(artifact["downloadUrl"])
            assert response.status_code==200
            parts=package_parts(response.content)
            if artifact["variant"]=="student":
                contents=b"\n".join(parts.values())
                assert b"ANS_PRIVATE" not in contents and b"EXPL_PRIVATE" not in contents
            assert response.headers["x-content-type-options"]=="nosniff"
        practice=result["practice"]
        prefix=f"/api/v1/practice-sets/{practice['practiceSetId']}"
        assert client.patch(prefix+"/draft",json={"submissionId":"api-stale-save","expectedRevision":0,"items":[],"constraints":{"count":1}}).status_code==409
        assert client.get(prefix+"/revisions/not-this-revision").status_code==404
        assert client.get("/api/v1/export-artifacts/not-an-artifact/download").status_code==404
        assert len(result["catalogPaths"])==4
        # Public registry retry must execute the same frozen export after a real asset failure.
        import time
        copied=client.post(prefix+"/revisions",json={"submissionId":"api-copy","sourceRevisionId":practice["currentRevision"]["practiceRevisionId"]})
        assert copied.status_code==201,copied.text
        new=copied.json()
        sealed=client.post(prefix+"/review",json={"submissionId":"api-review-copy","expectedRevision":new["revision"]})
        assert sealed.status_code==200,sealed.text
        fixed=sealed.json()["currentRevision"]
        sha=fixed["items"][0]["content"]["assets"][0]["sha256"]
        path=app.state.asset_store.path_of("blobs/"+sha);original=path.read_bytes();path.write_bytes(b"bad bytes")
        export=client.post(prefix+f"/revisions/{fixed['practiceRevisionId']}/exports",json={"submissionId":"api-failed-export","variant":"student","assessmentId":None})
        assert export.status_code==202,export.text
        job_id=export.json()["job"]["jobId"]
        def terminal():
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                job=client.get(f"/api/v1/workflow-jobs/{job_id}?domain=teaching").json()
                if job["state"] in {"failed","succeeded","cancelled","interrupted"}:return job
                time.sleep(.03)
            raise AssertionError("public job did not reach terminal")
        failed=terminal()
        assert failed["state"]=="failed" and failed["attempt"]==1
        before=app.state.job_engine.store("teaching").get(job_id)
        path.write_bytes(original)
        retry=client.post(f"/api/v1/workflow-jobs/{job_id}/retry",json={"domain":"teaching"})
        assert retry.status_code==200,retry.text
        succeeded=terminal()
        assert succeeded["state"]=="succeeded" and succeeded["attempt"]==2
        assert app.state.job_engine.store("teaching").get(job_id).frozen_input==before.frozen_input
