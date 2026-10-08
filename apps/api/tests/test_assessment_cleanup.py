"""施测归档/恢复与参测人次移除（误录入清理）的真实装配测试。

覆盖（全部走真 HTTP API 与真实教学库）：

- 归档：更新/补录/出勤校正与新成绩导入一律 409 ``ASSESSMENT_ARCHIVED``；恢复后可写；
  乐观锁用施测 revision（旧 revision → 409）；
- 人次移除：干净人次可移除（revision 递增、剩余人次正确、DB 行消失）；
  旧 revision → 409；归档施测 → 409 ``ASSESSMENT_ARCHIVED``；
  守卫：已有成绩版本（含草稿）、被成绩导入预览行引用、已有学情报告 → 409
  ``PARTICIPANT_REMOVE_BLOCKED``，且**零级联删除**（下游行原样保留）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.assessments import (
    ASSESSMENT_ARCHIVED,
    ASSESSMENT_IN_USE,
    PARTICIPANT_REMOVE_BLOCKED,
)
from tests.assessments_support import AssessmentsHarness, today
from tests.scores_support import ScoresHarness, SAMPLE_HEADER, write_score_xlsx


@pytest.fixture()
def harness(tmp_path: Path):
    with AssessmentsHarness(tmp_path) as running:
        yield running


@pytest.fixture()
def scores(tmp_path: Path):
    with ScoresHarness(tmp_path) as running:
        yield running


def _scene(harness: AssessmentsHarness, *, tag: str = "cl"):
    """一个班两名学生 + 一次施测（两名参测人次）。"""
    paper = harness.create_confirmed_paper(tag=tag)
    klass = harness.create_class(code=f"C-{tag}")
    students = [
        harness.create_student(name="张三", student_no="0012", class_id=klass["id"]),
        harness.create_student(name="李四", student_no="0013", class_id=klass["id"]),
    ]
    body = AssessmentsHarness.create_body(
        paper,
        submission_id=f"as-{tag}",
        class_ids=[klass["id"]],
        participants=[
            AssessmentsHarness.participant(item["id"], klass["id"])
            for item in students
        ],
    )
    response = harness.client.post("/api/v1/assessments", json=body)
    assert response.status_code == 201, response.text
    return paper, klass, students, response.json()


def _archive(harness: AssessmentsHarness, assessment_id: str, revision: int):
    return harness.client.post(
        f"/api/v1/assessments/{assessment_id}/archive",
        json={"expectedRevision": revision},
    )


def _restore(harness: AssessmentsHarness, assessment_id: str, revision: int):
    return harness.client.post(
        f"/api/v1/assessments/{assessment_id}/restore",
        json={"expectedRevision": revision},
    )


# --------------------------------------------------------------------------- 归档


def test_archive_blocks_writes_and_restore_reopens(harness: AssessmentsHarness) -> None:
    _paper, klass, students, detail = _scene(harness)
    assessment = detail["assessment"]
    aid = assessment["assessmentId"]

    archived = _archive(harness, aid, assessment["revision"])
    assert archived.status_code == 200, archived.text
    body = archived.json()
    assert body["state"] == "archived"
    assert body["revision"] == assessment["revision"] + 1

    # 更新 / 补录 / 出勤校正：归档后一律 409，即使 revision 正确
    updated = harness.client.patch(
        f"/api/v1/assessments/{aid}",
        json={"expectedRevision": body["revision"], "title": "改名"},
    )
    assert updated.status_code == 409 and updated.json()["code"] == ASSESSMENT_ARCHIVED

    added = harness.client.post(
        f"/api/v1/assessments/{aid}/participants",
        json={
            "expectedRevision": body["revision"],
            "submissionId": "add-after-archive",
            "participants": [
                AssessmentsHarness.participant(students[0]["id"], klass["id"], attempt_no=2)
            ],
        },
    )
    assert added.status_code == 409 and added.json()["code"] == ASSESSMENT_ARCHIVED

    participant_id = detail["participants"][0]["participantId"]
    attendance = harness.client.patch(
        f"/api/v1/assessments/{aid}/participants/{participant_id}/attendance",
        json={
            "submissionId": "att-after-archive",
            "expectedRevision": body["revision"],
            "attendance": "absent",
            "reason": "教师更正",
        },
    )
    assert attendance.status_code == 409 and attendance.json()["code"] == ASSESSMENT_ARCHIVED

    # 归档仍可读（列表/详情）
    listed = harness.client.get("/api/v1/assessments", params={"state": "archived"})
    assert listed.status_code == 200
    assert [item["assessmentId"] for item in listed.json()["items"]] == [aid]

    # 恢复后可写
    restored = _restore(harness, aid, body["revision"])
    assert restored.status_code == 200, restored.text
    reopened = restored.json()
    assert reopened["state"] == "open"
    renamed = harness.client.patch(
        f"/api/v1/assessments/{aid}",
        json={"expectedRevision": reopened["revision"], "title": "恢复后改名"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "恢复后改名"


def test_archive_revision_conflict_and_missing(harness: AssessmentsHarness) -> None:
    _paper, _klass, _students, detail = _scene(harness, tag="cl2")
    aid = detail["assessment"]["assessmentId"]

    stale = _archive(harness, aid, detail["assessment"]["revision"] + 5)
    assert stale.status_code == 409
    assert stale.json()["details"]["currentRevision"] == detail["assessment"]["revision"]

    missing = harness.client.post(
        "/api/v1/assessments/missing-assessment/archive",
        json={"expectedRevision": 0},
    )
    assert missing.status_code == 404


def test_archived_assessment_rejects_new_score_import(scores: ScoresHarness, tmp_path: Path) -> None:
    scene = scores.create_scene(tag="arch-score", students=[("甲", "0001")])
    aid = scene.assessment["assessmentId"]
    archived = _archive(scores, aid, scene.assessment["revision"])
    assert archived.status_code == 200, archived.text

    path = write_score_xlsx(
        tmp_path / "scores.xlsx", SAMPLE_HEADER, [["0001", "甲", 2, 2, 5]]
    )
    upload = scores.upload_scores(aid, path)
    assert upload.status_code == 409, upload.text
    assert upload.json()["code"] == ASSESSMENT_ARCHIVED


# --------------------------------------------------------------------------- 人次移除


def test_remove_clean_participant(harness: AssessmentsHarness) -> None:
    _paper, _klass, _students, detail = _scene(harness, tag="rm1")
    assessment = detail["assessment"]
    aid = assessment["assessmentId"]
    target = detail["participants"][0]["participantId"]

    response = harness.client.delete(
        f"/api/v1/assessments/{aid}/participants/{target}",
        params={"expectedRevision": assessment["revision"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assessment"]["revision"] == assessment["revision"] + 1
    assert [row["participantId"] for row in body["participants"]] == [
        item["participantId"] for item in detail["participants"][1:]
    ]
    assert harness.count("assessment_participants", "assessment_id = ?", (aid,)) == 1

    # 旧 revision 重放 → 409（先按陈旧冲突拒绝，不重复删除）
    replay = harness.client.delete(
        f"/api/v1/assessments/{aid}/participants/{target}",
        params={"expectedRevision": assessment["revision"]},
    )
    assert replay.status_code == 409


def test_remove_participant_blocked_by_score_revision(harness: AssessmentsHarness) -> None:
    _paper, _klass, _students, detail = _scene(harness, tag="rm2")
    assessment = detail["assessment"]
    aid = assessment["assessmentId"]
    target = detail["participants"][0]["participantId"]
    # 直接写入一条草稿成绩修订，模拟"成绩版本已存在"（守卫只数版本数，不看状态）
    harness.raw_execute(
        "INSERT INTO score_revisions (id, assessment_id, version, state) VALUES (?, ?, 1, 'draft')",
        (f"sr-{aid}", aid),
    )

    response = harness.client.delete(
        f"/api/v1/assessments/{aid}/participants/{target}",
        params={"expectedRevision": assessment["revision"]},
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == PARTICIPANT_REMOVE_BLOCKED
    assert harness.count("assessment_participants", "assessment_id = ?", (aid,)) == 2


def test_remove_participant_blocked_by_pending_import(scores: ScoresHarness, tmp_path: Path) -> None:
    """进行中的成绩导入批次会阻止移除人次（预览可能在引用它）；放弃批次后即可移除。"""
    scene = scores.create_scene(tag="rm3", students=[("甲", "0001"), ("乙", "0002")])
    aid = scene.assessment["assessmentId"]
    path = write_score_xlsx(
        tmp_path / "scores.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, 2, 5]],
    )
    upload = scores.upload_scores(aid, path)
    assert upload.status_code == 201, upload.text
    view = upload.json()
    assert view["state"] == "reviewing"

    target = scene.participant_id("0001")
    blocked = scores.client.delete(
        f"/api/v1/assessments/{aid}/participants/{target}",
        params={"expectedRevision": scene.assessment["revision"]},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == PARTICIPANT_REMOVE_BLOCKED
    assert scores.count("assessment_participants", "assessment_id = ?", (aid,)) == 2

    # 放弃批次之后可以移除（守卫只拦进行中的批次）
    discard = scores.client.post(
        f"/api/v1/score-imports/{view['importId']}/discard",
        json={"expectedRevision": view["revision"]},
    )
    assert discard.status_code == 200, discard.text
    removed = scores.client.delete(
        f"/api/v1/assessments/{aid}/participants/{target}",
        params={"expectedRevision": scene.assessment["revision"]},
    )
    assert removed.status_code == 200, removed.text
    assert scores.count("assessment_participants", "assessment_id = ?", (aid,)) == 1


def test_remove_participant_blocked_by_analysis_run(harness: AssessmentsHarness) -> None:
    _paper, _klass, _students, detail = _scene(harness, tag="rm4")
    assessment = detail["assessment"]
    aid = assessment["assessmentId"]
    target = detail["participants"][0]["participantId"]
    # 按 FK 顺序播种最小可用行：任务 → 成绩修订 → 学情运行（守卫只数报告数）
    now = today()
    harness.raw_execute(
        "INSERT INTO workflow_jobs (id, owner_id, kind, state, created_at, updated_at) "
        "VALUES (?, 'local', 'analysis', 'succeeded', ?, ?)",
        (f"job-{aid}", now, now),
    )
    harness.raw_execute(
        "INSERT INTO score_revisions (id, assessment_id, version, state) VALUES (?, ?, 1, 'draft')",
        (f"sr-{aid}", aid),
    )
    harness.raw_execute(
        "INSERT INTO analysis_runs (id, assessment_id, score_revision_id, paper_revision_id, "
        "subject_id, rule_code, input_hash, input_json, job_id, selected_count, leaf_count, "
        "knowledge_count, class_count, created_at) "
        "VALUES (?, ?, ?, ?, 'math', 'any_loss_v1', ?, '{}', ?, 1, 1, 0, 1, ?)",
        (f"run-{aid}", aid, f"sr-{aid}", assessment["paperRevisionId"], "0" * 64, f"job-{aid}", now),
    )

    blocked = harness.client.delete(
        f"/api/v1/assessments/{aid}/participants/{target}",
        params={"expectedRevision": assessment["revision"]},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == PARTICIPANT_REMOVE_BLOCKED
    # 守卫顺序把"报告"放在最前：教师得到最可行动的提示
    assert "学情报告" in blocked.json()["message"]
    assert harness.count("assessment_participants", "assessment_id = ?", (aid,)) == 2


def test_remove_participant_blocked_when_archived(harness: AssessmentsHarness) -> None:
    _paper, _klass, _students, detail = _scene(harness, tag="rm4b")
    assessment = detail["assessment"]
    aid = assessment["assessmentId"]
    target = detail["participants"][0]["participantId"]

    archived = _archive(harness, aid, assessment["revision"])
    assert archived.status_code == 200, archived.text
    blocked = harness.client.delete(
        f"/api/v1/assessments/{aid}/participants/{target}",
        params={"expectedRevision": archived.json()["revision"]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == ASSESSMENT_ARCHIVED
    assert harness.count("assessment_participants", "assessment_id = ?", (aid,)) == 2


def test_remove_participant_not_found_and_cross_assessment(harness: AssessmentsHarness) -> None:
    _paper, _klass, _students, detail = _scene(harness, tag="rm5")
    aid = detail["assessment"]["assessmentId"]
    revision = detail["assessment"]["revision"]

    missing = harness.client.delete(
        f"/api/v1/assessments/{aid}/participants/missing-participant",
        params={"expectedRevision": revision},
    )
    assert missing.status_code == 404

    # 另一个施测的人次不能被本施测移除（按 (id, assessment) 双条件删除）
    other = harness.import_draft_paper(tag="rm6", title="rm6 卷")
    paper2 = harness.confirm_paper(other, tag="rm6")
    klass2 = harness.create_class(code="C-rm6")
    student2 = harness.create_student(
        name="王五", student_no="0014", class_id=klass2["id"]
    )
    body2 = AssessmentsHarness.create_body(
        paper2,
        submission_id="as-rm6",
        class_ids=[klass2["id"]],
        participants=[AssessmentsHarness.participant(student2["id"], klass2["id"])],
    )
    created2 = harness.client.post("/api/v1/assessments", json=body2)
    assert created2.status_code == 201, created2.text
    detail2 = created2.json()
    aid2 = detail2["assessment"]["assessmentId"]
    foreign = detail2["participants"][0]["participantId"]
    cross = harness.client.delete(
        f"/api/v1/assessments/{aid}/participants/{foreign}",
        params={"expectedRevision": revision},
    )
    assert cross.status_code == 404
    assert harness.count("assessment_participants", "assessment_id = ?", (aid2,)) == 1


# --------------------------------------------------------------------------- 施测整体删除


def test_delete_clean_assessment_succeeds(harness: AssessmentsHarness) -> None:
    _paper, _klass, _students, detail = _scene(harness, tag="del1")
    aid = detail["assessment"]["assessmentId"]

    response = harness.client.delete(
        f"/api/v1/assessments/{aid}",
        params={"expectedRevision": detail["assessment"]["revision"]},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": True, "assessmentId": aid}

    # 物理删除：施测行与参测/范围子行全部消失
    assert harness.count("assessments", "id = ?", (aid,)) == 0
    assert harness.count("assessment_participants", "assessment_id = ?", (aid,)) == 0
    assert harness.count("assessment_classes", "assessment_id = ?", (aid,)) == 0
    fetched = harness.client.get(f"/api/v1/assessments/{aid}")
    assert fetched.status_code == 404


def test_delete_assessment_blocked_by_score_revision(harness: AssessmentsHarness) -> None:
    _paper, _klass, _students, detail = _scene(harness, tag="del2")
    aid = detail["assessment"]["assessmentId"]
    harness.raw_execute(
        "INSERT INTO score_revisions (id, assessment_id, version, state) VALUES (?, ?, 1, 'draft')",
        (f"sr-{aid}", aid),
    )

    blocked = harness.client.delete(
        f"/api/v1/assessments/{aid}",
        params={"expectedRevision": detail["assessment"]["revision"]},
    )
    assert blocked.status_code == 409, blocked.text
    body = blocked.json()
    assert body["code"] == ASSESSMENT_IN_USE
    assert body["details"]["counts"]["scoreRevisions"] == 1
    assert body["details"]["counts"]["scoreImports"] == 0
    assert body["details"]["counts"]["analysisRuns"] == 0
    assert body["details"]["counts"]["practiceConversions"] == 0
    # 零删除
    assert harness.count("assessments", "id = ?", (aid,)) == 1


def test_delete_assessment_blocked_by_import_and_practice_conversion(
    harness: AssessmentsHarness,
) -> None:
    """score_imports 与 practice_conversions 的引用同样拦截（逐项计数）。"""
    _paper, _klass, _students, detail = _scene(harness, tag="del3")
    aid = detail["assessment"]["assessmentId"]
    now = today()
    harness.raw_execute(
        "INSERT INTO workflow_jobs (id, owner_id, kind, state, created_at, updated_at) "
        "VALUES ('job-del3', 'local', 'analysis', 'succeeded', ?, ?)",
        (now, now),
    )
    harness.raw_execute(
        "INSERT INTO file_assets (id, kind, blob_key, sha256, media_type, byte_size, "
        "original_name, created_at) VALUES ('fa-del3', 'score_sheet', 'blobs/' || ?, ?, "
        "'application/octet-stream', 1, 'scores.xlsx', ?)",
        ("b" * 63, "b" * 64, now),
    )
    harness.raw_execute(
        "INSERT INTO score_imports (id, assessment_id, file_id, state, created_at) "
        "VALUES ('si-del3', ?, 'fa-del3', 'reviewing', ?)",
        (aid, now),
    )
    blocked = harness.client.delete(
        f"/api/v1/assessments/{aid}",
        params={"expectedRevision": detail["assessment"]["revision"]},
    )
    assert blocked.status_code == 409
    counts = blocked.json()["details"]["counts"]
    assert counts["scoreImports"] == 1


def test_delete_assessment_revision_conflict(harness: AssessmentsHarness) -> None:
    _paper, _klass, _students, detail = _scene(harness, tag="del4")
    aid = detail["assessment"]["assessmentId"]

    stale = harness.client.delete(
        f"/api/v1/assessments/{aid}",
        params={"expectedRevision": detail["assessment"]["revision"] + 3},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "ASSESSMENT_REVISION_STALE"
    assert stale.json()["details"]["currentRevision"] == detail["assessment"]["revision"]
    assert harness.count("assessments", "id = ?", (aid,)) == 1


def test_delete_assessment_not_found(harness: AssessmentsHarness) -> None:
    missing = harness.client.delete(
        "/api/v1/assessments/no-such-assessment", params={"expectedRevision": 0}
    )
    assert missing.status_code == 404
