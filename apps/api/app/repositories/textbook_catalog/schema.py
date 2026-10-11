"""教材目录库结构入口。

2026-09-30（TEACHING-LOOP B0 / T00）起，DDL 与迁移登记统一在
``app/core/migrations/textbooks.py``（冻结基线 + 后续增量）；本文件只保留
"库必须存在的表"清单与 ``migrate()`` 入口，不再自带 DDL 文本。

纪律不变：迁移幂等、不重建、不删除、不改写既有行；已登记迁移的 SQL 不得改写，
结构变化一律新增迁移（由总控登记）。
"""

from __future__ import annotations

import sqlite3

from app.core.migrations import apply_migrations

DATABASE = "textbooks"

#: 目录库必须存在的表：只读打开既有库时用于校验结构完整性
#: （缺表说明文件不是本应用的目录库，不能当"空库"继续用）。
REQUIRED_TABLES = (
    "catalog_state",
    "embedding_profiles",
    "index_generations",
    "libraries",
    "documents",
    "library_documents",
    "document_metadata_revisions",
    "document_revisions",
    "chunk_sets",
    "chunks",
    "generation_revisions",
    "import_drafts",
    "index_jobs",
    "cleanup_queue",
    "teaching_settings",
)


def migrate(connection: sqlite3.Connection) -> None:
    """应用登记迁移（含单行 catalog_state 补齐）；重复调用不改变既有数据。"""
    apply_migrations(connection, database=DATABASE)
