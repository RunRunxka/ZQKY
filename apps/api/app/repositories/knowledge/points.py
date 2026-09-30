"""知识点身份/修订/别名/教材依据仓储（TEACHING-LOOP B1 / T20）。

只做 SQL：每个方法都接收调用方事务里的 ``sqlite3.Connection``（由
``KnowledgeCatalog.write_transaction()`` / ``read_connection()`` 提供），本模块不自己
开连接、不做网络/解析/推理——与四库既有纪律一致。

冻结语义（``app/contracts/knowledge.py``）：

- 身份（``knowledge_points.id``）与内容修订（``knowledge_point_revisions``）分离：
  改名/改说明**追加** ``version+1`` 修订并切换 ``current_revision_id``；修订行由 DB
  触发器保护为不可变（``IMMUTABLE_REVISION``），历史引用保留。
- ``revision`` 是可变行的乐观锁：任何实际写入 +1；``expected_revision`` 不符抛
  409 ``REVISION_CONFLICT`` + ``details.currentRevision``。
- 别名规范化 ``normalize_alias``：NFKC（全角→半角）+ 折叠空白 + ``casefold``；
  同知识点内按规范化值去重；**跨知识点同名不合并**（由服务层记 warning）。
- 父节点：同库同科（FK ``(parent_id, subject_id)`` 兜底）、非自指（CHECK 兜底）、
  无环（触发器 ``KNOWLEDGE_CYCLE`` 兜底）；服务层先做可定位校验，仓储把
  ``sqlite3.IntegrityError`` 翻译成稳定错误码。
- 教材依据：``locator_hash = sha256(canonical_hash(locator_json 对象))``（B1 任务卡
  冻结公式）；``locator_json`` 至少含 ``charStart``/``charEnd``，另冻结证据读到的可见
  定位字段。``UNIQUE(knowledge_revision_id, document_revision_id, locator_hash)``
  保证同一修订同一区间不重复登记。
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.contracts.teaching_loop import (
    REVISION_CONFLICT,
    ErrorIssue,
    canonical_hash,
    error_details,
)
from app.core.exceptions import AppError
from app.core.sqlite import now_iso

#: 允许的状态与来源（与冻结 DDL 的 CHECK 一致）
SUBJECT_STATUSES = frozenset({"active", "archived"})
POINT_STATUSES = frozenset({"active", "archived"})
LINK_SOURCES = frozenset({"human", "ai_confirmed"})

MAX_CODE_CHARS = 64
MAX_NAME_CHARS = 200
MAX_LIST_LIMIT = 200
#: 父链自检的最大深度（防御损坏数据里的环；DB 触发器仍是权威）
MAX_PARENT_DEPTH = 512

_ALIAS_WHITESPACE = re.compile(r"\s+")
_LIKE_ESCAPE = "\\"

#: 知识点列表/计数共用的 FROM 子句（当前修订取名，父节点取 parent_code）
_POINT_FROM = (
    "knowledge_points kp "
    "LEFT JOIN knowledge_point_revisions r ON r.id = kp.current_revision_id "
    "LEFT JOIN knowledge_points p ON p.id = kp.parent_id"
)

#: "不修改该字段"的哨兵：与"显式清空"（None / "" / 空元组）严格区分
UNSET: Any = object()


# --------------------------------------------------------------------------- 错误


def invalid(message: str, *, code: str = "INVALID_REQUEST") -> AppError:
    return AppError(message, code=code, status_code=422)


def not_found(message: str, *, code: str) -> AppError:
    return AppError(message, code=code, status_code=404)


def conflict(message: str, *, code: str, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=409, retryable=retryable)


def corrupt(message: str) -> AppError:
    return AppError(message, code="KNOWLEDGE_CORRUPT", status_code=500)


def revision_conflict(current: int) -> AppError:
    return AppError(
        "数据已被其他操作更新，请刷新后重试。",
        code=REVISION_CONFLICT,
        status_code=409,
        details=error_details(current_revision=current),
    )


def translate_integrity_error(exc: sqlite3.IntegrityError) -> AppError:
    """把 DB 约束/触发器错误翻译成稳定错误码（不把 SQLite 原文当业务原因）。

    触发器等兜底路径与服务层预检**形状一致**：父树类错误一律带 ``details.issues``
    且 ``field="parentId"``（仓储只拿到已解析的父 id；服务层预检会按实际入参给出
    ``parentId``/``parentCode``）。
    """
    text = str(exc)
    if "KNOWLEDGE_CYCLE" in text:
        return AppError(
            "父节点变更会形成环（新父节点是本节点的后代）。",
            code="KNOWLEDGE_CYCLE",
            status_code=422,
            details=error_details(
                issues=[
                    ErrorIssue(
                        field="parentId",
                        code="KNOWLEDGE_CYCLE",
                        message="parentId 指向的父节点是本知识点的后代，会形成环。",
                    )
                ]
            ),
        )
    if "CHECK constraint failed" in text and "parent_id" in text:
        return AppError(
            "父节点非法：知识点不能把自己作为父节点。",
            code="KNOWLEDGE_PARENT_INVALID",
            status_code=422,
            details=error_details(
                issues=[
                    ErrorIssue(
                        field="parentId",
                        code="KNOWLEDGE_PARENT_INVALID",
                        message="parentId 指向本知识点自身，不能作为父节点。",
                    )
                ]
            ),
        )
    if "FOREIGN KEY" in text:
        return AppError(
            "父节点或学科不存在（父节点必须同库同科且已存在）。",
            code="KNOWLEDGE_PARENT_INVALID",
            status_code=422,
            details=error_details(
                issues=[
                    ErrorIssue(
                        field="parentId",
                        code="KNOWLEDGE_PARENT_INVALID",
                        message="parentId 指向的知识点不存在或不属于同学科。",
                    )
                ]
            ),
        )
    if "IMMUTABLE_REVISION" in text:
        return AppError(
            "内容修订不可变：改名请追加新修订。",
            code="IMMUTABLE_REVISION",
            status_code=409,
        )
    if "UNIQUE" in text and "knowledge_points" in text:
        return AppError(
            "同学科内编码已存在。", code="KNOWLEDGE_CODE_CONFLICT", status_code=409
        )
    if "UNIQUE" in text and "textbook_knowledge_links" in text:
        return AppError(
            "同一知识点修订、同一教材修订与同一区间已登记过依据。",
            code="KNOWLEDGE_LINK_DUPLICATE",
            status_code=409,
        )
    return AppError(
        "知识点写入违反数据库约束。", code="KNOWLEDGE_ROW_INVALID", status_code=422
    )


# --------------------------------------------------------------------------- 值校验


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise invalid(f"{field} 必须是非空字符串。")
    return value.strip()


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise invalid(f"{field} 必须是字符串或空。")
    text = value.strip()
    return text or None


def _bounded(value: str, *, field: str, maximum: int) -> str:
    if len(value) > maximum:
        raise invalid(f"{field} 不能超过 {maximum} 个字符。")
    return value


def _count(value: object, *, field: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise invalid(f"{field} 必须是不小于 {minimum} 的整数。")
    return value


def _choice(value: object, *, field: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise invalid(f"{field} 必须是 {sorted(allowed)} 之一。")
    return value


def normalize_alias(value: object) -> str:
    """别名规范化：NFKC（全角→半角）+ 折叠空白 + ``casefold``。"""
    if not isinstance(value, str) or not value.strip():
        raise invalid("别名必须是非空字符串。")
    text = unicodedata.normalize("NFKC", value)
    text = _ALIAS_WHITESPACE.sub(" ", text).strip()
    return text.casefold()


def alias_pairs(aliases: Sequence[str]) -> list[tuple[str, str]]:
    """``[(normalized_alias, 原样别名)]``；同知识点内按规范化值去重（保首见顺序）。"""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in aliases:
        text = _text(raw, field="alias")
        key = normalize_alias(text)
        if key in seen:
            continue
        seen.add(key)
        pairs.append((key, text))
    return pairs


def like_pattern(value: str) -> str:
    """``%value%`` 的 LIKE 模式；转义 ``%``/``_``/``\\`` 后调用方用 ESCAPE '\\'。"""
    escaped = (
        value.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", f"{_LIKE_ESCAPE}%")
        .replace("_", f"{_LIKE_ESCAPE}_")
    )
    return f"%{escaped}%"


# --------------------------------------------------------------------------- 记录


@dataclass(frozen=True)
class SubjectRecord:
    subject_id: str
    code: str
    name: str
    status: str


@dataclass(frozen=True)
class PointRecord:
    """知识点身份 + 当前内容修订 + 别名（列表/详情共用）。"""

    point_id: str
    subject_id: str
    code: str
    name: str
    description: str
    parent_id: str | None
    parent_code: str | None
    sort_order: int
    status: str
    revision: int
    revision_id: str
    version: int
    aliases: tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class LinkRecord:
    link_id: str
    knowledge_point_id: str
    knowledge_revision_id: str
    document_revision_id: str
    char_start: int
    char_end: int
    title_snapshot: str
    locator_hash: str
    locator: dict[str, Any]
    source: str
    created_at: str


# --------------------------------------------------------------------------- 学科


class SubjectRepository:
    """``subjects`` 表：教材字典登记与读取。"""

    def ensure_subject(self, conn: sqlite3.Connection, *, subject_id: str, name: str) -> None:
        """幂等登记学科（``INSERT OR IGNORE``）：已有学科的名称与状态一律不改写。"""
        subject_id = _bounded(_text(subject_id, field="subject_id"), field="subject_id", maximum=64)
        name = _bounded(_text(name, field="name"), field="name", maximum=200)
        conn.execute(
            "INSERT OR IGNORE INTO subjects (id, code, name, status) VALUES (?, ?, ?, 'active')",
            (subject_id, subject_id, name),
        )

    def get_subject(self, conn: sqlite3.Connection, subject_id: str) -> SubjectRecord | None:
        subject_id = _text(subject_id, field="subject_id")
        row = conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        if row is None:
            return None
        status = row["status"]
        if status not in SUBJECT_STATUSES:
            raise corrupt("知识点库数据损坏：subjects.status 不在枚举内。")
        for field in ("id", "code", "name"):
            if not isinstance(row[field], str) or not row[field]:
                raise corrupt(f"知识点库数据损坏：subjects.{field} 不是非空字符串。")
        return SubjectRecord(
            subject_id=row["id"], code=row["code"], name=row["name"], status=status
        )


# --------------------------------------------------------------------------- 知识点


class KnowledgePointRepository:
    """``knowledge_points`` / ``knowledge_point_revisions`` / ``knowledge_aliases``。"""

    # ---------------------------------------------------------------- 写入

    def create_point(
        self,
        conn: sqlite3.Connection,
        *,
        subject_id: str,
        code: str,
        name: str,
        description: str = "",
        parent_id: str | None = None,
        sort_order: int = 0,
        aliases: Sequence[str] = (),
        status: str = "active",
    ) -> PointRecord:
        """创建身份 + 首修订（version=1）+ 别名，同一事务内完成。"""
        subject_id = _bounded(_text(subject_id, field="subject_id"), field="subject_id", maximum=64)
        code = _bounded(_text(code, field="code"), field="code", maximum=MAX_CODE_CHARS)
        name = _bounded(_text(name, field="name"), field="name", maximum=MAX_NAME_CHARS)
        if not isinstance(description, str):
            raise invalid("description 必须是字符串。")
        parent_id = _optional_text(parent_id, field="parent_id")
        sort_order = _count(sort_order, field="sort_order")
        status = _choice(status, field="status", allowed=POINT_STATUSES)
        point_id = uuid.uuid4().hex
        revision_id = uuid.uuid4().hex
        now = now_iso()
        if parent_id is not None:
            self._require_parent(conn, point_id=point_id, subject_id=subject_id, parent_id=parent_id)
        try:
            conn.execute(
                "INSERT INTO knowledge_points "
                "(id, subject_id, code, parent_id, current_revision_id, sort_order, status, "
                "revision, created_at) VALUES (?, ?, ?, ?, NULL, ?, ?, 0, ?)",
                (point_id, subject_id, code, parent_id, sort_order, status, now),
            )
            conn.execute(
                "INSERT INTO knowledge_point_revisions "
                "(id, knowledge_point_id, version, name, description, created_at) "
                "VALUES (?, ?, 1, ?, ?, ?)",
                (revision_id, point_id, name, description, now),
            )
            conn.execute(
                "UPDATE knowledge_points SET current_revision_id = ? WHERE id = ?",
                (revision_id, point_id),
            )
            self.set_aliases(conn, point_id, aliases)
        except sqlite3.IntegrityError as exc:
            raise translate_integrity_error(exc) from exc
        return self.require_point(conn, point_id)

    def update_point(
        self,
        conn: sqlite3.Connection,
        point_id: str,
        *,
        expected_revision: int,
        name: str | None = None,
        description: str | None = None,
        parent_id: Any = UNSET,
        sort_order: int | None = None,
        aliases: Sequence[str] | None = None,
    ) -> PointRecord:
        """核乐观锁后更新；改名/改说明**追加修订**（version+1），无变化则原样返回。

        字段语义：``name/description/aliases`` 为 ``None`` = 不修改（服务层的"空白默认
        不动"）；``parent_id`` 用哨兵 ``UNSET`` 表示不修改，传 ``None`` 表示清空父节点。
        """
        point_id = _text(point_id, field="point_id")
        current = self.require_point(conn, point_id)
        if current.revision != expected_revision:
            raise revision_conflict(current.revision)

        new_name = current.name if name is None else _bounded(
            _text(name, field="name"), field="name", maximum=MAX_NAME_CHARS
        )
        new_description = current.description if description is None else _description(description)
        revision_changed = new_name != current.name or new_description != current.description

        updates: dict[str, Any] = {}
        if revision_changed:
            revision_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO knowledge_point_revisions "
                "(id, knowledge_point_id, version, name, description, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (revision_id, point_id, current.version + 1, new_name, new_description, now_iso()),
            )
            updates["current_revision_id"] = revision_id

        if parent_id is not UNSET and parent_id != current.parent_id:
            if parent_id is not None:
                self._require_parent(
                    conn, point_id=point_id, subject_id=current.subject_id, parent_id=parent_id
                )
            updates["parent_id"] = parent_id

        if sort_order is not None and sort_order != current.sort_order:
            updates["sort_order"] = _count(sort_order, field="sort_order")

        aliases_changed = False
        pairs: list[tuple[str, str]] = []
        if aliases is not None:
            pairs = alias_pairs(aliases)
            aliases_changed = [pair[0] for pair in pairs] != [
                normalize_alias(item) for item in current.aliases
            ]

        try:
            if updates:
                assignments = ", ".join(f"{column} = ?" for column in updates)
                conn.execute(
                    f"UPDATE knowledge_points SET {assignments}, revision = revision + 1 "
                    "WHERE id = ?",
                    (*updates.values(), point_id),
                )
            if aliases_changed:
                self.set_aliases(conn, point_id, [pair[1] for pair in pairs])
            if aliases_changed and not updates:
                conn.execute(
                    "UPDATE knowledge_points SET revision = revision + 1 WHERE id = ?",
                    (point_id,),
                )
        except sqlite3.IntegrityError as exc:
            raise translate_integrity_error(exc) from exc
        return self.require_point(conn, point_id)

    def set_status(
        self,
        conn: sqlite3.Connection,
        point_id: str,
        *,
        expected_revision: int,
        archived: bool,
    ) -> PointRecord:
        """归档/恢复：核乐观锁，状态实际变化才 ``revision + 1``（幂等空操作）。"""
        point_id = _text(point_id, field="point_id")
        target = "archived" if archived else "active"
        current = self.require_point(conn, point_id)
        if current.revision != expected_revision:
            raise revision_conflict(current.revision)
        if current.status == target:
            return current
        try:
            conn.execute(
                "UPDATE knowledge_points SET status = ?, revision = revision + 1 WHERE id = ?",
                (target, point_id),
            )
        except sqlite3.IntegrityError as exc:
            raise translate_integrity_error(exc) from exc
        return self.require_point(conn, point_id)

    def set_aliases(
        self, conn: sqlite3.Connection, point_id: str, aliases: Sequence[str]
    ) -> None:
        """整组替换别名（规范化去重）；空白别名 422，不静默丢弃。"""
        point_id = _text(point_id, field="point_id")
        pairs = alias_pairs(aliases)
        conn.execute("DELETE FROM knowledge_aliases WHERE knowledge_point_id = ?", (point_id,))
        for key, text in pairs:
            conn.execute(
                "INSERT INTO knowledge_aliases "
                "(id, knowledge_point_id, alias, normalized_alias, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, point_id, text, key, now_iso()),
            )

    # ---------------------------------------------------------------- 读取

    def get_point(self, conn: sqlite3.Connection, point_id: str) -> PointRecord | None:
        point_id = _text(point_id, field="point_id")
        row = self._point_row(conn, point_id)
        if row is None:
            return None
        return self._record(conn, row)

    def require_point(self, conn: sqlite3.Connection, point_id: str) -> PointRecord:
        record = self.get_point(conn, point_id)
        if record is None:
            raise not_found("知识点不存在。", code="KNOWLEDGE_POINT_NOT_FOUND")
        return record

    def get_by_code(
        self, conn: sqlite3.Connection, *, subject_id: str, code: str
    ) -> PointRecord | None:
        subject_id = _text(subject_id, field="subject_id")
        code = _text(code, field="code")
        row = conn.execute(
            "SELECT id FROM knowledge_points WHERE subject_id = ? AND code = ?",
            (subject_id, code),
        ).fetchone()
        if row is None:
            return None
        return self.get_point(conn, row["id"])

    def list_points(
        self,
        conn: sqlite3.Connection,
        *,
        subject_id: str | None = None,
        status: str | None = None,
        parent_id: str | None = None,
        q: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PointRecord], int]:
        """列表（subject/status/parent/q 过滤 + 分页）；返回 ``(items, total)``。"""
        if subject_id is not None:
            subject_id = _text(subject_id, field="subject_id")
        if status is not None:
            status = _choice(status, field="status", allowed=POINT_STATUSES)
        if parent_id is not None:
            parent_id = _text(parent_id, field="parent_id")
        offset = _count(offset, field="offset")
        limit = _count(limit, field="limit", minimum=1)
        if limit > MAX_LIST_LIMIT:
            raise invalid(f"limit 不能超过 {MAX_LIST_LIMIT}。")
        where, params = self._list_filter(
            subject_id=subject_id, status=status, parent_id=parent_id, q=q
        )
        total = conn.execute(
            f"SELECT COUNT(*) AS total FROM {_POINT_FROM}{where}", params
        ).fetchone()["total"]
        rows = conn.execute(
            "SELECT kp.id AS id FROM "
            f"{_POINT_FROM}{where} "
            "ORDER BY kp.sort_order ASC, kp.created_at ASC, kp.rowid ASC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        items = [self.require_point(conn, row["id"]) for row in rows]
        return items, int(total)

    def version_of_revision(self, conn: sqlite3.Connection, revision_id: str) -> int | None:
        """按内容修订 id 读 version（修订不可变，历史行永久可查）。"""
        revision_id = _text(revision_id, field="revision_id")
        row = conn.execute(
            "SELECT version FROM knowledge_point_revisions WHERE id = ?", (revision_id,)
        ).fetchone()
        if row is None:
            return None
        version = row["version"]
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise corrupt("知识点库数据损坏：content revision version 结构不符。")
        return version

    def list_point_ids(
        self,
        conn: sqlite3.Connection,
        *,
        subject_id: str | None = None,
        status: str | None = None,
    ) -> list[str]:
        if subject_id is not None:
            subject_id = _text(subject_id, field="subject_id")
        if status is not None:
            status = _choice(status, field="status", allowed=POINT_STATUSES)
        clauses: list[str] = []
        params: list[object] = []
        if subject_id is not None:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT id FROM knowledge_points{where} ORDER BY rowid ASC", params
        ).fetchall()
        return [row["id"] for row in rows]

    def points_with_alias(
        self,
        conn: sqlite3.Connection,
        *,
        subject_id: str,
        normalized_alias: str,
        exclude_point_id: str | None = None,
    ) -> list[str]:
        """同学科内已用该规范化别名的**其他**知识点 id（只提示，绝不合并）。"""
        subject_id = _text(subject_id, field="subject_id")
        normalized_alias = _text(normalized_alias, field="normalized_alias")
        rows = conn.execute(
            "SELECT a.knowledge_point_id AS id FROM knowledge_aliases a "
            "JOIN knowledge_points kp ON kp.id = a.knowledge_point_id "
            "WHERE kp.subject_id = ? AND a.normalized_alias = ? "
            "ORDER BY a.rowid ASC",
            (subject_id, normalized_alias),
        ).fetchall()
        return [
            row["id"] for row in rows if exclude_point_id is None or row["id"] != exclude_point_id
        ]

    def would_create_cycle(
        self, conn: sqlite3.Connection, *, point_id: str, parent_id: str | None
    ) -> bool:
        """把 ``point_id.parent = parent_id`` 是否会成环（沿父链上溯，DB 触发器仍兜底）。"""
        point_id = _text(point_id, field="point_id")
        parent_id = _optional_text(parent_id, field="parent_id")
        if parent_id is None:
            return False
        current = parent_id
        seen: set[str] = set()
        for _ in range(MAX_PARENT_DEPTH):
            if current == point_id:
                return True
            if current in seen:
                return True  # 既有数据已损坏成环：宁可拒绝写入
            seen.add(current)
            row = conn.execute(
                "SELECT parent_id FROM knowledge_points WHERE id = ?", (current,)
            ).fetchone()
            if row is None:
                return False
            current = row["parent_id"]
            if current is None:
                return False
        return True

    # ---------------------------------------------------------------- 内部

    def _require_parent(
        self,
        conn: sqlite3.Connection,
        *,
        point_id: str,
        subject_id: str,
        parent_id: str,
    ) -> None:
        """仓储级父节点兜底校验；与 ``translate_integrity_error`` 同形状（带 issues）。"""
        if parent_id == point_id:
            raise AppError(
                "父节点非法：知识点不能把自己作为父节点。",
                code="KNOWLEDGE_PARENT_INVALID",
                status_code=422,
                details=error_details(
                    issues=[
                        ErrorIssue(
                            field="parentId",
                            code="KNOWLEDGE_PARENT_INVALID",
                            message="parentId 指向本知识点自身，不能作为父节点。",
                        )
                    ]
                ),
            )
        row = self._point_row(conn, parent_id)
        if row is None:
            raise AppError(
                "父节点不存在。",
                code="KNOWLEDGE_PARENT_INVALID",
                status_code=422,
                details=error_details(
                    issues=[
                        ErrorIssue(
                            field="parentId",
                            code="KNOWLEDGE_PARENT_INVALID",
                            message="parentId 指向的知识点不存在。",
                        )
                    ]
                ),
            )
        if row["subject_id"] != subject_id:
            raise AppError(
                "父节点必须与知识点同学科。",
                code="KNOWLEDGE_CROSS_SUBJECT_PARENT",
                status_code=422,
                details=error_details(
                    issues=[
                        ErrorIssue(
                            field="parentId",
                            code="KNOWLEDGE_CROSS_SUBJECT_PARENT",
                            message="parentId 指向的知识点属于其他学科。",
                        )
                    ]
                ),
            )

    @staticmethod
    def _point_row(conn: sqlite3.Connection, point_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT kp.*, r.version AS r_version, r.name AS r_name, "
            "r.description AS r_description, p.code AS parent_code "
            "FROM knowledge_points kp "
            "LEFT JOIN knowledge_point_revisions r ON r.id = kp.current_revision_id "
            "LEFT JOIN knowledge_points p ON p.id = kp.parent_id "
            "WHERE kp.id = ?",
            (point_id,),
        ).fetchone()

    @staticmethod
    def _list_filter(
        *,
        subject_id: str | None,
        status: str | None,
        parent_id: str | None,
        q: str | None,
    ) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if subject_id is not None:
            clauses.append("kp.subject_id = ?")
            params.append(subject_id)
        if status is not None:
            clauses.append("kp.status = ?")
            params.append(status)
        if parent_id is not None:
            clauses.append("kp.parent_id = ?")
            params.append(parent_id)
        if q is not None and q.strip():
            pattern = like_pattern(q.strip())
            clauses.append(
                "(r.name LIKE ? ESCAPE '\\' OR kp.code LIKE ? ESCAPE '\\' "
                "OR EXISTS (SELECT 1 FROM knowledge_aliases a "
                "WHERE a.knowledge_point_id = kp.id "
                "AND a.normalized_alias LIKE ? ESCAPE '\\'))"
            )
            alias_pattern = like_pattern(normalize_alias(q))
            params.extend([pattern, pattern, alias_pattern])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, params

    def _record(self, conn: sqlite3.Connection, row: sqlite3.Row) -> PointRecord:
        revision_id = row["current_revision_id"]
        if not isinstance(revision_id, str) or not revision_id:
            raise corrupt("知识点库数据损坏：知识点缺少当前内容修订。")
        version = row["r_version"]
        name = row["r_name"]
        description = row["r_description"]
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version < 1
            or not isinstance(name, str)
            or not name
            or not isinstance(description, str)
        ):
            raise corrupt("知识点库数据损坏：当前内容修订结构不符。")
        status = row["status"]
        if status not in POINT_STATUSES:
            raise corrupt("知识点库数据损坏：knowledge_points.status 不在枚举内。")
        revision = row["revision"]
        sort_order = row["sort_order"]
        if (
            not isinstance(revision, int)
            or isinstance(revision, bool)
            or revision < 0
            or not isinstance(sort_order, int)
            or isinstance(sort_order, bool)
        ):
            raise corrupt("知识点库数据损坏：revision/sort_order 不是整数。")
        for field in ("id", "subject_id", "code", "created_at"):
            if not isinstance(row[field], str) or not row[field]:
                raise corrupt(f"知识点库数据损坏：knowledge_points.{field} 不是非空字符串。")
        return PointRecord(
            point_id=row["id"],
            subject_id=row["subject_id"],
            code=row["code"],
            name=name,
            description=description,
            parent_id=row["parent_id"],
            parent_code=row["parent_code"],
            sort_order=sort_order,
            status=status,
            revision=revision,
            revision_id=revision_id,
            version=version,
            aliases=self._aliases(conn, row["id"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _aliases(conn: sqlite3.Connection, point_id: str) -> tuple[str, ...]:
        rows = conn.execute(
            "SELECT alias FROM knowledge_aliases WHERE knowledge_point_id = ? ORDER BY rowid ASC",
            (point_id,),
        ).fetchall()
        return tuple(row["alias"] for row in rows)


# --------------------------------------------------------------------------- 教材依据


class TextbookLinkRepository:
    """``textbook_knowledge_links``：教材依据关联（只做本库 SQL）。"""

    def create_link(
        self,
        conn: sqlite3.Connection,
        *,
        point_id: str,
        knowledge_revision_id: str,
        document_revision_id: str,
        char_start: int,
        char_end: int,
        title_snapshot: str,
        source: str = "human",
        locator: dict[str, Any] | None = None,
    ) -> LinkRecord:
        point_id = _text(point_id, field="point_id")
        knowledge_revision_id = _text(knowledge_revision_id, field="knowledge_revision_id")
        document_revision_id = _text(document_revision_id, field="document_revision_id")
        char_start = _count(char_start, field="char_start")
        char_end = _count(char_end, field="char_end", minimum=1)
        if char_end <= char_start:
            raise invalid("教材依据区间必须满足 charEnd > charStart。")
        title_snapshot = _text(title_snapshot, field="title_snapshot")
        source = _choice(source, field="source", allowed=LINK_SOURCES)
        locator_payload = _locator_payload(
            document_revision_id=document_revision_id,
            char_start=char_start,
            char_end=char_end,
            locator=locator,
        )
        locator_json = json.dumps(
            locator_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        locator_hash = hashlib.sha256(
            canonical_hash(locator_payload).encode("utf-8")
        ).hexdigest()
        link_id = uuid.uuid4().hex
        try:
            conn.execute(
                "INSERT INTO textbook_knowledge_links "
                "(id, knowledge_point_id, knowledge_revision_id, document_revision_id, "
                "locator_json, locator_hash, title_snapshot, source, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    link_id,
                    point_id,
                    knowledge_revision_id,
                    document_revision_id,
                    locator_json,
                    locator_hash,
                    title_snapshot,
                    source,
                    now_iso(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise translate_integrity_error(exc) from exc
        record = self._get(conn, link_id)
        if record is None:  # pragma: no cover - 同事务刚写入
            raise corrupt("教材依据写入后读取失败。")
        return record

    def list_links(self, conn: sqlite3.Connection, *, point_id: str) -> list[LinkRecord]:
        point_id = _text(point_id, field="point_id")
        rows = conn.execute(
            "SELECT * FROM textbook_knowledge_links WHERE knowledge_point_id = ? "
            "ORDER BY created_at ASC, rowid ASC",
            (point_id,),
        ).fetchall()
        return [self._record(row) for row in rows]

    def get_link(self, conn: sqlite3.Connection, link_id: str) -> LinkRecord | None:
        link_id = _text(link_id, field="link_id")
        return self._get(conn, link_id)

    def delete_link(self, conn: sqlite3.Connection, *, point_id: str, link_id: str) -> bool:
        point_id = _text(point_id, field="point_id")
        link_id = _text(link_id, field="link_id")
        cursor = conn.execute(
            "DELETE FROM textbook_knowledge_links WHERE id = ? AND knowledge_point_id = ?",
            (link_id, point_id),
        )
        return bool(cursor.rowcount)

    def count_links(self, conn: sqlite3.Connection, *, point_id: str) -> int:
        point_id = _text(point_id, field="point_id")
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM textbook_knowledge_links "
            "WHERE knowledge_point_id = ?",
            (point_id,),
        ).fetchone()
        return int(row["total"])

    # ---------------------------------------------------------------- 内部

    def _get(self, conn: sqlite3.Connection, link_id: str) -> LinkRecord | None:
        row = conn.execute(
            "SELECT * FROM textbook_knowledge_links WHERE id = ?", (link_id,)
        ).fetchone()
        return self._record(row) if row is not None else None

    @staticmethod
    def _record(row: sqlite3.Row) -> LinkRecord:
        raw = row["locator_json"]
        if not isinstance(raw, str):
            raise corrupt("知识点库数据损坏：教材依据 locator_json 不是文本。")
        try:
            locator = json.loads(raw)
        except ValueError as exc:
            raise corrupt("知识点库数据损坏：教材依据 locator_json 不是合法 JSON。") from exc
        if not isinstance(locator, dict):
            raise corrupt("知识点库数据损坏：教材依据 locator_json 不是对象。")
        char_start = locator.get("charStart")
        char_end = locator.get("charEnd")
        if (
            not isinstance(char_start, int)
            or isinstance(char_start, bool)
            or not isinstance(char_end, int)
            or isinstance(char_end, bool)
            or char_end <= char_start
        ):
            raise corrupt("知识点库数据损坏：教材依据区间字段结构不符。")
        source = row["source"]
        if source not in LINK_SOURCES:
            raise corrupt("知识点库数据损坏：教材依据 source 不在枚举内。")
        for field in (
            "id",
            "knowledge_point_id",
            "knowledge_revision_id",
            "document_revision_id",
            "locator_hash",
            "title_snapshot",
            "created_at",
        ):
            if not isinstance(row[field], str) or not row[field]:
                raise corrupt(f"知识点库数据损坏：textbook_knowledge_links.{field} 不是非空字符串。")
        return LinkRecord(
            link_id=row["id"],
            knowledge_point_id=row["knowledge_point_id"],
            knowledge_revision_id=row["knowledge_revision_id"],
            document_revision_id=row["document_revision_id"],
            char_start=char_start,
            char_end=char_end,
            title_snapshot=row["title_snapshot"],
            locator_hash=row["locator_hash"],
            locator=dict(locator),
            source=source,
            created_at=row["created_at"],
        )


# --------------------------------------------------------------------------- 内部工具


def _description(value: object) -> str:
    if not isinstance(value, str):
        raise invalid("description 必须是字符串。")
    return value


def _locator_payload(
    *,
    document_revision_id: str,
    char_start: int,
    char_end: int,
    locator: dict[str, Any] | None,
) -> dict[str, Any]:
    """证据冻结的定位对象：区间为权威，附证据读取时的可见定位字段。"""
    payload: dict[str, Any] = {
        "documentRevisionId": document_revision_id,
        "charStart": char_start,
        "charEnd": char_end,
    }
    if isinstance(locator, dict):
        for key, value in locator.items():
            if value is None or key in payload:
                continue
            if isinstance(value, (str, int, float, bool)):
                payload[key] = value
    return payload


__all__ = [
    "LINK_SOURCES",
    "MAX_LIST_LIMIT",
    "POINT_STATUSES",
    "PointRecord",
    "SubjectRecord",
    "SubjectRepository",
    "TextbookLinkRepository",
    "LinkRecord",
    "KnowledgePointRepository",
    "UNSET",
    "alias_pairs",
    "conflict",
    "corrupt",
    "invalid",
    "like_pattern",
    "normalize_alias",
    "not_found",
    "revision_conflict",
    "translate_integrity_error",
]
