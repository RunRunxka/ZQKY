"""本机访问防护：Host 回环校验与 Origin 允许列表。"""

from __future__ import annotations


def test_request_without_origin_allowed(client):
    assert client.get("/api/v1/health").status_code == 200


def test_allowed_origin_passes(client):
    response = client.get("/api/v1/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 200


def test_unknown_origin_rejected(client):
    response = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "FORBIDDEN_ORIGIN"
    assert body["requestId"]
    assert body["retryable"] is False


def test_non_loopback_host_rejected(foreign_host_client):
    response = foreign_host_client.get("/api/v1/health")
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_HOST"
