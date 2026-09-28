"""教材目录仓储（RAG-REBUILD v1.0 · B0）:SQLite 权威层与只读记录类型。"""

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
]
