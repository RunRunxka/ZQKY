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

SCHEMA_REBUILD_FAILED = "SCHEMA_REBUILD_FAILED"
from app.core.exceptions import AppError
from app.core.migrations.base import (
    Migration,
    RebuildPlan,
    StatementAdjust,
    statement_digest,
)
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
    "RebuildPlan",
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
        if migration.rebuild is not None:
            _apply_rebuild(connection, migration)
        else:
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


def _apply_rebuild(connection: sqlite3.Connection, migration: Migration) -> None:
    """受控表重建（SQLite 官方流程）：事务外关外键 → 单事务重建与校验 → 登记提交。

    - ``foreign_keys`` 是 no-op in transaction：必须在 BEGIN 之前关闭（本连接为
      autocommit，``execute`` 立即生效），否则 ``DROP TABLE`` 会按旧表重写子表外键；
    - 事务内先建临时新表、显式列拷贝、删旧表、改名为原名，再重建索引/触发器；
    - **必须读取** ``PRAGMA foreign_key_check`` 的全部行与 ``PRAGMA integrity_check``
      的返回值：任一外键问题行或非 ``ok`` 即失败回滚；
    - 数据对账（``verifications``）任一计数非 0 失败回滚；
    - ``finally`` 恢复 ``foreign_keys=ON`` 并核验；失败时迁移不登记，可重跑。
    """
    plan = migration.rebuild
    assert plan is not None
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        enabled = connection.execute("PRAGMA foreign_keys").fetchone()
        if enabled is None or int(enabled[0]) != 0:
            raise AppError(
                f"迁移 {migration.id}：无法在事务外关闭 foreign_keys，拒绝重建表。",
                code=SCHEMA_REBUILD_FAILED,
                status_code=500,
            )
        with transaction(connection, immediate=True) as tx:
            tx.execute(plan.new_table_sql)
            tx.execute(plan.copy_sql)
            for statement in plan.drop_and_rename:
                tx.execute(statement)
            for statement in plan.restore:
                tx.execute(statement)
            fk_rows = tx.execute("PRAGMA foreign_key_check").fetchall()
            if fk_rows:
                first = dict(fk_rows[0]) if isinstance(fk_rows[0], sqlite3.Row) else fk_rows[0]
                raise AppError(
                    f"迁移 {migration.id}：foreign_key_check 报告 {len(fk_rows)} 处外键问题"
                    f"（首个：{first}）；已回滚，未登记。",
                    code=SCHEMA_REBUILD_FAILED,
                    status_code=500,
                )
            integrity = [str(row[0]) for row in tx.execute("PRAGMA integrity_check")]
            if integrity != ["ok"]:
                raise AppError(
                    f"迁移 {migration.id}：integrity_check 非 ok（{integrity[:3]}）；已回滚，未登记。",
                    code=SCHEMA_REBUILD_FAILED,
                    status_code=500,
                )
            for label, sql in plan.verifications:
                row = tx.execute(sql).fetchone()
                count = -1 if row is None else int(row[0])
                if count != 0:
                    raise AppError(
                        f"迁移 {migration.id}：数据对账未通过（{label}，不一致 {count}）。已回滚，未登记。",
                        code=SCHEMA_REBUILD_FAILED,
                        status_code=500,
                    )
            tx.execute(
                f"INSERT INTO {REGISTRY_TABLE} (id, sha256, applied_at) VALUES (?, ?, ?)",
                (migration.id, migration.sha256, now_iso()),
            )
    finally:
        connection.execute("PRAGMA foreign_keys = ON")
        restored = connection.execute("PRAGMA foreign_keys").fetchone()
        if restored is None or int(restored[0]) != 1:
            raise AppError(
                f"迁移 {migration.id}：恢复 foreign_keys=ON 失败；连接不可信，请重启应用。",
                code=SCHEMA_REBUILD_FAILED,
                status_code=500,
            )


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
