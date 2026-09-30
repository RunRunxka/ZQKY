"""班级 / 学生 / 归属历史（TEACHING-LOOP B1 / T30-a，验收 A9）。

覆盖：班级 CRUD 与乐观锁、同 code+学年冲突、归档行为（仍可读 / 拒绝新导入）、
``studentCount`` 只计活跃归属；学生创建（``0012`` 原样、无学号 NULL、同名可建）、
学号冲突、列表模糊查询；转班保留旧归属与重复转班语义；同班重复归属幂等；
``UnavailablePaperReader`` 返回 501（本批只冻结施测契约）。

全部使用 ``tmp_path`` 隔离数据根，不联网、不读写正式 ``.local-data``。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import roster as roster_route
from app.contracts.roster import (
    CLASS_ARCHIVED,
    CLASS_CODE_CONFLICT,
    PAPER_READER_UNAVAILABLE,
    ROSTER_IMPORT_CONFIRMED,
    STUDENT_NO_CONFLICT,
    ClassCreateRequest,
    ClassRevisionRequest,
    ClassUpdateRequest,
    MembershipTransferRequest,
    RosterImportConfirmRequest,
    StudentCreateRequest,
    StudentUpdateRequest,
    UnavailablePaperReader,
)
from app.contracts.teaching_loop import REVISION_CONFLICT
from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.teaching.students import StudentRepository
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

    def scalar(self, sql: str, params: tuple[object, ...] = ()) -> object:
        connection = connect(self.catalog.db_path)
        try:
            return connection.execute(sql, params).fetchone()[0]
        finally:
            connection.close()


def _install_error_handlers(app: FastAPI) -> None:
    """与 app.main 相同的错误信封（这里只装 roster 路由，避免动共享文件）。"""

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


def _class_payload(code: str = "701", school_year: str = "2026-2027") -> dict[str, str]:
    return {
        "code": code,
        "name": f"七年级{code}班",
        "schoolYear": school_year,
        "gradeId": "grade-7",
    }


def _create_class(harness: Harness, code: str = "701", school_year: str = "2026-2027"):
    return harness.service.create_class(
        ClassCreateRequest(**_class_payload(code, school_year))
    )


def _create_student(harness: Harness, name: str, student_no: str | None = None):
    return harness.service.create_student(
        StudentCreateRequest(name=name, studentNo=student_no)
    )


# --------------------------------------------------------------------------- 班级


def test_class_crud_roundtrip_via_http(client: TestClient) -> None:
    created = client.post("/api/v1/classes", json=_class_payload())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["code"] == "701"
    assert body["schoolYear"] == "2026-2027"
    assert body["gradeId"] == "grade-7"
    assert body["status"] == "active"
    assert body["revision"] == 0
    assert body["studentCount"] == 0
    assert body["createdAt"]
    assert "school_year" not in body  # 只出 camelCase

    class_id = body["id"]
    fetched = client.get(f"/api/v1/classes/{class_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == class_id

    patched = client.patch(
        f"/api/v1/classes/{class_id}",
        json={"expectedRevision": 0, "name": "七年级一班（改）"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "七年级一班（改）"
    assert patched.json()["revision"] == 1

    archived = client.post(
        f"/api/v1/classes/{class_id}/archive", json={"expectedRevision": 1}
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["revision"] == 2

    # 归档班级仍可读
    still_readable = client.get(f"/api/v1/classes/{class_id}")
    assert still_readable.status_code == 200
    assert still_readable.json()["status"] == "archived"

    restored = client.post(
        f"/api/v1/classes/{class_id}/restore", json={"expectedRevision": 2}
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
    assert restored.json()["revision"] == 3

    listed = client.get("/api/v1/classes?status=active")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == class_id


def test_class_code_conflict_within_school_year(harness: Harness) -> None:
    _create_class(harness, code="701", school_year="2026-2027")
    with pytest.raises(AppError) as err:
        _create_class(harness, code="701", school_year="2026-2027")
    assert err.value.code == CLASS_CODE_CONFLICT
    assert err.value.status_code == 409
    assert harness.count("classes") == 1

    other_year = _create_class(harness, code="701", school_year="2027-2028")
    assert other_year.school_year == "2027-2028"
    assert harness.count("classes") == 2


def test_class_update_revision_conflict_reports_current_revision(harness: Harness) -> None:
    created = _create_class(harness)
    harness.service.update_class(
        created.id, ClassUpdateRequest(expectedRevision=0, name="改名后")
    )
    with pytest.raises(AppError) as err:
        harness.service.update_class(
            created.id, ClassUpdateRequest(expectedRevision=0, name="再次改名")
        )
    assert err.value.code == REVISION_CONFLICT
    assert err.value.status_code == 409
    assert err.value.details == {"currentRevision": 1}

    with pytest.raises(AppError) as err2:
        harness.service.set_archived(
            created.id, ClassRevisionRequest(expectedRevision=0), archived=True
        )
    assert err2.value.code == REVISION_CONFLICT
    assert err2.value.details == {"currentRevision": 1}


def test_class_list_status_filter_and_paging(harness: Harness) -> None:
    first = _create_class(harness, code="701")
    _create_class(harness, code="702")
    harness.service.set_archived(
        first.id, ClassRevisionRequest(expectedRevision=0), archived=True
    )

    active = harness.service.list_classes(status="active")
    assert active.total == 1 and active.items[0].code == "702"
    archived = harness.service.list_classes(status="archived", offset=0, limit=1)
    assert archived.total == 1 and archived.items[0].code == "701"
    every = harness.service.list_classes()
    assert every.total == 2 and len(every.items) == 2

    with pytest.raises(AppError) as err:
        harness.service.list_classes(status="bogus")
    assert err.value.status_code == 422


def test_class_student_count_counts_active_memberships_only(harness: Harness) -> None:
    class_a = _create_class(harness, code="701")
    class_b = _create_class(harness, code="702")
    _create_student(harness, "李四", "0013")  # 无班级，不应计入任何班
    from_a = harness.service.create_student(
        StudentCreateRequest(
            name="张三", studentNo="0012", classId=class_a.id, joinedOn="2025-09-01"
        )
    )
    harness.service.create_student(
        StudentCreateRequest(name="王五", studentNo="0014", classId=class_a.id)
    )
    harness.service.create_student(
        StudentCreateRequest(name="赵六", studentNo="0015", classId=class_a.id)
    )
    assert harness.service.get_class(class_a.id).student_count == 3
    assert harness.service.get_class(class_b.id).student_count == 0

    harness.service.transfer_student(
        from_a.id,
        MembershipTransferRequest(
            expectedStudentRevision=0,
            fromClassId=class_a.id,
            toClassId=class_b.id,
            movedOn="2026-03-01",
        ),
    )
    assert harness.service.get_class(class_a.id).student_count == 2
    assert harness.service.get_class(class_b.id).student_count == 1


def test_archived_class_rejects_new_roster_import(harness: Harness) -> None:
    created = _create_class(harness)
    harness.service.set_archived(
        created.id, ClassRevisionRequest(expectedRevision=0), archived=True
    )
    content = "学号,姓名\n0012,张三\n".encode("utf-8")
    with pytest.raises(AppError) as err:
        harness.service.create_roster_import(
            class_id=created.id,
            file_name="roster.csv",
            content=content,
            media_type="text/csv",
        )
    assert err.value.code == CLASS_ARCHIVED
    assert err.value.status_code == 409
    assert harness.count("roster_imports") == 0
    assert harness.count("file_assets") == 0


def test_missing_class_and_student_return_404(harness: Harness) -> None:
    with pytest.raises(AppError) as err:
        harness.service.get_class("missing")
    assert err.value.status_code == 404
    with pytest.raises(AppError) as err2:
        harness.service.get_student("missing")
    assert err2.value.status_code == 404


# --------------------------------------------------------------------------- 学生


def test_student_create_keeps_leading_zero_null_no_and_duplicate_names(harness: Harness) -> None:
    numbered = _create_student(harness, "张三", "0012")
    assert numbered.student_no == "0012"
    assert harness.service.get_student(numbered.id).student_no == "0012"
    assert harness.scalar("SELECT student_no FROM students WHERE id = ?", (numbered.id,)) == "0012"

    without_no = _create_student(harness, "李四")
    assert without_no.student_no is None
    assert harness.service.get_student(without_no.id).student_no is None

    # 同名可建（姓名不是主键，只提示不合并）
    first = _create_student(harness, "王五")
    second = _create_student(harness, "王五")
    assert first.id != second.id
    assert harness.count("students", "name = ?", ("王五",)) == 2


def test_student_no_conflict_returns_409(harness: Harness) -> None:
    _create_student(harness, "张三", "0012")
    with pytest.raises(AppError) as err:
        _create_student(harness, "张三丰", "0012")
    assert err.value.code == STUDENT_NO_CONFLICT
    assert err.value.status_code == 409
    assert harness.count("students") == 1


def test_student_update_revision_conflict_and_no_op(harness: Harness) -> None:
    student = _create_student(harness, "张三", "0012")
    renamed = harness.service.update_student(
        student.id, StudentUpdateRequest(expectedRevision=0, name="张三丰")
    )
    assert renamed.name == "张三丰"
    assert renamed.revision == 1

    with pytest.raises(AppError) as err:
        harness.service.update_student(
            student.id, StudentUpdateRequest(expectedRevision=0, studentNo="0013")
        )
    assert err.value.code == REVISION_CONFLICT
    assert err.value.details == {"currentRevision": 1}

    # 只给 expectedRevision（无字段变更）：不改数据、不递增
    unchanged = harness.service.update_student(
        student.id, StudentUpdateRequest(expectedRevision=1)
    )
    assert unchanged.revision == 1 and unchanged.name == "张三丰"

    # 学号改为已存在的学号 → 409
    _create_student(harness, "李四", "0099")
    with pytest.raises(AppError) as err2:
        harness.service.update_student(
            student.id, StudentUpdateRequest(expectedRevision=1, studentNo="0099")
        )
    assert err2.value.code == STUDENT_NO_CONFLICT
    assert harness.service.get_student(student.id).revision == 1


def test_student_list_fuzzy_query_and_paging(harness: Harness) -> None:
    _create_student(harness, "张三", "0012")
    _create_student(harness, "张小明", "0013")
    _create_student(harness, "李四", "0099")

    by_name = harness.service.list_students(q="张")
    assert by_name.total == 2
    assert {item.name for item in by_name.items} == {"张三", "张小明"}

    by_no = harness.service.list_students(q="001")
    assert by_no.total == 2
    assert {item.student_no for item in by_no.items} == {"0012", "0013"}

    paged = harness.service.list_students(offset=1, limit=1)
    assert paged.total == 3 and len(paged.items) == 1 and paged.offset == 1

    assert harness.service.list_students(q="不存在").total == 0
    with pytest.raises(AppError):
        harness.service.list_students(limit=0)


# --------------------------------------------------------------------------- 归属与转班


def test_create_student_with_class_creates_active_membership(harness: Harness) -> None:
    created = _create_class(harness)
    student = harness.service.create_student(
        StudentCreateRequest(name="张三", studentNo="0012", classId=created.id, joinedOn="2026-08-31")
    )
    assert len(student.memberships) == 1
    membership = student.memberships[0]
    assert membership.class_id == created.id
    assert membership.class_name == created.name
    assert membership.joined_on == "2026-08-31"
    assert membership.left_on is None

    members = harness.service.list_class_students(created.id)
    assert members.total == 1 and members.items[0].student_no == "0012"


def test_transfer_keeps_history_and_repeat_semantics(harness: Harness) -> None:
    class_a = _create_class(harness, code="701")
    class_b = _create_class(harness, code="702")
    student = harness.service.create_student(
        StudentCreateRequest(name="张三", studentNo="0012", classId=class_a.id, joinedOn="2025-09-01")
    )

    moved = harness.service.transfer_student(
        student.id,
        MembershipTransferRequest(
            expectedStudentRevision=0,
            fromClassId=class_a.id,
            toClassId=class_b.id,
            movedOn="2026-03-01",
        ),
    )
    assert moved.revision == 1
    assert len(moved.memberships) == 2
    old, new = moved.memberships
    assert old.class_id == class_a.id and old.left_on == "2026-03-01" and old.joined_on == "2025-09-01"
    assert new.class_id == class_b.id and new.left_on is None and new.joined_on == "2026-03-01"

    # 同一载荷（学生 revision 已变）→ 乐观锁冲突，不产生新归属
    with pytest.raises(AppError) as err:
        harness.service.transfer_student(
            student.id,
            MembershipTransferRequest(
                expectedStudentRevision=0,
                fromClassId=class_a.id,
                toClassId=class_b.id,
                movedOn="2026-03-01",
            ),
        )
    assert err.value.code == REVISION_CONFLICT
    assert harness.count("class_memberships") == 2

    # 用新 revision 重复转班：来源班已无活跃归属 → 422，不静默无操作
    with pytest.raises(AppError) as err2:
        harness.service.transfer_student(
            student.id,
            MembershipTransferRequest(
                expectedStudentRevision=1,
                fromClassId=class_a.id,
                toClassId=class_b.id,
                movedOn="2026-03-02",
            ),
        )
    assert err2.value.status_code == 422
    assert harness.count("class_memberships") == 2
    assert harness.count("class_memberships", "left_on IS NOT NULL") == 1

    assert harness.service.list_class_students(class_a.id).total == 0
    assert harness.service.list_class_students(class_b.id).total == 1


def test_transfer_rejects_same_class_and_archived_target(harness: Harness) -> None:
    class_a = _create_class(harness, code="701")
    class_b = _create_class(harness, code="702")
    student = harness.service.create_student(
        StudentCreateRequest(name="张三", studentNo="0012", classId=class_a.id)
    )
    with pytest.raises(AppError) as err:
        harness.service.transfer_student(
            student.id,
            MembershipTransferRequest(
                expectedStudentRevision=0,
                fromClassId=class_a.id,
                toClassId=class_a.id,
                movedOn="2026-03-01",
            ),
        )
    assert err.value.status_code == 422

    harness.service.set_archived(
        class_b.id, ClassRevisionRequest(expectedRevision=0), archived=True
    )
    with pytest.raises(AppError) as err2:
        harness.service.transfer_student(
            student.id,
            MembershipTransferRequest(
                expectedStudentRevision=0,
                fromClassId=class_a.id,
                toClassId=class_b.id,
                movedOn="2026-03-01",
            ),
        )
    assert err2.value.code == CLASS_ARCHIVED
    assert harness.count("class_memberships") == 1


def test_transfer_before_join_date_is_rejected(harness: Harness) -> None:
    class_a = _create_class(harness, code="701")
    class_b = _create_class(harness, code="702")
    student = harness.service.create_student(
        StudentCreateRequest(
            name="张三", studentNo="0012", classId=class_a.id, joinedOn="2026-02-01"
        )
    )
    with pytest.raises(AppError) as err:
        harness.service.transfer_student(
            student.id,
            MembershipTransferRequest(
                expectedStudentRevision=0,
                fromClassId=class_a.id,
                toClassId=class_b.id,
                movedOn="2026-01-01",
            ),
        )
    assert err.value.status_code == 422
    assert harness.count("class_memberships") == 1
    assert harness.service.get_student(student.id).revision == 0


def test_membership_insert_is_idempotent_within_class(harness: Harness) -> None:
    created = _create_class(harness)
    repository = StudentRepository(harness.catalog)
    student = repository.create(name="张三", student_no="0012")

    with harness.catalog.write_transaction() as conn:
        first, created_first = repository.insert_membership_in(
            conn, class_id=created.id, student_id=student.id, joined_on="2026-09-01"
        )
    assert created_first is True
    with harness.catalog.write_transaction() as conn:
        # 同班同学生再次插入：幂等跳过，不新建行、不报错
        second, created_second = repository.insert_membership_in(
            conn, class_id=created.id, student_id=student.id, joined_on="2026-09-02"
        )
    assert created_second is False
    assert second.membership_id == first.membership_id
    assert harness.count("class_memberships") == 1


# --------------------------------------------------------------------------- 路由与施测占位


def test_route_without_service_returns_503(tmp_path: Path) -> None:
    app = FastAPI()
    app.state.roster_service = None
    _install_error_handlers(app)
    app.include_router(roster_route.router, prefix="/api/v1")
    with TestClient(app, base_url="http://127.0.0.1:8001") as test_client:
        response = test_client.get("/api/v1/classes")
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert body["retryable"] is True


def test_route_invalid_query_params_return_422_with_fields(client: TestClient) -> None:
    response = client.get("/api/v1/classes?limit=0")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INVALID_REQUEST"
    assert body["details"]["fields"]

    bogus = client.get("/api/v1/classes?status=bogus")
    assert bogus.status_code == 422
    assert bogus.json()["code"] == "INVALID_REQUEST"


def test_route_student_flow(client: TestClient) -> None:
    class_id = client.post("/api/v1/classes", json=_class_payload()).json()["id"]
    created = client.post(
        "/api/v1/students",
        json={"name": "张三", "studentNo": "0012", "classId": class_id},
    )
    assert created.status_code == 201, created.text
    student = created.json()
    assert student["studentNo"] == "0012"
    assert student["memberships"][0]["classId"] == class_id

    fetched = client.get(f"/api/v1/students/{student['id']}")
    assert fetched.status_code == 200 and fetched.json()["studentNo"] == "0012"

    listed = client.get("/api/v1/students?q=0012")
    assert listed.status_code == 200 and listed.json()["total"] == 1

    roster = client.get(f"/api/v1/classes/{class_id}/students")
    assert roster.status_code == 200 and roster.json()["total"] == 1

    patched = client.patch(
        f"/api/v1/students/{student['id']}",
        json={"expectedRevision": 0, "name": "张三丰"},
    )
    assert patched.status_code == 200 and patched.json()["name"] == "张三丰"

    conflict = client.post(
        "/api/v1/students", json={"name": "李四", "studentNo": "0012"}
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == STUDENT_NO_CONFLICT


def test_route_conflict_envelope_carries_current_revision(client: TestClient) -> None:
    class_id = client.post("/api/v1/classes", json=_class_payload()).json()["id"]
    client.patch(f"/api/v1/classes/{class_id}", json={"expectedRevision": 0, "name": "改了"})
    stale = client.patch(
        f"/api/v1/classes/{class_id}", json={"expectedRevision": 0, "name": "又改了"}
    )
    assert stale.status_code == 409
    body = stale.json()
    assert body["code"] == REVISION_CONFLICT
    assert body["details"]["currentRevision"] == 1


def test_confirm_already_confirmed_is_409(harness: Harness) -> None:
    """已确认批次再次确认（新 submissionId）→ 409 ROSTER_IMPORT_CONFIRMED。"""
    created = _create_class(harness)
    content = "学号,姓名\n0012,张三\n".encode("utf-8")
    view = harness.service.create_roster_import(
        class_id=created.id, file_name="roster.csv", content=content, media_type="text/csv"
    )
    harness.service.confirm_roster_import(
        view.import_id,
        RosterImportConfirmRequest(
            expectedRevision=view.revision,
            submissionId="confirm-1",
            identityMatches=[{"rowNo": 1, "action": "create"}],
        ),
    )
    with pytest.raises(AppError) as err:
        harness.service.confirm_roster_import(
            view.import_id,
            RosterImportConfirmRequest(
                expectedRevision=view.revision + 1,
                submissionId="confirm-2",
                identityMatches=[{"rowNo": 1, "action": "create"}],
            ),
        )
    assert err.value.code == ROSTER_IMPORT_CONFIRMED
    assert err.value.status_code == 409


def test_unavailable_paper_reader_raises_501() -> None:
    reader = UnavailablePaperReader()
    with pytest.raises(AppError) as err:
        reader.read_confirmed_paper_revision("paper-rev-1")
    assert err.value.code == PAPER_READER_UNAVAILABLE
    assert err.value.status_code == 501
