"""V00: independently constructed structured content and adversarial image bytes."""
from __future__ import annotations
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[4]
BOOT_ROOT = Path(tempfile.mkdtemp(prefix="zqky-v00-rich-bootstrap-"))
os.environ["ZQKY_DATA_DIR"] = str(BOOT_ROOT)
os.environ["ZQKY_ENV"] = "test"
sys.path.insert(0, str(ROOT / "apps/api"))
import pytest
from app.core.exceptions import AppError
from app.services.question_bank.service import build_question_bank_service
from app.services.question_bank import rich
from tests.test_question_bank import open_harness

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aP5sAAAAASUVORK5CYII=")
DOC = "1. 比较下列观察结果，正确的是（ ）\nA. 甲\nB. 乙\n答案：A\n解析：依据共同实验。\n"
EVENTS = []

@pytest.fixture(scope="session", autouse=True)
def rich_evidence():
    yield
    (Path(__file__).parent / "rich-http-evidence.json").write_text(json.dumps(EVENTS, ensure_ascii=False, indent=2), encoding="utf-8")
    assert BOOT_ROOT.resolve().parent == Path(tempfile.gettempdir()).resolve()
    shutil.rmtree(BOOT_ROOT)
    from tests.conftest import _PYTEST_DATA_DIR
    assert _PYTEST_DATA_DIR.resolve().parent == Path(tempfile.gettempdir()).resolve()
    if _PYTEST_DATA_DIR.exists():
        shutil.rmtree(_PYTEST_DATA_DIR)

@pytest.fixture()
def h(tmp_path):
    instance = open_harness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()

def error(response, code, status=422):
    EVENTS.append({"status": response.status_code, "body": response.json()})
    assert response.status_code == status, response.text
    assert response.json()["code"] == code

def scene(h, *, image=True, storage="managed"):
    u = h.upload(DOC, subjectId="math")
    assert u.status_code == 201, u.text
    imported = u.json()
    d = imported["drafts"][0]
    content = copy.deepcopy(d["content"])
    aid = None
    if image:
        if storage == "managed":
            aid = h.service.assets.store_original(PNG, media_type="image/png", original_name="pixel.png").blob_key
        else:
            digest, _ = h.service.blobs.write(PNG)
            aid = digest if storage == "legacy-bare" else "blobs/" + digest
    content["stemMarkdown"] = "观察实验。\n\n[表格]\n表头 | 甲 | 乙\n\n$$x^2$$" + (f"\n\n![图片]({aid})" if image else "")
    content["assetIds"] = [aid] if image else []
    source = h.catalog.get_import(imported["importId"])
    content["richContent"] = {
        "version": 2,
        "sharedMaterials": [{"id": "mat-v00", "blocks": [{"id": "mat-p-v00", "kind": "paragraph", "text": "共同实验：观察甲乙。"}]}],
        "stemBlocks": [
            {"id": "s-p", "kind": "paragraph", "text": "观察实验。"},
            {"id": "s-t", "kind": "table", "columnCount": 2, "cells": [{"text": "表头", "isHeader": True, "rowSpan": 1, "colSpan": 2}, {"text": "甲", "isHeader": False, "rowSpan": 1, "colSpan": 1}, {"text": "乙", "isHeader": False, "rowSpan": 1, "colSpan": 1}]},
            {"id": "s-f", "kind": "formula", "latex": "x^2", "ommlXml": '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:r><m:t>x</m:t></m:r></m:oMath>'},
        ] + ([{"id": "s-img", "kind": "image", "assetId": aid, "width": 10, "height": 20}] if image else []),
        "optionBlocks": {x["key"]: [{"id": "opt-" + x["key"], "kind": "paragraph", "text": x["textMarkdown"]}] for x in content["options"]},
        "answerBlocks": [{"id": "a-v00", "kind": "paragraph", "text": "A"}],
        "explanationBlocks": [{"id": "e-v00", "kind": "paragraph", "text": content["explanationMarkdown"]}],
        "assets": ([{"assetId": aid, "sha256": hashlib.sha256(PNG).hexdigest(), "mediaType": "image/png"}] if image else []),
        "origin": {"originalAssetId": source.original_blob_id, "originalSha256": source.file_sha256, "sourceLocator": {"kind": "markdown", "lineStart": 1}},
    }
    saved = h.patch_draft(d, content=content)
    assert saved.status_code == 200, saved.text
    reviewed = h.patch_draft(saved.json())
    assert reviewed.status_code == 200 and reviewed.json()["reviewState"] == "reviewed"
    return imported["importId"], reviewed.json(), aid

