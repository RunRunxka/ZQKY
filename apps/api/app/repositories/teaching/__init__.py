"""教学业务库：独立 SQLite（``<data_dir>/teaching/teaching.sqlite3``）。

B0 只含公共基础（提交幂等、受管资产登记、通用任务）；业务表由 B1+ 新增迁移登记。
"""

from app.repositories.teaching.catalog import TeachingCatalog

__all__ = ["TeachingCatalog"]
