"""施测三表仓储（TEACHING-LOOP B2 / T30-b）：只做 SQL，不含业务闸门。

纪律与其余教学库仓储一致：读走 ``catalog.read_connection()``，写走
``catalog.write_transaction()``（``BEGIN IMMEDIATE``）；服务层在同一写事务内组合
``*_in(conn, ...)`` 方法。视图类型只来自 ``app.contracts.assessments``，班级/学生记录
复用 ``app/repositories/teaching/{classes,students}.py``（不复制第二份字段）。

- ``assessments.paper_revision_id`` 由 DB 触发器 ``assessment_confirmed_paper_insert``
  保证只能是已确认修订，``assessment_paper_fixed`` 拒绝换卷 UPDATE；本仓储不提供绕过；
- 参测行只允许 INSERT（补考 = 新增人次），没有任何 UPDATE/DELETE 路径；
- ``paper_title``/``subject_id`` 读的是 ``papers`` 的**当前**值（与原卷 reader 口径一致），
  参测姓名/学号才是创建时冻结的快照列；
- 行结构非法时报 ``ASSESSMENT_ROW_CORRUPT``，不静默放行。
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from app.contracts.assessments import (
    ASSESSMENT_NOT_FOUND,
    ASSESSMENT_TYPES,
    AssessmentParticipantView,
    AssessmentView,
)
from app.contracts.teaching_loop import error_details
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.catalog import TeachingCatalog

DEFAULT_OWNER_ID = "local"
MAX_LIST_LIMIT = 200
ASSESSMENT_STATES: frozenset[str] = frozenset({"open", "closed", "archived"})
ATTENDANCE_VALUES: frozenset[str] = frozenset({"present", "absent", "exempt"})

ASSESSMENT_ROW_CORRUPT = "ASSESSMENT_ROW_CORRUPT"

#: 允许被 ``update_fields_in`` 修改的列（其余一律拒绝：换卷/状态/修订号不在这里改）
UPDATABLE_COLUMNS: frozenset[str] = frozenset({"title", "assessment_type", "held_on"})

_SELECT_ASSESSMENT = """
SELECT a.id, a.owner_id, a.paper_revision_id, a.title, a.assessment_type, a.held_on,
       a.active_score_revision_id, a.state, a.revision, a.created_at,
       p.id AS paper_id, p.title AS paper_title, p.subject_id AS subject_id,
       (SELECT COUNT(*) FROM assessment_participants ap
         WHERE ap.assessment_id = a.id) AS participant_count
  FROM assessments a
  JOIN paper_revisions r ON r.id = a.paper_revision_id
  JOIN papers p ON p.id = r.paper_id
"""

_SELECT_PARTICIPANT = """
SELECT id, assessment_id, student_id, class_id, attempt_no, attendance,
       name_snapshot, student_no_snapshot, class_confirmed, class_confirmation_note,
       class_confirmation_at
  FROM assessment_participants
