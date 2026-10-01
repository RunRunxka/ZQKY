"""B3/G0-C · B2-RV08：施测日期变更必须重核既有参测人次的班级归属。

真装配：``create_app(make_settings(tmp_path / "data"))`` + ``TestClient``，班级/学生/原卷
全部走真实 HTTP 链（复用 ``tests/assessments_support.py`` 的 ``AssessmentsHarness`` 模式）；
只读直查用于断言归属历史与快照**逐行未变**。

覆盖（任务卡 §1 RV08 + §3 冻结形状）：

- 日期变化 + 未覆盖且 ``class_confirmed=0`` 的人次 → 422 ``PARTICIPANT_CLASS_UNCONFIRMED``
  定位拒绝（``issues[].row`` 0 基、``field=classId``），日期未改变、整批零写入；
- 重新确认路径（``POST /assessments/{id}/participants``，带 ``attemptNo`` 命中既有行 +
  ``classConfirmed`` + 依据）→ 只写确认列、``revision+1``、参测人数不变；
- 重确认后 PATCH 成功；``class_memberships`` 与姓名/学号快照逐行不变；
- 部分重确认仍被拒（未确认的那一行仍定位）；
- 幂等重放不再重复 bump；过期 ``expectedRevision`` → 409；
- 边界（冻结形状）：命中既有行才算重确认，未命中仍是新增人次；
  「今天导入名单、分析过去考试」的创建期显式确认流程不受影响；
  日期未变化时不做重核（避免误伤标题/类型编辑）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.contracts.assessments import (
    ASSESSMENT_REVISION_STALE,
    PARTICIPANT_CLASS_UNCONFIRMED,
)
from tests.assessments_support import AssessmentsHarness, ConfirmedPaper, days_before, today

#: 任务卡口径：heldOn=09-30 / joinedOn=09-20 / 改到 09-01 → days_before(1) / days_before(11) / days_before(30)
HELD_ON = days_before(1)
JOINED_ON = days_before(11)
EARLIER_HELD_ON = days_before(30)


@pytest.fixture()
def harness(tmp_path: Path):
    with AssessmentsHarness(tmp_path) as running:
        yield running


class Scene:
    """已确认原卷 + 一个班 + 两名学生（joinedOn 晚于改后的施测日期）。"""

    def __init__(self, paper: ConfirmedPaper, klass: dict[str, Any], students: list[dict[str, Any]]):
        self.paper = paper
        self.klass = klass
        self.students = students


def _scene(
    harness: AssessmentsHarness,
    *,
    tag: str = "held",
    joined_on: str | None = None,
) -> Scene:
    paper = harness.create_confirmed_paper(tag=tag)
    klass = harness.create_class(code="C1")
    joined = joined_on or JOINED_ON
    students = [
        harness.create_student(
            name="张三", student_no="0012", class_id=klass["id"], joined_on=joined
        ),
        harness.create_student(
            name="李四", student_no=None, class_id=klass["id"], joined_on=joined
        ),
    ]
    return Scene(paper, klass, students)


def _create(
    harness: AssessmentsHarness,
    scene: Scene,
    *,
    submission_id: str = "held-1",
    held_on: str = HELD_ON,
    participants: list[dict[str, Any]] | None = None,
):
    body = AssessmentsHarness.create_body(
        scene.paper,
        submission_id=submission_id,
        class_ids=[scene.klass["id"]],
        participants=participants
        or [
            AssessmentsHarness.participant(scene.students[0]["id"], scene.klass["id"]),
            AssessmentsHarness.participant(scene.students[1]["id"], scene.klass["id"]),
        ],
        held_on=held_on,
    )
    return harness.client.post("/api/v1/assessments", json=body)


def _patch_held_on(harness: AssessmentsHarness, assessment_id: str, *, revision: int, held_on: str):
    return harness.client.patch(
        f"/api/v1/assessments/{assessment_id}",
        json={"expectedRevision": revision, "heldOn": held_on},
    )


def _participant_rows(harness: AssessmentsHarness) -> list[dict[str, Any]]:
    return harness.raw_rows(
        "SELECT id, assessment_id, student_id, class_id, attempt_no, attendance, "
        "name_snapshot, student_no_snapshot, class_confirmed, class_confirmation_note, "
        "class_confirmation_at FROM assessment_participants ORDER BY student_id, attempt_no"
    )


def _reconfirm(
    harness: AssessmentsHarness,
    scene: Scene,
    assessment_id: str,
    *,
    revision: int,
    rows: list[dict[str, Any]],
    submission_id: str = "reconfirm-1",
):
    return harness.client.post(
        f"/api/v1/assessments/{assessment_id}/participants",
        json={
            "submissionId": submission_id,
            "expectedRevision": revision,
            "participants": rows,
        },
    )


def _confirm_row(scene: Scene, student: dict[str, Any], *, attempt_no: int = 1, note: str) -> dict[str, Any]:
    return AssessmentsHarness.participant(
        student["id"],
        scene.klass["id"],
        attempt_no=attempt_no,
        class_confirmed=True,
        class_confirmation_note=note,
    )


# --------------------------------------------------------------------------- 主流程


def test_held_on_change_is_rejected_until_reconfirmed(harness: AssessmentsHarness) -> None:
    """任务卡 §1 RV08 主路径：改日期 → 定位拒绝 → 重新确认 → PATCH 成功，历史与快照不动。"""
    scene = _scene(harness)
    created = _create(harness, scene)
    assert created.status_code == 201, created.text
    assessment = created.json()["assessment"]
    assessment_id = assessment["assessmentId"]
    assert assessment["heldOn"] == HELD_ON
    assert assessment["revision"] == 0
    assert [row["classConfirmed"] for row in created.json()["participants"]] == [False, False]

    memberships_before = harness.memberships_snapshot()
    participants_before = _participant_rows(harness)
    assert len(participants_before) == 2

    rejected = _patch_held_on(
        harness, assessment_id, revision=0, held_on=EARLIER_HELD_ON
    )
    assert rejected.status_code == 422, rejected.text
    body = rejected.json()
    assert body["code"] == PARTICIPANT_CLASS_UNCONFIRMED
    issues = body["details"]["issues"]
    assert [issue["row"] for issue in issues] == [0, 1]
    assert all(issue["field"] == "classId" for issue in issues)
    assert all(EARLIER_HELD_ON in issue["message"] for issue in issues)
    assert all("重新确认本次班级" in issue["message"] for issue in issues)

    # 拒绝 = 整批回滚：日期未改、revision 未动、归属历史与参测行逐行不变
    current = harness.client.get(f"/api/v1/assessments/{assessment_id}")
    assert current.status_code == 200, current.text
    assert current.json()["assessment"]["heldOn"] == HELD_ON
    assert current.json()["assessment"]["revision"] == 0
    assert harness.memberships_snapshot() == memberships_before
    assert _participant_rows(harness) == participants_before

    note_zhang = "名单今天导入，该生实际一直在班，本次班级以 C1 记（张三）"
    note_li = "名单今天导入，该生实际一直在班，本次班级以 C1 记（李四）"
    reconfirmed = _reconfirm(
        harness,
        scene,
        assessment_id,
        revision=0,
        rows=[
            _confirm_row(scene, scene.students[0], note=note_zhang),
            _confirm_row(scene, scene.students[1], note=note_li),
        ],
    )
    assert reconfirmed.status_code == 200, reconfirmed.text
    confirmed_body = reconfirmed.json()
    assert confirmed_body["replayed"] is False
    assert confirmed_body["assessment"]["revision"] == 1
    assert confirmed_body["assessment"]["participantCount"] == 2  # 只更新确认列，不新增行
    by_student = {row["studentId"]: row for row in confirmed_body["participants"]}
    assert by_student[scene.students[0]["id"]]["classConfirmed"] is True
    assert by_student[scene.students[0]["id"]]["classConfirmationNote"] == note_zhang
    assert by_student[scene.students[0]["id"]]["classConfirmationAt"]
    assert by_student[scene.students[1]["id"]]["classConfirmationNote"] == note_li
    assert harness.count("assessment_participants") == 2
    assert harness.memberships_snapshot() == memberships_before

    updated = _patch_held_on(
        harness, assessment_id, revision=1, held_on=EARLIER_HELD_ON
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["heldOn"] == EARLIER_HELD_ON
    assert updated.json()["revision"] == 2
    assert updated.json()["classIds"] == [scene.klass["id"]]
    assert updated.json()["paperRevisionId"] == scene.paper.revision_id

    # 归属历史与姓名/学号快照逐行不变（只多写了确认三列）
    assert harness.memberships_snapshot() == memberships_before
    after = _participant_rows(harness)
    assert [
        (row["name_snapshot"], row["student_no_snapshot"], row["class_id"], row["attempt_no"])
        for row in after
    ] == [
        (row["name_snapshot"], row["student_no_snapshot"], row["class_id"], row["attempt_no"])
        for row in participants_before
    ]
    assert all(row["class_confirmed"] == 1 for row in after)


def test_partial_reconfirmation_still_rejected(harness: AssessmentsHarness) -> None:
    """只确认一部分人次不足以改日期：未确认的那一行仍被定位拒绝。"""
    scene = _scene(harness, tag="partial")
    created = _create(harness, scene)
    assert created.status_code == 201, created.text
    assessment_id = created.json()["assessment"]["assessmentId"]

    first = _reconfirm(
        harness,
        scene,
        assessment_id,
        revision=0,
        rows=[_confirm_row(scene, scene.students[0], note="只确认张三")],
        submission_id="reconfirm-partial-1",
    )
    assert first.status_code == 200, first.text
    assert first.json()["assessment"]["revision"] == 1

    rejected = _patch_held_on(harness, assessment_id, revision=1, held_on=EARLIER_HELD_ON)
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == PARTICIPANT_CLASS_UNCONFIRMED
    issues = rejected.json()["details"]["issues"]
    detail = harness.client.get(f"/api/v1/assessments/{assessment_id}").json()
    li_index = next(
        index
        for index, row in enumerate(detail["participants"])
        if row["studentId"] == scene.students[1]["id"]
    )
    assert [issue["row"] for issue in issues] == [li_index]
    assert "李四" in issues[0]["message"]
    assert detail["assessment"]["heldOn"] == HELD_ON  # 仍未改变

    second = _reconfirm(
        harness,
        scene,
        assessment_id,
        revision=1,
        rows=[_confirm_row(scene, scene.students[1], note="确认李四")],
        submission_id="reconfirm-partial-2",
    )
    assert second.status_code == 200, second.text
    assert second.json()["assessment"]["revision"] == 2
    accepted = _patch_held_on(harness, assessment_id, revision=2, held_on=EARLIER_HELD_ON)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["heldOn"] == EARLIER_HELD_ON


def test_reconfirmation_is_idempotent_and_revision_guarded(harness: AssessmentsHarness) -> None:
    """重确认走既有 submissionId 幂等与 expectedRevision 守卫（不重复 bump）。"""
    scene = _scene(harness, tag="idem")
    created = _create(harness, scene).json()
    assessment_id = created["assessment"]["assessmentId"]
    rows = [
        _confirm_row(scene, scene.students[0], note="确认张三"),
        _confirm_row(scene, scene.students[1], note="确认李四"),
    ]
    first = _reconfirm(harness, scene, assessment_id, revision=0, rows=rows)
    assert first.status_code == 200, first.text
    stored_at = {
        row["id"]: row["class_confirmation_at"]
        for row in harness.raw_rows(
            "SELECT id, class_confirmation_at FROM assessment_participants"
        )
    }

    replay = _reconfirm(harness, scene, assessment_id, revision=0, rows=rows)
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["assessment"]["revision"] == 1
    assert replay.json()["participants"] == first.json()["participants"]
    assert {
        row["id"]: row["class_confirmation_at"]
        for row in harness.raw_rows(
            "SELECT id, class_confirmation_at FROM assessment_participants"
        )
    } == stored_at

    stale = _reconfirm(
        harness,
        scene,
        assessment_id,
        revision=0,
        rows=[_confirm_row(scene, scene.students[0], note="过期重确认")],
        submission_id="reconfirm-stale",
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == ASSESSMENT_REVISION_STALE
    assert stale.json()["details"]["currentRevision"] == 1


def test_reconfirmation_does_not_refresh_snapshots(harness: AssessmentsHarness) -> None:
    """重新确认只写确认列：改名/转班后的既有快照仍是创建时的值。"""
    scene = _scene(harness, tag="snapshot")
    created = _create(harness, scene).json()
    assessment_id = created["assessment"]["assessmentId"]
    student_id = scene.students[0]["id"]

    harness.rename_student(student_id, name="张三改名", expected_revision=0)
    second_class = harness.create_class(code="C2")
    harness.transfer_student(
        student_id,
        from_class_id=scene.klass["id"],
        to_class_id=second_class["id"],
        moved_on=days_before(2),
        expected_student_revision=1,
    )
    memberships_before = harness.memberships_snapshot()
    rows_before = {row["student_id"]: row for row in _participant_rows(harness)}

    reconfirmed = _reconfirm(
        harness,
        scene,
        assessment_id,
        revision=0,
        rows=[_confirm_row(scene, scene.students[0], note="转班后按本次班级确认")],
    )
    assert reconfirmed.status_code == 200, reconfirmed.text
    rows_after = {row["student_id"]: row for row in _participant_rows(harness)}
    assert rows_after[student_id]["name_snapshot"] == "张三"
    assert rows_after[student_id]["student_no_snapshot"] == "0012"
    assert rows_after[student_id]["class_id"] == scene.klass["id"]
    assert rows_after[student_id]["attempt_no"] == rows_before[student_id]["attempt_no"]
    assert harness.memberships_snapshot() == memberships_before
    # 学生档案确实已改名/转班（快照不动是刻意冻结，不是写失败）
    current = harness.get_student(student_id)
    assert current["name"] == "张三改名"
    assert any(item["classId"] == second_class["id"] for item in current["memberships"])


# --------------------------------------------------------------------------- 冻结形状边界


def test_confirmation_requires_matching_existing_attempt(harness: AssessmentsHarness) -> None:
    """未命中既有 (student, class, attempt) 的确认行仍是**新增人次**（原语义不变）。"""
    scene = _scene(harness, tag="shape")
    created = _create(harness, scene).json()
    assessment_id = created["assessment"]["assessmentId"]

    added = _reconfirm(
        harness,
        scene,
        assessment_id,
        revision=0,
        rows=[_confirm_row(scene, scene.students[0], attempt_no=2, note="补考按本次班级确认")],
        submission_id="makeup-confirmed",
    )
    assert added.status_code == 200, added.text
    body = added.json()
    assert body["assessment"]["revision"] == 1
    assert body["assessment"]["participantCount"] == 3
    assert body["participants"][0]["attemptNo"] == 2
    assert body["participants"][0]["classConfirmed"] is True
    # 首次记录（attempt 1）不被覆盖
    assert harness.count("assessment_participants", "attempt_no = 1") == 2


def test_creation_time_confirmation_flow_unaffected(harness: AssessmentsHarness) -> None:
    """「今天导入名单、分析过去考试」：创建期显式确认仍可用，且之后改日期无需重复确认。"""
    paper = harness.create_confirmed_paper(tag="roster-today")
    klass = harness.create_class(code="C1")
    student = harness.create_student(
        name="王五", student_no="0031", class_id=klass["id"], joined_on=today()
    )
    note = "名单今天导入，该生实际一直在班，本次班级以 C1 记"
    body = AssessmentsHarness.create_body(
        paper,
        submission_id="roster-today-1",
        class_ids=[klass["id"]],
        participants=[
            AssessmentsHarness.participant(
                student["id"],
                klass["id"],
                class_confirmed=True,
                class_confirmation_note=note,
            )
        ],
        held_on=days_before(30),
    )
    created = harness.client.post("/api/v1/assessments", json=body)
    assert created.status_code == 201, created.text
    assessment = created.json()["assessment"]
    assert created.json()["participants"][0]["classConfirmed"] is True

    moved = _patch_held_on(
        harness,
        assessment["assessmentId"],
        revision=assessment["revision"],
        held_on=days_before(40),
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["heldOn"] == days_before(40)


def test_update_without_date_change_does_not_recheck(harness: AssessmentsHarness) -> None:
    """边界：heldOn 未变化时不做归属重核（标题/类型编辑不受影响）。

    构造：创建期覆盖成立（未确认）→ 事后转班使旧归属不再覆盖 heldOn。
    参测人次是历史快照，不因事后转班改写；日期没有变化时也没有新的归属风险。
    """
    scene = _scene(harness, tag="boundary")
    created = _create(harness, scene).json()
    assessment_id = created["assessment"]["assessmentId"]
    second_class = harness.create_class(code="C2")
    harness.transfer_student(
        scene.students[0]["id"],
        from_class_id=scene.klass["id"],
        to_class_id=second_class["id"],
        moved_on=days_before(2),
        expected_student_revision=0,
    )

    renamed = harness.client.patch(
        f"/api/v1/assessments/{assessment_id}",
        json={"expectedRevision": 0, "title": "第一次施测（改标题）", "assessmentType": "quiz"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "第一次施测（改标题）"
    assert renamed.json()["assessmentType"] == "quiz"
    assert renamed.json()["heldOn"] == HELD_ON
    # 同值 heldOn 也不算变化：不做重核
    same_date = _patch_held_on(harness, assessment_id, revision=1, held_on=HELD_ON)
    assert same_date.status_code == 200, same_date.text
    assert same_date.json()["revision"] == 2
