"""成绩导入 / 修订 / 矩阵仓储（TEACHING-LOOP B3 / T60）：只做 SQL，不含业务闸门。

表已由教学库迁移 ``0006_teaching_score_tables`` 登记（``score_imports`` /
``score_import_rows`` / ``score_revisions`` / ``student_item_scores`` /
``score_revision_corrections``）；本模块不建表、不改 DDL。纪律与其余教学库仓储一致：
读走 ``catalog.read_connection()``，写走 ``catalog.write_transaction()``，
``*_in(conn, ...)`` 方法要求调用方已持有写事务。

持久化口径（自由列 JSON 的唯一形状，服务层负责生成）：

- ``score_import_rows.raw_cells_json``：单元格数组，每项
  ``{row, column, text, cachedText, isFormula, correctedText?}``——``text`` 是公式视图原文、
  ``cachedText`` 是 data_only 缓存视图；教师 PATCH 校正后只追加 ``correctedText``，
  **原件两视图保留不覆盖**（预览展示与解析用 ``correctedText ?? (isFormula ? cachedText : text)``）；
- ``score_imports.summary_json``：预览摘要/警告/``updatedAt``/承认范围（DDL 没有
  ``updated_at`` 列，导入实体的更新时间由这里承载，缺失时回退 ``created_at``）；
- ``score_import_rows.participant_id``：只存**教师显式指定**的参测人次；自动匹配
  （学号文本 → 姓名）在服务层每次重算，服务端不猜也不把猜测固化；
- ``score_import_rows.issues_json``：最近一次生效写入时的行问题（审计证据），
  读取路径以同一解析函数实时重算，避免用旧结论放行；
- ``score_revisions.participant_snapshot_json`` / ``item_snapshot_json``：冻结的参测人次与
  固定计分叶（封存闸门按**该修订自己的**快照核完整性）。

结构非法（状态不在白名单、JSON 损坏、行号/坐标非法）一律 ``SCORE_ROW_CORRUPT``（500），
不静默放行。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contracts.scores import (
    SCORE_ASSESSMENT_REVISION_CONFLICT,
    SCORE_IMPORT_NOT_FOUND,
    SCORE_IMPORT_REVISION_CONFLICT,
    SCORE_IMPORT_STATES,
    ScoreImportState,
    ScoreItemSnapshot,
    ScoreParticipantSnapshot,
    ScoreRawCellView,
    ScoreRevisionState,
    ScoreRevisionView,
)
from app.contracts.teaching_loop import ErrorIssue, error_details
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.catalog import TeachingCatalog

DEFAULT_OWNER_ID = "local"
MAX_PAGE_LIMIT = 200
SCORE_REVISION_STATES: frozenset[str] = frozenset({"draft", "confirmed"})

#: 读取时结构非法（500）：不静默放行损坏的批次/行/修订。
SCORE_ROW_CORRUPT = "SCORE_ROW_CORRUPT"

_SELECT_IMPORT = """
SELECT i.id, i.assessment_id, i.file_id, i.base_score_revision_id,
       i.mapping_json, i.state, i.revision, i.preview_version, i.work_sheet,
       i.summary_json, i.created_at, a.title AS assessment_title
  FROM score_imports i
  JOIN assessments a ON a.id = i.assessment_id
"""

_SELECT_ROWS = """
SELECT row_no, participant_id, raw_cells_json, issues_json
  FROM score_import_rows
 WHERE import_id = ?
 ORDER BY row_no ASC
"""

_SELECT_REVISION = """
SELECT id, assessment_id, version, source_import_id, base_revision_id, state,
       participant_snapshot_json, item_snapshot_json, confirmed_at, created_at,
       (SELECT paper_revision_id FROM assessments
        WHERE assessments.id=score_revisions.assessment_id) AS paper_revision_id
  FROM score_revisions
