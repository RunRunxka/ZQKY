"""Validate B5 structure only when teaching migration 0010 is registered.

The B0 required-table list remains unchanged, so a valid pre-B5 database can
reach its pending migration. This check performs only SQL reads.
"""
from __future__ import annotations

import re
import sqlite3

from app.core.exceptions import AppError
from app.core.migrations import applied_migrations
from app.core.migrations.lesson_plans import MIGRATION


def _normalized(sql: str) -> str:
    # SQLite persists our original CREATE statements. Only layout whitespace
    # outside quoted tokens is incidental; literal case/JSON paths are semantic.
    return re.sub(r"'(?:(?:'')|[^'])*'|\"(?:(?:\"\")|[^\"])*\"|\s+",
                  lambda match: match[0] if match[0][0] in {"'", '\"'} else " ",
                  sql.strip().rstrip(";")).strip()


def verify_registered_lesson_schema(connection: sqlite3.Connection) -> None:
    if MIGRATION.id not in applied_migrations(connection):
        return
    # Comparing the declared SQL also protects FK columns, CHECKs, uniqueness
    # and immutable/lineage triggers; table existence alone is insufficient.
    for statement in MIGRATION.statements:
        match = re.match(r"CREATE\s+(?:UNIQUE\s+)?(TABLE|INDEX|TRIGGER)\s+([a-zA-Z_][a-zA-Z_0-9]*)", statement.strip(), re.I)
        if match is None:
            raise RuntimeError("B5 gate expects explicit CREATE declarations")
        kind, name = match.group(1).lower(), match.group(2)
        row = connection.execute("SELECT sql FROM sqlite_master WHERE type=? AND name=?", (kind, name)).fetchone()
        if row is None or not isinstance(row[0], str) or _normalized(row[0]) != _normalized(statement):
            raise AppError(
                f"已登记B5数据库结构缺失或改变（{name}）；拒绝启动或恢复，不按空库覆盖。",
                code="DATABASE_SCHEMA_INCOMPLETE", status_code=500,
            )
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise AppError("已登记B5教学库外键检查未通过；拒绝启动或恢复。", code="DATABASE_INTEGRITY_FAILED", status_code=500)
