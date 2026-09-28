"""本地 Embedding 适配层：Ollama 原生接口与配置指纹。"""

from app.providers.embeddings.fingerprint import (
    EMBEDDING_ADAPTER,
    EMBEDDING_DISTANCE,
    canonical_json,
    embedding_fingerprint,
    sha256_hex,
)
from app.providers.embeddings.ollama_embedding import (
    ADAPTER,
    DEFAULT_TIMEOUT_SECONDS,
    EMBEDDING_PROBE_TEXTS,
    LOOPBACK_HOSTS,
    EmbeddingProbeResult,
    OllamaEmbeddingProvider,
    is_embedding_capable,
    is_remote_or_cloud_model,
    model_names_match,
    normalize_loopback_base_url,
    normalize_model_tag,
)

__all__ = [
    "ADAPTER",
    "DEFAULT_TIMEOUT_SECONDS",
    "EMBEDDING_ADAPTER",
    "EMBEDDING_DISTANCE",
    "EMBEDDING_PROBE_TEXTS",
    "LOOPBACK_HOSTS",
    "EmbeddingProbeResult",
    "OllamaEmbeddingProvider",
    "canonical_json",
    "embedding_fingerprint",
    "is_embedding_capable",
    "is_remote_or_cloud_model",
    "model_names_match",
    "normalize_loopback_base_url",
    "normalize_model_tag",
    "sha256_hex",
]
