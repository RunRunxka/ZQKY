"""题库库结构入口。

2026-09-30（TEACHING-LOOP B0 / T00）起，DDL 与迁移登记统一在
``app/core/migrations/question_bank.py``（冻结基线 + 任务引擎列增量）；本文件只保留
"库必须存在的表"清单与 ``migrate()`` 入口，不再自带 DDL 文本。

约束不变：迁移幂等；``questions.current_revision_id`` 与
``question_revisions.question_id`` 的环形外键由写入方在同一事务内用
``PRAGMA defer_foreign_keys`` 延后校验；题库数据库独立于教材目录。
"""

from __future__ import annotations

import sqlite3

from app.core.migrations import apply_migrations

DATABASE = "question_bank"

#: 题库必须存在的表：只读打开既有库时用于校验结构完整性（缺表不得当空库继续用）。
REQUIRED_TABLES = (
    "question_imports",
    "question_source_blocks",
    "question_drafts",
    "question_suggestions",
    "questions",
    "question_revisions",
    "question_sources",
    "question_submissions",
    "question_jobs",
)


def migrate(connection: sqlite3.Connection) -> None:
    """应用登记迁移；重复调用不改变既有数据。"""
    apply_migrations(connection, database=DATABASE)
