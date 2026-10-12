"""G1-R07: real ASGI, frozen authoritative surfaces and isolated four databases."""
from __future__ import annotations

import copy
import hashlib
import os
import struct
import tempfile
import zlib
from pathlib import Path

os.environ.setdefault("ZQKY_DATA_DIR", tempfile.mkdtemp(prefix="zqky-g1-qb-bootstrap-"))
os.environ["ZQKY_ENV"] = "test"
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

import pytest

from app.contracts.teaching_loop import RichContentV2
from app.core.config import Settings
from app.services.question_bank import fingerprint as fp, rich
from tests import test_question_bank as harness_module
from tests.test_question_bank_confirm import confirm, set_content_and_review, upload_and_review, ONE_QUESTION_DOC
from tests.test_question_rich_content import rich_content, upload_one


@pytest.fixture()
def harness(tmp_path: Path, monkeypatch):
    def isolated_settings(path):
        return Settings(host="127.0.0.1", port=8001, allowed_origins=frozenset({"http://127.0.0.1:5174"}),
                        env="test", data_dir=path / "data", credentials_file=None)
    monkeypatch.setattr(harness_module, "make_settings", isolated_settings)
    instance = harness_module.open_harness(tmp_path)
    assert instance.settings.credentials_file is None
    try:
        yield instance
    finally:
        instance.close()


def save_review(h, import_id, content):
    model = RichContentV2.model_validate(content["richContent"])
    content["stemMarkdown"] = rich.project_blocks(model.stem_blocks)
    for option in content["options"]:
        option["textMarkdown"] = rich.project_blocks(model.option_blocks[option["key"]])
    return set_content_and_review(h, import_id, 0, content)


def create_rich(h, *, change=None):
    import_id, draft = upload_one(h)
    content = rich_content(h, import_id, draft)
    content["richContent"]["sharedMaterials"][0]["blocks"][0]["text"] = "共同材料：实验溶液浓度为 1 mol/L。"
    if change:
        change(content)
    return import_id, save_review(h, import_id, content)


def submit(h, import_id, draft, key, action=None):
    resolutions = [{"draftId": draft["draftId"], "action": action}] if action else []
    response = confirm(h, import_id, [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
                       submission_id=key, resolutions=resolutions)
    assert response.status_code == 200, response.text
    return response.json()


def png_rgb(red, green, blue):
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes([0, red, green, blue]))) + chunk(b"IEND", b""))


def add_image(h, content, data, *, storage="managed"):
    if storage == "managed":
        asset_id = h.service.assets.store_original(data, media_type="image/png", original_name="probe.png").blob_key
    else:
        asset_id, _ = h.service.blobs.write(data)
    content["richContent"]["sharedMaterials"][0]["blocks"].append(
        {"id": "material-image", "kind": "image", "assetId": asset_id, "width": 1, "height": 1})
    content["richContent"]["assets"].append(
        {"assetId": asset_id, "sha256": hashlib.sha256(data).hexdigest(), "mediaType": "image/png"})
    content["assetIds"].append(asset_id)


@pytest.mark.parametrize("action", [None, "edit_as_new"])
def test_material_1mol_and_2mol_both_confirm_with_equal_plain_surface(harness, action):
    first_import, first_draft = create_rich(harness)
    first = submit(harness, first_import, first_draft, "g1-material-first")
    assert len(first["confirmedQuestionIds"]) == 1
    second_import, second_draft = create_rich(harness, change=lambda c: c["richContent"]["sharedMaterials"][0]["blocks"][0].update(
        text="共同材料：实验溶液浓度为 2 mol/L。"))
    assert first_draft["content"]["stemMarkdown"] == second_draft["content"]["stemMarkdown"]
    assert first_draft["content"]["options"] == second_draft["content"]["options"]
    assert harness.import_detail(second_import)["drafts"][0]["duplicateOfQuestionId"] is None
    second = submit(harness, second_import, second_draft, "g1-material-second", action)
    assert second["failures"] == [] and second["skippedDraftIds"] == []
    assert len(second["confirmedQuestionIds"]) == 1
    assert harness.service.list_questions().total == 2


