"""班级 / 学生 / 名单导入 / 施测 冻结契约（TEACHING-LOOP B1 / T30-a）。

与 ``docs/design/teaching-loop-v1/sql/teaching.sql``（classes/students/class_memberships/
assessments/assessment_classes/assessment_participants）与 ``04`` F03/F06 一致。

关键语义（不得改写）：

- **学号按文本保存并保留前导零**（``0012``）；姓名不是主键，同名只提示不合并。
- 无学号、同名、姓名不符、重复行进入**人工身份核对**；确认时必须全部解决
  （``identityMatches`` 对每行给出 link/create/ignore，link 必须给 studentId）。
- 名单未出现的学生**不自动退班**；转班 = 旧归属置 ``leftOn`` 后新增归属，旧归属与旧参测记录不变。
- 非法数据整批回滚；409/422 用 ``details``（currentRevision / issues）定位到行。
- **施测三表不在本批迁移**（真实创建依赖 T40 已确认原卷，属 T30-b）；本批只冻结
  创建请求、参测人次、身份/班级/出勤快照与"读取已确认原卷修订"的端口契约。
  未实现的施测接口保持 501 ``FEATURE_NOT_IMPLEMENTED``，不返回模拟成功。
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.teaching_loop import AssetRef, ErrorIssue

# --------------------------------------------------------------------------- 枚举

ClassStatus = Literal["active", "archived"]
StudentStatus = Literal["active", "archived"]
RosterImportState = Literal["uploaded", "reviewing", "confirmed", "failed", "cancelled"]
ROSTER_IMPORT_STATES: frozenset[str] = frozenset(
    {"uploaded", "reviewing", "confirmed", "failed", "cancelled"}
)
RosterDecision = Literal["link", "create", "ignore"]
ROSTER_DECISIONS: frozenset[str] = frozenset({"link", "create", "ignore"})
#: 预览行的自动建议（不构成写入决定）
RosterRowSuggestion = Literal["link", "create", "name_mismatch", "no_student_no", "duplicate", "conflict"]
Attendance = Literal["present", "absent", "exempt"]
ATTENDANCE_VALUES: frozenset[str] = frozenset({"present", "absent", "exempt"})
AssessmentType = Literal["exam", "quiz", "practice"]

#: 名单表字段（表头/映射只允许这些）
ROSTER_IMPORT_FIELDS: tuple[str, ...] = ("studentNo", "name")

# --------------------------------------------------------------------------- 错误码

CLASS_CODE_CONFLICT = "CLASS_CODE_CONFLICT"
CLASS_ARCHIVED = "CLASS_ARCHIVED"
STUDENT_NO_CONFLICT = "STUDENT_NO_CONFLICT"
ROSTER_ROW_INVALID = "ROSTER_ROW_INVALID"
ROSTER_IDENTITY_UNRESOLVED = "ROSTER_IDENTITY_UNRESOLVED"
ROSTER_IMPORT_BLOCKING_ISSUES = "ROSTER_IMPORT_BLOCKING_ISSUES"
ROSTER_IMPORT_CONFIRMED = "ROSTER_IMPORT_CONFIRMED"
ROSTER_MAPPING_INVALID = "ROSTER_MAPPING_INVALID"
PAPER_NOT_CONFIRMED = "PAPER_NOT_CONFIRMED"
PAPER_READER_UNAVAILABLE = "PAPER_READER_UNAVAILABLE"

# --------------------------------------------------------------------------- 基类


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------- 班级


class ClassView(_Frozen):
    id: str
    code: str
    name: str
    school_year: str = Field(alias="schoolYear")
    grade_id: str = Field(alias="gradeId")
    status: ClassStatus = "active"
    revision: int = Field(ge=0)
    student_count: int = Field(default=0, alias="studentCount", ge=0)
    created_at: str = Field(alias="createdAt")


class ClassList(_Frozen):
    items: list[ClassView]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class ClassCreateRequest(_Strict):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    school_year: str = Field(alias="schoolYear", min_length=4, max_length=16)
    grade_id: str = Field(alias="gradeId", min_length=1, max_length=64)


class ClassUpdateRequest(_Strict):
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    school_year: str | None = Field(default=None, alias="schoolYear", min_length=4, max_length=16)
    grade_id: str | None = Field(default=None, alias="gradeId", min_length=1, max_length=64)


class ClassRevisionRequest(_Strict):
    expected_revision: int = Field(alias="expectedRevision", ge=0)


# --------------------------------------------------------------------------- 学生与归属


class StudentMembershipView(_Frozen):
    membership_id: str = Field(alias="membershipId")
    class_id: str = Field(alias="classId")
    class_name: str = Field(alias="className")
    joined_on: str = Field(alias="joinedOn")
    left_on: str | None = Field(default=None, alias="leftOn")


class StudentView(_Frozen):
    id: str
    student_no: str | None = Field(default=None, alias="studentNo")
    name: str
    status: StudentStatus = "active"
    revision: int = Field(ge=0)
    memberships: list[StudentMembershipView] = Field(default_factory=list)
    created_at: str = Field(alias="createdAt")


class StudentList(_Frozen):
    items: list[StudentView]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class StudentCreateRequest(_Strict):
    """无学号时必须显式建档（studentNo 留空）；姓名允许重名。"""

    name: str = Field(min_length=1, max_length=120)
    student_no: str | None = Field(default=None, alias="studentNo", max_length=64)
    class_id: str | None = Field(default=None, alias="classId")
    joined_on: str | None = Field(default=None, alias="joinedOn", max_length=10)

    @field_validator("student_no")
    @classmethod
    def normalize_student_no(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class StudentUpdateRequest(_Strict):
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    student_no: str | None = Field(default=None, alias="studentNo", max_length=64)


class MembershipTransferRequest(_Strict):
    """转班：旧归属置 leftOn，新班新增归属；旧参测记录不变。"""

    expected_student_revision: int = Field(alias="expectedStudentRevision", ge=0)
    from_class_id: str = Field(alias="fromClassId", min_length=1)
    to_class_id: str = Field(alias="toClassId", min_length=1)
    moved_on: str = Field(alias="movedOn", min_length=10, max_length=10)


# --------------------------------------------------------------------------- 名单导入


class RosterImportRowView(_Frozen):
    row_no: int = Field(alias="rowNo", ge=1)
    name: str = ""
    student_no: str | None = Field(default=None, alias="studentNo")
    matched_student_id: str | None = Field(default=None, alias="matchedStudentId")
    matched_student_name: str | None = Field(default=None, alias="matchedStudentName")
    suggestion: RosterRowSuggestion | None = None
    decision: RosterDecision | None = None
    issues: list[ErrorIssue] = Field(default_factory=list)


class RosterImportView(_Frozen):
    import_id: str = Field(alias="importId")
    class_id: str = Field(alias="classId")
    class_name: str = Field(alias="className")
    state: RosterImportState
    revision: int = Field(ge=0)
    file_asset: AssetRef = Field(alias="fileAsset")
    headers: list[str] = Field(default_factory=list)
    mapping: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    issues: list[ErrorIssue] = Field(default_factory=list)
    rows: list[RosterImportRowView] = Field(default_factory=list)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class RosterImportSummary(_Frozen):
    import_id: str = Field(alias="importId")
    class_id: str = Field(alias="classId")
    state: RosterImportState
    revision: int = Field(ge=0)
    row_count: int = Field(alias="rowCount", ge=0)
    blocking_issue_count: int = Field(alias="blockingIssueCount", ge=0)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class RosterImportList(_Frozen):
    items: list[RosterImportSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class RosterImportRowPatch(_Strict):
    row_no: int = Field(alias="rowNo", ge=1)
    decision: RosterDecision
    #: link 必填（指定既有学生）；create 不得填
    student_id: str | None = Field(default=None, alias="studentId")


class RosterImportPatchRequest(_Strict):
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    mapping: dict[str, str] | None = None
    rows: list[RosterImportRowPatch] | None = None


class RosterIdentityMatch(_Strict):
    row_no: int = Field(alias="rowNo", ge=1)
    action: RosterDecision
    student_id: str | None = Field(default=None, alias="studentId")


class RosterImportConfirmRequest(_Strict):
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    identity_matches: list[RosterIdentityMatch] = Field(
        default_factory=list, alias="identityMatches"
    )


class RosterAppliedRow(_Frozen):
    row_no: int = Field(alias="rowNo", ge=1)
    student_id: str = Field(alias="studentId")
    membership_id: str | None = Field(default=None, alias="membershipId")
    created_student: bool = Field(alias="createdStudent")
    created_membership: bool = Field(alias="createdMembership")


class RosterImportConfirmResult(_Frozen):
    import_id: str = Field(alias="importId")
    state: RosterImportState
    applied: list[RosterAppliedRow] = Field(default_factory=list)
    ignored: list[int] = Field(default_factory=list)
    replayed: bool = False


# --------------------------------------------------------------------------- 施测契约（真实创建 = T30-b）


class ParticipantSnapshot(_Frozen):
    """参测人次快照：身份/班级/出勤冻结；补考 = 新增人次，不覆盖首次记录。"""

    student_id: str = Field(alias="studentId", min_length=1)
    student_no: str | None = Field(default=None, alias="studentNo")
    name: str = Field(min_length=1, max_length=120)
    class_id: str = Field(alias="classId", min_length=1)
    attempt_no: int = Field(default=1, alias="attemptNo", ge=1)
    attendance: Attendance = "present"


class AssessmentCreateRequest(_Strict):
    """施测创建请求（T30-b 实现；本批只冻结形状）。"""

    paper_revision_id: str = Field(alias="paperRevisionId", min_length=1)
    title: str = Field(min_length=1, max_length=200)
    assessment_type: AssessmentType = Field(default="exam", alias="assessmentType")
    held_on: str = Field(alias="heldOn", min_length=10, max_length=10)
    class_ids: list[str] = Field(alias="classIds", min_length=1, max_length=50)
    participants: list[ParticipantSnapshot] = Field(default_factory=list)


class ConfirmedPaperRevisionView(_Frozen):
    """端口返回：已确认原卷修订（只有 state=confirmed 才能被施测引用）。"""

    paper_id: str = Field(alias="paperId")
    paper_revision_id: str = Field(alias="paperRevisionId")
    title: str
    subject_id: str = Field(alias="subjectId")
    total_score_units: int = Field(alias="totalScoreUnits", ge=0)
    scored_leaf_count: int = Field(alias="scoredLeafCount", ge=0)


class ConfirmedPaperReader(Protocol):
    """读取已确认原卷修订的端口（T30-b 由 T40 的原卷仓储实现）。

    B1 未实现该端口的真实后端：调用方必须得到明确的不可用错误
    （``PAPER_READER_UNAVAILABLE`` / 501），而不是空对象或模拟成功。
    """

    def read_confirmed_paper_revision(
        self, paper_revision_id: str
    ) -> ConfirmedPaperRevisionView: ...


class UnavailablePaperReader:
    """B1 装配的显式占位：任何调用都失败（不伪造原卷）。"""

    def read_confirmed_paper_revision(self, paper_revision_id: str) -> ConfirmedPaperRevisionView:
        from app.core.exceptions import AppError

        raise AppError(
            "已确认原卷读取端口尚未实现（依赖 T40 原卷业务）。",
            code=PAPER_READER_UNAVAILABLE,
            status_code=501,
        )
