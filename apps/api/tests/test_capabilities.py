"""能力状态：按实际实现如实报告（推倒重做后的最小骨架）。"""

from __future__ import annotations

REQUIRED_FEATURES = {"model_settings", "chat", "agent"}
READY_FEATURES = {"model_settings", "chat", "agent"}


def test_capabilities_reports_feature_state(client):
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "zhiqikeyuan-api"
    assert body["apiVersion"] == "v1"
    assert body["generatedAt"]
    features = {item["feature"]: item for item in body["capabilities"]}
    assert REQUIRED_FEATURES <= set(features)
    for feature in READY_FEATURES:
        assert features[feature]["status"] == "ready", feature
    for feature, item in features.items():
        assert item["detail"].strip()


def test_capabilities_does_not_claim_unimplemented_success(client):
    statuses = {
        item["status"] for item in client.get("/api/v1/capabilities").json()["capabilities"]
    }
    assert statuses <= {"planned", "ready", "unavailable"}
