"""T30-b 施测测试台（非 ``test_`` 前缀，不参与 pytest 收集）。

**真实装配**：``create_app(make_settings(tmp_path / "data"))`` + ``TestClient``；班级/学生/
名单/知识点/原卷确认全部走**真实 HTTP API**（T30-a 名单链 + T40 原卷确认链），不使用
mock reader 冒充"闭环"。仅有的替身是 T40 样本 DOCX 生成器（``tests.papers_support``，
程序化构造文件，不读正式数据目录、不联网）。

- ``AssessmentsHarness``：真实应用 + 临时数据根（不碰正式 ``.local-data``）；``raw_*``
  辅助方法只用于**断言**（归属历史快照/绕过服务直写触发器保护）；
- 日期一律用相对今天的动态值：``today()`` / ``days_before(n)``，避免测试随时间腐烂。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings
from tests.papers_support import (
    SAMPLE_LEAF_SCORES,
    SAMPLE_TOTAL_UNITS,
    SUBJECT_ID,
    build_paper_docx,
    items_payload_from_json,
)

#: 知识点覆盖：计分叶子题号 → 分值（T10 样本 DOCX 口径 4+8+6+3=21）
LEAF_QUESTION_NOS: tuple[str, ...] = ("16(1)", "16(2)", "17", "18")


def today() -> str:
    return datetime.now(UTC).date().isoformat()


def days_before(days: int) -> str:
    return (datetime.now(UTC).date() - timedelta(days=days)).isoformat()


@dataclass(frozen=True)
class ConfirmedPaper:
    """已确认原卷修订（reader 会放行的最小信息集），供创建施测使用。"""

    paper_id: str
    revision_id: str
    title: str
    total_score_units: int = SAMPLE_TOTAL_UNITS
    scored_leaf_count: int = len(LEAF_QUESTION_NOS)


class AssessmentsHarness:
    """真实应用测试台：进入上下文后 ``harness.client`` 可用。"""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = Path(tmp_path)
        self.settings = make_settings(self.tmp_path / "data")
        self.app = create_app(self.settings)
        self.db_path = self.settings.teaching_root / "teaching.sqlite3"
        self._client_context: TestClient | None = None
        self.client: TestClient = None  # type: ignore[assignment] - __enter__ 后可用

    # ---------------------------------------------------------------- 生命周期

    def __enter__(self) -> "AssessmentsHarness":
        self._client_context = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client = self._client_context.__enter__()
        return self

    def __exit__(self, *exc_info: object) -> None:
        context, self._client_context = self._client_context, None
        if context is not None:
            context.__exit__(*exc_info)  # type: ignore[arg-type]

    # ---------------------------------------------------------------- 班级/学生（真 API）

    def create_class(
        self,
        *,
        code: str,
        name: str | None = None,
        school_year: str = "2026",
        grade_id: str = "grade-1",
    ) -> dict[str, Any]:
        response = self.client.post(
            "/api/v1/classes",
            json={
                "code": code,
                "name": name or f"班级 {code}",
                "schoolYear": school_year,
                "gradeId": grade_id,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    def archive_class(self, class_id: str, *, expected_revision: int) -> dict[str, Any]:
        response = self.client.post(
            f"/api/v1/classes/{class_id}/archive",
            json={"expectedRevision": expected_revision},
        )
        assert response.status_code == 200, response.text
        return response.json()

    def create_student(
        self,
        *,
        name: str,
        student_no: str | None = None,
        class_id: str | None = None,
        joined_on: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name}
        if student_no is not None:
            body["studentNo"] = student_no
        if class_id is not None:
            body["classId"] = class_id
        if joined_on is not None:
            body["joinedOn"] = joined_on
        response = self.client.post("/api/v1/students", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    def get_student(self, student_id: str) -> dict[str, Any]:
        response = self.client.get(f"/api/v1/students/{student_id}")
        assert response.status_code == 200, response.text
        return response.json()

    def rename_student(self, student_id: str, *, name: str, expected_revision: int) -> dict:
        response = self.client.patch(
            f"/api/v1/students/{student_id}",
            json={"expectedRevision": expected_revision, "name": name},
        )
        assert response.status_code == 200, response.text
        return response.json()

    def transfer_student(
        self,
        student_id: str,
        *,
        from_class_id: str,
        to_class_id: str,
        moved_on: str,
        expected_student_revision: int,
    ) -> dict[str, Any]:
        response = self.client.post(
            f"/api/v1/students/{student_id}/transfer",
            json={
                "expectedStudentRevision": expected_student_revision,
                "fromClassId": from_class_id,
                "toClassId": to_class_id,
                "movedOn": moved_on,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    def import_roster(
        self,
        class_id: str,
        rows: list[tuple[str | None, str]],
        *,
        tag: str,
    ) -> dict[str, Any]:
        """CSV（学号,姓名）上传 → 全部 ``create`` 确认；返回确认结果（含行 → studentId）。"""
        lines = ["学号,姓名"]
        for student_no, name in rows:
            lines.append(f"{student_no or ''},{name}")
        content = ("\n".join(lines) + "\n").encode("utf-8")
        upload = self.client.post(
            f"/api/v1/classes/{class_id}/roster-imports",
            files={"file": ("roster.csv", content, "text/csv")},
        )
        assert upload.status_code == 201, upload.text
        view = upload.json()
        captures = self.client.post(
            f"/api/v1/roster-imports/{view['importId']}/confirm",
            json={
                "expectedRevision": view["revision"],
                "submissionId": f"roster-{tag}",
                "identityMatches": [
                    {"rowNo": row["rowNo"], "action": "create"} for row in view["rows"]
                ],
            },
        )
        assert captures.status_code == 200, captures.text
        return captures.json()

    # ---------------------------------------------------------------- 知识点（真 API）

    def create_point(self, *, code: str, name: str, subject_id: str = SUBJECT_ID) -> dict:
        response = self.client.post(
            "/api/v1/knowledge-points",
            json={"subjectId": subject_id, "code": code, "name": name},
        )
        assert response.status_code == 201, response.text
        return response.json()

    # ---------------------------------------------------------------- 原卷（真 API）

    def import_draft_paper(self, *, tag: str, title: str) -> dict[str, Any]:
        """导入 T10 样本 DOCX（未确认）；返回 ``{paperId, paperRevisionId, title, revision}``。"""
        docx = build_paper_docx(self.tmp_path / f"{tag}.docx")
        response = self.client.post(
            "/api/v1/paper-imports",
            files={
                "file": (
                    f"{tag}.docx",
                    docx.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"subjectId": SUBJECT_ID, "title": title},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return {
            "paperId": body["paper"]["paperId"],
            "paperRevisionId": body["revision"]["paperRevisionId"],
            "revision": body["paper"]["revision"],
            "title": body["paper"]["title"],
        }

    def confirm_paper(self, draft: dict[str, Any], *, tag: str) -> ConfirmedPaper:
        """给每个计分叶子补知识点 → 草稿 PATCH → 确认；返回已确认修订。"""
        content = self.client.get(
            f"/api/v1/papers/{draft['paperId']}/revisions/{draft['paperRevisionId']}/content"
        )
        assert content.status_code == 200, content.text
        knowledge: dict[str, list[str]] = {}
        for index, question_no in enumerate(LEAF_QUESTION_NOS):
            point = self.create_point(
                code=f"KP-{tag}-{index + 1}", name=f"{tag} 知识点 {index + 1}"
            )
            knowledge[question_no] = [point["id"]]
        patch = self.client.patch(
            f"/api/v1/papers/{draft['paperId']}/draft",
            json={
                "expectedRevision": draft["revision"],
                "items": items_payload_from_json(
                    content.json()["items"], knowledge=knowledge
                ),
            },
        )
        assert patch.status_code == 200, patch.text
        current = self.client.get(f"/api/v1/papers/{draft['paperId']}")
        assert current.status_code == 200, current.text
        confirmed = self.client.post(
            f"/api/v1/papers/{draft['paperId']}/confirm",
            json={
                "expectedRevision": current.json()["revision"],
                "submissionId": f"confirm-{tag}",
            },
        )
        assert confirmed.status_code == 200, confirmed.text
        body = confirmed.json()
        assert body["state"] == "confirmed"
        assert body["scoredLeafCount"] == len(LEAF_QUESTION_NOS)
        assert body["totalScoreUnits"] == SAMPLE_TOTAL_UNITS
        return ConfirmedPaper(
            paper_id=draft["paperId"],
            revision_id=body["paperRevisionId"],
            title=draft["title"],
        )

    def create_confirmed_paper(self, *, tag: str, title: str | None = None) -> ConfirmedPaper:
        draft = self.import_draft_paper(tag=tag, title=title or f"{tag} 期中测试卷")
        return self.confirm_paper(draft, tag=tag)

    # ---------------------------------------------------------------- 施测请求构造

    @staticmethod
    def create_body(
        paper: ConfirmedPaper,
        *,
        submission_id: str,
        class_ids: list[str],
        participants: list[dict[str, Any]],
        title: str = "第一次施测",
        assessment_type: str = "exam",
        held_on: str | None = None,
    ) -> dict[str, Any]:
        return {
            "submissionId": submission_id,
            "paperRevisionId": paper.revision_id,
            "title": title,
            "assessmentType": assessment_type,
            "heldOn": held_on or today(),
            "classIds": class_ids,
            "participants": participants,
        }

    @staticmethod
    def participant(
        student_id: str,
        class_id: str,
        *,
        attempt_no: int | None = None,
        attendance: str = "present",
        class_confirmed: bool = False,
        class_confirmation_note: str | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {"studentId": student_id, "classId": class_id}
        if attempt_no is not None:
            row["attemptNo"] = attempt_no
        if attendance != "present":
            row["attendance"] = attendance
        if class_confirmed:
            row["classConfirmed"] = True
            row["classConfirmationNote"] = class_confirmation_note or "教师核对后确认"
        return row

    # ---------------------------------------------------------------- 直读（只用于断言）

    def raw_rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in connection.execute(sql, list(params)).fetchall()]
        finally:
            connection.close()

    def raw_execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        """绕过服务直写（触发器/约束保护断言用）；失败抛 ``sqlite3.IntegrityError``。"""
        connection = sqlite3.connect(str(self.db_path))
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute(sql, list(params))
            connection.commit()
        finally:
            connection.close()

    def count(self, table: str, where: str = "", params: tuple[Any, ...] = ()) -> int:
        clause = f" WHERE {where}" if where else ""
        return self.raw_rows(f"SELECT COUNT(*) AS n FROM {table}{clause}", params)[0]["n"]

    def memberships_snapshot(self) -> list[dict[str, Any]]:
        return self.raw_rows(
            "SELECT id, class_id, student_id, joined_on, left_on FROM class_memberships "
            "ORDER BY class_id, student_id, joined_on"
        )


__all__ = [
    "AssessmentsHarness",
    "ConfirmedPaper",
    "LEAF_QUESTION_NOS",
    "SAMPLE_LEAF_SCORES",
    "SAMPLE_TOTAL_UNITS",
    "days_before",
    "today",
]
