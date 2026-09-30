"""教学业务库 SQLite 权威层（B0 基础；业务表在 B1+ 登记）。

纪律与其余三库一致：每次操作独立开连接（``connect``），写操作一律
``transaction(conn, immediate=True)``，网络/解析/推理不得进入事务；类型定义
统一来自 ``app.contracts.teaching_loop``。跨库引用由服务层校验（不在 SQL 里外键）。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.exceptions import AppError
from app.core.sqlite import connect, read_transaction, transaction
from app.repositories.teaching.schema import migrate as migrate_schema


class TeachingCatalog:
    """教学业务库的唯一读写入口；调用方给出数据库路径，测试使用临时目录。"""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._closed = False
        self._migrated = False

    # ------------------------------------------------------------ 生命周期

    @property
    def db_path(self) -> Path:
        return self._db_path

    def migrate(self) -> None:
        connection = self._open(require_migrated=False)
        try:
            migrate_schema(connection)
        finally:
            connection.close()
        self._migrated = True

    def close(self) -> None:
        self._closed = True

    def _open(self, *, require_migrated: bool = True) -> sqlite3.Connection:
        if self._closed:
            raise AppError("教学库已关闭。", code="TEACHING_DB_CLOSED", status_code=500)
        if require_migrated and not self._migrated:
            raise AppError(
                "教学库尚未迁移：先调用 migrate()。",
                code="TEACHING_DB_NOT_MIGRATED",
                status_code=500,
            )
        return connect(self._db_path)

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        connection = self._open()
        try:
            with transaction(connection, immediate=True) as conn:
                conn.execute("PRAGMA defer_foreign_keys = ON")
                yield conn
        finally:
            connection.close()

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        connection = self._open()
        try:
            with read_transaction(connection) as conn:
                yield conn
        finally:
            connection.close()

    @contextmanager
    def write_transaction(self) -> Iterator[sqlite3.Connection]:
        """单写事务入口：调用方在事务内只做 SQL。

        事务内不得做网络、文件与推理；抛异常整体回滚。
        任务结果与终态必须在同一事务内提交（见 ``app/services/jobs``）。
        """
        with self._write() as conn:
            yield conn

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        with self._read() as conn:
            yield conn
