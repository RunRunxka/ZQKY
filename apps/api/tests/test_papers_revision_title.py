"""B3/G0 · B2-RV11（+ RV02 闸门回归）：修订级标题快照与确认闸门。

覆盖：

- 确认 ``Original Title`` → 新草稿改 ``NEW DRAFT Title`` → 旧修订的内容 API 与
  ``ConfirmedPaperReaderAdapter`` 仍返回 ``Original Title``（逐字节一致），新草稿显示新标题；
- 修订级快照来源标注（``revision``）；空快照按 500 ``PAPER_ROW_CORRUPT`` 处理，
  不回退到可变 ``papers.title``；
- 确认闸门：空题面（``content={}``）与缺失共同材料/资产被逐条拒绝，修正后放行。

DOCX 样本程序化生成；临时目录隔离库；不触正式数据与网络。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.papers import PaperConfirmRequest, PaperDraftPatchRequest
from app.core.exceptions import AppError
from tests.papers_support import (
    PapersHarness,
    build_paper_docx,
    items_payload,
)

ORIGINAL_TITLE = "Original Title"
NEW_TITLE = "NEW DRAFT Title"


@pytest.fixture()
def harness(tmp_path: Path) -> PapersHarness:
    return PapersHarness(tmp_path)


def _revision(service, paper_id: str) -> int:
    return service.get_paper(paper_id).revision


def _confirm(service, paper_id: str, *, submission: str = "title-confirm"):
    return service.confirm(
        paper_id,
        PaperConfirmRequest.model_validate(
            {"expectedRevision": _revision(service, paper_id), "submissionId": submission}
        ),
    )


def _confirmed_sample(harness: PapersHarness, tmp_path: Path):
    service = harness.service()
    imported = harness.import_docx(
        service, build_paper_docx(tmp_path / "sample.docx"), title=ORIGINAL_TITLE
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
    confirmed = _confirm(service, paper_id)
    return service, imported, points, confirmed


# --------------------------------------------------------------------------- 标题快照


def test_original_title_survives_new_draft_rename(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, _points, confirmed = _confirmed_sample(harness, tmp_path)
    paper_id = imported.paper.paper_id
    revision_id = confirmed.paper_revision_id

    before_view = service.get_revision_content(paper_id, revision_id)
    before_reader = service.confirmed_reader().read(revision_id)
    assert before_view.title == ORIGINAL_TITLE
    assert before_reader.title == ORIGINAL_TITLE

    # 改已确认卷：自动新建草稿修订并改名
    draft = service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate(
            {"expectedRevision": 2, "title": NEW_TITLE}
        ),
    )
    assert draft.state == "draft"
    assert draft.version == 2
    assert draft.title == NEW_TITLE
    assert draft.paper_revision_id != revision_id
    assert service.get_paper(paper_id).title == NEW_TITLE

    # 固定修订的标题快照不随后续草稿改名而变（内容 API 与 reader 一致）
    after_view = service.get_revision_content(paper_id, revision_id)
    after_reader = service.confirmed_reader().read(revision_id)
    assert after_view.title == ORIGINAL_TITLE
    assert after_reader.title == ORIGINAL_TITLE
    assert after_view.model_dump() == before_view.model_dump()
    assert after_reader == before_reader


def test_title_snapshot_rows_are_labelled(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service, imported, _points, confirmed = _confirmed_sample(harness, tmp_path)
    paper_id = imported.paper.paper_id
    rows = harness.raw_rows(
        "SELECT id, version, state, title_snapshot, title_snapshot_source "
        "FROM paper_revisions ORDER BY version"
    )
    assert rows and all(row["title_snapshot"] == ORIGINAL_TITLE for row in rows)
    assert all(row["title_snapshot_source"] == "revision" for row in rows)

    draft = service.patch_draft(
        paper_id, PaperDraftPatchRequest.model_validate({"expectedRevision": 2, "title": NEW_TITLE})
    )
    rows = harness.raw_rows(
        "SELECT id, title_snapshot, title_snapshot_source FROM paper_revisions ORDER BY version"
    )
    by_id = {row["id"]: row for row in rows}
    assert by_id[confirmed.paper_revision_id]["title_snapshot"] == ORIGINAL_TITLE
    assert by_id[draft.paper_revision_id]["title_snapshot"] == NEW_TITLE
    assert by_id[draft.paper_revision_id]["title_snapshot_source"] == "revision"


def test_empty_title_snapshot_is_corrupt_not_paper_title(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service = harness.service()
    imported = harness.import_docx(
        service, build_paper_docx(tmp_path / "sample.docx"), title=ORIGINAL_TITLE
    )
    paper_id = imported.paper.paper_id
    revision_id = imported.paper.current_revision_id
    # 模拟"绕过迁移/行损坏"：把**草稿**修订的快照清空后，读取必须 500 CORRUPT，
    # 而不是回退到可变 papers.title
    harness.raw_execute(
        "UPDATE paper_revisions SET title_snapshot = '' WHERE id = ?", [revision_id]
    )
    harness.raw_execute(
        "UPDATE papers SET title = ? WHERE id = ?", ["改名后的可变标题", paper_id]
    )
    with pytest.raises(AppError) as corrupt:
        service.get_revision_content(paper_id, revision_id)
    assert corrupt.value.code == "PAPER_ROW_CORRUPT"
    assert corrupt.value.status_code == 500
    with pytest.raises(AppError) as reader_corrupt:
        service.confirmed_reader().read(revision_id)
    assert reader_corrupt.value.code == "PAPER_ROW_CORRUPT"


# --------------------------------------------------------------------------- 确认闸门（题面/材料）


def _item_payload(content_view, *, knowledge: dict[str, list[str]]):
    return items_payload(content_view.items, knowledge=knowledge)


def test_confirm_rejects_empty_stem_and_restores_after_fix(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service = harness.service()
    imported = harness.import_docx(service, build_paper_docx(tmp_path / "sample.docx"))
    paper_id = imported.paper.paper_id
    point = harness.add_point("K1", "二次函数")
    knowledge = {question_no: [point.point_id] for question_no in ("16(1)", "16(2)", "17", "18")}
    payload = _item_payload(imported.revision, knowledge=knowledge)
    for entry in payload:
        if entry["isScored"]:
            entry["content"] = {}
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate({"expectedRevision": 0, "items": payload}),
    )
    with pytest.raises(AppError) as empty_stem:
        _confirm(service, paper_id)
    assert empty_stem.value.code == "ITEM_STEM_MISSING"
    assert empty_stem.value.status_code == 422
    rows = {entry["row"] for entry in empty_stem.value.details["issues"]}
    assert rows == {2, 3, 4, 5}
    assert all(entry["field"] == "content" for entry in empty_stem.value.details["issues"])

    # 修正：恢复真实题面后再确认
    fixed = _item_payload(
        service.get_revision_content(paper_id, imported.paper.current_revision_id),
        knowledge=knowledge,
    )
    for entry in fixed:
        entry["content"] = dict(
            next(
                item
                for item in imported.revision.items
                if item.item_id == entry["itemId"]
            ).content
        )
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate({"expectedRevision": 1, "items": fixed}),
    )
    assert _confirm(service, paper_id).state == "confirmed"


def test_confirm_rejects_missing_shared_material_and_asset(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service = harness.service()
    imported = harness.import_docx(service, build_paper_docx(tmp_path / "sample.docx"))
    paper_id = imported.paper.paper_id
    point = harness.add_point("K1", "二次函数")
    knowledge = {question_no: [point.point_id] for question_no in ("16(1)", "16(2)", "17", "18")}
    payload = _item_payload(imported.revision, knowledge=knowledge)
    for entry in payload:
        if entry["questionNo"] != "16(1)":
            continue
        entry["content"] = dict(entry["content"])
        entry["content"]["sharedMaterials"] = [
            {
                "id": "material-99",
                "blocks": [
                    {"id": "p99", "kind": "paragraph", "text": "已被删除的共同材料"}
                ],
            }
        ]
        entry["content"]["assets"] = [
            {
                "assetId": "blobs/" + "9" * 64,
                "sha256": "9" * 64,
                "mediaType": "image/png",
            }
        ]
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate({"expectedRevision": 0, "items": payload}),
    )
    with pytest.raises(AppError) as missing:
        _confirm(service, paper_id)
    assert missing.value.code == "ITEM_MATERIAL_MISSING"
    assert missing.value.status_code == 422
    assert missing.value.details["issues"][0]["row"] == 2  # 16(1) 的 ordinal
    message = missing.value.details["issues"][0]["message"]
    assert "p99" in message and ("9" * 64) in message

    # 只缺共同材料（资产正常）也要拒绝；修正为真实材料后放行
    payload = _item_payload(
        service.get_revision_content(paper_id, imported.paper.current_revision_id),
        knowledge=knowledge,
    )
    real = next(item for item in imported.revision.items if item.question_no == "16(1)")
    for entry in payload:
        entry["content"] = dict(entry["content"])
        if entry["questionNo"] == "16(1)":
            entry["content"]["sharedMaterials"] = real.content["sharedMaterials"]
            entry["content"]["assets"] = real.content["assets"]
    service.patch_draft(
        paper_id,
        PaperDraftPatchRequest.model_validate({"expectedRevision": 1, "items": payload}),
    )
    assert _confirm(service, paper_id).state == "confirmed"
