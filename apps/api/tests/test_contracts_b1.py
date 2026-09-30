"""B1 契约测试：`error_details` 可用性、TableBlock 网格宽度、别名与驼峰序列化。

背景（B1 首败）：B0 冻结的 `ErrorDetails` 缺 `populate_by_name`，导致唯一 helper
`error_details(current_revision=…)` 直接抛 ValidationError；实现者（T10/T30-a）都踩到。
B1 给契约模型统一开启 `populate_by_name`（构造可用字段名，外部 JSON 仍按别名），
并给 `TableBlock` 增加可选 `columnCount`（行优先单元格序列的精确还原依据）。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts.knowledge import KnowledgePointView
from app.contracts.roster import RosterImportView
from app.contracts.teaching_loop import (
    ErrorIssue,
    RichContentV2,
    TableBlock,
    TableCell,
    error_details,
)


def test_error_details_helper_accepts_snake_case_and_emits_camel_case() -> None:
    details = error_details(
        current_revision=3,
        issues=[ErrorIssue(row=2, column="B", code="ROSTER_ROW_INVALID", message="重复行")],
        fields=["name"],
    )
    assert details == {
        "currentRevision": 3,
        "issues": [
            {
                "row": 2,
                "column": "B",
                "code": "ROSTER_ROW_INVALID",
                "message": "重复行",
            }
        ],
        "fields": ["name"],
    }
    assert error_details() == {}


def test_error_issue_accepts_alias_and_field_names() -> None:
    by_field = ErrorIssue(row=1, field="studentNo", code="X", message="m")
    by_alias = ErrorIssue(**{"row": 1, "field": "studentNo", "code": "X", "message": "m"})
    assert by_field == by_alias
    assert by_field.model_dump(by_alias=True) == {
        "row": 1,
        "column": None,
        "field": "studentNo",
        "code": "X",
        "message": "m",
    }
    with pytest.raises(ValidationError):
        ErrorIssue(row=1, code="X", message="m", unexpected=1)


def test_knowledge_point_view_builds_from_field_names_and_dumps_camel() -> None:
    view = KnowledgePointView(
        id="kp-1",
        subject_id="math",
        code="M1",
        name="函数单调性",
        revision=2,
        revision_id="rev-1",
        version=1,
        created_at="2026-09-30T00:00:00Z",
    )
    dumped = view.model_dump(by_alias=True)
    assert dumped["subjectId"] == "math"
    assert dumped["revisionId"] == "rev-1"
    assert dumped["createdAt"] == "2026-09-30T00:00:00Z"
    assert dumped["status"] == "active"
    assert dumped["parentId"] is None
    assert dumped["aliases"] == []


def test_roster_import_view_alias_round_trip() -> None:
    payload = {
        "importId": "imp-1",
        "classId": "c1",
        "className": "高一(1)班",
        "state": "reviewing",
        "revision": 0,
        "fileAsset": {
            "assetId": "a1",
            "kind": "roster",
            "blobKey": "blobs/" + "a" * 64,
            "sha256": "a" * 64,
            "mediaType": "text/csv",
            "byteSize": 12,
            "originalName": "名单.csv",
        },
        "headers": ["学号", "姓名"],
        "mapping": {"studentNo": "学号", "name": "姓名"},
        "warnings": [],
        "issues": [],
        "rows": [],
        "createdAt": "2026-09-30T00:00:00Z",
        "updatedAt": "2026-09-30T00:00:00Z",
    }
    view = RosterImportView.model_validate(payload)
    assert view.model_dump(by_alias=True) == payload


def test_table_block_column_count_is_optional_and_validated() -> None:
    cells = [
        TableCell(text="A", isHeader=True),
        TableCell(text="B", isHeader=True),
        TableCell(text="1", rowSpan=2),
        TableCell(text="2"),
    ]
    without = TableBlock.model_validate({"id": "t1", "kind": "table", "cells": [
        cell.model_dump(by_alias=True) for cell in cells
    ]})
    assert without.column_count is None
    with_count = TableBlock.model_validate(
        {
            "id": "t1",
            "kind": "table",
            "cells": [cell.model_dump(by_alias=True) for cell in cells],
            "columnCount": 2,
        }
    )
    assert with_count.column_count == 2
    with pytest.raises(ValidationError):
        TableBlock.model_validate(
            {"id": "t1", "kind": "table", "cells": [], "columnCount": 0}
        )


def test_rich_content_v2_round_trip_with_table_grid() -> None:
    payload = {
        "version": 2,
        "sharedMaterials": [],
        "stemBlocks": [
            {
                "id": "t1",
                "kind": "table",
                "cells": [
                    {"text": "A", "isHeader": True, "rowSpan": 1, "colSpan": 1},
                    {"text": "B", "isHeader": True, "rowSpan": 1, "colSpan": 1},
                ],
                "columnCount": 2,
            }
        ],
        "optionBlocks": {},
        "answerBlocks": [],
        "explanationBlocks": [],
        "assets": [],
        "origin": {
            "originalAssetId": "a1",
            "originalSha256": "b" * 64,
            "sourceLocator": {"blockStart": 1},
        },
    }
    rich = RichContentV2.model_validate(payload)
    assert rich.model_dump(by_alias=True) == payload
