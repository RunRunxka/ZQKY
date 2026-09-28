"""向量库端口与共享类型：point id 命名空间、payload 字段与范围过滤条件。

范围过滤必须作为向量库过滤条件下推（Qdrant filter），不允许"取回全库再过滤"：
本模块只描述条件，不下发请求；具体下发在 ``qdrant.py``，内存替身在 ``memory.py``。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

#: 固定命名空间：point id = uuid5(APP_NAMESPACE, f"{generation}/{chunk_set}/{ordinal}/{text_sha256}")
APP_NAMESPACE = uuid.UUID("6f1b0b26-6c8d-4e39-9c1f-3b1e4a7d5c20")

#: payload 字段名（与计划 §3.3 一致），建索引与过滤共用同一组常量
PAYLOAD_GENERATION_ID = "generation_id"
PAYLOAD_DOCUMENT_ID = "document_id"
PAYLOAD_REVISION_ID = "document_revision_id"
PAYLOAD_CHUNK_SET_ID = "chunk_set_id"
PAYLOAD_ORDINAL = "ordinal"
PAYLOAD_OWNER_ID = "owner_id"
PAYLOAD_REGION = "region"
PAYLOAD_TEXT_SHA256 = "text_sha256"

#: 必须建立 payload 索引的字段（计划 §3.3）
INDEXED_PAYLOAD_FIELDS: tuple[str, ...] = (
    PAYLOAD_REVISION_ID,
    PAYLOAD_CHUNK_SET_ID,
    PAYLOAD_OWNER_ID,
    PAYLOAD_REGION,
)

_FILTER_FIELDS: tuple[tuple[str, str], ...] = (
    ("revision_ids", PAYLOAD_REVISION_ID),
    ("chunk_set_ids", PAYLOAD_CHUNK_SET_ID),
    ("owners", PAYLOAD_OWNER_ID),
)

COLLECTION_DISTANCE_COSINE = "Cosine"


def point_id_for(
    generation_id: str, chunk_set_id: str, ordinal: int, text_sha256: str
) -> str:
    """确定性 point id：同输入同 id；换索引代、分块集或文本内容都会换 id。"""
    return str(
        uuid.uuid5(
            APP_NAMESPACE,
            f"{generation_id}/{chunk_set_id}/{ordinal}/{text_sha256}",
        )
    )


@dataclass(frozen=True)
class VectorPoint:
    point_id: str
    vector: list[float]
    payload: dict


@dataclass(frozen=True)
class VectorHit:
    point_id: str
    score: float
    payload: dict


@dataclass(frozen=True)
class AllowedFilter:
    """允许集合过滤；``None`` 表示该维度不加限制，空元组表示"不允许任何值"。"""

    revision_ids: tuple[str, ...] | None = None
    chunk_set_ids: tuple[str, ...] | None = None
    owners: tuple[str, ...] | None = None
    region: str | None = None

    def has_conditions(self) -> bool:
        return any(
            value is not None
            for value in (self.revision_ids, self.chunk_set_ids, self.owners, self.region)
        )

    def to_qdrant(self) -> dict[str, Any] | None:
        """转成 Qdrant filter；无条件时返回 None（调用方决定是否允许全库）。"""
        conditions: list[dict[str, Any]] = []
        for attribute, key in _FILTER_FIELDS:
            values = getattr(self, attribute)
            if values is not None:
                conditions.append({"key": key, "match": {"any": list(values)}})
        if self.region is not None:
            conditions.append({"key": PAYLOAD_REGION, "match": {"value": self.region}})
        if not conditions:
            return None
        return {"must": conditions}


def payload_matches(payload: dict, allowed: AllowedFilter | None) -> bool:
    """内存替身与测试用的过滤语义；必须与 Qdrant filter 保持一致。"""
    if allowed is None:
        return True
    for attribute, key in _FILTER_FIELDS:
        values = getattr(allowed, attribute)
        if values is None:
            continue
        if payload.get(key) not in values:
            return False
    if allowed.region is not None and payload.get(PAYLOAD_REGION) != allowed.region:
        return False
    return True


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """余弦相似度；任一向量为零向量返回 0.0（不抬高也不压低其他候选）。"""
    if len(left) != len(right):
        raise ValueError("向量维度不一致，无法比较。")
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for left_value, right_value in zip(left, right):
        dot += left_value * right_value
        left_norm += left_value * left_value
        right_norm += right_value * right_value
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm**0.5 * right_norm**0.5)


@runtime_checkable
class VectorStore(Protocol):
    """向量库端口；实现必须把范围过滤下推，不得先全量取回再过滤。"""

    def ensure_collection(self, *, name: str, dimensions: int, distance: str) -> None: ...

    def upsert(self, *, name: str, points: list[VectorPoint], wait: bool = True) -> None: ...

    def search(
        self,
        *,
        name: str,
        vector: list[float],
        limit: int,
        allowed: AllowedFilter | None = None,
    ) -> list[VectorHit]: ...

    def delete_by_filter(self, *, name: str, allowed: AllowedFilter) -> None: ...

    def count(self, *, name: str, allowed: AllowedFilter | None = None) -> int: ...

    def collection_exists(self, name: str) -> bool: ...

    def ping(self) -> bool: ...

    def delete_collection(self, name: str) -> None: ...
