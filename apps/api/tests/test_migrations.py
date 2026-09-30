"""迁移登记框架测试（TEACHING-LOOP B0 / 验收 A1–A3）。

覆盖：四库登记、重复 apply 幂等、失败迁移整体回滚且可重跑、已登记迁移散列漂移
拒绝、未知库角色、既有旧库（无登记表）首次登记不改变数据。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.core.migrations import (
    DATABASES,
    REGISTERED_MIGRATIONS,
    Migration,
    applied_migrations,
    apply_migrations,
    pending_migrations,
    statement_digest,
    verify_migrations,
)
from app.core.sqlite import connect, now_iso

EXPECTED_FOUNDATION = {
    "textbooks": {"catalog_state", "documents", "chunks", "index_jobs"},
    "question_bank": {"questions", "question_jobs", "question_submissions"},
    "knowledge": {"knowledge_submissions", "knowledge_jobs"},
    "teaching": {"command_submissions", "file_assets", "workflow_jobs"},
}


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def test_all_databases_register_and_apply_idempotently(tmp_path: Path) -> None:
    for database in DATABASES:
        path = tmp_path / f"{database}.sqlite3"
        connection = connect(path)
        try:
            first = apply_migrations(connection, database=database)
            assert first, f"{database} 首次迁移未登记任何条目"
            assert set(first) == {migration.id for migration in REGISTERED_MIGRATIONS[database]}

            records = applied_migrations(connection)
            assert set(records) == set(first)

            # 重复 apply：不返回新条目、不改变登记内容
            second = apply_migrations(connection, database=database)
            assert second == []
            assert applied_migrations(connection) == records

            # 结构齐备
            present = _table_names(connection)
            assert EXPECTED_FOUNDATION[database] <= present
            assert "schema_migrations" in present
            assert pending_migrations(connection, database=database) == []
            verify_migrations(connection, database=database)
        finally:
            connection.close()


def test_question_jobs_gains_engine_columns(tmp_path: Path) -> None:
    connection = connect(tmp_path / "question-bank.sqlite3")
    try:
        apply_migrations(connection, database="question_bank")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(question_jobs)")}
    finally:
        connection.close()
    required = {
        "owner_id",
        "frozen_input_json",
        "input_hash",
        "model_snapshot_json",
        "attempt",
        "lease_token",
        "lease_expires_at",
        "cancel_requested",
        "result_json",
        "error_json",
        "started_at",
        "finished_at",
    }
    assert required <= columns


def test_apply_is_idempotent_and_preserves_data(tmp_path: Path) -> None:
    path = tmp_path / "teaching.sqlite3"
    connection = connect(path)
    try:
        apply_migrations(connection, database="teaching")
        with connection:
            connection.execute(
                "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, "
                "original_name, media_type, byte_size, created_at) VALUES "
                "('a1', 'local', 'paper', 'blobs/' || ?, ?, 'x.docx', "
                "'application/vnd', 3, ?)",
                ("a" * 64, "a" * 64, now_iso()),
            )
        before = connection.execute("SELECT COUNT(*) FROM file_assets").fetchone()[0]
        apply_migrations(connection, database="teaching")
        after = connection.execute("SELECT COUNT(*) FROM file_assets").fetchone()[0]
        assert before == after == 1
        # 登记表只保留一条同名记录（不重复插入）
        count = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE id = ?",
            ("0001_teaching_baseline",),
        ).fetchone()[0]
        assert count == 1
    finally:
        connection.close()


def test_failed_migration_rolls_back_and_can_be_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "knowledge.sqlite3"
    connection = connect(path)
    original = REGISTERED_MIGRATIONS["knowledge"]
    try:
        baseline_applied = apply_migrations(connection, database="knowledge")
        # 只要求"当前登记的全部迁移都已应用"，不硬编码条数（B1 起会持续追加）
        assert baseline_applied == [migration.id for migration in original]

        failing = Migration(
            id="0002_broken",
            description="故意失败：第二条语句不是 SQL",
            statements=(
                "CREATE TABLE should_roll_back (id TEXT PRIMARY KEY)",
                "THIS IS NOT VALID SQL",
            ),
        )
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "knowledge", (*original, failing))
        with pytest.raises(sqlite3.Error):
            apply_migrations(connection, database="knowledge")

        # 失败迁移整体回滚：表未建、也未登记
        assert "should_roll_back" not in _table_names(connection)
        assert "0002_broken" not in applied_migrations(connection)
        # 基线仍完好
        assert "knowledge_jobs" in _table_names(connection)

        # 修复后重跑成功
        fixed = Migration(
            id="0002_broken",
            description="修复后的迁移",
            statements=("CREATE TABLE fixed_table (id TEXT PRIMARY KEY)", "SELECT 1"),
        )
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "knowledge", (*original, fixed))
        applied = apply_migrations(connection, database="knowledge")
        assert applied == ["0002_broken"]
        assert "fixed_table" in _table_names(connection)
    finally:
        connection.close()


def test_drift_detection_refuses_rewritten_migration(tmp_path: Path) -> None:
    connection = connect(tmp_path / "knowledge.sqlite3")
    try:
        apply_migrations(connection, database="knowledge")
        connection.execute(
            "UPDATE schema_migrations SET sha256 = 'deadbeef' WHERE id = ?",
            ("0001_knowledge_baseline",),
        )
        with pytest.raises(AppError) as apply_error:
            apply_migrations(connection, database="knowledge")
        assert apply_error.value.code == "SCHEMA_MIGRATION_DRIFT"

        with pytest.raises(AppError) as verify_error:
            verify_migrations(connection, database="knowledge")
        assert verify_error.value.code == "SCHEMA_MIGRATION_DRIFT"
    finally:
        connection.close()


def test_unknown_database_role_is_rejected(tmp_path: Path) -> None:
    connection = connect(tmp_path / "x.sqlite3")
    try:
        with pytest.raises(AppError) as error:
            apply_migrations(connection, database="unknown_db")
        assert error.value.code == "SCHEMA_DATABASE_UNKNOWN"
        with pytest.raises(AppError):
            verify_migrations(connection, database="unknown_db")
    finally:
        connection.close()


def test_legacy_database_without_registry_is_adopted(tmp_path: Path) -> None:
    """既有旧库（由旧版 migrate 建出、没有 schema_migrations）首次登记不改变数据。"""
    path = tmp_path / "question-bank.sqlite3"
    connection = connect(path)
    try:
        # 模拟旧库：直接跑基线语句，再删掉登记表
        baseline = REGISTERED_MIGRATIONS["question_bank"][0]
        for statement in baseline.statements:
            connection.execute(statement)
        connection.execute("DROP TABLE IF EXISTS schema_migrations")
        connection.execute(
            "INSERT INTO question_imports (id, owner_id, file_sha256, original_blob_id, "
            "uploaded_file_name, uploaded_bytes, state, revision, warnings_json, "
            "created_at, updated_at) VALUES ('imp-1','local','x','blob','f.md',1,"
            "'needs_review',0,'[]', ?, ?)",
            (now_iso(), now_iso()),
        )

        applied = apply_migrations(connection, database="question_bank")
        assert applied == [
            "0001_question_bank_baseline",
            "0002_question_jobs_engine_columns",
            "0003_question_jobs_engine_state_index",
        ]
        row = connection.execute(
            "SELECT id, revision FROM question_imports WHERE id = 'imp-1'"
        ).fetchone()
        assert row is not None and row[0] == "imp-1"
    finally:
        connection.close()


def test_statement_digest_is_stable_and_content_sensitive() -> None:
    first = statement_digest(("SELECT 1", "  SELECT 2  "))
    assert first == statement_digest(("SELECT 1", "SELECT 2"))
    assert first != statement_digest(("SELECT 1", "SELECT 3"))


def _index_columns(connection: sqlite3.Connection, table: str) -> dict[str, list[str]]:
    indexes: dict[str, list[str]] = {}
    for row in connection.execute(f"PRAGMA index_list({table})"):
        name = row[1]
        columns = [
            info[2]
            for info in connection.execute(f'PRAGMA index_info("{name}")')
        ]
        indexes[name] = columns
    return indexes


def test_task_tables_have_state_created_at_indexes(tmp_path: Path) -> None:
    """T00-a-02（V00 验收 fail）：三张任务表都必须有 (state, created_at) 索引。"""
    expectations = {
        "question_bank": ("question_jobs", "0003_question_jobs_engine_state_index"),
        "knowledge": ("knowledge_jobs", None),
        "teaching": ("workflow_jobs", None),
    }
    for database, (table, extra_migration) in expectations.items():
        connection = connect(tmp_path / f"{database}-index.sqlite3")
        try:
            applied = apply_migrations(connection, database=database)
            if extra_migration is not None:
                assert extra_migration in applied
            indexes = _index_columns(connection, table)
            assert any(columns == ["state", "created_at"] for columns in indexes.values()), (
                database,
                indexes,
            )
        finally:
            connection.close()


def test_existing_database_already_on_0002_gains_index_from_0003(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """既有库（已登记 0001+0002、列已补齐但没有索引）由 0003 补齐，且 0002 散列不变。

    构造"修复前现场"：手工执行 0002 的 12 条 ALTER（模拟旧钩子的效果），并用 0002 的
    当前散列登记它；随后应用完整清单只应新增 0003，0002 不得被判为漂移。
    """
    path = tmp_path / "question-bank.sqlite3"
    connection = connect(path)
    original = REGISTERED_MIGRATIONS["question_bank"]
    try:
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "question_bank", original[:1])
        apply_migrations(connection, database="question_bank")

        engine_migration = original[1]
        for statement in engine_migration.statements[:-1]:  # 12 条 ALTER
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations (id, sha256, applied_at) VALUES (?, ?, ?)",
            (engine_migration.id, engine_migration.sha256, now_iso()),
        )
        before = _index_columns(connection, "question_jobs")
        assert not any(
            columns == ["state", "created_at"] for columns in before.values()
        ), before

        monkeypatch.setitem(REGISTERED_MIGRATIONS, "question_bank", original)
        applied_again = apply_migrations(connection, database="question_bank")
        assert applied_again == ["0003_question_jobs_engine_state_index"]
        after = _index_columns(connection, "question_jobs")
        assert any(columns == ["state", "created_at"] for columns in after.values()), after
        assert applied_migrations(connection)[engine_migration.id] == engine_migration.sha256
    finally:
        connection.close()


def test_adjust_hooks_execute_every_declared_statement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """带 adjust 钩子的迁移在**全新库**上必须返回全部声明语句（防止声明与执行不一致）。"""
    for database, migrations in REGISTERED_MIGRATIONS.items():
        connection = connect(tmp_path / f"{database}-hook.sqlite3")
        try:
            for index in range(len(migrations)):
                # 逐条推进：把清单切成前缀，保证每次只应用一条
                monkeypatch.setitem(REGISTERED_MIGRATIONS, database, migrations[: index + 1])
                if migrations[index].adjust is not None:
                    produced = tuple(migrations[index].adjust(connection))
                    assert produced == migrations[index].statements, (
                        database,
                        migrations[index].id,
                    )
                apply_migrations(connection, database=database)
        finally:
            connection.close()
