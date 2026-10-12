"""知识点库结构入口：迁移登记与冻结基线在 ``app/core/migrations/knowledge.py``。

本批（B0）只含公共基础表；业务表增量由总控登记为新迁移，本文件不直接写 DDL。
"""

from __future__ import annotations

import sqlite3

from app.core.migrations import apply_migrations

DATABASE = "knowledge"

#: 库必须存在的表：只读打开既有库时用于校验结构完整性（缺表不得当空库继续用）。
REQUIRED_TABLES = ("knowledge_submissions", "knowledge_jobs")


def migrate(connection: sqlite3.Connection) -> None:
    """应用登记迁移；重复调用不改变既有数据。"""
    apply_migrations(connection, database=DATABASE)
