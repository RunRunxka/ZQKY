"""索引代服务（RAG-REBUILD v1.0 · B1）：重建闸门、执行、发布与 Embedding 配置。"""

from app.services.textbook_index.service import (
    DEFAULT_LEASE_SECONDS,
    DEFAULT_WORKER_ID,
    IndexService,
)

__all__ = ["DEFAULT_LEASE_SECONDS", "DEFAULT_WORKER_ID", "IndexService"]
