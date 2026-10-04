"""Review assertions: one known failure and an immutable-history regression."""
from pathlib import Path

from app.services.scores.imports import parse_score_text
from tests.scores_support import SAMPLE_HEADER, ScoresHarness, write_score_xlsx


def confirm(harness, scene, view, submission):
    return harness.confirm_import(view["importId"], {
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": view["baseScoreRevisionId"],
        "previewVersion": view["previewVersion"],
        "submissionId": submission,
        **view["requiredAcknowledgements"],
    })


def test_xlsx_overlong_score_must_not_be_truncated_into_valid_units(tmp_path: Path):
    with ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="review-long-cell")
        text = "1." + "0" * 19998 + "1"
        assert parse_score_text(text, max_units=200).code == "SCORE_CELL_INVALID"
        source = write_score_xlsx(tmp_path / "long.xlsx", SAMPLE_HEADER,
                                  [["0001", "甲", text, 2, 3]])
        response = harness.upload_scores(scene.assessment["assessmentId"], source)
        assert response.status_code == 422, (
            "Original cell C2 is not exact to cent units; accepting 201 after "
            "truncation allows an invalid source to be recorded as 100 units."
        )
        assert harness.count("score_imports") == 0
        assert harness.count("score_revisions") == 0
        assert harness.count("student_item_scores") == 0


def test_fixed_revision_and_snapshot_survive_attendance_retake_and_new_score(tmp_path: Path):
    with ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="review-fixed")
        source = write_score_xlsx(tmp_path / "normal.xlsx", SAMPLE_HEADER,
                                  [["0001", "甲", 1, 2, 3]])
        view = harness.upload_scores(scene.assessment["assessmentId"], source).json()
        v1 = confirm(harness, scene, view, "review-v1")
        assert v1.status_code == 200, v1.text
        old_id = v1.json()["revisionId"]
        before = harness.score_matrix(old_id).json()
        assert before["revision"]["paperRevisionId"] == scene.paper.revision_id
        assert len(before["revision"]["participantSnapshot"]) == 1
        attendance = harness.client.patch(
            f'/api/v1/assessments/{scene.assessment["assessmentId"]}/participants/'
            f'{scene.participant_id("0001")}/attendance',
            json={"expectedRevision": v1.json()["assessmentRevision"],
                  "submissionId": "review-attendance", "attendance": "absent",
                  "reason": "根据教师签到单校正当前人次"},
        )
        assert attendance.status_code == 200, attendance.text
        added = harness.client.post(
            f'/api/v1/assessments/{scene.assessment["assessmentId"]}/participants',
            json={"expectedRevision": attendance.json()["assessment"]["revision"],
                  "submissionId": "review-retake",
                  "participants": [harness.participant(scene.student_id("0001"),
                                                        scene.klass["id"], attempt_no=2)]},
        )
        assert added.status_code == 200, added.text
        correction = harness.correct_scores(scene.assessment["assessmentId"], {
            "baseScoreRevisionId": old_id,
            "expectedAssessmentRevision": added.json()["assessment"]["revision"],
            "submissionId": "review-correction", "reason": "复核第一人次Q1得分",
            "corrections": [{"participantId": scene.participant_id("0001"),
                             "itemId": "it-review-fixed-1", "status": "recorded",
                             "scoreText": "1.5"}],
        })
        assert correction.status_code == 200, correction.text
        assert harness.score_matrix(old_id).json() == before
        assert harness.client.get(f'/api/v1/score-revisions/{old_id}').json() == before["revision"]
        newer = harness.score_matrix(correction.json()["revisionId"]).json()
        assert newer["revision"]["paperRevisionId"] == scene.paper.revision_id
        assert newer["total"] == 2
        assert len(newer["revision"]["participantSnapshot"]) == 2
        assert all(cell["status"] == "missing" for cell in newer["rows"][1]["cells"])
