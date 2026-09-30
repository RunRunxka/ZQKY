"""知识点导入批次与预览行仓储（TEACHING-LOOP B1 / T20）。

只做 SQL：方法都接收调用方事务里的 ``sqlite3.Connection``，不自己开连接，
不做表格解析/模型调用（那些在服务层、事务外）。

表结构（B1 迁移 0002 冻结 + 0003 追加）：

- ``knowledge_imports``：批次（``source`` / ``subject_id`` / ``file_asset_id`` / ``state`` /
  ``revision`` 乐观锁 / ``mapping_json`` / ``issues_json`` / ``warnings_json`` / ``error_code``）；
- ``knowledge_import_rows``：预览行（``raw_cells_json`` 保存**原始单元格**，映射变化时可
  从原始值重新派生；``issues_json`` 保存 ``ErrorIssue`` 形状的问题；``decision`` 是
  ``create|update|ignore``）。

列语义（0003 起）：

- ``mapping_json`` 只存**映射本身**：``{"code": "编码", "name": "名称", ...}``（``{field: header}``）；
- 批次级 issues（缺列/未知列等）落在 ``issues_json``（``ErrorIssue`` 形状数组，与对外视图
  ``KnowledgeImportView.issues`` 一致）；
- 兼容 0003 之前的旧数据：旧布局把批次级 issues 塞在 ``mapping_json`` 的保留键里
  （``{"mapping": {...}, "issues": [...]}``），读取时宽容解析（取内层映射，旧 issues 与
  ``issues_json`` 合并去重），**新写入一律只用新列**。

``file_asset_id`` 是**跨库逻辑引用**（教学库 ``file_assets``），由服务层核验，本模块不做跨库读取。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contracts.knowledge import (
    KNOWLEDGE_IMPORT_FIELDS,
    KNOWLEDGE_IMPORT_STATES,
    KNOWLEDGE_ROW_ACTIONS,
)
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.knowledge.points import UNSET, corrupt, invalid, revision_conflict

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200


@dataclass(frozen=True)
class ImportRowRecord:
    """``knowledge_import_rows`` 一行（issues 已解析为 ErrorIssue 形状的 dict）。"""

    row_no: int
    name: str
    code: str
    parent_code: str | None
    description: str
    aliases: tuple[str, ...]
    target_knowledge_point_id: str | None
    base_revision: int | None
    base_revision_id: str | None
    decision: str | None
    raw_cells: dict[str, Any]
    issues: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ImportRowInput:
    """待写入的一行预览/候选（服务层派生结果）。"""

    row_no: int
    name: str = ""
    code: str = ""
    parent_code: str | None = None
    description: str = ""
    aliases: Sequence[str] = ()
    target_knowledge_point_id: str | None = None
    base_revision: int | None = None
    base_revision_id: str | None = None
    decision: str | None = None
    raw_cells: dict[str, Any] = field(default_factory=dict)
    issues: Sequence[Any] = ()


@dataclass(frozen=True)
class ImportRecord:
    import_id: str
    owner_id: str
    source: str
    subject_id: str
    file_asset_id: str
    state: str
    revision: int
    mapping: dict[str, str]
    batch_issues: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    error_code: str | None
    created_at: str
    updated_at: str


class KnowledgeImportRepository:
    """``knowledge_imports`` / ``knowledge_import_rows`` 的唯一读写入口。"""

    # ---------------------------------------------------------------- 写入

    def create_import(
        self,
        conn: sqlite3.Connection,
        *,
        source: str,
        subject_id: str,
        file_asset_id: str,
        mapping: dict[str, str] | None = None,
        batch_issues: Sequence[Any] = (),
        warnings: Sequence[str] = (),
        rows: Sequence[ImportRowInput] = (),
        state: str = "reviewing",
        owner_id: str = "local",
        import_id: str | None = None,
    ) -> ImportRecord:
        source = self._choice(source, field="source", allowed=frozenset({"file", "ai"}))
        state = self._choice(state, field="state", allowed=KNOWLEDGE_IMPORT_STATES)
        subject_id = self._text(subject_id, field="subject_id")
        file_asset_id = self._text(file_asset_id, field="file_asset_id")
        owner_id = self._text(owner_id, field="owner_id")
        import_id = uuid.uuid4().hex if import_id is None else self._text(
            import_id, field="import_id"
        )
        now = now_iso()
        try:
            conn.execute(
                "INSERT INTO knowledge_imports "
                "(id, owner_id, source, subject_id, file_asset_id, state, revision, "
                "mapping_json, issues_json, warnings_json, error_code, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, NULL, ?, ?)",
                (
                    import_id,
                    owner_id,
                    source,
                    subject_id,
                    file_asset_id,
                    state,
                    _dump_mapping(mapping),
                    _dump_issues(batch_issues),
                    _dump_warnings(warnings),
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise AppError(
                "知识点导入批次写入失败：学科或数据违反约束。",
                code="KNOWLEDGE_ROW_INVALID",
                status_code=422,
            ) from exc
        if rows:
            self.insert_rows(conn, import_id, rows)
        return self.require_import(conn, import_id)

    def update_import(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        *,
        expected_revision: int,
        state: str | None = None,
        mapping: dict[str, str] | None = None,
        batch_issues: Sequence[Any] | None = None,
        warnings: Sequence[str] | None = None,
        error_code: Any = UNSET,
    ) -> ImportRecord:
        """核乐观锁更新批次；只有实际变化才 ``revision + 1``。"""
        import_id = self._text(import_id, field="import_id")
        current = self.require_import(conn, import_id)
        if current.revision != expected_revision:
            raise revision_conflict(current.revision)
        updates: dict[str, Any] = {}
        if state is not None and state != current.state:
            updates["state"] = self._choice(
                state, field="state", allowed=KNOWLEDGE_IMPORT_STATES
            )
        if mapping is not None and _dump_mapping(mapping) != _dump_mapping(current.mapping):
            updates["mapping_json"] = _dump_mapping(mapping)
        if batch_issues is not None and _dump_issues(batch_issues) != _dump_issues(
            current.batch_issues
        ):
            updates["issues_json"] = _dump_issues(batch_issues)
        if warnings is not None:
            payload = _dump_warnings(warnings)
            if payload != _dump_warnings(current.warnings):
                updates["warnings_json"] = payload
        if error_code is not UNSET and error_code != current.error_code:
            updates["error_code"] = error_code
        if not updates:
            return current
        assignments = ", ".join(f"{column} = ?" for column in updates)
        conn.execute(
            f"UPDATE knowledge_imports SET {assignments}, revision = revision + 1, "
            "updated_at = ? WHERE id = ?",
            (*updates.values(), now_iso(), import_id),
        )
        return self.require_import(conn, import_id)

    def touch_import(self, conn: sqlite3.Connection, import_id: str) -> ImportRecord:
        """仅递增批次乐观锁（改行动作/映射后用），``revision + 1`` + ``updated_at``。"""
        import_id = self._text(import_id, field="import_id")
        self.require_import(conn, import_id)
        conn.execute(
            "UPDATE knowledge_imports SET revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso(), import_id),
        )
        return self.require_import(conn, import_id)

    def mark_confirmed(self, conn: sqlite3.Connection, import_id: str) -> ImportRecord:
        """确认入库：``state = confirmed`` + ``revision + 1``（原子，与业务写入同事务）。"""
        import_id = self._text(import_id, field="import_id")
        current = self.require_import(conn, import_id)
        if current.state == "confirmed":
            return current
        conn.execute(
            "UPDATE knowledge_imports SET state = 'confirmed', revision = revision + 1, "
            "updated_at = ? WHERE id = ?",
            (now_iso(), import_id),
        )
        return self.require_import(conn, import_id)

    def insert_rows(
        self, conn: sqlite3.Connection, import_id: str, rows: Sequence[ImportRowInput]
    ) -> None:
        import_id = self._text(import_id, field="import_id")
        for row in rows:
            values = self._row_values(import_id, row)
            conn.execute(
                "INSERT INTO knowledge_import_rows "
                "(import_id, row_no, name, code, parent_code, description, aliases_json, "
                "target_knowledge_point_id, base_revision, base_revision_id, decision, "
                "raw_cells_json, issues_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                values,
            )

    def replace_rows(
        self, conn: sqlite3.Connection, import_id: str, rows: Sequence[ImportRowInput]
    ) -> None:
        """整组替换预览行（映射变化后从原始单元格重新派生）。"""
        import_id = self._text(import_id, field="import_id")
        conn.execute("DELETE FROM knowledge_import_rows WHERE import_id = ?", (import_id,))
        self.insert_rows(conn, import_id, rows)

    def update_row(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        row_no: int,
        *,
        decision: str | None = None,
        base_revision: int | None = None,
        base_revision_id: str | None = None,
        target_knowledge_point_id: str | None = None,
        issues: Sequence[Any] | None = None,
    ) -> ImportRowRecord:
        import_id = self._text(import_id, field="import_id")
        if not isinstance(row_no, int) or isinstance(row_no, bool) or row_no < 1:
            raise invalid("row_no 必须是不小于 1 的整数。")
        updates: dict[str, Any] = {}
        if decision is not None:
            updates["decision"] = self._choice(
                decision, field="decision", allowed=KNOWLEDGE_ROW_ACTIONS
            )
        if base_revision is not None:
            if not isinstance(base_revision, int) or isinstance(base_revision, bool) or base_revision < 0:
                raise invalid("base_revision 必须是非负整数。")
            updates["base_revision"] = base_revision
        if base_revision_id is not None:
            updates["base_revision_id"] = self._text(base_revision_id, field="base_revision_id")
        if target_knowledge_point_id is not None:
            updates["target_knowledge_point_id"] = self._text(
                target_knowledge_point_id, field="target_knowledge_point_id"
            )
        if issues is not None:
            updates["issues_json"] = _dump_issues(issues)
        if not updates:
            record = self.get_row(conn, import_id, row_no)
            if record is None:
                raise AppError(
                    "知识点导入行不存在。", code="KNOWLEDGE_ROW_INVALID", status_code=422
                )
            return record
        assignments = ", ".join(f"{column} = ?" for column in updates)
        cursor = conn.execute(
            f"UPDATE knowledge_import_rows SET {assignments} "
            "WHERE import_id = ? AND row_no = ?",
            (*updates.values(), import_id, row_no),
        )
        if not cursor.rowcount:
            raise AppError(
                "知识点导入行不存在。", code="KNOWLEDGE_ROW_INVALID", status_code=422
            )
        record = self.get_row(conn, import_id, row_no)
        if record is None:  # pragma: no cover - 同事务刚更新
            raise corrupt("知识点导入行更新后读取失败。")
        return record

    # ---------------------------------------------------------------- 读取

    def get_import(self, conn: sqlite3.Connection, import_id: str) -> ImportRecord | None:
        import_id = self._text(import_id, field="import_id")
        row = conn.execute(
            "SELECT * FROM knowledge_imports WHERE id = ?", (import_id,)
        ).fetchone()
        return self._record(row) if row is not None else None

    def require_import(self, conn: sqlite3.Connection, import_id: str) -> ImportRecord:
        record = self.get_import(conn, import_id)
        if record is None:
            raise AppError("知识点导入不存在。", code="KNOWLEDGE_IMPORT_NOT_FOUND", status_code=404)
        return record

    def list_imports(
        self,
        conn: sqlite3.Connection,
        *,
        state: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> tuple[list[ImportRecord], int]:
        if state is not None:
            state = self._choice(state, field="state", allowed=KNOWLEDGE_IMPORT_STATES)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise invalid("offset 必须是不小于 0 的整数。")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise invalid("limit 必须是不小于 1 的整数。")
        if limit > MAX_LIST_LIMIT:
            raise invalid(f"limit 不能超过 {MAX_LIST_LIMIT}。")
        where = " WHERE state = ?" if state is not None else ""
        params: list[object] = [state] if state is not None else []
        total = conn.execute(
            f"SELECT COUNT(*) AS total FROM knowledge_imports{where}", params
        ).fetchone()["total"]
        rows = conn.execute(
            f"SELECT * FROM knowledge_imports{where} "
            "ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [self._record(row) for row in rows], int(total)

    def list_rows(self, conn: sqlite3.Connection, import_id: str) -> list[ImportRowRecord]:
        import_id = self._text(import_id, field="import_id")
        rows = conn.execute(
            "SELECT * FROM knowledge_import_rows WHERE import_id = ? ORDER BY row_no ASC",
            (import_id,),
        ).fetchall()
        return [self._row_record(row) for row in rows]

    def get_row(
        self, conn: sqlite3.Connection, import_id: str, row_no: int
    ) -> ImportRowRecord | None:
        import_id = self._text(import_id, field="import_id")
        row = conn.execute(
            "SELECT * FROM knowledge_import_rows WHERE import_id = ? AND row_no = ?",
            (import_id, row_no),
        ).fetchone()
        return self._row_record(row) if row is not None else None

    def count_rows(self, conn: sqlite3.Connection, import_id: str) -> int:
        import_id = self._text(import_id, field="import_id")
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM knowledge_import_rows WHERE import_id = ?",
            (import_id,),
        ).fetchone()
        return int(row["total"])

    def issue_codes(self, conn: sqlite3.Connection, import_id: str) -> list[str]:
        """本批次全部问题码（批次级 + 行级），供服务层统计阻断问题数。"""
        import_id = self._text(import_id, field="import_id")
        record = self.require_import(conn, import_id)
        codes = [str(issue.get("code", "")) for issue in record.batch_issues]
        rows = conn.execute(
            "SELECT issues_json FROM knowledge_import_rows WHERE import_id = ?",
            (import_id,),
        ).fetchall()
        for row in rows:
            for issue in _load_issues(row["issues_json"], field="issues_json"):
                codes.append(str(issue.get("code", "")))
        return codes

    # ---------------------------------------------------------------- 内部

    @staticmethod
    def _text(value: object, *, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise invalid(f"{field} 必须是非空字符串。")
        return value.strip()

    @staticmethod
    def _choice(value: object, *, field: str, allowed: frozenset[str]) -> str:
        if not isinstance(value, str) or value not in allowed:
            raise invalid(f"{field} 必须是 {sorted(allowed)} 之一。")
        return value

    def _row_values(self, import_id: str, row: ImportRowInput) -> tuple[Any, ...]:
        if not isinstance(row.row_no, int) or isinstance(row.row_no, bool) or row.row_no < 1:
            raise invalid("row_no 必须是不小于 1 的整数。")
        for value, field_name in (
            (row.name, "name"),
            (row.code, "code"),
            (row.description, "description"),
        ):
            if not isinstance(value, str):
                raise invalid(f"{field_name} 必须是字符串。")
        parent_code = row.parent_code
        if parent_code is not None and not isinstance(parent_code, str):
            raise invalid("parent_code 必须是字符串或空。")
        decision = row.decision
        if decision is not None:
            decision = self._choice(decision, field="decision", allowed=KNOWLEDGE_ROW_ACTIONS)
        if not isinstance(row.raw_cells, dict):
            raise invalid("raw_cells 必须是 JSON 对象。")
        return (
            import_id,
            row.row_no,
            row.name,
            row.code,
            parent_code,
            row.description,
            _dump_aliases(row.aliases),
            row.target_knowledge_point_id,
            row.base_revision,
            row.base_revision_id,
            decision,
            _dump_object(row.raw_cells, field="raw_cells"),
            _dump_issues(row.issues),
        )

    @staticmethod
    def _record(row: sqlite3.Row) -> ImportRecord:
        source = row["source"]
        if source not in ("file", "ai"):
            raise corrupt("知识点库数据损坏：knowledge_imports.source 不在枚举内。")
        state = row["state"]
        if state not in KNOWLEDGE_IMPORT_STATES:
            raise corrupt("知识点库数据损坏：knowledge_imports.state 不在枚举内。")
        revision = row["revision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise corrupt("知识点库数据损坏：knowledge_imports.revision 不是非负整数。")
        for field_name in (
            "id",
            "owner_id",
            "subject_id",
            "file_asset_id",
            "created_at",
            "updated_at",
        ):
            if not isinstance(row[field_name], str) or not row[field_name]:
                raise corrupt(
                    f"知识点库数据损坏：knowledge_imports.{field_name} 不是非空字符串。"
                )
        mapping, batch_issues = _load_mapping_and_issues(
            row["mapping_json"], row["issues_json"]
        )
        error_code = row["error_code"]
        if error_code is not None and not isinstance(error_code, str):
            raise corrupt("知识点库数据损坏：knowledge_imports.error_code 不是字符串。")
        return ImportRecord(
            import_id=row["id"],
            owner_id=row["owner_id"],
            source=source,
            subject_id=row["subject_id"],
            file_asset_id=row["file_asset_id"],
            state=state,
            revision=revision,
            mapping=mapping,
            batch_issues=batch_issues,
            warnings=tuple(_load_strings(row["warnings_json"], field="warnings_json")),
            error_code=error_code,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_record(row: sqlite3.Row) -> ImportRowRecord:
        decision = row["decision"]
        if decision is not None and decision not in KNOWLEDGE_ROW_ACTIONS:
            raise corrupt("知识点库数据损坏：knowledge_import_rows.decision 不在枚举内。")
        for field_name in ("name", "code", "description"):
            if not isinstance(row[field_name], str):
                raise corrupt(f"知识点库数据损坏：knowledge_import_rows.{field_name} 不是字符串。")
        aliases = _load_strings(row["aliases_json"], field="aliases_json")
        return ImportRowRecord(
            row_no=row["row_no"],
            name=row["name"],
            code=row["code"],
            parent_code=row["parent_code"],
            description=row["description"],
            aliases=tuple(aliases),
            target_knowledge_point_id=row["target_knowledge_point_id"],
            base_revision=row["base_revision"],
            base_revision_id=row["base_revision_id"],
            decision=decision,
            raw_cells=_load_object(row["raw_cells_json"], field="raw_cells_json"),
            issues=tuple(_load_issues(row["issues_json"], field="issues_json")),
        )


# --------------------------------------------------------------------------- JSON 列


def _dump_object(value: dict[str, Any], *, field: str) -> str:
    # 不排序键：raw_cells 的键序就是原表列序（预览的 headers 由它派生）
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise invalid(f"{field} 必须是可序列化的 JSON 对象。") from exc


def _load_object(raw: object, *, field: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise corrupt(f"知识点库数据损坏：{field} 不是文本。")
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise corrupt(f"知识点库数据损坏：{field} 不是合法 JSON。") from exc
    if not isinstance(value, dict):
        raise corrupt(f"知识点库数据损坏：{field} 不是 JSON 对象。")
    return value


def _dump_aliases(aliases: Sequence[str]) -> str:
    values: list[str] = []
    for item in aliases:
        if not isinstance(item, str) or not item.strip():
            raise invalid("别名必须是非空字符串。")
        values.append(item.strip())
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def _load_strings(raw: object, *, field: str) -> list[str]:
    if not isinstance(raw, str):
        raise corrupt(f"知识点库数据损坏：{field} 不是文本。")
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise corrupt(f"知识点库数据损坏：{field} 不是合法 JSON。") from exc
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise corrupt(f"知识点库数据损坏：{field} 不是字符串数组。")
    return list(value)


def _issue_payload(issue: Any) -> dict[str, Any]:
    """接受 dict 或 pydantic 的 ``ErrorIssue``（服务层两种都传）。"""
    if isinstance(issue, dict):
        return dict(issue)
    dump = getattr(issue, "model_dump", None)
    if callable(dump):
        return dump(exclude_none=True)
    raise invalid("issues 必须是对象数组。")


def _dump_issues(issues: Sequence[Any]) -> str:
    payload = [_issue_payload(issue) for issue in issues]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_issues(raw: object, *, field: str) -> list[dict[str, Any]]:
    if not isinstance(raw, str):
        raise corrupt(f"知识点库数据损坏：{field} 不是文本。")
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise corrupt(f"知识点库数据损坏：{field} 不是合法 JSON。") from exc
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise corrupt(f"知识点库数据损坏：{field} 不是对象数组。")
    return [dict(item) for item in value]


def _dump_mapping(mapping: dict[str, str] | None) -> str:
    """``mapping_json`` 只存映射本身（``{field: header}``，无保留键）。"""
    payload: dict[str, str] = {}
    for key, value in (mapping or {}).items():
        if key not in KNOWLEDGE_IMPORT_FIELDS:
            raise invalid(f"映射字段必须是 {list(KNOWLEDGE_IMPORT_FIELDS)} 之一：{key!r}。")
        if not isinstance(value, str) or not value:
            raise invalid("映射的表头必须是非空字符串。")
        payload[key] = value
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_mapping_and_issues(
    mapping_raw: object, issues_raw: object
) -> tuple[dict[str, str], tuple[dict[str, Any], ...]]:
    """读批次映射与批次级 issues（``issues_json`` 列）。

    兼容 0003 之前的旧数据：那时批次级 issues 塞在 ``mapping_json`` 的保留键里
    （``{"mapping": {...}, "issues": [...]}``）。旧布局按内层映射解析，
    并把旧 issues 与 ``issues_json`` 合并去重后返回；新写入一律走新列。
    """
    payload = _load_object(mapping_raw, field="mapping_json")
    legacy_issues: list[dict[str, Any]] = []
    if "mapping" in payload or "issues" in payload:
        inner = payload.get("mapping", {})
        if not isinstance(inner, dict):
            raise corrupt("知识点库数据损坏：mapping_json.mapping 不是对象。")
        raw_legacy = payload.get("issues", [])
        if not isinstance(raw_legacy, list) or any(
            not isinstance(item, dict) for item in raw_legacy
        ):
            raise corrupt("知识点库数据损坏：mapping_json.issues 不是对象数组。")
        legacy_issues = [dict(item) for item in raw_legacy]
        payload = inner
    mapping: dict[str, str] = {}
    for key, value in payload.items():
        if key not in KNOWLEDGE_IMPORT_FIELDS or not isinstance(value, str):
            raise corrupt("知识点库数据损坏：mapping_json 结构不符。")
        mapping[key] = value
    issues = [*legacy_issues, *_load_issues(issues_raw, field="issues_json")]
    return mapping, tuple(_dedupe_issues(issues))


def _dedupe_issues(issues: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for issue in issues:
        key = json.dumps(issue, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def _dump_warnings(warnings: Sequence[str]) -> str:
    values: list[str] = []
    for item in warnings:
        if not isinstance(item, str):
            raise invalid("warnings 必须是字符串数组。")
        values.append(item)
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


__all__ = [
    "DEFAULT_LIST_LIMIT",
    "MAX_LIST_LIMIT",
    "ImportRecord",
    "ImportRowInput",
    "ImportRowRecord",
    "KnowledgeImportRepository",
]
