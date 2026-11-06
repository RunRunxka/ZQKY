"""Embedding 探测结果的共享类型与固定样例。

Ollama 与云端适配器返回同一形状，``IndexService`` 只依赖这里的数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 检测流程固定样例：与 RAG-REBUILD §4.2 一致，两类学科文本各一条。
EMBEDDING_PROBE_TEXTS: tuple[str, ...] = ("集合与函数", "物质的结构与性质")


@dataclass(frozen=True)
class EmbeddingProbeResult:
    """一次真实嵌入能力检测的结果；不含地址与凭证。

    ``stable_digest`` 表示"登记身份可在调用前后复核"。本机 Ollama 有清单 digest，
    云端供应商没有权重哈希，因此云端为 False，由声明式身份（供应商 + 连接 +
    模型 ID + 维度）承担向量空间隔离，不冒充权重哈希。
    """

    model_name: str
    model_manifest_digest: str
    dimensions: int
    sample_count: int
    non_zero: bool
    finite: bool
    stable_digest: bool
    family: str
    parameter_size: str


__all__ = ["EMBEDDING_PROBE_TEXTS", "EmbeddingProbeResult"]

