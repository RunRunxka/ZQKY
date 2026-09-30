"""启动门控测试（TEACHING-LOOP B0 / 验收 A4）。

既有库只读体检：损坏/结构不符/漂移一律明确拒绝，且**不按空库重建**；
缺文件放行（由迁移创建）。同时守卫 Windows 上的文件句柄泄漏：拒绝后文件必须可删。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.core.database_gate import DatabaseExpectation, verify_existing_databases
from app.core.exceptions import AppError
from app.core.migrations import apply_migrations
from app.core.sqlite import connect


def _migrated(path: Path, database: str) -> Path:
    connection = connect(path)
    try:
        apply_migrations(connection, database=database)
    finally:
        connection.close()
    return path


def test_missing_file_is_allowed(tmp_path: Path) -> None:
    target = tmp_path / "not-created-yet.sqlite3"
    verify_existing_databases([DatabaseExpectation(target, "teaching", ("workflow_jobs",))])
    assert not target.exists(), "门控不得创建库文件"


def test_migrated_databases_pass(tmp_path: Path) -> None:
    teaching = _migrated(tmp_path / "teaching.sqlite3", "teaching")
    knowledge = _migrated(tmp_path / "knowledge.sqlite3", "knowledge")
    verify_existing_databases(
        [
            DatabaseExpectation(teaching, "teaching", ("workflow_jobs", "file_assets")),
            DatabaseExpectation(knowledge, "knowledge", ("knowledge_jobs",)),
        ]
    )


def test_garbage_file_is_refused_and_handle_released(tmp_path: Path) -> None:
    broken = tmp_path / "catalog.sqlite3"
    broken.write_bytes(b"this is not a sqlite database at all" * 10)
    with pytest.raises(AppError) as error:
        verify_existing_databases(
            [DatabaseExpectation(broken, "textbooks", ("catalog_state",))]
        )
    assert error.value.code == "DATABASE_UNREADABLE"
    # 拒绝后文件仍可用（句柄已释放），且内容没有被重建为空库
    broken.unlink()
    assert not broken.exists()


def test_corrupted_database_is_refused(tmp_path: Path) -> None:
    path = _migrated(tmp_path / "teaching.sqlite3", "teaching")
    # 造可靠可检出的损坏：删除索引的 schema 条目（quick_check 报 "Page X: never used"）
    connection = connect(path)
    try:
        connection.execute("CREATE INDEX IF NOT EXISTS idx_probe ON command_submissions(operation)")
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute("DELETE FROM sqlite_master WHERE name = 'idx_probe'")
        connection.execute("PRAGMA writable_schema = OFF")
    finally:
        connection.close()

    with pytest.raises(AppError) as error:
        verify_existing_databases(
            [DatabaseExpectation(path, "teaching", ("workflow_jobs",))]
        )
    assert error.value.code == "DATABASE_INTEGRITY_FAILED"
    assert path.exists(), "损坏库不得被删除或重建"


def test_missing_required_table_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "teaching.sqlite3"
    connection = connect(path)
    try:
        connection.execute("CREATE TABLE something_else (id TEXT PRIMARY KEY)")
    finally:
        connection.close()
    with pytest.raises(AppError) as error:
        verify_existing_databases(
            [DatabaseExpectation(path, "teaching", ("workflow_jobs", "file_assets"))]
        )
    assert error.value.code == "DATABASE_SCHEMA_INCOMPLETE"


def test_migration_drift_is_refused_by_gate(tmp_path: Path) -> None:
    path = _migrated(tmp_path / "knowledge.sqlite3", "knowledge")
    connection = connect(path)
    try:
        connection.execute(
            "UPDATE schema_migrations SET sha256 = 'not-the-real-hash' WHERE id = ?",
            ("0001_knowledge_baseline",),
        )
    finally:
        connection.close()
    with pytest.raises(AppError) as error:
        verify_existing_databases(
            [DatabaseExpectation(path, "knowledge", ("knowledge_jobs",))]
        )
    assert error.value.code == "SCHEMA_MIGRATION_DRIFT"


def test_gate_is_read_only_on_healthy_database(tmp_path: Path) -> None:
    path = _migrated(tmp_path / "teaching.sqlite3", "teaching")
    verify_existing_databases([DatabaseExpectation(path, "teaching", ("workflow_jobs",))])
    connection = connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM workflow_jobs").fetchone()[0] == 0
        # B1 起教学库有两条登记迁移（0001 基础 + 0002 业务表）
        assert (
            connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
            == 2
        )
    finally:
        connection.close()


def test_database_error_message_does_not_leak_environment(tmp_path: Path) -> None:
    broken = tmp_path / "catalog.sqlite3"
    broken.write_bytes(b"\x00" * 64)
    with pytest.raises(AppError) as error:
        verify_existing_databases([DatabaseExpectation(broken, "textbooks", ())])
    message = str(error.value)
    assert str(tmp_path) not in message, "错误信息不得回显完整路径"
    assert "file is not a database" not in message, "不得回显底层 sqlite 原文"
    assert "catalog.sqlite3" in message
