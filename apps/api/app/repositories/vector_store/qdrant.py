"""Qdrant REST 适配器（httpx，不新增依赖）。

只使用 Qdrant 官方 REST 路径，所有范围过滤都作为 filter 下推：
- ``PUT /collections/{name}``、``PUT /collections/{name}/index``
- ``PUT /collections/{name}/points?wait=true``
- ``POST /collections/{name}/points/search``
- ``POST /collections/{name}/points/delete?wait=true``
- ``POST /collections/{name}/points/count``
- ``GET /collections/{name}/exists``（不支持时回退 ``GET /collections/{name}``）
- ``GET /``（ping）、``DELETE /collections/{name}``

服务不可达一律抛 ``QDRANT_UNAVAILABLE``（503，可重试），绝不把不可达当作"没有匹配"。
"""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from app.core.exceptions import AppError
from app.repositories.vector_store.base import (
    INDEXED_PAYLOAD_FIELDS,
    AllowedFilter,
    VectorHit,
    VectorPoint,
)

DEFAULT_TIMEOUT_SECONDS = 30.0


def _unavailable(base_url: str, detail: str, *, retryable: bool = True) -> AppError:
    return AppError(
        f"向量库不可用（{base_url}）：{detail}",
        code="QDRANT_UNAVAILABLE",
        status_code=503,
        retryable=retryable,
    )


