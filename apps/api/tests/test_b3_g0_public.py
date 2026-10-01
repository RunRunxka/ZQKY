"""G0 公共修复测试（TEACHING-LOOP B3 / G0 · CTRL 归口）。

覆盖：①发布事务失败 → 用原 JobLease 在新短事务收敛 failed（无永久 running、零业务残留）；
②取消优先 → 收敛 cancelled；③失权零写入（不覆盖新持有者）；
④`resolve_frozen_model` 缺指纹 422 / 漂移 409 / 一致放行；⑤知识点跨库引用核验（存在/归档/学科）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.repositories.jobs.repository import JobStore
from app.repositories.teaching.catalog import TeachingCatalog
from app.services.jobs.engine import JobEngine, JobContext, JobOutcome
from app.services.knowledge_refs import (
    KnowledgeReference,
    require_active_knowledge_references,
)
from app.services.model_runtime import (
    MODEL_CONFIG_DRIFT,
    MODEL_FINGERPRINT_MISSING,
    fingerprint_of_handle,
    resolve_frozen_model,
)

PUBLISH_DOMAIN = "teaching"


@pytest.fixture()
def store(tmp_path: Path) -> JobStore:
    catalog = TeachingCatalog(tmp_path / "teaching.sqlite3")
    catalog.migrate()
    return JobStore(catalog, domain=PUBLISH_DOMAIN, table="workflow_jobs", kinds=frozenset({"export"}))


def _engine(store: JobStore) -> JobEngine:
    return JobEngine({PUBLISH_DOMAIN: store})


def _executor_raising_in_publish(error: BaseException):
    async def executor(job, ctx: JobContext) -> JobOutcome:
        def publish(conn):
            raise error

        return JobOutcome(result={"ok": True}, publish=publish)

    return executor


def test_publish_failure_converges_failed_with_original_lease(store: JobStore) -> None:
    record = store.create(kind="export", frozen_input={"variant": "teacher"})
    engine = _engine(store)

    async def run():
        return await engine.run_job(PUBLISH_DOMAIN, record.job_id, _executor_raising_in_publish(RuntimeError("boom")))

    final = asyncio.run(run())
    assert final.state == "failed"
    assert final.error_code == "JOB_FAILED"
    assert final.error and final.error.get("message")
    assert final.lease_token is None and final.finished_at is not None
    # 租约确实释放：可再次 claim（retry 后）
    store.retry(record.job_id)
    lease = store.claim(record.job_id)
    assert lease.attempt == 2


def test_publish_failure_with_domain_app_error_keeps_code(store: JobStore) -> None:
    record = store.create(kind="export", frozen_input={})
    engine = _engine(store)
    domain_error = AppError("题目关联已失效。", code="KNOWLEDGE_REFERENCE_INVALID", status_code=422)

    async def run():
        return await engine.run_job(
            PUBLISH_DOMAIN, record.job_id, _executor_raising_in_publish(domain_error)
        )

    final = asyncio.run(run())
    assert final.state == "failed"
    assert final.error_code == "KNOWLEDGE_REFERENCE_INVALID"


def test_publish_failure_after_cancel_request_converges_cancelled(store: JobStore) -> None:
    record = store.create(kind="export", frozen_input={})
    engine = _engine(store)

    async def run():
        store.request_cancel(record.job_id)
        return await engine.run_job(
            PUBLISH_DOMAIN, record.job_id, _executor_raising_in_publish(RuntimeError("boom"))
        )

    final = asyncio.run(run())
    assert final.state == "cancelled"
    assert final.lease_token is None


def test_publish_failure_after_lease_loss_writes_nothing(store: JobStore) -> None:
    """失权（被接管）后，旧租约的失败收敛必须零写入、不覆盖新持有者。"""
    record = store.create(kind="export", frozen_input={})
    stale = store.claim(record.job_id)  # attempt=1
    # 手工让租约过期，再由新尝试接管（仓储级故障注入）
    with store._catalog.write_transaction() as conn:  # noqa: SLF001 - 测试注入
        conn.execute(
            "UPDATE workflow_jobs SET lease_expires_at = '2000-01-01T00:00:00Z' WHERE id = ?",
            (record.job_id,),
        )
    fresh = store.claim(record.job_id)  # attempt=2 接管
    assert fresh.attempt == 2

    result = store.fail_if_current_lease(
        record.job_id, stale, code="JOB_FAILED", message="旧执行者迟到失败"
    )
    # 新持有者不被旧租约覆盖
    assert result.attempt == 2
    assert result.state == "running"
    assert result.error_code is None
    assert result.lease_token == fresh.token


def test_resolve_frozen_model_guards() -> None:
    class _Repo:
        pass

    class _Secrets:
        pass

    def _resolver(*args, **kwargs):  # pragma: no cover - 不应被调用（缺指纹时先失败）
        raise AssertionError("缺指纹时不得解析模型")

    from app.services import model_runtime

    original = model_runtime.resolve_chat_model
    calls: list[str] = []

    class _Handle:
        profile_id = "p1"
        model_id = "m1"
        config = type("C", (), {"protocol": "openai_chat", "baseUrl": "http://127.0.0.1:11434", "apiFormat": "auto"})()

    def fake_resolve(repo, secrets, profile_id, *, auth_service=None, purpose="chat"):
        calls.append(profile_id)
        return _Handle()

    model_runtime.resolve_chat_model = fake_resolve
    try:
        with pytest.raises(AppError) as missing:
            resolve_frozen_model(_Repo(), _Secrets(), {"profileId": "p1"})
        assert missing.value.code == MODEL_FINGERPRINT_MISSING
        assert calls == []

        good = fingerprint_of_handle(_Handle())
        handle = resolve_frozen_model(
            _Repo(), _Secrets(), {"profileId": "p1", "fingerprint": good}
        )
        assert handle.profile_id == "p1" and calls == ["p1"]

        with pytest.raises(AppError) as drift:
            resolve_frozen_model(
                _Repo(), _Secrets(), {"profileId": "p1", "fingerprint": "sha256:deadbeef"}
            )
        assert drift.value.code == MODEL_CONFIG_DRIFT
    finally:
        model_runtime.resolve_chat_model = original


def test_require_active_knowledge_references(tmp_path: Path) -> None:
    from app.repositories.knowledge.catalog import KnowledgeCatalog
    from app.core.sqlite import transaction, now_iso

    catalog = KnowledgeCatalog(tmp_path / "knowledge.sqlite3")
    catalog.migrate()
    with catalog.write_transaction() as conn:
        conn.execute(
            "INSERT INTO subjects (id, code, name) VALUES ('math','math','数学')"
        )
        conn.execute(
            "INSERT INTO knowledge_points (id, subject_id, code, status, current_revision_id) "
            "VALUES ('kp1','math','M1','active','kr1')"
        )
        conn.execute(
            "INSERT INTO knowledge_points (id, subject_id, code, status, current_revision_id) "
            "VALUES ('kp2','math','M2','archived','kr2')"
        )
        conn.execute(
            "INSERT INTO knowledge_point_revisions (id, knowledge_point_id, version, name) "
            "VALUES ('kr1','kp1',1,'函数单调性')"
        )
        conn.execute(
            "INSERT INTO knowledge_point_revisions (id, knowledge_point_id, version, name) "
            "VALUES ('kr2','kp2',1,'已归档点')"
        )
    snapshots = require_active_knowledge_references(
        catalog,
        [KnowledgeReference(knowledge_point_id="kp1", knowledge_revision_id="kr1")],
        expected_subject_id="math",
    )
    assert snapshots["kp1"].name == "函数单调性" and snapshots["kp1"].version == 1

    with pytest.raises(AppError) as missing:
        require_active_knowledge_references(
            catalog, [KnowledgeReference(knowledge_point_id="nope", knowledge_revision_id="krX")]
        )
    assert missing.value.code == "KNOWLEDGE_REFERENCE_INVALID"

    with pytest.raises(AppError) as archived:
        require_active_knowledge_references(
            catalog, [KnowledgeReference(knowledge_point_id="kp2", knowledge_revision_id="kr2")]
        )
    assert archived.value.code == "KNOWLEDGE_ARCHIVED"

    with pytest.raises(AppError) as subject:
        require_active_knowledge_references(
            catalog,
            [KnowledgeReference(knowledge_point_id="kp1", knowledge_revision_id="kr1")],
            expected_subject_id="chinese",
        )
    assert subject.value.code == "KNOWLEDGE_REFERENCE_INVALID"

    with pytest.raises(AppError) as wrong_revision:
        require_active_knowledge_references(
            catalog, [KnowledgeReference(knowledge_point_id="kp1", knowledge_revision_id="kr2")]
        )
    assert wrong_revision.value.code == "KNOWLEDGE_REFERENCE_INVALID"
