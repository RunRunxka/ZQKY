"""B3 R03–R07 的正确行为回归：真 HTTP、临时四库与受管原件。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.contracts.assessments import ParticipantAttendanceRequest
from tests.scores_support import SAMPLE_HEADER, ScoreScene, ScoresHarness, write_score_xlsx


@pytest.fixture()
def harness(tmp_path: Path):
    with ScoresHarness(tmp_path) as running:
        yield running


def _confirm(harness: ScoresHarness, scene: ScoreScene, view: dict[str, Any]):
    return harness.confirm_import(view["importId"], {
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": view["baseScoreRevisionId"],
        "previewVersion": view["previewVersion"],
        "submissionId": "confirm-" + view["importId"],
        **view.get("requiredAcknowledgements", {"absences": [], "missing": None}),
    })


def _upload(harness: ScoresHarness, scene: ScoreScene, tmp_path: Path):
    path = write_score_xlsx(tmp_path / "scores.xlsx", SAMPLE_HEADER, [["0001", "甲", 1, 2, 3]])
    response = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert response.status_code == 201, response.text
    return response.json()


def _units(harness: ScoresHarness, revision_id: str) -> list[list[int | None]]:
    matrix = harness.score_matrix(revision_id).json()
    rows = sorted(matrix["rows"], key=lambda row: (row["participant"]["studentNo"], row["participant"]["attemptNo"]))
    return [[cell["scoreUnits"] for cell in row["cells"]] for row in rows]


@pytest.mark.parametrize("conflict", ["score-score", "score-identity", "identity-identity"])
def test_column_case_conflicts_are_located_and_do_not_publish(
    harness: ScoresHarness, tmp_path: Path, conflict: str,
) -> None:
    scene = harness.create_scene(tag="case", students=[("甲", "0001")])
    view = _upload(harness, scene, tmp_path)
    mapping = view["mapping"]
    if conflict == "score-score":
        mapping["itemColumns"][1]["column"] = "c"
        column = "C"
    elif conflict == "score-identity":
        mapping["itemColumns"][0]["column"] = "a"
        column = "A"
    else:
        mapping["nameColumn"] = "a"
        column = "A"
    response = harness.patch_import(view["importId"], {"expectedRevision": view["revision"], "mapping": mapping})
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "SCORE_MAPPING_INVALID"
    assert any(issue.get("column") == column for issue in response.json()["details"]["issues"])
    assert harness.count("score_revisions") == 0
    unchanged = harness.client.get(f'/api/v1/score-imports/{view["importId"]}').json()
    assert unchanged["revision"] == view["revision"]


def test_legal_lowercase_mapping_is_canonical_and_preserves_physical_scores(
    harness: ScoresHarness, tmp_path: Path,
) -> None:
    scene = harness.create_scene(tag="lower", students=[("甲", "0001")])
    view = _upload(harness, scene, tmp_path)
    mapping = view["mapping"]
    mapping["studentNoColumn"] = "a"
    mapping["nameColumn"] = "b"
    for entry in mapping["itemColumns"]:
        entry["column"] = entry["column"].lower()
    patched = harness.patch_import(view["importId"], {"expectedRevision": 0, "mapping": mapping})
    assert patched.status_code == 200, patched.text
    saved = patched.json()["mapping"]
    assert (saved["studentNoColumn"], saved["nameColumn"]) == ("A", "B")
    assert [entry["column"] for entry in saved["itemColumns"]] == ["C", "D", "E"]
    published = _confirm(harness, scene, patched.json())
    assert published.status_code == 200, published.text
    assert _units(harness, published.json()["revisionId"]) == [[100, 200, 300]]


def test_same_sheet_header_change_reextracts_physical_student_rows(
    harness: ScoresHarness, tmp_path: Path,
) -> None:
    scene = harness.create_scene(tag="header", students=[("甲", "0001"), ("乙", "0002")])
    path = write_score_xlsx(tmp_path / "two-headers.xlsx", ["学号", "姓名", "小题得分", "", ""], [
        SAMPLE_HEADER, ["0001", "甲", 1, 2, 3], ["0002", "乙", 2, 3, 4],
    ])
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    mapping = {**view["mapping"], "headerRow": 2, "itemColumns": [
        {"itemId": f"it-header-{index}", "column": column}
        for index, column in enumerate(("C", "D", "E"), 1)
    ]}
    patched = harness.patch_import(view["importId"], {"expectedRevision": 0, "mapping": mapping})
    assert patched.status_code == 200, patched.text
    assert [row["rowNo"] for row in harness.list_import_rows(view["importId"]).json()["items"]] == [3, 4]
    published = _confirm(harness, scene, patched.json())
    assert published.status_code == 200, published.text
    assert _units(harness, published.json()["revisionId"]) == [[100, 200, 300], [200, 300, 400]]


def test_identity_mapping_change_reextracts_rows_and_preserves_coordinate_edits(
    harness: ScoresHarness, tmp_path: Path,
) -> None:
    scene = harness.create_scene(tag="identity", students=[("甲", "0001"), ("乙", "0002")])
    path = write_score_xlsx(tmp_path / "identity.xlsx", [*SAMPLE_HEADER, "实际姓名"], [
        ["", "备注", "", "", "", ""],
        ["", "", "", "", "", "甲"],
        ["0002", "", 2, 3, 4, "乙"],
    ])
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    assert [row["rowNo"] for row in harness.list_import_rows(view["importId"]).json()["items"]] == [2, 4]
    edited = harness.patch_import(view["importId"], {"expectedRevision": 0, "rows": [{
        "rowNo": 4, "participantId": scene.participant_id("0002"),
        "cells": [{"row": 4, "column": "C", "text": "0"}],
    }]})
    assert edited.status_code == 200, edited.text
    mapping = {**edited.json()["mapping"], "nameColumn": "F"}
    patched = harness.patch_import(view["importId"], {"expectedRevision": 1, "mapping": mapping, "rows": [{
        "rowNo": 3, "cells": [{"row": 3, "column": column, "text": value}
                              for column, value in zip(("C", "D", "E"), ("1", "2", "3"))],
    }]})
    assert patched.status_code == 200, patched.text
    rows = harness.list_import_rows(view["importId"]).json()["items"]
    assert [row["rowNo"] for row in rows] == [3, 4]
    assert rows[1]["participantId"] == scene.participant_id("0002")
    published = _confirm(harness, scene, patched.json())
    assert published.status_code == 200, published.text
    assert _units(harness, published.json()["revisionId"]) == [[100, 200, 300], [0, 300, 400]]


@pytest.mark.parametrize("identity", ["unknown", "duplicate"])
def test_incomplete_identity_detection_stays_recoverable_through_manual_mapping(
    harness: ScoresHarness, tmp_path: Path, identity: str,
) -> None:
    scene = harness.create_scene(tag="unknown", students=[("甲", "0001")])
    if identity == "unknown":
        header = "身份代号,学生称呼,Q1,Q2,Q3"
        data = "0001,甲,1,2,3"
        name_column, columns = "B", ("C", "D", "E")
    else:
        header = "学号,学号,姓名,姓名,Q1,Q2,Q3"
        data = "0001,0001,甲,甲,1,2,3"
        name_column, columns = "C", ("E", "F", "G")
    content = (header + "\r\n" + data + "\r\n").encode("utf-8")
    client = TestClient(harness.app, base_url="http://127.0.0.1:8001", raise_server_exceptions=False)
    uploaded = client.post(f'/api/v1/assessments/{scene.assessment["assessmentId"]}/score-imports',
                           files={"file": ("manual.csv", content, "text/csv")})
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    assert view["mapping"] is None
    assert any("学号" in warning for warning in view["warnings"])
    assert view["rowCount"] == 1
    evidence = harness.list_import_rows(view["importId"]).json()["items"][0]["cells"]
    assert [cell["originalText"] for cell in evidence] == data.split(",")
    assert all(cell["effectiveStatus"] is None for cell in evidence)
    patched = harness.patch_import(view["importId"], {"expectedRevision": 0, "mapping": {
        "workSheet": "CSV", "headerRow": 1, "studentNoColumn": "A", "nameColumn": name_column,
        "itemColumns": [{"itemId": f"it-unknown-{index}", "column": column}
                        for index, column in enumerate(columns, 1)],
    }})
    assert patched.status_code == 200, patched.text
    assert patched.json()["resolvedRowCount"] == 1
    published = _confirm(harness, scene, patched.json())
    assert published.status_code == 200, published.text
    assert _units(harness, published.json()["revisionId"]) == [[100, 200, 300]]


@pytest.mark.parametrize("encoding", ["utf-8-sig", "gb18030"])
def test_csv_chinese_evidence_and_authoritative_acknowledgements(
    harness: ScoresHarness, encoding: str,
) -> None:
    scene = harness.create_scene(tag="csv", students=[("甲", "0001"), ("乙", "0002"), ("丙", "0003"), ("丁", "0004")])
    content = ("学号,姓名,Q1,Q2,Q3\r\n0001,甲,缺考,,\r\n0002,乙,免考,,\r\n"
               "0003,丙,0,3,5\r\n0004,丁,2,,5\r\n").encode(encoding)
    client = TestClient(harness.app, base_url="http://127.0.0.1:8001", raise_server_exceptions=False)
    uploaded = client.post(f'/api/v1/assessments/{scene.assessment["assessmentId"]}/score-imports',
                           files={"file": ("chinese.csv", content, "text/csv")})
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    assert view["fileAsset"]["sha256"] == hashlib.sha256(content).hexdigest()
    assert view["missingCellCount"] == 1
    rows = harness.list_import_rows(view["importId"]).json()["items"]
    assert [row["participantName"] for row in rows] == ["甲", "乙", "丙", "丁"]
    assert [rows[index]["cells"][0]["text"] for index in (0, 1)] == ["缺考", "免考"]
    assert [cell["effectiveStatus"] for cell in rows[0]["cells"]] == ["absent"] * 3
    assert [cell["effectiveStatus"] for cell in rows[1]["cells"]] == ["exempt"] * 3
    assert rows[2]["cells"][0]["effectiveStatus"] == "recorded"
    assert rows[2]["cells"][0]["scoreUnits"] == 0
    required = view["requiredAcknowledgements"]
    assert required["absences"] == [{"classId": scene.klass["id"], "participantIds": [scene.participant_id("0001")]}]
    assert required["missing"] == {"participantIds": [scene.participant_id("0004")], "cellCount": 1}
    published = _confirm(harness, scene, view)
    assert published.status_code == 200, published.text
    matrix = harness.score_matrix(published.json()["revisionId"]).json()
    ordered = sorted(matrix["rows"], key=lambda row: row["participant"]["studentNo"])
    assert [[cell["status"] for cell in row["cells"]] for row in ordered] == [
        ["absent"] * 3, ["exempt"] * 3, ["recorded"] * 3, ["recorded", "missing", "recorded"],
    ]
    assert _units(harness, published.json()["revisionId"])[2] == [0, 300, 500]


def test_undecodable_csv_is_located_422_and_creates_no_import(harness: ScoresHarness) -> None:
    scene = harness.create_scene(tag="badcsv", students=[("甲", "0001")])
    uploaded = harness.client.post(f'/api/v1/assessments/{scene.assessment["assessmentId"]}/score-imports',
                                   files={"file": ("bad.csv", b"\xff", "text/csv")})
    assert uploaded.status_code == 422, uploaded.text
    assert uploaded.json()["code"] == "TABLE_PARSE_FAILED"
    assert harness.count("score_imports") == 0


@pytest.mark.parametrize("score_text", ["", "   ", "缺考", "免考"])
def test_recorded_nonnumeric_correction_is_located_422_with_zero_writes(
    harness: ScoresHarness, tmp_path: Path, score_text: str,
) -> None:
    scene = harness.create_scene(tag="correction", students=[("甲", "0001")])
    published = _confirm(harness, scene, _upload(harness, scene, tmp_path))
    assert published.status_code == 200, published.text
    base = published.json()
    client = TestClient(harness.app, base_url="http://127.0.0.1:8001", raise_server_exceptions=False)
    response = client.post(f'/api/v1/assessments/{scene.assessment["assessmentId"]}/score-revisions/correct', json={
        "baseScoreRevisionId": base["revisionId"], "expectedAssessmentRevision": base["assessmentRevision"],
        "submissionId": "bad-correction", "reason": "成绩校对", "corrections": [{
            "participantId": scene.participant_id("0001"), "itemId": "it-correction-1",
            "status": "recorded", "scoreText": score_text,
        }],
    })
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "SCORE_CELL_INVALID"
    assert response.json()["details"]["issues"][0]["field"] == "scoreText"
    assert harness.count("score_revisions") == 1
    assert harness.count("score_revision_corrections") == 0
    assert harness.assessment(scene.assessment["assessmentId"])["activeScoreRevisionId"] == base["revisionId"]
    assert _units(harness, base["revisionId"]) == [[100, 200, 300]]


def test_recorded_zero_correction_remains_valid(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = harness.create_scene(tag="zero", students=[("甲", "0001")])
    published = _confirm(harness, scene, _upload(harness, scene, tmp_path))
    assert published.status_code == 200, published.text
    base = published.json()
    response = harness.correct_scores(scene.assessment["assessmentId"], {
        "baseScoreRevisionId": base["revisionId"], "expectedAssessmentRevision": base["assessmentRevision"],
        "submissionId": "zero-correction", "reason": "改正为显式零分", "corrections": [{
            "participantId": scene.participant_id("0001"), "itemId": "it-zero-1",
            "status": "recorded", "scoreText": "0",
        }],
    })
    assert response.status_code == 200, response.text
    assert _units(harness, response.json()["revisionId"]) == [[0, 200, 300]]
    assert harness.count("score_revision_corrections") == 1


@pytest.mark.parametrize("total_text", ["9", "11"])
def test_explicit_total_mismatch_is_located_recoverable_and_blocks_confirmation(
    harness: ScoresHarness, tmp_path: Path, total_text: str,
) -> None:
    scene = harness.create_scene(tag="total", students=[("甲", "0001")])
    path = write_score_xlsx(tmp_path / "total.xlsx", [*SAMPLE_HEADER, "总分"], [["0001", "甲", 1, 2, 3, total_text]])
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    assert view["mapping"]["totalColumn"] == "F"
    issue = next(issue for issue in view["issues"] if issue["code"] == "SCORE_TOTAL_MISMATCH")
    assert (issue["row"], issue["column"], issue["field"]) == (2, "F", "totalColumn")
    blocked = _confirm(harness, scene, view)
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == "SCORE_TOTAL_MISMATCH"
    assert harness.count("score_revisions") == 0
    patched = harness.patch_import(view["importId"], {"expectedRevision": 0, "rows": [{
        "rowNo": 2, "cells": [{"row": 2, "column": "F", "text": "6"}],
    }]})
    assert patched.status_code == 200, patched.text
    rows = harness.list_import_rows(view["importId"]).json()["items"]
    total = next(cell for cell in rows[0]["cells"] if cell["column"] == "F")
    assert (total["originalText"], total["correctedText"], total["text"]) == (total_text, "6", "6")
    assert total["effectiveStatus"] is None
    published = _confirm(harness, scene, patched.json())
    assert published.status_code == 200, published.text
    assert _units(harness, published.json()["revisionId"]) == [[100, 200, 300]]


@pytest.mark.parametrize("total_text", ["0.60", ""])
def test_optional_total_uses_exact_decimal_units_or_allows_blank(
    harness: ScoresHarness, tmp_path: Path, total_text: str,
) -> None:
    scene = harness.create_scene(tag="decimal", students=[("甲", "0001")])
    path = write_score_xlsx(tmp_path / "decimal.xlsx", [*SAMPLE_HEADER, "合计"], [["0001", "甲", "0.1", "0.2", "0.3", total_text]])
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    assert view["issues"] == []
    published = _confirm(harness, scene, view)
    assert published.status_code == 200, published.text
    assert _units(harness, published.json()["revisionId"]) == [[10, 20, 30]]
    matrix = harness.score_matrix(published.json()["revisionId"]).json()
    assert matrix["rows"][0]["participant"]["totalUnits"] == 60


def test_total_with_incomplete_items_warns_without_imputing(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = harness.create_scene(tag="incomplete", students=[("甲", "0001")])
    path = write_score_xlsx(tmp_path / "incomplete.xlsx", [*SAMPLE_HEADER, "总分"], [["0001", "甲", 1, None, 3, 9]])
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    assert any("无法核对" in warning for warning in view["warnings"])
    assert view["missingCellCount"] == 1
    published = _confirm(harness, scene, view)
    assert published.status_code == 200, published.text
    assert _units(harness, published.json()["revisionId"]) == [[100, None, 300]]
    assert harness.score_matrix(published.json()["revisionId"]).json()["rows"][0]["participant"]["totalUnits"] is None


def test_illegal_total_is_422_with_physical_location(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = harness.create_scene(tag="badtotal", students=[("甲", "0001")])
    path = write_score_xlsx(tmp_path / "badtotal.xlsx", [*SAMPLE_HEADER, "总分"], [["0001", "甲", 1, 2, 3, "优秀"]])
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert uploaded.status_code == 422, uploaded.text
    assert uploaded.json()["code"] == "SCORE_CELL_INVALID"
    issue = uploaded.json()["details"]["issues"][0]
    assert (issue["row"], issue["column"], issue["field"]) == (2, "F", "totalColumn")
    assert harness.count("score_imports") == 0


@pytest.mark.parametrize("field,column", [("totalColumn", "c"), ("attendanceColumn", "a"), ("attendanceColumn", "f")])
def test_metadata_columns_share_physical_occupancy_validation(
    harness: ScoresHarness, tmp_path: Path, field: str, column: str,
) -> None:
    scene = harness.create_scene(tag="metadata", students=[("甲", "0001")])
    path = write_score_xlsx(tmp_path / "metadata.xlsx", [*SAMPLE_HEADER, "总分", "出勤"], [["0001", "甲", 1, 2, 3, 6, "正常"]])
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    mapping = {**view["mapping"], field: column}
    patched = harness.patch_import(view["importId"], {"expectedRevision": 0, "mapping": mapping})
    assert patched.status_code == 422, patched.text
    assert patched.json()["code"] == "SCORE_MAPPING_INVALID"
    assert any(issue.get("column") == column.upper() for issue in patched.json()["details"]["issues"])


def test_attendance_mismatch_requires_explicit_correction_and_refresh_before_confirm(
    harness: ScoresHarness, tmp_path: Path,
) -> None:
    scene = harness.create_scene(tag="attendance", students=[("甲", "0001")])
    path = write_score_xlsx(tmp_path / "attendance.xlsx", [*SAMPLE_HEADER, "出勤"], [["0001", "甲", None, None, None, "缺考"]])
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    assert view["missingCellCount"] == 3
    issue = next(issue for issue in view["issues"] if issue["code"] == "SCORE_ATTENDANCE_MISMATCH")
    assert (issue["row"], issue["column"]) == (2, "F")
    assert _confirm(harness, scene, view).status_code == 422
    corrected = harness.client.patch(
        f'/api/v1/assessments/{scene.assessment["assessmentId"]}/participants/{scene.participant_id("0001")}/attendance',
        json={"expectedRevision": scene.assessment["revision"], "submissionId": "correct-attendance",
              "attendance": "absent", "reason": "教师核对原表缺考记录"},
    )
    assert corrected.status_code == 200, corrected.text
    scene.assessment = corrected.json()["assessment"]
    stale = harness.client.get(f'/api/v1/score-imports/{view["importId"]}').json()
    assert stale["previewVersion"] == view["previewVersion"]
    assert stale["requiredAcknowledgements"] == view["requiredAcknowledgements"]
    assert stale["missingCellCount"] == 3
    bypass = _confirm(harness, scene, stale)
    assert bypass.status_code == 409, bypass.text
    assert bypass.json()["code"] == "SCORE_ASSESSMENT_REVISION_CONFLICT"
    refreshed = harness.client.post(f'/api/v1/score-imports/{view["importId"]}/refresh', json={
        "expectedImportRevision": view["revision"], "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": None,
    })
    assert refreshed.status_code == 200, refreshed.text
    fresh = refreshed.json()
    assert (fresh["revision"], fresh["previewVersion"]) == (1, 1)
    assert fresh["missingCellCount"] == 0
    assert fresh["requiredAcknowledgements"] == {"absences": [{
        "classId": scene.klass["id"], "participantIds": [scene.participant_id("0001")],
    }], "missing": None}
    assert fresh["issues"] == []
    published = _confirm(harness, scene, fresh)
    assert published.status_code == 200, published.text
    matrix = harness.score_matrix(published.json()["revisionId"]).json()
    assert [cell["status"] for cell in matrix["rows"][0]["cells"]] == ["absent"] * 3
    assert harness.client.post(f'/api/v1/score-imports/{view["importId"]}/refresh', json={
        "expectedImportRevision": fresh["revision"], "expectedAssessmentRevision": published.json()["assessmentRevision"],
        "baseScoreRevisionId": published.json()["revisionId"],
    }).status_code == 409


def test_unknown_attendance_can_be_corrected_at_original_coordinate(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = harness.create_scene(tag="badattendance", students=[("甲", "0001")])
    path = write_score_xlsx(tmp_path / "badattendance.xlsx", [*SAMPLE_HEADER, "出勤"], [["0001", "甲", 1, 2, 3, "可能出勤"]])
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    assert view["issues"][0]["column"] == "F"
    assert _confirm(harness, scene, view).status_code == 422
    patched = harness.patch_import(view["importId"], {"expectedRevision": 0, "rows": [{
        "rowNo": 2, "cells": [{"row": 2, "column": "F", "text": "present"}],
    }]})
    assert patched.status_code == 200, patched.text
    assert patched.json()["issues"] == []
    assert _confirm(harness, scene, patched.json()).status_code == 200


def test_refresh_new_attempt_preserves_edits_base_and_confirmed_historical_snapshot(
    harness: ScoresHarness, tmp_path: Path,
) -> None:
    scene = harness.create_scene(tag="retake", students=[("甲", "0001")])
    original = _confirm(harness, scene, _upload(harness, scene, tmp_path))
    assert original.status_code == 200, original.text
    base = original.json()
    scene.assessment = harness.assessment(scene.assessment["assessmentId"])
    second = _upload(harness, scene, tmp_path)
    edited = harness.patch_import(second["importId"], {"expectedRevision": 0, "rows": [{
        "rowNo": 2, "participantId": scene.participant_id("0001"),
        "cells": [{"row": 2, "column": "C", "text": "0"}],
    }]})
    assert edited.status_code == 200, edited.text
    added = harness.client.post(f'/api/v1/assessments/{scene.assessment["assessmentId"]}/participants', json={
        "expectedRevision": scene.assessment["revision"], "submissionId": "retake-participant",
        "participants": [harness.participant(scene.student_id("0001"), scene.klass["id"], attempt_no=2)],
    })
    assert added.status_code == 200, added.text
    scene.assessment = added.json()["assessment"]
    attempt = next(row for row in added.json()["participants"] if row["attemptNo"] == 2)
    stale = harness.client.get(f'/api/v1/score-imports/{second["importId"]}').json()
    assert stale["missingCellCount"] == 0
    assert _confirm(harness, scene, stale).status_code == 409
    refreshed = harness.client.post(f'/api/v1/score-imports/{second["importId"]}/refresh', json={
        "expectedImportRevision": edited.json()["revision"], "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": base["revisionId"],
    })
    assert refreshed.status_code == 200, refreshed.text
    fresh = refreshed.json()
    assert fresh["baseScoreRevisionId"] == base["revisionId"]
    assert (fresh["revision"], fresh["previewVersion"]) == (2, 2)
    assert fresh["requiredAcknowledgements"]["missing"] == {"participantIds": [attempt["participantId"]], "cellCount": 3}
    row = harness.list_import_rows(second["importId"]).json()["items"][0]
    assert row["participantId"] == scene.participant_id("0001")
    assert (row["cells"][0]["originalText"], row["cells"][0]["correctedText"], row["cells"][0]["scoreUnits"]) == ("1", "0", 0)
    published = _confirm(harness, scene, fresh)
    assert published.status_code == 200, published.text
    assert _units(harness, published.json()["revisionId"]) == [[0, 200, 300], [None, None, None]]
    historical = harness.score_matrix(base["revisionId"]).json()
    assert historical["total"] == 1
    assert historical["revision"]["paperRevisionId"] == scene.paper.revision_id
    assert _units(harness, base["revisionId"]) == [[100, 200, 300]]


def test_refresh_rejects_active_base_drift_and_retains_draft(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = harness.create_scene(tag="drift", students=[("甲", "0001")])
    first = _upload(harness, scene, tmp_path)
    second = _upload(harness, scene, tmp_path)
    published = _confirm(harness, scene, first)
    assert published.status_code == 200, published.text
    for requested_base in (None, published.json()["revisionId"]):
        refreshed = harness.client.post(f'/api/v1/score-imports/{second["importId"]}/refresh', json={
            "expectedImportRevision": 0, "expectedAssessmentRevision": published.json()["assessmentRevision"],
            "baseScoreRevisionId": requested_base,
        })
        assert refreshed.status_code == 409, refreshed.text
        assert refreshed.json()["code"] == "SCORE_BASE_REVISION_CONFLICT"
    saved = harness.client.get(f'/api/v1/score-imports/{second["importId"]}').json()
    assert (saved["revision"], saved["baseScoreRevisionId"], saved["state"]) == (0, None, "reviewing")


@pytest.mark.parametrize("stale_field", ["expectedImportRevision", "expectedAssessmentRevision"])
def test_refresh_checks_independent_revision_locks(
    harness: ScoresHarness, tmp_path: Path, stale_field: str,
) -> None:
    scene = harness.create_scene(tag="refresh-lock", students=[("甲", "0001")])
    view = _upload(harness, scene, tmp_path)
    body = {"expectedImportRevision": view["revision"],
            "expectedAssessmentRevision": scene.assessment["revision"], "baseScoreRevisionId": None}
    body[stale_field] += 1
    response = harness.client.post(f'/api/v1/score-imports/{view["importId"]}/refresh', json=body)
    assert response.status_code == 409, response.text
    expected = "SCORE_IMPORT_REVISION_CONFLICT" if stale_field == "expectedImportRevision" else "SCORE_ASSESSMENT_REVISION_CONFLICT"
    assert response.json()["code"] == expected
    assert "currentRevision" in response.json()["details"]
    assert harness.client.get(f'/api/v1/score-imports/{view["importId"]}').json()["revision"] == 0


def test_refresh_rechecks_assessment_revision_after_preview_computation(
    harness: ScoresHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = harness.create_scene(tag="refresh-race", students=[("甲", "0001")])
    view = _upload(harness, scene, tmp_path)
    service = harness.service()
    original_summary = service._summary_payload

    def summary_then_correct(**kwargs):
        summary = original_summary(**kwargs)
        harness.app.state.assessment_service.correct_participant_attendance(
            scene.assessment["assessmentId"], scene.participant_id("0001"),
            ParticipantAttendanceRequest(expectedRevision=scene.assessment["revision"],
                                         submissionId="race-attendance", attendance="absent", reason="教师校对"),
        )
        return summary

    monkeypatch.setattr(service, "_summary_payload", summary_then_correct)
    response = harness.client.post(f'/api/v1/score-imports/{view["importId"]}/refresh', json={
        "expectedImportRevision": 0, "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": None,
    })
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "SCORE_ASSESSMENT_REVISION_CONFLICT"
    saved = harness.client.get(f'/api/v1/score-imports/{view["importId"]}').json()
    assert (saved["revision"], saved["previewVersion"], saved["requiredAcknowledgements"]) == (0, 0, view["requiredAcknowledgements"])
    assert harness.count("score_revisions") == 0
