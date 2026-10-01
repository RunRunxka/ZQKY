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
class RebuildPlan:
    """受控表重建（SQLite 官方 12 步流程的受检实现，B3/G0→T60）。

    用于 SQLite 无法用 ``ALTER`` 完成的约束变更（例如给已有表恢复复合外键）。
    执行器会：事务外置 ``foreign_keys=OFF`` → 单事务内建新表/显式列拷贝/删旧表/
    改新表为原名/重建索引触发器 → 读取 ``PRAGMA foreign_key_check`` 全部行与
    ``integrity_check`` 返回值，任一外键问题行或非 ``ok`` 完整性都失败回滚 →
    写迁移登记并提交 → ``finally`` 恢复并核验 ``foreign_keys=ON``。
    禁止把 ``PRAGMA foreign_keys`` 写进语句列表（事务内无效），禁止先改名旧表。
    """

    table: str                      # 目标表名（最终保持原名）
    new_table_sql: str              # CREATE TABLE <临时名> (...)
    copy_sql: str                   # INSERT INTO <临时名> (cols) SELECT cols FROM <原名>
    drop_and_rename: tuple[str, ...]
    restore: tuple[str, ...] = ()   # 重建索引/触发器/视图（CREATE ... IF NOT EXISTS 幂等）
    #: 数据对账：(label, 返回单个不一致计数的 SELECT)；任一 > 0 → 失败回滚
    verifications: tuple[tuple[str, str], ...] = ()

    def fingerprint_text(self) -> str:
        parts = [self.table, self.new_table_sql, self.copy_sql]
        parts.extend(self.drop_and_rename)
        parts.extend(self.restore)
        parts.extend(label for label, _sql in self.verifications)
        parts.extend(sql for _label, sql in self.verifications)
        return "\n".join(parts)


@dataclass(frozen=True)
class Migration:
    """一条已登记的迁移；``statements`` 是声明语句，散列一经登记即冻结。

    ``rebuild`` 与 ``statements``/``adjust`` 互斥：重建迁移的散列覆盖重建计划文本，
    保证"已登记 = 已冻结"。
    """

    id: str
    description: str
    statements: tuple[str, ...] = ()
    adjust: StatementAdjust | None = field(default=None, compare=False)
    rebuild: RebuildPlan | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.rebuild is not None and (self.statements or self.adjust is not None):
            raise ValueError(f"迁移 {self.id}: rebuild 与 statements/adjust 互斥")

    @property
    def sha256(self) -> str:
        if self.rebuild is not None:
            return statement_digest((self.rebuild.fingerprint_text(),))
        return statement_digest(self.statements)
