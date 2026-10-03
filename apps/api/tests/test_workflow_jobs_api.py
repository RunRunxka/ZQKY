"""公共任务路由测试（TEACHING-LOOP B0 / 验收 A7）。

覆盖：视图字段（camelCase）、404/422/503、取消幂等、重试语义（仅终态、保留冻结输入）。
所有数据在 tmp_path 的隔离数据根内；不触网、不调用模型。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.jobs.registry import JobExecutorRegistry
from tests.conftest import make_settings


@pytest.fixture()
def app_client(tmp_path: Path):
    app = create_app(make_settings(tmp_path / "data"))
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        # These B0 state-route fixtures intentionally have no executable export.
        # B4 registers real exports; registered queued recovery is covered by the
        # registry/API integration tests, while these assertions retain 409 for
        # an unregistered queued job and frozen-input-only terminal retry.
        app.state.job_executors = JobExecutorRegistry()
        yield app, client


def _teaching_store(app):
    engine = app.state.job_engine
    assert engine is not None, "本地数据库运行时未装配任务引擎"
    return engine.store("teaching")


def _create_job(app, *, kind: str = "export", payload: dict | None = None, job_id: str = "job-1"):
    return _teaching_store(app).create(
        job_id=job_id,
        kind=kind,
        frozen_input=payload if payload is not None else {"variant": "teacher"},
        model_snapshot={"profileId": "p1", "fingerprint": "fp-1"},
    )


def test_get_job_view_fields_are_camel_case(app_client) -> None:
    app, client = app_client
    record = _create_job(app)
    response = client.get(f"/api/v1/workflow-jobs/{record.job_id}?domain=teaching")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["jobId"] == "job-1"
    assert body["domain"] == "teaching"
    assert body["kind"] == "export"
    assert body["attempt"] == 0
    assert body["state"] == "queued"
    assert body["result"] is None
    assert body["error"] is None
    # 内部字段不得泄漏
    assert "frozenInput" not in body and "leaseToken" not in body


def test_unknown_job_returns_404_job_not_found(app_client) -> None:
    _app, client = app_client
    response = client.get("/api/v1/workflow-jobs/missing?domain=teaching")
    assert response.status_code == 404
    assert response.json()["code"] == "JOB_NOT_FOUND"
    assert response.json()["retryable"] is False


def test_invalid_domain_returns_422(app_client) -> None:
    _app, client = app_client
    assert client.get("/api/v1/workflow-jobs/x?domain=bogus").status_code == 422
    body = client.post(
        "/api/v1/workflow-jobs/x/cancel", json={"domain": "bogus"}
    ).json()
    assert body["code"] == "INVALID_REQUEST"


def test_missing_domain_query_returns_422_with_fields(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path / "data"))
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.get("/api/v1/workflow-jobs/x")
        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_REQUEST"


def test_engine_not_assembled_returns_503(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path / "data"), bootstrap_textbooks=False)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.get("/api/v1/workflow-jobs/x?domain=teaching")
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert response.json()["retryable"] is True


def test_cancel_queued_job_is_immediate_and_idempotent(app_client) -> None:
    app, client = app_client
    _create_job(app)
    first = client.post(
        "/api/v1/workflow-jobs/job-1/cancel", json={"domain": "teaching"}
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["state"] == "cancelled"
    # 幂等：再次取消不改状态、不报错
    second = client.post(
        "/api/v1/workflow-jobs/job-1/cancel", json={"domain": "teaching"}
    )
    assert second.status_code == 200
    assert second.json()["state"] == "cancelled"


def test_retry_only_from_terminal_state_and_keeps_frozen_input(app_client) -> None:
    app, client = app_client
    store = _teaching_store(app)
    _create_job(app, payload={"variant": "student"}, job_id="job-r")

    # queued 不可重试
    blocked = client.post("/api/v1/workflow-jobs/job-r/retry", json={"domain": "teaching"})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "JOB_NOT_RETRYABLE"

    # 取消（终态）后可重试，冻结输入与模型指纹保留
    client.post("/api/v1/workflow-jobs/job-r/cancel", json={"domain": "teaching"})
    retried = client.post("/api/v1/workflow-jobs/job-r/retry", json={"domain": "teaching"})
    assert retried.status_code == 200, retried.text
    assert retried.json()["state"] == "queued"
    record = store.get("job-r")
    assert record.frozen_input == {"variant": "student"}
    assert record.model_snapshot == {"profileId": "p1", "fingerprint": "fp-1"}


def test_running_job_cancel_keeps_state_running_until_executor_stops(app_client) -> None:
    app, client = app_client
    store = _teaching_store(app)
    _create_job(app, job_id="job-run")
    store.claim("job-run")
    response = client.post(
        "/api/v1/workflow-jobs/job-run/cancel", json={"domain": "teaching"}
    )
    assert response.status_code == 200
    assert response.json()["state"] == "running"
    assert store.cancel_requested("job-run") is True


def test_job_payload_does_not_leak_internal_columns(app_client) -> None:
    app, client = app_client
    _create_job(app, job_id="job-json")
    body = client.get("/api/v1/workflow-jobs/job-json?domain=teaching").json()
    serialized = json.dumps(body, ensure_ascii=False)
    for forbidden in ("leaseExpiresAt", "leaseToken", "frozenInput", "inputHash", "modelSnapshot"):
        assert forbidden not in serialized
