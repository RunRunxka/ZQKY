"""题库统一任务引擎（B2 / A7）：organize 经引擎、六态、名额、取消、重启收敛与显式恢复。

覆盖点（任务卡 §6.5 / §9 A7）：
- organize 经 ``job_engine.store("question")`` 建任务 + ``run_job`` 执行：attempt=1、
  契约冻结在维护行里、同步返回终态视图；
- 视图六态 + attempt；``catalog.JOB_STATES`` 含 ``interrupted``（``_job_record`` 接受）；
- 模型名额并发上限（``model_limit=1`` 时第二个模型任务不进执行器）；
- 取消：``queued`` 立即 ``cancelled``、``running`` 批间停（不发布该批）；
- 重启收敛：``running → reconcile → interrupted → 显式 recover → succeeded``；
- 旧语义 checkpoint → ``ORGANIZER_MODEL_RESELECT_REQUIRED``，provider **零调用**；
- 失权/旧 attempt 迟到：租约失效方不能发布任何业务行。

全部使用 ``tmp_path`` 临时库与受控替身（假时钟/短租约）：不触网、不读写正式数据目录。
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from app.contracts.teaching_loop import JOB_STATES
from app.core.exceptions import AppError
from app.repositories.jobs.repository import JobStore
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.question_bank.records import DraftInput, JobRecord
from app.schemas.question_bank import OrganizeRequest
from app.services.jobs.engine import JobEngine
from app.services.question_bank import views
from app.services.question_bank.organizer import (
    ORGANIZE_CONTRACT_VERSION,
    ORGANIZE_INSTRUCTION,
    RESELECT_MODEL_CODE,
    RESELECT_MODEL_MESSAGE,
)
from tests.test_jobs_engine import FakeClock
from tests.test_question_bank import LOCAL_PROFILE, SAMPLE_DOC
from tests.test_question_generation import (
    GenerationHarness,
    GatedProvider,
    _generation_request,
    generation_reply,
)

TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


# --------------------------------------------------------------------------- 工具


def _organize_checkpoint(
    draft: dict, *, profile: str = LOCAL_PROFILE, fingerprint: str
) -> dict[str, Any]:
    """v2 整理契约（含 1 个批次），用于直接造历史行。

    ``fingerprint`` 必须传**任务创建时**配置的真实指纹（生产用
    ``model_runtime.fingerprint_of_handle``）：恢复路径按它核对当前配置（B2-RV04），
    写占位值会被如实判为漂移；夹具不得在恢复时用当前配置重写冻结值。
    """
    block_id = draft["sourceSpans"][0]["blockId"]
    return {
        "contractVersion": ORGANIZE_CONTRACT_VERSION,
        "modelProfileId": profile,
        "modelFingerprint": fingerprint,
        "instruction": ORGANIZE_INSTRUCTION,
        "drafts": [{"draftId": draft["draftId"], "revision": draft["revision"]}],
        "batches": [
            {
                "index": 0,
                "draftId": draft["draftId"],
                "blockIds": [block_id],
                "inputText": f"[块 {block_id}]\n旧文本",
                "charCount": len(block_id) + 8,
            }
        ],
        "nextBatchIndex": 0,
        "suggestionIds": [],
        "failedBatches": [],
    }


def _legacy_checkpoint(draft: dict) -> dict[str, Any]:
    """旧语义 checkpoint：把 profile id 当模型名、缺契约版本与指纹。"""
    block_id = draft["sourceSpans"][0]["blockId"]
    return {
        "modelProfileId": "63b3ffdc-1111-4222-8333-444455556666",
        "resolvedModel": "qwen2.5:7b",
        "instruction": "旧指令",
        "drafts": [{"draftId": draft["draftId"], "revision": draft["revision"]}],
        "batches": [
            {
                "index": 0,
                "draftId": draft["draftId"],
                "blockIds": [block_id],
                "inputText": "[块 x]\n旧文本",
                "charCount": 9,
            }
        ],
        "nextBatchIndex": 0,
        "suggestionIds": [],
        "failedBatches": [],
    }


# --------------------------------------------------- 1 organize 经引擎（终态视图）


def test_organize_runs_through_shared_engine_with_attempt_and_frozen_contract(
    tmp_path: Path,
) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        detail = harness.sample_detail()
        draft = detail["drafts"][0]
        response = harness.client.post(
            f"/api/v1/question-imports/{detail['importId']}/organize",
            json={
                "draftIds": [draft["draftId"]],
                "includeUnassigned": False,
                "modelProfileId": LOCAL_PROFILE,
            },
        )
        assert response.status_code == 200, response.text
        view = response.json()
        assert view["state"] == "succeeded"
        assert view["attempt"] == 1  # 经 JobEngine claim 执行
        assert view["suggestionCount"] == 1
        assert view["failedBatches"] == 0
        assert [(item["batchIndex"], item["code"]) for item in view["failures"]] == []

        record = harness.service.job_record(view["jobId"])
        assert record.domain == "question" and record.kind == "organize"
        assert record.attempt == 1
        # 契约冻结在任务行的 frozen_input；checkpoint 只留进度
        frozen = record.frozen_input
        assert frozen["contractVersion"] == ORGANIZE_CONTRACT_VERSION
        assert frozen["modelProfileId"] == LOCAL_PROFILE
        assert frozen["modelFingerprint"].startswith("sha256:")
        assert record.checkpoint["nextBatchIndex"] == 1
        assert len(record.checkpoint["suggestionIds"]) == 1
        assert record.result == {"suggestionCount": 1, "failedBatches": 0}

        # 公共任务视图（前端观察路径）同源
        job_view = harness.job_view(view["jobId"])
        assert job_view["state"] == "succeeded"
        assert job_view["attempt"] == 1
        assert job_view["result"]["suggestionCount"] == 1

        # 旧 URL 形状不变：GET job 视图 / 旧列表路径仍可用
        fetched = harness.service.get_organize_job(view["jobId"])
        assert fetched.jobId == view["jobId"]
        assert fetched.attempt == 1
        assert harness.catalog.get_job(view["jobId"]) is not None  # 旧目录读取路径兼容
        assert harness.catalog.list_jobs(kind="organize")[0].state == "succeeded"
    finally:
        harness.close()


def test_organize_job_view_accepts_six_states_and_attempt() -> None:
    """视图契约：六态 + attempt 都接受，``interrupted`` 不再被当成损坏。"""
    for state in sorted(JOB_STATES):
        record = JobRecord(
            job_id="job-1",
            kind="organize",
            state=state,
            checkpoint={"failedBatches": [], "suggestionIds": []},
            error_code=None,
            created_at="2026-10-01T00:00:00Z",
            updated_at="2026-10-01T00:00:00Z",
        )
        view = views.organize_job_view(record, suggestions=[], suggestion_count=0)
        assert view.state == state
        assert view.attempt == 0  # 目录记录没有 attempt 列：如实显示 0

    class _EngineRecord:
        job_id = "job-2"
        state = "interrupted"
        attempt = 3
        error_code = "ORGANIZER_MODEL_RESELECT_REQUIRED"
        checkpoint = {"failedBatches": [{"index": 0, "code": "ORGANIZER_INVALID_JSON"}]}

    view = views.organize_job_view(
        _EngineRecord(), suggestions=[], suggestion_count=0
    )
    assert (view.state, view.attempt, view.errorCode) == (
        "interrupted",
        3,
        RESELECT_MODEL_CODE,
    )
    assert view.failedBatches == 1 and view.failures[0].batchIndex == 0


# ------------------------------------------------------- 2 模型名额并发上限


def test_model_slots_limit_generation_jobs(tmp_path: Path) -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        provider = GatedProvider(started, release)
        catalog = QuestionBankCatalog(tmp_path / "question-bank.sqlite3")
        catalog.migrate()
        store = JobStore(
            catalog,
            domain="question",
            table="question_jobs",
            kinds=frozenset({"organize", "generate"}),
        )
        engine = JobEngine({"question": store}, heavy_limit=2, model_limit=1)
        harness = GenerationHarness(tmp_path, with_client=False, provider=provider, job_engine=engine)
        try:
            provider.replies = [generation_reply(), generation_reply()]
            first = await harness.service.create_generation_job(_generation_request([]))
            await asyncio.wait_for(started.wait(), timeout=5)
            second = await harness.service.create_generation_job(_generation_request([]))
            await asyncio.sleep(0.1)
            # 模型名额 = 1：第二个任务已在 queued/running，但不得进入执行器
            assert provider.entered == [0]
            assert engine.store("question").get(second.jobId).state in ("queued", "running")
            release.set()
            await asyncio.sleep(0.3)
            assert len(provider.entered) == 2
            assert engine.store("question").get(first.jobId).state == "succeeded"
            assert engine.store("question").get(second.jobId).state == "succeeded"
        finally:
            await engine.shutdown()
            harness.close()

    asyncio.run(scenario())


# ------------------------------------------------------------------------ 3 取消


def test_cancel_queued_job_is_immediate_and_never_calls_model(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        store = harness.service.job_engine.store("question")
        job = store.create(kind="organize", frozen_input={})
        view = harness.service.cancel_organize_job(job.job_id)
        assert view.state == "cancelled"
        assert harness.service.job_record(job.job_id).state == "cancelled"
        # 已取消的排队任务不会被"执行"顺手复活：不调模型、不写建议
        view_again = asyncio.run(harness.service.run_organize_job(job.job_id))
        assert view_again.state == "cancelled"
        assert harness.provider.calls == []
        assert harness.catalog.list_suggestions(organization_job_id=job.job_id) == []

        # 幂等：重复取消不改状态、不报错
        assert harness.service.cancel_organize_job(job.job_id).state == "cancelled"
    finally:
        harness.close()


def test_cancel_running_organize_stops_between_batches_without_publishing(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        provider = GatedProvider(started, release)
        harness = GenerationHarness(tmp_path, with_client=False, provider=provider)
        try:
            import_detail = harness.service.create_import(
                file_name="sample.md", data=SAMPLE_DOC.encode("utf-8")
            )
            drafts = harness.catalog.list_drafts(import_detail.importId)
            task = asyncio.ensure_future(
                harness.service.organize(
                    import_detail.importId,
                    OrganizeRequest(
                        draftIds=[draft.draft_id for draft in drafts],
                        includeUnassigned=False,
                        modelProfileId=LOCAL_PROFILE,
                    ),
                )
            )
            await asyncio.wait_for(started.wait(), timeout=5)
            job_id = harness.catalog.list_jobs(kind="organize")[0].job_id
            harness.service.cancel_organize_job(job_id)
            release.set()
            view = await asyncio.wait_for(task, timeout=5)
            assert view.state == "cancelled", view
            # 只有第 0 批进入模型；该批未发布（取消优先），后续批次不再调用
            assert len(provider.entered) == 1
            assert harness.catalog.list_suggestions(organization_job_id=job_id) == []
            record = harness.service.job_record(job_id)
            assert record.state == "cancelled"
            assert record.result is None
            assert "suggestionIds" not in record.checkpoint or not record.checkpoint[
                "suggestionIds"
            ]
        finally:
            await harness.service.job_engine.shutdown()
            harness.close()

    asyncio.run(scenario())


# ------------------------------------------------------------ 4 重启收敛 + 显式恢复


def frozen_fingerprint(
    harness: GenerationHarness, *, profile: str = LOCAL_PROFILE, **overrides: Any
) -> str:
    """任务创建时配置的真实指纹（与生产同一函数，RV04 核对口径）。"""
    from app.services.model_runtime import fingerprint_of_handle

    return fingerprint_of_handle(harness.handle(profile, **overrides))


def test_restart_convergence_then_explicit_recover_succeeds(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        detail = harness.sample_detail()
        draft = detail["drafts"][0]
        # 夹具修正（B3/G0 · RV04 范围变更）：冻结指纹取任务创建时配置的真实值，
        # 恢复时按它核对；断言一字未改。
        legacy_like = harness.catalog.create_job(
            kind="organize",
            state="running",
            checkpoint=_organize_checkpoint(
                draft, fingerprint=frozen_fingerprint(harness)
            ),
        )
        store = harness.service.job_engine.store("question")
        # 启动收敛：running → interrupted（不自动重跑模型）
        assert store.reconcile_interrupted() == [legacy_like.job_id]
        interrupted = store.get(legacy_like.job_id)
        assert interrupted.state == "interrupted"
        assert interrupted.attempt == 0
        # 题库目录的旧读取路径同样接受 interrupted（JOB_STATES 已含；不再当损坏行）
        assert harness.catalog.get_job(legacy_like.job_id).state == "interrupted"
        assert harness.provider.calls == []

        # 显式恢复：retry → run_job → 从 checkpoint 续跑
        assert asyncio.run(harness.service.recover_organize_jobs()) == 1
        recovered = harness.service.job_record(legacy_like.job_id)
        assert recovered.state == "succeeded"
        assert recovered.attempt == 1
        assert recovered.result == {"suggestionCount": 1, "failedBatches": 0}
        assert len(harness.provider.calls) == 1
        assert len(harness.catalog.list_suggestions(organization_job_id=legacy_like.job_id)) == 1
        # 幂等：没有可恢复任务时返回 0，不重复调用模型
        assert asyncio.run(harness.service.recover_organize_jobs()) == 0
        assert len(harness.provider.calls) == 1
    finally:
        harness.close()


def test_recover_organize_job_fails_on_frozen_model_drift(tmp_path: Path) -> None:
    """RV04 正确行为回归：创建后同 profile 配置变化 → 恢复明确失败、零调用、零发布。"""
    from app.services.model_runtime import MODEL_CONFIG_DRIFT

    harness = GenerationHarness(tmp_path)
    try:
        detail = harness.sample_detail()
        draft = detail["drafts"][0]
        frozen = frozen_fingerprint(harness)
        row = harness.catalog.create_job(
            kind="organize",
            state="running",
            checkpoint=_organize_checkpoint(draft, fingerprint=frozen),
        )
        store = harness.service.job_engine.store("question")
        assert store.reconcile_interrupted() == [row.job_id]
        # 排队/中断期间同 profile 换了模型：恢复必须拒绝，而不是悄悄用新模型
        harness.resolver.default = harness.handle(LOCAL_PROFILE, model_id="model-B")

        assert asyncio.run(harness.service.recover_organize_jobs()) == 1
        record = harness.service.job_record(row.job_id)
        assert record.state == "failed"
        assert record.error_code == MODEL_CONFIG_DRIFT
        # 零模型调用、零建议、零 checkpoint 推进；冻结指纹不被当前配置重写
        assert harness.provider.calls == []
        assert harness.catalog.list_suggestions(organization_job_id=row.job_id) == []
        assert record.checkpoint["nextBatchIndex"] == 0
        assert record.checkpoint["modelFingerprint"] == frozen
    finally:
        harness.close()


def test_recover_skips_succeeded_and_cancelled_jobs(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        store = harness.service.job_engine.store("question")
        cancelled = store.create(kind="organize", frozen_input={})
        store.request_cancel(cancelled.job_id)
        assert asyncio.run(harness.service.recover_organize_jobs()) == 0
        assert store.get(cancelled.job_id).state == "cancelled"
        assert harness.provider.calls == []
    finally:
        harness.close()


def test_legacy_checkpoint_requires_model_reselection_without_any_provider_call(
    tmp_path: Path,
) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        detail = harness.sample_detail()
        draft = detail["drafts"][0]
        legacy = harness.catalog.create_job(
            kind="organize", state="running", checkpoint=_legacy_checkpoint(draft)
        )
        store = harness.service.job_engine.store("question")
        assert store.reconcile_interrupted() == [legacy.job_id]

        assert asyncio.run(harness.service.recover_organize_jobs()) == 1
        stale = store.get(legacy.job_id)
        assert stale.state == "failed"
        assert stale.error_code == RESELECT_MODEL_CODE
        assert stale.checkpoint["needsModelReselection"] is True
        job_error = stale.checkpoint["jobError"]
        assert job_error["message"] == RESELECT_MODEL_MESSAGE
        # 不猜模型、不伪造指纹：provider 与 resolver 都是零调用
        assert harness.provider.calls == []
        assert harness.resolver.calls == []
        # 旧 checkpoint 里的进度与旧建议一条不动
        assert stale.checkpoint["nextBatchIndex"] == 0
        assert harness.catalog.list_suggestions(organization_job_id=legacy.job_id) == []

        # 显式运行同一条任务也不会被"顺手"执行
        view = asyncio.run(harness.service.run_organize_job(legacy.job_id))
        assert view.state == "failed"
        assert view.errorCode == RESELECT_MODEL_CODE
        assert harness.provider.calls == []
    finally:
        harness.close()


# ------------------------------------------------- 5 失权 / 旧 attempt 迟到


def _create_probe(catalog: QuestionBankCatalog) -> None:
    connection = sqlite3.connect(catalog.db_path)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS publish_probe (id TEXT PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()


def _probe_rows(catalog: QuestionBankCatalog) -> list[str]:
    connection = sqlite3.connect(catalog.db_path)
    try:
        return [
            row[0]
            for row in connection.execute(
                "SELECT id FROM publish_probe ORDER BY id"
            ).fetchall()
        ]
    finally:
        connection.close()


def test_stale_lease_cannot_publish_question_job(tmp_path: Path) -> None:
    """失权方（旧 attempt/旧 token）发布被拒：业务行零写入，新持有者照常发布。"""
    catalog = QuestionBankCatalog(tmp_path / "question-bank.sqlite3")
    catalog.migrate()
    _create_probe(catalog)
    clock = FakeClock()
    store = JobStore(
        catalog,
        domain="question",
        table="question_jobs",
        kinds=frozenset({"organize", "generate"}),
        lease_seconds=3,
        now=clock.now,
    )
    job = store.create(kind="generate", frozen_input={"count": 1})
    first = store.claim(job.job_id)
    assert first.attempt == 1

    # 租约过期 → 第二个持有者接管（旧 attempt 迟到）
    clock.advance(5)
    second = store.claim(job.job_id)
    assert second.attempt == 2

    def publish(conn: Any) -> None:
        conn.execute("INSERT INTO publish_probe (id) VALUES ('late')")

    with pytest.raises(AppError) as lost:
        store.complete(job.job_id, first, result={"late": True}, publish=publish)
    assert lost.value.code == "LEASE_LOST"
    assert _probe_rows(catalog) == []

    def publish_ok(conn: Any) -> None:
        conn.execute("INSERT INTO publish_probe (id) VALUES ('current')")

    done = store.complete(job.job_id, second, result={"late": False}, publish=publish_ok)
    assert done.state == "succeeded"
    assert done.attempt == 2
    assert _probe_rows(catalog) == ["current"]


def test_cancel_request_blocks_late_batch_publish(tmp_path: Path) -> None:
    """取消请求优先于迟到批次：``record_organize_batch`` 在事务内拒绝写入任何建议。"""
    catalog = QuestionBankCatalog(tmp_path / "question-bank.sqlite3")
    catalog.migrate()
    store = JobStore(
        catalog,
        domain="question",
        table="question_jobs",
        kinds=frozenset({"organize"}),
        lease_seconds=30,
    )
    import_id = catalog.create_import(
        owner_id="local-user",
        file_sha256="a" * 64,
        original_blob_id="a" * 64,
        uploaded_file_name="x.md",
        uploaded_bytes=1,
        state="needs_review",
    ).import_id
    draft = catalog.create_drafts(
        import_id,
        [
            DraftInput(
                content={
                    "type": "short_answer",
                    "stemMarkdown": "题干",
                    "options": [],
                    "answer": None,
                    "explanationMarkdown": None,
                    "assetIds": [],
                },
                metadata={"subjectId": "math"},
                source_spans=[],
                extraction_method="rule",
                review_state="needs_review",
            )
        ],
    )[0]
    job = store.create(kind="organize", frozen_input={"drafts": [draft.draft_id]})
    store.claim(job.job_id)
    store.request_cancel(job.job_id)

    job_now, created, failure = catalog.record_organize_batch(
        job.job_id,
        batch_index=0,
        next_batch_index=1,
        draft_id=draft.draft_id,
        base_draft_revision=draft.revision,
        proposed_content={
            "type": "short_answer",
            "stemMarkdown": "迟到的建议",
            "options": [],
            "answer": None,
            "explanationMarkdown": None,
            "assetIds": [],
        },
        source_block_ids=[],
    )
    assert created is None and failure is None
    assert catalog.list_suggestions(organization_job_id=job.job_id) == []
    assert job_now.state == "running"  # 标志已置，终态由引擎收尾
    assert store.get(job.job_id).cancel_requested is True
