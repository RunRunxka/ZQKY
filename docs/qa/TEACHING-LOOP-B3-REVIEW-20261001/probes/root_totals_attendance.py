"""Read-only product review; all application state and fixtures are temporary."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "apps" / "api"))
TEMP = tempfile.TemporaryDirectory(prefix="zqky-b3-root-review-")
BASE = Path(TEMP.name)
os.environ["ZQKY_DATA_DIR"] = str(BASE / "initial-import")

from tests.scores_support import ScoresHarness, absence_ack, write_score_xlsx

OBSERVATIONS = []

def emit(name: str, **facts: object) -> None:
    observation = {"probe": name, **facts}
    OBSERVATIONS.append(observation)
    print(json.dumps(observation, ensure_ascii=False))


def confirm(harness, scene, view, submission_id, absences=None):
    return harness.confirm_import(view["importId"], {
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": None,
        "previewVersion": view["previewVersion"],
        "submissionId": submission_id,
        "absences": absences or [],
    })


with ScoresHarness(BASE / "total") as harness:
    scene = harness.create_scene(tag="total", students=[("甲", "0001")])
    path = write_score_xlsx(BASE / "total.xlsx", ["学号", "姓名", "Q1", "Q2", "Q3", "总分"], [["0001", "甲", 1, 2, 3, 9]])
    upload = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert upload.status_code == 201, upload.text
    view = upload.json()
    outcome = confirm(harness, scene, view, "total-confirm")
    assert outcome.status_code == 200, outcome.text
    matrix = harness.score_matrix(outcome.json()["revisionId"]).json()
    emit("inconsistent_source_total", sourceTotalUnits=900, calculatedTotalUnits=matrix["rows"][0]["participant"]["totalUnits"], uploadStatus=upload.status_code, confirmStatus=outcome.status_code, warnings=view["warnings"], issues=view["issues"], mapping=view["mapping"])

with ScoresHarness(BASE / "attendance") as harness:
    scene = harness.create_scene(tag="attendance", students=[("甲", "0001")], attendance={"0001": "absent"})
    path = write_score_xlsx(BASE / "attendance.xlsx", ["学号", "姓名", "Q1", "Q2", "Q3"], [["0001", "甲", "缺考", "缺考", "缺考"]])
    upload = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert upload.status_code == 201, upload.text
    outcome = confirm(harness, scene, upload.json(), "absent-confirm", [absence_ack(scene.klass["id"], [scene.participant_id("0001")])])
    assert outcome.status_code == 200, outcome.text
    v1 = outcome.json()
    snapshot = harness.score_matrix(v1["revisionId"]).json()
    correction = harness.correct_scores(scene.assessment["assessmentId"], {
        "baseScoreRevisionId": v1["revisionId"],
        "expectedAssessmentRevision": v1["assessmentRevision"],
        "submissionId": "partial-attendance-correction",
        "reason": "复核成绩",
        "corrections": [{"participantId": scene.participant_id("0001"), "itemId": snapshot["items"][0]["itemId"], "status": "recorded", "scoreText": "1"}],
    })
    assert correction.status_code == 200, correction.text
    corrected = harness.score_matrix(correction.json()["revisionId"]).json()
    emit("mixed_attendance_correction", correctionStatus=correction.status_code, attendance=corrected["rows"][0]["participant"]["attendance"], cellStates=[cell["status"] for cell in corrected["rows"][0]["cells"]])

Path(__file__).with_suffix(".json").write_text(json.dumps(OBSERVATIONS, ensure_ascii=False, indent=2), encoding="utf-8")
TEMP.cleanup()
