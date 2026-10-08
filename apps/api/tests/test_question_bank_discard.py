"""放弃未确认题库导入批次（POST /question-imports/{id}/discard）。

语义与名单批次 ``discard_roster_import`` 一致：
- 状态置 ``cancelled``，批次记录/原始文件/原文块/草稿行全部保留（审计，不删行）；
- 已确认批次不可放弃（409 ``IMPORT_ALREADY_CONFIRMED``）；
- 已放弃批次重复放弃幂等返回（state 不变，revision 不再递增）；
- ``expectedRevision`` 不符 409 ``REVISION_CONFLICT``；
- 放弃后不能再 split / merge / organize / confirm（``IMPORT_CANCELLED``，不放宽既有守卫）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_question_bank import Harness, make_settings, open_harness

ONE_QUESTION_DOC = """1. 下列说法正确的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
答案：A
解析：甲说法正确。
"""

#: 两道题：merge 守卫测试需要至少两条草稿
TWO_QUESTION_DOC = ONE_QUESTION_DOC + """
2. 下列说法错误的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
答案：B
解析：乙说法错误。
"""


@pytest.fixture()
def harness(tmp_path: Path):
    instance = open_harness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def discard(harness: Harness, import_id: str, body: dict | None = None):
    return harness.client.post(
        f"/api/v1/question-imports/{import_id}/discard", json=body or {}
    )


def test_discard_sets_cancelled_and_keeps_rows(harness: Harness) -> None:
    """放弃后 state=cancelled、revision+1；原文块与草稿行全部保留（审计不删行）。"""
    detail = harness.upload(ONE_QUESTION_DOC).json()
    assert detail["state"] == "needs_review"
    import_id = detail["importId"]
    draft_count = len(detail["drafts"])
    block_count = len(harness.catalog.list_source_blocks(import_id))
    assert draft_count > 0 and block_count > 0

    response = discard(harness, import_id, {"expectedRevision": detail["revision"]})
    assert response.status_code == 200, response.text
    body = response.json()
    # 详情视图原形状：state/revision 在摘要字段里
    assert body["state"] == "cancelled"
    assert body["revision"] == detail["revision"] + 1
    assert body["importId"] == import_id
    assert body["uploadedFileName"] == detail["uploadedFileName"]

    # 只改状态：原文块、草稿行与行数完全不动
    assert len(harness.catalog.list_source_blocks(import_id)) == block_count
    assert len(harness.catalog.list_drafts(import_id)) == draft_count
    reloaded = harness.import_detail(import_id)
    assert reloaded["state"] == "cancelled"
    assert len(reloaded["drafts"]) == draft_count
    assert len(reloaded["unassignedBlocks"]) == len(detail["unassignedBlocks"])


def test_discard_confirmed_import_is_409(harness: Harness) -> None:
    """已确认批次不可放弃：409 IMPORT_ALREADY_CONFIRMED，状态与数据不动。"""
    detail = harness.upload(ONE_QUESTION_DOC).json()
    draft = harness.import_detail(detail["importId"])["drafts"][0]
    reviewed = harness.patch_draft(draft)
    assert reviewed.status_code == 200, reviewed.text
    confirmed = harness.client.post(
        f"/api/v1/question-imports/{detail['importId']}/confirm",
        json={
            "submissionId": "sub-confirm-before-discard",
            "importId": detail["importId"],
            "items": [{"draftId": draft["draftId"], "expectedDraftRevision": reviewed.json()["revision"]}],
            "duplicateResolutions": [],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["confirmedQuestionIds"], confirmed.text

    import_id = detail["importId"]
    before = harness.import_detail(import_id)
    response = discard(harness, import_id, {"expectedRevision": before["revision"]})
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "IMPORT_ALREADY_CONFIRMED"
    assert harness.import_detail(import_id)["state"] == "confirmed"


def test_discard_is_idempotent_for_cancelled(harness: Harness) -> None:
    """重复放弃幂等：state 保持 cancelled，revision 不再递增。"""
    detail = harness.upload(ONE_QUESTION_DOC).json()
    import_id = detail["importId"]
    first = discard(harness, import_id, {"expectedRevision": detail["revision"]})
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["state"] == "cancelled"

    second = discard(harness, import_id, {"expectedRevision": first_body["revision"]})
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["state"] == "cancelled"
    assert second_body["revision"] == first_body["revision"]


def test_discard_revision_conflict_is_409(harness: Harness) -> None:
    """expectedRevision 不符：409 REVISION_CONFLICT，状态不变。"""
    detail = harness.upload(ONE_QUESTION_DOC).json()
    import_id = detail["importId"]
    stale = detail["revision"] + 99
    response = discard(harness, import_id, {"expectedRevision": stale})
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "REVISION_CONFLICT"
    assert harness.import_detail(import_id)["state"] == "needs_review"

    missing = harness.client.get("/api/v1/question-imports/nope")
    assert missing.status_code == 404  # 对照组：404 是导入缺失的形状
    discard_missing = discard(harness, "nope")
    assert discard_missing.status_code == 404, discard_missing.text
    assert discard_missing.json()["code"] == "IMPORT_NOT_FOUND"


def test_discarded_import_rejects_split_merge_organize(harness: Harness) -> None:
    """放弃后不可再 split / merge / organize（IMPORT_CANCELLED，既有守卫不放宽）。"""
    detail = harness.upload(TWO_QUESTION_DOC).json()
    import_id = detail["importId"]
    assert discard(harness, import_id, {"expectedRevision": detail["revision"]}).status_code == 200

    draft = harness.import_detail(import_id)["drafts"][0]
    split = harness.client.post(
        f"/api/v1/question-imports/{import_id}/split",
        params={"draftId": draft["draftId"]},
        json={"expectedRevision": draft["revision"], "charOffset": 5},
    )
    assert split.status_code == 409, split.text
    assert split.json()["code"] == "IMPORT_CANCELLED"

    another = harness.import_detail(import_id)["drafts"][1]
    merge = harness.client.post(
        f"/api/v1/question-imports/{import_id}/merge",
        json={
            "expectedRevisions": {
                draft["draftId"]: draft["revision"],
                another["draftId"]: another["revision"],
            }
        },
    )
    assert merge.status_code == 409, merge.text
    assert merge.json()["code"] == "IMPORT_CANCELLED"

    organize = harness.client.post(
        f"/api/v1/question-imports/{import_id}/organize",
        json={"draftIds": [], "includeUnassigned": False, "modelProfileId": "chat-model-local"},
    )
    assert organize.status_code == 409, organize.text
    assert organize.json()["code"] == "IMPORT_CANCELLED"


def test_discarded_import_rejects_confirm(harness: Harness) -> None:
    """放弃后不可确认入库（IMPORT_CANCELLED），且不写 submission、不产题目。"""
    detail = harness.upload(ONE_QUESTION_DOC).json()
    import_id = detail["importId"]
    assert discard(harness, import_id, {"expectedRevision": detail["revision"]}).status_code == 200

    draft = harness.import_detail(import_id)["drafts"][0]
    reviewed = harness.patch_draft(draft)
    assert reviewed.status_code == 200, reviewed.text

    confirmed = harness.client.post(
        f"/api/v1/question-imports/{import_id}/confirm",
        json={
            "submissionId": "sub-confirm-after-discard",
            "importId": import_id,
            "items": [{"draftId": draft["draftId"], "expectedDraftRevision": reviewed.json()["revision"]}],
            "duplicateResolutions": [],
        },
    )
    assert confirmed.status_code == 409, confirmed.text
    assert confirmed.json()["code"] == "IMPORT_CANCELLED"
    # 确认整体未执行：没有 submission 记录，也没有题目产生
    assert harness.catalog.get_submission("sub-confirm-after-discard") is None
    questions = harness.client.get("/api/v1/questions")
    assert questions.status_code == 200
    assert questions.json()["questions"] == []


def test_confirm_still_works_for_operable_import(harness: Harness) -> None:
    """回归对照：未放弃批次的确认路径不受新守卫影响。"""
    detail = harness.upload(ONE_QUESTION_DOC).json()
    draft = harness.import_detail(detail["importId"])["drafts"][0]
    reviewed = harness.patch_draft(draft)
    assert reviewed.status_code == 200, reviewed.text
    confirmed = harness.client.post(
        f"/api/v1/question-imports/{detail['importId']}/confirm",
        json={
            "submissionId": "sub-regression-confirm",
            "importId": detail["importId"],
            "items": [{"draftId": draft["draftId"], "expectedDraftRevision": reviewed.json()["revision"]}],
            "duplicateResolutions": [],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["confirmedQuestionIds"], confirmed.text