@pytest.mark.parametrize("change", ["stem", "option", "formula", "table-layout", "table-text", "material-formula", "material-table", "image-bytes"])
def test_authoritative_surface_changes_are_not_duplicates(harness, change):
    first_import, first_draft = create_rich(harness, change=(lambda c: add_image(harness, c, png_rgb(0, 0, 255)))
                                           if change == "image-bytes" else None)
    assert len(submit(harness, first_import, first_draft, "g1-surface-first")["confirmedQuestionIds"]) == 1

    def edit(c):
        rc = c["richContent"]
        if change == "stem":
            rc["stemBlocks"][0]["text"] += " 新条件。"
        elif change == "option":
            rc["optionBlocks"]["A"][0]["text"] += " 新选项。"
        elif change == "formula":
            rc["stemBlocks"][2]["ommlXml"] = "<m:oMath><m:r><m:t>z</m:t></m:r></m:oMath>"
        elif change == "table-layout":
            rc["stemBlocks"][1]["cells"][0]["colSpan"] = 1
        elif change == "table-text":
            rc["stemBlocks"][1]["cells"][1]["text"] = "丙"
        elif change == "material-formula":
            rc["sharedMaterials"][0]["blocks"].append({"id": "material-formula", "kind": "formula", "latex": "y+1"})
        elif change == "material-table":
            rc["sharedMaterials"][0]["blocks"].append({"id": "material-table", "kind": "table", "columnCount": 1,
                                                       "cells": [{"text": "2 mol/L"}]})
        else:
            add_image(harness, c, png_rgb(255, 0, 0))
    second_import, second_draft = create_rich(harness, change=edit)
    assert harness.import_detail(second_import)["drafts"][0]["duplicateOfQuestionId"] is None
    result = submit(harness, second_import, second_draft, "g1-surface-second", "edit_as_new")
    assert result["failures"] == [] and len(result["confirmedQuestionIds"]) == 1
    assert harness.service.list_questions().total == 2


@pytest.mark.parametrize("action", [None, "link_existing", "edit_as_new"])
def test_true_repeat_ignores_origin_random_ids_and_keeps_answer_conflict_review(harness, action):
    first_import, first_draft = create_rich(harness)
    question_id = submit(harness, first_import, first_draft, "g1-repeat-first")["confirmedQuestionIds"][0]
    before = harness.catalog.get_question(question_id)

    def edit(c):
        rc = c["richContent"]
        rc["origin"]["sourceLocator"] = {"kind": "markdown", "lineStart": 999}
        blocks = [*[block for material in rc["sharedMaterials"] for block in material["blocks"]],
                  *rc["stemBlocks"], *[block for group in rc["optionBlocks"].values() for block in group],
                  *rc["answerBlocks"], *rc["explanationBlocks"]]
        for index, block in enumerate(blocks):
            block["id"] = f"independent-{index}"
        rc["sharedMaterials"][0]["id"] = "different-material-id"
        rc["sharedMaterials"][0]["blocks"][0]["id"] = "different-material-block-id"
        rc["stemBlocks"][0]["id"] = "different-stem-block-id"
        c["answer"]["choiceKeys"] = ["B"]
        rc["answerBlocks"][0]["text"] = "B"
        c["explanationMarkdown"] = "教师校对另一答案。"
        rc["explanationBlocks"][0]["text"] = c["explanationMarkdown"]
    second_import, second_draft = create_rich(harness, change=edit)
    preview = harness.import_detail(second_import)["drafts"][0]
    assert preview["duplicateOfQuestionId"] == question_id
    assert any("答案不同" in warning for warning in preview["warnings"])
    assert fp.duplicate_content_fingerprint(first_draft["content"]) == fp.duplicate_content_fingerprint(second_draft["content"])
    result = submit(harness, second_import, second_draft, "g1-repeat-second", action)
    if action == "edit_as_new":
        assert [failure["code"] for failure in result["failures"]] == ["DUPLICATE_UNRESOLVED"]
        assert harness.catalog.get_submission("g1-repeat-second") is None
    elif action == "link_existing":
        assert result["linkedQuestionIds"] == [question_id]
    else:
        assert result["skippedDraftIds"] == [second_draft["draftId"]]
    assert harness.service.list_questions().total == 1
    assert harness.catalog.get_question(question_id).content == before.content
    assert harness.catalog.get_draft(second_draft["draftId"]).content["answer"]["choiceKeys"] == ["B"]


