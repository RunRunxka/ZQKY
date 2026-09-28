"""教材目录记录类型：仓储函数返回的只读快照，不持有连接、不做延迟写入。

约束：
- 记录构造时 JSON 列已由仓储校验；``*_json`` 字段保留原始规范化文本，属性只做反序列化。
- 记录不含"是否已发布/是否在范围"等派生判断，范围解析由 ``TextbookCatalog.resolve_selection`` 统一给出。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.repositories.textbook_catalog import json_fields


@dataclass(frozen=True)
class CatalogState:
    active_generation_id: str | None
    rebuild_job_id: str | None
    catalog_version: int


@dataclass(frozen=True)
class LibraryRecord:
    library_id: str
    kind: str
    owner_id: str
    grade_id: str | None
    subject_id: str
    edition_id: str
    display_name: str
    revision: int
    deleted_at: str | None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


@dataclass(frozen=True)
class MetadataRevisionRecord:
    metadata_revision_id: str
    document_id: str
    title: str
    stage_id: str
    grade_ids: tuple[str, ...]
    subject_id: str
    edition_id: str
    publication_label: str
    volume_label: str
    created_at: str


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    owner_id: str
    origin_key: str | None
    current_revision_id: str | None
    current_metadata_revision_id: str
    revision: int
    deleted_at: str | None
    library_ids: tuple[str, ...]
    metadata: MetadataRevisionRecord

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def title(self) -> str:
        return self.metadata.title

    @property
    def stage_id(self) -> str:
        return self.metadata.stage_id

    @property
    def grade_ids(self) -> tuple[str, ...]:
        return self.metadata.grade_ids

    @property
    def subject_id(self) -> str:
        return self.metadata.subject_id

    @property
    def edition_id(self) -> str:
        return self.metadata.edition_id

    @property
    def publication_label(self) -> str:
        return self.metadata.publication_label

    @property
    def volume_label(self) -> str:
        return self.metadata.volume_label


@dataclass(frozen=True)
class RevisionRecord:
    revision_id: str
    document_id: str
    original_file_sha256: str
    normalized_text_sha256: str
    parser_version: str
    original_blob_id: str
    normalized_blob_id: str
    source_map_blob_id: str
    char_count: int
    created_at: str


@dataclass(frozen=True)
class ChunkInput:
    ordinal: int
    char_start: int
    char_end: int
    region: str
    chapter_path: Sequence[str]
    text_sha256: str
    legacy_chunk_id: str | None = None


@dataclass(frozen=True)
class ChunkRecord:
    chunk_set_id: str
    ordinal: int
    char_start: int
    char_end: int
    region: str
    chapter_path: tuple[str, ...]
    text_sha256: str
    legacy_chunk_id: str | None


@dataclass(frozen=True)
class ChunkSetRecord:
    chunk_set_id: str
    document_revision_id: str
    policy_fingerprint: str
    manifest_sha256: str
    chunk_count: int
    sealed_at: str


@dataclass(frozen=True)
class GenerationRecord:
    generation_id: str
    profile_id: str
    collection_name: str
    chunk_policy_json: str
    state: str
    created_at: str
    published_at: str | None

    @property
    def chunk_policy(self) -> dict:
        policy = json_fields.read_object(self.chunk_policy_json, field="index_generations.chunk_policy_json")
        assert policy is not None
        return policy


@dataclass(frozen=True)
class GenerationRevisionRecord:
    generation_id: str
    document_revision_id: str
    chunk_set_id: str
    state: str
    expected_chunk_count: int
    manifest_sha256: str


@dataclass(frozen=True)
class ProfileRecord:
    profile_id: str
    fingerprint: str
    adapter: str
    native_base_url: str
    model_name: str
    model_manifest_digest: str
    dimensions: int
    distance: str
    query_prefix: str
    document_prefix: str
    normalization: str
    options_json: str
    verified_at: str
    retired_at: str | None

    @property
    def options(self) -> dict:
        options = json_fields.read_object(self.options_json, field="embedding_profiles.options_json")
        assert options is not None
        return options

    @property
    def is_retired(self) -> bool:
        return self.retired_at is not None


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    kind: str
    input_revision_id: str | None
    document_id: str | None
    metadata_revision_id: str | None
    target_generation_id: str | None
    base_generation_id: str | None
    state: str
    idempotency_key: str | None
    request_fingerprint: str
    attempt: int
    lease_token: str | None
    lease_until: str | None
    checkpoint_json: str
    error_code: str | None
    error_message: str | None
    created_at: str
    updated_at: str

    @property
    def checkpoint(self) -> dict:
        checkpoint = json_fields.read_object(self.checkpoint_json, field="index_jobs.checkpoint_json")
        assert checkpoint is not None
        return checkpoint


@dataclass(frozen=True)
class ImportRecord:
    import_id: str
    owner_id: str
    target_document_id: str | None
    expected_current_revision_id: str | None
    metadata_json: str | None
    uploaded_blob_id: str
    uploaded_file_name: str
    uploaded_bytes: int
    parsed_artifacts_json: str | None
    state: str
    revision: int
    warnings_json: str
    error_code: str | None
    created_at: str
    updated_at: str

    @property
    def metadata(self) -> dict | None:
        return json_fields.read_object(
            self.metadata_json, field="import_drafts.metadata_json", allow_none=True
        )

    @property
    def parsed_artifacts(self) -> dict | None:
        return json_fields.read_object(
            self.parsed_artifacts_json, field="import_drafts.parsed_artifacts_json", allow_none=True
        )

    @property
    def warnings(self) -> list[str]:
        return json_fields.read_string_list(self.warnings_json, field="import_drafts.warnings_json")


@dataclass(frozen=True)
class TeachingRecord:
    owner_id: str
    selection_json: str | None
    revision: int
    updated_at: str | None

    @property
    def selection(self) -> dict | None:
        return json_fields.read_object(
            self.selection_json, field="teaching_settings.selection_json", allow_none=True
        )


@dataclass(frozen=True)
class ResolvedDocument:
    document_id: str
    document_revision_id: str
    metadata_revision_id: str
    chunk_set_id: str
    title: str
    subject_id: str
    edition_id: str
    grade_ids: tuple[str, ...]
    library_ids: tuple[str, ...]


@dataclass(frozen=True)
class AllowedChunks:
    revision_ids: tuple[str, ...]
    chunk_set_ids: tuple[str, ...]
