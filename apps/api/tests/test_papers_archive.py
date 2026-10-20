"""原卷归档功能移除后的语义（B3，2026-10-20 用户裁定「全局移除归档，只留删除」）。

覆盖（真 HTTP API + 真教学库）：

- ``POST /papers/{id}/archive`` 与 ``/restore`` 不再存在（404，路由已移除）；
- 列表不再有 ``status`` 过滤（``status=active/archived`` 都按 422 拒绝）；
- ``DELETE /papers/{id}`` 仍是唯一清理出口（引用守卫语义归 ``test_r10_delete_semantics``）；
- 残留 archived 行（旧库）按只读兜底拒绝编辑/确认，详情仍可读（归一化前）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.papers import PAPER_NOT_EDITABLE
from tests.assessments_support import (
    AssessmentsHarness,
    items_payload_from_json,
)


@pytest.fixture()
def harness(tmp_path: Path):
    with AssessmentsHarness(tmp_path) as running:
        yield running


def test_archive_and_restore_routes_are_gone(harness: AssessmentsHarness) -> None:
    draft = harness.import_draft_paper(tag="pa1", title="归档端点应不存在")

    archived = harness.client.post(
        f"/api/v1/papers/{draft['paperId']}/archive",
        json={"expectedRevision": draft["revision"]},
    )
    assert archived.status_code == 404, archived.text
    restored = harness.client.post(
        f"/api/v1/papers/{draft['paperId']}/restore",
        json={"expectedRevision": draft["revision"]},
    )
    assert restored.status_code == 404, restored.text
    # 数据未动
    detail = harness.client.get(f"/api/v1/papers/{draft['paperId']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "active"


def test_paper_list_has_no_status_filter(harness: AssessmentsHarness) -> None:
    paper = harness.create_confirmed_paper(tag="pa2")
    listed = harness.client.get("/api/v1/papers")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["paperId"] == paper.paper_id
    # status 过滤参数已移除：传入被忽略（FastAPI 不再声明该参数），返回全部
    for value in ("active", "archived"):
        filtered = harness.client.get("/api/v1/papers", params={"status": value})
        assert filtered.status_code == 200, (value, filtered.text)
        assert filtered.json()["total"] == 1


def test_stale_archived_row_stays_readable_but_not_editable(
    harness: AssessmentsHarness,
) -> None:
    """旧库残留 archived 行（模拟）：详情可读、编辑/确认被兜底拒绝、删除仍可用。"""
    paper = harness.import_draft_paper(tag="pa3", title="残留归档卷")
    harness.raw_execute(
        "UPDATE papers SET status = 'archived' WHERE id = ?", [paper["paperId"]]
    )
    detail = harness.client.get(f"/api/v1/papers/{paper['paperId']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "archived"
    assert harness.client.get("/api/v1/papers").json()["total"] == 1

    content = harness.client.get(
        f"/api/v1/papers/{paper['paperId']}/revisions/{paper['paperRevisionId']}/content"
    ).json()
    patch = harness.client.patch(
        f"/api/v1/papers/{paper['paperId']}/draft",
        json={
            "expectedRevision": paper["revision"],
            "items": items_payload_from_json(content["items"], knowledge={}),
        },
    )
    assert patch.status_code == 409, patch.text
    assert patch.json()["code"] == PAPER_NOT_EDITABLE

    deleted = harness.client.delete(
        f"/api/v1/papers/{paper['paperId']}",
        params={"expectedRevision": paper["revision"]},
    )
    assert deleted.status_code == 200, deleted.text
    assert harness.client.get("/api/v1/papers").json()["total"] == 0
