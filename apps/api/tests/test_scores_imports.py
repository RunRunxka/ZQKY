"""T60 成绩导入 / 自动映射 / 四态解析 / 行定位 / 校对 PATCH 测试。

对应任务卡 §3「T60」业务点 1–4 与测试清单：授权样例矩阵（Q1=2、Q2=3、Q3=5；
A=(2,2,5)、B=(2,3,空白)、C=缺考、D=(0,3,5)）、前导零学号、同名歧义、
越界/非数值文本/公式缓存、缺行缺列与承认集合口径、PATCH 的乐观锁与预览版本。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.contracts.scores import (
    SCORE_CELL_INVALID,
    SCORE_CELL_OVER_MAX,
    SCORE_IMPORT_NOT_EDITABLE,
    SCORE_IMPORT_REVISION_CONFLICT,
    SCORE_ITEM_UNKNOWN,
    SCORE_MAPPING_INVALID,
    SCORE_PARTICIPANT_UNKNOWN,
    SCORE_ROW_DUPLICATE_PARTICIPANT,
    SCORE_ROW_UNRESOLVED,
)
from tests.scores_support import (
    SAMPLE_HEADER,
    ScoresHarness,
    cells_by_column,
    inject_cached_values,
    row_for,
    write_score_xlsx,
)


@pytest.fixture()
def harness(tmp_path: Path):
    with ScoresHarness(tmp_path) as running:
        yield running


def _sample_scene(harness: ScoresHarness, *, tag: str = "s1"):
    """甲(0001)/乙(0002)/丙(0003 缺考)/丁(0004)。"""
    return harness.create_scene(
        tag=tag,
        students=[("甲", "0001"), ("乙", "0002"), ("丙", "0003"), ("丁", "0004")],
        attendance={"0003": "absent"},
    )


def _sample_xlsx(tmp_path: Path, *, name: str = "scores.xlsx") -> Path:
    return write_score_xlsx(
        tmp_path / name,
        SAMPLE_HEADER,
        [
            ["0001", "甲", 2, 2, 5],
            ["0002", "乙", 2, 3, None],
            ["0004", "丁", 0, 3, 5],
        ],
    )


def _issue_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        issue
        for issue in (payload.get("details", {}).get("issues") or [])
    ]


# --------------------------------------------------------------------------- 上传预览


def test_upload_auto_maps_and_builds_preview(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = _sample_scene(harness)
    response = harness.upload_scores(scene.assessment["assessmentId"], _sample_xlsx(tmp_path))
    assert response.status_code == 201, response.text
    view = response.json()
    assert view["state"] == "reviewing"
    assert view["revision"] == 0 and view["previewVersion"] == 0
    assert view["assessmentId"] == scene.assessment["assessmentId"]
    assert view["fileAsset"]["kind"] == "score_sheet"
    assert len(view["fileAsset"]["sha256"]) == 64
    mapping = view["mapping"]
    assert mapping["studentNoColumn"] == "A"
    assert mapping["nameColumn"] == "B"
    entries = mapping["itemColumns"]
    assert [entry["column"] for entry in entries] == ["C", "D", "E"]
    assert len({entry["itemId"] for entry in entries}) == 3
    assert all(entry["itemId"] for entry in entries)
    assert view["rowCount"] == 3
    assert view["resolvedRowCount"] == 3
    # 乙的 Q3 空白 = 1 个 missing；丙缺考不是 missing；甲/丁全 recorded
    assert view["missingCellCount"] == 1
    assert view["baseScoreRevisionId"] is None
    assert view["issues"] == []

    rows = harness.list_import_rows(view["importId"]).json()
    assert rows["total"] == 3
    jia = row_for(rows, "甲")
    assert jia["participantId"] == scene.participant_id("0001")
    assert cells_by_column(jia) == {"C": "2", "D": "2", "E": "5"}
    yi = row_for(rows, "乙")
    assert cells_by_column(yi)["E"] == ""
    assert yi["issues"] == []


def _leaf_items(scene) -> list[dict[str, Any]]:
    """用真读表接口拿不到 itemId；这里从服务侧读取已确认卷的计分叶（测试断言用）。"""
    service = scene  # 占位，真实调用见下方 helper
    raise NotImplementedError


def test_leading_zero_student_no_and_blank_cells(harness: ScoresHarness, tmp_path: Path) -> None:
    """前导零学号按文本匹配；空单元格是 missing 不是 0。"""
    scene = harness.create_scene(tag="lead", students=[("甲", "0012"), ("乙", "0007")])
    path = write_score_xlsx(
        tmp_path / "lead.xlsx",
        ["学号", "姓名", "Q1", "Q2", "Q3"],
        [["0012", "甲", 2, None, 5], ["0007", "乙", 0, 0, 0]],
    )
    response = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert response.status_code == 201, response.text
    view = response.json()
    assert view["resolvedRowCount"] == 2
    assert view["missingCellCount"] == 1
    rows = harness.list_import_rows(view["importId"]).json()
    jia = row_for(rows, "甲")
    assert jia["participantId"] == scene.participant_id("0012")
    assert cells_by_column(jia) == {"C": "2", "D": "", "E": "5"}


def test_over_max_cell_is_rejected_with_physical_coordinates(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = _sample_scene(harness)
    path = write_score_xlsx(
        tmp_path / "over.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, 2, 6]],
    )
    response = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == SCORE_CELL_OVER_MAX
    issues = _issue_rows(body)
    assert issues and issues[0]["row"] == 2 and issues[0]["column"] == "E"
    assert harness.count("score_imports") == 0


def test_non_numeric_cell_is_rejected(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = _sample_scene(harness)
    path = write_score_xlsx(
        tmp_path / "text.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, "优秀", 5]],
    )
    response = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == SCORE_CELL_INVALID
    assert _issue_rows(body)[0]["column"] == "D"


def test_formula_uses_cached_view_and_missing_cache_is_blocked(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = harness.create_scene(tag="formula", students=[("甲", "0001")])
    cached_path = write_score_xlsx(
        tmp_path / "formula.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, 2, "=C2+D2"]],
    )
    inject_cached_values(cached_path, {"E2": "4"})
    response = harness.upload_scores(scene.assessment["assessmentId"], cached_path)
    assert response.status_code == 201, response.text
    view = response.json()
    # 缓存值 4 参与解析（满分 5）：E 列是 recorded 而不是公式文本
    rows = harness.list_import_rows(view["importId"]).json()
    jia = row_for(rows, "甲")
    cell_e = next(cell for cell in jia["cells"] if cell["column"] == "E")
    assert cell_e["isFormula"] is True
    assert cell_e["text"] == "=C2+D2"
    assert cell_e["cachedText"] == "4"
    assert view["missingCellCount"] == 0

    no_cache = write_score_xlsx(
        tmp_path / "formula-nocache.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, 2, "=C2+D2"]],
    )
    blocked = harness.upload_scores(scene.assessment["assessmentId"], no_cache)
    assert blocked.status_code == 422, blocked.text
    body = blocked.json()
    assert body["code"] == SCORE_CELL_INVALID
    assert "缓存" in body["message"] or "缓存" in _issue_rows(body)[0]["message"]


def test_unmapped_leaf_and_absent_row_are_missing_not_zero(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """只映射 Q1/Q2：Q3 未映射 → missing；缺行人次全部 missing；绝不补 0。"""
    scene = harness.create_scene(tag="miss", students=[("甲", "0001"), ("乙", "0002")])
    path = write_score_xlsx(
        tmp_path / "partial.xlsx",
        ["学号", "姓名", "Q1", "Q2"],
        [["0001", "甲", 2, 3]],
    )
    response = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert response.status_code == 201, response.text
    view = response.json()
    assert len(view["mapping"]["itemColumns"]) == 2
    # 甲：Q3 未映射 missing（1）；乙：缺行 3 个 missing
    assert view["missingCellCount"] == 4
    assert any("missing" in warning for warning in view["warnings"])

    rows = harness.list_import_rows(view["importId"]).json()
    jia = row_for(rows, "甲")
    assert [cell["column"] for cell in jia["cells"]] == ["C", "D"]
    # 确认时未映射叶必须被承认覆盖（由确认测试断言 422/成功）


def test_ambiguous_same_name_requires_manual_participant(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """同名两生：学号为空的行按姓名匹配到 2 条 → 阻断，要求人工指定。"""
    scene = harness.create_scene(
        tag="dup", students=[("王五", "0001"), ("王五", "0002"), ("甲", "0003")]
    )
    path = write_score_xlsx(
        tmp_path / "dup.xlsx",
        SAMPLE_HEADER,
        [["", "王五", 2, 3, 5], ["0003", "甲", 2, 3, 5]],
    )
    response = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert response.status_code == 201, response.text
    view = response.json()
    assert view["rowCount"] == 2 and view["resolvedRowCount"] == 1
    codes = {issue["code"] for issue in view["issues"]}
    assert SCORE_ROW_DUPLICATE_PARTICIPANT in codes

    rows = harness.list_import_rows(view["importId"]).json()
    ambiguous = next(row for row in rows["items"] if row["participantId"] is None)
    assert ambiguous["issues"][0]["code"] == SCORE_ROW_DUPLICATE_PARTICIPANT
    assert len(ambiguous["candidates"]) == 2
    assert "王五" in ambiguous["candidates"][0]

    # 教师指定 participantId 后消歧：PATCH 生效、revision/preview 各 +1
    wanted = scene.participant_by_name("王五")[0]["participantId"]
    patched = harness.patch_import(
        view["importId"],
        {
            "expectedRevision": view["revision"],
            "rows": [{"rowNo": rows["items"][0]["rowNo"], "participantId": wanted}],
        },
    )
    assert patched.status_code == 200, patched.text
    updated = patched.json()
    assert updated["revision"] == view["revision"] + 1
    assert updated["previewVersion"] == view["previewVersion"] + 1
    assert updated["resolvedRowCount"] == 2
    assert updated["issues"] == []


def test_unknown_student_row_blocks_and_candidates_help(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = harness.create_scene(tag="unknown", students=[("甲", "0012")])
    path = write_score_xlsx(
        tmp_path / "unknown.xlsx",
        SAMPLE_HEADER,
        [["12", "甲", 2, 3, 5]],
    )
    response = harness.upload_scores(scene.assessment["assessmentId"], path)
    assert response.status_code == 201, response.text
    view = response.json()
    assert view["resolvedRowCount"] == 0
    assert view["issues"][0]["code"] == SCORE_ROW_UNRESOLVED
    rows = harness.list_import_rows(view["importId"]).json()
    # 数字学号丢失前导零：候选里给出 0012 的人次，仍要求人工指定
    assert any("0012" in candidate for candidate in rows["items"][0]["candidates"])


def test_patch_mapping_validation_and_revision_cas(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = _sample_scene(harness)
    response = harness.upload_scores(scene.assessment["assessmentId"], _sample_xlsx(tmp_path))
    view = response.json()
    import_id = view["importId"]
    leaf_ids = [entry["itemId"] for entry in view["mapping"]["itemColumns"]]

    # 未知题目 id → 422 SCORE_ITEM_UNKNOWN / SCORE_MAPPING_INVALID
    bad = harness.patch_import(
        import_id,
        {
            "expectedRevision": view["revision"],
            "mapping": {
                "workSheet": view["mapping"]["workSheet"],
                "headerRow": view["mapping"]["headerRow"],
                "studentNoColumn": "A",
                "itemColumns": [{"itemId": "no-such-item", "column": "C"}],
            },
        },
    )
    assert bad.status_code == 422, bad.text
    assert bad.json()["code"] == SCORE_MAPPING_INVALID
    assert any(
        issue["code"] == SCORE_ITEM_UNKNOWN for issue in _issue_rows(bad.json())
    )

    # 重复列 → 422 SCORE_MAPPING_INVALID
    duplicated = harness.patch_import(
        import_id,
        {
            "expectedRevision": view["revision"],
            "mapping": {
                "workSheet": view["mapping"]["workSheet"],
                "headerRow": view["mapping"]["headerRow"],
                "studentNoColumn": "A",
                "itemColumns": [
                    {"itemId": leaf_ids[0], "column": "C"},
                    {"itemId": leaf_ids[1], "column": "C"},
                ],
            },
        },
    )
    assert duplicated.status_code == 422
    assert duplicated.json()["code"] == SCORE_MAPPING_INVALID

    # 正确补映射 Q3 → E；revision/preview 前移，diff 消失
    ok = harness.patch_import(
        import_id,
        {
            "expectedRevision": view["revision"],
            "mapping": {
                "workSheet": view["mapping"]["workSheet"],
                "headerRow": view["mapping"]["headerRow"],
                "studentNoColumn": "A",
                "nameColumn": "B",
                "itemColumns": [
                    {"itemId": leaf_ids[0], "column": "C"},
                    {"itemId": leaf_ids[1], "column": "D"},
                    {"itemId": leaf_ids[2], "column": "E"},
                ],
            },
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["revision"] == view["revision"] + 1
    assert ok.json()["previewVersion"] == view["previewVersion"] + 1

    # 过期 revision → 409 + currentRevision（合法的补丁体，先失败在 CAS）
    accepted_mapping = {
        "workSheet": view["mapping"]["workSheet"],
        "headerRow": view["mapping"]["headerRow"],
        "studentNoColumn": "A",
        "nameColumn": "B",
        "itemColumns": [
            {"itemId": leaf_ids[0], "column": "C"},
            {"itemId": leaf_ids[1], "column": "D"},
            {"itemId": leaf_ids[2], "column": "E"},
        ],
    }
    stale = harness.patch_import(
        import_id, {"expectedRevision": view["revision"], "mapping": accepted_mapping}
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == SCORE_IMPORT_REVISION_CONFLICT
    assert stale.json()["details"]["currentRevision"] == view["revision"] + 1


def test_patch_cell_correction_keeps_original_and_recomputes(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """单元格校正按原表坐标；预览用校正值，原件两视图保留在库内。"""
    scene = _sample_scene(harness)
    out_of_range = write_score_xlsx(
        tmp_path / "over2.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, 2, 6]],  # 越界 → 上传就该被拒
    )
    rejected = harness.upload_scores(scene.assessment["assessmentId"], out_of_range)
    assert rejected.status_code == 422

    view = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path)
    ).json()
    assert view["missingCellCount"] == 1
    rows = harness.list_import_rows(view["importId"]).json()
    yi = row_for(rows, "乙")
    row_no = yi["rowNo"]
    assert cells_by_column(yi)["E"] == ""

    patched = harness.patch_import(
        view["importId"],
        {
            "expectedRevision": view["revision"],
            "rows": [{"rowNo": row_no, "cells": [{"row": row_no, "column": "E", "text": "4"}]}],
        },
    )
    assert patched.status_code == 200, patched.text
    updated = patched.json()
    assert updated["missingCellCount"] == 0
    rows_after = harness.list_import_rows(view["importId"]).json()
    corrected = row_for(rows_after, "乙")
    cell_e = next(cell for cell in corrected["cells"] if cell["column"] == "E")
    assert cell_e["text"] == "4"
    # 原件仍在库内（raw_cells_json 保留 text 与 correctedText）
    raw = harness.raw_rows(
        "SELECT raw_cells_json FROM score_import_rows WHERE import_id = ? AND row_no = ?",
        (view["importId"], row_no),
    )[0]["raw_cells_json"]
    assert '"correctedText":"4"' in raw


def test_patch_unknown_participant_and_out_of_range_column(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    scene = _sample_scene(harness)
    view = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path)
    ).json()
    rows = harness.list_import_rows(view["importId"]).json()
    row_no = rows["items"][0]["rowNo"]

    bad_participant = harness.patch_import(
        view["importId"],
        {
            "expectedRevision": view["revision"],
            "rows": [{"rowNo": row_no, "participantId": "no-such-participant"}],
        },
    )
    assert bad_participant.status_code == 422
    assert bad_participant.json()["code"] == SCORE_PARTICIPANT_UNKNOWN

    bad_column = harness.patch_import(
        view["importId"],
        {
            "expectedRevision": view["revision"],
            "rows": [{"rowNo": row_no, "cells": [{"row": row_no, "column": "ZZ", "text": "1"}]}],
        },
    )
    assert bad_column.status_code == 422
    assert bad_column.json()["code"] == SCORE_MAPPING_INVALID


def test_multi_sheet_selection_and_switch(harness: ScoresHarness, tmp_path: Path) -> None:
    """多工作表：默认第一个并给警告；PATCH 指定另一个工作表时按原件重建行。"""
    scene = _sample_scene(harness)
    path = write_score_xlsx(
        tmp_path / "multi.xlsx",
        SAMPLE_HEADER,
        [["0001", "甲", 2, 2, 5]],
        sheet_name="第一版",
        extra_sheets={
            "更正版": [
                list(SAMPLE_HEADER),
                ["0001", "甲", 1, 3, 5],
                ["0002", "乙", 2, 3, 5],
            ]
        },
    )
    view = harness.upload_scores(scene.assessment["assessmentId"], path).json()
    assert view["mapping"]["workSheet"] == "第一版"
    assert any("工作表" in warning for warning in view["warnings"])
    assert view["rowCount"] == 1

    switched = harness.patch_import(
        view["importId"],
        {
            "expectedRevision": view["revision"],
            "mapping": {
                "workSheet": "更正版",
                "headerRow": 1,
                "studentNoColumn": "A",
                "nameColumn": "B",
                "itemColumns": view["mapping"]["itemColumns"],
            },
        },
    )
    assert switched.status_code == 200, switched.text
    updated = switched.json()
    assert updated["rowCount"] == 2
    assert updated["resolvedRowCount"] == 2
    rows = harness.list_import_rows(view["importId"]).json()
    assert row_for(rows, "甲")["participantId"] == scene.participant_id("0001")


def test_unresolvable_headers_require_manual_mapping(
    harness: ScoresHarness, tmp_path: Path
) -> None:
    """表头认不出来时不猜：mapping 为空 + 警告；确认被拒。"""
    scene = _sample_scene(harness)
    path = write_score_xlsx(
        tmp_path / "opaque.xlsx",
        ["列1", "列2", "列3", "列4", "列5"],
        [["0001", "甲", 2, 2, 5]],
    )
    view = harness.upload_scores(scene.assessment["assessmentId"], path).json()
    assert view["mapping"] is None
    assert view["issues"] == []
    assert any("映射" in warning for warning in view["warnings"])
    # 确认必须报 SCORE_MAPPING_INVALID（422），不会用空映射写矩阵
    confirm = harness.confirm_import(
        view["importId"],
        {
            "expectedImportRevision": view["revision"],
            "expectedAssessmentRevision": scene.assessment["revision"],
            "baseScoreRevisionId": None,
            "previewVersion": view["previewVersion"],
            "submissionId": "no-mapping",
        },
    )
    assert confirm.status_code == 422, confirm.text
    assert confirm.json()["code"] == SCORE_MAPPING_INVALID


def test_import_list_filter_and_page_bounds(harness: ScoresHarness, tmp_path: Path) -> None:
    scene = _sample_scene(harness)
    first = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path, name="a.xlsx")
    ).json()
    second = harness.upload_scores(
        scene.assessment["assessmentId"], _sample_xlsx(tmp_path, name="b.xlsx")
    ).json()
    listing = harness.client.get(
        "/api/v1/score-imports",
        params={"assessmentId": scene.assessment["assessmentId"], "limit": 1},
    )
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 2 and len(body["items"]) == 1
    assert body["items"][0]["importId"] == second["importId"]
    assert body["items"][0]["rowCount"] == 3
    assert body["items"][0]["updatedAt"]
    other = harness.client.get("/api/v1/score-imports", params={"assessmentId": "nope"})
    assert other.status_code == 200 and other.json()["total"] == 0
    missing = harness.client.get(f"/api/v1/score-imports/{first['importId']}")
    assert missing.status_code == 200
    unknown = harness.client.get("/api/v1/score-imports/does-not-exist")
    assert unknown.status_code == 404