@pytest.mark.parametrize("legacy_kind", ["plain", "rich"])
def test_missing_new_algorithm_old_fingerprint_only_is_read_only_compatible(harness, legacy_kind, monkeypatch):
    if legacy_kind == "rich":
        first_import, first_draft = create_rich(harness)
    else:
        first_import, first_draft = upload_and_review(harness, ONE_QUESTION_DOC)
    question_id = submit(harness, first_import, first_draft, "g1-legacy-first")["confirmedQuestionIds"][0]
    record = harness.catalog.get_question(question_id)
    # Model a pre-new-algorithm revision: historical rows/old composition are unchanged.
    with harness.catalog.write_transaction() as conn:
        conn.execute("DELETE FROM question_content_fingerprints WHERE algorithm_version = ?", (fp.DUPLICATE_ALGORITHM_VERSION,))
    old_derived = harness.catalog.derived_fingerprint(record.current_revision_id, algorithm_version="derived-v1")
    if legacy_kind == "rich":
        second_import, second_draft = create_rich(harness)
    else:
        second_import, second_draft = upload_and_review(harness, ONE_QUESTION_DOC)
    def no_io(*args, **kwargs):
        raise AssertionError("legacy duplicate preview must not start asset IO")
    monkeypatch.setattr(rich, "read_asset", no_io)
    assert harness.import_detail(second_import)["drafts"][0]["duplicateOfQuestionId"] == question_id
    result = submit(harness, second_import, second_draft, "g1-legacy-second")
    assert result["skippedDraftIds"] == [second_draft["draftId"]]
    assert harness.catalog.derived_fingerprint(record.current_revision_id, algorithm_version="derived-v1") == old_derived
    assert harness.catalog.derived_fingerprint(record.current_revision_id, algorithm_version=fp.DUPLICATE_ALGORITHM_VERSION) is None
    assert harness.catalog.get_question(question_id).content_fingerprint == record.content_fingerprint


def test_same_image_bytes_across_managed_and_legacy_storage_are_duplicate(harness):
    first_import, first_draft = create_rich(harness, change=lambda c: add_image(harness, c, png_rgb(0, 0, 255)))
    question_id = submit(harness, first_import, first_draft, "g1-alias-first")["confirmedQuestionIds"][0]
    second_import, second_draft = create_rich(harness, change=lambda c: add_image(harness, c, png_rgb(0, 0, 255), storage="bare"))
    assert first_draft["content"]["assetIds"] != second_draft["content"]["assetIds"]
    assert harness.import_detail(second_import)["drafts"][0]["duplicateOfQuestionId"] == question_id
    assert submit(harness, second_import, second_draft, "g1-alias-second")["skippedDraftIds"] == [second_draft["draftId"]]


def test_existing_submission_replay_precedes_all_new_asset_or_identity_validation(harness, monkeypatch):
    import_id, draft = create_rich(harness, change=lambda c: add_image(harness, c, png_rgb(0, 0, 255)))
    first = submit(harness, import_id, draft, "g1-replay")
    def forbidden(*args, **kwargs):
        raise AssertionError("successful receipt must replay before new validation")
    monkeypatch.setattr(harness.service, "_derived_fingerprint", forbidden)
    monkeypatch.setattr(fp, "duplicate_content_fingerprint", forbidden)
    assert submit(harness, import_id, draft, "g1-replay") == first


def test_new_algorithm_publish_and_formal_patch_rollback_with_revision(harness, monkeypatch):
    import_id, draft = create_rich(harness)
    actual = harness.catalog.save_derived_fingerprint_in
    def fail_surface(*args, **kwargs):
        if kwargs["algorithm_version"] == fp.DUPLICATE_ALGORITHM_VERSION:
            raise RuntimeError("surface persistence failure")
        return actual(*args, **kwargs)
    monkeypatch.setattr(harness.catalog, "save_derived_fingerprint_in", fail_surface)
    with pytest.raises(RuntimeError, match="surface persistence failure"):
        submit(harness, import_id, draft, "g1-rollback")
    assert harness.service.list_questions().total == 0
    assert harness.catalog.get_submission("g1-rollback") is None
    monkeypatch.setattr(harness.catalog, "save_derived_fingerprint_in", actual)
    question_id = submit(harness, import_id, draft, "g1-rollback")["confirmedQuestionIds"][0]
    before = harness.client.get(f"/api/v1/questions/{question_id}").json()
    changed = copy.deepcopy(before["content"])
    changed["richContent"]["sharedMaterials"][0]["blocks"][0]["text"] = "新固定材料"
    monkeypatch.setattr(harness.catalog, "save_derived_fingerprint_in", fail_surface)
    with pytest.raises(RuntimeError, match="surface persistence failure"):
        harness.client.patch(f"/api/v1/questions/{question_id}", json={"expectedRevision": before["revision"],
            "content": changed, "metadata": before["metadata"]})
    assert harness.client.get(f"/api/v1/questions/{question_id}").json() == before


