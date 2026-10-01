"""T60 成绩修正测试：不可变 base 复制全矩阵、修正当时参测快照、审计与并发。

对应任务卡 §3「T60」业务点 6 与测试清单：v2 全矩阵 + 审计行 + active 前移 +
assessment.revision 递增；base≠active → 409；并发双修正只成功一个；旧修订与旧快照不变。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from app.contracts.scores import (
    SCORE_ASSESSMENT_REVISION_CONFLICT,
    SCORE_BASE_REVISION_CONFLICT,
    SCORE_CELL_OVER_MAX,
    SCORE_CORRECTION_INVALID,
    SCORE_ITEM_UNKNOWN,
    SCORE_NO_BASE_REVISION,
    SCORE_PARTICIPANT_UNKNOWN,
    SCORE_REVISION_IMMUTABLE,
    SCORE_REVISION_NOT_FOUND,
    ScoreRevisionCorrectRequest,
)
from app.core.exceptions import AppError
from app.services.scores.service import ScoreService
from tests.scores_support import (
    SAMPLE_HEADER,
    ScoreScene,
    ScoresHarness,
    absence_ack,
    missing_ack,
    write_score_xlsx,
)


@pytest.fixture()
def harness(tmp_path: Path):
    with ScoresHarness(tmp_path) as running:
        yield running


def _scene(harness: ScoresHarness, *, tag: str = "corr") -> ScoreScene:
    return harness.create_scene(
        tag=tag,
        students=[("甲", "0001"), ("乙", "0002"), ("丙", "0003"), ("丁", "0004")],
        attendance={"0003": "absent"},
    )


def _xlsx(tmp_path: Path) -> Path:
    return write_score_xlsx(
        tmp_path / "scores.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, 2, 5], ["0002", "乙", 2, 3, None], ["0004", "丁", 0, 3, 5]],
    )


def _confirm_v1(harness: ScoresHarness, scene: ScoreScene, tmp_path: Path) -> dict[str, Any]:
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _xlsx(tmp_path)
    ).json()
    response = harness.confirm_import(
        view["importId"],
        {
            "expectedImportRevision": view["revision"],
            "expectedAssessmentRevision": scene.assessment["revision"],
            "baseScoreRevisionId": None,
            "previewVersion": view["previewVersion"],
            "submissionId": "confirm-v1",
            "absences": [
                absence_ack(scene.klass["id"], [scene.participant_id("0003")])
            ],
            "missing": missing_ack([scene.participant_id("0002")], 1),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _snapshot_ids(harness: ScoresHarness, scene: ScoreScene, revision_id: str):
    revision = harness.client.get(f"/api/v1/score-revisions/{revision_id}").json()
    return revision["participantSnapshot"], revision["itemSnapshot"]


def test_correction_creates_full_new_version_with_audit(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = _scene(harness)
    v1 = _confirm_v1(harness, scene, tmp_path)
    participants, items = _snapshot_ids(harness, scene, v1["revisionId"])
    yi = next(item for item in participants if item["name"] == "乙")
    third = items[2]

    response = harness.correct_scores(
        scene.assessment["assessmentId"],
        {
            "baseScoreRevisionId": v1["revisionId"],
            "expectedAssessmentRevision": v1["assessmentRevision"],
            "submissionId": "correct-1",
            "reason": "补录漏填的 Q3 得分",
            "corrections": [
                {
                    "participantId": yi["participantId"],
                    "itemId": third["itemId"],
                    "status": "recorded",
                    "scoreText": "4",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["replayed"] is False
    assert result["version"] == 2
    assert result["baseRevisionId"] == v1["revisionId"]
    assert result["revisionId"] != v1["revisionId"]
    assert result["activeScoreRevisionId"] == result["revisionId"]
    assert result["assessmentRevision"] == v1["assessmentRevision"] + 1
    active = harness.raw_rows(
        "SELECT active_score_revision_id, revision FROM assessments WHERE id = ?",
        (scene.assessment["assessmentId"],),
    )[0]
    assert active["active_score_revision_id"] == result["revisionId"]
    assert active["revision"] == result["assessmentRevision"]

    # v2 全矩阵：乙的 Q3 变成 recorded(400)，总分非空；其余人次从 base 复制
    matrix = harness.score_matrix(result["revisionId"]).json()
    assert matrix["total"] == 4
    assert matrix["missingCellCount"] == 0
    by_name = {row["participant"]["name"]: row for row in matrix["rows"]}
    assert [cell["scoreUnits"] for cell in by_name["乙"]["cells"]] == [200, 300, 400]
    assert by_name["乙"]["participant"]["totalUnits"] == 900
    assert [cell["status"] for cell in by_name["丙"]["cells"]] == ["absent"] * 3
    assert by_name["甲"]["participant"]["totalUnits"] == 900

    # 审计：原值/新值/理由/坐标（人次+小题）
    audit = harness.raw_rows(
        "SELECT * FROM score_revision_corrections WHERE revision_id = ? ORDER BY seq",
        (result["revisionId"],),
    )
    assert len(audit) == 1
    entry = audit[0]
    assert entry["participant_id"] == yi["participantId"]
    assert entry["item_id"] == third["itemId"]
    assert entry["old_status"] == "missing" and entry["old_score_units"] is None
    assert entry["new_status"] == "recorded" and entry["new_score_units"] == 400
    assert entry["reason"] == "补录漏填的 Q3 得分"
    assert entry["seq"] == 1

    # 旧修订不变：仍是 missing、仍是旧快照、仍不可变
    old_matrix = harness.score_matrix(v1["revisionId"]).json()
    old_yi = next(
        row for row in old_matrix["rows"] if row["participant"]["name"] == "乙"
    )
    assert [cell["status"] for cell in old_yi["cells"]] == [
        "recorded",
        "recorded",
        "missing",
    ]
    assert old_matrix["missingCellCount"] == 1
    assert old_matrix["revision"]["state"] == "confirmed"
    revisions = harness.score_revisions(scene.assessment["assessmentId"]).json()
    assert revisions["total"] == 2
    assert [item["version"] for item in revisions["items"]] == [1, 2]
    assert revisions["items"][0]["baseRevisionId"] is None
    assert revisions["items"][1]["baseRevisionId"] == v1["revisionId"]

    # v2 已确认 → 不可变（DB 触发器兜底）
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError) as error:
        harness.raw_execute(
            "UPDATE student_item_scores SET score_units = 1 WHERE score_revision_id = ?",
            (result["revisionId"],),
        )
    assert SCORE_REVISION_IMMUTABLE in str(error.value)


def test_correction_version_and_validation_errors(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = _scene(harness)
    v1 = _confirm_v1(harness, scene, tmp_path)
    participants, items = _snapshot_ids(harness, scene, v1["revisionId"])
    yi = next(item for item in participants if item["name"] == "乙")
    third = items[2]
    first = items[0]
    c_id = scene.participant_id("0003")
    base = v1["revisionId"]

    def body(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "baseScoreRevisionId": base,
            "expectedAssessmentRevision": v1["assessmentRevision"],
            "submissionId": "corr-err",
            "reason": "修正",
            "corrections": [
                {
                    "participantId": yi["participantId"],
                    "itemId": third["itemId"],
                    "status": "recorded",
                    "scoreText": "4",
                }
            ],
        }
        payload.update(overrides)
        return payload

    # 施测版本不符
    stale = harness.correct_scores(
        scene.assessment["assessmentId"], body(expectedAssessmentRevision=0)
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == SCORE_ASSESSMENT_REVISION_CONFLICT
    assert stale.json()["details"]["currentRevision"] == v1["assessmentRevision"]

    # base 不存在
    unknown = harness.correct_scores(
        scene.assessment["assessmentId"], body(baseScoreRevisionId="nope")
    )
    assert unknown.status_code == 404
    assert unknown.json()["code"] == SCORE_REVISION_NOT_FOUND

    # 参测人次不在 base
    bad_participant = harness.correct_scores(
        scene.assessment["assessmentId"],
        body(
            corrections=[
                {"participantId": "ghost", "itemId": third["itemId"], "status": "recorded", "scoreText": "1"}
            ]
        ),
    )
    assert bad_participant.status_code == 422
    assert bad_participant.json()["code"] == SCORE_PARTICIPANT_UNKNOWN

    # 小题不在 base（用别的施测的 itemId 形状）
    bad_item = harness.correct_scores(
        scene.assessment["assessmentId"],
        body(
            corrections=[
                {"participantId": yi["participantId"], "itemId": "ghost-item", "status": "recorded", "scoreText": "1"}
            ]
        ),
    )
    assert bad_item.status_code == 422
    assert bad_item.json()["code"] == SCORE_ITEM_UNKNOWN

    # 同（人次, 小题）重复
    duplicated = harness.correct_scores(
        scene.assessment["assessmentId"],
        body(
            corrections=[
                {"participantId": yi["participantId"], "itemId": third["itemId"], "status": "recorded", "scoreText": "4"},
                {"participantId": yi["participantId"], "itemId": third["itemId"], "status": "recorded", "scoreText": "5"},
            ]
        ),
    )
    assert duplicated.status_code == 422
    assert duplicated.json()["code"] == SCORE_CORRECTION_INVALID

    # 没有实际变化（甲 = (2,2,5)，原样再提交一次）
    jia = next(item for item in participants if item["name"] == "甲")
    no_change = harness.correct_scores(
        scene.assessment["assessmentId"],
        body(
            corrections=[
                {"participantId": jia["participantId"], "itemId": first["itemId"], "status": "recorded", "scoreText": "2"}
            ]
        ),
    )
    assert no_change.status_code == 422
    assert no_change.json()["code"] == SCORE_CORRECTION_INVALID

    # 超满分
    over = harness.correct_scores(
        scene.assessment["assessmentId"],
        body(
            corrections=[
                {"participantId": yi["participantId"], "itemId": third["itemId"], "status": "recorded", "scoreText": "9"}
            ]
        ),
    )
    assert over.status_code == 422, over.text
    assert over.json()["code"] == SCORE_CELL_OVER_MAX

    # 缺考人次改成 recorded（1 分）允许：base 的 absent → recorded
    fixed_absent = harness.correct_scores(
        scene.assessment["assessmentId"],
        body(
            submissionId="corr-absent",
            corrections=[
                {"participantId": c_id, "itemId": first["itemId"], "status": "recorded", "scoreText": "1"}
            ],
        ),
    )
    assert fixed_absent.status_code == 200, fixed_absent.text
    assert fixed_absent.json()["version"] == 2

    # 双修正：base 仍是 v1 但 active 已是 v2 → 409
    stale_base = harness.correct_scores(
        scene.assessment["assessmentId"],
        body(
            submissionId="corr-stale",
            expectedAssessmentRevision=fixed_absent.json()["assessmentRevision"],
        ),
    )
    assert stale_base.status_code == 409, stale_base.text
    assert stale_base.json()["code"] == SCORE_BASE_REVISION_CONFLICT

    # active 被清空（合成状态）→ SCORE_NO_BASE_REVISION
    harness.raw_execute(
        "UPDATE assessments SET active_score_revision_id = NULL WHERE id = ?",
        (scene.assessment["assessmentId"],),
    )
    no_base = harness.correct_scores(
        scene.assessment["assessmentId"],
        body(
            submissionId="corr-nobase",
            expectedAssessmentRevision=fixed_absent.json()["assessmentRevision"],
        ),
    )
    assert no_base.status_code == 409, no_base.text
    assert no_base.json()["code"] == SCORE_NO_BASE_REVISION


def test_correction_replay_and_concurrency(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = _scene(harness)
    v1 = _confirm_v1(harness, scene, tmp_path)
    participants, items = _snapshot_ids(harness, scene, v1["revisionId"])
    yi = next(item for item in participants if item["name"] == "乙")
    payload = {
        "baseScoreRevisionId": v1["revisionId"],
        "expectedAssessmentRevision": v1["assessmentRevision"],
        "submissionId": "corr-concurrent",
        "reason": "修正 Q3",
        "corrections": [
            {
                "participantId": yi["participantId"],
                "itemId": items[2]["itemId"],
                "status": "recorded",
                "scoreText": "4",
            }
        ],
    }
    service: ScoreService = harness.service()
    request = ScoreRevisionCorrectRequest.model_validate(payload)
    barrier = threading.Barrier(2)
    succeeded: list[tuple[str, Any]] = []
    errors: list[AppError] = []
    lock = threading.Lock()

    def worker(tag: str) -> None:
        body = request.model_copy(update={"submission_id": tag})
        barrier.wait()
        try:
            outcome = service.correct_scores(scene.assessment["assessmentId"], body)
        except AppError as exc:
            with lock:
                errors.append(exc)
        else:
            with lock:
                succeeded.append((tag, outcome))

    threads = [
        threading.Thread(target=worker, args=(f"corr-{index}",)) for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert len(succeeded) == 1, f"并发双修正只允许一个成功：{succeeded} / {errors}"
    assert len(errors) == 1
    assert errors[0].status_code == 409
    assert harness.count(
        "score_revisions", "assessment_id = ?", (scene.assessment["assessmentId"],)
    ) == 2
    assert harness.count("score_revision_corrections") == 1

    # 重放：同 submissionId 同载荷返回原结果（不新增修订）
    winner_id, winner = succeeded[0]
    replay = harness.correct_scores(
        scene.assessment["assessmentId"], {**payload, "submissionId": winner_id}
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["revisionId"] == winner.revision_id
    assert harness.count("score_revision_corrections") == 1


def test_correction_keeps_old_snapshot_when_attempt_added(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """新增补考人次后修正：新版本用**修正当时**的快照；旧版本快照保持不变。"""
    scene = _scene(harness)
    v1 = _confirm_v1(harness, scene, tmp_path)
    participants, items = _snapshot_ids(harness, scene, v1["revisionId"])

    added = harness.client.post(
        f"/api/v1/assessments/{scene.assessment['assessmentId']}/participants",
        json={
            "expectedRevision": v1["assessmentRevision"],
            "submissionId": "add-attempt-corr",
            "participants": [
                {
                    "studentId": scene.student_id("0001"),
                    "classId": scene.klass["id"],
                    "attendance": "present",
                }
            ],
        },
    )
    assert added.status_code == 200, added.text
    new_participant = added.json()["participants"][0]["participantId"]
    assessment_revision = added.json()["assessment"]["revision"]
    assert assessment_revision == v1["assessmentRevision"] + 1

    response = harness.correct_scores(
        scene.assessment["assessmentId"],
        {
            "baseScoreRevisionId": v1["revisionId"],
            "expectedAssessmentRevision": assessment_revision,
            "submissionId": "corr-with-new-attempt",
            "reason": "补考人次加入后修正",
            "corrections": [
                {
                    "participantId": participants[1]["participantId"],
                    "itemId": items[2]["itemId"],
                    "status": "recorded",
                    "scoreText": "2",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    v2 = response.json()
    matrix = harness.score_matrix(v2["revisionId"]).json()
    assert matrix["total"] == 5
    fresh = next(
        row
        for row in matrix["rows"]
        if row["participant"]["participantId"] == new_participant
    )
    assert [cell["status"] for cell in fresh["cells"]] == ["missing"] * 3
    assert fresh["participant"]["attemptNo"] == 2

    # 旧版本仍按旧快照读（只有 4 人次）
    old = harness.score_matrix(v1["revisionId"]).json()
    assert old["total"] == 4
    old_ids = {row["participant"]["participantId"] for row in old["rows"]}
    assert new_participant not in old_ids


def test_revision_reads_and_404(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = _scene(harness)
    v1 = _confirm_v1(harness, scene, tmp_path)
    matrix_unknown = harness.client.get("/api/v1/score-revisions/ghost/matrix")
    assert matrix_unknown.status_code == 404
    assert matrix_unknown.json()["code"] == SCORE_REVISION_NOT_FOUND
    revision_unknown = harness.client.get("/api/v1/score-revisions/ghost")
    assert revision_unknown.status_code == 404
    listing_unknown = harness.client.get(
        "/api/v1/assessments/ghost-assessment/score-revisions"
    )
    assert listing_unknown.status_code == 404
    assert listing_unknown.json()["code"] == "ASSESSMENT_NOT_FOUND"
    # 合法读：矩阵 offset 超出 → 空页但 total 正确
    page = harness.score_matrix(v1["revisionId"], offset=10, limit=5).json()
    assert page["rows"] == [] and page["total"] == 4
    assert page["items"] and page["missingCellCount"] == 1
