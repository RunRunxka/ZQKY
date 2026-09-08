"""未实现接口必须返回 501 与统一错误信封，不得返回假成功。"""

from __future__ import annotations

import pytest

FUTURE_ROUTES = [
    ("GET", "/api/v1/models"),
    ("GET", "/api/v1/lesson-plans"),
    ("POST", "/api/v1/templates/inspect"),
    ("POST", "/api/v1/exports"),
]


@pytest.mark.parametrize("method,path", FUTURE_ROUTES)
def test_future_routes_return_501_envelope(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 501
    assert response.headers["x-request-id"]
    body = response.json()
    assert body["code"] == "FEATURE_NOT_IMPLEMENTED"
    assert body["requestId"]
    assert body["retryable"] is False


def test_routes_outside_v1_return_404_envelope(client):
    response = client.get("/definitely-missing")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOT_FOUND"
    assert body["requestId"]
