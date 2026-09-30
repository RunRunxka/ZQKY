"""名单服务门面（TEACHING-LOOP B1 / T30-a）。

装配：``build_roster_service(catalog, *, asset_store, file_assets, job_engine=None)``；
所有 SQL 只经 ``TeachingCatalog`` 的 ``write_transaction()`` / ``read_connection()``，
文件解析统一走 ``app/services/tabular.py``，资产本体走 ``AssetStore``，登记走
``FileAssetsRepository``；本批不调用模型、不联网（``job_engine`` 仅预留）。

关键语义（与冻结契约 ``app/contracts/roster.py`` 一致）：

- **学号是文本**：``0012`` 逐字保存与回读，任何路径都不做数值化；
- **上传**：解析 → 规范化 → 匹配与问题检测 → 一个写事务登记资产 + 批次（``reviewing``）+ 预览行；
  解析/校验失败不产生批次（不落任何业务行）；
- **确认**：走 B0 提交幂等（``operation="roster.import.confirm"``，同 ``submissionId`` 同载荷重放
  返回原结果且不再执行）；apply 内做状态/修订校验、逐行决定校验、阻断问题校验，按行序执行
  link/create，任一失败整批回滚（含提交登记）；``ignore`` 不动任何数据；
- **转班**：同一事务旧归属置 ``leftOn`` + 目标班新增归属；历史与未出现的学生一律不动。
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date
from typing import Any

from app.contracts.roster import (
    CLASS_ARCHIVED,
    ROSTER_DECISIONS,
    ROSTER_IDENTITY_UNRESOLVED,
    ROSTER_IMPORT_BLOCKING_ISSUES,
    ROSTER_IMPORT_CONFIRMED,
    ROSTER_ROW_INVALID,
    STUDENT_NO_CONFLICT,
    ClassCreateRequest,
    ClassList,
    ClassRevisionRequest,
    ClassUpdateRequest,
    ClassView,
    MembershipTransferRequest,
    RosterAppliedRow,
    RosterImportConfirmRequest,
    RosterImportConfirmResult,
    RosterImportList,
    RosterImportPatchRequest,
    RosterImportRowPatch,
    RosterImportRowView,
    RosterImportView,
    RosterIdentityMatch,
    StudentCreateRequest,
    StudentList,
    StudentUpdateRequest,
    StudentView,
)
from app.contracts.teaching_loop import (
    REVISION_CONFLICT,
    AssetRef,
    ErrorIssue,
    error_details,
)
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.teaching.classes import ClassRecord, ClassRepository
from app.repositories.teaching.roster import (
    BLOCKING_ISSUE_CODES,
    RosterImportRecord,
    RosterImportRepository,
    RosterRowPayload,
    RowDecision,
)
from app.repositories.teaching.students import StudentRepository
from app.services.assets.store import AssetStore
from app.services.roster import imports as row_analysis
from app.services.roster.imports import AnalyzedRow, ExtractedRow
from app.services.submissions.service import execute_command, make_command
from app.services.tabular import read_table

MAX_PAGE_LIMIT = 200
DEFAULT_MEDIA_TYPE = "application/octet-stream"
#: 可编辑（尚未确认）的批次状态
EDITABLE_IMPORT_STATES: frozenset[str] = frozenset({"uploaded", "reviewing"})


# --------------------------------------------------------------------------- 小工具


def _page(offset: int, limit: int) -> tuple[int, int]:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise _invalid("offset 必须是不小于 0 的整数。", fields=["offset"])
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 1
        or limit > MAX_PAGE_LIMIT
    ):
        raise _invalid(f"limit 必须是 1..{MAX_PAGE_LIMIT} 的整数。", fields=["limit"])
    return offset, limit


def _invalid(message: str, *, fields: list[str] | None = None) -> AppError:
    return AppError(
        message,
        code="INVALID_REQUEST",
        status_code=422,
        details=error_details(fields=fields) if fields else None,
    )


def _issue(
    row_no: int | None,
    *,
    code: str,
    message: str,
    field: str | None = None,
) -> ErrorIssue:
    return ErrorIssue(row=row_no, column=field, field=field, code=code, message=message)


def _issue_error(
    message: str, *, code: str, status_code: int, issues: list[ErrorIssue]
) -> AppError:
    """``details.issues`` 统一用共享 helper 序列化（``ErrorIssue`` 形状只有一份来源）。"""
    return AppError(
        message,
        code=code,
        status_code=status_code,
        details=error_details(issues=list(issues)),
    )


def _clean_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。", fields=[field])
    return value.strip()


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _clean_text(value, field=field)


def _optional_student_no(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _invalid("studentNo 必须是字符串或 null。", fields=["studentNo"])
    text = value.strip()
    if not text:
        raise _invalid(
            "studentNo 不能为空字符串；本批不支持清空学号。", fields=["studentNo"]
        )
    if len(text) > row_analysis.MAX_STUDENT_NO_CHARS:
        raise _invalid(
            f"studentNo 不能超过 {row_analysis.MAX_STUDENT_NO_CHARS} 字。",
            fields=["studentNo"],
        )
    return text


def _require_date(value: object, *, field: str) -> str:
    text = _clean_text(value, field=field)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise _invalid(f"{field} 必须是 YYYY-MM-DD 日期。", fields=[field]) from exc
    return text


def _today() -> str:
    return now_iso()[:10]


def _check_revision(current: int, expected: int) -> None:
    if current != expected:
        raise AppError(
            "数据已被其他操作更新，请刷新后重试。",
            code=REVISION_CONFLICT,
            status_code=409,
            details=error_details(current_revision=current),
        )


def _reject_archived(record: ClassRecord, *, action: str) -> None:
    if record.status == "archived":
        raise AppError(
            f"班级已归档，不能{action}；请先恢复班级。",
            code=CLASS_ARCHIVED,
            status_code=409,
        )


def _conflict(message: str) -> AppError:
    """批次状态不允许操作（未确认批次可改；已确认见 ``ROSTER_IMPORT_CONFIRMED``）。"""
    return AppError(message, code="INVALID_REQUEST", status_code=409)


def _resolve_decision(
    *,
    action: str | None,
    student_id: str | None,
    row_no: int,
    student_exists,
) -> tuple[str, str | None]:
    """校验并归一一个行决定；非法形状用带行号的 422 报出（不落任何写入）。"""
    if action is None:
        raise _issue_error(
            f"第 {row_no} 行还没有决定。",
            code=ROSTER_IDENTITY_UNRESOLVED,
            status_code=422,
            issues=[
                _issue(
                    row_no,
                    code=ROSTER_IDENTITY_UNRESOLVED,
                    message="该行还没有决定；请给出 link/create/ignore。",
                    field="identity",
                )
            ],
        )
    if action not in ROSTER_DECISIONS:
        raise _issue_error(
            f"第 {row_no} 行的决定不合法。",
            code="INVALID_REQUEST",
            status_code=422,
            issues=[
                _issue(
                    row_no,
                    code="INVALID_REQUEST",
                    message=f"决定必须是 {sorted(ROSTER_DECISIONS)} 之一。",
                    field="action",
                )
            ],
        )
    if action == "link":
        if not isinstance(student_id, str) or not student_id.strip():
            raise _issue_error(
                f"第 {row_no} 行选择 link 但没有指定学生。",
                code=ROSTER_IDENTITY_UNRESOLVED,
                status_code=422,
                issues=[
                    _issue(
                        row_no,
                        code=ROSTER_IDENTITY_UNRESOLVED,
                        message="link 必须给出 studentId。",
                        field="studentId",
                    )
                ],
            )
        if not student_exists(student_id.strip()):
            raise _issue_error(
                f"第 {row_no} 行 link 指定的学生不存在。",
                code=ROSTER_IDENTITY_UNRESOLVED,
                status_code=422,
                issues=[
                    _issue(
                        row_no,
                        code=ROSTER_IDENTITY_UNRESOLVED,
                        message="link 指定的学生不存在，请刷新后重选。",
                        field="studentId",
                    )
                ],
            )
        return "link", student_id.strip()
    if student_id is not None:
        raise _issue_error(
            f"第 {row_no} 行的决定不允许携带 studentId。",
            code="INVALID_REQUEST",
            status_code=422,
            issues=[
                _issue(
                    row_no,
                    code="INVALID_REQUEST",
                    message=f"{action} 不得携带 studentId。",
                    field="studentId",
                )
            ],
        )
    return action, None


def _require_editable(record: RosterImportRecord) -> None:
    if record.state == "confirmed":
        raise AppError(
            "该名单批次已确认，不能再修改或再次确认（重放请使用相同 submissionId）。",
            code=ROSTER_IMPORT_CONFIRMED,
            status_code=409,
        )
    if record.state not in EDITABLE_IMPORT_STATES:
        raise _conflict(f"批次状态为 {record.state}，不允许修改或确认。")


def _render_import(
    record: RosterImportRecord, *, file_asset: AssetRef | None
) -> RosterImportView:
    if file_asset is None:
        raise AppError(
            "名单批次关联的受管资产登记缺失。", code="ASSET_MISSING", status_code=500
        )
    rows = [
        RosterImportRowView(
            rowNo=row.row_no,
            name=row.name,
            studentNo=row.student_no,
            matchedStudentId=row.matched_student_id,
            matchedStudentName=row.matched_student_name,
            suggestion=row_analysis.suggestion_of(
                name=row.name,
                student_no=row.student_no,
                matched_student_id=row.matched_student_id,
                issues=row.issues,
            ),
            decision=row.decision,
            issues=list(row.issues),
        )
        for row in record.rows
    ]
    return RosterImportView(
        importId=record.import_id,
        classId=record.class_id,
        className=record.class_name,
        state=record.state,
        revision=record.revision,
        fileAsset=file_asset,
        headers=record.headers(),
        mapping=dict(record.mapping),
        warnings=list(record.warnings),
        # 批次级 issues 只汇总阻断问题（行列细节在 rows[].issues）
        issues=[
            issue
            for row in record.rows
            for issue in row.issues
            if row_analysis.is_blocking_issue(issue)
        ],
        rows=rows,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
    )


def _payloads(analyzed: list[AnalyzedRow]) -> list[RosterRowPayload]:
    return [
        RosterRowPayload(
            row_no=row.row_no,
            name=row.name,
            student_no=row.student_no,
            matched_student_id=row.matched_student_id,
            issues=row.issues,
            raw_cells=dict(row.raw_cells),
        )
        for row in analyzed
    ]


class RosterService:
    """班级 / 学生 / 名单导入的用例入口。"""

    def __init__(
        self,
        catalog: TeachingCatalog,
        *,
        asset_store: AssetStore,
        file_assets: FileAssetsRepository,
        job_engine: Any | None = None,
    ) -> None:
        self._catalog = catalog
        self._asset_store = asset_store
        self._file_assets = file_assets
        self._job_engine = job_engine  # 预留：本批名单流程不使用任务引擎
        self._classes = ClassRepository(catalog)
        self._students = StudentRepository(catalog)
        self._imports = RosterImportRepository(catalog)

    # ---------------------------------------------------------------- 班级

    def list_classes(
        self, *, status: str | None = None, offset: int = 0, limit: int = 50
    ) -> ClassList:
        offset, limit = _page(offset, limit)
        records, total = self._classes.list(status=status, offset=offset, limit=limit)
        return ClassList(
            items=[record.view() for record in records],
            total=total,
            offset=offset,
            limit=limit,
        )

    def create_class(self, payload: ClassCreateRequest) -> ClassView:
        record = self._classes.create(
            code=_clean_text(payload.code, field="code"),
            name=_clean_text(payload.name, field="name"),
            school_year=_clean_text(payload.school_year, field="schoolYear"),
            grade_id=_clean_text(payload.grade_id, field="gradeId"),
        )
        return record.view()

    def get_class(self, class_id: str) -> ClassView:
        return self._classes.get(class_id).view()

    def update_class(self, class_id: str, payload: ClassUpdateRequest) -> ClassView:
        record = self._classes.update(
            class_id,
            expected_revision=payload.expected_revision,
            name=_optional_text(payload.name, field="name"),
            school_year=_optional_text(payload.school_year, field="schoolYear"),
            grade_id=_optional_text(payload.grade_id, field="gradeId"),
        )
        return record.view()

    def set_archived(
        self, class_id: str, payload: ClassRevisionRequest, *, archived: bool
    ) -> ClassView:
        record = self._classes.set_status(
            class_id,
            expected_revision=payload.expected_revision,
            status="archived" if archived else "active",
        )
        return record.view()

    # ---------------------------------------------------------------- 学生

    def list_class_students(self, class_id: str) -> StudentList:
        with self._catalog.read_connection() as conn:
            self._classes.require_in(conn, class_id)
            records, total = self._students.list_in_class_in(conn, class_id)
        return StudentList(
            items=[record.view() for record in records],
            total=total,
            offset=0,
            limit=max(1, total),
        )

    def list_students(
        self, *, q: str | None = None, offset: int = 0, limit: int = 50
    ) -> StudentList:
        offset, limit = _page(offset, limit)
        records, total = self._students.list(q=q, offset=offset, limit=limit)
        return StudentList(
            items=[record.view() for record in records],
            total=total,
            offset=offset,
            limit=limit,
        )

    def get_student(self, student_id: str) -> StudentView:
        return self._students.get(student_id).view()

    def create_student(self, payload: StudentCreateRequest) -> StudentView:
        name = _clean_text(payload.name, field="name")
        class_id = (
            payload.class_id.strip()
            if isinstance(payload.class_id, str) and payload.class_id.strip()
            else None
        )
        joined_on = (
            _require_date(payload.joined_on, field="joinedOn")
            if payload.joined_on is not None
            else _today()
        )
        with self._catalog.write_transaction() as conn:
            if class_id is not None:
                _reject_archived(self._classes.require_in(conn, class_id), action="加入新学生")
            student = self._students.create_in(
                conn, name=name, student_no=payload.student_no
            )
            if class_id is not None:
                self._students.insert_membership_in(
                    conn,
                    class_id=class_id,
                    student_id=student.id,
                    joined_on=joined_on,
                )
            return self._students.require_in(conn, student.id).view()

    def update_student(
        self, student_id: str, payload: StudentUpdateRequest
    ) -> StudentView:
        record = self._students.update(
            student_id,
            expected_revision=payload.expected_revision,
            name=_optional_text(payload.name, field="name"),
            student_no=_optional_student_no(payload.student_no),
        )
        return record.view()

    def transfer_student(
        self, student_id: str, payload: MembershipTransferRequest
    ) -> StudentView:
        from_class_id = _clean_text(payload.from_class_id, field="fromClassId")
        to_class_id = _clean_text(payload.to_class_id, field="toClassId")
        if from_class_id == to_class_id:
            raise _invalid("转班的来源与目标班级不能相同。", fields=["toClassId"])
        moved_on = _require_date(payload.moved_on, field="movedOn")
        with self._catalog.write_transaction() as conn:
            self._classes.require_in(conn, from_class_id)
            _reject_archived(self._classes.require_in(conn, to_class_id), action="转入学生")
            record = self._students.transfer_in(
                conn,
                student_id,
                from_class_id=from_class_id,
                to_class_id=to_class_id,
                moved_on=moved_on,
                expected_revision=payload.expected_student_revision,
            )
            return record.view()

    # ---------------------------------------------------------------- 名单导入

    def create_roster_import(
        self,
        *,
        class_id: str,
        file_name: str,
        content: bytes,
        media_type: str,
        mapping: dict[str, str] | None = None,
        sheet_name: str | None = None,
    ) -> RosterImportView:
        file_name = _clean_text(file_name, field="fileName")
        media_type = (media_type or "").strip() or DEFAULT_MEDIA_TYPE
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise row_analysis.mapping_invalid("上传的名单文件为空。")
        with self._catalog.read_connection() as conn:
            klass = self._classes.require_in(conn, class_id)
        _reject_archived(klass, action="导入名单")

        tables = read_table(
            bytes(content),
            file_name=file_name,
            media_type=media_type,
            sheet_name=sheet_name,
        )
        warnings: list[str] = []
        table = tables[0]
        if len(tables) > 1:
            warnings.append(
                f"文件含 {len(tables)} 个工作表，仅处理第一个「{table.name}」。"
            )
        resolved = row_analysis.resolve_mapping(table.headers, mapping)
        extracted = row_analysis.extract_rows(table.headers, table.rows, resolved)
        if not extracted:
            raise row_analysis.mapping_invalid("名单没有数据行（只有表头）。")
        analyzed = self._analyze_extracted(extracted)

        # 文件本体先落盘（内容寻址、幂等），再在一个写事务里登记资产 + 批次 + 预览行。
        stored = self._asset_store.store_original(
            bytes(content), media_type=media_type, original_name=file_name
        )
        with self._catalog.write_transaction() as conn:
            asset = self._file_assets.create_in(
                conn,
                kind="roster",
                blob_key=stored.blob_key,
                sha256=stored.sha256,
                media_type=media_type,
                byte_size=stored.byte_size,
                original_name=file_name,
            )
            record = self._imports.create_in(
                conn,
                class_id=class_id,
                file_asset_id=asset.asset_id,
                mapping=resolved,
                warnings=warnings,
                state="reviewing",
            )
            self._imports.insert_rows_in(conn, record.import_id, _payloads(analyzed))
            import_id = record.import_id
        return self.get_roster_import(import_id)

    def get_roster_import(self, import_id: str) -> RosterImportView:
        with self._catalog.read_connection() as conn:
            record = self._imports.require_in(conn, import_id)
        asset = self._file_assets.get(record.file_asset_id)
        return _render_import(record, file_asset=asset.ref() if asset else None)

    def list_roster_imports(
        self,
        *,
        class_id: str | None = None,
        state: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> RosterImportList:
        offset, limit = _page(offset, limit)
        items, total = self._imports.list(
            class_id=class_id, state=state, offset=offset, limit=limit
        )
        return RosterImportList(
            items=list(items), total=total, offset=offset, limit=limit
        )

    def patch_roster_import(
        self, import_id: str, payload: RosterImportPatchRequest
    ) -> RosterImportView:
        with self._catalog.write_transaction() as conn:
            record = self._imports.require_in(conn, import_id)
            _require_editable(record)
            _check_revision(record.revision, payload.expected_revision)

            resolved_mapping: dict[str, str] | None = None
            replace_rows: list[RosterRowPayload] | None = None
            if payload.mapping is not None:
                resolved_mapping = row_analysis.resolve_mapping(
                    record.headers(), payload.mapping
                )
                raw_rows = [
                    (row.row_no, dict(row.raw_cells)) for row in record.rows
                ]
                extracted = row_analysis.extract_rows_from_raw(
                    raw_rows, resolved_mapping
                )
                if not extracted:
                    raise row_analysis.mapping_invalid("批次没有可重算的数据行。")
                analyzed = self._analyze_extracted_in(conn, extracted)
                replace_rows = _payloads(analyzed)
            decisions: list[RowDecision] | None = None
            if payload.rows is not None:
                decisions = self._validate_row_patches(conn, record, payload.rows)

            self._imports.apply_patch_in(
                conn,
                import_id,
                expected_revision=payload.expected_revision,
                mapping=resolved_mapping,
                replace_rows=replace_rows,
                decisions=decisions,
            )
        return self.get_roster_import(import_id)

    def confirm_roster_import(
        self, import_id: str, payload: RosterImportConfirmRequest
    ) -> RosterImportConfirmResult:
        command = make_command(
            operation="roster.import.confirm",
            submission_id=payload.submission_id,
            payload={
                "importId": import_id,
                "expectedRevision": payload.expected_revision,
                "identityMatches": [
                    {
                        "rowNo": match.row_no,
                        "action": match.action,
                        "studentId": match.student_id,
                    }
                    for match in payload.identity_matches
                ],
            },
        )
        outcome = execute_command(
            catalog=self._catalog,
            command=command,
            apply=lambda conn: self._apply_confirm(
                conn,
                import_id=import_id,
                expected_revision=payload.expected_revision,
                identity_matches=payload.identity_matches,
            ),
            table="command_submissions",
        )
        result = RosterImportConfirmResult.model_validate(outcome.result)
        return result.model_copy(update={"replayed": outcome.replayed})

    # ---------------------------------------------------------------- 内部

    def _analyze_extracted(self, extracted: list[ExtractedRow]) -> list[AnalyzedRow]:
        with self._catalog.read_connection() as conn:
            return self._analyze_extracted_in(conn, extracted)

    def _analyze_extracted_in(
        self, conn: sqlite3.Connection, extracted: list[ExtractedRow]
    ) -> list[AnalyzedRow]:
        numbers = [row.student_no for row in extracted if row.student_no]
        names = [
            row.name for row in extracted if row.student_no is None and row.name
        ]
        by_student_no = self._students.map_by_student_no_in(conn, numbers)
        by_name = self._students.map_by_name_in(conn, names)
        return row_analysis.analyze_rows(
            extracted, by_student_no=by_student_no, by_name=by_name
        )

    def _validate_row_patches(
        self,
        conn: sqlite3.Connection,
        record: RosterImportRecord,
        patches: list[RosterImportRowPatch],
    ) -> list[RowDecision]:
        decisions: list[RowDecision] = []
        seen: set[int] = set()
        for patch in patches:
            if patch.row_no in seen:
                raise _issue_error(
                    f"第 {patch.row_no} 行在同一请求里出现了多次。",
                    code="INVALID_REQUEST",
                    status_code=422,
                    issues=[
                        _issue(
                            patch.row_no,
                            code="INVALID_REQUEST",
                            message="同一行不能在 rows 里重复出现。",
                            field="rowNo",
                        )
                    ],
                )
            seen.add(patch.row_no)
            row = record.row(patch.row_no)
            if row is None:
                raise _issue_error(
                    f"批次中不存在第 {patch.row_no} 行。",
                    code="INVALID_REQUEST",
                    status_code=422,
                    issues=[
                        _issue(
                            patch.row_no,
                            code="INVALID_REQUEST",
                            message="批次中不存在该行。",
                            field="rowNo",
                        )
                    ],
                )
            action, matched = _resolve_decision(
                action=patch.decision,
                student_id=patch.student_id,
                row_no=patch.row_no,
                student_exists=lambda sid: self._students.exists_in(conn, sid),
            )
            if action == "ignore":
                matched = row.matched_student_id
            decisions.append(
                RowDecision(
                    row_no=patch.row_no, decision=action, matched_student_id=matched
                )
            )
        return decisions

    def _apply_confirm(
        self,
        conn: sqlite3.Connection,
        *,
        import_id: str,
        expected_revision: int,
        identity_matches: list[RosterIdentityMatch],
    ) -> dict[str, Any]:
        record = self._imports.require_in(conn, import_id)
        _require_editable(record)
        _check_revision(record.revision, expected_revision)
        # 归档班级不再接收新归属：确认会写归属，因此与"新导入"同一口径拒绝。
        _reject_archived(
            self._classes.require_in(conn, record.class_id), action="确认名单导入"
        )

        by_row = {row.row_no: row for row in record.rows}
        overrides: dict[int, RosterIdentityMatch] = {}
        for match in identity_matches:
            if match.row_no in overrides:
                raise _issue_error(
                    f"第 {match.row_no} 行在 identityMatches 里出现了多次。",
                    code="INVALID_REQUEST",
                    status_code=422,
                    issues=[
                        _issue(
                            match.row_no,
                            code="INVALID_REQUEST",
                            message="同一行不能在 identityMatches 里重复。",
                            field="rowNo",
                        )
                    ],
                )
            if match.row_no not in by_row:
                raise _issue_error(
                    f"批次中不存在第 {match.row_no} 行。",
                    code="INVALID_REQUEST",
                    status_code=422,
                    issues=[
                        _issue(
                            match.row_no,
                            code="INVALID_REQUEST",
                            message="批次中不存在该行。",
                            field="rowNo",
                        )
                    ],
                )
            overrides[match.row_no] = match

        # 逐行取决定：identityMatches 覆盖行上已保存的 decision。
        decisions: dict[int, tuple[str | None, str | None]] = {}
        unresolved: list[ErrorIssue] = []
        blocking: list[ErrorIssue] = []
        for row in record.rows:
            override = overrides.get(row.row_no)
            if override is not None:
                action, student_id = override.action, override.student_id
            elif row.decision is not None:
                action = row.decision
                student_id = row.matched_student_id if row.decision == "link" else None
            else:
                action, student_id = None, None
            decisions[row.row_no] = (action, student_id)
            if action is None:
                if any(issue.code in BLOCKING_ISSUE_CODES for issue in row.issues):
                    blocking.append(
                        _issue(
                            row.row_no,
                            code=ROSTER_IMPORT_BLOCKING_ISSUES,
                            message="该行存在未消歧的重复行或同名冲突，请先给出决定。",
                            field="identity",
                        )
                    )
                else:
                    unresolved.append(
                        _issue(
                            row.row_no,
                            code=ROSTER_IDENTITY_UNRESOLVED,
                            message="该行还没有决定；请给出 link/create/ignore。",
                            field="identity",
                        )
                    )
        # 重复组：两行最终指向同一身份（同学号/同姓名同特征）仍未消歧时阻断。
        identity_key = {
            row.row_no: f"{row.student_no or ''}\u0000{row.name}"
            for row in record.rows
        }
        for group in row_analysis.duplicate_groups(
            [(row.row_no, row.name, row.student_no) for row in record.rows]
        ):
            grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
            for row_no in group:
                action, student_id = decisions[row_no]
                if action is None or action == "ignore":
                    continue
                key = (
                    ("student", student_id)
                    if action == "link"
                    else ("create", identity_key[row_no])
                )
                grouped[key].append(row_no)
            for row_nos in grouped.values():
                if len(row_nos) < 2:
                    continue
                for row_no in row_nos:
                    others = "、".join(
                        f"第 {item} 行" for item in row_nos if item != row_no
                    )
                    blocking.append(
                        _issue(
                            row_no,
                            code=ROSTER_IMPORT_BLOCKING_ISSUES,
                            message=f"与{others}指向同一身份，请人工消歧。",
                            field="identity",
                        )
                    )
        if blocking:
            raise _issue_error(
                "名单仍有未消歧的重复行或同名冲突，整批未写入。",
                code=ROSTER_IMPORT_BLOCKING_ISSUES,
                status_code=422,
                issues=blocking,
            )
        if unresolved:
            raise _issue_error(
                "名单存在没有决定的行，整批未写入。",
                code=ROSTER_IDENTITY_UNRESOLVED,
                status_code=422,
                issues=unresolved,
            )

        # 决定形状校验（link 必须指向存在的学生；create/ignore 不得带 studentId）。
        resolved: dict[int, tuple[str, str | None]] = {}
        for row in record.rows:
            action, student_id = decisions[row.row_no]
            action, student_id = _resolve_decision(
                action=action,
                student_id=student_id,
                row_no=row.row_no,
                student_exists=lambda sid: self._students.exists_in(conn, sid),
            )
            if action == "create":
                if not row.name:
                    raise _issue_error(
                        f"第 {row.row_no} 行姓名为空，不能新建学生。",
                        code=ROSTER_ROW_INVALID,
                        status_code=422,
                        issues=[
                            _issue(
                                row.row_no,
                                code=ROSTER_ROW_INVALID,
                                message="姓名为空，不能新建学生；请改为 link 或 ignore。",
                                field="name",
                            )
                        ],
                    )
                if (
                    len(row.name) > row_analysis.MAX_NAME_CHARS
                    or len(row.student_no or "") > row_analysis.MAX_STUDENT_NO_CHARS
                ):
                    raise _issue_error(
                        f"第 {row.row_no} 行的姓名或学号超出长度上限。",
                        code=ROSTER_ROW_INVALID,
                        status_code=422,
                        issues=[
                            _issue(
                                row.row_no,
                                code=ROSTER_ROW_INVALID,
                                message="姓名或学号超出长度上限，不能新建学生。",
                                field="name",
                            )
                        ],
                    )
            resolved[row.row_no] = (action, student_id)

        # 按行序执行；任一失败整体回滚（含提交登记）。
        applied: list[RosterAppliedRow] = []
        ignored: list[int] = []
        stored_decisions: list[RowDecision] = []
        for row in record.rows:
            action, student_id = resolved[row.row_no]
            if action == "ignore":
                ignored.append(row.row_no)
                stored_decisions.append(
                    RowDecision(
                        row_no=row.row_no,
                        decision="ignore",
                        matched_student_id=row.matched_student_id,
                    )
                )
                continue
            if action == "link":
                student = self._students.require_in(conn, student_id or "")
                membership, created = self._students.insert_membership_in(
                    conn,
                    class_id=record.class_id,
                    student_id=student.id,
                    joined_on=_today(),
                )
                applied.append(
                    RosterAppliedRow(
                        rowNo=row.row_no,
                        studentId=student.id,
                        membershipId=membership.membership_id,
                        createdStudent=False,
                        createdMembership=created,
                    )
                )
                stored_decisions.append(
                    RowDecision(
                        row_no=row.row_no,
                        decision="link",
                        matched_student_id=student.id,
                    )
                )
                continue
            try:
                student = self._students.create_in(
                    conn, name=row.name, student_no=row.student_no
                )
            except AppError as exc:
                if exc.code == STUDENT_NO_CONFLICT:
                    raise _issue_error(
                        f"第 {row.row_no} 行新建学生时学号已存在，整批未写入。",
                        code=STUDENT_NO_CONFLICT,
                        status_code=409,
                        issues=[
                            _issue(
                                row.row_no,
                                code=STUDENT_NO_CONFLICT,
                                message="该学号已存在；请改为 link 或修正表格后重试。",
                                field="studentNo",
                            )
                        ],
                    ) from exc
                raise
            membership, created = self._students.insert_membership_in(
                conn,
                class_id=record.class_id,
                student_id=student.id,
                joined_on=_today(),
            )
            applied.append(
                RosterAppliedRow(
                    rowNo=row.row_no,
                    studentId=student.id,
                    membershipId=membership.membership_id,
                    createdStudent=True,
                    createdMembership=created,
                )
            )
            stored_decisions.append(
                RowDecision(
                    row_no=row.row_no, decision="create", matched_student_id=None
                )
            )

        self._imports.mark_confirmed_in(
            conn,
            import_id,
            expected_revision=expected_revision,
            decisions=stored_decisions,
        )
        result = RosterImportConfirmResult(
            importId=import_id,
            state="confirmed",
            applied=applied,
            ignored=ignored,
            replayed=False,
        )
        return result.model_dump(by_alias=True)


def build_roster_service(
    catalog: TeachingCatalog,
    *,
    asset_store: AssetStore,
    file_assets: FileAssetsRepository,
    job_engine: Any | None = None,
) -> RosterService:
    """装配工厂（签名由 B1 任务卡 §5 冻结；``job_engine`` 本批预留不用）。"""
    return RosterService(
        catalog,
        asset_store=asset_store,
        file_assets=file_assets,
        job_engine=job_engine,
    )


__all__ = ["RosterService", "build_roster_service"]