def confirm(h, iid, d, *, key="v00-rich"):
    return h.client.post(f"/api/v1/question-imports/{iid}/confirm", json={"submissionId": key, "importId": iid, "items": [{"draftId": d["draftId"], "expectedDraftRevision": d["revision"]}], "duplicateResolutions": []})

def patch_question(h, detail, content):
    return h.client.patch(f'/api/v1/questions/{detail["questionId"]}', json={"expectedRevision": detail["revision"], "content": content, "metadata": detail["metadata"]})

@pytest.mark.parametrize("storage", ["managed", "legacy-managed", "legacy-bare"])
def test_roundtrip_asset_bytes_shared_table_omml_and_owner(h, storage):
    iid, draft, aid = scene(h, storage=storage)
    read = h.client.get(f'/api/v1/question-drafts/{draft["draftId"]}/assets/{aid}/content')
    assert read.status_code == 200 and read.content == PNG and read.headers["content-type"] == "image/png"
    wrong = build_question_bank_service(h.catalog, h.settings, owner_id="v00-other-owner")
    with pytest.raises(AppError) as blocked:
        wrong.get_content_asset("draft", draft["draftId"], aid)
    assert blocked.value.code == "DRAFT_NOT_FOUND" and blocked.value.status_code == 404
    result = confirm(h, iid, draft)
    assert result.status_code == 200 and not result.json()["failures"], result.text
    qid = result.json()["confirmedQuestionIds"][0]
    detail = h.client.get(f"/api/v1/questions/{qid}").json()
    assert detail["content"] == draft["content"]
    assert detail["content"]["richContent"]["stemBlocks"][1]["cells"][0]["colSpan"] == 2
    assert detail["content"]["richContent"]["stemBlocks"][2]["ommlXml"].startswith("<m:oMath")
    assert h.service.get_content_asset("question", qid, aid) == (PNG, "image/png")
    with pytest.raises(AppError) as qblocked:
        wrong.get_content_asset("question", qid, aid)
    assert qblocked.value.code == "QUESTION_NOT_FOUND"

@pytest.mark.parametrize("mutation,field", [("stem", "content.stemMarkdown"), ("answer", "content.answer"), ("option", "content.options.A.textMarkdown"), ("explain", "content.explanationMarkdown")])
def test_authority_cannot_ignore_plain_edits(h, mutation, field):
    iid, d, _ = scene(h, image=False)
    content = copy.deepcopy(d["content"])
    if mutation == "stem": content["stemMarkdown"] += "偷改文字"
    elif mutation == "answer": content["answer"]["choiceKeys"] = ["B"]
    elif mutation == "option": content["options"][0]["textMarkdown"] += "偷改"
    else: content["explanationMarkdown"] += "偷改"
    r = h.patch_draft(d, content=content)
    error(r, "QUESTION_RICH_CONTENT_MISMATCH")
    assert any(x["field"] == field for x in r.json()["details"]["issues"])
    assert h.import_detail(iid)["drafts"][0] == d

def test_clear_explicit_null_and_current_reference_removal_preserves_old(h):
    iid, d, aid = scene(h)
    qid = confirm(h, iid, d).json()["confirmedQuestionIds"][0]
    detail = h.client.get(f"/api/v1/questions/{qid}").json()
    original = h.catalog.get_question(qid)
    with h.catalog._read() as conn:
        oldjson = conn.execute("SELECT content_json FROM question_revisions WHERE id=?", (original.current_revision_id,)).fetchone()["content_json"]
    content = copy.deepcopy(detail["content"])
    del content["richContent"]
    content["stemMarkdown"] = "转成普通文本"
    error(patch_question(h, detail, content), "QUESTION_RICH_CONTENT_CLEAR_REQUIRED")
    content["richContent"] = None
    content["assetIds"] = []
    success = patch_question(h, detail, content)
    assert success.status_code == 200 and success.json()["revision"] == detail["revision"] + 1
    error(h.client.get(f"/api/v1/questions/{qid}/assets/{aid}/content"), "QUESTION_ASSET_NOT_FOUND", 404)
    with h.catalog._read() as conn:
        assert conn.execute("SELECT content_json FROM question_revisions WHERE id=?", (original.current_revision_id,)).fetchone()["content_json"] == oldjson
    assert h.service.assets.read(aid) == PNG

