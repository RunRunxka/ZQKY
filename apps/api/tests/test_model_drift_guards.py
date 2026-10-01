"""模型配置漂移守卫（TEACHING-LOOP B3 / G0 · B2-RV04 正确行为回归）。

审查缺陷：整理恢复与 AI 补题按 profile ID 重新解析**当前**配置，却不比对任务创建时
冻结的 ``fingerprint``；同 profile 改模型后，任务仍成功且来源记录旧指纹（实际调用新模型）。

回归断言（反向对照见 ``docs/qa/TEACHING-LOOP-B2-REVIEW-20261001/probes/question_model_probe.py``）：

- 排队期间同 profile 配置变化 → 任务 ``failed`` + ``MODEL_CONFIG_DRIFT``，
  **零模型调用**、零批次/零来源、冻结指纹不被当前配置重写；
- 冻结指纹未变 → 正常执行，来源记录 = 实际执行句柄的 ``fingerprint_of_handle``；
- 旧行没有可核对指纹 → ``MODEL_FINGERPRINT_MISSING``，要求新任务（不静默放行）。

G0-B v2 增量（知识点候选侧，同口径）：

- ``knowledge:suggestion`` 执行器解析模型后核对冻结指纹：漂移 → 409
  ``MODEL_CONFIG_DRIFT``（零调用、不写候选批次）；快照无可核对指纹 → 422
  ``MODEL_FINGERPRINT_MISSING``；解析失败仍保留既有可读错误码
  （``MODEL_PROFILE_NOT_FOUND`` / ``MODEL_NOT_CONFIGURED``）；
- 注入 ``model_config_repo`` + ``secret_store`` 时走共享 ``resolve_frozen_model``
  （不再回落注入 resolver）。

全部使用 ``tmp_path`` 临时四库与受控模型替身：不触网、不读写正式数据目录。
"""

from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path
from typing import Any

import pytest

from app.core.exceptions import AppError
from app.repositories.question_bank.records import DraftRecord, JobRecord
from app.services.model_runtime import (
    MODEL_CONFIG_DRIFT,
    MODEL_FINGERPRINT_MISSING,
    fingerprint_of_handle,
)
from app.services.question_bank import generation
from app.services.question_bank.organizer import (
    ORGANIZE_CONTRACT_VERSION,
    ORGANIZE_INSTRUCTION,
)
from tests.test_question_bank import LOCAL_PROFILE, FakeLLMProvider
from tests.test_question_generation import (
    GatedProvider,
    GenerationHarness,
    _generation_request,
    generation_reply,
)

TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


async def _wait_terminal(store: Any, job_id: str, *, timeout: float = 8.0) -> JobRecord:
    deadline = asyncio.get_running_loop().time() + timeout
    record = store.get(job_id)
    while record.state not in TERMINAL_STATES and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.02)
        record = store.get(job_id)
    assert record.state in TERMINAL_STATES, record.state
    return record


def _organize_contract(
    draft: DraftRecord, *, fingerprint: str, profile: str = LOCAL_PROFILE
) -> dict[str, Any]:
    """B2 形状的整理冻结输入（单批），指纹取任务创建时的真实值。"""
    block_id = str(draft.source_spans[0]["blockId"])
    return {
        "contractVersion": ORGANIZE_CONTRACT_VERSION,
        "modelProfileId": profile,
        "modelFingerprint": fingerprint,
        "instruction": ORGANIZE_INSTRUCTION,
        "drafts": [{"draftId": draft.draft_id, "revision": draft.revision}],
        "batches": [
            {
                "index": 0,
                "draftId": draft.draft_id,
                "blockIds": [block_id],
                "inputText": f"[块 {block_id}]\n原文",
                "charCount": len(block_id) + 8,
            }
        ],
        "nextBatchIndex": 0,
        "suggestionIds": [],
        "failedBatches": [],
    }


# --------------------------------------------------------------------------- 生成


