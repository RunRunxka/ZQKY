"""题库 AI 整理：建议落 pending、失败批保留原文、取消、重试与重启恢复。

模型一律走注入替身（``FakeOrganizer``），不连真实 Ollama；断点恢复只依赖
``question_jobs.checkpoint_json`` 里的批次快照。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.schemas.question_bank import OrganizeRequest, SuggestionApplyRequest
from app.services.question_bank.organizer import DEFAULT_ORGANIZE_MODEL
from tests.test_question_bank import (
    FakeModelCatalog,
    FakeOrganizer,
    Harness,
    block_ids_of,
    open_harness,
    organize_reply,
)

MODEL_PROFILE = "qwen2.5:7b"


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
        "modelProfileId": overrides.pop("modelProfileId", MODEL_PROFILE),
    }
    assert not overrides, overrides
    return harness.client.post(f"/api/v1/question-imports/{import_id}/organize", json=body)


def job_records(harness: Harness):
    return harness.catalog.list_jobs(kind="organize")


# --------------------------------------------------------------------------- 5


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

    suggestions = harness.catalog.list_suggestions(organization_job_id=view["jobId"])
    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.suggestion_id == detail_view["suggestionId"]
    assert suggestion.state == "pending"
    assert suggestion.target_draft_id == draft["draftId"]
    assert suggestion.base_draft_revision == draft["revision"]
    # 建议不直接改草稿
    after = harness.import_detail(import_id)
    same = [item for item in after["drafts"] if item["draftId"] == draft["draftId"]][0]
    assert same["revision"] == draft["revision"]
    assert same["content"] == draft["content"]
    assert same["reviewState"] == "needs_review"

    listed = harness.client.get(f"/api/v1/question-imports/{import_id}")
    assert listed.status_code == 200

    # 明细字段可直接调用 apply：baseDraftRevision 就是 expectedDraftRevision
    applied = harness.client.post(
        f"/api/v1/question-suggestions/{detail_view['suggestionId']}/apply",
        json={
            "expectedDraftRevision": detail_view["baseDraftRevision"],
            "accept": True,
        },
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


def test_organize_uses_injected_model_and_bounded_batches(harness: Harness) -> None:
    detail = harness.sample_detail()
    response = organize(harness, detail["importId"])
    assert response.status_code == 200, response.text
    view = response.json()
    # 4 道草稿 -> 4 批；每批输入不超过 6000 字符，输出预算不超过 2048
    assert view["suggestionCount"] == 4
    assert len(harness.organizer.calls) == 4
    for call in harness.organizer.calls:
        assert call.model_name == MODEL_PROFILE
        assert call.max_output_tokens == 2048
        assert len(call.input_text) <= 6000
        assert "不推断原文缺失的答案" in call.instruction


def test_organize_invalid_json_keeps_original(harness: Harness) -> None:
    harness.organizer.replies = ["{不是 JSON"]
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

    after = harness.import_detail(detail["importId"])
    same = [item for item in after["drafts"] if item["draftId"] == draft["draftId"]][0]
    assert same["revision"] == draft["revision"]
    assert same["content"] == draft["content"]
    assert len(harness.catalog.list_source_blocks(detail["importId"])) == len(before_blocks)


def test_organize_unknown_source_block_fails_batch(harness: Harness) -> None:
    harness.organizer.replies = [
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


def test_organize_partial_success_can_retry_failed_batch(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    first, second = detail["drafts"][0], detail["drafts"][1]

    def handler(call):
        if call.batch_index == 0:
            return "not json"
        return organize_reply(block_ids_of(call.input_text))

    harness.service.organizer = FakeOrganizer(handler=handler)

    response = organize(
        harness, import_id, draftIds=[first["draftId"], second["draftId"]]
    )
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

    after = harness.import_detail(import_id)
    unchanged = [item for item in after["drafts"] if item["draftId"] == first["draftId"]][0]
    assert unchanged["content"] == first["content"]
    assert unchanged["revision"] == first["revision"]
    assert harness.catalog.get_job(view["jobId"]).checkpoint["failedBatches"][0]["code"] == (
        "ORGANIZER_INVALID_JSON"
    )

    # 只重试失败的那一道：新任务成功，不再产生重复建议
    harness.service.organizer = FakeOrganizer()
    retry = organize(harness, import_id, draftIds=[first["draftId"]])
    assert retry.status_code == 200, retry.text
    retry_view = retry.json()
    assert retry_view["failedBatches"] == 0
    assert retry_view["suggestionCount"] == 1
    assert retry_view["jobId"] != view["jobId"]


def test_organize_truncated_output_fails_batch(harness: Harness) -> None:
    def handler(call):
        raise AppError(
            "整理模型输出被截断，该批已失败，原文保留。",
            code="ORGANIZER_TRUNCATED",
            status_code=422,
        )

    harness.service.organizer = FakeOrganizer(handler=handler)
    detail = harness.sample_detail()
    response = organize(harness, detail["importId"], draftIds=[detail["drafts"][0]["draftId"]])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "failed"
    assert view["errorCode"] == "ORGANIZER_TRUNCATED"
    assert view["failedBatches"] == 1
    assert view["suggestions"] == []
    assert [(item["batchIndex"], item["code"]) for item in view["failures"]] == [
        (0, "ORGANIZER_TRUNCATED")
    ]
    assert view["failures"][0]["message"]


def test_organize_model_unavailable_fails_job(harness: Harness) -> None:
    def handler(call):
        raise AppError(
            "本机整理模型不可用，请确认 Ollama 已启动。",
            code="ORGANIZER_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )

    harness.service.organizer = FakeOrganizer(handler=handler)
    detail = harness.sample_detail()
    response = organize(harness, detail["importId"], draftIds=[detail["drafts"][0]["draftId"]])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "failed"
    assert view["errorCode"] == "ORGANIZER_UNAVAILABLE"
    assert view["failedBatches"] == 0
    # 传输层错误是整条任务失败，不是「批内容失败」：明细与失败批都为空
    assert view["suggestions"] == []
    assert view["failures"] == []


def test_organize_target_changed_discards_batch(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][0]

    def handler(call):
        # 模型调用期间用户编辑草稿：该批建议必须丢弃，不能落成过期建议
        current = [
            item
            for item in harness.import_detail(import_id)["drafts"]
            if item["draftId"] == draft["draftId"]
        ][0]
        edited = dict(current["content"])
        edited["stemMarkdown"] = "模型调用期间被改写的题干"
        harness.patch_draft(current, content=edited)
        return organize_reply(block_ids_of(call.input_text))

    harness.service.organizer = FakeOrganizer(handler=handler)
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


def test_organize_all_batches_fail_lists_every_failure(harness: Harness) -> None:
    """全批失败：明细为空、failures 覆盖每一批，草稿与原文一条不动。"""
    detail = harness.sample_detail()
    import_id = detail["importId"]
    before_blocks = [block.block_id for block in harness.catalog.list_source_blocks(import_id)]
    harness.service.organizer = FakeOrganizer(replies=["{坏 JSON"] * 4)

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
    from app.core.exceptions import AppError as ServiceAppError
    from app.services.question_bank import views

    mapped = views.organize_batch_failure({"index": 2, "code": "ORGANIZER_INVALID_JSON"})
    assert mapped.batchIndex == 2
    assert mapped.code == "ORGANIZER_INVALID_JSON"
    assert mapped.message  # 兜底文案非空

    for broken in (
        "not-a-dict",
        {"index": "x", "code": "ORGANIZER_INVALID_JSON"},
        {"index": 0, "code": ""},
        {"index": -1, "code": "ORGANIZER_INVALID_JSON"},
    ):
        with pytest.raises(ServiceAppError) as corrupt:
            views.organize_batch_failure(broken)
        assert corrupt.value.code == "QUESTION_BANK_CORRUPT"


def test_organize_cancel_stops_remaining_batches(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]

    def handler(call):
        harness.service.cancel_organize_job(call.job_id)
        return organize_reply(block_ids_of(call.input_text))

    cancelling = FakeOrganizer(handler=handler)
    harness.service.organizer = cancelling
    response = organize(harness, import_id)  # 4 道草稿 -> 4 批
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "cancelled"
    assert view["suggestionCount"] == 1
    assert view["failedBatches"] == 0
    assert len(cancelling.calls) == 1
    # 取消前已完成的那批建议仍然可见可处理；未跑的批次不产生伪造失败
    assert len(view["suggestions"]) == 1
    assert view["suggestions"][0]["state"] == "pending"
    assert view["failures"] == []

    # 取消的任务不会被重启恢复再跑
    harness.service.organizer = FakeOrganizer()
    assert harness.service.recover_organize_jobs() == 0
    assert harness.catalog.get_job(view["jobId"]).state == "cancelled"


def test_organize_recovers_after_crash(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft_ids = [item["draftId"] for item in detail["drafts"][:2]]

    def crashing(call):
        if call.batch_index == 1:
            raise RuntimeError("模拟进程崩溃")
        return organize_reply(block_ids_of(call.input_text))

    harness.service.organizer = FakeOrganizer(handler=crashing)
    with pytest.raises(RuntimeError):
        harness.client.post(
            f"/api/v1/question-imports/{import_id}/organize",
            json={"draftIds": draft_ids, "includeUnassigned": False, "modelProfileId": MODEL_PROFILE},
        )
    interrupted = [
        job for job in job_records(harness) if job.state == "running"
    ]
    assert len(interrupted) == 1
    job_id = interrupted[0].job_id
    assert interrupted[0].checkpoint["nextBatchIndex"] == 1

    # 重启恢复：从 checkpoint 续跑，不重复已完成的批次
    harness.service.organizer = FakeOrganizer()
    assert harness.service.recover_organize_jobs() == 1
    recovered = harness.catalog.get_job(job_id)
    assert recovered.state == "succeeded"
    assert len(harness.catalog.list_suggestions(organization_job_id=job_id)) == 2
    recovered_view = harness.service.get_organize_job(job_id)
    assert recovered_view.suggestionCount == 2
    assert len(recovered_view.suggestions) == 2
    assert recovered_view.failures == []
    assert {
        item.targetDraftId for item in recovered_view.suggestions
    } == set(draft_ids)

    # 恢复不会与手动取消冲突：再次恢复不重复执行
    assert harness.service.recover_organize_jobs() == 0


# --------------------------------------------------------------------------- 6


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
        json={
            "expectedDraftRevision": patched.json()["revision"],
            "accept": True,
        },
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
            "items": [{"draftId": draft["draftId"], "expectedDraftRevision": reviewed.json()["revision"]}],
        },
    )
    assert confirmed.status_code == 200, confirmed.text

    blocked = organize(harness, import_id, draftIds=[draft["draftId"]])
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "IMPORT_ALREADY_CONFIRMED"

    unknown = harness.client.post(
        f"/api/v1/question-imports/{harness.sample_detail()['importId']}/organize",
        json={"draftIds": ["missing"], "modelProfileId": MODEL_PROFILE},
    )
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "DRAFT_NOT_FOUND"

    missing_import = harness.client.post(
        "/api/v1/question-imports/nope/organize",
        json={"draftIds": [], "modelProfileId": MODEL_PROFILE},
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


def test_organize_empty_model_name_reaches_server_default(harness: Harness) -> None:
    """服务层语义（v1.2）：省略/空串 → 服务端默认本地模型，且只发给本机已安装名。

    注：共享 schema 目前仍是 ``modelProfileId: str = Field(min_length=1, ...)``，HTTP 层还无法
    省略该字段（未改共享 schema）；这里用 ``model_construct`` 直接验证服务层契约。
    """
    detail = harness.sample_detail()
    body = OrganizeRequest.model_construct(
        draftIds=[detail["drafts"][0]["draftId"]],
        includeUnassigned=False,
        modelProfileId="",
    )
    view = harness.service.organize(detail["importId"], body)
    assert view.suggestionCount == 1
    assert view.state == "succeeded"
    assert harness.organizer.calls[-1].model_name == DEFAULT_ORGANIZE_MODEL
    checkpoint = harness.catalog.get_job(view.jobId).checkpoint
    assert checkpoint["resolvedModel"] == DEFAULT_ORGANIZE_MODEL
    assert checkpoint["modelProfileId"] == ""


def test_organize_explicit_local_model_is_used(harness: Harness) -> None:
    harness.model_catalog = FakeModelCatalog(("qwen2.5:7b", "qwen2.5:7b-instruct"))
    harness.service.model_catalog = harness.model_catalog
    detail = harness.sample_detail()
    response = organize(
        harness, detail["importId"], modelProfileId="qwen2.5:7b-instruct"
    )
    assert response.status_code == 200, response.text
    assert harness.organizer.calls[-1].model_name == "qwen2.5:7b-instruct"
    assert harness.catalog.get_job(response.json()["jobId"]).checkpoint["resolvedModel"] == (
        "qwen2.5:7b-instruct"
    )


def test_organize_profile_id_is_never_sent_upstream(harness: Harness) -> None:
    """D2：前端传默认聊天模型 profileId（UUID）时必须 422，且不发出任何上游调用。"""
    profile_id = "63b3ffdc-1111-4222-8333-444455556666"
    detail = harness.sample_detail()
    response = organize(harness, detail["importId"], modelProfileId=profile_id)
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "ORGANIZER_MODEL_MISSING"
    assert "AI 整理只使用本机 Ollama 模型" in body["message"]
    assert profile_id not in body["message"]  # 不回显请求原文
    assert harness.organizer.calls == []  # 没有 /api/chat 调用
    # 不留下半死的整理任务
    assert job_records(harness) == []


def test_organize_unknown_model_name_is_rejected(harness: Harness) -> None:
    harness.model_catalog = FakeModelCatalog(("qwen2.5:7b",))
    harness.service.model_catalog = harness.model_catalog
    detail = harness.sample_detail()
    response = organize(
        harness, detail["importId"], modelProfileId="qwen2.5-coder:7b"
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "ORGANIZER_MODEL_MISSING"
    assert harness.organizer.calls == []


def test_organize_model_tag_normalization_follows_b1(harness: Harness) -> None:
    """tag 归一按 B1 语义：省略 tag 等价 :latest；不做包含匹配、不做双重 tag 折叠。"""
    # 本机安装名不带 tag，"qwen2.5:latest" 与 "qwen2.5" 等价 → 命中（传给上游的是已安装名）
    harness.model_catalog = FakeModelCatalog(("qwen2.5",))
    harness.service.model_catalog = harness.model_catalog
    detail = harness.sample_detail()
    matched = organize(harness, detail["importId"], modelProfileId="qwen2.5:latest")
    assert matched.status_code == 200, matched.text
    assert harness.organizer.calls[-1].model_name == "qwen2.5"
    assert matched.json()["state"] == "succeeded"

    # "qwen2.5-coder:7b" 不得命中 "qwen2.5:7b"（不做包含匹配）
    harness.model_catalog = FakeModelCatalog(("qwen2.5:7b",))
    harness.service.model_catalog = harness.model_catalog
    second = harness.sample_detail()
    rejected = organize(harness, second["importId"], modelProfileId="qwen2.5-coder:7b")
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "ORGANIZER_MODEL_MISSING"

    # 记录一个真实边界：B1 的 normalize_model_tag 不折叠双重 tag，
    # "qwen2.5:7b:latest" 与已安装的 "qwen2.5:7b" 不视为同一模型（如实拒绝，不猜）
    third = harness.sample_detail()
    doubled = organize(harness, third["importId"], modelProfileId="qwen2.5:7b:latest")
    assert doubled.status_code == 422
    assert doubled.json()["code"] == "ORGANIZER_MODEL_MISSING"


def test_ollama_adapters_read_tags_and_never_send_empty_model() -> None:
    """适配器层（MockTransport，不触网）：/api/tags 解析 + 空模型名不发 /api/chat。"""
    import httpx

    from app.services.question_bank.organizer import (
        OllamaModelCatalog,
        OllamaOrganizerModel,
        OrganizerCall,
    )

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "qwen2.5:7b", "model": "qwen2.5:7b"}, {"name": ""}]}
            )
        return httpx.Response(
            200, json={"message": {"content": "{}"}, "done_reason": "stop"}
        )

    transport = httpx.MockTransport(handler)
    catalog = OllamaModelCatalog("http://127.0.0.1:11434", transport=transport)
    assert catalog.installed_models() == ["qwen2.5:7b"]

    # 模型清单只允许本机回环地址
    with pytest.raises(AppError) as not_local:
        OllamaModelCatalog("http://10.0.0.5:11434")
    assert not_local.value.code == "ORGANIZER_BASE_URL_NOT_LOCAL"

    adapter = OllamaOrganizerModel("http://127.0.0.1:11434", transport=transport)
    with pytest.raises(AppError) as missing:
        adapter.organize(
            OrganizerCall(
                job_id="job",
                batch_index=0,
                model_name="",
                instruction="i",
                input_text="x",
                max_output_tokens=10,
            )
        )
    assert missing.value.code == "ORGANIZER_MODEL_MISSING"
    assert [request.url.path for request in seen] == ["/api/tags"]  # 没发 /api/chat

    raw = adapter.organize(
        OrganizerCall(
            job_id="job",
            batch_index=0,
            model_name="qwen2.5:7b",
            instruction="i",
            input_text="x",
            max_output_tokens=10,
        )
    )
    chat_requests = [request for request in seen if request.url.path == "/api/chat"]
    assert len(chat_requests) == 1
    payload = json.loads(chat_requests[0].content.decode("utf-8"))
    assert payload["model"] == "qwen2.5:7b"
    assert payload["format"] == "json"
    assert payload["stream"] is False
    assert payload["options"]["num_predict"] == 10
    assert raw == "{}"


def test_organize_catalog_unavailable_is_503(harness: Harness) -> None:
    """Ollama 不在场 → 503（可重试），与「模型不存在」的 422 区分开，且不发上游调用。"""
    harness.model_catalog = FakeModelCatalog(
        error=AppError(
            "本机 Ollama 不可用，无法确认已安装模型；请启动 Ollama 后重试。",
            code="ORGANIZER_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    )
    harness.service.model_catalog = harness.model_catalog
    detail = harness.sample_detail()
    response = organize(harness, detail["importId"], modelProfileId="qwen2.5:7b")
    assert response.status_code == 503
    assert response.json()["code"] == "ORGANIZER_UNAVAILABLE"
    assert response.json()["retryable"] is True
    assert harness.organizer.calls == []
    assert job_records(harness) == []


def test_organize_recovers_legacy_checkpoint_without_uuid_upstream(harness: Harness) -> None:
    """v1.0/v1.1 遗留 checkpoint（存的是 profile 标识）恢复时不把 UUID 当模型名发出。"""
    detail = harness.sample_detail()
    draft = detail["drafts"][0]
    legacy = harness.catalog.create_job(
        kind="organize",
        state="running",
        checkpoint={
            "modelProfileId": "63b3ffdc-1111-4222-8333-444455556666",
            "instruction": "旧指令",
            "drafts": [{"draftId": draft["draftId"], "revision": draft["revision"]}],
            "batches": [
                {
                    "index": 0,
                    "draftId": draft["draftId"],
                    "blockIds": [detail["drafts"][0]["sourceSpans"][0]["blockId"]],
                    "inputText": "[块 x]\n旧文本",
                    "charCount": 6,
                }
            ],
            "nextBatchIndex": 0,
            "suggestionIds": [],
            "failedBatches": [],
        },
    )
    assert harness.service.recover_organize_jobs() == 1
    job = harness.catalog.get_job(legacy.job_id)
    assert job.state == "failed"
    assert job.error_code == "ORGANIZER_MODEL_MISSING"
    assert harness.organizer.calls == []


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
