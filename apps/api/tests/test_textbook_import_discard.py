"""放弃教材导入草稿（discard）：守卫、幂等、乐观锁、审计保留与 HTTP 路由。

复用 ``test_textbook_ingest`` 的服务层 Harness 与 ``test_textbook_api`` 的 API
Harness；SQLite 与文件都在 pytest ``tmp_path`` 内，不触碰正式 .local-data。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.services.textbook_ingest import DISCARDABLE_IMPORT_STATES, IMPORT_ALREADY_COMMITTED
from tests.test_textbook_api import ApiHarness
from tests.test_textbook_ingest import METADATA, Harness, sample_text


def _needs_review_draft(env: Harness):
    """已确认分类的可编辑草稿（needs_review）。"""
    return env.import_with_metadata(sample_text())


@pytest.fixture()
def env(tmp_path) -> Harness:
    """与 test_textbook_ingest 同款：tmp_path 内建库，内存向量与假 Embedding。"""
    return Harness(tmp_path)


def _failed_draft(env: Harness):
    """解析失败的草稿（failed，原始 blob 保留）。"""
    return env.service.create_import(file_name="broken.pdf", data=b"%PDF-1.4 junk")


# --------------------------------------------------------------------------- 服务层


def test_discard_needs_review_draft_sets_state_and_bumps_revision(env: Harness) -> None:
    draft = _needs_review_draft(env)
    discarded = env.service.discard_import(draft.importId, expected_revision=draft.revision)
    assert discarded.state == "discarded"
    assert discarded.revision == draft.revision + 1
    assert discarded.canCommit is False
    assert discarded.importId == draft.importId
    # 草稿记录、原始 blob、解析产物一律保留（审计）：未提交的产物留在 staging 区
    assert env.catalog.get_import(draft.importId) is not None
    record = env.catalog.get_import(draft.importId)
    assert record is not None and record.uploaded_blob_id
    assert (env.settings.textbooks_root / "staging" / record.uploaded_blob_id).is_file()
    assert record.parsed_artifacts is not None
    artifacts = record.parsed_artifacts
    assert artifacts.get("normalizedBlobId")
    assert (env.settings.textbooks_root / "staging" / str(artifacts["normalizedBlobId"])).is_file()
    assert (env.settings.textbooks_root / "staging" / str(artifacts["sourceMapBlobId"])).is_file()


def test_discard_uploaded_and_failed_drafts_allowed(env: Harness) -> None:
    # uploaded：直接构造（跳过解析后的 needs_review 默认值）
    uploaded = env.catalog.create_import(
        owner_id="local-user",
        uploaded_file_name="raw.md",
        uploaded_bytes=10,
        uploaded_blob_id="blob-raw",
        state="uploaded",
    )
    discarded = env.service.discard_import(uploaded.import_id, expected_revision=uploaded.revision)
    assert discarded.state == "discarded"
    # failed：解析失败草稿同样可放弃
    failed = _failed_draft(env)
    discarded_failed = env.service.discard_import(failed.importId, expected_revision=failed.revision)
    assert discarded_failed.state == "discarded"
    assert discarded_failed.errorCode is None
    assert DISCARDABLE_IMPORT_STATES == frozenset({"uploaded", "needs_review", "failed"})


def test_discard_twice_is_idempotent(env: Harness) -> None:
    draft = _needs_review_draft(env)
    first = env.service.discard_import(draft.importId, expected_revision=draft.revision)
    again = env.service.discard_import(draft.importId, expected_revision=first.revision)
    assert again.state == "discarded"
    assert again.revision == first.revision  # 幂等：不再递增


def test_discard_stale_expected_revision_is_conflict(env: Harness) -> None:
    draft = _needs_review_draft(env)
    with pytest.raises(AppError) as err:
        env.service.discard_import(draft.importId, expected_revision=draft.revision + 5)
    assert err.value.code == "REVISION_CONFLICT"
    assert err.value.status_code == 409
    # 冲突不落写入：状态未变
    assert env.service.get_import_view(draft.importId).state == "needs_review"


def test_discard_ready_draft_is_already_committed_409(env: Harness) -> None:
    draft = _needs_review_draft(env)
    env.commit_and_run(draft, submission_id="submission-discard-ready-1")
    current = env.service.get_import_view(draft.importId)
    assert current.state == "ready"
    with pytest.raises(AppError) as err:
        env.service.discard_import(draft.importId, expected_revision=current.revision)
    assert err.value.code == IMPORT_ALREADY_COMMITTED
    assert err.value.status_code == 409
    # 已入库结果不受影响
    assert env.service.get_import_view(draft.importId).state == "ready"


def test_discard_cancelled_draft_is_not_discardable_409(env: Harness) -> None:
    draft = _needs_review_draft(env)
    job = env.service.commit_import(
        draft.importId,
        expected_revision=draft.revision,
        submission_id="submission-discard-cancelled-1",
        library_ids=[env.library.library_id],
    )
    cancelled = env.service.cancel_job(job.jobId)
    assert cancelled.state == "cancelled"
    current = env.service.get_import_view(draft.importId)
    assert current.state == "cancelled"
    with pytest.raises(AppError) as err:
        env.service.discard_import(draft.importId, expected_revision=current.revision)
    assert err.value.code == "IMPORT_NOT_DISCARDABLE"
    assert err.value.status_code == 409
    assert env.service.get_import_view(draft.importId).state == "cancelled"


def test_discard_missing_import_is_404(env: Harness) -> None:
    with pytest.raises(AppError) as err:
        env.service.discard_import("no-such-import", expected_revision=0)
    assert err.value.code == "IMPORT_NOT_FOUND"
    assert err.value.status_code == 404


def test_discarded_draft_cannot_patch_or_commit(env: Harness) -> None:
    draft = _needs_review_draft(env)
    discarded = env.service.discard_import(draft.importId, expected_revision=draft.revision)
    # patch：discarded 不在可编辑状态集合 → 既有守卫 409 IMPORT_NOT_EDITABLE
    with pytest.raises(AppError) as patch_err:
        env.service.update_import_metadata(
            draft.importId,
            expected_revision=discarded.revision,
            metadata=METADATA,
        )
    assert patch_err.value.code == "IMPORT_NOT_EDITABLE"
    assert patch_err.value.status_code == 409
    # commit：discarded 不是 needs_review → 既有守卫 409 IMPORT_NOT_COMMITTABLE
    with pytest.raises(AppError) as commit_err:
        env.service.commit_import(
            draft.importId,
            expected_revision=discarded.revision,
            submission_id="submission-discard-commit-1",
            library_ids=[env.library.library_id],
        )
    assert commit_err.value.code == "IMPORT_NOT_COMMITTABLE"
    assert commit_err.value.status_code == 409
    # 双保险：没有发生任何书册/修订落库
    assert env.catalog.list_documents() == []


# --------------------------------------------------------------------------- HTTP 路由


def test_discard_route_roundtrip(tmp_path) -> None:
    with ApiHarness(tmp_path) as api:
        response = api.upload(sample_text())
        assert response.status_code == 201, response.text
        draft = response.json()["draft"]

        ok = api.client.post(
            f"/api/v1/textbook-imports/{draft['importId']}/discard",
            json={"expectedRevision": draft["revision"]},
        )
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["state"] == "discarded"
        assert body["revision"] == draft["revision"] + 1

        # 幂等重放
        again = api.client.post(
            f"/api/v1/textbook-imports/{draft['importId']}/discard",
            json={"expectedRevision": body["revision"]},
        )
        assert again.status_code == 200
        assert again.json()["state"] == "discarded"
        assert again.json()["revision"] == body["revision"]

        # 放弃后 patch 既有 409
        patched = api.client.patch(
            f"/api/v1/textbook-imports/{draft['importId']}",
            json={"expectedRevision": body["revision"], "metadata": METADATA},
        )
        assert patched.status_code == 409
        assert patched.json()["code"] == "IMPORT_NOT_EDITABLE"


def test_discard_route_error_envelopes(tmp_path) -> None:
    with ApiHarness(tmp_path) as api:
        response = api.upload(sample_text())
        assert response.status_code == 201, response.text
        draft = response.json()["draft"]

        # 乐观锁冲突 409
        stale = api.client.post(
            f"/api/v1/textbook-imports/{draft['importId']}/discard",
            json={"expectedRevision": draft["revision"] + 3},
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "REVISION_CONFLICT"

        # 不存在 404
        missing = api.client.post(
            "/api/v1/textbook-imports/no-such-import/discard",
            json={"expectedRevision": 0},
        )
        assert missing.status_code == 404
        assert missing.json()["code"] == "IMPORT_NOT_FOUND"

        # 已入库 409 IMPORT_ALREADY_COMMITTED
        library = api.create_library()
        job = api.client.post(
            f"/api/v1/textbook-imports/{draft['importId']}/commit",
            json={
                "expectedRevision": draft["revision"],
                "submissionId": "submission-discard-api-1",
                "libraryIds": [library["libraryId"]],
            },
        )
        assert job.status_code == 200, job.text
        ready = api.client.get(f"/api/v1/textbook-imports/{draft['importId']}")
        assert ready.json()["state"] == "ready"
        committed = api.client.post(
            f"/api/v1/textbook-imports/{draft['importId']}/discard",
            json={"expectedRevision": ready.json()["revision"]},
        )
        assert committed.status_code == 409
        assert committed.json()["code"] == IMPORT_ALREADY_COMMITTED


def test_discard_route_unknown_fields_rejected(tmp_path) -> None:
    with ApiHarness(tmp_path) as api:
        response = api.upload(sample_text())
        assert response.status_code == 201, response.text
        draft = response.json()["draft"]
        bad = api.client.post(
            f"/api/v1/textbook-imports/{draft['importId']}/discard",
            json={"expectedRevision": draft["revision"], "unexpected": True},
        )
        assert bad.status_code == 422


def test_discard_route_service_missing_returns_503(tmp_path) -> None:
    from app.main import create_app
    from tests.test_textbook_api import _settings

    app = create_app(_settings(tmp_path / "data503"), bootstrap_textbooks=False)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.post(
            "/api/v1/textbook-imports/whatever/discard",
            json={"expectedRevision": 0},
        )
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert body["retryable"] is True
