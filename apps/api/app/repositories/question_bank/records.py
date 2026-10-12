"""题库记录类型：仓储函数返回的只读快照，不持有连接、不做延迟写入。

``content`` / ``metadata`` / ``source_spans`` / ``locator`` / ``checkpoint`` 等
JSON 列在仓储层已读回校验，这里只保留反序列化后的对象；``*_json`` 字段不暴露，
避免调用方拿到未经校验的原始文本。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ImportRecord:
    import_id: str
    owner_id: str
    file_sha256: str
    original_blob_id: str
    uploaded_file_name: str
    uploaded_bytes: int
    state: str
    revision: int
    warnings: tuple[str, ...]
    error_code: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SourceBlockInput:
    ordinal: int
    text: str
    locator: dict[str, Any]


@dataclass(frozen=True)
class SourceBlockRecord:
    block_id: str
    import_id: str
    ordinal: int
    text: str
    locator: dict[str, Any]


@dataclass(frozen=True)
class DraftInput:
    content: dict[str, Any]
    metadata: dict[str, Any]
    source_spans: list[dict[str, Any]]
    extraction_method: str
    review_state: str = "needs_review"
    missing_answer_acknowledged: bool = False
    warnings: tuple[str, ...] = ()
    content_fingerprint: str = ""


@dataclass(frozen=True)
class DraftRecord:
    draft_id: str
    import_id: str
    revision: int
    content: dict[str, Any]
    metadata: dict[str, Any]
    source_spans: list[dict[str, Any]]
    extraction_method: str
    review_state: str
    missing_answer_acknowledged: bool
    warnings: tuple[str, ...]
    content_fingerprint: str
    duplicate_of_question_id: str | None


@dataclass(frozen=True)
class SuggestionInput:
    organization_job_id: str
    target_draft_id: str
    base_draft_revision: int
    proposed_content: dict[str, Any]
    proposed_metadata: dict[str, Any]
    source_block_ids: tuple[str, ...]
    state: str = "pending"
    note: str | None = None


@dataclass(frozen=True)
class SuggestionRecord:
    suggestion_id: str
    organization_job_id: str
    target_draft_id: str
    base_draft_revision: int
    proposed_content: dict[str, Any]
    proposed_metadata: dict[str, Any]
    source_block_ids: tuple[str, ...]
    state: str
    note: str | None


@dataclass(frozen=True)
class QuestionRecord:
    question_id: str
    owner_id: str
    current_revision_id: str
    status: str
    created_at: str
    revision: int
    content: dict[str, Any]
    metadata: dict[str, Any]
    answer_state: str
    content_fingerprint: str
    confirmed_at: str
    sources: tuple[dict[str, Any], ...]
    source_import_id: str | None


@dataclass(frozen=True)
class SubmissionRecord:
    submission_id: str
    request_fingerprint: str
    result: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    kind: str
    state: str
    checkpoint: dict[str, Any]
    error_code: str | None
    created_at: str
    updated_at: str
