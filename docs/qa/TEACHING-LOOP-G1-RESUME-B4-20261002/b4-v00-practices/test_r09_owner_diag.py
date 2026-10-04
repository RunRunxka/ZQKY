"""Independent R09: standard-main HTTP-confirmed bank ownership into B4.

Prepared only until CTRL freezes this source and authorizes its execution.
Initial original paper is a real managed/confirmed fixture. Bank questions are
created solely by upload -> explicit human editing/review -> confirm HTTP.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import time
import uuid

# This guard precedes even the author context helper's indirect app.main import.
assert os.environ.get("ZQKY_ENV") == "test"
assert os.environ.get("ZQKY_QDRANT_URL") == "http://127.0.0.1:16333"
assert os.environ.get("ZQKY_EMBEDDING_BASE_URL") == "http://127.0.0.1:9"
assert os.environ.get("PYTHONUTF8") == "1"
assert os.environ.get("B4_P_RUN_ROOT") and os.environ.get("B4_P_EVIDENCE_DIR")
RUN_ROOT = Path(os.environ["B4_P_RUN_ROOT"]).resolve()
assert Path(os.environ["ZQKY_DATA_DIR"]).resolve().is_relative_to(RUN_ROOT)
assert Path(os.environ["ZQKY_TEXTBOOK_SOURCE_DIR"]).resolve().is_relative_to(RUN_ROOT)

import pytest
from openpyxl import Workbook
from app.contracts.teaching_loop import RichContentV2
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.sqlite import open_readonly
from app.repositories.teaching.papers import PaperRepository, ItemKnowledgeRecord
from app.services.question_bank.service import QuestionBankService
from app.services.rich_content.renderer_docx import render_rich_document
from tests.practices_support import open_api_scene

FOREIGN_OWNER = "r09-other-owner"
CONSTRAINTS = {"count": 1, "questionTypes": ["short_answer"], "difficulties": ["easy"]}


def record(name, value):
    destination = Path(os.environ["B4_P_EVIDENCE_DIR"]) / (name + ".json")
    assert not destination.exists(), f"Evidence overwrite refused: {destination}"
    destination.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
        indent=2, default=str) + "\n", encoding="utf-8")


class HTTP:
    def __init__(self, client):
        self.client = client
        self.calls = []

    def request(self, method, path, **kwargs):
        response = getattr(self.client, method)("/api/v1" + path, **kwargs)
        self.calls.append({"method": method, "path": path,
            "requestJson": kwargs.get("json"), "status": response.status_code,
            "response": response.json()})
        return response

    def json(self, method, path, expected=200, **kwargs):
        response = self.request(method, path, **kwargs)
        assert response.status_code == expected, (path, response.status_code, response.text)
        return response.json()


def wait_analysis(http, receipt):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        job = http.json("get", "/workflow-jobs/" + receipt["job"]["jobId"], params={"domain": "teaching"})
        if job["state"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            assert job["state"] == "succeeded", job
            return http.json("get", "/analysis-runs/" + receipt["runId"])
        time.sleep(.02)
    raise AssertionError("R09 real analysis job exceeded bounded 20 second wait")


def initial_analysis(app, http, tag):
    point = http.json("post", "/knowledge-points", 201,
        json={"subjectId": "math", "code": tag, "name": "R09 固定目标知识点"})
    rich = dict(version=2, sharedMaterials=[],
        stemBlocks=[dict(id="original-stem", kind="paragraph", text="初測原卷：计算一加一。")],
        optionBlocks={}, answerBlocks=[dict(id="original-answer", kind="paragraph", text="二")],
        explanationBlocks=[], assets=[], origin=dict(originalAssetId="r09-fixture-document",
        originalSha256="ab" * 32, sourceLocator={"paragraphIndex": 1}))
    # No bank question is inserted here. The only direct initial seed is a file paper.
    document = render_rich_document(rich=RichContentV2.model_validate(rich),
        assets=app.state.asset_store, variant="teacher", title="R09 初测原卷")
    asset = app.state.asset_store.store_original(document,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_name="r09-original.docx")
    repo = PaperRepository(app.state.teaching)
    with app.state.teaching.write_transaction() as conn:
        file = app.state.file_assets.create_in(conn, kind="paper", blob_key=asset.blob_key,
            sha256=asset.sha256, byte_size=asset.byte_size, original_name="r09-original.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        paper = repo.create_paper_in(conn, subject_id="math", title="R09 初测原卷")
        revision = repo.create_revision_in(conn, paper_id=paper.paper_id, version=1,
            source_file_id=file.asset_id, total_score_units=100, title_snapshot="R09 初测原卷")
        item_id = uuid.uuid4().hex
        repo.insert_items_in(conn, paper_revision_id=revision.revision_id,
            items=[dict(item_id=item_id, parent_item_id=None, question_no="Q1", ordinal=1,
                is_scored=True, max_score_units=100, content=rich, source_locator={"paragraphIndex": 1})])
        repo.insert_item_knowledge_in(conn, item_id=item_id, paper_revision_id=revision.revision_id,
            knowledge=[ItemKnowledgeRecord(point["id"], point["revisionId"], point["name"], "primary", "human")])
        repo.confirm_revision_in(conn, revision.revision_id)
        repo.set_current_revision_in(conn, paper.paper_id, revision.revision_id)
    klass = http.json("post", "/classes", 201,
        json={"code": tag, "name": "R09 隔离班级", "schoolYear": "2026", "gradeId": "g"})
    student = http.json("post", "/students", 201,
        json={"name": "R09 隔离学生", "studentNo": "00001", "classId": klass["id"], "joinedOn": "2026-01-01"})
    assessment = http.json("post", "/assessments", 201, json={"submissionId": tag + "-assessment",
        "paperRevisionId": revision.revision_id, "title": "R09 初测", "assessmentType": "exam",
        "heldOn": "2026-10-02", "classIds": [klass["id"]], "participants": [dict(
            studentId=student["id"], classId=klass["id"], attendance="present", attemptNo=1)]})
    workbook = Workbook()
    workbook.active.append(["学号", "姓名", "Q1"])
    workbook.active.append([student["studentNo"], student["name"], 0])
    data = io.BytesIO()
    workbook.save(data)
    imported = http.json("post", "/assessments/" + assessment["assessment"]["assessmentId"] + "/score-imports",
        201, files={"file": ("r09-scores.xlsx", data.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    score = http.json("post", "/score-imports/" + imported["importId"] + "/confirm", json={
        "submissionId": tag + "-scores", "expectedImportRevision": imported["revision"],
        "expectedAssessmentRevision": assessment["assessment"]["revision"],
        "previewVersion": imported["previewVersion"], "baseScoreRevisionId": None})
    analysis = http.json("post", "/assessments/" + assessment["assessment"]["assessmentId"] + "/analysis-runs",
        202, json={"submissionId": tag + "-analysis", "scoreRevisionId": score["revisionId"],
            "selectedParticipantIds": [assessment["participants"][0]["participantId"]], "ruleCode": "any_loss_v1"})
    ready = wait_analysis(http, analysis)
    assert ready["reportReady"] is True and ready["job"]["state"] == "succeeded"
    return {"point": point, "assessment": assessment, "score": score, "analysis": ready,
        "originalPaperId": paper.paper_id, "originalPaperRevisionId": revision.revision_id,
        "originalAssetSHA256": hashlib.sha256(document).hexdigest()}


def upload_review_confirm(app, http, point, tag, expected_owner):
    stem = "R09 " + tag + "：计算二加二并写出结果。"
    uploaded = http.json("post", "/question-imports", 201,
        files={"file": (tag + ".md", ("1. " + stem + "\n答案：四\n").encode("utf-8"), "text/markdown")},
        data={"subjectId": "math"})
    assert uploaded["ownerId"] == expected_owner
    assert uploaded["state"] == "needs_review" and uploaded["draftCount"] == 1, uploaded
    draft = uploaded["drafts"][0]
    # Explicit human edit clears parser rich projection; then a second unchanged
    # patch marks the exact current content as reviewed, respecting review reset.
    content = {"type": "short_answer", "stemMarkdown": stem, "options": [],
        "answer": {"textMarkdown": "四"}, "explanationMarkdown": "二加二等于四。",
        "assetIds": [], "richContent": None}
    edited = http.json("patch", "/question-drafts/" + draft["draftId"], json={
        "expectedRevision": draft["revision"], "content": content,
        "metadata": {"subjectId": "math", "difficulty": "easy"}, "reviewState": "needs_review",
        "knowledgeLinks": [{"knowledgePointId": point["id"], "role": "primary"}]})
    reviewed = http.json("patch", "/question-drafts/" + draft["draftId"], json={
        "expectedRevision": edited["revision"], "content": edited["content"],
        "metadata": edited["metadata"], "reviewState": "reviewed"})
    assert reviewed["reviewState"] == "reviewed"
    confirmed = http.json("post", "/question-imports/" + uploaded["importId"] + "/confirm", json={
        "submissionId": tag + "-confirm", "importId": uploaded["importId"], "items": [dict(
            draftId=reviewed["draftId"], expectedDraftRevision=reviewed["revision"])], "duplicateResolutions": []})
    assert confirmed["failures"] == [] and len(confirmed["confirmedQuestionIds"]) == 1, confirmed
    question_id = confirmed["confirmedQuestionIds"][0]
    detail = http.json("get", "/questions/" + question_id)
    assert detail["ownerId"] == expected_owner and detail["status"] == "confirmed"
    assert detail["content"]["stemMarkdown"] == stem and detail["type"] == "short_answer"
    assert [(x["knowledgePointId"], x["knowledgeRevisionId"]) for x in detail["knowledgeLinks"]] == [
        (point["id"], point["revisionId"])]
    # Public question DTO has numeric revision only; capture the corresponding
    # immutable revision id read-only, without manufacturing or editing a row.
    conn = open_readonly(app.state.question_bank.db_path)
    try:
        row = conn.execute("SELECT id,owner_id,current_revision_id FROM questions WHERE id=?", (question_id,)).fetchone()
        assert row["owner_id"] == expected_owner
        result = {"questionId": row["id"], "questionRevisionId": row["current_revision_id"],
            "ownerId": row["owner_id"], "importId": uploaded["importId"], "draftId": reviewed["draftId"],
            "detail": detail, "confirmed": confirmed, "reviewed": reviewed}
        snapshot = app.state.fixed_question_reader.read_revision(result["questionRevisionId"], owner_id=expected_owner)
        assert snapshot.question_id == question_id and snapshot.content["stemMarkdown"] == stem
        return result
    finally:
        conn.close()


def owner_facts(app):
    result = {}
    for domain, catalog in {"textbook": app.state.catalog, "knowledge": app.state.knowledge,
                           "question": app.state.question_bank, "teaching": app.state.teaching}.items():
        conn = open_readonly(catalog.db_path)
        try:
            names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            tables = {}
            for table in names:
                columns = [r[1] for r in conn.execute('PRAGMA table_info("' + table + '")')]
                count = conn.execute('SELECT count(*) FROM "' + table + '"').fetchone()[0]
                groups = [dict(r) for r in conn.execute('SELECT owner_id,count(*) AS rowCount FROM "' + table + '" GROUP BY owner_id ORDER BY owner_id')] if "owner_id" in columns else None
                tables[table] = {"rows": count, "hasOwnerColumn": "owner_id" in columns, "owners": groups}
            integrity = [r[0] for r in conn.execute("PRAGMA integrity_check")]
            fks = [dict(r) for r in conn.execute("PRAGMA foreign_key_check")]
            result[domain] = {"path": str(catalog.db_path), "tables": tables,
                              "integrity": integrity, "foreignKeyViolations": fks}
            assert integrity == ["ok"] and fks == []
        finally:
            conn.close()
    return result


@pytest.fixture
def scene(tmp_path, request):
    assert tmp_path.resolve().is_relative_to(RUN_ROOT)
    http = None
    app = None
    facts = None
    try:
        with open_api_scene(tmp_path) as (app, client, settings):
            http = HTTP(client)
            assert settings.credentials_file is None and Settings.from_env().credentials_file is None
            assert app.state.question_bank_service.owner_id == "local-user"
            assert app.state.practice_service.owner_id == "local"
            tag = "r09-" + uuid.uuid4().hex[:12]
            seed = initial_analysis(app, http, tag)
            question = upload_review_confirm(app, http, seed["point"], tag + "-standard", "local-user")
            standard = app.state.question_bank_service
            foreign = QuestionBankService(app.state.question_bank, settings, owner_id=FOREIGN_OWNER,
                knowledge_catalog=app.state.knowledge, coordinator=app.state.publication_coordinator,
                job_engine=app.state.job_engine)
            try:
                app.state.question_bank_service = foreign
                foreign_question = upload_review_confirm(app, http, seed["point"], tag + "-foreign", FOREIGN_OWNER)
            finally:
                app.state.question_bank_service = standard
                foreign.close()
            assert app.state.question_bank_service is standard and standard.owner_id == "local-user"
            facts = {"standardQuestion": question, "foreignQuestion": foreign_question, "seed": seed,
                "runtimeOwners": {key: getattr(getattr(app.state, key), "owner_id", None) for key in (
                    "question_bank_service", "practice_service", "analysis_service", "knowledge_service", "paper_service",
                    "score_service", "assessment_service", "roster_service", "export_artifacts_service")},
                "questionReaderOwner": getattr(app.state.practice_service, "question_owner_id", None)}
            yield {"app": app, "http": http, **facts}
    finally:
        # The context has actually exited before this final resource receipt.
        # Keep even failed fixture HTTP calls; root runner retains the OS temp.
        record(request.node.name + "-facts", {"root": tmp_path, "facts": facts,
            "httpCalls": http.calls if http else [], "catalogs": owner_facts(app) if app else None,
            "testClientContextExited": True, "listenersCreated": 0,
            "formalCredentialsRead": False, "newTempRetained": True})


def create_practice(scene):
    return scene["http"].json("post", "/practice-sets", 201, json={
        "submissionId": "r09-create-" + uuid.uuid4().hex, "analysisRunId": scene["seed"]["analysis"]["runId"],
        "title": "R09 真实题库补题练习", "targetKnowledgePointIds": [scene["seed"]["point"]["id"]],
        "constraints": CONSTRAINTS})


def draft_item(scene, question):
    return {"itemKey": "manual-fixed-item", "questionRevisionId": question["questionRevisionId"],
        "ordinal": 1, "maxScore": "1", "selectedKnowledgePointIds": [scene["seed"]["point"]["id"]],
        "itemStructure": {"nodes": [dict(nodeKey="leaf", parentNodeKey=None, questionNo="1", ordinal=1,
            isScored=True, maxScore="1", knowledgePointIds=[scene["seed"]["point"]["id"]],
            sourceBlockIds=["stem:0"])]}}


def test_standard_http_question_is_confirmed_and_strictly_addressable(scene):
    question = scene["standardQuestion"]
    listing = scene["http"].json("get", "/questions", params={"subjectId": "math"})
    assert [x["questionId"] for x in listing["questions"]] == [question["questionId"]]
    fixed = scene["app"].state.fixed_question_reader.read_revision(question["questionRevisionId"], owner_id="local-user")
    assert fixed.owner_id == "local-user" and fixed.question_status == "confirmed"
    with pytest.raises(AppError) as caught:
        scene["app"].state.fixed_question_reader.read_revision(question["questionRevisionId"], owner_id="local")
    assert caught.value.code == "QUESTION_NOT_FOUND" and caught.value.status_code == 404
    inaccessible = scene["http"].request("get", "/questions/" + scene["foreignQuestion"]["questionId"])
    assert inaccessible.status_code == 404 and inaccessible.json()["code"] == "QUESTION_NOT_FOUND"


def test_standard_http_question_enters_real_b4_suggestions(scene):
    practice = create_practice(scene)
    suggestions = scene["http"].json("post", "/practice-sets/" + practice["practiceSetId"] + "/suggestions",
        json={"expectedRevision": practice["revision"], "constraints": CONSTRAINTS})
    record("suggestions-" + practice["practiceSetId"], {"practice": practice, "suggestions": suggestions,
        "expectedQuestionRevisionId": scene["standardQuestion"]["questionRevisionId"]})
    assert suggestions["selectedCount"] == 1 and suggestions["gaps"] == [], suggestions
    assert [x["questionRevisionId"] for x in suggestions["items"]] == [scene["standardQuestion"]["questionRevisionId"]]


def test_standard_http_fixed_revision_saves_and_reviews_in_real_b4(scene):
    practice = create_practice(scene)
    saved = scene["http"].request("patch", "/practice-sets/" + practice["practiceSetId"] + "/draft", json={
        "expectedRevision": practice["revision"], "items": [draft_item(scene, scene["standardQuestion"])],
        "constraints": CONSTRAINTS})
    record("manual-save-" + practice["practiceSetId"], {"practice": practice,
        "status": saved.status_code, "response": saved.json(), "expectedQuestionOwner": "local-user"})
    assert saved.status_code == 200, saved.text
    saved_body = saved.json()
    assert saved_body["currentRevision"]["draftItems"][0]["questionRevisionId"] == scene["standardQuestion"]["questionRevisionId"]
    reviewed = scene["http"].json("post", "/practice-sets/" + practice["practiceSetId"] + "/review", json={
        "submissionId": "r09-review-" + uuid.uuid4().hex, "expectedRevision": saved_body["revision"]})
    assert reviewed["currentRevision"]["state"] == "reviewed"
    assert reviewed["currentRevision"]["items"][0]["questionRevisionId"] == scene["standardQuestion"]["questionRevisionId"]
    assert reviewed["currentRevision"]["items"][0]["content"]["stemBlocks"][0]["text"] == scene["standardQuestion"]["detail"]["content"]["stemMarkdown"]


def test_foreign_owner_question_stays_excluded_and_save_is_rejected(scene):
    practice = create_practice(scene)
    suggestions = scene["http"].json("post", "/practice-sets/" + practice["practiceSetId"] + "/suggestions",
        json={"expectedRevision": practice["revision"], "constraints": CONSTRAINTS})
    assert scene["foreignQuestion"]["questionRevisionId"] not in [x["questionRevisionId"] for x in suggestions["items"]]
    denied = scene["http"].request("patch", "/practice-sets/" + practice["practiceSetId"] + "/draft", json={
        "expectedRevision": practice["revision"], "items": [draft_item(scene, scene["foreignQuestion"])],
        "constraints": CONSTRAINTS})
    assert denied.status_code == 404 and denied.json()["code"] == "QUESTION_NOT_FOUND", denied.text
    assert all(key in denied.json() for key in ("code", "message", "requestId", "retryable"))
    unchanged = scene["http"].json("get", "/practice-sets/" + practice["practiceSetId"])
    assert unchanged["revision"] == practice["revision"] and unchanged["currentRevision"]["items"] == []
    with pytest.raises(AppError) as caught:
        scene["app"].state.fixed_question_reader.read_revision(scene["foreignQuestion"]["questionRevisionId"], owner_id="local-user")
    assert caught.value.code == "QUESTION_NOT_FOUND" and caught.value.status_code == 404
