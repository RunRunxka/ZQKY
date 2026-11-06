"""Embedding 适配层：本机 Ollama、云端百炼与配置指纹。"""

from app.providers.embeddings.dashscope_embedding import (
    ADAPTER as DASHSCOPE_ADAPTER,
    DEFAULT_MODEL as DASHSCOPE_DEFAULT_MODEL,
    DIMENSION_CHOICES as DASHSCOPE_DIMENSION_CHOICES,
    DashScopeEmbeddingProvider,
    DashScopeTarget,
    declared_identity_digest,
)
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
from app.providers.embeddings.output_validation import invalid_output, normalize_vectors

__all__ = [
    "ADAPTER",
    "DASHSCOPE_ADAPTER",
    "DASHSCOPE_DEFAULT_MODEL",
    "DASHSCOPE_DIMENSION_CHOICES",
    "DEFAULT_TIMEOUT_SECONDS",
    "EMBEDDING_ADAPTER",
    "EMBEDDING_DISTANCE",
    "EMBEDDING_PROBE_TEXTS",
    "LOOPBACK_HOSTS",
    "DashScopeEmbeddingProvider",
    "DashScopeTarget",
    "EmbeddingProbeResult",
    "OllamaEmbeddingProvider",
    "canonical_json",
    "declared_identity_digest",
    "embedding_fingerprint",
    "invalid_output",
    "is_embedding_capable",
    "is_remote_or_cloud_model",
    "model_names_match",
    "normalize_loopback_base_url",
    "normalize_model_tag",
    "normalize_vectors",
    "sha256_hex",
]
