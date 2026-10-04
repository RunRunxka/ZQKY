"""Read-only review probes; only isolated app roots are written."""
import copy
import io
import json
import os
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tests.practices_support import open_api_scene, seed_api_loop


OUT = Path(__file__).parent


def save_result(name, result):
    (OUT / name).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def copied_draft(app, client, seed, tag):
    prefix = "/api/v1/practice-sets/" + seed["practice"]["practiceSetId"]
    response = client.post(prefix + "/revisions", json={
        "submissionId": tag + "-copy",
        "sourceRevisionId": seed["practice"]["currentRevision"]["practiceRevisionId"],
    })
    assert response.status_code == 201, response.text
    state = response.json()
    payload = {
        "expectedRevision": state["revision"],
        "items": copy.deepcopy(state["currentRevision"]["draftItems"]),
        "constraints": state["currentRevision"]["constraints"],
    }
    return prefix, payload


def test_unknown_patch_success_can_be_safely_replayed(tmp_path):
    with open_api_scene(tmp_path) as (app, client, settings):
        seed = seed_api_loop(app, client, tag="review-patch")
        prefix, payload = copied_draft(app, client, seed, "patch-boundary")
        first = client.patch(prefix + "/draft", json=payload)
        assert first.status_code == 200, first.text
        # The backend succeeded; the front-end may lose this response and resend its package.
        replay = client.patch(prefix + "/draft", json=payload)
        state = client.get(prefix).json()
        save_result("patch-replay.json", {
            "dataRoot": str(settings.data_dir),
            "originalExpectedRevision": payload["expectedRevision"],
            "firstStatus": first.status_code,
            "firstRevision": first.json()["revision"],
            "replayStatus": replay.status_code,
            "replayBody": replay.json(),
            "finalRevision": state["revision"],
            "savedPayload": state["currentRevision"]["draftItems"],
            "sentPayload": payload["items"],
        })
        assert replay.status_code == 200, "Committed PATCH replay cannot resolve its lost receipt"
        assert replay.json()["revision"] == first.json()["revision"]


def test_accepted_complete_question_number_round_trips_generated_score_template(tmp_path):
    import time
    with open_api_scene(tmp_path) as (app, client, settings):
        seed = seed_api_loop(app, client, tag="review-formula-header")
        prefix, payload = copied_draft(app, client, seed, "formula-boundary")
        payload["items"][0]["itemStructure"]["nodes"][0]["questionNo"] = "=16"
        saved = client.patch(prefix + "/draft", json=payload)
        assert saved.status_code == 200, saved.text
        sealed = client.post(prefix + "/review", json={
            "submissionId": "formula-review",
            "expectedRevision": saved.json()["revision"],
        })
        assert sealed.status_code == 200, sealed.text
        fixed = sealed.json()["currentRevision"]["practiceRevisionId"]
        conversion = client.post(prefix + "/revisions/" + fixed + "/assessments", json={
            "submissionId": "formula-convert", "title": "公式样貌题号",
            "heldOn": "2026-10-03", "classIds": [seed["classId"]],
            "participants": [{"studentId": seed["studentId"], "classId": seed["classId"],
                "attendance": "present", "attemptNo": 1}],
        })
        assert conversion.status_code == 201, conversion.text
        assessment = conversion.json()["assessmentId"]
        receipt = client.post(prefix + "/revisions/" + fixed + "/exports", json={
            "submissionId": "formula-export", "variant": "score_template", "assessmentId": assessment,
        })
        assert receipt.status_code == 202, receipt.text
        job_id = receipt.json()["job"]["jobId"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            job = client.get("/api/v1/workflow-jobs/" + job_id + "?domain=teaching").json()
            if job["state"] in {"succeeded", "failed", "cancelled", "interrupted"}:
                break
            time.sleep(.02)
        assert job["state"] == "succeeded", job
        artifact = client.get("/api/v1/export-artifacts/" + job["result"]["artifactId"]).json()
        data = client.get(artifact["downloadUrl"]).content
        workbook = load_workbook(io.BytesIO(data))
        cell = workbook["成绩"]["E1"]
        meta = workbook["固定映射"]["C6"]
        workbook["成绩"]["E2"] = 0
        stream = io.BytesIO()
        workbook.save(stream)
        imported = client.post("/api/v1/assessments/" + assessment + "/score-imports", files={
            "file": ("scores.xlsx", stream.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        })
        assert imported.status_code == 201, imported.text
        preview = imported.json()
        save_result("formula-header.json", {
            "dataRoot": str(settings.data_dir), "savedQuestionNo": "=16",
            "header": {"value": cell.value, "dataType": cell.data_type},
            "fixedMappingQuestionNo": {"value": meta.value, "dataType": meta.data_type},
            "scoreImport": preview,
        })
        assert cell.data_type == "s", "A teacher-entered question identity must be exported as literal text"


def test_committed_changed_patch_replay_resolves_saved_matrix_identity(tmp_path):
    with open_api_scene(tmp_path) as (app, client, settings):
        seed = seed_api_loop(app, client, tag="review-changed-patch")
        prefix, payload = copied_draft(app, client, seed, "changed-patch-boundary")
        old_score = payload["items"][0]["maxScore"]
        payload["items"][0]["maxScore"] = "1.00"
        payload["items"][0]["itemStructure"]["nodes"][0]["maxScore"] = "1.00"
        first = client.patch(prefix + "/draft", json=payload)
        assert first.status_code == 200, first.text
        replay = client.patch(prefix + "/draft", json=payload)
        state = client.get(prefix).json()
        save_result("changed-patch-replay.json", {
            "dataRoot": str(settings.data_dir), "oldScore": old_score,
            "editedScore": "1.00", "originalExpectedRevision": payload["expectedRevision"],
            "firstStatus": first.status_code, "firstRevision": first.json()["revision"],
            "firstTotalScoreUnits": first.json()["currentRevision"]["totalScoreUnits"],
            "replayStatus": replay.status_code, "replayBody": replay.json(),
            "finalRevision": state["revision"],
            "finalScore": state["currentRevision"]["draftItems"][0]["maxScore"],
            "sentItems": payload["items"],
        })
        assert replay.status_code == 200, "UI frozen save replay receives permanent CAS conflict after the real edit committed"
        assert replay.json()["revision"] == first.json()["revision"]