def test_generation_fails_on_drift_while_queued_without_model_call(tmp_path: Path) -> None:
    """排队期间同 profile 改模型：failed/MODEL_CONFIG_DRIFT，零调用、零发布、指纹不重写。"""

    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        holder_provider = GatedProvider(started, release)
        observed = FakeLLMProvider()
        harness = GenerationHarness(
            tmp_path, with_client=False, provider=holder_provider
        )
        try:
            store = harness.service.job_engine.store("question")
            # ① 用一条阻塞中的补题任务占住唯一模型名额：目标任务只能排队
            holder = await harness.service.create_generation_job(_generation_request([]))
            await asyncio.wait_for(started.wait(), timeout=5)

            # ② 目标任务：创建时冻结 model-A 的指纹
            handle_a = harness.handle(LOCAL_PROFILE, model_id="model-A", provider=observed)
            harness.resolver.default = handle_a
            target = await harness.service.create_generation_job(_generation_request([]))
            frozen = generation.build_model_snapshot(handle_a)["fingerprint"]

            # ③ 排队期间同 profile 换成 model-B，再放行
            harness.resolver.default = harness.handle(
                LOCAL_PROFILE, model_id="model-B", provider=observed
            )
            release.set()
            record = await _wait_terminal(store, target.jobId)
            await _wait_terminal(store, holder.jobId)

            assert record.state == "failed", record.state
            assert record.error_code == MODEL_CONFIG_DRIFT
            # 漂移在模型调用前失败：执行器没有发过任何上游请求
            assert observed.calls == []
            # 冻结指纹与冻结输入不被当前配置重写
            assert record.model_snapshot["fingerprint"] == frozen
            assert record.frozen_input["modelProfileId"] == LOCAL_PROFILE
            # 零发布：没有批次、没有草稿、没有来源
            assert harness.row_count("question_imports") == 0
            assert harness.row_count("question_drafts") == 0
            assert harness.row_count("question_import_provenance") == 0
        finally:
            release.set()
            await harness.service.job_engine.shutdown()
            harness.close()

    asyncio.run(scenario())


def test_generation_records_actual_fingerprint_when_unchanged(tmp_path: Path) -> None:
    """指纹未变：正常执行，来源记录 = 实际执行句柄的指纹（执行与来源一致）。"""
    harness = GenerationHarness(tmp_path)
    try:
        handle = harness.handle(LOCAL_PROFILE)
        harness.resolver.default = handle
        harness.provider.replies = [generation_reply()]
        view = harness.run_generation()
        assert view["state"] == "succeeded", view

        expected = generation.build_model_snapshot(handle)["fingerprint"]
        assert expected == fingerprint_of_handle(handle)
        record = harness.service.job_record(view["jobId"])
        assert record.model_snapshot["fingerprint"] == expected
        import_id = harness.generation_view(view["jobId"])["importId"]
        assert harness.provenance(import_id).model_snapshot["fingerprint"] == expected
        assert len(harness.provider.calls) == 1
    finally:
        harness.close()


def test_generation_without_frozen_fingerprint_is_rejected(tmp_path: Path) -> None:
    """旧任务行没有可核对指纹 → MODEL_FINGERPRINT_MISSING，零调用、不静默放行。"""
    harness = GenerationHarness(tmp_path)
    try:
        observed = FakeLLMProvider()
        harness.resolver.default = harness.handle(LOCAL_PROFILE, provider=observed)
        store = harness.service.job_engine.store("question")
        job = store.create(
            kind="generate",
            frozen_input=generation.build_frozen_input(
                model_profile_id=LOCAL_PROFILE,
                subject_id="math",
                knowledge=[],
                question_types=["short_answer"],
                difficulty="medium",
                count=1,
                instructions="",
                materials=[],
                owner_id=harness.service.owner_id,
            ),
            model_snapshot={"profileId": LOCAL_PROFILE},  # 旧行：没有 fingerprint
        )
        view = asyncio.run(harness.service.run_generation_job(job.job_id))
        assert view.state == "failed"
        assert view.errorCode == MODEL_FINGERPRINT_MISSING
        assert observed.calls == []
        assert harness.row_count("question_imports") == 0
        assert harness.row_count("question_import_provenance") == 0
    finally:
        harness.close()


# --------------------------------------------------------------------------- 整理


def test_organize_recovery_rejects_drift_and_writes_nothing(tmp_path: Path) -> None:
    """恢复按冻结指纹核对；同 profile 改模型 → failed，零调用、零建议、进度不动。"""
    harness = GenerationHarness(tmp_path)
    try:
        detail = harness.sample_detail()
        draft = harness.catalog.get_draft(detail["drafts"][0]["draftId"])
        assert draft is not None

        observed = FakeLLMProvider()
        handle_a = harness.handle(LOCAL_PROFILE, model_id="model-A", provider=observed)
        frozen = fingerprint_of_handle(handle_a)
        store = harness.service.job_engine.store("question")
        job = store.create(
            kind="organize",
            frozen_input=_organize_contract(draft, fingerprint=frozen),
            model_snapshot={"profileId": LOCAL_PROFILE, "fingerprint": frozen},
        )
        # 排队/中断期间同 profile 换成 model-B：恢复必须拒绝
        harness.resolver.default = harness.handle(
            LOCAL_PROFILE, model_id="model-B", provider=observed
        )

        view = asyncio.run(harness.service.run_organize_job(job.job_id))
        assert view.state == "failed"
        record = harness.service.job_record(job.job_id)
        assert record.error_code == MODEL_CONFIG_DRIFT
        assert observed.calls == []
        assert harness.catalog.list_suggestions(organization_job_id=job.job_id) == []
        assert record.checkpoint.get("nextBatchIndex", 0) == 0
        assert record.frozen_input["modelFingerprint"] == frozen  # 不重写冻结值
    finally:
        harness.close()


