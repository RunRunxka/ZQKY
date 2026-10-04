"""Read-only G1 follow-up review: fresh temporary roots, no real listener."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

QA = Path(__file__).resolve().parent
REPO = QA.parents[3]
ROOT = Path(tempfile.mkdtemp(prefix="zqky-g1-review-score-qb-"))
os.environ["ZQKY_DATA_DIR"] = str(ROOT / "bootstrap")
os.environ["ZQKY_ENV"] = "test"
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, str(REPO / "apps" / "api"))

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.tabular import read_score_sheet
from tests import test_question_bank as harness_module
from tests.test_question_bank_confirm import confirm, set_content_and_review
from tests.test_question_rich_content import PNG, rich_content, upload_one

RESULTS = []


def run(name, probe):
    probe()
    RESULTS.append({"name": name, "status": "pass"})


def csv_bytes(rows, encoding="utf-8-sig"):
    buffer = io.StringIO(newline="")
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue().encode(encoding)


def score_gb18030_full_text():
    number = "1." + "0" * 19998
    sheet = read_score_sheet(csv_bytes([["学号", "姓名", "Q1"], ["0007", "独立甲", number]], "gb18030"))[0]
    assert sheet.rows[1][0].text == "0007"
    assert sheet.rows[1][1].text == "独立甲"
    assert sheet.rows[1][2].text == number
    assert sheet.rows[1][2].cached_text == number


def score_csv_length_coordinate():
    try:
        read_score_sheet(csv_bytes([[], ["学号", "Q1"], ["0007", "1." + "0" * 19998 + "1"]]))
    except AppError as exc:
        assert exc.code == "TABLE_TOO_LARGE"
        assert exc.details["address"] == "B3"
        assert exc.details["actualLength"] == 20001
        assert exc.details["view"] == "csv"
    else:
        raise AssertionError("overlong score accepted")


def score_bad_encoding():
    try:
        read_score_sheet(b"\xff")
    except AppError as exc:
        assert exc.code == "TABLE_PARSE_FAILED" and exc.status_code == 422
    else:
        raise AssertionError("invalid encoding accepted")


def new_harness(name):
    def isolated_settings(path):
        return Settings(host="127.0.0.1", port=8001, env="test",
                        allowed_origins=frozenset({"http://127.0.0.1:5174"}),
                        data_dir=path / "data", credentials_file=None)
    harness_module.make_settings = isolated_settings
    return harness_module.open_harness(ROOT / name)


def make_rich(h, material):
    import_id, draft = upload_one(h)
    content = rich_content(h, import_id, draft)
    content["richContent"]["sharedMaterials"][0]["blocks"][0]["text"] = material
    reviewed = set_content_and_review(h, import_id, 0, content)
    return import_id, reviewed


def submit(h, import_id, draft, key):
    response = confirm(h, import_id, [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}], submission_id=key)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["failures"] == [], result
    return result


def formal_patch_current_surface():
    h = new_harness("formal-patch")
    try:
        imp1, draft1 = make_rich(h, "共同材料：1 mol/L。")
        qid = submit(h, imp1, draft1, "review-current-first")["confirmedQuestionIds"][0]
        original = h.catalog.get_question(qid)
        with h.catalog._read() as conn:
            old_revision = dict(conn.execute("SELECT * FROM question_revisions WHERE id=?", (original.current_revision_id,)).fetchone())
            old_fingerprints = [dict(row) for row in conn.execute("SELECT * FROM question_content_fingerprints WHERE question_revision_id=? ORDER BY algorithm_version", (original.current_revision_id,))]
        detail = h.client.get(f"/api/v1/questions/{qid}").json()
        changed = copy.deepcopy(detail["content"])
        changed["richContent"]["sharedMaterials"][0]["blocks"][0]["text"] = "共同材料：2 mol/L。"
        patched = h.client.patch(f"/api/v1/questions/{qid}", json={"expectedRevision": detail["revision"], "content": changed, "metadata": detail["metadata"]})
        assert patched.status_code == 200, patched.text
        new_id = h.catalog.get_question(qid).current_revision_id
        assert new_id != original.current_revision_id
        imp2, draft2 = make_rich(h, "共同材料：2 mol/L。")
        assert draft2["duplicateOfQuestionId"] == qid
        assert submit(h, imp2, draft2, "review-current-repeated")["skippedDraftIds"] == [draft2["draftId"]]
        imp3, draft3 = make_rich(h, "共同材料：1 mol/L。")
        assert draft3["duplicateOfQuestionId"] is None
        assert len(submit(h, imp3, draft3, "review-current-old-new")["confirmedQuestionIds"]) == 1
        assert h.service.list_questions().total == 2
        with h.catalog._read() as conn:
            assert dict(conn.execute("SELECT * FROM question_revisions WHERE id=?", (original.current_revision_id,)).fetchone()) == old_revision
            assert [dict(row) for row in conn.execute("SELECT * FROM question_content_fingerprints WHERE question_revision_id=? ORDER BY algorithm_version", (original.current_revision_id,))] == old_fingerprints
            assert {row[0] for row in conn.execute("SELECT algorithm_version FROM question_content_fingerprints WHERE question_revision_id=?", (new_id,))} == {"derived-v1", "question-surface-v1"}
    finally:
        h.close()


def teacher_image_does_not_create_new_surface():
    h = new_harness("teacher-image")
    try:
        imp1, draft1 = make_rich(h, "共同材料：固定。")
        qid = submit(h, imp1, draft1, "review-teacher-first")["confirmedQuestionIds"][0]
        before = h.catalog.get_question(qid)
        imp2, draft2 = upload_one(h)
        content = rich_content(h, imp2, draft2)
        content["richContent"]["sharedMaterials"][0]["blocks"][0]["text"] = "共同材料：固定。"
        aid = h.service.assets.store_original(PNG, media_type="image/png", original_name="teacher.png").blob_key
        content["richContent"]["explanationBlocks"].append({"id": "teacher-image-only", "kind": "image", "assetId": aid, "width": 1, "height": 1})
        content["richContent"]["assets"].append({"assetId": aid, "sha256": hashlib.sha256(PNG).hexdigest(), "mediaType": "image/png"})
        content["assetIds"] = [aid]
        content["explanationMarkdown"] += f"\n\n![图片]({aid})"
        draft2 = set_content_and_review(h, imp2, 0, content)
        assert draft2["duplicateOfQuestionId"] == qid
        assert submit(h, imp2, draft2, "review-teacher-repeat")["skippedDraftIds"] == [draft2["draftId"]]
        assert h.service.list_questions().total == 1
        assert h.catalog.get_question(qid).content == before.content
    finally:
        h.close()


if __name__ == "__main__":
    try:
        run("GB18030完整20000字及前导零", score_gb18030_full_text)
        run("CSV超限精确B3拒绝", score_csv_length_coordinate)
        run("非法编码明确422", score_bad_encoding)
        run("正式改题当前修订查重及旧修订保留", formal_patch_current_surface)
        run("教师解析图片不造新题且不覆盖已有题", teacher_image_does_not_create_new_surface)
    finally:
        (QA / "probe-results.json").write_text(json.dumps({"results": RESULTS, "temporaryRoot": str(ROOT), "credentialsFile": None, "rootRetained": True}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": len(RESULTS), "failed": 0, "temporaryRoot": str(ROOT)}, ensure_ascii=False))
