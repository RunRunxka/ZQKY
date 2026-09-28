"""题库 SQLite 权威层：导入、原文块、草稿、AI 建议、题目、提交与任务。

约束（与教材目录同一套纪律，库文件彼此独立）：
- 所有写操作在 ``transaction(conn, immediate=True)`` 内完成；仓储函数只做 SQL，
  解析、文件与模型调用一律在事务外由服务层执行；
- 每次操作独立开连接（``connect``）：实例可被 FastAPI 线程池跨线程使用；
- ``question_imports`` 的 revision 是乐观锁；``question_drafts`` 的 revision 同时是
  校对修订号，命中 ``expected_revision`` 才写；
- 草稿内容/分类一经变化，已校对状态强制回到 ``needs_review``（显式排除除外）；
- 原文块只增不改：``question_source_blocks`` 没有更新与删除路径，未归属原文不会被丢弃；
- ``question_submissions`` 是确认入库的幂等表：同 submissionId 同载荷返回原结果，
  同键不同载荷抛 ``IDEMPOTENCY_CONFLICT``；
- 确认入库的多表写入共用一次 ``write_transaction()``，失败整体回滚。
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, get_args

from app.core.exceptions import AppError
from app.core.sqlite import connect, now_iso, read_transaction, transaction
from app.repositories.question_bank import json_fields
from app.repositories.question_bank.records import (
    DraftInput,
    DraftRecord,
    ImportRecord,
    JobRecord,
    QuestionRecord,
    SourceBlockInput,
    SourceBlockRecord,
    SubmissionRecord,
    SuggestionInput,
    SuggestionRecord,
)
from app.repositories.question_bank.schema import migrate as migrate_schema
from app.schemas.question_bank import (
    AnswerState,
    DraftReviewState,
    ImportState,
    QuestionStatus,
    SuggestionState,
)

IMPORT_STATES = frozenset(get_args(ImportState))
DRAFT_REVIEW_STATES = frozenset(get_args(DraftReviewState))
SUGGESTION_STATES = frozenset(get_args(SuggestionState))
QUESTION_STATUSES = frozenset(get_args(QuestionStatus))
ANSWER_STATES = frozenset(get_args(AnswerState))
EXTRACTION_METHODS = frozenset({"rule", "ai", "manual"})
JOB_KINDS = frozenset({"organize"})
JOB_STATES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})
LOCATOR_KINDS = frozenset({"markdown", "pdf", "docx", "text"})

#: 草稿 update 允许写入的列（其余字段一律拒绝，避免隐式写坏指纹与状态机）
_DRAFT_UPDATE_COLUMNS = frozenset(
    {
        "content_json",
        "metadata_json",
        "source_spans_json",
        "review_state",
        "missing_answer_acknowledged",
        "warnings_json",
        "content_fingerprint",
        "duplicate_of_question_id",
        "extraction_method",
    }
)


def _invalid(message: str, *, code: str = "INVALID_REQUEST") -> AppError:
    return AppError(message, code=code, status_code=422)


def _not_found(message: str, *, code: str) -> AppError:
    return AppError(message, code=code, status_code=404)


def _conflict(message: str, *, code: str, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=409, retryable=retryable)


def _corrupt(message: str) -> AppError:
    return AppError(message, code="QUESTION_BANK_CORRUPT", status_code=500)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。")
    return value


def _text_or_empty(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise _invalid(f"{field} 必须是字符串。")
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


def _stored_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise _corrupt(f"题库数据损坏：{field} 不是非空字符串。")
    return value


def _stored_maybe_empty(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise _corrupt(f"题库数据损坏：{field} 不是字符串。")
    return value


def _stored_count(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _corrupt(f"题库数据损坏：{field} 不是非负整数。")
    return value


def _stored_flag(value: object, *, field: str) -> bool:
    if value not in (0, 1):
        raise _corrupt(f"题库数据损坏：{field} 不是 0/1 标志。")
    return bool(value)


class QuestionBankCatalog:
    """题库的唯一读写入口；调用方给出数据库路径，测试使用临时目录。"""

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
            with transaction(connection, immediate=True) as conn:
                migrate_schema(conn)
        finally:
            connection.close()
        self._migrated = True

    def close(self) -> None:
        self._closed = True

    def _open(self, *, require_migrated: bool = True) -> sqlite3.Connection:
        if self._closed:
            raise AppError("题库已关闭。", code="QUESTION_BANK_CLOSED", status_code=500)
        if require_migrated and not self._migrated:
            raise AppError(
                "题库尚未迁移：先调用 migrate()。",
                code="QUESTION_BANK_NOT_MIGRATED",
                status_code=500,
            )
        return connect(self._db_path)

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        connection = self._open()
        try:
            with transaction(connection, immediate=True) as conn:
                conn.execute("PRAGMA defer_foreign_keys = ON")
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

    @contextmanager
    def write_transaction(self) -> Iterator[sqlite3.Connection]:
        """确认入库专用的单事务入口：调用方在事务内只经本类 ``*_in(conn)`` 方法读写。

        事务内不得做网络、文件与推理；抛异常整体回滚，失败不留下半确认数据。
        """
        with self._write() as conn:
            yield conn

    # ------------------------------------------------------------------ 导入

    def create_import(
        self,
        *,
        owner_id: str,
        file_sha256: str,
        original_blob_id: str,
        uploaded_file_name: str,
        uploaded_bytes: int,
        state: str = "uploaded",
        warnings: Sequence[str] = (),
    ) -> ImportRecord:
        owner_id = _text(owner_id, field="owner_id")
        file_sha256 = _text(file_sha256, field="file_sha256")
        original_blob_id = _text(original_blob_id, field="original_blob_id")
        uploaded_file_name = _text(uploaded_file_name, field="uploaded_file_name")
        uploaded_bytes = _count(uploaded_bytes, field="uploaded_bytes", minimum=0)
        state = _choice(state, field="state", allowed=IMPORT_STATES)
        warnings_json = json_fields.write_string_list(list(warnings), field="warnings_json")
        import_id = uuid.uuid4().hex
        now = now_iso()
        with self._write() as conn:
            conn.execute(
                "INSERT INTO question_imports (id, owner_id, file_sha256, original_blob_id, "
                "uploaded_file_name, uploaded_bytes, state, revision, warnings_json, error_code, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?)",
                (
                    import_id,
                    owner_id,
                    file_sha256,
                    original_blob_id,
                    uploaded_file_name,
                    uploaded_bytes,
                    state,
                    warnings_json,
                    now,
                    now,
                ),
            )
            return self._import_record(self._import_row_in(conn, import_id))

    def get_import(self, import_id: str) -> ImportRecord | None:
        import_id = _text(import_id, field="import_id")
        with self._read() as conn:
            row = self._import_row_in(conn, import_id)
        return self._import_record(row) if row is not None else None

    def list_imports(self, *, limit: int = 50) -> list[ImportRecord]:
        limit = _count(limit, field="limit", minimum=1)
        if limit > 500:
            raise _invalid("limit 不能超过 500。")
        with self._read() as conn:
            rows = conn.execute(
                "SELECT * FROM question_imports ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._import_record(row) for row in rows]

    def update_import(
        self,
        import_id: str,
        *,
        expected_revision: int,
        state: str | None = None,
        warnings: Sequence[str] | None = None,
        error_code: str | None = None,
        clear_error: bool = False,
    ) -> ImportRecord:
        import_id = _text(import_id, field="import_id")
        updates: dict[str, object] = {}
        if state is not None:
            updates["state"] = _choice(state, field="state", allowed=IMPORT_STATES)
        if warnings is not None:
            updates["warnings_json"] = json_fields.write_string_list(
                list(warnings), field="warnings_json"
            )
        if clear_error:
            updates["error_code"] = None
        elif error_code is not None:
            updates["error_code"] = _text(error_code, field="error_code")
        with self._write() as conn:
            row = self._require_import_row_in(conn, import_id)
            self._check_revision(row["revision"], expected_revision, what="导入")
            if updates:
                self._apply_updates(conn, "question_imports", import_id, updates)
            return self._import_record(self._import_row_in(conn, import_id))

    def set_import_state_in(
        self,
        conn: sqlite3.Connection,
        import_id: str,
        *,
        state: str,
        error_code: str | None = None,
    ) -> None:
        """确认流程的事务内状态推进（不参与乐观锁，由调用方在同一事务里完成核验）。"""
        state = _choice(state, field="state", allowed=IMPORT_STATES)
        error_code = _optional_text(error_code, field="error_code")
        self._require_import_row_in(conn, import_id)
        conn.execute(
            "UPDATE question_imports SET state = ?, error_code = COALESCE(?, error_code), "
            "revision = revision + 1, updated_at = ? WHERE id = ?",
            (state, error_code, now_iso(), import_id),
        )

    # ------------------------------------------------------------- 原文块

    def add_source_blocks(
        self, import_id: str, blocks: Sequence[SourceBlockInput]
    ) -> list[SourceBlockRecord]:
        """只增不改：原文块一次写入，之后没有更新与删除路径。"""
        import_id = _text(import_id, field="import_id")
        if isinstance(blocks, (str, bytes)) or not isinstance(blocks, Sequence):
            raise _invalid("blocks 必须是 SourceBlockInput 序列。")
        prepared: list[tuple[str, int, str, str]] = []
        seen: set[int] = set()
        for block in blocks:
            if not isinstance(block, SourceBlockInput):
                raise _invalid("blocks 元素必须是 SourceBlockInput。")
            ordinal = _count(block.ordinal, field="ordinal", minimum=0)
            if ordinal in seen:
                raise _invalid("原文块 ordinal 不允许重复。")
            seen.add(ordinal)
            text = _text_or_empty(block.text, field="text")
            locator_json = json_fields.write_object(block.locator, field="locator_json")
            prepared.append((uuid.uuid4().hex, ordinal, text, locator_json))
        with self._write() as conn:
            self._require_import_row_in(conn, import_id)
            conn.executemany(
                "INSERT INTO question_source_blocks (id, import_id, ordinal, text, locator_json) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (block_id, import_id, ordinal, text, locator_json)
                    for block_id, ordinal, text, locator_json in prepared
                ],
            )
            return self._source_block_records_in(conn, import_id)

    def list_source_blocks(self, import_id: str) -> list[SourceBlockRecord]:
        import_id = _text(import_id, field="import_id")
        with self._read() as conn:
            self._require_import_row_in(conn, import_id)
            return self._source_block_records_in(conn, import_id)

    def source_blocks_by_ids(self, block_ids: Sequence[str]) -> dict[str, SourceBlockRecord]:
        requested: list[str] = []
        seen: set[str] = set()
        for block_id in block_ids:
            text = _text(block_id, field="block_id")
            if text not in seen:
                seen.add(text)
                requested.append(text)
        if not requested:
            return {}
        placeholders = ", ".join("?" for _ in requested)
        with self._read() as conn:
            rows = conn.execute(
                f"SELECT * FROM question_source_blocks WHERE id IN ({placeholders}) "
                "ORDER BY ordinal ASC, rowid ASC",
                requested,
            ).fetchall()
        return {row["id"]: self._source_block_record(row) for row in rows}

    # ------------------------------------------------------------------ 草稿

    def create_drafts(self, import_id: str, drafts: Sequence[DraftInput]) -> list[DraftRecord]:
        import_id = _text(import_id, field="import_id")
        if isinstance(drafts, (str, bytes)) or not isinstance(drafts, Sequence):
            raise _invalid("drafts 必须是 DraftInput 序列。")
        prepared = [self._draft_insert_values(import_id, draft) for draft in drafts]
        with self._write() as conn:
            self._require_import_row_in(conn, import_id)
            return self._insert_drafts_in(conn, prepared)

    def get_draft(self, draft_id: str) -> DraftRecord | None:
        draft_id = _text(draft_id, field="draft_id")
        with self._read() as conn:
            row = self._draft_row_in(conn, draft_id)
        return self._draft_record(row) if row is not None else None

    def list_drafts(self, import_id: str) -> list[DraftRecord]:
        import_id = _text(import_id, field="import_id")
        with self._read() as conn:
            self._require_import_row_in(conn, import_id)
            return self._draft_records_in(conn, import_id)

    def update_draft(
        self,
        draft_id: str,
        *,
        expected_revision: int,
        content: object | None = None,
        metadata: object | None = None,
        source_spans: Sequence[dict[str, Any]] | None = None,
        review_state: str | None = None,
        missing_answer_acknowledged: bool | None = None,
        warnings: Sequence[str] | None = None,
        content_fingerprint: str | None = None,
        duplicate_of_question_id: str | None = None,
        clear_duplicate: bool = False,
        extraction_method: str | None = None,
    ) -> DraftRecord:
        """乐观锁更新；content/metadata 实际变化时强制回到 ``needs_review``。

        显式把 reviewState 设为 ``excluded`` 表示人工排除，允许与内容修改同批提交；
        其余情况下内容一变，``reviewed`` 不会被保留。
        """
        draft_id = _text(draft_id, field="draft_id")
        updates: dict[str, object] = {}
        content_changed = False
        with self._write() as conn:
            row = self._require_draft_row_in(conn, draft_id)
            self._check_revision(row["revision"], expected_revision, what="草稿")
            if content is not None:
                serialized = json_fields.write_object(content, field="content_json")
                content_changed = serialized != row["content_json"]
                updates["content_json"] = serialized
            if metadata is not None:
                serialized = json_fields.write_object(metadata, field="metadata_json")
                content_changed = content_changed or serialized != row["metadata_json"]
                updates["metadata_json"] = serialized
            if source_spans is not None:
                updates["source_spans_json"] = json_fields.write_object_list(
                    list(source_spans), field="source_spans_json"
                )
            if review_state is not None:
                updates["review_state"] = _choice(
                    review_state, field="review_state", allowed=DRAFT_REVIEW_STATES
                )
            if missing_answer_acknowledged is not None:
                if not isinstance(missing_answer_acknowledged, bool):
                    raise _invalid("missing_answer_acknowledged 必须是布尔值。")
                updates["missing_answer_acknowledged"] = int(missing_answer_acknowledged)
            if warnings is not None:
                updates["warnings_json"] = json_fields.write_string_list(
                    list(warnings), field="warnings_json"
                )
            if content_fingerprint is not None:
                updates["content_fingerprint"] = _text_or_empty(
                    content_fingerprint, field="content_fingerprint"
                )
            if clear_duplicate:
                updates["duplicate_of_question_id"] = None
            elif duplicate_of_question_id is not None:
                updates["duplicate_of_question_id"] = _text(
                    duplicate_of_question_id, field="duplicate_of_question_id"
                )
            if extraction_method is not None:
                updates["extraction_method"] = _choice(
                    extraction_method, field="extraction_method", allowed=EXTRACTION_METHODS
                )
            target_state = updates.get("review_state", row["review_state"])
            if content_changed and target_state != "excluded":
                updates["review_state"] = "needs_review"
            if updates:
                self._apply_updates(conn, "question_drafts", draft_id, updates)
            return self._draft_record(self._draft_row_in(conn, draft_id))

    def replace_draft_set(
        self,
        import_id: str,
        *,
        excluded: Sequence[tuple[str, int, str]],
        created: Sequence[DraftInput],
    ) -> list[DraftRecord]:
        """拆分/合并的原子写入：新增草稿 + 把被替代的草稿标记为 excluded（保留原行）。

        ``excluded`` 元素为 ``(draft_id, expected_revision, warning)``；
        任一 revision 不符整笔回滚，不出现"拆了一半"的中间态。
        """
        import_id = _text(import_id, field="import_id")
        prepared = [self._draft_insert_values(import_id, draft) for draft in created]
        with self._write() as conn:
            self._require_import_row_in(conn, import_id)
            for draft_id, expected_revision, warning in excluded:
                draft_id = _text(draft_id, field="draft_id")
                row = self._require_draft_row_in(conn, draft_id)
                if row["import_id"] != import_id:
                    raise _invalid("草稿不属于该导入。", code="DRAFT_IMPORT_MISMATCH")
                self._check_revision(row["revision"], expected_revision, what="草稿")
            inserted = self._insert_drafts_in(conn, prepared)
            for draft_id, _expected, warning in excluded:
                row = self._require_draft_row_in(conn, draft_id)
                warnings = json_fields.read_string_list(
                    row["warnings_json"], field="question_drafts.warnings_json"
                )
                note = _text(warning, field="warning")
                if note not in warnings:
                    warnings.append(note)
                conn.execute(
                    "UPDATE question_drafts SET review_state = 'excluded', warnings_json = ?, "
                    "revision = revision + 1 WHERE id = ?",
                    (
                        json_fields.write_string_list(warnings, field="warnings_json"),
                        draft_id,
                    ),
                )
            return inserted

    def set_draft_review_state(self, draft_id: str, *, expected_revision: int, review_state: str) -> DraftRecord:
        return self.update_draft(
            draft_id, expected_revision=expected_revision, review_state=review_state
        )

    # ---------------------------------------------------------------- 建议

    def create_suggestions(self, rows: Sequence[SuggestionInput]) -> list[SuggestionRecord]:
        if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
            raise _invalid("rows 必须是 SuggestionInput 序列。")
        prepared: list[tuple[str, SuggestionInput]] = []
        for row in rows:
            if not isinstance(row, SuggestionInput):
                raise _invalid("rows 元素必须是 SuggestionInput。")
            prepared.append((uuid.uuid4().hex, row))
        with self._write() as conn:
            for suggestion_id, row in prepared:
                draft = self._require_draft_row_in(conn, _text(row.target_draft_id, field="target_draft_id"))
                base_revision = _count(
                    row.base_draft_revision, field="base_draft_revision", minimum=0
                )
                state = _choice(row.state, field="state", allowed=SUGGESTION_STATES)
                conn.execute(
                    "INSERT INTO question_suggestions (id, organization_job_id, target_draft_id, "
                    "base_draft_revision, proposed_content_json, proposed_metadata_json, "
                    "source_block_ids_json, state, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        suggestion_id,
                        _text(row.organization_job_id, field="organization_job_id"),
                        draft["id"],
                        base_revision,
                        json_fields.write_object(
                            row.proposed_content, field="proposed_content_json"
                        ),
                        json_fields.write_object(
                            row.proposed_metadata, field="proposed_metadata_json"
                        ),
                        json_fields.write_string_list(
                            list(row.source_block_ids), field="source_block_ids_json"
                        ),
                        state,
                        _optional_text(row.note, field="note"),
                    ),
                )
            ids = [suggestion_id for suggestion_id, _row in prepared]
            placeholders = ", ".join("?" for _ in ids)
            rows_out = conn.execute(
                f"SELECT * FROM question_suggestions WHERE id IN ({placeholders}) ORDER BY rowid ASC",
                ids,
            ).fetchall()
            return [self._suggestion_record(row) for row in rows_out]

    def get_suggestion(self, suggestion_id: str) -> SuggestionRecord | None:
        suggestion_id = _text(suggestion_id, field="suggestion_id")
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM question_suggestions WHERE id = ?", (suggestion_id,)
            ).fetchone()
        return self._suggestion_record(row) if row is not None else None

    def list_suggestions(
        self,
        *,
        organization_job_id: str | None = None,
        target_draft_id: str | None = None,
        state: str | None = None,
    ) -> list[SuggestionRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if organization_job_id is not None:
            clauses.append("organization_job_id = ?")
            params.append(_text(organization_job_id, field="organization_job_id"))
        if target_draft_id is not None:
            clauses.append("target_draft_id = ?")
            params.append(_text(target_draft_id, field="target_draft_id"))
        if state is not None:
            clauses.append("state = ?")
            params.append(_choice(state, field="state", allowed=SUGGESTION_STATES))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._read() as conn:
            rows = conn.execute(
                f"SELECT * FROM question_suggestions{where} ORDER BY rowid ASC", params
            ).fetchall()
        return [self._suggestion_record(row) for row in rows]

    def apply_suggestion(
        self,
        suggestion_id: str,
        *,
        expected_draft_revision: int,
        accept: bool,
        warning: str,
    ) -> tuple[SuggestionRecord, DraftRecord]:
        """应用/拒绝一条建议；单事务内先核建议状态，再核草稿修订与建议基线。"""
        suggestion_id = _text(suggestion_id, field="suggestion_id")
        with self._write() as conn:
            row = conn.execute(
                "SELECT * FROM question_suggestions WHERE id = ?", (suggestion_id,)
            ).fetchone()
            if row is None:
                raise _not_found("AI 建议不存在。", code="SUGGESTION_NOT_FOUND")
            suggestion = self._suggestion_record(row)
            if suggestion.state != "pending":
                raise _conflict(
                    f"该建议已处理（state={suggestion.state}），不能重复应用。",
                    code="SUGGESTION_NOT_PENDING",
                )
            draft_row = self._require_draft_row_in(conn, suggestion.target_draft_id)
            self._check_revision(
                draft_row["revision"], expected_draft_revision, what="草稿"
            )
            if draft_row["revision"] != suggestion.base_draft_revision:
                raise _conflict(
                    "草稿已在建议生成后被修改（base_draft_revision 过期），"
                    "请重新整理后再应用。",
                    code="DRAFT_REVISION_CONFLICT",
                )
            if not accept:
                conn.execute(
                    "UPDATE question_suggestions SET state = 'rejected' WHERE id = ?",
                    (suggestion_id,),
                )
                return (
                    self._suggestion_record(
                        conn.execute(
                            "SELECT * FROM question_suggestions WHERE id = ?", (suggestion_id,)
                        ).fetchone()
                    ),
                    self._draft_record(self._require_draft_row_in(conn, suggestion.target_draft_id)),
                )

            warnings = json_fields.read_string_list(
                draft_row["warnings_json"], field="question_drafts.warnings_json"
            )
            note = _text(warning, field="warning")
            if note not in warnings:
                warnings.append(note)
            # 分类只补空：人工已填的分类不被 AI 建议覆盖
            current_metadata = json_fields.read_object(
                draft_row["metadata_json"], field="question_drafts.metadata_json"
            )
            assert current_metadata is not None
            merged_metadata = dict(current_metadata)
            for key in ("stageId", "gradeId", "subjectId", "editionId", "difficulty"):
                if not merged_metadata.get(key) and suggestion.proposed_metadata.get(key):
                    merged_metadata[key] = suggestion.proposed_metadata[key]
            conn.execute(
                "UPDATE question_drafts SET content_json = ?, metadata_json = ?, "
                "review_state = 'needs_review', warnings_json = ?, revision = revision + 1 "
                "WHERE id = ?",
                (
                    json_fields.write_object(
                        suggestion.proposed_content, field="content_json"
                    ),
                    json_fields.write_object(merged_metadata, field="metadata_json"),
                    json_fields.write_string_list(warnings, field="warnings_json"),
                    suggestion.target_draft_id,
                ),
            )
            conn.execute(
                "UPDATE question_suggestions SET state = 'applied' WHERE id = ?",
                (suggestion_id,),
            )
            return (
                self._suggestion_record(
                    conn.execute(
                        "SELECT * FROM question_suggestions WHERE id = ?", (suggestion_id,)
                    ).fetchone()
                ),
                self._draft_record(self._require_draft_row_in(conn, suggestion.target_draft_id)),
            )

    # ---------------------------------------------------------------- 题目

    def find_questions_by_fingerprint(self, owner_id: str, fingerprint: str) -> list[QuestionRecord]:
        owner_id = _text(owner_id, field="owner_id")
        fingerprint = _text(fingerprint, field="fingerprint")
        with self._read() as conn:
            return self._questions_by_fingerprint_in(conn, owner_id, fingerprint)

    def list_questions(
        self,
        *,
        owner_id: str,
        subject_id: str | None = None,
        grade_id: str | None = None,
        edition_id: str | None = None,
        status: str | None = None,
        query: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[QuestionRecord], int]:
        owner_id = _text(owner_id, field="owner_id")
        offset = _count(offset, field="offset", minimum=0)
        limit = _count(limit, field="limit", minimum=1)
        if limit > 200:
            raise _invalid("limit 不能超过 200。")
        statuses: tuple[str, ...]
        if status is None:
            # 默认只看在用题目；归档需显式 status=archived，status=all 才两者都返回
            statuses = ("confirmed",)
        elif status == "all":
            statuses = tuple(sorted(QUESTION_STATUSES))
        else:
            statuses = (_choice(status, field="status", allowed=QUESTION_STATUSES),)
        placeholders = ", ".join("?" for _ in statuses)
        with self._read() as conn:
            rows = conn.execute(
                f"SELECT q.* FROM questions AS q JOIN question_revisions AS r "
                "ON r.id = q.current_revision_id WHERE q.owner_id = ? "
                f"AND q.status IN ({placeholders}) ORDER BY q.created_at DESC, q.rowid DESC",
                (owner_id, *statuses),
            ).fetchall()
            records = [self._question_record(conn, row) for row in rows]
        filtered: list[QuestionRecord] = []
        needle = (query or "").strip().casefold()
        for record in records:
            metadata = record.metadata
            if subject_id is not None and metadata.get("subjectId") != subject_id:
                continue
            if grade_id is not None and metadata.get("gradeId") != grade_id:
                continue
            if edition_id is not None and metadata.get("editionId") != edition_id:
                continue
            if needle:
                haystack = " ".join(
                    [
                        str(record.content.get("stemMarkdown", "")),
                        str(record.content.get("explanationMarkdown") or ""),
                        " ".join(
                            str(option.get("textMarkdown", ""))
                            for option in record.content.get("options", [])
                        ),
                        " ".join(str(tag) for tag in metadata.get("knowledgeTags", [])),
                    ]
                ).casefold()
                if needle not in haystack:
                    continue
            filtered.append(record)
        return filtered[offset : offset + limit], len(filtered)

    def get_question(self, question_id: str) -> QuestionRecord | None:
        question_id = _text(question_id, field="question_id")
        with self._read() as conn:
            row = self._question_row_in(conn, question_id)
            if row is None:
                return None
            return self._question_record(conn, row)

    def patch_question(
        self,
        question_id: str,
        *,
        expected_revision: int,
        content: object,
        metadata: object,
        answer_state: str,
        content_fingerprint: str,
    ) -> QuestionRecord:
        """题目编辑：追加不可变新修订，并把 current_revision_id 指向它。"""
        question_id = _text(question_id, field="question_id")
        answer_state = _choice(answer_state, field="answer_state", allowed=ANSWER_STATES)
        content_json = json_fields.write_object(content, field="content_json")
        metadata_json = json_fields.write_object(metadata, field="metadata_json")
        content_fingerprint = _text(content_fingerprint, field="content_fingerprint")
        with self._write() as conn:
            row = self._require_question_row_in(conn, question_id)
            if row["status"] != "confirmed":
                raise _conflict("已归档的题目不能再修改。", code="QUESTION_ARCHIVED")
            revision_count = self._revision_count_in(conn, question_id)
            self._check_revision(revision_count, expected_revision, what="题目")
            revision_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO question_revisions (id, question_id, content_json, metadata_json, "
                "answer_state, content_fingerprint, confirmed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    revision_id,
                    question_id,
                    content_json,
                    metadata_json,
                    answer_state,
                    content_fingerprint,
                    now_iso(),
                ),
            )
            conn.execute(
                "UPDATE questions SET current_revision_id = ? WHERE id = ?",
                (revision_id, question_id),
            )
            return self._question_record(conn, self._require_question_row_in(conn, question_id))

    def archive_question(self, question_id: str, *, expected_revision: int | None = None) -> QuestionRecord:
        """归档（逻辑删除）：不物理删除题目、修订与来源。"""
        question_id = _text(question_id, field="question_id")
        with self._write() as conn:
            row = self._require_question_row_in(conn, question_id)
            if expected_revision is not None:
                revision_count = self._revision_count_in(conn, question_id)
                self._check_revision(revision_count, expected_revision, what="题目")
            if row["status"] != "archived":
                conn.execute("UPDATE questions SET status = 'archived' WHERE id = ?", (question_id,))
            return self._question_record(conn, self._require_question_row_in(conn, question_id))

    # ------------------------------------------------- 确认入库（事务内接口）

    def import_in(self, conn: sqlite3.Connection, import_id: str) -> ImportRecord | None:
        row = self._import_row_in(conn, _text(import_id, field="import_id"))
        return self._import_record(row) if row is not None else None

    def draft_in(self, conn: sqlite3.Connection, draft_id: str) -> DraftRecord | None:
        row = self._draft_row_in(conn, _text(draft_id, field="draft_id"))
        return self._draft_record(row) if row is not None else None

    def submission_in(self, conn: sqlite3.Connection, submission_id: str) -> SubmissionRecord | None:
        row = conn.execute(
            "SELECT * FROM question_submissions WHERE submission_id = ?",
            (_text(submission_id, field="submission_id"),),
        ).fetchone()
        if row is None:
            return None
        result = json_fields.read_object(row["result_json"], field="question_submissions.result_json")
        assert result is not None
        return SubmissionRecord(
            submission_id=row["submission_id"],
            request_fingerprint=row["request_fingerprint"],
            result=result,
            created_at=_stored_text(row["created_at"], field="question_submissions.created_at"),
        )

    def save_submission_in(
        self,
        conn: sqlite3.Connection,
        *,
        submission_id: str,
        request_fingerprint: str,
        result: dict[str, Any],
    ) -> None:
        conn.execute(
            "INSERT INTO question_submissions (submission_id, request_fingerprint, result_json, "
            "created_at) VALUES (?, ?, ?, ?)",
            (
                _text(submission_id, field="submission_id"),
                _text(request_fingerprint, field="request_fingerprint"),
                json_fields.write_object(result, field="result_json"),
                now_iso(),
            ),
        )

    def insert_question_in(
        self,
        conn: sqlite3.Connection,
        *,
        owner_id: str,
        content: dict[str, Any],
        metadata: dict[str, Any],
        answer_state: str,
        content_fingerprint: str,
        source_spans: Sequence[dict[str, Any]],
        import_id: str | None,
    ) -> QuestionRecord:
        owner_id = _text(owner_id, field="owner_id")
        answer_state = _choice(answer_state, field="answer_state", allowed=ANSWER_STATES)
        question_id = uuid.uuid4().hex
        revision_id = uuid.uuid4().hex
        now = now_iso()
        conn.execute(
            "INSERT INTO questions (id, owner_id, current_revision_id, status, created_at) "
            "VALUES (?, ?, ?, 'confirmed', ?)",
            (question_id, owner_id, revision_id, now),
        )
        conn.execute(
            "INSERT INTO question_revisions (id, question_id, content_json, metadata_json, "
            "answer_state, content_fingerprint, confirmed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                revision_id,
                question_id,
                json_fields.write_object(content, field="content_json"),
                json_fields.write_object(metadata, field="metadata_json"),
                answer_state,
                _text(content_fingerprint, field="content_fingerprint"),
                now,
            ),
        )
        self._insert_sources_in(conn, question_id, source_spans=source_spans, import_id=import_id)
        return self._question_record(conn, self._require_question_row_in(conn, question_id))

    def add_question_sources_in(
        self,
        conn: sqlite3.Connection,
        question_id: str,
        *,
        source_spans: Sequence[dict[str, Any]],
        import_id: str | None,
    ) -> int:
        return self._insert_sources_in(
            conn, _text(question_id, field="question_id"), source_spans=source_spans, import_id=import_id
        )

    def mark_draft_duplicate_in(
        self,
        conn: sqlite3.Connection,
        draft_id: str,
        *,
        question_id: str | None,
        warning: str,
        review_state: str | None = None,
    ) -> None:
        """记录重复判定结果：不动 content/metadata，也不改 revision（不打断乐观锁）。"""
        draft_id = _text(draft_id, field="draft_id")
        row = self._require_draft_row_in(conn, draft_id)
        warnings = json_fields.read_string_list(
            row["warnings_json"], field="question_drafts.warnings_json"
        )
        note = _text(warning, field="warning")
        if note not in warnings:
            warnings.append(note)
        state = row["review_state"]
        if review_state is not None:
            state = _choice(review_state, field="review_state", allowed=DRAFT_REVIEW_STATES)
        conn.execute(
            "UPDATE question_drafts SET duplicate_of_question_id = ?, warnings_json = ?, "
            "review_state = ? WHERE id = ?",
            (
                _optional_text(question_id, field="duplicate_of_question_id"),
                json_fields.write_string_list(warnings, field="warnings_json"),
                state,
                draft_id,
            ),
        )

    def questions_by_fingerprint_in(
        self, conn: sqlite3.Connection, owner_id: str, fingerprint: str
    ) -> list[QuestionRecord]:
        return self._questions_by_fingerprint_in(
            conn, _text(owner_id, field="owner_id"), _text(fingerprint, field="fingerprint")
        )

    def has_any_question_in(self, conn: sqlite3.Connection, owner_id: str) -> bool:
        row = conn.execute(
            "SELECT 1 AS present FROM questions WHERE owner_id = ? LIMIT 1",
            (_text(owner_id, field="owner_id"),),
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------ 任务

    def create_job(
        self,
        *,
        kind: str,
        state: str = "queued",
        checkpoint: dict[str, Any] | None = None,
    ) -> JobRecord:
        kind = _choice(kind, field="kind", allowed=JOB_KINDS)
        state = _choice(state, field="state", allowed=JOB_STATES)
        payload = json_fields.write_object(checkpoint or {}, field="checkpoint_json")
        job_id = uuid.uuid4().hex
        now = now_iso()
        with self._write() as conn:
            conn.execute(
                "INSERT INTO question_jobs (id, kind, state, checkpoint_json, error_code, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, NULL, ?, ?)",
                (job_id, kind, state, payload, now, now),
            )
            return self._job_record(self._job_row_in(conn, job_id))

    def get_job(self, job_id: str) -> JobRecord | None:
        job_id = _text(job_id, field="job_id")
        with self._read() as conn:
            row = self._job_row_in(conn, job_id)
        return self._job_record(row) if row is not None else None

    def update_job(
        self,
        job_id: str,
        *,
        state: str | None = None,
        checkpoint: dict[str, Any] | None = None,
        error_code: str | None = None,
        clear_error: bool = False,
    ) -> JobRecord:
        job_id = _text(job_id, field="job_id")
        updates: dict[str, object] = {}
        if state is not None:
            updates["state"] = _choice(state, field="state", allowed=JOB_STATES)
        if checkpoint is not None:
            updates["checkpoint_json"] = json_fields.write_object(
                checkpoint, field="checkpoint_json"
            )
        if clear_error:
            updates["error_code"] = None
        elif error_code is not None:
            updates["error_code"] = _text(error_code, field="error_code")
        with self._write() as conn:
            self._require_job_row_in(conn, job_id)
            if updates:
                self._apply_updates(conn, "question_jobs", job_id, updates)
            return self._job_record(self._job_row_in(conn, job_id))

    def pending_jobs(
        self,
        *,
        kinds: Sequence[str] = ("organize",),
        states: Sequence[str] = ("queued", "running"),
        limit: int = 8,
    ) -> list[JobRecord]:
        kind_values = [
            _choice(kind, field="kinds", allowed=JOB_KINDS) for kind in kinds
        ]
        state_values = [
            _choice(state, field="states", allowed=JOB_STATES) for state in states
        ]
        limit = _count(limit, field="limit", minimum=1)
        if not kind_values or not state_values:
            return []
        kind_placeholders = ", ".join("?" for _ in kind_values)
        state_placeholders = ", ".join("?" for _ in state_values)
        with self._read() as conn:
            rows = conn.execute(
                f"SELECT * FROM question_jobs WHERE kind IN ({kind_placeholders}) "
                f"AND state IN ({state_placeholders}) ORDER BY created_at ASC, rowid ASC LIMIT ?",
                (*kind_values, *state_values, limit),
            ).fetchall()
        return [self._job_record(row) for row in rows]

    def list_jobs(self, *, kind: str | None = None, limit: int = 50) -> list[JobRecord]:
        limit = _count(limit, field="limit", minimum=1)
        if limit > 500:
            raise _invalid("limit 不能超过 500。")
        clauses: list[str] = []
        params: list[object] = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(_choice(kind, field="kind", allowed=JOB_KINDS))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._read() as conn:
            rows = conn.execute(
                f"SELECT * FROM question_jobs{where} ORDER BY created_at DESC, rowid DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._job_record(row) for row in rows]

    # -------------------------------------------------------------- 内部写入

    def _draft_insert_values(self, import_id: str, draft: DraftInput) -> tuple:
        if not isinstance(draft, DraftInput):
            raise _invalid("drafts 元素必须是 DraftInput。")
        extraction_method = _choice(
            draft.extraction_method, field="extraction_method", allowed=EXTRACTION_METHODS
        )
        review_state = _choice(
            draft.review_state, field="review_state", allowed=DRAFT_REVIEW_STATES
        )
        if not isinstance(draft.missing_answer_acknowledged, bool):
            raise _invalid("missing_answer_acknowledged 必须是布尔值。")
        return (
            uuid.uuid4().hex,
            import_id,
            json_fields.write_object(draft.content, field="content_json"),
            json_fields.write_object(draft.metadata, field="metadata_json"),
            json_fields.write_object_list(list(draft.source_spans), field="source_spans_json"),
            extraction_method,
            review_state,
            int(draft.missing_answer_acknowledged),
            json_fields.write_string_list(list(draft.warnings), field="warnings_json"),
            _text_or_empty(draft.content_fingerprint, field="content_fingerprint"),
        )

    def _insert_drafts_in(self, conn: sqlite3.Connection, prepared: Sequence[tuple]) -> list[DraftRecord]:
        conn.executemany(
            "INSERT INTO question_drafts (id, import_id, revision, content_json, metadata_json, "
            "source_spans_json, extraction_method, review_state, missing_answer_acknowledged, "
            "warnings_json, content_fingerprint, duplicate_of_question_id) "
            "VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            [
                (
                    draft_id,
                    import_id,
                    content_json,
                    metadata_json,
                    source_spans_json,
                    extraction_method,
                    review_state,
                    acknowledged,
                    warnings_json,
                    content_fingerprint,
                )
                for (
                    draft_id,
                    import_id,
                    content_json,
                    metadata_json,
                    source_spans_json,
                    extraction_method,
                    review_state,
                    acknowledged,
                    warnings_json,
                    content_fingerprint,
                ) in prepared
            ],
        )
        return [
            self._draft_record(self._require_draft_row_in(conn, draft_id))
            for draft_id, *_rest in prepared
        ]

    def _insert_sources_in(
        self,
        conn: sqlite3.Connection,
        question_id: str,
        *,
        source_spans: Sequence[dict[str, Any]],
        import_id: str | None,
    ) -> int:
        if isinstance(source_spans, (str, bytes)) or not isinstance(source_spans, Sequence):
            raise _invalid("source_spans 必须是对象序列。")
        existing = {
            json_fields.dump(row["source_span_json"])
            for row in conn.execute(
                "SELECT source_span_json FROM question_sources WHERE question_id = ?",
                (question_id,),
            ).fetchall()
        }
        added = 0
        for span in source_spans:
            payload = json_fields.write_object(span, field="source_span_json")
            assert payload is not None
            if payload in existing:
                continue
            existing.add(payload)
            conn.execute(
                "INSERT INTO question_sources (question_id, source_span_json, import_id) "
                "VALUES (?, ?, ?)",
                (question_id, payload, _optional_text(import_id, field="import_id")),
            )
            added += 1
        return added

    def _apply_updates(
        self,
        conn: sqlite3.Connection,
        table: str,
        row_id: str,
        updates: dict[str, object],
    ) -> None:
        if table == "question_drafts":
            unknown = sorted(set(updates) - _DRAFT_UPDATE_COLUMNS)
            if unknown:
                raise _invalid(f"不允许更新的字段：{', '.join(unknown)}。")
        assignments = ", ".join(f"{column} = ?" for column in updates)
        if table == "question_drafts":
            conn.execute(
                f"UPDATE question_drafts SET {assignments}, revision = revision + 1 WHERE id = ?",
                (*updates.values(), row_id),
            )
        elif table == "question_imports":
            conn.execute(
                f"UPDATE question_imports SET {assignments}, revision = revision + 1, updated_at = ? "
                "WHERE id = ?",
                (*updates.values(), now_iso(), row_id),
            )
        elif table == "question_jobs":
            conn.execute(
                f"UPDATE question_jobs SET {assignments}, updated_at = ? WHERE id = ?",
                (*updates.values(), now_iso(), row_id),
            )
        else:  # pragma: no cover - 内部调用只使用上述三张表
            raise _corrupt(f"题库内部错误：未知的更新目标表 {table}。")

    @staticmethod
    def _check_revision(current: int, expected: int, *, what: str) -> None:
        if not isinstance(expected, int) or isinstance(expected, bool):
            raise _invalid("expected_revision 必须是整数。")
        if current != expected:
            raise _conflict(
                f"{what}已被其他操作更新（当前 revision={current}），请刷新后重试。",
                code="REVISION_CONFLICT",
            )

    # ------------------------------------------------------------ 内部：行

    def _import_row_in(self, conn: sqlite3.Connection, import_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM question_imports WHERE id = ?", (import_id,)).fetchone()

    def _require_import_row_in(self, conn: sqlite3.Connection, import_id: str) -> sqlite3.Row:
        row = self._import_row_in(conn, import_id)
        if row is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        return row

    def _draft_row_in(self, conn: sqlite3.Connection, draft_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM question_drafts WHERE id = ?", (draft_id,)).fetchone()

    def _require_draft_row_in(self, conn: sqlite3.Connection, draft_id: str) -> sqlite3.Row:
        row = self._draft_row_in(conn, draft_id)
        if row is None:
            raise _not_found("草稿不存在。", code="DRAFT_NOT_FOUND")
        return row

    def _question_row_in(self, conn: sqlite3.Connection, question_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()

    def _require_question_row_in(self, conn: sqlite3.Connection, question_id: str) -> sqlite3.Row:
        row = self._question_row_in(conn, question_id)
        if row is None:
            raise _not_found("题目不存在。", code="QUESTION_NOT_FOUND")
        return row

    def _job_row_in(self, conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM question_jobs WHERE id = ?", (job_id,)).fetchone()

    def _require_job_row_in(self, conn: sqlite3.Connection, job_id: str) -> sqlite3.Row:
        row = self._job_row_in(conn, job_id)
        if row is None:
            raise _not_found("整理任务不存在。", code="JOB_NOT_FOUND")
        return row

    def _revision_count_in(self, conn: sqlite3.Connection, question_id: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM question_revisions WHERE question_id = ?",
            (question_id,),
        ).fetchone()
        return _stored_count(row["total"], field="question_revisions.count")

    # ------------------------------------------------------- 内部：记录映射

    def _source_block_records_in(
        self, conn: sqlite3.Connection, import_id: str
    ) -> list[SourceBlockRecord]:
        rows = conn.execute(
            "SELECT * FROM question_source_blocks WHERE import_id = ? "
            "ORDER BY ordinal ASC, rowid ASC",
            (import_id,),
        ).fetchall()
        return [self._source_block_record(row) for row in rows]

    def _source_block_record(self, row: sqlite3.Row) -> SourceBlockRecord:
        locator = json_fields.read_object(
            row["locator_json"], field="question_source_blocks.locator_json"
        )
        assert locator is not None
        kind = locator.get("kind")
        if kind not in LOCATOR_KINDS:
            raise _corrupt("题库数据损坏：原文块 locator.kind 非法。")
        return SourceBlockRecord(
            block_id=_stored_text(row["id"], field="question_source_blocks.id"),
            import_id=_stored_text(row["import_id"], field="question_source_blocks.import_id"),
            ordinal=_stored_count(row["ordinal"], field="question_source_blocks.ordinal"),
            text=_stored_maybe_empty(row["text"], field="question_source_blocks.text"),
            locator=locator,
        )

    def _import_record(self, row: sqlite3.Row) -> ImportRecord:
        state = row["state"]
        if state not in IMPORT_STATES:
            raise _corrupt("题库数据损坏：question_imports.state 结构不符。")
        return ImportRecord(
            import_id=_stored_text(row["id"], field="question_imports.id"),
            owner_id=_stored_text(row["owner_id"], field="question_imports.owner_id"),
            file_sha256=_stored_text(row["file_sha256"], field="question_imports.file_sha256"),
            original_blob_id=_stored_text(
                row["original_blob_id"], field="question_imports.original_blob_id"
            ),
            uploaded_file_name=_stored_text(
                row["uploaded_file_name"], field="question_imports.uploaded_file_name"
            ),
            uploaded_bytes=_stored_count(
                row["uploaded_bytes"], field="question_imports.uploaded_bytes"
            ),
            state=state,
            revision=_stored_count(row["revision"], field="question_imports.revision"),
            warnings=tuple(
                json_fields.read_string_list(
                    row["warnings_json"], field="question_imports.warnings_json"
                )
            ),
            error_code=row["error_code"],
            created_at=_stored_text(row["created_at"], field="question_imports.created_at"),
            updated_at=_stored_text(row["updated_at"], field="question_imports.updated_at"),
        )

    def _draft_record(self, row: sqlite3.Row) -> DraftRecord:
        review_state = row["review_state"]
        if review_state not in DRAFT_REVIEW_STATES:
            raise _corrupt("题库数据损坏：question_drafts.review_state 结构不符。")
        extraction_method = row["extraction_method"]
        if extraction_method not in EXTRACTION_METHODS:
            raise _corrupt("题库数据损坏：question_drafts.extraction_method 结构不符。")
        content = json_fields.read_object(row["content_json"], field="question_drafts.content_json")
        metadata = json_fields.read_object(
            row["metadata_json"], field="question_drafts.metadata_json"
        )
        assert content is not None and metadata is not None
        return DraftRecord(
            draft_id=_stored_text(row["id"], field="question_drafts.id"),
            import_id=_stored_text(row["import_id"], field="question_drafts.import_id"),
            revision=_stored_count(row["revision"], field="question_drafts.revision"),
            content=content,
            metadata=metadata,
            source_spans=json_fields.read_object_list(
                row["source_spans_json"], field="question_drafts.source_spans_json"
            ),
            extraction_method=extraction_method,
            review_state=review_state,
            missing_answer_acknowledged=_stored_flag(
                row["missing_answer_acknowledged"],
                field="question_drafts.missing_answer_acknowledged",
            ),
            warnings=tuple(
                json_fields.read_string_list(
                    row["warnings_json"], field="question_drafts.warnings_json"
                )
            ),
            content_fingerprint=_stored_maybe_empty(
                row["content_fingerprint"], field="question_drafts.content_fingerprint"
            ),
            duplicate_of_question_id=row["duplicate_of_question_id"],
        )

    def _draft_records_in(self, conn: sqlite3.Connection, import_id: str) -> list[DraftRecord]:
        rows = conn.execute(
            "SELECT * FROM question_drafts WHERE import_id = ? ORDER BY rowid ASC", (import_id,)
        ).fetchall()
        return [self._draft_record(row) for row in rows]

    def _suggestion_record(self, row: sqlite3.Row) -> SuggestionRecord:
        state = row["state"]
        if state not in SUGGESTION_STATES:
            raise _corrupt("题库数据损坏：question_suggestions.state 结构不符。")
        proposed_content = json_fields.read_object(
            row["proposed_content_json"], field="question_suggestions.proposed_content_json"
        )
        proposed_metadata = json_fields.read_object(
            row["proposed_metadata_json"], field="question_suggestions.proposed_metadata_json"
        )
        assert proposed_content is not None and proposed_metadata is not None
        return SuggestionRecord(
            suggestion_id=_stored_text(row["id"], field="question_suggestions.id"),
            organization_job_id=_stored_text(
                row["organization_job_id"], field="question_suggestions.organization_job_id"
            ),
            target_draft_id=_stored_text(
                row["target_draft_id"], field="question_suggestions.target_draft_id"
            ),
            base_draft_revision=_stored_count(
                row["base_draft_revision"], field="question_suggestions.base_draft_revision"
            ),
            proposed_content=proposed_content,
            proposed_metadata=proposed_metadata,
            source_block_ids=tuple(
                json_fields.read_string_list(
                    row["source_block_ids_json"], field="question_suggestions.source_block_ids_json"
                )
            ),
            state=state,
            note=row["note"],
        )

    def _questions_by_fingerprint_in(
        self, conn: sqlite3.Connection, owner_id: str, fingerprint: str
    ) -> list[QuestionRecord]:
        rows = conn.execute(
            "SELECT q.* FROM questions AS q JOIN question_revisions AS r "
            "ON r.id = q.current_revision_id WHERE q.owner_id = ? "
            "AND q.status = 'confirmed' AND r.content_fingerprint = ? "
            "ORDER BY q.created_at ASC, q.rowid ASC",
            (owner_id, fingerprint),
        ).fetchall()
        return [self._question_record(conn, row) for row in rows]

    def _question_record(self, conn: sqlite3.Connection, row: sqlite3.Row) -> QuestionRecord:
        revision_row = conn.execute(
            "SELECT * FROM question_revisions WHERE id = ?", (row["current_revision_id"],)
        ).fetchone()
        if revision_row is None:
            raise _corrupt("题库数据损坏：题目的当前修订缺失。")
        answer_state = revision_row["answer_state"]
        if answer_state not in ANSWER_STATES:
            raise _corrupt("题库数据损坏：question_revisions.answer_state 结构不符。")
        status = row["status"]
        if status not in QUESTION_STATUSES:
            raise _corrupt("题库数据损坏：questions.status 结构不符。")
        content = json_fields.read_object(
            revision_row["content_json"], field="question_revisions.content_json"
        )
        metadata = json_fields.read_object(
            revision_row["metadata_json"], field="question_revisions.metadata_json"
        )
        assert content is not None and metadata is not None
        source_rows = conn.execute(
            "SELECT source_span_json, import_id FROM question_sources WHERE question_id = ? "
            "ORDER BY rowid ASC",
            (row["id"],),
        ).fetchall()
        sources: list[dict[str, Any]] = []
        import_id: str | None = None
        for source_row in source_rows:
            span = json_fields.read_object(
                source_row["source_span_json"], field="question_sources.source_span_json"
            )
            assert span is not None
            sources.append(span)
            if import_id is None and source_row["import_id"] is not None:
                import_id = source_row["import_id"]
        return QuestionRecord(
            question_id=_stored_text(row["id"], field="questions.id"),
            owner_id=_stored_text(row["owner_id"], field="questions.owner_id"),
            current_revision_id=_stored_text(
                row["current_revision_id"], field="questions.current_revision_id"
            ),
            status=status,
            created_at=_stored_text(row["created_at"], field="questions.created_at"),
            revision=self._revision_count_in(conn, row["id"]),
            content=content,
            metadata=metadata,
            answer_state=answer_state,
            content_fingerprint=_stored_text(
                revision_row["content_fingerprint"], field="question_revisions.content_fingerprint"
            ),
            confirmed_at=_stored_text(
                revision_row["confirmed_at"], field="question_revisions.confirmed_at"
            ),
            sources=tuple(sources),
            source_import_id=import_id,
        )

    def _job_record(self, row: sqlite3.Row) -> JobRecord:
        kind = row["kind"]
        state = row["state"]
        if kind not in JOB_KINDS or state not in JOB_STATES:
            raise _corrupt("题库数据损坏：question_jobs 的 kind/state 结构不符。")
        checkpoint = json_fields.read_object(
            row["checkpoint_json"], field="question_jobs.checkpoint_json"
        )
        assert checkpoint is not None
        return JobRecord(
            job_id=_stored_text(row["id"], field="question_jobs.id"),
            kind=kind,
            state=state,
            checkpoint=checkpoint,
            error_code=row["error_code"],
            created_at=_stored_text(row["created_at"], field="question_jobs.created_at"),
            updated_at=_stored_text(row["updated_at"], field="question_jobs.updated_at"),
        )
