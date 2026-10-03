"""能力状态：按实际实现如实报告，已实现能力 ready，其余 planned。"""

from __future__ import annotations

REQUIRED_FEATURES = {
    "model_settings",
    "chat",
    "lesson_plan_ai_fill",
    "paper_compose",
    "templates",
    "textbook_repository",
    "question_bank",
    "rag",
    "agent_tasks",
    "mcp",
    "skills",
}

# B5 正常四库装配含真实教案服务与执行器；缺少依赖时须动态 unavailable。
READY_FEATURES = {"model_settings", "chat", "textbook_repository", "question_bank", "lesson_plan_ai_fill"}


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
    assert features["rag"]["status"] == "unavailable"
    for feature, item in features.items():
        if feature not in READY_FEATURES | {"rag"}:
            assert item["status"] == "planned", feature
        assert item["detail"].strip()


def test_capabilities_does_not_claim_unimplemented_success(client):
    statuses = {
        item["status"] for item in client.get("/api/v1/capabilities").json()["capabilities"]
    }
    assert statuses == {"planned", "ready", "unavailable"}


def test_lesson_capability_does_not_claim_ready_when_real_service_is_missing(client, monkeypatch):
    monkeypatch.setattr(client.app.state, "lesson_plan_service", None)
    features = {item["feature"]: item for item in client.get("/api/v1/capabilities").json()["capabilities"]}
    assert features["lesson_plan_ai_fill"]["status"] == "unavailable"
    response = client.get("/api/v1/lesson-plans")
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
