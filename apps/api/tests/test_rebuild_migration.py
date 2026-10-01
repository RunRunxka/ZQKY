"""受控表重建迁移测试（TEACHING-LOOP B3 / CTRL · 成绩期前置）。

覆盖：受控重建成功（数据保留、外键完好、登记、`foreign_keys` 恢复 ON）；
外键问题行 → 失败回滚且不登记；数据对账不符 → 失败回滚；integrity_check 读取；
失败后可重跑（修复计划再应用成功）。用临时注册表注入重建迁移，不改真实清单。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.core.migrations import (
    REGISTERED_MIGRATIONS,
    Migration,
    RebuildPlan,
    applied_migrations,
    apply_migrations,
)
from app.core.sqlite import connect, now_iso
from app.core.migrations import SCHEMA_REBUILD_FAILED


def _schema(connection: sqlite3.Connection) -> None:
    """父/子两表 + 外键 + 索引，模拟"需要恢复约束"的既有结构。"""
    connection.executescript(
        """
        CREATE TABLE parent (id TEXT PRIMARY KEY, label TEXT NOT NULL);
        CREATE TABLE child (
            id TEXT PRIMARY KEY,
            parent_id TEXT NOT NULL REFERENCES parent(id),
            score INTEGER NOT NULL
        );
        CREATE INDEX idx_child_parent ON child(parent_id);
        INSERT INTO parent (id, label) VALUES ('p1','甲'), ('p2','乙');
        INSERT INTO child (id, parent_id, score) VALUES ('c1','p1',0), ('c2','p1',5), ('c3','p2',7);
        """
    )


def _plan(*, copy_sql: str | None = None, verifications=()) -> RebuildPlan:
    """给 parent 增加 CHECK(label <> '')（SQLite 不能 ALTER ADD CHECK → 必须重建）。"""
    return RebuildPlan(
        table="parent",
        new_table_sql=(
            "CREATE TABLE parent_new ("
            "id TEXT PRIMARY KEY, "
            "label TEXT NOT NULL CHECK(length(trim(label)) > 0))"
        ),
        copy_sql=copy_sql or "INSERT INTO parent_new (id, label) SELECT id, label FROM parent",
        drop_and_rename=("DROP TABLE parent", "ALTER TABLE parent_new RENAME TO parent"),
        restore=("CREATE INDEX IF NOT EXISTS idx_child_parent ON child(parent_id)",),
        verifications=verifications,
    )


def _rebuild_migration(plan: RebuildPlan, migration_id: str = "9001_rebuild_parent") -> Migration:
    return Migration(id=migration_id, description="测试重建", rebuild=plan)


def test_rebuild_preserves_data_and_fk_and_restores_pragma(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connect(tmp_path / "t.sqlite3")
    try:
        _schema(connection)
        monkeypatch.setitem(
            REGISTERED_MIGRATIONS, "teaching", (_rebuild_migration(_plan()),)
        )
        applied = apply_migrations(connection, database="teaching")
        assert applied == ["9001_rebuild_parent"]
        # 数据保留
        rows = connection.execute("SELECT id, label FROM parent ORDER BY id").fetchall()
        assert [(r["id"], r["label"]) for r in rows] == [("p1", "甲"), ("p2", "乙")]
        assert connection.execute("SELECT COUNT(*) FROM child").fetchone()[0] == 3
        # 新约束生效
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO parent (id, label) VALUES ('p3','')")
        # 外键仍然指向父表（重建未破坏子表引用）
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO child (id, parent_id, score) VALUES ('c9','nope',1)")
        # pragma 恢复 ON
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        # 登记
        assert "9001_rebuild_parent" in applied_migrations(connection)
    finally:
        connection.close()


def test_rebuild_fails_on_foreign_key_violation_and_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connect(tmp_path / "t.sqlite3")
    try:
        _schema(connection)
        # 故意漏拷一父行 → 子表出现外键孤儿
        plan = _plan(copy_sql="INSERT INTO parent_new (id, label) SELECT id, label FROM parent WHERE id <> 'p2'")
        monkeypatch.setitem(
            REGISTERED_MIGRATIONS, "teaching", (_rebuild_migration(plan),)
        )
        with pytest.raises(AppError) as error:
            apply_migrations(connection, database="teaching")
        assert error.value.code == SCHEMA_REBUILD_FAILED
        # 回滚：原表与数据原样，未登记，pragma 恢复
        assert connection.execute("SELECT COUNT(*) FROM parent").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM child").fetchone()[0] == 3
        assert "9001_rebuild_parent" not in applied_migrations(connection)
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()


def test_rebuild_fails_on_verification_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connect(tmp_path / "t.sqlite3")
    try:
        _schema(connection)
        plan = _plan(
            verifications=(
                (
                    "parent 行数应为 9",
                    "SELECT CASE WHEN (SELECT COUNT(*) FROM parent) = 9 THEN 0 ELSE 1 END",
                ),
            )
        )
        monkeypatch.setitem(
            REGISTERED_MIGRATIONS, "teaching", (_rebuild_migration(plan),)
        )
        with pytest.raises(AppError) as error:
            apply_migrations(connection, database="teaching")
        assert error.value.code == SCHEMA_REBUILD_FAILED
        assert connection.execute("SELECT COUNT(*) FROM parent").fetchone()[0] == 2
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()


def test_failed_rebuild_can_be_retried_with_fixed_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connect(tmp_path / "t.sqlite3")
    try:
        _schema(connection)
        bad = _plan(copy_sql="INSERT INTO parent_new (id, label) SELECT id, label FROM missing_table")
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", (_rebuild_migration(bad),))
        with pytest.raises(sqlite3.Error):
            apply_migrations(connection, database="teaching")
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        # 修复后重跑成功
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", (_rebuild_migration(_plan()),))
        assert apply_migrations(connection, database="teaching") == ["9001_rebuild_parent"]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_rebuild_migration_hash_covers_plan_text() -> None:
    first = Migration(id="9002", description="x", rebuild=_plan())
    second = Migration(
        id="9002",
        description="x",
        rebuild=_plan(copy_sql="INSERT INTO parent_new (id, label) SELECT id, label FROM parent ORDER BY id"),
    )
    assert first.sha256 != second.sha256
    assert Migration(id="9002", description="x", rebuild=_plan()).sha256 == first.sha256
    with pytest.raises(ValueError):
        Migration(id="9003", description="x", statements=("SELECT 1",), rebuild=_plan())
