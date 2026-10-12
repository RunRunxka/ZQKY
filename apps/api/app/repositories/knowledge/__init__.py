"""知识点库：独立 SQLite（``<data_dir>/knowledge/knowledge.sqlite3``）。

B0 只含公共基础（提交幂等、任务）；知识点/修订/别名/导入的业务表由 B1 新增迁移登记。
"""

from app.repositories.knowledge.catalog import KnowledgeCatalog

__all__ = ["KnowledgeCatalog"]
