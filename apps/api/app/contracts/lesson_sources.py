"""Read-only fixed question selection, supplemental to frozen B5 lesson DTOs."""
from pydantic import BaseModel, ConfigDict, Field


class ConfirmedQuestionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, populate_by_name=True)
    question_id: str = Field(alias="questionId")
    question_revision_id: str = Field(alias="questionRevisionId")
    subject_id: str = Field(alias="subjectId")
    stem_markdown: str = Field(alias="stemMarkdown")


class LessonSourceUploadView(BaseModel):
    """教师上传的学情材料回执（2026-10-13 补齐 ``POST /lesson-plans/source-uploads``）。

    ``assetRef`` 即受管资产 id：生成流以它作为 ``sourceAssetRef`` 读回材料文本；
    其余字段供界面显示文件名/体积，不改写服务端口径。
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, populate_by_name=True)

    asset_ref: str = Field(alias="assetRef")
    file_name: str = Field(alias="fileName")
    media_type: str = Field(alias="mediaType")
    byte_size: int = Field(alias="byteSize")
    sha256: str


__all__ = ["ConfirmedQuestionRevision", "LessonSourceUploadView"]
