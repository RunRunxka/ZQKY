"""能力状态：按实际实现如实报告，model_settings / chat / skills 已就绪，其余 planned。"""

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


def test_capabilities_reports_feature_state(client):
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "zhiqikeyuan-api"
    assert body["apiVersion"] == "v1"
    assert body["generatedAt"]
    features = {item["feature"]: item for item in body["capabilities"]}
    assert REQUIRED_FEATURES <= set(features)
    assert features["model_settings"]["status"] == "ready"
    assert features["chat"]["status"] == "ready"
    assert features["skills"]["status"] == "ready"
    # 技能只到提示词级：不得把 MCP 执行当作已实现
    assert features["mcp"]["status"] == "planned"
    for feature, item in features.items():
        if feature not in ("model_settings", "chat", "skills"):
            assert item["status"] == "planned"
        assert item["detail"].strip()


def test_capabilities_does_not_claim_unimplemented_success(client):
    statuses = {
        item["status"] for item in client.get("/api/v1/capabilities").json()["capabilities"]
    }
    assert statuses == {"planned", "ready"}
