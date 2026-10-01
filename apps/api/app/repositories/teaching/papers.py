"""原卷仓储（TEACHING-LOOP B2 / T40）：只做 SQL。

表由教学库迁移 ``0003_teaching_paper_tables`` 登记（设计四表 + B2 补齐的
``paper_source_blocks`` / ``paper_issues`` / ``ai_proposals`` 与确认冻结触发器）；本模块
不建表、不改 DDL，也不复制契约类型（对外视图一律来自 ``app.contracts.papers``）。

纪律与其余库一致：

- 每个方法都接收调用方事务里的 ``sqlite3.Connection``（由
  ``TeachingCatalog.write_transaction()`` / ``read_connection()`` 提供），本模块不自己开
  连接、不做网络/解析/推理；
- 读取逐列校验：枚举越界、JSON 列损坏、整数列形状不符 → ``PAPER_ROW_CORRUPT``（500），
  不把坏行静默当合法数据；
- ``expected_revision`` 乐观锁在服务层判定；这里只提供**原子自增**（``bump_revision_in``）
  与整表替换的删除/插入原语，不替服务层做业务判断；
- 父子引用靠 ``(parent_item_id, paper_revision_id)`` 外键与 ``(item_id, paper_revision_id)``
  外键兜底；写入顺序不敏感（调用方事务统一 ``PRAGMA defer_foreign_keys = ON``）。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.contracts.papers import PAPER_BLOCK_DISPOSITIONS, PAPER_NOT_FOUND
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.catalog import TeachingCatalog

DEFAULT_OWNER_ID = "local"
MAX_LIST_LIMIT = 200

#: 读取到结构损坏的行（枚举越界 / JSON 损坏 / 列形状不符）时的稳定错误码
PAPER_ROW_CORRUPT = "PAPER_ROW_CORRUPT"
#: 按 id 找不到原卷/修订的稳定错误码
PAPER_REVISION_NOT_FOUND = "PAPER_REVISION_NOT_FOUND"

_BLOCK_KINDS = frozenset({"paragraph", "table", "formula", "image", "unknown"})
_REVISION_STATES = frozenset({"draft", "confirmed"})
_PAPER_STATUSES = frozenset({"active", "archived"})
_PROPOSAL_STATES = frozenset({"pending", "applied", "rejected", "stale"})
_ISSUE_SEVERITIES = frozenset({"info", "warning", "blocking"})
_ISSUE_STATUSES = frozenset({"open", "resolved", "excluded"})
_KNOWLEDGE_ROLES = frozenset({"primary", "secondary"})
_KNOWLEDGE_SOURCES = frozenset({"human", "ai_confirmed", "bank_confirmed"})


# --------------------------------------------------------------------------- 错误


def _invalid(message: str, *, fields: list[str] | None = None) -> AppError:
    details: dict[str, Any] | None = None
    if fields:
        details = {"fields": list(fields)}
    return AppError(message, code="INVALID_REQUEST", status_code=422, details=details)


def _not_found(message: str, *, code: str = PAPER_NOT_FOUND) -> AppError:
    return AppError(message, code=code, status_code=404)


def _corrupt(message: str) -> AppError:
    return AppError(message, code=PAPER_ROW_CORRUPT, status_code=500)


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。", fields=[field])
    return value


def _row_text(row: sqlite3.Row, field: str) -> str:
    value = row[field]
    if not isinstance(value, str) or not value:
        raise _corrupt(f"教学库数据损坏：{field} 不是非空字符串。")
    return value


def _row_int(row: sqlite3.Row, field: str, *, minimum: int = 0) -> int:
    value = row[field]
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise _corrupt(f"教学库数据损坏：{field} 不是不小于 {minimum} 的整数。")
    return value


def _row_optional_int(row: sqlite3.Row, field: str) -> int | None:
    value = row[field]
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise _corrupt(f"教学库数据损坏：{field} 不是整数或空。")
    return value


def _row_choice(row: sqlite3.Row, field: str, allowed: frozenset[str]) -> str:
    value = row[field]
    if not isinstance(value, str) or value not in allowed:
        raise _corrupt(f"教学库数据损坏：{field} 不在枚举内（{value!r}）。")
    return value


def _load_object(raw: object, *, field: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise _corrupt(f"教学库数据损坏：{field} 不是 JSON 文本。")
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise _corrupt(f"教学库数据损坏：{field} 不是合法 JSON。") from exc
    if not isinstance(value, dict):
        raise _corrupt(f"教学库数据损坏：{field} 不是 JSON 对象。")
    return value


def _load_optional_object(raw: object, *, field: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    return _load_object(raw, field=field)


def _dump_object(value: dict[str, Any], *, field: str) -> str:
    if not isinstance(value, dict):
        raise _invalid(f"{field} 必须是 JSON 对象。", fields=[field])
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise _invalid(f"{field} 必须是可序列化的 JSON 对象。", fields=[field]) from exc


# --------------------------------------------------------------------------- 记录


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    owner_id: str
    subject_id: str
    title: str
    current_revision_id: str | None
    status: str
    revision: int
    created_at: str


@dataclass(frozen=True)
class RevisionRecord:
    """修订行。

    ``title_snapshot``（B3/G0 · B2-RV11）是**修订级标题快照**：固定修订的展示标题
    只能读它，不随后续草稿改名而变；``title_snapshot_source`` 标注来源
    （``revision`` = 创建/保存草稿时写入；``backfilled_from_paper`` = 迁移回填）。
    """

    revision_id: str
    paper_id: str
    version: int
    source_file_id: str
    total_score_units: int
    state: str
    confirmed_at: str | None
    created_at: str
    title_snapshot: str
    title_snapshot_source: str


@dataclass(frozen=True)
class ItemKnowledgeRecord:
    knowledge_point_id: str
    knowledge_revision_id: str
    knowledge_name_snapshot: str
    role: str
    source: str


@dataclass(frozen=True)
class ItemRecord:
    item_id: str
    paper_revision_id: str
    parent_item_id: str | None
    question_no: str
    ordinal: int
    is_scored: bool
    max_score_units: int | None
    content: dict[str, Any]
    source_locator: dict[str, Any]
    knowledge: tuple[ItemKnowledgeRecord, ...] = ()


@dataclass(frozen=True)
class BlockRecord:
    block_id: str
    paper_revision_id: str
    ordinal: int
    kind: str
    block: dict[str, Any]
    locator: dict[str, Any]
    disposition: str
    item_id: str | None
    exclude_reason: str | None


@dataclass(frozen=True)
class IssueRecord:
    issue_id: str
    paper_revision_id: str
    code: str
    severity: str
    message: str
    block_id: str | None
    locator: dict[str, Any]
    status: str
    resolution: dict[str, Any] | None
    created_at: str


@dataclass(frozen=True)
class ProposalRecord:
    proposal_id: str
    job_id: str
    target_kind: str
    target_id: str
    base_revision: int
    payload: dict[str, Any]
    state: str
    created_at: str


@dataclass(frozen=True)
class RevisionCopyMap:
    """确认修订 → 新草稿修订的逐行 id 映射（客户端仍持有旧 id 时由服务层重映射）。"""

    item_map: dict[str, str]
    block_map: dict[str, str]
    issue_map: dict[str, str]


@dataclass(frozen=True)
class PaperSummary:
    """原卷概览（列表/详情共用）：行本身 + 当前修订的计数。"""

    paper_id: str
    subject_id: str
    title: str
    status: str
    revision: int
    created_at: str
    current_revision_id: str | None
    version: int
    current_state: str | None
    total_score_units: int
    item_count: int
    scored_leaf_count: int
    blocking_issue_count: int
    unassigned_block_count: int
    open_issue_count: int


# --------------------------------------------------------------------------- 行映射


def _paper_record(row: sqlite3.Row) -> PaperRecord:
    status = row["status"]
    if status not in _PAPER_STATUSES:
        raise _corrupt(f"教学库数据损坏：papers.status 不在枚举内（{status!r}）。")
    revision = row["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise _corrupt("教学库数据损坏：papers.revision 不是非负整数。")
    current = row["current_revision_id"]
    if current is not None and (not isinstance(current, str) or not current):
        raise _corrupt("教学库数据损坏：papers.current_revision_id 不是非空字符串或空。")
    return PaperRecord(
        paper_id=_row_text(row, "id"),
        owner_id=_row_text(row, "owner_id"),
        subject_id=_row_text(row, "subject_id"),
        title=_row_text(row, "title"),
        current_revision_id=current,
        status=status,
        revision=revision,
        created_at=_row_text(row, "created_at"),
    )


def _revision_record(row: sqlite3.Row) -> RevisionRecord:
    state = row["state"]
    if state not in _REVISION_STATES:
        raise _corrupt(f"教学库数据损坏：paper_revisions.state 不在枚举内（{state!r}）。")
    version = _row_int(row, "version", minimum=1)
    total = row["total_score_units"]
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise _corrupt("教学库数据损坏：paper_revisions.total_score_units 不是非负整数。")
    confirmed_at = row["confirmed_at"]
    if confirmed_at is not None and not isinstance(confirmed_at, str):
        raise _corrupt("教学库数据损坏：paper_revisions.confirmed_at 不是字符串或空。")
    title_snapshot = row["title_snapshot"]
    if not isinstance(title_snapshot, str) or not title_snapshot.strip():
        # 0005 迁移已为全部旧行回填；空快照只能意味着行损坏/绕过迁移，不能静默回退到可变标题
        raise _corrupt("教学库数据损坏：paper_revisions.title_snapshot 为空（修订级标题快照缺失）。")
    title_snapshot_source = row["title_snapshot_source"]
    if not isinstance(title_snapshot_source, str) or not title_snapshot_source.strip():
        raise _corrupt("教学库数据损坏：paper_revisions.title_snapshot_source 为空。")
    return RevisionRecord(
        revision_id=_row_text(row, "id"),
        paper_id=_row_text(row, "paper_id"),
        version=version,
        source_file_id=_row_text(row, "source_file_id"),
        total_score_units=total,
        state=state,
        confirmed_at=confirmed_at,
        created_at=_row_text(row, "created_at"),
        title_snapshot=title_snapshot,
        title_snapshot_source=title_snapshot_source,
    )


def _item_record(row: sqlite3.Row, knowledge: tuple[ItemKnowledgeRecord, ...]) -> ItemRecord:
    is_scored = row["is_scored"]
    if is_scored not in (0, 1):
        raise _corrupt("教学库数据损坏：paper_items.is_scored 不是 0/1 标志。")
    max_score = _row_optional_int(row, "max_score_units")
    if is_scored == 1 and (max_score is None or max_score <= 0):
        raise _corrupt("教学库数据损坏：计分题缺少正整数满分。")
    if is_scored == 0 and max_score is not None:
        raise _corrupt("教学库数据损坏：非计分题带了满分。")
    question_no = _row_text(row, "question_no")
    return ItemRecord(
        item_id=_row_text(row, "id"),
        paper_revision_id=_row_text(row, "paper_revision_id"),
        parent_item_id=row["parent_item_id"],
        question_no=question_no,
        ordinal=_row_int(row, "ordinal", minimum=1),
        is_scored=bool(is_scored),
        max_score_units=max_score,
        content=_load_object(row["content_json"], field="paper_items.content_json"),
        source_locator=_load_object(
            row["source_locator_json"], field="paper_items.source_locator_json"
        ),
        knowledge=knowledge,
    )


def _knowledge_record(row: sqlite3.Row) -> ItemKnowledgeRecord:
    return ItemKnowledgeRecord(
        knowledge_point_id=_row_text(row, "knowledge_point_id"),
        knowledge_revision_id=_row_text(row, "knowledge_revision_id"),
        knowledge_name_snapshot=_row_text(row, "knowledge_name_snapshot"),
        role=_row_choice(row, "role", _KNOWLEDGE_ROLES),
        source=_row_choice(row, "source", _KNOWLEDGE_SOURCES),
    )


def _block_record(row: sqlite3.Row) -> BlockRecord:
    return BlockRecord(
        block_id=_row_text(row, "id"),
        paper_revision_id=_row_text(row, "paper_revision_id"),
        ordinal=_row_int(row, "ordinal", minimum=1),
        kind=_row_choice(row, "kind", _BLOCK_KINDS),
        block=_load_object(row["block_json"], field="paper_source_blocks.block_json"),
        locator=_load_object(row["locator_json"], field="paper_source_blocks.locator_json"),
        disposition=_row_choice(row, "disposition", PAPER_BLOCK_DISPOSITIONS),
        item_id=row["item_id"],
        exclude_reason=row["exclude_reason"],
    )


def _issue_record(row: sqlite3.Row) -> IssueRecord:
    resolution = _load_optional_object(
        row["resolution_json"], field="paper_issues.resolution_json"
    )
    return IssueRecord(
        issue_id=_row_text(row, "id"),
        paper_revision_id=_row_text(row, "paper_revision_id"),
        code=_row_text(row, "code"),
        severity=_row_choice(row, "severity", _ISSUE_SEVERITIES),
        message=_row_text(row, "message"),
        block_id=row["block_id"],
        locator=_load_object(row["locator_json"], field="paper_issues.locator_json"),
        status=_row_choice(row, "status", _ISSUE_STATUSES),
        resolution=resolution,
        created_at=_row_text(row, "created_at"),
    )


def _proposal_record(row: sqlite3.Row) -> ProposalRecord:
    target_kind = row["target_kind"]
    if target_kind not in ("paper_revision", "lesson_revision"):
        raise _corrupt("教学库数据损坏：ai_proposals.target_kind 不在枚举内。")
    base_revision = row["base_revision"]
    if not isinstance(base_revision, int) or isinstance(base_revision, bool) or base_revision < 0:
        raise _corrupt("教学库数据损坏：ai_proposals.base_revision 不是非负整数。")
    return ProposalRecord(
        proposal_id=_row_text(row, "id"),
        job_id=_row_text(row, "job_id"),
        target_kind=target_kind,
        target_id=_row_text(row, "target_id"),
        base_revision=base_revision,
        payload=_load_object(row["payload_json"], field="ai_proposals.payload_json"),
        state=_row_choice(row, "state", _PROPOSAL_STATES),
        created_at=_row_text(row, "created_at"),
    )


# --------------------------------------------------------------------------- 仓储


class PaperRepository:
    """原卷相关表的唯一 SQL 入口；实例本身无状态。"""

    def __init__(self, catalog: TeachingCatalog) -> None:
        self._catalog = catalog

    # ---------------------------------------------------------------- 原卷

    def create_paper_in(
        self,
        conn: sqlite3.Connection,
        *,
        subject_id: str,
        title: str,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> PaperRecord:
        paper_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO papers (id, owner_id, subject_id, title, current_revision_id, "
            "status, revision, created_at) VALUES (?, ?, ?, ?, NULL, 'active', 0, ?)",
            (
                paper_id,
                _require_text(owner_id, field="owner_id"),
                _require_text(subject_id, field="subject_id"),
                _require_text(title, field="title"),
                now_iso(),
            ),
        )
        return self.require_paper_in(conn, paper_id)

    def get_paper_in(self, conn: sqlite3.Connection, paper_id: str) -> PaperRecord | None:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return _paper_record(row) if row is not None else None

    def require_paper_in(self, conn: sqlite3.Connection, paper_id: str) -> PaperRecord:
        record = self.get_paper_in(conn, paper_id)
        if record is None:
            raise _not_found(f"原卷不存在：{paper_id}。")
        return record

    def set_current_revision_in(
        self, conn: sqlite3.Connection, paper_id: str, revision_id: str | None
    ) -> None:
        conn.execute(
            "UPDATE papers SET current_revision_id = ? WHERE id = ?", (revision_id, paper_id)
        )

    def bump_revision_in(self, conn: sqlite3.Connection, paper_id: str) -> int:
        """原子自增 ``papers.revision`` 并返回新值（编辑锁）。"""
        cursor = conn.execute(
            "UPDATE papers SET revision = revision + 1 WHERE id = ?", (paper_id,)
        )
        if not cursor.rowcount:
            raise _not_found(f"原卷不存在：{paper_id}。")
        row = conn.execute("SELECT revision FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return _row_int(row, "revision")

    def set_status_in(self, conn: sqlite3.Connection, paper_id: str, status: str) -> None:
        if status not in _PAPER_STATUSES:
            raise _invalid(f"status 必须是 {sorted(_PAPER_STATUSES)} 之一。", fields=["status"])
        conn.execute("UPDATE papers SET status = ? WHERE id = ?", (status, paper_id))

    def list_papers(
        self,
        conn: sqlite3.Connection,
        *,
        subject_id: str | None = None,
        status: str | None = None,
        q: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PaperSummary], int]:
        offset, limit = _page(offset, limit)
        if status is not None and status not in _PAPER_STATUSES:
            raise _invalid(f"status 必须是 {sorted(_PAPER_STATUSES)} 之一。", fields=["status"])
        clauses: list[str] = []
        params: list[object] = []
        if subject_id is not None:
            clauses.append("p.subject_id = ?")
            params.append(_require_text(subject_id, field="subject_id"))
        if status is not None:
            clauses.append("p.status = ?")
            params.append(status)
        if q is not None and q.strip():
            clauses.append("p.title LIKE ? ESCAPE '\\'")
            params.append(f"%{_escape_like(q.strip())}%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        total = conn.execute(
            f"SELECT COUNT(*) AS total FROM papers p{where}", params
        ).fetchone()["total"]
        rows = conn.execute(
            f"SELECT p.id AS id FROM papers p{where} "
            "ORDER BY p.created_at DESC, p.rowid DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        items = [self.summary_in(conn, row["id"]) for row in rows]
        return items, int(total)

    def summary_in(self, conn: sqlite3.Connection, paper_id: str) -> PaperSummary:
        """概览：原卷行 + 当前修订（版本/状态/总分） + 计数（题目/计分叶/阻断问题）。"""
        row = conn.execute(
            """
            SELECT p.id, p.subject_id, p.title, p.status, p.revision, p.created_at,
                   p.current_revision_id,
                   r.version AS version, r.state AS current_state,
                   r.total_score_units AS total_score_units,
                   (SELECT COUNT(*) FROM paper_items i
                     WHERE i.paper_revision_id = p.current_revision_id) AS item_count,
                   (SELECT COUNT(*) FROM paper_items i
                     WHERE i.paper_revision_id = p.current_revision_id AND i.is_scored = 1
                       AND NOT EXISTS (SELECT 1 FROM paper_items c
                                        WHERE c.parent_item_id = i.id)) AS scored_leaf_count,
                   (SELECT COUNT(*) FROM paper_issues s
                     WHERE s.paper_revision_id = p.current_revision_id
                       AND s.severity = 'blocking' AND s.status = 'open')
                     AS blocking_issue_count,
                   (SELECT COUNT(*) FROM paper_source_blocks b
                     WHERE b.paper_revision_id = p.current_revision_id
                       AND b.disposition = 'unassigned') AS unassigned_block_count,
                   (SELECT COUNT(*) FROM paper_issues s
                     WHERE s.paper_revision_id = p.current_revision_id AND s.status = 'open')
                     AS open_issue_count
              FROM papers p
              LEFT JOIN paper_revisions r ON r.id = p.current_revision_id
             WHERE p.id = ?
            """,
            (paper_id,),
        ).fetchone()
        if row is None:
            raise _not_found(f"原卷不存在：{paper_id}。")
        version = row["version"]
        if version is not None and (
            not isinstance(version, int) or isinstance(version, bool) or version < 1
        ):
            raise _corrupt("教学库数据损坏：paper_revisions.version 不是正整数。")
        current_state = row["current_state"]
        if current_state is not None and current_state not in _REVISION_STATES:
            raise _corrupt("教学库数据损坏：paper_revisions.state 不在枚举内。")
        total_score_units = row["total_score_units"]
        if total_score_units is None:
            total_score_units = 0
        if (
            not isinstance(total_score_units, int)
            or isinstance(total_score_units, bool)
            or total_score_units < 0
        ):
            raise _corrupt("教学库数据损坏：paper_revisions.total_score_units 不是非负整数。")
        return PaperSummary(
            paper_id=_row_text(row, "id"),
            subject_id=_row_text(row, "subject_id"),
            title=_row_text(row, "title"),
            status=_row_choice(row, "status", _PAPER_STATUSES),
            revision=_row_int(row, "revision"),
            created_at=_row_text(row, "created_at"),
            current_revision_id=row["current_revision_id"],
            version=version or 0,
            current_state=current_state,
            total_score_units=total_score_units,
            item_count=int(row["item_count"]),
            scored_leaf_count=int(row["scored_leaf_count"]),
            blocking_issue_count=int(row["blocking_issue_count"]),
            unassigned_block_count=int(row["unassigned_block_count"]),
            open_issue_count=int(row["open_issue_count"]),
        )

    # ---------------------------------------------------------------- 修订

    def create_revision_in(
        self,
        conn: sqlite3.Connection,
        *,
        paper_id: str,
        version: int,
        source_file_id: str,
        total_score_units: int,
        title_snapshot: str,
        title_snapshot_source: str = "revision",
        state: str = "draft",
        revision_id: str | None = None,
    ) -> RevisionRecord:
        """新建草稿修订；``title_snapshot`` 必填（B3/G0 · B2-RV11）。

        修订级标题快照在创建时冻结：之后 ``papers.title`` 改名只影响新草稿，
        已有修订（含已确认修订）继续读自己的快照。
        """
        if state != "draft":
            # ``no_direct_sealed_paper_revisions`` 触发器是权威；这里给出同义的服务级拒绝
            raise _invalid("新修订只能以草稿状态创建；确认必须走确认闸门。", fields=["state"])
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise _invalid("version 必须是不小于 1 的整数。", fields=["version"])
        if (
            not isinstance(total_score_units, int)
            or isinstance(total_score_units, bool)
            or total_score_units < 0
        ):
            raise _invalid("total_score_units 必须是不小于 0 的整数。", fields=["totalScoreUnits"])
        new_id = uuid.uuid4().hex if revision_id is None else _require_text(
            revision_id, field="revision_id"
        )
        conn.execute(
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
            "source_practice_revision_id, total_score_units, state, confirmed_at, created_at, "
            "title_snapshot, title_snapshot_source) "
            "VALUES (?, ?, ?, ?, NULL, ?, 'draft', NULL, ?, ?, ?)",
            (
                new_id,
                _require_text(paper_id, field="paper_id"),
                version,
                _require_text(source_file_id, field="source_file_id"),
                total_score_units,
                now_iso(),
                _require_text(title_snapshot, field="title_snapshot"),
                _require_text(title_snapshot_source, field="title_snapshot_source"),
            ),
        )
        return self.require_revision_in(conn, new_id)

    def set_revision_title_snapshot_in(
        self,
        conn: sqlite3.Connection,
        revision_id: str,
        title: str,
        *,
        source: str = "revision",
    ) -> bool:
        """把修订级标题快照改写为 ``title``（只对草稿修订可达；确认后触发器拒绝）。"""
        cursor = conn.execute(
            "UPDATE paper_revisions SET title_snapshot = ?, title_snapshot_source = ? "
            "WHERE id = ?",
            (
                _require_text(title, field="title"),
                _require_text(source, field="source"),
                _require_text(revision_id, field="revision_id"),
            ),
        )
        return bool(cursor.rowcount)

    def get_revision_in(
        self, conn: sqlite3.Connection, revision_id: str
    ) -> RevisionRecord | None:
        row = conn.execute(
            "SELECT * FROM paper_revisions WHERE id = ?", (revision_id,)
        ).fetchone()
        return _revision_record(row) if row is not None else None

    def require_revision_in(self, conn: sqlite3.Connection, revision_id: str) -> RevisionRecord:
        record = self.get_revision_in(conn, revision_id)
        if record is None:
            raise _not_found(
                f"原卷修订不存在：{revision_id}。", code=PAPER_REVISION_NOT_FOUND
            )
        return record

    def require_revision_of_paper_in(
        self, conn: sqlite3.Connection, paper_id: str, revision_id: str
    ) -> RevisionRecord:
        """修订必须属于该原卷（跨卷访问按 404 处理，不泄漏他卷修订）。"""
        record = self.require_revision_in(conn, revision_id)
        if record.paper_id != paper_id:
            raise _not_found(
                f"原卷修订不属于该原卷：{revision_id}。", code=PAPER_REVISION_NOT_FOUND
            )
        return record

    def next_version_in(self, conn: sqlite3.Connection, paper_id: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM paper_revisions WHERE paper_id = ?",
            (paper_id,),
        ).fetchone()
        return int(row["version"]) + 1

    def set_revision_total_in(
        self, conn: sqlite3.Connection, revision_id: str, total_score_units: int
    ) -> None:
        if (
            not isinstance(total_score_units, int)
            or isinstance(total_score_units, bool)
            or total_score_units < 0
        ):
            raise _invalid("total_score_units 必须是不小于 0 的整数。", fields=["totalScoreUnits"])
        conn.execute(
            "UPDATE paper_revisions SET total_score_units = ? WHERE id = ?",
            (total_score_units, revision_id),
        )

    def confirm_revision_in(self, conn: sqlite3.Connection, revision_id: str) -> None:
        """置 ``confirmed``（``paper_confirm`` 触发器是权威闸门；服务层先做可定位预检）。"""
        conn.execute(
            "UPDATE paper_revisions SET state = 'confirmed', confirmed_at = ? "
            "WHERE id = ? AND state = 'draft'",
            (now_iso(), revision_id),
        )

    # ---------------------------------------------------------------- 题目

    def insert_items_in(
        self,
        conn: sqlite3.Connection,
        *,
        paper_revision_id: str,
        items: Sequence[ItemRecord | dict[str, Any]],
    ) -> None:
        """插入题目行（父先子后由调用方排序；事务统一 defer 外键）。"""
        for item in items:
            if isinstance(item, dict):
                row = item
            else:
                row = {
                    "item_id": item.item_id,
                    "parent_item_id": item.parent_item_id,
                    "question_no": item.question_no,
                    "ordinal": item.ordinal,
                    "is_scored": item.is_scored,
                    "max_score_units": item.max_score_units,
                    "content": item.content,
                    "source_locator": item.source_locator,
                }
            conn.execute(
                "INSERT INTO paper_items (id, paper_revision_id, parent_item_id, question_no, "
                "ordinal, is_scored, max_score_units, question_revision_id, content_json, "
                "source_locator_json) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    _require_text(row["item_id"], field="itemId"),
                    paper_revision_id,
                    row["parent_item_id"],
                    _require_text(row["question_no"], field="questionNo"),
                    row["ordinal"],
                    1 if row["is_scored"] else 0,
                    row["max_score_units"],
                    _dump_object(row["content"] or {}, field="content"),
                    _dump_object(row["source_locator"] or {}, field="sourceLocator"),
                ),
            )

    def delete_items_in(self, conn: sqlite3.Connection, paper_revision_id: str) -> None:
        conn.execute(
            "DELETE FROM paper_item_knowledge WHERE paper_revision_id = ?",
            (paper_revision_id,),
        )
        conn.execute("DELETE FROM paper_items WHERE paper_revision_id = ?", (paper_revision_id,))

    def insert_item_knowledge_in(
        self,
        conn: sqlite3.Connection,
        *,
        item_id: str,
        paper_revision_id: str,
        knowledge: Sequence[ItemKnowledgeRecord],
    ) -> None:
        for entry in knowledge:
            conn.execute(
                "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, "
                "knowledge_point_id, knowledge_revision_id, knowledge_name_snapshot, role, "
                "source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    item_id,
                    paper_revision_id,
                    entry.knowledge_point_id,
                    entry.knowledge_revision_id,
                    entry.knowledge_name_snapshot,
                    entry.role,
                    entry.source,
                ),
            )

    def taken_item_ids_in(
        self, conn: sqlite3.Connection, item_ids: Sequence[str]
    ) -> set[str]:
        """这些题目 id 是否已被**任一修订**占用（题目 id 是全局主键，跨修订不可复用）。"""
        requested = [item_id for item_id in dict.fromkeys(item_ids) if item_id]
        if not requested:
            return set()
        placeholders = ", ".join("?" for _ in requested)
        rows = conn.execute(
            f"SELECT id FROM paper_items WHERE id IN ({placeholders})", requested
        ).fetchall()
        return {row["id"] for row in rows}

    def list_items_in(
        self, conn: sqlite3.Connection, paper_revision_id: str
    ) -> list[ItemRecord]:
        rows = conn.execute(
            "SELECT * FROM paper_items WHERE paper_revision_id = ? "
            "ORDER BY ordinal ASC, rowid ASC",
            (paper_revision_id,),
        ).fetchall()
        knowledge_rows = conn.execute(
            "SELECT * FROM paper_item_knowledge WHERE paper_revision_id = ? ORDER BY rowid ASC",
            (paper_revision_id,),
        ).fetchall()
        by_item: dict[str, list[ItemKnowledgeRecord]] = {}
        for row in knowledge_rows:
            by_item.setdefault(row["item_id"], []).append(_knowledge_record(row))
        return [_item_record(row, tuple(by_item.get(row["id"], ()))) for row in rows]

    def copy_revision_content_in(
        self,
        conn: sqlite3.Connection,
        *,
        source_revision_id: str,
        target_revision_id: str,
    ) -> RevisionCopyMap:
        """把已确认修订的题目/块/问题逐行复制为草稿内容；返回逐行 id 映射。

        题目 id 重新生成，块行 id 按 ``<新修订 id>:<原解析器块 id>`` 生成（块 id 在解析器
        里是文档内序号，全局主键必须带修订命名空间）；确认修订的行不可变，复制体必须是
        一组全新行，避免"同一个 id 同时属于两个修订"引发的触发器与引用歧义。服务层用
        返回的映射把客户端基于旧修订的请求（itemId/blockId/issueId）翻译到新草稿上。
        """
        item_map: dict[str, str] = {}
        for item in self.list_items_in(conn, source_revision_id):
            new_id = uuid.uuid4().hex
            item_map[item.item_id] = new_id
        # 先建占位行（parent 待回填），再回填父引用并复制知识与内容
        for item in self.list_items_in(conn, source_revision_id):
            conn.execute(
                "INSERT INTO paper_items (id, paper_revision_id, parent_item_id, question_no, "
                "ordinal, is_scored, max_score_units, question_revision_id, content_json, "
                "source_locator_json) VALUES (?, ?, NULL, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    item_map[item.item_id],
                    target_revision_id,
                    item.question_no,
                    item.ordinal,
                    1 if item.is_scored else 0,
                    item.max_score_units,
                    _dump_object(item.content, field="content"),
                    _dump_object(item.source_locator, field="sourceLocator"),
                ),
            )
        for item in self.list_items_in(conn, source_revision_id):
            if item.parent_item_id is not None:
                mapped = item_map.get(item.parent_item_id)
                if mapped is None:
                    raise _corrupt("教学库数据损坏：题目父引用指向修订之外的题目。")
                conn.execute(
                    "UPDATE paper_items SET parent_item_id = ? WHERE id = ?",
                    (mapped, item_map[item.item_id]),
                )
            self.insert_item_knowledge_in(
                conn,
                item_id=item_map[item.item_id],
                paper_revision_id=target_revision_id,
                knowledge=item.knowledge,
            )
        block_map: dict[str, str] = {}
        for block in self.list_blocks_in(conn, source_revision_id):
            raw_id = block.block.get("id") if isinstance(block.block, dict) else None
            block_map[block.block_id] = (
                f"{target_revision_id}:{raw_id}"
                if isinstance(raw_id, str) and raw_id
                else uuid.uuid4().hex
            )
        for block in self.list_blocks_in(conn, source_revision_id):
            conn.execute(
                "INSERT INTO paper_source_blocks (id, paper_revision_id, ordinal, kind, "
                "block_json, locator_json, disposition, item_id, exclude_reason) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    block_map[block.block_id],
                    target_revision_id,
                    block.ordinal,
                    block.kind,
                    _dump_object(block.block, field="block"),
                    _dump_object(block.locator, field="locator"),
                    block.disposition,
                    item_map.get(block.item_id) if block.item_id else None,
                    block.exclude_reason,
                ),
            )
        issue_map: dict[str, str] = {}
        for issue in self.list_issues_in(conn, source_revision_id):
            new_issue_id = uuid.uuid4().hex
            issue_map[issue.issue_id] = new_issue_id
            conn.execute(
                "INSERT INTO paper_issues (id, paper_revision_id, code, severity, message, "
                "block_id, locator_json, status, resolution_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    new_issue_id,
                    target_revision_id,
                    issue.code,
                    issue.severity,
                    issue.message,
                    block_map.get(issue.block_id) if issue.block_id else None,
                    _dump_object(issue.locator, field="locator"),
                    issue.status,
                    _dump_object(issue.resolution, field="resolution")
                    if issue.resolution is not None
                    else None,
                    now_iso(),
                ),
            )
        return RevisionCopyMap(
            item_map=item_map, block_map=block_map, issue_map=issue_map
        )

    # ---------------------------------------------------------------- 原文块

    def insert_blocks_in(
        self,
        conn: sqlite3.Connection,
        *,
        paper_revision_id: str,
        blocks: Sequence[dict[str, Any]],
    ) -> None:
        for block in blocks:
            disposition = block.get("disposition", "unassigned")
            if disposition not in PAPER_BLOCK_DISPOSITIONS:
                raise _invalid(
                    f"块处置必须是 {sorted(PAPER_BLOCK_DISPOSITIONS)} 之一。",
                    fields=["disposition"],
                )
            conn.execute(
                "INSERT INTO paper_source_blocks (id, paper_revision_id, ordinal, kind, "
                "block_json, locator_json, disposition, item_id, exclude_reason) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _require_text(block["block_id"], field="blockId"),
                    paper_revision_id,
                    block["ordinal"],
                    _require_text(block["kind"], field="kind"),
                    _dump_object(block["block"], field="block"),
                    _dump_object(block.get("locator") or {}, field="locator"),
                    disposition,
                    block.get("item_id"),
                    block.get("exclude_reason"),
                ),
            )

    def list_blocks_in(
        self, conn: sqlite3.Connection, paper_revision_id: str
    ) -> list[BlockRecord]:
        rows = conn.execute(
            "SELECT * FROM paper_source_blocks WHERE paper_revision_id = ? "
            "ORDER BY ordinal ASC, rowid ASC",
            (paper_revision_id,),
        ).fetchall()
        return [_block_record(row) for row in rows]

    def update_block_in(
        self,
        conn: sqlite3.Connection,
        *,
        paper_revision_id: str,
        block_id: str,
        disposition: str,
        item_id: str | None,
        exclude_reason: str | None,
    ) -> bool:
        cursor = conn.execute(
            "UPDATE paper_source_blocks SET disposition = ?, item_id = ?, exclude_reason = ? "
            "WHERE id = ? AND paper_revision_id = ?",
            (disposition, item_id, exclude_reason, block_id, paper_revision_id),
        )
        return bool(cursor.rowcount)

    def clear_block_item_refs_in(
        self,
        conn: sqlite3.Connection,
        *,
        paper_revision_id: str,
        keep_item_ids: Sequence[str],
    ) -> int:
        """把引用了已不存在题目的块重置为 ``unassigned``（返回受影响块数）。

        整表替换题目后必须做这一步：被删除题目上的块不能悬空引用（外键 + 确认闸门
        都要求"每个块有归属或明确排除"）。
        """
        keep = {item_id for item_id in keep_item_ids}
        rows = conn.execute(
            "SELECT id, item_id FROM paper_source_blocks WHERE paper_revision_id = ? "
            "AND disposition = 'item'",
            (paper_revision_id,),
        ).fetchall()
        stale = [row["id"] for row in rows if row["item_id"] not in keep]
        for block_id in stale:
            conn.execute(
                "UPDATE paper_source_blocks SET disposition = 'unassigned', item_id = NULL "
                "WHERE id = ? AND paper_revision_id = ?",
                (block_id, paper_revision_id),
            )
        return len(stale)

    def update_block_payload_in(
        self,
        conn: sqlite3.Connection,
        *,
        paper_revision_id: str,
        block_id: str,
        block: dict[str, Any],
    ) -> bool:
        """改写块的持久化内容（B3/G0 · B2-RV02 补录）；``block_json`` 必须是 JSON 对象。"""
        cursor = conn.execute(
            "UPDATE paper_source_blocks SET block_json = ? "
            "WHERE id = ? AND paper_revision_id = ?",
            (
                _dump_object(block, field="block"),
                _require_text(block_id, field="block_id"),
                _require_text(paper_revision_id, field="paper_revision_id"),
            ),
        )
        return bool(cursor.rowcount)

    def insert_block_after_in(
        self,
        conn: sqlite3.Connection,
        *,
        paper_revision_id: str,
        after_block_id: str,
        block: dict[str, Any],
        kind: str,
        disposition: str,
        item_id: str | None,
        locator: dict[str, Any] | None = None,
    ) -> str:
        """在 ``after_block_id`` 之后插入一个新块并返回其行 id（B3/G0 · B2-RV02 补录资产）。

        ``ordinal`` 是修订内唯一键：从目标块之后按 **降序** 逐个 +1（降序移动不会与
        尚未让位的行冲突），再把新块放到 ``目标 ordinal + 1``。目标块不存在 → 422 可定位。
        """
        if disposition not in PAPER_BLOCK_DISPOSITIONS:
            raise _invalid(
                f"块处置必须是 {sorted(PAPER_BLOCK_DISPOSITIONS)} 之一。",
                fields=["disposition"],
            )
        revision_id = _require_text(paper_revision_id, field="paper_revision_id")
        target = conn.execute(
            "SELECT ordinal FROM paper_source_blocks WHERE id = ? AND paper_revision_id = ?",
            (_require_text(after_block_id, field="after_block_id"), revision_id),
        ).fetchone()
        if target is None:
            raise _invalid("目标原文块不在该修订内。", fields=["targetBlockId"])
        target_ordinal = int(target["ordinal"])
        shifting = conn.execute(
            "SELECT id, ordinal FROM paper_source_blocks WHERE paper_revision_id = ? "
            "AND ordinal > ? ORDER BY ordinal DESC",
            (revision_id, target_ordinal),
        ).fetchall()
        for row in shifting:
            conn.execute(
                "UPDATE paper_source_blocks SET ordinal = ? WHERE id = ? AND paper_revision_id = ?",
                (int(row["ordinal"]) + 1, row["id"], revision_id),
            )
        payload = dict(block)
        raw_id = payload.get("id")
        if not isinstance(raw_id, str) or not raw_id:
            raise _invalid("新块的 block.id 必须是非空字符串。", fields=["blockId"])
        new_id = f"{revision_id}:{raw_id}"
        conn.execute(
            "INSERT INTO paper_source_blocks (id, paper_revision_id, ordinal, kind, "
            "block_json, locator_json, disposition, item_id, exclude_reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                new_id,
                revision_id,
                target_ordinal + 1,
                _require_text(kind, field="kind"),
                _dump_object(payload, field="block"),
                _dump_object(dict(locator or {}), field="locator"),
                disposition,
                item_id,
            ),
        )
        return new_id

    def count_unassigned_in(self, conn: sqlite3.Connection, paper_revision_id: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM paper_source_blocks "
            "WHERE paper_revision_id = ? AND disposition = 'unassigned'",
            (paper_revision_id,),
        ).fetchone()
        return int(row["n"])

    # ---------------------------------------------------------------- 问题清单

    def insert_issues_in(
        self,
        conn: sqlite3.Connection,
        *,
        paper_revision_id: str,
        issues: Sequence[dict[str, Any]],
    ) -> list[IssueRecord]:
        created_at = now_iso()
        for issue in issues:
            conn.execute(
                "INSERT INTO paper_issues (id, paper_revision_id, code, severity, message, "
                "block_id, locator_json, status, resolution_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', NULL, ?)",
                (
                    issue.get("issue_id") or uuid.uuid4().hex,
                    paper_revision_id,
                    _require_text(issue["code"], field="code"),
                    _require_text(issue["severity"], field="severity"),
                    _require_text(issue["message"], field="message"),
                    issue.get("block_id"),
                    _dump_object(issue.get("locator") or {}, field="locator"),
                    created_at,
                ),
            )
        return self.list_issues_in(conn, paper_revision_id)

    def list_issues_in(
        self, conn: sqlite3.Connection, paper_revision_id: str
    ) -> list[IssueRecord]:
        rows = conn.execute(
            "SELECT * FROM paper_issues WHERE paper_revision_id = ? "
            "ORDER BY rowid ASC",
            (paper_revision_id,),
        ).fetchall()
        return [_issue_record(row) for row in rows]

    def get_issue_in(
        self, conn: sqlite3.Connection, paper_revision_id: str, issue_id: str
    ) -> IssueRecord | None:
        row = conn.execute(
            "SELECT * FROM paper_issues WHERE id = ? AND paper_revision_id = ?",
            (issue_id, paper_revision_id),
        ).fetchone()
        return _issue_record(row) if row is not None else None

    def update_issue_in(
        self,
        conn: sqlite3.Connection,
        *,
        paper_revision_id: str,
        issue_id: str,
        status: str,
        resolution: dict[str, Any] | None,
    ) -> bool:
        if status not in _ISSUE_STATUSES:
            raise _invalid(f"status 必须是 {sorted(_ISSUE_STATUSES)} 之一。", fields=["status"])
        cursor = conn.execute(
            "UPDATE paper_issues SET status = ?, resolution_json = ? "
            "WHERE id = ? AND paper_revision_id = ?",
            (
                status,
                _dump_object(resolution, field="resolution") if resolution is not None else None,
                issue_id,
                paper_revision_id,
            ),
        )
        return bool(cursor.rowcount)

    def count_open_blocking_in(self, conn: sqlite3.Connection, paper_revision_id: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM paper_issues "
            "WHERE paper_revision_id = ? AND severity = 'blocking' AND status = 'open'",
            (paper_revision_id,),
        ).fetchone()
        return int(row["n"])

    # ---------------------------------------------------------------- 提交幂等

    def submission_recorded_in(
        self,
        conn: sqlite3.Connection,
        *,
        owner_id: str,
        operation: str,
        submission_id: str,
    ) -> bool:
        """该提交是否已登记（只读；确认重放判定用，不替代 ``execute_command`` 的 hash 校验）。"""
        row = conn.execute(
            "SELECT 1 FROM command_submissions "
            "WHERE owner_id = ? AND operation = ? AND submission_id = ?",
            (
                _require_text(owner_id, field="owner_id"),
                _require_text(operation, field="operation"),
                _require_text(submission_id, field="submission_id"),
            ),
        ).fetchone()
        return row is not None

    # ---------------------------------------------------------------- AI 建议

    def create_proposal_in(
        self,
        conn: sqlite3.Connection,
        *,
        job_id: str,
        target_revision_id: str,
        base_revision: int,
        payload: dict[str, Any],
        proposal_id: str | None = None,
    ) -> ProposalRecord:
        new_id = proposal_id or uuid.uuid4().hex
        conn.execute(
            "INSERT INTO ai_proposals (id, job_id, target_kind, target_id, base_revision, "
            "payload_json, state, created_at) VALUES (?, ?, 'paper_revision', ?, ?, ?, "
            "'pending', ?)",
            (
                _require_text(new_id, field="proposal_id"),
                _require_text(job_id, field="job_id"),
                _require_text(target_revision_id, field="target_revision_id"),
                base_revision,
                _dump_object(payload, field="payload"),
                now_iso(),
            ),
        )
        return self.require_proposal_in(conn, new_id)

    def get_proposal_in(
        self, conn: sqlite3.Connection, proposal_id: str
    ) -> ProposalRecord | None:
        row = conn.execute("SELECT * FROM ai_proposals WHERE id = ?", (proposal_id,)).fetchone()
        return _proposal_record(row) if row is not None else None

    def require_proposal_in(
        self, conn: sqlite3.Connection, proposal_id: str
    ) -> ProposalRecord:
        record = self.get_proposal_in(conn, proposal_id)
        if record is None:
            raise _not_found(
                f"AI 建议不存在：{proposal_id}。", code="PAPER_PROPOSAL_NOT_FOUND"
            )
        return record

    def find_proposal_by_job_in(
        self, conn: sqlite3.Connection, job_id: str
    ) -> ProposalRecord | None:
        row = conn.execute(
            "SELECT * FROM ai_proposals WHERE job_id = ? ORDER BY rowid DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        return _proposal_record(row) if row is not None else None

    def list_proposals_in(
        self, conn: sqlite3.Connection, target_revision_id: str
    ) -> list[ProposalRecord]:
        rows = conn.execute(
            "SELECT * FROM ai_proposals WHERE target_kind = 'paper_revision' AND target_id = ? "
            "ORDER BY created_at DESC, rowid DESC",
            (target_revision_id,),
        ).fetchall()
        return [_proposal_record(row) for row in rows]

    def set_proposal_state_in(
        self, conn: sqlite3.Connection, proposal_id: str, state: str
    ) -> bool:
        if state not in _PROPOSAL_STATES:
            raise _invalid(f"state 必须是 {sorted(_PROPOSAL_STATES)} 之一。", fields=["state"])
        cursor = conn.execute(
            "UPDATE ai_proposals SET state = ? WHERE id = ?", (state, proposal_id)
        )
        return bool(cursor.rowcount)


__all__ = [
    "BlockRecord",
    "ItemKnowledgeRecord",
    "ItemRecord",
    "IssueRecord",
    "PAPER_REVISION_NOT_FOUND",
    "PAPER_ROW_CORRUPT",
    "PaperRecord",
    "PaperRepository",
    "PaperSummary",
    "ProposalRecord",
    "RevisionCopyMap",
    "RevisionRecord",
]


# --------------------------------------------------------------------------- 内部


def _page(offset: int, limit: int) -> tuple[int, int]:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise _invalid("offset 必须是不小于 0 的整数。", fields=["offset"])
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 1
        or limit > MAX_LIST_LIMIT
    ):
        raise _invalid(f"limit 必须是 1..{MAX_LIST_LIMIT} 的整数。", fields=["limit"])
    return offset, limit


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
