"""班级仓储（TEACHING-LOOP B1 / T30-a）：只做 SQL，不含表格/文件/模型逻辑。

纪律与其余仓储一致：写操作一律经 ``catalog.write_transaction()``（``BEGIN IMMEDIATE``），
读操作经 ``catalog.read_connection()``；类型来自 ``app.contracts.roster``（``ClassView``），
**不复制第二份字段**。服务层在同一写事务内组合多个 ``*_in(conn, ...)`` 方法。

- ``UNIQUE(owner_id, school_year, code)`` 冲突 → 409 ``CLASS_CODE_CONFLICT``（不产生半成品行）；
- 更新/归档/恢复一律走乐观锁 ``revision``：不符 → 409 ``REVISION_CONFLICT`` + ``details.currentRevision``；
- 归档班级**仍可读**（``get``/``list`` 不过滤 status，status 只是过滤参数）；
- ``student_count`` = 该班 ``left_on IS NULL`` 的活跃归属数（SQL 子查询，不用缓存列）。
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass

from app.contracts.roster import CLASS_CODE_CONFLICT, ClassStatus, ClassView
from app.contracts.teaching_loop import REVISION_CONFLICT, error_details
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.catalog import TeachingCatalog

DEFAULT_OWNER_ID = "local"
MAX_LIST_LIMIT = 200
CLASS_STATUSES: frozenset[str] = frozenset({"active", "archived"})

CLASS_NOT_FOUND = "CLASS_NOT_FOUND"
CLASS_ROW_CORRUPT = "CLASS_ROW_CORRUPT"

_SELECT_CLASS = """
SELECT c.id, c.owner_id, c.code, c.name, c.school_year, c.grade_id, c.status,
       c.revision, c.created_at,
       (SELECT COUNT(*) FROM class_memberships m
         WHERE m.class_id = c.id AND m.left_on IS NULL) AS student_count
  FROM classes c