def test_legacy_plain_and_equivalent_paragraph_only_rich_are_duplicate(harness):
    import_id, draft = upload_and_review(harness, ONE_QUESTION_DOC)
    question_id = submit(harness, import_id, draft, "g1-equivalent-plain")["confirmedQuestionIds"][0]
    second_import, raw = upload_one(harness)
    content = rich_content(harness, second_import, raw)
    content["richContent"]["sharedMaterials"] = []
    content["richContent"]["stemBlocks"] = content["richContent"]["stemBlocks"][:1]
    second = save_review(harness, second_import, content)
    assert harness.import_detail(second_import)["drafts"][0]["duplicateOfQuestionId"] == question_id
    assert submit(harness, second_import, second, "g1-equivalent-rich")["skippedDraftIds"] == [second["draftId"]]


@pytest.mark.parametrize("action", [None, "edit_as_new"])
def test_two_true_repeats_in_one_confirmation_package_cannot_create_two_questions(harness, action):
    document = ONE_QUESTION_DOC + "\n" + ONE_QUESTION_DOC.replace("1.", "2.", 1)
    response = harness.upload(document)
    assert response.status_code == 201, response.text
    import_id = response.json()["importId"]
    drafts = harness.import_detail(import_id)["drafts"]
    reviewed = []
    for draft in drafts:
        result = harness.patch_draft(draft)
        assert result.status_code == 200, result.text
        reviewed.append(result.json())
    resolutions = [{"draftId": reviewed[1]["draftId"], "action": action}] if action else []
    result = confirm(harness, import_id, [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}
        for draft in reviewed], submission_id="g1-within-batch", resolutions=resolutions)
    assert result.status_code == 200, result.text
    if action:
        assert [failure["code"] for failure in result.json()["failures"]] == ["DUPLICATE_UNRESOLVED"]
        assert harness.service.list_questions().total == 0
        assert harness.catalog.get_submission("g1-within-batch") is None
    else:
        assert len(result.json()["confirmedQuestionIds"]) == 1
        assert result.json()["skippedDraftIds"] == [reviewed[1]["draftId"]]
        assert harness.service.list_questions().total == 1


def test_teacher_explanation_image_does_not_create_a_new_surface(harness):
    first_import, first_draft = create_rich(harness)
    question_id = submit(harness, first_import, first_draft, "g1-teacher-first")["confirmedQuestionIds"][0]
    def edit(c):
        data = png_rgb(0, 255, 0)
        asset_id = harness.service.assets.store_original(data, media_type="image/png", original_name="teacher.png").blob_key
        c["richContent"]["explanationBlocks"].append({"id": "teacher-image", "kind": "image", "assetId": asset_id, "width": 1, "height": 1})
        c["richContent"]["assets"].append({"assetId": asset_id, "sha256": hashlib.sha256(data).hexdigest(), "mediaType": "image/png"})
        c["assetIds"].append(asset_id)
        c["explanationMarkdown"] = rich.project_blocks(RichContentV2.model_validate(c["richContent"]).explanation_blocks)
    second_import, second_draft = create_rich(harness, change=edit)
    assert fp.duplicate_content_fingerprint(first_draft["content"]) == fp.duplicate_content_fingerprint(second_draft["content"])
    assert harness.import_detail(second_import)["drafts"][0]["duplicateOfQuestionId"] == question_id
    assert submit(harness, second_import, second_draft, "g1-teacher-second")["skippedDraftIds"] == [second_draft["draftId"]]
