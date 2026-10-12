"""T60 成绩测试台（非 ``test_`` 前缀，不参与 pytest 收集）。

**真实装配**：``create_app(make_settings(tmp_path/'data'))`` + 真 ``ScoreService``
（``build_score_service`` 用 app.state 上的真仓储/资产/reader/协调器）＋ ``TestClient``。
班级/学生/施测/参测人次走**真实 HTTP API**；成绩文件是程序化生成的 XLSX（不读正式数据、
不联网）。唯一的"非 HTTP"前置是 ``seed_confirmed_paper``：直接在**迁移后的真库**里写入
一张已确认原卷（含计分叶与知识点，走过确认触发器），用于构造 3 叶/100 叶等固定样本——
不是 mock 仓储，SQL 与触发器都是真的。

固定样本口径（B3 授权原文第五节）：Q1=2 分、Q2=3、Q3=5（×100 单位）；A=(2,2,5)、
B=(2,3,空白)、C=缺考、D=(0,3,5)。
"""

from __future__ import annotations

import os
import re
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from app.core.sqlite import now_iso
from app.services.scores.service import build_score_service
from tests.assessments_support import AssessmentsHarness, ConfirmedPaper, days_before, today

#: 授权样例的三叶与满分（单位 = 分 × 100）
SAMPLE_LEAVES: tuple[tuple[str, int], ...] = (("Q1", 200), ("Q2", 300), ("Q3", 500))
SAMPLE_TOTAL_UNITS = sum(units for _, units in SAMPLE_LEAVES)
#: 样例原表表头（身份列 + 三个计分叶列）
SAMPLE_HEADER: tuple[str, ...] = ("学号", "姓名", "Q1", "Q2", "Q3")
SUBJECT_ID = "math"


@dataclass(frozen=True)
class SeededPaper:
    """直接种子出来的已确认原卷（真库、真确认触发器）。"""

    paper_id: str
    revision_id: str
    title: str
    leaves: tuple[tuple[str, int], ...]

    @property
    def total_score_units(self) -> int:
        return sum(units for _, units in self.leaves)

    def confirmed(self) -> ConfirmedPaper:
        return ConfirmedPaper(
            paper_id=self.paper_id,
            revision_id=self.revision_id,
            title=self.title,
            total_score_units=self.total_score_units,
            scored_leaf_count=len(self.leaves),
        )


@dataclass
class ScoreScene:
    """标准场景：已确认原卷 + 一个班 + 学生 + 施测（含参测人次）。"""

    paper: SeededPaper
    klass: dict[str, Any]
    students: list[dict[str, Any]]
    assessment: dict[str, Any]
    participants: list[dict[str, Any]]

    def participant_id(self, student_no: str) -> str:
        for row in self.participants:
            if row.get("studentNoSnapshot") == student_no:
                return row["participantId"]
        raise AssertionError(f"场景里没有学号 {student_no} 的参测人次")

    def participant_by_name(self, name: str) -> list[dict[str, Any]]:
        return [row for row in self.participants if row["nameSnapshot"] == name]

    def student_id(self, student_no: str) -> str:
        for row in self.students:
            if row.get("studentNo") == student_no:
                return row["id"]
        raise AssertionError(f"场景里没有学号 {student_no} 的学生")


