"""Review fixes: physical duplicate rows and optimistic preview context boundaries."""

from pathlib import Path

import pytest

from app.contracts.assessments import ParticipantAttendanceRequest
from tests.scores_support import SAMPLE_HEADER, ScoresHarness, write_score_xlsx


def test_duplicate_rows_remain_located_blockers_until_explicitly_disambiguated(tmp_path: Path) -> None:
    with ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="duplicate", students=[("甲", "0001"), ("乙", "0002")])
        source = write_score_xlsx(tmp_path / "duplicate.xlsx", SAMPLE_HEADER,
                                  [["0001", "甲", 1, 2, 3], ["0001", "甲", 2, 3, 5]])
        uploaded = harness.upload_scores(scene.assessment["assessmentId"], source)
        assert uploaded.status_code == 201, uploaded.text
        view = uploaded.json()
        assert {issue["row"] for issue in view["issues"]
                if issue["code"] == "SCORE_ROW_DUPLICATE_PARTICIPANT"} == {2, 3}
        refused = harness.confirm_import(view["importId"], {
            "expectedImportRevision": view["revision"], "previewVersion": view["previewVersion"],
            "expectedAssessmentRevision": scene.assessment["revision"],
            "baseScoreRevisionId": None, "submissionId": "duplicate-confirm",
            **view["requiredAcknowledgements"],
        })
        assert refused.status_code == 422, refused.text
        assert refused.json()["code"] == "SCORE_ROW_DUPLICATE_PARTICIPANT"
        assert harness.count("score_revisions") == harness.count("student_item_scores") == 0
        resolved = harness.patch_import(view["importId"], {
            "expectedRevision": view["revision"],
            "rows": [{"rowNo": 3, "participantId": scene.participant_id("0002")}],
        })
        assert resolved.status_code == 200, resolved.text
        assert not any(issue["code"] == "SCORE_ROW_DUPLICATE_PARTICIPANT"
                       for issue in resolved.json()["issues"])


@pytest.mark.parametrize("interleave", [False, True])
def test_patch_cannot_adopt_a_changed_assessment_context(tmp_path: Path, monkeypatch, interleave: bool) -> None:
    with ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="context", students=[("甲", "0001")])
        source = write_score_xlsx(tmp_path / "context.xlsx", SAMPLE_HEADER, [["0001", "甲", 1, 2, 3]])
        view = harness.upload_scores(scene.assessment["assessmentId"], source).json()
        before_imports = harness.raw_rows("SELECT * FROM score_imports")
        before_rows = harness.raw_rows("SELECT * FROM score_import_rows")

        def change_attendance():
            harness.app.state.assessment_service.correct_participant_attendance(
                scene.assessment["assessmentId"], scene.participant_id("0001"),
                ParticipantAttendanceRequest(expectedRevision=scene.assessment["revision"],
                                             submissionId="change-attendance", attendance="absent",
                                             reason="教师核对签到后校正"),
            )

        if interleave:
            service = harness.service()
            original_summary = service._summary_payload

            def summarize_then_change(**kwargs):
                result = original_summary(**kwargs)
                change_attendance()
                return result

            monkeypatch.setattr(service, "_summary_payload", summarize_then_change)
        else:
            change_attendance()
        response = harness.patch_import(view["importId"], {
            "expectedRevision": view["revision"],
            "rows": [{"rowNo": 2, "cells": [{"row": 2, "column": "C", "text": "0"}]}],
        })
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "SCORE_ASSESSMENT_REVISION_CONFLICT"
        assert harness.raw_rows("SELECT * FROM score_imports") == before_imports
        assert harness.raw_rows("SELECT * FROM score_import_rows") == before_rows
        assert harness.count("score_revisions") == 0
