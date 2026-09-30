"""V8 公共任务路由独立探针（V00 / TEACHING-LOOP B0，真实 FastAPI + TestClient）。

覆盖（`/api/v1/workflow-jobs/...`）：
  8① 视图字段 camelCase（jobId/domain/kind/attempt/state/result/error）
  8② 未知 id → 404 JOB_NOT_FOUND
  8③ 非法 domain → 422 INVALID_REQUEST（GET 与 POST）
  8④ 未装配 → 503 SERVICE_UNAVAILABLE（引擎缺失 / 已知域但没有对应仓储）
  8⑤ 取消幂等（queued → cancelled；running 只置标志；重复取消不改状态）
  8⑥ queued/running 重试 → 409 JOB_NOT_RETRYABLE；终态重试 → queued（attempt 不变）
  附加：失败任务的视图带统一错误信封；GET 的 domain 缺省/多余参数行为

全部使用 tmp_path 风格临时数据根；不读写正式 .local-data 与 apps/api/.env
（显式注入进程内 SecretStore）。
"""

from __future__ import annotations

from pathlib import Path

from _probe_common import check, cleanup, record, run_main, temp_root

from app.core.config import Settings
from app.core.secrets import SecretStore

PROBE = "v8_workflow_jobs_api_probe"


def _settings(data_dir: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8000,
        allowed_origins=frozenset({"http://127.0.0.1:5173"}),
        env="test",
        data_dir=data_dir,
        credentials_file=None,
    )


def _client(data_dir: Path, *, bootstrap: bool = True):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(_settings(data_dir), secret_store=SecretStore(), bootstrap_textbooks=bootstrap)
    # 本机访问防护会拒绝非回环 Host，因此 TestClient 使用回环 base_url
    return app, TestClient(app, base_url="http://127.0.0.1:8000")


