"""教材目录仓储：只读记录类型与 JSON 字段编解码（R0-B 恢复的最小子集）。

R2 恢复 `catalog.py`（SQLite 权威层）；本包导出纯类型、编解码工具与权威层。
"""

from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import (
    AllowedChunks,
    CatalogState,
    ChunkInput,
    ChunkRecord,
    ChunkSetRecord,
    DocumentRecord,
    GenerationRecord,
    GenerationRevisionRecord,
    ImportRecord,
    JobRecord,
    LibraryRecord,
    MetadataRevisionRecord,
    ProfileRecord,
    ResolvedDocument,
    RevisionRecord,
    TeachingRecord,
)
from app.repositories.textbook_catalog.json_fields import (
    read_object,
    read_string_list,
    write_object,
    write_string_list,
)

__all__ = [
    "AllowedChunks",
    "CatalogState",
    "ChunkInput",
    "ChunkRecord",
    "ChunkSetRecord",
    "DocumentRecord",
    "GenerationRecord",
    "GenerationRevisionRecord",
    "ImportRecord",
    "JobRecord",
    "LibraryRecord",
    "MetadataRevisionRecord",
    "ProfileRecord",
    "ResolvedDocument",
    "RevisionRecord",
    "TeachingRecord",
    "TextbookCatalog",
    "read_object",
    "read_string_list",
    "write_object",
    "write_string_list",
]
