"""向量库：Qdrant REST 调用形状（filter 下推）、point id 确定性与内存替身语义。"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest

from app.core.exceptions import AppError
from app.repositories.vector_store import (
    APP_NAMESPACE,
    AllowedFilter,
    HttpQdrantStore,
    InMemoryVectorStore,
    VectorPoint,
    point_id_for,
)


class Router:
    def __init__(self, routes: dict[tuple[str, str], object]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str, object]] = []
        self.urls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = None
        if request.content:
            body = json.loads(request.content)
        self.calls.append((request.method, request.url.path, body))
        self.urls.append(str(request.url))
        entry = self.routes.get((request.method, request.url.path))
        if entry is None:
            return httpx.Response(404, json={"status": "error"})
        if callable(entry):
            return entry(request)
        status, payload = entry
        return httpx.Response(status, json=payload)

    def bodies(self, method: str, path: str) -> list[object]:
        return [body for m, p, body in self.calls if (m, p) == (method, path)]

    def paths(self) -> list[str]:
        return [path for _m, path, _b in self.calls]


def store(router: Router) -> HttpQdrantStore:
    return HttpQdrantStore("http://127.0.0.1:6333", transport=httpx.MockTransport(router))


OK = (200, {"status": "ok", "result": True})


# ------------------------------------------------------------------ 集合生命周期


def test_ensure_collection_creates_and_indexes_payload_fields() -> None:
    router = Router(
        {
            ("GET", "/collections/textbooks_1/exists"): (200, {"result": {"exists": False}}),
            ("PUT", "/collections/textbooks_1"): (200, {"result": True}),
            ("PUT", "/collections/textbooks_1/index"): (200, {"result": {"operation_id": 1}}),
        }
    )
    store(router).ensure_collection(name="textbooks_1", dimensions=1024, distance="Cosine")

    assert router.bodies("PUT", "/collections/textbooks_1") == [
        {"vectors": {"size": 1024, "distance": "Cosine"}}
    ]
    indexed = router.bodies("PUT", "/collections/textbooks_1/index")
    assert indexed == [
        {"field_name": "document_revision_id", "field_schema": "keyword"},
        {"field_name": "chunk_set_id", "field_schema": "keyword"},
        {"field_name": "owner_id", "field_schema": "keyword"},
        {"field_name": "region", "field_schema": "keyword"},
    ]


def test_ensure_collection_does_not_recreate_existing_collection() -> None:
    router = Router(
        {
            ("GET", "/collections/textbooks_1/exists"): (200, {"result": {"exists": True}}),
            ("GET", "/collections/textbooks_1"): (
                200,
                {"result": {"config": {"params": {"vectors": {"size": 1024, "distance": "Cosine"}}}}},
            ),
        }
    )
    store(router).ensure_collection(name="textbooks_1", dimensions=1024, distance="Cosine")
    assert ("PUT", "/collections/textbooks_1") not in [
        (method, path) for method, path, _body in router.calls
    ]


def test_ensure_collection_rejects_dimension_mismatch() -> None:
    router = Router(
        {
            ("GET", "/collections/textbooks_1/exists"): (200, {"result": {"exists": True}}),
            ("GET", "/collections/textbooks_1"): (
                200,
                {"result": {"config": {"params": {"vectors": {"size": 768, "distance": "Cosine"}}}}},
            ),
        }
    )
    with pytest.raises(AppError) as exc_info:
        store(router).ensure_collection(name="textbooks_1", dimensions=1024, distance="Cosine")
    assert (exc_info.value.code, exc_info.value.status_code) == ("QDRANT_COLLECTION_MISMATCH", 409)


def test_collection_exists_falls_back_to_collection_info() -> None:
    router = Router(
        {
            ("GET", "/collections/legacy/exists"): (404, {"status": "error"}),
            ("GET", "/collections/legacy"): (200, {"result": {"config": {}}}),
        }
    )
    assert store(router).collection_exists("legacy") is True


# ------------------------------------------------------------------------- 写入/检索


def test_upsert_and_search_push_down_filter() -> None:
    point = VectorPoint(
        point_id="11111111-1111-5111-8111-111111111111",
        vector=[0.1, 0.2, 0.3],
        payload={
            "generation_id": "g1",
            "document_revision_id": "r1",
            "chunk_set_id": "c1",
            "owner_id": "local-user",
            "region": "body",
            "ordinal": 0,
            "text_sha256": "a" * 64,
        },
    )
    router = Router(
        {
            ("PUT", "/collections/textbooks_1/points"): (200, {"result": {"operation_id": 2}}),
            ("POST", "/collections/textbooks_1/points/search"): (
                200,
                {"result": [{"id": point.point_id, "score": 0.75, "payload": point.payload}]},
            ),
        }
    )
    client = store(router)
    client.upsert(name="textbooks_1", points=[point], wait=True)
    assert router.urls == ["http://127.0.0.1:6333/collections/textbooks_1/points?wait=true"]
    assert router.bodies("PUT", "/collections/textbooks_1/points") == [
        {
            "points": [
                {"id": point.point_id, "vector": [0.1, 0.2, 0.3], "payload": point.payload}
            ]
        }
    ]

    hits = client.search(
        name="textbooks_1",
        vector=[0.1, 0.2, 0.3],
        limit=50,
        allowed=AllowedFilter(revision_ids=("r1",), chunk_set_ids=("c1",), region="body"),
    )
    assert [hit.point_id for hit in hits] == [point.point_id]
    assert hits[0].score == pytest.approx(0.75)
    body = router.bodies("POST", "/collections/textbooks_1/points/search")[0]
    assert body["limit"] == 50
    assert body["with_payload"] is True
    assert body["filter"] == {
        "must": [
            {"key": "document_revision_id", "match": {"any": ["r1"]}},
            {"key": "chunk_set_id", "match": {"any": ["c1"]}},
            {"key": "region", "match": {"value": "body"}},
        ]
    }


def test_search_without_filter_does_not_send_filter() -> None:
    router = Router(
        {("POST", "/collections/textbooks_1/points/search"): (200, {"result": []})}
    )
    store(router).search(name="textbooks_1", vector=[1.0], limit=5, allowed=None)
    body = router.bodies("POST", "/collections/textbooks_1/points/search")[0]
    assert "filter" not in body
    assert body["vector"] == [1.0]


def test_upsert_wait_false_uses_false_query() -> None:
    router = Router({("PUT", "/collections/textbooks_1/points"): (200, {"result": {}})})
    store(router).upsert(
        name="textbooks_1",
        points=[VectorPoint(point_id="p", vector=[1.0], payload={})],
        wait=False,
    )
    assert router.urls == ["http://127.0.0.1:6333/collections/textbooks_1/points?wait=false"]
    # 空点列表不发请求
    store(router).upsert(name="textbooks_1", points=[], wait=True)
    assert len(router.urls) == 1


def test_owners_filter_uses_owner_id_key() -> None:
    router = Router(
        {("POST", "/collections/textbooks_1/points/search"): (200, {"result": []})}
    )
    store(router).search(
        name="textbooks_1", vector=[1.0], limit=5, allowed=AllowedFilter(owners=("system",))
    )
    body = router.bodies("POST", "/collections/textbooks_1/points/search")[0]
    assert body["filter"] == {"must": [{"key": "owner_id", "match": {"any": ["system"]}}]}


def test_delete_by_filter_and_count_shapes() -> None:
    router = Router(
        {
            ("POST", "/collections/textbooks_1/points/delete"): (200, {"result": {"operation_id": 3}}),
            ("POST", "/collections/textbooks_1/points/count"): (200, {"result": {"count": 7}}),
        }
    )
    client = store(router)
    client.delete_by_filter(name="textbooks_1", allowed=AllowedFilter(revision_ids=("r1", "r2")))
    assert router.bodies("POST", "/collections/textbooks_1/points/delete") == [
        {"filter": {"must": [{"key": "document_revision_id", "match": {"any": ["r1", "r2"]}}]}}
    ]
    assert client.count(name="textbooks_1", allowed=AllowedFilter(region="body")) == 7
    assert router.bodies("POST", "/collections/textbooks_1/points/count") == [
        {"exact": True, "filter": {"must": [{"key": "region", "match": {"value": "body"}}]}}
    ]
    assert client.count(name="textbooks_1") == 7
    assert router.bodies("POST", "/collections/textbooks_1/points/count")[1] == {"exact": True}


def test_delete_without_conditions_is_refused_before_send() -> None:
    router = Router({})
    with pytest.raises(AppError) as exc_info:
        store(router).delete_by_filter(name="textbooks_1", allowed=AllowedFilter())
    assert exc_info.value.code == "QDRANT_FILTER_REQUIRED"
    assert router.calls == []


# --------------------------------------------------------------------------- 健康


def test_unreachable_qdrant_is_503_not_empty_result() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = store(Router({}))
    client._transport = httpx.MockTransport(boom)  # type: ignore[attr-defined]
    with pytest.raises(AppError) as exc_info:
        client.search(name="textbooks_1", vector=[1.0], limit=5, allowed=None)
    assert (exc_info.value.code, exc_info.value.status_code) == ("QDRANT_UNAVAILABLE", 503)
    assert exc_info.value.retryable is True

    assert client.ping() is False
    assert client.ping_error()


def test_ping_true_and_delete_collection_idempotent() -> None:
    router = Router(
        {
            ("GET", "/"): (200, {"title": "qdrant"}),
            ("DELETE", "/collections/textbooks_1"): (404, {"status": "error"}),
        }
    )
    client = store(router)
    assert client.ping() is True
    assert client.ping_error() is None
    client.delete_collection("textbooks_1")  # 404 视为已删除，幂等
    assert router.paths().count("/") == 1


# ----------------------------------------------------------------- point id


def test_point_id_is_deterministic_and_namespaced() -> None:
    first = point_id_for("gen", "chunk", 3, "a" * 64)
    assert first == point_id_for("gen", "chunk", 3, "a" * 64)
    assert uuid.UUID(first).version == 5
    assert first == str(uuid.uuid5(APP_NAMESPACE, f"gen/chunk/3/{'a' * 64}"))
    assert first != point_id_for("gen2", "chunk", 3, "a" * 64)
    assert first != point_id_for("gen", "chunk2", 3, "a" * 64)
    assert first != point_id_for("gen", "chunk", 4, "a" * 64)
    assert first != point_id_for("gen", "chunk", 3, "b" * 64)


# ------------------------------------------------------------------ 内存替身


def _payload(*, revision: str, chunk_set: str, owner: str, region: str, ordinal: int) -> dict:
    return {
        "document_revision_id": revision,
        "chunk_set_id": chunk_set,
        "owner_id": owner,
        "region": region,
        "ordinal": ordinal,
    }


def test_memory_store_filter_semantics_match_qdrant() -> None:
    store = InMemoryVectorStore()
    store.ensure_collection(name="c", dimensions=2, distance="Cosine")
    store.upsert(
        name="c",
        points=[
            VectorPoint(point_id="p1", vector=[1.0, 0.0], payload=_payload(revision="r1", chunk_set="s1", owner="system", region="body", ordinal=0)),
            VectorPoint(point_id="p2", vector=[0.0, 1.0], payload=_payload(revision="r2", chunk_set="s2", owner="local-user", region="exercise", ordinal=1)),
            VectorPoint(point_id="p3", vector=[0.7, 0.7], payload=_payload(revision="r1", chunk_set="s2", owner="local-user", region="body", ordinal=2)),
        ],
    )
    assert store.count(name="c") == 3
    assert store.count(name="c", allowed=AllowedFilter(revision_ids=("r1",))) == 2
    assert store.count(name="c", allowed=AllowedFilter(owners=("system",), region="body")) == 1
    # 空元组表示"不允许任何值"
    assert store.count(name="c", allowed=AllowedFilter(revision_ids=())) == 0

    hits = store.search(
        name="c", vector=[1.0, 0.0], limit=10, allowed=AllowedFilter(region="body")
    )
    assert [hit.point_id for hit in hits] == ["p1", "p3"]  # 余弦排序
    assert hits[0].score > hits[1].score

    store.delete_by_filter(name="c", allowed=AllowedFilter(revision_ids=("r1",)))
    assert store.count(name="c") == 1
    assert store.point_ids("c") == ["p2"]


def test_memory_store_guards() -> None:
    store = InMemoryVectorStore()
    with pytest.raises(AppError) as missing:
        store.count(name="nope")
    assert missing.value.code == "QDRANT_COLLECTION_MISSING"

    store.ensure_collection(name="c", dimensions=2, distance="Cosine")
    with pytest.raises(AppError) as mismatch:
        store.ensure_collection(name="c", dimensions=3, distance="Cosine")
    assert mismatch.value.code == "QDRANT_COLLECTION_MISMATCH"

    with pytest.raises(AppError) as bad_vector:
        store.upsert(
            name="c",
            points=[VectorPoint(point_id="p", vector=[1.0, 2.0, 3.0], payload={})],
        )
    assert bad_vector.value.code == "VECTOR_DIMENSION_MISMATCH"

    with pytest.raises(AppError) as no_filter:
        store.delete_by_filter(name="c", allowed=AllowedFilter())
    assert no_filter.value.code == "QDRANT_FILTER_REQUIRED"

    with pytest.raises(AppError) as bad_query:
        store.search(name="c", vector=[1.0], limit=1, allowed=None)
    assert bad_query.value.code == "VECTOR_DIMENSION_MISMATCH"

    store.delete_collection("c")
    assert store.collection_exists("c") is False
    assert store.ping() is True
