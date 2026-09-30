"""V1 迁移登记独立探针（V00 / TEACHING-LOOP B0）。

覆盖：
  1① 重复 apply 不改既有行、不重复登记（含库文件字节对比）
  1② 中途失败迁移整体回滚（表未建、未登记）→ 修复后重跑成功
  1③ 篡改 schema_migrations.sha256 / 改写已登记 SQL → SCHEMA_MIGRATION_DRIFT
  1④ 旧库采纳：手工造"无 schema_migrations 但已有题库九表 + 数据"的旧库 →
      apply 后基线登记、既有行逐字节不变

独立构造：旧库 DDL 取自候选起点之前的历史版本
（`git show 301fc356:apps/api/app/repositories/question_bank/schema.py`，逐字复制），
不使用候选的迁移模块生成，避免"用被测代码造夹具"。
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from _probe_common import (
    check,
    cleanup,
    expect_error,
    record,
    run_main,
    temp_root,
)

# --- 候选模块（探针运行时导入，不改动） ---
from app.core.exceptions import AppError
from app.core.migrations import (
    Migration,
    REGISTERED_MIGRATIONS,
    applied_migrations,
    apply_migrations,
    verify_migrations,
)
from app.core.sqlite import connect

PROBE = "v1_migrations_probe"


def _dump_all(connection: sqlite3.Connection) -> dict:
    """整库逻辑快照：表/索引 DDL + 每张表逐行（列值，含 schema_migrations）。"""
    snapshot: dict = {}
    objects = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
    ).fetchall()
    snapshot["schema"] = sorted(
        (row["type"], row["name"], row["tbl_name"], row["sql"]) for row in objects
    )
    for row in objects:
        if row["type"] != "table" or str(row["name"]).startswith("sqlite_"):
            continue
        columns = [
            info["name"]
            for info in connection.execute(f'PRAGMA table_info("{row["name"]}")')
        ]
        order = ", ".join(f'"{column}"' for column in columns)
        rows = [
            tuple(data[c] for c in columns)
            for data in connection.execute(f'SELECT {order} FROM "{row["name"]}"')
        ]
        snapshot[f"table:{row['name']}"] = rows
    return snapshot


def _column_bytes(connection: sqlite3.Connection, table: str, where: str) -> dict:
    """某行既有列的**逐列字节**（HEX(CAST(col AS BLOB))），用于"逐字节不变"断言。"""
    columns = [info["name"] for info in connection.execute(f'PRAGMA table_info("{table}")')]
    expr = ", ".join(f"HEX(CAST(\"{c}\" AS BLOB)) AS \"{c}\"" for c in columns)
    row = connection.execute(f'SELECT {expr} FROM "{table}" WHERE {where}').fetchone()
    return {c: row[c] for c in columns} if row is not None else {}


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _settle(path: Path) -> str:
    """关闭所有连接后把 WAL 归并并返回文件 sha256（用于"无写入"对比）。"""
    connection = sqlite3.connect(str(path), isolation_level=None)
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()
    return _file_hash(path)


def part_1(root: Path) -> None:
    db = root / "teaching.sqlite3"
    connection = connect(db)
    try:
        first = apply_migrations(connection, database="teaching")
        check("v1.1a fresh apply registers baseline", first == ["0001_teaching_baseline"], str(first))
        before = _dump_all(connection)
    finally:
        connection.close()
    hash_before = _settle(db)

    connection = connect(db)
    try:
        second = apply_migrations(connection, database="teaching")
        after = _dump_all(connection)
    finally:
        connection.close()
    hash_after = _settle(db)

    check("v1.1b repeat apply applies nothing", second == [], str(second))
    check(
        "v1.1c repeat apply leaves every table/row identical",
        before == after,
        "dump equal" if before == after else f"diff keys={[k for k in before if before.get(k) != after.get(k)]}",
    )
    check(
        "v1.1d repeat apply leaves db file byte-identical",
        hash_before == hash_after,
        f"{hash_before[:16]} vs {hash_after[:16]}",
    )
    check(
        "v1.1e no duplicate registration row",
        len(after["table:schema_migrations"]) == 1,
        str(after["table:schema_migrations"]),
    )


def part_2(root: Path) -> None:
    db = root / "knowledge.sqlite3"
    original = REGISTERED_MIGRATIONS["knowledge"]
    bad = Migration(
        id="9001_probe_bad",
        description="探针注入的坏迁移（中途失败）",
        statements=(
            "CREATE TABLE IF NOT EXISTS probe_tmp (x INTEGER)",
            "SELECT * FROM probe_table_that_does_not_exist",
        ),
    )
    fixed = Migration(
        id="9001_probe_bad",
        description="探针注入的坏迁移（修复后）",
        statements=(
            "CREATE TABLE IF NOT EXISTS probe_tmp (x INTEGER)",
            "CREATE INDEX IF NOT EXISTS idx_probe_tmp ON probe_tmp(x)",
        ),
    )
    connection = connect(db)
    try:
        REGISTERED_MIGRATIONS["knowledge"] = original + (bad,)
        try:
            apply_migrations(connection, database="knowledge")
            record("v1.2a failing migration raises", False, "no exception")
        except (sqlite3.Error, AppError) as exc:
            record("v1.2a failing migration raises", True, f"{type(exc).__name__}: {exc}")
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        check("v1.2b failed migration left no table", "probe_tmp" not in tables, str(sorted(tables)))
        registered = applied_migrations(connection)
        check(
            "v1.2c failed migration not registered",
            "9001_probe_bad" not in registered,
            str(sorted(registered)),
        )
        baseline_registered = "0001_knowledge_baseline" in registered
        check(
            "v1.2d per-migration transactions: baseline kept, failed one rolled back",
            baseline_registered,
            f"baseline_registered={baseline_registered}（每条迁移独立事务：失败条不登记，"
            "已成功的基线保留）",
        )

        REGISTERED_MIGRATIONS["knowledge"] = original + (fixed,)
        applied_now = apply_migrations(connection, database="knowledge")
        check("v1.2e rerun after fix succeeds", "9001_probe_bad" in applied_now, str(applied_now))
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        check("v1.2f fixed migration created its table", "probe_tmp" in tables, str(sorted(tables)))
    finally:
        REGISTERED_MIGRATIONS["knowledge"] = original
        connection.close()


def part_3(root: Path) -> None:
    db = root / "teaching-drift.sqlite3"
    connection = connect(db)
    try:
        apply_migrations(connection, database="teaching")
        connection.execute(
            "UPDATE schema_migrations SET sha256 = ? WHERE id = ?",
            ("00" * 32, "0001_teaching_baseline"),
        )
        try:
            verify_migrations(connection, database="teaching")
            record("v1.3a tampered registry sha256 -> drift on verify", False, "no exception")
        except AppError as exc:
            expect_error("v1.3a tampered registry sha256 -> drift on verify", exc, "SCHEMA_MIGRATION_DRIFT")
        try:
            apply_migrations(connection, database="teaching")
            record("v1.3b tampered registry sha256 -> drift on apply", False, "no exception")
        except AppError as exc:
            expect_error("v1.3b tampered registry sha256 -> drift on apply", exc, "SCHEMA_MIGRATION_DRIFT")
    finally:
        connection.close()

    # 反向：登记散列未变，但迁移 SQL 被改写（模拟"改写已冻结基线"）
    db2 = root / "teaching-sql-changed.sqlite3"
    connection = connect(db2)
    original = REGISTERED_MIGRATIONS["teaching"]
    try:
        apply_migrations(connection, database="teaching")
        baseline = original[0]
        changed = Migration(
            id=baseline.id,
            description=baseline.description,
            statements=baseline.statements
            + ("CREATE TABLE IF NOT EXISTS probe_rewritten_baseline (x INTEGER)",),
        )
        REGISTERED_MIGRATIONS["teaching"] = (changed,)
        try:
            verify_migrations(connection, database="teaching")
            record("v1.3c rewritten registered SQL -> drift", False, "no exception")
        except AppError as exc:
            expect_error("v1.3c rewritten registered SQL -> drift", exc, "SCHEMA_MIGRATION_DRIFT")
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        check(
            "v1.3d drift refuses without executing new SQL",
            "probe_rewritten_baseline" not in tables,
            str(sorted(tables)),
        )
    finally:
        REGISTERED_MIGRATIONS["teaching"] = original
        connection.close()


LEGACY_DDL = """
CREATE TABLE IF NOT EXISTS question_imports (
    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, file_sha256 TEXT NOT NULL,
    original_blob_id TEXT NOT NULL, uploaded_file_name TEXT NOT NULL,
    uploaded_bytes INTEGER NOT NULL, state TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0, warnings_json TEXT NOT NULL DEFAULT '[]',
    error_code TEXT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS question_source_blocks (
    id TEXT PRIMARY KEY, import_id TEXT NOT NULL REFERENCES question_imports(id),
    ordinal INTEGER NOT NULL, text TEXT NOT NULL, locator_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS question_drafts (
    id TEXT PRIMARY KEY, import_id TEXT NOT NULL REFERENCES question_imports(id),
    revision INTEGER NOT NULL DEFAULT 0, content_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL, source_spans_json TEXT NOT NULL DEFAULT '[]',
    extraction_method TEXT NOT NULL, review_state TEXT NOT NULL,
    missing_answer_acknowledged INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]', content_fingerprint TEXT NOT NULL DEFAULT '',
    duplicate_of_question_id TEXT NULL);
CREATE TABLE IF NOT EXISTS question_suggestions (
    id TEXT PRIMARY KEY, organization_job_id TEXT NOT NULL,
    target_draft_id TEXT NOT NULL REFERENCES question_drafts(id),
    base_draft_revision INTEGER NOT NULL, proposed_content_json TEXT NOT NULL,
    proposed_metadata_json TEXT NOT NULL,
    source_block_ids_json TEXT NOT NULL DEFAULT '[]', state TEXT NOT NULL, note TEXT NULL);
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
    current_revision_id TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS question_revisions (
    id TEXT PRIMARY KEY, question_id TEXT NOT NULL, content_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL, answer_state TEXT NOT NULL,
    content_fingerprint TEXT NOT NULL, confirmed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS question_sources (
    question_id TEXT NOT NULL, source_span_json TEXT NOT NULL, import_id TEXT NULL);
CREATE TABLE IF NOT EXISTS question_submissions (
    submission_id TEXT PRIMARY KEY, request_fingerprint TEXT NOT NULL,
    result_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS question_jobs (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL,
    checkpoint_json TEXT NOT NULL DEFAULT '{}', error_code TEXT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_question_source_blocks_import ON question_source_blocks(import_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_question_drafts_import ON question_drafts(import_id);
CREATE INDEX IF NOT EXISTS idx_question_suggestions_job ON question_suggestions(organization_job_id, state);
CREATE INDEX IF NOT EXISTS idx_question_suggestions_draft ON question_suggestions(target_draft_id);
CREATE INDEX IF NOT EXISTS idx_question_revisions_question ON question_revisions(question_id);
CREATE INDEX IF NOT EXISTS idx_question_sources_question ON question_sources(question_id);
CREATE INDEX IF NOT EXISTS idx_questions_owner ON questions(owner_id, status);
CREATE INDEX IF NOT EXISTS idx_question_jobs_state ON question_jobs(kind, state);
"""


def part_4(root: Path) -> None:
    db = root / "question-bank.sqlite3"
    # 用历史 DDL 造"旧库"（无 schema_migrations）；纯 sqlite3，绕过候选迁移模块。
    raw = sqlite3.connect(str(db))
    try:
        raw.executescript(LEGACY_DDL)
        raw.execute(
            "INSERT INTO question_imports (id, owner_id, file_sha256, original_blob_id, "
            "uploaded_file_name, uploaded_bytes, state, revision, warnings_json, "
            "error_code, created_at, updated_at) VALUES "
            "('imp-legacy', 'local', 'ff00', 'ab12', '旧.docx', 42, 'ready', 3, '[]', NULL, "
            "'2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z')"
        )
        raw.execute(
            "INSERT INTO questions (id, owner_id, current_revision_id, status, created_at) "
            "VALUES ('q-legacy', 'local', 'rev-legacy', 'confirmed', '2026-09-01T00:00:00Z')"
        )
        raw.execute(
            "INSERT INTO question_jobs (id, kind, state, checkpoint_json, error_code, "
            "created_at, updated_at) VALUES "
            "('job-legacy', 'organize', 'succeeded', '{\"step\":4}', NULL, "
            "'2026-09-01T00:00:00Z', '2026-09-01T01:00:00Z')"
        )
        raw.commit()
    finally:
        raw.close()

    check(
        "v1.4a legacy fixture has no schema_migrations",
        _table_names(db) == sorted(
            {
                "question_imports",
                "question_source_blocks",
                "question_drafts",
                "question_suggestions",
                "questions",
                "question_revisions",
                "question_sources",
                "question_submissions",
                "question_jobs",
            }
        ),
        str(_table_names(db)),
    )

    connection = connect(db)  # 候选统一连接（WAL/busy_timeout）
    try:
        before_imports = _column_bytes(connection, "question_imports", "id='imp-legacy'")
        before_questions = _column_bytes(connection, "questions", "id='q-legacy'")
        before_jobs = _column_bytes(connection, "question_jobs", "id='job-legacy'")
        before_schema = {
            row["name"]: row["sql"]
            for row in connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table'"
            )
        }
        before_job_columns = [
            info["name"] for info in connection.execute("PRAGMA table_info(question_jobs)")
        ]

        applied_now = apply_migrations(connection, database="question_bank")
        registered = applied_migrations(connection)

        after_imports = _column_bytes(connection, "question_imports", "id='imp-legacy'")
        after_questions = _column_bytes(connection, "questions", "id='q-legacy'")
        after_jobs = _column_bytes(connection, "question_jobs", "id='job-legacy'")
        after_schema = {
            row["name"]: row["sql"]
            for row in connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table'"
            )
        }
        after_job_columns = [
            info["name"] for info in connection.execute("PRAGMA table_info(question_jobs)")
        ]
    finally:
        connection.close()

    check(
        "v1.4b legacy db adopted: baseline + engine migration registered",
        set(registered) >= {"0001_question_bank_baseline", "0002_question_jobs_engine_columns"},
        f"applied_now={applied_now} registered={sorted(registered)}",
    )
    check(
        "v1.4c pre-existing question_imports row byte-identical",
        before_imports == after_imports,
        "" if before_imports == after_imports else f"{before_imports} != {after_imports}",
    )
    check(
        "v1.4d pre-existing questions row byte-identical",
        before_questions == after_questions,
        "" if before_questions == after_questions else f"{before_questions} != {after_questions}",
    )
    check(
        "v1.4e pre-existing question_jobs row: legacy columns byte-identical",
        all(after_jobs.get(c) == v for c, v in before_jobs.items()),
        "" if all(after_jobs.get(c) == v for c, v in before_jobs.items()) else f"{before_jobs} vs {after_jobs}",
    )
    unchanged_others = [
        t for t in before_schema if t != "question_jobs" and before_schema.get(t) != after_schema.get(t)
    ]
    check(
        "v1.4f legacy tables DDL untouched (question_jobs 除外：ADD COLUMN 是本批冻结增量)",
        not unchanged_others,
        f"changed={unchanged_others}",
    )
    job_ddl_changed = before_schema.get("question_jobs") != after_schema.get("question_jobs")
    engine_columns = [c for c in after_job_columns if c not in before_job_columns]
    legacy_declared_kept = all(
        c in after_schema["question_jobs"] for c in before_job_columns
    )
    new_declared = all(c in after_schema["question_jobs"] for c in engine_columns)
    check(
        "v1.4f2 question_jobs DDL change is append-only ADD COLUMN",
        job_ddl_changed and legacy_declared_kept and new_declared,
        f"changed={job_ddl_changed} legacy_kept={legacy_declared_kept} new_declared={new_declared}",
    )
    new_columns = [c for c in after_job_columns if c not in before_job_columns]
    check(
        "v1.4g engine columns appended (ALTER TABLE, additive only)",
        "frozen_input_json" in new_columns and "lease_token" in new_columns,
        f"new_columns={new_columns}",
    )
    check(
        "v1.4h legacy columns order preserved",
        after_job_columns[: len(before_job_columns)] == before_job_columns,
        f"{after_job_columns}",
    )


def _table_names(db: Path) -> list[str]:
    raw = sqlite3.connect(str(db))
    try:
        return sorted(
            row[0]
            for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")
        )
    finally:
        raw.close()


def main() -> None:
    root = temp_root("v1")
    try:
        for part in ("p1", "p2", "p3", "p4"):
            (root / part).mkdir(parents=True, exist_ok=True)
        part_1(root / "p1")
        part_2(root / "p2")
        part_3(root / "p3")
        part_4(root / "p4")
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
