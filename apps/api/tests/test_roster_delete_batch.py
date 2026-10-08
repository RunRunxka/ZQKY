"""班级受引用守卫的彻底删除（DELETE /classes/{id}）与批量添加学生（students/batch）。

覆盖（全部 tmp_path 隔离数据根，真 HTTP API + 真教学库）：

- 班级删除四类用例：
  * 可删成功：无任何引用的班级物理删除，``class_memberships`` 等子行一并消失；
  * 被引用 409 ``CLASS_IN_USE``：``details.counts`` 列出归属/施测范围/教案计数；
  * 乐观锁 409 ``REVISION_CONFLICT``（``details.currentRevision``）；
  * 404（班级不存在）。
- 批量添加学生：部分跳过（学号已存在给出 existingStudentId/existingName）、
  幂等重放（同 ``submissionId`` 返回原结果 ``replayed=True``）、
  非法行整批回滚（422 + 行号定位，零写入）、归档班级 409 ``CLASS_ARCHIVED``。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import roster as roster_route
from app.contracts.roster import CLASS_ARCHIVED
from app.contracts.teaching_loop import REVISION_CONFLICT
from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.teaching.catalog import TeachingCatalog
from app.schemas.errors import error_response
from app.services.assets.store import AssetStore
from app.services.roster.service import build_roster_service


class Harness:
    """一套隔离的教学库 + 资产库 + 名单服务。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.catalog = TeachingCatalog(root / "teaching.sqlite3")
        self.catalog.migrate()
        self.asset_store = AssetStore(root / "assets")
        self.service = build_roster_service(
            self.catalog,
            asset_store=self.asset_store,
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

    def raw_execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        """绕过服务直写（守卫计数断言用；仅测试内部触发）。"""
        connection = connect(self.catalog.db_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(sql, params)
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
        finally:
            connection.close()

    def raw_execute_many(self, statements: list[tuple[str, tuple[object, ...]]]) -> None:
        """在同一事务内执行多条直写（需要跨行外键链的播种）；外键检查延迟到 COMMIT。"""
        connection = connect(self.catalog.db_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("PRAGMA defer_foreign_keys = ON")
            try:
                for sql, params in statements:
                    connection.execute(sql, params)
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
        finally:
            connection.close()


def _install_error_handlers(app: FastAPI) -> None:
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


@pytest.fixture()
def harness(tmp_path: Path):
    instance = Harness(tmp_path)
    yield instance
    instance.close()


@pytest.fixture()
def client(harness: Harness):
    app = FastAPI()
    app.state.roster_service = harness.service
    _install_error_handlers(app)
    app.include_router(roster_route.router, prefix="/api/v1")
    with TestClient(app, base_url="http://127.0.0.1:8001") as test_client:
        yield test_client


def _create_class(client: TestClient, code: str = "701") -> dict:
    response = client.post(
        "/api/v1/classes",
        json={
            "code": code,
            "name": f"七年级{code}班",
            "schoolYear": "2026-2027",
            "gradeId": "grade-7",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------- 班级删除


def test_delete_clean_class_succeeds(client: TestClient, harness: Harness) -> None:
    created = _create_class(client)
    class_id = created["id"]

    deleted = client.delete(f"/api/v1/classes/{class_id}", params={"expectedRevision": 0})
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body == {"deleted": True, "classId": class_id}

    # 物理删除：班级行与归属子行都不存在
    assert harness.count("classes", "id = ?", (class_id,)) == 0
    fetched = client.get(f"/api/v1/classes/{class_id}")
    assert fetched.status_code == 404


def test_delete_class_blocked_by_membership(client: TestClient, harness: Harness) -> None:
    created = _create_class(client)
    class_id = created["id"]
    student = client.post(
        "/api/v1/students", json={"name": "张三", "studentNo": "0012", "classId": class_id}
    )
    assert student.status_code == 201, student.text

    blocked = client.delete(f"/api/v1/classes/{class_id}", params={"expectedRevision": 0})
    assert blocked.status_code == 409, blocked.text
    body = blocked.json()
    assert body["code"] == "CLASS_IN_USE"
    assert body["details"]["counts"]["memberships"] == 1
    assert body["details"]["counts"]["assessments"] == 0
    assert body["details"]["counts"]["lessonPlans"] == 0
    # 零删除：班级行仍在
    assert harness.count("classes", "id = ?", (class_id,)) == 1


def test_delete_class_blocked_by_assessment_scope(client: TestClient, harness: Harness) -> None:
    """参测范围行（assessment_classes）是真实外链：按外键顺序播种最小链路后验证守卫计数。"""
    created = _create_class(client)
    class_id = created["id"]
    now = "2026-10-07T00:00:00Z"
    # file_assets → papers → paper_revisions(confirmed) → assessments → assessment_classes
    harness.raw_execute(
        "INSERT INTO file_assets (id, kind, blob_key, sha256, media_type, byte_size, "
        "original_name, created_at) VALUES ('fa-x', 'paper', 'blobs/' || ? || '0', ?, "
        "'application/octet-stream', 1, 'x.docx', ?)",
        ("a" * 63, "a" * 64, now),
    )
    harness.raw_execute(
        "INSERT INTO papers (id, owner_id, subject_id, title, current_revision_id, status, "
        "revision, created_at) VALUES ('p-x', 'local', 'math', 'x 卷', NULL, 'active', 0, ?)",
        (now,),
    )
    harness.raw_execute(
        "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
        "total_score_units, state, confirmed_at, created_at, title_snapshot, "
        "title_snapshot_source) VALUES ('pr-x', 'p-x', 1, 'fa-x', 100, 'draft', NULL, ?, "
        "'x 卷', 'revision')",
        (now,),
    )
    # 一道计分叶子 + 知识点关联（满足 paper_confirm 触发器闸门）
    harness.raw_execute(
        "INSERT INTO paper_items (id, paper_revision_id, parent_item_id, question_no, ordinal, "
        "is_scored, max_score_units, content_json, source_locator_json) VALUES "
        "('pi-x', 'pr-x', NULL, '1', 1, 1, 100, '{}', '{}')"
    )
    harness.raw_execute(
        "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
        "knowledge_revision_id, knowledge_name_snapshot, role, source) VALUES "
        "('pi-x', 'pr-x', 'kp-x', 'kp-x-r', '点', 'primary', 'human')"
    )
    harness.raw_execute(
        "UPDATE paper_revisions SET state='confirmed', confirmed_at=? WHERE id='pr-x'",
        (now,),
    )
    harness.raw_execute(
        "INSERT INTO assessments (id, owner_id, paper_revision_id, title, assessment_type, "
        "held_on, state, revision, created_at) VALUES ('as-x', 'local', 'pr-x', 'x 施测', "
        "'exam', '2026-10-07', 'open', 0, ?)",
        (now,),
    )
    harness.raw_execute(
        "INSERT INTO assessment_classes (assessment_id, class_id) VALUES ('as-x', ?)",
        (class_id,),
    )
    blocked = client.delete(f"/api/v1/classes/{class_id}", params={"expectedRevision": 0})
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "CLASS_IN_USE"
    assert blocked.json()["details"]["counts"]["assessments"] == 1


def test_delete_class_blocked_by_lesson_plan(client: TestClient, harness: Harness) -> None:
    """教案引用（lesson_plans.class_id）计数：按 0010 迁移外键顺序播种最小可引用行。"""
    created = _create_class(client)
    class_id = created["id"]
    now = "2026-10-07T00:00:00Z"
    zero_hash = "0" * 64
    # lesson_plan_revisions 先行 → lesson_plans（class_id 外键 + current 指针）
    harness.raw_execute_many(
        [
            (
                "INSERT INTO lesson_plan_revisions (id, lesson_plan_id, owner_id, version, "
                "data_json, content_hash, source, context_snapshot_json, source_metadata_json, "
                "selected_fields_json, process_metadata_json, created_at) VALUES "
                "('lp-1-r', 'lp-1', 'local', 1, '{}', ?, 'manual', '{}', '{}', '[]', '[]', ?)",
                (zero_hash, now),
            ),
            (
                "INSERT INTO lesson_plans (id, owner_id, subject_id, class_id, "
                "current_revision_id, revision, created_at, updated_at) VALUES "
                "('lp-1', 'local', 'math', ?, 'lp-1-r', 1, ?, ?)",
                (class_id, now, now),
            ),
        ]
    )
    blocked = client.delete(f"/api/v1/classes/{class_id}", params={"expectedRevision": 0})
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "CLASS_IN_USE"
    assert blocked.json()["details"]["counts"]["lessonPlans"] == 1


def test_delete_class_revision_conflict(client: TestClient) -> None:
    created = _create_class(client)
    class_id = created["id"]
    # 先归档一次使 revision 变 1，再用旧 revision 删除
    archived = client.post(f"/api/v1/classes/{class_id}/archive", json={"expectedRevision": 0})
    assert archived.status_code == 200, archived.text

    stale = client.delete(f"/api/v1/classes/{class_id}", params={"expectedRevision": 0})
    assert stale.status_code == 409
    assert stale.json()["code"] == REVISION_CONFLICT
    assert stale.json()["details"]["currentRevision"] == 1


def test_delete_class_not_found(client: TestClient) -> None:
    missing = client.delete("/api/v1/classes/no-such-class", params={"expectedRevision": 0})
    assert missing.status_code == 404


# --------------------------------------------------------------------------- 批量添加学生


def _batch_payload(
    items: list[dict], *, submission: str = "batch-1", joined_on: str | None = None
) -> dict:
    payload: dict = {"submissionId": submission, "items": items}
    if joined_on is not None:
        payload["joinedOn"] = joined_on
    return payload


def test_batch_add_students_creates_and_skips(client: TestClient, harness: Harness) -> None:
    created_class = _create_class(client)
    class_id = created_class["id"]
    # 既有学生（同学号）：应当被跳过并给出既有身份
    existing = client.post(
        "/api/v1/students", json={"name": "老王", "studentNo": "0001"}
    )
    assert existing.status_code == 201, existing.text
    existing_body = existing.json()

    response = client.post(
        f"/api/v1/classes/{class_id}/students/batch",
        json=_batch_payload(
            [
                {"name": "张三", "studentNo": "0012"},
                {"name": "李四", "studentNo": "0013"},
                {"name": "同名新同学", "studentNo": "0001"},  # 学号已存在 → 跳过
                {"name": "王五无学号"},  # 无学号显式建档
            ],
            joined_on="2026-09-01",
        ),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["replayed"] is False
    created_names = [item["name"] for item in body["created"]]
    assert created_names == ["张三", "李四", "王五无学号"]
    assert [item["studentNo"] for item in body["created"][:2]] == ["0012", "0013"]
    # 跳过行：0 基下标 + 既有学生信息
    assert len(body["skipped"]) == 1
    skip = body["skipped"][0]
    assert skip["index"] == 2
    assert skip["code"] == "STUDENT_NO_CONFLICT"
    assert skip["existingStudentId"] == existing_body["id"]
    assert skip["existingName"] == "老王"
    # 姓名重复允许（同名不同人，两条记录）
    names = client.get("/api/v1/students", params={"q": "同名新同学"})
    assert names.status_code == 200
    # 归属与 joinedOn
    roster = client.get(f"/api/v1/classes/{class_id}/students")
    assert roster.status_code == 200
    joined = {
        item["name"]: [
            m["joinedOn"] for m in item["memberships"] if m["classId"] == class_id
        ]
        for item in roster.json()["items"]
    }
    assert joined["张三"] == ["2026-09-01"]
    assert "老王" not in joined  # 既有学生未加班（跳过行不写归属）
    assert harness.count("class_memberships", "class_id = ?", (class_id,)) == 3


def test_batch_add_students_replay_is_idempotent(
    client: TestClient, harness: Harness
) -> None:
    created_class = _create_class(client)
    class_id = created_class["id"]
    payload = _batch_payload(
        [{"name": "张三", "studentNo": "0012"}], submission="same-sub", joined_on="2026-09-01"
    )
    first = client.post(f"/api/v1/classes/{class_id}/students/batch", json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["replayed"] is False

    replay = client.post(f"/api/v1/classes/{class_id}/students/batch", json=payload)
    assert replay.status_code == 200, replay.text
    replayed = replay.json()
    assert replayed["replayed"] is True
    # 返回的是原结果：不再新建、不再跳过
    assert [item["name"] for item in replayed["created"]] == ["张三"]
    assert replayed["skipped"] == []
    # 数据零变化
    assert harness.count("students", "name = '张三'") == 1
    assert harness.count("class_memberships", "class_id = ?", (class_id,)) == 1

    # 同 submissionId 不同载荷 → 409 SUBMISSION_CONFLICT
    conflict = client.post(
        f"/api/v1/classes/{class_id}/students/batch",
        json=_batch_payload(
            [{"name": "赵六", "studentNo": "0014"}], submission="same-sub"
        ),
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "SUBMISSION_CONFLICT"


def test_batch_add_students_invalid_row_rolls_back_all(
    client: TestClient, harness: Harness
) -> None:
    created_class = _create_class(client)
    class_id = created_class["id"]
    bad = client.post(
        f"/api/v1/classes/{class_id}/students/batch",
        json=_batch_payload(
            [
                {"name": "张三", "studentNo": "0012"},
                {"name": "", "studentNo": "0013"},  # 非法行：姓名空
            ],
            submission="batch-invalid",
        ),
    )
    assert bad.status_code == 422, bad.text
    body = bad.json()
    assert body["code"] == "ROSTER_ROW_INVALID"
    issues = body["details"]["issues"]
    assert issues[0]["row"] == 1  # 0 基下标定位非法行
    # 整批回滚：合法行也没有写入
    assert harness.count("students") == 0
    assert harness.count("class_memberships") == 0

    too_long = client.post(
        f"/api/v1/classes/{class_id}/students/batch",
        json=_batch_payload(
            [{"name": "张三", "studentNo": "1" * 65}], submission="batch-toolong"
        ),
    )
    assert too_long.status_code == 422
    assert too_long.json()["code"] == "ROSTER_ROW_INVALID"
    assert harness.count("students") == 0

    # 失败后正常请求仍可成功（不留半提交状态）
    ok = client.post(
        f"/api/v1/classes/{class_id}/students/batch",
        json=_batch_payload([{"name": "张三", "studentNo": "0012"}], submission="batch-ok"),
    )
    assert ok.status_code == 200, ok.text
    assert len(ok.json()["created"]) == 1


def test_batch_add_students_archived_class_rejected(
    client: TestClient, harness: Harness
) -> None:
    created_class = _create_class(client)
    class_id = created_class["id"]
    archived = client.post(f"/api/v1/classes/{class_id}/archive", json={"expectedRevision": 0})
    assert archived.status_code == 200, archived.text

    response = client.post(
        f"/api/v1/classes/{class_id}/students/batch",
        json=_batch_payload([{"name": "张三", "studentNo": "0012"}]),
    )
    assert response.status_code == 409
    assert response.json()["code"] == CLASS_ARCHIVED
    assert harness.count("students") == 0


def test_batch_add_students_class_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/v1/classes/no-such-class/students/batch",
        json=_batch_payload([{"name": "张三"}]),
    )
    assert response.status_code == 404


def test_batch_add_students_empty_items_rejected(client: TestClient) -> None:
    created_class = _create_class(client)
    response = client.post(
        f"/api/v1/classes/{created_class['id']}/students/batch",
        json=_batch_payload([], submission="batch-empty"),
    )
    assert response.status_code == 422


def test_delete_class_blocked_by_roster_import(client: TestClient, harness: Harness) -> None:
    """名单导入批次（roster_imports.class_id 真实外键）同样拦截：删除前先放弃/清理批次。"""
    created = _create_class(client)
    class_id = created["id"]
    now = "2026-10-07T00:00:00Z"
    harness.raw_execute_many(
        [
            (
                "INSERT INTO file_assets (id, kind, blob_key, sha256, media_type, byte_size, "
                "original_name, created_at) VALUES ('fa-roster', 'roster', 'blobs/' || ?, ?, "
                "'text/csv', 1, 'roster.csv', ?)",
                ("c" * 63, "c" * 64, now),
            ),
            (
                "INSERT INTO roster_imports (id, class_id, file_asset_id, mapping_json, "
                "warnings_json, state, revision, created_at, updated_at) VALUES "
                "('ri-1', ?, 'fa-roster', '{}', '[]', 'confirmed', 0, ?, ?)",
                (class_id, now, now),
            ),
        ]
    )
    blocked = client.delete(f"/api/v1/classes/{class_id}", params={"expectedRevision": 0})
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "CLASS_IN_USE"
    assert blocked.json()["details"]["counts"]["rosterImports"] == 1
