"""B1 迁移与启动门控兼容测试（TEACHING-LOOP B1 / 验收 A1、A2）。

覆盖：新库与"仅 B0 结构"的既有库两条路径；重复应用幂等；0001 散列不得改写；
中途失败整体回滚；启动门控对"尚未应用 B1 迁移"的合法旧库放行（不判损坏），
迁移后新表齐备；触发器（环、修订不可变）与部分唯一索引生效。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.core.database_gate import DatabaseExpectation, verify_existing_databases
from app.core.exceptions import AppError
from app.core.migrations import (
    REGISTERED_MIGRATIONS,
    Migration,
    applied_migrations,
    apply_migrations,
)
from app.core.sqlite import connect, now_iso
from app.repositories.knowledge.schema import REQUIRED_TABLES as KNOWLEDGE_REQUIRED
from app.repositories.teaching.schema import REQUIRED_TABLES as TEACHING_REQUIRED

#: B0 r2 冻结的 0001 声明散列：改写即回归（既有库会判 SCHEMA_MIGRATION_DRIFT）。
KNOWLEDGE_0001_SHA256 = "c1260aece348b1f7068e812d95a8bbb65f69d885c3a246d1d9938ff8f2285da9"
TEACHING_0001_SHA256 = "bf78fb3fb702b6f65f3d9802dfd9b53b6628d14e58d33380a9a7da8936b8612a"

#: 各库 B0 之后的追加迁移（顺序即登记顺序）
B1_APPLIED = {
    "knowledge": [
        "0001_knowledge_baseline",
        "0002_knowledge_business_tables",
        "0003_knowledge_import_issues_column",
    ],
    "teaching": ["0001_teaching_baseline", "0002_teaching_business_tables"],
}

KNOWLEDGE_B1_TABLES = {
    "subjects",
    "knowledge_points",
    "knowledge_point_revisions",
    "knowledge_aliases",
    "textbook_knowledge_links",
    "knowledge_imports",
    "knowledge_import_rows",
}
TEACHING_B1_TABLES = {
    "classes",
    "students",
    "class_memberships",
    "roster_imports",
    "roster_import_rows",
}

#: 模块导入时的完整清单快照：monkeypatch 前缀后用它恢复
REGISTERED_MIGRATIONS_FULL = {
    database: tuple(migrations) for database, migrations in REGISTERED_MIGRATIONS.items()
}


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def test_b1_migrations_declared_and_hash_stable() -> None:
    knowledge = {migration.id: migration.sha256 for migration in REGISTERED_MIGRATIONS["knowledge"]}
    teaching = {migration.id: migration.sha256 for migration in REGISTERED_MIGRATIONS["teaching"]}
    assert knowledge["0001_knowledge_baseline"] == KNOWLEDGE_0001_SHA256
    assert teaching["0001_teaching_baseline"] == TEACHING_0001_SHA256
    assert "0002_knowledge_business_tables" in knowledge
    assert "0003_knowledge_import_issues_column" in knowledge
    assert "0002_teaching_business_tables" in teaching


def test_new_database_applies_b1_and_is_idempotent(tmp_path: Path) -> None:
    for database, tables in (
        ("knowledge", KNOWLEDGE_B1_TABLES),
        ("teaching", TEACHING_B1_TABLES),
    ):
        connection = connect(tmp_path / f"{database}.sqlite3")
        try:
            applied = apply_migrations(connection, database=database)
            assert applied == B1_APPLIED[database]
            assert tables <= _tables(connection)
            assert apply_migrations(connection, database=database) == []
            assert applied_migrations(connection)[f"0002_{database}_business_tables"]
        finally:
            connection.close()


def test_legacy_b0_only_database_passes_gate_then_gains_b1_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """合法"尚未应用 B1 迁移"的既有库：门控放行 → 迁移后新表齐备。"""
    knowledge_path = tmp_path / "knowledge.sqlite3"
    teaching_path = tmp_path / "teaching.sqlite3"

    for database, path, prefix in (
        ("knowledge", knowledge_path, REGISTERED_MIGRATIONS["knowledge"][:1]),
        ("teaching", teaching_path, REGISTERED_MIGRATIONS["teaching"][:1]),
    ):
        monkeypatch.setitem(REGISTERED_MIGRATIONS, database, prefix)
        connection = connect(path)
        try:
            assert apply_migrations(connection, database=database) == [f"0001_{database}_baseline"]
        finally:
            connection.close()
        # 恢复完整清单：下一阶段模拟"升级到 B1"
        monkeypatch.setitem(REGISTERED_MIGRATIONS, database, REGISTERED_MIGRATIONS_FULL[database])

    # 尚未应用 B1 迁移：门控必须放行（只按 B0 基础表要求）
    verify_existing_databases(
        [
            DatabaseExpectation(knowledge_path, "knowledge", KNOWLEDGE_REQUIRED),
            DatabaseExpectation(teaching_path, "teaching", TEACHING_REQUIRED),
        ]
    )

    for database, path, tables in (
        ("knowledge", knowledge_path, KNOWLEDGE_B1_TABLES),
        ("teaching", teaching_path, TEACHING_B1_TABLES),
    ):
        connection = connect(path)
        try:
            assert apply_migrations(connection, database=database) == B1_APPLIED[
                database
            ][1:]
            assert tables <= _tables(connection)
        finally:
            connection.close()
        verify_existing_databases([DatabaseExpectation(path, database, ())])


def test_mid_failure_rolls_back_b1_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connect(tmp_path / "knowledge.sqlite3")
    original = REGISTERED_MIGRATIONS["knowledge"]
    try:
        apply_migrations(connection, database="knowledge")
        broken = Migration(
            id="0003_broken",
            description="故意失败：第二条语句不是 SQL",
            statements=(
                "CREATE TABLE should_roll_back_b1 (id TEXT PRIMARY KEY)",
                "THIS IS NOT VALID SQL",
            ),
        )
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "knowledge", (*original, broken))
        with pytest.raises(sqlite3.Error):
            apply_migrations(connection, database="knowledge")
        assert "should_roll_back_b1" not in _tables(connection)
        assert "0003_broken" not in applied_migrations(connection)
    finally:
        connection.close()


def test_knowledge_triggers_block_cycles_and_revision_mutation(tmp_path: Path) -> None:
    connection = connect(tmp_path / "knowledge.sqlite3")
    try:
        apply_migrations(connection, database="knowledge")
        connection.execute(
            "INSERT INTO subjects (id, code, name) VALUES ('math', 'math', '数学')"
        )
        connection.execute(
            "INSERT INTO knowledge_points (id, subject_id, code) VALUES ('k1','math','K1')"
        )
        connection.execute(
            "INSERT INTO knowledge_points (id, subject_id, code, parent_id) "
            "VALUES ('k2','math','K2','k1')"
        )
        # 自指
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE knowledge_points SET parent_id='k2' WHERE id='k2'")
        # 环 k1 → k2（k2 已是 k1 的子节点）
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE knowledge_points SET parent_id='k2' WHERE id='k1'")
        # 跨学科父节点：复合外键要求同 subject_id
        connection.execute(
            "INSERT INTO subjects (id, code, name) VALUES ('physics','physics','物理')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO knowledge_points (id, subject_id, code, parent_id) "
                "VALUES ('k3','physics','K3','k1')"
            )
        # 修订不可变
        connection.execute(
            "INSERT INTO knowledge_point_revisions (id, knowledge_point_id, version, name) "
            "VALUES ('r1','k1',1,'函数单调性')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE knowledge_point_revisions SET name='改名' WHERE id='r1'")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM knowledge_point_revisions WHERE id='r1'")
    finally:
        connection.close()


def test_active_membership_partial_unique_index(tmp_path: Path) -> None:
    connection = connect(tmp_path / "teaching.sqlite3")
    try:
        apply_migrations(connection, database="teaching")
        connection.execute(
            "INSERT INTO classes (id, owner_id, code, name, school_year, grade_id) "
            "VALUES ('c1','local','A1','高一(1)班','2026-2027','senior-1')"
        )
        connection.execute(
            "INSERT INTO classes (id, owner_id, code, name, school_year, grade_id) "
            "VALUES ('c2','local','A2','高一(2)班','2026-2027','senior-1')"
        )
        connection.execute(
            "INSERT INTO students (id, owner_id, student_no, name) VALUES ('s1','local','0012','张三')"
        )
        connection.execute(
            "INSERT INTO class_memberships (id, class_id, student_id, joined_on) "
            "VALUES ('m1','c1','s1','2026-09-01')"
        )
        # 同班重复活跃归属被拒
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO class_memberships (id, class_id, student_id, joined_on) "
                "VALUES ('m2','c1','s1','2026-09-02')"
            )
        # 离班后可再次入班（历史保留）
        connection.execute(
            "UPDATE class_memberships SET left_on='2026-09-30' WHERE id='m1'"
        )
        connection.execute(
            "INSERT INTO class_memberships (id, class_id, student_id, joined_on) "
            "VALUES ('m3','c1','s1','2026-10-01')"
        )
        rows = connection.execute(
            "SELECT id, left_on FROM class_memberships WHERE student_id='s1' ORDER BY id"
        ).fetchall()
        assert [(row["id"], row["left_on"]) for row in rows] == [
            ("m1", "2026-09-30"),
            ("m3", None),
        ]
    finally:
        connection.close()


def test_roster_import_requires_registered_asset(tmp_path: Path) -> None:
    """名单批次的 file_asset_id 是本库真实外键：未登记资产必须被拒。"""
    connection = connect(tmp_path / "teaching.sqlite3")
    try:
        apply_migrations(connection, database="teaching")
        connection.execute(
            "INSERT INTO classes (id, owner_id, code, name, school_year, grade_id) "
            "VALUES ('c1','local','A1','高一(1)班','2026-2027','senior-1')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO roster_imports (id, owner_id, class_id, file_asset_id, "
                "state, revision, created_at, updated_at) "
                "VALUES ('i1','local','c1','missing-asset','uploaded',0,?,?)",
                (now_iso(), now_iso()),
            )
        connection.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) "
            "VALUES ('a1','local','roster','blobs/' || ?, ?, 'r.csv', 'text/csv', 3, ?)",
            ("b" * 64, "b" * 64, now_iso()),
        )
        connection.execute(
            "INSERT INTO roster_imports (id, owner_id, class_id, file_asset_id, "
            "state, revision, created_at, updated_at) "
            "VALUES ('i1','local','c1','a1','uploaded',0,?,?)",
            (now_iso(), now_iso()),
        )
        count = connection.execute("SELECT COUNT(*) FROM roster_imports").fetchone()[0]
        assert count == 1
    finally:
        connection.close()


def test_b1_gate_refuses_corrupt_database_after_migration(tmp_path: Path) -> None:
    path = tmp_path / "knowledge.sqlite3"
    connection = connect(path)
    try:
        apply_migrations(connection, database="knowledge")
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute("DELETE FROM sqlite_master WHERE name = 'ix_kp_parent'")
        connection.execute("PRAGMA writable_schema = OFF")
    finally:
        connection.close()
    with pytest.raises(AppError) as error:
        verify_existing_databases([DatabaseExpectation(path, "knowledge", ())])
    assert error.value.code in {"DATABASE_INTEGRITY_FAILED", "DATABASE_UNREADABLE"}
