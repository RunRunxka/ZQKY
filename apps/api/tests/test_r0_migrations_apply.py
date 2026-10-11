"""R0-A 迁移恢复验证：四库 apply 两次幂等 + verify 通过（骨架重置后回归哨兵）。

不复制 B0 已覆盖的框架语义（失败回滚/漂移拒绝见 ``test_migrations.py``）；
本文件只钉住「四库迁移清单可在全新 sqlite 上干净走完且幂等」这一恢复底线。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.core.migrations import (
    DATABASES,
    REGISTERED_MIGRATIONS,
    applied_migrations,
    apply_migrations,
    verify_migrations,
)
from app.core.sqlite import connect

#: 数据库角色 → 磁盘文件名（与任务卡要求的四个库一一对应）。
_R0_DATABASES = ("textbooks", "knowledge", "question_bank", "teaching")


def test_r0_databases_are_the_four_registered_roles() -> None:
    assert set(DATABASES) == set(_R0_DATABASES)


@pytest.mark.parametrize("database", _R0_DATABASES)
def test_r0_apply_twice_is_idempotent_and_verify_passes(tmp_path: Path, database: str) -> None:
    all_ids = [migration.id for migration in REGISTERED_MIGRATIONS[database]]
    assert all_ids, f"{database} 迁移清单为空，恢复不完整"

    path = tmp_path / f"{database}.sqlite3"
    connection = connect(path)
    try:
        first = apply_migrations(connection, database=database)
        assert first == all_ids
        records = applied_migrations(connection)
        assert set(records) == set(all_ids)

        # 第二次 apply：幂等，返回空列表且登记不变
        second = apply_migrations(connection, database=database)
        assert second == []
        assert applied_migrations(connection) == records

        # 只读散列校验通过（无漂移）
        verify_migrations(connection, database=database)
    finally:
        connection.close()


def test_r0_connection_without_changes_fails_verify_on_unknown_database(tmp_path: Path) -> None:
    """负例：未知数据库角色在 apply/verify 都被拒绝，不落任何文件副作用。"""
    path = tmp_path / "unknown.sqlite3"
    connection: sqlite3.Connection = connect(path)
    try:
        with pytest.raises(AppError) as apply_error:
            apply_migrations(connection, database="no_such_db")
        assert apply_error.value.code == "SCHEMA_DATABASE_UNKNOWN"
        with pytest.raises(AppError) as verify_error:
            verify_migrations(connection, database="no_such_db")
        assert verify_error.value.code == "SCHEMA_DATABASE_UNKNOWN"
    finally:
        connection.close()
