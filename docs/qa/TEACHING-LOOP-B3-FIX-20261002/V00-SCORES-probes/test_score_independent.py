"""Independent V00 acceptance: real routes/catalogs; all storage under OS temp."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[4]
BOOT_ROOT = Path(tempfile.mkdtemp(prefix="zqky-v00-scores-bootstrap-"))
os.environ["ZQKY_DATA_DIR"] = str(BOOT_ROOT)
os.environ["ZQKY_ENV"] = "test"
sys.path.insert(0, str(ROOT / "apps/api"))

import pytest
from fastapi.testclient import TestClient
from app.core.exceptions import AppError
from app.contracts.assessments import ParticipantAttendanceRequest
from app.services.scores.imports import parse_score_text
from tests.scores_support import ScoresHarness, write_score_xlsx, inject_cached_values

EVIDENCE = Path(__file__).parent
EVENTS = []


@pytest.fixture(scope="session", autouse=True)
def evidence():
    yield
    (EVIDENCE / "http-evidence.json").write_text(json.dumps(EVENTS, ensure_ascii=False, indent=2), encoding="utf-8")
    assert BOOT_ROOT.resolve().parent == Path(tempfile.gettempdir()).resolve()
    shutil.rmtree(BOOT_ROOT)
    from tests.conftest import _PYTEST_DATA_DIR
    assert _PYTEST_DATA_DIR.resolve().parent == Path(tempfile.gettempdir()).resolve()
    if _PYTEST_DATA_DIR.exists():
        shutil.rmtree(_PYTEST_DATA_DIR)


@pytest.fixture()
def h(tmp_path):
    with ScoresHarness(tmp_path) as running:
        yield running


def capture(label, response):
    try:
        body = response.json()
    except Exception:
        body = response.text
    EVENTS.append({"case": label, "status": response.status_code, "body": body})
    return body


def upload(h, scene, tmp_path, rows, header=None):
    path = write_score_xlsx(tmp_path / "source.xlsx", header or ["学号", "姓名", "Q1", "Q2", "Q3"], rows)
    r = h.upload_scores(scene.assessment["assessmentId"], path)
    v = capture("upload", r)
    assert r.status_code == 201, r.text
    return v


def command(scene, v, key="confirm"):
    return {
        "expectedImportRevision": v["revision"],
        "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": v["baseScoreRevisionId"],
        "previewVersion": v["previewVersion"], "submissionId": key,
        **copy.deepcopy(v["requiredAcknowledgements"]),
    }


def published(h, scene, v, key="confirm"):
    r = h.confirm_import(v["importId"], command(scene, v, key))
    b = capture("confirm", r)
    assert r.status_code == 200, r.text
    return b


def matrix(h, rid):
    r = h.score_matrix(rid, limit=200)
    assert r.status_code == 200, r.text
    return r.json()


def state(h):
    return {t: h.raw_rows(f"SELECT * FROM {t} ORDER BY rowid") for t in
            ["score_revisions", "student_item_scores", "score_revision_corrections", "score_imports", "score_import_rows", "assessments", "assessment_participants", "command_submissions"]}


@pytest.mark.parametrize("text", ["1e9999999", "1e-9999999", "1.000000000000000000000000000001", "1.23000000000000000000000000001"])
def test_decimal_context_never_rounds_underflows_or_raises_500(h, tmp_path, text):
    s = h.create_scene(tag="numeric-context", students=[("甲", "00001")])
    content = f"学号,姓名,Q1,Q2,Q3\n00001,甲,{text},2,3\n".encode("utf-8")
    c = TestClient(h.app, base_url="http://127.0.0.1:8001", raise_server_exceptions=False)
    r = c.post(f'/api/v1/assessments/{s.assessment["assessmentId"]}/score-imports', files={"file": ("strict.csv", content, "text/csv")})
    capture("strict-numeric-" + text, r)
    assert r.status_code == 422, r.text
    assert r.json()["code"] == ("SCORE_CELL_OVER_MAX" if text == "1e9999999" else "SCORE_CELL_INVALID")
    issues = r.json()["details"]["issues"]
    assert any(x.get("row") == 2 and x.get("column") == "C" for x in issues)
    assert h.count("score_imports") == 0 and h.count("score_revisions") == 0


@pytest.mark.parametrize("text,units", [("1.23000000000000000000000000000", 123), ("1e-2", 1)])
def test_exact_decimal_tail_zero_and_scientific_nonlossy(h, tmp_path, text, units):
    s = h.create_scene(tag="validexact", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", text, 2, 3]])
    result = published(h, s, v)
    m = matrix(h, result["revisionId"])
    assert m["rows"][0]["cells"][0]["scoreUnits"] == units


@pytest.mark.parametrize("text", ["NaN", "Infinity", "-0.01", "TRUE", "#DIV/0!", "0.001", "2.01"])
def test_bad_cells_are_located_and_zero_write(h, text):
    s = h.create_scene(tag="bad-cell", students=[("甲", "00001")])
    r = h.client.post(f'/api/v1/assessments/{s.assessment["assessmentId"]}/score-imports', files={"file": ("bad.csv", f"学号,姓名,Q1,Q2,Q3\n00001,甲,{text},2,3\n".encode(), "text/csv")})
    capture("invalid-" + text, r)
    assert r.status_code == 422, r.text
    assert any(x.get("row") == 2 and x.get("column") == "C" for x in r.json()["details"]["issues"])
    assert h.count("score_imports") == 0


def test_authoritative_four_states_full_matrix_and_exact_ack(h, tmp_path):
    s = h.create_scene(tag="fourstates", students=[("甲", "00001"), ("乙", "00002"), ("丙", "00003"), ("丁", "00004"), ("戊", "00005")])
    v = upload(h, s, tmp_path, [["00001", "甲", "0", "0.2", "0.3"], ["00002", "乙", 2, 3, None], ["00003", "丙", "缺考", None, None], ["00004", "丁", None, "免考", None]])
    ack = v["requiredAcknowledgements"]
    assert ack["absences"] == [{"classId": s.klass["id"], "participantIds": [s.participant_id("00003")]}]
    assert set(ack["missing"]["participantIds"]) == {s.participant_id("00002"), s.participant_id("00005")}
    assert ack["missing"]["cellCount"] == v["missingCellCount"] == 4
    for patch in [{"missing": None}, {"absences": []}, {"previewVersion": v["previewVersion"] + 1}]:
        before = state(h)
        r = h.confirm_import(v["importId"], {**command(s, v), **patch})
        capture("bad-ack", r)
        assert r.status_code == 422 and r.json()["code"] == "SCORE_ACKNOWLEDGEMENT_MISMATCH"
        assert state(h) == before
    r = published(h, s, v)
    m = matrix(h, r["revisionId"])
    assert m["revision"]["paperRevisionId"] == s.paper.revision_id
    rows = {x["participant"]["studentNo"]: x for x in m["rows"]}
    assert len(rows) == 5 and len(m["items"]) == 3 and h.count("student_item_scores") == 15
    assert [x["scoreUnits"] for x in rows["00001"]["cells"]] == [0, 20, 30]
    assert rows["00001"]["participant"]["totalUnits"] == 50
    for no, statuses in [("00002", ["recorded", "recorded", "missing"]), ("00003", ["absent"] * 3), ("00004", ["exempt"] * 3), ("00005", ["missing"] * 3)]:
        assert [x["status"] for x in rows[no]["cells"]] == statuses
        assert rows[no]["participant"]["totalUnits"] is None


@pytest.mark.parametrize("field,value", [("nameColumn", "a"), ("totalColumn", "c"), ("attendanceColumn", "c")])
def test_every_column_role_uses_same_canonical_identity(h, tmp_path, field, value):
    s = h.create_scene(tag="case", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3, 6, "正常"]], ["学号", "姓名", "Q1", "Q2", "Q3", "总分", "出勤"])
    before = state(h)
    mapping = {**v["mapping"], field: value}
    r = h.patch_import(v["importId"], {"expectedRevision": v["revision"], "mapping": mapping})
    capture("column-collision", r)
    assert r.status_code == 422 and r.json()["code"] == "SCORE_MAPPING_INVALID"
    assert any(x.get("column") == value.upper() for x in r.json()["details"]["issues"])
    assert state(h) == before


def test_case_duplicate_score_and_lowercase_valid(h, tmp_path):
    s = h.create_scene(tag="casepair", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3]])
    mapping = copy.deepcopy(v["mapping"])
    mapping["itemColumns"][1]["column"] = "c"
    r = h.patch_import(v["importId"], {"expectedRevision": 0, "mapping": mapping})
    assert r.status_code == 422
    mapping = copy.deepcopy(v["mapping"])
    for field in ["studentNoColumn", "nameColumn"]:
        mapping[field] = mapping[field].lower()
    for i in mapping["itemColumns"]:
        i["column"] = i["column"].lower()
    r = h.patch_import(v["importId"], {"expectedRevision": 0, "mapping": mapping})
    assert r.status_code == 200, r.text
    assert [x["column"] for x in r.json()["mapping"]["itemColumns"]] == ["C", "D", "E"]
    m = matrix(h, published(h, s, r.json())["revisionId"])
    assert [x["scoreUnits"] for x in m["rows"][0]["cells"]] == [100, 200, 300]


def test_unknown_identity_gb18030_and_header_reextract_keeps_correction(h, tmp_path):
    s = h.create_scene(tag="manual", students=[("甲", "00001")])
    source = "身份码,称呼,Q1,Q2,Q3\n00001,甲,1,2,3\n".encode("gb18030")
    r = h.client.post(f'/api/v1/assessments/{s.assessment["assessmentId"]}/score-imports', files={"file": ("manual.csv", source, "text/csv")})
    v = capture("gb-manual-upload", r)
    assert r.status_code == 201 and v["mapping"] is None
    rows = h.list_import_rows(v["importId"]).json()["items"]
    assert any(x.get("originalText") == "甲" for x in rows[0]["cells"])
    mapping = {"workSheet": "CSV", "headerRow": 1, "studentNoColumn": "A", "nameColumn": "B", "itemColumns": [{"itemId": f"it-manual-{n}", "column": c} for n, c in [(1, "C"), (2, "D"), (3, "E")]]}
    # CSV sheet name is returned by raw API metadata rather than assumed.
    raw = h.service()._scores
    with h.app.state.teaching.read_connection() as conn:
        rec = raw.require_in(conn, v["importId"])
    mapping["workSheet"] = rec.summary["sheet"]["name"] if "sheet" in rec.summary else "CSV"
    r = h.patch_import(v["importId"], {"expectedRevision": 0, "mapping": mapping, "rows": [{"rowNo": 2, "cells": [{"row": 2, "column": "C", "text": "0"}]}]})
    assert r.status_code == 200, r.text
    v = r.json()
    rows = h.list_import_rows(v["importId"]).json()["items"]
    c = next(x for x in rows[0]["cells"] if x["column"] == "C")
    assert (c["originalText"], c["correctedText"], c["text"], c["scoreUnits"]) == ("1", "0", "0", 0)
    assert [x["scoreUnits"] for x in matrix(h, published(h, s, v)["revisionId"])["rows"][0]["cells"]] == [0, 200, 300]


def test_same_sheet_header_and_identity_reextract(h, tmp_path):
    s = h.create_scene(tag="header", students=[("甲", "00001"), ("乙", "00002")])
    v = upload(h, s, tmp_path, [["学号", "姓名", "Q1", "Q2", "Q3"], ["00001", "甲", 1, 2, 3], ["00002", "乙", 0, 3, 5]], ["学号", "姓名", "小题得分", "", ""])
    m = {"workSheet": "成绩", "headerRow": 2, "studentNoColumn": "A", "nameColumn": "B", "itemColumns": [{"itemId": f"it-header-{n}", "column": c} for n, c in [(1, "C"), (2, "D"), (3, "E")]]}
    r = h.patch_import(v["importId"], {"expectedRevision": 0, "mapping": m, "rows": [{"rowNo": 3, "participantId": s.participant_id("00001"), "cells": [{"row": 3, "column": "C", "text": "0"}]}]})
    assert r.status_code == 200, r.text
    rows = h.list_import_rows(v["importId"]).json()["items"]
    assert [x["rowNo"] for x in rows] == [3, 4]
    assert rows[0]["participantId"] == s.participant_id("00001")
    assert [x["scoreUnits"] for x in matrix(h, published(h, s, r.json())["revisionId"])["rows"][0]["cells"]] in [[0, 200, 300], [0, 300, 500]]


def test_confirm_fault_after_full_matrix_rolls_back_and_identical_replay_precedes_stale_versions(h, tmp_path, monkeypatch):
    s = h.create_scene(tag="atomic", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3]])
    before = state(h)
    repo = h.service()._scores
    original = repo.seal_revision_in
    def fail_after_seal(conn, revision_id):
        original(conn, revision_id)
        raise AppError("Injected publication failure", code="V00_INJECTED_FAILURE", status_code=503)
    monkeypatch.setattr(repo, "seal_revision_in", fail_after_seal)
    r = h.confirm_import(v["importId"], command(s, v))
    assert r.status_code == 503 and r.json()["code"] == "V00_INJECTED_FAILURE"
    assert state(h) == before
    monkeypatch.setattr(repo, "seal_revision_in", original)
    committed = published(h, s, v)
    replay = h.confirm_import(v["importId"], command(s, v))
    assert replay.status_code == 200 and replay.json()["replayed"] is True
    assert replay.json()["revisionId"] == committed["revisionId"]
    assert h.count("score_revisions") == 1 and h.count("student_item_scores") == 3
    conflict = h.confirm_import(v["importId"], {**command(s, v), "previewVersion": 99})
    assert conflict.status_code == 409 and conflict.json()["code"] == "SUBMISSION_CONFLICT"


def test_concurrent_same_command_is_single_fact(h, tmp_path):
    s = h.create_scene(tag="concurrent", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3]])
    b = command(s, v)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: h.confirm_import(v["importId"], b), range(2)))
    assert [x.status_code for x in replies] == [200, 200]
    assert len({x.json()["revisionId"] for x in replies}) == 1
    assert sorted(x.json()["replayed"] for x in replies) == [False, True]
    assert h.count("score_revisions") == 1 and h.count("student_item_scores") == 3


def test_concurrent_distinct_commands_preserve_first(h, tmp_path):
    s = h.create_scene(tag="dual", students=[("甲", "00001")])
    a = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3]])
    b = upload(h, s, tmp_path, [["00001", "甲", 0, 3, 5]])
    with ThreadPoolExecutor(max_workers=2) as pool:
        fs = [pool.submit(h.confirm_import, v["importId"], command(s, v, v["importId"])) for v in [a, b]]
        rs = [f.result() for f in fs]
    assert sorted(x.status_code for x in rs) == [200, 409]
    assert h.count("score_revisions") == 1 and h.count("student_item_scores") == 3
    winner = next(x.json() for x in rs if x.status_code == 200)
    assert h.assessment(s.assessment["assessmentId"])["activeScoreRevisionId"] == winner["revisionId"]


@pytest.mark.parametrize("text", ["", "缺考", "免考", " "])
def test_nonnumeric_recorded_correction_is_located_zero_write(h, tmp_path, text):
    s = h.create_scene(tag="correctionbad", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3]])
    base = published(h, s, v)
    before = state(h)
    r = h.correct_scores(s.assessment["assessmentId"], {"submissionId": "correct-invalid", "expectedAssessmentRevision": base["assessmentRevision"], "baseScoreRevisionId": base["revisionId"], "reason": "V00 verified error", "corrections": [{"participantId": s.participant_id("00001"), "itemId": "it-correctionbad-1", "status": "recorded", "scoreText": text}]})
    assert r.status_code == 422 and r.json()["code"] == "SCORE_CELL_INVALID"
    assert r.json()["details"]["issues"][0]["field"] == "scoreText"
    assert state(h) == before


def test_correction_audit_full_copy_old_snapshot_fixed_paper(h, tmp_path):
    s = h.create_scene(tag="correct", students=[("甲", "00001"), ("乙", "00002")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3], ["00002", "乙", 2, 3, 5]])
    base = published(h, s, v)
    old = matrix(h, base["revisionId"])
    s.assessment = h.assessment(s.assessment["assessmentId"])
    r = h.client.post(f'/api/v1/assessments/{s.assessment["assessmentId"]}/participants', json={"submissionId": "retake", "expectedRevision": s.assessment["revision"], "participants": [h.participant(s.student_id("00001"), s.klass["id"], attempt_no=2)]})
    assert r.status_code == 200, r.text
    s.assessment = r.json()["assessment"]
    b = {"submissionId": "correct-zero", "expectedAssessmentRevision": s.assessment["revision"], "baseScoreRevisionId": base["revisionId"], "reason": "核对原表C2误写", "corrections": [{"participantId": s.participant_id("00001"), "itemId": "it-correct-1", "status": "recorded", "scoreText": "0"}]}
    r = h.client.post(f'/api/v1/assessments/{s.assessment["assessmentId"]}/score-corrections', json=b)
    assert r.status_code == 200, r.text
    new = matrix(h, r.json()["revisionId"])
    assert new["total"] == 3 and len(new["items"]) == 3
    by_id = {x["participant"]["participantId"]: x for x in new["rows"]}
    assert [x["scoreUnits"] for x in by_id[s.participant_id("00001")]["cells"]] == [0, 200, 300]
    assert [x["status"] for x in next(x for x in new["rows"] if x["participant"]["attemptNo"] == 2)["cells"]] == ["missing"] * 3
    assert matrix(h, base["revisionId"]) == old
    audit = h.raw_rows("SELECT * FROM score_revision_corrections")
    assert len(audit) == 1 and audit[0]["reason"] == b["reason"]
    assert new["revision"]["paperRevisionId"] == old["revision"]["paperRevisionId"] == s.paper.revision_id
    replay = h.client.post(f'/api/v1/assessments/{s.assessment["assessmentId"]}/score-corrections', json=b)
    assert replay.status_code == 200 and replay.json()["replayed"]
    assert h.count("score_revisions") == 2 and h.count("student_item_scores") == 15


def test_total_exact_decimal_attendance_and_refresh_versions(h, tmp_path):
    s = h.create_scene(tag="meta", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", "0.1", "0.2", "0.3", "0.61", "正常"]], ["学号", "姓名", "Q1", "Q2", "Q3", "总分", "出勤"])
    assert any(x["code"] == "SCORE_TOTAL_MISMATCH" and x["row"] == 2 and x["column"] == "F" for x in v["issues"])
    assert h.confirm_import(v["importId"], command(s, v)).status_code == 422
    r = h.patch_import(v["importId"], {"expectedRevision": 0, "rows": [{"rowNo": 2, "cells": [{"row": 2, "column": "F", "text": "0.60"}]}]})
    assert r.status_code == 200 and r.json()["issues"] == []
    v = r.json()
    b = {"expectedRevision": s.assessment["revision"], "submissionId": "attendance", "attendance": "absent", "reason": "校验缺考证据"}
    oldparticipant = h.raw_rows("SELECT * FROM assessment_participants")[0]
    r = h.client.patch(f'/api/v1/assessments/{s.assessment["assessmentId"]}/participants/{s.participant_id("00001")}/attendance', json=b)
    assert r.status_code == 200, r.text
    changed = h.raw_rows("SELECT * FROM assessment_participants")[0]
    assert {k: x for k, x in oldparticipant.items() if k != "attendance"} == {k: x for k, x in changed.items() if k != "attendance"}
    assert changed["attendance"] == "absent"
    savedcommand = h.raw_rows("SELECT * FROM command_submissions WHERE operation='assessment.participant_attendance'")
    assert len(savedcommand) == 1 and "校验缺考证据" in json.dumps(savedcommand, ensure_ascii=False)
    replay = h.client.patch(f'/api/v1/assessments/{s.assessment["assessmentId"]}/participants/{s.participant_id("00001")}/attendance', json=b)
    assert replay.status_code == 200 and replay.json()["replayed"]
    s.assessment = r.json()["assessment"]
    stale = h.get_import(v["importId"]).json()
    assert stale["requiredAcknowledgements"] == v["requiredAcknowledgements"] and stale["previewVersion"] == v["previewVersion"]
    assert h.confirm_import(v["importId"], command(s, stale)).status_code == 409
    refbody = {"expectedImportRevision": v["revision"], "expectedAssessmentRevision": s.assessment["revision"], "baseScoreRevisionId": None}
    for field in ["expectedImportRevision", "expectedAssessmentRevision"]:
        before = state(h)
        bad = {**refbody, field: refbody[field] + 1}
        assert h.client.post(f'/api/v1/score-imports/{v["importId"]}/refresh', json=bad).status_code == 409
        assert state(h) == before
    refreshed = h.client.post(f'/api/v1/score-imports/{v["importId"]}/refresh', json=refbody)
    assert refreshed.status_code == 200, refreshed.text
    fresh = refreshed.json()
    assert (fresh["revision"], fresh["previewVersion"]) == (v["revision"] + 1, v["previewVersion"] + 1)
    assert any(x["code"] == "SCORE_ATTENDANCE_MISMATCH" for x in fresh["issues"])
    rows = h.list_import_rows(v["importId"]).json()["items"]
    assert next(x for x in rows[0]["cells"] if x["column"] == "F")["correctedText"] == "0.60"


def test_attendance_injected_failure_rolls_back_audit_and_minimal_row(h, monkeypatch):
    s = h.create_scene(tag="auditatomic", students=[("甲", "00001")])
    before = state(h)
    service = h.app.state.assessment_service
    original = service._assessments.bump_revision_in
    def fail_after_update(conn, aid):
        original(conn, aid)
        raise AppError("V00 attendance fault", code="V00_ATTENDANCE_FAULT", status_code=503)
    monkeypatch.setattr(service._assessments, "bump_revision_in", fail_after_update)
    r = h.client.patch(f'/api/v1/assessments/{s.assessment["assessmentId"]}/participants/{s.participant_id("00001")}/attendance', json={"expectedRevision": s.assessment["revision"], "submissionId": "attendance-fault", "attendance": "absent", "reason": "V00故障注入"})
    assert r.status_code == 503 and r.json()["code"] == "V00_ATTENDANCE_FAULT"
    assert state(h) == before


def test_active_pointer_composite_fk_and_confirmed_gate(h, tmp_path):
    one = h.create_scene(tag="fk1", students=[("甲", "00001")])
    two = h.create_scene(tag="fk2", students=[("乙", "00002")])
    rid = published(h, one, upload(h, one, tmp_path, [["00001", "甲", 1, 2, 3]]))["revisionId"]
    before = state(h)
    with pytest.raises(sqlite3.IntegrityError):
        h.raw_execute("UPDATE assessments SET active_score_revision_id=? WHERE id=?", (rid, two.assessment["assessmentId"]))
    assert state(h) == before
    conn = sqlite3.connect(h.db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        fks = conn.execute("PRAGMA foreign_key_list(assessments)").fetchall()
        assert any(x[2] == "score_revisions" and x[3] == "active_score_revision_id" for x in fks)
        assert any(x[2] == "score_revisions" and x[3] == "id" and x[4] == "assessment_id" for x in fks)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    finally:
        conn.close()


def test_patch_stale_context_does_not_implicitly_refresh(h, tmp_path):
    s = h.create_scene(tag="stalepatch", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3]])
    changed = h.client.post(f'/api/v1/assessments/{s.assessment["assessmentId"]}/participants', json={"expectedRevision": s.assessment["revision"], "submissionId": "newattempt", "participants": [h.participant(s.student_id("00001"), s.klass["id"], attempt_no=2)]})
    assert changed.status_code == 200, changed.text
    before = state(h)
    r = h.patch_import(v["importId"], {"expectedRevision": v["revision"], "rows": [{"rowNo": 2, "cells": [{"row": 2, "column": "C", "text": "0"}]}]})
    capture("stale-patch-must-not-refresh", r)
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "SCORE_ASSESSMENT_REVISION_CONFLICT"
    assert state(h) == before


def test_patch_rechecks_context_after_preview(h, tmp_path, monkeypatch):
    s = h.create_scene(tag="patchrace", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3]])
    svc = h.service()
    summary = svc._summary_payload
    def crossed(**kwargs):
        result = summary(**kwargs)
        h.app.state.assessment_service.correct_participant_attendance(s.assessment["assessmentId"], s.participant_id("00001"), ParticipantAttendanceRequest(expectedRevision=s.assessment["revision"], submissionId="racingattendance", attendance="absent", reason="V00 interleave"))
        return result
    monkeypatch.setattr(svc, "_summary_payload", crossed)
    beforeimports = h.raw_rows("SELECT * FROM score_imports")
    beforerows = h.raw_rows("SELECT * FROM score_import_rows")
    r = h.patch_import(v["importId"], {"expectedRevision": v["revision"], "rows": [{"rowNo": 2, "cells": [{"row": 2, "column": "C", "text": "0"}]}]})
    capture("patch-context-race-must-rollback", r)
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "SCORE_ASSESSMENT_REVISION_CONFLICT"
    assert h.raw_rows("SELECT * FROM score_imports") == beforeimports
    assert h.raw_rows("SELECT * FROM score_import_rows") == beforerows
    assert h.count("score_revisions") == 0


def test_formula_cache_preserves_original_and_no_cache_rejects(h, tmp_path):
    s = h.create_scene(tag="formulaind", students=[("甲", "00001")])
    path = write_score_xlsx(tmp_path / "formula.xlsx", ["学号", "姓名", "Q1", "Q2", "Q3"], [["00001", "甲", "=1+0.25", 2, 3]])
    no = h.upload_scores(s.assessment["assessmentId"], path)
    assert no.status_code == 422 and no.json()["code"] == "SCORE_CELL_INVALID"
    assert h.count("score_imports") == 0
    inject_cached_values(path, {"C2": "1.25"})
    ok = h.upload_scores(s.assessment["assessmentId"], path)
    assert ok.status_code == 201, ok.text
    v = ok.json()
    originalhash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert v["fileAsset"]["sha256"] == originalhash
    cell = h.list_import_rows(v["importId"]).json()["items"][0]["cells"][0]
    assert (cell["originalText"], cell["originalCachedText"], cell["isFormula"], cell["scoreUnits"]) == ("=1+0.25", "1.25", True, 125)
    result = published(h, s, v)
    assert matrix(h, result["revisionId"])["rows"][0]["cells"][0]["scoreUnits"] == 125


def test_same_name_never_guessed_and_each_row_can_be_assigned(h, tmp_path):
    s = h.create_scene(tag="samenames", students=[("同名", "00001"), ("同名", "00002")])
    v = upload(h, s, tmp_path, [["", "同名", 1, 2, 3], ["", "同名", 0, 3, 5]])
    assert all(x["participantId"] is None and len(x["candidates"]) == 2 for x in h.list_import_rows(v["importId"]).json()["items"])
    assert h.confirm_import(v["importId"], command(s, v)).status_code == 422
    r = h.patch_import(v["importId"], {"expectedRevision": 0, "rows": [{"rowNo": 2, "participantId": s.participant_id("00001")}, {"rowNo": 3, "participantId": s.participant_id("00002")}]})
    assert r.status_code == 200, r.text
    m = matrix(h, published(h, s, r.json())["revisionId"])
    byno = {x["participant"]["studentNo"]: x for x in m["rows"]}
    assert [x["scoreUnits"] for x in byno["00001"]["cells"]] == [100, 200, 300]
    assert [x["scoreUnits"] for x in byno["00002"]["cells"]] == [0, 300, 500]


def test_retake_not_auto_latest_duplicate_rows_need_distinct_ids(h, tmp_path):
    s = h.create_scene(tag="multi", students=[("甲", "00001")])
    add = h.client.post(f'/api/v1/assessments/{s.assessment["assessmentId"]}/participants', json={"submissionId": "attempt2", "expectedRevision": s.assessment["revision"], "participants": [h.participant(s.student_id("00001"), s.klass["id"], attempt_no=2)]})
    assert add.status_code == 200
    second = add.json()["participants"][0]
    s.assessment = add.json()["assessment"]
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3], ["00001", "甲", 0, 3, 5]])
    rows = h.list_import_rows(v["importId"]).json()["items"]
    assert all(x["participantId"] is None and len(x["candidates"]) == 2 for x in rows)
    bad = h.patch_import(v["importId"], {"expectedRevision": 0, "rows": [{"rowNo": 2, "participantId": s.participant_id("00001")}, {"rowNo": 3, "participantId": s.participant_id("00001")}]})
    assert bad.status_code == 200
    duplicate_confirm = h.confirm_import(v["importId"], command(s, bad.json()))
    capture("explicit-duplicate-physical-rows", duplicate_confirm)
    assert duplicate_confirm.status_code == 422
    fixed = h.patch_import(v["importId"], {"expectedRevision": 1, "rows": [{"rowNo": 3, "participantId": second["participantId"]}]})
    assert fixed.status_code == 200, fixed.text
    m = matrix(h, published(h, s, fixed.json())["revisionId"])
    byattempt = {x["participant"]["attemptNo"]: x for x in m["rows"]}
    assert [x["scoreUnits"] for x in byattempt[1]["cells"]] == [100, 200, 300]
    assert [x["scoreUnits"] for x in byattempt[2]["cells"]] == [0, 300, 500]


@pytest.mark.parametrize("patch", [
    {"rowNo": 99, "cells": [{"row": 99, "column": "C", "text": "0"}]},
    {"rowNo": 2, "cells": [{"row": 3, "column": "C", "text": "0"}]},
    {"rowNo": 2, "cells": [{"row": 2, "column": "F", "text": "0"}]},
    {"rowNo": 2, "participantId": "unknown-participant"},
])
def test_physical_patch_bounds_and_participant_ownership(h, tmp_path, patch):
    s = h.create_scene(tag="bounds", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3]])
    before = state(h)
    r = h.patch_import(v["importId"], {"expectedRevision": 0, "rows": [patch]})
    assert r.status_code == 422, r.text
    assert len(r.json()["details"]["issues"]) > 0
    assert state(h) == before


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"limit": 201}])
def test_preview_and_matrix_page_bounds(h, tmp_path, params):
    s = h.create_scene(tag="pages", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3]])
    result = published(h, s, v)
    for route in [f'/api/v1/score-imports/{v["importId"]}/rows', f'/api/v1/score-revisions/{result["revisionId"]}/matrix']:
        response = h.client.get(route, params=params)
        assert response.status_code == 422, response.text


def test_confirmed_gate_rejects_draft_active_pointer(h):
    s = h.create_scene(tag="draftgate", students=[("甲", "00001")])
    h.raw_execute("INSERT INTO score_revisions(id,assessment_id,version,state) VALUES('draft-rid',?,1,'draft')", (s.assessment["assessmentId"],))
    before = h.raw_rows("SELECT * FROM assessments")
    with pytest.raises(sqlite3.IntegrityError, match="SCORE_REVISION_NOT_CONFIRMED"):
        h.raw_execute("UPDATE assessments SET active_score_revision_id='draft-rid' WHERE id=?", (s.assessment["assessmentId"],))
    assert h.raw_rows("SELECT * FROM assessments") == before


def test_actual_duplicate_physical_rows_cannot_discard_second_scores(h, tmp_path):
    s = h.create_scene(tag="actualduplicate", students=[("甲", "00001")])
    v = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3], ["00001", "甲", 2, 3, 5]])
    before = state(h)
    r = h.confirm_import(v["importId"], command(s, v))
    capture("duplicate-actual-confirm", r)
    if r.status_code == 200:
        EVENTS.append({"case": "duplicate-discarded-second-scores-matrix", "body": matrix(h, r.json()["revisionId"])})
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "SCORE_ROW_DUPLICATE_PARTICIPANT"
    assert state(h) == before
    assert {x.get("row") for x in r.json()["details"]["issues"]} == {2, 3}


def test_duplicate_identity_headers_enter_manual_mapping_not_500(h):
    s = h.create_scene(tag="dupidentity", students=[("甲", "00001")])
    source = "学号,学号,称呼,Q1,Q2,Q3\n00001,00001,甲,1,2,3\n".encode("utf-8-sig")
    r = h.client.post(f'/api/v1/assessments/{s.assessment["assessmentId"]}/score-imports', files={"file": ("dupheaders.csv", source, "text/csv")})
    v = capture("duplicate-identity-header", r)
    assert r.status_code == 201, r.text
    assert v["mapping"] is None
    mapping = {"workSheet": "CSV", "headerRow": 1, "studentNoColumn": "A", "nameColumn": "C", "itemColumns": [{"itemId": f"it-dupidentity-{n}", "column": c} for n, c in [(1, "D"), (2, "E"), (3, "F")]]}
    fixed = h.patch_import(v["importId"], {"expectedRevision": 0, "mapping": mapping})
    assert fixed.status_code == 200, fixed.text
    confirmed = published(h, s, fixed.json())
    assert [x["scoreUnits"] for x in matrix(h, confirmed["revisionId"])["rows"][0]["cells"]] == [100, 200, 300]


def test_refresh_cannot_replace_active_base_with_new_revision(h, tmp_path):
    s = h.create_scene(tag="baseind", students=[("甲", "00001")])
    a = upload(h, s, tmp_path, [["00001", "甲", 1, 2, 3]])
    b = upload(h, s, tmp_path, [["00001", "甲", 0, 3, 5]])
    committed = published(h, s, a)
    before = state(h)
    for requested_base in [None, committed["revisionId"]]:
        r = h.client.post(f'/api/v1/score-imports/{b["importId"]}/refresh', json={"expectedImportRevision": b["revision"], "expectedAssessmentRevision": committed["assessmentRevision"], "baseScoreRevisionId": requested_base})
        assert r.status_code == 409 and r.json()["code"] == "SCORE_BASE_REVISION_CONFLICT"
        assert state(h) == before
