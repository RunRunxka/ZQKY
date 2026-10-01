"""B3 业务段 V00 独立验收共享库（自建探针基础设施）。

- 不进 `apps/**`，不引用实现者测试夹具；只复用产品模块（真实 `create_app` + 真装配）。
- **隔离**：导入 `app.*` 之前把 `ZQKY_DATA_DIR` 指到调用方给的临时目录（缺省自动建），
  断言它不等于仓库正式 `.local-data`；不联网、不占端口（TestClient 进程内）。
- 已确认原卷用**自写的直连 SQL** 种子（真表、真触发器；draft → UPDATE confirmed），
  班级/学生/施测/成绩全部走真实 HTTP API。

用法（在 apps/api 的 venv 下执行）：

    cd apps/api
    .venv/Scripts/python.exe -X utf8 <abs>/b3lib.py   # 自检

或由各探针在导入本模块前设好 ZQKY_DATA_DIR。
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

# --------------------------------------------------------------------------- 路径与隔离

REPO = Path(__file__).resolve().parents[4]
API_DIR = REPO / "apps" / "api"
OFFICIAL_DATA_DIR = (REPO / ".local-data").resolve()


def isolated_data_dir(prefix: str = "zqky-b3v00-") -> Path:
    """确保 ZQKY_DATA_DIR 指向临时目录（导入 app 前调用），并返回该目录。"""
    raw = os.environ.get("ZQKY_DATA_DIR")
    if raw:
        path = Path(raw).resolve()
    else:
        path = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
        os.environ["ZQKY_DATA_DIR"] = str(path)
    if path == OFFICIAL_DATA_DIR or OFFICIAL_DATA_DIR in path.parents:
        raise AssertionError(f"探针数据目录不得指向正式 .local-data：{path}")
    return path


isolated_data_dir()

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def _seed_data_dir() -> Path:
    raw = os.environ.get("ZQKY_DATA_DIR")
    assert raw, "ZQKY_DATA_DIR 未设置"
    return Path(raw)


# --------------------------------------------------------------------------- 时间


def today() -> str:
    return datetime.now(UTC).date().isoformat()


def days_before(n: int) -> str:
    return (datetime.now(UTC).date() - timedelta(days=n)).isoformat()


# --------------------------------------------------------------------------- 文件夹具


def write_xlsx(
    path: Path,
    header: Sequence[Any],
    rows: Sequence[Sequence[Any]],
    *,
    sheet_name: str = "成绩",
) -> Path:
    """程序化写 XLSX（自建；返回路径）。"""
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(list(header))
    for row in rows:
        sheet.append(list(row))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(target)
    return target


def write_csv(path: Path, header: Sequence[Any], rows: Sequence[Sequence[Any]]) -> Path:
    import csv

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(list(header))
        for row in rows:
            writer.writerow(list(row))
    return target


# --------------------------------------------------------------------------- 断言收集


class Verdict:
    """收集断言与证据；exit code = 0 when no failures."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.checks: list[dict[str, Any]] = []
        self.failures: list[dict[str, Any]] = []
        self.observations: list[str] = []
        self.started = time.time()

    def check(self, label: str, ok: bool, detail: Any = None) -> bool:
        entry = {"label": label, "ok": bool(ok), "detail": _jsonable(detail)}
        self.checks.append(entry)
        if not ok:
            self.failures.append(entry)
        return bool(ok)

    def expect(self, label: str, actual: Any, expected: Any) -> bool:
        return self.check(
            label, actual == expected, {"actual": _jsonable(actual), "expected": _jsonable(expected)}
        )

    def note(self, text: str) -> None:
        self.observations.append(text)

    def finish(self, *, path: Path | None = None) -> int:
        payload = {
            "probe": self.name,
            "startedAt": self.started,
            "durationSeconds": round(time.time() - self.started, 3),
            "checks": self.checks,
            "failures": self.failures,
            "observations": self.observations,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        print(text)
        if path is not None:
            path.write_text(text, encoding="utf-8")
        print(
            f"[{self.name}] checks={len(self.checks)} failures={len(self.failures)} "
            f"duration={payload['durationSeconds']}s"
        )
        return 1 if self.failures else 0


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


# --------------------------------------------------------------------------- HTTP 测试台


class Harness:
    """真实装配 + TestClient；全部业务写入走 HTTP。"""

    def __init__(self, *, tag: str = "b3v00", data_dir: Path | None = None) -> None:
        from fastapi.testclient import TestClient
        from app.core.config import Settings
        from app.main import create_app

        self.tag = tag
        base = data_dir or (_seed_data_dir() / f"app-{tag}")
        base.mkdir(parents=True, exist_ok=True)
        self.settings = Settings(
            host="127.0.0.1",
            port=8001,
            allowed_origins=frozenset({"http://127.0.0.1:5173", "http://127.0.0.1:5174"}),
            env="test",
            data_dir=base,
        )
        self.app = create_app(self.settings)
        self.db_path = self.settings.teaching_root / "teaching.sqlite3"
        self._ctx = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client = self._ctx

    def __enter__(self) -> "Harness":
        self._ctx.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        self._ctx.__exit__(*exc)  # type: ignore[arg-type]

    # ---------------------------------------------------------------- 直连（断言/种子）

    def raw(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in connection.execute(sql, list(params)).fetchall()]
        finally:
            connection.close()

    def raw_exec(self, sql: str, params: Sequence[Any] = ()) -> None:
        """绕过服务直写（触发器/约束断言用）；失败抛 sqlite3.IntegrityError。"""
        connection = sqlite3.connect(str(self.db_path))
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute(sql, list(params))
            connection.commit()
        finally:
            connection.close()

    def raw_exec_many(self, statements: Sequence[tuple[str, Sequence[Any]]]) -> None:
        connection = sqlite3.connect(str(self.db_path))
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            for sql, params in statements:
                connection.execute(sql, list(params))
            connection.commit()
        finally:
            connection.close()

    def count(self, table: str, where: str = "", params: Sequence[Any] = ()) -> int:
        clause = f" WHERE {where}" if where else ""
        return int(self.raw(f"SELECT COUNT(*) AS n FROM {table}{clause}", params)[0]["n"])

    # ---------------------------------------------------------------- 班级/学生（真 API）

    def create_class(self, *, code: str, name: str | None = None) -> dict[str, Any]:
        response = self.client.post(
            "/api/v1/classes",
            json={
                "code": code,
                "name": name or f"班级 {code}",
                "schoolYear": "2026",
                "gradeId": "grade-1",
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    def create_student(
        self, *, name: str, student_no: str | None, class_id: str, joined_on: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name, "classId": class_id}
        if student_no is not None:
            body["studentNo"] = student_no
        if joined_on is not None:
            body["joinedOn"] = joined_on
        response = self.client.post("/api/v1/students", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    # ---------------------------------------------------------------- 已确认原卷种子（自写 SQL）

    def seed_confirmed_paper(
        self,
        *,
        tag: str,
        leaves: Sequence[tuple[str, int]],
        subject_id: str = "math",
        title: str | None = None,
    ) -> dict[str, Any]:
        """直连真库写一份已确认原卷（draft → 走确认触发器 UPDATE）。"""
        now = datetime.now(UTC).isoformat()
        paper_id = f"pp-{tag}"
        revision_id = f"pr-{tag}"
        asset_id = f"fa-{tag}"
        headline = title or f"{tag} 成绩样本卷"
        sha = ("cd" * 32)[:64]
        statements: list[tuple[str, Sequence[Any]]] = [
            (
                "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
                "media_type, byte_size, created_at) VALUES (?, 'local', 'paper', ?, ?, ?, "
                "'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 1, ?)",
                (asset_id, f"blobs/{sha}", sha, f"{tag}.docx", now),
            ),
            (
                "INSERT INTO papers (id, owner_id, subject_id, title, status, revision, created_at) "
                "VALUES (?, 'local', ?, ?, 'active', 1, ?)",
                (paper_id, subject_id, headline, now),
            ),
            (
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
                "total_score_units, state, title_snapshot, title_snapshot_source, created_at) "
                "VALUES (?, ?, 1, ?, ?, 'draft', ?, 'human', ?)",
                (revision_id, paper_id, asset_id, sum(u for _, u in leaves), headline, now),
            ),
        ]
        for index, (question_no, units) in enumerate(leaves, start=1):
            item_id = f"it-{tag}-{index}"
            statements.append(
                (
                    "INSERT INTO paper_items (id, paper_revision_id, parent_item_id, question_no, "
                    "ordinal, is_scored, max_score_units, content_json, source_locator_json) "
                    "VALUES (?, ?, NULL, ?, ?, 1, ?, '{}', '{}')",
                    (item_id, revision_id, question_no, index, units),
                )
            )
            # 确认触发器要求每个计分叶有知识点关联（ITEM_KNOWLEDGE_MISSING）
            statements.append(
                (
                    "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, "
                    "knowledge_point_id, knowledge_revision_id, knowledge_name_snapshot, role, source) "
                    "VALUES (?, ?, ?, ?, ?, 'primary', 'human')",
                    (
                        item_id,
                        revision_id,
                        f"kp-{tag}-{index}",
                        f"kpv-{tag}-{index}",
                        f"知识点 {index}",
                    ),
                )
            )
        statements.append(
            (
                "UPDATE paper_revisions SET state = 'confirmed', confirmed_at = ? WHERE id = ?",
                (now, revision_id),
            )
        )
        statements.append(
            (
                "UPDATE papers SET current_revision_id = ? WHERE id = ?",
                (revision_id, paper_id),
            )
        )
        self.raw_exec_many(statements)
        self._seed = getattr(self, "_seed", {})
        self._seed[tag] = {
            "paperId": paper_id,
            "revisionId": revision_id,
            "title": headline,
            "leaves": [(q, u) for q, u in leaves],
            "itemIds": [f"it-{tag}-{i}" for i in range(1, len(leaves) + 1)],
        }
        return dict(self._seed[tag], **{"items": self._seed[tag]["itemIds"]})

    # ---------------------------------------------------------------- 施测（真 API）

    def create_assessment(
        self,
        *,
        paper: dict[str, Any],
        class_id: str,
        participants: Sequence[dict[str, Any]],
        submission_id: str,
        title: str = "成绩验收施测",
        held_on: str | None = None,
    ) -> dict[str, Any]:
        response = self.client.post(
            "/api/v1/assessments",
            json={
                "submissionId": submission_id,
                "paperRevisionId": paper["revisionId"],
                "title": title,
                "assessmentType": "exam",
                "heldOn": held_on or today(),
                "classIds": [class_id],
                "participants": list(participants),
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    @staticmethod
    def participant(
        student_id: str, class_id: str, *, attendance: str = "present"
    ) -> dict[str, Any]:
        row: dict[str, Any] = {"studentId": student_id, "classId": class_id}
        if attendance != "present":
            row["attendance"] = attendance
        return row

    # ---------------------------------------------------------------- 成绩链（真 API）

    def upload_scores(
        self,
        assessment_id: str,
        path: Path,
        *,
        file_name: str | None = None,
        media_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
            files={"file": (file_name or path.name, path.read_bytes(), media_type)},
            data=data or None,
        )

    def import_view(self, import_id: str) -> Any:
        return self.client.get(f"/api/v1/score-imports/{import_id}")

    def import_rows(self, import_id: str, *, offset: int = 0, limit: int = 200) -> Any:
        return self.client.get(
            f"/api/v1/score-imports/{import_id}/rows",
            params={"offset": offset, "limit": limit},
        )

    def patch_import(self, import_id: str, body: dict[str, Any]) -> Any:
        return self.client.patch(f"/api/v1/score-imports/{import_id}", json=body)

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

    def assessment(self, assessment_id: str) -> Any:
        response = self.client.get(f"/api/v1/assessments/{assessment_id}")
        assert response.status_code == 200, response.text
        return response.json()

    def add_participants(
        self,
        assessment_id: str,
        *,
        expected_revision: int,
        submission_id: str,
        student_id: str,
        class_id: str,
        attendance: str = "present",
        attempt_no: int | None = None,
    ) -> Any:
        row: dict[str, Any] = {
            "studentId": student_id,
            "classId": class_id,
            "attendance": attendance,
        }
        if attempt_no is not None:
            row["attemptNo"] = attempt_no
        return self.client.post(
            f"/api/v1/assessments/{assessment_id}/participants",
            json={
                "submissionId": submission_id,
                "expectedRevision": expected_revision,
                "participants": [row],
            },
        )

    # ---------------------------------------------------------------- 场景组合

    def sample_scene(
        self,
        *,
        tag: str,
        leaves: Sequence[tuple[str, int]] = (("Q1", 200), ("Q2", 300), ("Q3", 500)),
        students: Sequence[tuple[str, str, str]] = (
            ("A", "0001", "present"),
            ("B", "0002", "present"),
            ("C", "0003", "absent"),
            ("D", "0004", "present"),
        ),
    ) -> dict[str, Any]:
        """已确认原卷 + 一个班 + 四名学生（A/B/C/D）+ 施测（含参测人次）。"""
        paper = self.seed_confirmed_paper(tag=tag, leaves=leaves)
        klass = self.create_class(code=f"C-{tag}")
        joined = days_before(30)
        created: dict[str, dict[str, Any]] = {}
        participants: list[dict[str, Any]] = []
        for name, no, attendance in students:
            student = self.create_student(
                name=name, student_no=no, class_id=klass["id"], joined_on=joined
            )
            created[name] = student
            participants.append(self.participant(student["id"], klass["id"], attendance=attendance))
        detail = self.create_assessment(
            paper=paper,
            class_id=klass["id"],
            participants=participants,
            submission_id=f"as-{tag}",
            title=f"{tag} 施测",
        )
        assessment = detail["assessment"]
        return {
            "paper": paper,
            "class": klass,
            "students": created,
            "assessment": assessment,
            "participants": detail["participants"],
            "byName": {row["nameSnapshot"]: row for row in detail["participants"]},
            "byNo": {row["studentNoSnapshot"]: row for row in detail["participants"]},
            "tag": tag,
        }

    @staticmethod
    def confirm_body(
        view: dict[str, Any],
        *,
        assessment_revision: int | None = None,
        submission_id: str,
        base_score_revision_id: Any = ...,
        absences: list[dict[str, Any]] | None = None,
        missing: dict[str, Any] | None = None,
        preview_version: int | None = None,
    ) -> dict[str, Any]:
        summary = view.get("summary") if isinstance(view.get("summary"), dict) else {}
        preview = summary.get("preview") if isinstance(summary.get("preview"), dict) else {}
        if absences is None:
            absent_by_class = preview.get("absentByClass") or {}
            absences = [
                {"classId": class_id, "participantIds": list(ids)}
                for class_id, ids in absent_by_class.items()
            ]
        if missing is None and preview.get("missingCellCount"):
            missing = {
                "participantIds": list(preview.get("missingParticipantIds") or []),
                "cellCount": int(preview["missingCellCount"]),
            }
        if base_score_revision_id is ...:
            base_score_revision_id = view.get("baseScoreRevisionId")
        body: dict[str, Any] = {
            "expectedImportRevision": view["revision"],
            "expectedAssessmentRevision": (
                assessment_revision
                if assessment_revision is not None
                else int(summary.get("assessmentRevision") or 0)
            ),
            "baseScoreRevisionId": base_score_revision_id,
            "previewVersion": (
                preview_version if preview_version is not None else view["previewVersion"]
            ),
            "submissionId": submission_id,
            "absences": absences,
        }
        if missing is not None:
            body["missing"] = missing
        return body


def matrix_map(page: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """matrix 响应 → {participantName: {"totalUnits":..., "cells": {itemId: (status, units)}}}"""
    out: dict[str, dict[str, Any]] = {}
    for row in page["rows"]:
        participant = row["participant"]
        out[participant["name"]] = {
            "participant": participant,
            "cells": {cell["itemId"]: cell for cell in row["cells"]},
        }
    return out


def cell_statuses(page: dict[str, Any], name: str) -> dict[str, str]:
    for row in page["rows"]:
        if row["participant"]["name"] == name:
            return {cell["itemId"]: cell["status"] for cell in row["cells"]}
    raise AssertionError(f"矩阵里没有 {name}")


if __name__ == "__main__":
    verdict = Verdict("b3lib-selfcheck")
    with Harness(tag="selfcheck") as harness:
        scene = harness.sample_scene(tag="selfcheck")
        verdict.expect("participants 数量", len(scene["participants"]), 4)
        verdict.expect("施测创建", scene["assessment"]["state"], "open")
        verdict.expect(
            "teaching 库存在", harness.db_path.exists(), True
        )
        verdict.expect(
            "迁移登记 0006/0007",
            [
                row["id"]
                for row in harness.raw(
                    "SELECT id FROM schema_migrations ORDER BY id"
                )
                if row["id"].startswith("0006") or row["id"].startswith("0007")
            ],
            ["0006_teaching_score_tables", "0007_teaching_assessment_active_score_fk"],
        )
    sys.exit(verdict.finish())
