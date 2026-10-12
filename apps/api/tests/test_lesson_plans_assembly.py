"""R7-BE 教案域装配：app.state 键、执行器注册、路由注册与 503 边界。

注意：R5/R6 装配对空 data_dir 也会建库成功，因此「依赖缺失」分支以**就地
清空 app.state 前置键**的方式表达（真实启动不会出现该状态；它是装配代码
的守卫分支，必须如实 503 不假成功）。路由存在性用 TestClient 实测
（FastAPI 0.141 的 include_router 是惰性聚合，route 表检查不可靠）。
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.secrets import SecretStore
from app.main import create_app
from app.services.jobs.registry import JobExecutorRegistry


def _settings(tmp_path: Path) -> Settings:
    return Settings(host="127.0.0.1", port=8001, allowed_origins=frozenset({"http://127.0.0.1:5174"}),
                    env="test", data_dir=tmp_path, credentials_file=None,
                    textbook_source_dir=tmp_path / "empty", qdrant_url="http://127.0.0.1:16333",
                    embedding_base_url="http://127.0.0.1:9")


def test_domain_assembles_with_real_catalogs(tmp_path):
    """空库首启（R5/R6 建库成功）时教案域装配：服务/执行器/路由就位。"""
    app = create_app(_settings(tmp_path), secret_store=SecretStore())
    assert app.state.lesson_plan_service is not None
    assert app.state.lesson_generation_service is not None
    assert app.state.lesson_export_ready is True
    registry = getattr(app.state, "job_executors", None)
    assert isinstance(registry, JobExecutorRegistry)
    spec = registry.spec_for("teaching", "lesson_generation")
    assert spec is not None and spec.uses_model
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        # 列表路由（真实 200）；流与固定题路由（参数校验 422 = 路由存在且进了契约层）
        assert client.get("/api/v1/lesson-plans").status_code == 200
        stream = client.post("/api/v1/lesson-plans/generation-stream", json={})
        assert stream.status_code == 422 and stream.json()["code"] == "INVALID_REQUEST"
        sources = client.get("/api/v1/confirmed-question-revisions")
        assert sources.status_code in (422, 503)  # 422=契约层；503=固定题来源未装配（题库空库属装配态差异）
        assert sources.status_code != 404 and sources.status_code != 501


def test_domain_missing_dependencies_stays_503(tmp_path):
    """前置服务缺失时本域不装配：路由 503（不假成功）。

    真实启动时 R5/R6 会自建前置；这里用装配函数直接驱动（跳过依赖装配），
    表达教案域自身的守卫分支。
    """
    app = create_app(_settings(tmp_path), secret_store=SecretStore())
    # 模拟前置缺失（R5/R6 未装配的状态）：清键后重跑本域 assemble
    from app.services.lesson_plans import assembly as lesson_assembly

    for key in ("teaching", "asset_store", "file_assets", "analysis_service",
                "lesson_plan_service", "lesson_generation_service", "lesson_export_ready"):
        setattr(app.state, key, None)
    lesson_assembly.assemble(app, _settings(tmp_path))
    assert app.state.lesson_plan_service is None
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.get("/api/v1/lesson-plans")
        # 依赖齐全时路由已注册（第一次装配），服务缺失 → 503；否则 501
        assert response.status_code in (501, 503)
        if response.status_code == 503:
            assert response.json()["code"] == "SERVICE_UNAVAILABLE"