class HttpQdrantStore:
    """同步 HTTP 客户端；每次调用独立连接，可被线程池跨线程使用。"""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        raw = (base_url or "").strip()
        parsed = urlsplit(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AppError(
                "Qdrant 地址必须是 http/https URL。",
                code="QDRANT_BASE_URL_INVALID",
                status_code=422,
            )
        self.base_url = raw.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self._transport = transport
        self._last_ping_error: str | None = None

    # ------------------------------------------------------------- HTTP 底座

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        allow_missing: bool = False,
    ) -> dict | None:
        try:
            with self._client() as client:
                response = client.request(method, path, json=json_body)
        except httpx.HTTPError as exc:
            raise _unavailable(self.base_url, exc.__class__.__name__) from exc
        if response.status_code >= 400:
            if response.status_code == 404 and allow_missing:
                return None
            raise self._map_error(response)
        if response.content and response.status_code != 204:
            try:
                payload = response.json()
            except ValueError as exc:
                raise AppError(
                    "Qdrant 返回了非 JSON 响应。",
                    code="QDRANT_INVALID_RESPONSE",
                    status_code=502,
                ) from exc
            if not isinstance(payload, dict):
                raise AppError(
                    "Qdrant 响应顶层不是 JSON 对象。",
                    code="QDRANT_INVALID_RESPONSE",
                    status_code=502,
                )
            return payload
        return {}

    def _map_error(self, response: httpx.Response) -> AppError:
        status = response.status_code
        if status == 404:
            return AppError(
                "Qdrant collection 不存在。",
                code="QDRANT_COLLECTION_MISSING",
                status_code=404,
            )
        if status >= 500:
            return _unavailable(self.base_url, f"HTTP {status}")
        return AppError(
            f"Qdrant 拒绝了请求（HTTP {status}）。",
            code="QDRANT_REQUEST_REJECTED",
            status_code=422,
        )

    @staticmethod
    def _result(payload: dict | None) -> object:
        if payload is None:
            return None
        return payload.get("result")

    # ------------------------------------------------------------------ 集合

    def collection_exists(self, name: str) -> bool:
        payload = self._request(
            "GET", f"/collections/{name}/exists", allow_missing=True
        )
        result = self._result(payload)
        if isinstance(result, dict) and isinstance(result.get("exists"), bool):
            return bool(result["exists"])
        if payload is not None and self._result(payload) is None:
            # 个别版本没有 /exists：回退到集合信息接口判定
            info = self._request("GET", f"/collections/{name}", allow_missing=True)
            return info is not None
        if payload is None:
            info = self._request("GET", f"/collections/{name}", allow_missing=True)
            return info is not None
        raise AppError(
            "Qdrant /exists 响应结构不符。",
            code="QDRANT_INVALID_RESPONSE",
            status_code=502,
        )

    def ensure_collection(self, *, name: str, dimensions: int, distance: str) -> None:
        if not name:
            raise AppError("collection 名称不能为空。", code="QDRANT_REQUEST_REJECTED", status_code=422)
        if not isinstance(dimensions, int) or dimensions <= 0:
            raise AppError(
                "向量维度必须是正整数。",
                code="QDRANT_REQUEST_REJECTED",
                status_code=422,
            )
        if self.collection_exists(name):
            self._verify_collection_shape(name, dimensions=dimensions, distance=distance)
            return
        self._request(
            "PUT",
            f"/collections/{name}",
            json_body={"vectors": {"size": dimensions, "distance": distance}},
        )
        for field in INDEXED_PAYLOAD_FIELDS:
            self._request(
                "PUT",
                f"/collections/{name}/index",
                json_body={"field_name": field, "field_schema": "keyword"},
            )

    def _verify_collection_shape(self, name: str, *, dimensions: int, distance: str) -> None:
        payload = self._request("GET", f"/collections/{name}", allow_missing=True)
        result = self._result(payload)
        if not isinstance(result, dict):
            return
        config = result.get("config")
        params = config.get("params") if isinstance(config, dict) else None
        vectors = params.get("vectors") if isinstance(params, dict) else None
        if not isinstance(vectors, dict):
            return
        size = vectors.get("size")
        actual_distance = vectors.get("distance")
        if isinstance(size, int) and size != dimensions:
            raise AppError(
                f"collection {name} 已存在且维度为 {size}，与配置维度 {dimensions} 不一致。",
                code="QDRANT_COLLECTION_MISMATCH",
                status_code=409,
            )
        if (
            isinstance(actual_distance, str)
            and actual_distance.lower() != distance.lower()
        ):
            raise AppError(
                f"collection {name} 已存在且距离为 {actual_distance}，与配置 {distance} 不一致。",
                code="QDRANT_COLLECTION_MISMATCH",
                status_code=409,
            )

    def delete_collection(self, name: str) -> None:
        self._request("DELETE", f"/collections/{name}", allow_missing=True)

    # ------------------------------------------------------------------ 写入

    def upsert(self, *, name: str, points: list[VectorPoint], wait: bool = True) -> None:
        if not points:
            return
        body = {
            "points": [
                {
                    "id": point.point_id,
                    "vector": list(point.vector),
                    "payload": dict(point.payload),
                }
                for point in points
            ]
        }
        self._request("PUT", f"/collections/{name}/points?wait={'true' if wait else 'false'}", json_body=body)

    # ------------------------------------------------------------------ 检索

    def search(
        self,
        *,
        name: str,
        vector: list[float],
        limit: int,
        allowed: AllowedFilter | None = None,
    ) -> list[VectorHit]:
        body: dict = {
            "vector": list(vector),
            "limit": int(limit),
            "with_payload": True,
        }
        if allowed is not None:
            qdrant_filter = allowed.to_qdrant()
            if qdrant_filter is not None:
                body["filter"] = qdrant_filter
        payload = self._request("POST", f"/collections/{name}/points/search", json_body=body)
        result = self._result(payload)
        if not isinstance(result, list):
            raise AppError(
                "Qdrant 检索响应缺少 result 数组。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            )
        hits: list[VectorHit] = []
        for item in result:
            if not isinstance(item, dict):
                raise AppError(
                    "Qdrant 检索结果项结构不符。",
                    code="QDRANT_INVALID_RESPONSE",
                    status_code=502,
                )
            score = item.get("score")
            raw_payload = item.get("payload")
            hits.append(
                VectorHit(
                    point_id=str(item.get("id")),
                    score=float(score) if isinstance(score, (int, float)) else 0.0,
                    payload=raw_payload if isinstance(raw_payload, dict) else {},
                )
            )
        return hits

    # ------------------------------------------------------------------ 删除

    def delete_by_filter(self, *, name: str, allowed: AllowedFilter) -> None:
        qdrant_filter = allowed.to_qdrant() if allowed is not None else None
        if qdrant_filter is None:
            raise AppError(
                "按条件删除向量必须给出至少一个过滤条件，拒绝全量删除。",
                code="QDRANT_FILTER_REQUIRED",
                status_code=422,
            )
        self._request(
            "POST",
            f"/collections/{name}/points/delete?wait=true",
            json_body={"filter": qdrant_filter},
            allow_missing=True,
        )

    # ------------------------------------------------------------------ 计数

    def count(self, *, name: str, allowed: AllowedFilter | None = None) -> int:
        body: dict = {"exact": True}
        if allowed is not None:
            qdrant_filter = allowed.to_qdrant()
            if qdrant_filter is not None:
                body["filter"] = qdrant_filter
        payload = self._request("POST", f"/collections/{name}/points/count", json_body=body)
        result = self._result(payload)
        if not isinstance(result, dict):
            raise AppError(
                "Qdrant 计数响应缺少 result 对象。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            )
        count = result.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise AppError(
                "Qdrant 计数响应缺少合法 count。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            )
        return count

    # ------------------------------------------------------------------ 健康

    def ping(self) -> bool:
        """只返回可达性；失败原因存在 ``ping_error()``，不抛异常、不伪装可用。"""
        try:
            with self._client() as client:
                response = client.get("/")
        except httpx.HTTPError as exc:
            self._last_ping_error = f"连接失败：{exc.__class__.__name__}"
            return False
        if response.status_code >= 400:
            self._last_ping_error = f"HTTP {response.status_code}"
            return False
        self._last_ping_error = None
        return True

    def ping_error(self) -> str | None:
        return self._last_ping_error

    def close(self) -> None:
        """无长连接可关闭；保留接口便于统一生命周期。"""
        return None

    # 兼容注入：把不可达错误统一为可读文案的辅助
    def unavailable_error(self, detail: str) -> AppError:
        return _unavailable(self.base_url, detail)
