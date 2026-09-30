"""启动门控：既有数据库的只读体检（损坏不重建）。

（2026-09-30，TEACHING-LOOP B0 / T00。）

启动顺序（``app/main.py`` 生命周期）：

1. ``require_data_root_ready``：数据根处于恢复未完成状态时拒绝启动；
2. ``verify_existing_databases``（本模块）：**已经存在**的库必须可读、结构完整、
   迁移散列一致；损坏/结构不符明确报错——**绝不按空库重建**；
3. 迁移登记应用（``catalog.migrate()``）：缺库在此新建；
4. 任务收敛（遗留 ``running`` → ``interrupted``）。

第 2 步只对已存在的文件做体检；文件不存在说明该库尚未建立，由第 3 步创建。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

from app.core.exceptions import AppError
from app.core.migrations import verify_migrations
from app.core.sqlite import BUSY_TIMEOUT_MS

#: 体检专用打开方式：**不设 WAL**。``app.core.sqlite.connect`` 在垃圾文件上会因
#: ``PRAGMA journal_mode`` 直接抛错而留下未关闭的句柄（Windows 上文件被占用）；
#: 体检先证明文件是可读的 SQLite 库，之后才由迁移/正常路径按标准 PRAGMA 打开。
def _open_for_check(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        str(path), isolation_level=None, timeout=BUSY_TIMEOUT_MS / 1000
    )
    connection.row_factory = sqlite3.Row
    return connection


class DatabaseExpectation(NamedTuple):
    """一个受管数据库角色的期望：路径 + 角色 + 必须存在的表。"""

    path: Path
    database: str
    required_tables: tuple[str, ...]


def verify_existing_database(expectation: DatabaseExpectation) -> None:
    """体检单个既有库；文件不存在时直接返回（由迁移创建）。"""
    path = Path(expectation.path)
    if not path.exists():
        return
    connection: sqlite3.Connection | None = None
    try:
        connection = _open_for_check(path)
        _require_integrity(connection, path)
        _require_tables(connection, path, expectation.required_tables)
        verify_migrations(connection, database=expectation.database)
    except AppError:
        raise
    except sqlite3.Error as exc:
        raise AppError(
            f"数据库无法读取（{path.name}）：{exc.__class__.__name__}。"
            "已拒绝启动，不会按空库重建。",
            code="DATABASE_UNREADABLE",
            status_code=500,
        ) from exc
    finally:
        if connection is not None:
            connection.close()


def verify_existing_databases(expectations: Iterable[DatabaseExpectation]) -> None:
    for expectation in expectations:
        verify_existing_database(expectation)


def _require_integrity(connection: sqlite3.Connection, path: Path) -> None:
    row = connection.execute("PRAGMA quick_check").fetchone()
    verdict = "" if row is None else str(row[0]).strip().lower()
    if verdict != "ok":
        raise AppError(
            f"数据库完整性检查未通过（{path.name}）：{row[0] if row else '无结果'}。"
            "已拒绝启动，不会按空库重建；请从备份恢复。",
            code="DATABASE_INTEGRITY_FAILED",
            status_code=500,
        )


def _require_tables(
    connection: sqlite3.Connection, path: Path, required_tables: tuple[str, ...]
) -> None:
    if not required_tables:
        return
    present = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    missing = [name for name in required_tables if name not in present]
    if missing:
        raise AppError(
            f"数据库结构不完整（{path.name} 缺少 {', '.join(missing)}）；"
            "请勿把未迁移或来源不符的库当既有库使用。已拒绝启动。",
            code="DATABASE_SCHEMA_INCOMPLETE",
            status_code=500,
        )
