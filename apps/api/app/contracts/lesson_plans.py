"""B5 v1: v1 document content inside an explicit v2 server envelope.

Limits count UTF-16 code units, matching the existing browser validator. A
legacy-valid document above the public 2 MiB request ceiling is rejected visibly;
the original local bytes are retained. Local edit revisions are never server CAS.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.b4 import FixedKnowledge
from app.contracts.teaching_loop import JobView
from app.schemas.rag_v2 import EvidenceRef, ScopeSnapshot, TextbookEvidence
from app.schemas.textbook import TextbookSelection

MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_SAFE_INTEGER = 9007199254740991
AllowedField = Literal["coreCompetencies", "keyPoints", "teachingDesign", "process", "exercises"]
ALLOWED_FIELDS = ("coreCompetencies", "keyPoints", "teachingDesign", "process", "exercises")
LessonSource = Literal["manual", "rule", "import_local", "ai_applied"]
LessonType = Literal["new", "review", "exercise", "experiment", "other"]


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le", errors="surrogatepass")) // 2


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, populate_by_name=True)


class ProcessItem(Frozen):
    id: str = Field(max_length=100000)
    stage: str = Field(max_length=120)
    design: str = Field(max_length=100000)
    secondary: str = Field(max_length=100000)

    @field_validator("id", "stage", "design", "secondary")
    @classmethod
    def lengths(cls, value: str, info):
        limit = 120 if info.field_name == "stage" else 100000
        if utf16_length(value) > limit:
            raise ValueError(f"{info.field_name} exceeds {limit} UTF-16 code units")
        value.encode("utf-8")  # Invalid Unicode is a visible validation error.
        return value


class LessonPlanData(Frozen):
    title: str = Field(max_length=80)
    total_lessons: str = Field(alias="totalLessons", max_length=100000)
    current_lesson_no: str = Field(alias="currentLessonNo", max_length=100000)
    lesson_types: list[LessonType] = Field(alias="lessonTypes", max_length=100000)
    other_type_text: str = Field(alias="otherTypeText", max_length=80)
    core_competencies: str = Field(alias="coreCompetencies", max_length=100000)
    key_points: str = Field(alias="keyPoints", max_length=100000)
    teaching_design: str = Field(alias="teachingDesign", max_length=100000)
    process: list[ProcessItem] = Field(max_length=100)
    exercises: str = Field(max_length=100000)
    reflection: str = Field(max_length=100000)

    @field_validator("title", "total_lessons", "current_lesson_no", "other_type_text",
                     "core_competencies", "key_points", "teaching_design", "exercises", "reflection")
    @classmethod
    def lengths(cls, value: str, info):
        limit = 80 if info.field_name in ("title", "other_type_text") else 100000
        if utf16_length(value) > limit:
            raise ValueError(f"{info.field_name} exceeds {limit} UTF-16 code units")
        value.encode("utf-8")
        return value

    @model_validator(mode="after")
    def identifiers(self):
        if len({item.id for item in self.process}) != len(self.process):
            raise ValueError("process IDs must be unique")
        return self


class DraftEnvelope(Frozen):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    revision: int = Field(ge=0, le=MAX_SAFE_INTEGER)
    updated_at: str = Field(alias="updatedAt", min_length=1, max_length=64)
    data: LessonPlanData

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("schemaVersion must be integer 1")
        return value

    @field_validator("updated_at")
    @classmethod
    def iso_timestamp(cls, value: str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if "T" not in value or parsed.tzinfo is None:
            raise ValueError("updatedAt must be an ISO datetime with a timezone")
        return value  # Preserve the original timestamp spelling.


class AnalysisContextInput(Frozen):
    analysis_run_id: str = Field(alias="analysisRunId", min_length=1, max_length=128)
    selected_knowledge_point_ids: list[str] = Field(alias="selectedKnowledgePointIds", min_length=1, max_length=50)

    @field_validator("selected_knowledge_point_ids")
    @classmethod
    def unique_points(cls, value):
        if any(not x or len(x) > 128 for x in value) or len(set(value)) != len(value):
            raise ValueError("selectedKnowledgePointIds must be nonempty unique IDs")
        return value  # Input order is meaningful and preserved.


class RequestModel(Frozen):
    @model_validator(mode="after")
    def size(self):
        raw = json.dumps(self.model_dump(by_alias=True, mode="json"), ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("The canonical request exceeds the 2 MiB import/save limit; retain the original draft")
        return self


class LessonCreateRequest(RequestModel):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    subject_id: str = Field(alias="subjectId", min_length=1, max_length=64)
    class_id: str = Field(alias="classId", min_length=1, max_length=128)
    data: LessonPlanData
    context: AnalysisContextInput | None
    source: Literal["manual", "rule"] = "manual"


class LessonImportRequest(RequestModel):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    subject_id: str = Field(alias="subjectId", min_length=1, max_length=64)
    class_id: str = Field(alias="classId", min_length=1, max_length=128)
    draft: DraftEnvelope
    context: AnalysisContextInput | None


class LessonSaveRequest(RequestModel):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    expected_revision: int = Field(alias="expectedRevision", ge=1, le=MAX_SAFE_INTEGER)
    data: LessonPlanData
    context: AnalysisContextInput | None
    source: Literal["manual", "rule"] = "manual"


class LessonRevisionRequest(RequestModel):
    """教案归档/恢复的乐观锁请求（只带修订号，与施测/原卷归档口径一致）。"""

    expected_revision: int = Field(default=0, alias="expectedRevision", ge=0, le=MAX_SAFE_INTEGER)


class AnalysisContextSnapshot(Frozen):
    analysis_run_id: str = Field(alias="analysisRunId")
    input_hash: str = Field(alias="inputHash")
    score_revision_id: str = Field(alias="scoreRevisionId")
    paper_revision_id: str = Field(alias="paperRevisionId")
    class_name: str | None = Field(alias="className")
    class_name_note: str = Field(alias="classNameNote")
    knowledge_points: list[FixedKnowledge] = Field(alias="knowledgePoints")


class LessonContextSnapshot(Frozen):
    subject_id: str = Field(alias="subjectId")
    class_id: str = Field(alias="classId")
    class_name_at_save: str = Field(alias="classNameAtSave")
    analysis: AnalysisContextSnapshot | None


class StageMetadata(Frozen):
    process_id: str = Field(alias="processId", min_length=1, max_length=100000)
    phase: Literal["introduction", "exploration", "practice", "conclusion"]
    minutes: int = Field(ge=1, le=180)
    knowledge_aliases: list[str] = Field(alias="knowledgeAliases", min_length=1, max_length=50)
    activity: str = Field(min_length=1, max_length=4000)
    check: str = Field(min_length=1, max_length=4000)
    evidence_aliases: list[str] = Field(alias="evidenceAliases", min_length=1, max_length=31)


class LessonRevisionView(Frozen):
    protocol_version: Literal[2] = Field(default=2, alias="protocolVersion")
    lesson_plan_id: str = Field(alias="lessonPlanId")
    revision_id: str = Field(alias="revisionId")
    version: int
    data: LessonPlanData
    content_hash: str = Field(alias="contentHash")
    source: LessonSource
    context_snapshot: LessonContextSnapshot = Field(alias="contextSnapshot")
    analysis_run_id: str | None = Field(alias="analysisRunId")
    accepted_proposal_id: str | None = Field(alias="acceptedProposalId")
    import_envelope: DraftEnvelope | None = Field(alias="importEnvelope")
    selected_fields: list[AllowedField] = Field(alias="selectedFields")
    process_metadata: list[StageMetadata] = Field(alias="processMetadata")
    review_state: Literal["unreviewed", "reviewed"] = Field(alias="reviewState")
    created_at: str = Field(alias="createdAt")


class LessonView(Frozen):
    protocol_version: Literal[2] = Field(default=2, alias="protocolVersion")
    lesson_plan_id: str = Field(alias="lessonPlanId")
    subject_id: str = Field(alias="subjectId")
    class_id: str = Field(alias="classId")
    revision: int
    current_revision_id: str = Field(alias="currentRevisionId")
    current_revision: LessonRevisionView = Field(alias="currentRevision")
    replayed: bool = False


class LessonSummary(Frozen):
    lesson_plan_id: str = Field(alias="lessonPlanId")
    subject_id: str = Field(alias="subjectId")
    class_id: str = Field(alias="classId")
    revision: int
    current_revision_id: str = Field(alias="currentRevisionId")
    title: str
    source: LessonSource
    analysis_run_id: str | None = Field(alias="analysisRunId")
    updated_at: str = Field(alias="updatedAt")


class LessonRevisionSummary(Frozen):
    lesson_plan_id: str = Field(alias="lessonPlanId")
    revision_id: str = Field(alias="revisionId")
    version: int
    title: str
    content_hash: str = Field(alias="contentHash")
    source: LessonSource
    analysis_run_id: str | None = Field(alias="analysisRunId")
    accepted_proposal_id: str | None = Field(alias="acceptedProposalId")
    selected_fields: list[AllowedField] = Field(alias="selectedFields")
    review_state: Literal["unreviewed", "reviewed"] = Field(alias="reviewState")
    created_at: str = Field(alias="createdAt")


class EvidenceSlice(Frozen):
    document_revision_id: str = Field(alias="documentRevisionId", min_length=1, max_length=64)
    char_start: int = Field(alias="charStart", ge=0, le=MAX_SAFE_INTEGER)
    char_end: int = Field(alias="charEnd", ge=1, le=MAX_SAFE_INTEGER)

    @model_validator(mode="after")
    def span(self):
        if self.char_start >= self.char_end or self.char_end - self.char_start > 6000:
            raise ValueError("Selected source spans must contain 1..6000 code points")
        return self


class LessonEvidenceRequest(RequestModel):
    selection: TextbookSelection
    slices: list[EvidenceSlice] = Field(min_length=1, max_length=6)


class LessonEvidenceView(Frozen):
    scope_snapshot: ScopeSnapshot = Field(alias="scopeSnapshot")
    evidence_refs: list[EvidenceRef] = Field(alias="evidenceRefs")
    evidence: list[TextbookEvidence]


class LessonGenerateRequest(RequestModel):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    base_revision_id: str = Field(alias="baseRevisionId", min_length=1, max_length=128)
    base_server_revision: int = Field(alias="baseServerRevision", ge=1, le=MAX_SAFE_INTEGER)
    analysis_run_id: str = Field(alias="analysisRunId", min_length=1, max_length=128)
    class_id: str = Field(alias="classId", min_length=1, max_length=128)
    selected_knowledge_point_ids: list[str] = Field(alias="selectedKnowledgePointIds", min_length=1, max_length=50)
    requirements: str = Field(min_length=1, max_length=4000)
    duration_minutes: int = Field(alias="durationMinutes", ge=5, le=180)
    model_profile_id: str = Field(alias="modelProfileId", min_length=1, max_length=128)
    scope_snapshot: ScopeSnapshot = Field(alias="scopeSnapshot")
    evidence_refs: list[EvidenceRef] = Field(alias="evidenceRefs", min_length=1, max_length=6)
    question_revision_ids: list[str] = Field(alias="questionRevisionIds", max_length=20)
    practice_revision_ids: list[str] = Field(alias="practiceRevisionIds", max_length=5)

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def strict_coordinates(cls, value):
        if isinstance(value, list):
            for ref in value:
                if isinstance(ref, dict):
                    for key in ("charStart", "charEnd"):
                        coordinate = ref.get(key)
                        if type(coordinate) is not int or not 0 <= coordinate <= MAX_SAFE_INTEGER:
                            raise ValueError("Evidence coordinates must be safe integers")
        return value

    @model_validator(mode="after")
    def bounded_evidence(self):
        identities = [(x.documentRevisionId, x.charStart, x.charEnd) for x in self.evidence_refs]
        spans = [x.charEnd - x.charStart for x in self.evidence_refs]
        if len(set(identities)) != len(identities) or any(x > 6000 for x in spans) or sum(spans) > 16000:
            raise ValueError("Evidence spans must be unique, at most 6000 each and 16000 in total")
        return self

    @field_validator("selected_knowledge_point_ids", "question_revision_ids", "practice_revision_ids")
    @classmethod
    def unique_ids(cls, value):
        if any(not x or len(x) > 128 for x in value) or len(set(value)) != len(value):
            raise ValueError("IDs must be nonempty and unique; input order is preserved")
        return value

    @field_validator("requirements")
    @classmethod
    def requirements_limit(cls, value):
        if not value.strip() or utf16_length(value) > 4000:
            raise ValueError("requirements must contain 1..4000 UTF-16 code units")
        value.encode("utf-8")
        return value


class LessonGenerationReceipt(Frozen):
    lesson_plan_id: str = Field(alias="lessonPlanId")
    input_hash: str = Field(alias="inputHash")
    job: JobView
    replayed: bool


class LessonPatch(Frozen):
    core_competencies: str | None = Field(default=None, alias="coreCompetencies", max_length=100000)
    key_points: str | None = Field(default=None, alias="keyPoints", max_length=100000)
    teaching_design: str | None = Field(default=None, alias="teachingDesign", max_length=100000)
    process: list[ProcessItem]  # Required: four phases/budget are verified by the AI validator.
    exercises: str | None = Field(default=None, max_length=100000)


class ProposalEvidenceView(Frozen):
    alias: str
    kind: Literal["textbook", "question", "practice"]
    reference_id: str = Field(alias="referenceId")
    title: str
    sha256: str
    locator: dict
    text: str


class LessonBudget(Frozen):
    duration_minutes: int = Field(alias="durationMinutes", ge=5, le=180)
    stages: list[StageMetadata] = Field(min_length=4, max_length=12)


class GenerationSourceView(Frozen):
    analysis: AnalysisContextSnapshot
    class_id: str = Field(alias="classId")
    selected_knowledge_points: list[FixedKnowledge] = Field(alias="selectedKnowledgePoints")
    model_profile_id: str = Field(alias="modelProfileId")
    scope_snapshot: ScopeSnapshot = Field(alias="scopeSnapshot")
    evidence_refs: list[EvidenceRef] = Field(alias="evidenceRefs")
    requirements: str


class LessonProposalView(Frozen):
    protocol_version: Literal[2] = Field(default=2, alias="protocolVersion")
    lesson_plan_id: str = Field(alias="lessonPlanId")
    proposal_id: str = Field(alias="proposalId")
    job_id: str = Field(alias="jobId")
    base_revision_id: str = Field(alias="baseRevisionId")
    base_server_revision: int = Field(alias="baseServerRevision")
    input_hash: str = Field(alias="inputHash")
    model_fingerprint: str = Field(alias="modelFingerprint")
    state: Literal["pending", "applied", "rejected", "stale"]
    patch: LessonPatch
    budget: LessonBudget
    evidence: list[ProposalEvidenceView]
    generation_source: GenerationSourceView = Field(alias="generationSource")
    selected_fields: list[AllowedField] = Field(alias="selectedFields")
    accepted_revision_id: str | None = Field(alias="acceptedRevisionId")
    created_at: str = Field(alias="createdAt")
    decided_at: str | None = Field(alias="decidedAt")
    replayed: bool = False


class LessonApplyRequest(RequestModel):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
    expected_revision: int = Field(alias="expectedRevision", ge=1, le=MAX_SAFE_INTEGER)
    base_revision_id: str = Field(alias="baseRevisionId", min_length=1, max_length=128)
    selected_fields: list[AllowedField] = Field(alias="selectedFields", min_length=1, max_length=5)

    @field_validator("selected_fields")
    @classmethod
    def unique_fields(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("selectedFields must be unique")
        return value


class LessonRejectRequest(RequestModel):
    submission_id: str = Field(alias="submissionId", min_length=1, max_length=128)
