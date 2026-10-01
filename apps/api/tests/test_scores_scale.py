"""T60 规模测试：≥100 个计分叶 × 多人数 的导入 + 确认 + 分页读取。

对应任务卡测试清单最后一条：一次全量通过（不追求性能，追求正确 + 不截断）。

两个层次：

- ``test_hundred_leaves_scale_core``：100 叶 × 20 人次。102 列（远超 B1 字符串读表的
  64 列上限）走完整链：自动映射 → 预览 → 确认 → 全矩阵（2,000 格）→ 分页读取，
  默认测试套件里运行；
- ``test_scale_baseline_two_hundred_participants``：任务卡基线 100 叶 × 200 人次
  （20,000 格）。默认**不跑**（``ZQKY_RUN_SCALE_BASELINE=1`` 开启），原因是冻结的
  ``app/services/tabular.py::read_score_sheet``（CTRL 文件，本任务不可写）在 read-only
  工作表上用 ``ws.cell(r, c)`` 逐格取值，代价约 O(物理行数² × 列数)：实测 51 行 × 42 列
  37.6 s、101 行 × 42 列 141.3 s（openpyxl 3.1.5），推算 201 行 × 102 列约 20+ 分钟。
  该测试仍随交付提供并已实际跑过一次（见结果卡证据）；reader 修好后去掉守卫即可纳入常规套件。

原卷（100 叶）用真库种子（走确认触发器），学生/施测/参测人次走真实 API，
成绩表程序化生成 XLSX（102 列）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests.scores_support import ScoresHarness, write_score_xlsx

LEAF_COUNT = 100
LEAF_MAX_UNITS = 100  # 1 分
LEAVES: tuple[tuple[str, int], ...] = tuple(
    (f"Q{index}", LEAF_MAX_UNITS) for index in range(1, LEAF_COUNT + 1)
)
BASELINE_PARTICIPANTS = 200
BASELINE_ENABLED = os.environ.get("ZQKY_RUN_SCALE_BASELINE", "") == "1"


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


@pytest.mark.skipif(
    not BASELINE_ENABLED,
    reason=(
        "任务卡基线 100 叶 × 200 人次默认不跑：冻结的 read_score_sheet 在 read-only 工作表上"
        "逐格 cell() 取值，代价 O(行数²×列数)，201×102 物理矩形实测推算 20+ 分钟；"
        "用 ZQKY_RUN_SCALE_BASELINE=1 显式开启。"
    ),
)
def test_scale_baseline_two_hundred_participants(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """任务卡基线：100 叶 × 200 人次（20,000 格）一次全量通过。"""
    _run_scale(harness, tmp_path, participant_count=BASELINE_PARTICIPANTS, tag="scale-base")
