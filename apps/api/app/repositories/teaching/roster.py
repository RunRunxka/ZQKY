"""名单导入批次仓储（TEACHING-LOOP B1 / T30-a）：只做 SQL。

表已由教学库迁移 ``0002_teaching_business_tables`` 登记（``roster_imports`` /
``roster_import_rows``）；本模块不建表、不改 DDL。字段对外一律走
``app.contracts.roster`` 的 ``RosterImportView`` / ``RosterImportSummary`` / ``RosterImportRowView``。

持久化与派生口径：

- 行上保存 ``name`` / ``student_no``（文本，保留前导零）与 ``raw_cells_json``（审计原文）；
  ``issues_json`` 保存 ``ErrorIssue`` 列表，**行建议（suggestion）由 issues + 匹配结果派生**
  （见 ``app.services.roster.imports``），因此 DDL 不需要额外列；
- 阻断问题在预览期以固定 issue code 落库：``ROSTER_ROW_DUPLICATE``（同批重复行）与
  ``ROSTER_NAME_CONFLICT``（同名多命中）；``list`` 的 ``blockingIssueCount`` 按这两个 code 统计；
- 批次修订 ``revision`` 是乐观锁：``apply_patch_in`` / ``mark_confirmed_in`` 各只递增一次；
- 读取结构非法（状态不在白名单、JSON 损坏、行号非法等）一律 ``ROSTER_ROW_CORRUPT``（500），
  不静默放行。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.contracts.roster import (
    ROSTER_IMPORT_STATES,
    RosterImportState,
    RosterImportSummary,
    RosterDecision,
)
from app.contracts.teaching_loop import REVISION_CONFLICT, ErrorIssue, error_details
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.catalog import TeachingCatalog

DEFAULT_OWNER_ID = "local"
MAX_LIST_LIMIT = 200

ROSTER_IMPORT_NOT_FOUND = "ROSTER_IMPORT_NOT_FOUND"
ROSTER_ROW_CORRUPT = "ROSTER_ROW_CORRUPT"
#: 预览期阻断问题 code（确认时未消歧一律 422 ``ROSTER_IMPORT_BLOCKING_ISSUES``）
ROSTER_ROW_DUPLICATE = "ROSTER_ROW_DUPLICATE"
ROSTER_NAME_CONFLICT = "ROSTER_NAME_CONFLICT"
BLOCKING_ISSUE_CODES: tuple[str, ...] = (ROSTER_ROW_DUPLICATE, ROSTER_NAME_CONFLICT)

_SELECT_IMPORT = """
SELECT i.id, i.owner_id, i.class_id, i.file_asset_id, i.state, i.revision,
       i.mapping_json, i.warnings_json, i.error_code, i.created_at, i.updated_at,
       c.name AS class_name
  FROM roster_imports i
  JOIN classes c ON c.id = i.class_id
"""

_SELECT_ROWS = """
SELECT r.row_no, r.name, r.student_no, r.matched_student_id,
       s.name AS matched_student_name, r.decision, r.raw_cells_json, r.issues_json
  FROM roster_import_rows r
  LEFT JOIN students s ON s.id = r.matched_student_id
 WHERE r.import_id = ?
 ORDER BY r.row_no ASC
"""

#: 阻断行数：issues_json 里出现阻断 code 的行数（json_each 需 SQLite JSON1，Python 3.12 自带）
_BLOCKING_COUNT_SQL = """
SELECT COUNT(*) AS n FROM roster_import_rows r
 WHERE r.import_id = ?
   AND EXISTS (
        SELECT 1 FROM json_each(r.issues_json) e
         WHERE json_extract(e.value, '$.code') IN (?, ?)
   )
"""

#: 批次列表里的阻断行数：与外层 roster_imports 关联（两个 code 占位符先于 WHERE 绑定）
_SUMMARY_BLOCKING = """
SELECT COUNT(*) FROM roster_import_rows r
 WHERE r.import_id = i.id
   AND EXISTS (
        SELECT 1 FROM json_each(r.issues_json) e
         WHERE json_extract(e.value, '$.code') IN (?, ?)
   )
