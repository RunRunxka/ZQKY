"""B3/G0 · B2-RV03：原文块正文与受控资产内容读取。

覆盖：

- 无题号文档（``items=[]``）的原文块也必须带持久化正文（HTTP 与本地路径一致）；
- 未归属/公式/合并表格/图片块的 ``PaperSourceBlockView.content`` 齐备且与库内一致；
- ``GET /papers/{id}/revisions/{rid}/assets/{assetId}/content`` 只放行**本修订**图片块
  引用过的受管键（正向读真实字节 + 正确 media type；非法键/未引用/越修订被拒）。

不读正式数据目录；DOCX 样本由 ``tests.papers_support`` 程序化生成。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.contracts.papers import PaperConfirmRequest, PaperDraftPatchRequest
from app.core.exceptions import AppError
from tests.papers_support import (
    MATERIAL_BODY,
    PNG_BYTES,
    PapersHarness,
    build_no_question_docx,
    build_paper_docx,
    items_payload,
)

NEEDLE = "这是一份没有题号的文档"


@pytest.fixture()
def harness(tmp_path: Path) -> PapersHarness:
    return PapersHarness(tmp_path)


def test_no_question_document_blocks_expose_persisted_content(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service = harness.service()
    imported = harness.import_docx(service, build_no_question_docx(tmp_path / "none.docx"))
    assert imported.revision.items == []
    assert imported.revision.blocks, "无题号文档仍应有原文块"

    for block in imported.revision.blocks:
        assert block.disposition == "unassigned"
        assert block.content, f"块 {block.block_id} 没有正文"
        assert isinstance(block.content.get("id"), str)
    dumped = json.dumps(
        imported.revision.model_dump(mode="json", by_alias=True), ensure_ascii=False
    )
    assert NEEDLE in dumped
    assert NEEDLE in json.dumps(
        [block.content for block in imported.revision.blocks], ensure_ascii=False
    )

    table = next(block for block in imported.revision.blocks if block.kind == "table")
    assert table.content["cells"][0]["text"] == "甲"


def test_block_views_match_persisted_rows_for_all_kinds(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service = harness.service()
    imported = harness.import_docx(
        service, build_paper_docx(tmp_path / "sample.docx", with_unknown_object=True)
    )
    rows = harness.raw_rows(
        "SELECT id, kind, block_json, disposition FROM paper_source_blocks "
        "WHERE paper_revision_id = ? ORDER BY ordinal",
        [imported.paper.current_revision_id],
    )
    views = {block.block_id: block for block in imported.revision.blocks}
    assert len(views) == len(rows)
    for row in rows:
        view = views[row["id"]]
        assert view.kind == row["kind"]
        assert view.content == json.loads(row["block_json"])

    kinds = {block.kind for block in imported.revision.blocks}
    assert {"paragraph", "table", "formula", "image"} <= kinds
    # 合并表格：rowSpan/colSpan 占位保留；公式：latex 或 ommlXml 至少一个非空
    table = next(block for block in imported.revision.blocks if block.kind == "table")
    assert any(cell.get("colSpan", 1) > 1 for cell in table.content["cells"])
    formula = next(
        block for block in imported.revision.blocks if block.kind == "formula"
    )
    assert formula.content.get("latex") or formula.content.get("ommlXml")
    image = next(block for block in imported.revision.blocks if block.kind == "image")
    assert image.content["assetId"].startswith("blobs/")
    # 共享材料正文（共同材料）也可读
    material_body = next(
        block
        for block in imported.revision.blocks
        if block.kind == "paragraph"
        and MATERIAL_BODY in str(block.content.get("text") or "")
    )
    assert material_body.disposition == "shared_material"


def test_unassigned_content_survives_http_route(
    tmp_path: Path, harness: PapersHarness
) -> None:
    app, service = harness.create_app_with_service()
    imported = harness.import_docx(service, build_no_question_docx(tmp_path / "none.docx"))
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.get(
            f"/api/v1/papers/{imported.paper.paper_id}/revisions/"
            f"{imported.paper.current_revision_id}/content"
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"] == []
    assert body["blocks"]
    assert NEEDLE in json.dumps(body["blocks"], ensure_ascii=False)
    assert all(block["content"] for block in body["blocks"])


# --------------------------------------------------------------------------- 受控资产内容


def test_asset_content_route_reads_referenced_bytes(
    tmp_path: Path, harness: PapersHarness
) -> None:
    app, service = harness.create_app_with_service()
    imported = harness.import_docx(service, build_paper_docx(tmp_path / "sample.docx"))
    image = next(block for block in imported.revision.blocks if block.kind == "image")
    asset_id = image.content["assetId"]
    assert asset_id.startswith("blobs/")

    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.get(
            f"/api/v1/papers/{imported.paper.paper_id}/revisions/"
            f"{imported.paper.current_revision_id}/assets/{asset_id}/content"
        )
        assert response.status_code == 200, response.text
        assert response.content == PNG_BYTES
        assert response.headers["content-type"].startswith("image/png")

        # 形状合法但未被该修订引用的键 → 404（另取一个真实存在的 blob）
        unreferenced = harness.assets.store_original(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 32,
            media_type="image/png",
            original_name="unreferenced.png",
        )
        missing = client.get(
            f"/api/v1/papers/{imported.paper.paper_id}/revisions/"
            f"{imported.paper.current_revision_id}/assets/"
            f"{unreferenced.blob_key}/content"
        )
        assert missing.status_code == 404
        assert missing.json()["code"] == "PAPER_ASSET_NOT_FOUND"

        # 非法键（非受管形状）一律 422，且不读取任何文件
        for bad_key in ("blobs/" + "A" * 64, "blobs/abc", "notblobs/" + "a" * 64):
            rejected = client.get(
                f"/api/v1/papers/{imported.paper.paper_id}/revisions/"
                f"{imported.paper.current_revision_id}/assets/{bad_key}/content"
            )
            assert rejected.status_code == 422, (bad_key, rejected.text)
            assert rejected.json()["code"] == "INVALID_ASSET_KEY"


def test_asset_content_is_scoped_to_its_revision(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service = harness.service()
    imported = harness.import_docx(service, build_paper_docx(tmp_path / "a.docx"))
    paper_id = imported.paper.paper_id
    point = harness.add_point("K1", "二次函数")
    knowledge = {
        "16(1)": [point.point_id],
        "16(2)": [point.point_id],
        "17": [point.point_id],
        "18": [point.point_id],
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
    confirmed = service.confirm(
        paper_id,
        PaperConfirmRequest.model_validate(
            {"expectedRevision": 1, "submissionId": "scope-confirm"}
        ),
    )
    old_revision = confirmed.paper_revision_id
    # 改已确认卷 → 自动 fork 新草稿修订（旧修订逐字节不变）
    draft = service.patch_draft(
        paper_id, PaperDraftPatchRequest.model_validate({"expectedRevision": 2, "title": "补录后草稿"})
    )
    assert draft.state == "draft"
    assert draft.paper_revision_id != old_revision

    # 在新草稿修订里放一张只有它引用过的图片（补录路径的真实形状）
    added = harness.assets.store_original(
        b"\x89PNG\r\n\x1a\n" + b"\x01" * 32,
        media_type="image/png",
        original_name="supplement.png",
    )
    harness.raw_execute(
        "INSERT INTO paper_source_blocks (id, paper_revision_id, ordinal, kind, block_json, "
        "locator_json, disposition, item_id, exclude_reason) VALUES (?, ?, ?, 'image', ?, '{}', "
        "'excluded', NULL, '测试补录')",
        [
            f"{draft.paper_revision_id}:supplement-test",
            draft.paper_revision_id,
            max(block.ordinal for block in draft.blocks) + 1,
            json.dumps(
                {
                    "id": "supplement-test",
                    "kind": "image",
                    "assetId": added.blob_key,
                    "width": 8,
                    "height": 8,
                },
                ensure_ascii=False,
            ),
        ],
    )
    data, media_type = service.get_revision_asset_content(
        paper_id, draft.paper_revision_id, added.blob_key
    )
    assert data and media_type == "image/png"
    # 同一原卷的**旧修订**没有被该资产引用 → 404（不跨修订放行）
    with pytest.raises(AppError) as other_revision:
        service.get_revision_asset_content(paper_id, old_revision, added.blob_key)
    assert other_revision.value.code == "PAPER_ASSET_NOT_FOUND"
    assert other_revision.value.status_code == 404

    # 跨卷：B 卷修订 id + A 卷原卷 id → 404（修订不属于该原卷）
    other = harness.import_docx(service, build_paper_docx(tmp_path / "b.docx"))
    image = next(block for block in imported.revision.blocks if block.kind == "image")
    with pytest.raises(AppError) as foreign:
        service.get_revision_asset_content(
            other.paper.paper_id, old_revision, image.content["assetId"]
        )
    assert foreign.value.status_code == 404

    # 非法键：即使被引用也不可能通过（形状先拒绝，不落到文件系统）
    with pytest.raises(AppError) as invalid_key:
        service.get_revision_asset_content(
            paper_id, draft.paper_revision_id, "../../assets/png"
        )
    assert invalid_key.value.code == "INVALID_ASSET_KEY"
    assert invalid_key.value.status_code == 422
