"""向量库端口（RAG-REBUILD v1.0 · B1）：Qdrant REST 适配器与内存测试替身。"""

from app.repositories.vector_store.base import (
    APP_NAMESPACE,
    INDEXED_PAYLOAD_FIELDS,
    PAYLOAD_CHUNK_SET_ID,
    PAYLOAD_DOCUMENT_ID,
    PAYLOAD_GENERATION_ID,
    PAYLOAD_ORDINAL,
    PAYLOAD_OWNER_ID,
    PAYLOAD_REGION,
    PAYLOAD_REVISION_ID,
    PAYLOAD_TEXT_SHA256,
    AllowedFilter,
    VectorHit,
    VectorPoint,
    VectorStore,
    cosine_similarity,
    payload_matches,
    point_id_for,
)
from app.repositories.vector_store.memory import InMemoryVectorStore
from app.repositories.vector_store.qdrant import DEFAULT_TIMEOUT_SECONDS, HttpQdrantStore

__all__ = [
    "APP_NAMESPACE",
    "DEFAULT_TIMEOUT_SECONDS",
    "INDEXED_PAYLOAD_FIELDS",
    "PAYLOAD_CHUNK_SET_ID",
    "PAYLOAD_DOCUMENT_ID",
    "PAYLOAD_GENERATION_ID",
    "PAYLOAD_ORDINAL",
    "PAYLOAD_OWNER_ID",
    "PAYLOAD_REGION",
    "PAYLOAD_REVISION_ID",
    "PAYLOAD_TEXT_SHA256",
    "AllowedFilter",
    "HttpQdrantStore",
    "InMemoryVectorStore",
    "VectorHit",
    "VectorPoint",
    "VectorStore",
    "cosine_similarity",
    "payload_matches",
    "point_id_for",
]
