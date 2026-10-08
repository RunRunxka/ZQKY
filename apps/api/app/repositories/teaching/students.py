"""学生与班级归属仓储（TEACHING-LOOP B1 / T30-a）：只做 SQL。

- **学号按文本保存**：``WHERE student_no = ?`` 精确匹配，绝不做数值化（``0012`` 保持 ``0012``）；
  ``UNIQUE(owner_id, student_no)`` 冲突 → 409 ``STUDENT_NO_CONFLICT``；``student_no`` 允许 NULL
  （无学号显式建档），姓名允许重名（同名只提示不合并）。
- 归属历史：``insert_membership_in`` 命中 ``ux_active_membership``（同班同学活跃归属）时
  **幂等跳过**并如实返回 ``created=False``；``transfer_in`` 在同一事务把旧归属置 ``left_on``、
  新增目标班归属并递增学生 ``revision``；旧归属与历史记录一律保留。
- 更新走乐观锁 ``revision``：不符 → 409 ``REVISION_CONFLICT`` + ``details.currentRevision``。
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass

from app.contracts.roster import (
    STUDENT_NO_CONFLICT,
    StudentMembershipView,
    StudentView,
)
from app.contracts.teaching_loop import REVISION_CONFLICT, error_details
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.catalog import TeachingCatalog

DEFAULT_OWNER_ID = "local"
MAX_LIST_LIMIT = 200
STUDENT_STATUSES: frozenset[str] = frozenset({"active", "archived"})

STUDENT_NOT_FOUND = "STUDENT_NOT_FOUND"
STUDENT_ROW_CORRUPT = "STUDENT_ROW_CORRUPT"

_MEMBERSHIP_SELECT = """
SELECT m.id, m.class_id, m.student_id, m.joined_on, m.left_on, c.name AS class_name
  FROM class_memberships m
  JOIN classes c ON c.id = m.class_id
