"""最小骨架冒烟（推倒重做后）：装配、路由边界、AssetStore、凭证绑定。

覆盖推倒重做保留的骨架行为（不依赖任何已删除业务域）：
- create_app 装配成功（无业务目录要求）；
- /health 200；未知 /api/v1 路由 501 FEATURE_NOT_IMPLEMENTED（不假成功）；
- /chat/stream 与 /agent/stream 路由存在（模型缺失时为流前 HTTP 错误）；
- /agent/upload 落 AssetStore 并返回 sha256（内容寻址、幂等）；
- SecretStore 绑定 .env 文件后就地生效。
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.secrets import SecretStore
from app.main import create_app
from app.services.assets.store import AssetStore

ALLOWED = frozenset({"http://127.0.0.1:5173"})


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=tmp_path)
    app = create_app(settings)
    return TestClient(app, base_url="http://127.0.0.1:8001")


def test_health_and_unknown_route(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/api/v1/health").status_code == 200
        # R3 起知识点域已装配：/knowledge-points 是真实端点（空库 → 200 空页）
        resp = client.get("/api/v1/knowledge-points")
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0, "offset": 0, "limit": 50}
        # 未知业务路由仍 501 FEATURE_NOT_IMPLEMENTED（不假成功）
        unknown = client.get("/api/v1/practices")
        assert unknown.status_code in (501, 503)  # 503 = 域模块在列但装配未回归
        if unknown.status_code == 501:
            assert unknown.json()["code"] == "FEATURE_NOT_IMPLEMENTED"


def test_chat_and_agent_routes_present(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        chat = client.post("/api/v1/chat/stream", json={
            "requestId": "r1", "modelProfileId": "no-such", "messages": [{"role": "user", "content": "hi"}],
        })
        # 路由存在即可：空/畸形请求 422 或模型缺失 404 都是流前 HTTP 错误（非 501）
        assert chat.status_code in (404, 422)
        agent = client.post("/api/v1/agent/stream", json={
            "requestId": "r1", "threadId": "t1", "message": "hi", "modelProfileId": "no-such",
        })
        assert agent.status_code == 404
        assert agent.json()["code"] == "MODEL_PROFILE_NOT_FOUND"


def test_agent_upload_stores_blob(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        resp = client.post("/api/v1/agent/upload", files={"file": ("t.txt", b"hello", "text/plain")})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["assetId"] == body["sha256"]
        assert (tmp_path / "assets" / "blobs" / body["assetId"]).exists()


def test_asset_store_roundtrip(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "assets")
    first = store.store_original(b"same-bytes", media_type="text/plain", original_name="a.txt")
    second = store.store_original(b"same-bytes", media_type="text/plain", original_name="b.txt")
    assert first.sha256 == second.sha256  # 内容寻址幂等
    assert store.read(first.blob_key) == b"same-bytes"


def test_secret_store_env_binding(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('ZQKY_API_KEY_CONN_X="sk-test"\n', encoding="utf-8")
    store = SecretStore()
    store.bind_env_file(env_file)
    assert store.resolve("CONN_X") == "sk-test"
