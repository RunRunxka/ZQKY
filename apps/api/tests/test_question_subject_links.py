"""改题/改草稿学科时不得继承跨学科知识点关联（TEACHING-LOOP B3 / G0 · B2-RV07）。

审查缺陷：``patch_question``（与草稿同类入口）只在**显式提供** ``knowledgeLinks`` 时
校验新学科；省略关联时无条件复制旧关联，正常 HTTP 请求即可造出"语文题带数学知识点"。

回归断言（反向对照见 ``docs/qa/TEACHING-LOOP-B2-REVIEW-20261001/probes/question_jobs_probe.py``）：

- 学科变化 + 省略关联 + 旧关联与新学科冲突 → 422 ``KNOWLEDGE_REFERENCE_INVALID``，
  ``details.issues`` 指向冲突知识点，文案要求显式替换/清空；题目/草稿一字未改；
- 显式 ``knowledgeLinks: []`` → 新修订零关联；
- 显式新学科关联 → 成功，按新集合替换；
- 同学科改内容 → 照旧复制旧关联（不误伤）。

全部用 ``tmp_path`` 临时四库与受控模型替身：不触网、不读写正式数据目录。
"""

from __future__ import annotations

from pathlib import Path

from tests.test_question_bank_confirm import ONE_QUESTION_DOC, confirm, reviewed_draft
from tests.test_question_generation import GenerationHarness

MATH = "math"
CHINESE = "chinese"


def _patch_question(harness: GenerationHarness, question_id: str, detail: dict, **overrides):
    payload = {
        "expectedRevision": detail["revision"],
        "content": detail["content"],
        "metadata": detail["metadata"],
    }
    payload.update(overrides)
    return harness.client.patch(f"/api/v1/questions/{question_id}", json=payload)


def _confirmed_question(harness: GenerationHarness, point: dict, *, subject_id: str = MATH):
    """上传 → 关联 → 标校对 → 确认，返回 ``(questionId, QuestionDetail)``。"""
    detail = harness.upload_sample(ONE_QUESTION_DOC, subjectId=subject_id)
    draft = detail["drafts"][0]
    linked = harness.patch_links(
        draft["draftId"],
        draft["revision"],
        [{"knowledgePointId": point["pointId"], "role": "primary"}],
    )
    assert linked.status_code == 200, linked.text
    reviewed = harness.patch_draft(
        {
            "draftId": draft["draftId"],
            "revision": linked.json()["revision"],
            "content": linked.json()["content"],
            "metadata": linked.json()["metadata"],
        }
    )
    assert reviewed.status_code == 200, reviewed.text
    result = confirm(
        harness,
        detail["importId"],
        [
            {
                "draftId": draft["draftId"],
                "expectedDraftRevision": reviewed.json()["revision"],
            }
        ],
        submission_id=f"subject-{draft['draftId'][:12]}",
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["failures"] == [], body
    question_id = body["confirmedQuestionIds"][0]
    response = harness.client.get(f"/api/v1/questions/{question_id}")
    assert response.status_code == 200, response.text
    return question_id, response.json()


# --------------------------------------------------------------------------- 题目


def test_question_subject_change_without_links_is_rejected_with_locator(
    tmp_path: Path,
) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        point = harness.create_point(subject_id=MATH, code="kp-math", name="一次函数")
        question_id, detail = _confirmed_question(harness, point)
        old_revision_id = harness.catalog.get_question(question_id).current_revision_id

        changed = dict(detail["metadata"])
        changed["subjectId"] = CHINESE
        response = _patch_question(harness, question_id, detail, metadata=changed)

        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] == "KNOWLEDGE_REFERENCE_INVALID"
        # details.issues 指向冲突知识点，并要求显式替换/清空
        issues = body["details"]["issues"]
        assert issues and issues[0]["field"].endswith("knowledgePointId")
        assert point["pointId"] in issues[0]["message"]
        assert CHINESE in issues[0]["message"]
        assert "knowledgeLinks" in body["message"]
        assert "清空" in body["message"]
        # 拒绝时题目一字未改：没有新修订、旧关联原样
        record = harness.catalog.get_question(question_id)
        assert record.current_revision_id == old_revision_id
        assert harness.catalog.question_knowledge_links(question_id)[0].knowledge_point_id == (
            point["pointId"]
        )
    finally:
        harness.close()


