"""A confirmed question is accessible only through its owner's service."""
import pytest

from app.services.question_bank.service import build_question_bank_service
from tests.test_question_bank import open_harness
from tests.test_question_bank_confirm import ONE_QUESTION_DOC, confirm, upload_and_review


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_other_owner_cannot_read_edit_or_archive_confirmed_question(tmp_path, method):
    harness = open_harness(tmp_path)
    other = None
    try:
        import_id, draft = upload_and_review(harness, ONE_QUESTION_DOC, subjectId="math")
        receipt = confirm(harness, import_id, [{"draftId": draft["draftId"],
            "expectedDraftRevision": draft["revision"]}], submission_id="owner-boundary")
        assert receipt.status_code == 200 and receipt.json()["failures"] == []
        question_id = receipt.json()["confirmedQuestionIds"][0]
        detail = harness.service.get_question(question_id)
        before = harness.catalog.get_question(question_id)
        other = build_question_bank_service(harness.catalog, harness.settings, owner_id="another-owner")
        harness.app.state.question_bank_service = other
        kwargs = {}
        if method == "patch":
            kwargs["json"] = {"expectedRevision": detail.revision,
                "content": detail.content.model_dump(by_alias=True, mode="json"),
                "metadata": detail.metadata.model_dump(by_alias=True, mode="json")}
        elif method == "delete":
            kwargs["params"] = {"expectedRevision": detail.revision}
        response = getattr(harness.client, method)("/api/v1/questions/" + question_id, **kwargs)
        assert response.status_code == 404 and response.json()["code"] == "QUESTION_NOT_FOUND"
        assert response.json()["requestId"] and response.json()["retryable"] is False
        assert harness.catalog.get_question(question_id) == before
        harness.app.state.question_bank_service = harness.service
        restored = harness.client.get("/api/v1/questions/" + question_id)
        assert restored.status_code == 200 and restored.json() == detail.model_dump(by_alias=True, mode="json")
    finally:
        harness.app.state.question_bank_service = harness.service
        if other is not None:
            other.close()
        harness.close()