def main() -> None:
    root = temp_root("v8")
    try:
        app, client = _client(root / "data")
        with client:
            engine = app.state.job_engine
            check("v8.0a engine assembled with three domain stores", set(engine._stores) == {"question", "knowledge", "teaching"}, str(sorted(engine._stores)))
            store = engine.store("teaching")

            # 8① camelCase 视图
            job = store.create(kind="export", frozen_input={"format": "docx"}, model_snapshot={"m": 1})
            response = client.get(f"/api/v1/workflow-jobs/{job.job_id}", params={"domain": "teaching"})
            check("v8.1a GET returns 200", response.status_code == 200, str(response.status_code))
            body = response.json()
            check(
                "v8.1b view fields are exactly camelCase JobView",
                set(body) == {"jobId", "domain", "kind", "attempt", "state", "result", "error"},
                str(sorted(body)),
            )
            check(
                "v8.1c view values",
                body["jobId"] == job.job_id
                and body["domain"] == "teaching"
                and body["kind"] == "export"
                and body["attempt"] == 0
                and body["state"] == "queued"
                and body["result"] is None
                and body["error"] is None,
                str(body),
            )

            # 8② 404
            missing = client.get("/api/v1/workflow-jobs/no-such-job", params={"domain": "teaching"})
            check(
                "v8.2 unknown id -> 404 JOB_NOT_FOUND",
                missing.status_code == 404 and missing.json().get("code") == "JOB_NOT_FOUND",
                f"status={missing.status_code} body={missing.json()}",
            )

            # 8③ 非法 domain
            bad_get = client.get(f"/api/v1/workflow-jobs/{job.job_id}", params={"domain": "bogus"})
            check(
                "v8.3a GET illegal domain -> 422 INVALID_REQUEST",
                bad_get.status_code == 422 and bad_get.json().get("code") == "INVALID_REQUEST",
                f"status={bad_get.status_code} body={bad_get.json()}",
            )
            check(
                "v8.3b 422 details.fields points at domain",
                bad_get.json().get("details", {}).get("fields") == ["domain"],
                str(bad_get.json().get("details")),
            )
            bad_post = client.post(f"/api/v1/workflow-jobs/{job.job_id}/cancel", json={"domain": "bogus"})
            check(
                "v8.3c POST cancel illegal domain -> 422",
                bad_post.status_code == 422 and bad_post.json().get("code") == "INVALID_REQUEST",
                f"status={bad_post.status_code}",
            )
            malformed = client.post(f"/api/v1/workflow-jobs/{job.job_id}/cancel", json={})
            check(
                "v8.3d POST cancel missing domain -> 422 INVALID_REQUEST",
                malformed.status_code == 422 and malformed.json().get("code") == "INVALID_REQUEST",
                f"status={malformed.status_code} body={malformed.json().get('code')}",
            )
            no_domain = client.get(f"/api/v1/workflow-jobs/{job.job_id}")
            check("v8.3e GET without domain -> 422", no_domain.status_code == 422, str(no_domain.status_code))

            # 8⑤ 取消幂等
            queued = store.create(kind="export", frozen_input={})
            first_cancel = client.post(f"/api/v1/workflow-jobs/{queued.job_id}/cancel", json={"domain": "teaching"})
            second_cancel = client.post(f"/api/v1/workflow-jobs/{queued.job_id}/cancel", json={"domain": "teaching"})
            check(
                "v8.5a queued cancel -> cancelled",
                first_cancel.status_code == 200 and first_cancel.json()["state"] == "cancelled",
                f"status={first_cancel.status_code} state={first_cancel.json().get('state')}",
            )
            check(
                "v8.5b cancel is idempotent (second call no-op)",
                second_cancel.status_code == 200
                and second_cancel.json()["state"] == "cancelled"
                and second_cancel.json()["jobId"] == queued.job_id,
                str(second_cancel.json()),
            )
            before_updated = store.get(queued.job_id).updated_at
            third = client.post(f"/api/v1/workflow-jobs/{queued.job_id}/cancel", json={"domain": "teaching"})
            check(
                "v8.5c repeated cancel does not rewrite the row",
                store.get(queued.job_id).updated_at == before_updated and third.status_code == 200,
                f"updated_at={before_updated}",
            )

            running = store.create(kind="export", frozen_input={})
            store.claim(running.job_id)
            running_cancel = client.post(f"/api/v1/workflow-jobs/{running.job_id}/cancel", json={"domain": "teaching"})
            check(
                "v8.5d running cancel keeps running state",
                running_cancel.status_code == 200 and running_cancel.json()["state"] == "running",
                str(running_cancel.json().get("state")),
            )
            check(
                "v8.5e running cancel set the cooperative flag",
                store.get(running.job_id).cancel_requested is True,
                "",
            )

            # 8⑥ 重试语义
            still_queued = store.create(kind="export", frozen_input={})
            for label, target in (("queued", still_queued.job_id), ("running", running.job_id)):
                attempt = client.post(f"/api/v1/workflow-jobs/{target}/retry", json={"domain": "teaching"})
                check(
                    f"v8.6a retry on {label} -> 409 JOB_NOT_RETRYABLE",
                    attempt.status_code == 409 and attempt.json().get("code") == "JOB_NOT_RETRYABLE",
                    f"status={attempt.status_code} code={attempt.json().get('code')}",
                )

            failed = store.create(kind="export", frozen_input={"frozen": True}, model_snapshot={"fingerprint": "fp"})
            lease = store.claim(failed.job_id)
            store.fail_if_current_lease(failed.job_id, lease, code="MODEL_CONFIG_INVALID", message="模型配置失效", retryable=True)
            failed_view = client.get(f"/api/v1/workflow-jobs/{failed.job_id}", params={"domain": "teaching"}).json()
            check(
                "v8.6b failed view carries the error envelope",
                failed_view["state"] == "failed"
                and failed_view["error"]["code"] == "MODEL_CONFIG_INVALID"
                and failed_view["error"]["message"] == "模型配置失效"
                and failed_view["error"]["retryable"] is True,
                str(failed_view.get("error")),
            )
            snapshot_before = store.get(failed.job_id)
            retried = client.post(f"/api/v1/workflow-jobs/{failed.job_id}/retry", json={"domain": "teaching"})
            check(
                "v8.6c terminal retry -> back to queued",
                retried.status_code == 200 and retried.json()["state"] == "queued",
                f"status={retried.status_code} state={retried.json().get('state')}",
            )
            after = store.get(failed.job_id)
            check(
                "v8.6d retry keeps frozen input/model snapshot/attempt",
                after.frozen_input == snapshot_before.frozen_input
                and after.model_snapshot == snapshot_before.model_snapshot
                and after.attempt == snapshot_before.attempt,
                f"attempt={after.attempt}",
            )
            check(
                "v8.6e retried row clears the previous error (r2 口径：queued 视图无 error)",
                after.state == "queued"
                and after.error_code is None
                and after.error is None
                and snapshot_before.error_code == "MODEL_CONFIG_INVALID",
                f"state={after.state} error_code={after.error_code}（retry 同事务清空 error；"
                "r1 曾是 observation，r2 已修）",
            )
            reclaimed = store.claim(failed.job_id)
            check(
                "v8.6f next claim bumps attempt and keeps error empty",
                store.get(failed.job_id).error_code is None
                and store.get(failed.job_id).error is None
                and reclaimed.attempt == snapshot_before.attempt + 1,
                f"attempt={reclaimed.attempt} error={store.get(failed.job_id).error_code}",
            )

            # 8④ 503 未装配
            _, bare = _client(root / "bare", bootstrap=False)
            with bare:
                bare_response = bare.get("/api/v1/workflow-jobs/whatever", params={"domain": "teaching"})
                check(
                    "v8.4a unassembled engine -> 503 SERVICE_UNAVAILABLE (retryable)",
                    bare_response.status_code == 503
                    and bare_response.json().get("code") == "SERVICE_UNAVAILABLE"
                    and bare_response.json().get("retryable") is True,
                    f"status={bare_response.status_code} body={bare_response.json()}",
                )
                bare_post = bare.post("/api/v1/workflow-jobs/whatever/retry", json={"domain": "teaching"})
                check("v8.4b unassembled engine retry -> 503", bare_post.status_code == 503, str(bare_post.status_code))

            engine._stores.pop("question")
            missing_store = client.get("/api/v1/workflow-jobs/whatever", params={"domain": "question"})
            check(
                "v8.4c known domain without a store -> 503 (not fake 404)",
                missing_store.status_code == 503 and missing_store.json().get("code") == "SERVICE_UNAVAILABLE",
                f"status={missing_store.status_code} body={missing_store.json()}",
            )

            # 附加：知识点库域也可用（kind 白名单）
            knowledge_store = engine.store("knowledge")
            knowledge_job = knowledge_store.create(kind="suggestion", frozen_input={})
            knowledge_view = client.get(
                f"/api/v1/workflow-jobs/{knowledge_job.job_id}", params={"domain": "knowledge"}
            )
            check(
                "v8.7 knowledge domain works with its own kind whitelist",
                knowledge_view.status_code == 200 and knowledge_view.json()["domain"] == "knowledge",
                str(knowledge_view.status_code),
            )
            try:
                knowledge_store.create(kind="export", frozen_input={})
                record("v8.8 unknown kind rejected by whitelist", False, "no exception")
            except Exception as exc:  # noqa: BLE001
                check(
                    "v8.8 unknown kind rejected by whitelist",
                    getattr(exc, "code", "") == "INVALID_REQUEST",
                    f"{type(exc).__name__}: {getattr(exc, 'code', exc)}",
                )
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
