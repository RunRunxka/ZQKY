"""Read-only fixed question selection, supplemental to frozen B5 lesson DTOs."""
from pydantic import BaseModel, ConfigDict, Field


class ConfirmedQuestionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, populate_by_name=True)
    question_id: str = Field(alias="questionId")
    question_revision_id: str = Field(alias="questionRevisionId")
    subject_id: str = Field(alias="subjectId")
    stem_markdown: str = Field(alias="stemMarkdown")
