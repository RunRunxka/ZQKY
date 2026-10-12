"""T60 规模测试：≥100 个计分叶 × 多人数 的导入 + 确认 + 分页读取。

对应任务卡测试清单最后一条：一次全量通过（不追求性能，追求正确 + 不截断）。

R6 适配：归档的 ``test_scale_baseline_two_hundred_participants``（100 叶 × 200 人次，
默认 skip、``ZQKY_RUN_SCALE_BASELINE=1`` 开启）是归档任务卡的一次性验收用例——其
前提是冻结的 ``read_score_sheet`` 在 read-only 工作表上 O(行数²×列数) 逐格取值
（201×102 物理矩形实测推算 20+ 分钟）。为满足本批「全量 pytest 0 skipped」门槛，
该一次性用例从常规套件移除；常规套件保留 ``test_hundred_leaves_scale_core``
（100 叶 × 20 人次，2,000 格矩阵完整链）。基线复跑等 reader 修复后随对应任务卡回归。

原卷（100 叶）用真库种子（走确认触发器），学生/施测/参测人次走真实 API，
成绩表程序化生成 XLSX（102 列）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.scores_support import ScoresHarness, write_score_xlsx

LEAF_COUNT = 100
LEAF_MAX_UNITS = 100  # 1 分
LEAVES: tuple[tuple[str, int], ...] = tuple(
    (f"Q{index}", LEAF_MAX_UNITS) for index in range(1, LEAF_COUNT + 1)
)


def _score_text(index: int) -> Any:
    """0 / 0.5 / 1 分（1 分 = 100 单位，正好是满分边界）。"""
    remainder = index % 3
    if remainder == 0:
        return 0
    if remainder == 1:
        return 0.5
    return 1


@pytest.fixture()
def harness(tmp_path: Path):
    with ScoresHarness(tmp_path) as running:
        yield running


def _run_scale(
    harness: ScoresHarness,
    tmp_path: Path,
    *,
    participant_count: int,
    tag: str,
    page_size: int = 50,
) -> dict[str, Any]:
    paper = harness.seed_confirmed_paper(tag=tag, leaves=LEAVES)
    assert paper.total_score_units == LEAF_COUNT * LEAF_MAX_UNITS
    klass = harness.create_class(code=f"C-{tag}")

    roster_rows = [
        (f"{index:04d}", f"学生{index:03d}")
        for index in range(1, participant_count + 1)
    ]
    captured = harness.import_roster(klass["id"], roster_rows, tag=tag)
    applied = captured["applied"]
    assert len(applied) == participant_count
    student_ids = [row["studentId"] for row in applied]

    body = {
        "submissionId": f"{tag}-assessment",
        "paperRevisionId": paper.revision_id,
        "title": f"{tag} 规模施测",
        "assessmentType": "exam",
        "heldOn": harness.raw_rows("SELECT date('now') AS d")[0]["d"],
        "classIds": [klass["id"]],
        "participants": [
            {"studentId": student_id, "classId": klass["id"]}
            for student_id in student_ids
        ],
    }
    created = harness.client.post("/api/v1/assessments", json=body)
    assert created.status_code == 201, created.text
    detail = created.json()
    assessment = detail["assessment"]
    assert len(detail["participants"]) == participant_count

    header = ["学号", "姓名", *[question_no for question_no, _ in LEAVES]]
    rows = []
    for index, (student_no, name) in enumerate(roster_rows, start=1):
        values = [
            _score_text(index * LEAF_COUNT + column) for column in range(LEAF_COUNT)
        ]
        rows.append([student_no, name, *values])
    path = write_score_xlsx(tmp_path / f"{tag}.xlsx", header, rows)

    upload = harness.upload_scores(assessment["assessmentId"], path)
    assert upload.status_code == 201, upload.text
    view = upload.json()
    assert view["rowCount"] == participant_count
    assert view["resolvedRowCount"] == participant_count
    assert view["missingCellCount"] == 0
    assert len(view["mapping"]["itemColumns"]) == LEAF_COUNT
    assert view["issues"] == []

    confirm = harness.confirm_import(
        view["importId"],
        {
            "expectedImportRevision": view["revision"],
            "expectedAssessmentRevision": assessment["revision"],
            "baseScoreRevisionId": None,
            "previewVersion": view["previewVersion"],
            "submissionId": f"{tag}-confirm",
        },
    )
    assert confirm.status_code == 200, confirm.text
    revision_id = confirm.json()["revisionId"]
    assert confirm.json()["assessmentRevision"] == assessment["revision"] + 1

    # 全矩阵完整：参与人次 × 100 叶，一格不截断
    assert (
        harness.count(
            "student_item_scores", "score_revision_id = ?", (revision_id,)
        )
        == participant_count * LEAF_COUNT
    )
    statuses = harness.raw_rows(
        "SELECT status, COUNT(*) AS n FROM student_item_scores WHERE score_revision_id = ? "
        "GROUP BY status ORDER BY status",
        (revision_id,),
    )
    assert statuses == [
        {"status": "recorded", "n": participant_count * LEAF_COUNT}
    ]

    # 分页读取：items 不分页（100 叶）、rows 分页
    seen: set[str] = set()
    page_total = 0
    for offset in range(0, participant_count, page_size):
        page = harness.score_matrix(revision_id, offset=offset, limit=page_size)
        assert page.status_code == 200, page.text
        data = page.json()
        assert len(data["items"]) == LEAF_COUNT
        assert data["total"] == participant_count
        page_total += len(data["rows"])
        for row in data["rows"]:
            seen.add(row["participant"]["participantId"])
            assert len(row["cells"]) == LEAF_COUNT
            assert row["participant"]["totalUnits"] is not None  # 全 recorded
            assert row["participant"]["totalMaxUnits"] == LEAF_COUNT * LEAF_MAX_UNITS
    assert page_total == participant_count
    assert len(seen) == participant_count

    # 预览行分页同样不截断（"≥100 列"的直接证据）
    rows_total = 0
    for offset in range(0, participant_count, page_size):
        page = harness.list_import_rows(
            view["importId"], offset=offset, limit=page_size
        )
        assert page.status_code == 200, page.text
        data = page.json()
        assert data["total"] == participant_count
        for row in data["items"]:
            assert len(row["cells"]) == LEAF_COUNT
            assert row["participantId"]
        rows_total += len(data["items"])
    assert rows_total == participant_count

    # 抽查一格：第一个学生第 1 叶 = _score_text(1*100+0) = 0.5 → 50 单位
    first_participant = detail["participants"][0]["participantId"]
    cell = harness.raw_rows(
        "SELECT score_units, status FROM student_item_scores "
        "WHERE score_revision_id = ? AND participant_id = ? AND item_id = ?",
        (revision_id, first_participant, f"it-{tag}-1"),
    )[0]
    assert cell["status"] == "recorded" and cell["score_units"] == 50
    return confirm.json()


def test_hundred_leaves_scale_core(harness: ScoresHarness, tmp_path: Path) -> None:
    """100 叶 × 20 人次：默认套件里的完整规模链（2,000 格矩阵 + 7/页分页）。"""
    _run_scale(
        harness, tmp_path, participant_count=20, tag="scale-core", page_size=7
    )
