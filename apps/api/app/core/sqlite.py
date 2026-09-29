"""SQLite 连接的统一入口：外键、WAL 与有限 busy_timeout 一处设定。

教材目录与题库各自持有独立数据库文件，互不打开对方的连接。所有写事务都
经 ``transaction()``，外部 I/O（网络、解析、推理）不得在事务内执行。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.core.exceptions import AppError

BUSY_TIMEOUT_MS = 5000


def now_iso() -> str:
    """全库统一的时间戳：UTC、秒精度、可排序。"""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def connect(path: Path | str) -> sqlite3.Connection:
    """打开（必要时创建）数据库并设定固定 PRAGMA。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target), isolation_level=None, timeout=BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = %d" % BUSY_TIMEOUT_MS)
    return connection


@contextmanager
def transaction(
    connection: sqlite3.Connection, *, immediate: bool = False
) -> Iterator[sqlite3.Connection]:
    """显式事务；``immediate=True`` 用于需要抢写锁的读改写。"""
    connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield connection
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    else:
        connection.execute("COMMIT")


@contextmanager
def read_transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    connection.execute("BEGIN")
    try:
        yield connection
    finally:
        connection.execute("COMMIT")


def open_readonly(path: Path | str, *, required_tables: tuple[str, ...] = ()) -> sqlite3.Connection:
    """以**只读**方式打开既有数据库：不建库、不建表、不写 WAL。

    验收脚本与只读工具用这个入口，避免"路径写错时静默建出空库"把失败伪装成空数据
    （见 docs/PLAN.md §6.2）。库文件不存在或缺少必需表时抛 ``AppError``。
    """
    target = Path(path)
    if not target.is_file():
        raise AppError(
            f"数据库不存在，拒绝创建空库：{target.name}",
            code="DATABASE_MISSING",
            status_code=500,
        )
    connection = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        present = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    except sqlite3.DatabaseError as exc:
        connection.close()
        raise AppError(
            f"数据库无法读取：{target.name}",
            code="DATABASE_UNREADABLE",
            status_code=500,
        ) from exc
    missing = [name for name in required_tables if name not in present]
    if missing:
        connection.close()
        raise AppError(
            f"数据库结构不完整（缺少 {', '.join(missing)}）；请勿把未迁移的库当既有库使用。",
            code="DATABASE_SCHEMA_INCOMPLETE",
            status_code=500,
        )
    return connection
