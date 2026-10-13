"""R10-BE 删除语义（2026-10-13 用户裁定「舍弃所有归档功能，只留删除」+「拆开交叉引用」）。

分两层：

**学生删除冻结契约**（``DELETE /students/{id}?expectedRevision=N`` → 200
``{mode, message}``；两种模式班级 ``studentCount`` 都下降）——用隔离教学库 + 名单服务
直测（``Harness`` 复制自 ``test_roster_delete_batch`` 的最小装配，避免跨文件依赖）：

- ``deleted``：无参测快照引用 → 学生行与归属行物理删除、名单导入匹配指针置空；
- ``removed_with_history``：有参测快照引用（成绩/报告的证据锚点）→ 关闭活跃归属 +
  身份标记已移除，学生行与成绩数据保留；
- 乐观锁 409 / 不存在 404；重复删除 404（不静默成功）。

**端到端链删除**（真实 API + ``seed_api_loop`` 全闭环：班+学生+试卷+施测+小题分+
报告+练习+转换+导出+回流）：按 练习 → 报告 → 施测(两场) → 试卷 → 学生 → 班级
逐级删除，结束态教学库业务行归零、``PRAGMA foreign_key_check`` 空、
``PRAGMA quick_check`` ok（任务历史 ``workflow_jobs``、受管资产 ``file_assets``
与提交幂等记录按裁定保留）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import roster as roster_route
from app.contracts.teaching_loop import REVISION_CONFLICT
from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.teaching.catalog import TeachingCatalog
from app.schemas.errors import error_response
from app.services.assets.store import AssetStore
from app.services.roster.service import build_roster_service


class RosterHarness:
    """隔离教学库 + 资产库 + 名单服务（``test_roster_delete_batch.Harness`` 同构）。"""

    def __init__(self, root: Path) -> None:
        self.catalog = TeachingCatalog(root / "teaching.sqlite3")
        self.catalog.migrate()
        self.service = build_roster_service(
            self.catalog,
            asset_store=AssetStore(root / "assets"),
            file_assets=FileAssetsRepository(self.catalog),
        )

    def close(self) -> None:
        self.catalog.close()

    def count(self, table: str, where: str = "", params: tuple[object, ...] = ()) -> int:
        connection = connect(self.catalog.db_path)
        try:
            clause = f" WHERE {where}" if where else ""
            row = connection.execute(
                f"SELECT COUNT(*) AS n FROM {table}{clause}", params
            ).fetchone()
            return int(row["n"])
        finally:
            connection.close()

    def cell(self, sql: str, params: tuple[object, ...] = ()) -> object:
        connection = connect(self.catalog.db_path)
        try:
            row = connection.execute(sql, params).fetchone()
            return None if row is None else row[0]
        finally:
            connection.close()

    def raw_execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        connection = connect(self.catalog.db_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(sql, params)
            connection.commit()
        finally:
            connection.close()


@pytest.fixture()
def roster_harness(tmp_path: Path):
    harness = RosterHarness(tmp_path)
    yield harness
    harness.close()


@pytest.fixture()
def roster_client(roster_harness: RosterHarness) -> TestClient:
    app = FastAPI()
    app.state.roster_service = roster_harness.service

    @app.exception_handler(AppError)
    async def app_error(_request, exc: AppError):
        return error_response(
            exc.status_code,
            exc.code,
            str(exc),
            retryable=exc.retryable,
            details=getattr(exc, "details", None),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request, exc: StarletteHTTPException):
        return error_response(exc.status_code, "REQUEST_FAILED", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, exc: RequestValidationError):
        fields = [str(error.get("loc", ())[1:]) for error in exc.errors() if error.get("loc")]
        return error_response(
            422, "INVALID_REQUEST", "请求参数不合法。", details={"fields": fields}
        )

    app.include_router(roster_route.router, prefix="/api/v1")
    client = TestClient(app)
    yield client
    client.close()


def _class_with_students(client: TestClient, *, count: int = 1) -> tuple[str, list[dict]]:
    created = client.post(
        "/api/v1/classes",
        json={"code": "C-1", "name": "一班", "schoolYear": "2026", "gradeId": "g1"},
    )
    assert created.status_code == 201, created.text
    class_id = created.json()["id"]
    students = []
    for index in range(count):
        response = client.post(
            "/api/v1/students",
            json={
                "name": f"学生{index}",
                "studentNo": f"00{index}",
                "classId": class_id,
            },
        )
        assert response.status_code == 201, response.text
        students.append(response.json())
    return class_id, students


def _class_student_count(client: TestClient, class_id: str) -> int:
    response = client.get(f"/api/v1/classes/{class_id}")
    assert response.status_code == 200, response.text
    return response.json()["studentCount"]


# --------------------------------------------------------------------------- 学生删除


def test_delete_student_without_history_is_physical(
    roster_client: TestClient, roster_harness: RosterHarness
) -> None:
    """``deleted``：无参测引用 → 学生行与归属行物理删除；班级计数下降。"""
    class_id, students = _class_with_students(roster_client, count=2)
    target = students[0]
    assert _class_student_count(roster_client, class_id) == 2

    response = roster_client.delete(
        f"/api/v1/students/{target['id']}",
        params={"expectedRevision": target["revision"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "deleted"
    assert "彻底删除" in body["message"] and "1 条班级归属记录" in body["message"]
    assert roster_harness.count("students", "id = ?", (target["id"],)) == 0
    assert roster_harness.count("class_memberships", "student_id = ?", (target["id"],)) == 0
    assert _class_student_count(roster_client, class_id) == 1
    # 重复删除 → 404（不静默成功）
    again = roster_client.delete(
        f"/api/v1/students/{target['id']}", params={"expectedRevision": target["revision"]}
    )
    assert again.status_code == 404


def test_delete_student_with_history_closes_membership_and_keeps_row(
    roster_client: TestClient, roster_harness: RosterHarness
) -> None:
    """``removed_with_history``：有参测快照引用 → 关归属 + 标记已移除；成绩锚点保留、计数下降。"""
    class_id, students = _class_with_students(roster_client, count=2)
    target = students[0]
    # 最小参测快照链路：试卷（confirmed）→ 施测 → 人次（学生被引用的证据锚点）
    now = "2026-10-07T00:00:00Z"
    roster_harness.raw_execute(
        "INSERT INTO file_assets (id, kind, blob_key, sha256, media_type, byte_size, "
        "original_name, created_at) VALUES ('fa-s', 'paper', 'blobs/' || ? || '0', ?, "
        "'application/octet-stream', 1, 's.docx', ?)",
        ("a" * 63, "a" * 64, now),
    )
    roster_harness.raw_execute(
        "INSERT INTO papers (id, owner_id, subject_id, title, current_revision_id, status, "
        "revision, created_at) VALUES ('p-s', 'local', 'math', 's 卷', NULL, 'active', 0, ?)",
        (now,),
    )
    roster_harness.raw_execute(
        "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
        "total_score_units, state, confirmed_at, created_at, title_snapshot, "
        "title_snapshot_source) VALUES ('pr-s', 'p-s', 1, 'fa-s', 100, 'draft', NULL, ?, "
        "'s 卷', 'revision')",
        (now,),
    )
    roster_harness.raw_execute(
        "INSERT INTO paper_items (id, paper_revision_id, parent_item_id, question_no, ordinal, "
        "is_scored, max_score_units, content_json, source_locator_json) VALUES "
        "('pi-s', 'pr-s', NULL, '1', 1, 1, 100, '{}', '{}')"
    )
    roster_harness.raw_execute(
        "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
        "knowledge_revision_id, knowledge_name_snapshot, role, source) VALUES "
        "('pi-s', 'pr-s', 'kp-s', 'kp-s-r', '点', 'primary', 'human')"
    )
    roster_harness.raw_execute(
        "UPDATE paper_revisions SET state='confirmed', confirmed_at=? WHERE id='pr-s'", (now,)
    )
    roster_harness.raw_execute(
        "INSERT INTO assessments (id, owner_id, paper_revision_id, title, assessment_type, "
        "held_on, state, revision, created_at) VALUES ('as-s', 'local', 'pr-s', 's 施测', "
        "'exam', '2026-10-07', 'open', 0, ?)",
        (now,),
    )
    roster_harness.raw_execute(
        "INSERT INTO assessment_classes (assessment_id, class_id) VALUES ('as-s', ?)",
        (class_id,),
    )
    roster_harness.raw_execute(
        "INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, "
        "attendance, name_snapshot) VALUES ('ap-s', 'as-s', ?, ?, 'present', ?)",
        (target["id"], class_id, target["name"]),
    )

    response = roster_client.delete(
        f"/api/v1/students/{target['id']}",
        params={"expectedRevision": target["revision"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "removed_with_history"
    assert "历史成绩" in body["message"] and "保留" in body["message"]
    # 学生行保留为成绩锚点，但身份标记已移除、活跃归属已关闭
    assert roster_harness.count("students", "id = ?", (target["id"],)) == 1
    assert roster_harness.cell("SELECT status FROM students WHERE id = ?", (target["id"],)) == "archived"
    assert (
        roster_harness.cell(
            "SELECT COUNT(*) FROM class_memberships WHERE student_id = ? AND left_on IS NULL",
            (target["id"],),
        )
        == 0
    )
    assert roster_harness.count("assessment_participants", "student_id = ?", (target["id"],)) == 1
    # 班级计数下降（问题 2 的根因：归档不再只改 status）
    assert _class_student_count(roster_client, class_id) == 1


def test_class_count_excludes_removed_students_with_stale_membership(
    roster_client: TestClient, roster_harness: RosterHarness
) -> None:
    """人数与学生列表同口径：身份已移除（archived）但归属行仍是活跃态的历史数据不再充数。

    这类行来自旧归档路径（只改 status、不关归属）；R10-BE 起 ``studentCount``
    按「活跃归属 ∧ 学生身份活跃」统计，历史脏数据不会再把人数顶高（不改用户数据）。
    """
    class_id, students = _class_with_students(roster_client, count=2)
    target = students[0]
    assert _class_student_count(roster_client, class_id) == 2
    # 模拟旧归档：只把 status 置 archived，归属行保持活跃（不做任何删除）
    roster_harness.raw_execute(
        "UPDATE students SET status = 'archived', revision = revision + 1 WHERE id = ?",
        (target["id"],),
    )
    assert _class_student_count(roster_client, class_id) == 1
    # 学生行与归属行仍在（不改用户数据，只是不再计入人数）
    assert roster_harness.count("students", "id = ?", (target["id"],)) == 1
    assert roster_harness.count("class_memberships", "student_id = ?", (target["id"],)) == 1


def test_delete_student_revision_conflict_and_missing(roster_client: TestClient) -> None:
    _class_id, students = _class_with_students(roster_client, count=1)
    target = students[0]

    stale = roster_client.delete(
        f"/api/v1/students/{target['id']}",
        params={"expectedRevision": target["revision"] + 1},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == REVISION_CONFLICT
    missing = roster_client.delete(
        "/api/v1/students/no-such-student", params={"expectedRevision": 0}
    )
    assert missing.status_code == 404


def test_delete_student_clears_import_match_pointer(
    roster_client: TestClient, roster_harness: RosterHarness
) -> None:
    """物理删除学生前把名单导入预览行的匹配指针置空（批次审计行保留、外键不悬挂）。"""
    class_id, students = _class_with_students(roster_client, count=1)
    target = students[0]
    now = "2026-10-07T00:00:00Z"
    roster_harness.raw_execute(
        "INSERT INTO file_assets (id, kind, blob_key, sha256, media_type, byte_size, "
        "original_name, created_at) VALUES ('fa-i', 'roster', 'blobs/' || ? || '0', ?, "
        "'application/octet-stream', 1, 'roster.xlsx', ?)",
        ("d" * 63, "d" * 64, now),
    )
    roster_harness.raw_execute(
        "INSERT INTO roster_imports (id, owner_id, class_id, file_asset_id, state, revision, "
        "mapping_json, warnings_json, created_at, updated_at) VALUES ('ri-1', 'local', ?, 'fa-i', "
        "'reviewing', 0, '{}', '[]', ?, ?)",
        (class_id, now, now),
    )
    roster_harness.raw_execute(
        "INSERT INTO roster_import_rows (import_id, row_no, name, raw_cells_json, issues_json, "
        "matched_student_id) VALUES ('ri-1', 1, '', '{}', '[]', ?)",
        (target["id"],),
    )

    response = roster_client.delete(
        f"/api/v1/students/{target['id']}",
        params={"expectedRevision": target["revision"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["mode"] == "deleted"
    assert roster_harness.count("roster_import_rows", "import_id = ? AND matched_student_id IS NOT NULL", ("ri-1",)) == 0
    assert roster_harness.count("roster_import_rows", "import_id = ?", ("ri-1",)) == 1


# --------------------------------------------------------------------------- 端到端链


def test_real_chain_delete_ends_clean_with_integrity(tmp_path) -> None:
    """全闭环链（班+学生+试卷+施测+小题分+报告+练习+转换+导出+回流）逐级删除到零。

    R10-BE 验收脚本化版本：练习（连带历史）→ 报告 → 两场施测 → 试卷（含已确认修订）
    → 学生（无参测引用 → deleted）→ 班级；结束态业务行归零、外键检查空、quick_check ok。
    保留：``workflow_jobs``（任务历史）、``file_assets``（受管资产）、
    ``command_submissions``（提交幂等记录）。
    """
    from tests.practices_support import open_api_scene, seed_api_loop

    with open_api_scene(tmp_path) as (app, client, _settings):
        loop = seed_api_loop(app, client, tag="r10-del")
        teaching_path = loop["catalogPaths"]["teaching"]

        run_id = loop["analysis"]["runId"]
        run = client.get(f"/api/v1/analysis-runs/{run_id}").json()
        initial_assessment = run["assessmentId"]
        assessment_view = client.get(f"/api/v1/assessments/{initial_assessment}").json()
        paper_id = assessment_view["assessment"]["paperId"]
        converted_assessment = loop["conversion"]["assessmentId"]

        # 1) 练习（连带历史：reviewed 修订/导出/工件/转换/映射）
        set_id = loop["practice"]["practiceSetId"]
        set_view = client.get(f"/api/v1/practice-sets/{set_id}").json()
        removed = client.delete(
            f"/api/v1/practice-sets/{set_id}",
            params={"expectedRevision": set_view["revision"], "includeHistory": "true"},
        )
        assert removed.status_code == 200, removed.text

        # 2) 报告（级联练习：此时已无派生练习，计数为 0）
        deleted_run = client.delete(f"/api/v1/analysis-runs/{run_id}")
        assert deleted_run.status_code == 200, deleted_run.text
        assert deleted_run.json()["removedPracticeSets"] == 0

        # 3) 两场施测（各自级联成绩链；回执逐项计数）；回流施测的原卷 id 一并记下
        converted_paper = client.get(
            f"/api/v1/assessments/{converted_assessment}"
        ).json()["assessment"]["paperId"]
        for assessment_id in (initial_assessment, converted_assessment):
            view = client.get(f"/api/v1/assessments/{assessment_id}").json()["assessment"]
            response = client.delete(
                f"/api/v1/assessments/{assessment_id}",
                params={"expectedRevision": view["revision"]},
            )
            assert response.status_code == 200, response.text
            assert response.json()["deleted"] is True

        # 4) 两张试卷（初测卷 + 练习回流生成卷；已确认修订随卷级联删除）
        for target_paper in (paper_id, converted_paper):
            paper_view = client.get(f"/api/v1/papers/{target_paper}").json()
            deleted_paper = client.delete(
                f"/api/v1/papers/{target_paper}",
                params={"expectedRevision": paper_view["revision"]},
            )
            assert deleted_paper.status_code == 200, deleted_paper.text

        # 5) 学生（两场施测删除后已无参测快照 → 物理删除）
        student_id = loop["studentId"]
        student_view = client.get(f"/api/v1/students/{student_id}").json()
        deleted_student = client.delete(
            f"/api/v1/students/{student_id}",
            params={"expectedRevision": student_view["revision"]},
        )
        assert deleted_student.status_code == 200, deleted_student.text
        assert deleted_student.json()["mode"] == "deleted"

        # 6) 班级（无参测范围/教案引用 → 物理删除）
        class_id = loop["classId"]
        class_view = client.get(f"/api/v1/classes/{class_id}").json()
        deleted_class = client.delete(
            f"/api/v1/classes/{class_id}", params={"expectedRevision": class_view["revision"]}
        )
        assert deleted_class.status_code == 200, deleted_class.text

        # 结束态：业务行归零 + 外键检查空 + quick_check ok
        connection = sqlite3.connect(teaching_path)
        try:
            for table in (
                "classes",
                "class_memberships",
                "students",
                "roster_imports",
                "papers",
                "paper_revisions",
                "paper_items",
                "assessments",
                "assessment_classes",
                "assessment_participants",
                "score_imports",
                "score_revisions",
                "student_item_scores",
                "analysis_runs",
                "practice_sets",
                "practice_revisions",
                "practice_conversions",
                "practice_exports",
                "export_artifacts",
            ):
                remaining = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                assert remaining == 0, f"{table} 仍有 {remaining} 行"
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            # 保留项：任务历史、受管资产与提交幂等记录仍在（不属于链）
            assert connection.execute("SELECT COUNT(*) FROM workflow_jobs").fetchone()[0] > 0
            assert connection.execute("SELECT COUNT(*) FROM file_assets").fetchone()[0] > 0
        finally:
            connection.close()