"""


def _invalid(message: str, *, fields: list[str] | None = None) -> AppError:
    return AppError(
        message,
        code="INVALID_REQUEST",
        status_code=422,
        details=error_details(fields=fields) if fields else None,
    )


def _not_found(assessment_id: str) -> AppError:
    return AppError(
        f"施测不存在：{assessment_id}。", code=ASSESSMENT_NOT_FOUND, status_code=404
    )


def _corrupt(message: str) -> AppError:
    return AppError(message, code=ASSESSMENT_ROW_CORRUPT, status_code=500)


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。", fields=[field])
    return value.strip()


@dataclass(frozen=True)
class AssessmentRecord:
    """``assessments`` 一行（附当前卷标题/学科、班级范围与参测人数）。"""

    assessment_id: str
    owner_id: str
    paper_revision_id: str
    title: str
    assessment_type: str
    held_on: str
    state: str
    revision: int
    created_at: str
    active_score_revision_id: str | None
    paper_id: str
    paper_title: str
    subject_id: str
    class_ids: tuple[str, ...] = ()
    participant_count: int = 0

    def view(self) -> AssessmentView:
        return AssessmentView(
            assessmentId=self.assessment_id,
            paperRevisionId=self.paper_revision_id,
            paperId=self.paper_id,
            paperTitle=self.paper_title,
            subjectId=self.subject_id,
            title=self.title,
            assessmentType=self.assessment_type,
            heldOn=self.held_on,
            activeScoreRevisionId=self.active_score_revision_id,
            state=self.state,
            revision=self.revision,
            classIds=list(self.class_ids),
            participantCount=self.participant_count,
            createdAt=self.created_at,
        )


@dataclass(frozen=True)
class ParticipantRecord:
    """``assessment_participants`` 一行；姓名/学号是创建时冻结的快照。"""

    participant_id: str
    assessment_id: str
    student_id: str
    class_id: str
    attempt_no: int
    attendance: str
    name_snapshot: str
    student_no_snapshot: str | None
    class_confirmed: bool
    class_confirmation_note: str | None
    class_confirmation_at: str | None

    def view(self) -> AssessmentParticipantView:
        return AssessmentParticipantView(
            participantId=self.participant_id,
            studentId=self.student_id,
            studentNoSnapshot=self.student_no_snapshot,
            nameSnapshot=self.name_snapshot,
            classId=self.class_id,
            attemptNo=self.attempt_no,
            attendance=self.attendance,
            classConfirmed=self.class_confirmed,
            classConfirmationNote=self.class_confirmation_note,
            classConfirmationAt=self.class_confirmation_at,
        )


class AssessmentRepository:
    """施测三表的唯一读写入口；调用方注入已迁移的 ``TeachingCatalog``。"""

    def __init__(self, catalog: TeachingCatalog) -> None:
        self._catalog = catalog

    # -------------------------------------------------------------- 写入
    # 以下 ``*_in`` 方法要求调用方已持有写事务；它们只做 SQL，不判业务闸门。

    def create_in(
        self,
        conn: sqlite3.Connection,
        *,
        paper_revision_id: str,
        title: str,
        assessment_type: str,
        held_on: str,
        owner_id: str = DEFAULT_OWNER_ID,
        assessment_id: str | None = None,
        created_at: str | None = None,
    ) -> str:
        paper_revision_id = _require_text(paper_revision_id, field="paperRevisionId")
        title = _require_text(title, field="title")
        if assessment_type not in ASSESSMENT_TYPES:
            raise _invalid(
                "assessmentType 只能是 exam / quiz / practice。",
                fields=["assessmentType"],
            )
        held_on = _require_text(held_on, field="heldOn")
        owner_id = _require_text(owner_id, field="owner_id")
        new_id = assessment_id or uuid.uuid4().hex
        conn.execute(
            "INSERT INTO assessments "
            "(id, owner_id, paper_revision_id, title, assessment_type, held_on, state, revision, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'open', 0, ?)",
            (
                new_id,
                owner_id,
                paper_revision_id,
                title,
                assessment_type,
                held_on,
                created_at or now_iso(),
            ),
        )
        return new_id

    def insert_class_scope_in(
        self, conn: sqlite3.Connection, assessment_id: str, class_id: str
    ) -> None:
        conn.execute(
            "INSERT INTO assessment_classes (assessment_id, class_id) VALUES (?, ?)",
            (
                _require_text(assessment_id, field="assessmentId"),
                _require_text(class_id, field="classId"),
            ),
        )

    def insert_participant_in(
        self,
        conn: sqlite3.Connection,
        *,
        assessment_id: str,
        student_id: str,
        class_id: str,
        attempt_no: int,
        attendance: str,
        name_snapshot: str,
        student_no_snapshot: str | None,
        class_confirmed: bool = False,
        class_confirmation_note: str | None = None,
        class_confirmation_at: str | None = None,
        participant_id: str | None = None,
    ) -> str:
        assessment_id = _require_text(assessment_id, field="assessmentId")
        student_id = _require_text(student_id, field="studentId")
        class_id = _require_text(class_id, field="classId")
        if (
            not isinstance(attempt_no, int)
            or isinstance(attempt_no, bool)
            or attempt_no < 1
        ):
            raise _invalid("attemptNo 必须是不小于 1 的整数。", fields=["attemptNo"])
        if attendance not in ATTENDANCE_VALUES:
            raise _invalid(
                "attendance 只能是 present / absent / exempt。", fields=["attendance"]
            )
        name_snapshot = _require_text(name_snapshot, field="nameSnapshot")
        if student_no_snapshot is not None:
            student_no_snapshot = _require_text(student_no_snapshot, field="studentNoSnapshot")
        if class_confirmed:
            if not class_confirmation_note or not class_confirmation_note.strip():
                raise _invalid(
                    "显式确认本次班级必须带依据。", fields=["classConfirmationNote"]
                )
            class_confirmation_note = class_confirmation_note.strip()
            class_confirmation_at = class_confirmation_at or now_iso()
        else:
            class_confirmation_note = None
            class_confirmation_at = None
        new_id = participant_id or uuid.uuid4().hex
        conn.execute(
            "INSERT INTO assessment_participants "
            "(id, assessment_id, student_id, class_id, attempt_no, attendance, "
            " name_snapshot, student_no_snapshot, class_confirmed, class_confirmation_note, "
            " class_confirmation_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                new_id,
                assessment_id,
                student_id,
                class_id,
                attempt_no,
                attendance,
                name_snapshot,
                student_no_snapshot,
                1 if class_confirmed else 0,
                class_confirmation_note,
                class_confirmation_at,
            ),
        )
        return new_id

    def update_fields_in(
        self,
        conn: sqlite3.Connection,
        assessment_id: str,
        fields: Mapping[str, object],
    ) -> None:
        """按白名单更新标题/类型/日期；不改 ``paper_revision_id``/``state``/``revision``。"""
        assessment_id = _require_text(assessment_id, field="assessmentId")
        unknown = set(fields) - UPDATABLE_COLUMNS
        if unknown:
            raise AppError(
                f"不允许修改的字段：{sorted(unknown)}。",
                code="INVALID_REQUEST",
                status_code=422,
            )
        assignments = ", ".join(f"{column} = ?" for column in fields)
        conn.execute(
            f"UPDATE assessments SET {assignments} WHERE id = ?",
            (*fields.values(), assessment_id),
        )

    def bump_revision_in(self, conn: sqlite3.Connection, assessment_id: str) -> int:
        assessment_id = _require_text(assessment_id, field="assessmentId")
        cursor = conn.execute(
            "UPDATE assessments SET revision = revision + 1 WHERE id = ?",
            (assessment_id,),
        )
        if cursor.rowcount != 1:
            raise _not_found(assessment_id)
        row = conn.execute(
            "SELECT revision FROM assessments WHERE id = ?", (assessment_id,)
        ).fetchone()
        assert row is not None  # pragma: no cover - 刚更新过
        revision = row["revision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise _corrupt("教学库数据损坏：assessments.revision 不是非负整数。")
        return revision

    # -------------------------------------------------------------- 读取

    def get(self, assessment_id: str) -> AssessmentRecord:
        with self._catalog.read_connection() as conn:
            record = self.get_in(conn, assessment_id)
        if record is None:
            raise _not_found(assessment_id)
        return record

    def get_in(
        self, conn: sqlite3.Connection, assessment_id: str
    ) -> AssessmentRecord | None:
        if not isinstance(assessment_id, str) or not assessment_id.strip():
            raise _invalid("assessment_id 必须是非空字符串。", fields=["assessmentId"])
        row = conn.execute(
            f"{_SELECT_ASSESSMENT} WHERE a.id = ?", (assessment_id.strip(),)
        ).fetchone()
        if row is None:
            return None
        return _assessment_record(row, self._class_ids_in(conn, row["id"]))

    def require_in(
        self, conn: sqlite3.Connection, assessment_id: str
    ) -> AssessmentRecord:
        record = self.get_in(conn, assessment_id)
        if record is None:
            raise _not_found(_safe_text(assessment_id))
        return record

    def list_in(
        self,
        conn: sqlite3.Connection,
        *,
        subject_id: str | None = None,
        class_id: str | None = None,
        state: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AssessmentRecord], int]:
        """筛选 + 分页；``classId`` 是"该班在本次施测范围内"（EXISTS 子查询）。"""
        if state is not None and state not in ASSESSMENT_STATES:
            raise _invalid(
                "state 只能是 open / closed / archived。", fields=["state"]
            )
        conditions: list[str] = []
        params: list[object] = []
        if subject_id is not None:
            conditions.append("p.subject_id = ?")
            params.append(subject_id)
        if class_id is not None:
            conditions.append(
                "EXISTS (SELECT 1 FROM assessment_classes ac "
                "WHERE ac.assessment_id = a.id AND ac.class_id = ?)"
            )
            params.append(class_id)
        if state is not None:
            conditions.append("a.state = ?")
            params.append(state)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        total = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM assessments a "
                "JOIN paper_revisions r ON r.id = a.paper_revision_id "
                "JOIN papers p ON p.id = r.paper_id "
                f"{where}",
                tuple(params),
            ).fetchone()["n"]
        )
        rows = conn.execute(
            f"{_SELECT_ASSESSMENT} {where} "
            "ORDER BY a.created_at DESC, a.rowid DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        ids = [row["id"] for row in rows]
        scope = self._class_ids_for_in(conn, ids)
        return [
            _assessment_record(row, scope.get(row["id"], ())) for row in rows
        ], total

    def list_participants_in(
        self, conn: sqlite3.Connection, assessment_id: str
    ) -> list[ParticipantRecord]:
        assessment_id = _require_text(assessment_id, field="assessmentId")
        rows = conn.execute(
            f"{_SELECT_PARTICIPANT} WHERE assessment_id = ? "
            "ORDER BY class_id ASC, attempt_no ASC, name_snapshot ASC, rowid ASC",
            (assessment_id,),
        ).fetchall()
        return [self._participant(row) for row in rows]

    def require_participant_in(
        self, conn: sqlite3.Connection, participant_id: str
    ) -> ParticipantRecord:
        participant_id = _require_text(participant_id, field="participantId")
        row = conn.execute(
            f"{_SELECT_PARTICIPANT} WHERE id = ?", (participant_id,)
        ).fetchone()
        if row is None:
            raise AppError(
                f"参测记录不存在：{participant_id}。",
                code=ASSESSMENT_NOT_FOUND,
                status_code=404,
            )
        return self._participant(row)

    # -------------------------------------------------------------- 内部

    def _class_ids_in(
        self, conn: sqlite3.Connection, assessment_id: str
    ) -> tuple[str, ...]:
        rows = conn.execute(
            "SELECT class_id FROM assessment_classes WHERE assessment_id = ? "
            "ORDER BY rowid ASC",
            (assessment_id,),
        ).fetchall()
        return tuple(row["class_id"] for row in rows)

    def _class_ids_for_in(
        self, conn: sqlite3.Connection, assessment_ids: list[str]
    ) -> dict[str, tuple[str, ...]]:
        if not assessment_ids:
            return {}
        placeholders = ", ".join("?" for _ in assessment_ids)
        rows = conn.execute(
            "SELECT assessment_id, class_id FROM assessment_classes "
            f"WHERE assessment_id IN ({placeholders}) ORDER BY rowid ASC",
            tuple(assessment_ids),
        ).fetchall()
        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(row["assessment_id"], []).append(row["class_id"])
        return {key: tuple(value) for key, value in grouped.items()}

    @staticmethod
    def _participant(row: sqlite3.Row) -> ParticipantRecord:
        attempt_no = row["attempt_no"]
        if (
            not isinstance(attempt_no, int)
            or isinstance(attempt_no, bool)
            or attempt_no < 1
        ):
            raise _corrupt("教学库数据损坏：assessment_participants.attempt_no 不是正整数。")
        attendance = row["attendance"]
        if not isinstance(attendance, str) or attendance not in ATTENDANCE_VALUES:
            raise _corrupt(
                "教学库数据损坏：assessment_participants.attendance 结构不符。"
            )
        # 行结构非法时如实报错，不静默放行
        return ParticipantRecord(
            participant_id=_row_text(row, "id"),
            assessment_id=_row_text(row, "assessment_id"),
            student_id=_row_text(row, "student_id"),
            class_id=_row_text(row, "class_id"),
            attempt_no=attempt_no,
            attendance=attendance,
            name_snapshot=_row_text(row, "name_snapshot"),
            student_no_snapshot=_row_optional_text(row, "student_no_snapshot"),
            class_confirmed=bool(row["class_confirmed"]),
            class_confirmation_note=_row_optional_text(row, "class_confirmation_note"),
            class_confirmation_at=_row_optional_text(row, "class_confirmation_at"),
        )

def _row_text(row: sqlite3.Row, field: str) -> str:
    value = row[field]
    if not isinstance(value, str) or not value:
        raise _corrupt(f"教学库数据损坏：字段 {field} 不是非空字符串。")
    return value


def _row_optional_text(row: sqlite3.Row, field: str) -> str | None:
    value = row[field]
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _corrupt(f"教学库数据损坏：字段 {field} 结构不符。")
    return value


def _safe_text(value: object) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else "<unknown>"


def _assessment_record(
    row: sqlite3.Row, class_ids: tuple[str, ...]
) -> AssessmentRecord:
    state = row["state"]
    if not isinstance(state, str) or state not in ASSESSMENT_STATES:
        raise _corrupt(f"教学库数据损坏：assessments.state 结构不符（{state!r}）。")
    assessment_type = row["assessment_type"]
    if not isinstance(assessment_type, str) or assessment_type not in ASSESSMENT_TYPES:
        raise _corrupt(
            f"教学库数据损坏：assessments.assessment_type 结构不符（{assessment_type!r}）。"
        )
    revision = row["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise _corrupt("教学库数据损坏：assessments.revision 不是非负整数。")
    count = row["participant_count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise _corrupt("教学库数据损坏：participant_count 不是非负整数。")
    if not class_ids:
        raise _corrupt(
            f"教学库数据损坏：施测 {row['id']!r} 没有班级范围（assessment_classes 为空）。"
        )
    return AssessmentRecord(
        assessment_id=_row_text(row, "id"),
        owner_id=_row_text(row, "owner_id"),
        paper_revision_id=_row_text(row, "paper_revision_id"),
        title=_row_text(row, "title"),
        assessment_type=assessment_type,
        held_on=_row_text(row, "held_on"),
        state=state,
        revision=revision,
        created_at=_row_text(row, "created_at"),
        active_score_revision_id=(
            row["active_score_revision_id"]
            if isinstance(row["active_score_revision_id"], str)
            else None
        ),
        paper_id=_row_text(row, "paper_id"),
        paper_title=_row_text(row, "paper_title"),
        subject_id=_row_text(row, "subject_id"),
        class_ids=class_ids,
        participant_count=count,
    )


__all__ = [
    "ASSESSMENT_ROW_CORRUPT",
    "ASSESSMENT_STATES",
    "ATTENDANCE_VALUES",
    "DEFAULT_OWNER_ID",
    "MAX_LIST_LIMIT",
    "UPDATABLE_COLUMNS",
    "AssessmentRecord",
    "AssessmentRepository",
    "ParticipantRecord",
]
