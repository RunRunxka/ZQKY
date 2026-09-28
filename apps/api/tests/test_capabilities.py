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

# RAG-REBUILD v1.0 起教材资料库与题库有真实存储实现；rag 仍按运行时状态动态报告。
READY_FEATURES = {"model_settings", "chat", "textbook_repository", "question_bank"}


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
