"""题库确认入库、重复处理、题目管理与装配契约。

确认采用「整体成功或整体拒绝」：任一草稿不合法 -> HTTP 200 + ``ConfirmResult.failures``，
不写入任何题目、也不记 submission；同 submissionId 同载荷重放返回原结果。
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_question_bank import (
    NO_ANSWER_DOC,
    Harness,
    make_settings,
    open_harness,
    review_payload,
)

ONE_QUESTION_DOC = """1. 下列说法正确的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
答案：A
解析：甲说法正确。
"""

#: 与 ONE_QUESTION_DOC 题干/选项完全相同，但答案与解析不同（指纹不含答案与解析）
SAME_STEM_OTHER_ANSWER_DOC = """1. 下列说法正确的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
答案：C
解析：丙说法正确。
"""

#: 题干确实不同
DIFFERENT_STEM_DOC = """1. 下列说法错误的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
答案：D
解析：丁说法错误。
"""


@pytest.fixture()
def harness(tmp_path: Path):
    instance = open_harness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def confirm(
    harness: Harness,
    import_id: str,
    items: list[dict],
    *,
    submission_id: str,
    resolutions: list[dict] | None = None,
):
    return harness.client.post(
        f"/api/v1/question-imports/{import_id}/confirm",
        json={
            "submissionId": submission_id,
            "importId": import_id,
            "items": items,
            "duplicateResolutions": resolutions or [],
        },
    )


def reviewed_draft(harness: Harness, import_id: str, index: int = 0, **overrides) -> dict:
    """取导入详情里的第 index 道草稿并标记为已校对。"""
    draft = harness.import_detail(import_id)["drafts"][index]
    response = harness.patch_draft(draft, **overrides)
    assert response.status_code == 200, response.text
    return response.json()


def upload_and_review(harness: Harness, doc: str, *, index: int = 0, **fields: str) -> tuple[str, dict]:
    detail = harness.upload(doc, **fields).json()
    draft = reviewed_draft(harness, detail["importId"], index)
    return detail["importId"], draft


def set_content_and_review(
    harness: Harness, import_id: str, index: int, content: dict, **overrides
) -> dict:
    """先落内容改动（自动回 needs_review），再单独标记已校对。"""
    draft = harness.import_detail(import_id)["drafts"][index]
    changed = harness.patch_draft(draft, content=content)
    assert changed.status_code == 200, changed.text
    assert changed.json()["reviewState"] == "needs_review"
    return reviewed_draft(harness, import_id, index, content=content, **overrides)


def questions(harness: Harness, **params) -> dict:
    response = harness.client.get("/api/v1/questions", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- 7


def test_confirm_is_idempotent_per_submission(harness: Harness) -> None:
    import_id, draft = upload_and_review(harness, ONE_QUESTION_DOC, subjectId="math")

    first = confirm(
        harness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="submission-0001",
    )
    assert first.status_code == 200, first.text
    result = first.json()
    assert len(result["confirmedQuestionIds"]) == 1
    assert result["failures"] == []
    question_id = result["confirmedQuestionIds"][0]

    # 同 submissionId 同载荷：返回同一结果，不产生第二批题目
    replay = confirm(
        harness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="submission-0001",
    )
    assert replay.status_code == 200, replay.text
    assert replay.json() == result
    assert questions(harness)["total"] == 1

    # 同 submissionId 不同载荷：409 IDEMPOTENCY_CONFLICT
    conflict = confirm(
        harness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"] + 1}],
        submission_id="submission-0001",
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"

    detail = harness.client.get(f"/api/v1/questions/{question_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "confirmed"
    assert body["revision"] == 1
    assert body["answerState"] == "provided"
    assert body["content"]["answer"]["choiceKeys"] == ["A"]
    assert body["sourceImportId"] == import_id
    assert body["sources"]


def test_confirm_requires_reviewed_draft(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][0]

    response = confirm(
        harness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="submission-0002",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["confirmedQuestionIds"] == []
    assert [failure["code"] for failure in body["failures"]] == ["DRAFT_NOT_REVIEWED"]
    assert questions(harness)["total"] == 0

    # 草稿修订过期（并发编辑）同样逐条拒绝
    reviewed = reviewed_draft(harness, import_id)
    stale = confirm(
        harness,
        import_id,
        [{"draftId": reviewed["draftId"], "expectedDraftRevision": reviewed["revision"] + 3}],
        submission_id="submission-0003",
    )
    assert stale.status_code == 200
    assert [failure["code"] for failure in stale.json()["failures"]] == ["REVISION_CONFLICT"]
    assert questions(harness)["total"] == 0


def test_confirm_failure_is_all_or_nothing(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    good = reviewed_draft(harness, import_id, 0)
    bad = harness.import_detail(import_id)["drafts"][1]  # 仍未校对

    response = confirm(
        harness,
        import_id,
        [
            {"draftId": good["draftId"], "expectedDraftRevision": good["revision"]},
            {"draftId": bad["draftId"], "expectedDraftRevision": bad["revision"]},
        ],
        submission_id="submission-0004",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["confirmedQuestionIds"] == []
    assert [failure["draftId"] for failure in body["failures"]] == [bad["draftId"]]
    assert [failure["code"] for failure in body["failures"]] == ["DRAFT_NOT_REVIEWED"]
    assert questions(harness)["total"] == 0
    assert harness.import_detail(import_id)["state"] == "needs_review"

    # 修正后用同一 submissionId 重试：失败不会被记成提交
    fixed = reviewed_draft(harness, import_id, 1)
    retry = confirm(
        harness,
        import_id,
        [
            {"draftId": good["draftId"], "expectedDraftRevision": good["revision"]},
            {"draftId": fixed["draftId"], "expectedDraftRevision": fixed["revision"]},
        ],
        submission_id="submission-0004",
    )
    assert retry.status_code == 200, retry.text
    assert len(retry.json()["confirmedQuestionIds"]) == 2
    assert questions(harness)["total"] == 2


def test_confirm_import_id_mismatch_is_422(harness: Harness) -> None:
    detail = harness.sample_detail()
    draft = reviewed_draft(harness, detail["importId"], 0)
    response = harness.client.post(
        f"/api/v1/question-imports/{detail['importId']}/confirm",
        json={
            "submissionId": "submission-0005",
            "importId": "another-import",
            "items": [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


# --------------------------------------------------------------------------- 8


def test_missing_answer_requires_acknowledgement(harness: Harness) -> None:
    detail = harness.upload(NO_ANSWER_DOC).json()
    import_id = detail["importId"]
    draft = detail["drafts"][0]
    assert draft["content"]["answer"] is None

    reviewed = reviewed_draft(harness, import_id)
    assert reviewed["reviewState"] == "reviewed"

    response = confirm(
        harness,
        import_id,
        [{"draftId": reviewed["draftId"], "expectedDraftRevision": reviewed["revision"]}],
        submission_id="submission-0006",
    )
    assert response.status_code == 200, response.text
    failures = response.json()["failures"]
    assert [failure["code"] for failure in failures] == ["MISSING_ANSWER_NOT_ACKNOWLEDGED"]
    assert "原文未提供答案" in failures[0]["message"]
    assert questions(harness)["total"] == 0

    acknowledged = reviewed_draft(harness, import_id, acknowledge=True)
    assert acknowledged["missingAnswerAcknowledged"] is True
    assert acknowledged["reviewState"] == "reviewed"

    ok = confirm(
        harness,
        import_id,
        [{"draftId": acknowledged["draftId"], "expectedDraftRevision": acknowledged["revision"]}],
        submission_id="submission-0006",
    )
    assert ok.status_code == 200, ok.text
    question_id = ok.json()["confirmedQuestionIds"][0]
    detail_body = harness.client.get(f"/api/v1/questions/{question_id}").json()
    assert detail_body["answerState"] == "not_provided"
    assert detail_body["content"]["answer"] is None
    # 答案缺失仍继续显示在列表里
    listing = questions(harness)
    assert listing["total"] == 1
    assert listing["questions"][0]["answerState"] == "not_provided"


# -------------------------------------------------------------------------- 12


def test_choice_answer_key_must_exist_in_options(harness: Harness) -> None:
    detail = harness.upload(ONE_QUESTION_DOC).json()
    import_id = detail["importId"]
    draft = detail["drafts"][0]
    broken = copy.deepcopy(draft["content"])
    broken["answer"] = {"choiceKeys": ["E"], "accepted": None, "textMarkdown": None}
    reviewed = set_content_and_review(harness, import_id, 0, broken)
    assert reviewed["reviewState"] == "reviewed"

    response = confirm(
        harness,
        import_id,
        [{"draftId": reviewed["draftId"], "expectedDraftRevision": reviewed["revision"]}],
        submission_id="submission-0007",
    )
    assert response.status_code == 200, response.text
    failures = response.json()["failures"]
    assert [failure["code"] for failure in failures] == ["ANSWER_KEY_NOT_IN_OPTIONS"]
    assert questions(harness)["total"] == 0


def test_true_false_and_text_answer_structure_checks(harness: Harness) -> None:
    doc = """1. 地球是圆的（ ）
