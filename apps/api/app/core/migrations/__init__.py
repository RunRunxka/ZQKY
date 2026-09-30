"""四库迁移登记：增量、幂等、SQL 散列、失败可恢复。

（2026-09-30，TEACHING-LOOP B0 / T00。）

设计口径：

- 每个数据库（``textbooks`` / ``question_bank`` / ``knowledge`` / ``teaching``）有
  **追加式**迁移清单；迁移一经登记（``schema_migrations`` 有记录）就不得再改 SQL，
  改 SQL 会被本模块的散列校验判为漂移并拒绝启动（fail closed）。
- 每条迁移在**独立事务**中执行：失败整体回滚、不写登记，下次启动从该条重跑。
- 重复调用不改变既有数据；``CREATE TABLE IF NOT EXISTS`` 类基线对既有库是空操作。
- 业务表增量（B1+）一律**新增迁移**，由总控登记；实现方不直接改冻结基线 SQL。

迁移记录表（每库各自持有）：

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
```
"""

from __future__ import annotations

import sqlite3

from app.contracts.teaching_loop import SCHEMA_MIGRATION_DRIFT
from app.core.exceptions import AppError
from app.core.migrations.base import Migration, StatementAdjust, statement_digest
from app.core.migrations import knowledge as _knowledge
from app.core.migrations import question_bank as _question_bank
from app.core.migrations import teaching as _teaching
from app.core.migrations import textbooks as _textbooks
from app.core.sqlite import now_iso, transaction

__all__ = [
    "DATABASES",
    "Migration",
    "REGISTERED_MIGRATIONS",
    "REGISTRY_TABLE",
    "StatementAdjust",
    "apply_migrations",
    "applied_migrations",
    "pending_migrations",
    "statement_digest",
    "verify_migrations",
]

REGISTRY_TABLE = "schema_migrations"


#: 数据库角色 → 追加式迁移清单（顺序即执行顺序）。
REGISTERED_MIGRATIONS: dict[str, tuple[Migration, ...]] = {
    "textbooks": _textbooks.MIGRATIONS,
    "question_bank": _question_bank.MIGRATIONS,
    "knowledge": _knowledge.MIGRATIONS,
    "teaching": _teaching.MIGRATIONS,
}

DATABASES: tuple[str, ...] = tuple(REGISTERED_MIGRATIONS)


def _unknown_database(database: str) -> AppError:
    return AppError(
        f"未知数据库角色：{database}（可用：{', '.join(DATABASES)}）。",
        code="SCHEMA_DATABASE_UNKNOWN",
        status_code=500,
    )


def _drift_error(database: str, migration: Migration, recorded: str) -> AppError:
    return AppError(
        f"数据库 {database} 的迁移 {migration.id} 已登记散列与当前 SQL 不一致"
        f"（登记 {recorded[:12]}…，当前 {migration.sha256[:12]}…）。"
        "已登记迁移不得改写；请新增一条迁移，或从备份恢复该库。",
        code=SCHEMA_MIGRATION_DRIFT,
        status_code=500,
    )


def _ensure_registry_table(connection: sqlite3.Connection) -> None:
    with transaction(connection, immediate=True) as tx:
        tx.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {REGISTRY_TABLE} (
                id TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )


def applied_migrations(connection: sqlite3.Connection) -> dict[str, str]:
    """返回 ``{migration_id: sha256}``；库中尚无登记表时返回空字典（不建表）。"""
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (REGISTRY_TABLE,),
    ).fetchone()
    if table_exists is None:
        return {}
    return {
        row["id"]: row["sha256"]
        for row in connection.execute(f"SELECT id, sha256 FROM {REGISTRY_TABLE}")
    }


def apply_migrations(connection: sqlite3.Connection, *, database: str) -> list[str]:
    """按登记顺序应用未执行的迁移，返回本次实际应用的迁移 id 列表。

    - 已登记且散列一致 → 跳过（重复调用不改变既有数据）。
    - 已登记但散列不符 → ``SCHEMA_MIGRATION_DRIFT``（拒绝继续，不执行任何语句）。
    - 未登记 → 单事务执行（含登记行）；失败整体回滚，本次调用终止。
    """
    migrations = REGISTERED_MIGRATIONS.get(database)
    if migrations is None:
        raise _unknown_database(database)

    _ensure_registry_table(connection)
    applied = applied_migrations(connection)

    applied_now: list[str] = []
    for migration in migrations:
        recorded = applied.get(migration.id)
        if recorded is not None:
            if recorded != migration.sha256:
                raise _drift_error(database, migration, recorded)
            continue
        statements = (
            tuple(migration.adjust(connection)) if migration.adjust else migration.statements
        )
        with transaction(connection, immediate=True) as tx:
            for statement in statements:
                tx.execute(statement)
            tx.execute(
                f"INSERT INTO {REGISTRY_TABLE} (id, sha256, applied_at) VALUES (?, ?, ?)",
                (migration.id, migration.sha256, now_iso()),
            )
        applied[migration.id] = migration.sha256
        applied_now.append(migration.id)
    return applied_now


def pending_migrations(connection: sqlite3.Connection, *, database: str) -> list[str]:
    """返回尚未登记的迁移 id（只读；不建登记表）。"""
    migrations = REGISTERED_MIGRATIONS.get(database)
    if migrations is None:
        raise _unknown_database(database)
    applied = applied_migrations(connection)
    return [migration.id for migration in migrations if migration.id not in applied]


def verify_migrations(connection: sqlite3.Connection, *, database: str) -> None:
    """只读校验：散列漂移即抛错；未应用的迁移不在这里报错（由 apply 处理）。"""
    migrations = REGISTERED_MIGRATIONS.get(database)
    if migrations is None:
        raise _unknown_database(database)
    applied = applied_migrations(connection)
    for migration in migrations:
        recorded = applied.get(migration.id)
        if recorded is not None and recorded != migration.sha256:
            raise _drift_error(database, migration, recorded)
