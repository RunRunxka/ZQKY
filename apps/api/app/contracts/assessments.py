"""施测 v1 冻结契约（TEACHING-LOOP B2 / T30-b）。

与 ``docs/design/teaching-loop-v1/sql/teaching.sql`` 的 assessments/assessment_classes/
assessment_participants 一致；B2 分期偏差（``active_score_revision_id`` 只允许空、无
``score_revisions`` 外键）与"本次班级显式确认"落库列见 ``core/migrations/teaching.py``。

关键语义（不得改写）：

- **只用已确认原卷的固定修订**（DB 触发器 ``assessment_confirmed_paper_insert`` + 服务）：
  draft/不存在/无计分叶子/零总分一律拒绝；施测**不能换卷**（``assessment_paper_fixed``）。
- 参测姓名/学号一律**从服务端 students 读取后冻结**，不信任客户端快照；客户端字段仅用于定位不一致。
- 默认要求**显式非空参测名单**（空 participants → 422，不建零人施测）；``attemptNo`` 首次为 1，
  补考新增人次，禁止覆盖首次记录；``(assessment, student, attempt)`` 唯一。
- 名单导入日 ≠ 真实入班日：历史归属未覆盖 ``heldOn`` 时返回可定位的
  ``PARTICIPANT_CLASS_UNCONFIRMED``，教师显式确认本次班级并写入依据后才冻结快照；
  **不自动修改归属历史**。
- 创建/班级范围/人次与幂等结果在教学库**同一事务**提交；一个非法参测行整批回滚。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.roster import Attendance, ParticipantSnapshot  # noqa: F401 - 单一来源复用

# --------------------------------------------------------------------------- 枚举

AssessmentType = Literal["exam", "quiz", "practice"]
AssessmentState = Literal["open", "closed", "archived"]
ASSESSMENT_TYPES: frozenset[str] = frozenset({"exam", "quiz", "practice"})

# --------------------------------------------------------------------------- 错误码

ASSESSMENT_NOT_FOUND = "ASSESSMENT_NOT_FOUND"
ASSESSMENT_PAPER_INVALID = "ASSESSMENT_PAPER_INVALID"
ASSESSMENT_PAPER_FIXED = "ASSESSMENT_PAPER_FIXED"
ASSESSMENT_HELD_ON_INVALID = "ASSESSMENT_HELD_ON_INVALID"
ASSESSMENT_REVISION_STALE = "ASSESSMENT_REVISION_STALE"
PARTICIPANT_EMPTY = "PARTICIPANT_EMPTY"
PARTICIPANT_INVALID = "PARTICIPANT_INVALID"
PARTICIPANT_CLASS_UNCONFIRMED = "PARTICIPANT_CLASS_UNCONFIRMED"
PARTICIPANT_ATTEMPT_CONFLICT = "PARTICIPANT_ATTEMPT_CONFLICT"
PARTICIPANT_CLASS_SCOPE = "PARTICIPANT_CLASS_SCOPE"
CLASS_ARCHIVED = "CLASS_ARCHIVED"

# --------------------------------------------------------------------------- 基类


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------- 输入


class AssessmentParticipantInput(_Strict):
    """一行参测人次；姓名/学号由服务端按 ``studentId`` 读取后冻结。

    - ``classConfirmed`` + ``classConfirmationNote``：历史归属未覆盖 ``heldOn`` 时的显式确认
      （服务端仍会校验 ``classId`` 在 ``classIds`` 范围内）；
    - ``attemptNo`` 缺省 1；补考在 ``participants`` 维护接口里显式给下一人次。
    """

    student_id: str = Field(alias="studentId", min_length=1)
    class_id: str = Field(alias="classId", min_length=1)
    attendance: Attendance = "present"
    attempt_no: int | None = Field(default=None, alias="attemptNo", ge=1, le=99)
    class_confirmed: bool = Field(default=False, alias="classConfirmed")
    class_confirmation_note: str | None = Field(
        default=None, alias="classConfirmationNote", max_length=500
    )

    @field_validator("class_confirmation_note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @model_validator(mode="after")
    def require_note_when_confirmed(self) -> "AssessmentParticipantInput":
        # 与数据库 CHECK 对称：显式确认必须带依据（教师为什么认定本次班级）
        if self.class_confirmed and not self.class_confirmation_note:
            raise ValueError("classConfirmed=true 时必须提供 classConfirmationNote")
        if not self.class_confirmed and self.class_confirmation_note:
            raise ValueError("提供 classConfirmationNote 时必须同时 classConfirmed=true")
        return self


class AssessmentCreateRequest(_Strict):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    paper_revision_id: str = Field(alias="paperRevisionId", min_length=1)
    title: str = Field(min_length=1, max_length=200)
    assessment_type: AssessmentType = Field(default="exam", alias="assessmentType")
    held_on: str = Field(alias="heldOn", min_length=10, max_length=10)
    class_ids: list[str] = Field(alias="classIds", min_length=1, max_length=50)
    participants: list[AssessmentParticipantInput] = Field(min_length=1, max_length=2000)

    @field_validator("class_ids")
    @classmethod
    def unique_classes(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("classIds 不允许重复")
        return value


class ParticipantAddRequest(_Strict):
    """补考/补录：新增人次（不修改既有记录），核施测编辑锁。"""

    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    participants: list[AssessmentParticipantInput] = Field(min_length=1, max_length=500)


class AssessmentUpdateRequest(_Strict):
    """标题/类型/日期/班级范围的版本守卫更新（不含参加记录）。"""

    expected_revision: int = Field(alias="expectedRevision", ge=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    assessment_type: AssessmentType | None = Field(default=None, alias="assessmentType")
    held_on: str | None = Field(default=None, alias="heldOn", min_length=10, max_length=10)


# --------------------------------------------------------------------------- 视图


class AssessmentParticipantView(_Frozen):
    participant_id: str = Field(alias="participantId")
    student_id: str = Field(alias="studentId")
    student_no_snapshot: str | None = Field(default=None, alias="studentNoSnapshot")
    name_snapshot: str = Field(alias="nameSnapshot")
    class_id: str = Field(alias="classId")
    attempt_no: int = Field(alias="attemptNo", ge=1)
    attendance: Attendance
    class_confirmed: bool = Field(alias="classConfirmed")
    class_confirmation_note: str | None = Field(default=None, alias="classConfirmationNote")
    class_confirmation_at: str | None = Field(default=None, alias="classConfirmationAt")


class AssessmentView(_Frozen):
    assessment_id: str = Field(alias="assessmentId")
    paper_revision_id: str = Field(alias="paperRevisionId")
    paper_id: str = Field(alias="paperId")
    paper_title: str = Field(alias="paperTitle")
    subject_id: str = Field(alias="subjectId")
    title: str
    assessment_type: AssessmentType = Field(alias="assessmentType")
    held_on: str = Field(alias="heldOn")
    #: 当前生效成绩修订（B3/T60 起可写；null = 尚无正式成绩版本）
    active_score_revision_id: str | None = Field(
        default=None, alias="activeScoreRevisionId"
    )
    state: AssessmentState = "open"
    revision: int = Field(ge=0)
    class_ids: list[str] = Field(default_factory=list, alias="classIds")
    participant_count: int = Field(default=0, alias="participantCount", ge=0)
    created_at: str = Field(alias="createdAt")


class AssessmentDetailView(_Frozen):
    assessment: AssessmentView
    participants: list[AssessmentParticipantView] = Field(default_factory=list)


class AssessmentList(_Frozen):
    items: list[AssessmentView]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class AssessmentCreateResult(_Frozen):
    assessment: AssessmentView
    participants: list[AssessmentParticipantView] = Field(default_factory=list)
    replayed: bool = False


class ParticipantMutationResult(_Frozen):
    assessment: AssessmentView
    participants: list[AssessmentParticipantView] = Field(default_factory=list)
    replayed: bool = False