答案：正确

2. 简述光合作用的意义。
"""
    detail = harness.upload(doc).json()
    import_id = detail["importId"]
    drafts = harness.import_detail(import_id)["drafts"]
    assert len(drafts) == 2

    true_false = drafts[0]
    assert true_false["content"]["type"] == "true_false"
    assert true_false["content"]["answer"]["accepted"] is True

    reviewed = reviewed_draft(harness, import_id, 0)
    ok = confirm(
        harness,
        import_id,
        [{"draftId": reviewed["draftId"], "expectedDraftRevision": reviewed["revision"]}],
        submission_id="submission-0008",
    )
    assert ok.status_code == 200, ok.text
    assert len(ok.json()["confirmedQuestionIds"]) == 1

    # 判断题答案给成文本 key：结构校验拒绝
    broken = copy.deepcopy(reviewed["content"])
    broken["answer"] = {"choiceKeys": ["A"], "accepted": None, "textMarkdown": None}
    bad = set_content_and_review(harness, import_id, 0, broken)
    rejected = confirm(
        harness,
        import_id,
        [{"draftId": bad["draftId"], "expectedDraftRevision": bad["revision"]}],
        submission_id="submission-0009",
    )
    assert rejected.status_code == 200
    assert [failure["code"] for failure in rejected.json()["failures"]] == [
        "ANSWER_KEY_NOT_IN_OPTIONS"
    ]


# --------------------------------------------------------------------------- 9


def test_duplicate_default_skips_and_ignores_answer_difference(harness: Harness) -> None:
    first_import, first_draft = upload_and_review(harness, ONE_QUESTION_DOC)
    created = confirm(
        harness,
        first_import,
        [{"draftId": first_draft["draftId"], "expectedDraftRevision": first_draft["revision"]}],
        submission_id="submission-0010",
    ).json()
    question_id = created["confirmedQuestionIds"][0]

    # 题干与选项相同、答案不同：指纹相同 -> 默认 skip，不新增题目
    second_import, second_draft = upload_and_review(harness, SAME_STEM_OTHER_ANSWER_DOC)
    skipped = confirm(
        harness,
        second_import,
        [{"draftId": second_draft["draftId"], "expectedDraftRevision": second_draft["revision"]}],
        submission_id="submission-0011",
    )
    assert skipped.status_code == 200, skipped.text
    body = skipped.json()
    assert body["confirmedQuestionIds"] == []
    assert body["skippedDraftIds"] == [second_draft["draftId"]]
    assert body["failures"] == []
    assert questions(harness)["total"] == 1

    # 草稿记录了重复对象，便于界面提示
    after = harness.import_detail(second_import)["drafts"][0]
    assert after["duplicateOfQuestionId"] == question_id
    assert any("已跳过" in warning for warning in after["warnings"])
    # 已有题目未被改动
    detail = harness.client.get(f"/api/v1/questions/{question_id}").json()
    assert detail["content"]["answer"]["choiceKeys"] == ["A"]
    assert detail["revision"] == 1


def test_duplicate_edit_as_new_requires_different_content(harness: Harness) -> None:
    first_import, first_draft = upload_and_review(harness, ONE_QUESTION_DOC)
    confirm(
        harness,
        first_import,
        [{"draftId": first_draft["draftId"], "expectedDraftRevision": first_draft["revision"]}],
        submission_id="submission-0012",
    )

    import_id, draft = upload_and_review(harness, SAME_STEM_OTHER_ANSWER_DOC)
    unresolved = confirm(
        harness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="submission-0013",
        resolutions=[
            {"draftId": draft["draftId"], "action": "edit_as_new", "existingQuestionId": None}
        ],
    )
    assert unresolved.status_code == 200, unresolved.text
    assert [failure["code"] for failure in unresolved.json()["failures"]] == [
        "DUPLICATE_UNRESOLVED"
    ]
    assert questions(harness)["total"] == 1

    # 内容确实不同 -> 新题
    different = harness.upload(DIFFERENT_STEM_DOC).json()
    new_draft = reviewed_draft(harness, different["importId"])
    created = confirm(
        harness,
        different["importId"],
        [{"draftId": new_draft["draftId"], "expectedDraftRevision": new_draft["revision"]}],
        submission_id="submission-0014",
        resolutions=[
            {"draftId": new_draft["draftId"], "action": "edit_as_new", "existingQuestionId": None}
        ],
    )
    assert created.status_code == 200, created.text
    assert len(created.json()["confirmedQuestionIds"]) == 1
    assert questions(harness)["total"] == 2


def test_duplicate_link_existing_adds_source_only(harness: Harness) -> None:
    first_import, first_draft = upload_and_review(harness, ONE_QUESTION_DOC)
    created = confirm(
        harness,
        first_import,
        [{"draftId": first_draft["draftId"], "expectedDraftRevision": first_draft["revision"]}],
        submission_id="submission-0015",
    ).json()
    question_id = created["confirmedQuestionIds"][0]
    before = harness.client.get(f"/api/v1/questions/{question_id}").json()

    second_import, second_draft = upload_and_review(harness, SAME_STEM_OTHER_ANSWER_DOC)
    linked = confirm(
        harness,
        second_import,
        [{"draftId": second_draft["draftId"], "expectedDraftRevision": second_draft["revision"]}],
        submission_id="submission-0016",
        resolutions=[
            {
                "draftId": second_draft["draftId"],
                "action": "link_existing",
                "existingQuestionId": question_id,
            }
        ],
    )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body["linkedQuestionIds"] == [question_id]
    assert body["confirmedQuestionIds"] == []
    assert questions(harness)["total"] == 1

    after = harness.client.get(f"/api/v1/questions/{question_id}").json()
    assert len(after["sources"]) > len(before["sources"])
    assert after["revision"] == before["revision"]
    assert after["content"] == before["content"]
    # 被并入的草稿已消费，不能再次确认
    consumed = harness.import_detail(second_import)["drafts"][0]
    assert consumed["reviewState"] == "excluded"
    assert any("已并入" in warning for warning in consumed["warnings"])


def test_duplicate_link_existing_without_match_is_rejected(harness: Harness) -> None:
    detail = harness.upload(ONE_QUESTION_DOC).json()
    import_id = detail["importId"]
    draft = reviewed_draft(harness, import_id)
    response = confirm(
        harness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="submission-0017",
        resolutions=[
            {
                "draftId": draft["draftId"],
                "action": "link_existing",
                "existingQuestionId": "not-a-question",
            }
        ],
    )
    assert response.status_code == 200, response.text
    assert [failure["code"] for failure in response.json()["failures"]] == [
        "DUPLICATE_RESOLUTION_INVALID"
    ]
    assert questions(harness)["total"] == 0


# --------------------------------------------------------------------------- 8（管理）


def test_question_list_filters_and_pagination(harness: Harness) -> None:
    math_import, math_draft = upload_and_review(
        harness, ONE_QUESTION_DOC, subjectId="math", gradeId="senior-1"
    )
    confirm(
        harness,
        math_import,
        [{"draftId": math_draft["draftId"], "expectedDraftRevision": math_draft["revision"]}],
        submission_id="submission-0018",
    )
    physics_import, physics_draft = upload_and_review(
        harness, DIFFERENT_STEM_DOC, subjectId="physics", gradeId="senior-2"
    )
    confirm(
        harness,
        physics_import,
        [{"draftId": physics_draft["draftId"], "expectedDraftRevision": physics_draft["revision"]}],
        submission_id="submission-0019",
    )

    assert questions(harness)["total"] == 2
    assert questions(harness, subjectId="math")["total"] == 1
    assert questions(harness, gradeId="senior-2")["total"] == 1
    assert questions(harness, subjectId="math", gradeId="senior-2")["total"] == 0
    assert questions(harness, q="错误")["total"] == 1
    assert questions(harness, q="不存在的词")["total"] == 0

    first_page = questions(harness, limit=1, offset=0)
    assert first_page["total"] == 2
    assert len(first_page["questions"]) == 1
    second_page = questions(harness, limit=1, offset=1)
    assert len(second_page["questions"]) == 1
    assert first_page["questions"][0]["questionId"] != second_page["questions"][0]["questionId"]

    too_many = harness.client.get("/api/v1/questions", params={"limit": 500})
    assert too_many.status_code == 422
    assert too_many.json()["code"] == "INVALID_REQUEST"


def test_question_patch_and_archive(harness: Harness) -> None:
    import_id, draft = upload_and_review(harness, ONE_QUESTION_DOC)
    created = confirm(
        harness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="submission-0020",
    ).json()
    question_id = created["confirmedQuestionIds"][0]

    current = harness.client.get(f"/api/v1/questions/{question_id}").json()
    edited = copy.deepcopy(current["content"])
    edited["stemMarkdown"] = "修改后的题干（ ）"
    edited["explanationMarkdown"] = "修改后的解析。"
    patched = harness.client.patch(
        f"/api/v1/questions/{question_id}",
        json={
            "expectedRevision": current["revision"],
            "content": edited,
            "metadata": current["metadata"],
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["revision"] == current["revision"] + 1
    assert patched.json()["content"]["stemMarkdown"] == "修改后的题干（ ）"
    # 修订不可变：旧修订行仍在
    revisions = harness.catalog.get_question(question_id)
    assert revisions.revision == 2

    stale = harness.client.patch(
        f"/api/v1/questions/{question_id}",
        json={
            "expectedRevision": current["revision"],
            "content": edited,
            "metadata": current["metadata"],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "REVISION_CONFLICT"

    # 归档（逻辑删除）：不物理删除
    archived = harness.client.delete(
        f"/api/v1/questions/{question_id}", params={"expectedRevision": 2}
    )
    assert archived.status_code == 204
    detail = harness.client.get(f"/api/v1/questions/{question_id}").json()
    assert detail["status"] == "archived"
    assert detail["content"]["stemMarkdown"] == "修改后的题干（ ）"
    assert questions(harness)["total"] == 0
    assert questions(harness, status="archived")["total"] == 1
    assert questions(harness, status="all")["total"] == 1

    # 已归档题目不能继续编辑
    blocked = harness.client.patch(
        f"/api/v1/questions/{question_id}",
        json={
            "expectedRevision": 2,
            "content": edited,
            "metadata": current["metadata"],
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "QUESTION_ARCHIVED"

    missing = harness.client.get("/api/v1/questions/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "QUESTION_NOT_FOUND"


# -------------------------------------------------------------------------- 10


def test_question_bank_modules_never_touch_textbook_collections() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    directories = (
        app_root / "services" / "question_bank",
        app_root / "repositories" / "question_bank",
    )
    forbidden = (
        "vector_store",
        "collection_name",
        "textbooks_",
        "textbooks_root",
        "qdrant",
        "textbook_index",
        "textbook_ingest",
        "rag_v2",
        "embedding_profiles",
    )
    files = [path for directory in directories for path in directory.rglob("*.py")]
    assert files, "题库源码目录为空，隔离扫描无效"
    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} 含禁止标识：{token}"


# -------------------------------------------------------------------------- 11


def test_routes_require_assembled_service(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    app = create_app(settings)
    # 装配后服务在位；本用例显式撤下服务，验证「未装配即 503」而不是返回空结果。
    assert app.state.question_bank is not None
    app.state.question_bank_service = None
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        for method, path, payload in (
            ("get", "/api/v1/questions", None),
            ("get", "/api/v1/question-imports", None),
            ("get", "/api/v1/question-imports/whatever", None),
            ("get", "/api/v1/questions/whatever", None),
            (
                "post",
                "/api/v1/question-imports/whatever/organize",
                {"draftIds": [], "modelProfileId": "qwen2.5:7b"},
            ),
            (
                "post",
                "/api/v1/question-imports/whatever/confirm",
                {"submissionId": "submission-9999", "importId": "whatever", "items": [{"draftId": "x", "expectedDraftRevision": 0}]},
            ),
            ("patch", "/api/v1/question-drafts/whatever", review_payload({"revision": 0, "content": {"type": "other", "stemMarkdown": "x", "options": [], "answer": None, "explanationMarkdown": None, "assetIds": []}, "metadata": {}})),
        ):
            response = getattr(client, method)(path, json=payload) if payload else getattr(client, method)(path)
            assert response.status_code == 503, f"{method} {path} -> {response.status_code}"
            body = response.json()
            assert body["code"] == "SERVICE_UNAVAILABLE"
            assert body["retryable"] is True
