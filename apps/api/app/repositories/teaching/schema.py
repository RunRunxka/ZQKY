"""教学业务库结构入口：迁移登记与冻结基线在 ``app/core/migrations/teaching.py``。

本批（B0）只含公共基础表（提交幂等、受管资产登记、通用任务）；班级、学生、原卷、
成绩、报告、教案、练习等业务表由 B1+ 提供 SQL、总控登记为新迁移。
"""

from __future__ import annotations

import sqlite3

from app.core.migrations import apply_migrations

DATABASE = "teaching"

#: 库必须存在的表：只读打开既有库时用于校验结构完整性（缺表不得当空库继续用）。
REQUIRED_TABLES = ("command_submissions", "file_assets", "workflow_jobs")


def migrate(connection: sqlite3.Connection) -> None:
    """应用登记迁移；重复调用不改变既有数据。"""
    apply_migrations(connection, database=DATABASE)
