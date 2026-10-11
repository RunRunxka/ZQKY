"""Embedding 配置指纹：进入向量空间身份的字段一处定义、canonical JSON 取 sha256。

指纹只包含会影响向量空间的参数（适配器、模型清单 digest、维度、距离、前缀、归一化与选项）；
地址、超时、代理等连接参数不进入指纹。同一逻辑内容必须产生同一字节串与同一指纹。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

EMBEDDING_ADAPTER = "ollama"
EMBEDDING_DISTANCE = "cosine"


def canonical_json(payload: Any) -> str:
    """固定键序与分隔符的 JSON：同一逻辑内容产生同一字节串。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(text: str | bytes) -> str:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()


def embedding_fingerprint(
    *,
    model_manifest_digest: str,
    dimensions: int,
    query_prefix: str,
    document_prefix: str,
    normalization: str,
    options: dict[str, Any] | None = None,
    adapter: str = EMBEDDING_ADAPTER,
    distance: str = EMBEDDING_DISTANCE,
) -> str:
    """按计划 §4.2 的字段集合计算配置指纹。"""
    payload = {
        "adapter": adapter,
        "modelManifestDigest": model_manifest_digest,
        "dimensions": dimensions,
        "distance": distance,
        "queryPrefix": query_prefix,
        "documentPrefix": document_prefix,
        "normalization": normalization,
        "options": dict(options or {}),
    }
    return sha256_hex(canonical_json(payload))
