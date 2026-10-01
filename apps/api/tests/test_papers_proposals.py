"""T40 AI 建议与已确认读取验收（B2 / A5）：四类非法、过期 stale、应用绑定、reader 闸门。

模型一律受控替身（``FakeProvider`` + ``FakeResolver``）：不触网、不读写正式数据目录与
凭证；凭证哨兵值不得出现在冻结输入、任务快照或响应里。

B3/G0 增补：``teaching:paper_mapping`` 真装配注册 + 公共 retry 回归（失败 → retry →
新 attempt 终态 succeeded，候选与成功同事务发布）。
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.contracts.papers import (
    PaperDraftPatchRequest,
    PaperProposalDecisionRequest,
    PaperProposalJobRequest,
)
from app.core.exceptions import AppError
from app.main import create_app
from app.providers.llm.base import FINISH_LENGTH, LLMResponse
from app.services.papers import proposals as proposal_rules
from tests.conftest import make_settings
from tests.papers_support import (
    FAKE_API_KEY,
    LOCAL_PROFILE,
    SUBJECT_ID,
    FakeProvider,
    PapersHarness,
    build_paper_docx,
    items_payload,
    items_payload_from_json,
    make_handle,
)

TERMINAL = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


@pytest.fixture()
def harness(tmp_path: Path) -> PapersHarness:
    return PapersHarness(tmp_path)


def _reply(entries) -> str:
    return json.dumps({"items": entries}, ensure_ascii=False)


def _prepared(harness: PapersHarness, tmp_path: Path):
    """导入样本 + 关联知识点 + 补全知识点（可直接确认的草稿）。"""
    points = [
        harness.add_point("K1", "二次函数"),
        harness.add_point("K2", "单调性"),
    ]
    docx = build_paper_docx(tmp_path / "sample.docx")
    service = harness.service()
    imported = harness.import_docx(service, docx)
    paper_id = imported.paper.paper_id
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 0,
                "items": items_payload(
                    imported.revision.items,
                    knowledge={
                        "16(1)": [points[0].point_id],
                        "16(2)": [points[1].point_id],
                        "17": [points[0].point_id],
                        "18": [points[1].point_id],
                    },
                ),
            }
        ),
    )
    return service, imported, points


def _leaves(imported):
    return [item for item in imported.revision.items if item.is_scored]


# --------------------------------------------------------------------------- 建任务


def test_create_proposal_job_guards(tmp_path: Path, harness: PapersHarness) -> None:
    service, imported, _points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    request = PaperProposalJobRequest(
        modelProfileId=LOCAL_PROFILE, expectedRevision=service.get_paper(paper_id).revision
    )

    # 未装配任务引擎 / 模型解析器 → 503（可重试），不返回假任务
    missing_engine = harness.service(engine=None)
    with pytest.raises(AppError) as no_engine:
        asyncio.run(missing_engine.create_proposal_job(paper_id, request))
    assert no_engine.value.code == "SERVICE_UNAVAILABLE"
    assert no_engine.value.status_code == 503

    no_resolver = harness.service(engine=harness.new_engine(), resolver=None)
    with pytest.raises(AppError) as no_model:
        asyncio.run(no_resolver.create_proposal_job(paper_id, request))
    assert no_model.value.code == "SERVICE_UNAVAILABLE"

    # 编辑锁过期 → 409 PAPER_REVISION_STALE（冻结前就拒绝）
    with pytest.raises(AppError) as stale:
        harness.run_proposal_job(paper_id, expected_revision=99, provider=FakeProvider())
    assert stale.value.code == "PAPER_REVISION_STALE"
    assert stale.value.details["currentRevision"] == request.expected_revision

    # 已确认修订不能发起建议
    from app.contracts.papers import PaperConfirmRequest

    paper = service.get_paper(paper_id)
    service.confirm(
        paper_id,
        PaperConfirmRequest.model_validate(
            {"expectedRevision": paper.revision, "submissionId": "confirm-for-proposal"}
        ),
    )
    paper = service.get_paper(paper_id)
    with pytest.raises(AppError) as confirmed:
        harness.run_proposal_job(
            paper_id, expected_revision=paper.revision, provider=FakeProvider()
        )
    assert confirmed.value.code == "PAPER_NOT_EDITABLE"


def test_proposal_happy_path_pending_and_succeeded_same_transaction(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    leaves = _leaves(imported)
    provider = FakeProvider(
        handler=lambda request: _reply(
            [
                {
                    "itemId": leaves[0].item_id,
                    "knowledgePointId": points[0].point_id,
                    "evidence": [leaves[0].item_id],
                    "ambiguity": False,
                },
                {
                    "itemId": leaves[1].item_id,
                    "proposedCode": "K9",
                    "proposedName": "待确认新知识点",
                    "evidence": [leaves[1].item_id],
                },
            ]
        )
    )
    svc, record = harness.run_proposal_job(
        paper_id, expected_revision=1, provider=provider
    )
    assert record.state == "succeeded"
    assert record.result["itemCount"] == 2
    proposal_id = record.result["proposalId"]

    rows = harness.raw_rows("SELECT * FROM ai_proposals")
    assert len(rows) == 1
    assert rows[0]["id"] == proposal_id
    assert rows[0]["state"] == "pending"
    assert rows[0]["base_revision"] == 1
    assert rows[0]["target_id"] == imported.paper.current_revision_id
    assert rows[0]["job_id"] == record.job_id

    view = svc.get_proposal(proposal_id)
    assert view.state == "pending"
    assert view.stale is False
    assert view.base_revision == 1
    assert [item.item_id for item in view.items] == [leaves[0].item_id, leaves[1].item_id]
    # questionNo 由服务端按冻结题目回填（不依赖模型输出）
    assert [item.question_no for item in view.items] == ["16(1)", "16(2)"]
    assert view.items[0].knowledge_point_id == points[0].point_id
    assert view.items[0].evidence == [leaves[0].item_id]
    assert view.items[1].proposed_code == "K9"

    # 冻结输入与任务快照不含凭证；执行器只解析注入的 profileId
    frozen = harness.raw_rows(
        "SELECT frozen_input_json, model_snapshot_json, result_json FROM workflow_jobs"
    )[0]
    assert FAKE_API_KEY not in json.dumps(frozen, ensure_ascii=False)
    assert "allowedKnowledgePointIds" in frozen["frozen_input_json"]
    assert '"items"' in frozen["frozen_input_json"]


def test_proposal_invalid_outputs_fail_without_writing_proposals(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    leaves = _leaves(imported)
    before = harness.count("ai_proposals")

    cases = {
        "invalid_json": "这不是 JSON",
        "not_object": json.dumps([1, 2, 3]),
        "missing_items": json.dumps({"candidates": []}),
        "unknown_point": _reply(
            [
                {
                    "itemId": leaves[0].item_id,
                    "knowledgePointId": "point-does-not-exist",
                    "evidence": [],
                }
            ]
        ),
        "unknown_item": _reply(
            [{"itemId": "item-does-not-exist", "knowledgePointId": points[0].point_id}]
        ),
        "evidence_out_of_range": _reply(
            [
                {
                    "itemId": leaves[0].item_id,
                    "knowledgePointId": points[0].point_id,
                    "evidence": ["evidence-not-allowed"],
                }
            ]
        ),
        "duplicate_item": _reply(
            [
                {"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id},
                {"itemId": leaves[0].item_id, "knowledgePointId": points[1].point_id},
            ]
        ),
        "no_mapping": _reply([{"itemId": leaves[0].item_id, "evidence": []}]),
        "truncated": LLMResponse(text='{"items":[', finishReason=FINISH_LENGTH),
    }
    for label, reply in cases.items():
        provider = FakeProvider(handler=lambda request, reply=reply: reply)
        _svc, record = harness.run_proposal_job(
            paper_id, expected_revision=1, provider=provider
        )
        assert record.state == "failed", label
        assert record.error_code == "PAPER_PROPOSAL_INVALID", label
        assert harness.count("ai_proposals") == before, label

    # 解析错误带 row/field 定位（可直接被前端消费）
    with pytest.raises(AppError) as unknown_point:
        proposal_rules.parse_reply(
            cases["unknown_point"],
            allowed_item_ids=[leaves[0].item_id],
            allowed_point_ids=[points[0].point_id],
        )
    assert unknown_point.value.code == "PAPER_PROPOSAL_INVALID"
    issue = unknown_point.value.details["issues"][0]
    assert issue["row"] == 0
    assert issue["field"] == "knowledgePointId"

    with pytest.raises(AppError) as evidence:
        proposal_rules.parse_reply(
            cases["evidence_out_of_range"],
            allowed_item_ids=[leaves[0].item_id],
            allowed_point_ids=[points[0].point_id],
        )
    assert evidence.value.details["issues"][0]["field"] == "evidence"


def test_publish_stale_rolls_back_and_writes_zero_proposals(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    leaves = _leaves(imported)

    def mutating_handler(request):
        # 模型返回前草稿被别的编辑推进：发布事务内复核必须报 stale 并整批回滚
        current = service.get_paper(paper_id)
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {"expectedRevision": current.revision, "title": "模型返回前的改名"}
            ),
        )
        return _reply(
            [{"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id}]
        )

    provider = FakeProvider(handler=mutating_handler)
    _svc, record = harness.run_proposal_job(
        paper_id, expected_revision=1, provider=provider
    )
    # B3/G0 引擎收敛语义：发布事务回滚后任务以**领域错误码**收敛 failed（不再停在 running）
    assert record.state == "failed"
    assert record.error_code == "PAPER_PROPOSAL_STALE"
    assert harness.count("ai_proposals") == 0
    # 草稿本身的改动仍然生效（回滚只影响任务发布事务）
    assert service.get_paper(paper_id).title == "模型返回前的改名"


# --------------------------------------------------------------------------- 应用/拒绝


def _create_proposal(harness: PapersHarness, tmp_path: Path):
    service, imported, points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    leaves = _leaves(imported)
    provider = FakeProvider(
        handler=lambda request: _reply(
            [
                {"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id},
                {"itemId": leaves[1].item_id, "knowledgePointId": points[1].point_id},
            ]
        )
    )
    svc, record = harness.run_proposal_job(
        paper_id, expected_revision=1, provider=provider
    )
    assert record.state == "succeeded"
    return svc, imported, points, record.result["proposalId"]


def _create_proposal_with_unlinked_leaf(harness: PapersHarness, tmp_path: Path):
    """16(1) 故意不建人工关联：用于断言 apply 新写入的 ai_confirmed 快照取当前修订。"""
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]
    docx = build_paper_docx(tmp_path / "sample.docx")
    service = harness.service()
    imported = harness.import_docx(service, docx)
    paper_id = imported.paper.paper_id
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 0,
                "items": items_payload(
                    imported.revision.items,
                    knowledge={
                        "16(2)": [points[1].point_id],
                        "17": [points[0].point_id],
                        "18": [points[1].point_id],
                    },
                ),
            }
        ),
    )
    leaves = _leaves(imported)
    provider = FakeProvider(
        handler=lambda request: _reply(
            [
                {"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id},
                {"itemId": leaves[1].item_id, "knowledgePointId": points[1].point_id},
            ]
        )
    )
    svc, record = harness.run_proposal_job(
        paper_id, expected_revision=1, provider=provider
    )
    assert record.state == "succeeded"
    return svc, imported, points, record.result["proposalId"]


def test_proposal_job_cancel_does_not_publish(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    leaves = _leaves(imported)

    def cancel_mid_call(request):
        # 模型返回前请求取消：执行器在发布前探测到，迟到结果不得落库
        running = harness.raw_rows(
            "SELECT id FROM workflow_jobs WHERE state = 'running'"
        )
        assert running, "任务应当在执行中"
        harness.raw_execute(
            "UPDATE workflow_jobs SET cancel_requested = 1 WHERE id = ?",
            [running[0]["id"]],
        )
        return _reply(
            [{"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id}]
        )

    provider = FakeProvider(handler=cancel_mid_call)
    _svc, record = harness.run_proposal_job(
        paper_id, expected_revision=1, provider=provider
    )
    assert record.state == "cancelled"
    assert harness.count("ai_proposals") == 0


def test_proposal_job_retry_reuses_frozen_input(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    leaves = _leaves(imported)
    # 第一次：模型返回非法 JSON → failed，不落建议
    _svc, failed = harness.run_proposal_job(
        paper_id, expected_revision=1, provider=FakeProvider(handler=lambda request: "nope")
    )
    assert failed.state == "failed"
    assert failed.error_code == "PAPER_PROPOSAL_INVALID"
    assert harness.count("ai_proposals") == 0
    frozen_before = harness.raw_rows(
        "SELECT frozen_input_json, input_hash FROM workflow_jobs WHERE id = ?",
        [failed.job_id],
    )[0]

    # 重试：沿用原冻结输入/指纹（不重新冻结），成功写入 pending 建议
    svc, retried = harness.rerun_proposal_job(
        failed.job_id,
        provider=FakeProvider(
            handler=lambda request: _reply(
                [{"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id}]
            )
        ),
    )
    assert retried.state == "succeeded"
    assert retried.attempt == 2
    frozen_after = harness.raw_rows(
        "SELECT frozen_input_json, input_hash FROM workflow_jobs WHERE id = ?",
        [failed.job_id],
    )[0]
    assert frozen_after == frozen_before
    assert harness.count("ai_proposals") == 1
    assert svc.get_proposal(retried.result["proposalId"]).state == "pending"


def test_apply_proposal_guards_and_success(tmp_path: Path, harness: PapersHarness) -> None:
    svc, imported, points, proposal_id = _create_proposal_with_unlinked_leaf(
        harness, tmp_path
    )
    paper_id = imported.paper.paper_id
    leaves = _leaves(imported)

    def apply(payload: dict):
        return svc.apply_proposal(
            proposal_id, PaperProposalDecisionRequest.model_validate(payload)
        )

    with pytest.raises(AppError) as empty:
        apply({"expectedRevision": 1, "selections": []})
    assert empty.value.code == "PAPER_PROPOSAL_INVALID"

    with pytest.raises(AppError) as mismatched:
        apply(
            {
                "expectedRevision": 1,
                "selections": [
                    {
                        "itemId": leaves[0].item_id,
                        "knowledgePointId": points[1].point_id,  # 与建议内容不符
                    }
                ],
            }
        )
    assert mismatched.value.code == "PAPER_PROPOSAL_INVALID"
    assert mismatched.value.details["issues"][0]["field"] == "knowledgePointId"

    with pytest.raises(AppError) as stale_revision:
        apply(
            {
                "expectedRevision": 0,
                "selections": [
                    {"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id}
                ],
            }
        )
    assert stale_revision.value.code == "PAPER_REVISION_STALE"

    # 知识点改名（追加修订）后应用：名称快照必须取**当前**修订
    renamed_revision = harness.rename_point(points[0].point_id, name="二次函数（新名）")
    content = apply(
        {
            "expectedRevision": 1,
            "selections": [
                {"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id},
                {"itemId": leaves[1].item_id, "knowledgePointId": points[1].point_id},
            ],
        }
    )
    assert content.state == "draft"
    by_no = {item.question_no: item for item in content.items}
    link = by_no["16(1)"].knowledge[0]
    assert link.knowledge_point_id == points[0].point_id
    assert link.knowledge_revision_id == renamed_revision
    assert link.knowledge_name_snapshot == "二次函数（新名）"
    assert link.source == "ai_confirmed"
    # 已有人工关联的题不被覆盖、不重复
    existing = by_no["16(2)"].knowledge
    assert len(existing) == 1
    assert existing[0].source == "human"
    assert harness.raw_rows("SELECT state FROM ai_proposals")[0]["state"] == "applied"
    # 应用改写草稿内容 → 编辑锁 +1
    assert svc.get_paper(paper_id).revision == 2
    assert svc.get_proposal(proposal_id).state == "applied"
    assert svc.get_proposal(proposal_id).stale is False

    # 已应用的再操作 → 409
    with pytest.raises(AppError) as applied:
        apply(
            {
                "expectedRevision": 2,
                "selections": [
                    {"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id}
                ],
            }
        )
    assert applied.value.code == "PAPER_PROPOSAL_INVALID"
    assert applied.value.status_code == 409


def test_apply_rejects_stale_proposal_after_draft_change(
    tmp_path: Path, harness: PapersHarness
) -> None:
    svc, imported, points, proposal_id = _create_proposal(harness, tmp_path)
    paper_id = imported.paper.paper_id
    leaves = _leaves(imported)
    current = svc.get_paper(paper_id)
    svc.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {"expectedRevision": current.revision, "title": "草稿又被改了"}
        ),
    )
    view = svc.get_proposal(proposal_id)
    assert view.stale is True  # 只读视图实时计算
    with pytest.raises(AppError) as stale:
        svc.apply_proposal(
            proposal_id,
            PaperProposalDecisionRequest.model_validate(
                {
                    "expectedRevision": view.base_revision + 1,
                    "selections": [
                        {"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id}
                    ],
                }
            ),
        )
    assert stale.value.code == "PAPER_PROPOSAL_STALE"
    assert stale.value.details["currentRevision"] == view.base_revision + 1


def test_apply_does_not_overwrite_existing_links(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    leaves = _leaves(imported)
    provider = FakeProvider(
        handler=lambda request: _reply(
            [
                {
                    "itemId": leaves[0].item_id,
                    "knowledgePointId": points[0].point_id,
                }
            ]
        )
    )
    svc, record = harness.run_proposal_job(
        paper_id, expected_revision=1, provider=provider
    )
    assert record.state == "succeeded"
    proposal_id = record.result["proposalId"]
    # 16(1) 已有人工关联同一个知识点：应用不覆盖、不重复
    content = svc.apply_proposal(
        proposal_id,
        PaperProposalDecisionRequest.model_validate(
            {
                "expectedRevision": 1,
                "selections": [
                    {"itemId": leaves[0].item_id, "knowledgePointId": points[0].point_id}
                ],
            }
        ),
    )
    link = next(item for item in content.items if item.question_no == "16(1)").knowledge
    assert len(link) == 1
    assert link[0].source == "human"


def test_reject_marks_rejected_without_touching_draft(
    tmp_path: Path, harness: PapersHarness
) -> None:
    svc, imported, _points, proposal_id = _create_proposal(harness, tmp_path)
    paper_id = imported.paper.paper_id
    before_items = harness.raw_rows(
        "SELECT * FROM paper_items WHERE paper_revision_id = ? ORDER BY ordinal",
        [imported.paper.current_revision_id],
    )
    view = svc.reject_proposal(
        proposal_id,
        PaperProposalDecisionRequest.model_validate(
            {"expectedRevision": 1, "selections": []}
        ),
    )
    assert view.state == "rejected"
    assert view.stale is False
    assert svc.get_paper(paper_id).revision == 1  # 拒绝不动编辑锁
    assert (
        harness.raw_rows(
            "SELECT * FROM paper_items WHERE paper_revision_id = ? ORDER BY ordinal",
            [imported.paper.current_revision_id],
        )
        == before_items
    )
    with pytest.raises(AppError) as again:
        svc.reject_proposal(
            proposal_id,
            PaperProposalDecisionRequest.model_validate(
                {"expectedRevision": 1, "selections": []}
            ),
        )
    assert again.value.code == "PAPER_PROPOSAL_INVALID"


# --------------------------------------------------------------------------- reader


def test_confirmed_reader_satisfies_frozen_port(tmp_path: Path, harness: PapersHarness) -> None:
    """T30-b 端口符合性：方法名/返回视图与 ``app.contracts.roster.ConfirmedPaperReader`` 一致。

    该 Protocol 未标 ``runtime_checkable``，因此做**结构性**断言：端口方法存在且可调用，
    调用返回契约的 ``ConfirmedPaperRevisionView``；``read()`` 与端口方法同义。
    """
    from app.contracts.papers import PaperConfirmRequest
    from app.contracts.roster import ConfirmedPaperReader, ConfirmedPaperRevisionView

    service, imported, _points = _prepared(harness, tmp_path)
    reader = service.confirmed_reader()
    port_method = getattr(reader, "read_confirmed_paper_revision", None)
    assert callable(port_method), "adapter 必须实现端口方法 read_confirmed_paper_revision"
    # 端口声明的必需成员必须全部存在（协议是结构契约）
    assert set(ConfirmedPaperReader.__protocol_attrs__) <= set(dir(reader))

    paper = service.get_paper(imported.paper.paper_id)
    confirmed = service.confirm(
        imported.paper.paper_id,
        PaperConfirmRequest.model_validate(
            {"expectedRevision": paper.revision, "submissionId": "port-conformance"}
        ),
    )
    view = reader.read_confirmed_paper_revision(confirmed.paper_revision_id)
    assert isinstance(view, ConfirmedPaperRevisionView)
    assert view.paper_id == imported.paper.paper_id
    assert view.paper_revision_id == confirmed.paper_revision_id
    assert view.title == "sample"
    assert view.subject_id == SUBJECT_ID
    assert view.total_score_units == 2100
    assert view.scored_leaf_count == 4
    # 线上 JSON 形状（camelCase）
    assert set(view.model_dump(by_alias=True)) == {
        "paperId",
        "paperRevisionId",
        "title",
        "subjectId",
        "totalScoreUnits",
        "scoredLeafCount",
    }

    # read() 是等价别名：同一闸门、同一数据
    snapshot = reader.read(confirmed.paper_revision_id)
    assert snapshot.paper_id == view.paper_id
    assert snapshot.paper_revision_id == view.paper_revision_id
    assert snapshot.title == view.title
    assert snapshot.subject_id == view.subject_id
    assert snapshot.total_score_units == view.total_score_units
    assert snapshot.scored_leaf_count == view.scored_leaf_count

    # 端口方法同样拒绝草稿（施测只能引用已确认修订）：另一份卷仍是草稿
    other = harness.import_docx(
        service, build_paper_docx(tmp_path / "still-draft.docx"), title="仍是草稿"
    )
    with pytest.raises(AppError) as draft:
        reader.read_confirmed_paper_revision(other.paper.current_revision_id)
    assert draft.value.code == "ASSESSMENT_PAPER_INVALID"
    with pytest.raises(AppError) as missing:
        reader.read_confirmed_paper_revision("no-such-revision")
    assert missing.value.code == "PAPER_NOT_FOUND"


def test_confirmed_reader_only_returns_confirmed_revisions(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, _points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    reader = service.confirmed_reader()

    from app.contracts.papers import PaperConfirmRequest

    with pytest.raises(AppError) as draft:
        reader.read(imported.paper.current_revision_id)
    assert draft.value.code == "ASSESSMENT_PAPER_INVALID"
    assert draft.value.status_code == 422

    with pytest.raises(AppError) as draft_current:
        reader.read_current(paper_id)
    assert draft_current.value.code == "ASSESSMENT_PAPER_INVALID"

    with pytest.raises(AppError) as missing:
        reader.read("no-such-revision")
    assert missing.value.code == "PAPER_NOT_FOUND"
    assert missing.value.status_code == 404

    paper = service.get_paper(paper_id)
    result = service.confirm(
        paper_id,
        PaperConfirmRequest.model_validate(
            {"expectedRevision": paper.revision, "submissionId": "reader-confirm"}
        ),
    )
    snapshot = reader.read(result.paper_revision_id)
    assert snapshot.title == "sample"  # 真实标题（文件名词干），不是调用方传入的快照
    assert snapshot.subject_id == SUBJECT_ID
    assert snapshot.total_score_units == 2100
    assert snapshot.scored_leaf_count == 4
    assert [item.question_no for item in snapshot.scored_leaves] == [
        "16(1)",
        "16(2)",
        "17",
        "18",
    ]
    assert all(item.max_score_units for item in snapshot.scored_leaves)

    # 改已确认卷 = 新草稿：当前修订不再是已确认卷，reader 拒绝；旧修订仍可读
    current = service.get_paper(paper_id)
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {"expectedRevision": current.revision, "title": "改后"}
        ),
    )
    with pytest.raises(AppError) as forked:
        reader.read_current(paper_id)
    assert forked.value.code == "ASSESSMENT_PAPER_INVALID"
    assert reader.read(result.paper_revision_id).total_score_units == 2100


# --------------------------------------------------------------------------- HTTP 端到端


def test_proposal_over_http_end_to_end(tmp_path: Path) -> None:
    harness = PapersHarness(tmp_path)
    point = harness.add_point("K1", "二次函数")
    app, _service = harness.create_app_with_service(provider=None)
    docx = build_paper_docx(tmp_path / "sample.docx")
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        imported = client.post(
            "/api/v1/paper-imports",
            files={"file": ("sample.docx", docx.read_bytes(), "application/octet-stream")},
            data={"subjectId": SUBJECT_ID},
        ).json()
        paper_id = imported["paper"]["paperId"]
        revision_id = imported["revision"]["paperRevisionId"]
        content = client.get(
            f"/api/v1/papers/{paper_id}/revisions/{revision_id}/content"
        ).json()

        # 服务未装配时（CTRL 装配前）路由必须 503，而不是假成功
        app.state.paper_service = None
        unavailable = client.post(
            f"/api/v1/papers/{paper_id}/knowledge-proposals",
            json={"modelProfileId": LOCAL_PROFILE, "expectedRevision": 0},
        )
        assert unavailable.status_code == 503
        assert unavailable.json()["code"] == "SERVICE_UNAVAILABLE"
        app.state.paper_service = _service

        # 先补全草稿（计分叶子带知识点），再发起建议任务
        patched = client.patch(
            f"/api/v1/papers/{paper_id}/draft",
            json={
                "expectedRevision": 0,
                "items": items_payload_from_json(
                    content["items"], knowledge={"16(1)": [point.point_id]}
                ),
            },
        )
        assert patched.status_code == 200, patched.text

        accepted = client.post(
            f"/api/v1/papers/{paper_id}/knowledge-proposals",
            json={"modelProfileId": LOCAL_PROFILE, "expectedRevision": 1},
        )
        assert accepted.status_code == 202, accepted.text
        job_id = accepted.json()["jobId"]
        assert accepted.json()["state"] in {"queued", "running"}

        proposal_id = None
        for _ in range(200):
            job = client.get(
                "/api/v1/workflow-jobs/" + job_id, params={"domain": "teaching"}
            ).json()
            if job["state"] in {"succeeded", "failed", "cancelled", "interrupted"}:
                assert job["state"] == "succeeded", job
                proposal_id = job["result"]["proposalId"]
                break
            import time

            time.sleep(0.02)
        assert proposal_id, "建议任务未收敛"

        proposal = client.get(f"/api/v1/paper-proposals/{proposal_id}")
        assert proposal.status_code == 200
        assert proposal.json()["state"] == "pending"
        assert proposal.json()["items"] == []  # 替身模型默认返回空建议

        rejected = client.post(
            f"/api/v1/paper-proposals/{proposal_id}/reject",
            json={"expectedRevision": 1, "selections": []},
        )
        assert rejected.status_code == 200
        assert rejected.json()["state"] == "rejected"

        missing = client.get("/api/v1/paper-proposals/nope")
        assert missing.status_code == 404
        assert missing.json()["code"] == "PAPER_PROPOSAL_NOT_FOUND"


def test_apply_proposal_over_http(tmp_path: Path) -> None:
    harness = PapersHarness(tmp_path)
    point = harness.add_point("K1", "二次函数")
    app, _service = harness.create_app_with_service(provider=None)
    docx = build_paper_docx(tmp_path / "sample.docx")
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        imported = client.post(
            "/api/v1/paper-imports",
            files={"file": ("sample.docx", docx.read_bytes(), "application/octet-stream")},
            data={"subjectId": SUBJECT_ID},
        ).json()
        paper_id = imported["paper"]["paperId"]
        revision_id = imported["revision"]["paperRevisionId"]
        leaf = next(
            item
            for item in imported["revision"]["items"]
            if item["questionNo"] == "16(1)"
        )
        patched = client.patch(
            f"/api/v1/papers/{paper_id}/draft",
            json={
                "expectedRevision": 0,
                "items": items_payload_from_json(
                    imported["revision"]["items"],
                    knowledge={"16(1)": [point.point_id]},
                ),
            },
        )
        assert patched.status_code == 200, patched.text
        body = client.post(
            f"/api/v1/papers/{paper_id}/knowledge-proposals",
            json={"modelProfileId": LOCAL_PROFILE, "expectedRevision": 1},
        ).json()
        proposal_id = _wait_proposal(client, body["jobId"])
        # 替身模型默认空建议：应用无选择 → 422
        empty_selection = client.post(
            f"/api/v1/paper-proposals/{proposal_id}/apply",
            json={"expectedRevision": 1, "selections": []},
        )
        assert empty_selection.status_code == 422
        assert empty_selection.json()["code"] == "PAPER_PROPOSAL_INVALID"
        assert revision_id  # 修订 id 已被用于读取内容（上方 GET）


def _wait_proposal(client: TestClient, job_id: str) -> str:
    import time

    for _ in range(200):
        job = client.get(
            "/api/v1/workflow-jobs/" + job_id, params={"domain": "teaching"}
        ).json()
        if job["state"] in TERMINAL:
            assert job["state"] == "succeeded", job
            return job["result"]["proposalId"]
        time.sleep(0.02)
    raise AssertionError("建议任务未收敛")


# --------------------------------------------------------------------------- 真装配 retry（B3/G0 · RV01 原卷侧）


def _raw_teaching_rows(settings, sql: str, params: list | None = None) -> list[dict]:
    import sqlite3

    connection = sqlite3.connect(str(settings.teaching_root / "teaching.sqlite3"))
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(sql, list(params or [])).fetchall()]
    finally:
        connection.close()


def _wait_job_state(client: TestClient, job_id: str, expected: str) -> dict:
    deadline = time.monotonic() + 20.0
    view = client.get(
        f"/api/v1/workflow-jobs/{job_id}", params={"domain": "teaching"}
    ).json()
    while view["state"] != expected and time.monotonic() < deadline:
        time.sleep(0.02)
        view = client.get(
            f"/api/v1/workflow-jobs/{job_id}", params={"domain": "teaching"}
        ).json()
    assert view["state"] == expected, view
    return view


def test_paper_mapping_registered_and_retry_reaches_new_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """真装配（create_app + TestClient + 临时数据根）：`teaching:paper_mapping` 注册。

    失败的建议任务经公共 retry → 新 attempt 终态 succeeded；冻结输入与模型指纹在重试
    前后逐字节不变（不重新冻结）；候选与任务成功**同事务**发布。
    """
    settings = make_settings(tmp_path / "data")
    app = create_app(settings)
    calls = {"count": 0}
    leaf_ids: list[str] = []

    def handler(_request):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("模型替身首次调用失败（测试注入）")
        return _reply(
            [
                {
                    "itemId": leaf_ids[0],
                    "knowledgePointId": None,
                    "proposedCode": "K9",
                    "proposedName": "二次函数（待确认候选）",
                    "evidence": [leaf_ids[0]],
                    "ambiguity": False,
                }
            ]
        )

    provider = FakeProvider(handler=handler)
    handle = make_handle(LOCAL_PROFILE, provider=provider)

    def fake_resolve_chat_model(repo, secrets, profile_id, *, auth_service=None, purpose="chat"):
        assert profile_id == LOCAL_PROFILE
        return handle

    # 真装配路径：main.py 注入的冻结解析器（repo+secret）→ resolve_frozen_model 核对指纹
    monkeypatch.setattr(
        "app.services.model_runtime.resolve_chat_model", fake_resolve_chat_model
    )

    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        registry = app.state.job_executors
        assert registry is not None, "执行器注册表未装配"
        assert registry.has("teaching", "paper_mapping") is True

        docx = build_paper_docx(tmp_path / "retry.docx")
        imported = client.post(
            "/api/v1/paper-imports",
            files={
                "file": (
                    "retry.docx",
                    docx.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"subjectId": SUBJECT_ID, "title": "retry 样本"},
        )
        assert imported.status_code == 201, imported.text
        body = imported.json()
        paper_id = body["paper"]["paperId"]
        revision = body["paper"]["revision"]
        leaf_ids.extend(
            item["itemId"] for item in body["revision"]["items"] if item["isScored"]
        )
        assert leaf_ids

        created = client.post(
            f"/api/v1/papers/{paper_id}/knowledge-proposals",
            json={"modelProfileId": LOCAL_PROFILE, "expectedRevision": revision},
        )
        assert created.status_code == 202, created.text
        job_id = created.json()["jobId"]

        failed = _wait_job_state(client, job_id, "failed")
        assert failed["attempt"] == 1
        before = _raw_teaching_rows(
            settings,
            "SELECT frozen_input_json, model_snapshot_json FROM workflow_jobs WHERE id = ?",
            [job_id],
        )[0]

        retry = client.post(
            f"/api/v1/workflow-jobs/{job_id}/retry", json={"domain": "teaching"}
        )
        assert retry.status_code == 200, retry.text
        final = _wait_job_state(client, job_id, "succeeded")
        assert final["attempt"] == 2
        assert final["result"]["proposalId"]
        assert calls["count"] == 2  # 首次失败 + 重试各一次真实（替身）模型调用

        after = _raw_teaching_rows(
            settings,
            "SELECT frozen_input_json, model_snapshot_json FROM workflow_jobs WHERE id = ?",
            [job_id],
        )[0]
        assert after == before  # 重试沿用原冻结输入与模型指纹，不重新冻结
        snapshot = json.loads(after["model_snapshot_json"])
        assert snapshot["fingerprint"].startswith("sha256:")
        assert FAKE_API_KEY not in json.dumps(after, ensure_ascii=False)

    proposals = _raw_teaching_rows(
        settings, "SELECT job_id, state FROM ai_proposals WHERE job_id = ?", [job_id]
    )
    assert len(proposals) == 1  # 只有成功的 attempt 发布了候选（与 succeeded 同事务）
    assert proposals[0]["state"] == "pending"
