"""闭环测试套件（根 ``test/``）与真实导入器对齐的常驻回归。

验证 ``scripts/build-closed-loop-fixtures.py`` 产出的四件套能被真实管线读取：

- 教材 md：解析/分块可用，存在 ``exercise`` 区且正文块多于习题块（避开习题区健全性守卫）；
- 名单 xlsx：``POST /roster-imports`` 预览 40 行、无行级问题、全部可建；
- 试卷 docx：``POST /paper-imports`` 拆出 12 个顶层题 / 16 个计分叶（``11(1)`` 子号正确）；
- 小题分 xlsx：在「已确认试卷 → 施测（40 人）」上上传，表头自动映射、行解析 40 人。

套件文件是仓库资产：本测试保证其与导入规则同步（改动 fixtures 或导入规则都会在此暴露）。
"""

from __future__ import annotations

from pathlib import Path

from app.services.document_parsing.chunking import chunk_document
from app.services.document_parsing.parser import parse_document
from tests.assessments_support import (  # noqa: E402
    SUBJECT_ID,
    AssessmentsHarness,
    items_payload_from_json,
    today,
)

REPO_ROOT = Path(__file__).resolve().parents[3]  # tests → api → apps → 仓库根
KIT = REPO_ROOT / "test"

TEXTBOOK = KIT / "教材-函数与导数节选.md"
ROSTER = KIT / "名单-高一1班.xlsx"
PAPER = KIT / "试卷-函数与导数单元测试.docx"
SCORES = KIT / "小题分-函数与导数单元测试.xlsx"

EXPECTED_SCORED = [str(i) for i in range(1, 11)] + ["11(1)", "11(2)", "12(1)", "12(2)", "12(3)", "12(4)"]


def test_kit_files_exist() -> None:
    for path in (TEXTBOOK, ROSTER, PAPER, SCORES, KIT / "manifest.json"):
        assert path.is_file(), f"缺少套件文件：{path}（先运行 scripts/build-closed-loop-fixtures.py）"


def test_textbook_markdown_parse_and_regions() -> None:
    parsed = parse_document(path=TEXTBOOK, file_name=TEXTBOOK.name)
    assert parsed.char_count > 1500, "教材正文过短"
    chunks = chunk_document(parsed)
    assert chunks, "分块为空"
    regions = [chunk.region for chunk in chunks]
    assert "exercise" in regions, "未识别出习题区（习题/复习参考题 标记）"
    body_count, exercise_count = regions.count("body"), regions.count("exercise")
    assert body_count >= exercise_count, "正文块应不少于习题块（健全性守卫）"
    assert exercise_count / len(regions) < 0.9, "习题区占比过高（健全性守卫会判规则失效）"


