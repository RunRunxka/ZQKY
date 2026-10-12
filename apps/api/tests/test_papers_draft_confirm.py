"""T40 草稿与确认验收（B2 / A3+A4）：整表替换、校验定位、确认闸门与确认后不可变。

全部用 ``tmp_path`` 隔离库；确认闸门逐项拒绝后再修正成功；确认后绕过服务直写由
DB 触发器拒绝；改已确认卷 = 新建 draft 修订（旧修订逐字节不变）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.contracts.papers import (
    PaperConfirmRequest,
    PaperDraftPatchRequest,
)
from app.core.exceptions import AppError
from app.services.papers.service import _parse_score_units
from tests.papers_support import (
    SUBJECT_ID,
    PapersHarness,
    blocks_payload,
    build_paper_docx,
    issues_payload,
    items_payload,
    items_payload_from_json,
)


@pytest.fixture()
def harness(tmp_path: Path) -> PapersHarness:
    return PapersHarness(tmp_path)


def _import(harness: PapersHarness, tmp_path: Path, *, name: str = "sample.docx", **kwargs):
    docx = build_paper_docx(tmp_path / name, **kwargs)
    service = harness.service()
    return service, harness.import_docx(service, docx)


def _knowledge_map(points) -> dict[str, list[str]]:
    return {
        "16(1)": [points[0].point_id],
        "16(2)": [points[1].point_id],
        "17": [points[0].point_id],
        "18": [points[1].point_id],
    }


def _patch_payload(view, *, revision: int, **kwargs) -> PaperDraftPatchRequest:
    payload = {
        "expectedRevision": revision,
        "items": items_payload(view.revision.items, **kwargs),
    }
    return PaperDraftPatchRequest.model_validate(payload)


# --------------------------------------------------------------------------- 分值解析


def test_score_units_parsing_rules() -> None:
    assert _parse_score_units("2.5") == 250
    assert _parse_score_units("0.01") == 1
    assert _parse_score_units("12") == 1200
    for bad in ("0", "0.00", "-1.5", "1.234", "abc", "10000"):
        with pytest.raises(AppError) as excinfo:
            _parse_score_units(bad)
        assert excinfo.value.code == "ITEM_SCORE_INVALID"
        assert excinfo.value.status_code == 422


# --------------------------------------------------------------------------- 草稿 PATCH


def test_patch_replaces_items_and_bumps_revision(tmp_path: Path, harness: PapersHarness) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]

    content = service.patch_draft(
        paper_id,
        _patch_payload(imported, revision=0, knowledge=_knowledge_map(points)),
    )
    assert content.version == 1
    assert content.state == "draft"
    assert content.total_score_units == 2100
    assert service.get_paper(paper_id).revision == 1
    leaf = next(item for item in content.items if item.question_no == "16(1)")
    assert [(k.knowledge_point_id, k.source, k.role) for k in leaf.knowledge] == [
        (points[0].point_id, "human", "primary")
    ]
    # 关联冻结了知识点当前修订与名称快照
    assert leaf.knowledge[0].knowledge_revision_id == points[0].revision_id
    assert leaf.knowledge[0].knowledge_name_snapshot == "二次函数"
    assert harness.count("paper_item_knowledge", "source = 'human'") == 4

    # 旧 expectedRevision 一律 409 + currentRevision
    with pytest.raises(AppError) as stale:
        service.patch_draft(paper_id, _patch_payload(imported, revision=0))
    assert stale.value.code == "PAPER_REVISION_STALE"
    assert stale.value.status_code == 409
    assert stale.value.details["currentRevision"] == 1


def test_patch_rebuilds_items_drops_removed_and_reuses_ids(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    kept = next(item for item in imported.revision.items if item.question_no == "17")
    new_items = [
        {
            "itemId": kept.item_id,
            "questionNo": kept.question_no,
            "ordinal": 1,
            "isScored": True,
            "maxScore": "6",
            "content": dict(kept.content),
        },
        {
            "questionNo": "20",
            "ordinal": 2,
            "isScored": True,
            "maxScore": "4.5",
        },
    ]
    content = service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {"expectedRevision": 0, "items": new_items, "title": "改名后的卷"}
        ),
    )
    assert [item.question_no for item in content.items] == ["17", "20"]
    assert content.items[0].item_id == kept.item_id
    assert content.total_score_units == 1050
    assert content.title == "改名后的卷"
    # 被删题目的块不再悬空引用：重置为 unassigned 且问题清单可见
    stale_blocks = [block for block in content.blocks if block.disposition == "item"]
    assert all(block.item_id == kept.item_id for block in stale_blocks)
    assert harness.count(
        "paper_issues", "code = 'PAPER_BLOCK_ITEM_RESET' AND severity = 'warning'"
    ) == 1


def test_patch_rejects_invalid_item_trees_with_locators(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id

    def patch(items, expected_revision: int = 0):
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {"expectedRevision": expected_revision, "items": items}
            ),
        )

    base = {
        "questionNo": "1",
        "ordinal": 1,
        "isScored": True,
        "maxScore": "5",
        "content": {},
    }
    with pytest.raises(AppError) as duplicate:
        patch([base, {**base, "ordinal": 2, "questionNo": "1"}])
    assert duplicate.value.code == "ITEM_QUESTION_NO_DUPLICATE"
    assert duplicate.value.details["issues"][0]["row"] == 1
    assert duplicate.value.details["issues"][0]["field"] == "questionNo"

    with pytest.raises(AppError) as ordinal:
        patch([base, {**base, "questionNo": "2"}])
    assert ordinal.value.code == "ITEM_ORDINAL_DUPLICATE"

    with pytest.raises(AppError) as cross_revision_parent:
        patch([{**base, "parentItemId": "not-in-this-revision"}])
    assert cross_revision_parent.value.code == "ITEM_PARENT_INVALID"
    assert cross_revision_parent.value.details["issues"][0]["field"] == "parentItemId"

    # 环：A 的父是 B、B 的父是 A（整表替换后成环；客户端为新建题目指定 id）
    with pytest.raises(AppError) as cycle:
        patch(
            [
                {
                    **base,
                    "itemId": "item-a",
                    "questionNo": "1",
                    "isScored": False,
                    "maxScore": None,
                    "parentItemId": "item-b",
                },
                {
                    **base,
                    "itemId": "item-b",
                    "questionNo": "2",
                    "ordinal": 2,
                    "isScored": False,
                    "maxScore": None,
                    "parentItemId": "item-a",
                },
            ]
        )
    assert cycle.value.code == "ITEM_CYCLE"
    assert cycle.value.details["issues"][0]["field"] == "parentItemId"

    # 非叶子计分：新建父容器 + 子题
    with pytest.raises(AppError) as leaf_only:
        patch(
            [
                {**base, "itemId": "item-parent", "questionNo": "1", "maxScore": "5"},
                {
                    **base,
                    "itemId": "item-child",
                    "questionNo": "1(1)",
                    "ordinal": 2,
                    "maxScore": "2",
                    "parentItemId": "item-parent",
                },
            ]
        )
    assert leaf_only.value.code == "SCORED_ITEM_MUST_BE_LEAF"
    assert leaf_only.value.details["issues"][0]["field"] == "isScored"

    # 分值非法：负值/三位小数在契约层就被拒（422）
    with pytest.raises(Exception) as pattern:
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 0,
                "items": [{**base, "maxScore": "-1"}],
            }
        )
    assert type(pattern.value).__name__ == "ValidationError"

    with pytest.raises(Exception) as decimals:
        PaperDraftPatchRequest.model_validate(
            {"expectedRevision": 0, "items": [{**base, "maxScore": "1.234"}]}
        )
    assert type(decimals.value).__name__ == "ValidationError"


def test_patch_score_rules_and_container_without_score(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    item = next(i for i in imported.revision.items if i.question_no == "17")

    # 计分题缺 maxScore
    with pytest.raises(AppError) as missing:
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {
                    "expectedRevision": 0,
                    "items": [
                        {
                            "itemId": item.item_id,
                            "questionNo": item.question_no,
                            "ordinal": 1,
                            "isScored": True,
                            "content": {},
                        }
                    ],
                }
            ),
        )
    assert missing.value.code == "ITEM_SCORE_INVALID"
    assert missing.value.details["issues"][0]["field"] == "maxScore"

    # 容器带 maxScore
    with pytest.raises(AppError) as container:
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {
                    "expectedRevision": 0,
                    "items": [
                        {
                            "questionNo": "16",
                            "ordinal": 1,
                            "isScored": False,
                            "maxScore": "12",
                            "content": {},
                        }
                    ],
                }
            ),
        )
    assert container.value.code == "ITEM_SCORE_INVALID"
    assert container.value.details["issues"][0]["field"] == "maxScore"

    # 有子题的父容器计分（客户端为新建题目指定 id 以表达父子关系）
    with pytest.raises(AppError) as scored_parent:
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {
                    "expectedRevision": 0,
                    "items": [
                        {
                            "itemId": "new-parent",
                            "questionNo": "16",
                            "ordinal": 1,
                            "isScored": True,
                            "maxScore": "12",
                            "content": {},
                        },
                        {
                            "itemId": "new-child",
                            "questionNo": "16(1)",
                            "ordinal": 2,
                            "isScored": True,
                            "maxScore": "4",
                            "parentItemId": "new-parent",
                            "content": {},
                        },
                    ],
                }
            ),
        )
    assert scored_parent.value.code == "SCORED_ITEM_MUST_BE_LEAF"

    # 复用其他修订已占用的 itemId（题目 id 是全局主键，不能跨修订复用）
    other = harness.import_docx(service, build_paper_docx(tmp_path / "other.docx"), title="另一份")
    foreign_id = other.revision.items[0].item_id
    with pytest.raises(AppError) as unknown_id:
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {
                    "expectedRevision": 0,
                    "items": [
                        {
                            "itemId": foreign_id,
                            "questionNo": "1",
                            "ordinal": 1,
                            "isScored": True,
                            "maxScore": "5",
                            "content": {},
                        }
                    ],
                }
            ),
        )
    assert unknown_id.value.code == "ITEM_ID_INVALID"
    assert unknown_id.value.details["issues"][0]["field"] == "itemId"


def test_patch_validates_knowledge_references_across_library(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    same_subject = harness.add_point("K1", "二次函数")
    archived = harness.add_point("K2", "旧知识点")
    harness.archive_point(archived.point_id)
    other = harness.add_point("P1", "力的合成", subject_id="physics")

    def patch(point_id: str):
        service.patch_draft(
            paper_id,
            _patch_payload(
                imported,
                revision=0,
                knowledge={"16(1)": [point_id]},
            ),
        )

    for bad, label in (
        ("missing-point", "不存在"),
        (archived.point_id, "已归档"),
        (other.point_id, "跨学科"),
    ):
        with pytest.raises(AppError) as excinfo:
            patch(bad)
        assert excinfo.value.code == "KNOWLEDGE_REFERENCE_INVALID", label
        assert excinfo.value.status_code == 422
        assert excinfo.value.details["issues"][0]["field"] == "knowledgePointId"

    assert service.get_paper(paper_id).revision == 0  # 失败不改编辑锁
    patch(same_subject.point_id)
    assert service.get_paper(paper_id).revision == 1


def test_patch_blocks_and_issues_dispositions(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported = _import(harness, tmp_path, with_unknown_object=True)
    paper_id = imported.paper.paper_id
    blocks = blocks_payload(imported.revision.blocks)
    image = next(
        block for block in imported.revision.blocks if block.kind == "image"
    )
    # 排除块必须给理由
    with pytest.raises(AppError) as no_reason:
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {
                    "expectedRevision": 0,
                    "blocks": [{"blockId": image.block_id, "disposition": "excluded"}],
                }
            ),
        )
    assert no_reason.value.code == "PAPER_BLOCK_INVALID"

    with pytest.raises(AppError) as unknown_block:
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {
                    "expectedRevision": 0,
                    "blocks": [
                        {"blockId": "no-such-block", "disposition": "unassigned"}
                    ],
                }
            ),
        )
    assert unknown_block.value.code == "PAPER_BLOCK_INVALID"

    # 阻断问题必须给 resolution 才能解决
    blocking = next(
        issue for issue in imported.revision.issues if issue.severity == "blocking"
    )
    with pytest.raises(AppError) as needs_resolution:
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {
                    "expectedRevision": 0,
                    "issues": [{"issueId": blocking.issue_id, "status": "resolved"}],
                }
            ),
        )
    assert needs_resolution.value.code == "PAPER_ISSUE_BLOCKING"
    assert needs_resolution.value.details["issues"][0]["field"] == "resolution"

    with pytest.raises(AppError) as unknown_issue:
        service.patch_draft(
            paper_id,
            PaperDraftPatchRequest.model_validate(
                {
                    "expectedRevision": 0,
                    "issues": [{"issueId": "no-such-issue", "status": "resolved"}],
                }
            ),
        )
    assert unknown_issue.value.code == "PAPER_ISSUE_NOT_FOUND"

    content = service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 0,
                "blocks": blocks,
                "issues": issues_payload(
                    imported.revision.issues,
                    target_block_id=next(
                        block.block_id
                        for block in imported.revision.blocks
                        if block.kind == "paragraph"
                    ),
                ),
            }
        ),
    )
    assert content.state == "draft"
    updated = next(block for block in content.blocks if block.block_id == image.block_id)
    assert updated.disposition == "shared_material"  # 未提供的块保持原样
    assert all(issue.status == "resolved" for issue in content.issues)


def test_patch_rejects_archived_paper(tmp_path: Path, harness: PapersHarness) -> None:
    service, imported = _import(harness, tmp_path)
    harness.raw_execute("UPDATE papers SET status = 'archived' WHERE id = ?", [imported.paper.paper_id])
    with pytest.raises(AppError) as archived:
        service.patch_draft(imported.paper.paper_id, _patch_payload(imported, revision=0))
    assert archived.value.code == "PAPER_NOT_EDITABLE"
    assert archived.value.status_code == 409


# --------------------------------------------------------------------------- 确认闸门


def _confirm(service, paper_id: str, *, submission: str = "s-1"):
    revision = service.get_paper(paper_id).revision
    return service.confirm(
        paper_id,
        PaperConfirmRequest.model_validate(
            {"expectedRevision": revision, "submissionId": submission}
        ),
    )


def test_confirm_requires_knowledge_for_every_scored_leaf(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    with pytest.raises(AppError) as missing:
        _confirm(service, paper_id)
    assert missing.value.code == "ITEM_KNOWLEDGE_MISSING"
    assert missing.value.status_code == 422
    rows = {issue["row"] for issue in missing.value.details["issues"]}
    assert rows == {2, 3, 4, 5}  # 16(1)/16(2)/17/18 的 ordinal
    assert service.get_paper(paper_id).current_state == "draft"


def test_confirm_requires_all_blocks_assigned(tmp_path: Path, harness: PapersHarness) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]
    service.patch_draft(
        paper_id, _patch_payload(imported, revision=0, knowledge=_knowledge_map(points))
    )
    image = next(block for block in imported.revision.blocks if block.kind == "image")
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 1,
                "blocks": [{"blockId": image.block_id, "disposition": "unassigned"}],
            }
        ),
    )
    with pytest.raises(AppError) as unassigned:
        _confirm(service, paper_id)
    assert unassigned.value.code == "PAPER_BLOCK_UNASSIGNED"
    assert unassigned.value.details["issues"][0]["row"] == image.ordinal


def test_confirm_requires_no_open_blocking_issue(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported = _import(harness, tmp_path, with_unknown_object=True)
    paper_id = imported.paper.paper_id
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]
    service.patch_draft(
        paper_id, _patch_payload(imported, revision=0, knowledge=_knowledge_map(points))
    )
    with pytest.raises(AppError) as blocking:
        _confirm(service, paper_id)
    assert blocking.value.code == "PAPER_ISSUE_BLOCKING"
    assert any("UNSUPPORTED_OBJECT" in issue["message"] for issue in blocking.value.details["issues"])

    # 显式补录（结构化处置；内容损失类问题不允许仅以排除放行）后放行
    supplement_target = next(
        block for block in imported.revision.blocks if block.kind == "paragraph"
    )
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
                            "targetBlockId": issue.block_id or supplement_target.block_id,
                            "text": "教师已补录原图中缺失的内容（测试样本）。",
                        },
                    }
                    for issue in imported.revision.issues
                    if issue.severity == "blocking"
                ],
            }
        ),
    )
    result = _confirm(service, paper_id)
    assert result.state == "confirmed"


def test_confirm_requires_positive_matching_total(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]
    service.patch_draft(
        paper_id, _patch_payload(imported, revision=0, knowledge=_knowledge_map(points))
    )
    revision_id = service.get_paper(paper_id).current_revision_id
    # 绕过服务改总分（草稿容差），确认闸门必须拒绝
    harness.raw_execute(
        "UPDATE paper_revisions SET total_score_units = 999 WHERE id = ?", [revision_id]
    )
    with pytest.raises(AppError) as mismatch:
        _confirm(service, paper_id)
    assert mismatch.value.code == "PAPER_TOTAL_MISMATCH"

    # 全部不计分 → NO_SCORED_ITEMS
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {
                "expectedRevision": 1,
                "items": items_payload(
                    imported.revision.items,
                    score_overrides={key: None for key in ("16(1)", "16(2)", "17", "18")},
                ),
            }
        ),
    )
    with pytest.raises(AppError) as none_scored:
        _confirm(service, paper_id)
    assert none_scored.value.code == "NO_SCORED_ITEMS"


def test_confirm_succeeds_then_replays_and_conflicts(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]
    service.patch_draft(
        paper_id, _patch_payload(imported, revision=0, knowledge=_knowledge_map(points))
    )
    result = _confirm(service, paper_id, submission="sub-1")
    assert result.state == "confirmed"
    assert result.total_score_units == 2100
    assert result.scored_leaf_count == 4
    assert result.replayed is False

    paper = service.get_paper(paper_id)
    assert paper.revision == 2  # 确认后编辑锁 +1
    assert paper.current_state == "confirmed"
    assert paper.blocking_issue_count == 0
    revision_row = harness.raw_rows(
        "SELECT * FROM paper_revisions WHERE id = ?", [result.paper_revision_id]
    )[0]
    assert revision_row["state"] == "confirmed"
    assert revision_row["confirmed_at"]

    # 同一 submissionId 同载荷重放：返回原结果、不再执行
    replay = service.confirm(
        paper_id,
        PaperConfirmRequest.model_validate(
            {"expectedRevision": 1, "submissionId": "sub-1"}
        ),
    )
    assert replay.replayed is True
    assert replay.paper_revision_id == result.paper_revision_id
    assert service.get_paper(paper_id).revision == 2
    assert harness.count("command_submissions", "operation = 'paper.confirm'") == 1

    # 同 submissionId 不同载荷 → 409 SUBMISSION_CONFLICT
    with pytest.raises(AppError) as conflict:
        service.confirm(
            paper_id,
            PaperConfirmRequest.model_validate(
                {"expectedRevision": 2, "submissionId": "sub-1"}
            ),
        )
    assert conflict.value.code == "SUBMISSION_CONFLICT"

    # 再次确认（新 submissionId）→ 409 PAPER_NOT_EDITABLE
    with pytest.raises(AppError) as repeat:
        _confirm(service, paper_id, submission="sub-2")
    assert repeat.value.code == "PAPER_NOT_EDITABLE"


# --------------------------------------------------------------------------- 确认后不可变


def test_confirmed_revision_is_immutable_against_direct_writes(
    tmp_path: Path, harness: PapersHarness
) -> None:
    # 带未知对象的样本：确认后修订里仍有 paper_issues 行，DELETE 保护才可能被检验
    service, imported = _import(harness, tmp_path, with_unknown_object=True)
    paper_id = imported.paper.paper_id
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]
    service.patch_draft(
        paper_id, _patch_payload(imported, revision=0, knowledge=_knowledge_map(points))
    )
    supplement_target = next(
        block for block in imported.revision.blocks if block.kind == "paragraph"
    )
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
                            "targetBlockId": issue.block_id or supplement_target.block_id,
                            "text": "教师已补录原图中缺失的内容（测试样本）。",
                        },
                    }
                    for issue in imported.revision.issues
                    if issue.severity == "blocking"
                ],
            }
        ),
    )
    result = _confirm(service, paper_id)
    revision_id = result.paper_revision_id

    attempts = [
        (
            "UPDATE paper_items SET question_no = 'x' WHERE paper_revision_id = ?",
            [revision_id],
        ),
        ("DELETE FROM paper_items WHERE paper_revision_id = ?", [revision_id]),
        (
            "UPDATE paper_source_blocks SET disposition = 'excluded', exclude_reason = 'x' "
            "WHERE paper_revision_id = ?",
            [revision_id],
        ),
        ("DELETE FROM paper_source_blocks WHERE paper_revision_id = ?", [revision_id]),
        ("DELETE FROM paper_issues WHERE paper_revision_id = ?", [revision_id]),
        (
            "UPDATE paper_revisions SET total_score_units = 1 WHERE id = ?",
            [revision_id],
        ),
        ("DELETE FROM paper_revisions WHERE id = ?", [revision_id]),
    ]
    for sql, params in attempts:
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            harness.raw_execute(sql, params)
        assert "IMMUTABLE_REVISION" in str(excinfo.value), sql

    # 直写 confirmed 修订（绕过确认闸门）也被触发器拒绝
    with pytest.raises(sqlite3.IntegrityError) as sealed:
        harness.raw_execute(
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
            "total_score_units, state, confirmed_at, created_at) "
            "VALUES ('r-x', ?, 99, ?, 100, 'confirmed', '2030-01-01T00:00:00Z', "
            "'2030-01-01T00:00:00Z')",
            [paper_id, harness.raw_rows("SELECT source_file_id FROM paper_revisions")[0]["source_file_id"]],
        )
    assert "USE_CONFIRM_TRANSITION" in str(sealed.value)
    # 触发器兜底拒绝后数据保持原样
    assert harness.count("paper_revisions", "id = 'r-x'") == 0
    assert harness.count("paper_items", "paper_revision_id = ?", [revision_id]) == 5
    assert harness.count("paper_issues", "paper_revision_id = ?", [revision_id]) >= 1


def test_edit_confirmed_paper_forks_new_draft_revision(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]
    service.patch_draft(
        paper_id, _patch_payload(imported, revision=0, knowledge=_knowledge_map(points))
    )
    confirmed = _confirm(service, paper_id)
    frozen_revision = confirmed.paper_revision_id
    frozen_items = harness.raw_rows(
        "SELECT * FROM paper_items WHERE paper_revision_id = ? ORDER BY ordinal",
        [frozen_revision],
    )
    frozen_blocks = harness.raw_rows(
        "SELECT * FROM paper_source_blocks WHERE paper_revision_id = ? ORDER BY ordinal",
        [frozen_revision],
    )
    frozen_issues = harness.raw_rows(
        "SELECT * FROM paper_issues WHERE paper_revision_id = ? ORDER BY rowid",
        [frozen_revision],
    )

    # 改已确认卷：自动新建 draft 修订并应用本次 patch
    new_content = service.patch_draft(
        paper_id,
        _patch_payload(imported, revision=2, knowledge=_knowledge_map(points)),
    )
    assert new_content.state == "draft"
    assert new_content.version == 2
    assert new_content.paper_revision_id != frozen_revision
    assert len(new_content.items) == 5
    assert [k.source for item in new_content.items for k in item.knowledge] == ["human"] * 4
    paper = service.get_paper(paper_id)
    assert paper.current_revision_id == new_content.paper_revision_id
    assert paper.current_state == "draft"
    assert paper.revision == 3

    # 旧修订逐字节不变（含子记录）
    assert harness.raw_rows(
        "SELECT * FROM paper_items WHERE paper_revision_id = ? ORDER BY ordinal",
        [frozen_revision],
    ) == frozen_items
    assert harness.raw_rows(
        "SELECT * FROM paper_source_blocks WHERE paper_revision_id = ? ORDER BY ordinal",
        [frozen_revision],
    ) == frozen_blocks
    assert harness.raw_rows(
        "SELECT * FROM paper_issues WHERE paper_revision_id = ? ORDER BY rowid",
        [frozen_revision],
    ) == frozen_issues
    assert harness.raw_rows(
        "SELECT state, confirmed_at FROM paper_revisions WHERE id = ?", [frozen_revision]
    )[0]["state"] == "confirmed"

    # 新草稿修订的块 id 带本修订命名空间，且内容可读
    assert all(
        block.block_id.startswith(f"{new_content.paper_revision_id}:")
        for block in new_content.blocks
    )


def test_confirm_over_http_end_to_end(tmp_path: Path) -> None:
    harness = PapersHarness(tmp_path)
    harness.add_point("K1", "二次函数")
    harness.add_point("K2", "单调性")
    app, _service = harness.create_app_with_service(provider=None)
    docx = build_paper_docx(tmp_path / "sample.docx")
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        imported = client.post(
            "/api/v1/paper-imports",
            files={"file": ("sample.docx", docx.read_bytes(), "application/octet-stream")},
            data={"subjectId": SUBJECT_ID},
        ).json()
        paper_id = imported["paper"]["paperId"]
        # 契约层拒绝负分值（422）
        bad = client.patch(
            f"/api/v1/papers/{paper_id}/draft",
            json={
                "expectedRevision": 0,
                "items": [
                    {"questionNo": "1", "ordinal": 1, "isScored": True, "maxScore": "-1"}
                ],
            },
        )
        assert bad.status_code == 422
        assert bad.json()["code"] == "INVALID_REQUEST"

        content = client.get(
            f"/api/v1/papers/{paper_id}/revisions/"
            f"{imported['revision']['paperRevisionId']}/content"
        ).json()
        knowledge = {
            "16(1)": [harness.add_point("K3", "顶点").point_id],
            "16(2)": [harness.add_point("K4", "单调").point_id],
            "17": [harness.add_point("K5", "方程").point_id],
            "18": [harness.add_point("K6", "对称轴").point_id],
        }
        patch = client.patch(
            f"/api/v1/papers/{paper_id}/draft",
            json={
                "expectedRevision": 0,
                "items": items_payload_from_json(content["items"], knowledge=knowledge),
            },
        )
        assert patch.status_code == 200, patch.text

        stale = client.post(
            f"/api/v1/papers/{paper_id}/confirm",
            json={"expectedRevision": 0, "submissionId": "http-1"},
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "PAPER_REVISION_STALE"
        assert stale.json()["details"]["currentRevision"] == 1

        confirmed = client.post(
            f"/api/v1/papers/{paper_id}/confirm",
            json={"expectedRevision": 1, "submissionId": "http-1"},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["state"] == "confirmed"
        assert confirmed.json()["scoredLeafCount"] == 4
        assert confirmed.json()["totalScoreUnits"] == 2100