@pytest.mark.parametrize("kind", ["span", "shared", "image-dimensions"])
def test_derived_fingerprint_structure_and_shared_changes_keep_legacy(h, kind):
    iid, d, aid = scene(h)
    qid = confirm(h, iid, d).json()["confirmedQuestionIds"][0]
    before = h.catalog.get_question(qid)
    oldfp = h.catalog.derived_fingerprint(before.current_revision_id, algorithm_version="derived-v1")
    content = copy.deepcopy(h.client.get(f"/api/v1/questions/{qid}").json()["content"])
    if kind == "span": content["richContent"]["stemBlocks"][1]["cells"][0]["colSpan"] = 1
    elif kind == "shared": content["richContent"]["sharedMaterials"][0]["blocks"][0]["text"] += " 新条件。"
    else: content["richContent"]["stemBlocks"][-1]["width"] = 30
    response = patch_question(h, h.client.get(f"/api/v1/questions/{qid}").json(), content)
    assert response.status_code == 200, response.text
    after = h.catalog.get_question(qid)
    assert before.content_fingerprint == after.content_fingerprint
    assert oldfp != h.catalog.derived_fingerprint(after.current_revision_id, algorithm_version="derived-v1")
    assert oldfp == h.catalog.derived_fingerprint(before.current_revision_id, algorithm_version="derived-v1")

@pytest.mark.parametrize("mutation,code", [("hash", "QUESTION_ASSET_DIGEST_MISMATCH"), ("media", "QUESTION_ASSET_MEDIA_INVALID"), ("dangling", "QUESTION_RICH_CONTENT_INVALID")])
def test_asset_declaration_falsehood_is_located_before_write(h, mutation, code):
    iid, d, _ = scene(h)
    content = copy.deepcopy(d["content"])
    if mutation == "hash": content["richContent"]["assets"][0]["sha256"] = "a" * 64
    elif mutation == "media": content["richContent"]["assets"][0]["mediaType"] = "image/jpeg"
    else: content["assetIds"] = []
    response = h.patch_draft(d, content=content)
    error(response, code)
    assert response.json()["details"]["issues"]
    assert h.import_detail(iid)["drafts"][0] == d

def test_managed_corruption_cannot_fall_back_and_confirm_is_zero_write(h):
    iid, d, aid = scene(h)
    h.service.blobs.write(PNG)  # genuine legacy fallback exists
    h.service.assets.path_of(aid).write_bytes(b"bad-primary-copy")
    read = h.client.get(f'/api/v1/question-drafts/{d["draftId"]}/assets/{aid}/content')
    error(read, "ASSET_CORRUPT", 500)
    attempted = confirm(h, iid, d)
    assert attempted.status_code == 200 and attempted.json()["confirmedQuestionIds"] == []
    assert attempted.json()["failures"][0]["code"] == "ASSET_CORRUPT"
    assert h.catalog.get_submission("v00-rich") is None
    assert h.service.list_questions().total == 0

def test_confirm_replay_precedes_missing_byte_read_and_publish_io_outside_lock(h, monkeypatch):
    iid, d, aid = scene(h)
    actualread = rich.read_asset
    originaltx = h.catalog.write_transaction
    originalpublication = h.service._publication
    active = {"transaction": False, "publication": False, "reads": 0}
    @contextmanager
    def tx():
        with originaltx() as conn:
            active["transaction"] = True
            try: yield conn
            finally: active["transaction"] = False
    @contextmanager
    def publication(operation):
        with originalpublication(operation):
            active["publication"] = True
            try: yield
            finally: active["publication"] = False
    def read(*args, **kwargs):
        assert not active["transaction"] and not active["publication"]
        active["reads"] += 1
        return actualread(*args, **kwargs)
    monkeypatch.setattr(h.catalog, "write_transaction", tx)
    monkeypatch.setattr(h.service, "_publication", publication)
    monkeypatch.setattr(rich, "read_asset", read)
    first = confirm(h, iid, d)
    assert first.status_code == 200 and first.json()["failures"] == [] and active["reads"] > 0
    h.service.assets.path_of(aid).unlink()
    monkeypatch.setattr(rich, "read_asset", lambda *_a, **_k: pytest.fail("Replay reached image IO"))
    replay = confirm(h, iid, d)
    assert replay.status_code == 200 and replay.json() == first.json()

