"""Ollama Embedding 适配器测试：地址闸门、原生接口、输出校验、digest 身份。

全部使用 ``httpx.MockTransport`` 注入上游；不连接真实 Ollama（真实调用由总控在集成阶段验收）。
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.exceptions import AppError
from app.providers.embeddings.ollama_embedding import (
    EMBEDDING_PROBE_TEXTS,
    OllamaEmbeddingProvider,
    is_embedding_capable,
    is_remote_or_cloud_model,
    model_names_match,
    normalize_loopback_base_url,
    normalize_model_tag,
)

TAGS_PAYLOAD = {
    "models": [
        {
            "name": "qwen2.5:7b",
            "size": 4_700_000_000,
            "digest": "sha256:chat-digest",
        },
        {
            "name": "bge-m3:latest",
            "size": 1_200_000_000,
            "digest": "sha256:embed-digest",
        },
    ]
}

SHOW_EMBED = {
    "details": {"family": "bert", "parameter_size": "567M", "format": "gguf"},
    "capabilities": ["embedding"],
}
SHOW_CHAT = {
    "details": {"family": "qwen2", "parameter_size": "7.6B", "format": "gguf"},
    "capabilities": ["completion", "tools"],
}


def make_provider(handler, *, base_url: str = "http://127.0.0.1:11434") -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(base_url, transport=httpx.MockTransport(handler))


class Router:
    """按 (method, path) 路由响应，并记录调用。"""

    def __init__(self, routes: dict[tuple[str, str], object]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str, object]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = None
        if request.content:
            try:
                body = json.loads(request.content)
            except ValueError:
                body = request.content
        self.calls.append((request.method, request.url.path, body))
        entry = self.routes.get((request.method, request.url.path))
        if entry is None:
            return httpx.Response(404, json={"error": "not found"})
        if callable(entry):
            return entry(request)
        status, payload = entry
        # 允许 NaN 等非标准 JSON 字面量：用 allow_nan 自己序列化，模拟上游异常输出
        return httpx.Response(
            status, content=json.dumps(payload, allow_nan=True).encode("utf-8")
        )

    def bodies(self, method: str, path: str) -> list[object]:
        return [body for call_method, call_path, body in self.calls if (call_method, call_path) == (method, path)]

    def paths(self) -> list[str]:
        return [path for _method, path, _body in self.calls]


def embed_ok(dimensions: int = 3):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={"embeddings": [[0.1 * (index + 1)] * dimensions for index in range(len(payload["input"]))]},
        )

    return handler


# --------------------------------------------------------------------------- 地址


@pytest.mark.parametrize(
    "base_url",
    [
        "http://192.168.1.9:11434",
        "https://api.example.com/v1",
        "http://[::2]:11434",
        "http://user:pass@127.0.0.1:11434",
        "http://127.0.0.1:11434?x=1",
        "ftp://127.0.0.1:11434",
        "",
    ],
)
def test_non_loopback_base_urls_are_rejected_at_construction(base_url: str) -> None:
    with pytest.raises(AppError) as exc_info:
        OllamaEmbeddingProvider(base_url)
    assert exc_info.value.code in {
        "EMBEDDING_BASE_URL_NOT_LOCAL",
        "EMBEDDING_BASE_URL_INVALID",
    }
    assert exc_info.value.status_code == 422


def test_loopback_base_url_is_normalized() -> None:
    provider = OllamaEmbeddingProvider("http://localhost:11434/")
    assert provider.base_url == "http://localhost:11434"
    assert normalize_loopback_base_url("http://[::1]:11434") == "http://[::1]:11434"


# ------------------------------------------------------------------ 模型清单/能力


def test_list_models_sorted_and_enriched_from_show() -> None:
    router = Router(
        {
            ("GET", "/api/tags"): (200, TAGS_PAYLOAD),
            ("GET", "/api/show"): (200, SHOW_EMBED),
        }
    )
    models = make_provider(router).list_models()
    assert [model.name for model in models] == ["bge-m3:latest", "qwen2.5:7b"]
    bge = models[0]
    assert bge.digest == "embed-digest"
    assert bge.sizeBytes == 1_200_000_000
    assert bge.family == "bert"
    assert bge.parameterSize == "567M"
    assert bge.isEmbeddingCapable is True
    # 详情接口一律按 plan 约定携带 {"model": name}（调用顺序与排序无关，按集合比较）
    assert {
        json.dumps(body, sort_keys=True) for body in router.bodies("GET", "/api/show")
    } == {
        json.dumps({"model": model.name}, sort_keys=True) for model in models
    }


def test_list_models_survives_show_failure_per_model() -> None:
    def show(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload["model"] == "qwen2.5:7b":
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json=SHOW_EMBED)

    router = Router({("GET", "/api/tags"): (200, TAGS_PAYLOAD), ("GET", "/api/show"): show})
    models = make_provider(router).list_models()
    by_name = {model.name: model for model in models}
    assert by_name["qwen2.5:7b"].family == ""
    assert by_name["qwen2.5:7b"].isEmbeddingCapable is False
    assert by_name["bge-m3:latest"].isEmbeddingCapable is True


def test_list_models_on_unreachable_service_is_503_not_empty_list() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(AppError) as exc_info:
        make_provider(boom).list_models()
    assert (exc_info.value.code, exc_info.value.status_code) == ("EMBEDDING_UNAVAILABLE", 503)
    assert exc_info.value.retryable is True


def test_embedding_capability_detection() -> None:
    assert is_embedding_capable({"capabilities": ["embedding"]}) is True
    assert is_embedding_capable({"capabilities": ["completion", "tools"]}) is False
    # capabilities 存在但为空：按"不具备嵌入能力"处理，不回退 family
    assert is_embedding_capable({"capabilities": [], "family": "bert"}) is False
    assert is_embedding_capable({"family": "bert"}) is True
    assert is_embedding_capable({"family": "nomic-bert"}) is True
    assert is_embedding_capable({"family": "llama"}) is False
    assert is_embedding_capable({}) is False
    assert is_embedding_capable(None) is False
    assert is_remote_or_cloud_model("gpt-oss:120b-cloud", {}) is True
    assert is_remote_or_cloud_model("bge-m3", {"remote_host": "https://example.com"}) is True
    assert is_remote_or_cloud_model("bge-m3", {"family": "bert"}) is False


# --------------------------------------------------------------------- embed


def test_embed_sends_truncate_false_and_validates_shape() -> None:
    router = Router(
        {
            ("POST", "/api/embed"): (
                200,
                {"embeddings": [[0.5, 0.5], [0.25, 0.75]]},
            )
        }
    )
    provider = make_provider(router)
    vectors = provider.embed(model="bge-m3:latest", texts=["甲", "乙"])
    assert vectors == [[0.5, 0.5], [0.25, 0.75]]
    assert router.bodies("POST", "/api/embed") == [
        {"model": "bge-m3:latest", "input": ["甲", "乙"], "truncate": False}
    ]


@pytest.mark.parametrize(
    "embeddings",
    [
        [[1.0, 0.0]],  # 数量少一条
        [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]],  # 数量多一条
        [[1.0, 0.0], [1.0]],  # 维度不一致
        [[1.0, 0.0], [float("nan"), 1.0]],  # 非有限值
        [[1.0, 0.0], [0.0, 0.0]],  # 零向量
        [[1.0, 0.0], ["a", 1.0]],  # 非数值
        [[1.0, 0.0], []],  # 空向量
    ],
)
def test_embed_rejects_invalid_output(embeddings: list) -> None:
    router = Router({("POST", "/api/embed"): (200, {"embeddings": embeddings})})
    with pytest.raises(AppError) as exc_info:
        make_provider(router).embed(model="bge-m3", texts=["甲", "乙"])
    assert exc_info.value.code == "EMBEDDING_INVALID_OUTPUT"
    assert exc_info.value.retryable is False


def test_embed_rejects_empty_input_before_send() -> None:
    router = Router({("POST", "/api/embed"): (200, {"embeddings": []})})
    with pytest.raises(AppError) as exc_info:
        make_provider(router).embed(model="bge-m3", texts=[])
    assert exc_info.value.code == "INVALID_REQUEST"
    assert router.calls == []


def test_embed_missing_model_maps_to_missing() -> None:
    router = Router({("POST", "/api/embed"): (404, {"error": "model 'x' not found"})})
    with pytest.raises(AppError) as exc_info:
        make_provider(router).embed(model="x", texts=["甲"])
    assert exc_info.value.code == "EMBEDDING_MODEL_MISSING"


def test_embed_out_of_memory_is_retryable() -> None:
    router = Router(
        {("POST", "/api/embed"): (500, {"error": "CUDA error: out of memory"})}
    )
    with pytest.raises(AppError) as exc_info:
        make_provider(router).embed(model="bge-m3", texts=["甲"])
    assert exc_info.value.code == "EMBEDDING_OUT_OF_MEMORY"
    assert exc_info.value.retryable is True


def test_redirect_is_not_followed_and_is_reported() -> None:
    router = Router({("GET", "/api/tags"): (302, {"error": "moved"})})
    with pytest.raises(AppError) as exc_info:
        make_provider(router).list_models()
    assert exc_info.value.code == "EMBEDDING_REDIRECT_REJECTED"


# ------------------------------------------------------------------- digest


def test_manifest_digest_strips_prefix_and_matches_latest_tag() -> None:
    router = Router({("GET", "/api/tags"): (200, TAGS_PAYLOAD)})
    provider = make_provider(router)
    assert provider.manifest_digest("bge-m3:latest") == "embed-digest"
    assert provider.manifest_digest("bge-m3") == "embed-digest"
    with pytest.raises(AppError) as exc_info:
        provider.manifest_digest("nope")
    assert exc_info.value.code == "EMBEDDING_MODEL_MISSING"


# -------------------------------------------------------------------- 检测


def test_verify_candidate_happy_path() -> None:
    router = Router(
        {
            ("GET", "/api/tags"): (200, TAGS_PAYLOAD),
            ("GET", "/api/show"): (200, SHOW_EMBED),
            ("POST", "/api/embed"): embed_ok(4),
        }
    )
    result = make_provider(router).verify_embedding_candidate(model_name="bge-m3:latest")
    assert result.dimensions == 4
    assert result.sample_count == len(EMBEDDING_PROBE_TEXTS)
    assert result.model_manifest_digest == "embed-digest"
    assert result.stable_digest is True
    assert router.bodies("POST", "/api/embed") == [
        {"model": "bge-m3:latest", "input": list(EMBEDDING_PROBE_TEXTS), "truncate": False}
    ]
    # 调用前后各取一次 digest
    assert router.paths().count("/api/tags") == 2


def test_verify_candidate_rejects_digest_change() -> None:
    state = {"count": 0}

    def tags(request: httpx.Request) -> httpx.Response:
        state["count"] += 1
        payload = json.loads(json.dumps(TAGS_PAYLOAD))
        if state["count"] > 1:
            payload["models"][1]["digest"] = "sha256:changed"
        return httpx.Response(200, json=payload)

    router = Router(
        {
            ("GET", "/api/tags"): tags,
            ("GET", "/api/show"): (200, SHOW_EMBED),
            ("POST", "/api/embed"): embed_ok(2),
        }
    )
    with pytest.raises(AppError) as exc_info:
        make_provider(router).verify_embedding_candidate(model_name="bge-m3:latest")
    assert (exc_info.value.code, exc_info.value.status_code) == ("EMBEDDING_MODEL_CHANGED", 409)


def test_verify_candidate_rejects_chat_and_cloud_models() -> None:
    chat_router = Router(
        {("GET", "/api/tags"): (200, TAGS_PAYLOAD), ("GET", "/api/show"): (200, SHOW_CHAT)}
    )
    with pytest.raises(AppError) as chat_error:
        make_provider(chat_router).verify_embedding_candidate(model_name="qwen2.5:7b")
    assert chat_error.value.code == "EMBEDDING_MODEL_NOT_EMBEDDING"

    cloud_tags = {"models": [{"name": "gpt-oss:120b-cloud", "size": 1, "digest": "sha256:c"}]}
    cloud_router = Router(
        {
            ("GET", "/api/tags"): (200, cloud_tags),
            ("GET", "/api/show"): (200, {"details": {"family": "gpt_oss", "remote_host": "https://ollama.com"}}),
        }
    )
    with pytest.raises(AppError) as cloud_error:
        make_provider(cloud_router).verify_embedding_candidate(model_name="gpt-oss:120b-cloud")
    assert cloud_error.value.code == "EMBEDDING_MODEL_NOT_LOCAL"


def test_verify_candidate_missing_model() -> None:
    router = Router({("GET", "/api/tags"): (200, TAGS_PAYLOAD)})
    with pytest.raises(AppError) as exc_info:
        make_provider(router).verify_embedding_candidate(model_name="not-installed")
    assert exc_info.value.code == "EMBEDDING_MODEL_MISSING"


# ------------------------------------------------- v1.3 模型名 tag 语义归一


def test_normalize_model_tag_semantics() -> None:
    assert normalize_model_tag("bge-m3") == "bge-m3:latest"
    assert normalize_model_tag("bge-m3:latest") == "bge-m3:latest"
    assert normalize_model_tag("bge-m3:v2") == "bge-m3:v2"
    assert normalize_model_tag("  bge-m3  ") == "bge-m3:latest"
    assert normalize_model_tag("") == ""
    # registry/namespace 前缀只检查最后一段是否带 tag
    assert normalize_model_tag("registry:5000/team/bge-m3") == "registry:5000/team/bge-m3:latest"
    assert normalize_model_tag("registry:5000/team/bge-m3:v2") == "registry:5000/team/bge-m3:v2"


def test_model_names_match_is_tag_aware_not_substring() -> None:
    assert model_names_match("bge-m3", "bge-m3:latest") is True
    assert model_names_match("bge-m3:latest", "bge-m3") is True
    assert model_names_match("bge-m3", " bge-m3:latest ") is True
    # 不得改成"包含即命中"
    assert model_names_match("bge-m3", "bge-m3-large") is False
    assert model_names_match("bge-m3", "bge-m3-large:latest") is False
    assert model_names_match("bge-m3:latest", "bge-m3-large") is False
    assert model_names_match("bge-m3-large", "bge-m3") is False
    # 不同 tag 不是同一模型
    assert model_names_match("bge-m3", "bge-m3:v2") is False
    assert model_names_match("bge-m3:latest", "bge-m3:v2") is False
    assert model_names_match("", "") is False
    assert model_names_match("bge-m3", "") is False


def test_manifest_digest_matches_latest_tag_both_directions() -> None:
    """tags 里是无 tag 的 bge-m3，调用方按 bge-m3:latest 查也要命中（反之亦然）。"""
    router = Router(
        {
            ("GET", "/api/tags"): (
                200,
                {"models": [{"name": "bge-m3", "size": 1, "digest": "sha256:abc"}]},
            )
        }
    )
    provider = make_provider(router)
    assert provider.manifest_digest("bge-m3:latest") == "abc"
    assert provider.manifest_digest("bge-m3") == "abc"

    only_large = Router(
        {
            ("GET", "/api/tags"): (
                200,
                {"models": [{"name": "bge-m3-large:latest", "size": 1, "digest": "sha256:x"}]},
            )
        }
    )
    with pytest.raises(AppError) as exc_info:
        make_provider(only_large).manifest_digest("bge-m3")
    assert exc_info.value.code == "EMBEDDING_MODEL_MISSING"


def test_list_models_keeps_raw_tag_names() -> None:
    """在场列表保留 Ollama 原始 tag（不归一），归一判断由调用方按需做。"""
    router = Router({("GET", "/api/tags"): (200, TAGS_PAYLOAD), ("GET", "/api/show"): (200, SHOW_EMBED)})
    names = [candidate.name for candidate in make_provider(router).list_models()]
    assert names == ["bge-m3:latest", "qwen2.5:7b"]