"""

#: 批次摘要（列表）：同库只读 JOIN 补班级展示名与上传原文件名（名称优先，
#: LEFT JOIN——班级/资产登记缺失时取 NULL，由服务层落 null，不伪造名称）
_SELECT_SUMMARY = f"""
SELECT i.id, i.class_id, i.state, i.revision, i.created_at, i.updated_at,
       c.name AS class_name, fa.original_name AS uploaded_file_name,
       (SELECT COUNT(*) FROM roster_import_rows r WHERE r.import_id = i.id) AS row_count,
       ({_SUMMARY_BLOCKING.strip()}) AS blocking_count
  FROM roster_imports i
  LEFT JOIN classes c ON c.id = i.class_id
  LEFT JOIN file_assets fa ON fa.id = i.file_asset_id
"""


def _invalid(message: str, *, fields: list[str] | None = None) -> AppError:
    return AppError(
        message,
        code="INVALID_REQUEST",
        status_code=422,
        details=error_details(fields=fields) if fields else None,
    )


def _not_found(import_id: str) -> AppError:
    return AppError(
        f"名单批次不存在：{import_id}。", code=ROSTER_IMPORT_NOT_FOUND, status_code=404
    )


def _corrupt(message: str) -> AppError:
    return AppError(message, code=ROSTER_ROW_CORRUPT, status_code=500)


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。", fields=[field])
    return value.strip()


def _check_page(*, offset: int, limit: int) -> None:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise _invalid("offset 必须是不小于 0 的整数。", fields=["offset"])
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 1
        or limit > MAX_LIST_LIMIT
    ):
        raise _invalid(f"limit 必须是 1..{MAX_LIST_LIMIT} 的整数。", fields=["limit"])


def _check_revision(current: int, expected: int | None) -> None:
    if expected is not None and current != expected:
        raise AppError(
            "数据已被其他操作更新，请刷新后重试。",
            code=REVISION_CONFLICT,
            status_code=409,
            details=error_details(current_revision=current),
        )


def _dump_issues(issues: Sequence[ErrorIssue]) -> str:
    payload = [
        issue.model_dump(exclude_none=True) if isinstance(issue, ErrorIssue) else issue
        for issue in issues
    ]
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:  # pragma: no cover - 形状由 ErrorIssue 保证
        raise _invalid("issues 必须是可序列化的 ErrorIssue 列表。") from exc


def _load_issues(raw: object) -> tuple[ErrorIssue, ...]:
    if not isinstance(raw, str):
        raise _corrupt("教学库数据损坏：roster_import_rows.issues_json 不是文本。")
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise _corrupt("教学库数据损坏：roster_import_rows.issues_json 不是合法 JSON。") from exc
    if not isinstance(value, list):
        raise _corrupt("教学库数据损坏：roster_import_rows.issues_json 不是数组。")
    issues: list[ErrorIssue] = []
    for item in value:
        if not isinstance(item, dict):
            raise _corrupt("教学库数据损坏：issues 元素不是对象。")
        try:
            issues.append(ErrorIssue.model_validate(item))
        except Exception as exc:  # pydantic ValidationError：结构不符
            raise _corrupt(f"教学库数据损坏：issues 元素结构不符（{exc.__class__.__name__}）。") from exc
    return tuple(issues)


def _dump_mapping(mapping: dict[str, str]) -> str:
    if not isinstance(mapping, dict):
        raise _invalid("mapping 必须是 JSON 对象。", fields=["mapping"])
    for key, value in mapping.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise _invalid("mapping 的键与值都必须是字符串。", fields=["mapping"])
    return json.dumps(mapping, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_mapping(raw: object) -> dict[str, str]:
    if not isinstance(raw, str):
        raise _corrupt("教学库数据损坏：roster_imports.mapping_json 不是文本。")
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise _corrupt("教学库数据损坏：mapping_json 不是合法 JSON。") from exc
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise _corrupt("教学库数据损坏：mapping_json 不是字符串映射。")
    return dict(value)


def _load_warnings(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, str):
        raise _corrupt("教学库数据损坏：roster_imports.warnings_json 不是文本。")
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise _corrupt("教学库数据损坏：warnings_json 不是合法 JSON。") from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise _corrupt("教学库数据损坏：warnings_json 不是字符串数组。")
    return tuple(value)


def _dump_raw_cells(raw_cells: dict[str, str]) -> str:
    if not isinstance(raw_cells, dict):
        raise _invalid("raw_cells 必须是字符串映射。")
    for key, value in raw_cells.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise _invalid("raw_cells 的键与值都必须是字符串。")
    return json.dumps(raw_cells, ensure_ascii=False, separators=(",", ":"))


def _load_raw_cells(raw: object) -> dict[str, str]:
    if not isinstance(raw, str):
        raise _corrupt("教学库数据损坏：roster_import_rows.raw_cells_json 不是文本。")
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise _corrupt("教学库数据损坏：raw_cells_json 不是合法 JSON。") from exc
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise _corrupt("教学库数据损坏：raw_cells_json 不是字符串映射。")
    return dict(value)


@dataclass(frozen=True)
class RosterRowPayload:
    """写入一行预览所需的全部值（服务层分析结果）。"""

    row_no: int
    name: str
    student_no: str | None
    matched_student_id: str | None
    issues: tuple[ErrorIssue, ...]
    raw_cells: dict[str, str]


@dataclass(frozen=True)
class RosterRowRecord:
    """``roster_import_rows`` 一行（附 matched 学生姓名）。"""

    row_no: int
    name: str
    student_no: str | None
    matched_student_id: str | None
    matched_student_name: str | None
    decision: str | None
    issues: tuple[ErrorIssue, ...]
    raw_cells: dict[str, str]


@dataclass(frozen=True)
class RosterImportRecord:
    """``roster_imports`` 一行 + 预览行。"""

    import_id: str
    owner_id: str
    class_id: str
    class_name: str
    file_asset_id: str
    state: str
    revision: int
    mapping: dict[str, str]
    warnings: tuple[str, ...]
    error_code: str | None
    created_at: str
    updated_at: str
    rows: tuple[RosterRowRecord, ...] = ()

    def headers(self) -> list[str]:
        """原始表头：从各行审计原文键的首次出现顺序重建（不依赖额外列）。"""
        headers: list[str] = []
        seen: set[str] = set()
        for row in self.rows:
            for header in row.raw_cells:
                if header not in seen:
                    seen.add(header)
                    headers.append(header)
        return headers

    def row(self, row_no: int) -> RosterRowRecord | None:
        for item in self.rows:
            if item.row_no == row_no:
                return item
        return None


@dataclass(frozen=True)
class RowDecision:
    """一次行决定写入（PATCH 或确认时固化）。"""

    row_no: int
    decision: RosterDecision
    matched_student_id: str | None


class RosterImportRepository:
    """名单批次与行的唯一读写入口。"""

    def __init__(self, catalog: TeachingCatalog) -> None:
        self._catalog = catalog

    # -------------------------------------------------------------- 批次写入

    def create(
        self,
        *,
        class_id: str,
        file_asset_id: str,
        mapping: dict[str, str],
        warnings: Sequence[str] = (),
        state: RosterImportState = "reviewing",
        owner_id: str = DEFAULT_OWNER_ID,
        import_id: str | None = None,
    ) -> RosterImportRecord:
        with self._catalog.write_transaction() as conn:
            return self.create_in(
                conn,
                class_id=class_id,
                file_asset_id=file_asset_id,
                mapping=mapping,
                warnings=warnings,
                state=state,
                owner_id=owner_id,
                import_id=import_id,
            )

    def create_in(
        self,
        conn: sqlite3.Connection,
        *,
        class_id: str,
        file_asset_id: str,
        mapping: dict[str, str],
        warnings: Sequence[str] = (),
        state: RosterImportState = "reviewing",
        owner_id: str = DEFAULT_OWNER_ID,
        import_id: str | None = None,
    ) -> RosterImportRecord:
        if state not in ROSTER_IMPORT_STATES:
            raise _invalid(f"state 必须是 {sorted(ROSTER_IMPORT_STATES)} 之一。")
        class_id = _require_text(class_id, field="classId")
        file_asset_id = _require_text(file_asset_id, field="fileAssetId")
        owner_id = _require_text(owner_id, field="owner_id")
        warning_list = [_require_text(item, field="warning") for item in warnings]
        new_id = import_id or uuid.uuid4().hex
        now = now_iso()
        conn.execute(
            "INSERT INTO roster_imports "
            "(id, owner_id, class_id, file_asset_id, state, revision, mapping_json, "
            " warnings_json, error_code, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?, NULL, ?, ?)",
            (
                new_id,
                owner_id,
                class_id,
                file_asset_id,
                state,
                _dump_mapping(mapping),
                json.dumps(warning_list, ensure_ascii=False),
                now,
                now,
            ),
        )
        return RosterImportRecord(
            import_id=new_id,
            owner_id=owner_id,
            class_id=class_id,
            class_name="",
            file_asset_id=file_asset_id,
            state=state,
            revision=0,
            mapping=dict(mapping),
            warnings=tuple(warning_list),
            error_code=None,
            created_at=now,
            updated_at=now,
        )

    def insert_rows_in(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        rows: Sequence[RosterRowPayload],
    ) -> None:
        import_id = _require_text(import_id, field="importId")
        for row in rows:
            self._insert_row_in(conn, import_id, row)

    def replace_rows_in(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        rows: Sequence[RosterRowPayload],
    ) -> None:
        """整批替换预览行（改映射后重算；行号与顺序由服务层保证）。"""
        import_id = _require_text(import_id, field="importId")
        conn.execute("DELETE FROM roster_import_rows WHERE import_id = ?", (import_id,))
        for row in rows:
            self._insert_row_in(conn, import_id, row)

    def apply_patch_in(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        *,
        expected_revision: int | None = None,
        mapping: dict[str, str] | None = None,
        replace_rows: Sequence[RosterRowPayload] | None = None,
        decisions: Sequence[RowDecision] | None = None,
    ) -> RosterImportRecord:
        """一次 PATCH 的全部 SQL：改映射 / 换行 / 写行决定；有变更则 revision+1。

        ``expected_revision`` 给出时先做乐观锁校验（不符 409 + ``currentRevision``）。
        """
        import_id = _require_text(import_id, field="importId")
        current = self.require_in(conn, import_id)
        _check_revision(current.revision, expected_revision)
        changed = False
        if replace_rows is not None:
            self.replace_rows_in(conn, import_id, replace_rows)
            changed = True
        if mapping is not None:
            conn.execute(
                "UPDATE roster_imports SET mapping_json = ? WHERE id = ?",
                (_dump_mapping(mapping), import_id),
            )
            changed = True
        if decisions is not None:
            self._write_decisions_in(conn, import_id, decisions)
            changed = True
        if changed:
            self._bump_in(conn, import_id)
        return self.require_in(conn, import_id)

    def mark_confirmed_in(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        *,
        expected_revision: int | None = None,
        decisions: Sequence[RowDecision] | None = None,
    ) -> RosterImportRecord:
        """确认成功时的终态写入：固化行决定 + state=confirmed + revision+1（同一事务）。"""
        import_id = _require_text(import_id, field="importId")
        current = self.require_in(conn, import_id)
        _check_revision(current.revision, expected_revision)
        if decisions is not None:
            self._write_decisions_in(conn, import_id, decisions)
        conn.execute(
            "UPDATE roster_imports SET state = 'confirmed', error_code = NULL WHERE id = ?",
            (import_id,),
        )
        self._bump_in(conn, import_id)
        return self.require_in(conn, import_id)

    def set_state(
        self,
        import_id: str,
        *,
        state: RosterImportState,
        error_code: str | None = None,
    ) -> RosterImportRecord:
        if state not in ROSTER_IMPORT_STATES:
            raise _invalid(f"state 必须是 {sorted(ROSTER_IMPORT_STATES)} 之一。")
        with self._catalog.write_transaction() as conn:
            return self.set_state_in(conn, import_id, state=state, error_code=error_code)

    def set_state_in(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        *,
        state: RosterImportState,
        error_code: str | None = None,
    ) -> RosterImportRecord:
        if state not in ROSTER_IMPORT_STATES:
            raise _invalid(f"state 必须是 {sorted(ROSTER_IMPORT_STATES)} 之一。")
        self.require_in(conn, import_id)
        conn.execute(
            "UPDATE roster_imports SET state = ?, error_code = ? WHERE id = ?",
            (state, error_code, import_id),
        )
        self._bump_in(conn, import_id)
        return self.require_in(conn, import_id)

    # -------------------------------------------------------------- 批次读取

    def get(self, import_id: str) -> RosterImportRecord:
        with self._catalog.read_connection() as conn:
            return self.require_in(conn, import_id)

    def get_in(
        self, conn: sqlite3.Connection, import_id: str
    ) -> RosterImportRecord | None:
        if not isinstance(import_id, str) or not import_id.strip():
            raise _invalid("import_id 必须是非空字符串。", fields=["importId"])
        row = conn.execute(
            f"{_SELECT_IMPORT} WHERE i.id = ?", (import_id.strip(),)
        ).fetchone()
        if row is None:
            return None
        return self._record(conn, row)

    def require_in(
        self, conn: sqlite3.Connection, import_id: str
    ) -> RosterImportRecord:
        record = self.get_in(conn, import_id)
        if record is None:
            raise _not_found(import_id)
        return record

    def list(
        self,
        *,
        class_id: str | None = None,
        state: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[RosterImportSummary], int]:
        _check_page(offset=offset, limit=limit)
        if state is not None and state not in ROSTER_IMPORT_STATES:
            raise _invalid(
                f"state 必须是 {sorted(ROSTER_IMPORT_STATES)} 之一。", fields=["state"]
            )
        conditions: list[str] = []
        params: list[object] = []
        if class_id is not None:
            conditions.append("i.class_id = ?")
            params.append(_require_text(class_id, field="classId"))
        if state is not None:
            conditions.append("i.state = ?")
            params.append(state)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._catalog.read_connection() as conn:
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) AS n FROM roster_imports i {where}", tuple(params)
                ).fetchone()["n"]
            )
            rows = conn.execute(
                f"{_SELECT_SUMMARY} {where} "
                "ORDER BY i.created_at DESC, i.rowid DESC LIMIT ? OFFSET ?",
                (ROSTER_ROW_DUPLICATE, ROSTER_NAME_CONFLICT, *params, limit, offset),
            ).fetchall()
        return [self._summary(row) for row in rows], total

    def blocking_issue_count(self, import_id: str) -> int:
        with self._catalog.read_connection() as conn:
            return self._blocking_issue_count_in(conn, import_id)

    # -------------------------------------------------------------- 内部

    def _blocking_issue_count_in(
        self, conn: sqlite3.Connection, import_id: str
    ) -> int:
        row = conn.execute(
            _BLOCKING_COUNT_SQL,
            (import_id, ROSTER_ROW_DUPLICATE, ROSTER_NAME_CONFLICT),
        ).fetchone()
        return int(row["n"])

    def _insert_row_in(
        self, conn: sqlite3.Connection, import_id: str, row: RosterRowPayload
    ) -> None:
        if not isinstance(row, RosterRowPayload):
            raise _invalid("rows 元素必须是 RosterRowPayload。")
        row_no = row.row_no
        if not isinstance(row_no, int) or isinstance(row_no, bool) or row_no < 1:
            raise _invalid("row_no 必须是不小于 1 的整数。", fields=["rowNo"])
        if not isinstance(row.name, str):
            raise _invalid("行姓名必须是字符串。", fields=["name"])
        if row.student_no is not None and not isinstance(row.student_no, str):
            raise _invalid("行学号必须是字符串或 null。", fields=["studentNo"])
        conn.execute(
            "INSERT INTO roster_import_rows "
            "(import_id, row_no, name, student_no, matched_student_id, decision, "
            " raw_cells_json, issues_json) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)",
            (
                import_id,
                row_no,
                row.name,
                row.student_no,
                row.matched_student_id,
                _dump_raw_cells(row.raw_cells),
                _dump_issues(row.issues),
            ),
        )

    def _write_decisions_in(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        decisions: Sequence[RowDecision],
    ) -> None:
        for decision in decisions:
            if not isinstance(decision, RowDecision):
                raise _invalid("decisions 元素必须是 RowDecision。")
            cursor = conn.execute(
                "UPDATE roster_import_rows SET decision = ?, matched_student_id = ? "
                "WHERE import_id = ? AND row_no = ?",
                (
                    decision.decision,
                    decision.matched_student_id,
                    import_id,
                    decision.row_no,
                ),
            )
            if cursor.rowcount == 0:
                raise _invalid(
                    f"批次中不存在第 {decision.row_no} 行。",
                    fields=["rows"],
                )

    def _bump_in(self, conn: sqlite3.Connection, import_id: str) -> None:
        conn.execute(
            "UPDATE roster_imports SET revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso(), import_id),
        )

    def _record(
        self, conn: sqlite3.Connection, row: sqlite3.Row
    ) -> RosterImportRecord:
        state = row["state"]
        if not isinstance(state, str) or state not in ROSTER_IMPORT_STATES:
            raise _corrupt(f"教学库数据损坏：roster_imports.state 结构不符（{state!r}）。")
        revision = row["revision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise _corrupt("教学库数据损坏：roster_imports.revision 不是非负整数。")
        class_name = row["class_name"]
        if not isinstance(class_name, str) or not class_name:
            raise _corrupt("教学库数据损坏：批次关联的班级名称缺失。")
        error_code = row["error_code"]
        if error_code is not None and not isinstance(error_code, str):
            raise _corrupt("教学库数据损坏：roster_imports.error_code 结构不符。")
        for field in ("created_at", "updated_at"):
            value = row[field]
            if not isinstance(value, str) or not value:
                raise _corrupt(f"教学库数据损坏：roster_imports.{field} 不是非空字符串。")
        rows = self._rows_in(conn, row["id"])
        warnings = _load_warnings(row["warnings_json"])
        return RosterImportRecord(
            import_id=row["id"],
            owner_id=row["owner_id"],
            class_id=row["class_id"],
            class_name=class_name,
            file_asset_id=row["file_asset_id"],
            state=state,
            revision=revision,
            mapping=_load_mapping(row["mapping_json"]),
            warnings=warnings,
            error_code=error_code,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            rows=rows,
        )

    def _rows_in(
        self, conn: sqlite3.Connection, import_id: str
    ) -> tuple[RosterRowRecord, ...]:
        rows = conn.execute(_SELECT_ROWS, (import_id,)).fetchall()
        records: list[RosterRowRecord] = []
        for row in rows:
            row_no = row["row_no"]
            if not isinstance(row_no, int) or isinstance(row_no, bool) or row_no < 1:
                raise _corrupt("教学库数据损坏：roster_import_rows.row_no 不是正整数。")
            name = row["name"]
            if not isinstance(name, str):
                raise _corrupt("教学库数据损坏：roster_import_rows.name 不是字符串。")
            student_no = row["student_no"]
            if student_no is not None and not isinstance(student_no, str):
                raise _corrupt("教学库数据损坏：roster_import_rows.student_no 结构不符。")
            decision = row["decision"]
            if decision is not None and decision not in ("link", "create", "ignore"):
                raise _corrupt(f"教学库数据损坏：行决定结构不符（{decision!r}）。")
            records.append(
                RosterRowRecord(
                    row_no=row_no,
                    name=name,
                    student_no=student_no,
                    matched_student_id=row["matched_student_id"],
                    matched_student_name=row["matched_student_name"],
                    decision=decision,
                    issues=_load_issues(row["issues_json"]),
                    raw_cells=_load_raw_cells(row["raw_cells_json"]),
                )
            )
        return tuple(records)

    @staticmethod
    def _summary(row: sqlite3.Row) -> RosterImportSummary:
        class_name = row["class_name"]
        if class_name is not None and (not isinstance(class_name, str) or not class_name):
            raise _corrupt("教学库数据损坏：roster_imports.class_name 结构不符。")
        uploaded_file_name = row["uploaded_file_name"]
        if uploaded_file_name is not None and (
            not isinstance(uploaded_file_name, str) or not uploaded_file_name
        ):
            raise _corrupt("教学库数据损坏：file_assets.original_name 结构不符。")
        return RosterImportSummary(
            importId=row["id"],
            classId=row["class_id"],
            # 名称优先：JOIN classes.name / file_assets.original_name 实时补展示名；
            # 关联缺失时为 None（不伪造名称），字段保留以兼容旧前端。
            className=class_name,
            uploadedFileName=uploaded_file_name,
            state=row["state"],
            revision=row["revision"],
            rowCount=row["row_count"],
            blockingIssueCount=row["blocking_count"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )


__all__ = [
    "BLOCKING_ISSUE_CODES",
    "DEFAULT_OWNER_ID",
    "ROSTER_IMPORT_NOT_FOUND",
    "ROSTER_NAME_CONFLICT",
    "ROSTER_ROW_CORRUPT",
    "ROSTER_ROW_DUPLICATE",
    "RosterImportRecord",
    "RosterImportRepository",
    "RosterRowPayload",
    "RosterRowRecord",
    "RowDecision",
]
