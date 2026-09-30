"""名单导入（TEACHING-LOOP B1 / T30-a，验收 A8）。

覆盖：CSV/XLSX 上传与自动/手工映射、预览持久化与六类建议（link/create/no_student_no/
name_mismatch/duplicate/conflict）、学号文本（``0012`` 不被改写）、确认决策校验（缺决定/
link 缺 studentId/create 带 studentId）、重复行未消歧零写入确认、整批回滚与恢复、
重放（同 submissionId 同载荷）、未出现学生不动、空表/坏表可读 422。

全部使用 ``tmp_path`` 隔离数据根；XLSX 用 openpyxl 现造；不联网、不读写正式数据。
"""

from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import roster as roster_route
from app.contracts.roster import (
    ROSTER_IDENTITY_UNRESOLVED,
    ROSTER_IMPORT_BLOCKING_ISSUES,
    ROSTER_MAPPING_INVALID,
    STUDENT_NO_CONFLICT,
    ClassCreateRequest,
    ClassRevisionRequest,
    MembershipTransferRequest,
    RosterImportConfirmRequest,
    RosterImportPatchRequest,
    StudentCreateRequest,
)
from app.core.exceptions import AppError
from app.core.sqlite import connect, now_iso
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.teaching.roster import (
    ROSTER_NAME_CONFLICT,
    ROSTER_ROW_DUPLICATE,
    RosterImportRepository,
)
from app.schemas.errors import error_response
from app.services.assets.store import AssetStore
from app.services.roster.service import build_roster_service


class Harness:
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
            return int(
                connection.execute(
                    f"SELECT COUNT(*) AS n FROM {table}{clause}", params
                ).fetchone()["n"]
            )
        finally:
            connection.close()


@pytest.fixture()
def harness(tmp_path: Path):
    instance = Harness(tmp_path)
    yield instance
    instance.close()


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
def client(harness: Harness):
    app = FastAPI()
    app.state.roster_service = harness.service
    _install_error_handlers(app)
    app.include_router(roster_route.router, prefix="/api/v1")
    with TestClient(app, base_url="http://127.0.0.1:8001") as test_client:
        yield test_client


# --------------------------------------------------------------------------- 夹具工具


def make_class(harness: Harness, code: str = "701"):
    return harness.service.create_class(
        ClassCreateRequest(
            code=code, name=f"七年级{code}班", schoolYear="2026-2027", gradeId="grade-7"
        )
    )


def make_student(
    harness: Harness,
    name: str,
    student_no: str | None = None,
    *,
    class_id: str | None = None,
):
    return harness.service.create_student(
        StudentCreateRequest(name=name, studentNo=student_no, classId=class_id)
    )


def csv_bytes(rows: list[list[str]], *, bom: bool = False) -> bytes:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    text = buffer.getvalue()
    return ("\ufeff" + text if bom else text).encode("utf-8")


def xlsx_bytes(sheets: dict[str, list[list[object]]]) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    first = True
    for name, rows in sheets.items():
        worksheet = workbook.active if first else workbook.create_sheet()
        worksheet.title = name
        first = False
        for row in rows:
            worksheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def upload(harness: Harness, class_id: str, *, content: bytes, file_name: str, **kwargs):
    return harness.service.create_roster_import(
        class_id=class_id,
        file_name=file_name,
        content=content,
        media_type=kwargs.pop("media_type", "text/csv"),
        **kwargs,
    )


def row_by_no(view, row_no: int):
    return next(row for row in view.rows if row.row_no == row_no)


def confirm(
    harness: Harness,
    import_id: str,
    *,
    expected_revision: int,
    submission_id: str,
    identity_matches: list[dict] | None = None,
):
    return harness.service.confirm_roster_import(
        import_id,
        RosterImportConfirmRequest(
            expectedRevision=expected_revision,
            submissionId=submission_id,
            identityMatches=identity_matches or [],
        ),
    )


# --------------------------------------------------------------------------- 上传与预览


