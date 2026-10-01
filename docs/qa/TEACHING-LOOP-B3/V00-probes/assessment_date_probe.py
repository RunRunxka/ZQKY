"""Read-only B2 product review using the real HTTP application and temporary data.

Run from repository root:
apps/api/.venv/Scripts/python.exe -X utf8 docs/qa/TEACHING-LOOP-B2-REVIEW-20261001/probes/assessment_date_probe.py

Exit 0 means the diagnostic executed. Read bugReproduced for the product defect.
Environment is isolated BEFORE any import that can load app.main.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(root / "apps" / "api"))
    with tempfile.TemporaryDirectory(prefix="b2-review-assessment-") as temporary:
        scratch = Path(temporary)
        os.environ["ZQKY_DATA_DIR"] = str(scratch / "bootstrap")
        # Do not move this import above environment isolation.
        from tests.assessments_support import AssessmentsHarness

        with AssessmentsHarness(scratch / "scene") as harness:
            paper = harness.create_confirmed_paper(tag="probe")
            klass = harness.create_class(code="PROBE")
            student = harness.create_student(
                name="Probe",
                student_no="001",
                class_id=klass["id"],
                joined_on="2026-09-20",
            )
            request = harness.create_body(
                paper,
                submission_id="probe-create",
                class_ids=[klass["id"]],
                participants=[harness.participant(student["id"], klass["id"])],
                held_on="2026-09-30",
            )
            created = harness.client.post("/api/v1/assessments", json=request)
            assert created.status_code == 201, created.text
            initial = created.json()["assessment"]
            assessment_id = initial["assessmentId"]
            changed = harness.client.patch(
                f"/api/v1/assessments/{assessment_id}",
                json={"expectedRevision": initial["revision"], "heldOn": "2026-09-01"},
            )
            response = harness.client.get(f"/api/v1/assessments/{assessment_id}")
            assert response.status_code == 200, response.text
            detail = response.json()
            joined = harness.memberships_snapshot()[0]["joined_on"]
            participant = detail["participants"][0]
            result = {
                "probe": "B2 assessment date membership review",
                "create_status": created.status_code,
                "patch_status": changed.status_code,
                "initialHeldOn": initial["heldOn"],
                "requestedHeldOn": "2026-09-01",
                "heldOn": detail["assessment"]["heldOn"],
                "participantConfirmed": participant["classConfirmed"],
                "joinedOn": joined,
                "expected": "Reject date changes invalidating unconfirmed participant membership, or require an explicit confirmation flow.",
                "bugReproduced": (
                    changed.status_code == 200
                    and detail["assessment"]["heldOn"] < joined
                    and participant["classConfirmed"] is False
                ),
                "executionSucceeded": True,
                "isolation": "ZQKY_DATA_DIR set before importing tests.assessments_support/app.main; all application data under TemporaryDirectory",
            }
    # Temporary data and TestClient lifespan have both been released before output.
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