def test_organize_recovery_succeeds_when_fingerprint_unchanged(tmp_path: Path) -> None:
    """指纹未变：恢复照常执行（正常路径不受守卫影响，来源与执行同一模型）。"""
    harness = GenerationHarness(tmp_path)
    try:
        detail = harness.sample_detail()
        draft = harness.catalog.get_draft(detail["drafts"][0]["draftId"])
        assert draft is not None

        observed = FakeLLMProvider()
        handle = harness.handle(LOCAL_PROFILE, provider=observed)
        frozen = fingerprint_of_handle(handle)
        store = harness.service.job_engine.store("question")
        job = store.create(
            kind="organize",
            frozen_input=_organize_contract(draft, fingerprint=frozen),
            model_snapshot={"profileId": LOCAL_PROFILE, "fingerprint": frozen},
        )
        harness.resolver.default = harness.handle(LOCAL_PROFILE, provider=observed)

        view = asyncio.run(harness.service.run_organize_job(job.job_id))
        assert view.state == "succeeded", view
        assert len(observed.calls) == 1
        assert len(harness.catalog.list_suggestions(organization_job_id=job.job_id)) == 1
        record = harness.service.job_record(job.job_id)
        assert record.model_snapshot["fingerprint"] == frozen
    finally:
        harness.close()


# ---------------------------------------------------------------------- 知识点候选


async def _wait_knowledge_terminal(store: Any, job_id: str, *, timeout: float = 8.0) -> JobRecord:
    deadline = asyncio.get_running_loop().time() + timeout
    record = store.get(job_id)
    while record.state not in TERMINAL_STATES and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.02)
        record = store.get(job_id)
    assert record.state in TERMINAL_STATES, record.state
    return record


def test_knowledge_suggestion_fails_on_drift_without_model_call_or_batch(tmp_path: Path) -> None:
    """知识点候选：排队期间同 profile 改模型 → failed/MODEL_CONFIG_DRIFT，零调用、零批次。

    与题库同一口径（解析后核对 ``fingerprint_of_handle``）：漂移在模型调用前停止，
    不登记候选批次、不写草稿行，冻结快照原样保留。
    """
    from app.contracts.knowledge import KnowledgeSuggestionRequest
    from tests.test_knowledge_suggestions import (
        FakeProvider,
        FakeResolver,
        make_handle,
        make_harness,
    )

    async def scenario() -> None:
        observed = FakeProvider()
        resolver = FakeResolver({LOCAL_PROFILE: make_handle(provider=observed)})
        harness = make_harness(tmp_path, model_resolver=resolver, with_client=False)
        engine = harness.service.job_engine
        assert engine is not None, "知识点任务引擎未装配"
        engine._ensure_primitives()  # noqa: SLF001 - 占位名额用（与审查探针同一手法）
        assert engine._model is not None  # noqa: SLF001
        await engine._model.acquire()  # noqa: SLF001 - 任务保持 queued
        try:
            handle_a = make_handle(provider=observed)
            resolver.profiles[LOCAL_PROFILE] = handle_a
            view = await harness.service.create_suggestion_job(
                KnowledgeSuggestionRequest.model_validate(harness.payload())
            )
            record = engine.store("knowledge").get(view.job_id)
            frozen = record.model_snapshot["fingerprint"]
            assert frozen == fingerprint_of_handle(handle_a)
            assert len(observed.calls) == 0  # 还没轮到模型（名额被占）

            # 排队期间同 profile 换成 model-B，再放行名额
            resolver.profiles[LOCAL_PROFILE] = dataclasses.replace(
                handle_a, model_id="model-B"
            )
        finally:
            engine._model.release()  # noqa: SLF001

        record = await _wait_knowledge_terminal(engine.store("knowledge"), view.job_id)
        assert record.state == "failed", record.state
        assert record.error_code == MODEL_CONFIG_DRIFT
        # 漂移在模型调用前失败：零上游请求、零候选批次
        assert observed.calls == []
        assert harness.knowledge_count("knowledge_imports") == 0
        assert harness.knowledge_count("knowledge_import_rows") == 0
        # 冻结快照不被当前配置重写
        assert record.model_snapshot["fingerprint"] == frozen
        assert record.frozen_input["modelProfileId"] == LOCAL_PROFILE

    asyncio.run(scenario())


