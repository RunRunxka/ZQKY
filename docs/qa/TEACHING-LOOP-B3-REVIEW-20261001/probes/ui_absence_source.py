"""Read-only B3 review: generate real API preview and test UI-derived acknowledgement.

All databases/assets belong to TemporaryDirectory; no model/network/formal data access.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
API = ROOT / "apps" / "api"
sys.path.insert(0, str(API))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="b3-review-ui-absence-") as directory:
        root = Path(directory)
        os.environ["ZQKY_DATA_DIR"] = str(root / "default-isolated")
        from tests.scores_support import ScoresHarness, write_score_xlsx

        with ScoresHarness(root / "scene") as harness:
            scene = harness.create_scene(tag="ui-absence", students=(("甲", "0001"), ("乙", "0002")))
            # Both were created present (normal UI default); the teacher score sheet marks absence.
            source = write_score_xlsx(
                root / "scores.xlsx",
                ("学号", "姓名", "Q1", "Q2", "Q3"),
                (("0001", "甲", "缺考", None, None), ("0002", "乙", 2, 3, 5)),
            )
            response = harness.upload_scores(scene.assessment["assessmentId"], source)
            assert response.status_code == 201, response.text
            view = response.json()
            rows = harness.list_import_rows(view["importId"]).json()["items"]
            absent_id = scene.participant_id("0001")
            # This is the actual front-end deriveMissingAcknowledgement output: 3 leaves minus
            # one filled absence marker => 2 missing cells, despite preview missingCellCount=0.
            payload = {
                "expectedImportRevision": view["revision"],
                "expectedAssessmentRevision": scene.assessment["revision"],
                "baseScoreRevisionId": None,
                "previewVersion": view["previewVersion"],
                "submissionId": "ui-derived-ack",
                "absences": [{"classId": scene.klass["id"], "participantIds": [absent_id]}],
                "missing": {"participantIds": [absent_id], "cellCount": 2},
            }
            rejected = harness.confirm_import(view["importId"], payload)
            assert rejected.status_code == 422, rejected.text
            assert rejected.json()["code"] == "SCORE_ACKNOWLEDGEMENT_MISMATCH"
            payload["missing"] = None
            payload["submissionId"] = "correct-server-ack"
            accepted = harness.confirm_import(view["importId"], payload)
            assert accepted.status_code == 200, accepted.text
            fixture = {
                "view": view,
                "rows": rows,
                "participants": [
                    {"participantId": p["participantId"], "classId": p["classId"],
                     "name": p["nameSnapshot"], "attendance": p["attendance"]}
                    for p in scene.participants
                ],
                "leaves": [{"itemId": f"it-ui-absence-{i}", "questionNo": q}
                           for i, (q, _) in enumerate(scene.paper.leaves, start=1)],
                "assessmentRevision": scene.assessment["revision"],
                "rejected": {"status": rejected.status_code, "body": rejected.json()},
                "accepted": {"status": accepted.status_code, "body": accepted.json()},
            }
            destination = Path(__file__).with_name("ui_absence_fixture.json")
            destination.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"source": "real API", "missingCellCount": view["missingCellCount"],
                              "uiPayloadStatus": rejected.status_code,
                              "correctPayloadStatus": accepted.status_code,
                              "fixture": str(destination)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