def test_question_subject_change_with_explicit_links_replaces_or_clears(
    tmp_path: Path,
) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        math_point = harness.create_point(subject_id=MATH, code="kp-math", name="一次函数")
        chinese_point = harness.create_point(subject_id=CHINESE, code="kp-cn", name="古诗鉴赏")
        question_id, detail = _confirmed_question(harness, math_point)
        old_revision_id = harness.catalog.get_question(question_id).current_revision_id
        old_rows = harness.revision_link_rows(old_revision_id)

        # ① 显式清空：学科变化 + `knowledgeLinks: []` → 新修订零关联
        moved = dict(detail["metadata"])
        moved["subjectId"] = CHINESE
        cleared = _patch_question(
            harness, question_id, detail, metadata=moved, knowledgeLinks=[]
        )
        assert cleared.status_code == 200, cleared.text
        cleared_body = cleared.json()
        assert cleared_body["metadata"]["subjectId"] == CHINESE
        assert cleared_body["knowledgeLinks"] == []
        assert cleared_body["revision"] == detail["revision"] + 1
        assert harness.revision_link_rows(old_revision_id) == old_rows  # 旧修订不可改

        # ② 显式替换为新学科关联 → 成功
        fresh = harness.client.get(f"/api/v1/questions/{question_id}").json()
        replaced = _patch_question(
            harness,
            question_id,
            fresh,
            knowledgeLinks=[{"knowledgePointId": chinese_point["pointId"], "role": "primary"}],
        )
        assert replaced.status_code == 200, replaced.text
        replaced_body = replaced.json()
        assert [
            (item["knowledgePointId"], item["subjectIdSnapshot"])
            for item in replaced_body["knowledgeLinks"]
        ] == [(chinese_point["pointId"], CHINESE)]
        # 检索按最新修订：新学科知识点命中，旧学科不再命中
        assert (
            harness.client.get(
                "/api/v1/questions", params={"knowledgePointId": chinese_point["pointId"]}
            ).json()["total"]
            == 1
        )
        assert (
            harness.client.get(
                "/api/v1/questions", params={"knowledgePointId": math_point["pointId"]}
            ).json()["total"]
            == 0
        )
    finally:
        harness.close()


