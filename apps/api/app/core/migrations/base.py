"""迁移条目定义（被 ``app.core.migrations`` 与各库冻结 SQL 模块共用）。

单独成模块是为了避免 ``app.core.migrations.__init__`` 与各库 SQL 模块的循环导入：
SQL 模块只依赖本模块，注册表与执行逻辑在 ``__init__``。
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

#: 语句级调整钩子：在真正执行前根据库现状过滤/派生语句（例如过滤已存在的列）。
#: 散列只对**声明语句**（``Migration.statements``）计算，钩子不得改变声明集合。
StatementAdjust = Callable[[sqlite3.Connection], Sequence[str]]


def statement_digest(statements: Sequence[str]) -> str:
    """声明语句集合的散列（去首尾空白、逐条 sha256 链）。"""
    digest = hashlib.sha256()
    for statement in statements:
        digest.update(statement.strip().encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


@dataclass(frozen=True)
class Migration:
    """一条已登记的迁移；``statements`` 是声明语句，散列一经登记即冻结。"""

    id: str
    description: str
    statements: tuple[str, ...]
    adjust: StatementAdjust | None = field(default=None, compare=False)

    @property
    def sha256(self) -> str:
        return statement_digest(self.statements)
