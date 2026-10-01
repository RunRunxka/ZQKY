"""B2 review: reproduce retry dispatch and question knowledge integrity gaps.

Run from apps/api: uv run --no-sync python <absolute path to this script>.
The probe creates isolated temporary data before importing app.main, uses a fake
provider, and opens no network server. Exit 0 means observations were captured;
it does not mean the observed product behavior passed acceptance.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time

repository_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(repository_root / "apps" / "api"))
probe_root = Path(tempfile.mkdtemp(prefix="zqky-b2-review-jobs-"))
os.environ["ZQKY_DATA_DIR"] = str(probe_root / "module-default-isolated")
os.environ.pop("ZQKY_CREDENTIALS_FILE", None)

from tests.test_question_generation import GenerationHarness, generation_reply
from tests.test_question_bank_confirm import reviewed_draft, confirm

harness = GenerationHarness(probe_root / "h")
observations: dict = {"probeRoot": str(probe_root)}
try:
    point = harness.create_point()
    detail = harness.upload_sample(subjectId="math")
    draft = detail["drafts"][0]
    linked = harness.patch_links(
        draft["draftId"], draft["revision"],
        [{"knowledgePointId": point["pointId"]}],
    )
    assert linked.status_code == 200, linked.text
    current_point = harness.client.get("/api/v1/knowledge-points/" + point["pointId"])
    assert current_point.status_code == 200, current_point.text
    archived = harness.client.post(
        "/api/v1/knowledge-points/" + point["pointId"] + "/archive",
        json={"expectedRevision": current_point.json()["revision"]},
    )
    assert archived.status_code == 200, archived.text
    observations["archiveViaPublicApi"] = {"statusCode": archived.status_code}
    draft = reviewed_draft(harness, detail["importId"])
    response = confirm(
        harness, detail["importId"],
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="archived-confirm",
    )
    observations["archivedKnowledgeConfirm"] = {
        "statusCode": response.status_code,
        "body": response.json(),
    }
    print("archived_kp_confirm", response.status_code, response.json())
    assert response.status_code == 200, response.text
    question_id = response.json()["confirmedQuestionIds"][0]
    question = harness.service.get_question(question_id).model_dump(mode="json")
    metadata = dict(question["metadata"])
    metadata["subjectId"] = "chinese"
    patch = harness.client.patch(
        "/api/v1/questions/" + question_id,
        json={
            "expectedRevision": question["revision"],
            "content": question["content"],
            "metadata": metadata,
        },
    )
    assert patch.status_code == 200, patch.text
    observations["subjectChangeWithoutLinkReplacement"] = {
        "statusCode": patch.status_code,
        "subjectId": patch.json()["metadata"]["subjectId"],
        "knowledgeLinks": patch.json()["knowledgeLinks"],
    }
    print("cross_subject_patch", patch.status_code,
          patch.json()["metadata"]["subjectId"], patch.json()["knowledgeLinks"])

    harness.provider.replies = ["INVALID JSON"]
    job_id = harness.start_generation().json()["jobId"]
    failed = harness.wait_job(job_id)
    assert failed["state"] == "failed", failed
    calls_before = len(harness.provider.calls)
    retried = harness.client.post(
        "/api/v1/workflow-jobs/" + job_id + "/retry",
        json={"domain": "question"},
    )
    harness.provider.replies = [generation_reply()]
    observed_states = []
    for _ in range(20):
        view = harness.job_view(job_id)
        observed_states.append(view["state"])
        time.sleep(0.01)
    observations["publicRetry"] = {
        "statusCode": retried.status_code,
        "retryState": retried.json()["state"],
        "pollStates": observed_states,
        "callsBefore": calls_before,
        "callsAfter": len(harness.provider.calls),
        "attemptAfter": view["attempt"],
    }
    print("retry_real_api", retried.status_code, retried.json()["state"],
          "after_20_polls", view["state"], "calls_before_after", calls_before,
          len(harness.provider.calls), "attempt", view["attempt"])
finally:
    harness.close()

Path(__file__).with_suffix(".json").write_text(
    json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
)
print("probe_root", probe_root)
