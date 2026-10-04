"""B4 v1 frozen wire contract. Fixed revisions, integer units, explicit attempts."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.contracts.assessments import AssessmentParticipantInput
from app.contracts.teaching_loop import JobView, RichContentV2, ScoreStatus, Observation


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class AnalysisCreateRequest(Frozen):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    score_revision_id: str = Field(alias="scoreRevisionId", min_length=1)
    selected_participant_ids: list[str] = Field(alias="selectedParticipantIds", min_length=1, max_length=2000)
    rule_code: Literal["any_loss_v1"] = Field(alias="ruleCode")


class FrozenParticipant(Frozen):
    participant_id: str = Field(alias="participantId")
    student_id: str = Field(alias="studentId")
    student_no: str | None = Field(alias="studentNo")
    name: str
    class_id: str = Field(alias="classId")
    class_name: None = Field(default=None, alias="className")
    class_name_note: Literal["该成绩未记录班名"] = Field(default="该成绩未记录班名", alias="classNameNote")
    attempt_no: int = Field(alias="attemptNo")
    attendance: Literal["present", "absent", "exempt"]


class FixedKnowledge(Frozen):
    knowledge_point_id: str = Field(alias="knowledgePointId")
    knowledge_revision_id: str = Field(alias="knowledgeRevisionId")
    name: str
    role: Literal["primary", "secondary"] = "primary"


class SelectionSnapshot(Frozen):
    selected_participant_ids: list[str] = Field(alias="selectedParticipantIds")
    unique_student_count: int = Field(alias="uniqueStudentCount")
    participant_count: int = Field(alias="participantCount")
    leaf_count: int = Field(alias="leafCount")
    state_counts: dict[ScoreStatus, int] = Field(alias="stateCounts")


class AnalysisReceipt(Frozen):
    run_id: str = Field(alias="runId")
    input_hash: str = Field(alias="inputHash")
    score_revision_id: str = Field(alias="scoreRevisionId")
    paper_revision_id: str = Field(alias="paperRevisionId")
    job: JobView
    replayed: bool
    reused: bool


class AnalysisRunView(Frozen):
    run_id: str = Field(alias="runId")
    assessment_id: str = Field(alias="assessmentId")
    subject_id: str = Field(alias="subjectId")
    score_revision_id: str = Field(alias="scoreRevisionId")
    paper_revision_id: str = Field(alias="paperRevisionId")
    paper_title: str = Field(alias="paperTitle")
    input_hash: str = Field(alias="inputHash")
    rule_code: Literal["any_loss_v1"] = Field(alias="ruleCode")
    selection_snapshot: SelectionSnapshot = Field(alias="selectionSnapshot")
    participants: list[FrozenParticipant]
    knowledge_points: list[FixedKnowledge] = Field(alias="knowledgePoints")
    job: JobView
    report_ready: bool = Field(alias="reportReady")
    created_at: str = Field(alias="createdAt")


class ClassReportRow(Frozen):
    class_id: str = Field(alias="classId")
    class_name: None = Field(default=None, alias="className")
    class_name_note: str = Field(default="该成绩未记录班名", alias="classNameNote")
    knowledge_point: FixedKnowledge = Field(alias="knowledgePoint")
    selected_count: int = Field(alias="selectedCount")
    valid_count: int = Field(alias="validCount")
    needs_count: int = Field(alias="needsCount")
    incomplete_count: int = Field(alias="incompleteCount")
    no_evidence_count: int = Field(alias="noEvidenceCount")
    full_credit_count: int = Field(alias="fullCreditCount")
    numerator: int
    denominator: int
    ratio: float | None


class StudentReportRow(Frozen):
    participant: FrozenParticipant
    knowledge_point: FixedKnowledge = Field(alias="knowledgePoint")
    observation: Observation
    information_incomplete: bool = Field(alias="informationIncomplete")
    expected_count: int = Field(alias="expectedCount")
    valid_count: int = Field(alias="validCount")
    state_counts: dict[ScoreStatus, int] = Field(alias="stateCounts")
    total_score_units: int | None = Field(alias="totalScoreUnits")
    total_max_score_units: int = Field(alias="totalMaxScoreUnits")


class EvidenceRow(Frozen):
    evidence_id: str = Field(alias="evidenceId")
    run_id: str = Field(alias="runId")
    score_revision_id: str = Field(alias="scoreRevisionId")
    paper_revision_id: str = Field(alias="paperRevisionId")
    participant: FrozenParticipant
    item_id: str = Field(alias="itemId")
    item_path: str = Field(alias="itemPath")
    max_score_units: int = Field(alias="maxScoreUnits")
    score_units: int | None = Field(alias="scoreUnits")
    status: ScoreStatus
    knowledge_points: list[FixedKnowledge] = Field(alias="knowledgePoints")
    content: dict[str, Any]
    shared_materials: list[dict[str, Any]] = Field(alias="sharedMaterials")
    source_locator: dict[str, Any] = Field(alias="sourceLocator")
    assets: list[dict[str, Any]]
    practice_revision_id: str | None = Field(default=None, alias="practiceRevisionId")
    practice_item_id: str | None = Field(default=None, alias="practiceItemId")
    association_note: str = Field(default="综合题失分关联，具体错因待教师确认", alias="associationNote")


class NoteRequest(Frozen):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    participant_id: str | None = Field(default=None, alias="participantId")
    knowledge_point_id: str | None = Field(default=None, alias="knowledgePointId")
    note: str = Field(min_length=1, max_length=2000)


class NoteView(Frozen):
    note_id: str = Field(alias="noteId")
    run_id: str = Field(alias="runId")
    participant_id: str | None = Field(alias="participantId")
    knowledge_point_id: str | None = Field(alias="knowledgePointId")
    note: str
    created_at: str = Field(alias="createdAt")
    replayed: bool = False


class Page[T](Frozen):
    items: list[T]
    total: int
    offset: int
    limit: int


class PracticeConstraints(Frozen):
    count: int = Field(ge=1, le=100)
    question_types: list[str] = Field(default_factory=list, alias="questionTypes")
    difficulties: list[str] = Field(default_factory=list)
    include_unknown_difficulty: bool = Field(default=False, alias="includeUnknownDifficulty")
    exclude_original: bool = Field(default=True, alias="excludeOriginal")
    deduplicate: bool = True


class PracticeCreateRequest(Frozen):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    analysis_run_id: str = Field(alias="analysisRunId")
    title: str = Field(min_length=1, max_length=200)
    target_knowledge_point_ids: list[str] = Field(alias="targetKnowledgePointIds", min_length=1)
    constraints: PracticeConstraints


class PracticeNode(Frozen):
    node_key: str = Field(alias="nodeKey", min_length=1)
    parent_node_key: str | None = Field(default=None, alias="parentNodeKey")
    question_no: str = Field(alias="questionNo", min_length=1)
    ordinal: int = Field(ge=1)
    is_scored: bool = Field(alias="isScored")
    max_score: str | None = Field(default=None, alias="maxScore")
    knowledge_point_ids: list[str] = Field(default_factory=list, alias="knowledgePointIds")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")


class PracticeStructure(Frozen):
    nodes: list[PracticeNode] = Field(min_length=1, max_length=100)


class PracticeDraftItem(Frozen):
    item_key: str = Field(alias="itemKey", min_length=1)
    question_revision_id: str = Field(alias="questionRevisionId")
    ordinal: int = Field(ge=1)
    item_structure: PracticeStructure = Field(alias="itemStructure")
    max_score: str = Field(alias="maxScore")
    selected_knowledge_point_ids: list[str] = Field(alias="selectedKnowledgePointIds", min_length=1)


class PracticeDraftPatch(Frozen):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    items: list[PracticeDraftItem] = Field(max_length=100)
    constraints: PracticeConstraints


class PracticeSuggestionsRequest(Frozen):
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    constraints: PracticeConstraints


class PracticeReviewRequest(Frozen):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    expected_revision: int = Field(alias="expectedRevision", ge=0)


class PracticeRevisionRequest(Frozen):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    source_revision_id: str = Field(alias="sourceRevisionId")


class PracticeSuggestion(Frozen):
    question_id: str = Field(alias="questionId")
    question_revision_id: str = Field(alias="questionRevisionId")
    content: RichContentV2
    knowledge_points: list[FixedKnowledge] = Field(alias="knowledgePoints")
    question_type: str | None = Field(alias="questionType")
    difficulty: str | None
    reason: str
    answer_state: str = Field(alias="answerState")


class PracticeSuggestions(Frozen):
    items: list[PracticeSuggestion]
    requested_count: int = Field(alias="requestedCount")
    selected_count: int = Field(alias="selectedCount")
    coverage: dict[str, int]
    gaps: list[str]


class PracticeItemView(Frozen):
    practice_item_id: str = Field(alias="practiceItemId")
    selection_id: str = Field(alias="selectionId")
    item_key: str = Field(alias="itemKey")
    node_key: str = Field(alias="nodeKey")
    parent_item_id: str | None = Field(alias="parentItemId")
    question_no: str = Field(alias="questionNo")
    ordinal: int
    is_scored: bool = Field(alias="isScored")
    max_score_units: int | None = Field(alias="maxScoreUnits")
    question_id: str = Field(alias="questionId")
    question_revision_id: str = Field(alias="questionRevisionId")
    content: RichContentV2
    knowledge_points: list[FixedKnowledge] = Field(alias="knowledgePoints")
    source_locator: dict[str, Any] = Field(alias="sourceLocator")
    reason: str
    answer_state: str = Field(alias="answerState")


class PracticeRevisionView(Frozen):
    practice_set_id: str = Field(alias="practiceSetId")
    practice_revision_id: str = Field(alias="practiceRevisionId")
    version: int
    state: Literal["draft", "reviewed"]
    title: str
    subject_id: str = Field(alias="subjectId")
    analysis_run_id: str = Field(alias="analysisRunId")
    target_knowledge_points: list[FixedKnowledge] = Field(alias="targetKnowledgePoints")
    constraints: PracticeConstraints
    input_hash: str = Field(alias="inputHash")
    total_score_units: int = Field(alias="totalScoreUnits")
    draft_items: list[PracticeDraftItem] = Field(alias="draftItems")
    items: list[PracticeItemView]
    reviewed_at: str | None = Field(alias="reviewedAt")
    created_at: str = Field(alias="createdAt")


class PracticeSetView(Frozen):
    practice_set_id: str = Field(alias="practiceSetId")
    title: str
    subject_id: str = Field(alias="subjectId")
    analysis_run_id: str = Field(alias="analysisRunId")
    revision: int
    current_revision: PracticeRevisionView = Field(alias="currentRevision")
    revisions: list[PracticeRevisionView]
    replayed: bool = False


class ExportRequest(Frozen):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    variant: Literal["student", "teacher", "score_template"]
    assessment_id: str | None = Field(default=None, alias="assessmentId")

    @model_validator(mode="after")
    def require_template_assessment(self) -> ExportRequest:
        if (self.variant == "score_template") != (self.assessment_id is not None):
            raise ValueError("score_template 必须给本练习施测 assessmentId；DOCX 不给 assessmentId")
        return self


class ExportReceipt(Frozen):
    export_id: str = Field(alias="exportId")
    practice_revision_id: str = Field(alias="practiceRevisionId")
    input_hash: str = Field(alias="inputHash")
    job: JobView
    replayed: bool
    reused: bool


class ExportArtifact(Frozen):
    artifact_id: str = Field(alias="artifactId")
    export_id: str = Field(alias="exportId")
    practice_revision_id: str = Field(alias="practiceRevisionId")
    variant: Literal["student", "teacher", "score_template"]
    assessment_id: str | None = Field(alias="assessmentId")
    file_asset_id: str = Field(alias="fileAssetId")
    filename: str
    media_type: str = Field(alias="mediaType")
    sha256: str
    byte_size: int = Field(alias="byteSize")
    download_url: str = Field(alias="downloadUrl")
    created_at: str = Field(alias="createdAt")


class PracticeConversionRequest(Frozen):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=200)
    held_on: str = Field(alias="heldOn", min_length=10, max_length=10)
    class_ids: list[str] = Field(alias="classIds", min_length=1, max_length=50)
    participants: list[AssessmentParticipantInput] = Field(min_length=1, max_length=2000)


class PracticeConversionReceipt(Frozen):
    conversion_id: str = Field(alias="conversionId")
    paper_id: str = Field(alias="paperId")
    paper_revision_id: str = Field(alias="paperRevisionId")
    assessment_id: str = Field(alias="assessmentId")
    practice_revision_id: str = Field(alias="practiceRevisionId")
    replayed: bool
