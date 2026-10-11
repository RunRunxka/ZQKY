"""教材目录 SQLite 权威层：迁移、不可变修订、分类、范围解析、幂等任务与删除。

约束：
- 所有写操作在 ``transaction(conn, immediate=True)`` 内完成；函数内不做网络、解析与推理。
- 每次操作独立开连接（``connect``）：实例可被 FastAPI 线程池跨线程使用，连接不跨线程共享。
- ``document_revisions`` / ``document_metadata_revisions`` / ``chunk_sets`` / ``chunks`` 写入后没有更新路径；
  改分类只能新建元数据修订。
- 带 ``expected_revision`` 的写操作在同一事务内先比对再写。
- JSON 列读回校验；损坏抛 ``CATALOG_CORRUPT``（500），不静默降级、不覆盖原行。
- 目录写入（逻辑库、书册、关联、分类、发布、删除）递增 ``catalog_state.catalog_version``；
  任务、索引代、导入草稿、Embedding 配置、任教设置不占用该版本号。
- 范围解析只认 ``catalog_state.active_generation_id`` 这一个当前索引指针。
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, get_args

from app.core.exceptions import AppError
from app.core.sqlite import (
    connect,
    now_iso,
    open_readonly,
    read_transaction,
    transaction,
)
from app.repositories.textbook_catalog import json_fields
from app.repositories.textbook_catalog.schema import REQUIRED_TABLES
from app.repositories.textbook_catalog.records import (
    AllowedChunks,
    CatalogState,
    ChunkInput,
    ChunkRecord,
    ChunkSetRecord,
    DocumentRecord,
    GenerationRecord,
    GenerationRevisionRecord,
    ImportRecord,
    JobRecord,
    LibraryRecord,
    MetadataRevisionRecord,
    ProfileRecord,
    ResolvedDocument,
    RevisionRecord,
    TeachingRecord,
)
from app.repositories.textbook_catalog.schema import migrate as migrate_schema
from app.schemas.textbook import (
    ChunkRegion,
    GenerationState,
    ImportState,
    JobKind,
    JobState,
    LibraryKind,
    OwnerId,
)

LIBRARY_KINDS = frozenset(get_args(LibraryKind))
OWNER_IDS = frozenset(get_args(OwnerId))
GENERATION_STATES = frozenset(get_args(GenerationState))
GENERATION_REVISION_STATES = frozenset({"pending", "ready", "skipped_deleted"})
JOB_KINDS = frozenset(get_args(JobKind))
JOB_STATES = frozenset(get_args(JobState))
JOB_FINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})
IMPORT_STATES = frozenset(get_args(ImportState))
CHUNK_REGIONS = frozenset(get_args(ChunkRegion))
NORMALIZATIONS = frozenset({"none", "l2"})
TEACHING_OWNER = "local-user"


def _invalid(message: str, *, code: str = "INVALID_REQUEST") -> AppError:
    return AppError(message, code=code, status_code=422)


def _not_found(message: str, *, code: str) -> AppError:
    return AppError(message, code=code, status_code=404)


def _conflict(message: str, *, code: str, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=409, retryable=retryable)


def _corrupt(message: str) -> AppError:
    return AppError(message, code="CATALOG_CORRUPT", status_code=500)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。")
    return value


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field=field)


def _choice(value: object, *, field: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _invalid(f"{field} 必须是 {sorted(allowed)} 之一。")
    return value


def _count(value: object, *, field: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise _invalid(f"{field} 必须是不小于 {minimum} 的整数。")
    return value


def _unique_texts(values: object, *, field: str, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _invalid(f"{field} 必须是字符串序列。")
    items = list(values)
    if not allow_empty and not items:
        raise _invalid(f"{field} 不能为空。")
    seen: list[str] = []
    for item in items:
        text = _text(item, field=field)
        if text not in seen:
            seen.append(text)
    return tuple(seen)


def _stored_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise _corrupt(f"教材目录数据损坏：{field} 不是非空字符串。")
    return value


def _stored_count(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _corrupt(f"教材目录数据损坏：{field} 不是非负整数。")
    return value


def _lease_deadline(seconds: int) -> str:
    moment = datetime.now(UTC) + timedelta(seconds=seconds)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TextbookCatalog:
    """教材目录的唯一读写入口；调用方给出数据库路径，测试使用临时目录。"""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._closed = False
        self._migrated = False

    # ------------------------------------------------------------ 生命周期

    @property
    def db_path(self) -> Path:
        return self._db_path

    def migrate(self) -> None:
        connection = self._open(require_migrated=False)
        try:
            # 迁移执行器（app.core.migrations）逐条自管事务；这里不再包外层事务。
            migrate_schema(connection)
        finally:
            connection.close()
        self._migrated = True

    def close(self) -> None:
        self._closed = True

    def open_existing(self) -> None:
        """**只读**打开既有目录：不建库、不建表、不改结构。

        验收脚本与只读工具用这个入口，避免"路径写错时静默建出空库"把失败伪装成空数据
        （docs/PLAN.md §6.2）。库不存在或结构不完整时明确报错。
        """
        connection = open_readonly(self._db_path, required_tables=REQUIRED_TABLES)
        connection.close()
        self._migrated = True

    def _open(self, *, require_migrated: bool = True) -> sqlite3.Connection:
        """每次操作独立连接：实例可被 FastAPI 线程池并发使用，连接不跨线程共享。"""
        if self._closed:
            raise AppError("教材目录已关闭。", code="CATALOG_CLOSED", status_code=500)
        if require_migrated and not self._migrated:
            raise AppError(
                "教材目录尚未迁移：先调用 migrate()。",
                code="CATALOG_NOT_MIGRATED",
                status_code=500,
            )
        return connect(self._db_path)

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """写事务：IMMEDIATE 抢写锁后立即提交；函数内不得做网络/解析/推理。"""
        connection = self._open()
        try:
            with transaction(connection, immediate=True) as conn:
                yield conn
        finally:
            connection.close()

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        connection = self._open()
        try:
            with read_transaction(connection) as conn:
                yield conn
        finally:
            connection.close()

    def _read_one(self, sql: str, params: Sequence[object] = ()) -> sqlite3.Row | None:
        with self._read() as conn:
            return conn.execute(sql, params).fetchone()

    def _read_all(self, sql: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
        with self._read() as conn:
            return list(conn.execute(sql, params).fetchall())

    # ------------------------------------------------------------ 目录状态

    def catalog_state(self) -> CatalogState:
        with self._read() as conn:
            row = conn.execute("SELECT * FROM catalog_state WHERE id = 1").fetchone()
        if row is None:
            raise _corrupt("教材目录数据损坏：catalog_state 缺少 id=1 行。")
        return CatalogState(
            active_generation_id=row["active_generation_id"],
            rebuild_job_id=row["rebuild_job_id"],
            catalog_version=_stored_count(row["catalog_version"], field="catalog_state.catalog_version"),
        )

    def set_active_generation(self, generation_id: str | None) -> None:
        target = _optional_text(generation_id, field="generation_id")
        with self._write() as conn:
            if target is not None and self._generation_row(conn, target) is None:
                raise _not_found("索引代不存在。", code="GENERATION_NOT_FOUND")
            conn.execute("UPDATE catalog_state SET active_generation_id = ? WHERE id = 1", (target,))

    def set_rebuild_job(self, job_id: str | None) -> None:
        target = _optional_text(job_id, field="job_id")
        with self._write() as conn:
            if target is not None and self._job_row(conn, target) is None:
                raise _not_found("索引任务不存在。", code="JOB_NOT_FOUND")
            conn.execute("UPDATE catalog_state SET rebuild_job_id = ? WHERE id = 1", (target,))

    # ------------------------------------------------------------ 逻辑库

    def create_library(
        self,
        *,
        kind: str,
        owner_id: str,
        display_name: str,
        grade_id: str | None,
        subject_id: str,
        edition_id: str,
    ) -> LibraryRecord:
        kind = _choice(kind, field="kind", allowed=LIBRARY_KINDS)
        owner_id = _choice(owner_id, field="owner_id", allowed=OWNER_IDS)
        display_name = _text(display_name, field="display_name")
        grade_id = _optional_text(grade_id, field="grade_id")
        subject_id = _text(subject_id, field="subject_id")
        edition_id = _text(edition_id, field="edition_id")
        library_id = uuid.uuid4().hex
        with self._write() as conn:
            conn.execute(
                "INSERT INTO libraries (id, kind, owner_id, grade_id, subject_id, edition_id, "
                "display_name, revision, deleted_at) VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL)",
                (library_id, kind, owner_id, grade_id, subject_id, edition_id, display_name),
            )
            self._touch_catalog(conn)
            return self._library_record(self._library_row(conn, library_id))

    def get_library(self, library_id: str) -> LibraryRecord | None:
        with self._read() as conn:
            row = self._library_row(conn, library_id)
        return self._library_record(row) if row is not None else None

    def list_libraries(
        self,
        *,
        kind: str | None = None,
        grade_id: str | None = None,
        subject_id: str | None = None,
        edition_id: str | None = None,
        include_deleted: bool = False,
    ) -> list[LibraryRecord]:
        if kind is not None:
            kind = _choice(kind, field="kind", allowed=LIBRARY_KINDS)
        clauses: list[str] = []
        params: list[object] = []
        for column, value in (
            ("kind", kind),
            ("grade_id", grade_id),
            ("subject_id", subject_id),
            ("edition_id", edition_id),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        if not include_deleted:
            clauses.append("deleted_at IS NULL")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._read_all(
            f"SELECT * FROM libraries{where} ORDER BY rowid ASC", params
        )
        return [self._library_record(row) for row in rows]

    def update_library(
        self,
        library_id: str,
        *,
        expected_revision: int,
        display_name: str | None = None,
        grade_id: str | None = None,
        edition_id: str | None = None,
    ) -> LibraryRecord:
        library_id = _text(library_id, field="library_id")
        updates: dict[str, str] = {}
        if display_name is not None:
            updates["display_name"] = _text(display_name, field="display_name")
        if grade_id is not None:
            updates["grade_id"] = _text(grade_id, field="grade_id")
        if edition_id is not None:
            updates["edition_id"] = _text(edition_id, field="edition_id")
        with self._write() as conn:
            row = self._live_library_row(conn, library_id)
            self._check_revision(row["revision"], expected_revision, what="逻辑库")
            if updates:
                assignments = ", ".join(f"{column} = ?" for column in updates)
                conn.execute(
                    f"UPDATE libraries SET {assignments}, revision = revision + 1 WHERE id = ?",
                    (*updates.values(), library_id),
                )
                self._touch_catalog(conn)
            return self._library_record(self._library_row(conn, library_id))

    def delete_library(self, library_id: str, *, expected_revision: int) -> None:
        library_id = _text(library_id, field="library_id")
        with self._write() as conn:
            row = self._live_library_row(conn, library_id)
            self._check_revision(row["revision"], expected_revision, what="逻辑库")
            # 逻辑删除只标记；library_documents 关联保留，范围解析与列表按 deleted_at 过滤
            conn.execute(
                "UPDATE libraries SET deleted_at = ?, revision = revision + 1 WHERE id = ?",
                (now_iso(), library_id),
            )
            self._touch_catalog(conn)

    def link_document(self, library_id: str, document_id: str) -> None:
        library_id = _text(library_id, field="library_id")
        document_id = _text(document_id, field="document_id")
        with self._write() as conn:
            self._live_library_row(conn, library_id)
            self._require_document_row(conn, document_id, live=True)
            cursor = conn.execute(
                "INSERT OR IGNORE INTO library_documents (library_id, document_id) VALUES (?, ?)",
                (library_id, document_id),
            )
            if cursor.rowcount:
                self._touch_catalog(conn)

    def unlink_document(self, library_id: str, document_id: str) -> None:
        library_id = _text(library_id, field="library_id")
        document_id = _text(document_id, field="document_id")
        with self._write() as conn:
            if self._library_row(conn, library_id) is None:
                raise _not_found("逻辑库不存在。", code="LIBRARY_NOT_FOUND")
            self._require_document_row(conn, document_id, live=False)
            cursor = conn.execute(
                "DELETE FROM library_documents WHERE library_id = ? AND document_id = ?",
                (library_id, document_id),
            )
            if cursor.rowcount:
                self._touch_catalog(conn)

    def library_document_ids(self, library_id: str) -> list[str]:
        library_id = _text(library_id, field="library_id")
        with self._read() as conn:
            library = self._library_row(conn, library_id)
            if library is None:
                raise _not_found("逻辑库不存在。", code="LIBRARY_NOT_FOUND")
            if library["deleted_at"] is not None:
                return []
            rows = conn.execute(
                "SELECT d.id AS document_id FROM library_documents AS ld "
                "JOIN documents AS d ON d.id = ld.document_id "
                "WHERE ld.library_id = ? AND d.deleted_at IS NULL ORDER BY d.rowid ASC",
                (library_id,),
            ).fetchall()
            return [row["document_id"] for row in rows]

    # ------------------------------------------------------------ 书册

    def create_document(
        self,
        *,
        owner_id: str,
        title: str,
        stage_id: str,
        grade_ids: Sequence[str],
        subject_id: str,
        edition_id: str,
        publication_label: str = "",
        volume_label: str = "",
        origin_key: str | None = None,
        library_ids: Sequence[str] = (),
    ) -> DocumentRecord:
        owner_id = _choice(owner_id, field="owner_id", allowed=OWNER_IDS)
        title = _text(title, field="title")
        stage_id = _text(stage_id, field="stage_id")
        subject_id = _text(subject_id, field="subject_id")
        edition_id = _text(edition_id, field="edition_id")
        grade_ids = _unique_texts(grade_ids, field="grade_ids")
        publication_label = _text_or_empty(publication_label, field="publication_label")
        volume_label = _text_or_empty(volume_label, field="volume_label")
        origin_key = _optional_text(origin_key, field="origin_key")
        library_ids = _unique_texts(library_ids, field="library_ids", allow_empty=True)
        document_id = uuid.uuid4().hex
        metadata_revision_id = uuid.uuid4().hex
        with self._write() as conn:
            if origin_key is not None:
                existing = conn.execute(
                    "SELECT id FROM documents WHERE owner_id = ? AND origin_key = ?",
                    (owner_id, origin_key),
                ).fetchone()
                if existing is not None:
                    raise _conflict("同一来源键的教材已存在。", code="DOCUMENT_ORIGIN_CONFLICT")
            for library_id in library_ids:
                self._live_library_row(conn, library_id)
            # documents.current_metadata_revision_id 与元数据修订的 document_id 互为环形外键，
            # 同一事务内插入需延后到 COMMIT 校验。
            conn.execute("PRAGMA defer_foreign_keys = ON")
            conn.execute(
                "INSERT INTO documents (id, owner_id, origin_key, current_revision_id, "
                "current_metadata_revision_id, revision, deleted_at) VALUES (?, ?, ?, NULL, ?, 0, NULL)",
                (document_id, owner_id, origin_key, metadata_revision_id),
            )
            self._insert_metadata_revision(
                conn,
                metadata_revision_id=metadata_revision_id,
                document_id=document_id,
                title=title,
                stage_id=stage_id,
                grade_ids=grade_ids,
                subject_id=subject_id,
                edition_id=edition_id,
                publication_label=publication_label,
                volume_label=volume_label,
            )
            for library_id in library_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO library_documents (library_id, document_id) VALUES (?, ?)",
                    (library_id, document_id),
                )
            self._touch_catalog(conn)
            return self._document_record(conn, document_id)

    def get_document(self, document_id: str) -> DocumentRecord | None:
        document_id = _text(document_id, field="document_id")
        with self._read() as conn:
            row = self._document_row(conn, document_id)
            if row is None:
                return None
            return self._build_document_record(conn, row)

    def require_live_document(self, document_id: str) -> DocumentRecord:
        document_id = _text(document_id, field="document_id")
        with self._read() as conn:
            self._require_document_row(conn, document_id, live=True)
            return self._document_record(conn, document_id)

    def list_documents(
        self,
        *,
        library_id: str | None = None,
        grade_id: str | None = None,
        subject_id: str | None = None,
        edition_id: str | None = None,
        include_deleted: bool = False,
    ) -> list[DocumentRecord]:
        with self._read() as conn:
            if library_id is not None:
                library = self._library_row(conn, library_id)
                if library is None:
                    raise _not_found("逻辑库不存在。", code="LIBRARY_NOT_FOUND")
                if library["deleted_at"] is not None:
                    return []
                rows = conn.execute(
                    "SELECT d.* FROM library_documents AS ld "
                    "JOIN documents AS d ON d.id = ld.document_id "
                    "WHERE ld.library_id = ? ORDER BY d.rowid ASC",
                    (library_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM documents ORDER BY rowid ASC").fetchall()
            records: list[DocumentRecord] = []
            for row in rows:
                if not include_deleted and row["deleted_at"] is not None:
                    continue
                # 分类过滤走当前元数据修订；损坏的 grade_ids_json 在此抛 CATALOG_CORRUPT
                record = self._build_document_record(conn, row)
                if grade_id is not None and grade_id not in record.grade_ids:
                    continue
                if subject_id is not None and record.subject_id != subject_id:
                    continue
                if edition_id is not None and record.edition_id != edition_id:
                    continue
                records.append(record)
            return records

    def update_document_metadata(
        self,
        document_id: str,
        *,
        expected_revision: int,
        title: str,
        stage_id: str,
        grade_ids: Sequence[str],
        subject_id: str,
        edition_id: str,
        publication_label: str = "",
        volume_label: str = "",
        library_ids: Sequence[str] | None = None,
    ) -> DocumentRecord:
        document_id = _text(document_id, field="document_id")
        title = _text(title, field="title")
        stage_id = _text(stage_id, field="stage_id")
        subject_id = _text(subject_id, field="subject_id")
        edition_id = _text(edition_id, field="edition_id")
        grade_ids = _unique_texts(grade_ids, field="grade_ids")
        publication_label = _text_or_empty(publication_label, field="publication_label")
        volume_label = _text_or_empty(volume_label, field="volume_label")
        target_libraries: tuple[str, ...] | None = None
        if library_ids is not None:
            target_libraries = _unique_texts(library_ids, field="library_ids")
        with self._write() as conn:
            row = self._require_document_row(conn, document_id, live=True)
            self._check_revision(row["revision"], expected_revision, what="书册")
            if target_libraries is not None:
                for library_id in target_libraries:
                    self._live_library_row(conn, library_id)
            metadata_revision_id = uuid.uuid4().hex
            # 旧元数据修订保留原样，分类变更只追加新修订
            self._insert_metadata_revision(
                conn,
                metadata_revision_id=metadata_revision_id,
                document_id=document_id,
                title=title,
                stage_id=stage_id,
                grade_ids=grade_ids,
                subject_id=subject_id,
                edition_id=edition_id,
                publication_label=publication_label,
                volume_label=volume_label,
            )
            conn.execute(
                "UPDATE documents SET current_metadata_revision_id = ?, revision = revision + 1 "
                "WHERE id = ?",
                (metadata_revision_id, document_id),
            )
            if target_libraries is not None:
                conn.execute("DELETE FROM library_documents WHERE document_id = ?", (document_id,))
                for library_id in target_libraries:
                    conn.execute(
                        "INSERT OR IGNORE INTO library_documents (library_id, document_id) "
                        "VALUES (?, ?)",
                        (library_id, document_id),
                    )
            self._touch_catalog(conn)
            return self._document_record(conn, document_id)

    def delete_document(self, document_id: str, *, expected_revision: int) -> None:
        document_id = _text(document_id, field="document_id")
        with self._write() as conn:
            row = self._require_document_row(conn, document_id, live=True)
            self._check_revision(row["revision"], expected_revision, what="书册")
            # 先逻辑删除并递增目录版本，再入清理队列；current_revision_id 保持原值
            conn.execute(
                "UPDATE documents SET deleted_at = ?, revision = revision + 1 WHERE id = ?",
                (now_iso(), document_id),
            )
            conn.execute(
                "INSERT INTO cleanup_queue (document_id, enqueued_at, attempts) VALUES (?, ?, 0) "
                "ON CONFLICT(document_id) DO NOTHING",
                (document_id, now_iso()),
            )
            self._touch_catalog(conn)

    def find_document_by_origin_key(self, owner_id: str, origin_key: str) -> DocumentRecord | None:
        owner_id = _choice(owner_id, field="owner_id", allowed=OWNER_IDS)
        origin_key = _text(origin_key, field="origin_key")
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE owner_id = ? AND origin_key = ?",
                (owner_id, origin_key),
            ).fetchone()
            if row is None:
                return None
            # 已逻辑删除的书册同样返回：来源键唯一性把删除行也算在内
            return self._build_document_record(conn, row)

    def document_ids_in_any_library(self, document_id: str) -> list[str]:
        document_id = _text(document_id, field="document_id")
        with self._read() as conn:
            self._require_document_row(conn, document_id, live=False)
            rows = conn.execute(
                "SELECT l.id AS library_id FROM library_documents AS ld "
                "JOIN libraries AS l ON l.id = ld.library_id "
                "WHERE ld.document_id = ? AND l.deleted_at IS NULL ORDER BY l.id ASC",
                (document_id,),
            ).fetchall()
            return [row["library_id"] for row in rows]

    # ------------------------------------------------------------ 修订

    def create_document_revision(
        self,
        document_id: str,
        *,
        original_file_sha256: str,
        normalized_text_sha256: str,
        parser_version: str,
        original_blob_id: str,
        normalized_blob_id: str,
        source_map_blob_id: str,
        char_count: int,
    ) -> RevisionRecord:
        document_id = _text(document_id, field="document_id")
        original_file_sha256 = _text(original_file_sha256, field="original_file_sha256")
        normalized_text_sha256 = _text(normalized_text_sha256, field="normalized_text_sha256")
        parser_version = _text(parser_version, field="parser_version")
        original_blob_id = _text(original_blob_id, field="original_blob_id")
        normalized_blob_id = _text(normalized_blob_id, field="normalized_blob_id")
        source_map_blob_id = _text(source_map_blob_id, field="source_map_blob_id")
        char_count = _count(char_count, field="char_count", minimum=0)
        revision_id = uuid.uuid4().hex
        with self._write() as conn:
            self._require_document_row(conn, document_id, live=True)
            conn.execute(
                "INSERT INTO document_revisions (id, document_id, original_file_sha256, "
                "normalized_text_sha256, parser_version, original_blob_id, normalized_blob_id, "
                "source_map_blob_id, char_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    revision_id,
                    document_id,
                    original_file_sha256,
                    normalized_text_sha256,
                    parser_version,
                    original_blob_id,
                    normalized_blob_id,
                    source_map_blob_id,
                    char_count,
                    now_iso(),
                ),
            )
            # 新修订在 publish_document_revision 之前不进入任何范围，也不递增目录版本
            row = conn.execute("SELECT * FROM document_revisions WHERE id = ?", (revision_id,)).fetchone()
            return self._revision_record(row)

    def get_revision(self, revision_id: str) -> RevisionRecord | None:
        revision_id = _text(revision_id, field="revision_id")
        row = self._read_one(
            "SELECT * FROM document_revisions WHERE id = ?", (revision_id,)
        )
        return self._revision_record(row) if row is not None else None

    def list_document_revisions(self, document_id: str) -> list[RevisionRecord]:
        document_id = _text(document_id, field="document_id")
        rows = self._read_all(
            "SELECT * FROM document_revisions WHERE document_id = ? ORDER BY rowid ASC",
            (document_id,),
        )
        return [self._revision_record(row) for row in rows]

    def publish_document_revision(
        self,
        document_id: str,
        *,
        revision_id: str,
        metadata_revision_id: str,
        expected_document_revision: int | None = None,
    ) -> DocumentRecord:
        document_id = _text(document_id, field="document_id")
        revision_id = _text(revision_id, field="revision_id")
        metadata_revision_id = _text(metadata_revision_id, field="metadata_revision_id")
        with self._write() as conn:
            row = self._require_document_row(conn, document_id, live=True)
            if expected_document_revision is not None:
                self._check_revision(row["revision"], expected_document_revision, what="书册")
            revision = conn.execute(
                "SELECT id FROM document_revisions WHERE id = ? AND document_id = ?",
                (revision_id, document_id),
            ).fetchone()
            if revision is None:
                raise _invalid("修订不存在或不属于该教材。")
            metadata = conn.execute(
                "SELECT id FROM document_metadata_revisions WHERE id = ? AND document_id = ?",
                (metadata_revision_id, document_id),
            ).fetchone()
            if metadata is None:
                raise _invalid("元数据修订不存在或不属于该教材。")
            conn.execute(
                "UPDATE documents SET current_revision_id = ?, current_metadata_revision_id = ?, "
                "revision = revision + 1 WHERE id = ?",
                (revision_id, metadata_revision_id, document_id),
            )
            self._touch_catalog(conn)
            return self._document_record(conn, document_id)

    def get_metadata_revision(self, metadata_revision_id: str) -> MetadataRevisionRecord | None:
        metadata_revision_id = _text(metadata_revision_id, field="metadata_revision_id")
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM document_metadata_revisions WHERE id = ?", (metadata_revision_id,)
            ).fetchone()
        return self._metadata_record(row) if row is not None else None

    def current_metadata_revision(self, document_id: str) -> MetadataRevisionRecord:
        document_id = _text(document_id, field="document_id")
        with self._read() as conn:
            self._require_document_row(conn, document_id, live=False)
            return self._metadata_record_for_document(conn, document_id)

    # ------------------------------------------------------------ 分块

    def create_chunk_set(
        self,
        document_revision_id: str,
        *,
        policy_fingerprint: str,
        manifest_sha256: str,
        chunks: Sequence[ChunkInput],
    ) -> ChunkSetRecord:
        document_revision_id = _text(document_revision_id, field="document_revision_id")
        policy_fingerprint = _text(policy_fingerprint, field="policy_fingerprint")
        manifest_sha256 = _text(manifest_sha256, field="manifest_sha256")
        normalized = _validate_chunks(chunks)
        with self._write() as conn:
            revision = conn.execute(
                "SELECT id FROM document_revisions WHERE id = ?", (document_revision_id,)
            ).fetchone()
            if revision is None:
                raise _not_found("文档修订不存在。", code="REVISION_NOT_FOUND")
            existing = conn.execute(
                "SELECT * FROM chunk_sets WHERE document_revision_id = ? AND policy_fingerprint = ?",
                (document_revision_id, policy_fingerprint),
            ).fetchone()
            if existing is not None:
                # 同一修订 + 同一策略是同一分块集：内容一致时重放返回既有集，否则拒绝覆盖
                if existing["manifest_sha256"] == manifest_sha256 and existing["chunk_count"] == len(normalized):
                    return self._chunk_set_record(existing)
                raise _conflict(
                    "同一修订与分块策略已存在内容不同的分块集，拒绝覆盖。",
                    code="IDEMPOTENCY_CONFLICT",
                )
            chunk_set_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO chunk_sets (id, document_revision_id, policy_fingerprint, "
                "manifest_sha256, chunk_count, sealed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    chunk_set_id,
                    document_revision_id,
                    policy_fingerprint,
                    manifest_sha256,
                    len(normalized),
                    now_iso(),
                ),
            )
            conn.executemany(
                "INSERT INTO chunks (chunk_set_id, ordinal, char_start, char_end, region, "
                "chapter_path_json, text_sha256, legacy_chunk_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        chunk_set_id,
                        chunk.ordinal,
                        chunk.char_start,
                        chunk.char_end,
                        chunk.region,
                        json_fields.write_string_list(list(chunk.chapter_path), field="chapter_path"),
                        chunk.text_sha256,
                        chunk.legacy_chunk_id,
                    )
                    for chunk in normalized
                ],
            )
            row = conn.execute("SELECT * FROM chunk_sets WHERE id = ?", (chunk_set_id,)).fetchone()
            return self._chunk_set_record(row)

    def get_chunk_set(self, chunk_set_id: str) -> ChunkSetRecord | None:
        chunk_set_id = _text(chunk_set_id, field="chunk_set_id")
        row = self._read_one(
            "SELECT * FROM chunk_sets WHERE id = ?", (chunk_set_id,)
        )
        return self._chunk_set_record(row) if row is not None else None

    def find_chunk_set(self, document_revision_id: str, policy_fingerprint: str) -> ChunkSetRecord | None:
        document_revision_id = _text(document_revision_id, field="document_revision_id")
        policy_fingerprint = _text(policy_fingerprint, field="policy_fingerprint")
        row = self._read_one(
            "SELECT * FROM chunk_sets WHERE document_revision_id = ? AND policy_fingerprint = ?",
            (document_revision_id, policy_fingerprint),
        )
        return self._chunk_set_record(row) if row is not None else None

    def list_chunks(self, chunk_set_id: str) -> list[ChunkRecord]:
        chunk_set_id = _text(chunk_set_id, field="chunk_set_id")
        rows = self._read_all(
            "SELECT * FROM chunks WHERE chunk_set_id = ? ORDER BY ordinal ASC", (chunk_set_id,)
        )
        return [self._chunk_record(row) for row in rows]

    def get_chunk(self, chunk_set_id: str, ordinal: int) -> ChunkRecord | None:
        chunk_set_id = _text(chunk_set_id, field="chunk_set_id")
        ordinal = _count(ordinal, field="ordinal", minimum=0)
        row = self._read_one(
            "SELECT * FROM chunks WHERE chunk_set_id = ? AND ordinal = ?", (chunk_set_id, ordinal)
        )
        return self._chunk_record(row) if row is not None else None

    # ------------------------------------------------------------ 索引代

    def create_generation(
        self,
        *,
        profile_id: str,
        collection_name: str,
        chunk_policy_json: object,
        state: str = "building",
    ) -> GenerationRecord:
        profile_id = _text(profile_id, field="profile_id")
        collection_name = _text(collection_name, field="collection_name")
        state = _choice(state, field="state", allowed=GENERATION_STATES)
        policy = json_fields.write_object(chunk_policy_json, field="chunk_policy_json")
        generation_id = uuid.uuid4().hex
        now = now_iso()
        with self._write() as conn:
            profile = conn.execute(
                "SELECT id FROM embedding_profiles WHERE id = ?", (profile_id,)
            ).fetchone()
            if profile is None:
                raise _not_found("Embedding 配置不存在。", code="PROFILE_NOT_FOUND")
            duplicate = conn.execute(
                "SELECT id FROM index_generations WHERE collection_name = ?", (collection_name,)
            ).fetchone()
            if duplicate is not None:
                raise _conflict("collection 名称已被其他索引代占用。", code="COLLECTION_CONFLICT")
            conn.execute(
                "INSERT INTO index_generations (id, profile_id, collection_name, chunk_policy_json, "
                "state, created_at, published_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    generation_id,
                    profile_id,
                    collection_name,
                    policy,
                    state,
                    now,
                    now if state == "ready" else None,
                ),
            )
            return self._generation_record(self._generation_row(conn, generation_id))

    def get_generation(self, generation_id: str) -> GenerationRecord | None:
        generation_id = _text(generation_id, field="generation_id")
        with self._read() as conn:
            row = self._generation_row(conn, generation_id)
        return self._generation_record(row) if row is not None else None

    def list_generations(self) -> list[GenerationRecord]:
        rows = self._read_all(
            "SELECT * FROM index_generations ORDER BY created_at DESC, rowid DESC"
        )
        return [self._generation_record(row) for row in rows]

    def update_generation_state(self, generation_id: str, state: str) -> None:
        generation_id = _text(generation_id, field="generation_id")
        state = _choice(state, field="state", allowed=GENERATION_STATES)
        with self._write() as conn:
            self._require_generation_row(conn, generation_id)
            conn.execute("UPDATE index_generations SET state = ? WHERE id = ?", (state, generation_id))

    def publish_generation(self, generation_id: str) -> None:
        generation_id = _text(generation_id, field="generation_id")
        with self._write() as conn:
            row = self._require_generation_row(conn, generation_id)
            if row["state"] == "aborted":
                raise _conflict("已终止的索引代不能发布。", code="GENERATION_ABORTED")
            if row["state"] != "ready":
                conn.execute(
                    "UPDATE index_generations SET state = 'ready', published_at = ? WHERE id = ?",
                    (now_iso(), generation_id),
                )
            # 已经 ready 时不改写 published_at：发布是幂等的

    def upsert_generation_revision(
        self,
        generation_id: str,
        document_revision_id: str,
        chunk_set_id: str,
        *,
        state: str,
        expected_chunk_count: int,
        manifest_sha256: str,
    ) -> None:
        generation_id = _text(generation_id, field="generation_id")
        document_revision_id = _text(document_revision_id, field="document_revision_id")
        chunk_set_id = _text(chunk_set_id, field="chunk_set_id")
        state = _choice(state, field="state", allowed=GENERATION_REVISION_STATES)
        expected_chunk_count = _count(expected_chunk_count, field="expected_chunk_count", minimum=0)
        manifest_sha256 = manifest_sha256 if isinstance(manifest_sha256, str) else None
        if manifest_sha256 is None:
            raise _invalid("manifest_sha256 必须是字符串。")
        with self._write() as conn:
            self._require_generation_row(conn, generation_id)
            if conn.execute(
                "SELECT id FROM document_revisions WHERE id = ?", (document_revision_id,)
            ).fetchone() is None:
                raise _not_found("文档修订不存在。", code="REVISION_NOT_FOUND")
            if conn.execute("SELECT id FROM chunk_sets WHERE id = ?", (chunk_set_id,)).fetchone() is None:
                raise _not_found("分块集不存在。", code="CHUNK_SET_NOT_FOUND")
            conn.execute(
                "INSERT INTO generation_revisions (generation_id, document_revision_id, chunk_set_id, "
                "state, expected_chunk_count, manifest_sha256) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(generation_id, document_revision_id) DO UPDATE SET "
                "chunk_set_id = excluded.chunk_set_id, state = excluded.state, "
                "expected_chunk_count = excluded.expected_chunk_count, "
                "manifest_sha256 = excluded.manifest_sha256",
                (
                    generation_id,
                    document_revision_id,
                    chunk_set_id,
                    state,
                    expected_chunk_count,
                    manifest_sha256,
                ),
            )

    def set_generation_revision_state(
        self, generation_id: str, document_revision_id: str, state: str
    ) -> None:
        generation_id = _text(generation_id, field="generation_id")
        document_revision_id = _text(document_revision_id, field="document_revision_id")
        state = _choice(state, field="state", allowed=GENERATION_REVISION_STATES)
        with self._write() as conn:
            row = conn.execute(
                "SELECT generation_id FROM generation_revisions WHERE generation_id = ? "
                "AND document_revision_id = ?",
                (generation_id, document_revision_id),
            ).fetchone()
            if row is None:
                raise _not_found("索引代修订记录不存在。", code="GENERATION_REVISION_NOT_FOUND")
            conn.execute(
                "UPDATE generation_revisions SET state = ? WHERE generation_id = ? "
                "AND document_revision_id = ?",
                (state, generation_id, document_revision_id),
            )

    def list_generation_revisions(self, generation_id: str) -> list[GenerationRevisionRecord]:
        generation_id = _text(generation_id, field="generation_id")
        rows = self._read_all(
            "SELECT * FROM generation_revisions WHERE generation_id = ? ORDER BY document_revision_id ASC",
            (generation_id,),
        )
        return [self._generation_revision_record(row) for row in rows]

    def generation_chunk_total(self, generation_id: str) -> int:
        generation_id = _text(generation_id, field="generation_id")
        row = self._read_one(
            "SELECT COALESCE(SUM(expected_chunk_count), 0) AS total FROM generation_revisions "
            "WHERE generation_id = ? AND state = 'ready'",
            (generation_id,),
        )
        return int(row["total"])

    # ------------------------------------------------------------ Embedding 配置

    def create_embedding_profile(
        self,
        *,
        fingerprint: str,
        adapter: str,
        native_base_url: str,
        model_name: str,
        model_manifest_digest: str,
        dimensions: int,
        distance: str,
        query_prefix: str,
        document_prefix: str,
        normalization: str,
        options_json: object = "{}",
    ) -> ProfileRecord:
        fingerprint = _text(fingerprint, field="fingerprint")
        adapter = _choice(adapter, field="adapter", allowed=frozenset({"ollama"}))
        native_base_url = _text(native_base_url, field="native_base_url")
        model_name = _text(model_name, field="model_name")
        model_manifest_digest = _text(model_manifest_digest, field="model_manifest_digest")
        dimensions = _count(dimensions, field="dimensions", minimum=1)
        distance = _choice(distance, field="distance", allowed=frozenset({"cosine"}))
        query_prefix = _text_or_empty(query_prefix, field="query_prefix")
        document_prefix = _text_or_empty(document_prefix, field="document_prefix")
        normalization = _choice(normalization, field="normalization", allowed=NORMALIZATIONS)
        options = json_fields.write_object(options_json, field="options_json")
        profile_id = uuid.uuid4().hex
        with self._write() as conn:
            existing = conn.execute(
                "SELECT id FROM embedding_profiles WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if existing is not None:
                raise _conflict(
                    "相同指纹的 Embedding 配置已存在。", code="PROFILE_CONFLICT"
                )
            conn.execute(
                "INSERT INTO embedding_profiles (id, fingerprint, adapter, native_base_url, model_name, "
                "model_manifest_digest, dimensions, distance, query_prefix, document_prefix, "
                "normalization, options_json, verified_at, retired_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                (
                    profile_id,
                    fingerprint,
                    adapter,
                    native_base_url,
                    model_name,
                    model_manifest_digest,
                    dimensions,
                    distance,
                    query_prefix,
                    document_prefix,
                    normalization,
                    options,
                    now_iso(),
                ),
            )
            row = conn.execute("SELECT * FROM embedding_profiles WHERE id = ?", (profile_id,)).fetchone()
            return self._profile_record(row)

    def find_embedding_profile(self, fingerprint: str) -> ProfileRecord | None:
        fingerprint = _text(fingerprint, field="fingerprint")
        row = self._read_one(
            "SELECT * FROM embedding_profiles WHERE fingerprint = ?", (fingerprint,)
        )
        return self._profile_record(row) if row is not None else None

    def get_embedding_profile(self, profile_id: str) -> ProfileRecord | None:
        profile_id = _text(profile_id, field="profile_id")
        row = self._read_one(
            "SELECT * FROM embedding_profiles WHERE id = ?", (profile_id,)
        )
        return self._profile_record(row) if row is not None else None

    def list_embedding_profiles(self) -> list[ProfileRecord]:
        rows = self._read_all(
            "SELECT * FROM embedding_profiles ORDER BY verified_at ASC, rowid ASC"
        )
        return [self._profile_record(row) for row in rows]

    def retire_embedding_profile(self, profile_id: str) -> ProfileRecord:
        """软停用：``retired_at`` 为空才写入，重复停用幂等；存在性检查与写入在同一写事务。"""
        profile_id = _text(profile_id, field="profile_id")
        with self._write() as conn:
            row = conn.execute(
                "SELECT id, retired_at FROM embedding_profiles WHERE id = ?", (profile_id,)
            ).fetchone()
            if row is None:
                raise _not_found("Embedding 配置不存在。", code="PROFILE_NOT_FOUND")
            if row["retired_at"] is None:
                conn.execute(
                    "UPDATE embedding_profiles SET retired_at = ? WHERE id = ?",
                    (now_iso(), profile_id),
                )
            updated = conn.execute(
                "SELECT * FROM embedding_profiles WHERE id = ?", (profile_id,)
            ).fetchone()
            return self._profile_record(updated)

    def delete_embedding_profile(self, profile_id: str) -> None:
        """硬删：仅允许从未被任何索引代引用的配置；存在性 + 引用检查 + 删除在同一写事务内完成。"""
        profile_id = _text(profile_id, field="profile_id")
        with self._write() as conn:
            row = conn.execute(
                "SELECT id FROM embedding_profiles WHERE id = ?", (profile_id,)
            ).fetchone()
            if row is None:
                raise _not_found("Embedding 配置不存在。", code="PROFILE_NOT_FOUND")
            referenced = conn.execute(
                "SELECT COUNT(*) FROM index_generations WHERE profile_id = ?", (profile_id,)
            ).fetchone()[0]
            if referenced:
                raise _conflict(
                    "该配置已被索引代使用，请改用停用。",
                    code="EMBEDDING_PROFILE_IN_USE",
                )
            conn.execute("DELETE FROM embedding_profiles WHERE id = ?", (profile_id,))

    # ------------------------------------------------------------ 索引任务

    def create_job(
        self,
        *,
        kind: str,
        idempotency_key: str,
        request_fingerprint: str,
        input_revision_id: str | None = None,
        document_id: str | None = None,
        metadata_revision_id: str | None = None,
        target_generation_id: str | None = None,
        base_generation_id: str | None = None,
        state: str = "queued",
    ) -> JobRecord:
        kind = _choice(kind, field="kind", allowed=JOB_KINDS)
        idempotency_key = _text(idempotency_key, field="idempotency_key")
        if len(idempotency_key) > 200:
            raise _invalid("idempotency_key 不能超过 200 字符。")
        request_fingerprint = _text_or_empty(request_fingerprint, field="request_fingerprint")
        state = _choice(state, field="state", allowed=JOB_STATES)
        input_revision_id = _optional_text(input_revision_id, field="input_revision_id")
        document_id = _optional_text(document_id, field="document_id")
        metadata_revision_id = _optional_text(metadata_revision_id, field="metadata_revision_id")
        target_generation_id = _optional_text(target_generation_id, field="target_generation_id")
        base_generation_id = _optional_text(base_generation_id, field="base_generation_id")
        job_id = uuid.uuid4().hex
        now = now_iso()
        with self._write() as conn:
            existing = conn.execute(
                "SELECT * FROM index_jobs WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if existing is not None:
                # 同键同载荷返回既有任务；同键不同载荷拒绝，避免把新请求接到旧任务上
                if existing["request_fingerprint"] == request_fingerprint:
                    return self._job_record(existing)
                raise _conflict(
                    "同一幂等键已登记不同载荷的任务。", code="IDEMPOTENCY_CONFLICT"
                )
            if input_revision_id is not None and conn.execute(
                "SELECT id FROM document_revisions WHERE id = ?", (input_revision_id,)
            ).fetchone() is None:
                raise _not_found("文档修订不存在。", code="REVISION_NOT_FOUND")
            if document_id is not None:
                self._require_document_row(conn, document_id, live=False)
            if metadata_revision_id is not None and conn.execute(
                "SELECT id FROM document_metadata_revisions WHERE id = ?", (metadata_revision_id,)
            ).fetchone() is None:
                raise _not_found("元数据修订不存在。", code="METADATA_REVISION_NOT_FOUND")
            for generation_id in (target_generation_id, base_generation_id):
                if generation_id is not None:
                    self._require_generation_row(conn, generation_id)
            conn.execute(
                "INSERT INTO index_jobs (id, kind, input_revision_id, document_id, metadata_revision_id, "
                "target_generation_id, base_generation_id, state, idempotency_key, request_fingerprint, "
                "attempt, lease_token, lease_until, checkpoint_json, error_code, error_message, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL, '{}', "
                "NULL, NULL, ?, ?)",
                (
                    job_id,
                    kind,
                    input_revision_id,
                    document_id,
                    metadata_revision_id,
                    target_generation_id,
                    base_generation_id,
                    state,
                    idempotency_key,
                    request_fingerprint,
                    now,
                    now,
                ),
            )
            return self._job_record(self._job_row(conn, job_id))

    def find_job_by_key(self, idempotency_key: str) -> JobRecord | None:
        idempotency_key = _text(idempotency_key, field="idempotency_key")
        row = self._read_one(
            "SELECT * FROM index_jobs WHERE idempotency_key = ?", (idempotency_key,)
        )
        return self._job_record(row) if row is not None else None

    def get_job(self, job_id: str) -> JobRecord | None:
        job_id = _text(job_id, field="job_id")
        with self._read() as conn:
            row = self._job_row(conn, job_id)
        return self._job_record(row) if row is not None else None

    def list_jobs(
        self,
        *,
        kinds: Sequence[str] | None = None,
        states: Sequence[str] | None = None,
        limit: int = 50,
    ) -> list[JobRecord]:
        limit = _count(limit, field="limit", minimum=1)
        if limit > 500:
            raise _invalid("limit 不能超过 500。")
        clauses: list[str] = []
        params: list[object] = []
        if kinds is not None:
            kind_values = [_choice(kind, field="kinds", allowed=JOB_KINDS) for kind in kinds]
            if kind_values:
                clauses.append(f"kind IN ({', '.join('?' for _ in kind_values)})")
                params.extend(kind_values)
        if states is not None:
            state_values = [_choice(state, field="states", allowed=JOB_STATES) for state in states]
            if state_values:
                clauses.append(f"state IN ({', '.join('?' for _ in state_values)})")
                params.extend(state_values)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self._read_all(
            f"SELECT * FROM index_jobs{where} ORDER BY created_at DESC, rowid DESC LIMIT ?", params
        )
        return [self._job_record(row) for row in rows]

    def has_active_ingest_jobs(self) -> bool:
        row = self._read_one(
            "SELECT 1 AS present FROM index_jobs WHERE kind = 'ingest' "
            "AND state IN ('queued', 'running') LIMIT 1"
        )
        return row is not None

    def claim_job(self, job_id: str, *, lease_seconds: int = 90) -> JobRecord:
        job_id = _text(job_id, field="job_id")
        lease_seconds = _count(lease_seconds, field="lease_seconds", minimum=1)
        if lease_seconds > 86400:
            raise _invalid("lease_seconds 不能超过 86400。")
        now = now_iso()
        with self._write() as conn:
            row = self._require_job_row(conn, job_id)
            if row["state"] == "queued":
                pass
            elif row["state"] == "running":
                if row["lease_until"] is not None and row["lease_until"] > now:
                    raise _conflict(
                        "任务仍在其他执行者的租约内。", code="JOB_BUSY", retryable=True
                    )
            else:
                raise _conflict("任务已结束，不能再次领取。", code="JOB_NOT_CLAIMABLE")
            conn.execute(
                "UPDATE index_jobs SET state = 'running', attempt = attempt + 1, lease_token = ?, "
                "lease_until = ?, updated_at = ? WHERE id = ?",
                (uuid.uuid4().hex, _lease_deadline(lease_seconds), now, job_id),
            )
            return self._job_record(self._job_row(conn, job_id))

    def renew_lease(self, job_id: str, *, lease_token: str, lease_seconds: int = 90) -> bool:
        job_id = _text(job_id, field="job_id")
        lease_token = _text(lease_token, field="lease_token")
        lease_seconds = _count(lease_seconds, field="lease_seconds", minimum=1)
        if lease_seconds > 86400:
            raise _invalid("lease_seconds 不能超过 86400。")
        now = now_iso()
        with self._write() as conn:
            row = self._job_row(conn, job_id)
            if row is None or not self._lease_matches(row, lease_token, now):
                return False
            conn.execute(
                "UPDATE index_jobs SET lease_until = ?, updated_at = ? WHERE id = ?",
                (_lease_deadline(lease_seconds), now, job_id),
            )
            return True

    def require_lease(self, job_id: str, lease_token: str) -> JobRecord:
        job_id = _text(job_id, field="job_id")
        lease_token = _text(lease_token, field="lease_token")
        now = now_iso()
        with self._read() as conn:
            row = self._require_job_row(conn, job_id)
            if not self._lease_matches(row, lease_token, now):
                raise _conflict("任务租约已失效，请重新认领。", code="LEASE_LOST")
            return self._job_record(row)

    def checkpoint_job(self, job_id: str, *, lease_token: str, checkpoint: dict) -> None:
        job_id = _text(job_id, field="job_id")
        lease_token = _text(lease_token, field="lease_token")
        if not isinstance(checkpoint, dict):
            raise _invalid("checkpoint 必须是 JSON 对象。")
        payload = json_fields.write_object(checkpoint, field="checkpoint")
        now = now_iso()
        with self._write() as conn:
            row = self._require_job_row(conn, job_id)
            if not self._lease_matches(row, lease_token, now):
                raise _conflict("任务租约已失效，请重新认领。", code="LEASE_LOST")
            conn.execute(
                "UPDATE index_jobs SET checkpoint_json = ?, updated_at = ? WHERE id = ?",
                (payload, now, job_id),
            )

    def finish_job(
        self,
        job_id: str,
        *,
        lease_token: str,
        state: str,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> JobRecord:
        job_id = _text(job_id, field="job_id")
        lease_token = _text(lease_token, field="lease_token")
        state = _choice(state, field="state", allowed=JOB_FINAL_STATES)
        error_code = _optional_text(error_code, field="error_code")
        if error_message is not None and not isinstance(error_message, str):
            raise _invalid("error_message 必须是字符串。")
        now = now_iso()
        with self._write() as conn:
            row = self._require_job_row(conn, job_id)
            if not self._lease_matches(row, lease_token, now):
                raise _conflict("任务租约已失效，请重新认领。", code="LEASE_LOST")
            conn.execute(
                "UPDATE index_jobs SET state = ?, error_code = ?, error_message = ?, lease_token = NULL, "
                "lease_until = NULL, updated_at = ? WHERE id = ?",
                (state, error_code, error_message, now, job_id),
            )
            return self._job_record(self._job_row(conn, job_id))

    def first_recoverable_job(self) -> JobRecord | None:
        now = now_iso()
        row = self._read_one(
            "SELECT * FROM index_jobs WHERE state = 'queued' OR (state = 'running' AND "
            "(lease_until IS NULL OR lease_until <= ?)) ORDER BY created_at ASC, rowid ASC LIMIT 1",
            (now,),
        )
        return self._job_record(row) if row is not None else None

    # ------------------------------------------------------------ 导入草稿

    def create_import(
        self,
        *,
        owner_id: str,
        uploaded_file_name: str,
        uploaded_bytes: int,
        uploaded_blob_id: str,
        target_document_id: str | None = None,
        expected_current_revision_id: str | None = None,
        metadata_json: object = None,
        parsed_artifacts_json: object = None,
        warnings: Sequence[str] = (),
        state: str = "uploaded",
    ) -> ImportRecord:
        owner_id = _choice(owner_id, field="owner_id", allowed=OWNER_IDS)
        uploaded_file_name = _text(uploaded_file_name, field="uploaded_file_name")
        uploaded_bytes = _count(uploaded_bytes, field="uploaded_bytes", minimum=0)
        uploaded_blob_id = _text(uploaded_blob_id, field="uploaded_blob_id")
        target_document_id = _optional_text(target_document_id, field="target_document_id")
        expected_current_revision_id = _optional_text(
            expected_current_revision_id, field="expected_current_revision_id"
        )
        state = _choice(state, field="state", allowed=IMPORT_STATES)
        metadata = json_fields.write_object(metadata_json, field="metadata_json", allow_none=True)
        artifacts = json_fields.write_object(
            parsed_artifacts_json, field="parsed_artifacts_json", allow_none=True
        )
        warnings_json = json_fields.write_string_list(list(warnings), field="warnings_json")
        import_id = uuid.uuid4().hex
        now = now_iso()
        with self._write() as conn:
            if target_document_id is not None:
                self._require_document_row(conn, target_document_id, live=False)
            if expected_current_revision_id is not None and conn.execute(
                "SELECT id FROM document_revisions WHERE id = ?", (expected_current_revision_id,)
            ).fetchone() is None:
                raise _not_found("文档修订不存在。", code="REVISION_NOT_FOUND")
            conn.execute(
                "INSERT INTO import_drafts (id, owner_id, target_document_id, "
                "expected_current_revision_id, metadata_json, uploaded_blob_id, uploaded_file_name, "
                "uploaded_bytes, parsed_artifacts_json, state, revision, warnings_json, error_code, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?)",
                (
                    import_id,
                    owner_id,
                    target_document_id,
                    expected_current_revision_id,
                    metadata,
                    uploaded_blob_id,
                    uploaded_file_name,
                    uploaded_bytes,
                    artifacts,
                    state,
                    warnings_json,
                    now,
                    now,
                ),
            )
            return self._import_record(self._import_row(conn, import_id))

    def get_import(self, import_id: str) -> ImportRecord | None:
        import_id = _text(import_id, field="import_id")
        with self._read() as conn:
            row = self._import_row(conn, import_id)
        return self._import_record(row) if row is not None else None

    def list_imports(self, *, target_document_id: str | None = None, limit: int = 50) -> list[ImportRecord]:
        limit = _count(limit, field="limit", minimum=1)
        if limit > 500:
            raise _invalid("limit 不能超过 500。")
        clauses: list[str] = []
        params: list[object] = []
        if target_document_id is not None:
            clauses.append("target_document_id = ?")
            params.append(_text(target_document_id, field="target_document_id"))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self._read_all(
            f"SELECT * FROM import_drafts{where} ORDER BY created_at DESC, rowid DESC LIMIT ?",
            params,
        )
        return [self._import_record(row) for row in rows]

    def update_import(self, import_id: str, *, expected_revision: int, **fields: object) -> ImportRecord:
        import_id = _text(import_id, field="import_id")
        allowed = {
            "state",
            "metadata_json",
            "parsed_artifacts_json",
            "warnings_json",
            "error_code",
            "uploaded_blob_id",
            "uploaded_file_name",
            "uploaded_bytes",
        }
        unknown = sorted(set(fields) - allowed)
        if unknown:
            raise _invalid(f"不允许更新的字段：{', '.join(unknown)}。")
        updates: dict[str, object] = {}
        if "state" in fields:
            updates["state"] = _choice(fields["state"], field="state", allowed=IMPORT_STATES)
        if "metadata_json" in fields:
            updates["metadata_json"] = json_fields.write_object(
                fields["metadata_json"], field="metadata_json", allow_none=True
            )
        if "parsed_artifacts_json" in fields:
            updates["parsed_artifacts_json"] = json_fields.write_object(
                fields["parsed_artifacts_json"], field="parsed_artifacts_json", allow_none=True
            )
        if "warnings_json" in fields:
            updates["warnings_json"] = json_fields.write_string_list(
                fields["warnings_json"], field="warnings_json"
            )
        if "error_code" in fields:
            updates["error_code"] = _optional_text(fields["error_code"], field="error_code")
        if "uploaded_blob_id" in fields:
            updates["uploaded_blob_id"] = _text(fields["uploaded_blob_id"], field="uploaded_blob_id")
        if "uploaded_file_name" in fields:
            updates["uploaded_file_name"] = _text(
                fields["uploaded_file_name"], field="uploaded_file_name"
            )
        if "uploaded_bytes" in fields:
            updates["uploaded_bytes"] = _count(
                fields["uploaded_bytes"], field="uploaded_bytes", minimum=0
            )
        with self._write() as conn:
            row = self._require_import_row(conn, import_id)
            self._check_revision(row["revision"], expected_revision, what="导入草稿")
            if updates:
                assignments = ", ".join(f"{column} = ?" for column in updates)
                conn.execute(
                    f"UPDATE import_drafts SET {assignments}, revision = revision + 1, updated_at = ? "
                    "WHERE id = ?",
                    (*updates.values(), now_iso(), import_id),
                )
            return self._import_record(self._import_row(conn, import_id))

    def set_import_state(
        self,
        import_id: str,
        *,
        state: str,
        error_code: str | None = None,
        expected_revision: int | None = None,
    ) -> ImportRecord:
        """单独推进草稿状态（放弃等状态迁移用）：同事务内先比 revision 再写。

        与 ``update_import`` 的区别是 ``expected_revision`` 可选：状态迁移的乐观锁由
        服务层在读取快照上判断后传入，写入前在同一事务内复核（CAS），并发编辑不会
        被静默覆盖；其余校验（state 合法性、行存在、递增 revision、更新时间）一致。
        """
        state = _choice(state, field="state", allowed=IMPORT_STATES)
        error_code = _optional_text(error_code, field="error_code")
        with self._write() as conn:
            row = self._require_import_row(conn, import_id)
            if expected_revision is not None:
                self._check_revision(row["revision"], expected_revision, what="导入草稿")
            conn.execute(
                "UPDATE import_drafts SET state = ?, error_code = ?, "
                "revision = revision + 1, updated_at = ? WHERE id = ?",
                (state, error_code, now_iso(), import_id),
            )
            return self._import_record(self._import_row(conn, import_id))

    # ------------------------------------------------------------ 任教设置

    def get_teaching_settings(self) -> TeachingRecord:
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM teaching_settings WHERE owner_id = ?", (TEACHING_OWNER,)
            ).fetchone()
        if row is None:
            return TeachingRecord(owner_id=TEACHING_OWNER, selection_json=None, revision=0, updated_at=None)
        return self._teaching_record(row)

    def set_teaching_settings(
        self, *, selection_json: object = None, expected_revision: int
    ) -> TeachingRecord:
        selection = json_fields.write_object(
            selection_json, field="selection_json", allow_none=True
        )
        with self._write() as conn:
            row = conn.execute(
                "SELECT * FROM teaching_settings WHERE owner_id = ?", (TEACHING_OWNER,)
            ).fetchone()
            current = row["revision"] if row is not None else 0
            self._check_revision(current, expected_revision, what="任教设置")
            now = now_iso()
            if row is None:
                conn.execute(
                    "INSERT INTO teaching_settings (owner_id, selection_json, revision, updated_at) "
                    "VALUES (?, ?, 1, ?)",
                    (TEACHING_OWNER, selection, now),
                )
            else:
                conn.execute(
                    "UPDATE teaching_settings SET selection_json = ?, revision = revision + 1, "
                    "updated_at = ? WHERE owner_id = ?",
                    (selection, now, TEACHING_OWNER),
                )
            return self._teaching_record(
                conn.execute(
                    "SELECT * FROM teaching_settings WHERE owner_id = ?", (TEACHING_OWNER,)
                ).fetchone()
            )

    # ------------------------------------------------------------ 范围解析

    def resolve_selection(self, selection: Any) -> list[ResolvedDocument]:
        """按任教范围逐条核验，任一不满足即 409；不返回任何"尽力而为"的部分结果。"""
        grade_id = _text(getattr(selection, "gradeId", None), field="selection.gradeId")
        subject_id = _text(getattr(selection, "subjectId", None), field="selection.subjectId")
        edition_id = _text(getattr(selection, "editionId", None), field="selection.editionId")
        raw_ids = getattr(selection, "documentIds", None)
        document_ids = _unique_texts(raw_ids, field="selection.documentIds", allow_empty=True)
        if not document_ids:
            raise AppError("任教范围未选择任何教材。", code="RAG_SCOPE_EMPTY", status_code=422)
        with self._read() as conn:
            state = conn.execute("SELECT * FROM catalog_state WHERE id = 1").fetchone()
            if state is None:
                raise _corrupt("教材目录数据损坏：catalog_state 缺少 id=1 行。")
            generation_id = state["active_generation_id"]
            if not generation_id:
                raise _conflict("当前没有已发布的教材索引代。", code="INDEX_NOT_READY")
            generation = self._generation_row(conn, generation_id)
            if generation is None or generation["state"] != "ready":
                raise _conflict("当前索引代未就绪。", code="INDEX_NOT_READY")
            resolved: list[ResolvedDocument] = []
            for document_id in document_ids:
                row = self._document_row(conn, document_id)
                if row is None or row["deleted_at"] is not None:
                    raise _conflict("所选教材已删除或不存在。", code="RAG_SCOPE_CHANGED")
                if row["owner_id"] not in OWNER_IDS:
                    raise _conflict("所选教材归属异常。", code="RAG_SCOPE_CHANGED")
                metadata = self._metadata_record_for_document(conn, document_id)
                if grade_id not in metadata.grade_ids:
                    raise _conflict("所选教材年级与任教范围不一致。", code="RAG_SCOPE_CHANGED")
                if metadata.subject_id != subject_id:
                    raise _conflict("所选教材学科与任教范围不一致。", code="RAG_SCOPE_CHANGED")
                if metadata.edition_id != edition_id:
                    raise _conflict("所选教材版本与任教范围不一致。", code="RAG_SCOPE_CHANGED")
                library_ids = self._matching_library_ids(
                    conn,
                    document_id,
                    owner_id=row["owner_id"],
                    grade_id=grade_id,
                    subject_id=subject_id,
                    edition_id=edition_id,
                )
                if not library_ids:
                    raise _conflict(
                        "所选教材不属于任何与任教范围一致的未删除逻辑库。",
                        code="RAG_SCOPE_CHANGED",
                    )
                revision_id = row["current_revision_id"]
                if not revision_id:
                    raise _conflict("所选教材尚未发布有效修订。", code="RAG_SCOPE_CHANGED")
                link = conn.execute(
                    "SELECT * FROM generation_revisions WHERE generation_id = ? "
                    "AND document_revision_id = ?",
                    (generation_id, revision_id),
                ).fetchone()
                if link is None or link["state"] != "ready":
                    raise _conflict("所选教材尚未进入当前索引代。", code="INDEX_NOT_READY")
                resolved.append(
                    ResolvedDocument(
                        document_id=document_id,
                        document_revision_id=revision_id,
                        metadata_revision_id=metadata.metadata_revision_id,
                        chunk_set_id=link["chunk_set_id"],
                        title=metadata.title,
                        subject_id=metadata.subject_id,
                        edition_id=metadata.edition_id,
                        grade_ids=metadata.grade_ids,
                        library_ids=library_ids,
                    )
                )
            return resolved

    def allowed_chunks(
        self, generation_id: str, document_revision_ids: Sequence[str]
    ) -> AllowedChunks:
        """返回给定索引代内处于 ready 的修订与分块集白名单；缺口显式报错，不静默缩小范围。"""
        generation_id = _text(generation_id, field="generation_id")
        revision_ids = _unique_texts(
            document_revision_ids, field="document_revision_ids", allow_empty=True
        )
        with self._read() as conn:
            self._require_generation_row(conn, generation_id)
            ready: list[str] = []
            chunk_set_ids: list[str] = []
            for revision_id in revision_ids:
                row = conn.execute(
                    "SELECT * FROM generation_revisions WHERE generation_id = ? "
                    "AND document_revision_id = ?",
                    (generation_id, revision_id),
                ).fetchone()
                if row is None or row["state"] != "ready":
                    raise _conflict("教材索引代尚未包含所选修订。", code="INDEX_NOT_READY")
                ready.append(revision_id)
                if row["chunk_set_id"] not in chunk_set_ids:
                    chunk_set_ids.append(row["chunk_set_id"])
            return AllowedChunks(revision_ids=tuple(ready), chunk_set_ids=tuple(chunk_set_ids))

    # ------------------------------------------------------------ 清理队列

    def enqueue_cleanup(self, document_id: str) -> None:
        document_id = _text(document_id, field="document_id")
        with self._write() as conn:
            self._require_document_row(conn, document_id, live=False)
            conn.execute(
                "INSERT INTO cleanup_queue (document_id, enqueued_at, attempts) VALUES (?, ?, 0) "
                "ON CONFLICT(document_id) DO NOTHING",
                (document_id, now_iso()),
            )

    def pending_cleanup(self, limit: int = 50) -> list[str]:
        limit = _count(limit, field="limit", minimum=1)
        if limit > 500:
            raise _invalid("limit 不能超过 500。")
        rows = self._read_all(
            "SELECT document_id FROM cleanup_queue ORDER BY enqueued_at ASC, rowid ASC LIMIT ?",
            (limit,),
        )
        return [row["document_id"] for row in rows]

    def clear_cleanup(self, document_id: str) -> None:
        document_id = _text(document_id, field="document_id")
        with self._write() as conn:
            conn.execute("DELETE FROM cleanup_queue WHERE document_id = ?", (document_id,))

    # ------------------------------------------------------------ 内部：行与记录

    def _touch_catalog(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute(
            "UPDATE catalog_state SET catalog_version = catalog_version + 1 WHERE id = 1"
        )
        if cursor.rowcount != 1:
            raise _corrupt("教材目录数据损坏：catalog_state 缺少 id=1 行。")

    @staticmethod
    def _check_revision(current: int, expected: int, *, what: str) -> None:
        if not isinstance(expected, int) or isinstance(expected, bool):
            raise _invalid("expected_revision 必须是整数。")
        if current != expected:
            raise _conflict(
                f"{what}已被其他操作更新（当前 revision={current}），请刷新后重试。",
                code="REVISION_CONFLICT",
            )

    def _insert_metadata_revision(
        self,
        conn: sqlite3.Connection,
        *,
        metadata_revision_id: str,
        document_id: str,
        title: str,
        stage_id: str,
        grade_ids: Sequence[str],
        subject_id: str,
        edition_id: str,
        publication_label: str,
        volume_label: str,
    ) -> None:
        conn.execute(
            "INSERT INTO document_metadata_revisions (id, document_id, title, stage_id, "
            "grade_ids_json, subject_id, edition_id, publication_label, volume_label, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                metadata_revision_id,
                document_id,
                title,
                stage_id,
                json_fields.write_string_list(list(grade_ids), field="grade_ids_json"),
                subject_id,
                edition_id,
                publication_label,
                volume_label,
                now_iso(),
            ),
        )

    def _library_row(self, conn: sqlite3.Connection, library_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM libraries WHERE id = ?", (library_id,)).fetchone()

    def _live_library_row(self, conn: sqlite3.Connection, library_id: str) -> sqlite3.Row:
        row = self._library_row(conn, library_id)
        if row is None or row["deleted_at"] is not None:
            raise _not_found("逻辑库不存在或已删除。", code="LIBRARY_NOT_FOUND")
        return row

    def _library_record(self, row: sqlite3.Row) -> LibraryRecord:
        if row["kind"] not in LIBRARY_KINDS or row["owner_id"] not in OWNER_IDS:
            raise _corrupt("教材目录数据损坏：libraries 的 kind/owner_id 结构不符。")
        return LibraryRecord(
            library_id=row["id"],
            kind=row["kind"],
            owner_id=row["owner_id"],
            grade_id=row["grade_id"],
            subject_id=_stored_text(row["subject_id"], field="libraries.subject_id"),
            edition_id=_stored_text(row["edition_id"], field="libraries.edition_id"),
            display_name=_stored_text(row["display_name"], field="libraries.display_name"),
            revision=_stored_count(row["revision"], field="libraries.revision"),
            deleted_at=row["deleted_at"],
        )

    def _document_row(self, conn: sqlite3.Connection, document_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()

    def _require_document_row(
        self, conn: sqlite3.Connection, document_id: str, *, live: bool
    ) -> sqlite3.Row:
        row = self._document_row(conn, document_id)
        if row is None or (live and row["deleted_at"] is not None):
            raise _conflict("教材不存在或已停用。", code="DOCUMENT_UNAVAILABLE")
        return row

    def _document_record(self, conn: sqlite3.Connection, document_id: str) -> DocumentRecord:
        row = self._document_row(conn, document_id)
        if row is None:
            raise _corrupt("教材目录数据损坏：写入的书册行缺失。")
        return self._build_document_record(conn, row)

    def _build_document_record(self, conn: sqlite3.Connection, row: sqlite3.Row) -> DocumentRecord:
        metadata = self._metadata_record_for_document(conn, row["id"])
        library_rows = conn.execute(
            "SELECT ld.library_id AS library_id FROM library_documents AS ld "
            "JOIN libraries AS l ON l.id = ld.library_id "
            "WHERE ld.document_id = ? AND l.deleted_at IS NULL ORDER BY ld.library_id ASC",
            (row["id"],),
        ).fetchall()
        return DocumentRecord(
            document_id=row["id"],
            owner_id=row["owner_id"],
            origin_key=row["origin_key"],
            current_revision_id=row["current_revision_id"],
            current_metadata_revision_id=row["current_metadata_revision_id"],
            revision=_stored_count(row["revision"], field="documents.revision"),
            deleted_at=row["deleted_at"],
            library_ids=tuple(item["library_id"] for item in library_rows),
            metadata=metadata,
        )

    def _metadata_record_for_document(
        self, conn: sqlite3.Connection, document_id: str
    ) -> MetadataRevisionRecord:
        row = conn.execute(
            "SELECT m.* FROM documents AS d JOIN document_metadata_revisions AS m "
            "ON m.id = d.current_metadata_revision_id WHERE d.id = ?",
            (document_id,),
        ).fetchone()
        if row is None:
            raise _corrupt("教材目录数据损坏：当前元数据修订缺失。")
        return self._metadata_record(row)

    def _metadata_record(self, row: sqlite3.Row) -> MetadataRevisionRecord:
        grade_ids = json_fields.read_string_list(
            row["grade_ids_json"],
            field="document_metadata_revisions.grade_ids_json",
            allow_empty=False,
        )
        return MetadataRevisionRecord(
            metadata_revision_id=row["id"],
            document_id=row["document_id"],
            title=_stored_text(row["title"], field="document_metadata_revisions.title"),
            stage_id=_stored_text(row["stage_id"], field="document_metadata_revisions.stage_id"),
            grade_ids=tuple(grade_ids),
            subject_id=_stored_text(row["subject_id"], field="document_metadata_revisions.subject_id"),
            edition_id=_stored_text(row["edition_id"], field="document_metadata_revisions.edition_id"),
            publication_label=_stored_maybe_empty(
                row["publication_label"], field="document_metadata_revisions.publication_label"
            ),
            volume_label=_stored_maybe_empty(
                row["volume_label"], field="document_metadata_revisions.volume_label"
            ),
            created_at=_stored_text(row["created_at"], field="document_metadata_revisions.created_at"),
        )

    def _revision_record(self, row: sqlite3.Row) -> RevisionRecord:
        return RevisionRecord(
            revision_id=row["id"],
            document_id=row["document_id"],
            original_file_sha256=_stored_text(
                row["original_file_sha256"], field="document_revisions.original_file_sha256"
            ),
            normalized_text_sha256=_stored_text(
                row["normalized_text_sha256"], field="document_revisions.normalized_text_sha256"
            ),
            parser_version=_stored_text(row["parser_version"], field="document_revisions.parser_version"),
            original_blob_id=_stored_text(row["original_blob_id"], field="document_revisions.original_blob_id"),
            normalized_blob_id=_stored_text(
                row["normalized_blob_id"], field="document_revisions.normalized_blob_id"
            ),
            source_map_blob_id=_stored_text(
                row["source_map_blob_id"], field="document_revisions.source_map_blob_id"
            ),
            char_count=_stored_count(row["char_count"], field="document_revisions.char_count"),
            created_at=_stored_text(row["created_at"], field="document_revisions.created_at"),
        )

    def _chunk_set_record(self, row: sqlite3.Row) -> ChunkSetRecord:
        return ChunkSetRecord(
            chunk_set_id=row["id"],
            document_revision_id=row["document_revision_id"],
            policy_fingerprint=_stored_text(
                row["policy_fingerprint"], field="chunk_sets.policy_fingerprint"
            ),
            manifest_sha256=_stored_text(row["manifest_sha256"], field="chunk_sets.manifest_sha256"),
            chunk_count=_stored_count(row["chunk_count"], field="chunk_sets.chunk_count"),
            sealed_at=_stored_text(row["sealed_at"], field="chunk_sets.sealed_at"),
        )

    def _chunk_record(self, row: sqlite3.Row) -> ChunkRecord:
        region = row["region"]
        if region not in CHUNK_REGIONS:
            raise _corrupt("教材目录数据损坏：chunks.region 结构不符。")
        return ChunkRecord(
            chunk_set_id=row["chunk_set_id"],
            ordinal=_stored_count(row["ordinal"], field="chunks.ordinal"),
            char_start=_stored_count(row["char_start"], field="chunks.char_start"),
            char_end=_stored_count(row["char_end"], field="chunks.char_end"),
            region=region,
            chapter_path=tuple(
                json_fields.read_string_list(row["chapter_path_json"], field="chunks.chapter_path_json")
            ),
            text_sha256=_stored_text(row["text_sha256"], field="chunks.text_sha256"),
            legacy_chunk_id=row["legacy_chunk_id"],
        )

    def _generation_row(self, conn: sqlite3.Connection, generation_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM index_generations WHERE id = ?", (generation_id,)).fetchone()

    def _require_generation_row(self, conn: sqlite3.Connection, generation_id: str) -> sqlite3.Row:
        row = self._generation_row(conn, generation_id)
        if row is None:
            raise _not_found("索引代不存在。", code="GENERATION_NOT_FOUND")
        return row

    def _generation_record(self, row: sqlite3.Row) -> GenerationRecord:
        if row["state"] not in GENERATION_STATES:
            raise _corrupt("教材目录数据损坏：index_generations.state 结构不符。")
        policy = json_fields.read_object(row["chunk_policy_json"], field="index_generations.chunk_policy_json")
        assert policy is not None
        return GenerationRecord(
            generation_id=row["id"],
            profile_id=row["profile_id"],
            collection_name=_stored_text(row["collection_name"], field="index_generations.collection_name"),
            chunk_policy_json=row["chunk_policy_json"],
            state=row["state"],
            created_at=_stored_text(row["created_at"], field="index_generations.created_at"),
            published_at=row["published_at"],
        )

    def _generation_revision_record(self, row: sqlite3.Row) -> GenerationRevisionRecord:
        if row["state"] not in GENERATION_REVISION_STATES:
            raise _corrupt("教材目录数据损坏：generation_revisions.state 结构不符。")
        return GenerationRevisionRecord(
            generation_id=row["generation_id"],
            document_revision_id=row["document_revision_id"],
            chunk_set_id=row["chunk_set_id"],
            state=row["state"],
            expected_chunk_count=_stored_count(
                row["expected_chunk_count"], field="generation_revisions.expected_chunk_count"
            ),
            manifest_sha256=row["manifest_sha256"],
        )

    def _profile_record(self, row: sqlite3.Row) -> ProfileRecord:
        if (
            row["adapter"] not in {"ollama"}
            or row["distance"] != "cosine"
            or row["normalization"] not in NORMALIZATIONS
        ):
            raise _corrupt("教材目录数据损坏：embedding_profiles 结构不符。")
        options = json_fields.read_object(row["options_json"], field="embedding_profiles.options_json")
        assert options is not None
        return ProfileRecord(
            profile_id=row["id"],
            fingerprint=_stored_text(row["fingerprint"], field="embedding_profiles.fingerprint"),
            adapter=row["adapter"],
            native_base_url=_stored_text(row["native_base_url"], field="embedding_profiles.native_base_url"),
            model_name=_stored_text(row["model_name"], field="embedding_profiles.model_name"),
            model_manifest_digest=_stored_text(
                row["model_manifest_digest"], field="embedding_profiles.model_manifest_digest"
            ),
            dimensions=_stored_count(row["dimensions"], field="embedding_profiles.dimensions"),
            distance=row["distance"],
            query_prefix=_stored_maybe_empty(row["query_prefix"], field="embedding_profiles.query_prefix"),
            document_prefix=_stored_maybe_empty(
                row["document_prefix"], field="embedding_profiles.document_prefix"
            ),
            normalization=row["normalization"],
            options_json=row["options_json"],
            verified_at=_stored_text(row["verified_at"], field="embedding_profiles.verified_at"),
            retired_at=row["retired_at"],
        )

    def _job_row(self, conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM index_jobs WHERE id = ?", (job_id,)).fetchone()

    def _require_job_row(self, conn: sqlite3.Connection, job_id: str) -> sqlite3.Row:
        row = self._job_row(conn, job_id)
        if row is None:
            raise _not_found("索引任务不存在。", code="JOB_NOT_FOUND")
        return row

    def _job_record(self, row: sqlite3.Row) -> JobRecord:
        if row["kind"] not in JOB_KINDS or row["state"] not in JOB_STATES:
            raise _corrupt("教材目录数据损坏：index_jobs 的 kind/state 结构不符。")
        checkpoint = json_fields.read_object(row["checkpoint_json"], field="index_jobs.checkpoint_json")
        assert checkpoint is not None
        return JobRecord(
            job_id=row["id"],
            kind=row["kind"],
            input_revision_id=row["input_revision_id"],
            document_id=row["document_id"],
            metadata_revision_id=row["metadata_revision_id"],
            target_generation_id=row["target_generation_id"],
            base_generation_id=row["base_generation_id"],
            state=row["state"],
            idempotency_key=row["idempotency_key"],
            request_fingerprint=row["request_fingerprint"],
            attempt=_stored_count(row["attempt"], field="index_jobs.attempt"),
            lease_token=row["lease_token"],
            lease_until=row["lease_until"],
            checkpoint_json=row["checkpoint_json"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            created_at=_stored_text(row["created_at"], field="index_jobs.created_at"),
            updated_at=_stored_text(row["updated_at"], field="index_jobs.updated_at"),
        )

    @staticmethod
    def _lease_matches(row: sqlite3.Row, lease_token: str, now: str) -> bool:
        if row["state"] != "running" or row["lease_token"] != lease_token:
            return False
        return row["lease_until"] is not None and row["lease_until"] > now

    def _import_row(self, conn: sqlite3.Connection, import_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM import_drafts WHERE id = ?", (import_id,)).fetchone()

    def _require_import_row(self, conn: sqlite3.Connection, import_id: str) -> sqlite3.Row:
        row = self._import_row(conn, import_id)
        if row is None:
            raise _not_found("导入草稿不存在。", code="IMPORT_NOT_FOUND")
        return row

    def _import_record(self, row: sqlite3.Row) -> ImportRecord:
        if row["state"] not in IMPORT_STATES:
            raise _corrupt("教材目录数据损坏：import_drafts.state 结构不符。")
        json_fields.read_object(row["metadata_json"], field="import_drafts.metadata_json", allow_none=True)
        json_fields.read_object(
            row["parsed_artifacts_json"], field="import_drafts.parsed_artifacts_json", allow_none=True
        )
        json_fields.read_string_list(row["warnings_json"], field="import_drafts.warnings_json")
        return ImportRecord(
            import_id=row["id"],
            owner_id=row["owner_id"],
            target_document_id=row["target_document_id"],
            expected_current_revision_id=row["expected_current_revision_id"],
            metadata_json=row["metadata_json"],
            uploaded_blob_id=_stored_text(row["uploaded_blob_id"], field="import_drafts.uploaded_blob_id"),
            uploaded_file_name=_stored_text(
                row["uploaded_file_name"], field="import_drafts.uploaded_file_name"
            ),
            uploaded_bytes=_stored_count(row["uploaded_bytes"], field="import_drafts.uploaded_bytes"),
            parsed_artifacts_json=row["parsed_artifacts_json"],
            state=row["state"],
            revision=_stored_count(row["revision"], field="import_drafts.revision"),
            warnings_json=row["warnings_json"],
            error_code=row["error_code"],
            created_at=_stored_text(row["created_at"], field="import_drafts.created_at"),
            updated_at=_stored_text(row["updated_at"], field="import_drafts.updated_at"),
        )

    def _teaching_record(self, row: sqlite3.Row) -> TeachingRecord:
        json_fields.read_object(
            row["selection_json"], field="teaching_settings.selection_json", allow_none=True
        )
        return TeachingRecord(
            owner_id=row["owner_id"],
            selection_json=row["selection_json"],
            revision=_stored_count(row["revision"], field="teaching_settings.revision"),
            updated_at=row["updated_at"],
        )

    def _matching_library_ids(
        self,
        conn: sqlite3.Connection,
        document_id: str,
        *,
        owner_id: str,
        grade_id: str,
        subject_id: str,
        edition_id: str,
    ) -> tuple[str, ...]:
        # grade_id 为 NULL 的逻辑库表示年级未确认，不参与任何任教范围
        rows = conn.execute(
            "SELECT l.id AS library_id FROM library_documents AS ld "
            "JOIN libraries AS l ON l.id = ld.library_id "
            "WHERE ld.document_id = ? AND l.deleted_at IS NULL AND l.owner_id = ? "
            "AND l.grade_id = ? AND l.subject_id = ? AND l.edition_id = ? ORDER BY l.id ASC",
            (document_id, owner_id, grade_id, subject_id, edition_id),
        ).fetchall()
        return tuple(row["library_id"] for row in rows)


def _validate_chunks(chunks: Sequence[ChunkInput]) -> list[ChunkInput]:
    if isinstance(chunks, (str, bytes)) or not isinstance(chunks, Sequence):
        raise _invalid("chunks 必须是 ChunkInput 序列。")
    normalized: list[ChunkInput] = []
    seen: set[int] = set()
    for chunk in chunks:
        if not isinstance(chunk, ChunkInput):
            raise _invalid("chunks 元素必须是 ChunkInput。")
        ordinal = _count(chunk.ordinal, field="chunk.ordinal", minimum=0)
        if ordinal in seen:
            raise _invalid("chunk.ordinal 不允许重复。")
        seen.add(ordinal)
        char_start = _count(chunk.char_start, field="chunk.char_start", minimum=0)
        char_end = _count(chunk.char_end, field="chunk.char_end", minimum=0)
        if char_end <= char_start:
            raise _invalid("chunk.char_end 必须大于 char_start。")
        region = _choice(chunk.region, field="chunk.region", allowed=CHUNK_REGIONS)
        chapter_path = _unique_texts(chunk.chapter_path, field="chunk.chapter_path", allow_empty=True)
        text_sha256 = _text(chunk.text_sha256, field="chunk.text_sha256")
        legacy_chunk_id = _optional_text(chunk.legacy_chunk_id, field="chunk.legacy_chunk_id")
        normalized.append(
            ChunkInput(
                ordinal=ordinal,
                char_start=char_start,
                char_end=char_end,
                region=region,
                chapter_path=chapter_path,
                text_sha256=text_sha256,
                legacy_chunk_id=legacy_chunk_id,
            )
        )
    return normalized


def _text_or_empty(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise _invalid(f"{field} 必须是字符串。")
    return value


def _stored_maybe_empty(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise _corrupt(f"教材目录数据损坏：{field} 不是字符串。")
    return value
