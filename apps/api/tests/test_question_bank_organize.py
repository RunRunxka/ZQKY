"""题库 AI 整理（RAG-QUALITY v1.1）：当前聊天模型、任务冻结、恢复、错误分类与预算。

模型语义：``OrganizeRequest.modelProfileId`` 是**点击时的聊天模型 profile id**，本地或云端
一视同仁；解析只经注入的 ``model_resolver``。全部替身，不连真实云端/本机模型；
断点恢复只依赖 ``question_jobs.checkpoint_json``（contractVersion=2）。
"""

from __future__ import annotations

import inspect
import json
import threading
from pathlib import Path
from typing import Any, Sequence

import pytest

from app.api.v1 import question_bank as question_bank_route
from app.core.exceptions import AppError
from app.providers.llm.base import FINISH_LENGTH, LLMResponse, ProviderError
from app.repositories.question_bank.records import SourceBlockInput, SuggestionInput
from app.schemas.model_config import ModelProtocol
from app.schemas.question_bank import DraftPatchRequest, OrganizeRequest, SuggestionApplyRequest
from app.services.question_bank import views
from app.services.question_bank.organizer import (
    MAX_BATCH_INPUT_CHARS,
    MAX_OUTPUT_TOKENS,
    ORGANIZE_CONTRACT_VERSION,
    ORGANIZE_INSTRUCTION,
    RESELECT_MODEL_CODE,
    pack_batches,
    render_block,
)
from app.services.question_bank.service import QuestionBankService
from tests.test_question_bank import (
    CLOUD_PROFILE,
    FAKE_API_KEY,
    LOCAL_PROFILE,
    FakeLLMProvider,
    FakeResolver,
    Harness,
    block_ids_of,
    make_handle,
    open_harness,
    organize_reply,
)


@pytest.fixture()
def harness(tmp_path: Path):
    instance = open_harness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def organize(harness: Harness, import_id: str, **overrides):
    body = {
        "draftIds": overrides.pop("draftIds", []),
        "includeUnassigned": overrides.pop("includeUnassigned", False),
        "modelProfileId": overrides.pop("modelProfileId", LOCAL_PROFILE),
    }
    assert not overrides, overrides
    return harness.client.post(f"/api/v1/question-imports/{import_id}/organize", json=body)


def organize_body(draft_ids: Sequence[str], *, profile: str = LOCAL_PROFILE) -> OrganizeRequest:
    return OrganizeRequest(
        draftIds=list(draft_ids), includeUnassigned=False, modelProfileId=profile
    )


def job_records(harness: Harness):
    return harness.catalog.list_jobs(kind="organize")


def running_job(harness: Harness):
    jobs = [job for job in job_records(harness) if job.state == "running"]
    assert len(jobs) == 1, [job.state for job in job_records(harness)]
    return jobs[0]


def draft_by_id(harness: Harness, import_id: str, draft_id: str) -> dict:
    detail = harness.import_detail(import_id)
    return [item for item in detail["drafts"] if item["draftId"] == draft_id][0]


def crash_on(batch_index: int):
    """模型调用在第 N 批模拟进程崩溃（其余批次正常返回）。"""

    def handler(call):
        if call.index == batch_index:
            raise RuntimeError("模拟进程崩溃")
        return organize_reply(block_ids_of(call.input_text))

    return handler


# ------------------------------------------------------- 1/2 本地与云端 profile


@pytest.mark.parametrize(
    "protocol",
    [
        ModelProtocol.openai_chat,
        ModelProtocol.openai_responses,
        ModelProtocol.anthropic_messages,
    ],
)
def test_organize_uses_current_chat_profile_and_freezes_it(
    harness: Harness, protocol: ModelProtocol
) -> None:
    """① 本地 profile：用该 profile 的 provider 调用一次；checkpoint 记 profileId，不是模型名。"""
    harness.resolver.profiles[LOCAL_PROFILE] = make_handle(
        LOCAL_PROFILE,
        protocol=protocol,
        api_format=f"api_format_{protocol.value}",
        provider=harness.provider,
    )
    detail = harness.sample_detail()
    draft = detail["drafts"][0]

    response = organize(harness, detail["importId"], draftIds=[draft["draftId"]])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "succeeded"
    assert view["suggestionCount"] == 1

    # 该 profile 的 provider 恰好被调用一次（单草稿单批）
    assert len(harness.provider.calls) == 1
    call = harness.provider.calls[0]
    assert call.model_profile_id == LOCAL_PROFILE
    assert call.max_output_tokens == MAX_OUTPUT_TOKENS
    assert len(call.input_text) <= MAX_BATCH_INPUT_CHARS
    assert ORGANIZE_INSTRUCTION in call.messages[0].content
    assert harness.resolver.calls == [LOCAL_PROFILE]

    checkpoint = harness.catalog.get_job(view["jobId"]).checkpoint
    assert checkpoint["contractVersion"] == ORGANIZE_CONTRACT_VERSION
    assert checkpoint["modelProfileId"] == LOCAL_PROFILE
    assert checkpoint["modelFingerprint"].startswith("sha256:")
    # 不写模型名、不写凭证、不写完整配置
    assert "resolvedModel" not in checkpoint
    serialized = json.dumps(checkpoint, ensure_ascii=False)
    assert "qwen2.5:7b" not in serialized
    assert FAKE_API_KEY not in serialized
    assert "apiKey" not in serialized


