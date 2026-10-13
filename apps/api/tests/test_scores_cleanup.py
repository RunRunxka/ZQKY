"""成绩版本 / 导入批次的彻底删除（误录入清理）：受守卫 + 单事务原子删除。

覆盖（全部走真 HTTP API 与真实教学库，``ScoresHarness`` 真实装配）：

- 版本删除：404；confirmed 成功（矩阵与修正行被清、active 指针清空且
  ``clearedActive=true``、不 bump ``assessments.revision``）；守卫 409
  ``SCORE_REVISION_IN_USE`` 三键计数（analysisRuns / dependentRevisions /
  importBatches）；删除后不可变触发器原样恢复（对另一 confirmed 版本试图直连
  SQL DELETE → 被拒，且触发器对象仍在 schema）。
- 批次删除：404；reviewing/cancelled 成功（预览行被清）；confirmed 且已生成
  版本 → 409 ``SCORE_IMPORT_IN_USE``；先删版本后批次可删；既有 discard 语义不变。
- 施测删除联动：清掉版本 + 批次后，施测删除的 ``count_references_in``
  对应键归零（删除链可解开）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.contracts.scores import (
    SCORE_IMPORT_CONFIRMED,
    SCORE_IMPORT_IN_USE,
    SCORE_IMPORT_NOT_FOUND,
    SCORE_REVISION_IN_USE,
    SCORE_REVISION_NOT_FOUND,
)
from tests.assessments_support import today
from tests.scores_support import (
    SAMPLE_HEADER,
    ScoresHarness,
    absence_ack,
    missing_ack,
    write_score_xlsx,
)


@pytest.fixture()
def harness(tmp_path: Path):
    with ScoresHarness(tmp_path) as running:
        yield running


def _scene(harness: ScoresHarness, *, tag: str = "sc1"):
    return harness.create_scene(tag=tag, students=[("甲", "0001"), ("乙", "0002")])


def _xlsx(tmp_path: Path, *, name: str = "scores.xlsx") -> Path:
    return write_score_xlsx(
        tmp_path / name,
        SAMPLE_HEADER,
        [["0001", "甲", 2, 2, 5], ["0002", "乙", 2, 3, None]],
    )


def _confirm_v1(
    harness: ScoresHarness, scene, tmp_path: Path, *, tag: str = "sc1"
) -> dict:
    """上传 → 确认首个成绩版本（两人次场景：乙缺 Q3 一个 missing 格）。"""
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _xlsx(tmp_path, name=f"scores-{tag}.xlsx")
    ).json()
    # 施测 revision 动态读取（同场景多次确认/删除后旧值已过期）
    current = harness.assessment(scene.assessment["assessmentId"])
    response = harness.confirm_import(
        view["importId"],
        {
            "expectedImportRevision": view["revision"],
            "expectedAssessmentRevision": current["revision"],
            "baseScoreRevisionId": view["baseScoreRevisionId"],
            "previewVersion": view["previewVersion"],
            "submissionId": f"confirm-{tag}",
            "missing": missing_ack([scene.participant_id("0002")], 1),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- 版本删除


def test_delete_revision_not_found(harness: ScoresHarness) -> None:
    missing = harness.client.delete("/api/v1/score-revisions/no-such-revision")
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == SCORE_REVISION_NOT_FOUND


def test_delete_confirmed_revision_clears_matrix_and_active_pointer(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = _scene(harness, tag="d1")
    confirmed = _confirm_v1(harness, scene, tmp_path, tag="d1")
    revision_id = confirmed["revisionId"]
    import_id = confirmed["importId"]
    assessment = harness.assessment(scene.assessment["assessmentId"])
    assert assessment["activeScoreRevisionId"] == revision_id
    revision_before = assessment["revision"]

    # 先删掉批次产出版本 → 批次随后也能删（联动顺序在批次用例复验）
    response = harness.client.delete(f"/api/v1/score-revisions/{revision_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "deleted": True,
        "revisionId": revision_id,
        "clearedActive": True,
        "removedScores": 6,  # 2 人次 × 3 叶
        "removedCorrections": 0,
    }

    # 版本行、矩阵行、修正行全部物理消失；active 指针被派生清空
    assert harness.count("score_revisions", "id = ?", (revision_id,)) == 0
    assert harness.count("student_item_scores", "score_revision_id = ?", (revision_id,)) == 0
    assert harness.count("score_revision_corrections", "revision_id = ?", (revision_id,)) == 0
    detail = harness.assessment(scene.assessment["assessmentId"])
    assert detail["activeScoreRevisionId"] is None
    # 不 bump assessments.revision：删除是独立动作，保持其它标签页 CAS 语义
    assert detail["revision"] == revision_before
    # 读路径 404
    gone = harness.client.get(f"/api/v1/score-revisions/{revision_id}")
    assert gone.status_code == 404
    # 重复删除同一版本 → 404（行已不存在）
    again = harness.client.delete(f"/api/v1/score-revisions/{revision_id}")
    assert again.status_code == 404

    # 版本删除后，其来源批次不再被产出守卫拦截（联动见批次用例）
    assert harness.count("score_imports", "id = ?", (import_id,)) == 1


def test_delete_revision_guard_counts_three_keys(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """任一引用 >0 → 409 ``SCORE_REVISION_IN_USE``，counts 恒含三键。"""
    scene = _scene(harness, tag="d2")
    confirmed = _confirm_v1(harness, scene, tmp_path, tag="d2")
    revision_id = confirmed["revisionId"]
    aid = scene.assessment["assessmentId"]

    # ① analysisRuns：播种最小 analysis_runs（workflow_jobs → score_revisions 已在）
    now = today()
    harness.raw_execute(
        "INSERT INTO workflow_jobs (id, owner_id, kind, state, created_at, updated_at) "
        "VALUES (?, 'local', 'analysis', 'succeeded', ?, ?)",
        (f"job-d2", now, now),
    )
    harness.raw_execute(
        "INSERT INTO analysis_runs (id, assessment_id, score_revision_id, paper_revision_id, "
        "subject_id, rule_code, input_hash, input_json, job_id, selected_count, leaf_count, "
        "knowledge_count, class_count, created_at) "
        "VALUES (?, ?, ?, ?, 'math', 'any_loss_v1', ?, '{}', ?, 1, 1, 0, 1, ?)",
        ("run-d2", aid, revision_id, scene.paper.revision_id, "0" * 64, "job-d2", now),
    )
    blocked = harness.client.delete(f"/api/v1/score-revisions/{revision_id}")
    assert blocked.status_code == 409, blocked.text
    body = blocked.json()
    assert body["code"] == SCORE_REVISION_IN_USE
    counts = body["details"]["counts"]
    assert counts == {"analysisRuns": 1, "dependentRevisions": 0, "importBatches": 0}
    assert "学情报告 1 条" in body["message"]
    assert "成绩版本仍被引用" in body["message"]
    assert harness.count("score_revisions", "id = ?", (revision_id,)) == 1
    # 学情报告按既有产品语义不可物理删除（analysis_no_delete 触发器，b4 登记）；
    # 版本删除守卫只负责如实报告引用并整体拒绝。


def test_delete_revision_guard_by_dependent_revision(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """修正链：v2 base v1 → v1 被 dependentRevisions 拦截。"""
    scene = _scene(harness, tag="d3")
    confirmed = _confirm_v1(harness, scene, tmp_path, tag="d3")
    v1 = confirmed["revisionId"]
    revision = harness.client.get(f"/api/v1/score-revisions/{v1}").json()
    yi = next(
        item
        for item in revision["participantSnapshot"]
        if item["studentNo"] == "0002"
    )
    third = revision["itemSnapshot"][2]
    corrected = harness.correct_scores(
        scene.assessment["assessmentId"],
        {
            "baseScoreRevisionId": v1,
            "expectedAssessmentRevision": confirmed["assessmentRevision"],
            "submissionId": "correct-d3",
            "reason": "补录漏填",
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
    assert corrected.status_code == 200, corrected.text
    v2 = corrected.json()["revisionId"]

    blocked = harness.client.delete(f"/api/v1/score-revisions/{v1}")
    assert blocked.status_code == 409, blocked.text
    body = blocked.json()
    counts = body["details"]["counts"]
    assert counts == {"analysisRuns": 0, "dependentRevisions": 1, "importBatches": 0}
    assert "基于它的更新成绩版本 1 条" in body["message"]
    # v2（有修正审计）自身无引用，可删
    ok = harness.client.delete(f"/api/v1/score-revisions/{v2}")
    assert ok.status_code == 200, ok.text
    assert ok.json()["removedCorrections"] == 1
    assert harness.count("score_revision_corrections", "revision_id = ?", (v2,)) == 0
    # v2 删除后 dependentRevisions 归零；首批导入的 base 本为 null（上传时无 active），
    # 因此 v1 引用全零 → 可删（删除链自修正链末端逐级解开）
    ok_again = harness.client.delete(f"/api/v1/score-revisions/{v1}")
    assert ok_again.status_code == 200, ok_again.text
    assert ok_again.json()["removedScores"] == 6
    assert harness.count("score_revisions", "assessment_id = ?", (scene.assessment["assessmentId"],)) == 0


def test_delete_revision_guard_by_import_batch(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """第二批导入 base 指向 v1（即使未确认）→ v1 被 importBatches 拦截。"""
    scene = _scene(harness, tag="d4")
    confirmed = _confirm_v1(harness, scene, tmp_path, tag="d4")
    v1 = confirmed["revisionId"]
    second = harness.upload_scores(
        scene.assessment["assessmentId"],
        _xlsx(tmp_path, name="scores-d4b.xlsx"),
    ).json()
    assert second["baseScoreRevisionId"] == v1

    blocked = harness.client.delete(f"/api/v1/score-revisions/{v1}")
    assert blocked.status_code == 409, blocked.text
    counts = blocked.json()["details"]["counts"]
    assert counts == {"analysisRuns": 0, "dependentRevisions": 0, "importBatches": 1}
    assert "基于它的导入批次 1 条" in blocked.json()["message"]


def test_delete_revision_restores_immutability_triggers(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """删除后两条不可变 DELETE 触发器必须原样恢复（受控行为不留后门）。"""
    scene = _scene(harness, tag="d5")
    confirmed = _confirm_v1(harness, scene, tmp_path, tag="d5")
    revision_id = confirmed["revisionId"]

    deleted = harness.client.delete(f"/api/v1/score-revisions/{revision_id}")
    assert deleted.status_code == 200, deleted.text

    # 对另一 confirmed 版本试图直连 SQL DELETE → 触发器兜底生效
    other = _confirm_v1(harness, scene, tmp_path, tag="d5b")
    connection = sqlite3.connect(str(harness.db_path))
    try:
        for sql, params in (
            ("DELETE FROM score_revisions WHERE id = ?", (other["revisionId"],)),
            (
                "DELETE FROM student_item_scores WHERE score_revision_id = ?",
                (other["revisionId"],),
            ),
        ):
            try:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute("BEGIN")
                connection.execute(sql, params)
            except sqlite3.IntegrityError as excinfo_error:
                assert "SCORE_REVISION_IMMUTABLE" in str(excinfo_error)
            else:  # pragma: no cover - 触发器兜底必须拦截
                pytest.fail(f"触发器未拦截：{sql}")
            finally:
                connection.execute("ROLLBACK")
        # 触发器对象仍在 schema 里（逐字恢复，与登记一致）
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' "
                "AND name IN ('immutable_score_revisions_delete', "
                "'immutable_item_scores_delete')"
            ).fetchall()
        }
        assert names == {
            "immutable_score_revisions_delete",
            "immutable_item_scores_delete",
        }
    finally:
        connection.close()


def test_delete_draft_revision_succeeds(harness: ScoresHarness, tmp_path: Path) -> None:
    """draft 版本同样可删（无 confirmed 触发器拦截路径也保持原子与回执）。"""
    scene = _scene(harness, tag="d6")
    aid = scene.assessment["assessmentId"]
    harness.raw_execute(
        "INSERT INTO score_revisions (id, assessment_id, version, state) "
        "VALUES ('sr-draft-d6', ?, 1, 'draft')",
        (aid,),
    )
    response = harness.client.delete("/api/v1/score-revisions/sr-draft-d6")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deleted"] is True
    assert body["clearedActive"] is False
    assert body["removedScores"] == 0 and body["removedCorrections"] == 0


# --------------------------------------------------------------------------- 批次删除


def test_delete_import_not_found(harness: ScoresHarness) -> None:
    missing = harness.client.delete("/api/v1/score-imports/no-such-import")
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == SCORE_IMPORT_NOT_FOUND


def test_delete_import_reviewing_and_cancelled(harness: ScoresHarness, tmp_path: Path) -> None:
    """reviewing 直接删；cancelled（先放弃）同样可删；预览行随批次消失。"""
    scene = _scene(harness, tag="i1")
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _xlsx(tmp_path, name="i1.xlsx")
    ).json()
    assert harness.count("score_import_rows", "import_id = ?", (view["importId"],)) == 2

    deleted = harness.client.delete(f"/api/v1/score-imports/{view['importId']}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted": True, "importId": view["importId"]}
    assert harness.count("score_imports", "id = ?", (view["importId"],)) == 0
    assert harness.count("score_import_rows", "import_id = ?", (view["importId"],)) == 0
    assert harness.client.get(f"/api/v1/score-imports/{view['importId']}").status_code == 404

    # cancelled 批次也可删
    view2 = harness.upload_scores(
        scene.assessment["assessmentId"], _xlsx(tmp_path, name="i1b.xlsx")
    ).json()
    discarded = harness.client.post(
        f"/api/v1/score-imports/{view2['importId']}/discard",
        json={"expectedRevision": view2["revision"]},
    )
    assert discarded.status_code == 200, discarded.text
    deleted2 = harness.client.delete(f"/api/v1/score-imports/{view2['importId']}")
    assert deleted2.status_code == 200, deleted2.text
    assert harness.count("score_imports", "id = ?", (view2["importId"],)) == 0


def test_delete_import_confirmed_with_revisions_is_409(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """confirmed 且已产出成绩版本 → 409；先彻底删版本后批次可删。"""
    scene = _scene(harness, tag="i2")
    confirmed = _confirm_v1(harness, scene, tmp_path, tag="i2")
    import_id = confirmed["importId"]
    revision_id = confirmed["revisionId"]

    blocked = harness.client.delete(f"/api/v1/score-imports/{import_id}")
    assert blocked.status_code == 409, blocked.text
    body = blocked.json()
    assert body["code"] == SCORE_IMPORT_IN_USE
    assert body["details"]["counts"] == {"scoreRevisions": 1}
    assert "已生成的成绩版本 1 条" in body["message"]
    assert harness.count("score_imports", "id = ?", (import_id,)) == 1

    # 先删版本（active 指针清空、矩阵清空），批次守卫归零
    removed = harness.client.delete(f"/api/v1/score-revisions/{revision_id}")
    assert removed.status_code == 200, removed.text
    deleted = harness.client.delete(f"/api/v1/score-imports/{import_id}")
    assert deleted.status_code == 200, deleted.text
    assert harness.count("score_imports", "id = ?", (import_id,)) == 0
    assert harness.count("score_import_rows", "import_id = ?", (import_id,)) == 0


def test_delete_import_keeps_discard_semantics(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """既有 discard 语义保持不变：confirmed 仍 409 ``SCORE_IMPORT_CONFIRMED``。"""
    scene = _scene(harness, tag="i3")
    confirmed = _confirm_v1(harness, scene, tmp_path, tag="i3")
    view = harness.client.get(
        f"/api/v1/score-imports/{confirmed['importId']}"
    ).json()
    discarded = harness.client.post(
        f"/api/v1/score-imports/{confirmed['importId']}/discard",
        json={"expectedRevision": view["revision"]},
    )
    assert discarded.status_code == 409, discarded.text
    assert discarded.json()["code"] == SCORE_IMPORT_CONFIRMED


def test_delete_import_failed_state_allowed(harness: ScoresHarness, tmp_path: Path) -> None:
    """failed 状态批次也可删（任何 state 都可删）。"""
    scene = _scene(harness, tag="i4")
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _xlsx(tmp_path, name="i4.xlsx")
    ).json()
    harness.raw_execute(
        "UPDATE score_imports SET state = 'failed' WHERE id = ?",
        (view["importId"],),
    )
    deleted = harness.client.delete(f"/api/v1/score-imports/{view['importId']}")
    assert deleted.status_code == 200, deleted.text
    assert harness.count("score_imports", "id = ?", (view["importId"],)) == 0


# --------------------------------------------------------------------------- 施测删除联动


def test_assessment_delete_cascades_scores_without_precleanup(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """R10-BE：施测删除直接级联成绩链（不再需要先手删版本/批次）。

    施测是成绩链的所有者：已确认修订、导入批次、小题分矩阵随施测一并删除
    （回执逐项计数），不再有"被成绩引用就只能归档"的挡路词。
    """
    scene = _scene(harness, tag="link")
    _confirm_v1(harness, scene, tmp_path, tag="link")
    aid = scene.assessment["assessmentId"]
    assessment = harness.assessment(aid)

    deleted = harness.client.delete(
        f"/api/v1/assessments/{aid}",
        params={"expectedRevision": assessment["revision"]},
    )
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["scoreRevisions"] == 1 and body["scoreImports"] == 1 and body["itemScores"] > 0
    assert harness.count("assessments", "id = ?", (aid,)) == 0
    assert harness.count("score_revisions", "assessment_id = ?", (aid,)) == 0
    assert harness.count("score_imports", "assessment_id = ?", (aid,)) == 0
    assert harness.count("student_item_scores", "assessment_id = ?", (aid,)) == 0