def test_same_subject_content_change_still_copies_links(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        point = harness.create_point(subject_id=MATH, code="kp-math", name="一次函数")
        question_id, detail = _confirmed_question(harness, point)

        content = dict(detail["content"])
        content["stemMarkdown"] = "同学科改内容（ ）"
        patched = _patch_question(harness, question_id, detail, content=content)
        assert patched.status_code == 200, patched.text
        body = patched.json()
        assert body["metadata"]["subjectId"] == MATH
        assert [item["knowledgePointId"] for item in body["knowledgeLinks"]] == [
            point["pointId"]
        ]
        assert body["revision"] == detail["revision"] + 1
    finally:
        harness.close()


def test_question_subject_change_without_any_links_is_allowed(tmp_path: Path) -> None:
    """旧关联为空时改学科不设门槛（不误伤）——只有继承冲突关联才需要显式处置。"""
    harness = GenerationHarness(tmp_path)
    try:
        detail = harness.upload_sample(ONE_QUESTION_DOC, subjectId=MATH)
        draft = reviewed_draft(harness, detail["importId"], 0)
        result = confirm(
            harness,
            detail["importId"],
            [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
            submission_id="subject-empty-links",
        )
        assert result.status_code == 200, result.text
        question_id = result.json()["confirmedQuestionIds"][0]
        detail_view = harness.client.get(f"/api/v1/questions/{question_id}").json()
        assert detail_view["knowledgeLinks"] == []

        moved = dict(detail_view["metadata"])
        moved["subjectId"] = CHINESE
        response = _patch_question(harness, question_id, detail_view, metadata=moved)
        assert response.status_code == 200, response.text
        assert response.json()["metadata"]["subjectId"] == CHINESE
        assert response.json()["knowledgeLinks"] == []
    finally:
        harness.close()


# --------------------------------------------------------------------------- 草稿


def test_draft_subject_change_without_links_is_rejected_with_locator(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        point = harness.create_point(subject_id=MATH, code="kp-math", name="一次函数")
        detail = harness.upload_sample(ONE_QUESTION_DOC, subjectId=MATH)
        draft = detail["drafts"][0]
        linked = harness.patch_links(
            draft["draftId"], draft["revision"], [{"knowledgePointId": point["pointId"]}]
        )
        assert linked.status_code == 200, linked.text
        current = linked.json()

        moved = dict(current["metadata"])
        moved["subjectId"] = CHINESE
        response = harness.client.patch(
            f"/api/v1/question-drafts/{draft['draftId']}",
            json={
                "expectedRevision": current["revision"],
                "content": current["content"],
                "metadata": moved,
            },
        )
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] == "KNOWLEDGE_REFERENCE_INVALID"
        assert point["pointId"] in body["details"]["issues"][0]["message"]
        # 草稿一字未改：revision 与关联都保持原样
        after = harness.catalog.get_draft(draft["draftId"])
        assert after.revision == current["revision"]
        assert after.metadata["subjectId"] == MATH
        assert [
            item.knowledge_point_id
            for item in harness.catalog.draft_knowledge_links(draft["draftId"])
        ] == [point["pointId"]]

        # 显式清空 → 新修订、零关联、回到 needs_review
        cleared = harness.client.patch(
            f"/api/v1/question-drafts/{draft['draftId']}",
            json={
                "expectedRevision": current["revision"],
                "content": current["content"],
                "metadata": moved,
                "knowledgeLinks": [],
            },
        )
        assert cleared.status_code == 200, cleared.text
        cleared_body = cleared.json()
        assert cleared_body["metadata"]["subjectId"] == CHINESE
        assert cleared_body["knowledgeLinks"] == []
        assert cleared_body["reviewState"] == "needs_review"
    finally:
        harness.close()


def test_draft_subject_change_with_new_subject_links_succeeds(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        chinese_point = harness.create_point(subject_id=CHINESE, code="kp-cn", name="古诗鉴赏")
        detail = harness.upload_sample(ONE_QUESTION_DOC, subjectId=MATH)
        draft = detail["drafts"][0]
        moved = dict(draft["metadata"])
        moved["subjectId"] = CHINESE
        response = harness.client.patch(
            f"/api/v1/question-drafts/{draft['draftId']}",
            json={
                "expectedRevision": draft["revision"],
                "content": draft["content"],
                "metadata": moved,
                "knowledgeLinks": [
                    {"knowledgePointId": chinese_point["pointId"], "role": "primary"}
                ],
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert [
            (item["knowledgePointId"], item["subjectIdSnapshot"])
            for item in body["knowledgeLinks"]
        ] == [(chinese_point["pointId"], CHINESE)]
    finally:
        harness.close()


# --------------------------------------------------- 确认前复核（B2-RV06 题库侧）


def _ready_draft_with_point(harness: GenerationHarness, point: dict) -> tuple[str, dict]:
    detail = harness.upload_sample(ONE_QUESTION_DOC, subjectId=MATH)
    draft = detail["drafts"][0]
    linked = harness.patch_links(
        draft["draftId"], draft["revision"], [{"knowledgePointId": point["pointId"]}]
    )
    assert linked.status_code == 200, linked.text
    reviewed = harness.patch_draft(
        {
            "draftId": draft["draftId"],
            "revision": linked.json()["revision"],
            "content": linked.json()["content"],
            "metadata": linked.json()["metadata"],
        }
    )
    assert reviewed.status_code == 200, reviewed.text
    return detail["importId"], reviewed.json()


def test_confirm_rejects_draft_bound_to_archived_knowledge_point(tmp_path: Path) -> None:
    """RV06：草稿绑定活跃知识点 → 归档 → 确认 409，不发布新的已确认关联。"""
    harness = GenerationHarness(tmp_path)
    try:
        point = harness.create_point(subject_id=MATH, code="kp-archive", name="即将归档")
        import_id, draft = _ready_draft_with_point(harness, point)
        harness.archive_point(point["pointId"])

        response = confirm(
            harness,
            import_id,
            [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
            submission_id="archived-confirm-b3",
        )
        assert response.status_code == 409, response.text
        body = response.json()
        assert body["code"] == "KNOWLEDGE_ARCHIVED"
        # 零发布：没有正式题、没有正式关联、导入状态未变成 confirmed
        assert harness.row_count("questions") == 0
        assert harness.row_count("question_knowledge_links") == 0
        assert harness.catalog.get_import(import_id).state != "confirmed"
    finally:
        harness.close()


def test_confirm_replay_after_archive_returns_original_result(tmp_path: Path) -> None:
    """幂等重放不受 RV06 复核影响：已确认的历史关联不回溯重核。"""
    harness = GenerationHarness(tmp_path)
    try:
        point = harness.create_point(subject_id=MATH, code="kp-replay", name="重放点")
        import_id, draft = _ready_draft_with_point(harness, point)
        first = confirm(
            harness,
            import_id,
            [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
            submission_id="replay-after-archive",
        )
        assert first.status_code == 200, first.text
        assert len(first.json()["confirmedQuestionIds"]) == 1

        harness.archive_point(point["pointId"])  # 确认之后归档：历史关联仍可读
        replay = confirm(
            harness,
            import_id,
            [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
            submission_id="replay-after-archive",
        )
        assert replay.status_code == 200, replay.text
        assert replay.json() == first.json()
        question_id = first.json()["confirmedQuestionIds"][0]
        detail = harness.client.get(f"/api/v1/questions/{question_id}").json()
        assert [item["knowledgePointId"] for item in detail["knowledgeLinks"]] == [
            point["pointId"]
        ]
    finally:
        harness.close()