def test_organize_uses_cloud_profile_like_local(harness: Harness) -> None:
    """② 云端 profile：不同 protocol / modelId / baseUrl 同样走通，本地/云端一视同仁。"""
    cloud_provider = FakeLLMProvider()
    harness.resolver.profiles[CLOUD_PROFILE] = make_handle(
        CLOUD_PROFILE,
        model_id="gpt-5.2",
        protocol=ModelProtocol.anthropic_messages,
        base_url="https://api.example.com/v1",
        api_format="anthropic",
        provider=cloud_provider,
    )
    detail = harness.sample_detail()
    response = organize(
        harness, detail["importId"], draftIds=[detail["drafts"][0]["draftId"]],
        modelProfileId=CLOUD_PROFILE,
    )
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "succeeded"
    assert len(cloud_provider.calls) == 1
    assert cloud_provider.calls[0].model_id == "gpt-5.2"
    assert cloud_provider.calls[0].model_profile_id == CLOUD_PROFILE
    assert harness.provider.calls == []  # 本地 profile 的 provider 一次都没调
    checkpoint = harness.catalog.get_job(view["jobId"]).checkpoint
    assert checkpoint["modelProfileId"] == CLOUD_PROFILE
    assert "gpt-5.2" not in json.dumps(checkpoint, ensure_ascii=False)


# ---------------------------------------------- 3/4 resolver 失败与未装配装配


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (
            AppError("模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404),
            404,
            "MODEL_PROFILE_NOT_FOUND",
        ),
        (
            AppError(
                "该连接未保存凭证，请先在设置中填写 API Key。",
                code="MODEL_NOT_CONFIGURED",
                status_code=400,
            ),
            400,
            "MODEL_NOT_CONFIGURED",
        ),
        (
            AppError(
                "该模型配置用途为 embedding，不能用于chat。",
                code="MODEL_PURPOSE_MISMATCH",
                status_code=422,
            ),
            422,
            "MODEL_PURPOSE_MISMATCH",
        ),
    ],
)
def test_profile_unavailable_fails_before_job(
    harness: Harness, error: AppError, status_code: int, code: str
) -> None:
    """③ profile 不存在/不可调用：HTTP 错误码 + 可读原因；0 次 provider 调用、0 条任务行。"""
    detail = harness.sample_detail()
    harness.resolver.error = error

    response = organize(harness, detail["importId"], draftIds=[detail["drafts"][0]["draftId"]])
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["code"] == code
    assert body["message"]  # 可读原因
    assert harness.provider.calls == []
    assert job_records(harness) == []
    # 草稿与原文一条不动
    assert harness.import_detail(detail["importId"])["drafts"] == detail["drafts"]


def test_missing_model_resolver_is_503(tmp_path: Path) -> None:
    """④ modelResolver 未注入 → 503 SERVICE_UNAVAILABLE，不建任务、不发上游。"""
    instance = open_harness(tmp_path, model_resolver=None)
    try:
        assert instance.service.model_resolver is None
        detail = instance.sample_detail()
        response = organize(instance, detail["importId"])
        assert response.status_code == 503, response.text
        body = response.json()
        assert body["code"] == "SERVICE_UNAVAILABLE"
        assert body["retryable"] is True
        assert "model_resolver" in body["message"]
        assert instance.provider.calls == []
        assert job_records(instance) == []
    finally:
        instance.close()


def test_organize_http_contract_requires_model_profile_id(harness: Harness) -> None:
    """HTTP 契约：modelProfileId 必填且非空（不再有“省略即用默认模型”的旧语义）。"""
    detail = harness.sample_detail()
    for payload in (
        {"draftIds": []},
        {"draftIds": [], "modelProfileId": ""},
    ):
        response = harness.client.post(
            f"/api/v1/question-imports/{detail['importId']}/organize", json=payload
        )
        assert response.status_code == 422, response.text
        assert harness.provider.calls == []
        assert job_records(harness) == []


async def test_recover_without_resolver_fails_job_honestly(harness: Harness) -> None:
    """恢复路径同样不假成功：未装配 model_resolver → 任务按失败落库并给可读原因。"""
    detail = harness.sample_detail()
    draft = detail["drafts"][0]
    job = harness.catalog.create_job(
        kind="organize",
        state="queued",
        checkpoint={
            "contractVersion": ORGANIZE_CONTRACT_VERSION,
            "modelProfileId": LOCAL_PROFILE,
            "modelFingerprint": "sha256:" + "1" * 64,
            "instruction": ORGANIZE_INSTRUCTION,
            "drafts": [{"draftId": draft["draftId"], "revision": draft["revision"]}],
            "batches": [
                {
                    "index": 0,
                    "draftId": draft["draftId"],
                    "blockIds": [draft["sourceSpans"][0]["blockId"]],
                    "inputText": "[块 x]\n旧文本",
                    "charCount": 9,
                }
            ],
            "nextBatchIndex": 0,
            "suggestionIds": [],
            "failedBatches": [],
        },
    )
    harness.service.model_resolver = None
    assert await harness.service.recover_organize_jobs() == 1
    failed = harness.catalog.get_job(job.job_id)
    assert failed.state == "failed"
    assert failed.error_code == "SERVICE_UNAVAILABLE"
    assert "model_resolver" in failed.checkpoint["jobError"]["message"]
    assert harness.provider.calls == []


# ------------------------------------------------------------- 5 模型冻结


def test_model_switch_during_run_does_not_affect_frozen_job(harness: Harness) -> None:
    """⑤ 任务进行中切换聊天模型：已冻结任务仍用原 profile 的句柄，运行中只解析一次。"""
    cloud_provider = FakeLLMProvider()
    switched = False

    def handler(call):
        nonlocal switched
        if not switched:
            switched = True
            # 模型调用期间用户在界面上换了聊天模型：解析器指向另一个 profile
            harness.service.model_resolver = FakeResolver(
                {
                    CLOUD_PROFILE: make_handle(
                        CLOUD_PROFILE, model_id="cloud-x", provider=cloud_provider
                    )
                }
            )
        return organize_reply(block_ids_of(call.input_text))

    harness.provider.handler = handler
    detail = harness.sample_detail()
    response = organize(harness, detail["importId"])  # 4 道草稿 -> 4 批

    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "succeeded"
    assert view["suggestionCount"] == 4
    assert len(harness.provider.calls) == 4
    # 全部批次仍用冻结前的 profile / 模型
    assert {call.model_profile_id for call in harness.provider.calls} == {LOCAL_PROFILE}
    assert {call.model_id for call in harness.provider.calls} == {"qwen2.5:7b"}
    assert cloud_provider.calls == []
    # 冻结解析只发生一次（在 organize 入口）
    assert harness.resolver.calls == [LOCAL_PROFILE]
    checkpoint = harness.catalog.get_job(view["jobId"]).checkpoint
    assert checkpoint["modelProfileId"] == LOCAL_PROFILE