def test_preflight_cas_detects_draft_revision_changed_without_partial_confirm(h, monkeypatch):
    iid, d, _ = scene(h)
    original = h.service._derived_fingerprint
    def raced(content):
        result = original(content)
        h.catalog.set_draft_review_state(d["draftId"], expected_revision=d["revision"], review_state="needs_review")
        return result
    monkeypatch.setattr(h.service, "_derived_fingerprint", raced)
    result = confirm(h, iid, d)
    assert result.status_code == 200 and result.json()["confirmedQuestionIds"] == []
    assert result.json()["failures"][0]["code"] == "REVISION_CONFLICT"
    assert h.catalog.get_submission("v00-rich") is None and h.service.list_questions().total == 0


@pytest.mark.parametrize("asset", ["../outside", "blobs/../outside", "C:/outside.png", "blobs/" + "A" * 64])
def test_arbitrary_asset_paths_are_rejected_before_io(h, monkeypatch, asset):
    _, draft, _ = scene(h, image=False)
    monkeypatch.setattr(rich, "read_asset", lambda *_args, **_kwargs: pytest.fail("Illegal path reached file IO"))
    with pytest.raises(AppError) as blocked:
        h.service.get_content_asset("draft", draft["draftId"], asset)
    assert (blocked.value.code, blocked.value.status_code) == ("INVALID_ASSET_KEY", 422)


def test_unreferenced_real_image_never_opens_bytes(h, monkeypatch):
    _, draft, _ = scene(h)
    extra = h.service.assets.store_original(PNG + b"other", media_type="image/png", original_name="unused.png").blob_key
    monkeypatch.setattr(rich, "read_asset", lambda *_args, **_kwargs: pytest.fail("Unreferenced image reached file IO"))
    with pytest.raises(AppError) as blocked:
        h.service.get_content_asset("draft", draft["draftId"], extra)
    assert (blocked.value.code, blocked.value.status_code) == ("QUESTION_ASSET_NOT_FOUND", 404)


def test_rich_split_rejects_before_content_loss(h):
    iid, draft, _ = scene(h)
    spans = draft["sourceSpans"]
    offset = (min(x["charStart"] for x in spans) + max(x["charEnd"] for x in spans)) // 2
    response = h.client.post(f"/api/v1/question-imports/{iid}/split", params={"draftId": draft["draftId"]}, json={"expectedRevision": draft["revision"], "charOffset": offset})
    error(response, "QUESTION_RICH_CONTENT_EDIT_UNSUPPORTED")
    assert response.json()["details"]["issues"][0]["field"] == "content.richContent"
    assert h.import_detail(iid)["drafts"][0] == draft


def test_rich_ai_accept_reject_is_explicit_not_silent_loss(h):
    iid, draft, _ = scene(h)
    response = h.client.post(f"/api/v1/question-imports/{iid}/organize", json={"draftIds": [draft["draftId"]], "includeUnassigned": False, "modelProfileId": "chat-model-local"})
    # This isolated Harness deliberately injects the inline organizer adapter;
    # shared-engine queued/create/retry acceptance belongs to root/G0 fixtures.
    assert response.status_code == 200 and response.json()["state"] == "succeeded", response.text
    assert len(h.provider.calls) == 1
    suggestions = h.catalog.list_suggestions(organization_job_id=response.json()["jobId"])
    assert len(suggestions) == 1
    sid = suggestions[0].suggestion_id
    accepted = h.client.post(f"/api/v1/question-suggestions/{sid}/apply", json={"expectedDraftRevision": draft["revision"], "accept": True})
    error(accepted, "QUESTION_RICH_CONTENT_EDIT_UNSUPPORTED")
    assert accepted.json()["details"]["issues"][0]["field"] == "content.richContent"
    assert h.catalog.get_suggestion(sid).state == "pending"
    rejected = h.client.post(f"/api/v1/question-suggestions/{sid}/apply", json={"expectedDraftRevision": draft["revision"], "accept": False})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["content"] == draft["content"]
    assert h.catalog.get_draft(draft["draftId"]).revision == draft["revision"]
