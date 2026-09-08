"""健康检查：真实可用性、最小字段，不泄露配置。"""

from __future__ import annotations

import json

REQUIRED_FIELDS = {"status", "service", "apiVersion", "time"}


def test_health_returns_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "zhiqikeyuan-api"
    assert body["apiVersion"] == "v1"
    assert set(body) == REQUIRED_FIELDS


def test_health_does_not_leak_config(client):
    body = client.get("/api/v1/health").json()
    text = json.dumps(body, ensure_ascii=False)
    assert "ZQKY_" not in text
    assert "allowed_origins" not in text
    assert "127.0.0.1" not in text
