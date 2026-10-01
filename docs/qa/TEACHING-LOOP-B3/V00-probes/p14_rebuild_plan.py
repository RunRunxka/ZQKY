"""V00 · RebuildPlan 探针：数据承载库上的受控表重建（自建演练）。

覆盖（`app/core/migrations/base.py` 的受检 12 步流程 + `_apply_rebuild` 执行器）：
  A. 成功：有数据的表重建为带复合外键/约束的新定义，数据完整、索引重建、
     迁移登记、`foreign_keys` 恢复 ON；
  B. 外键问题行：新定义指向不存在的父行 → `foreign_key_check` 报行 → 整体回滚
     （表定义与数据都没变、未登记），`foreign_keys` 仍恢复 ON；
  C. 对账不符：`verifications` 计数非 0 → 回滚且未登记；
  D. 可重跑：修正数据后重跑成功；
  E. 指纹：RebuildPlan 文本变化会改变 `Migration.sha256`（已登记即冻结）。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p14_rebuild_plan.py
退出码 0 = 全部断言通过。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402

from app.core.migrations.base import Migration, RebuildPlan  # noqa: E402
from app.core.migrations import _apply_rebuild  # noqa: E402
from app.core.sqlite import connect  # noqa: E402

DDL_OLD = (
    "CREATE TABLE owners (id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL)",
    "CREATE TABLE items (id TEXT PRIMARY KEY NOT NULL, owner_id TEXT, amount INTEGER NOT NULL, note TEXT)",
    "CREATE INDEX idx_items_owner ON items(owner_id)",
)
DDL_NEW_TABLE = """
CREATE TABLE items_new (
    id TEXT PRIMARY KEY NOT NULL,
    owner_id TEXT,
    amount INTEGER NOT NULL CHECK(amount >= 0),
    note TEXT,
    FOREIGN KEY(owner_id) REFERENCES owners(id)
)
"""
COPY = "INSERT INTO items_new (id, owner_id, amount, note) SELECT id, owner_id, amount, note FROM items"
DROP_RENAME = ("DROP TABLE items", "ALTER TABLE items_new RENAME TO items")
RESTORE = ("CREATE INDEX IF NOT EXISTS idx_items_owner ON items(owner_id)",)


def fingerprint_variant() -> str:
    base = Migration(
        id="x", description="x",
        rebuild=RebuildPlan(
            table="items", new_table_sql=DDL_NEW_TABLE, copy_sql=COPY,
            drop_and_rename=DROP_RENAME, restore=RESTORE,
        ),
    )
    changed = Migration(
        id="x", description="x",
        rebuild=RebuildPlan(
            table="items", new_table_sql=DDL_NEW_TABLE.replace("CHECK(amount >= 0)", "CHECK(amount >= -1)"),
            copy_sql=COPY, drop_and_rename=DROP_RENAME, restore=RESTORE,
        ),
    )
    return base.sha256 if base.sha256 != changed.sha256 else "SAME"


def fresh_db(path: Path, *, orphan: bool = False) -> sqlite3.Connection:
    connection = connect(path)
    with connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        for statement in DDL_OLD:
            connection.execute(statement)
        connection.execute("INSERT INTO owners (id, name) VALUES ('o1','甲'), ('o2','乙')")
        connection.execute("INSERT INTO items VALUES ('i1','o1',10,'正常')")
        connection.execute("INSERT INTO items VALUES ('i2','o2',20,'正常')")
        if orphan:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("INSERT INTO items VALUES ('i3','missing',30,'孤儿行')")
            connection.execute("PRAGMA foreign_keys = ON")
    return connection


def migration(*, verifications: tuple[tuple[str, str], ...] = ()) -> Migration:
    return Migration(
        id="v00_rebuild",
        description="探针重建",
        rebuild=RebuildPlan(
            table="items",
            new_table_sql=DDL_NEW_TABLE,
            copy_sql=COPY,
            drop_and_rename=DROP_RENAME,
            restore=RESTORE,
            verifications=verifications,
        ),
    )


def snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    ddl = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='items'"
    ).fetchone()
    rows = [dict(row) for row in connection.execute("SELECT * FROM items ORDER BY id")]
    indexes = sorted(
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='items' AND name NOT LIKE 'sqlite_%'"
        )
    )
    registered = sorted(
        row[0]
        for row in connection.execute("SELECT id FROM schema_migrations")
    )
    return {
        "ddl": (ddl[0] if ddl else None),
        "rows": rows,
        "indexes": indexes,
        "registered": registered,
        "foreignKeys": connection.execute("PRAGMA foreign_keys").fetchone()[0],
    }


def apply(connection: sqlite3.Connection, plan: Migration) -> str | None:
    try:
        _apply_rebuild(connection, plan)
        return None
    except Exception as exc:  # noqa: BLE001 - 如实收集失败
        return f"{type(exc).__name__}: {exc}"


def main() -> int:
    results: dict[str, Any] = {}
    failures: list[str] = []
    base = V.PROBE_TMP / "rebuild"

    # A. 成功
    path = base / "ok.sqlite3"
    connection = fresh_db(path)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        error = apply(connection, migration())
        after = snapshot(connection)
        results["success"] = {
            "error": error,
            "rowsPreserved": after["rows"],
            "hasCheck": "CHECK(amount >= 0)" in (after["ddl"] or ""),
            "hasForeignKey": "FOREIGN KEY(owner_id) REFERENCES owners(id)" in (after["ddl"] or ""),
            "indexes": after["indexes"],
            "registered": after["registered"],
            "foreignKeys": after["foreignKeys"],
        }
        if not (
            error is None
            and [row["id"] for row in after["rows"]] == ["i1", "i2"]
            and results["success"]["hasCheck"]
            and results["success"]["hasForeignKey"]
            and results["success"]["indexes"] == ["idx_items_owner"]
            and "v00_rebuild" in after["registered"]
            and after["foreignKeys"] == 1
        ):
            failures.append("A: 成功重建结果不符")
    finally:
        connection.close()

    # B. 外键问题行 → 回滚
    path_b = base / "fk.sqlite3"
    connection_b = fresh_db(path_b, orphan=True)
    try:
        before_b = snapshot(connection_b)
        error_b = apply(connection_b, migration())
        after_b = snapshot(connection_b)
        results["fk_problem_row"] = {
            "error": error_b,
            "ddlUnchanged": after_b["ddl"] == before_b["ddl"],
            "rowsUnchanged": after_b["rows"] == before_b["rows"],
            "registeredBefore": before_b["registered"],
            "registeredAfter": after_b["registered"],
            "foreignKeys": after_b["foreignKeys"],
        }
        if not (
            error_b is not None
            and "foreign_key_check" in error_b
            and after_b["ddl"] == before_b["ddl"]
            and after_b["rows"] == before_b["rows"]
            and after_b["registered"] == []
            and after_b["foreignKeys"] == 1
        ):
            failures.append("B: 外键问题行未整体回滚")
    finally:
        connection_b.close()

    # C. 对账不符 → 回滚；D. 修正后重跑成功
    path_c = base / "verify.sqlite3"
    connection_c = fresh_db(path_c)
    try:
        before_c = snapshot(connection_c)
        bad = migration(verifications=(("note 非空行数应为 0", "SELECT count(*) FROM items WHERE note IS NOT NULL"),))
        error_c = apply(connection_c, bad)
        after_c = snapshot(connection_c)
        good = migration(verifications=(("行数对账", "SELECT count(*) FROM items WHERE amount < 0"),))
        error_c2 = apply(connection_c, good)
        after_c2 = snapshot(connection_c)
        results["verification_mismatch"] = {
            "error": error_c,
            "ddlUnchanged": after_c["ddl"] == before_c["ddl"],
            "registeredAfterFailure": after_c["registered"],
            "foreignKeysAfterFailure": after_c["foreignKeys"],
            "retryError": error_c2,
            "rowsAfterRetry": after_c2["rows"],
            "registeredAfterRetry": after_c2["registered"],
            "foreignKeysAfterRetry": after_c2["foreignKeys"],
        }
        if not (
            error_c is not None
            and "数据对账未通过" in error_c
            and after_c["ddl"] == before_c["ddl"]
            and after_c["registered"] == []
            and after_c["foreignKeys"] == 1
            and error_c2 is None
            and [row["id"] for row in after_c2["rows"]] == ["i1", "i2"]
            and "v00_rebuild" in after_c2["registered"]
            and after_c2["foreignKeys"] == 1
        ):
            failures.append("C/D: 对账不符未回滚或修正后不可重跑")
    finally:
        connection_c.close()

    # E. 指纹
    results["fingerprint"] = {
        "variantChanged": fingerprint_variant() != "SAME",
        "sha": migration().sha256[:16],
    }
    if fingerprint_variant() == "SAME":
        failures.append("E: RebuildPlan 文本变化未改变迁移散列")

    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p14_rebuild_plan", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in ("success", "fk_problem_row", "verification_mismatch", "fingerprint"):
        print(key, json.dumps(results.get(key), ensure_ascii=False)[:460])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