# ------------------------------------------------------------- 6 崩溃与恢复


async def test_recover_resolves_frozen_profile_and_continues(harness: Harness) -> None:
    """⑥ 崩溃后重新进入：用 checkpoint 里的 profileId 重新解析并续跑，不重复已完成批次。"""
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft_ids = [item["draftId"] for item in detail["drafts"][:2]]
    harness.provider.handler = crash_on(1)

    with pytest.raises(RuntimeError):
        await harness.service.organize(import_id, organize_body(draft_ids))
    interrupted = running_job(harness)
    job_id = interrupted.job_id
    assert interrupted.checkpoint["nextBatchIndex"] == 1  # 第 0 批已提交

    # 重启恢复：解析器换成记录型替身，仍按 checkpoint 的 profile id 解析
    replacement = FakeResolver({LOCAL_PROFILE: harness.handle(LOCAL_PROFILE)})
    harness.service.model_resolver = replacement
    harness.provider.handler = None

    assert await harness.service.recover_organize_jobs() == 1
    assert replacement.calls == [LOCAL_PROFILE]
    recovered = harness.catalog.get_job(job_id)
    assert recovered.state == "succeeded"
    assert len(harness.catalog.list_suggestions(organization_job_id=job_id)) == 2
    # 第 0 批只跑过 1 次；第 1 批崩溃 1 次 + 恢复重放 1 次 → 共 3 次调用，没有重复落建议
    assert len(harness.provider.calls) == 3
    assert await harness.service.recover_organize_jobs() == 0