def test_roster_preview_is_importable(tmp_path: Path) -> None:
    with AssessmentsHarness(tmp_path) as harness:
        klass = harness.create_class(code="C-KIT")
        response = harness.client.post(
            f"/api/v1/classes/{klass['id']}/roster-imports",
            files={
                "file": (
                    ROSTER.name,
                    ROSTER.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert response.status_code == 201, response.text
        view = response.json()
        rows = view.get("rows") or []
        assert len(rows) == 40, view
        assert not view.get("issues"), view.get("issues")
        # 预览期 decision 为空，自动建议应为 create（学号未命中 → 建档）
        assert {row.get("suggestion") for row in rows} == {"create"}, rows[:2]


def test_paper_docx_splits_into_expected_leaves(tmp_path: Path) -> None:
    with AssessmentsHarness(tmp_path) as harness:
        response = harness.client.post(
            "/api/v1/paper-imports",
            files={
                "file": (
                    PAPER.name,
                    PAPER.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"subjectId": SUBJECT_ID, "title": "函数与导数单元测试"},
        )
        assert response.status_code == 201, response.text
        paper = response.json()["paper"]
        # 12 个顶层题号（11/12 为含子号的容器）+ 6 个子号 = 18 个题号路径；计分叶 16 个
        assert paper["itemCount"] == 18, paper
        assert paper["scoredLeafCount"] == 16, paper

        revision_id = response.json()["revision"]["paperRevisionId"]
        content = harness.client.get(
            f"/api/v1/papers/{paper['paperId']}/revisions/{revision_id}/content"
        )
        assert content.status_code == 200, content.text
        scored = {
            item["questionNo"]
            for item in content.json()["items"]
            if item.get("isScored")
        }
        assert scored == set(EXPECTED_SCORED), scored


def test_score_sheet_maps_against_confirmed_paper(tmp_path: Path) -> None:
    with AssessmentsHarness(tmp_path) as harness:
        # 1) 导入并确认套件试卷（计分叶逐项挂一个知识点，满足确认前置）
        created = harness.client.post(
            "/api/v1/paper-imports",
            files={
                "file": (
                    PAPER.name,
                    PAPER.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"subjectId": SUBJECT_ID, "title": "函数与导数单元测试"},
        )
        assert created.status_code == 201, created.text
        draft = {
            "paperId": created.json()["paper"]["paperId"],
            "paperRevisionId": created.json()["revision"]["paperRevisionId"],
            "revision": created.json()["paper"]["revision"],
        }
        content = harness.client.get(
            f"/api/v1/papers/{draft['paperId']}/revisions/{draft['paperRevisionId']}/content"
        )
        assert content.status_code == 200, content.text
        point = harness.create_point(code="KP-KIT-1", name="函数与导数（套件）")
        knowledge = {
            item["questionNo"]: [point["id"]]
            for item in content.json()["items"]
            if item.get("isScored")
        }
        patched = harness.client.patch(
            f"/api/v1/papers/{draft['paperId']}/draft",
            json={
                "expectedRevision": draft["revision"],
                "items": items_payload_from_json(content.json()["items"], knowledge=knowledge),
                # 未归属的版式块显式排除（说明性段落；真实流程中由教师在校对页处理）
                "blocks": [
                    {
                        "blockId": block["blockId"],
                        "disposition": "excluded",
                        "excludeReason": "版式说明行（测试套件预处理）",
                    }
                    for block in content.json()["blocks"]
                    if block.get("disposition") == "unassigned"
                ],
            },
        )
        assert patched.status_code == 200, patched.text
        current = harness.client.get(f"/api/v1/papers/{draft['paperId']}").json()
        confirmed = harness.client.post(
            f"/api/v1/papers/{draft['paperId']}/confirm",
            json={"expectedRevision": current["revision"], "submissionId": "confirm-kit"},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["scoredLeafCount"] == 16

        # 2) 班级 40 人 + 施测（全部参测）
        klass = harness.create_class(code="C-KIT-SCORE")
        students = [
            harness.create_student(name=f"考生{index:02d}", student_no=f"2026{index:04d}", class_id=klass["id"])
            for index in range(1, 41)
        ]
        participants = [
            AssessmentsHarness.participant(student["id"], klass["id"]) for student in students
        ]
        assessment = harness.client.post(
            "/api/v1/assessments",
            json={
                "submissionId": "kit-as",
                "paperRevisionId": draft["paperRevisionId"],
                "title": "函数与导数单元测试",
                "assessmentType": "exam",
                "heldOn": today(),
                "classIds": [klass["id"]],
                "participants": participants,
            },
        )
        assert assessment.status_code == 201, assessment.text
        assessment_id = assessment.json()["assessment"]["assessmentId"]

        # 3) 上传套件小题分 → 表头自动映射、40 行解析
        uploaded = harness.client.post(
            f"/api/v1/assessments/{assessment_id}/score-imports",
            files={
                "file": (
                    SCORES.name,
                    SCORES.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert uploaded.status_code == 201, uploaded.text
        view = uploaded.json()
        assert view["rowCount"] == 40, view
        assert view["resolvedRowCount"] == 40, view
        mapping = view["mapping"]
        assert mapping, "表头应自动映射到已确认试卷的计分叶"
        assert mapping.get("studentNoColumn"), mapping
        item_columns = mapping.get("itemColumns") or {}
        assert len(item_columns) >= 16, mapping
