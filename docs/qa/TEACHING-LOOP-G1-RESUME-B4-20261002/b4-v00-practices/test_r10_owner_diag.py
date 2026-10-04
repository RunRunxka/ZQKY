"""R10 independent foreign confirmed-question mutation boundaries; prepared only."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

assert os.environ.get("ZQKY_ENV") == "test"
assert os.environ.get("ZQKY_QDRANT_URL") == "http://127.0.0.1:16333"
assert os.environ.get("ZQKY_EMBEDDING_BASE_URL") == "http://127.0.0.1:9"
assert os.environ.get("PYTHONUTF8") == "1" and os.environ.get("B4_P_RUN_ROOT")
RUN_ROOT = Path(os.environ["B4_P_RUN_ROOT"]).resolve()
assert Path(os.environ["ZQKY_DATA_DIR"]).resolve().is_relative_to(RUN_ROOT)
assert Path(os.environ["ZQKY_TEXTBOOK_SOURCE_DIR"]).resolve().is_relative_to(RUN_ROOT)

from app.core.sqlite import open_readonly
from app.services.question_bank.service import QuestionBankService
from test_r09_owner_diag import scene, record, FOREIGN_OWNER


def snapshot(app, question_id):
    conn = open_readonly(app.state.question_bank.db_path)
    try:
        question = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        assert question is not None and question["owner_id"] == FOREIGN_OWNER
        revisions = [dict(r) for r in conn.execute(
            "SELECT * FROM question_revisions WHERE question_id=? ORDER BY id", (question_id,))]
        for row in revisions:
            row["decodedContent"] = json.loads(row["content_json"])
            row["decodedMetadata"] = json.loads(row["metadata_json"])
        return {"question": dict(question), "revisions": revisions,
            "foreignKeyViolations": [dict(r) for r in conn.execute("PRAGMA foreign_key_check")]}
    finally:
        conn.close()


def read_foreign_via_real_service(scene):
    app, http = scene["app"], scene["http"]
    standard = app.state.question_bank_service
    foreign = QuestionBankService(app.state.question_bank, app.state.settings, owner_id=FOREIGN_OWNER,
        knowledge_catalog=app.state.knowledge, coordinator=app.state.publication_coordinator,
        job_engine=app.state.job_engine)
    try:
        app.state.question_bank_service = foreign
        result = http.json("get", "/questions/" + scene["foreignQuestion"]["questionId"])
        assert result["ownerId"] == FOREIGN_OWNER
        return result
    finally:
        app.state.question_bank_service = standard
        foreign.close()
        assert app.state.question_bank_service is standard and standard.owner_id == "local-user"


def test_foreign_question_patch_is_404_and_has_no_committed_mutation(scene):
    app, http = scene["app"], scene["http"]
    question_id = scene["foreignQuestion"]["questionId"]
    detail = read_foreign_via_real_service(scene)
    before = snapshot(app, question_id)
    content = copy.deepcopy(detail["content"])
    content["stemMarkdown"] += " R10 未授权编辑标记。"
    body = {"expectedRevision": detail["revision"], "content": content, "metadata": detail["metadata"]}
    # Call using restored unmodified standard service. Do not rollback a real
    # unauthorized HTTP mutation: capture its committed result as counterexample.
    response = http.request("patch", "/questions/" + question_id, json=body)
    after_detail = read_foreign_via_real_service(scene)
    after = snapshot(app, question_id)
    record("r10-patch-" + question_id, {"request": body, "status": response.status_code,
        "response": response.json(), "beforeDetail": detail, "afterDetail": after_detail,
        "beforeDB": before, "afterDB": after, "dbUnchanged": before == after,
        "serviceReferenceRestored": app.state.question_bank_service.owner_id == "local-user",
        "sampleRowsRolledBackOrRewritten": False})
    assert response.status_code == 404 and response.json()["code"] == "QUESTION_NOT_FOUND", response.text
    assert all(key in response.json() for key in ("code", "message", "requestId", "retryable"))
    assert before == after and detail == after_detail


def test_foreign_question_delete_is_404_and_does_not_archive(scene):
    app, http = scene["app"], scene["http"]
    question_id = scene["foreignQuestion"]["questionId"]
    detail = read_foreign_via_real_service(scene)
    before = snapshot(app, question_id)
    assert detail["status"] == "confirmed"
    params = {"expectedRevision": detail["revision"]}
    # Successful broken behavior is an empty 204, so capture bytes explicitly
    # instead of the R09 HTTP helper's unconditional JSON response decoding.
    response = http.client.delete("/api/v1/questions/" + question_id, params=params)
    response_body = response.json() if response.content else None
    http.calls.append({"method": "delete", "path": "/questions/" + question_id,
        "requestParams": params, "status": response.status_code, "response": response_body,
        "responseBytes": len(response.content)})
    after_detail = read_foreign_via_real_service(scene)
    after = snapshot(app, question_id)
    record("r10-delete-" + question_id, {"requestParams": params, "status": response.status_code,
        "response": response_body, "responseBytes": len(response.content),
        "beforeDetail": detail, "afterDetail": after_detail, "beforeDB": before, "afterDB": after,
        "dbUnchanged": before == after,
        "serviceReferenceRestored": app.state.question_bank_service.owner_id == "local-user",
        "sampleRowsRolledBackOrRewritten": False})
    assert response.status_code == 404 and response_body["code"] == "QUESTION_NOT_FOUND", response.text
    assert all(key in response_body for key in ("code", "message", "requestId", "retryable"))
    assert before == after and after_detail["status"] == "confirmed" and detail == after_detail