async def test_recover_fails_job_with_readable_reason_when_profile_gone(
    harness: Harness,
) -> None:
    """⑥ profile 已不存在/不可调用 → 任务失败落库并给可读原因（不发上游）。"""
    detail = harness.sample_detail()
    draft = detail["drafts"][0]
    job = harness.catalog.create_job(
        kind="organize",
        state="running",
        checkpoint={
            "contractVersion": ORGANIZE_CONTRACT_VERSION,
            "modelProfileId": "removed-profile",
            "modelFingerprint": "sha256:" + "0" * 64,
            "instruction": ORGANIZE_INSTRUCTION,
            "drafts": [{"draftId": draft["draftId"], "revision": draft["revision"]}],
            "batches": [
                {
                    "index": 0,
                    "draftId": draft["draftId"],
                    "blockIds": [draft["sourceSpans"][0]["blockId"]],
                    "inputText": "[块 x]\n旧文本",
                    "charCount": 9,
                }
            ],
            "nextBatchIndex": 0,
            "suggestionIds": [],
            "failedBatches": [],
        },
    )
    harness.service.model_resolver = FakeResolver(
        error=AppError("模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404)
    )
    assert await harness.service.recover_organize_jobs() == 1

    failed = harness.catalog.get_job(job.job_id)
    assert failed.state == "failed"
    assert failed.error_code == "MODEL_PROFILE_NOT_FOUND"
    message = failed.checkpoint["jobError"]["message"]
    assert "模型" in message and "重新选择" in message
    assert harness.provider.calls == []


async def test_legacy_checkpoint_is_not_auto_resumed_and_keeps_suggestions(
    harness: Harness,
) -> None:
    """⑦ 旧形状 checkpoint：不自动恢复、标记需重新选择模型；已产生的建议一条不动。"""
    detail = harness.sample_detail()
    draft = detail["drafts"][0]
    legacy = harness.catalog.create_job(
        kind="organize",
        state="running",
        checkpoint={
            # v1.0/v1.1 形状：没有 contractVersion / 指纹，modelProfileId 可能是模型名或 UUID
            "modelProfileId": "63b3ffdc-1111-4222-8333-444455556666",
            "resolvedModel": "qwen2.5:7b",
            "instruction": "旧指令",
            "drafts": [{"draftId": draft["draftId"], "revision": draft["revision"]}],
            "batches": [
                {
                    "index": 0,
                    "draftId": draft["draftId"],
                    "blockIds": [draft["sourceSpans"][0]["blockId"]],
                    "inputText": "[块 x]\n旧文本",
                    "charCount": 9,
                }
            ],
            "nextBatchIndex": 0,
            "suggestionIds": ["legacy-suggestion"],
            "failedBatches": [],
        },
    )
    # 旧任务已产生的建议：内容与状态必须原样保留
    existing = harness.catalog.create_suggestions(
        [
            SuggestionInput(
                organization_job_id=legacy.job_id,
                target_draft_id=draft["draftId"],
                base_draft_revision=draft["revision"],
                proposed_content=draft["content"],
                proposed_metadata=draft["metadata"],
                source_block_ids=(draft["sourceSpans"][0]["blockId"],),
                state="pending",
            )
        ]
    )
    before = harness.catalog.list_suggestions(organization_job_id=legacy.job_id)
    assert len(before) == 1

    assert await harness.service.recover_organize_jobs() == 1
    stale = harness.catalog.get_job(legacy.job_id)
    assert stale.state == "failed"
    assert stale.error_code == RESELECT_MODEL_CODE
    assert stale.checkpoint["needsModelReselection"] is True
    assert harness.provider.calls == []
    assert harness.resolver.calls == []

    after = harness.catalog.list_suggestions(organization_job_id=legacy.job_id)
    assert [item.suggestion_id for item in after] == [existing[0].suggestion_id]
    assert [item.state for item in after] == ["pending"]
    assert [item.proposed_content for item in after] == [existing[0].proposed_content]
    assert draft_by_id(harness, detail["importId"], draft["draftId"])["revision"] == draft["revision"]


# ------------------------------------------------------------- 8 错误分类


@pytest.mark.parametrize(
    ("label", "failure", "expected_code", "batch_level"),
    [
        (
            "length",
            LLMResponse(text='{"stem":"截断的题目"', finishReason=FINISH_LENGTH),
            "ORGANIZER_OUTPUT_TRUNCATED",
            True,
        ),
        ("invalid_json", "{不是 JSON", "ORGANIZER_INVALID_JSON", True),
        (
            "unknown_block",
            json.dumps(
                {
                    "stem": "题干",
                    "options": [],
                    "answer": None,
                    "sourceBlockIds": ["not-in-input"],
                },
                ensure_ascii=False,
            ),
            "ORGANIZER_UNKNOWN_SOURCE_BLOCK",
            True,
        ),
        (
            "auth",
            ProviderError("UPSTREAM_AUTH_FAILED", "上游认证失败，请检查凭证与权限。"),
            "AUTH_REQUIRED",
            False,
        ),
        (
            "rate_limited",
            ProviderError("RATE_LIMITED", "上游限流，请稍后重试。", retryable=True),
            "RATE_LIMITED",
            False,
        ),
        (
            "network",
            ProviderError("UPSTREAM_UNREACHABLE", "无法连接到模型服务，请检查 Base URL 与网络。"),
            "UPSTREAM_UNAVAILABLE",
            False,
        ),
    ],
)
def test_error_classification(
    harness: Harness, label: str, failure: Any, expected_code: str, batch_level: bool
) -> None:
    """⑧ 五类错误各自的 code 与“建议是否落库”，且绝不把上游失败说成试题内容问题。"""
    harness.provider.replies = [failure]
    detail = harness.sample_detail()
    draft = detail["drafts"][0]
    before_blocks = harness.catalog.list_source_blocks(detail["importId"])

    response = organize(harness, detail["importId"], draftIds=[draft["draftId"]])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "failed"
    assert view["errorCode"] == expected_code, label
    assert view["suggestionCount"] == 0
    assert view["suggestions"] == []
    assert harness.catalog.list_suggestions(organization_job_id=view["jobId"]) == []

    if batch_level:
        assert view["failedBatches"] == 1
        assert [(item["batchIndex"], item["code"]) for item in view["failures"]] == [
            (0, expected_code)
        ]
        assert view["failures"][0]["message"]
        if expected_code == "ORGANIZER_OUTPUT_TRUNCATED":
            message = view["failures"][0]["message"]
            assert "截断" in message and "原文保留" in message
    else:
        # 任务级：不是「某批内容失败」，文案指向模型服务
        assert view["failedBatches"] == 0
        assert view["failures"] == []
        job_message = harness.catalog.get_job(view["jobId"]).checkpoint["jobError"]["message"]
        assert "模型" in job_message
        assert "试题" not in job_message and "题目" not in job_message
        assert "内容无效" not in job_message

    # 原文与草稿一条不动
    after = draft_by_id(harness, detail["importId"], draft["draftId"])
    assert after["revision"] == draft["revision"]
    assert after["content"] == draft["content"]
    assert len(harness.catalog.list_source_blocks(detail["importId"])) == len(before_blocks)


def test_unknown_upstream_code_falls_back_to_model_service() -> None:
    """未知上游 code 一律按任务级「模型服务不可用」处理，不冤枉试题内容。"""
    from app.services.question_bank.organizer import job_level_error_code, job_level_message

    assert job_level_error_code("SOMETHING_NEW_FROM_UPSTREAM") == "UPSTREAM_UNAVAILABLE"
    assert job_level_error_code("ORGANIZER_INVALID_JSON") == "UPSTREAM_UNAVAILABLE"
    for code in (
        "AUTH_REQUIRED",
        "RATE_LIMITED",
        "UPSTREAM_UNAVAILABLE",
        "MODEL_NOT_CONFIGURED",
        "MODEL_PROFILE_NOT_FOUND",
        "SERVICE_UNAVAILABLE",
    ):
        assert "模型" in job_level_message(code)


def test_organize_invalid_json_keeps_original(harness: Harness) -> None:
    """既有覆盖点（改写）：非法 JSON 该批失败，原文保留、草稿不变。"""
    harness.provider.replies = ["{不是 JSON"]
    detail = harness.sample_detail()
    draft = detail["drafts"][0]
    before_blocks = harness.catalog.list_source_blocks(detail["importId"])

    response = organize(harness, detail["importId"], draftIds=[draft["draftId"]])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "failed"
    assert view["errorCode"] == "ORGANIZER_INVALID_JSON"
    assert view["suggestionCount"] == 0
    assert view["failedBatches"] == 1
    assert view["suggestions"] == []
    assert len(view["failures"]) == 1
    failure = view["failures"][0]
    assert failure["batchIndex"] == 0
    assert failure["code"] == "ORGANIZER_INVALID_JSON"
    assert failure["message"]

    after = draft_by_id(harness, detail["importId"], draft["draftId"])
    assert after["revision"] == draft["revision"]
    assert after["content"] == draft["content"]
    assert len(harness.catalog.list_source_blocks(detail["importId"])) == len(before_blocks)


def test_organize_unknown_source_block_fails_batch(harness: Harness) -> None:
    """既有覆盖点（改写）：引用输入之外的来源块 → 该批失败、不落建议。"""
    harness.provider.replies = [
        json.dumps(
            {"stem": "题干", "options": [], "answer": None, "sourceBlockIds": ["not-in-input"]},
            ensure_ascii=False,
        )
    ]
    detail = harness.sample_detail()
    response = organize(
        harness, detail["importId"], draftIds=[detail["drafts"][0]["draftId"]]
    )
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "failed"
    assert view["errorCode"] == "ORGANIZER_UNKNOWN_SOURCE_BLOCK"
    assert view["failedBatches"] == 1
    assert harness.catalog.list_suggestions(organization_job_id=view["jobId"]) == []


def test_organize_truncated_output_fails_batch(harness: Harness) -> None:
    """既有覆盖点（改写）：finish_reason=length → ORGANIZER_OUTPUT_TRUNCATED，不生成建议。"""
    harness.provider.replies = [
        LLMResponse(text='{"stem":"写到一半被截断"', finishReason=FINISH_LENGTH)
    ]
    detail = harness.sample_detail()
    response = organize(
        harness, detail["importId"], draftIds=[detail["drafts"][0]["draftId"]]
    )
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "failed"
    assert view["errorCode"] == "ORGANIZER_OUTPUT_TRUNCATED"
    assert view["failedBatches"] == 1
    assert view["suggestions"] == []
    assert [(item["batchIndex"], item["code"]) for item in view["failures"]] == [
        (0, "ORGANIZER_OUTPUT_TRUNCATED")
    ]
    assert "截断" in view["failures"][0]["message"]


# ------------------------------------------------------------- 9 预算


def test_pack_batches_counts_labels_and_separators() -> None:
    """⑨ 预算含标签与分隔符：6000 码点是**打包文本**上限，不是原文上限。"""
    assert MAX_BATCH_INPUT_CHARS == 6000
    block_a, block_b = "a" * 32, "b" * 32
    rendered_a = 3000
    rendered_b = 2998

    def body_for(block_id: str, rendered_chars: int) -> str:
        return "x" * (rendered_chars - len(render_block(block_id, "")))

    # 3000 + 2（分隔符）+ 2998 == 6000 → 刚好一批
    exact = pack_batches("d1", [(block_a, body_for(block_a, rendered_a)), (block_b, body_for(block_b, rendered_b))])
    assert len(exact) == 1
    assert exact[0].char_count == 6000
    assert len(exact[0].input_text) == 6000

    # 3000 + 2 + 2999 == 6001 → 必须分两批
    over = pack_batches(
        "d1",
        [(block_a, body_for(block_a, rendered_a)), (block_b, body_for(block_b, rendered_b + 1))],
    )
    assert len(over) == 2
    for batch in over:
        assert batch.char_count == len(batch.input_text) <= MAX_BATCH_INPUT_CHARS

    # 单块超限：按行/硬切分包，每片渲染后仍 ≤ 上限，且拼回等于原正文
    huge_line = "y" * 20000
    sliced = pack_batches("d1", [(block_a, huge_line)])
    assert len(sliced) >= 3
    for batch in sliced:
        assert batch.char_count == len(batch.input_text) <= MAX_BATCH_INPUT_CHARS
        assert batch.block_ids == (block_a,)
    rebuilt = "".join(
        batch.input_text[len(render_block(block_a, "")) :] for batch in sliced
    )
    assert rebuilt == huge_line


def test_organize_splits_oversized_source_into_bounded_batches(harness: Harness) -> None:
    """⑨ 端到端：超过 6000 的来源被切成多批，每批打包文本（含标签、分隔符）≤ 6000。"""
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][0]
    big = "题" * 14000
    harness.catalog.add_source_blocks(
        import_id,
        [
            SourceBlockInput(
                ordinal=999,
                text=big,
                locator={
                    "kind": "markdown",
                    "lineStart": 0,
                    "lineEnd": 0,
                    "charStart": 900000,
                    "charEnd": 914000,
                },
            )
        ],
    )

    response = organize(
        harness, import_id, draftIds=[draft["draftId"]], includeUnassigned=True
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "succeeded"
    calls = harness.provider.calls
    assert len(calls) >= 2
    for call in calls:
        assert len(call.input_text) <= MAX_BATCH_INPUT_CHARS
    # 大块按正文预算切片：批次数 == 小批 + 大块切片数
    big_block_id = harness.catalog.list_source_blocks(import_id)[-1].block_id
    body_budget = MAX_BATCH_INPUT_CHARS - len(render_block(big_block_id, ""))
    expected_slices = -(-len(big) // body_budget)
    assert len(calls) == 1 + expected_slices
    assert sum(1 for call in calls if big_block_id in call.input_text) == expected_slices


# ------------------------------------------------------------- 10 异步与线程


class ThreadRecordingCatalog:
    """目录代理：记录每个被观察方法所在线程，用于验证 SQL 不在事件循环线程执行。"""

    WATCHED = frozenset(
        {
            "get_import",
            "list_drafts",
            "list_source_blocks",
            "create_job",
            "get_job",
            "list_suggestions",
            "record_organize_batch",
            "fail_organize_job",
            "finish_organize_job",
        }
    )

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.threads: list[int] = []

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if name not in self.WATCHED or not callable(attribute):
            return attribute

        def observed(*args: Any, **kwargs: Any) -> Any:
            self.threads.append(threading.get_ident())
            return attribute(*args, **kwargs)

        return observed


async def test_organize_is_async_and_runs_sql_off_the_loop_thread(harness: Harness) -> None:
    """⑩ organize/run/recover 是协程；SQL 经有界线程执行，不在事件循环线程。"""
    assert inspect.iscoroutinefunction(QuestionBankService.organize)
    assert inspect.iscoroutinefunction(QuestionBankService.run_organize_job)
    assert inspect.iscoroutinefunction(QuestionBankService.recover_organize_jobs)
    assert inspect.iscoroutinefunction(question_bank_route.organize_question_import)

    proxy = ThreadRecordingCatalog(harness.catalog)
    harness.service.catalog = proxy
    loop_thread = threading.get_ident()
    detail = harness.sample_detail()
    draft = detail["drafts"][0]

    view = await harness.service.organize(
        detail["importId"], organize_body([draft["draftId"]])
    )
    assert view.state == "succeeded"

    assert proxy.threads, "没有观察到任何 SQL 调用"
    assert all(thread != loop_thread for thread in proxy.threads)  # SQL 不在事件循环线程
    assert all(thread != loop_thread for thread in harness.resolver.thread_ids)
    # 模型调用在事件循环线程上 await（网络 I/O 不在事务里，也不占线程池）
    assert [call.thread_id for call in harness.provider.calls] == [loop_thread]


# ------------------------------------------------------- 既有覆盖点（改写）


def test_organize_creates_pending_suggestions(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][0]

    response = organize(harness, import_id, draftIds=[draft["draftId"]])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "succeeded"
    assert view["suggestionCount"] == 1
    assert view["failedBatches"] == 0
    assert view["errorCode"] is None
    assert view["failures"] == []

    # 响应直接带出建议明细：前端不必再猜 id（计划 §8.4「不直接覆盖人工草稿」）
    assert len(view["suggestions"]) == 1
    detail_view = view["suggestions"][0]
    for field in (
        "suggestionId",
        "organizationJobId",
        "targetDraftId",
        "baseDraftRevision",
        "proposedContent",
        "proposedMetadata",
        "sourceBlockIds",
        "state",
    ):
        assert field in detail_view
    assert detail_view["organizationJobId"] == view["jobId"]
    assert detail_view["targetDraftId"] == draft["draftId"]
    assert detail_view["baseDraftRevision"] == draft["revision"]
    assert detail_view["state"] == "pending"
    assert detail_view["sourceBlockIds"]  # 必须来自输入块
    assert detail_view["proposedMetadata"] == draft["metadata"]  # 事务内取当前草稿分类

    suggestions = harness.catalog.list_suggestions(organization_job_id=view["jobId"])
    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.suggestion_id == detail_view["suggestionId"]
    assert suggestion.state == "pending"
    assert suggestion.target_draft_id == draft["draftId"]
    assert suggestion.base_draft_revision == draft["revision"]
    # 建议不直接改草稿
    after = draft_by_id(harness, import_id, draft["draftId"])
    assert after["revision"] == draft["revision"]
    assert after["content"] == draft["content"]
    assert after["reviewState"] == "needs_review"

    # 明细字段可直接调用 apply：baseDraftRevision 就是 expectedDraftRevision
    applied = harness.client.post(
        f"/api/v1/question-suggestions/{detail_view['suggestionId']}/apply",
        json={"expectedDraftRevision": detail_view["baseDraftRevision"], "accept": True},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["revision"] == draft["revision"] + 1
    assert applied.json()["content"]["stemMarkdown"] == (
        detail_view["proposedContent"]["stemMarkdown"]
    )

    # 已处理的不再出现在明细里；累计计数保留，供界面显示「已处理 N/M」
    refreshed = harness.service.get_organize_job(view["jobId"])
    assert refreshed.suggestions == []
    assert refreshed.suggestionCount == 1
    assert refreshed.failedBatches == 0


@pytest.mark.parametrize(
    ("profile_limit", "expected_tokens"),
    [(512, 512), (8192, MAX_OUTPUT_TOKENS)],
)
def test_organize_uses_injected_model_and_respects_output_cap(
    harness: Harness, profile_limit: int, expected_tokens: int
) -> None:
    """输出预算 = min(2048, 所选模型 max_output_tokens)，逐批同样受约束。"""
    harness.resolver.profiles[LOCAL_PROFILE] = harness.handle(
        LOCAL_PROFILE, max_output_tokens=profile_limit
    )
    detail = harness.sample_detail()
    response = organize(harness, detail["importId"])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["suggestionCount"] == 4
    assert len(harness.provider.calls) == 4
    for call in harness.provider.calls:
        assert call.max_output_tokens == expected_tokens
        assert len(call.input_text) <= MAX_BATCH_INPUT_CHARS
        assert "不推断原文缺失的答案" in call.messages[0].content


def test_organize_partial_success_can_retry_failed_batch(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    first, second = detail["drafts"][0], detail["drafts"][1]

    def handler(call):
        if call.index == 0:
            return "not json"
        return organize_reply(block_ids_of(call.input_text))

    harness.provider.handler = handler

    response = organize(harness, import_id, draftIds=[first["draftId"], second["draftId"]])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "succeeded"
    assert view["suggestionCount"] == 1
    assert view["failedBatches"] == 1
    assert len(view["suggestions"]) == 1
    assert len(view["failures"]) == 1
    failure = view["failures"][0]
    assert failure["batchIndex"] == 0
    assert failure["code"] == "ORGANIZER_INVALID_JSON"
    assert failure["message"]

    unchanged = draft_by_id(harness, import_id, first["draftId"])
    assert unchanged["content"] == first["content"]
    assert unchanged["revision"] == first["revision"]
    assert harness.catalog.get_job(view["jobId"]).checkpoint["failedBatches"][0]["code"] == (
        "ORGANIZER_INVALID_JSON"
    )

    # 只重试失败的那一道：新任务成功，不再产生重复建议
    harness.provider.handler = None
    retry = organize(harness, import_id, draftIds=[first["draftId"]])
    assert retry.status_code == 200, retry.text
    retry_view = retry.json()
    assert retry_view["failedBatches"] == 0
    assert retry_view["suggestionCount"] == 1
    assert retry_view["jobId"] != view["jobId"]


def test_organize_target_changed_discards_batch(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][0]

    def handler(call):
        # 模型调用期间用户编辑草稿（同一服务入口，不经 HTTP）：该批建议必须丢弃，
        # 不能落成过期建议；编辑发生在事务之外（模型调用期间）。
        current = harness.catalog.get_draft(draft["draftId"])
        edited = dict(current.content)
        edited["stemMarkdown"] = "模型调用期间被改写的题干"
        harness.service.patch_draft(
            draft["draftId"],
            DraftPatchRequest(
                expectedRevision=current.revision,
                content=edited,
                metadata=current.metadata,
            ),
        )
        return organize_reply(block_ids_of(call.input_text))

    harness.provider.handler = handler
    response = organize(harness, import_id, draftIds=[draft["draftId"]])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "failed"
    assert view["suggestionCount"] == 0
    assert view["failedBatches"] == 1
    assert harness.catalog.list_suggestions(organization_job_id=view["jobId"]) == []
    checkpoint = harness.catalog.get_job(view["jobId"]).checkpoint
    assert checkpoint["failedBatches"][0]["code"] == "ORGANIZE_DRAFT_CHANGED"
    assert view["suggestions"] == []
    assert [(item["batchIndex"], item["code"]) for item in view["failures"]] == [
        (0, "ORGANIZE_DRAFT_CHANGED")
    ]
    assert "被编辑" in view["failures"][0]["message"]
    # 人工编辑保留，草稿没有被建议覆盖
    assert draft_by_id(harness, import_id, draft["draftId"])["content"]["stemMarkdown"] == (
        "模型调用期间被改写的题干"
    )


def test_organize_all_batches_fail_lists_every_failure(harness: Harness) -> None:
    """全批失败：明细为空、failures 覆盖每一批，草稿与原文一条不动。"""
    detail = harness.sample_detail()
    import_id = detail["importId"]
    before_blocks = [block.block_id for block in harness.catalog.list_source_blocks(import_id)]
    harness.provider.replies = ["{坏 JSON"] * 4

    response = organize(harness, import_id)  # 4 道草稿 -> 4 批
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "failed"
    assert view["suggestions"] == []
    assert view["suggestionCount"] == 0
    assert view["failedBatches"] == 4
    assert [item["batchIndex"] for item in view["failures"]] == [0, 1, 2, 3]
    assert {item["code"] for item in view["failures"]} == {"ORGANIZER_INVALID_JSON"}
    assert all(item["message"] for item in view["failures"])

    after = harness.import_detail(import_id)
    assert [item["content"] for item in after["drafts"]] == [
        item["content"] for item in detail["drafts"]
    ]
    assert [item["revision"] for item in after["drafts"]] == [
        item["revision"] for item in detail["drafts"]
    ]
    assert [item["reviewState"] for item in after["drafts"]] == [
        "needs_review" for _ in detail["drafts"]
    ]
    assert len(after["unassignedBlocks"]) == len(detail["unassignedBlocks"])
    assert [block.block_id for block in harness.catalog.list_source_blocks(import_id)] == (
        before_blocks
    )


def test_batch_failure_mapping_is_strict() -> None:
    """失败批映射：缺 message 用固定兜底文案；结构损坏报 QUESTION_BANK_CORRUPT，不静默跳过。"""
    mapped = views.organize_batch_failure({"index": 2, "code": "ORGANIZER_INVALID_JSON"})
    assert mapped.batchIndex == 2
    assert mapped.code == "ORGANIZER_INVALID_JSON"
    assert mapped.message  # 兜底文案非空

    for code in ("ORGANIZER_OUTPUT_TRUNCATED", "ORGANIZE_DRAFT_CHANGED"):
        fallback = views.organize_batch_failure({"index": 0, "code": code})
        assert fallback.message

    for broken in (
        "not-a-dict",
        {"index": "x", "code": "ORGANIZER_INVALID_JSON"},
        {"index": 0, "code": ""},
        {"index": -1, "code": "ORGANIZER_INVALID_JSON"},
    ):
        with pytest.raises(AppError) as corrupt:
            views.organize_batch_failure(broken)
        assert corrupt.value.code == "QUESTION_BANK_CORRUPT"


async def test_organize_cancel_stops_remaining_batches(harness: Harness) -> None:
    """取消：不再调用后续批次；已提交的批次建议保留可处理，未跑的批次不产生伪造失败。"""
    detail = harness.sample_detail()
    import_id = detail["importId"]

    def handler(call):
        if call.index == 1:
            harness.service.cancel_organize_job(running_job(harness).job_id)
        return organize_reply(block_ids_of(call.input_text))

    harness.provider.handler = handler
    view = await harness.service.organize(import_id, organize_body([]))  # 4 道草稿 -> 4 批
    assert view.state == "cancelled"
    assert len(harness.provider.calls) == 2  # 第 2 批（含）之后的批次不再调用模型
    assert view.suggestionCount == 1  # 第 0 批已提交，仍可见可处理
    assert view.failedBatches == 0
    assert [item.state for item in view.suggestions] == ["pending"]
    assert view.failures == []

    # 取消的任务不会被重启恢复再跑
    assert await harness.service.recover_organize_jobs() == 0
    assert harness.catalog.get_job(view.jobId).state == "cancelled"


async def test_cancel_during_batch_discards_that_batch(harness: Harness) -> None:
    """取消发生在某批模型调用期间：该批建议不落库（事务内检查任务未取消）。"""
    detail = harness.sample_detail()

    def handler(call):
        harness.service.cancel_organize_job(running_job(harness).job_id)
        return organize_reply(block_ids_of(call.input_text))

    harness.provider.handler = handler
    view = await harness.service.organize(
        detail["importId"], organize_body([detail["drafts"][0]["draftId"]])
    )
    assert view.state == "cancelled"
    assert len(harness.provider.calls) == 1
    assert view.suggestionCount == 0
    assert view.suggestions == []
    assert view.failures == []
    assert harness.catalog.list_suggestions(organization_job_id=view.jobId) == []


# ------------------------------------------------------------- 应用建议


def test_apply_suggestion_after_stale_base_is_conflict(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][0]
    job = organize(harness, import_id, draftIds=[draft["draftId"]]).json()
    suggestion = harness.catalog.list_suggestions(organization_job_id=job["jobId"])[0]
    current = harness.import_detail(import_id)["drafts"][0]

    # 建议基线过期：先编辑草稿，再应用
    edited = dict(current["content"])
    edited["stemMarkdown"] = "编辑后的题干"
    patched = harness.patch_draft(current, content=edited)
    assert patched.status_code == 200
    assert patched.json()["revision"] == current["revision"] + 1

    response = harness.client.post(
        f"/api/v1/question-suggestions/{suggestion.suggestion_id}/apply",
        json={"expectedDraftRevision": patched.json()["revision"], "accept": True},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "DRAFT_REVISION_CONFLICT"
    assert harness.catalog.get_suggestion(suggestion.suggestion_id).state == "pending"


def test_apply_suggestion_updates_draft(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][0]
    job = organize(harness, import_id, draftIds=[draft["draftId"]]).json()
    suggestion = harness.catalog.list_suggestions(organization_job_id=job["jobId"])[0]

    # 乐观锁不匹配（客户端 revision 过期）-> 409 REVISION_CONFLICT
    stale = harness.client.post(
        f"/api/v1/question-suggestions/{suggestion.suggestion_id}/apply",
        json={"expectedDraftRevision": draft["revision"] + 5, "accept": True},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "REVISION_CONFLICT"

    applied = harness.client.post(
        f"/api/v1/question-suggestions/{suggestion.suggestion_id}/apply",
        json={"expectedDraftRevision": draft["revision"], "accept": True},
    )
    assert applied.status_code == 200, applied.text
    updated = applied.json()
    assert updated["revision"] == draft["revision"] + 1
    assert updated["reviewState"] == "needs_review"
    assert updated["content"]["stemMarkdown"] == suggestion.proposed_content["stemMarkdown"]
    assert harness.catalog.get_suggestion(suggestion.suggestion_id).state == "applied"

    # 不能重复应用
    again = harness.client.post(
        f"/api/v1/question-suggestions/{suggestion.suggestion_id}/apply",
        json={"expectedDraftRevision": updated["revision"], "accept": True},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "SUGGESTION_NOT_PENDING"


def test_reject_suggestion_keeps_draft(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][1]
    job = organize(harness, import_id, draftIds=[draft["draftId"]]).json()
    suggestion = harness.catalog.list_suggestions(organization_job_id=job["jobId"])[0]

    rejected = harness.client.post(
        f"/api/v1/question-suggestions/{suggestion.suggestion_id}/apply",
        json={"expectedDraftRevision": draft["revision"], "accept": False},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["revision"] == draft["revision"]
    assert rejected.json()["content"] == draft["content"]
    assert harness.catalog.get_suggestion(suggestion.suggestion_id).state == "rejected"


def test_organize_rejects_failed_or_confirmed_import(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][0]
    reviewed = harness.patch_draft(draft)
    assert reviewed.status_code == 200
    confirmed = harness.client.post(
        f"/api/v1/question-imports/{import_id}/confirm",
        json={
            "submissionId": "submission-0001",
            "importId": import_id,
            "items": [
                {"draftId": draft["draftId"], "expectedDraftRevision": reviewed.json()["revision"]}
            ],
        },
    )
    assert confirmed.status_code == 200, confirmed.text

    blocked = organize(harness, import_id, draftIds=[draft["draftId"]])
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "IMPORT_ALREADY_CONFIRMED"

    unknown = harness.client.post(
        f"/api/v1/question-imports/{harness.sample_detail()['importId']}/organize",
        json={"draftIds": ["missing"], "modelProfileId": LOCAL_PROFILE},
    )
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "DRAFT_NOT_FOUND"

    missing_import = harness.client.post(
        "/api/v1/question-imports/nope/organize",
        json={"draftIds": [], "modelProfileId": LOCAL_PROFILE},
    )
    assert missing_import.status_code == 404
    assert missing_import.json()["code"] == "IMPORT_NOT_FOUND"


def test_apply_rejects_missing_suggestion(harness: Harness) -> None:
    detail = harness.sample_detail()
    response = harness.client.post(
        "/api/v1/question-suggestions/nope/apply",
        json={"expectedDraftRevision": 0, "accept": True},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "SUGGESTION_NOT_FOUND"
    assert detail["drafts"]


def test_service_apply_suggestion_direct(harness: Harness) -> None:
    """服务层入口（不经 HTTP）同样受 draft 修订约束。"""
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][2]
    job = organize(harness, import_id, draftIds=[draft["draftId"]]).json()
    suggestion = harness.catalog.list_suggestions(organization_job_id=job["jobId"])[0]
    view = harness.service.apply_suggestion(
        suggestion.suggestion_id,
        SuggestionApplyRequest(expectedDraftRevision=draft["revision"], accept=True),
    )
    assert view.revision == draft["revision"] + 1
    assert view.reviewState == "needs_review"


def test_organize_include_unassigned_attaches_blocks(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][0]
    response = organize(harness, import_id, draftIds=[draft["draftId"]], includeUnassigned=True)
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["suggestionCount"] >= 1
    suggested_blocks = set(
        harness.catalog.list_suggestions(organization_job_id=view["jobId"])[0].source_block_ids
    )
    unassigned_ids = {block["blockId"] for block in detail["unassignedBlocks"]}
    # 未归属块被挂到前一道所选草稿，来源仍可回溯
    assert suggested_blocks & unassigned_ids
    assert "includeUnassigned" in harness.catalog.get_job(view["jobId"]).checkpoint


def test_organize_rejects_draft_from_other_import(harness: Harness) -> None:
    """草稿不属于该导入 → 404 DRAFT_NOT_FOUND，不建任务、不发上游。"""
    first_detail = harness.sample_detail()
    import_id = first_detail["importId"]
    other_detail = harness.sample_detail()
    foreign = other_detail["drafts"][0]

    response = harness.client.post(
        f"/api/v1/question-imports/{import_id}/organize",
        json={"draftIds": [foreign["draftId"]], "modelProfileId": LOCAL_PROFILE},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "DRAFT_NOT_FOUND"
    assert harness.provider.calls == []
    assert job_records(harness) == []


def test_excluded_only_drafts_is_rejected(harness: Harness) -> None:
    """没有可整理的草稿（全部排除）→ 422 ORGANIZE_TARGET_EMPTY。"""
    detail = harness.sample_detail()
    import_id = detail["importId"]
    for draft in detail["drafts"]:
        harness.catalog.set_draft_review_state(
            draft["draftId"], expected_revision=draft["revision"], review_state="excluded"
        )
    response = organize(harness, import_id)
    assert response.status_code == 422
    assert response.json()["code"] == "ORGANIZE_TARGET_EMPTY"
    assert harness.provider.calls == []
    assert job_records(harness) == []