"""


# --------------------------------------------------------------------------- 小工具


def _invalid(message: str, *, fields: list[str] | None = None) -> AppError:
    return AppError(
        message,
        code="INVALID_REQUEST",
        status_code=422,
        details=error_details(fields=fields) if fields else None,
    )


def _corrupt(message: str) -> AppError:
    return AppError(message, code=SCORE_ROW_CORRUPT, status_code=500)


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。", fields=[field])
    return value.strip()


def _load_json(raw: object, *, table: str, column: str) -> Any:
    if not isinstance(raw, str):
        raise _corrupt(f"教学库数据损坏：{table}.{column} 不是文本。")
    try:
        return json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise _corrupt(f"教学库数据损坏：{table}.{column} 不是合法 JSON。") from exc


def _dump_json(value: Any) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise _invalid("批次数据必须是可序列化的 JSON。") from exc


def _check_page(*, offset: int, limit: int) -> None:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise _invalid("offset 必须是不小于 0 的整数。", fields=["offset"])
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 1
        or limit > MAX_PAGE_LIMIT
    ):
        raise _invalid(f"limit 必须是 1..{MAX_PAGE_LIMIT} 的整数。", fields=["limit"])


def _check_import_state(value: object) -> ScoreImportState:
    if not isinstance(value, str) or value not in SCORE_IMPORT_STATES:
        raise _corrupt(f"教学库数据损坏：score_imports.state 结构不符（{value!r}）。")
    return value  # type: ignore[return-value]


# --------------------------------------------------------------------------- 单元格


@dataclass(frozen=True)
class RawCellRecord:
    """``raw_cells_json`` 中的一格（原件两视图 + 可选教师校正）。"""

    row: int
    column: str
    text: str
    cached_text: str
    is_formula: bool
    corrected_text: str | None = None

    def has_correction(self) -> bool:
        return self.corrected_text is not None

    def parse_input(self) -> str:
        """解析输入文本：教师校正优先，公式单元格用缓存视图，其余用公式视图。"""
        if self.corrected_text is not None:
            return self.corrected_text
        return self.cached_text if self.is_formula else self.text

    def view(self) -> ScoreRawCellView:
        """对外视图：未校正时 ``text``=公式视图、``cachedText``=缓存视图（与契约一致）；
        教师校正后显示生效的校正值（原始两视图仍在 ``raw_cells_json`` 内，供审计）。"""
        if self.corrected_text is not None:
            return ScoreRawCellView(
                row=self.row,
                column=self.column,
                text=self.corrected_text,
                cachedText=self.corrected_text,
                isFormula=False,
                originalText=self.text,
                originalCachedText=self.cached_text,
                correctedText=self.corrected_text,
            )
        return ScoreRawCellView(
            row=self.row,
            column=self.column,
            text=self.text,
            cachedText=self.cached_text,
            isFormula=self.is_formula,
            originalText=self.text,
            originalCachedText=self.cached_text,
        )

    def dump(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "row": self.row,
            "column": self.column,
            "text": self.text,
            "cachedText": self.cached_text,
            "isFormula": self.is_formula,
        }
        if self.corrected_text is not None:
            payload["correctedText"] = self.corrected_text
        return payload


def dump_cells(cells: Sequence[RawCellRecord]) -> str:
    return _dump_json([cell.dump() for cell in cells])


def load_cells(raw: object, *, import_id: str, row_no: int) -> tuple[RawCellRecord, ...]:
    value = _load_json(raw, table="score_import_rows", column="raw_cells_json")
    if not isinstance(value, list):
        raise _corrupt(
            f"教学库数据损坏：批次 {import_id} 第 {row_no} 行 raw_cells_json 不是数组。"
        )
    cells: list[RawCellRecord] = []
    for item in value:
        if not isinstance(item, dict):
            raise _corrupt(f"教学库数据损坏：批次 {import_id} 第 {row_no} 行单元格不是对象。")
        row = item.get("row")
        column = item.get("column")
        text = item.get("text", "")
        cached = item.get("cachedText", "")
        flag = item.get("isFormula", False)
        corrected = item.get("correctedText")
        if not isinstance(row, int) or isinstance(row, bool) or row < 1:
            raise _corrupt(f"教学库数据损坏：批次 {import_id} 第 {row_no} 行单元格行号非法。")
        if not isinstance(column, str) or not column or len(column) > 3:
            raise _corrupt(f"教学库数据损坏：批次 {import_id} 第 {row_no} 行单元格列字母非法。")
        if not isinstance(text, str) or not isinstance(cached, str):
            raise _corrupt(f"教学库数据损坏：批次 {import_id} 第 {row_no} 行单元格文本非法。")
        if not isinstance(flag, bool):
            raise _corrupt(f"教学库数据损坏：批次 {import_id} 第 {row_no} 行 isFormula 非法。")
        if corrected is not None and not isinstance(corrected, str):
            raise _corrupt(f"教学库数据损坏：批次 {import_id} 第 {row_no} 行校正文本非法。")
        cells.append(
            RawCellRecord(
                row=row,
                column=column.upper(),
                text=text,
                cached_text=cached,
                is_formula=flag,
                corrected_text=corrected,
            )
        )
    return tuple(cells)


# --------------------------------------------------------------------------- 记录


@dataclass(frozen=True)
class ScoreImportRowRecord:
    """``score_import_rows`` 一行。``participant_id`` 只存教师显式指定值。"""

    row_no: int
    participant_id: str | None
    cells: tuple[RawCellRecord, ...]
    issues: tuple[ErrorIssue, ...]

    def cell_map(self) -> dict[str, RawCellRecord]:
        return {cell.column: cell for cell in self.cells}


@dataclass(frozen=True)
class ScoreImportRecord:
    """``score_imports`` 一行（+ 关联施测标题与预览行）。"""

    import_id: str
    assessment_id: str
    assessment_title: str
    file_asset_id: str
    base_score_revision_id: str | None
    state: ScoreImportState
    revision: int
    preview_version: int
    work_sheet: str | None
    mapping: dict[str, Any] | None
    summary: dict[str, Any]
    created_at: str
    rows: tuple[ScoreImportRowRecord, ...] = ()
    row_count: int = 0

    @property
    def updated_at(self) -> str:
        value = self.summary.get("updatedAt")
        return value if isinstance(value, str) and value else self.created_at

    @property
    def warnings(self) -> tuple[str, ...]:
        value = self.summary.get("warnings")
        if not isinstance(value, list):
            return ()
        return tuple(item for item in value if isinstance(item, str))

    def row(self, row_no: int) -> ScoreImportRowRecord | None:
        for item in self.rows:
            if item.row_no == row_no:
                return item
        return None


@dataclass(frozen=True)
class ScoreRevisionRecord:
    """``score_revisions`` 一行（含冻结快照）。"""

    revision_id: str
    assessment_id: str
    paper_revision_id: str
    version: int
    state: ScoreRevisionState
    source_import_id: str | None
    base_revision_id: str | None
    participant_snapshot: tuple[ScoreParticipantSnapshot, ...]
    item_snapshot: tuple[ScoreItemSnapshot, ...]
    confirmed_at: str | None
    created_at: str

    def view(self) -> ScoreRevisionView:
        return ScoreRevisionView(
            revisionId=self.revision_id,
            assessmentId=self.assessment_id,
            paperRevisionId=self.paper_revision_id,
            version=self.version,
            state=self.state,
            sourceImportId=self.source_import_id,
            baseRevisionId=self.base_revision_id,
            participantSnapshot=[item.model_dump(by_alias=True) for item in self.participant_snapshot],
            itemSnapshot=[item.model_dump(by_alias=True) for item in self.item_snapshot],
            confirmedAt=self.confirmed_at,
            createdAt=self.created_at,
        )

    def participant_ids(self) -> tuple[str, ...]:
        return tuple(item.participant_id for item in self.participant_snapshot)

    def item_ids(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.item_snapshot)


@dataclass(frozen=True)
class ScoreMatrixCellRecord:
    """``student_item_scores`` 一格的读回值。"""

    participant_id: str
    item_id: str
    status: str
    score_units: int | None


@dataclass(frozen=True)
class MatrixStats:
    """修订级 missing/absent 口径统计（与导入预览同口径）。"""

    missing_participant_ids: tuple[str, ...]
    missing_cell_count: int
    absent_participant_ids: tuple[str, ...]


@dataclass(frozen=True)
class ScoreCorrectionRecord:
    revision_id: str
    seq: int
    participant_id: str
    item_id: str
    old_status: str
    old_score_units: int | None
    new_status: str
    new_score_units: int | None
    reason: str
    created_at: str


@dataclass(frozen=True)
class AssessmentContext:
    """施测三版本校验所需的最小读取面（含 ``active_score_revision_id``）。

    ``AssessmentRepository`` 的 ``AssessmentRecord`` 不暴露 active 成绩指针，而成绩确认的
    ``baseScoreRevisionId`` 语义必须与它比较；这里只读该列（+ 版本/原卷/标题），不复制其它字段。
    """

    assessment_id: str
    title: str
    revision: int
    paper_revision_id: str
    active_score_revision_id: str | None


@dataclass(frozen=True)
class RowPayload:
    """写入一行的值（服务层解析结果；``issues`` 是审计证据）。"""

    row_no: int
    participant_id: str | None
    cells: tuple[RawCellRecord, ...]
    issues: tuple[ErrorIssue, ...] = field(default_factory=tuple)


def _normalize_issue(issue: object) -> ErrorIssue:
    if isinstance(issue, ErrorIssue):
        return issue
    if isinstance(issue, dict):
        try:
            return ErrorIssue.model_validate(issue)
        except Exception as exc:  # pragma: no cover - 形状由服务层保证
            raise _corrupt(f"教学库数据损坏：issues 元素结构不符（{exc.__class__.__name__}）。") from exc
    raise _corrupt("教学库数据损坏：issues 元素不是对象。")


def load_issues(raw: object, *, import_id: str, row_no: int) -> tuple[ErrorIssue, ...]:
    value = _load_json(raw, table="score_import_rows", column="issues_json")
    if not isinstance(value, list):
        raise _corrupt(f"教学库数据损坏：批次 {import_id} 第 {row_no} 行 issues_json 不是数组。")
    return tuple(_normalize_issue(item) for item in value)


# --------------------------------------------------------------------------- 仓储


class ScoreRepository:
    """成绩五表的唯一读写入口；调用方注入已迁移的 ``TeachingCatalog``。"""

    def __init__(self, catalog: TeachingCatalog) -> None:
        self._catalog = catalog

    # -------------------------------------------------------------- 导入批次写

    def create_import_in(
        self,
        conn: sqlite3.Connection,
        *,
        assessment_id: str,
        file_asset_id: str,
        base_score_revision_id: str | None,
        work_sheet: str | None,
        mapping: Mapping[str, Any] | None,
        summary: Mapping[str, Any],
        rows: Sequence[RowPayload],
        state: ScoreImportState = "reviewing",
        import_id: str | None = None,
    ) -> ScoreImportRecord:
        assessment_id = _require_text(assessment_id, field="assessmentId")
        file_asset_id = _require_text(file_asset_id, field="fileAssetId")
        _check_import_state(state)
        if base_score_revision_id is not None:
            base_score_revision_id = _require_text(
                base_score_revision_id, field="baseScoreRevisionId"
            )
        new_id = import_id or uuid.uuid4().hex
        now = now_iso()
        payload = dict(summary)
        payload.setdefault("updatedAt", now)
        conn.execute(
            "INSERT INTO score_imports "
            "(id, assessment_id, file_id, base_score_revision_id, mapping_json, state, "
            " revision, preview_version, work_sheet, summary_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)",
            (
                new_id,
                assessment_id,
                file_asset_id,
                base_score_revision_id,
                _dump_json(dict(mapping) if mapping is not None else {}),
                state,
                work_sheet,
                _dump_json(payload),
                now,
            ),
        )
        self.insert_rows_in(conn, new_id, rows)
        return self.require_in(conn, new_id)

    def insert_rows_in(
        self, conn: sqlite3.Connection, import_id: str, rows: Sequence[RowPayload]
    ) -> None:
        import_id = _require_text(import_id, field="importId")
        for row in rows:
            if not isinstance(row, RowPayload):
                raise _invalid("rows 元素必须是 RowPayload。")
            if not isinstance(row.row_no, int) or isinstance(row.row_no, bool) or row.row_no < 1:
                raise _invalid("row_no 必须是不小于 1 的整数。", fields=["rowNo"])
            conn.execute(
                "INSERT INTO score_import_rows "
                "(import_id, row_no, participant_id, raw_cells_json, issues_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    import_id,
                    row.row_no,
                    row.participant_id,
                    dump_cells(row.cells),
                    _dump_json([issue.model_dump(exclude_none=True) for issue in row.issues]),
                ),
            )

    def replace_rows_in(
        self, conn: sqlite3.Connection, import_id: str, rows: Sequence[RowPayload]
    ) -> None:
        """整批替换预览行（换工作表/改映射后重算；行号由服务层保证唯一）。"""
        import_id = _require_text(import_id, field="importId")
        conn.execute("DELETE FROM score_import_rows WHERE import_id = ?", (import_id,))
        self.insert_rows_in(conn, import_id, rows)

    def apply_patch_in(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        *,
        expected_revision: int,
        mapping: Mapping[str, Any] | None = None,
        work_sheet: str | None = None,
        replace_rows: Sequence[RowPayload] | None = None,
        row_updates: Sequence[RowPayload] | None = None,
        summary: Mapping[str, Any] | None = None,
    ) -> ScoreImportRecord:
        """一次生效 PATCH 的全部 SQL；成功则 ``revision`` 与 ``preview_version`` 各 +1。"""
        import_id = _require_text(import_id, field="importId")
        current = self.require_in(conn, import_id)
        _check_revision(current.revision, expected_revision)
        if replace_rows is not None:
            self.replace_rows_in(conn, import_id, replace_rows)
        if row_updates is not None:
            self.update_rows_in(conn, import_id, row_updates)
        if mapping is not None:
            conn.execute(
                "UPDATE score_imports SET mapping_json = ? WHERE id = ?",
                (_dump_json(dict(mapping)), import_id),
            )
        if work_sheet is not None:
            conn.execute(
                "UPDATE score_imports SET work_sheet = ? WHERE id = ?",
                (work_sheet, import_id),
            )
        if summary is not None:
            conn.execute(
                "UPDATE score_imports SET summary_json = ? WHERE id = ?",
                (_dump_json(dict(summary)), import_id),
            )
        now = now_iso()
        conn.execute(
            "UPDATE score_imports "
            "SET revision = revision + 1, preview_version = preview_version + 1, "
            "    summary_json = json_set(summary_json, '$.updatedAt', ?) "
            "WHERE id = ?",
            (now, import_id),
        )
        return self.require_in(conn, import_id)

    def mark_confirmed_in(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        *,
        expected_revision: int,
        summary: Mapping[str, Any] | None = None,
    ) -> ScoreImportRecord:
        """确认成功时的终态写入：state=confirmed + revision+1（同一事务）。"""
        import_id = _require_text(import_id, field="importId")
        current = self.require_in(conn, import_id)
        _check_revision(current.revision, expected_revision)
        if summary is not None:
            conn.execute(
                "UPDATE score_imports SET summary_json = ? WHERE id = ?",
                (_dump_json(dict(summary)), import_id),
            )
        now = now_iso()
        conn.execute(
            "UPDATE score_imports SET state = 'confirmed', revision = revision + 1, "
            "summary_json = json_set(summary_json, '$.updatedAt', ?) WHERE id = ?",
            (now, import_id),
        )
        return self.require_in(conn, import_id)

    def update_rows_in(
        self, conn: sqlite3.Connection, import_id: str, rows: Sequence[RowPayload]
    ) -> None:
        """按行号更新既有预览行（行不存在 → 422）；确认时也用于冻结生效人次与问题。"""
        for row in rows:
            if not isinstance(row, RowPayload):
                raise _invalid("row_updates 元素必须是 RowPayload。")
            cursor = conn.execute(
                "UPDATE score_import_rows "
                "SET participant_id = ?, raw_cells_json = ?, issues_json = ? "
                "WHERE import_id = ? AND row_no = ?",
                (
                    row.participant_id,
                    dump_cells(row.cells),
                    _dump_json(
                        [issue.model_dump(exclude_none=True) for issue in row.issues]
                    ),
                    import_id,
                    row.row_no,
                ),
            )
            if cursor.rowcount != 1:
                raise _invalid(
                    f"批次中不存在第 {row.row_no} 行。", fields=["rows"]
                )

    # -------------------------------------------------------------- 导入批次读

    def get_in(
        self, conn: sqlite3.Connection, import_id: str, *, with_rows: bool = True
    ) -> ScoreImportRecord | None:
        if not isinstance(import_id, str) or not import_id.strip():
            raise _invalid("import_id 必须是非空字符串。", fields=["importId"])
        row = conn.execute(
            f"{_SELECT_IMPORT} WHERE i.id = ?", (import_id.strip(),)
        ).fetchone()
        if row is None:
            return None
        return self._record(conn, row, with_rows=with_rows)

    def require_in(
        self, conn: sqlite3.Connection, import_id: str, *, with_rows: bool = True
    ) -> ScoreImportRecord:
        record = self.get_in(conn, import_id, with_rows=with_rows)
        if record is None:
            raise AppError(
                f"成绩导入批次不存在：{import_id}。",
                code=SCORE_IMPORT_NOT_FOUND,
                status_code=404,
            )
        return record

    def get(self, import_id: str) -> ScoreImportRecord:
        with self._catalog.read_connection() as conn:
            return self.require_in(conn, import_id)

    def list_in(
        self,
        conn: sqlite3.Connection,
        *,
        assessment_id: str | None = None,
        state: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ScoreImportRecord], int]:
        _check_page(offset=offset, limit=limit)
        if state is not None and state not in SCORE_IMPORT_STATES:
            raise _invalid(f"state 必须是 {sorted(SCORE_IMPORT_STATES)} 之一。", fields=["state"])
        conditions: list[str] = []
        params: list[object] = []
        if assessment_id is not None:
            conditions.append("i.assessment_id = ?")
            params.append(_require_text(assessment_id, field="assessmentId"))
        if state is not None:
            conditions.append("i.state = ?")
            params.append(state)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        total = int(
            conn.execute(
                f"SELECT COUNT(*) AS n FROM score_imports i {where}", tuple(params)
            ).fetchone()["n"]
        )
        rows = conn.execute(
            f"{_SELECT_IMPORT} {where} "
            "ORDER BY i.created_at DESC, i.rowid DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [self._record(conn, row, with_rows=False) for row in rows], total

    # -------------------------------------------------------------- 成绩修订写

    def next_version_in(self, conn: sqlite3.Connection, assessment_id: str) -> int:
        assessment_id = _require_text(assessment_id, field="assessmentId")
        row = conn.execute(
            "SELECT coalesce(max(version), 0) AS v FROM score_revisions "
            "WHERE assessment_id = ?",
            (assessment_id,),
        ).fetchone()
        version = row["v"]
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise _corrupt("教学库数据损坏：score_revisions.version 不是非负整数。")
        return version + 1

    def insert_revision_in(
        self,
        conn: sqlite3.Connection,
        *,
        assessment_id: str,
        version: int,
        source_import_id: str | None,
        base_revision_id: str | None,
        participant_snapshot: Sequence[ScoreParticipantSnapshot],
        item_snapshot: Sequence[ScoreItemSnapshot],
        revision_id: str | None = None,
        state: ScoreRevisionState = "draft",
    ) -> str:
        assessment_id = _require_text(assessment_id, field="assessmentId")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise _invalid("version 必须是不小于 1 的整数。")
        if state not in SCORE_REVISION_STATES:
            raise _invalid(f"state 必须是 {sorted(SCORE_REVISION_STATES)} 之一。")
        if not participant_snapshot or not item_snapshot:
            # 空快照一律拒绝：draft 可以短暂为空，但本服务只写完整矩阵版本
            raise AppError(
                "成绩修订必须携带非空的参测人次与计分叶快照。",
                code="SCORE_MATRIX_INCOMPLETE",
                status_code=422,
            )
        new_id = revision_id or uuid.uuid4().hex
        conn.execute(
            "INSERT INTO score_revisions "
            "(id, assessment_id, version, source_import_id, base_revision_id, state, "
            " participant_snapshot_json, item_snapshot_json, confirmed_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
            (
                new_id,
                assessment_id,
                version,
                source_import_id,
                base_revision_id,
                state,
                _dump_json(
                    [
                        item.model_dump(by_alias=True, exclude_none=False)
                        for item in participant_snapshot
                    ]
                ),
                _dump_json(
                    [item.model_dump(by_alias=True) for item in item_snapshot]
                ),
                now_iso(),
            ),
        )
        return new_id

    def insert_matrix_in(
        self,
        conn: sqlite3.Connection,
        *,
        revision_id: str,
        assessment_id: str,
        paper_revision_id: str,
        cells: Sequence[tuple[str, str, str, int | None]],
    ) -> None:
        """写全矩阵：``(participant_id, item_id, status, score_units)`` 逐格插入。"""
        revision_id = _require_text(revision_id, field="revisionId")
        assessment_id = _require_text(assessment_id, field="assessmentId")
        paper_revision_id = _require_text(paper_revision_id, field="paperRevisionId")
        conn.executemany(
            "INSERT INTO student_item_scores "
            "(score_revision_id, assessment_id, paper_revision_id, participant_id, "
            " item_id, score_units, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    revision_id,
                    assessment_id,
                    paper_revision_id,
                    participant_id,
                    item_id,
                    score_units,
                    status,
                )
                for participant_id, item_id, status, score_units in cells
            ],
        )

    def seal_revision_in(self, conn: sqlite3.Connection, revision_id: str) -> None:
        """封存：draft → confirmed；封存闸门按该修订自己的快照核矩阵完整性。"""
        revision_id = _require_text(revision_id, field="revisionId")
        cursor = conn.execute(
            "UPDATE score_revisions SET state = 'confirmed', confirmed_at = ? "
            "WHERE id = ? AND state = 'draft'",
            (now_iso(), revision_id),
        )
        if cursor.rowcount != 1:
            row = conn.execute(
                "SELECT state FROM score_revisions WHERE id = ?", (revision_id,)
            ).fetchone()
            if row is None:
                raise self._revision_not_found(revision_id)
            raise AppError(
                "成绩修订不处于可封存状态，请刷新后重试。",
                code="SCORE_REVISION_IMMUTABLE",
                status_code=409,
            )

    def set_active_revision_in(
        self,
        conn: sqlite3.Connection,
        assessment_id: str,
        *,
        revision_id: str,
        expected_revision: int,
    ) -> int:
        """推进 active 指针与施测版本（乐观锁）；返回新的 assessment.revision。"""
        assessment_id = _require_text(assessment_id, field="assessmentId")
        cursor = conn.execute(
            "UPDATE assessments SET active_score_revision_id = ?, revision = revision + 1 "
            "WHERE id = ? AND revision = ?",
            (revision_id, assessment_id, expected_revision),
        )
        if cursor.rowcount != 1:
            row = conn.execute(
                "SELECT revision FROM assessments WHERE id = ?", (assessment_id,)
            ).fetchone()
            if row is None:
                raise AppError(
                    f"施测不存在：{assessment_id}。",
                    code="ASSESSMENT_NOT_FOUND",
                    status_code=404,
                )
            current = row["revision"]
            raise AppError(
                "施测已被其他操作更新，请刷新后重试。",
                code=SCORE_ASSESSMENT_REVISION_CONFLICT,
                status_code=409,
                details=error_details(current_revision=current),
            )
        row = conn.execute(
            "SELECT revision FROM assessments WHERE id = ?", (assessment_id,)
        ).fetchone()
        assert row is not None  # pragma: no cover - 刚更新过
        revision = row["revision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise _corrupt("教学库数据损坏：assessments.revision 不是非负整数。")
        return revision

    def insert_corrections_in(
        self,
        conn: sqlite3.Connection,
        revision_id: str,
        entries: Sequence[ScoreCorrectionRecord],
    ) -> None:
        revision_id = _require_text(revision_id, field="revisionId")
        for seq, entry in enumerate(entries, start=1):
            if not isinstance(entry, ScoreCorrectionRecord):
                raise _invalid("corrections 元素必须是 ScoreCorrectionRecord。")
            conn.execute(
                "INSERT INTO score_revision_corrections "
                "(revision_id, seq, participant_id, item_id, old_status, old_score_units, "
                " new_status, new_score_units, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    revision_id,
                    seq,
                    entry.participant_id,
                    entry.item_id,
                    entry.old_status,
                    entry.old_score_units,
                    entry.new_status,
                    entry.new_score_units,
                    entry.reason,
                    entry.created_at,
                ),
            )

    # -------------------------------------------------------------- 成绩修订读

    def get_revision_in(
        self, conn: sqlite3.Connection, revision_id: str
    ) -> ScoreRevisionRecord | None:
        if not isinstance(revision_id, str) or not revision_id.strip():
            raise _invalid("revision_id 必须是非空字符串。", fields=["revisionId"])
        row = conn.execute(
            f"{_SELECT_REVISION} WHERE id = ?", (revision_id.strip(),)
        ).fetchone()
        if row is None:
            return None
        return self._revision(row)

    def require_revision_in(
        self, conn: sqlite3.Connection, revision_id: str
    ) -> ScoreRevisionRecord:
        record = self.get_revision_in(conn, revision_id)
        if record is None:
            raise self._revision_not_found(revision_id)
        return record

    def get_revision(self, revision_id: str) -> ScoreRevisionRecord:
        with self._catalog.read_connection() as conn:
            return self.require_revision_in(conn, revision_id)

    def assessment_context_in(
        self, conn: sqlite3.Connection, assessment_id: str
    ) -> AssessmentContext | None:
        if not isinstance(assessment_id, str) or not assessment_id.strip():
            raise _invalid("assessment_id 必须是非空字符串。", fields=["assessmentId"])
        row = conn.execute(
            "SELECT id, title, revision, paper_revision_id, active_score_revision_id "
            "FROM assessments WHERE id = ?",
            (assessment_id.strip(),),
        ).fetchone()
        if row is None:
            return None
        revision = row["revision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise _corrupt("教学库数据损坏：assessments.revision 不是非负整数。")
        title = row["title"]
        if not isinstance(title, str) or not title:
            raise _corrupt("教学库数据损坏：assessments.title 不是非空字符串。")
        paper_revision_id = row["paper_revision_id"]
        if not isinstance(paper_revision_id, str) or not paper_revision_id:
            raise _corrupt("教学库数据损坏：assessments.paper_revision_id 不是非空字符串。")
        active = row["active_score_revision_id"]
        if active is not None and (not isinstance(active, str) or not active):
            raise _corrupt(
                "教学库数据损坏：assessments.active_score_revision_id 结构不符。"
            )
        return AssessmentContext(
            assessment_id=row["id"],
            title=title,
            revision=revision,
            paper_revision_id=paper_revision_id,
            active_score_revision_id=active,
        )

    def list_revisions_in(
        self, conn: sqlite3.Connection, assessment_id: str
    ) -> list[ScoreRevisionRecord]:
        assessment_id = _require_text(assessment_id, field="assessmentId")
        rows = conn.execute(
            f"{_SELECT_REVISION} WHERE assessment_id = ? ORDER BY version ASC, rowid ASC",
            (assessment_id,),
        ).fetchall()
        return [self._revision(row) for row in rows]

    def list_corrections_in(
        self, conn: sqlite3.Connection, revision_id: str
    ) -> list[ScoreCorrectionRecord]:
        revision_id = _require_text(revision_id, field="revisionId")
        rows = conn.execute(
            "SELECT revision_id, seq, participant_id, item_id, old_status, old_score_units, "
            "new_status, new_score_units, reason, created_at "
            "FROM score_revision_corrections WHERE revision_id = ? ORDER BY seq ASC",
            (revision_id,),
        ).fetchall()
        return [
            ScoreCorrectionRecord(
                revision_id=row["revision_id"],
                seq=row["seq"],
                participant_id=row["participant_id"],
                item_id=row["item_id"],
                old_status=row["old_status"],
                old_score_units=row["old_score_units"],
                new_status=row["new_status"],
                new_score_units=row["new_score_units"],
                reason=row["reason"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def matrix_cells_in(
        self,
        conn: sqlite3.Connection,
        revision_id: str,
        *,
        participant_ids: Sequence[str] | None = None,
    ) -> list[ScoreMatrixCellRecord]:
        revision_id = _require_text(revision_id, field="revisionId")
        params: list[object] = [revision_id]
        clause = ""
        if participant_ids is not None:
            if not participant_ids:
                return []
            placeholders = ", ".join("?" for _ in participant_ids)
            clause = f" AND participant_id IN ({placeholders})"
            params.extend(participant_ids)
        rows = conn.execute(
            "SELECT participant_id, item_id, status, score_units FROM student_item_scores "
            f"WHERE score_revision_id = ?{clause} ORDER BY participant_id ASC, item_id ASC",
            tuple(params),
        ).fetchall()
        cells: list[ScoreMatrixCellRecord] = []
        for row in rows:
            status = row["status"]
            if not isinstance(status, str) or status not in {
                "recorded",
                "missing",
                "absent",
                "exempt",
            }:
                raise _corrupt("教学库数据损坏：student_item_scores.status 结构不符。")
            units = row["score_units"]
            if units is not None and (
                not isinstance(units, int) or isinstance(units, bool) or units < 0
            ):
                raise _corrupt("教学库数据损坏：student_item_scores.score_units 结构不符。")
            if status == "recorded" and units is None:
                raise _corrupt("教学库数据损坏：recorded 单元格缺少 score_units。")
            if status != "recorded" and units is not None:
                raise _corrupt("教学库数据损坏：非 recorded 单元格带有 score_units。")
            cells.append(
                ScoreMatrixCellRecord(
                    participant_id=row["participant_id"],
                    item_id=row["item_id"],
                    status=status,
                    score_units=units,
                )
            )
        return cells

    def matrix_stats_in(
        self, conn: sqlite3.Connection, revision_id: str
    ) -> MatrixStats:
        """修订级 missing/absent 统计（读视图与导入预览同口径）。"""
        revision_id = _require_text(revision_id, field="revisionId")
        rows = conn.execute(
            "SELECT participant_id, status, COUNT(*) AS n FROM student_item_scores "
            "WHERE score_revision_id = ? GROUP BY participant_id, status",
            (revision_id,),
        ).fetchall()
        missing_participants: set[str] = set()
        absent_participants: set[str] = set()
        missing_cells = 0
        for row in rows:
            status = row["status"]
            count = row["n"]
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise _corrupt("教学库数据损坏：矩阵统计不是非负整数。")
            if status == "missing":
                missing_participants.add(row["participant_id"])
                missing_cells += count
            elif status == "absent":
                absent_participants.add(row["participant_id"])
        return MatrixStats(
            missing_participant_ids=tuple(sorted(missing_participants)),
            missing_cell_count=missing_cells,
            absent_participant_ids=tuple(sorted(absent_participants)),
        )

    # -------------------------------------------------------------- 内部

    def _record(
        self, conn: sqlite3.Connection, row: sqlite3.Row, *, with_rows: bool
    ) -> ScoreImportRecord:
        state = _check_import_state(row["state"])
        revision = row["revision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise _corrupt("教学库数据损坏：score_imports.revision 不是非负整数。")
        preview_version = row["preview_version"]
        if (
            not isinstance(preview_version, int)
            or isinstance(preview_version, bool)
            or preview_version < 0
        ):
            raise _corrupt("教学库数据损坏：score_imports.preview_version 不是非负整数。")
        title = row["assessment_title"]
        if not isinstance(title, str) or not title:
            raise _corrupt("教学库数据损坏：批次关联的施测标题缺失。")
        for name in ("created_at",):
            value = row[name]
            if not isinstance(value, str) or not value:
                raise _corrupt(f"教学库数据损坏：score_imports.{name} 不是非空字符串。")
        work_sheet = row["work_sheet"]
        if work_sheet is not None and (not isinstance(work_sheet, str) or not work_sheet):
            raise _corrupt("教学库数据损坏：score_imports.work_sheet 结构不符。")
        mapping_raw = _load_json(
            row["mapping_json"], table="score_imports", column="mapping_json"
        )
        if mapping_raw == {}:
            mapping: dict[str, Any] | None = None
        elif isinstance(mapping_raw, dict):
            mapping = dict(mapping_raw)
        else:
            raise _corrupt("教学库数据损坏：score_imports.mapping_json 不是对象。")
        summary_raw = _load_json(
            row["summary_json"], table="score_imports", column="summary_json"
        )
        if not isinstance(summary_raw, dict):
            raise _corrupt("教学库数据损坏：score_imports.summary_json 不是对象。")
        rows = self._rows_in(conn, row["id"]) if with_rows else ()
        return ScoreImportRecord(
            import_id=row["id"],
            assessment_id=row["assessment_id"],
            assessment_title=title,
            file_asset_id=row["file_id"],
            base_score_revision_id=row["base_score_revision_id"],
            state=state,
            revision=revision,
            preview_version=preview_version,
            work_sheet=work_sheet,
            mapping=mapping,
            summary=dict(summary_raw),
            created_at=row["created_at"],
            rows=rows,
            row_count=len(rows) if with_rows else self._row_count_in(conn, row["id"]),
        )

    def _row_count_in(self, conn: sqlite3.Connection, import_id: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM score_import_rows WHERE import_id = ?",
            (import_id,),
        ).fetchone()
        return int(row["n"])

    def _rows_in(
        self, conn: sqlite3.Connection, import_id: str
    ) -> tuple[ScoreImportRowRecord, ...]:
        rows = conn.execute(_SELECT_ROWS, (import_id,)).fetchall()
        records: list[ScoreImportRowRecord] = []
        for row in rows:
            row_no = row["row_no"]
            if not isinstance(row_no, int) or isinstance(row_no, bool) or row_no < 1:
                raise _corrupt("教学库数据损坏：score_import_rows.row_no 不是正整数。")
            participant_id = row["participant_id"]
            if participant_id is not None and (
                not isinstance(participant_id, str) or not participant_id
            ):
                raise _corrupt("教学库数据损坏：score_import_rows.participant_id 结构不符。")
            records.append(
                ScoreImportRowRecord(
                    row_no=row_no,
                    participant_id=participant_id,
                    cells=load_cells(
                        row["raw_cells_json"], import_id=import_id, row_no=row_no
                    ),
                    issues=load_issues(
                        row["issues_json"], import_id=import_id, row_no=row_no
                    ),
                )
            )
        return tuple(records)

    def _revision(self, row: sqlite3.Row) -> ScoreRevisionRecord:
        state = row["state"]
        if not isinstance(state, str) or state not in SCORE_REVISION_STATES:
            raise _corrupt(f"教学库数据损坏：score_revisions.state 结构不符（{state!r}）。")
        version = row["version"]
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise _corrupt("教学库数据损坏：score_revisions.version 不是正整数。")
        participants_raw = _load_json(
            row["participant_snapshot_json"],
            table="score_revisions",
            column="participant_snapshot_json",
        )
        items_raw = _load_json(
            row["item_snapshot_json"], table="score_revisions", column="item_snapshot_json"
        )
        if not isinstance(participants_raw, list) or not isinstance(items_raw, list):
            raise _corrupt("教学库数据损坏：成绩修订快照不是数组。")
        try:
            participants = tuple(
                ScoreParticipantSnapshot.model_validate(item) for item in participants_raw
            )
            items = tuple(ScoreItemSnapshot.model_validate(item) for item in items_raw)
        except Exception as exc:
            raise _corrupt(
                f"教学库数据损坏：成绩修订快照结构不符（{exc.__class__.__name__}）。"
            ) from exc
        created_at = row["created_at"]
        if not isinstance(created_at, str) or not created_at:
            raise _corrupt("教学库数据损坏：score_revisions.created_at 不是非空字符串。")
        confirmed_at = row["confirmed_at"]
        if confirmed_at is not None and not isinstance(confirmed_at, str):
            raise _corrupt("教学库数据损坏：score_revisions.confirmed_at 结构不符。")
        return ScoreRevisionRecord(
            revision_id=row["id"],
            assessment_id=row["assessment_id"],
            paper_revision_id=row["paper_revision_id"],
            version=version,
            state=state,  # type: ignore[arg-type]
            source_import_id=row["source_import_id"],
            base_revision_id=row["base_revision_id"],
            participant_snapshot=participants,
            item_snapshot=items,
            confirmed_at=confirmed_at,
            created_at=created_at,
        )

    @staticmethod
    def _revision_not_found(revision_id: str) -> AppError:
        return AppError(
            f"成绩修订不存在：{revision_id}。",
            code="SCORE_REVISION_NOT_FOUND",
            status_code=404,
        )


def _check_revision(current: int, expected: int) -> None:
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
        raise _invalid("expectedRevision 必须是不小于 0 的整数。", fields=["expectedRevision"])
    if current != expected:
        raise AppError(
            "成绩导入批次已被其他操作更新，请刷新后重试。",
            code=SCORE_IMPORT_REVISION_CONFLICT,
            status_code=409,
            details=error_details(current_revision=current),
        )


__all__ = [
    "AssessmentContext",
    "DEFAULT_OWNER_ID",
    "MAX_PAGE_LIMIT",
    "MatrixStats",
    "RawCellRecord",
    "RowPayload",
    "SCORE_REVISION_STATES",
    "SCORE_ROW_CORRUPT",
    "ScoreCorrectionRecord",
    "ScoreImportRecord",
    "ScoreImportRowRecord",
    "ScoreMatrixCellRecord",
    "ScoreRepository",
    "ScoreRevisionRecord",
    "dump_cells",
    "load_cells",
]
