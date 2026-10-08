"""放弃未确认成绩导入批次（误上传清理）：与名单批次 discard 同语义。

覆盖：正常放弃（state=cancelled、revision+1、批次/资产/预览行保留、零业务写入）、
已确认批次 409 ``SCORE_IMPORT_CONFIRMED``、重复放弃幂等（不再递增 revision）、
``expectedRevision`` 不符 409 + ``details.currentRevision``、放弃后不可再 patch、
放弃后确认被拒，以及 HTTP 路由（``POST /api/v1/score-imports/{id}/discard``）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.contracts.scores import (
    SCORE_IMPORT_CONFIRMED,
    SCORE_IMPORT_NOT_EDITABLE,
    SCORE_IMPORT_REVISION_CONFLICT,
    ScoreImportConfirmRequest,
    ScoreImportDiscardRequest,
    ScoreImportPatchRequest,
)
from app.core.exceptions import AppError
from tests.scores_support import SAMPLE_HEADER, ScoresHarness, write_score_xlsx


@pytest.fixture()
def harness(tmp_path: Path):
    with ScoresHarness(tmp_path) as running:
        yield running


def _scene(harness: ScoresHarness, *, tag: str = "d1"):
    return harness.create_scene(
        tag=tag, students=[("甲", "0001"), ("乙", "0002")]
    )


def _xlsx(tmp_path: Path, *, name: str = "scores.xlsx") -> Path:
    return write_score_xlsx(
        tmp_path / name,
        SAMPLE_HEADER,
        [["0001", "甲", 2, 2, 5], ["0002", "乙", 2, 3, None]],
    )


def _upload(harness: ScoresHarness, tmp_path: Path, *, tag: str = "d1") -> dict[str, Any]:
    scene = _scene(harness, tag=tag)
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _xlsx(tmp_path, name=f"scores-{tag}.xlsx")
    ).json()
    assert view["state"] == "reviewing"
    return view


# --------------------------------------------------------------------------- 服务层


def test_discard_keeps_records_and_zero_writes(harness: ScoresHarness, tmp_path: Path) -> None:
    """放弃只改状态：批次记录、原始文件资产、预览行全部保留；无任何成绩矩阵写入。"""
    view = _upload(harness, tmp_path)

    discarded = harness.service().discard_score_import(
        view["importId"], ScoreImportDiscardRequest(expectedRevision=view["revision"])
    )
    assert discarded.state == "cancelled"
    assert discarded.revision == view["revision"] + 1
    assert discarded.preview_version == view["previewVersion"]

    # 审计保留：批次、预览行、文件资产登记都不删除
    assert harness.count("score_imports") == 1
    assert harness.count("score_import_rows") == 2
    assert harness.count("file_assets", "kind = 'score_sheet'") == 1
    # 没有确认动作：成绩修订与矩阵零写入
    assert harness.count("score_revisions") == 0
    assert harness.count("student_item_scores") == 0

    # 读回仍是完整视图（cancelled、行数不变）
    detail = harness.get_import(view["importId"]).json()
    assert detail["state"] == "cancelled"
    assert detail["revision"] == view["revision"] + 1
    assert detail["rowCount"] == 2


def test_discard_is_idempotent(harness: ScoresHarness, tmp_path: Path) -> None:
    view = _upload(harness, tmp_path, tag="d2")
    first = harness.service().discard_score_import(
        view["importId"], ScoreImportDiscardRequest(expectedRevision=view["revision"])
    )
    again = harness.service().discard_score_import(
        view["importId"], ScoreImportDiscardRequest(expectedRevision=first.revision)
    )
    assert again.state == "cancelled"
    assert again.revision == first.revision  # 幂等：不再递增


def test_discard_revision_conflict(harness: ScoresHarness, tmp_path: Path) -> None:
    view = _upload(harness, tmp_path, tag="d3")
    with pytest.raises(AppError) as err:
        harness.service().discard_score_import(
            view["importId"],
            ScoreImportDiscardRequest(expectedRevision=view["revision"] + 5),
        )
    assert err.value.code == SCORE_IMPORT_REVISION_CONFLICT
    assert err.value.status_code == 409
    assert err.value.details == {"currentRevision": view["revision"]}
    # 冲突不写入
    assert harness.service().get_score_import(view["importId"]).state == "reviewing"


def test_discard_confirmed_import_is_409(harness: ScoresHarness, tmp_path: Path) -> None:
    """已确认批次不可放弃：历史与已确认成绩版本不动。"""
    scene = harness.create_scene(tag="d4", students=[("甲", "0001")])
    view = harness.upload_scores(
        scene.assessment["assessmentId"],
        write_score_xlsx(tmp_path / "d4.xlsx", SAMPLE_HEADER, [["0001", "甲", 2, 2, 5]]),
    ).json()
    body = {
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": view["baseScoreRevisionId"],
        "previewVersion": view["previewVersion"],
        "submissionId": "discard-confirmed-1",
    }
    response = harness.confirm_import(view["importId"], body)
    assert response.status_code == 200, response.text
    confirmed = harness.service().get_score_import(view["importId"])
    assert confirmed.state == "confirmed"

    with pytest.raises(AppError) as err:
        harness.service().discard_score_import(
            view["importId"],
            ScoreImportDiscardRequest(expectedRevision=confirmed.revision),
        )
    assert err.value.code == SCORE_IMPORT_CONFIRMED
    assert err.value.status_code == 409
    # 确认成果不受影响
    assert harness.count("score_revisions") == 1
    assert harness.service().get_score_import(view["importId"]).state == "confirmed"


def test_discarded_import_is_not_editable(harness: ScoresHarness, tmp_path: Path) -> None:
    """放弃后批次不在可编辑集合：patch/confirm/refresh 一律 409 ``SCORE_IMPORT_NOT_EDITABLE``。"""
    view = _upload(harness, tmp_path, tag="d5")
    discarded = harness.service().discard_score_import(
        view["importId"], ScoreImportDiscardRequest(expectedRevision=view["revision"])
    )
    assert discarded.state == "cancelled"
    revision = discarded.revision

    with pytest.raises(AppError) as err:
        harness.service().patch_score_import(
            view["importId"],
            ScoreImportPatchRequest(
                expectedRevision=revision,
                rows=[{"rowNo": 1, "participantId": "p-1"}],
            ),
        )
    assert err.value.code == SCORE_IMPORT_NOT_EDITABLE

    # 确认（不带 submissionId 幂等）也被既有可编辑守卫拒绝
    with pytest.raises(AppError) as err:
        harness.service().confirm_score_import(
            view["importId"],
            ScoreImportConfirmRequest(
                expectedImportRevision=revision,
                expectedAssessmentRevision=0,
                baseScoreRevisionId=None,
                previewVersion=0,
                submissionId="discard-after-1",
            ),
        )
    assert err.value.code == SCORE_IMPORT_NOT_EDITABLE


# --------------------------------------------------------------------------- HTTP 路由


def test_discard_route(harness: ScoresHarness, tmp_path: Path) -> None:
    view = _upload(harness, tmp_path, tag="d6")
    response = harness.client.post(
        f"/api/v1/score-imports/{view['importId']}/discard",
        json={"expectedRevision": view["revision"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "cancelled"
    assert body["revision"] == view["revision"] + 1

    # confirmed 路径复用服务层守卫（见 test_discard_confirmed_import_is_409），路由层不重复
    stale = harness.client.post(
        f"/api/v1/score-imports/{view['importId']}/discard",
        json={"expectedRevision": 0},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == SCORE_IMPORT_REVISION_CONFLICT
    assert stale.json()["details"]["currentRevision"] == view["revision"] + 1
