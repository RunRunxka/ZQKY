"""B3/G0 · B2-RV02：原卷问题处置（结构化 resolution + 补录副作用 + 确认阻断）。

覆盖：

- ``supplement_text`` 必须真的改变目标段落块的持久化内容，之后确认成功；
- ``{"anything": 1}`` / 缺字段 / 缺理由的 exclude / 内容损失码用 exclude → 422 且可定位；
- ``supplement_asset`` 必须是受管键且字节可读（sha256 核验），否则 422 可定位；
- 未补录的 blocking 问题（含内容损失）仍然阻断确认。

模型一律不参与（本文件不创建 AI 建议任务）；所有数据在 ``tmp_path`` 隔离库里。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.contracts.papers import (
    PaperConfirmRequest,
    PaperDraftPatchRequest,
)
from app.core.exceptions import AppError
from app.services.jobs.engine import FrozenJob
from app.services.papers.proposals import ProposalRunner
from tests.papers_support import (
    FAKE_API_KEY,
    LOCAL_PROFILE,
    FakeProvider,
    FakeResolver,
    PapersHarness,
    build_paper_docx,
    items_payload,
    make_handle,
)


@pytest.fixture()
def harness(tmp_path: Path) -> PapersHarness:
    return PapersHarness(tmp_path)


def _prepared(harness: PapersHarness, tmp_path: Path, *, unknown_object: bool = True):
    """导入样本（默认带未知对象 → blocking UNSUPPORTED_OBJECT）并给计分叶补知识点。"""
    service = harness.service()
    imported = harness.import_docx(
        service,
        build_paper_docx(tmp_path / "sample.docx", with_unknown_object=unknown_object),
    )
    paper_id = imported.paper.paper_id
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]
    knowledge = {
        "16(1)": [points[0].point_id],
        "16(2)": [points[1].point_id],
        "17": [points[0].point_id],
        "18": [points[1].point_id],
    }
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 0,
                "items": items_payload(imported.revision.items, knowledge=knowledge),
            }
        ),
    )
    return service, imported, points


def _revision(service, paper_id: str) -> int:
    return service.get_paper(paper_id).revision


def _target_paragraph(imported):
    return next(
        block
        for block in imported.revision.blocks
        if block.kind == "paragraph" and block.disposition == "item"
    )


def _blocking_issue(imported):
    return next(
        issue for issue in imported.revision.issues if issue.severity == "blocking"
    )


def _confirm(service, paper_id: str, *, submission: str = "issue-resolution"):
    return service.confirm(
        paper_id,
        PaperConfirmRequest.model_validate(
            {"expectedRevision": _revision(service, paper_id), "submissionId": submission}
        ),
    )


# --------------------------------------------------------------------------- 正常路径


def test_supplement_text_changes_block_then_confirm_succeeds(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, _points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    issue = _blocking_issue(imported)
    assert issue.code == "UNSUPPORTED_OBJECT"
    target = _target_paragraph(imported)
    before = next(
        block for block in imported.revision.blocks if block.block_id == target.block_id
    ).content

    content = service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 1,
                "issues": [
                    {
                        "issueId": issue.issue_id,
                        "status": "resolved",
                        "resolution": {
                            "kind": "supplement_text",
                            "targetBlockId": target.block_id,
                            "text": "补录：该图形是半径 2 的四分之一圆。",
                        },
                    }
                ],
            }
        ),
    )
    updated = next(block for block in content.blocks if block.block_id == target.block_id)
    assert "补录：该图形是半径 2 的四分之一圆。" in updated.content["text"]
    assert updated.content != before
    resolved = next(entry for entry in content.issues if entry.issue_id == issue.issue_id)
    assert resolved.status == "resolved"
    assert resolved.resolution == {
        "kind": "supplement_text",
        "targetBlockId": target.block_id,
        "text": "补录：该图形是半径 2 的四分之一圆。",
    }

    # 补录后（且知识点齐备）确认成功；已确认修订的块内容仍是补录后的正文
    result = _confirm(service, paper_id)
    assert result.state == "confirmed"
    frozen = service.get_revision_content(paper_id, result.paper_revision_id)
    frozen_block = next(
        block for block in frozen.blocks if block.block_id == target.block_id
    )
    assert "补录：该图形是半径 2 的四分之一圆。" in frozen_block.content["text"]


def test_supplement_asset_inserts_referenced_image_block(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, _points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    issue = _blocking_issue(imported)
    target = _target_paragraph(imported)
    stored = harness.assets.store_original(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 64,
        media_type="image/png",
        original_name="补录图.png",
    )
    content = service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 1,
                "issues": [
                    {
                        "issueId": issue.issue_id,
                        "status": "resolved",
                        "resolution": {
                            "kind": "supplement_asset",
                            "targetBlockId": target.block_id,
                            "assetId": stored.blob_key,
                        },
                    }
                ],
            }
        ),
    )
    added = [
        block
        for block in content.blocks
        if block.kind == "image" and block.content.get("assetId") == stored.blob_key
    ]
    assert len(added) == 1
    # 新块与目标块同处置/同归属，并紧跟目标块
    assert added[0].disposition == target.disposition
    assert added[0].item_id == target.item_id
    assert added[0].ordinal == target.ordinal + 1
    assert _confirm(service, paper_id).state == "confirmed"


# --------------------------------------------------------------------------- 形状与内容校验


def test_arbitrary_resolution_json_is_rejected_by_contract(
    tmp_path: Path, harness: PapersHarness
) -> None:
    _service, imported, _points = _prepared(harness, tmp_path)
    issue = _blocking_issue(imported)
    with pytest.raises(Exception) as invalid:
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 1,
                "issues": [
                    {
                        "issueId": issue.issue_id,
                        "status": "resolved",
                        "resolution": {"anything": 1},
                    }
                ],
            }
        )
    assert "resolution" in str(invalid.value)


def test_resolution_missing_fields_rejected_with_locator(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, _points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    issue = _blocking_issue(imported)
    target = _target_paragraph(imported)

    cases = [
        ({"kind": "supplement_text", "targetBlockId": target.block_id}, "text"),
        ({"kind": "supplement_text", "text": "补录"}, "targetBlockId"),
        ({"kind": "supplement_asset", "targetBlockId": target.block_id}, "assetId"),
        ({"kind": "exclude"}, "reason"),
    ]
    for resolution, field in cases:
        with pytest.raises(AppError) as rejected:
            service.patch_draft(
                paper_id,
                PaperDraftPatchRequest.model_validate(
                    {
                        "expectedRevision": 1,
                        "issues": [
                            {
                                "issueId": issue.issue_id,
                                "status": "resolved",
                                "resolution": resolution,
                            }
                        ],
                    }
                ),
            )
        assert rejected.value.status_code == 422
        assert rejected.value.code == "PAPER_ISSUE_RESOLUTION_INVALID"
        fields = [entry["field"] for entry in rejected.value.details["issues"]]
        assert field in fields
    # 全部被拒：问题仍是 open，编辑锁未推进
    view = service.get_revision_content(paper_id, imported.paper.current_revision_id)
    assert view.issues[0].status == "open"
    assert _revision(service, paper_id) == 1


def test_content_loss_issue_cannot_be_excluded(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, _points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    issue = _blocking_issue(imported)
    assert issue.code in ("UNSUPPORTED_OBJECT", "RICH_IMAGE_UNSUPPORTED", "CONTENT_LOSS")

    with pytest.raises(AppError) as rejected:
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {
                    "expectedRevision": 1,
                    "issues": [
                        {
                            "issueId": issue.issue_id,
                            "status": "excluded",
                            "resolution": {"kind": "exclude", "reason": "教师判定无关"},
                        }
                    ],
                }
            ),
        )
    assert rejected.value.code == "PAPER_ISSUE_RESOLUTION_INVALID"
    assert rejected.value.details["issues"][0]["field"] == "kind"

    # 未补录的 blocking 仍然阻断确认（可定位）
    with pytest.raises(AppError) as blocked:
        _confirm(service, paper_id)
    assert blocked.value.code == "PAPER_ISSUE_BLOCKING"
    assert any("UNSUPPORTED_OBJECT" in entry["message"] for entry in blocked.value.details["issues"])


def test_non_content_loss_blocking_issue_can_be_excluded_with_reason(
    tmp_path: Path, harness: PapersHarness
) -> None:
    """题号重复（blocking，非内容损失）允许显式排除（带理由）后放行。"""
    service = harness.service()
    imported = harness.import_docx(
        service, build_paper_docx(tmp_path / "dup.docx", with_duplicate_number=True)
    )
    paper_id = imported.paper.paper_id
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]
    knowledge = {
        "16(1)": [points[0].point_id],
        "16(2)": [points[1].point_id],
        "17": [points[0].point_id],
        "18": [points[1].point_id],
    }
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 0,
                "items": items_payload(imported.revision.items, knowledge=knowledge),
            }
        ),
    )
    with pytest.raises(AppError) as blocked:
        _confirm(service, paper_id)
    assert blocked.value.code == "PAPER_ISSUE_BLOCKING"
    blocking = [
        issue for issue in imported.revision.issues if issue.severity == "blocking"
    ]
    assert {issue.code for issue in blocking} == {"ITEM_QUESTION_NO_DUPLICATE"}

    content = service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 1,
                "issues": [
                    {
                        "issueId": issue.issue_id,
                        "status": "excluded",
                        "resolution": {"kind": "exclude", "reason": "原件重复，教师已核对"},
                    }
                    for issue in blocking
                ],
            }
        ),
    )
    excluded = next(
        entry for entry in content.issues if entry.issue_id == blocking[0].issue_id
    )
    assert excluded.status == "excluded"
    assert excluded.resolution == {"kind": "exclude", "reason": "原件重复，教师已核对"}
    assert _confirm(service, paper_id).state == "confirmed"


def test_supplement_asset_rejects_unreadable_or_unmanaged_keys(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, _points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    issue = _blocking_issue(imported)
    target = _target_paragraph(imported)

    bad_keys = [
        "../../etc/passwd",
        "blobs/" + "A" * 64,  # 大写不是合法受管键
        "blobs/" + "0" * 63,  # 长度不符
        "blobs/" + "f" * 64,  # 形状合法但文件不存在
    ]
    for asset_id in bad_keys:
        with pytest.raises(AppError) as rejected:
            service.patch_draft(
                paper_id,
                PaperDraftPatchRequest.model_validate(
                    {
                        "expectedRevision": 1,
                        "issues": [
                            {
                                "issueId": issue.issue_id,
                                "status": "resolved",
                                "resolution": {
                                    "kind": "supplement_asset",
                                    "targetBlockId": target.block_id,
                                    "assetId": asset_id,
                                },
                            }
                        ],
                    }
                ),
            )
        assert rejected.value.status_code == 422
        assert rejected.value.code == "PAPER_ISSUE_RESOLUTION_INVALID"
        assert rejected.value.details["issues"][0]["field"] == "assetId"


def test_supplement_text_requires_paragraph_target(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, _points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    issue = _blocking_issue(imported)
    table = next(block for block in imported.revision.blocks if block.kind == "table")

    with pytest.raises(AppError) as rejected:
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {
                    "expectedRevision": 1,
                    "issues": [
                        {
                            "issueId": issue.issue_id,
                            "status": "resolved",
                            "resolution": {
                                "kind": "supplement_text",
                                "targetBlockId": table.block_id,
                                "text": "不该写进表格的补录",
                            },
                        }
                    ],
                }
            ),
        )
    assert rejected.value.code == "PAPER_ISSUE_RESOLUTION_INVALID"
    assert rejected.value.details["issues"][0]["field"] == "targetBlockId"
    assert "段落" in rejected.value.details["issues"][0]["message"]


def test_http_route_rejects_free_form_resolution(
    tmp_path: Path, harness: PapersHarness
) -> None:
    app, service = harness.create_app_with_service()
    imported = harness.import_docx(
        service, build_paper_docx(tmp_path / "http.docx", with_unknown_object=True)
    )
    issue = next(
        entry for entry in imported.revision.issues if entry.severity == "blocking"
    )
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.patch(
            f"/api/v1/papers/{imported.paper.paper_id}/draft",
            json={
                "expectedRevision": 0,
                "issues": [
                    {
                        "issueId": issue.issue_id,
                        "status": "resolved",
                        "resolution": {"anything": 1},
                    }
                ],
            },
        )
    assert response.status_code == 422
    # pydantic 校验失败（FastAPI 默认 422 形状）：必须指出 resolution 不能是任意 JSON
    assert "resolution" in response.text


# --------------------------------------------------------------------------- RV04 原卷侧接线


class _NeverCancelled:
    async def cancellation_requested(self) -> bool:
        return False


def test_proposal_snapshot_freezes_fingerprint_and_rejects_drift(
    tmp_path: Path, harness: PapersHarness
) -> None:
    """RV04 原卷侧：创建任务写指纹；执行前比对真实配置指纹，漂移明确失败且零发布。"""
    service, imported, points = _prepared(harness, tmp_path)
    paper_id = imported.paper.paper_id
    leaf = next(item for item in imported.revision.items if item.is_scored)
    reply = json.dumps(
        {
            "items": [
                {
                    "itemId": leaf.item_id,
                    "knowledgePointId": points[0].point_id,
                    "evidence": [leaf.item_id],
                }
            ]
        },
        ensure_ascii=False,
    )
    provider = FakeProvider(replies=[reply])
    _svc, record = harness.run_proposal_job(
        paper_id, expected_revision=1, provider=provider
    )
    assert record.state == "succeeded"
    snapshot = json.loads(
        harness.raw_rows("SELECT model_snapshot_json FROM workflow_jobs")[0][
            "model_snapshot_json"
        ]
    )
    assert snapshot["profileId"] == LOCAL_PROFILE
    assert snapshot["fingerprint"].startswith("sha256:")
    assert FAKE_API_KEY not in json.dumps(snapshot)

    # 漂移：同 profile 的实际模型已换成另一个 → 执行器必须 409，且不调用模型、不发布
    drifted_provider = FakeProvider(replies=[reply])
    drifted = replace(
        make_handle(provider=drifted_provider),
        model_id="DIFFERENT-MODEL",
        config=replace(
            make_handle(provider=drifted_provider).config, modelId="DIFFERENT-MODEL"
        ),
    )
    drift_service = harness.service(
        resolver=FakeResolver({LOCAL_PROFILE: drifted})
    )
    published: list[object] = []
    runner = ProposalRunner(
        resolve_model=drift_service._resolve_model_for_job,  # noqa: SLF001 - 真实接线
        publish_proposal=lambda _conn, draft: published.append(draft),
    )
    frozen = FrozenJob(
        job_id=record.job_id,
        domain="teaching",
        kind="paper_mapping",
        attempt=record.attempt + 1,
        input={"modelProfileId": LOCAL_PROFILE},
        model_snapshot=snapshot,
        input_hash="x",
    )

    async def run(frozen_job: FrozenJob):
        return await runner(frozen_job, _NeverCancelled())

    with pytest.raises(AppError) as drift:
        asyncio.run(run(frozen))
    assert drift.value.code == "MODEL_CONFIG_DRIFT"
    assert drift.value.status_code == 409
    assert published == []
    assert drifted_provider.calls == []

    # 旧任务没有冻结指纹 → 422（要求重新发起，不静默放行）
    with pytest.raises(AppError) as missing:
        asyncio.run(run(replace(frozen, model_snapshot={"profileId": LOCAL_PROFILE})))
    assert missing.value.code == "MODEL_FINGERPRINT_MISSING"
    assert missing.value.status_code == 422
