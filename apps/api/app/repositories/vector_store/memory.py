"""内存向量库替身：与 HttpQdrantStore 同一协议、同一过滤与计数语义。

只供测试与显式注入使用，**不装配为默认生产实现**（生产固定使用 Qdrant）。
余弦相似度排序与 Qdrant Cosine 一致；相同分数按 point id 升序稳定排序。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.exceptions import AppError
from app.repositories.vector_store.base import (
    AllowedFilter,
    VectorHit,
    VectorPoint,
    cosine_similarity,
    payload_matches,
)


@dataclass
class _Collection:
    dimensions: int
    distance: str
    points: dict[str, tuple[list[float], dict]] = field(default_factory=dict)


def _missing(name: str) -> AppError:
    return AppError(
        f"collection {name} 不存在。",
        code="QDRANT_COLLECTION_MISSING",
        status_code=404,
    )


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._collections: dict[str, _Collection] = {}

    # ------------------------------------------------------------------ 集合

    def ensure_collection(self, *, name: str, dimensions: int, distance: str) -> None:
        if not isinstance(dimensions, int) or dimensions <= 0:
            raise AppError(
                "向量维度必须是正整数。",
                code="QDRANT_REQUEST_REJECTED",
                status_code=422,
            )
        existing = self._collections.get(name)
        if existing is not None:
            if existing.dimensions != dimensions or existing.distance.lower() != distance.lower():
                raise AppError(
                    f"collection {name} 已存在且形状不一致（{existing.dimensions}/{existing.distance}）。",
                    code="QDRANT_COLLECTION_MISMATCH",
                    status_code=409,
                )
            return
        self._collections[name] = _Collection(dimensions=dimensions, distance=distance)

    def collection_exists(self, name: str) -> bool:
        return name in self._collections

    def delete_collection(self, name: str) -> None:
        self._collections.pop(name, None)

    def ping(self) -> bool:
        return True

    def ping_error(self) -> str | None:
        return None

    # ------------------------------------------------------------------ 写入

    def upsert(self, *, name: str, points: list[VectorPoint], wait: bool = True) -> None:
        collection = self._require(name)
        for point in points:
            if not isinstance(point.point_id, str) or not point.point_id:
                raise AppError(
                    "point_id 必须是非空字符串。",
                    code="QDRANT_REQUEST_REJECTED",
                    status_code=422,
                )
            if len(point.vector) != collection.dimensions:
                raise AppError(
                    f"向量维度 {len(point.vector)} 与 collection 维度 {collection.dimensions} 不一致。",
                    code="VECTOR_DIMENSION_MISMATCH",
                    status_code=422,
                )
            collection.points[point.point_id] = (list(point.vector), dict(point.payload))

    # ------------------------------------------------------------------ 检索

    def search(
        self,
        *,
        name: str,
        vector: list[float],
        limit: int,
        allowed: AllowedFilter | None = None,
    ) -> list[VectorHit]:
        collection = self._require(name)
        if len(vector) != collection.dimensions:
            raise AppError(
                f"查询向量维度 {len(vector)} 与 collection 维度 {collection.dimensions} 不一致。",
                code="VECTOR_DIMENSION_MISMATCH",
                status_code=422,
            )
        hits: list[VectorHit] = []
        for point_id, (point_vector, payload) in collection.points.items():
            if not payload_matches(payload, allowed):
                continue
            hits.append(
                VectorHit(
                    point_id=point_id,
                    score=cosine_similarity(vector, point_vector),
                    payload=dict(payload),
                )
            )
        hits.sort(key=lambda hit: (-hit.score, hit.point_id))
        if limit >= 0:
            return hits[: int(limit)]
        return hits

    # ------------------------------------------------------------------ 计数

    def count(self, *, name: str, allowed: AllowedFilter | None = None) -> int:
        collection = self._require(name)
        if allowed is None or not allowed.has_conditions():
            return len(collection.points)
        return sum(
            1 for payload in (item[1] for item in collection.points.values()) if payload_matches(payload, allowed)
        )

    # ------------------------------------------------------------------ 删除

    def delete_by_filter(self, *, name: str, allowed: AllowedFilter) -> None:
        collection = self._collections.get(name)
        if collection is None:
            return
        if allowed is None or not allowed.has_conditions():
            raise AppError(
                "按条件删除向量必须给出至少一个过滤条件，拒绝全量删除。",
                code="QDRANT_FILTER_REQUIRED",
                status_code=422,
            )
        for point_id in [
            point_id
            for point_id, (_vector, payload) in collection.points.items()
            if payload_matches(payload, allowed)
        ]:
            collection.points.pop(point_id, None)

    # ------------------------------------------------------------ 测试辅助

    def payloads(self, name: str) -> list[dict]:
        collection = self._require(name)
        return [dict(payload) for _vector, payload in collection.points.values()]

    def point_ids(self, name: str) -> list[str]:
        return sorted(self._require(name).points)

    def _require(self, name: str) -> _Collection:
        collection = self._collections.get(name)
        if collection is None:
            raise _missing(name)
        return collection