class ScoresHarness(AssessmentsHarness):
    """在 T30-b 测试台上加挂真 ``ScoreService``（不复制第二套装配）。"""

    def __enter__(self) -> "ScoresHarness":
        super().__enter__()
        self.app.state.score_service = build_score_service(
            self.app.state.teaching,
            asset_store=self.app.state.asset_store,
            file_assets=self.app.state.file_assets,
            assessment_service=self.app.state.assessment_service,
            paper_reader=self.app.state.confirmed_paper_reader,
            publication_coordinator=self.app.state.publication_coordinator,
        )
        return self

    # ---------------------------------------------------------------- 种子原卷

    def seed_confirmed_paper(
        self,
        *,
        tag: str,
        leaves: Sequence[tuple[str, int]] = SAMPLE_LEAVES,
        title: str | None = None,
    ) -> SeededPaper:
        """在真库里写一张已确认原卷（draft → UPDATE confirmed，走确认触发器）。"""
        headline = title or f"{tag} 成绩样本卷"
        paper_id = f"pp-{tag}"
        revision_id = f"pr-{tag}"
        asset_id = f"fa-paper-{tag}"
        now = now_iso()
        sha = ("ab" * 32)[:64]
        connection = sqlite3.connect(str(self.db_path))
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute(
                "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
                "media_type, byte_size, created_at) VALUES (?, 'local', 'paper', ?, ?, ?, "
                "'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 1, ?)",
                (asset_id, f"blobs/{sha}", sha, f"{tag}.docx", now),
            )
            connection.execute(
                "INSERT INTO papers (id, owner_id, subject_id, title, status, revision, created_at) "
                "VALUES (?, 'local', ?, ?, 'active', 1, ?)",
                (paper_id, SUBJECT_ID, headline, now),
            )
            connection.execute(
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
                "total_score_units, state, title_snapshot, title_snapshot_source, created_at) "
                "VALUES (?, ?, 1, ?, ?, 'draft', ?, 'human', ?)",
                (revision_id, paper_id, asset_id, sum(u for _, u in leaves), headline, now),
            )
            for index, (question_no, units) in enumerate(leaves, start=1):
                item_id = f"it-{tag}-{index}"
                connection.execute(
                    "INSERT INTO paper_items (id, paper_revision_id, parent_item_id, question_no, "
                    "ordinal, is_scored, max_score_units, content_json, source_locator_json) "
                    "VALUES (?, ?, NULL, ?, ?, 1, ?, '{}', '{}')",
                    (item_id, revision_id, question_no, index, units),
                )
                connection.execute(
                    "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, "
                    "knowledge_point_id, knowledge_revision_id, knowledge_name_snapshot, role, source) "
                    "VALUES (?, ?, ?, ?, ?, 'primary', 'human')",
                    (item_id, revision_id, f"kp-{tag}-{index}", f"kpv-{tag}-{index}", f"知识点 {index}"),
                )
            connection.execute(
                "UPDATE paper_revisions SET state = 'confirmed', confirmed_at = ? WHERE id = ?",
                (now, revision_id),
            )
            connection.execute(
                "UPDATE papers SET current_revision_id = ? WHERE id = ?",
                (revision_id, paper_id),
            )
            connection.commit()
        finally:
            connection.close()
        return SeededPaper(
            paper_id=paper_id,
            revision_id=revision_id,
            title=headline,
            leaves=tuple((q, u) for q, u in leaves),
        )

    # ---------------------------------------------------------------- 场景

    def create_scene(
        self,
        *,
        tag: str,
        students: Sequence[tuple[str, str | None]] = (("甲", "0001"),),
        leaves: Sequence[tuple[str, int]] = SAMPLE_LEAVES,
        attendance: dict[str, str] | None = None,
        held_on: str | None = None,
        submission_id: str | None = None,
    ) -> ScoreScene:
        """真 API 建立：已确认原卷 → 班级 → 学生 → 施测（含参测人次）。"""
        paper = self.seed_confirmed_paper(tag=tag, leaves=leaves)
        klass = self.create_class(code=f"C-{tag}")
        joined = days_before(30)
        created = [
            self.create_student(name=name, student_no=student_no, class_id=klass["id"], joined_on=joined)
            for name, student_no in students
        ]
        attendance = attendance or {}
        participants = [
            AssessmentsHarness.participant(
                student["id"],
                klass["id"],
                attendance=attendance.get(student.get("studentNo") or student["name"], "present"),
            )
            for student in created
        ]
        body = AssessmentsHarness.create_body(
            paper.confirmed(),
            submission_id=submission_id or f"as-{tag}",
            class_ids=[klass["id"]],
            participants=participants,
            title=f"{tag} 施测",
            held_on=held_on or today(),
        )
        response = self.client.post("/api/v1/assessments", json=body)
        assert response.status_code == 201, response.text
        detail = response.json()
        return ScoreScene(
            paper=paper,
            klass=klass,
            students=created,
            assessment=detail["assessment"],
            participants=detail["participants"],
        )

    # ---------------------------------------------------------------- 成绩 API

    def upload_scores(
        self,
        assessment_id: str,
        path: Path,
        *,
        file_name: str | None = None,
        work_sheet: str | None = None,
        base_score_revision_id: str | None = None,
    ) -> Any:
        data: dict[str, str] = {}
        if work_sheet is not None:
            data["workSheet"] = work_sheet
        if base_score_revision_id is not None:
            data["baseScoreRevisionId"] = base_score_revision_id
        return self.client.post(
            f"/api/v1/assessments/{assessment_id}/score-imports",
            files={
                "file": (
                    file_name or path.name,
                    path.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            data=data or None,
        )

    def patch_import(self, import_id: str, body: dict[str, Any]) -> Any:
        return self.client.patch(f"/api/v1/score-imports/{import_id}", json=body)

    def get_import(self, import_id: str) -> Any:
        return self.client.get(f"/api/v1/score-imports/{import_id}")

    def list_import_rows(self, import_id: str, *, offset: int = 0, limit: int = 200) -> Any:
        return self.client.get(
            f"/api/v1/score-imports/{import_id}/rows",
            params={"offset": offset, "limit": limit},
        )

    def confirm_import(self, import_id: str, body: dict[str, Any]) -> Any:
        return self.client.post(f"/api/v1/score-imports/{import_id}/confirm", json=body)

    def score_revisions(self, assessment_id: str) -> Any:
        return self.client.get(f"/api/v1/assessments/{assessment_id}/score-revisions")

    def score_matrix(self, revision_id: str, *, offset: int = 0, limit: int = 50) -> Any:
        return self.client.get(
            f"/api/v1/score-revisions/{revision_id}/matrix",
            params={"offset": offset, "limit": limit},
        )

    def correct_scores(self, assessment_id: str, body: dict[str, Any]) -> Any:
        return self.client.post(
            f"/api/v1/assessments/{assessment_id}/score-revisions/correct", json=body
        )

    def assessment(self, assessment_id: str) -> dict[str, Any]:
        response = self.client.get(f"/api/v1/assessments/{assessment_id}")
        assert response.status_code == 200, response.text
        return response.json()["assessment"]

    def service(self):
        return self.app.state.score_service


# --------------------------------------------------------------------------- XLSX 夹具


def write_score_xlsx(
    path: Path,
    header: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    sheet_name: str = "成绩",
    extra_sheets: dict[str, Sequence[Sequence[Any]]] | None = None,
) -> Path:
    """写一份成绩 XLSX；以 ``=`` 开头的字符串按公式写入（openpyxl 口径）。"""
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(list(header))
    for row in rows:
        sheet.append(list(row))
    for name, extra_rows in (extra_sheets or {}).items():
        extra = workbook.create_sheet(title=name)
        for row in extra_rows:
            extra.append(list(row))
    target = Path(path)
    workbook.save(target)
    return target


def inject_cached_values(path: Path, cached: dict[str, str]) -> Path:
    """给（由 openpyxl 写入、无缓存的）公式单元格注入 data_only 缓存值。

    openpyxl 不计算公式、也不写缓存；这里直接改 ``xl/worksheets/sheet1.xml``，
    模拟"Excel 保存过的"文件：``<c r="D2"><f>...</f><v>5</v></c>``。
    """
    target = Path(path)
    temporary = target.with_suffix(".cached.xlsx")
    with zipfile.ZipFile(target) as source, zipfile.ZipFile(
        temporary, "w", zipfile.ZIP_DEFLATED
    ) as destination:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                text = data.decode("utf-8")
                for reference, value in cached.items():
                    pattern = re.compile(rf'<c r="{re.escape(reference)}"[^>]*>.*?</c>')
                    match = pattern.search(text)
                    assert match, f"注入缓存失败：找不到单元格 {reference}"
                    cell = match.group(0)
                    formula = re.search(r"<f>.*?</f>", cell)
                    assert formula, f"注入缓存失败：{reference} 不是公式单元格"
                    replacement = (
                        f'<c r="{reference}">{formula.group(0)}<v>{value}</v></c>'
                    )
                    text = text[: match.start()] + replacement + text[match.end() :]
                data = text.encode("utf-8")
            destination.writestr(item, data)
    os.replace(temporary, target)
    return target


# --------------------------------------------------------------------------- 承认构造


def absence_ack(class_id: str, participant_ids: Sequence[str]) -> dict[str, Any]:
    return {"classId": class_id, "participantIds": list(participant_ids)}


def missing_ack(participant_ids: Sequence[str], cell_count: int) -> dict[str, Any]:
    return {"participantIds": list(participant_ids), "cellCount": cell_count}


def row_for(view: dict[str, Any], name: str) -> dict[str, Any]:
    """在预览行列表里按姓名找行（测试断言用）。"""
    for row in view["items"]:
        if row.get("participantName") == name:
            return row
    raise AssertionError(f"预览行里没有 {name}")


def cells_by_column(row: dict[str, Any]) -> dict[str, str]:
    return {cell["column"]: cell.get("text", "") for cell in row.get("cells", [])}


__all__ = [
    "SAMPLE_LEAVES",
    "SAMPLE_TOTAL_UNITS",
    "ScoreScene",
    "ScoresHarness",
    "SeededPaper",
    "absence_ack",
    "cells_by_column",
    "inject_cached_values",
    "missing_ack",
    "row_for",
    "write_score_xlsx",
]
