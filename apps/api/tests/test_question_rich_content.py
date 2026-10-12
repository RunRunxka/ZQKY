"""QB-RICH：真实 HTTP/临时四库的富内容权威编辑与资产读取回归。"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from app.contracts.teaching_loop import RichContentV2
from app.core.exceptions import AppError
from app.services.question_bank import fingerprint as fp, rich
from app.services.question_bank.service import build_question_bank_service
from tests.test_question_bank import Harness, open_harness
from tests.test_question_bank_confirm import ONE_QUESTION_DOC, confirm, set_content_and_review
from tests.test_question_bank_organize import organize


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aP5sAAAAASUVORK5CYII="
)


@pytest.fixture()
def harness(tmp_path: Path):
    instance = open_harness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def upload_one(h: Harness) -> tuple[str, dict]:
    response = h.upload(ONE_QUESTION_DOC, subjectId="math")
    assert response.status_code == 201, response.text
    detail = response.json()
    return detail["importId"], detail["drafts"][0]


def image_asset(h: Harness, storage: str = "managed") -> str:
    if storage == "managed":
        return h.service.assets.store_original(PNG, media_type="image/png", original_name="one.png").blob_key
    digest, _ = h.service.blobs.write(PNG)
    return f"blobs/{digest}" if storage == "compatible-managed" else digest


def rich_content(h: Harness, import_id: str, draft: dict, *, asset_id: str | None = None) -> dict:
    content = copy.deepcopy(draft["content"])
    imported = h.catalog.get_import(import_id)
    payload = {
        "version": 2,
        "sharedMaterials": [{"id": "material-1", "blocks": [
            {"id": "material-p", "kind": "paragraph", "text": "共同材料：实验观察。"},
        ]}],
        "stemBlocks": [
            {"id": "stem-p", "kind": "paragraph", "text": content["stemMarkdown"]},
            {"id": "stem-t", "kind": "table", "columnCount": 2, "cells": [
                {"text": "观察", "isHeader": True, "rowSpan": 1, "colSpan": 2},
                {"text": "甲", "isHeader": False, "rowSpan": 1, "colSpan": 1},
                {"text": "乙", "isHeader": False, "rowSpan": 1, "colSpan": 1},
            ]},
            {"id": "stem-f", "kind": "formula", "latex": "x^2 + y^2", "ommlXml": "<m:oMath/>"},
        ],
        "optionBlocks": {
            option["key"]: [{"id": f"option-{option['key']}", "kind": "paragraph", "text": option["textMarkdown"]}]
            for option in content["options"]
        },
        "answerBlocks": [{"id": "answer-p", "kind": "paragraph", "text": "A"}],
        "explanationBlocks": [{"id": "explain-p", "kind": "paragraph", "text": content["explanationMarkdown"]}],
        "assets": [],
        "origin": {
            "originalAssetId": imported.original_blob_id, "originalSha256": imported.file_sha256,
            "sourceLocator": {"kind": "markdown", "lineStart": 1},
        },
    }
    if asset_id:
        payload["stemBlocks"].append({"id": "stem-i", "kind": "image", "assetId": asset_id, "width": 1, "height": 1})
        payload["assets"].append({"assetId": asset_id, "sha256": hashlib.sha256(PNG).hexdigest(), "mediaType": "image/png"})
    model = RichContentV2.model_validate(payload)
    content["richContent"] = model.model_dump(mode="json", by_alias=True)
    content["stemMarkdown"] = rich.project_blocks(model.stem_blocks)
    content["assetIds"] = [asset_id] if asset_id else []
    return content


def reviewed_rich(h: Harness, *, storage: str | None = "managed") -> tuple[str, dict, str | None]:
    import_id, draft = upload_one(h)
    asset_id = image_asset(h, storage) if storage else None
    content = rich_content(h, import_id, draft, asset_id=asset_id)
    reviewed = set_content_and_review(h, import_id, 0, content)
    return import_id, reviewed, asset_id


def confirm_rich(h: Harness, import_id: str, draft: dict, submission_id: str = "rich-confirm-1"):
    return confirm(h, import_id, [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}], submission_id=submission_id)


def question_patch(h: Harness, detail: dict, content: dict):
    return h.client.patch(f"/api/v1/questions/{detail['questionId']}", json={
        "expectedRevision": detail["revision"], "content": content, "metadata": detail["metadata"],
    })


def assert_error(response, code: str, *, field: str | None = None, status: int = 422):
    assert response.status_code == status, response.text
    assert response.json()["code"] == code
    if field:
        assert any(issue["field"] == field for issue in response.json()["details"]["issues"])


def test_rich_round_trip_freezes_structure_shared_material_formula_and_real_image(harness: Harness):
    import_id, draft, asset_id = reviewed_rich(harness)
    read = harness.import_detail(import_id)["drafts"][0]
    assert read["content"] == draft["content"]
    response = confirm_rich(harness, import_id, draft)
    assert response.status_code == 200, response.text
    assert response.json()["failures"] == []
    question_id = response.json()["confirmedQuestionIds"][0]
    detail = harness.client.get(f"/api/v1/questions/{question_id}").json()
    assert detail["content"] == draft["content"]
    assert detail["content"]["richContent"]["stemBlocks"][1]["cells"][0]["colSpan"] == 2
    assert detail["content"]["richContent"]["stemBlocks"][2]["ommlXml"] == "<m:oMath/>"
    image = harness.client.get(f"/api/v1/questions/{question_id}/assets/{asset_id}/content")
    assert image.status_code == 200, image.text
    assert image.content == PNG
    assert image.headers["content-type"] == "image/png"


@pytest.mark.parametrize("field", ["stemMarkdown", "options", "answer", "explanationMarkdown"])
def test_retaining_rich_cannot_silently_ignore_markdown_edits(harness: Harness, field: str):
    import_id, draft, _ = reviewed_rich(harness, storage=None)
    changed = copy.deepcopy(draft["content"])
    if field == "options":
        changed["options"][0]["textMarkdown"] = "人工修改选项"
        located = "content.options.A.textMarkdown"
    elif field == "answer":
        changed["answer"]["choiceKeys"] = ["B"]
        located = "content.answer"
    else:
        changed[field] = "人工修改文本"
        located = f"content.{field}"
    response = harness.patch_draft(draft, content=changed)
    assert_error(response, "QUESTION_RICH_CONTENT_MISMATCH", field=located)
    assert harness.import_detail(import_id)["drafts"][0] == draft


def test_rich_clear_must_be_explicit_null_and_plain_markdown_remains_editable(harness: Harness):
    import_id, draft, _ = reviewed_rich(harness, storage=None)
    changed = copy.deepcopy(draft["content"])
    del changed["richContent"]
    changed["stemMarkdown"] = "转为 Markdown 后的新题干"
    blocked = harness.patch_draft(draft, content=changed)
    assert_error(blocked, "QUESTION_RICH_CONTENT_CLEAR_REQUIRED", field="content.richContent")
    changed["richContent"] = None
    allowed = harness.patch_draft(draft, content=changed)
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["content"]["richContent"] is None
    next_content = copy.deepcopy(allowed.json()["content"])
    del next_content["richContent"]
    next_content["stemMarkdown"] += "，继续纯文本编辑"
    next_response = harness.patch_draft(allowed.json(), content=next_content)
    assert next_response.status_code == 200, next_response.text
    assert harness.import_detail(import_id)["drafts"][0]["content"]["stemMarkdown"] == next_content["stemMarkdown"]


def test_choice_answer_text_cannot_hide_different_effective_choice_keys(harness: Harness):
    import_id, draft, _ = reviewed_rich(harness, storage=None)
    consistent = copy.deepcopy(draft["content"])
    consistent["answer"]["textMarkdown"] = "A"
    saved = harness.patch_draft(draft, content=consistent)
    assert saved.status_code == 200, saved.text
    changed = copy.deepcopy(saved.json()["content"])
    changed["answer"]["choiceKeys"] = ["B"]
    assert_error(harness.patch_draft(saved.json(), content=changed), "QUESTION_RICH_CONTENT_MISMATCH", field="content.answer")
    changed["answer"]["choiceKeys"] = ["A"]
    changed["answer"]["textMarkdown"] = "保留旧富内容却改答案文本"
    assert_error(harness.patch_draft(saved.json(), content=changed), "QUESTION_RICH_CONTENT_MISMATCH", field="content.answer.textMarkdown")
    assert harness.import_detail(import_id)["drafts"][0] == saved.json()


def test_formal_rich_edit_has_same_guard_and_new_revision_does_not_change_old_json(harness: Harness):
    import_id, draft, _ = reviewed_rich(harness, storage=None)
    question_id = confirm_rich(harness, import_id, draft).json()["confirmedQuestionIds"][0]
    detail = harness.client.get(f"/api/v1/questions/{question_id}").json()
    record = harness.catalog.get_question(question_id)
    with harness.catalog._read() as conn:
        original = dict(conn.execute("SELECT * FROM question_revisions WHERE id = ?", (record.current_revision_id,)).fetchone())
    changed = copy.deepcopy(detail["content"])
    changed["stemMarkdown"] = "改动富内容以外的题干"
    assert_error(question_patch(harness, detail, changed), "QUESTION_RICH_CONTENT_MISMATCH", field="content.stemMarkdown")
    del changed["richContent"]
    assert_error(question_patch(harness, detail, changed), "QUESTION_RICH_CONTENT_CLEAR_REQUIRED", field="content.richContent")
    changed["richContent"] = None
    accepted = question_patch(harness, detail, changed)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["revision"] == 2
    with harness.catalog._read() as conn:
        retained = dict(conn.execute("SELECT * FROM question_revisions WHERE id = ?", (record.current_revision_id,)).fetchone())
    assert retained == original


def test_synchronized_rich_and_markdown_edit_creates_the_intended_formal_revision(harness: Harness):
    import_id, draft, _ = reviewed_rich(harness, storage=None)
    question_id = confirm_rich(harness, import_id, draft).json()["confirmedQuestionIds"][0]
    detail = harness.client.get(f"/api/v1/questions/{question_id}").json()
    changed = copy.deepcopy(detail["content"])
    changed["richContent"]["stemBlocks"][0]["text"] = "教师同时修改富内容和派生题干（ ）"
    changed["stemMarkdown"] = rich.project_blocks(RichContentV2.model_validate(changed["richContent"]).stem_blocks)
    response = question_patch(harness, detail, changed)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    assert response.json()["content"] == changed
    assert harness.client.get(f"/api/v1/questions/{question_id}").json()["content"] == changed


@pytest.mark.parametrize("change", ["shared-material", "table-span", "image-size"])
def test_rich_or_material_structure_changes_derived_fingerprint_and_keeps_legacy_composition(harness: Harness, change: str):
    import_id, draft, _ = reviewed_rich(harness)
    question_id = confirm_rich(harness, import_id, draft).json()["confirmedQuestionIds"][0]
    detail = harness.client.get(f"/api/v1/questions/{question_id}").json()
    before = harness.catalog.get_question(question_id)
    first_derived = harness.service._derived_fingerprint(before.content)
    changed = copy.deepcopy(detail["content"])
    if change == "shared-material":
        changed["richContent"]["sharedMaterials"][0]["blocks"][0]["text"] += " 新条件。"
    elif change == "table-span":
        changed["richContent"]["stemBlocks"][1]["cells"][0]["colSpan"] = 1
    else:
        changed["richContent"]["stemBlocks"][-1]["width"] = 2
    response = question_patch(harness, detail, changed)
    assert response.status_code == 200, response.text
    after = harness.catalog.get_question(question_id)
    assert after.content_fingerprint == before.content_fingerprint == fp.content_fingerprint(changed)
    second_derived = harness.service._derived_fingerprint(after.content)
    assert second_derived[0] == first_derived[0] == "derived-v1"
    assert second_derived[1] != first_derived[1]
    assert harness.catalog.derived_fingerprint(before.current_revision_id, algorithm_version="derived-v1") == first_derived[1]
    assert harness.catalog.derived_fingerprint(after.current_revision_id, algorithm_version="derived-v1") == second_derived[1]


@pytest.mark.parametrize("storage", ["managed", "compatible-managed", "compatible-bare"])
def test_managed_and_compatible_blob_adapters_verify_bytes_and_serve_only_referenced_image(harness: Harness, storage: str):
    import_id, draft, asset_id = reviewed_rich(harness, storage=storage)
    assert harness.service.get_content_asset("draft", draft["draftId"], asset_id) == (PNG, "image/png")
    response = harness.client.get(f"/api/v1/question-drafts/{draft['draftId']}/assets/{asset_id}/content")
    assert response.status_code == 200, response.text
    assert response.content == PNG
    assert confirm_rich(harness, import_id, draft).json()["failures"] == []


@pytest.mark.parametrize("asset_id", ["../outside", "blobs/../outside", "C:\\outside.png", "blobs/" + "A" * 64, "file://outside"])
def test_asset_read_rejects_arbitrary_paths_without_file_access(harness: Harness, monkeypatch, asset_id: str):
    _, draft = upload_one(harness)
    monkeypatch.setattr(rich, "read_asset", lambda *_args, **_kwargs: pytest.fail("illegal path reached file IO"))
    with pytest.raises(AppError) as blocked:
        harness.service.get_content_asset("draft", draft["draftId"], asset_id)
    assert (blocked.value.status_code, blocked.value.code) == (422, "INVALID_ASSET_KEY")


def test_unreferenced_asset_and_other_owner_cannot_read_real_bytes(harness: Harness):
    import_id, draft, asset_id = reviewed_rich(harness)
    other_asset = harness.service.assets.store_original(PNG + b"extra", media_type="image/png", original_name="extra.png").blob_key
    with pytest.raises(AppError) as missing:
        harness.service.get_content_asset("draft", draft["draftId"], other_asset)
    assert (missing.value.status_code, missing.value.code) == (404, "QUESTION_ASSET_NOT_FOUND")
    other = build_question_bank_service(harness.catalog, harness.settings, owner_id="someone-else")
    with pytest.raises(AppError) as owner_blocked:
        other.get_content_asset("draft", draft["draftId"], asset_id)
    assert (owner_blocked.value.status_code, owner_blocked.value.code) == (404, "DRAFT_NOT_FOUND")
    question_id = confirm_rich(harness, import_id, draft).json()["confirmedQuestionIds"][0]
    with pytest.raises(AppError) as question_blocked:
        other.get_content_asset("question", question_id, asset_id)
    assert (question_blocked.value.status_code, question_blocked.value.code) == (404, "QUESTION_NOT_FOUND")


@pytest.mark.parametrize("invalid", ["digest", "media", "missing", "unreferenced", "assetIds", "empty-formula", "duplicate-block"])
def test_invalid_rich_inputs_are_located_and_never_persisted(harness: Harness, invalid: str):
    import_id, draft = upload_one(harness)
    asset_id = image_asset(harness)
    content = rich_content(harness, import_id, draft, asset_id=asset_id)
    expected = "QUESTION_RICH_CONTENT_INVALID"
    if invalid == "digest":
        content["richContent"]["assets"][0]["sha256"] = "0" * 64
        expected = "QUESTION_ASSET_DIGEST_MISMATCH"
    elif invalid == "media":
        content["richContent"]["assets"][0]["mediaType"] = "image/jpeg"
        expected = "QUESTION_ASSET_MEDIA_INVALID"
    elif invalid == "missing":
        missing_key = "blobs/" + "0" * 64
        content["richContent"]["stemBlocks"][-1]["assetId"] = missing_key
        content["richContent"]["assets"][0]["assetId"] = missing_key
        content["assetIds"] = [missing_key]
        content["stemMarkdown"] = rich.project_blocks(RichContentV2.model_validate(content["richContent"]).stem_blocks)
        expected = "QUESTION_ASSET_NOT_FOUND"
    elif invalid == "unreferenced":
        content["richContent"]["assets"].append({"assetId": "blobs/" + "0" * 64, "sha256": "0" * 64, "mediaType": "image/png"})
    elif invalid == "assetIds":
        content["assetIds"] = []
    elif invalid == "empty-formula":
        content["richContent"]["stemBlocks"][2]["latex"] = None
        content["richContent"]["stemBlocks"][2]["ommlXml"] = None
    else:
        content["richContent"]["stemBlocks"][0]["id"] = "material-p"
    response = harness.patch_draft(draft, content=content)
    assert_error(response, expected)
    assert response.json()["details"]["issues"]
    assert harness.import_detail(import_id)["drafts"][0] == draft


def test_new_plain_image_also_requires_safe_existing_real_image_bytes(harness: Harness):
    _, draft = upload_one(harness)
    content = copy.deepcopy(draft["content"])
    content["assetIds"] = ["../outside"]
    assert_error(harness.patch_draft(draft, content=content), "INVALID_ASSET_KEY")
    content["assetIds"] = ["blobs/" + "0" * 64]
    assert_error(harness.patch_draft(draft, content=content), "QUESTION_ASSET_NOT_FOUND")
    bad = harness.service.assets.store_original(b"not-an-image", media_type="image/png", original_name="bad.png")
    content["assetIds"] = [bad.blob_key]
    assert_error(harness.patch_draft(draft, content=content), "QUESTION_ASSET_MEDIA_INVALID")
    content["assetIds"] = [image_asset(harness)]
    response = harness.patch_draft(draft, content=content)
    assert response.status_code == 200, response.text


def test_corrupt_managed_primary_never_falls_back_to_valid_compatible_copy(harness: Harness):
    _, draft, asset_id = reviewed_rich(harness)
    harness.service.blobs.write(PNG)
    harness.service.assets.path_of(asset_id).write_bytes(b"corrupt")
    response = harness.client.get(f"/api/v1/question-drafts/{draft['draftId']}/assets/{asset_id}/content")
    assert_error(response, "ASSET_CORRUPT", status=500)


def test_confirm_failed_asset_precheck_writes_no_question_or_submission(harness: Harness):
    import_id, draft, asset_id = reviewed_rich(harness)
    harness.service.assets.path_of(asset_id).write_bytes(b"corrupt")
    response = confirm_rich(harness, import_id, draft)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["confirmedQuestionIds"] == []
    assert result["failures"][0]["code"] == "ASSET_CORRUPT"
    assert harness.catalog.get_submission("rich-confirm-1") is None
    assert harness.service.list_questions().total == 0
    assert harness.catalog.get_draft(draft["draftId"]).revision == draft["revision"]


def test_confirm_replay_returns_original_fact_before_missing_asset_precheck(harness: Harness, monkeypatch):
    import_id, draft, asset_id = reviewed_rich(harness)
    first = confirm_rich(harness, import_id, draft)
    assert first.json()["failures"] == []
    harness.service.assets.path_of(asset_id).unlink()
    monkeypatch.setattr(rich, "read_asset", lambda *_args, **_kwargs: pytest.fail("replay must precede file IO"))
    replay = confirm_rich(harness, import_id, draft)
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()


def test_confirm_asset_io_is_outside_sql_write_transaction_and_publication_lock(harness: Harness, monkeypatch):
    import_id, draft, _ = reviewed_rich(harness)
    actual_transaction = harness.catalog.write_transaction
    actual_read = rich.read_asset
    active = {"write": False, "publication": False, "reads": 0}

    @contextmanager
    def checked_transaction():
        with actual_transaction() as conn:
            active["write"] = True
            try:
                yield conn
            finally:
                active["write"] = False

    @contextmanager
    def checked_publication(_operation):
        active["publication"] = True
        try:
            yield
        finally:
            active["publication"] = False

    def checked_read(*args, **kwargs):
        assert not active["write"] and not active["publication"]
        active["reads"] += 1
        return actual_read(*args, **kwargs)

    monkeypatch.setattr(harness.catalog, "write_transaction", checked_transaction)
    monkeypatch.setattr(harness.service, "_publication", checked_publication)
    monkeypatch.setattr(rich, "read_asset", checked_read)
    response = confirm_rich(harness, import_id, draft)
    assert response.json()["failures"] == []
    assert active["reads"] > 0


def test_confirm_draft_change_after_asset_preflight_is_rejected_by_original_revision(harness: Harness, monkeypatch):
    import_id, draft, _ = reviewed_rich(harness)
    actual = harness.service._derived_fingerprint

    def racing(content):
        result = actual(content)
        harness.catalog.set_draft_review_state(draft["draftId"], expected_revision=draft["revision"], review_state="needs_review")
        return result

    monkeypatch.setattr(harness.service, "_derived_fingerprint", racing)
    response = confirm_rich(harness, import_id, draft)
    assert response.status_code == 200, response.text
    assert response.json()["failures"][0]["code"] == "REVISION_CONFLICT"
    assert harness.service.list_questions().total == 0
    assert harness.catalog.get_submission("rich-confirm-1") is None


def test_current_asset_reference_removal_does_not_delete_old_revision_or_blob(harness: Harness):
    import_id, draft, asset_id = reviewed_rich(harness)
    question_id = confirm_rich(harness, import_id, draft).json()["confirmedQuestionIds"][0]
    old = harness.catalog.get_question(question_id)
    detail = harness.client.get(f"/api/v1/questions/{question_id}").json()
    changed = copy.deepcopy(detail["content"])
    changed["richContent"] = None
    changed["assetIds"] = []
    changed["stemMarkdown"] = "明确转为不含图片的 Markdown"
    response = question_patch(harness, detail, changed)
    assert response.status_code == 200, response.text
    missing = harness.client.get(f"/api/v1/questions/{question_id}/assets/{asset_id}/content")
    assert_error(missing, "QUESTION_ASSET_NOT_FOUND", status=404)
    with harness.catalog._read() as conn:
        raw = conn.execute("SELECT content_json FROM question_revisions WHERE id = ?", (old.current_revision_id,)).fetchone()["content_json"]
    retained = json.loads(raw)
    assert retained == old.content
    assert retained["assetIds"] == [asset_id]
    assert harness.service.assets.read(asset_id) == PNG
    assert harness.service._derived_fingerprint(retained) == harness.service._derived_fingerprint(old.content)


@pytest.mark.parametrize("storage", ["managed", "compatible-managed", "compatible-bare"])
def test_legacy_markdown_image_remains_readable_and_old_revision_keeps_reference(harness: Harness, storage: str):
    import_id, draft = upload_one(harness)
    asset_id = image_asset(harness, storage)
    content = copy.deepcopy(draft["content"])
    content.pop("richContent", None)
    content["assetIds"] = [asset_id]
    content["stemMarkdown"] += f"\n\n![旧 Markdown 图片]({asset_id})"
    draft = set_content_and_review(harness, import_id, 0, content)
    question_id = confirm_rich(harness, import_id, draft).json()["confirmedQuestionIds"][0]
    old = harness.catalog.get_question(question_id)
    assert old.content.get("richContent") is None
    response = harness.client.get(f"/api/v1/questions/{question_id}/assets/{asset_id}/content")
    assert response.status_code == 200, response.text
    assert response.content == PNG
    detail = harness.client.get(f"/api/v1/questions/{question_id}").json()
    changed = copy.deepcopy(detail["content"])
    changed["stemMarkdown"] = "题干已修订，保留图片"
    patched = question_patch(harness, detail, changed)
    assert patched.status_code == 200, patched.text
    assert harness.service.get_content_asset("question", question_id, asset_id) == (PNG, "image/png")
    with harness.catalog._read() as conn:
        raw = conn.execute("SELECT content_json FROM question_revisions WHERE id = ?", (old.current_revision_id,)).fetchone()["content_json"]
    assert json.loads(raw) == old.content
    assert rich.read_asset(asset_id, assets=harness.service.assets, blobs=harness.service.blobs) == (PNG, "image/png")


def test_split_merge_and_ai_accept_require_explicit_rich_to_markdown_conversion(harness: Harness):
    detail = harness.sample_detail(subjectId="math")
    import_id = detail["importId"]
    draft = detail["drafts"][0]
    content = rich_content(harness, import_id, draft)
    # 样本文本的答案可能不是 A；投影沿原答案构造，避免 fixture 改题。
    answer = content["answer"]
    answer_text = answer.get("textMarkdown") or ", ".join(answer.get("choiceKeys", []))
    content["richContent"]["answerBlocks"][0]["text"] = answer_text
    draft = set_content_and_review(harness, import_id, 0, content)
    start = min(span["charStart"] for span in draft["sourceSpans"])
    end = max(span["charEnd"] for span in draft["sourceSpans"])
    split = harness.client.post(f"/api/v1/question-imports/{import_id}/split", params={"draftId": draft["draftId"]}, json={"expectedRevision": draft["revision"], "charOffset": (start + end) // 2})
    assert_error(split, "QUESTION_RICH_CONTENT_EDIT_UNSUPPORTED", field="content.richContent")
    second = harness.import_detail(import_id)["drafts"][1]
    merge = harness.client.post(f"/api/v1/question-imports/{import_id}/merge", json={"expectedRevisions": {draft["draftId"]: draft["revision"], second["draftId"]: second["revision"]}})
    assert_error(merge, "QUESTION_RICH_CONTENT_EDIT_UNSUPPORTED", field="content.richContent")
    job = organize(harness, import_id, draftIds=[draft["draftId"]]).json()
    suggestion = harness.catalog.list_suggestions(organization_job_id=job["jobId"])[0]
    accept = harness.client.post(f"/api/v1/question-suggestions/{suggestion.suggestion_id}/apply", json={"expectedDraftRevision": draft["revision"], "accept": True})
    assert_error(accept, "QUESTION_RICH_CONTENT_EDIT_UNSUPPORTED", field="content.richContent")
    assert "richContent=null" in accept.json()["message"]
    assert harness.catalog.get_suggestion(suggestion.suggestion_id).state == "pending"
    rejected = harness.client.post(f"/api/v1/question-suggestions/{suggestion.suggestion_id}/apply", json={"expectedDraftRevision": draft["revision"], "accept": False})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["content"] == draft["content"]
    assert harness.catalog.get_draft(draft["draftId"]).revision == draft["revision"]
