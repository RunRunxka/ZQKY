"""T40 原卷导入验收（B2 / A3 之一）：块/定位/图片/OMML/未知对象与规则拆题。

全部用 ``tmp_path`` 隔离的临时库与程序化构造的 DOCX（不读正式数据目录、不联网、
不碰正式凭证）；图片 sha256 与 OMML 逐字节断言都以原件为参照。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from tests.papers_support import (
    PNG_BYTES,
    SAMPLE_TOTAL_UNITS,
    SUBJECT_ID,
    PapersHarness,
    broken_docx_bytes,
    build_empty_docx,
    build_no_question_docx,
    build_paper_docx,
    install_papers_router,
)
from tests.rich_content_support import source_omml_strings


@pytest.fixture()
def harness(tmp_path: Path) -> PapersHarness:
    return PapersHarness(tmp_path)


def test_import_persists_blocks_in_order_with_kinds_and_locators(
    tmp_path: Path, harness: PapersHarness
) -> None:
    docx = build_paper_docx(tmp_path / "sample.docx")
    view = harness.import_docx(harness.service(), docx)

    assert view.paper.subject_id == SUBJECT_ID
    assert view.paper.current_state == "draft"
    assert view.paper.version == 1
    assert view.revision.version == 1
    assert view.revision.state == "draft"
    assert view.revision.total_score_units == SAMPLE_TOTAL_UNITS
    assert view.revision.total_score == "21"

    blocks = view.revision.blocks
    assert len(blocks) == 13
    assert [block.ordinal for block in blocks] == list(range(1, 14))
    assert [block.kind for block in blocks] == [
        "paragraph",
        "paragraph",
        "paragraph",
        "image",
        "table",
        "paragraph",
        "paragraph",
        "paragraph",
        "paragraph",
        "formula",
        "paragraph",
        "formula",
        "paragraph",
    ]
    # 定位来自解析器（1 基块序号），每个块都有 blockStart
    assert all(isinstance(block.locator.get("blockStart"), int) for block in blocks)
    starts = [block.locator["blockStart"] for block in blocks]
    assert starts == sorted(starts)

    # 表格的网格宽度与行数在 locator 里保留（来源核对用）
    table = next(block for block in blocks if block.kind == "table")
    assert table.locator["tableColumns"] == 2
    assert table.locator["tableRows"] == 2

    # 原件资产与修订来源
    assets = harness.raw_rows("SELECT * FROM file_assets WHERE kind = 'paper'")
    assert len(assets) == 1
    assert assets[0]["sha256"] == hashlib.sha256(docx.read_bytes()).hexdigest()
    assert assets[0]["original_name"] == "sample.docx"
    revision_row = harness.raw_rows("SELECT * FROM paper_revisions")[0]
    assert revision_row["source_file_id"] == assets[0]["id"]
    assert revision_row["total_score_units"] == SAMPLE_TOTAL_UNITS


def test_import_image_block_keeps_real_bytes_and_sha256(
    tmp_path: Path, harness: PapersHarness
) -> None:
    docx = build_paper_docx(tmp_path / "sample.docx")
    view = harness.import_docx(harness.service(), docx)

    image = next(block for block in view.revision.blocks if block.kind == "image")
    payload = harness.raw_rows(
        "SELECT block_json FROM paper_source_blocks WHERE id = ?", [image.block_id]
    )[0]["block_json"]
    assert hashlib.sha256(PNG_BYTES).hexdigest() in payload
    # 图片块引用的受管键必须真实存在，且读回字节就是原件里的 PNG
    import json

    block = json.loads(payload)
    blob_key = block["assetId"]
    assert blob_key == f"blobs/{hashlib.sha256(PNG_BYTES).hexdigest()}"
    assert harness.assets.read(blob_key) == PNG_BYTES
    assert block["width"] == 192 and block["height"] == 96


def test_import_omml_is_preserved_byte_for_byte(
    tmp_path: Path, harness: PapersHarness
) -> None:
    import json

    docx = build_paper_docx(tmp_path / "sample.docx")
    view = harness.import_docx(harness.service(), docx)
    stored = [
        json.loads(
            harness.raw_rows(
                "SELECT block_json FROM paper_source_blocks WHERE id = ?", [block.block_id]
            )[0]["block_json"]
        )["ommlXml"]
        for block in view.revision.blocks
        if block.kind == "formula"
    ]
    source = source_omml_strings(docx)
    assert len(stored) == len(source) == 2
    assert stored == source


def test_import_unknown_object_becomes_blocking_issue_with_locator(
    tmp_path: Path, harness: PapersHarness
) -> None:
    docx = build_paper_docx(tmp_path / "sample.docx", with_unknown_object=True)
    view = harness.import_docx(harness.service(), docx)

    unknown = [issue for issue in view.revision.issues if issue.code == "UNSUPPORTED_OBJECT"]
    assert unknown, "未知对象必须产生可见问题"
    assert all(issue.severity == "blocking" for issue in unknown)
    assert any(issue.locator.get("blockStart") for issue in unknown)
    # 问题定位可以没有 block_id（本题对象段没有产出任何块）
    assert any(issue.block_id is None for issue in unknown)
    # 未知对象不影响其余内容解析
    assert view.revision.total_score_units == SAMPLE_TOTAL_UNITS
    assert harness.count("paper_issues", "severity = 'blocking' AND status = 'open'") == len(
        unknown
    )


def test_import_splits_parent_child_and_extracts_scores(
    tmp_path: Path, harness: PapersHarness
) -> None:
    docx = build_paper_docx(tmp_path / "sample.docx")
    view = harness.import_docx(harness.service(), docx)

    by_no = {item.question_no: item for item in view.revision.items}
    assert list(by_no) == ["16", "16(1)", "16(2)", "17", "18"]
    parent = by_no["16"]
    assert parent.is_scored is False
    assert parent.max_score is None  # 容器不分值（分值由小题表达）
    assert by_no["16(1)"].parent_item_id == parent.item_id
    assert by_no["16(2)"].parent_item_id == parent.item_id
    assert (by_no["16(1)"].is_scored, by_no["16(1)"].max_score) == (True, "4")
    assert (by_no["16(2)"].is_scored, by_no["16(2)"].max_score) == (True, "8")
    assert (by_no["17"].is_scored, by_no["17"].max_score) == (True, "6")
    assert (by_no["18"].is_scored, by_no["18"].max_score) == (True, "3")
    assert by_no["17"].content["version"] == 2
    assert by_no["17"].content["origin"]["originalSha256"] == hashlib.sha256(
        docx.read_bytes()
    ).hexdigest()
    # 计分叶子合计 = 草稿总分
    assert view.revision.total_score_units == SAMPLE_TOTAL_UNITS


def test_import_bare_child_numbers_without_scores_are_blocking(
    tmp_path: Path, harness: PapersHarness
) -> None:
    docx = build_paper_docx(tmp_path / "sample.docx", with_unscored_children=True)
    view = harness.import_docx(harness.service(), docx)

    by_no = {item.question_no: item for item in view.revision.items}
    assert "19" in by_no and "19(1)" in by_no and "19(2)" in by_no
    assert by_no["19"].is_scored is False  # 有子题的父容器不计分
    assert by_no["19(1)"].parent_item_id == by_no["19"].item_id
    assert by_no["19(1)"].is_scored is False and by_no["19(1)"].max_score is None
    missing = [issue for issue in view.revision.issues if issue.code == "ITEM_SCORE_MISSING"]
    assert {issue.message.split()[1] for issue in missing} == {"19(1)", "19(2)"}
    assert all(issue.severity == "blocking" for issue in missing)
    assert view.revision.total_score_units == SAMPLE_TOTAL_UNITS  # 缺分题不计入


def test_import_standalone_child_owns_number_block_and_following_body(
    tmp_path: Path, harness: PapersHarness
) -> None:
    """LOOP-02：独立成段的 ``(1)`` 子题必须拿到自己的题号块与后续正文，不能留在父容器上。"""
    docx = build_paper_docx(tmp_path / "sample.docx", with_standalone_child_text=True)
    view = harness.import_docx(harness.service(), docx)

    by_no = {item.question_no: item for item in view.revision.items}
    assert by_no["20"].is_scored is False  # 有子题的父容器不计分
    assert (by_no["20(1)"].is_scored, by_no["20(1)"].max_score) == (True, "4")
    assert (by_no["20(2)"].is_scored, by_no["20(2)"].max_score) == (True, "6")
    # 子题号块与后续正文都在子题自己的题干里
    first = "".join(
        block["text"] for block in by_no["20(1)"].content["stemBlocks"] if "text" in block
    )
    assert "（1）（4 分）求第一四分位数。" in first
    assert "解：先排序再取中位数。" in first
    second = "".join(
        block["text"] for block in by_no["20(2)"].content["stemBlocks"] if "text" in block
    )
    assert "（2）（6 分）求中位数。" in second
    # 父容器不再吸收子题正文
    parent_text = "".join(
        block["text"] for block in by_no["20"].content["stemBlocks"] if "text" in block
    )
    assert "第一四分位数" not in parent_text


def test_import_section_heading_is_boundary_not_previous_item_score(
    tmp_path: Path, harness: PapersHarness
) -> None:
    """LOOP-01：分节标题是结构边界——节合计不得成为上一题满分，标题也不进上一题题干。"""
    docx = build_paper_docx(tmp_path / "sample.docx", with_section_heading=True)
    view = harness.import_docx(harness.service(), docx)

    by_no = {item.question_no: item for item in view.revision.items}
    # 样本里最后一个叶子是 18（3 分）；分节标题的「共18分」不得被它吸收
    assert by_no["18"].max_score == "3"
    assert all(item.max_score != "18" for item in view.revision.items)
    heading = [
        block
        for block in view.revision.blocks
        if block.disposition != "item"
        and "多项选择题" in str(block.content.get("text", ""))
    ]
    assert len(heading) == 1
    assert heading[0].disposition == "unassigned"  # 由教师指定归属或排除，不静默吞掉
    warnings = [issue for issue in view.revision.issues if issue.code == "PAPER_BLOCK_UNASSIGNED"]
    assert any(issue.block_id == heading[0].block_id for issue in warnings)
    stem = "".join(
        block["text"] for block in by_no["18"].content["stemBlocks"] if "text" in block
    )
    assert "多项选择题" not in stem
    assert view.revision.total_score_units == SAMPLE_TOTAL_UNITS


def test_import_duplicate_question_number_records_blocking_issue(
    tmp_path: Path, harness: PapersHarness
) -> None:
    docx = build_paper_docx(tmp_path / "sample.docx", with_duplicate_number=True)
    view = harness.import_docx(harness.service(), docx)

    numbers = [item.question_no for item in view.revision.items]
    assert numbers.count("16") == 1  # 不新建重复行（DB 唯一约束是权威）
    duplicates = [
        issue for issue in view.revision.issues if issue.code == "ITEM_QUESTION_NO_DUPLICATE"
    ]
    assert len(duplicates) == 1
    assert duplicates[0].severity == "blocking"
    # 重复题号段仍然归属该题（内容不丢）
    assert view.revision.total_score_units == SAMPLE_TOTAL_UNITS


def test_import_assigns_every_block_and_keeps_materials_shared(
    tmp_path: Path, harness: PapersHarness
) -> None:
    docx = build_paper_docx(tmp_path / "sample.docx")
    view = harness.import_docx(harness.service(), docx)

    item_ids = {item.item_id for item in view.revision.items}
    by_no = {item.question_no: item.item_id for item in view.revision.items}
    assert all(
        block.disposition in {"item", "shared_material", "excluded", "unassigned"}
        for block in view.revision.blocks
    )
    assert all(
        block.item_id in item_ids for block in view.revision.blocks if block.disposition == "item"
    )
    # 首个题号之前的块（标题/材料/图片/表格）是共享材料
    leading = [block for block in view.revision.blocks if block.ordinal <= 5]
    assert all(block.disposition == "shared_material" for block in leading)
    # 16(1)/16(2) 的题号段归属各自小题
    number_blocks = {
        block.ordinal: block for block in view.revision.blocks if block.disposition == "item"
    }
    assert number_blocks[7].item_id == by_no["16(1)"]
    assert number_blocks[8].item_id == by_no["16(2)"]
    # 题干内容里保留了共享材料（前导材料对所有题可见）
    leaf = next(item for item in view.revision.items if item.question_no == "16(1)")
    assert leaf.content["sharedMaterials"]
    # 问题清单里的 block_id 都能对应到真实块（或明确为 None）
    block_ids = {block.block_id for block in view.revision.blocks}
    assert all(issue.block_id in block_ids for issue in view.revision.issues if issue.block_id)


def test_import_rejects_non_docx_and_broken_files(
    tmp_path: Path, harness: PapersHarness
) -> None:
    service = harness.service()
    with pytest.raises(AppError) as non_docx:
        service.create_import(
            file_name="sample.pdf",
            content=b"%PDF-1.4",
            media_type="application/pdf",
            subject_id=SUBJECT_ID,
        )
    assert non_docx.value.code == "UNSUPPORTED_DOCUMENT_FORMAT"
    assert non_docx.value.status_code == 422

    with pytest.raises(AppError) as broken:
        service.create_import(
            file_name="broken.docx",
            content=broken_docx_bytes(),
            media_type="application/octet-stream",
            subject_id=SUBJECT_ID,
        )
    assert broken.value.code == "PAPER_IMPORT_PARSE_FAILED"

    empty = build_empty_docx(tmp_path / "empty.docx")
    with pytest.raises(AppError) as no_blocks:
        harness.import_docx(service, empty)
    assert no_blocks.value.code == "PAPER_IMPORT_PARSE_FAILED"
    # 失败不留下任何业务行（资产表也不登记）
    assert harness.count("papers") == 0
    assert harness.count("paper_revisions") == 0
    assert harness.count("file_assets") == 0


def test_import_without_question_numbers_records_no_items_issue(
    tmp_path: Path, harness: PapersHarness
) -> None:
    docx = build_no_question_docx(tmp_path / "no-number.docx")
    view = harness.import_docx(harness.service(), docx)

    assert view.revision.items == []
    assert view.revision.total_score_units == 0
    codes = [issue.code for issue in view.revision.issues if issue.severity == "blocking"]
    assert "NO_ITEMS_DETECTED" in codes
    # 没有题号时块无处归属：保持 unassigned 并逐块可见（不猜）
    assert all(
        block.disposition in {"unassigned", "shared_material"}
        for block in view.revision.blocks
    )
    assert any(
        issue.code == "PAPER_BLOCK_UNASSIGNED" for issue in view.revision.issues
    )


def test_import_same_document_twice_is_isolated(tmp_path: Path, harness: PapersHarness) -> None:
    docx = build_paper_docx(tmp_path / "sample.docx")
    service = harness.service()
    first = harness.import_docx(service, docx)
    second = harness.import_docx(service, docx, title="第二份")

    assert first.paper.paper_id != second.paper.paper_id
    assert {block.block_id for block in first.revision.blocks}.isdisjoint(
        {block.block_id for block in second.revision.blocks}
    )
    assert harness.count("papers") == 2
    assert harness.count("paper_source_blocks") == 26


def test_import_over_http_multipart(tmp_path: Path) -> None:
    """路由层：multipart 解析 + 201 结果 + 列表/详情/修订内容读取。"""
    harness = PapersHarness(tmp_path)
    app, _service = harness.create_app_with_service(provider=None)
    docx = build_paper_docx(tmp_path / "sample.docx")
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.post(
            "/api/v1/paper-imports",
            files={
                "file": (
                    "sample.docx",
                    docx.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"subjectId": SUBJECT_ID, "title": "接口导入"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["paper"]["title"] == "接口导入"
        assert body["revision"]["totalScoreUnits"] == SAMPLE_TOTAL_UNITS
        paper_id = body["paper"]["paperId"]
        revision_id = body["revision"]["paperRevisionId"]

        listing = client.get("/api/v1/papers", params={"subjectId": SUBJECT_ID})
        assert listing.status_code == 200
        assert listing.json()["total"] == 1

        detail = client.get(f"/api/v1/papers/{paper_id}")
        assert detail.status_code == 200
        assert detail.json()["scoredLeafCount"] == 4

        content = client.get(f"/api/v1/papers/{paper_id}/revisions/{revision_id}/content")
        assert content.status_code == 200
        assert len(content.json()["blocks"]) == 13

        missing = client.get("/api/v1/papers/nope")
        assert missing.status_code == 404
        assert missing.json()["code"] == "PAPER_NOT_FOUND"

        bad = client.post(
            "/api/v1/paper-imports",
            files={"file": ("sample.pdf", b"%PDF-1.4", "application/pdf")},
            data={"subjectId": SUBJECT_ID},
        )
        assert bad.status_code == 422
        assert bad.json()["code"] == "UNSUPPORTED_DOCUMENT_FORMAT"


def test_import_requires_subject_id_over_http(tmp_path: Path) -> None:
    harness = PapersHarness(tmp_path)
    app, _service = harness.create_app_with_service(provider=None)
    install_papers_router(app)
    docx = build_paper_docx(tmp_path / "sample.docx")
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.post(
            "/api/v1/paper-imports",
            files={"file": ("sample.docx", docx.read_bytes(), "application/octet-stream")},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_REQUEST"
