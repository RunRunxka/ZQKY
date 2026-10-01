"""成绩 v1 冻结契约（TEACHING-LOOP B3 / T60）。

与 ``docs/design/teaching-loop-v1/sql/teaching.sql`` 的 score_imports / score_import_rows /
score_revisions / student_item_scores 一致；设计未定义、由 B3 任务卡冻结补齐的部分（列映射、
单元格校正、承认范围、只读矩阵分页、修正请求）在这里给出唯一形状。

关键语义（不得改写）：

- 输入**只有教师提供的 XLSX/CSV 原始小题得分**：不调用大模型评分、不推断分数。
  服务端读表使用公式视图 + data_only 缓存视图（不计算公式）、保留**物理行列坐标**、
  超限明确报错、不静默截断。
- 分数一律 **Decimal ×100 整数单位**（``scoreUnits``）入出；对外文本用 ``scoreText``
  （最多两位小数）。0 = 显式记 0（recorded），空 = missing，缺考 = absent，免考 = exempt；
  四态不得互相顶替。recorded 必须有分数；非 recorded 必须没有分数。
- **全矩阵 = 冻结参测人次集合 × 冻结原卷的固定计分叶集合**。缺行、缺列一律显式落
  ``missing``，绝不静默补 0；确认时必须**逐类承认**（按班列举缺考人次 + missing 统计），
  且承认内容必须与预览完全一致，否则 422 ``SCORE_ACKNOWLEDGEMENT_MISMATCH``。
- 总分只在**该人次所有叶均 recorded** 时给出（``totalUnits``），否则为 null——
  有 missing/absent/exempt 的人次不展示总分，也不用 0 代替。
- 确认后成绩修订**不可变**（DB 触发器 + 服务）；修正 = 从不可变 base 复制**全矩阵**，
  用**修正当时的**参测快照生成新的完整版本，默认 base 必须等于当前 ``activeScoreRevisionId``；
  审计保留原值/新值/理由/坐标。修正请求本身即一次完整确认（带 submissionId 幂等）。
- 三个版本语义**互不替代**：
  - ``expectedImportRevision``：导入批次自己的乐观锁（草稿改动，如映射/行定位/单元格校正）；
  - ``expectedAssessmentRevision``：施测实体的乐观锁（参测人次等在被审阅期间变化）；
  - ``baseScoreRevisionId``：本导入所基于的**正式成绩版本**（首个版本为 null；修正时必须是当前
    active）。三者任一不符都明确 409，前端保留编辑。
- 名单/学号：学号按文本读取（前导零保留），**姓名不是主键**；同名同班等歧义行必须由教师
  人工指定 ``participantId``，服务端不猜。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.teaching_loop import AssetRef, ErrorIssue, ScoreStatus

# --------------------------------------------------------------------------- 枚举

ScoreImportState = Literal["uploaded", "reviewing", "confirmed", "failed", "cancelled"]
ScoreRevisionState = Literal["draft", "confirmed"]
SCORE_IMPORT_STATES: frozenset[str] = frozenset(
    {"uploaded", "reviewing", "confirmed", "failed", "cancelled"}
)

#: 分数文本：0–9999，最多两位小数（与 ``paper_items.max_score_units`` 的一百分之一一致）
SCORE_TEXT_PATTERN = r"^\d{1,4}(\.\d{1,2})?$"

# --------------------------------------------------------------------------- 错误码

SCORE_IMPORT_NOT_FOUND = "SCORE_IMPORT_NOT_FOUND"
SCORE_IMPORT_NOT_EDITABLE = "SCORE_IMPORT_NOT_EDITABLE"
SCORE_IMPORT_REVISION_CONFLICT = "SCORE_IMPORT_REVISION_CONFLICT"
SCORE_MAPPING_INVALID = "SCORE_MAPPING_INVALID"
SCORE_ROW_UNRESOLVED = "SCORE_ROW_UNRESOLVED"
SCORE_ROW_DUPLICATE_PARTICIPANT = "SCORE_ROW_DUPLICATE_PARTICIPANT"
SCORE_CELL_INVALID = "SCORE_CELL_INVALID"
SCORE_CELL_OVER_MAX = "SCORE_CELL_OVER_MAX"
SCORE_ASSESSMENT_REVISION_CONFLICT = "SCORE_ASSESSMENT_REVISION_CONFLICT"
SCORE_BASE_REVISION_CONFLICT = "SCORE_BASE_REVISION_CONFLICT"
SCORE_ACKNOWLEDGEMENT_MISMATCH = "SCORE_ACKNOWLEDGEMENT_MISMATCH"
SCORE_MATRIX_INCOMPLETE = "SCORE_MATRIX_INCOMPLETE"
SCORE_REVISION_NOT_FOUND = "SCORE_REVISION_NOT_FOUND"
SCORE_REVISION_IMMUTABLE = "SCORE_REVISION_IMMUTABLE"
SCORE_NO_BASE_REVISION = "SCORE_NO_BASE_REVISION"
SCORE_PARTICIPANT_UNKNOWN = "SCORE_PARTICIPANT_UNKNOWN"
SCORE_ITEM_UNKNOWN = "SCORE_ITEM_UNKNOWN"
SCORE_CORRECTION_INVALID = "SCORE_CORRECTION_INVALID"
ASSESSMENT_NOT_FOUND = "ASSESSMENT_NOT_FOUND"

# --------------------------------------------------------------------------- 基类


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------- 列映射


class ScoreItemColumn(_Strict):
    """一个计分叶 → 原表列的映射；``column`` 为列字母（如 ``"D"``）。"""

    item_id: str = Field(alias="itemId", min_length=1)
    column: str = Field(min_length=1, max_length=3)


class ScoreColumnMapping(_Strict):
    """成绩导入的列映射（固定到原卷计分叶）。

    - ``workSheet``：工作表名；``headerRow`` 仅用于原表表头定位展示（0 = 无表头）；
    - ``identityColumns``：原表中用于定位人次的原表列（至少一项）；
    - ``itemColumns``：**固定计分叶** 的列映射；未映射的计分叶在确认时按 missing 处理，
      未映射的叶必须被承认覆盖，映射到不存在的题目 id 一律 422。
    """

    work_sheet: str = Field(alias="workSheet", min_length=1, max_length=120)
    header_row: int = Field(default=0, alias="headerRow", ge=0)
    student_no_column: str | None = Field(
        default=None, alias="studentNoColumn", max_length=3
    )
    name_column: str | None = Field(default=None, alias="nameColumn", max_length=3)
    item_columns: list[ScoreItemColumn] = Field(
        default_factory=list, alias="itemColumns"
    )

    @model_validator(mode="after")
    def _check(self) -> "ScoreColumnMapping":
        if self.student_no_column is None and self.name_column is None:
            raise ValueError("identityColumns: 学号列与姓名列至少提供一项。")
        seen: set[str] = set()
        for entry in self.item_columns:
            if entry.item_id in seen:
                raise ValueError(f"itemColumns 重复题目：{entry.item_id}")
            seen.add(entry.item_id)
        return self


# --------------------------------------------------------------------------- 导入视图


class ScoreRawCellView(_Frozen):
    """原表单元格（两视图 + 物理坐标）；``text`` 为公式视图，``cachedText`` 为缓存值。"""

    row: int = Field(ge=1)
    column: str = Field(min_length=1, max_length=3)
    text: str = ""
    cached_text: str = Field(default="", alias="cachedText")
    is_formula: bool = Field(default=False, alias="isFormula")


class ScoreImportRowView(_Frozen):
    """原表一行的解析结果；``cells`` 覆盖映射到的计分叶（含原始文本与解析结果）。"""

    row_no: int = Field(alias="rowNo", ge=1)
    participant_id: str | None = Field(default=None, alias="participantId")
    participant_name: str | None = Field(default=None, alias="participantName")
    #: 歧义/未匹配行的可选取人次（含 姓名/学号/班级 摘要），供教师显式消歧
    candidates: list[str] = Field(default_factory=list)
    cells: list[ScoreRawCellView] = Field(default_factory=list)
    issues: list[ErrorIssue] = Field(default_factory=list)


class ScoreImportRowPatch(_Strict):
    """行定位/校正：``rowNo`` + 显式 ``participantId`` 或单元格校正。"""

    row_no: int = Field(alias="rowNo", ge=1)
    participant_id: str | None = Field(default=None, alias="participantId")
    cells: list["ScoreCellPatch"] = Field(default_factory=list)


class ScoreImportPatchRequest(_Strict):
    """一次生效的导入校对补丁；``mapping``/``rows``/``cells`` 至少提供一项。

    ``expectedRevision`` 是导入批次自己的乐观锁（CAS）：不符返回 409
    ``SCORE_IMPORT_REVISION_CONFLICT`` + ``currentRevision``，前端保留编辑。
    """

    expected_revision: int = Field(alias="expectedRevision", ge=0)
    mapping: ScoreColumnMapping | None = None
    rows: list[ScoreImportRowPatch] = Field(default_factory=list)


class ScoreCellPatch(_Strict):
    """单元格校正：以 **原表坐标** 定位（行号 + 列字母），与题目映射无关。"""

    row: int = Field(ge=1)
    column: str = Field(min_length=1, max_length=3)
    text: str = ""


class ScoreImportView(_Frozen):
    import_id: str = Field(alias="importId")
    assessment_id: str = Field(alias="assessmentId")
    assessment_title: str = Field(alias="assessmentTitle")
    state: ScoreImportState
    revision: int = Field(ge=0)
    preview_version: int = Field(alias="previewVersion", ge=0)
    file_asset: AssetRef = Field(alias="fileAsset")
    mapping: ScoreColumnMapping | None = None
    base_score_revision_id: str | None = Field(
        default=None, alias="baseScoreRevisionId"
    )
    warnings: list[str] = Field(default_factory=list)
    issues: list[ErrorIssue] = Field(default_factory=list)
    row_count: int = Field(alias="rowCount", ge=0)
    resolved_row_count: int = Field(alias="resolvedRowCount", ge=0)
    missing_cell_count: int = Field(alias="missingCellCount", ge=0)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ScoreImportRowList(_Frozen):
    items: list[ScoreImportRowView]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class ScoreImportSummary(_Frozen):
    import_id: str = Field(alias="importId")
    assessment_id: str = Field(alias="assessmentId")
    state: ScoreImportState
    revision: int = Field(ge=0)
    row_count: int = Field(alias="rowCount", ge=0)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ScoreImportList(_Frozen):
    items: list[ScoreImportSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


# --------------------------------------------------------------------------- 确认请求


class ScoreAbsenceAcknowledgement(_Strict):
    """逐班承认缺考人次：列举的是**本次确认覆盖的 absent 人次**。"""

    class_id: str = Field(alias="classId", min_length=1)
    participant_ids: list[str] = Field(alias="participantIds", min_length=1)


class ScoreMissingAcknowledgement(_Strict):
    """承认 missing 覆盖范围：必须与预览一致（人次集合 + 单元数）。"""

    participant_ids: list[str] = Field(alias="participantIds", min_length=1)
    cell_count: int = Field(alias="cellCount", ge=1)


class ScoreImportConfirmRequest(_Strict):
    expected_import_revision: int = Field(alias="expectedImportRevision", ge=0)
    expected_assessment_revision: int = Field(alias="expectedAssessmentRevision", ge=0)
    base_score_revision_id: str | None = Field(
        default=None, alias="baseScoreRevisionId"
    )
    preview_version: int = Field(alias="previewVersion", ge=0)
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    absences: list[ScoreAbsenceAcknowledgement] = Field(default_factory=list)
    missing: ScoreMissingAcknowledgement | None = None


class ScoreImportConfirmResult(_Frozen):
    import_id: str = Field(alias="importId")
    state: ScoreImportState
    revision_id: str = Field(alias="revisionId")
    assessment_revision: int = Field(alias="assessmentRevision")
    active_score_revision_id: str = Field(alias="activeScoreRevisionId")
    replayed: bool = False


# --------------------------------------------------------------------------- 成绩修订视图


class ScoreRevisionView(_Frozen):
    revision_id: str = Field(alias="revisionId")
    assessment_id: str = Field(alias="assessmentId")
    version: int = Field(ge=1)
    state: ScoreRevisionState
    source_import_id: str | None = Field(default=None, alias="sourceImportId")
    base_revision_id: str | None = Field(default=None, alias="baseRevisionId")
    participant_snapshot: list["ScoreParticipantSnapshot"] = Field(
        default_factory=list, alias="participantSnapshot"
    )
    #: 该修订记录的固定计分叶（固化自原卷修订；矩阵列集合）
    item_snapshot: list["ScoreItemSnapshot"] = Field(
        default_factory=list, alias="itemSnapshot"
    )
    confirmed_at: str | None = Field(default=None, alias="confirmedAt")
    created_at: str = Field(alias="createdAt")


class ScoreParticipantSnapshot(_Frozen):
    participant_id: str = Field(alias="participantId")
    student_id: str = Field(alias="studentId")
    student_no: str | None = Field(default=None, alias="studentNo")
    name: str = Field(min_length=1, max_length=120)
    class_id: str = Field(alias="classId")
    attempt_no: int = Field(alias="attemptNo", ge=1)
    attendance: Literal["present", "absent", "exempt"]


class ScoreItemSnapshot(_Frozen):
    item_id: str = Field(alias="itemId")
    item_path: str = Field(alias="itemPath")
    max_score_units: int = Field(alias="maxScoreUnits", ge=0)


class ScoreRevisionList(_Frozen):
    items: list[ScoreRevisionView]
    total: int = Field(ge=0)


# --------------------------------------------------------------------------- 只读矩阵


class ScoreCellValue(_Frozen):
    item_id: str = Field(alias="itemId")
    status: ScoreStatus
    score_units: int | None = Field(default=None, alias="scoreUnits", ge=0)


class ScoreMatrixParticipant(_Frozen):
    participant_id: str = Field(alias="participantId")
    student_id: str = Field(alias="studentId")
    student_no: str | None = Field(default=None, alias="studentNo")
    name: str = Field(min_length=1, max_length=120)
    class_id: str = Field(alias="classId")
    attempt_no: int = Field(alias="attemptNo", ge=1)
    attendance: Literal["present", "absent", "exempt"]
    #: 只在全员 recorded 时非空；否则 null（有 missing/absent/exempt 不展示总分）
    total_units: int | None = Field(default=None, alias="totalUnits", ge=0)
    total_max_units: int = Field(alias="totalMaxUnits", ge=0)


class ScoreMatrixRow(_Frozen):
    participant: ScoreMatrixParticipant
    #: 与 ``items`` 顺序一一对应
    cells: list[ScoreCellValue]


class ScoreMatrixPage(_Frozen):
    revision: ScoreRevisionView
    items: list[ScoreItemSnapshot]
    rows: list[ScoreMatrixRow]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    #: 该修订的 missing 覆盖（确认时承认过的范围；读视图同口径）
    missing_participant_ids: list[str] = Field(
        default_factory=list, alias="missingParticipantIds"
    )
    missing_cell_count: int = Field(alias="missingCellCount", ge=0)
    absent_class_ids: list[str] = Field(default_factory=list, alias="absentClassIds")


# --------------------------------------------------------------------------- 修正


class ScoreCorrectionEntry(_Strict):
    participant_id: str = Field(alias="participantId", min_length=1)
    item_id: str = Field(alias="itemId", min_length=1)
    status: ScoreStatus
    score_text: str | None = Field(default=None, alias="scoreText")

    @model_validator(mode="after")
    def _check(self) -> "ScoreCorrectionEntry":
        if self.status == "recorded" and self.score_text is None:
            raise ValueError("recorded 必须提供 scoreText。")
        if self.status != "recorded" and self.score_text is not None:
            raise ValueError("非 recorded 不得提供 scoreText。")
        return self


class ScoreRevisionCorrectRequest(_Strict):
    """修正 = 从不可变 base 复制全矩阵 + 当时快照 → 新完整版本（本身即一次完整确认）。"""

    base_score_revision_id: str = Field(alias="baseScoreRevisionId", min_length=1)
    expected_assessment_revision: int = Field(alias="expectedAssessmentRevision", ge=0)
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=200)
    corrections: list[ScoreCorrectionEntry] = Field(alias="corrections", min_length=1)


class ScoreRevisionCorrectResult(_Frozen):
    revision_id: str = Field(alias="revisionId")
    base_revision_id: str = Field(alias="baseRevisionId")
    version: int = Field(ge=1)
    assessment_revision: int = Field(alias="assessmentRevision")
    active_score_revision_id: str = Field(alias="activeScoreRevisionId")
    replayed: bool = False


ScoreImportRowPatch.model_rebuild()
ScoreRevisionView.model_rebuild()
