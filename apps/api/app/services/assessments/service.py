"""施测服务（TEACHING-LOOP B2 / T30-b）：真实创建/读取/更新/补录人次。

门面由 ``build_assessment_service`` 装配（签名由 B2 任务卡 §8 冻结，CTRL 的
``app.main`` 用 ``app.state.confirmed_paper_reader`` 注入 reader）：reader 为 ``None`` 或
缺该端口时创建请求 503；端口显式报告自身未实现（501 ``PAPER_READER_UNAVAILABLE``）时
原样上报，两者都不伪造已确认原卷。

关键语义（与 ``app/contracts/assessments.py`` 的冻结契约一致）：

- **创建闸门**：只接受 ``ConfirmedPaperReader`` 放行的已确认修订（不存在/未确认/
  无非空计分叶子/零总分 → 422 ``ASSESSMENT_PAPER_INVALID``）；``heldOn`` 必须能
  ``date.fromisoformat`` 解析（字符串排序不代替日期校验）；``classIds`` 逐项存在且未归档；
  ``participants`` 非空；每个学生必须已建档（姓名/学号**从服务端读取后冻结**）。
- **归属核验**：按 ``heldOn`` 检查该生在该班的归属是否覆盖（``joined_on <= heldOn <=
  left_on``，``left_on`` 为空视为仍在班）；未覆盖时必须由教师显式确认本次班级
  （``classConfirmed`` + 依据），否则 422 ``PARTICIPANT_CLASS_UNCONFIRMED``（逐行定位）；
  **绝不自动修改归属历史**，也绝不自动选班。
- **人次**：``attemptNo`` 创建时缺省 1，补录时缺省为 ``该生既往 max(attempt_no) + 1``；
  ``(assessment, student, attempt)`` 冲突 → 409 ``PARTICIPANT_ATTEMPT_CONFLICT``；
  补考只新增行，**不 UPDATE/DELETE 既有参测记录**。
- **事务**：创建/班级范围/人次与 ``command_submissions`` 幂等结果在同一教学库写事务提交
  （``execute_command``）；任一行非法整批回滚。同 ``submissionId`` 同载荷重放返回原结果
  （``replayed=True``），不同载荷 409 ``SUBMISSION_CONFLICT``。
- **日期变更重核（B3/G0 · B2-RV08）**：``PATCH /assessments/{id}`` 的 ``heldOn`` 变化时，对
  **现有全部参测人次**重跑与创建时相同的覆盖判定（``joined_on <= heldOn <= left_on``）；
  存在未覆盖且 ``class_confirmed=0`` 的人次 → 422 ``PARTICIPANT_CLASS_UNCONFIRMED`` 定位拒绝
  （``issues[].row`` 是参测人次列表的 0 基下标），教师必须先重新确认本次班级。
  **不改** ``class_memberships``、**不改**姓名/学号快照；日期未变化时不重核（标题/类型编辑不受影响）。
- **重新确认路径（本批冻结形状，走 ``POST /assessments/{id}/participants``）**：请求里的参测行
  若 ``classConfirmed=true`` + 依据，且给了 ``attemptNo`` 且命中**既有** (studentId, classId,
  attemptNo) 人次 → 视为对该人次的重新确认：只更新 ``class_confirmed`` /
  ``class_confirmation_note`` / ``class_confirmation_at``，不新增行、不改人次、不改快照、
  不动归属历史；整批仍受 ``expectedRevision`` 守卫与 ``submissionId`` 幂等保护。
  未命中既有行时保持原语义（新增人次；``(student, attempt)`` 冲突仍 409）。
- **快照冻结**：参测姓名/学号写入 ``name_snapshot``/``student_no_snapshot``；之后学生改名/
  转班/退班不改变既有施测快照（本服务没有任何回写历史行的路径）。
- **错误定位**：``details.issues[].row`` 是 ``participants`` 数组的 **0 基下标**（与请求体
  一一对应）；``classIds`` 项用 ``field = "classIds[i]"`` 定位，``heldOn`` 用 ``field =
  "heldOn"``；消息只包含服务端读取的真实标识，不回显请求体。
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from app.contracts.assessments import (
    ASSESSMENT_HELD_ON_INVALID,
    ASSESSMENT_PAPER_FIXED,
    ASSESSMENT_PAPER_INVALID,
    ASSESSMENT_REVISION_STALE,
    CLASS_ARCHIVED,
    PARTICIPANT_ATTEMPT_CONFLICT,
    PARTICIPANT_CLASS_SCOPE,
    PARTICIPANT_CLASS_UNCONFIRMED,
    PARTICIPANT_EMPTY,
    PARTICIPANT_INVALID,
    AssessmentCreateRequest,
    AssessmentCreateResult,
    AssessmentDetailView,
    AssessmentList,
    AssessmentParticipantInput,
    AssessmentUpdateRequest,
    AssessmentView,
    ParticipantAddRequest,
    ParticipantMutationResult,
)
from app.contracts.papers import PAPER_NOT_FOUND
from app.contracts.roster import (
    ConfirmedPaperRevisionView,
    PAPER_READER_UNAVAILABLE,
)
from app.contracts.teaching_loop import ErrorIssue, error_details
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.assessments import (
    ASSESSMENT_STATES,
    DEFAULT_OWNER_ID,
    MAX_LIST_LIMIT,
    AssessmentRecord,
    AssessmentRepository,
    ParticipantRecord,
)
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.teaching.classes import ClassRepository
from app.repositories.teaching.students import (
    MembershipRecord,
    StudentRecord,
    StudentRepository,
)
from app.services.submissions.service import execute_command, make_command

#: 提交幂等身份里的操作名（同一 submissionId 在不同操作下互不干扰）
CREATE_OPERATION = "assessment.create"
PARTICIPANTS_OPERATION = "assessment.participants"

#: 找不到可用 reader 时的统一错误（装配缺失，可重试；不返回假成功）
_SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


# --------------------------------------------------------------------------- 小工具


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。", fields=[field])
    return value.strip()


def _optional_filter(value: object, *, field: str) -> str | None:
    """查询筛选参数：``None``/空白视为未提供，其余去空白后使用。"""
    if value is None:
        return None
    text = value.strip() if isinstance(value, str) else ""
    return text or None


def _page(offset: object, limit: object) -> tuple[int, int]:
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


def _invalid(message: str, *, fields: list[str] | None = None) -> AppError:
    return AppError(
        message,
        code="INVALID_REQUEST",
        status_code=422,
        details=error_details(fields=fields) if fields else None,
    )


def _issue(
    row: int | None,
    *,
    code: str,
    message: str,
    field: str | None = None,
) -> ErrorIssue:
    return ErrorIssue(row=row, column=field, field=field, code=code, message=message)


def _issues_error(
    message: str, *, code: str, status_code: int, issues: list[ErrorIssue]
) -> AppError:
    return AppError(
        message,
        code=code,
        status_code=status_code,
        details=error_details(issues=list(issues)),
    )


def _paper_invalid(message: str) -> AppError:
    return _issues_error(
        message,
        code=ASSESSMENT_PAPER_INVALID,
        status_code=422,
        issues=[
            _issue(
                None,
                code=ASSESSMENT_PAPER_INVALID,
                message="只能引用已确认且可计分的原卷修订。",
                field="paperRevisionId",
            )
        ],
    )


def _stale(current_revision: int) -> AppError:
    return AppError(
        "施测已被其他操作更新，请刷新后重试。",
        code=ASSESSMENT_REVISION_STALE,
        status_code=409,
        details=error_details(current_revision=current_revision),
    )


def _participant_locator(row: ParticipantRecord) -> str:
    """只拼接**服务端读取**的真实标识，用于定位拒绝的可读文案（不回显请求体）。"""
    return (
        f"{row.name_snapshot}（第 {row.attempt_no} 人次，班级 {row.class_id}，"
        f"参测记录 {row.participant_id}）"
    )


def _class_unconfirmed_error(
    *,
    held_on: date,
    uncovered: list[tuple[int, str]],
    cause: str,
) -> AppError:
    """归属未覆盖的定位拒绝（创建与日期变更共用同一错误形状）。

    ``issues[].row`` 是参测人次列表的 0 基下标；``field`` 指向该人次的班级归属；
    ``uncovered`` 的第二项是**服务端读取**的真实标识拼出的定位说明（不回显请求体）。
    文案要求教师**显式重新确认本次班级**，不提供任何自动改归属/自动选班的路径。
    """
    issues = [
        _issue(
            index,
            code=PARTICIPANT_CLASS_UNCONFIRMED,
            message=(
                f"{locator} 的班级归属未覆盖 {held_on.isoformat()}；"
                "请重新确认本次班级并填写依据"
                "（classConfirmed=true + classConfirmationNote）后重试。"
            ),
            field="classId",
        )
        for index, locator in uncovered
    ]
    return _issues_error(
        (
            f"{cause}：有 {len(uncovered)} 个参测人次的历史归属未覆盖 "
            f"{held_on.isoformat()}；请重新确认本次班级后重试（不会自动修改归属历史）。"
        ),
        code=PARTICIPANT_CLASS_UNCONFIRMED,
        status_code=422,
        issues=issues,
    )


def _reader_unavailable() -> AppError:
    return AppError(
        "已确认原卷读取端口未装配：无法创建施测，请检查启动日志与依赖。",
        code=_SERVICE_UNAVAILABLE,
        status_code=503,
        retryable=True,
    )


def _require_held_on(value: object) -> date:
    """``heldOn`` 必须是合法日历日期（不能用字符串排序代替解析）。"""
    text = value if isinstance(value, str) else ""
    try:
        return date.fromisoformat(text.strip())
    except (TypeError, ValueError) as exc:
        raise _issues_error(
            "heldOn 必须是合法的日历日期（YYYY-MM-DD）。",
            code=ASSESSMENT_HELD_ON_INVALID,
            status_code=422,
            issues=[
                _issue(
                    None,
                    code=ASSESSMENT_HELD_ON_INVALID,
                    message="heldOn 不是合法日历日期。",
                    field="heldOn",
                )
            ],
        ) from exc


def _stored_held_on(value: object) -> date:
    """读回库内 ``held_on``；结构非法时报 500，不静默按错误日期核验归属。"""
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise AppError(
            "教学库数据损坏：assessments.held_on 不是合法日期。",
            code="ASSESSMENT_ROW_CORRUPT",
            status_code=500,
        ) from exc


def _membership_covers(
    membership: MembershipRecord, *, class_id: str, held_on: date
) -> bool:
    """该归属是否覆盖 ``heldOn``；日期无法解析时按"未覆盖"处理（需人工确认）。"""
    if membership.class_id != class_id:
        return False
    try:
        joined = date.fromisoformat(membership.joined_on)
        left = date.fromisoformat(membership.left_on) if membership.left_on else None
    except (TypeError, ValueError):
        return False
    return joined <= held_on and (left is None or left >= held_on)


def _translate_integrity_error(exc: sqlite3.IntegrityError) -> AppError:
    """把 DB 约束/触发器拒绝转成统一错误信封（服务预检之外的兜底路径）。"""
    message = str(exc)
    upper = message.upper()
    if "PAPER_NOT_CONFIRMED" in upper:
        return _paper_invalid("只允许使用已确认的原卷修订；本次创建已整批回滚。")
    if "ASSESSMENT_PAPER_FIXED" in upper:
        return AppError(
            "施测创建后不能更换原卷修订。",
            code=ASSESSMENT_PAPER_FIXED,
            status_code=409,
        )
    if "ATTEMPT_NO" in upper and "ASSESSMENT_PARTICIPANTS" in upper:
        return _issues_error(
            "同一学生的该人次已存在；补考请新增下一人次。",
            code=PARTICIPANT_ATTEMPT_CONFLICT,
            status_code=409,
            issues=[
                _issue(
                    None,
                    code=PARTICIPANT_ATTEMPT_CONFLICT,
                    message="(施测, 学生, 人次) 不允许重复。",
                    field="attemptNo",
                )
            ],
        )
    if "FOREIGN KEY" in upper:
        return _issues_error(
            "参测行引用了不存在的班级或学生；本次创建已整批回滚。",
            code=PARTICIPANT_INVALID,
            status_code=422,
            issues=[
                _issue(
                    None,
                    code=PARTICIPANT_INVALID,
                    message="参测行的班级/学生必须已存在。",
                    field="participants",
                )
            ],
        )
    return AppError(
        "施测数据不满足约束，请检查字段。", code="INVALID_REQUEST", status_code=422
    )


# --------------------------------------------------------------------------- 中间结构


@dataclass(frozen=True)
class _ValidatedParticipant:
    """通过全部闸门、准备落库的一行参测人次（字段名与仓储 INSERT 关键字一致）。

    ``participant_id`` 非空表示这一行是**既有参测人次的重新确认**（B3/G0 · B2-RV08）：
    只更新确认列，不新增行、不改人次与快照。
    """

    student_id: str
    class_id: str
    attempt_no: int
    attendance: str
    name_snapshot: str
    student_no_snapshot: str | None
    class_confirmed: bool
    class_confirmation_note: str | None
    class_confirmation_at: str | None
    participant_id: str | None = None


# --------------------------------------------------------------------------- 服务


class AssessmentService:
    """施测用例入口；调用方注入已迁移 ``TeachingCatalog`` 与已确认原卷 reader。"""

    def __init__(
        self,
        catalog: TeachingCatalog,
        *,
        reader: Any | None,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> None:
        self._catalog = catalog
        self._reader = reader
        self._owner_id = owner_id
        self._assessments = AssessmentRepository(catalog)
        self._classes = ClassRepository(catalog)
        self._students = StudentRepository(catalog)

    # ---------------------------------------------------------------- 读取

    def list_assessments(
        self,
        *,
        subject_id: str | None = None,
        class_id: str | None = None,
        state: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> AssessmentList:
        offset, limit = _page(offset, limit)
        subject = _optional_filter(subject_id, field="subjectId")
        class_filter = _optional_filter(class_id, field="classId")
        state_filter = _optional_filter(state, field="state")
        if state_filter is not None and state_filter not in ASSESSMENT_STATES:
            raise _invalid(
                "state 只能是 open / closed / archived。", fields=["state"]
            )
        with self._catalog.read_connection() as conn:
            records, total = self._assessments.list_in(
                conn,
                subject_id=subject,
                class_id=class_filter,
                state=state_filter,
                offset=offset,
                limit=limit,
            )
        return AssessmentList(
            items=[record.view() for record in records],
            total=total,
            offset=offset,
            limit=limit,
        )

    def get_assessment(self, assessment_id: str) -> AssessmentDetailView:
        assessment_id = _text(assessment_id, field="assessmentId")
        with self._catalog.read_connection() as conn:
            record = self._assessments.require_in(conn, assessment_id)
            participants = self._assessments.list_participants_in(
                conn, record.assessment_id
            )
        return AssessmentDetailView(
            assessment=record.view(),
            participants=[item.view() for item in participants],
        )

    # ---------------------------------------------------------------- 创建

    def create_assessment(
        self, payload: AssessmentCreateRequest
    ) -> AssessmentCreateResult:
        paper = self._read_confirmed_paper(payload.paper_revision_id)
        held_on = _require_held_on(payload.held_on)
        command = make_command(
            operation=CREATE_OPERATION,
            submission_id=payload.submission_id,
            payload=payload.model_dump(by_alias=True),
            owner_id=self._owner_id,
        )
        try:
            outcome = execute_command(
                catalog=self._catalog,
                command=command,
                apply=lambda conn: self._apply_create(
                    conn, payload=payload, paper=paper, held_on=held_on
                ),
                table="command_submissions",
            )
        except sqlite3.IntegrityError as exc:
            raise _translate_integrity_error(exc) from exc
        result = AssessmentCreateResult.model_validate(outcome.result)
        return result.model_copy(update={"replayed": outcome.replayed})

    def _apply_create(
        self,
        conn: sqlite3.Connection,
        *,
        payload: AssessmentCreateRequest,
        paper: ConfirmedPaperRevisionView,
        held_on: date,
    ) -> dict[str, Any]:
        validated = self._validate_participants(
            conn,
            assessment_id=None,
            class_ids=list(payload.class_ids),
            participants=list(payload.participants),
            held_on=held_on,
            assign_next_attempt=False,
        )
        assessment_id = self._assessments.create_in(
            conn,
            paper_revision_id=paper.paper_revision_id,
            title=payload.title,
            assessment_type=payload.assessment_type,
            held_on=held_on.isoformat(),
            owner_id=self._owner_id,
        )
        for class_id in payload.class_ids:
            self._assessments.insert_class_scope_in(conn, assessment_id, class_id)
        for row in validated:
            self._assessments.insert_participant_in(
                conn, assessment_id=assessment_id, **asdict(row)
            )
        record = self._assessments.require_in(conn, assessment_id)
        participants = self._assessments.list_participants_in(conn, assessment_id)
        result = AssessmentCreateResult(
            assessment=record.view(),
            participants=[item.view() for item in participants],
            replayed=False,
        )
        return result.model_dump(by_alias=True)

    # ---------------------------------------------------------------- 更新

    def update_assessment(
        self, assessment_id: str, payload: AssessmentUpdateRequest
    ) -> AssessmentView:
        assessment_id = _text(assessment_id, field="assessmentId")
        fields: dict[str, object] = {}
        if payload.title is not None:
            fields["title"] = _text(payload.title, field="title")
        if payload.assessment_type is not None:
            fields["assessment_type"] = payload.assessment_type
        new_held_on: date | None = None
        if payload.held_on is not None:
            new_held_on = _require_held_on(payload.held_on)
            fields["held_on"] = new_held_on.isoformat()
        with self._catalog.write_transaction() as conn:
            record = self._assessments.require_in(conn, assessment_id)
            if record.revision != payload.expected_revision:
                raise _stale(record.revision)
            if new_held_on is not None and new_held_on.isoformat() != record.held_on:
                # B3/G0 · B2-RV08：日期变化必须重核现有全部参测人次，不能绕过班级归属确认。
                self._require_participants_covered_in(
                    conn, record=record, held_on=new_held_on
                )
            if fields:
                try:
                    self._assessments.update_fields_in(conn, assessment_id, fields)
                    self._assessments.bump_revision_in(conn, assessment_id)
                except sqlite3.IntegrityError as exc:
                    raise _translate_integrity_error(exc) from exc
                record = self._assessments.require_in(conn, assessment_id)
        return record.view()

    def _require_participants_covered_in(
        self, conn: sqlite3.Connection, *, record: AssessmentRecord, held_on: date
    ) -> None:
        """按**新施测日期**逐人次重核班级归属；未覆盖且未确认 → 422 定位拒绝（零写入）。

        与创建时同一覆盖判定（``_membership_covers``）；已显式确认的人次不需要重复确认。
        """
        participants = self._assessments.list_participants_in(conn, record.assessment_id)
        memberships: dict[str, list[MembershipRecord]] = {}
        uncovered: list[tuple[int, ParticipantRecord]] = []
        for index, row in enumerate(participants):
            if row.class_confirmed:
                continue
            if row.student_id not in memberships:
                memberships[row.student_id] = self._students.memberships_in(
                    conn, row.student_id
                )
            if not any(
                _membership_covers(item, class_id=row.class_id, held_on=held_on)
                for item in memberships[row.student_id]
            ):
                uncovered.append((index, _participant_locator(row)))
        if uncovered:
            raise _class_unconfirmed_error(
                held_on=held_on,
                uncovered=uncovered,
                cause="施测日期变更被拒绝（已整批回滚，日期未改变）",
            )

    # ---------------------------------------------------------------- 补录/补考

    def add_participants(
        self, assessment_id: str, payload: ParticipantAddRequest
    ) -> ParticipantMutationResult:
        assessment_id = _text(assessment_id, field="assessmentId")
        command = make_command(
            operation=PARTICIPANTS_OPERATION,
            submission_id=payload.submission_id,
            payload={
                "assessmentId": assessment_id,
                "expectedRevision": payload.expected_revision,
                "participants": [
                    item.model_dump(by_alias=True) for item in payload.participants
                ],
            },
            owner_id=self._owner_id,
        )
        try:
            outcome = execute_command(
                catalog=self._catalog,
                command=command,
                apply=lambda conn: self._apply_add(
                    conn,
                    assessment_id=assessment_id,
                    expected_revision=payload.expected_revision,
                    participants=list(payload.participants),
                ),
                table="command_submissions",
            )
        except sqlite3.IntegrityError as exc:
            raise _translate_integrity_error(exc) from exc
        result = ParticipantMutationResult.model_validate(outcome.result)
        return result.model_copy(update={"replayed": outcome.replayed})

    def _apply_add(
        self,
        conn: sqlite3.Connection,
        *,
        assessment_id: str,
        expected_revision: int,
        participants: list[AssessmentParticipantInput],
    ) -> dict[str, Any]:
        record = self._assessments.require_in(conn, assessment_id)
        if record.revision != expected_revision:
            raise _stale(record.revision)
        held_on = _stored_held_on(record.held_on)
        existing = self._assessments.list_participants_in(conn, record.assessment_id)
        # 命中既有 (student, class, attempt) 的显式确认行 = 重新确认本次班级（B3/G0 · B2-RV08）
        reconfirmable = {
            (row.student_id, row.class_id, row.attempt_no): row for row in existing
        }
        validated = self._validate_participants(
            conn,
            assessment_id=record.assessment_id,
            class_ids=list(record.class_ids),
            participants=participants,
            held_on=held_on,
            assign_next_attempt=True,
            reconfirmable=reconfirmable,
        )
        mutated_ids: list[str] = []
        for row in validated:
            if row.participant_id is not None:
                # 只写确认列：不新增行、不改人次/快照、不动归属历史
                self._confirm_participant_in(
                    conn,
                    assessment_id=record.assessment_id,
                    participant_id=row.participant_id,
                    note=row.class_confirmation_note,
                    confirmed_at=row.class_confirmation_at,
                )
                mutated_ids.append(row.participant_id)
                continue
            mutated_ids.append(
                self._assessments.insert_participant_in(
                    conn, assessment_id=record.assessment_id, **asdict(row)
                )
            )
        self._assessments.bump_revision_in(conn, record.assessment_id)
        updated = self._assessments.require_in(conn, record.assessment_id)
        mutated = [
            self._assessments.require_participant_in(conn, participant_id)
            for participant_id in mutated_ids
        ]
        result = ParticipantMutationResult(
            assessment=updated.view(),
            participants=[item.view() for item in mutated],
            replayed=False,
        )
        return result.model_dump(by_alias=True)

    def _confirm_participant_in(
        self,
        conn: sqlite3.Connection,
        *,
        assessment_id: str,
        participant_id: str,
        note: str | None,
        confirmed_at: str | None,
    ) -> None:
        """把既有参测人次标记为「教师显式确认本次班级」。

        列集合**固定三列**（``class_confirmed``/``class_confirmation_note``/
        ``class_confirmation_at``），姓名/学号快照、班级、人次与归属历史一律不动；
        DB 层 CHECK 兜底（``class_confirmed=1`` 必须有非空依据）。
        仓储（``repositories/teaching/assessments.py``）不在 B3/G0-C 的可写范围内，
        这一条最小 UPDATE 就地收在服务层，避免为了 RV08 扩大文件归属。
        """
        if not note or not note.strip():
            raise _invalid("重新确认本次班级必须填写依据。", fields=["classConfirmationNote"])
        cursor = conn.execute(
            "UPDATE assessment_participants "
            "SET class_confirmed = 1, class_confirmation_note = ?, class_confirmation_at = ? "
            "WHERE id = ? AND assessment_id = ?",
            (note.strip(), confirmed_at or now_iso(), participant_id, assessment_id),
        )
        if cursor.rowcount != 1:
            raise AppError(
                f"参测记录不存在或不属于本次施测：{participant_id}。",
                code=ASSESSMENT_NOT_FOUND,
                status_code=404,
            )

    # ---------------------------------------------------------------- 内部：原卷端口

    def _read_confirmed_paper(self, paper_revision_id: str) -> ConfirmedPaperRevisionView:
        """经 reader 端口读取已确认修订；缺装配 503，不可用/不存在按 422 拒绝。"""
        revision_id = _text(paper_revision_id, field="paperRevisionId")
        reader = self._reader
        if reader is None:
            raise _reader_unavailable()
        method = getattr(reader, "read_confirmed_paper_revision", None)
        if not callable(method):
            # T40 的 ``ConfirmedPaperReaderAdapter`` 以 ``read()`` 暴露同一语义；
            # 快照字段（paper_id/…/scored_leaf_count）与端口视图一一对应。
            method = getattr(reader, "read", None)
        if not callable(method):
            raise _reader_unavailable()
        try:
            raw = method(revision_id)
            view = ConfirmedPaperRevisionView(
                paperId=_reader_text(raw, "paper_id"),
                paperRevisionId=_reader_text(raw, "paper_revision_id"),
                title=_reader_text(raw, "title"),
                subjectId=_reader_text(raw, "subject_id"),
                totalScoreUnits=_reader_int(raw, "total_score_units"),
                scoredLeafCount=_reader_int(raw, "scored_leaf_count"),
            )
        except AppError as exc:
            if exc.code == PAPER_NOT_FOUND:
                raise _paper_invalid(
                    "原卷修订不存在或不可用于施测；请先在原卷工作台完成确认。"
                ) from exc
            if exc.code == PAPER_READER_UNAVAILABLE:
                # 端口自身的显式不可用（501）：原样上报，不伪造确认卷。
                raise
            raise
        except AttributeError as exc:
            raise _reader_unavailable() from exc
        if view.total_score_units <= 0 or view.scored_leaf_count < 1:
            raise _paper_invalid("已确认原卷必须至少有一个计分叶子（小题）且总分大于 0。")
        return view

    # ---------------------------------------------------------------- 内部：参测闸门

    def _validate_participants(
        self,
        conn: sqlite3.Connection,
        *,
        assessment_id: str | None,
        class_ids: list[str],
        participants: list[AssessmentParticipantInput],
        held_on: date,
        assign_next_attempt: bool,
        reconfirmable: dict[tuple[str, str, int], ParticipantRecord] | None = None,
    ) -> list[_ValidatedParticipant]:
        """同一写事务内逐行核验：存在性/范围/跨班重复/人次唯一/归属覆盖。

        任一行失败抛可定位的 ``AppError``（422/409），整个事务回滚，零写入。

        ``reconfirmable`` 非空时（补录/补考接口），命中其中 (student, class, attempt)
        且 ``classConfirmed=true`` 的行按**既有人的重新确认**处理：不做覆盖判定、
        不分配人次、不写快照（见 ``_confirm_participant_in``）。
        """
        if not participants:
            raise AppError(
                "participants 不能为空：不建立零人参测的施测。",
                code=PARTICIPANT_EMPTY,
                status_code=422,
            )

        ordered_classes: list[str] = []
        for index, raw_class_id in enumerate(class_ids):
            class_id = _text(raw_class_id, field="classId")
            if class_id in ordered_classes:
                raise _issues_error(
                    "classIds 不允许重复。",
                    code="INVALID_REQUEST",
                    status_code=422,
                    issues=[
                        _issue(
                            None,
                            code="INVALID_REQUEST",
                            message="classIds 中出现重复班级。",
                            field=f"classIds[{index}]",
                        )
                    ],
                )
            record = self._classes.get_in(conn, class_id)
            if record is None:
                raise _issues_error(
                    f"班级不存在：{class_id}。",
                    code=PARTICIPANT_INVALID,
                    status_code=422,
                    issues=[
                        _issue(
                            None,
                            code=PARTICIPANT_INVALID,
                            message="本次施测引用的班级不存在。",
                            field=f"classIds[{index}]",
                        )
                    ],
                )
            if record.status == "archived":
                raise _issues_error(
                    f"班级已归档，不能作为本次施测范围：{class_id}。",
                    code=CLASS_ARCHIVED,
                    status_code=422,
                    issues=[
                        _issue(
                            None,
                            code=CLASS_ARCHIVED,
                            message="已归档班级不能纳入施测范围；请先恢复。",
                            field=f"classIds[{index}]",
                        )
                    ],
                )
            ordered_classes.append(class_id)

        existing_attempts: set[tuple[str, int]] = set()
        max_attempts: dict[str, int] = {}
        if assessment_id is not None:
            for row in self._assessments.list_participants_in(conn, assessment_id):
                existing_attempts.add((row.student_id, row.attempt_no))
                max_attempts[row.student_id] = max(
                    max_attempts.get(row.student_id, 0), row.attempt_no
                )

        students: dict[str, StudentRecord | None] = {}
        memberships: dict[str, list[MembershipRecord]] = {}
        seen_student_class: dict[str, str] = {}
        seen_attempts: dict[tuple[str, int], int] = {}
        validated: list[_ValidatedParticipant] = []

        for index, item in enumerate(participants):
            student_id = _text(item.student_id, field="studentId")
            class_id = _text(item.class_id, field="classId")

            # 1) 学生必须已建档（姓名/学号随后从服务端读取冻结）
            if student_id not in students:
                students[student_id] = self._students.get_in(conn, student_id)
            student = students[student_id]
            if student is None:
                raise _issues_error(
                    f"第 {index + 1} 个参测行的学生不存在：{student_id}。",
                    code=PARTICIPANT_INVALID,
                    status_code=422,
                    issues=[
                        _issue(
                            index,
                            code=PARTICIPANT_INVALID,
                            message="studentId 不存在；请先建立学生档案。",
                            field="studentId",
                        )
                    ],
                )

            # 2) 行内班级必须在本次施测的 classIds 范围内
            if class_id not in ordered_classes:
                raise _issues_error(
                    f"第 {index + 1} 个参测行的班级不在本次施测范围内：{class_id}。",
                    code=PARTICIPANT_CLASS_SCOPE,
                    status_code=422,
                    issues=[
                        _issue(
                            index,
                            code=PARTICIPANT_CLASS_SCOPE,
                            message="该行 classId 不在本次 classIds 内。",
                            field="classId",
                        )
                    ],
                )

            # 3) 先行判定「重新确认既有参测人次」（B3/G0 · B2-RV08）：
            #    带 attemptNo 且命中既有 (student, class, attempt) 的显式确认行不改人次、
            #    不新增行，只更新确认列；未命中则保持原补录/补考语义（下同）。
            confirm_key = (
                (student_id, class_id, item.attempt_no)
                if item.attempt_no is not None
                else None
            )
            existing_row = (
                reconfirmable.get(confirm_key)
                if reconfirmable and confirm_key is not None
                else None
            )
            if item.class_confirmed and existing_row is not None:
                if not item.class_confirmation_note:
                    raise _issues_error(
                        f"第 {index + 1} 个参测行缺少重新确认依据。",
                        code=PARTICIPANT_CLASS_UNCONFIRMED,
                        status_code=422,
                        issues=[
                            _issue(
                                index,
                                code=PARTICIPANT_CLASS_UNCONFIRMED,
                                message="重新确认本次班级必须填写依据。",
                                field="classConfirmationNote",
                            )
                        ],
                    )
                validated.append(
                    _ValidatedParticipant(
                        student_id=existing_row.student_id,
                        class_id=existing_row.class_id,
                        attempt_no=existing_row.attempt_no,
                        attendance=existing_row.attendance,
                        name_snapshot=existing_row.name_snapshot,
                        student_no_snapshot=existing_row.student_no_snapshot,
                        class_confirmed=True,
                        class_confirmation_note=item.class_confirmation_note,
                        class_confirmation_at=now_iso(),
                        participant_id=existing_row.participant_id,
                    )
                )
                continue

            # 3a) 同一学生首次跨班重复必须人工选定（不自动选班、不重复计入）
            previous_class = seen_student_class.get(student_id)
            if previous_class is not None and previous_class != class_id:
                raise _issues_error(
                    f"第 {index + 1} 个参测行的学生在本次请求里出现在多个班级。",
                    code=PARTICIPANT_INVALID,
                    status_code=422,
                    issues=[
                        _issue(
                            index,
                            code=PARTICIPANT_INVALID,
                            message=(
                                "同一学生不能在本次施测中跨班重复；"
                                "请人工选定一个本次班级后重提。"
                            ),
                            field="classId",
                        )
                    ],
                )
            seen_student_class[student_id] = class_id

            # 4) 人次：创建缺省 1；补录缺省 = 该生既往 max(attempt_no) + 1
            if item.attempt_no is not None:
                attempt_no = item.attempt_no
            elif assign_next_attempt:
                attempt_no = max_attempts.get(student_id, 0) + 1
            else:
                attempt_no = 1
            if attempt_no > 99:
                raise _issues_error(
                    f"第 {index + 1} 个参测行的人次超过上限（99）。",
                    code=PARTICIPANT_ATTEMPT_CONFLICT,
                    status_code=409,
                    issues=[
                        _issue(
                            index,
                            code=PARTICIPANT_ATTEMPT_CONFLICT,
                            message="该学生的参测人次已达上限 99。",
                            field="attemptNo",
                        )
                    ],
                )
            key = (student_id, attempt_no)
            if key in existing_attempts or key in seen_attempts:
                raise _issues_error(
                    f"第 {index + 1} 个参测行的人次与既有记录冲突。",
                    code=PARTICIPANT_ATTEMPT_CONFLICT,
                    status_code=409,
                    issues=[
                        _issue(
                            index,
                            code=PARTICIPANT_ATTEMPT_CONFLICT,
                            message=(
                                f"该学生第 {attempt_no} 人次已存在；"
                                "补考请新增下一人次，不覆盖首次记录。"
                            ),
                            field="attemptNo",
                        )
                    ],
                )
            seen_attempts[key] = index
            max_attempts[student_id] = max(max_attempts.get(student_id, 0), attempt_no)

            # 5) 归属核验：未覆盖 heldOn 时必须显式确认本次班级（不改归属历史）
            if student_id not in memberships:
                memberships[student_id] = self._students.memberships_in(conn, student_id)
            covered = any(
                _membership_covers(item_membership, class_id=class_id, held_on=held_on)
                for item_membership in memberships[student_id]
            )
            confirmed = bool(item.class_confirmed)
            if not covered and not confirmed:
                raise _class_unconfirmed_error(
                    held_on=held_on,
                    uncovered=[
                        (
                            index,
                            f"第 {index + 1} 个参测行（学生 {student.name}，班级 {class_id}，"
                            f"第 {attempt_no} 人次）",
                        )
                    ],
                    cause="参测名单的历史归属未覆盖施测日期",
                )
            validated.append(
                _ValidatedParticipant(
                    student_id=student_id,
                    class_id=class_id,
                    attempt_no=attempt_no,
                    attendance=item.attendance,
                    name_snapshot=student.name,
                    student_no_snapshot=student.student_no,
                    class_confirmed=confirmed,
                    class_confirmation_note=(
                        item.class_confirmation_note if confirmed else None
                    ),
                    class_confirmation_at=now_iso() if confirmed else None,
                )
            )
        return validated


# --------------------------------------------------------------------------- reader 适配


def _reader_text(source: Any, attribute: str) -> str:
    value = getattr(source, attribute)
    if not isinstance(value, str) or not value:
        raise AttributeError(f"reader 返回的 {attribute} 不是非空字符串")
    return value


def _reader_int(source: Any, attribute: str) -> int:
    value = getattr(source, attribute)
    if not isinstance(value, int) or isinstance(value, bool):
        raise AttributeError(f"reader 返回的 {attribute} 不是整数")
    return value


# --------------------------------------------------------------------------- 工厂


def build_assessment_service(
    teaching_catalog: TeachingCatalog, *, reader: Any | None
) -> AssessmentService:
    """装配工厂（签名由 B2 任务卡 §8 冻结）。

    ``reader`` 是 T40 的 ``ConfirmedPaperReaderAdapter``（``None``/缺端口时创建请求
    返回 503，不返回模拟成功）。
    """
    return AssessmentService(teaching_catalog, reader=reader)


__all__ = [
    "AssessmentService",
    "CREATE_OPERATION",
    "PARTICIPANTS_OPERATION",
    "build_assessment_service",
]
