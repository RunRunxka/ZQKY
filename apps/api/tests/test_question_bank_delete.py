"""彻底删除题库导入批次（DELETE /question-imports/{id}）。

与「放弃」的语义区分（两者都保留在文档里）：
- 放弃（``POST .../discard``）：状态置 ``cancelled``，批次/原文/草稿行**保留**（审计）；
- 彻底删除（``DELETE ...``）：批次与解析产物从库里**移除**。

删除语义（R10，2026-10-13 用户裁定「批次只是导入记录，不因来源追溯而不能删」）：
- **不再有阻断守卫**：已确认批次、草稿并入正式题都可删；
- 题目一律保留：``question_sources.import_id`` 置空（来源跨度保留，回执
  ``unlinkedQuestionSources``），批次自身的解析产物随批次删除。

单写事务按 FK 顺序删除：建议 → 草稿关联 → 原文块 → 草稿 → 来源登记 → 批次行；
**受管原件（blobs/<sha256>）不物理删除**：内容寻址、可能被其他批次复用，
回执与报告如实声明"只删库行，原件保留待清理策略"，不伪造"原件已删"。

触发器核对（2026-10-08）：题库仅有 ``question_knowledge_links``（题目修订关联）
的不可变 UPDATE/DELETE 触发器，本路径不触碰该表，其余表无触发器。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.test_question_bank import Harness, open_harness

ONE_QUESTION_DOC = """1. 下列说法正确的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
答案：A
解析：甲说法正确。
"""


@pytest.fixture()
def harness(tmp_path: Path):
    instance = open_harness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def delete_import(harness: Harness, import_id: str):
    return harness.client.delete(f"/api/v1/question-imports/{import_id}")


def row_count(harness: Harness, table: str) -> int:
    connection = sqlite3.connect(harness.catalog.db_path)
    try:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        connection.close()


def confirm_one(harness: Harness, import_id: str, submission_id: str) -> dict:
    """校对并把第一道草稿确认入库（构造 confirmed 批次 / 来源引用 / 并入记录的公共步骤）。"""
    detail = harness.import_detail(import_id)
    draft = detail["drafts"][0]
    reviewed = harness.patch_draft(draft)
    assert reviewed.status_code == 200, reviewed.text
    confirmed = harness.client.post(
        f"/api/v1/question-imports/{import_id}/confirm",
        json={
            "submissionId": submission_id,
            "importId": import_id,
            "items": [
                {"draftId": draft["draftId"], "expectedDraftRevision": reviewed.json()["revision"]}
            ],
            "duplicateResolutions": [],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


# ----------------------------------------------------------------- 成功删除


def test_delete_import_removes_all_rows_and_keeps_blob(harness: Harness) -> None:
    """成功：批次与解析产物全部移除；受管原件（blob）保留（不伪造原件已删）。"""
    detail = harness.upload(ONE_QUESTION_DOC).json()
    import_id = detail["importId"]
    draft_count = len(detail["drafts"])
    block_count = len(harness.catalog.list_source_blocks(import_id))
    assert draft_count > 0 and block_count > 0
    blob_id = harness.catalog.get_import(import_id).file_sha256
    blob_path = harness.settings.question_bank_root / "blobs" / blob_id
    assert blob_path.is_file()

    before = {
        "suggestions": row_count(harness, "question_suggestions"),
        "drafts": row_count(harness, "question_drafts"),
        "imports": row_count(harness, "question_imports"),
    }
    response = delete_import(harness, import_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"deleted": True, "importId": import_id}

    # 库行清零：批次、草稿、原文块、建议、来源登记
    assert harness.catalog.get_import(import_id) is None
    assert row_count(harness, "question_imports") == before["imports"] - 1
    assert row_count(harness, "question_drafts") == before["drafts"] - draft_count
    assert row_count(harness, "question_source_blocks") == 0
    assert row_count(harness, "question_suggestions") == before["suggestions"]
    assert row_count(harness, "question_import_provenance") == 0
    assert row_count(harness, "question_draft_knowledge_links") == 0
    # 列表里也不再有该批次
    listing = harness.client.get("/api/v1/question-imports").json()
    assert all(item["importId"] != import_id for item in listing["imports"])
    # 详情 404（批次确实没了）
    assert harness.client.get(f"/api/v1/question-imports/{import_id}").status_code == 404

    # 受管原件不物理删除：blob 文件仍在（清理属独立策略）
    assert blob_path.is_file()


def test_delete_import_removes_suggestions_and_links_of_batch(harness: Harness) -> None:
    """成功（含 AI 建议与草稿关联）：本批次的建议与关联随批次一起删，不碰其他批次。"""
    from app.repositories.question_bank.records import SuggestionInput

    first = harness.upload(ONE_QUESTION_DOC).json()
    other = harness.upload(ONE_QUESTION_DOC).json()
    first_draft = harness.import_detail(first["importId"])["drafts"][0]
    other_draft = harness.import_detail(other["importId"])["drafts"][0]

    suggestion = harness.catalog.create_suggestions(
        [
            SuggestionInput(
                organization_job_id="job-delete-1",
                target_draft_id=first_draft["draftId"],
                base_draft_revision=first_draft["revision"],
                proposed_content=first_draft["content"],
                proposed_metadata=first_draft["metadata"],
                source_block_ids=(),
                state="pending",
            )
        ]
    )[0]
    # 其他批次草稿带一条草稿关联（删除时必须保留）
    links = [
        {
            "knowledgePointId": "kp-x",
            "knowledgeRevisionId": "rev-x",
            "subjectIdSnapshot": "math",
            "knowledgeNameSnapshot": "知识点 X",
            "role": "primary",
            "source": "human",
        }
    ]
    assert harness.catalog.set_draft_knowledge_links(
        other_draft["draftId"], expected_revision=other_draft["revision"], links=links
    )

    response = delete_import(harness, first["importId"])
    assert response.status_code == 200, response.text
    assert row_count(harness, "question_suggestions") == 0
    assert harness.catalog.get_suggestion(suggestion.suggestion_id) is None
    # 其他批次的草稿关联与批次本身不受影响
    assert row_count(harness, "question_draft_knowledge_links") == 1
    assert harness.catalog.get_import(other["importId"]) is not None


# --------------------------------------- 批次只是记录：已确认 / 并入记录都可删（R10）


def test_delete_confirmed_import_keeps_formal_question(harness: Harness) -> None:
    """已确认批次可彻底删除（R10 用户裁定「批次只是导入记录」）：

    批次与解析产物清除；**题目保留**，其来源行仍在但批次指针置空（来源跨度保留），
    回执给出 ``unlinkedQuestionSources`` 计数。
    """
    detail = harness.upload(ONE_QUESTION_DOC).json()
    import_id = detail["importId"]
    question_id = confirm_one(harness, import_id, "sub-delete-confirmed")[
        "confirmedQuestionIds"
    ][0]

    response = delete_import(harness, import_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deleted"] is True and body["importId"] == import_id

    # 批次与解析产物清除
    assert harness.catalog.get_import(import_id) is None
    assert row_count(harness, "question_source_blocks") == 0
    assert row_count(harness, "question_drafts") == 0
    assert row_count(harness, "question_import_provenance") == 0

    # 题目保留；来源行保留但 import_id 置空（来源跨度不丢）
    assert row_count(harness, "questions") == 1
    connection = sqlite3.connect(harness.catalog.db_path)
    try:
        rows = connection.execute(
            "SELECT import_id, source_span_json FROM question_sources WHERE question_id = ?",
            (question_id,),
        ).fetchall()
    finally:
        connection.close()
    assert rows, "题目来源行应保留"
    assert all(row[0] is None for row in rows), "批次指针应置空"
    assert all(row[1] for row in rows), "来源跨度应保留"


def test_delete_import_with_merged_draft_cascades_records(harness: Harness) -> None:
    """草稿带并入记录（``duplicate_of_question_id`` 指向正式题）→ 批次可删：并入记录随批次清除。"""
    first = harness.upload(ONE_QUESTION_DOC).json()
    question_id = confirm_one(harness, first["importId"], "sub-delete-merge-a")[
        "confirmedQuestionIds"
    ][0]
    other = harness.upload(ONE_QUESTION_DOC).json()
    other_id = other["importId"]
    draft = harness.import_detail(other_id)["drafts"][0]
    with harness.catalog.write_transaction() as conn:
        harness.catalog.mark_draft_duplicate_in(
            conn,
            draft["draftId"],
            question_id=question_id,
            warning="已跳过：与已有题目内容相同。",
        )

    response = delete_import(harness, other_id)
    assert response.status_code == 200, response.text
    assert harness.catalog.get_import(other_id) is None
    # 被删批次的草稿随批次清除；第一个（保留的）批次的草稿仍在
    assert row_count(harness, "question_drafts") == 1
    # 正式题不受影响
    assert row_count(harness, "questions") == 1


def test_delete_import_after_duplicate_skip_and_link_existing(harness: Harness) -> None:
    """skip 与 link_existing 两条真实可达路径下删除都不再被守卫挡住（R10）。

    - skip：批次仍是 ``needs_review``、草稿带并入记录 → 删除成功；
    - link_existing：批次置 confirmed 且 ``question_sources.import_id`` 指向它 →
      删除成功且题目保留（来源指针置空）。
    """
    first = harness.upload(ONE_QUESTION_DOC).json()
    question_id = confirm_one(harness, first["importId"], "sub-delete-src-a")[
        "confirmedQuestionIds"
    ][0]

    # 路径一：重复题面 + skip
    second = harness.upload(ONE_QUESTION_DOC).json()
    second_id = second["importId"]
    draft = harness.import_detail(second_id)["drafts"][0]
    reviewed = harness.patch_draft(draft)
    assert reviewed.status_code == 200, reviewed.text
    skipped = harness.client.post(
        f"/api/v1/question-imports/{second_id}/confirm",
        json={
            "submissionId": "sub-delete-src-b",
            "importId": second_id,
            "items": [
                {"draftId": draft["draftId"], "expectedDraftRevision": reviewed.json()["revision"]}
            ],
            "duplicateResolutions": [{"draftId": draft["draftId"], "action": "skip"}],
        },
    )
    assert skipped.status_code == 200, skipped.text
    assert harness.import_detail(second_id)["state"] == "needs_review"
    removed_skip = delete_import(harness, second_id)
    assert removed_skip.status_code == 200, removed_skip.text

    # 路径二：重复题面 + link_existing（批次置 confirmed，来源行指向它）
    third = harness.upload(ONE_QUESTION_DOC).json()
    third_id = third["importId"]
    draft = harness.import_detail(third_id)["drafts"][0]
    reviewed = harness.patch_draft(draft)
    assert reviewed.status_code == 200, reviewed.text
    linked = harness.client.post(
        f"/api/v1/question-imports/{third_id}/confirm",
        json={
            "submissionId": "sub-delete-src-c",
            "importId": third_id,
            "items": [
                {"draftId": draft["draftId"], "expectedDraftRevision": reviewed.json()["revision"]}
            ],
            "duplicateResolutions": [
                {
                    "draftId": draft["draftId"],
                    "action": "link_existing",
                    "existingQuestionId": question_id,
                }
            ],
        },
    )
    assert linked.status_code == 200, linked.text
    removed_linked = delete_import(harness, third_id)
    assert removed_linked.status_code == 200, removed_linked.text
    assert harness.catalog.get_import(third_id) is None
    assert row_count(harness, "questions") == 1


# ----------------------------------------------------------------- 404 与语义区分


def test_delete_missing_import_is_404(harness: Harness) -> None:
    response = delete_import(harness, "nope")
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "IMPORT_NOT_FOUND"


def test_discard_keeps_rows_then_delete_removes_them(harness: Harness) -> None:
    """语义区分：放弃保留全部记录（可再查），彻底删除移除记录；两者是互补操作。"""
    detail = harness.upload(ONE_QUESTION_DOC).json()
    import_id = detail["importId"]
    draft_count = len(detail["drafts"])

    # 先放弃：记录保留、状态 cancelled、可再查详情
    discarded = harness.client.post(
        f"/api/v1/question-imports/{import_id}/discard",
        json={"expectedRevision": detail["revision"]},
    )
    assert discarded.status_code == 200, discarded.text
    assert discarded.json()["state"] == "cancelled"
    assert len(harness.import_detail(import_id)["drafts"]) == draft_count

    # 再彻底删除：记录移除、详情 404
    response = delete_import(harness, import_id)
    assert response.status_code == 200, response.text
    assert response.json()["deleted"] is True
    assert harness.client.get(f"/api/v1/question-imports/{import_id}").status_code == 404
    assert harness.catalog.get_import(import_id) is None


def test_delete_cancelled_import_succeeds(harness: Harness) -> None:
    """已放弃（cancelled）批次可以直接彻底删除：放弃不是删除的前置，也不构成障碍。"""
    detail = harness.upload(ONE_QUESTION_DOC).json()
    import_id = detail["importId"]
    discarded = harness.client.post(
        f"/api/v1/question-imports/{import_id}/discard",
        json={"expectedRevision": detail["revision"]},
    )
    assert discarded.status_code == 200, discarded.text
    assert delete_import(harness, import_id).status_code == 200
    assert harness.catalog.get_import(import_id) is None
