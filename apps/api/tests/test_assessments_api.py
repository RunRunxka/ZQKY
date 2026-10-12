"""T30-b 施测接口测试：真实装配（名单 T30-a + 原卷确认链 T40）→ 施测创建/闸门/快照。

覆盖任务卡 §8 与验收条件 A8：

- 创建成功（201）+ 服务端姓名/学号快照冻结 + ``attemptNo`` 缺省 1；
- 幂等重放（同载荷）与 409 ``SUBMISSION_CONFLICT``（同 submissionId 不同载荷）；
- 拒绝：draft/不存在卷、空 participants、非法日期、班级不存在/已归档、行班级越范围、
  重复 classIds、同学生跨班重复、(student, attempt) 重复；
- 归属确认流：历史归属未覆盖 ``heldOn`` → 422 ``PARTICIPANT_CLASS_UNCONFIRMED``（row 定位）
  → 带 ``classConfirmed`` + 依据重提成功且**归属历史逐行不变**；
- 补考：自动下一人次、旧记录不变、再次同人次 409；
- 快照不变：学生改名/转班后既有施测快照仍是旧值；
- 版本守卫（409 + ``details.currentRevision``）与换卷 UPDATE 被 DB 触发器拒绝；
- 整批回滚（一行非法 → 零 assessments/assessment_classes/assessment_participants/submission）；
- 规模：200 人一次创建可用（记录耗时，不做硬门槛）。
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.contracts.assessments import (
    ASSESSMENT_HELD_ON_INVALID,
    ASSESSMENT_NOT_FOUND,
    ASSESSMENT_PAPER_INVALID,
    ASSESSMENT_REVISION_STALE,
    CLASS_ARCHIVED,
    PARTICIPANT_ATTEMPT_CONFLICT,
    PARTICIPANT_CLASS_SCOPE,
    PARTICIPANT_CLASS_UNCONFIRMED,
    PARTICIPANT_INVALID,
)
from app.contracts.teaching_loop import REVISION_CONFLICT, SUBMISSION_CONFLICT
from tests.assessments_support import (
    AssessmentsHarness,
    ConfirmedPaper,
    SAMPLE_TOTAL_UNITS,
    days_before,
    today,
)

SUBJECT_ID = "math"


@pytest.fixture()
def harness(tmp_path: Path):
    with AssessmentsHarness(tmp_path) as running:
        yield running


@dataclass
class Scene:
    """标准前置：已确认原卷 + 一个班 + 两名学生（一名有学号 0012、一名无学号）。"""

    paper: ConfirmedPaper
    klass: dict[str, Any]
    students: list[dict[str, Any]]


def _scene(
    harness: AssessmentsHarness,
    *,
    tag: str = "s1",
    class_code: str = "C1",
    joined_on: str | None = None,
) -> Scene:
    paper = harness.create_confirmed_paper(tag=tag)
    klass = harness.create_class(code=class_code)
    joined = joined_on or days_before(30)
    students = [
        harness.create_student(
            name="张三", student_no="0012", class_id=klass["id"], joined_on=joined
        ),
        harness.create_student(
            name="李四", student_no=None, class_id=klass["id"], joined_on=joined
        ),
    ]
    return Scene(paper=paper, klass=klass, students=students)


def _create(harness: AssessmentsHarness, scene: Scene, body: dict[str, Any]):
    return harness.client.post("/api/v1/assessments", json=body)


def _body(scene: Scene, **overrides: Any) -> dict[str, Any]:
    participants = overrides.pop(
        "participants",
        [
            AssessmentsHarness.participant(scene.students[0]["id"], scene.klass["id"]),
            AssessmentsHarness.participant(scene.students[1]["id"], scene.klass["id"]),
        ],
    )
    body = AssessmentsHarness.create_body(
        scene.paper,
        submission_id="sub-1",
        class_ids=[scene.klass["id"]],
        participants=participants,
        held_on=days_before(5),
    )
    body.update(overrides)
    return body


# --------------------------------------------------------------------------- 合法性


def test_create_confirmed_paper_success_and_list_detail(harness: AssessmentsHarness) -> None:
    scene = _scene(harness)
    response = _create(harness, scene, _body(scene))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["replayed"] is False
    assessment = body["assessment"]
    assert assessment["assessmentId"]
    assert assessment["paperRevisionId"] == scene.paper.revision_id
    assert assessment["paperId"] == scene.paper.paper_id
    assert assessment["paperTitle"] == scene.paper.title
    assert assessment["subjectId"] == SUBJECT_ID
    assert assessment["assessmentType"] == "exam"
    assert assessment["state"] == "open"
    assert assessment["revision"] == 0
    assert assessment["classIds"] == [scene.klass["id"]]
    assert assessment["participantCount"] == 2
    assert assessment["heldOn"] == days_before(5)

    rows = body["participants"]
    assert [row["nameSnapshot"] for row in rows] == ["张三", "李四"]
    assert [row["studentNoSnapshot"] for row in rows] == ["0012", None]
    assert all(row["attemptNo"] == 1 for row in rows)
    assert all(row["attendance"] == "present" for row in rows)
    assert all(row["classConfirmed"] is False for row in rows)
    # 客户端没有任何快照字段可上报；服务端从 students 读取后冻结
    assert all(row["studentId"] in {s["id"] for s in scene.students} for row in rows)

    detail = harness.client.get(f"/api/v1/assessments/{assessment['assessmentId']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["assessment"] == assessment
    # 详情按 (class_id, attempt_no, name_snapshot) 排序
    ordered = detail.json()["participants"]
    assert [(row["classId"], row["attemptNo"], row["nameSnapshot"]) for row in ordered] == sorted(
        (row["classId"], row["attemptNo"], row["nameSnapshot"]) for row in ordered
    )

    listing = harness.client.get("/api/v1/assessments")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["assessmentId"] == assessment["assessmentId"]

    by_subject = harness.client.get("/api/v1/assessments", params={"subjectId": SUBJECT_ID})
    assert by_subject.json()["total"] == 1
    other_subject = harness.client.get("/api/v1/assessments", params={"subjectId": "physics"})
    assert other_subject.json()["total"] == 0
    by_class = harness.client.get(
        "/api/v1/assessments", params={"classId": scene.klass["id"]}
    )
    assert by_class.json()["total"] == 1
    by_state = harness.client.get("/api/v1/assessments", params={"state": "open"})
    assert by_state.json()["total"] == 1
    closed = harness.client.get("/api/v1/assessments", params={"state": "closed"})
    assert closed.json()["total"] == 0
    bad_state = harness.client.get("/api/v1/assessments", params={"state": "draft"})
    assert bad_state.status_code == 422
    assert bad_state.json()["code"] == "INVALID_REQUEST"
    # 真实路由注册后不再命中 B0 通配占位
    assert listing.status_code != 501

    assert harness.count("assessments") == 1
    assert harness.count("assessment_classes") == 1
    assert harness.count("assessment_participants") == 2


def test_create_replay_same_submission_and_conflict(harness: AssessmentsHarness) -> None:
    scene = _scene(harness)
    body = _body(scene)
    first = _create(harness, scene, body)
    assert first.status_code == 201, first.text

    replayed = _create(harness, scene, body)
    assert replayed.status_code == 201, replayed.text
    assert replayed.json()["replayed"] is True
    assert replayed.json()["assessment"]["assessmentId"] == first.json()["assessment"]["assessmentId"]
    assert replayed.json()["participants"] == first.json()["participants"]
    assert harness.count("assessments") == 1
    assert harness.count("assessment_participants") == 2

    changed = dict(body)
    changed["title"] = "换标题但同 submissionId"
    conflict = _create(harness, scene, changed)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == SUBMISSION_CONFLICT
    assert harness.count("assessments") == 1


def test_list_pagination_and_filters(harness: AssessmentsHarness) -> None:
    scene = _scene(harness)
    first = _create(harness, scene, _body(scene))
    second = _create(harness, scene, _body(scene, submissionId="sub-2", title="第二次施测"))
    assert first.status_code == 201 and second.status_code == 201, (first.text, second.text)
    first_id = first.json()["assessment"]["assessmentId"]
    second_id = second.json()["assessment"]["assessmentId"]

    page = harness.client.get("/api/v1/assessments", params={"limit": 1, "offset": 0})
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert page.json()["offset"] == 0 and page.json()["limit"] == 1
    assert len(page.json()["items"]) == 1
    other = harness.client.get("/api/v1/assessments", params={"limit": 1, "offset": 1})
    assert {page.json()["items"][0]["assessmentId"], other.json()["items"][0]["assessmentId"]} == {
        first_id,
        second_id,
    }
    too_many = harness.client.get("/api/v1/assessments", params={"limit": 500})
    assert too_many.status_code == 422


def test_create_unknown_assessment_404(harness: AssessmentsHarness) -> None:
    missing = harness.client.get("/api/v1/assessments/no-such-assessment")
    assert missing.status_code == 404
    assert missing.json()["code"] == ASSESSMENT_NOT_FOUND


# --------------------------------------------------------------------------- 拒绝


def test_create_rejects_draft_and_unknown_paper(harness: AssessmentsHarness) -> None:
    draft = harness.import_draft_paper(tag="draft", title="未确认卷")
    klass = harness.create_class(code="C1")
    student = harness.create_student(
        name="张三", student_no="0012", class_id=klass["id"], joined_on=days_before(30)
    )
    participants = [AssessmentsHarness.participant(student["id"], klass["id"])]

    for revision_id in (draft["paperRevisionId"], "paper-revision-does-not-exist"):
        body = {
            "submissionId": f"sub-{revision_id[:8]}",
            "paperRevisionId": revision_id,
            "title": "拒绝卷",
            "heldOn": days_before(1),
            "classIds": [klass["id"]],
            "participants": participants,
        }
        response = harness.client.post("/api/v1/assessments", json=body)
        assert response.status_code == 422, response.text
        assert response.json()["code"] == ASSESSMENT_PAPER_INVALID
        if revision_id.startswith("paper-revision"):
            # 服务端把 reader 的"不存在"翻译为可定位的 422（不区分探测）
            assert response.json()["details"]["issues"][0]["field"] == "paperRevisionId"
    assert harness.count("assessments") == 0
    assert harness.count("command_submissions", "operation = ?", ("assessment.create",)) == 0

    # 绕过服务直插（draft 修订）同样被 DB 触发器拒绝
    with pytest.raises(sqlite3.IntegrityError) as err:
        harness.raw_execute(
            "INSERT INTO assessments (id, owner_id, paper_revision_id, title, "
            "assessment_type, held_on, state, revision, created_at) "
            "VALUES ('raw-1', 'local', ?, '绕过', 'exam', ?, 'open', 0, '2026-01-01T00:00:00Z')",
            (draft["paperRevisionId"], days_before(1)),
        )
    assert "PAPER_NOT_CONFIRMED" in str(err.value)


def test_create_rejects_empty_and_invalid_date(harness: AssessmentsHarness) -> None:
    scene = _scene(harness)
    empty = _body(scene, participants=[])
    response = _create(harness, scene, empty)
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"

    bad_date = _body(scene, heldOn="2026-13-40")
    response = _create(harness, scene, bad_date)
    assert response.status_code == 422
    assert response.json()["code"] == ASSESSMENT_HELD_ON_INVALID
    assert response.json()["details"]["issues"][0]["field"] == "heldOn"

    not_a_date = _body(scene, heldOn="20261340xx")
    response = _create(harness, scene, not_a_date)
    assert response.status_code == 422
    assert response.json()["code"] == ASSESSMENT_HELD_ON_INVALID
    assert harness.count("assessments") == 0


def test_create_rejects_missing_and_archived_class(harness: AssessmentsHarness) -> None:
    scene = _scene(harness)
    missing = _body(scene, classIds=["class-does-not-exist"])
    response = _create(harness, scene, missing)
    assert response.status_code == 422
    assert response.json()["code"] == PARTICIPANT_INVALID
    assert response.json()["details"]["issues"][0]["field"] == "classIds[0]"

    archived_class = harness.create_class(code="C-ARCHIVED")
    harness.archive_class(archived_class["id"], expected_revision=0)
    student = harness.create_student(
        name="王五",
        student_no="0031",
        class_id=scene.klass["id"],
        joined_on=days_before(30),
    )
    response = _create(
        harness,
        scene,
        _body(
            scene,
            classIds=[scene.klass["id"], archived_class["id"]],
            participants=[
                AssessmentsHarness.participant(student["id"], scene.klass["id"])
            ],
        ),
    )
    assert response.status_code == 422
    assert response.json()["code"] == CLASS_ARCHIVED
    assert response.json()["details"]["issues"][0]["field"] == "classIds[1]"
    assert harness.count("assessments") == 0


def test_create_rejects_participant_scope_and_duplicates(harness: AssessmentsHarness) -> None:
    scene = _scene(harness)
    other_class = harness.create_class(code="C2")

    out_of_scope = _body(
        scene,
        classIds=[scene.klass["id"]],
        participants=[
            AssessmentsHarness.participant(scene.students[0]["id"], other_class["id"])
        ],
    )
    response = _create(harness, scene, out_of_scope)
    assert response.status_code == 422
    assert response.json()["code"] == PARTICIPANT_CLASS_SCOPE
    issue = response.json()["details"]["issues"][0]
    assert issue["row"] == 0 and issue["field"] == "classId"

    duplicated_scope = _body(
        scene, classIds=[scene.klass["id"], scene.klass["id"]]
    )
    response = _create(harness, scene, duplicated_scope)
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"

    cross_class = _body(
        scene,
        classIds=[scene.klass["id"], other_class["id"]],
        participants=[
            AssessmentsHarness.participant(scene.students[0]["id"], scene.klass["id"]),
            AssessmentsHarness.participant(scene.students[0]["id"], other_class["id"]),
        ],
    )
    response = _create(harness, scene, cross_class)
    assert response.status_code == 422
    assert response.json()["code"] == PARTICIPANT_INVALID
    issue = response.json()["details"]["issues"][0]
    assert issue["row"] == 1 and issue["field"] == "classId"
    assert "人工选定" in issue["message"]

    same_attempt = _body(
        scene,
        participants=[
            AssessmentsHarness.participant(
                scene.students[0]["id"], scene.klass["id"], attempt_no=1
            ),
            AssessmentsHarness.participant(
                scene.students[0]["id"], scene.klass["id"], attempt_no=1
            ),
        ],
    )
    response = _create(harness, scene, same_attempt)
    assert response.status_code == 409
    assert response.json()["code"] == PARTICIPANT_ATTEMPT_CONFLICT
    assert response.json()["details"]["issues"][0]["row"] == 1

    unknown_student = _body(
        scene,
        participants=[
            AssessmentsHarness.participant("student-does-not-exist", scene.klass["id"])
        ],
    )
    response = _create(harness, scene, unknown_student)
    assert response.status_code == 422
    assert response.json()["code"] == PARTICIPANT_INVALID
    issue = response.json()["details"]["issues"][0]
    assert issue["row"] == 0 and issue["field"] == "studentId"
    assert harness.count("assessments") == 0


# --------------------------------------------------------------------------- 归属确认流


def test_class_confirmation_flow_freezes_note_without_touching_history(
    harness: AssessmentsHarness,
) -> None:
    """名单导入日 ≠ 真实入班日：未覆盖 heldOn 时教师显式确认，归属历史不变。"""
    paper = harness.create_confirmed_paper(tag="uncovered")
    klass = harness.create_class(code="C1")
    # 今天建班/建档（joinedOn 今天），施测日期在过去 → 归属未覆盖
    student = harness.create_student(
        name="张三", student_no="0012", class_id=klass["id"], joined_on=today()
    )
    held_on = days_before(30)
    body = AssessmentsHarness.create_body(
        paper,
        submission_id="uncovered-1",
        class_ids=[klass["id"]],
        participants=[AssessmentsHarness.participant(student["id"], klass["id"])],
        held_on=held_on,
    )
    before = harness.memberships_snapshot()

    rejected = harness.client.post("/api/v1/assessments", json=body)
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == PARTICIPANT_CLASS_UNCONFIRMED
    issue = rejected.json()["details"]["issues"][0]
    assert issue["row"] == 0 and issue["field"] == "classId"
    assert held_on in issue["message"]
    assert harness.count("assessments") == 0
    assert harness.memberships_snapshot() == before

    note = "名单今天导入，该生实际一直在班，本次班级以 C1 记"
    confirmed = dict(body)
    confirmed["participants"] = [
        AssessmentsHarness.participant(
            student["id"],
            klass["id"],
            class_confirmed=True,
            class_confirmation_note=note,
        )
    ]
    accepted = harness.client.post("/api/v1/assessments", json=confirmed)
    assert accepted.status_code == 201, accepted.text
    row = accepted.json()["participants"][0]
    assert row["classConfirmed"] is True
    assert row["classConfirmationNote"] == note
    assert row["classConfirmationAt"]
    stored = harness.raw_rows(
        "SELECT class_confirmed, class_confirmation_note, class_confirmation_at "
        "FROM assessment_participants WHERE id = ?",
        (row["participantId"],),
    )[0]
    assert stored["class_confirmed"] == 1
    assert stored["class_confirmation_note"] == note
    assert stored["class_confirmation_at"]
    # 归属历史逐行不变（不自动改 joined_on/left_on，不新增归属）
    assert harness.memberships_snapshot() == before

    # 同载荷重放：不再要求确认，返回原结果
    replay = harness.client.post("/api/v1/assessments", json=confirmed)
    assert replay.status_code == 201
    assert replay.json()["replayed"] is True


# --------------------------------------------------------------------------- 补考/补录


def test_add_makeup_attempt_allocates_next_and_keeps_old_rows(
    harness: AssessmentsHarness,
) -> None:
    scene = _scene(harness)
    created = _create(harness, scene, _body(scene))
    assert created.status_code == 201, created.text
    assessment = created.json()["assessment"]
    first_rows = {
        row["studentId"]: harness.raw_rows(
            "SELECT * FROM assessment_participants WHERE id = ?", (row["participantId"],)
        )[0]
        for row in created.json()["participants"]
    }

    response = harness.client.post(
        f"/api/v1/assessments/{assessment['assessmentId']}/participants",
        json={
            "submissionId": "makeup-1",
            "expectedRevision": assessment["revision"],
            "participants": [
                AssessmentsHarness.participant(scene.students[0]["id"], scene.klass["id"])
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["replayed"] is False
    assert body["assessment"]["revision"] == assessment["revision"] + 1
    assert body["assessment"]["participantCount"] == 3
    added = body["participants"]
    assert len(added) == 1
    assert added[0]["attemptNo"] == 2
    assert added[0]["nameSnapshot"] == "张三"

    # 旧人次记录逐字节不变（没有任何 UPDATE）
    for student_id, raw in first_rows.items():
        assert (
            harness.raw_rows(
                "SELECT * FROM assessment_participants WHERE student_id = ? AND attempt_no = 1",
                (student_id,),
            )[0]
            == raw
        )

    # 再次同人次 → 409
    conflict = harness.client.post(
        f"/api/v1/assessments/{assessment['assessmentId']}/participants",
        json={
            "submissionId": "makeup-2",
            "expectedRevision": body["assessment"]["revision"],
            "participants": [
                AssessmentsHarness.participant(
                    scene.students[0]["id"], scene.klass["id"], attempt_no=2
                )
            ],
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == PARTICIPANT_ATTEMPT_CONFLICT
    assert conflict.json()["details"]["issues"][0]["field"] == "attemptNo"

    # 幂等重放补考提交
    replay = harness.client.post(
        f"/api/v1/assessments/{assessment['assessmentId']}/participants",
        json={
            "submissionId": "makeup-1",
            "expectedRevision": assessment["revision"],
            "participants": [
                AssessmentsHarness.participant(scene.students[0]["id"], scene.klass["id"])
            ],
        },
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["participants"] == added
    assert harness.count("assessment_participants") == 3

    # 过期 revision 守卫
    stale = harness.client.post(
        f"/api/v1/assessments/{assessment['assessmentId']}/participants",
        json={
            "submissionId": "makeup-3",
            "expectedRevision": assessment["revision"],
            "participants": [
                AssessmentsHarness.participant(scene.students[1]["id"], scene.klass["id"])
            ],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == ASSESSMENT_REVISION_STALE
    assert stale.json()["details"]["currentRevision"] == body["assessment"]["revision"]
    assert harness.count("assessment_participants") == 3


def test_participant_add_validates_scope_and_students(harness: AssessmentsHarness) -> None:
    scene = _scene(harness)
    created = _create(harness, scene, _body(scene)).json()
    assessment_id = created["assessment"]["assessmentId"]
    revision = created["assessment"]["revision"]
    other_class = harness.create_class(code="C2")

    out_of_scope = harness.client.post(
        f"/api/v1/assessments/{assessment_id}/participants",
        json={
            "submissionId": "bad-scope",
            "expectedRevision": revision,
            "participants": [
                AssessmentsHarness.participant(
                    harness.create_student(
                        name="王五", student_no="0031", class_id=other_class["id"],
                        joined_on=days_before(30),
                    )["id"],
                    other_class["id"],
                )
            ],
        },
    )
    assert out_of_scope.status_code == 422
    assert out_of_scope.json()["code"] == PARTICIPANT_CLASS_SCOPE

    unknown = harness.client.post(
        f"/api/v1/assessments/{assessment_id}/participants",
        json={
            "submissionId": "bad-student",
            "expectedRevision": revision,
            "participants": [
                AssessmentsHarness.participant("student-does-not-exist", scene.klass["id"])
            ],
        },
    )
    assert unknown.status_code == 422
    assert unknown.json()["code"] == PARTICIPANT_INVALID
    assert harness.count("assessment_participants") == 2

    # 混合行（第一行合法、第二行非法）→ 整批回滚，零新增
    mixed = harness.client.post(
        f"/api/v1/assessments/{assessment_id}/participants",
        json={
            "submissionId": "mixed-rollback",
            "expectedRevision": revision,
            "participants": [
                AssessmentsHarness.participant(scene.students[0]["id"], scene.klass["id"]),
                AssessmentsHarness.participant(
                    "student-does-not-exist", scene.klass["id"]
                ),
            ],
        },
    )
    assert mixed.status_code == 422
    assert mixed.json()["code"] == PARTICIPANT_INVALID
    assert mixed.json()["details"]["issues"][0]["row"] == 1
    assert harness.count("assessment_participants") == 2
    assert harness.count(
        "command_submissions",
        "operation = ? AND submission_id = ?",
        ("assessment.participants", "mixed-rollback"),
    ) == 0


# --------------------------------------------------------------------------- 快照不变


def test_rename_and_transfer_do_not_change_snapshots(harness: AssessmentsHarness) -> None:
    scene = _scene(harness)
    created = _create(harness, scene, _body(scene))
    assert created.status_code == 201, created.text
    assessment_id = created.json()["assessment"]["assessmentId"]
    student_id = scene.students[0]["id"]

    harness.rename_student(student_id, name="张三改名", expected_revision=0)
    second_class = harness.create_class(code="C2")
    harness.transfer_student(
        student_id,
        from_class_id=scene.klass["id"],
        to_class_id=second_class["id"],
        moved_on=today(),
        expected_student_revision=1,
    )

    detail = harness.client.get(f"/api/v1/assessments/{assessment_id}")
    assert detail.status_code == 200, detail.text
    rows = {row["studentId"]: row for row in detail.json()["participants"]}
    assert rows[student_id]["nameSnapshot"] == "张三"
    assert rows[student_id]["classId"] == scene.klass["id"]
    assert rows[student_id]["studentNoSnapshot"] == "0012"
    # 学生表已更新，但施测快照未变
    current = harness.get_student(student_id)
    assert current["name"] == "张三改名"
    assert any(item["classId"] == second_class["id"] for item in current["memberships"])


def test_client_snapshot_fields_are_rejected_and_server_snapshot_wins(
    harness: AssessmentsHarness,
) -> None:
    """参测姓名/学号只能由服务端读取冻结：客户端快照字段直接拒绝（契约 extra=forbid）。"""
    scene = _scene(harness)
    forged = dict(AssessmentsHarness.participant(scene.students[0]["id"], scene.klass["id"]))
    forged.update({"name": "李鬼", "studentNo": "9999"})
    rejected = _create(harness, scene, _body(scene, participants=[forged]))
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "INVALID_REQUEST"
    assert harness.count("assessments") == 0

    absent = AssessmentsHarness.participant(
        scene.students[0]["id"], scene.klass["id"], attendance="absent"
    )
    accepted = _create(harness, scene, _body(scene, participants=[absent]))
    assert accepted.status_code == 201, accepted.text
    row = accepted.json()["participants"][0]
    assert row["nameSnapshot"] == "张三"
    assert row["studentNoSnapshot"] == "0012"
    assert row["attendance"] == "absent"


# --------------------------------------------------------------------------- 版本守卫


def test_update_revision_guard_and_paper_fixed(harness: AssessmentsHarness) -> None:
    scene = _scene(harness)
    created = _create(harness, scene, _body(scene)).json()
    assessment = created["assessment"]
    assessment_id = assessment["assessmentId"]

    stale = harness.client.patch(
        f"/api/v1/assessments/{assessment_id}",
        json={"expectedRevision": 5, "title": "过期更新"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == ASSESSMENT_REVISION_STALE
    assert stale.json()["details"]["currentRevision"] == 0

    updated = harness.client.patch(
        f"/api/v1/assessments/{assessment_id}",
        json={
            "expectedRevision": 0,
            "title": "第一次施测（改）",
            "assessmentType": "quiz",
            "heldOn": days_before(6),
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["title"] == "第一次施测（改）"
    assert body["assessmentType"] == "quiz"
    assert body["heldOn"] == days_before(6)
    assert body["revision"] == 1
    assert body["paperRevisionId"] == scene.paper.revision_id

    bad_date = harness.client.patch(
        f"/api/v1/assessments/{assessment_id}",
        json={"expectedRevision": 1, "heldOn": "2026-02-30"},
    )
    assert bad_date.status_code == 422
    assert bad_date.json()["code"] == ASSESSMENT_HELD_ON_INVALID

    # 换卷 UPDATE（绕过服务）被 DB 触发器拒绝
    with pytest.raises(sqlite3.IntegrityError) as err:
        harness.raw_execute(
            "UPDATE assessments SET paper_revision_id = 'other-revision' WHERE id = ?",
            (assessment_id,),
        )
    assert "ASSESSMENT_PAPER_FIXED" in str(err.value)


# --------------------------------------------------------------------------- 整批回滚


def test_batch_rollback_leaves_no_rows(harness: AssessmentsHarness) -> None:
    scene = _scene(harness)
    before = {
        table: harness.count(table)
        for table in ("assessments", "assessment_classes", "assessment_participants")
    }
    other_class = harness.create_class(code="C2")
    participants = [
        AssessmentsHarness.participant(scene.students[0]["id"], scene.klass["id"]),
        AssessmentsHarness.participant(scene.students[1]["id"], other_class["id"]),  # 越范围
        AssessmentsHarness.participant(scene.students[1]["id"], scene.klass["id"]),
    ]
    response = _create(harness, scene, _body(scene, participants=participants))
    assert response.status_code == 422
    assert response.json()["code"] == PARTICIPANT_CLASS_SCOPE
    assert response.json()["details"]["issues"][0]["row"] == 1

    for table, expected in before.items():
        assert harness.count(table) == expected, table
    assert (
        harness.count(
            "command_submissions",
            "operation = ? AND submission_id = ?",
            ("assessment.create", "sub-1"),
        )
        == 0
    )


# --------------------------------------------------------------------------- 规模


def test_scale_two_hundred_participants(harness: AssessmentsHarness) -> None:
    paper = harness.create_confirmed_paper(tag="scale")
    klass = harness.create_class(code="C1")
    rows = [(f"{index:04d}", f"学生{index:03d}") for index in range(1, 201)]
    confirmed = harness.import_roster(klass["id"], rows, tag="scale")
    student_ids = [applied["studentId"] for applied in confirmed["applied"]]
    assert len(student_ids) == 200

    body = AssessmentsHarness.create_body(
        paper,
        submission_id="scale-1",
        class_ids=[klass["id"]],
        participants=[
            AssessmentsHarness.participant(student_id, klass["id"])
            for student_id in student_ids
        ],
        held_on=today(),
    )
    started = time.perf_counter()
    response = harness.client.post("/api/v1/assessments", json=body)
    elapsed = time.perf_counter() - started
    assert response.status_code == 201, response.text
    assert response.json()["assessment"]["participantCount"] == 200
    assert harness.count("assessment_participants") == 200
    # 名单→原卷→施测全链：学号按文本冻结（前导零保留）
    snapshots = {
        row["studentId"]: row["studentNoSnapshot"]
        for row in response.json()["participants"]
    }
    assert snapshots[student_ids[0]] == "0001"
    assert harness.raw_rows(
        "SELECT student_no_snapshot FROM assessment_participants WHERE student_id = ?",
        (student_ids[0],),
    )[0]["student_no_snapshot"] == "0001"
    # 记录耗时（无硬门槛；本地 SQLite 一次事务写入 200 行）
    print(f"[T30-b] 200 名参测一次创建耗时 {elapsed:.3f}s")


# --------------------------------------------------------------------------- 装配缺失


class _PortReader:
    """只实现冻结端口 ``ConfirmedPaperReader`` 的替身（不依赖 T40 adapter 细节）。"""

    def __init__(self, source: ConfirmedPaper | None = None, *, error: Exception | None = None):
        self._source = source
        self._error = error
        self.calls: list[str] = []

    def read_confirmed_paper_revision(self, paper_revision_id: str):
        from app.contracts.roster import ConfirmedPaperRevisionView

        self.calls.append(paper_revision_id)
        if self._error is not None:
            raise self._error
        assert self._source is not None
        return ConfirmedPaperRevisionView(
            paperId=self._source.paper_id,
            paperRevisionId=self._source.revision_id,
            title=self._source.title,
            subjectId=SUBJECT_ID,
            totalScoreUnits=SAMPLE_TOTAL_UNITS,
            scoredLeafCount=self._source.scored_leaf_count,
        )


def test_service_uses_frozen_reader_port_contract(harness: AssessmentsHarness) -> None:
    """门面按冻结端口（``read_confirmed_paper_revision``）工作，而非 T40 adapter 私有形状。"""
    from app.services.assessments.service import build_assessment_service

    scene = _scene(harness)
    port = _PortReader(scene.paper)
    harness.app.state.assessment_service = build_assessment_service(
        harness.app.state.teaching, reader=port
    )
    accepted = _create(harness, scene, _body(scene))
    assert accepted.status_code == 201, accepted.text
    assert port.calls == [scene.paper.revision_id]

    missing = _PortReader(error=_paper_not_found())
    harness.app.state.assessment_service = build_assessment_service(
        harness.app.state.teaching, reader=missing
    )
    rejected = _create(
        harness, scene, _body(scene, submissionId="sub-2", title="换提交号")
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == ASSESSMENT_PAPER_INVALID

    # 端口未装配（None）→ 503，可重试，不伪造原卷
    harness.app.state.assessment_service = build_assessment_service(
        harness.app.state.teaching, reader=None
    )
    unavailable = _create(
        harness, scene, _body(scene, submissionId="sub-3", title="无 reader")
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "SERVICE_UNAVAILABLE"
    assert unavailable.json()["retryable"] is True

    # 端口显式报告不可用（B1 占位语义）→ 原样 501 PAPER_READER_UNAVAILABLE
    from app.contracts.roster import PAPER_READER_UNAVAILABLE, UnavailablePaperReader

    harness.app.state.assessment_service = build_assessment_service(
        harness.app.state.teaching, reader=UnavailablePaperReader()
    )
    placeholder = _create(
        harness, scene, _body(scene, submissionId="sub-4", title="占位 reader")
    )
    assert placeholder.status_code == 501
    assert placeholder.json()["code"] == PAPER_READER_UNAVAILABLE


def _paper_not_found() -> Exception:
    """reader 端"修订不存在"（T40 adapter 口径：404 PAPER_NOT_FOUND）。"""
    from app.contracts.papers import PAPER_NOT_FOUND
    from app.core.exceptions import AppError

    return AppError("原卷修订不存在。", code=PAPER_NOT_FOUND, status_code=404)


def test_other_assessment_routes_keep_501_placeholder(harness: AssessmentsHarness) -> None:
    """本批不做的成绩等子路由仍由 B0 通配占位返回 501，不得被真实路由吞成 404/200。"""
    response = harness.client.post("/api/v1/assessments/some-id/scores", json={})
    assert response.status_code == 501
    assert response.json()["code"] == "FEATURE_NOT_IMPLEMENTED"


def test_missing_service_returns_503(harness: AssessmentsHarness) -> None:
    harness.app.state.assessment_service = None
    listing = harness.client.get("/api/v1/assessments")
    assert listing.status_code == 503
    assert listing.json()["code"] == "SERVICE_UNAVAILABLE"
    assert listing.json()["retryable"] is True
    # 形状合法的请求：装配缺失先于业务闸门（503 而不是 422/501）
    created = harness.client.post(
        "/api/v1/assessments",
        json={
            "submissionId": "sub-1",
            "paperRevisionId": "rev-1",
            "title": "施测",
            "heldOn": days_before(1),
            "classIds": ["c1"],
            "participants": [
                {"studentId": "s1", "classId": "c1", "attemptNo": 1}
            ],
        },
    )
    assert created.status_code == 503
    assert created.json()["code"] == "SERVICE_UNAVAILABLE"


def test_revision_conflict_code_is_not_generic(harness: AssessmentsHarness) -> None:
    """版本守卫用施测契约的错误码（不是通用 REVISION_CONFLICT）。"""
    assert ASSESSMENT_REVISION_STALE != REVISION_CONFLICT
    assert SAMPLE_TOTAL_UNITS > 0