def test_knowledge_suggestion_keeps_resolution_error_codes_and_blocks_missing_fingerprint(
    tmp_path: Path,
) -> None:
    """既有可读错误码保留（解析先于核对）；无可核对指纹 → 422，不静默放行。"""
    from tests.test_knowledge_suggestions import (
        FakeProvider,
        FakeResolver,
        make_handle,
        make_harness,
    )

    # ① 解析失败（配置不存在）：仍报 MODEL_PROFILE_NOT_FOUND，而不是"缺指纹"
    harness = make_harness(
        tmp_path / "missing",
        resolver_error=AppError(
            "模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404
        ),
    )
    try:
        job = harness.run_job(harness.payload())
        assert job["state"] == "failed"
        assert job["error"]["code"] == "MODEL_PROFILE_NOT_FOUND"
        assert harness.knowledge_count("knowledge_imports") == 0
    finally:
        harness.close()

    # ② 快照没有指纹（创建时解析失败、行已存在）：解析成功也必须 422 停下
    harness = make_harness(tmp_path / "legacy")
    try:
        observed = FakeProvider()
        harness.service.model_resolver = FakeResolver(
            {LOCAL_PROFILE: make_handle(provider=observed)}
        )
        store = harness.service.job_engine.store("knowledge")
        job = store.create(
            kind="suggestion",
            frozen_input={
                "contractVersion": 2,
                "subjectId": "math",
                "modelProfileId": LOCAL_PROFILE,
                "allowedKnowledgePointIds": [],
                "evidenceIds": ["material-1"],
                "materials": [{"id": "material-1", "text": "证据文本"}],
                "textbookEvidence": [],
                "instructions": "",
            },
            model_snapshot={"profileId": LOCAL_PROFILE},  # 旧行：没有 fingerprint
        )
        record = asyncio.run(
            harness.service.job_engine.run_job(
                "knowledge", job.job_id, harness.service._suggestion_executor, uses_model=True
            )
        )
        assert record.state == "failed"
        assert record.error_code == MODEL_FINGERPRINT_MISSING
        assert observed.calls == []
        assert harness.knowledge_count("knowledge_imports") == 0
    finally:
        harness.close()


def test_knowledge_service_uses_shared_frozen_resolver_when_deps_injected(tmp_path: Path) -> None:
    """注入 model_config_repo/secret_store 后核对走共享 resolve_frozen_model（不再回落 resolver）。"""
    from app.services import model_runtime
    from app.services.knowledge.service import build_knowledge_service
    from tests.test_knowledge_suggestions import FakeResolver, make_handle, make_harness

    harness = make_harness(tmp_path, with_client=False)
    try:
        handle = make_handle()
        good = fingerprint_of_handle(handle)
        calls: list[str] = []

        def fake_resolve_chat_model(repo, secrets, profile_id, *, auth_service=None, purpose="chat"):
            calls.append(profile_id)
            return handle

        original = model_runtime.resolve_chat_model
        model_runtime.resolve_chat_model = fake_resolve_chat_model
        try:
            service = build_knowledge_service(
                harness.catalog,
                asset_store=harness.assets,
                file_assets=harness.file_assets,
                evidence=None,
                coordinator=harness.coordinator,
                # 注入路径生效时这个解析器不得被调用
                model_resolver=FakeResolver(error=AssertionError("不应回落到注入 resolver")),
                job_engine=harness.job_engine,
                model_config_repo=object(),
                secret_store=object(),
                model_auth_service=None,
            )
            resolved = asyncio.run(
                service._resolve_frozen_handle(  # noqa: SLF001 - 注入路径断言
                    {"profileId": LOCAL_PROFILE, "fingerprint": good}
                )
            )
            assert resolved is handle
            assert calls == [LOCAL_PROFILE]

            with pytest.raises(AppError) as drift:
                asyncio.run(
                    service._resolve_frozen_handle(  # noqa: SLF001
                        {"profileId": LOCAL_PROFILE, "fingerprint": "sha256:deadbeef"}
                    )
                )
            assert drift.value.code == MODEL_CONFIG_DRIFT
            assert calls == [LOCAL_PROFILE, LOCAL_PROFILE]  # 漂移也在调用前判定

            with pytest.raises(AppError) as missing:
                asyncio.run(
                    service._resolve_frozen_handle(  # noqa: SLF001
                        {"profileId": LOCAL_PROFILE}
                    )
                )
            assert missing.value.code == MODEL_FINGERPRINT_MISSING
        finally:
            model_runtime.resolve_chat_model = original
    finally:
        harness.close()