def test_csv_import_auto_mapping_persists_preview(harness: Harness) -> None:
    created = make_class(harness)
    matches = make_student(harness, "张三", "0012")
    content = csv_bytes(
        [["学号", "姓名"], ["0012", "张三"], ["0013", "王五"]], bom=True
    )
    view = upload(harness, created.id, content=content, file_name="名单.csv")

    assert view.state == "reviewing"
    assert view.revision == 0
    assert view.class_id == created.id and view.class_name == created.name
    assert view.headers == ["学号", "姓名"]
    assert view.mapping == {"studentNo": "学号", "name": "姓名"}
    assert view.warnings == []
    assert view.file_asset.kind == "roster"
    assert view.file_asset.original_name == "名单.csv"
    assert view.file_asset.blob_key == f"blobs/{view.file_asset.sha256}"

    first, second = view.rows
    assert first.row_no == 1 and first.student_no == "0012"
    assert first.matched_student_id == matches.id
    assert first.matched_student_name == "张三"
    assert first.suggestion == "link"
    assert first.issues == []
    assert second.student_no == "0013"  # 前导零原样保留
    assert second.matched_student_id is None
    assert second.suggestion == "create"

    # 预览已持久化：重新读取得到同样的建议与问题
    reloaded = harness.service.get_roster_import(view.import_id)
    assert reloaded == view
    assert harness.count("roster_import_rows", "import_id = ?", (view.import_id,)) == 2
    assert harness.count("file_assets", "kind = 'roster'") == 1
    # 预览不建学生、不建归属
    assert harness.count("students") == 1
    assert harness.count("class_memberships") == 0

    listed = harness.service.list_roster_imports(class_id=created.id)
    assert listed.total == 1
    assert listed.items[0].row_count == 2
    assert listed.items[0].blocking_issue_count == 0


def test_xlsx_manual_mapping_and_numeric_cells(harness: Harness) -> None:
    created = make_class(harness)
    content = xlsx_bytes(
        {"七年一班": [["编号", "学生姓名"], ["0012", "张三"], [13, "李四"]]}
    )
    view = harness.service.create_roster_import(
        class_id=created.id,
        file_name="名单.xlsx",
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        mapping={"studentNo": "编号", "name": "学生姓名"},
    )
    assert view.mapping == {"studentNo": "编号", "name": "学生姓名"}
    assert row_by_no(view, 1).student_no == "0012"  # 文本单元格前导零保留
    assert row_by_no(view, 2).student_no == "13"  # 数值单元格不出现 13.0
    assert row_by_no(view, 1).suggestion == "create"