"""


def _invalid(message: str, *, fields: list[str] | None = None) -> AppError:
    return AppError(
        message,
        code="INVALID_REQUEST",
        status_code=422,
        details=error_details(fields=fields) if fields else None,
    )


def _not_found(class_id: str) -> AppError:
    return AppError(f"班级不存在：{class_id}。", code=CLASS_NOT_FOUND, status_code=404)


def _corrupt(message: str) -> AppError:
    return AppError(message, code=CLASS_ROW_CORRUPT, status_code=500)


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


def _class_conflict(exc: sqlite3.IntegrityError) -> AppError:
    message = str(exc)
    if "UNIQUE" in message.upper():
        return AppError(
            "同一学年的班级编码已存在，请换一个编码。",
            code=CLASS_CODE_CONFLICT,
            status_code=409,
        )
    return AppError(
        "班级数据不满足约束，请检查字段。", code="INVALID_REQUEST", status_code=422
    )


@dataclass(frozen=True)
class ClassRecord:
    """教学库 ``classes`` 一行（附活跃学生数）。``view()`` 给出对外 camelCase 视图。"""

    id: str
    owner_id: str
    code: str
    name: str
    school_year: str
    grade_id: str
    status: str
    revision: int
    created_at: str
    student_count: int = 0

    def view(self) -> ClassView:
        return ClassView(
            id=self.id,
            code=self.code,
            name=self.name,
            schoolYear=self.school_year,
            gradeId=self.grade_id,
            status=self.status,
            revision=self.revision,
            studentCount=self.student_count,
            createdAt=self.created_at,
        )


class ClassRepository:
    """班级表的唯一读写入口；调用方注入已迁移的 ``TeachingCatalog``。"""

    def __init__(self, catalog: TeachingCatalog) -> None:
        self._catalog = catalog

    # -------------------------------------------------------------- 写入

    def create(
        self,
        *,
        code: str,
        name: str,
        school_year: str,
        grade_id: str,
        owner_id: str = DEFAULT_OWNER_ID,
        class_id: str | None = None,
    ) -> ClassRecord:
        with self._catalog.write_transaction() as conn:
            return self.create_in(
                conn,
                code=code,
                name=name,
                school_year=school_year,
                grade_id=grade_id,
                owner_id=owner_id,
                class_id=class_id,
            )

    def create_in(
        self,
        conn: sqlite3.Connection,
        *,
        code: str,
        name: str,
        school_year: str,
        grade_id: str,
        owner_id: str = DEFAULT_OWNER_ID,
        class_id: str | None = None,
    ) -> ClassRecord:
        code = _require_text(code, field="code")
        name = _require_text(name, field="name")
        school_year = _require_text(school_year, field="schoolYear")
        grade_id = _require_text(grade_id, field="gradeId")
        owner_id = _require_text(owner_id, field="owner_id")
        new_id = class_id or uuid.uuid4().hex
        created_at = now_iso()
        try:
            conn.execute(
                "INSERT INTO classes "
                "(id, owner_id, code, name, school_year, grade_id, status, revision, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'active', 0, ?)",
                (new_id, owner_id, code, name, school_year, grade_id, created_at),
            )
        except sqlite3.IntegrityError as exc:
            raise _class_conflict(exc) from exc
        return ClassRecord(
            id=new_id,
            owner_id=owner_id,
            code=code,
            name=name,
            school_year=school_year,
            grade_id=grade_id,
            status="active",
            revision=0,
            created_at=created_at,
            student_count=0,
        )

    def update(
        self,
        class_id: str,
        *,
        expected_revision: int,
        name: str | None = None,
        school_year: str | None = None,
        grade_id: str | None = None,
    ) -> ClassRecord:
        with self._catalog.write_transaction() as conn:
            return self.update_in(
                conn,
                class_id,
                expected_revision=expected_revision,
                name=name,
                school_year=school_year,
                grade_id=grade_id,
            )

    def update_in(
        self,
        conn: sqlite3.Connection,
        class_id: str,
        *,
        expected_revision: int,
        name: str | None = None,
        school_year: str | None = None,
        grade_id: str | None = None,
    ) -> ClassRecord:
        current = self._require_row_in(conn, class_id)
        _check_revision(current["revision"], expected_revision)
        fields: dict[str, str] = {}
        if name is not None:
            fields["name"] = _require_text(name, field="name")
        if school_year is not None:
            fields["school_year"] = _require_text(school_year, field="schoolYear")
        if grade_id is not None:
            fields["grade_id"] = _require_text(grade_id, field="gradeId")
        if fields:
            assignments = ", ".join(f"{column} = ?" for column in fields)
            try:
                conn.execute(
                    f"UPDATE classes SET {assignments}, revision = revision + 1 WHERE id = ?",
                    (*fields.values(), class_id),
                )
            except sqlite3.IntegrityError as exc:
                raise _class_conflict(exc) from exc
        return self._require_record_in(conn, class_id)

    def set_status(
        self, class_id: str, *, expected_revision: int, status: ClassStatus
    ) -> ClassRecord:
        with self._catalog.write_transaction() as conn:
            return self.set_status_in(
                conn, class_id, expected_revision=expected_revision, status=status
            )

    def set_status_in(
        self,
        conn: sqlite3.Connection,
        class_id: str,
        *,
        expected_revision: int,
        status: ClassStatus,
    ) -> ClassRecord:
        if status not in CLASS_STATUSES:
            raise _invalid("status 只能是 active 或 archived。", fields=["status"])
        current = self._require_row_in(conn, class_id)
        _check_revision(current["revision"], expected_revision)
        conn.execute(
            "UPDATE classes SET status = ?, revision = revision + 1 WHERE id = ?",
            (status, class_id),
        )
        return self._require_record_in(conn, class_id)

    # -------------------------------------------------------------- 读取

    def get(self, class_id: str) -> ClassRecord:
        with self._catalog.read_connection() as conn:
            record = self.get_in(conn, class_id)
        if record is None:
            raise _not_found(class_id)
        return record

    def get_in(self, conn: sqlite3.Connection, class_id: str) -> ClassRecord | None:
        if not isinstance(class_id, str) or not class_id.strip():
            raise _invalid("class_id 必须是非空字符串。", fields=["classId"])
        row = conn.execute(
            f"{_SELECT_CLASS} WHERE c.id = ?", (class_id.strip(),)
        ).fetchone()
        return self._record(row) if row is not None else None

    def require_in(self, conn: sqlite3.Connection, class_id: str) -> ClassRecord:
        record = self.get_in(conn, class_id)
        if record is None:
            raise _not_found(class_id)
        return record

    def require(self, class_id: str) -> ClassRecord:
        return self.get(class_id)

    def list(
        self,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ClassRecord], int]:
        if status is not None and status not in CLASS_STATUSES:
            raise _invalid(
                "status 只能是 active 或 archived。", fields=["status"]
            )
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
        where = "WHERE c.status = ?" if status is not None else ""
        params: tuple[object, ...] = (status,) if status is not None else ()
        with self._catalog.read_connection() as conn:
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) AS n FROM classes c {where}", params
                ).fetchone()["n"]
            )
            rows = conn.execute(
                f"{_SELECT_CLASS} {where} "
                "ORDER BY c.created_at DESC, c.rowid DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [self._record(row) for row in rows], total

    # -------------------------------------------------------------- 内部

    def _require_row_in(self, conn: sqlite3.Connection, class_id: str) -> sqlite3.Row:
        if not isinstance(class_id, str) or not class_id.strip():
            raise _invalid("class_id 必须是非空字符串。", fields=["classId"])
        row = conn.execute(
            "SELECT revision FROM classes WHERE id = ?", (class_id.strip(),)
        ).fetchone()
        if row is None:
            raise _not_found(class_id)
        return row

    def _require_record_in(self, conn: sqlite3.Connection, class_id: str) -> ClassRecord:
        row = conn.execute(
            f"{_SELECT_CLASS} WHERE c.id = ?", (class_id.strip(),)
        ).fetchone()
        if row is None:  # pragma: no cover - 调用前已确认存在
            raise _not_found(class_id)
        return self._record(row)

    @staticmethod
    def _record(row: sqlite3.Row) -> ClassRecord:
        """行 → 记录；结构非法时报 ``CLASS_ROW_CORRUPT``，不静默放行。"""
        status = row["status"]
        if not isinstance(status, str) or status not in CLASS_STATUSES:
            raise _corrupt(f"教学库数据损坏：classes.status 结构不符（{status!r}）。")
        revision = row["revision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise _corrupt("教学库数据损坏：classes.revision 不是非负整数。")
        student_count = row["student_count"]
        if (
            not isinstance(student_count, int)
            or isinstance(student_count, bool)
            or student_count < 0
        ):
            raise _corrupt("教学库数据损坏：classes.student_count 不是非负整数。")
        for field in ("id", "owner_id", "code", "name", "school_year", "grade_id", "created_at"):
            value = row[field]
            if not isinstance(value, str) or not value:
                raise _corrupt(f"教学库数据损坏：classes.{field} 不是非空字符串。")
        return ClassRecord(
            id=row["id"],
            owner_id=row["owner_id"],
            code=row["code"],
            name=row["name"],
            school_year=row["school_year"],
            grade_id=row["grade_id"],
            status=status,
            revision=revision,
            created_at=row["created_at"],
            student_count=student_count,
        )


__all__ = [
    "CLASS_NOT_FOUND",
    "CLASS_ROW_CORRUPT",
    "CLASS_STATUSES",
    "ClassRecord",
    "ClassRepository",
    "DEFAULT_OWNER_ID",
    "MAX_LIST_LIMIT",
]