"""


def _invalid(message: str, *, fields: list[str] | None = None) -> AppError:
    return AppError(
        message,
        code="INVALID_REQUEST",
        status_code=422,
        details=error_details(fields=fields) if fields else None,
    )


def _not_found(student_id: str) -> AppError:
    return AppError(f"学生不存在：{student_id}。", code=STUDENT_NOT_FOUND, status_code=404)


def _corrupt(message: str) -> AppError:
    return AppError(message, code=STUDENT_ROW_CORRUPT, status_code=500)


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。", fields=[field])
    return value.strip()


def _check_revision(current: int, expected: int) -> None:
    if current != expected:
        raise AppError(
            "数据已被其他操作更新，请刷新后重试。",
            code=REVISION_CONFLICT,
            status_code=409,
            details=error_details(current_revision=current),
        )


def _student_no_conflict() -> AppError:
    return AppError(
        "该学号在本机学生库中已存在；请改用 link 或核对学号。",
        code=STUDENT_NO_CONFLICT,
        status_code=409,
    )


def _like_pattern(text: str) -> str:
    """把用户输入转义为 LIKE 模式（``\\`` / ``%`` / ``_`` 不参与通配）。"""
    escaped = (
        text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


@dataclass(frozen=True)
class MembershipRecord:
    """``class_memberships`` 一行（附班级名称）。"""

    membership_id: str
    class_id: str
    class_name: str
    joined_on: str
    left_on: str | None

    @property
    def active(self) -> bool:
        return self.left_on is None

    def view(self) -> StudentMembershipView:
        return StudentMembershipView(
            membershipId=self.membership_id,
            classId=self.class_id,
            className=self.class_name,
            joinedOn=self.joined_on,
            leftOn=self.left_on,
        )


@dataclass(frozen=True)
class StudentRecord:
    """``students`` 一行 + 归属历史。``view()`` 给出对外 camelCase 视图。"""

    id: str
    owner_id: str
    student_no: str | None
    name: str
    status: str
    revision: int
    created_at: str
    memberships: tuple[MembershipRecord, ...] = ()

    def view(self) -> StudentView:
        return StudentView(
            id=self.id,
            studentNo=self.student_no,
            name=self.name,
            status=self.status,
            revision=self.revision,
            memberships=[item.view() for item in self.memberships],
            createdAt=self.created_at,
        )


class StudentRepository:
    """学生表与归属历史表的唯一读写入口。"""

    def __init__(self, catalog: TeachingCatalog) -> None:
        self._catalog = catalog

    # -------------------------------------------------------------- 学生写入

    def create(
        self,
        *,
        name: str,
        student_no: str | None = None,
        owner_id: str = DEFAULT_OWNER_ID,
        student_id: str | None = None,
    ) -> StudentRecord:
        with self._catalog.write_transaction() as conn:
            return self.create_in(
                conn,
                name=name,
                student_no=student_no,
                owner_id=owner_id,
                student_id=student_id,
            )

    def create_in(
        self,
        conn: sqlite3.Connection,
        *,
        name: str,
        student_no: str | None = None,
        owner_id: str = DEFAULT_OWNER_ID,
        student_id: str | None = None,
    ) -> StudentRecord:
        name = _require_text(name, field="name")
        owner_id = _require_text(owner_id, field="owner_id")
        if student_no is not None:
            if not isinstance(student_no, str):
                raise _invalid("studentNo 必须是字符串或 null。", fields=["studentNo"])
            student_no = student_no.strip() or None
        new_id = student_id or uuid.uuid4().hex
        created_at = now_iso()
        try:
            conn.execute(
                "INSERT INTO students "
                "(id, owner_id, student_no, name, status, revision, created_at) "
                "VALUES (?, ?, ?, ?, 'active', 0, ?)",
                (new_id, owner_id, student_no, name, created_at),
            )
        except sqlite3.IntegrityError as exc:
            message = str(exc).upper()
            if "UNIQUE" in message:
                raise _student_no_conflict() from exc
            raise _invalid("学生数据不满足约束，请检查姓名与学号。") from exc
        return StudentRecord(
            id=new_id,
            owner_id=owner_id,
            student_no=student_no,
            name=name,
            status="active",
            revision=0,
            created_at=created_at,
        )

    def set_status(
        self,
        student_id: str,
        *,
        expected_revision: int,
        status: str,
    ) -> StudentRecord:
        with self._catalog.write_transaction() as conn:
            return self.set_status_in(
                conn, student_id, expected_revision=expected_revision, status=status
            )

    def set_status_in(
        self,
        conn: sqlite3.Connection,
        student_id: str,
        *,
        expected_revision: int,
        status: str,
    ) -> StudentRecord:
        """归档/恢复：只改 ``status`` 并递增 ``revision``；归属历史原样保留。"""
        if status not in STUDENT_STATUSES:
            raise _invalid("status 只能是 active 或 archived。", fields=["status"])
        current = self._require_row_in(conn, student_id)
        _check_revision(current["revision"], expected_revision)
        conn.execute(
            "UPDATE students SET status = ?, revision = revision + 1 WHERE id = ?",
            (status, student_id),
        )
        return self._require_record_in(conn, student_id)

    def update(
        self,
        student_id: str,
        *,
        expected_revision: int,
        name: str | None = None,
        student_no: str | None = None,
    ) -> StudentRecord:
        with self._catalog.write_transaction() as conn:
            return self.update_in(
                conn,
                student_id,
                expected_revision=expected_revision,
                name=name,
                student_no=student_no,
            )

    def update_in(
        self,
        conn: sqlite3.Connection,
        student_id: str,
        *,
        expected_revision: int,
        name: str | None = None,
        student_no: str | None = None,
    ) -> StudentRecord:
        """改名/改学号；``None`` 表示**不修改该字段**（本批不支持清空学号）。"""
        current = self._require_row_in(conn, student_id)
        _check_revision(current["revision"], expected_revision)
        fields: dict[str, object] = {}
        if name is not None:
            fields["name"] = _require_text(name, field="name")
        if student_no is not None:
            if not isinstance(student_no, str):
                raise _invalid("studentNo 必须是字符串或 null。", fields=["studentNo"])
            normalized = student_no.strip()
            if not normalized:
                raise _invalid(
                    "studentNo 不能为空字符串；本批不支持清空学号。", fields=["studentNo"]
                )
            fields["student_no"] = normalized
        if fields:
            assignments = ", ".join(f"{column} = ?" for column in fields)
            try:
                conn.execute(
                    f"UPDATE students SET {assignments}, revision = revision + 1 WHERE id = ?",
                    (*fields.values(), student_id),
                )
            except sqlite3.IntegrityError as exc:
                if "UNIQUE" in str(exc).upper():
                    raise _student_no_conflict() from exc
                raise _invalid("学生数据不满足约束，请检查姓名与学号。") from exc
        return self._require_record_in(conn, student_id)

    # -------------------------------------------------------------- 学生读取

    def get(self, student_id: str) -> StudentRecord:
        with self._catalog.read_connection() as conn:
            record = self.get_in(conn, student_id)
        if record is None:
            raise _not_found(student_id)
        return record

    def get_in(
        self, conn: sqlite3.Connection, student_id: str
    ) -> StudentRecord | None:
        if not isinstance(student_id, str) or not student_id.strip():
            raise _invalid("student_id 必须是非空字符串。", fields=["studentId"])
        row = conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id.strip(),)
        ).fetchone()
        if row is None:
            return None
        return self._with_memberships_in(conn, self._record(row))

    def require_in(self, conn: sqlite3.Connection, student_id: str) -> StudentRecord:
        record = self.get_in(conn, student_id)
        if record is None:
            raise _not_found(student_id)
        return record

    def exists_in(self, conn: sqlite3.Connection, student_id: str) -> bool:
        if not isinstance(student_id, str) or not student_id.strip():
            return False
        row = conn.execute(
            "SELECT 1 FROM students WHERE id = ?", (student_id.strip(),)
        ).fetchone()
        return row is not None

    def find_by_no_in(
        self,
        conn: sqlite3.Connection,
        student_no: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> StudentRecord | None:
        """按 ``(owner_id, student_no)`` **精确**（文本）查一名学生。"""
        text = _require_text(student_no, field="studentNo")
        row = conn.execute(
            "SELECT * FROM students WHERE owner_id = ? AND student_no = ?",
            (owner_id, text),
        ).fetchone()
        if row is None:
            return None
        return self._with_memberships_in(conn, self._record(row))

    def map_by_student_no_in(
        self,
        conn: sqlite3.Connection,
        numbers: list[str],
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        status: str = "active",
    ) -> dict[str, StudentRecord]:
        """批量按学号精确匹配（保持文本相等，不做数值化）。

        默认只匹配**活跃**学生：归档学生不参与名单导入自动关联（避免误关联已移除身份）。
        """
        wanted: list[str] = []
        seen: set[str] = set()
        for number in numbers:
            if isinstance(number, str) and number and number not in seen:
                seen.add(number)
                wanted.append(number)
        if not wanted:
            return {}
        placeholders = ", ".join("?" for _ in wanted)
        rows = conn.execute(
            "SELECT * FROM students WHERE owner_id = ? AND status = ? "
            f"AND student_no IN ({placeholders})",
            (owner_id, status, *wanted),
        ).fetchall()
        return {row["student_no"]: self._record(row) for row in rows}

    def map_by_name_in(
        self,
        conn: sqlite3.Connection,
        names: list[str],
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        status: str = "active",
    ) -> dict[str, list[StudentRecord]]:
        """批量按姓名精确匹配；同名多人在结果里原样保留（不静默选一个）。

        默认只匹配**活跃**学生（与 ``map_by_student_no_in`` 同口径）。
        """
        wanted: list[str] = []
        seen: set[str] = set()
        for name in names:
            if isinstance(name, str) and name and name not in seen:
                seen.add(name)
                wanted.append(name)
        if not wanted:
            return {}
        placeholders = ", ".join("?" for _ in wanted)
        rows = conn.execute(
            f"SELECT * FROM students WHERE owner_id = ? AND status = ? "
            f"AND name IN ({placeholders}) "
            "ORDER BY created_at ASC, rowid ASC",
            (owner_id, status, *wanted),
        ).fetchall()
        result: dict[str, list[StudentRecord]] = {}
        for row in rows:
            result.setdefault(row["name"], []).append(self._record(row))
        return result

    def list(
        self,
        *,
        q: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> tuple[list[StudentRecord], int]:
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise _invalid("offset 必须是不小于 0 的整数。", fields=["offset"])
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or limit > MAX_LIST_LIMIT
        ):
            raise _invalid(
                f"limit 必须是 1..{MAX_LIST_LIMIT} 的整数。", fields=["limit"]
            )
        if status is not None and status not in STUDENT_STATUSES:
            raise _invalid("status 只能是 active 或 archived。", fields=["status"])
        where = "WHERE owner_id = ?"
        params: list[object] = [owner_id]
        if status is not None:
            where += " AND status = ?"
            params.append(status)
        if isinstance(q, str) and q.strip():
            where += " AND (name LIKE ? ESCAPE '\\' OR student_no LIKE ? ESCAPE '\\')"
            pattern = _like_pattern(q.strip())
            params.extend([pattern, pattern])
        with self._catalog.read_connection() as conn:
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) AS n FROM students {where}", tuple(params)
                ).fetchone()["n"]
            )
            rows = conn.execute(
                f"SELECT * FROM students {where} "
                "ORDER BY created_at ASC, rowid ASC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
            records = [self._record(row) for row in rows]
            records = self._attach_memberships_in(conn, records)
        return records, total

    def list_in_class(
        self, class_id: str, *, include_archived: bool = False
    ) -> tuple[list[StudentRecord], int]:
        with self._catalog.read_connection() as conn:
            return self.list_in_class_in(conn, class_id, include_archived=include_archived)

    def list_in_class_in(
        self,
        conn: sqlite3.Connection,
        class_id: str,
        *,
        include_archived: bool = False,
    ) -> tuple[list[StudentRecord], int]:
        """该班**活跃**成员（``left_on IS NULL``）；每名学生的完整归属历史一并带出。

        默认排除已归档学生（归档 = 退出新流程；历史快照不受影响）；
        ``include_archived=True`` 供名单管理界面显示并恢复。
        """
        class_id = _require_text(class_id, field="classId")
        sql = (
            "SELECT s.* FROM students s "
            "JOIN class_memberships m ON m.student_id = s.id "
            "WHERE m.class_id = ? AND m.left_on IS NULL "
        )
        if not include_archived:
            sql += "AND s.status = 'active' "
        sql += "ORDER BY s.created_at ASC, s.rowid ASC"
        rows = conn.execute(sql, (class_id,)).fetchall()
        records = self._attach_memberships_in(
            conn, [self._record(row) for row in rows]
        )
        return records, len(records)

    # -------------------------------------------------------------- 归属

    def memberships_in(
        self, conn: sqlite3.Connection, student_id: str
    ) -> list[MembershipRecord]:
        rows = conn.execute(
            f"{_MEMBERSHIP_SELECT} WHERE m.student_id = ? "
            "ORDER BY m.joined_on ASC, m.rowid ASC",
            (student_id,),
        ).fetchall()
        return [self._membership(row) for row in rows]

    def active_membership_in(
        self,
        conn: sqlite3.Connection,
        student_id: str,
        *,
        class_id: str | None = None,
    ) -> MembershipRecord | None:
        sql = f"{_MEMBERSHIP_SELECT} WHERE m.student_id = ? AND m.left_on IS NULL"
        params: list[object] = [student_id]
        if class_id is not None:
            sql += " AND m.class_id = ?"
            params.append(class_id)
        sql += " ORDER BY m.joined_on DESC, m.rowid DESC LIMIT 1"
        row = conn.execute(sql, tuple(params)).fetchone()
        return self._membership(row) if row is not None else None

    def active_membership(
        self, student_id: str, *, class_id: str | None = None
    ) -> MembershipRecord | None:
        with self._catalog.read_connection() as conn:
            return self.active_membership_in(conn, student_id, class_id=class_id)

    def insert_membership_in(
        self,
        conn: sqlite3.Connection,
        *,
        class_id: str,
        student_id: str,
        joined_on: str,
    ) -> tuple[MembershipRecord, bool]:
        """新增归属；该班已有活跃归属（同班同学）时**幂等跳过**，返回 ``created=False``。

        目标班/学生不存在时由外键拒绝（服务层先做存在性与归档校验）。
        """
        class_id = _require_text(class_id, field="classId")
        student_id = _require_text(student_id, field="studentId")
        joined_on = _require_text(joined_on, field="joinedOn")
        existing = self.active_membership_in(conn, student_id, class_id=class_id)
        if existing is not None:
            return existing, False
        previous = conn.execute(
            "SELECT id FROM class_memberships "
            "WHERE class_id = ? AND student_id = ? AND joined_on = ?",
            (class_id, student_id, joined_on),
        ).fetchone()
        if previous is not None:
            # 同一 (班级, 学生, 加入日期) 已有归属行：不重复建行，如实返回 created=False。
            record = self._membership_by_id_in(conn, previous["id"])
            assert record is not None  # pragma: no cover - 同事务内刚读到
            return record, False
        membership_id = uuid.uuid4().hex
        try:
            conn.execute(
                "INSERT INTO class_memberships (id, class_id, student_id, joined_on, left_on) "
                "VALUES (?, ?, ?, ?, NULL)",
                (membership_id, class_id, student_id, joined_on),
            )
        except sqlite3.IntegrityError as exc:
            record = self.active_membership_in(conn, student_id, class_id=class_id)
            if record is not None:
                return record, False
            raise _invalid("归属写入不满足约束，请检查班级与学生。") from exc
        record = self._membership_by_id_in(conn, membership_id)
        assert record is not None  # pragma: no cover - 同事务内刚写入
        return record, True

    def close_active_membership_in(
        self,
        conn: sqlite3.Connection,
        *,
        class_id: str,
        student_id: str,
        left_on: str,
    ) -> bool:
        left_on = _require_text(left_on, field="leftOn")
        try:
            cursor = conn.execute(
                "UPDATE class_memberships SET left_on = ? "
                "WHERE class_id = ? AND student_id = ? AND left_on IS NULL",
                (left_on, class_id, student_id),
            )
        except sqlite3.IntegrityError as exc:
            # 表级 CHECK：left_on IS NULL OR left_on >= joined_on
            raise _invalid(
                "离班（转班）日期不能早于入班日期。", fields=["movedOn"]
            ) from exc
        return cursor.rowcount > 0

    def transfer_in(
        self,
        conn: sqlite3.Connection,
        student_id: str,
        *,
        from_class_id: str,
        to_class_id: str,
        moved_on: str,
        expected_revision: int,
    ) -> StudentRecord:
        """转班（同一事务）：旧归属置 ``left_on`` + 目标班新增归属 + 学生 revision+1。

        来源班没有活跃归属时 422（请求不适用），不做静默无操作。
        """
        if from_class_id == to_class_id:
            raise _invalid("转班的来源与目标班级不能相同。", fields=["toClassId"])
        current = self._require_row_in(conn, student_id)
        _check_revision(current["revision"], expected_revision)
        closed = self.close_active_membership_in(
            conn, class_id=from_class_id, student_id=student_id, left_on=moved_on
        )
        if not closed:
            raise _invalid(
                "学生在来源班级没有活跃归属，无法转班。", fields=["fromClassId"]
            )
        self.insert_membership_in(
            conn, class_id=to_class_id, student_id=student_id, joined_on=moved_on
        )
        conn.execute(
            "UPDATE students SET revision = revision + 1 WHERE id = ?", (student_id,)
        )
        return self._require_record_in(conn, student_id)

    # -------------------------------------------------------------- 内部

    def _require_row_in(
        self, conn: sqlite3.Connection, student_id: str
    ) -> sqlite3.Row:
        if not isinstance(student_id, str) or not student_id.strip():
            raise _invalid("student_id 必须是非空字符串。", fields=["studentId"])
        row = conn.execute(
            "SELECT revision FROM students WHERE id = ?", (student_id.strip(),)
        ).fetchone()
        if row is None:
            raise _not_found(student_id)
        return row

    def _require_record_in(
        self, conn: sqlite3.Connection, student_id: str
    ) -> StudentRecord:
        row = conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id.strip(),)
        ).fetchone()
        if row is None:  # pragma: no cover - 调用前已确认存在
            raise _not_found(student_id)
        return self._with_memberships_in(conn, self._record(row))

    def _with_memberships_in(
        self, conn: sqlite3.Connection, record: StudentRecord
    ) -> StudentRecord:
        memberships = tuple(self.memberships_in(conn, record.id))
        return StudentRecord(
            id=record.id,
            owner_id=record.owner_id,
            student_no=record.student_no,
            name=record.name,
            status=record.status,
            revision=record.revision,
            created_at=record.created_at,
            memberships=memberships,
        )

    def _attach_memberships_in(
        self, conn: sqlite3.Connection, records: list[StudentRecord]
    ) -> list[StudentRecord]:
        if not records:
            return []
        ids = [record.id for record in records]
        placeholders = ", ".join("?" for _ in ids)
        rows = conn.execute(
            f"{_MEMBERSHIP_SELECT} WHERE m.student_id IN ({placeholders}) "
            "ORDER BY m.joined_on ASC, m.rowid ASC",
            tuple(ids),
        ).fetchall()
        grouped: dict[str, list[MembershipRecord]] = {}
        for row in rows:
            grouped.setdefault(row["student_id"], []).append(self._membership(row))
        return [
            StudentRecord(
                id=record.id,
                owner_id=record.owner_id,
                student_no=record.student_no,
                name=record.name,
                status=record.status,
                revision=record.revision,
                created_at=record.created_at,
                memberships=tuple(grouped.get(record.id, ())),
            )
            for record in records
        ]

    def _membership_by_id_in(
        self, conn: sqlite3.Connection, membership_id: str
    ) -> MembershipRecord | None:
        row = conn.execute(
            f"{_MEMBERSHIP_SELECT} WHERE m.id = ?", (membership_id,)
        ).fetchone()
        return self._membership(row) if row is not None else None

    @staticmethod
    def _membership(row: sqlite3.Row) -> MembershipRecord:
        joined_on = row["joined_on"]
        left_on = row["left_on"]
        class_name = row["class_name"]
        if not isinstance(joined_on, str) or not joined_on:
            raise _corrupt("教学库数据损坏：class_memberships.joined_on 不是非空字符串。")
        if left_on is not None and (not isinstance(left_on, str) or not left_on):
            raise _corrupt("教学库数据损坏：class_memberships.left_on 结构不符。")
        if not isinstance(class_name, str) or not class_name:
            raise _corrupt("教学库数据损坏：班级名称缺失。")
        return MembershipRecord(
            membership_id=row["id"],
            class_id=row["class_id"],
            class_name=class_name,
            joined_on=joined_on,
            left_on=left_on,
        )

    @staticmethod
    def _record(row: sqlite3.Row) -> StudentRecord:
        status = row["status"]
        if not isinstance(status, str) or status not in STUDENT_STATUSES:
            raise _corrupt(f"教学库数据损坏：students.status 结构不符（{status!r}）。")
        revision = row["revision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise _corrupt("教学库数据损坏：students.revision 不是非负整数。")
        student_no = row["student_no"]
        if student_no is not None:
            if not isinstance(student_no, str) or not student_no.strip():
                raise _corrupt("教学库数据损坏：students.student_no 结构不符。")
        name = row["name"]
        if not isinstance(name, str) or not name.strip():
            raise _corrupt("教学库数据损坏：students.name 不是非空字符串。")
        for field in ("id", "owner_id", "created_at"):
            value = row[field]
            if not isinstance(value, str) or not value:
                raise _corrupt(f"教学库数据损坏：students.{field} 不是非空字符串。")
        return StudentRecord(
            id=row["id"],
            owner_id=row["owner_id"],
            student_no=student_no,
            name=name,
            status=status,
            revision=revision,
            created_at=row["created_at"],
        )


__all__ = [
    "DEFAULT_OWNER_ID",
    "MAX_LIST_LIMIT",
    "STUDENT_NOT_FOUND",
    "STUDENT_ROW_CORRUPT",
    "STUDENT_STATUSES",
    "MembershipRecord",
    "StudentRecord",
    "StudentRepository",
]
