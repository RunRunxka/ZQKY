"""T60 成绩确认测试：三版本语义、承认范围、单事务矩阵、幂等重放、并发与不可变。

对应任务卡 §3「T60」业务点 5 与测试清单：授权样例矩阵（A/B/C/D）确认后读数、
缺列缺行承认、承认不符 422 定位、三种 409、同 submissionId 重放、并发双确认、
确认后 PATCH/改分被拒（服务层 + DB 触发器兜底）。
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest

from app.contracts.scores import (
    SCORE_ACKNOWLEDGEMENT_MISMATCH,
    SCORE_ASSESSMENT_REVISION_CONFLICT,
    SCORE_BASE_REVISION_CONFLICT,
    SCORE_CELL_INVALID,
    SCORE_IMPORT_NOT_EDITABLE,
    SCORE_IMPORT_REVISION_CONFLICT,
    SCORE_MATRIX_INCOMPLETE,
    SCORE_ROW_DUPLICATE_PARTICIPANT,
)
from app.contracts.teaching_loop import SUBMISSION_CONFLICT
from app.core.exceptions import AppError
from app.services.scores.service import ScoreService
from tests.scores_support import (
    SAMPLE_HEADER,
    ScoreScene,
    ScoresHarness,
    absence_ack,
    cells_by_column,
    missing_ack,
    row_for,
    write_score_xlsx,
)


@pytest.fixture()
def harness(tmp_path: Path):
    with ScoresHarness(tmp_path) as running:
        yield running


def _sample_scene(harness: ScoresHarness, *, tag: str = "c1") -> ScoreScene:
    return harness.create_scene(
        tag=tag,
        students=[("甲", "0001"), ("乙", "0002"), ("丙", "0003"), ("丁", "0004")],
        attendance={"0003": "absent"},
    )


def _sample_xlsx(tmp_path: Path) -> Path:
    return write_score_xlsx(
        tmp_path / "scores.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, 2, 5], ["0002", "乙", 2, 3, None], ["0004", "丁", 0, 3, 5]],
    )


def _confirm_body(
    view: dict[str, Any],
    scene: ScoreScene,
    *,
    submission_id: str = "sub-confirm-1",
    absences: list[dict[str, Any]] | None = None,
    missing: dict[str, Any] | None = None,
    preview_version: int | None = None,
    expected_import_revision: int | None = None,
    expected_assessment_revision: int | None = None,
    base: str | None | object = ...,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "expectedImportRevision": (
            view["revision"]
            if expected_import_revision is None
            else expected_import_revision
        ),
        "expectedAssessmentRevision": (
            scene.assessment["revision"]
            if expected_assessment_revision is None
            else expected_assessment_revision
        ),
        "baseScoreRevisionId": view["baseScoreRevisionId"] if base is ... else base,
        "previewVersion": (
            view["previewVersion"] if preview_version is None else preview_version
        ),
        "submissionId": submission_id,
    }
    if absences is not None:
        body["absences"] = absences
    if missing is not None:
        body["missing"] = missing
    return body


def _issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(payload.get("details", {}).get("issues") or [])


# --------------------------------------------------------------------------- 正常路径


def test_confirm_sample_matrix_and_totals(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = _sample_scene(harness)
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path)
    ).json()
    assert view["missingCellCount"] == 1

    body = _confirm_body(
        view,
        scene,
        absences=[absence_ack(scene.klass["id"], [scene.participant_id("0003")])],
        missing=missing_ack([scene.participant_id("0002")], 1),
    )
    response = harness.confirm_import(view["importId"], body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["state"] == "confirmed"
    assert result["replayed"] is False
    assert result["revisionId"]
    assert result["activeScoreRevisionId"] == result["revisionId"]
    assert result["assessmentRevision"] == scene.assessment["revision"] + 1

    # 施测版本前移 + 导入置 confirmed（同事务）
    assert harness.assessment(scene.assessment["assessmentId"])["revision"] == result[
        "assessmentRevision"
    ]
    import_view = harness.get_import(view["importId"]).json()
    assert import_view["state"] == "confirmed"
    assert import_view["revision"] == view["revision"] + 1

    matrix = harness.score_matrix(result["revisionId"]).json()
    assert matrix["total"] == 4 and len(matrix["rows"]) == 4
    items = matrix["items"]
    assert [item["maxScoreUnits"] for item in items] == [200, 300, 500]
    assert all(item["itemPath"] for item in items)
    assert matrix["missingCellCount"] == 1
    assert matrix["missingParticipantIds"] == [scene.participant_id("0002")]
    assert matrix["absentClassIds"] == [scene.klass["id"]]

    by_name = {row["participant"]["name"]: row for row in matrix["rows"]}
    jia = by_name["甲"]
    assert [cell["status"] for cell in jia["cells"]] == ["recorded"] * 3
    assert [cell["scoreUnits"] for cell in jia["cells"]] == [200, 200, 500]
    assert jia["participant"]["totalUnits"] == 900
    assert jia["participant"]["totalMaxUnits"] == 1000

    yi = by_name["乙"]
    assert [cell["status"] for cell in yi["cells"]] == ["recorded", "recorded", "missing"]
    assert yi["participant"]["totalUnits"] is None

    bing = by_name["丙"]
    assert [cell["status"] for cell in bing["cells"]] == ["absent"] * 3
    assert bing["participant"]["attendance"] == "absent"
    assert bing["participant"]["totalUnits"] is None

    ding = by_name["丁"]
    assert [cell["status"] for cell in ding["cells"]] == ["recorded"] * 3
    assert ding["cells"][0]["scoreUnits"] == 0  # 0 是有效分，不是 missing
    assert ding["participant"]["totalUnits"] == 800

    # 分页：items 不分页、rows 分页
    page = harness.score_matrix(result["revisionId"], offset=0, limit=2).json()
    assert len(page["rows"]) == 2 and page["total"] == 4
    assert len(page["items"]) == 3
    assert page["missingCellCount"] == 1

    revisions = harness.score_revisions(scene.assessment["assessmentId"]).json()
    assert revisions["total"] == 1
    revision = revisions["items"][0]
    assert revision["revisionId"] == result["revisionId"]
    assert revision["version"] == 1 and revision["state"] == "confirmed"
    assert len(revision["participantSnapshot"]) == 4
    assert len(revision["itemSnapshot"]) == 3
    assert revision["sourceImportId"] == view["importId"]
    assert revision["baseRevisionId"] is None
    single = harness.client.get(f"/api/v1/score-revisions/{result['revisionId']}")
    assert single.status_code == 200
    assert single.json()["itemSnapshot"] == revision["itemSnapshot"]


def test_confirm_acknowledgement_mismatch_variants(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = _sample_scene(harness)
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path)
    ).json()
    c_id = scene.participant_id("0003")
    b_id = scene.participant_id("0002")
    good_absences = [absence_ack(scene.klass["id"], [c_id])]

    cases = [
        ("missing 未承认", {"absences": good_absences, "missing": None}, None),
        (
            "missing 单元数不符",
            {"absences": good_absences, "missing": missing_ack([b_id], 3)},
            "cellCount",
        ),
        (
            "missing 人次不符",
            {"absences": good_absences, "missing": missing_ack([c_id], 1)},
            "participantIds",
        ),
        (
            "缺考班级未承认",
            {"absences": [], "missing": missing_ack([b_id], 1)},
            "absences",
        ),
        (
            "缺考人次不符",
            {
                "absences": [absence_ack(scene.klass["id"], [b_id])],
                "missing": missing_ack([b_id], 1),
            },
            "participantIds",
        ),
    ]
    for label, kwargs, expected_field in cases:
        response = harness.confirm_import(
            view["importId"], _confirm_body(view, scene, **kwargs)
        )
        assert response.status_code == 422, f"{label}: {response.text}"
        body = response.json()
        assert body["code"] == SCORE_ACKNOWLEDGEMENT_MISMATCH, label
        issues = _issues(body)
        assert issues, label
        if expected_field is not None:
            assert any(issue["field"] == expected_field for issue in issues), label
        assert harness.count("score_revisions") == 0, label
        assert harness.assessment(scene.assessment["assessmentId"])[
            "revision"
        ] == scene.assessment["revision"], label

    # 预览版本不符（PATCH 之后用旧 previewVersion 承认）
    patched = harness.patch_import(
        view["importId"],
        {
            "expectedRevision": view["revision"],
            "rows": [
                {
                    "rowNo": row_for(
                        harness.list_import_rows(view["importId"]).json(), "乙"
                    )["rowNo"],
                    "cells": [
                        {
                            "row": row_for(
                                harness.list_import_rows(view["importId"]).json(), "乙"
                            )["rowNo"],
                            "column": "E",
                            "text": "4",
                        }
                    ],
                }
            ],
        },
    )
    assert patched.status_code == 200, patched.text
    updated = patched.json()
    stale = harness.confirm_import(
        view["importId"],
        _confirm_body(
            updated,
            scene,
            absences=good_absences,
            missing=missing_ack([b_id], 1),
            preview_version=view["previewVersion"],
        ),
    )
    assert stale.status_code == 422, stale.text
    assert stale.json()["code"] == SCORE_ACKNOWLEDGEMENT_MISMATCH
    assert any(
        issue["field"] == "previewVersion" for issue in _issues(stale.json())
    )


def test_confirm_three_versions_conflict(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = _sample_scene(harness)
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path)
    ).json()
    b_id = scene.participant_id("0002")
    c_id = scene.participant_id("0003")
    kwargs = {
        "absences": [absence_ack(scene.klass["id"], [c_id])],
        "missing": missing_ack([b_id], 1),
    }

    stale_import = harness.confirm_import(
        view["importId"],
        _confirm_body(view, scene, expected_import_revision=99, **kwargs),
    )
    assert stale_import.status_code == 409, stale_import.text
    assert stale_import.json()["code"] == SCORE_IMPORT_REVISION_CONFLICT
    assert stale_import.json()["details"]["currentRevision"] == view["revision"]

    stale_assessment = harness.confirm_import(
        view["importId"],
        _confirm_body(view, scene, expected_assessment_revision=7, **kwargs),
    )
    assert stale_assessment.status_code == 409, stale_assessment.text
    assert stale_assessment.json()["code"] == SCORE_ASSESSMENT_REVISION_CONFLICT
    assert stale_assessment.json()["details"]["currentRevision"] == scene.assessment[
        "revision"
    ]

    wrong_base = harness.confirm_import(
        view["importId"], _confirm_body(view, scene, base="no-such-revision", **kwargs)
    )
    assert wrong_base.status_code == 409, wrong_base.text
    assert wrong_base.json()["code"] == SCORE_BASE_REVISION_CONFLICT
    assert harness.count("score_revisions") == 0

    # 首个版本确认成功后：新导入的 base 必须是 v1；拿 null 确认 → 409
    first = harness.confirm_import(view["importId"], _confirm_body(view, scene, **kwargs))
    assert first.status_code == 200, first.text
    v1 = first.json()["revisionId"]
    second = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path)
    ).json()
    assert second["baseScoreRevisionId"] == v1
    assert harness.count("score_revisions") == 1
    stale_base = harness.confirm_import(
        second["importId"],
        _confirm_body(
            second,
            scene,
            base=None,
            submission_id="stale-base",
            expected_assessment_revision=first.json()["assessmentRevision"],
            **kwargs,
        ),
    )
    assert stale_base.status_code == 409, stale_base.text
    assert stale_base.json()["code"] == SCORE_BASE_REVISION_CONFLICT


def test_confirm_replay_is_idempotent(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = _sample_scene(harness)
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path)
    ).json()
    body = _confirm_body(
        view,
        scene,
        absences=[
            absence_ack(scene.klass["id"], [scene.participant_id("0003")])
        ],
        missing=missing_ack([scene.participant_id("0002")], 1),
    )
    first = harness.confirm_import(view["importId"], body)
    assert first.status_code == 200, first.text
    revision_id = first.json()["revisionId"]
    revision_count = harness.count(
        "score_revisions", "assessment_id = ?", (scene.assessment["assessmentId"],)
    )
    import_row = harness.raw_rows(
        "SELECT revision, state FROM score_imports WHERE id = ?", (view["importId"],)
    )[0]

    replay = harness.confirm_import(view["importId"], body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["revisionId"] == revision_id
    assert replay.json()["assessmentRevision"] == first.json()["assessmentRevision"]
    assert (
        harness.count(
            "score_revisions",
            "assessment_id = ?",
            (scene.assessment["assessmentId"],),
        )
        == revision_count
    )
    after = harness.raw_rows(
        "SELECT revision, state FROM score_imports WHERE id = ?", (view["importId"],)
    )[0]
    assert after == import_row

    conflict = harness.confirm_import(view["importId"], {**body, "previewVersion": 99})
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == SUBMISSION_CONFLICT


def test_concurrent_double_confirm_advances_once(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = _sample_scene(harness)
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path)
    ).json()
    service: ScoreService = harness.service()
    body = _confirm_body(
        view,
        scene,
        absences=[
            absence_ack(scene.klass["id"], [scene.participant_id("0003")])
        ],
        missing=missing_ack([scene.participant_id("0002")], 1),
    )
    from app.contracts.scores import ScoreImportConfirmRequest

    barrier = threading.Barrier(2)
    results: list[Any] = []
    errors: list[AppError] = []
    lock = threading.Lock()

    def worker(submission_id: str) -> None:
        payload = ScoreImportConfirmRequest.model_validate(
            {**body, "submissionId": submission_id}
        )
        barrier.wait()
        try:
            outcome = service.confirm_score_import(view["importId"], payload)
        except AppError as exc:  # 竞争失败方：明确 409
            with lock:
                errors.append(exc)
        else:
            with lock:
                results.append(outcome)

    threads = [
        threading.Thread(target=worker, args=(f"concurrent-{index}",))
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert len(results) == 1, f"应当只前进一批：{results} / {errors}"
    assert len(errors) == 1
    assert errors[0].status_code == 409
    assert errors[0].code in (
        SCORE_IMPORT_NOT_EDITABLE,
        SCORE_BASE_REVISION_CONFLICT,
        SCORE_ASSESSMENT_REVISION_CONFLICT,
    )
    assert (
        harness.count(
            "score_revisions",
            "assessment_id = ?",
            (scene.assessment["assessmentId"],),
        )
        == 1
    )
    assert harness.assessment(scene.assessment["assessmentId"])["revision"] == 1


def test_confirmed_revision_is_immutable(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = _sample_scene(harness)
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path)
    ).json()
    confirmed = harness.confirm_import(
        view["importId"],
        _confirm_body(
            view,
            scene,
            absences=[
                absence_ack(scene.klass["id"], [scene.participant_id("0003")])
            ],
            missing=missing_ack([scene.participant_id("0002")], 1),
        ),
    )
    assert confirmed.status_code == 200, confirmed.text
    revision_id = confirmed.json()["revisionId"]

    # 服务层：确认后 PATCH 被拒
    patched = harness.patch_import(
        view["importId"], {"expectedRevision": view["revision"] + 1, "rows": [
            {"rowNo": 2, "cells": [{"row": 2, "column": "C", "text": "1"}]}
        ]}
    )
    assert patched.status_code == 409, patched.text
    assert patched.json()["code"] == SCORE_IMPORT_NOT_EDITABLE
    again = harness.confirm_import(
        view["importId"],
        _confirm_body(view, scene, submission_id="another-confirm"),
    )
    assert again.status_code == 409, again.text
    assert again.json()["code"] == SCORE_IMPORT_NOT_EDITABLE

    # DB 触发器兜底：直连 SQL 改分/改修订都被拒
    with pytest.raises(sqlite3.IntegrityError) as score_error:
        harness.raw_execute(
            "UPDATE student_item_scores SET score_units = 1 WHERE score_revision_id = ?",
            (revision_id,),
        )
    assert "SCORE_REVISION_IMMUTABLE" in str(score_error.value)
    with pytest.raises(sqlite3.IntegrityError) as revision_error:
        harness.raw_execute(
            "UPDATE score_revisions SET version = 9 WHERE id = ?", (revision_id,)
        )
    assert "SCORE_REVISION_IMMUTABLE" in str(revision_error.value)
    with pytest.raises(sqlite3.IntegrityError) as delete_error:
        harness.raw_execute(
            "DELETE FROM student_item_scores WHERE score_revision_id = ?", (revision_id,)
        )
    assert "SCORE_REVISION_IMMUTABLE" in str(delete_error.value)


# --------------------------------------------------------------------------- 阻断


def test_ambiguous_row_blocks_confirm_until_patched(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = harness.create_scene(
        tag="amb", students=[("王五", "0001"), ("王五", "0002")]
    )
    path = write_score_xlsx(
        tmp_path / "amb.xlsx", SAMPLE_HEADER, [["", "王五", 2, 3, 5]]
    )
    view = harness.upload_scores(scene.assessment["assessmentId"], path).json()
    assert view["issues"][0]["code"] == SCORE_ROW_DUPLICATE_PARTICIPANT
    blocked = harness.confirm_import(
        view["importId"], _confirm_body(view, scene, missing=missing_ack(
            [row["participantId"] for row in scene.participants], 6
        ))
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == SCORE_ROW_DUPLICATE_PARTICIPANT
    assert _issues(blocked.json())
    assert harness.count("score_revisions") == 0

    # 人工指定后可以确认
    wanted = scene.participant_by_name("王五")[0]["participantId"]
    rows = harness.list_import_rows(view["importId"]).json()
    patched = harness.patch_import(
        view["importId"],
        {
            "expectedRevision": view["revision"],
            "rows": [{"rowNo": rows["items"][0]["rowNo"], "participantId": wanted}],
        },
    )
    assert patched.status_code == 200, patched.text
    updated = patched.json()
    other = scene.participant_by_name("王五")[1]["participantId"]
    ok = harness.confirm_import(
        view["importId"],
        _confirm_body(updated, scene, missing=missing_ack([other], 3)),
    )
    assert ok.status_code == 200, ok.text


def test_attendance_conflict_blocks_confirm(harness: ScoresHarness, tmp_path: Path) -> None:
    """缺考人次却填了数值 → 阻断确认（不自动覆盖、不静默丢弃）。"""
    scene = harness.create_scene(
        tag="conf",
        students=[("甲", "0001"), ("乙", "0002")],
        attendance={"0002": "absent"},
    )
    path = write_score_xlsx(
        tmp_path / "conf.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, 3, 5], ["0002", "乙", 2, 3, 5]],
    )
    view = harness.upload_scores(scene.assessment["assessmentId"], path).json()
    assert view["issues"], "缺考+数值应当作为阻断问题出现在预览"
    assert view["issues"][0]["code"] == SCORE_CELL_INVALID
    blocked = harness.confirm_import(
        view["importId"], _confirm_body(view, scene)
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == SCORE_CELL_INVALID
    assert harness.count("score_revisions") == 0


def test_absent_marker_from_file_is_kept_with_warning(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """文件标记缺考但快照是 present：按文件记 absent，不改施测快照，并给出警告。"""
    scene = harness.create_scene(tag="marker", students=[("甲", "0001"), ("乙", "0002")])
    path = write_score_xlsx(
        tmp_path / "marker.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, 3, 5], ["0002", "乙", "缺考", "缺考", "缺考"]],
    )
    view = harness.upload_scores(scene.assessment["assessmentId"], path).json()
    assert any("缺考" in warning for warning in view["warnings"])
    yi_id = scene.participant_id("0002")
    confirmed = harness.confirm_import(
        view["importId"],
        _confirm_body(
            view,
            scene,
            absences=[absence_ack(scene.klass["id"], [yi_id])],
        ),
    )
    assert confirmed.status_code == 200, confirmed.text
    matrix = harness.score_matrix(confirmed.json()["revisionId"]).json()
    by_name = {row["participant"]["name"]: row for row in matrix["rows"]}
    assert [cell["status"] for cell in by_name["乙"]["cells"]] == ["absent"] * 3
    # 施测快照没有被改写：出勤仍是 present
    assert by_name["乙"]["participant"]["attendance"] == "present"
    detail = harness.client.get(
        f"/api/v1/assessments/{scene.assessment['assessmentId']}"
    ).json()
    snapshot = [p for p in detail["participants"] if p["nameSnapshot"] == "乙"][0]
    assert snapshot["attendance"] == "present"


def test_participant_added_after_preview_requires_refresh(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """新增补考使旧预览失效：确认/PATCH拒绝；显式刷新后人工消歧，新人次落missing。"""
    scene = harness.create_scene(tag="added", students=[("甲", "0001")])
    view = harness.upload_scores(
        scene.assessment["assessmentId"],
        write_score_xlsx(tmp_path / "a.xlsx", SAMPLE_HEADER, [["0001", "甲", 2, 3, 5]]),
    ).json()
    assert view["missingCellCount"] == 0

    added = harness.client.post(
        f"/api/v1/assessments/{scene.assessment['assessmentId']}/participants",
        json={
            "expectedRevision": scene.assessment["revision"],
            "submissionId": "add-attempt",
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

    stale = harness.confirm_import(view["importId"], _confirm_body(view, scene))
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == SCORE_ASSESSMENT_REVISION_CONFLICT

    refreshed = harness.patch_import(
        view["importId"], {"expectedRevision": view["revision"], "rows": []}
    )
    assert refreshed.status_code == 422  # 空补丁不生效：退回并携带有效补丁
    before_import = harness.raw_rows("SELECT * FROM score_imports")
    before_rows = harness.raw_rows("SELECT * FROM score_import_rows")
    stale_patch = harness.patch_import(
        view["importId"],
        {
            "expectedRevision": view["revision"],
            "rows": [{"rowNo": 2, "participantId": scene.participant_id("0001")}],
        },
    )
    assert stale_patch.status_code == 409, stale_patch.text
    assert stale_patch.json()["code"] == SCORE_ASSESSMENT_REVISION_CONFLICT
    assert harness.raw_rows("SELECT * FROM score_imports") == before_import
    assert harness.raw_rows("SELECT * FROM score_import_rows") == before_rows
    assessment = harness.assessment(scene.assessment["assessmentId"])
    refreshed = harness.client.post(f'/api/v1/score-imports/{view["importId"]}/refresh', json={
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": assessment["revision"],
        "baseScoreRevisionId": view["baseScoreRevisionId"],
    })
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["revision"] == view["revision"] + 1
    assert refreshed.json()["previewVersion"] == view["previewVersion"] + 1
    refreshed = harness.patch_import(view["importId"], {
        "expectedRevision": refreshed.json()["revision"],
        "rows": [{"rowNo": 2, "participantId": scene.participant_id("0001")}],
    })
    assert refreshed.status_code == 200, refreshed.text
    updated = refreshed.json()
    assert updated["missingCellCount"] == 3

    assessment = harness.assessment(scene.assessment["assessmentId"])
    ok = harness.confirm_import(
        view["importId"],
        _confirm_body(
            updated,
            scene,
            expected_assessment_revision=assessment["revision"],
            missing=missing_ack([new_participant], 3),
        ),
    )
    assert ok.status_code == 200, ok.text
    matrix = harness.score_matrix(ok.json()["revisionId"]).json()
    assert matrix["total"] == 2
    added_row = next(
        row
        for row in matrix["rows"]
        if row["participant"]["participantId"] == new_participant
    )
    assert [cell["status"] for cell in added_row["cells"]] == ["missing"] * 3
    original_row = next(row for row in matrix["rows"]
                        if row["participant"]["participantId"] == scene.participant_id("0001"))
    assert [cell["scoreUnits"] for cell in original_row["cells"]] == [200, 300, 500]


def test_no_participants_is_incomplete(harness: ScoresHarness, tmp_path: Path) -> None:
    """没有计分叶/没有参测人次时不建立空矩阵（SCORE_MATRIX_INCOMPLETE）。"""
    scene = harness.create_scene(tag="empty", students=[("甲", "0001")])
    view = harness.upload_scores(
        scene.assessment["assessmentId"],
        write_score_xlsx(tmp_path / "e.xlsx", SAMPLE_HEADER, [["0001", "甲", 2, 3, 5]]),
    ).json()
    harness.raw_execute(
        "DELETE FROM assessment_participants WHERE assessment_id = ?",
        (scene.assessment["assessmentId"],),
    )
    blocked = harness.confirm_import(view["importId"], _confirm_body(view, scene))
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == SCORE_MATRIX_INCOMPLETE
    assert harness.count("score_revisions") == 0


# --------------------------------------------------------------------------- 缺列/缺行/免考


def test_unmapped_leaf_and_missing_row_require_exact_acknowledgement(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """缺列（未映射叶）+ 缺行：missing 集合与单元数完全一致才能确认。"""
    scene = harness.create_scene(tag="ql", students=[("甲", "0001"), ("乙", "0002")])
    path = write_score_xlsx(
        tmp_path / "ql.xlsx", ["学号", "姓名", "Q1", "Q2"], [["0001", "甲", 2, 3]]
    )
    view = harness.upload_scores(scene.assessment["assessmentId"], path).json()
    assert view["missingCellCount"] == 4  # 甲 Q3 + 乙 3 格
    jia_id = scene.participant_id("0001")
    yi_id = scene.participant_id("0002")

    blocked = harness.confirm_import(view["importId"], _confirm_body(view, scene))
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == SCORE_ACKNOWLEDGEMENT_MISMATCH
    assert any(
        issue["field"] == "missing" for issue in _issues(blocked.json())
    )

    partial = harness.confirm_import(
        view["importId"],
        _confirm_body(view, scene, missing=missing_ack([jia_id], 1)),
    )
    assert partial.status_code == 422, partial.text
    assert any(
        issue["field"] == "participantIds" for issue in _issues(partial.json())
    )

    ok = harness.confirm_import(
        view["importId"],
        _confirm_body(view, scene, missing=missing_ack([jia_id, yi_id], 4)),
    )
    assert ok.status_code == 200, ok.text
    matrix = harness.score_matrix(ok.json()["revisionId"]).json()
    assert matrix["missingCellCount"] == 4
    assert sorted(matrix["missingParticipantIds"]) == sorted([jia_id, yi_id])
    by_name = {row["participant"]["name"]: row for row in matrix["rows"]}
    assert [cell["status"] for cell in by_name["甲"]["cells"]] == [
        "recorded",
        "recorded",
        "missing",
    ]
    assert by_name["甲"]["participant"]["totalUnits"] is None
    assert [cell["status"] for cell in by_name["乙"]["cells"]] == ["missing"] * 3


def test_exempt_participant_is_explicit_state_without_totals(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """免考：显式 exempt（不是 missing/absent），不需要缺考承认，不展示总分。"""
    scene = harness.create_scene(
        tag="ex",
        students=[("甲", "0001"), ("乙", "0002")],
        attendance={"0002": "exempt"},
    )
    view = harness.upload_scores(
        scene.assessment["assessmentId"],
        write_score_xlsx(tmp_path / "ex.xlsx", SAMPLE_HEADER, [["0001", "甲", 2, 3, 5]]),
    ).json()
    assert view["missingCellCount"] == 0
    ok = harness.confirm_import(view["importId"], _confirm_body(view, scene))
    assert ok.status_code == 200, ok.text
    matrix = harness.score_matrix(ok.json()["revisionId"]).json()
    by_name = {row["participant"]["name"]: row for row in matrix["rows"]}
    assert [cell["status"] for cell in by_name["乙"]["cells"]] == ["exempt"] * 3
    assert by_name["乙"]["participant"]["attendance"] == "exempt"
    assert by_name["乙"]["participant"]["totalUnits"] is None
    assert matrix["missingCellCount"] == 0
    assert matrix["absentClassIds"] == []