def test_xlsx_sheet_selection_and_warning(harness: Harness) -> None:
    created = make_class(harness)
    content = xlsx_bytes(
        {
            "一班": [["学号", "姓名"], ["0012", "张三"]],
            "二班": [["学号", "姓名"], ["0013", "李四"]],
        }
    )
    default_view = upload(
        harness,
        created.id,
        content=content,
        file_name="名单.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert default_view.warnings and "一班" in default_view.warnings[0]
    assert row_by_no(default_view, 1).name == "张三"

    selected = upload(
        harness,
        created.id,
        content=content,
        file_name="名单.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        sheet_name="二班",
    )
    assert selected.warnings == []
    assert [row.name for row in selected.rows] == ["李四"]


def test_suggestion_classification_all_cases(harness: Harness) -> None:
    created = make_class(harness)
    matched = make_student(harness, "张三", "0012")
    make_student(harness, "赵六六", "0014")
    make_student(harness, "孙七")
    make_student(harness, "孙七")  # 同名两人 → conflict

    content = csv_bytes(
        [
            ["学号", "姓名"],
            ["0012", "张三"],  # link
            ["0013", "李四"],  # create
            ["", "王五"],  # no_student_no
            ["0014", "赵六"],  # name_mismatch
            ["0020", "周八"],  # duplicate（与下一行）
            ["0020", "周九"],  # duplicate（与上一行）
            ["", "孙七"],  # conflict
        ]
    )
    view = upload(harness, created.id, content=content, file_name="roster.csv")
    assert [row.suggestion for row in view.rows] == [
        "link",
        "create",
        "no_student_no",
        "name_mismatch",
        "duplicate",
        "duplicate",
        "conflict",
    ]
    # link 行已带命中学生；姓名不符行不自动改姓名
    assert row_by_no(view, 1).matched_student_id == matched.id
    mismatch = row_by_no(view, 4)
    assert mismatch.matched_student_id is not None
    assert any(
        issue.code == "ROSTER_ROW_INVALID" and issue.field == "name"
        for issue in mismatch.issues
    )
    # 两行互为重复：两侧都标 duplicate issue
    for row_no in (5, 6):
        assert any(
            issue.code == ROSTER_ROW_DUPLICATE and issue.row == row_no
            for issue in row_by_no(view, row_no).issues
        )
    conflict_row = row_by_no(view, 7)
    assert conflict_row.matched_student_id is None  # 不得静默选第一人
    assert any(issue.code == ROSTER_NAME_CONFLICT for issue in conflict_row.issues)
    # 批次级 issues 汇总阻断问题（第 5/6/7 行）
    assert {issue.row for issue in view.issues} == {5, 6, 7}

    summary = harness.service.list_roster_imports(class_id=created.id).items[0]
    assert summary.blocking_issue_count == 3
    assert RosterImportRepository(harness.catalog).blocking_issue_count(view.import_id) == 3


def test_patch_mapping_reanalyzes_and_rows_store_decisions(harness: Harness) -> None:
    created = make_class(harness)
    existing = make_student(harness, "张三", "0012")
    content = csv_bytes([["编号", "姓名"], ["0012", "张三"], ["0013", "李四"]])
    # 先只用姓名列映射：两行都是"无学号"
    view = upload(
        harness,
        created.id,
        content=content,
        file_name="roster.csv",
        mapping={"name": "姓名"},
    )
    assert all(row.suggestion == "no_student_no" for row in view.rows)
    assert all(row.student_no is None for row in view.rows)

    # 改映射后重算（行号不变、学号恢复、建议重算）
    repatched = harness.service.patch_roster_import(
        view.import_id,
        RosterImportPatchRequest(
            expectedRevision=view.revision,
            mapping={"name": "姓名", "studentNo": "编号"},
        ),
    )
    assert repatched.revision == view.revision + 1
    assert repatched.mapping == {"studentNo": "编号", "name": "姓名"}
    assert row_by_no(repatched, 1).suggestion == "link"
    assert row_by_no(repatched, 2).suggestion == "create"

    # 行决定持久化
    decided = harness.service.patch_roster_import(
        repatched.import_id,
        RosterImportPatchRequest(
            expectedRevision=repatched.revision,
            rows=[{"rowNo": 1, "decision": "link", "studentId": existing.id}],
        ),
    )
    assert row_by_no(decided, 1).decision == "link"
    assert row_by_no(decided, 1).matched_student_id == existing.id
    assert row_by_no(decided, 2).decision is None

    # 陈旧 revision → 409 + currentRevision
    with pytest.raises(AppError) as err:
        harness.service.patch_roster_import(
            view.import_id,
            RosterImportPatchRequest(expectedRevision=0, rows=[]),
        )
    assert err.value.code == "REVISION_CONFLICT"
    assert err.value.details == {"currentRevision": decided.revision}

    # 非法行决定：link 缺 studentId / create 带 studentId
    with pytest.raises(AppError) as err2:
        harness.service.patch_roster_import(
            decided.import_id,
            RosterImportPatchRequest(
                expectedRevision=decided.revision,
                rows=[{"rowNo": 2, "decision": "link"}],
            ),
        )
    assert err2.value.code == ROSTER_IDENTITY_UNRESOLVED
    assert err2.value.details["issues"][0]["row"] == 2
    with pytest.raises(AppError) as err3:
        harness.service.patch_roster_import(
            decided.import_id,
            RosterImportPatchRequest(
                expectedRevision=decided.revision,
                rows=[{"rowNo": 2, "decision": "create", "studentId": existing.id}],
            ),
        )
    assert err3.value.status_code == 422


# --------------------------------------------------------------------------- 确认


def test_confirm_success_counts_and_leaves_unlisted_students(harness: Harness) -> None:
    class_a = make_class(harness, code="701")
    class_b = make_class(harness, code="702")
    matched = make_student(harness, "张三", "0012", class_id=class_b.id)
    untouched = make_student(harness, "王五", class_id=class_a.id)
    unlisted = make_student(harness, "陈九", "0099", class_id=class_a.id)

    content = csv_bytes(
        [["学号", "姓名"], ["0012", "张三"], ["0013", "李四"], ["", "王五"]]
    )
    view = upload(harness, class_a.id, content=content, file_name="roster.csv")
    result = confirm(
        harness,
        view.import_id,
        expected_revision=view.revision,
        submission_id="confirm-ok",
        identity_matches=[
            {"rowNo": 1, "action": "link", "studentId": matched.id},
            {"rowNo": 2, "action": "create"},
            {"rowNo": 3, "action": "ignore"},
        ],
    )
    assert result.state == "confirmed"
    assert result.replayed is False
    assert result.ignored == [3]
    assert [(item.row_no, item.created_student) for item in result.applied] == [
        (1, False),
        (2, True),
    ]
    assert result.applied[0].created_membership is True
    assert result.applied[0].student_id == matched.id

    # 0012 未被改写（文本身份、姓名不变）
    reloaded_student = harness.service.get_student(matched.id)
    assert reloaded_student.student_no == "0012"
    assert reloaded_student.name == "张三"
    assert harness.count(
        "students", "student_no = ? AND name = ?", ("0012", "张三")
    ) == 1

    # 本批行涉及的归属都建立；未出现的学生不动
    roster = harness.service.list_class_students(class_a.id)
    assert roster.total == 4  # 王五、陈九、张三、李四
    assert {item.student_no for item in roster.items} == {"0012", "0013", "0099", None}
    kept = harness.service.get_student(untouched.id)
    assert kept.revision == 0
    assert len(kept.memberships) == 1 and kept.memberships[0].left_on is None
    assert harness.service.get_student(unlisted.id).memberships[0].left_on is None
    # 张三在 B 班的原归属保持活跃（转班不在名单确认范围内）
    assert harness.service.list_class_students(class_b.id).total == 1

    confirmed = harness.service.get_roster_import(view.import_id)
    assert confirmed.state == "confirmed"
    assert confirmed.revision == view.revision + 1
    assert [row.decision for row in confirmed.rows] == ["link", "create", "ignore"]


def test_confirm_without_decisions_is_422_per_row(harness: Harness) -> None:
    created = make_class(harness)
    make_student(harness, "张三", "0012")
    content = csv_bytes([["学号", "姓名"], ["0012", "张三"], ["0013", "李四"]])
    view = upload(harness, created.id, content=content, file_name="roster.csv")

    with pytest.raises(AppError) as err:
        confirm(
            harness,
            view.import_id,
            expected_revision=view.revision,
            submission_id="confirm-missing",
        )
    assert err.value.code == ROSTER_IDENTITY_UNRESOLVED
    assert err.value.status_code == 422
    assert [issue["row"] for issue in err.value.details["issues"]] == [1, 2]
    # 零写入
    assert harness.count("students") == 1
    assert harness.count("class_memberships") == 0
    assert harness.count("command_submissions") == 0
    assert harness.service.get_roster_import(view.import_id).state == "reviewing"


def test_confirm_duplicate_unresolved_is_422_zero_writes(harness: Harness) -> None:
    created = make_class(harness)
    existing = make_student(harness, "张三", "0012")
    content = csv_bytes(
        [["学号", "姓名"], ["0012", "张三"], ["0012", "张三"]]
    )
    view = upload(harness, created.id, content=content, file_name="roster.csv")
    assert [row.suggestion for row in view.rows] == ["duplicate", "duplicate"]

    with pytest.raises(AppError) as err:
        confirm(
            harness,
            view.import_id,
            expected_revision=view.revision,
            submission_id="confirm-dup-1",
        )
    assert err.value.code == ROSTER_IMPORT_BLOCKING_ISSUES
    assert {issue["row"] for issue in err.value.details["issues"]} == {1, 2}
    assert harness.count("class_memberships") == 0
    assert harness.count("command_submissions") == 0
    assert harness.service.get_roster_import(view.import_id).revision == view.revision

    # 两行都 link 到同一身份仍属未消歧 → 阻断
    with pytest.raises(AppError) as err2:
        confirm(
            harness,
            view.import_id,
            expected_revision=view.revision,
            submission_id="confirm-dup-2",
            identity_matches=[
                {"rowNo": 1, "action": "link", "studentId": existing.id},
                {"rowNo": 2, "action": "link", "studentId": existing.id},
            ],
        )
    assert err2.value.code == ROSTER_IMPORT_BLOCKING_ISSUES
    assert harness.count("class_memberships") == 0

    # 正确消歧（一行 link、一行 ignore）后成功，且只建立一条归属
    resolved = confirm(
        harness,
        view.import_id,
        expected_revision=view.revision,
        submission_id="confirm-dup-3",
        identity_matches=[
            {"rowNo": 1, "action": "link", "studentId": existing.id},
            {"rowNo": 2, "action": "ignore"},
        ],
    )
    assert resolved.applied[0].created_membership is True
    assert resolved.ignored == [2]
    assert harness.count("class_memberships") == 1


def test_confirm_decision_shape_errors_are_422(harness: Harness) -> None:
    created = make_class(harness)
    existing = make_student(harness, "张三", "0012")
    content = csv_bytes([["学号", "姓名"], ["0012", "张三"], ["0013", "李四"]])
    view = upload(harness, created.id, content=content, file_name="roster.csv")

    with pytest.raises(AppError) as err:
        confirm(
            harness,
            view.import_id,
            expected_revision=view.revision,
            submission_id="shape-1",
            identity_matches=[
                {"rowNo": 1, "action": "link"},
                {"rowNo": 2, "action": "ignore"},
            ],
        )
    assert err.value.code == ROSTER_IDENTITY_UNRESOLVED
    assert err.value.details["issues"][0]["row"] == 1

    with pytest.raises(AppError) as err2:
        confirm(
            harness,
            view.import_id,
            expected_revision=view.revision,
            submission_id="shape-2",
            identity_matches=[
                {"rowNo": 1, "action": "link", "studentId": "missing-student"},
                {"rowNo": 2, "action": "ignore"},
            ],
        )
    assert err2.value.code == ROSTER_IDENTITY_UNRESOLVED

    with pytest.raises(AppError) as err3:
        confirm(
            harness,
            view.import_id,
            expected_revision=view.revision,
            submission_id="shape-3",
            identity_matches=[
                {"rowNo": 1, "action": "create", "studentId": existing.id},
                {"rowNo": 2, "action": "ignore"},
            ],
        )
    assert err3.value.status_code == 422
    assert err3.value.code == "INVALID_REQUEST"

    with pytest.raises(AppError) as err4:
        confirm(
            harness,
            view.import_id,
            expected_revision=view.revision,
            submission_id="shape-4",
            identity_matches=[
                {"rowNo": 1, "action": "ignore", "studentId": existing.id},
                {"rowNo": 2, "action": "ignore"},
            ],
        )
    assert err4.value.status_code == 422

    # 所有失败路径零写入
    assert harness.count("students") == 1
    assert harness.count("class_memberships") == 0
    assert harness.count("command_submissions") == 0


def test_confirm_replay_returns_original_result(harness: Harness) -> None:
    created = make_class(harness)
    content = csv_bytes([["学号", "姓名"], ["0013", "李四"]])
    view = upload(harness, created.id, content=content, file_name="roster.csv")
    payload = {
        "expected_revision": view.revision,
        "submission_id": "replay-1",
        "identity_matches": [{"rowNo": 1, "action": "create"}],
    }
    first = confirm(harness, view.import_id, **payload)
    assert first.replayed is False and first.applied[0].created_student is True
    students_after_first = harness.count("students")
    memberships_after_first = harness.count("class_memberships")

    replay = confirm(harness, view.import_id, **payload)
    assert replay.replayed is True
    assert replay.applied == first.applied
    assert replay.ignored == first.ignored
    assert harness.count("students") == students_after_first
    assert harness.count("class_memberships") == memberships_after_first

    # 同 submissionId 不同载荷 → 409 SUBMISSION_CONFLICT
    with pytest.raises(AppError) as err:
        confirm(
            harness,
            view.import_id,
            expected_revision=view.revision,
            submission_id="replay-1",
            identity_matches=[{"rowNo": 1, "action": "ignore"}],
        )
    assert err.value.code == "SUBMISSION_CONFLICT"
    assert err.value.status_code == 409
    assert harness.count("students") == students_after_first


def test_confirm_midway_failure_rolls_back_whole_batch(harness: Harness) -> None:
    created = make_class(harness)
    content = csv_bytes([["学号", "姓名"], ["0012", "张三"], ["0099", "李四"]])
    view = upload(harness, created.id, content=content, file_name="roster.csv")
    assert [row.suggestion for row in view.rows] == ["create", "create"]

    # 预览之后该学号在库中已出现：第 2 行 create 必然失败（第 1 行已执行 → 必须整批回滚）
    late = make_student(harness, "李四", "0099")
    with pytest.raises(AppError) as err:
        confirm(
            harness,
            view.import_id,
            expected_revision=view.revision,
            submission_id="rollback-1",
            identity_matches=[
                {"rowNo": 1, "action": "create"},
                {"rowNo": 2, "action": "create"},
            ],
        )
    assert err.value.code == STUDENT_NO_CONFLICT
    assert err.value.status_code == 409
    assert err.value.details["issues"][0]["row"] == 2
    assert harness.count("students") == 1  # 只有预告存在的那名
    assert harness.count("class_memberships") == 0
    assert harness.count("command_submissions") == 0
    assert harness.service.get_roster_import(view.import_id).state == "reviewing"

    # 修正决定后可成功（第 2 行改 link）
    fixed = confirm(
        harness,
        view.import_id,
        expected_revision=view.revision,
        submission_id="rollback-2",
        identity_matches=[
            {"rowNo": 1, "action": "create"},
            {"rowNo": 2, "action": "link", "studentId": late.id},
        ],
    )
    assert [item.created_student for item in fixed.applied] == [True, False]
    assert harness.count("students") == 2
    assert harness.count("class_memberships") == 2


def test_unlisted_students_and_history_are_not_touched(harness: Harness) -> None:
    class_a = make_class(harness)
    class_b = make_class(harness, code="702")
    left_behind = make_student(harness, "王五", class_id=class_a.id)
    moved_before = make_student(harness, "赵六", "0014", class_id=class_b.id)
    harness.service.transfer_student(
        moved_before.id,
        MembershipTransferRequest(
            expectedStudentRevision=0,
            fromClassId=class_b.id,
            toClassId=class_a.id,
            movedOn=date.today().isoformat(),
        ),
    )
    history_before = harness.service.get_student(moved_before.id).memberships

    content = csv_bytes([["学号", "姓名"], ["0013", "李四"]])
    view = upload(harness, class_a.id, content=content, file_name="roster.csv")
    confirm(
        harness,
        view.import_id,
        expected_revision=view.revision,
        submission_id="untouched-1",
        identity_matches=[{"rowNo": 1, "action": "create"}],
    )
    after = harness.service.get_student(moved_before.id)
    assert [(m.membership_id, m.left_on) for m in after.memberships] == [
        (m.membership_id, m.left_on) for m in history_before
    ]
    assert harness.service.get_student(left_behind.id).memberships[0].left_on is None
    assert harness.service.list_class_students(class_a.id).total == 3
    assert harness.service.list_class_students(class_b.id).total == 0


def test_empty_headerless_and_bad_tables_are_readable_422(harness: Harness) -> None:
    created = make_class(harness)
    cases: list[tuple[bytes, str, str | None, dict | None]] = [
        (b"", "empty.csv", None, None),
        (csv_bytes([["学号", "姓名"]]), "header-only.csv", None, None),
        (csv_bytes([["学号", "班级"], ["0012", "一班"]]), "no-name.csv", None, None),
        (csv_bytes([["学号", "姓名"], ["0012", "张三"]]), "bad-map.csv", None, {"foo": "学号"}),
        (
            csv_bytes([["学号", "姓名"], ["0012", "张三"]]),
            "missing-header.csv",
            None,
            {"name": "不存在"},
        ),
        (b"not a real xlsx", "broken.xlsx", None, None),
    ]
    for content, file_name, sheet_name, mapping in cases:
        with pytest.raises(AppError) as err:
            harness.service.create_roster_import(
                class_id=created.id,
                file_name=file_name,
                content=content,
                media_type="application/octet-stream",
                mapping=mapping,
                sheet_name=sheet_name,
            )
        assert err.value.status_code == 422, file_name
        assert err.value.code in (ROSTER_MAPPING_INVALID, "TABLE_PARSE_FAILED"), (
            file_name,
            err.value.code,
        )
        assert str(err.value).strip(), file_name
    assert harness.count("roster_imports") == 0
    assert harness.count("file_assets") == 0


# --------------------------------------------------------------------------- 路由


def test_roster_routes_upload_patch_confirm_and_replay(client: TestClient) -> None:
    class_id = client.post(
        "/api/v1/classes",
        json={"code": "701", "name": "七年级一班", "schoolYear": "2026-2027", "gradeId": "g7"},
    ).json()["id"]
    uploaded = client.post(
        f"/api/v1/classes/{class_id}/roster-imports",
        files={"file": ("名单.csv", csv_bytes([["学号", "姓名"], ["0012", "张三"]]), "text/csv")},
    )
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    assert view["classId"] == class_id
    assert view["state"] == "reviewing"
    assert view["mapping"] == {"studentNo": "学号", "name": "姓名"}
    assert view["fileAsset"]["kind"] == "roster"
    assert view["rows"][0]["rowNo"] == 1
    assert view["rows"][0]["studentNo"] == "0012"
    assert view["rows"][0]["suggestion"] == "create"

    listed = client.get(f"/api/v1/roster-imports?classId={class_id}")
    assert listed.status_code == 200 and listed.json()["total"] == 1

    fetched = client.get(f"/api/v1/roster-imports/{view['importId']}")
    assert fetched.status_code == 200

    patched = client.patch(
        f"/api/v1/roster-imports/{view['importId']}",
        json={
            "expectedRevision": view["revision"],
            "rows": [{"rowNo": 1, "decision": "create"}],
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["rows"][0]["decision"] == "create"

    body = {
        "expectedRevision": patched.json()["revision"],
        "submissionId": "http-confirm-1",
        "identityMatches": [{"rowNo": 1, "action": "create"}],
    }
    confirmed = client.post(
        f"/api/v1/roster-imports/{view['importId']}/confirm", json=body
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["state"] == "confirmed"
    assert confirmed.json()["replayed"] is False
    assert confirmed.json()["applied"][0]["createdStudent"] is True

    replay = client.post(
        f"/api/v1/roster-imports/{view['importId']}/confirm", json=body
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True

    missing = client.get("/api/v1/roster-imports/not-there")
    assert missing.status_code == 404
    assert missing.json()["code"] == "ROSTER_IMPORT_NOT_FOUND"

    no_file = client.post(f"/api/v1/classes/{class_id}/roster-imports", data={"x": "1"})
    assert no_file.status_code == 415  # 非 multipart 明确拒绝


def test_roster_upload_limit_is_413(client: TestClient) -> None:
    class_id = client.post(
        "/api/v1/classes",
        json={"code": "701", "name": "七年级一班", "schoolYear": "2026-2027", "gradeId": "g7"},
    ).json()["id"]
    too_big = b"x" * (10 * 1024 * 1024 + 4096 + 1)
    response = client.post(
        f"/api/v1/classes/{class_id}/roster-imports",
        content=too_big,
        headers={"content-type": "application/octet-stream"},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "DOCUMENT_TOO_LARGE"


def test_batch_state_transition_and_editable_guard(harness: Harness) -> None:
    created = make_class(harness)
    content = csv_bytes([["学号", "姓名"], ["0013", "李四"]])
    view = upload(harness, created.id, content=content, file_name="roster.csv")

    repository = RosterImportRepository(harness.catalog)
    updated = repository.set_state(view.import_id, state="failed", error_code="EXTRACT_FAILED")
    assert updated.state == "failed"
    assert updated.error_code == "EXTRACT_FAILED"
    assert updated.revision == view.revision + 1

    # 失败批次不可再修改或确认（状态守卫）
    with pytest.raises(AppError) as err:
        harness.service.patch_roster_import(
            view.import_id,
            RosterImportPatchRequest(
                expectedRevision=updated.revision,
                rows=[{"rowNo": 1, "decision": "create"}],
            ),
        )
    assert err.value.status_code == 409
    with pytest.raises(AppError) as err2:
        confirm(
            harness,
            view.import_id,
            expected_revision=updated.revision,
            submission_id="failed-1",
            identity_matches=[{"rowNo": 1, "action": "create"}],
        )
    assert err2.value.status_code == 409
    assert harness.count("students") == 0


def test_confirm_rejected_for_archived_class(harness: Harness) -> None:
    created = make_class(harness)
    content = csv_bytes([["学号", "姓名"], ["0013", "李四"]])
    view = upload(harness, created.id, content=content, file_name="roster.csv")

    harness.service.set_archived(
        created.id, ClassRevisionRequest(expectedRevision=0), archived=True
    )
    with pytest.raises(AppError) as err:
        confirm(
            harness,
            view.import_id,
            expected_revision=view.revision,
            submission_id="archived-1",
            identity_matches=[{"rowNo": 1, "action": "create"}],
        )
    assert err.value.code == "CLASS_ARCHIVED"
    assert err.value.status_code == 409
    assert harness.count("students") == 0
    assert harness.count("class_memberships") == 0
    assert harness.count("command_submissions") == 0

    harness.service.set_archived(
        created.id, ClassRevisionRequest(expectedRevision=1), archived=False
    )
    ok = confirm(
        harness,
        view.import_id,
        expected_revision=view.revision,
        submission_id="archived-2",
        identity_matches=[{"rowNo": 1, "action": "create"}],
    )
    assert ok.state == "confirmed"


def test_confirm_joined_on_is_confirm_date(harness: Harness) -> None:
    created = make_class(harness)
    content = csv_bytes([["学号", "姓名"], ["0013", "李四"]])
    view = upload(harness, created.id, content=content, file_name="roster.csv")
    confirm(
        harness,
        view.import_id,
        expected_revision=view.revision,
        submission_id="joined-1",
        identity_matches=[{"rowNo": 1, "action": "create"}],
    )
    membership = harness.service.list_class_students(created.id).items[0].memberships[0]
    assert membership.joined_on == now_iso()[:10]
    assert membership.left_on is None
